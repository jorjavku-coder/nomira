"""Vigilancia de estrados digitales (primero: TRIJAEM, Tribunal de Justicia Administrativa del Estado de México).

Cómo funciona
- El despacho marca qué asuntos de su agenda quiere vigilar y con qué número de expediente los publica el tribunal.
- Dos formas de detectar publicaciones:
  1. Automática: un proceso en segundo plano consulta el mismo servicio público que usa la página de estrados del
     TRIJAEM (POST /servicios/Estrados/EstradosPublicos con número de expediente y sala) unas pocas veces al día,
     en horario hábil y con pausa entre consultas para no saturar al tribunal. Se apaga con TRIJAEM_ESTRADOS_ACTIVO=false.
  2. Cotejo: el abogado pega el texto (o sube el PDF) de la lista del día y Nomira busca ahí todos los expedientes
     que el despacho vigila. Funciona siempre, aunque la consulta automática no esté configurada o falle.
- Cada publicación se guarda una sola vez (huella única) y genera aviso en Nomira y, si hay correo, por correo.

Límites que se dicen al usuario: Nomira no sustituye la consulta oficial. La fecha en que «surte efectos» es una
estimación (día hábil siguiente según el calendario del asunto) que el abogado debe confirmar.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

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

# Salas del TRIJAEM con su clave en el sistema de estrados (consultadas en /servicios/Estrados/salasPub, nov. 2026)
SALAS_TRIJAEM = {
    "1": "Primera Sala Regional Toluca", "2": "Segunda Sala Regional Naucalpan de Juárez", "3": "Tercera Sala Regional Tlalnepantla de Baz",
    "4": "Cuarta Sala Regional Ecatepec de Morelos", "5": "Quinta Sala Regional Nezahualcóyotl", "6": "Sexta Sala Regional Atizapán de Zaragoza",
    "7": "Séptima Sala Regional Toluca",
    "8": "Octava Sala Regional Especializada en Materia de Responsabilidades Administrativas Valle de Toluca",
    "9": "Novena Sala Regional Especializada en Materia de Responsabilidades Administrativas Valle de México",
    "10": "Primera Sección de la Sala Superior Toluca", "11": "Segunda Sección de la Sala Superior Tlalnepantla de Baz",
    "12": "Tercera Sección de la Sala Superior Ecatepec de Morelos",
    "13": "Cuarta Sección de la Sala Superior en Materia de Responsabilidades Administrativas Toluca",
}
URL_TRIJAEM = "https://trijaem.gob.mx/servicios/Estrados/EstradosPublicos"
DIAS_HISTORIAL = 3  # al empezar a vigilar, lo publicado antes de esto se guarda como antecedente, sin aviso

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
    clave: str | None = None  # identificador del acuerdo en el tribunal, si lo da
    fecha_acuerdo: date | None = None
    promocion: str | None = None


# ------------------------------------------------------------------ expedientes

def clave_expediente(texto: str | None) -> tuple[int, int] | None:
    """«JA-0123/2026», «123 / 2026» y «123/2026» son el mismo expediente: (123, 2026)."""
    x = EXPEDIENTE.search(texto or "")
    return (int(x.group(1)), int(x.group(2))) if x else None


def numero_tribunal(texto: str | None) -> str | None:
    """Como lo busca el TRIJAEM: «número/año» sin prefijo ni ceros a la izquierda (JA-0491/2026 → 491/2026)."""
    k = clave_expediente(texto)
    return f"{k[0]}/{k[1]}" if k else None


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
    if h.clave:
        return hashlib.sha256(f"acuerdo:{h.clave}".encode()).hexdigest()
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


# ------------------------------------------------------------------ consulta automática (conector TRIJAEM)

def _fecha(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def interpretar(datos, v: m.AgVigilancia) -> list[Hallazgo]:
    """Convierte la respuesta del TRIJAEM ({"data": [...], "error": {...}}) en hallazgos del expediente vigilado.
    Cada fila trae: no_expediente, id_sala, nombreSala, fecha_acuerdo, fecha_registro_ok (publicación),
    no_promocion, UNE, nombreJuicio, id_acuerdo y TEJA (enlace al acuerdo)."""
    if not isinstance(datos, dict) or not isinstance(datos.get("data"), list):
        raise FalloConsulta("El tribunal respondió en un formato que Nomira no reconoce.")
    k = clave_expediente(v.expediente)
    r = []
    for f in datos["data"]:
        if not isinstance(f, dict) or clave_expediente(str(f.get("no_expediente") or "")) != k:
            continue
        if v.id_sala and str(f.get("id_sala") or "") != str(v.id_sala):
            continue
        publicada = _fecha(f.get("fecha_registro_ok")) or _fecha(f.get("fecha_acuerdo"))
        if not publicada:
            continue
        acuerdo = _fecha(f.get("fecha_acuerdo"))
        promo = str(f.get("no_promocion") or "").strip()[:30] or None
        juicio = str(f.get("nombreJuicio") or "").strip()[:80] or None
        partes = ["Acuerdo publicado en estrados"]
        if acuerdo:
            partes.append(f"de fecha {acuerdo.strftime('%d/%m/%Y')}")
        if promo:
            partes.append(f"· promoción {promo}")
        if juicio:
            partes.append(f"· {juicio}")
        enlace = str(f.get("TEJA") or "")
        r.append(Hallazgo(fecha=publicada, descripcion=" ".join(partes), sala=str(f.get("nombreSala") or v.sala or "")[:120] or None,
                          tipo=juicio, enlace=enlace[:500] if enlace.startswith("https://trijaem.gob.mx/") else None,
                          clave=str(f.get("id_acuerdo") or "")[:40] or None, fecha_acuerdo=acuerdo, promocion=promo))
    return r


def configurado(fuente: str = "trijaem") -> bool:
    return fuente == "trijaem" and bool(ajustes().trijaem_estrados_activo)


def _cliente() -> httpx.Client:
    return httpx.Client(timeout=25, follow_redirects=False, headers={
        "User-Agent": "Mozilla/5.0 (compatible; Nomira/1.0; +https://nomirasoft.com)", "Accept": "application/json, text/plain, */*",
        "Origin": "https://trijaem.gob.mx", "Referer": "https://trijaem.gob.mx/servicios/Estrados", "X-Requested-With": "XMLHttpRequest"})


def consultar(v: m.AgVigilancia, cliente: httpx.Client | None = None) -> list[Hallazgo]:
    if not configurado(v.fuente):
        raise SinConfigurar("La revisión automática del TRIJAEM está apagada en Nomira.")
    numero = numero_tribunal(v.expediente)
    if not numero or not v.id_sala:
        raise SinConfigurar("Falta la sala del TRIJAEM: el tribunal solo busca por expediente y sala.")
    # El sistema del tribunal recibe JSON aunque declara x-www-form-urlencoded (así lo envía su propia página).
    cuerpo = json.dumps({"no_expediente": numero, "id_sala": str(v.id_sala)})
    propio = cliente is None
    cliente = cliente or _cliente()
    try:
        r = cliente.post(URL_TRIJAEM, content=cuerpo, headers={"Content-Type": "application/x-www-form-urlencoded"})
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
                            sala=h.sala, tipo=h.tipo, descripcion=h.descripcion[:2000], enlace=h.enlace, origen=origen,
                            fecha_acuerdo=h.fecha_acuerdo, promocion=h.promocion)
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
        if p.promocion and p.promocion in (v.promociones or []):
            quien += f" · respuesta a su promoción {p.promocion}"
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
    primera = v.ultimo_estado != "ok" and not db.scalar(select(m.AgPublicacion.id).where(m.AgPublicacion.vigilancia_id == v.id).limit(1))
    v.ultimo_estado, v.ultimo_error = "ok", None
    nuevas = guardar(db, v, hallazgos, "automatica")
    if primera:  # lo publicado hace días queda como antecedente: no es «nuevo» para el despacho
        limite = base.hoy() - timedelta(days=DIAS_HISTORIAL)
        viejas = [p for p in nuevas if p.fecha_publicacion < limite]
        for p in viejas:
            p.vista_en = m.ahora()
        nuevas = [p for p in nuevas if p.fecha_publicacion >= limite]
    return nuevas


def ejecutar(db: Session, ahora: datetime | None = None, pausa: float = PAUSA_SEG) -> dict:
    ahora = ahora or base.ahora_local()
    r = {"revisadas": 0, "nuevas": 0, "correos": 0}
    if not configurado() or not en_horario(ahora):
        return r
    limite = m.ahora() - timedelta(hours=REVISAR_CADA_HORAS)
    pend = list(db.scalars(select(m.AgVigilancia).join(m.AgAsunto, m.AgAsunto.id == m.AgVigilancia.asunto_id)
                           .where(m.AgVigilancia.activa.is_(True), m.AgVigilancia.fuente == "trijaem", m.AgAsunto.estado == "activo",
                                  m.AgVigilancia.id_sala.is_not(None),
                                  (m.AgVigilancia.ultima_revision.is_(None)) | (m.AgVigilancia.ultima_revision < limite))
                           .order_by(m.AgVigilancia.ultima_revision.nullsfirst()).limit(MAX_POR_RONDA)))
    activos: dict[int, bool] = {}
    nuevas = []
    with _cliente() as cli:
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
