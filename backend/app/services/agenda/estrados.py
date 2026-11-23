"""Vigilancia de estrados digitales (primero: TRIJAEM, Tribunal de Justicia Administrativa del Estado de México).

Cómo funciona
- El despacho marca qué asuntos de su agenda quiere vigilar y con qué número de expediente los publica el tribunal.
- Dos formas de detectar publicaciones:
  1. Automática: si Nomira tiene configurada la dirección de consulta del tribunal (TRIJAEM_ESTRADOS_API), un proceso
     en segundo plano revisa cada expediente unas pocas veces al día, en horario hábil y sin saturar al tribunal.
  2. Cotejo: el abogado pega el texto (o sube el PDF) de la lista del día y Nomira busca ahí todos los expedientes
     que el despacho vigila. Funciona siempre, aunque la consulta automática no esté configurada o falle.
- Cada publicación se guarda una sola vez (huella única) y genera aviso en Nomira y, si hay correo, por correo.

Límites que se dicen al usuario: Nomira no sustituye la consulta oficial. La fecha en que «surte efectos» es una
estimación (día hábil siguiente según el calendario del asunto) que el abogado debe confirmar.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models as m
from ...config import ajustes
from .. import correo, envios, modulos
from ..plantillas_correo import _base, _boton, _url, escape, fecha_larga
from . import base

log = logging.getLogger("nomira.estrados")

FUENTES = {"trijaem": {"nombre": "TRIJAEM · Estrados digitales", "tribunal": "Tribunal de Justicia Administrativa del Estado de México",
                       "consulta": "https://trijaem.gob.mx/servicios/Estrados#!/",
                       "efectos": "Según el propio TRIJAEM, las notificaciones por estrados surten efectos a partir del día siguiente de su publicación."}}
REVISAR_CADA_HORAS = 3  # cada expediente se consulta como máximo cada 3 horas
HORARIO = (7, 21)  # solo de 7:00 a 21:00, hora del centro de México, de lunes a viernes
PAUSA_SEG = 1.5  # entre una consulta y otra, para no saturar al tribunal
MAX_POR_RONDA = 150
EXPEDIENTE = re.compile(r"(?<![\d/])0*(\d{1,6})\s*/\s*(\d{4})(?!\d)")


class SinConfigurar(Exception):
    pass


class FalloConsulta(Exception):
    pass


@dataclass
class Hallazgo:
    fecha: date
    descripcion: str
    sala: str | None = None
    tipo: str | None = None
    enlace: str | None = None


# ------------------------------------------------------------------ expedientes

def clave_expediente(texto: str | None) -> tuple[int, int] | None:
    """«JA-0123/2026», «123 / 2026» y «123/2026» son el mismo expediente: (123, 2026)."""
    x = EXPEDIENTE.search(texto or "")
    return (int(x.group(1)), int(x.group(2))) if x else None


def normalizar_expediente(texto: str) -> str:
    return re.sub(r"\s+", "", (texto or "").upper())[:80]


def _plano(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip().lower()


def misma_sala(vigilada: str | None, otra: str | None) -> bool:
    """Si alguna de las dos no dice sala, no se descarta; si ambas la dicen, una debe contener a la otra."""
    a, b = _plano(vigilada or ""), _plano(otra or "")
    return not a or not b or a in b or b in a


def huella(h: Hallazgo) -> str:
    base_txt = "|".join([h.fecha.isoformat(), _plano(h.tipo or ""), _plano(h.descripcion)[:600]])
    return hashlib.sha256(base_txt.encode()).hexdigest()


# ------------------------------------------------------------------ cotejo de una lista pegada o PDF

def cotejar_texto(texto: str, fecha: date, vigilancias: list[m.AgVigilancia], sala: str | None = None) -> dict[int, list[Hallazgo]]:
    """Busca en la lista del día los expedientes vigilados. Devuelve {vigilancia_id: [hallazgos]}."""
    lineas = [ln.strip() for ln in (texto or "").splitlines()]
    por_clave: dict[tuple[int, int], list[m.AgVigilancia]] = {}
    for v in vigilancias:
        k = clave_expediente(v.expediente)
        if k and v.activa and misma_sala(v.sala, sala):
            por_clave.setdefault(k, []).append(v)
    r: dict[int, list[Hallazgo]] = {}
    for i, ln in enumerate(lineas):
        for x in EXPEDIENTE.finditer(ln):
            k = (int(x.group(1)), int(x.group(2)))
            for v in por_clave.get(k, []):
                # la línea donde aparece y las siguientes (hasta 2) traen la síntesis, sin pasar al siguiente expediente
                partes = [ln]
                for t in lineas[i + 1:i + 3]:
                    if not t or EXPEDIENTE.search(t):
                        break
                    partes.append(t)
                contexto = " ".join(partes)[:1500]
                h = Hallazgo(fecha=fecha, descripcion=contexto, sala=sala or v.sala, tipo="Publicación en lista")
                if all(huella(h) != huella(o) for o in r.get(v.id, [])):
                    r.setdefault(v.id, []).append(h)
    return r


def texto_de_pdf(contenido: bytes, max_paginas: int = 200) -> str:
    import pymupdf
    with pymupdf.open(stream=contenido, filetype="pdf") as doc:
        return "\n".join(doc[i].get_text() for i in range(min(len(doc), max_paginas)))


# ------------------------------------------------------------------ consulta automática (conector)

CAMPOS = {
    "fecha": ("fechaPublicacion", "fecha_publicacion", "fechaPublicacionEstrados", "fechaAcuerdo", "fecha"),
    "descripcion": ("sintesis", "síntesis", "descripcion", "acuerdo", "contenido", "texto", "resumen", "observaciones"),
    "sala": ("sala", "nombreSala", "seccion", "ponencia"),
    "tipo": ("tipo", "tipoAcuerdo", "tipoNotificacion", "tipoDocumento", "actuacion"),
    "enlace": ("url", "liga", "enlace", "pdf", "archivo", "documento"),
    "expediente": ("expediente", "numeroExpediente", "noExpediente", "num_expediente"),
}


def _campo(fila: dict, nombre: str):
    bajas = {str(k).lower(): v for k, v in fila.items()}
    for c in CAMPOS[nombre]:
        if bajas.get(c.lower()) not in (None, ""):
            return bajas[c.lower()]
    return None


def _fecha(v) -> date | None:
    if v is None:
        return None
    s = str(v).strip()
    for patron, orden in ((r"(\d{4})-(\d{2})-(\d{2})", "amd"), (r"(\d{1,2})/(\d{1,2})/(\d{4})", "dma"), (r"(\d{1,2})-(\d{1,2})-(\d{4})", "dma")):
        x = re.search(patron, s)
        if x:
            a, b, c = (int(g) for g in x.groups())
            try:
                return date(a, b, c) if orden == "amd" else date(c, b, a)
            except ValueError:
                return None
    return None


def _filas(datos) -> list[dict]:
    if isinstance(datos, list):
        return [x for x in datos if isinstance(x, dict)]
    if isinstance(datos, dict):
        for v in datos.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return [x for x in v if isinstance(x, dict)]
        return [datos] if _campo(datos, "descripcion") else []
    return []


def interpretar(datos, v: m.AgVigilancia) -> list[Hallazgo]:
    """Convierte la respuesta del tribunal en hallazgos. Tolera nombres de campo distintos y descarta lo que
    no corresponde al expediente o a la sala vigilados."""
    k = clave_expediente(v.expediente)
    r = []
    for f in _filas(datos):
        exp = _campo(f, "expediente")
        if exp and k and clave_expediente(str(exp)) != k:
            continue
        sala = _campo(f, "sala")
        if not misma_sala(v.sala, str(sala) if sala else None):
            continue
        fecha = _fecha(_campo(f, "fecha"))
        desc = _campo(f, "descripcion")
        if not fecha or not desc:
            continue
        enlace = _campo(f, "enlace")
        enlace = str(enlace) if enlace and str(enlace).startswith("https://") else None
        r.append(Hallazgo(fecha=fecha, descripcion=re.sub(r"\s+", " ", str(desc)).strip()[:2000],
                          sala=str(sala)[:120] if sala else v.sala, tipo=str(_campo(f, "tipo") or "")[:80] or None, enlace=enlace))
    return r


def configurado(fuente: str = "trijaem") -> bool:
    return fuente == "trijaem" and "{expediente}" in (ajustes().trijaem_estrados_api or "")


def consultar(v: m.AgVigilancia, cliente: httpx.Client | None = None) -> list[Hallazgo]:
    plantilla = ajustes().trijaem_estrados_api or ""
    if v.fuente != "trijaem" or "{expediente}" not in plantilla:
        raise SinConfigurar("La consulta automática de este tribunal aún no está configurada en Nomira.")
    if not plantilla.startswith("https://trijaem.gob.mx/"):
        raise SinConfigurar("La dirección de consulta configurada no pertenece al TRIJAEM.")
    url = plantilla.replace("{expediente}", quote(v.expediente, safe="")).replace("{sala}", quote(v.sala or "", safe=""))
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=20, follow_redirects=False, headers={"User-Agent": "Nomira/1.0 (+https://nomirasoft.com)", "Accept": "application/json"})
    try:
        r = cliente.get(url)
        if r.status_code != 200:
            raise FalloConsulta(f"El tribunal respondió {r.status_code}.")
        try:
            datos = r.json()
        except ValueError:
            raise FalloConsulta("El tribunal respondió en un formato que Nomira no reconoce.")
        return interpretar(datos, v)
    except httpx.HTTPError as e:
        raise FalloConsulta(f"No se pudo conectar con el tribunal ({type(e).__name__}).")
    finally:
        if propio:
            cliente.close()


# ------------------------------------------------------------------ guardar y avisar

def surte_efectos(db: Session, v: m.AgVigilancia, publicada: date) -> date:
    """Estimación: día hábil siguiente a la publicación, según el calendario del asunto."""
    a = db.get(m.AgAsunto, v.asunto_id)
    cal_id = (a.calendario_id if a else None) or base.config(db, v.organizacion_id).calendario_id
    return base.calendario(db, cal_id, v.organizacion_id).siguiente_habil(publicada)


def guardar(db: Session, v: m.AgVigilancia, hallazgos: list[Hallazgo], origen: str) -> list[m.AgPublicacion]:
    nuevas = []
    for h in hallazgos:
        p = m.AgPublicacion(organizacion_id=v.organizacion_id, vigilancia_id=v.id, huella=huella(h), fecha_publicacion=h.fecha,
                            sala=h.sala, tipo=h.tipo, descripcion=h.descripcion[:2000], enlace=h.enlace, origen=origen)
        try:
            with db.begin_nested():
                db.add(p)
                db.flush()
            nuevas.append(p)
        except IntegrityError:
            pass
    return nuevas


def destinatarios(db: Session, v: m.AgVigilancia) -> list[m.Usuario]:
    """Responsable del asunto y quien activó la vigilancia; si no hay ninguno activo, quienes supervisan."""
    a = db.get(m.AgAsunto, v.asunto_id)
    ids = [x for x in ((a.responsable_id if a else None), v.creado_por_id) if x]
    us = list(db.scalars(select(m.Usuario).where(m.Usuario.id.in_(ids), m.Usuario.organizacion_id == v.organizacion_id,
                                                 m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None)))) if ids else []
    return us or base.supervisores(db, v.organizacion_id)


def avisar(db: Session, pubs: list[m.AgPublicacion], excepto: int | None = None) -> int:
    """Correo a los destinatarios de cada vigilancia (si el correo está configurado y no lo desactivaron)."""
    if not pubs or not correo.configurado():
        return 0
    por_usuario: dict[int, tuple[m.Usuario, list[m.AgPublicacion]]] = {}
    for p in pubs:
        v = db.get(m.AgVigilancia, p.vigilancia_id)
        for u in destinatarios(db, v):
            if u.id != excepto:
                por_usuario.setdefault(u.id, (u, []))[1].append(p)
    enviados = 0
    for uid, (u, lista) in por_usuario.items():
        pref = db.scalar(select(m.AgPreferencia).where(m.AgPreferencia.usuario_id == uid))
        if pref and not pref.alertas_correo:
            continue
        asunto, html, texto = correo_publicaciones(db, u, lista)
        llave = "estrados:" + hashlib.sha256(f"{uid}:{sorted(p.id for p in lista)}".encode()).hexdigest()[:40]
        r = envios.registrar_y_enviar(db, "agenda_estrados", [u.email], asunto, html, texto, organizacion_id=u.organizacion_id, llave=llave)
        enviados += bool(r and r.estado == "enviado")
    return enviados


def correo_publicaciones(db: Session, u: m.Usuario, pubs: list[m.AgPublicacion]) -> tuple[str, str, str]:
    n = len(pubs)
    asunto = f"📜 {n} publicación(es) nueva(s) en estrados de sus asuntos" if n > 1 else "📜 Se publicó algo en estrados de uno de sus asuntos"
    html_items, txt_items = [], []
    for p in pubs:
        v = db.get(m.AgVigilancia, p.vigilancia_id)
        a = db.get(m.AgAsunto, v.asunto_id)
        ef = surte_efectos(db, v, p.fecha_publicacion)
        quien = f"{a.titulo} · Exp. {v.expediente}" if a else f"Exp. {v.expediente}"
        html_items.append(f'<li style="margin:0 0 10px"><b>{escape(quien)}</b><br><span style="color:#64748b;font-size:14px">'
                          f'Publicado el {escape(fecha_larga(p.fecha_publicacion))}{escape(" · " + p.sala if p.sala else "")} · '
                          f'surtiría efectos el {escape(fecha_larga(ef))} (estimado)</span></li>')
        txt_items.append(f"- {quien}: publicado el {fecha_larga(p.fecha_publicacion)}; surtiría efectos el {fecha_larga(ef)} (estimado)")
    html = _base(asunto, f"""<h1 style="margin:0 0 12px;font-size:22px;color:#123048">Hola, {escape(u.nombre.split()[0])}</h1>
<p>Nomira encontró publicaciones en los estrados digitales para expedientes que su despacho vigila:</p>
<ul style="padding-left:18px">{''.join(html_items)}</ul>
{_boton("Ver la publicación en Nomira", _url("/agenda/estrados"))}
<p style="font-size:13px;color:#64748b">Por seguridad este correo no incluye el contenido del acuerdo. Confirme siempre en la consulta oficial del tribunal; la fecha en que surte efectos es una estimación que debe validar.</p>""")
    texto = f"Hola, {u.nombre}\n\nPublicaciones nuevas en estrados:\n" + "\n".join(txt_items) + f"\n\nVer en Nomira: {_url('/agenda/estrados')}\n"
    return asunto, html, texto


# ------------------------------------------------------------------ revisión periódica

def en_horario(ahora: datetime) -> bool:
    return ahora.weekday() < 5 and HORARIO[0] <= ahora.hour < HORARIO[1]


def revisar(db: Session, v: m.AgVigilancia, cliente: httpx.Client | None = None) -> list[m.AgPublicacion]:
    v.ultima_revision = m.ahora()
    try:
        hallazgos = consultar(v, cliente)
    except SinConfigurar as e:
        v.ultimo_estado, v.ultimo_error = "sin_conexion", str(e)[:300]
        return []
    except FalloConsulta as e:
        v.ultimo_estado, v.ultimo_error = "error", str(e)[:300]
        log.warning("Estrados: falló la consulta de la vigilancia %s: %s", v.id, e)
        return []
    v.ultimo_estado, v.ultimo_error = "ok", None
    return guardar(db, v, hallazgos, "automatica")


def ejecutar(db: Session, ahora: datetime | None = None, pausa: float = PAUSA_SEG) -> dict:
    ahora = ahora or base.ahora_local()
    r = {"revisadas": 0, "nuevas": 0, "correos": 0}
    if not configurado() or not en_horario(ahora):
        return r
    limite = m.ahora() - timedelta(hours=REVISAR_CADA_HORAS)
    pend = list(db.scalars(select(m.AgVigilancia).join(m.AgAsunto, m.AgAsunto.id == m.AgVigilancia.asunto_id)
                           .where(m.AgVigilancia.activa.is_(True), m.AgVigilancia.fuente == "trijaem", m.AgAsunto.estado == "activo",
                                  (m.AgVigilancia.ultima_revision.is_(None)) | (m.AgVigilancia.ultima_revision < limite))
                           .order_by(m.AgVigilancia.ultima_revision.nullsfirst()).limit(MAX_POR_RONDA)))
    activos: dict[int, bool] = {}
    nuevas = []
    with httpx.Client(timeout=20, follow_redirects=False, headers={"User-Agent": "Nomira/1.0 (+https://nomirasoft.com)", "Accept": "application/json"}) as cli:
        for i, v in enumerate(pend):
            if v.organizacion_id not in activos:
                org = db.get(m.Organizacion, v.organizacion_id)
                activos[v.organizacion_id] = bool(org and org.estado == "activa" and "agenda" in modulos.activos(db, v.organizacion_id))
            if not activos[v.organizacion_id]:
                continue
            if i and pausa:
                time.sleep(pausa)
            nuevas += revisar(db, v, cli)
            r["revisadas"] += 1
            db.commit()
    r["nuevas"] = len(nuevas)
    r["correos"] = avisar(db, nuevas)
    db.commit()
    return r
