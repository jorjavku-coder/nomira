"""Academia como LMS: acceso a cursos de Nomira con costo, límite de cursos propios, espacio para
videos/SCORM, URL firmadas para medios y publicación/entrega de cursos desde la cuenta editora.

Reglas:
- Un curso del catálogo de Nomira «con costo» solo deja ver su contenido al despacho que tiene un
  acceso vigente (compra pagada confirmada por Stripe, asignación desde Comercial o cortesía).
- Los cursos propios archivados no cuentan para el límite.
- Ningún medio (video, SCORM) se sirve sin una URL firmada, de corta duración y ligada a la persona.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import models as m
from .. import almacenamiento as almacen
from ...config import ajustes
from . import base

DURACION_FIRMA_S = 6 * 3600


def config(db: Session) -> m.AcConfig:
    c = db.scalar(select(m.AcConfig))
    if c is None:
        c = m.AcConfig(cursos_incluidos=5, cuota_medios_mb=2048, video_max_mb=500, scorm_max_mb=300)
        db.add(c)
        db.flush()
    return c


# ------------------------------------------------------------------ acceso a cursos con costo

def es_de_pago(c: m.AcCurso) -> bool:
    return c.organizacion_id is None and c.acceso == "pago"


def acceso_vigente(db: Session, org_id: int, c: m.AcCurso) -> m.AcAcceso | None:
    return db.scalar(select(m.AcAcceso).where(m.AcAcceso.organizacion_id == org_id, m.AcAcceso.curso_id == c.id,
                                              m.AcAcceso.revocado_en.is_(None)))


def tiene_acceso(db: Session, org_id: int, c: m.AcCurso) -> bool:
    return not es_de_pago(c) or acceso_vigente(db, org_id, c) is not None


def otorgar(db: Session, org_id: int, c: m.AcCurso, origen: str, *, compra_id: int | None = None, cotizacion_id: int | None = None,
            admin_id: int | None = None) -> m.AcAcceso:
    x = db.scalar(select(m.AcAcceso).where(m.AcAcceso.organizacion_id == org_id, m.AcAcceso.curso_id == c.id))
    if x is None:
        x = m.AcAcceso(organizacion_id=org_id, curso_id=c.id, origen=origen, compra_id=compra_id, cotizacion_id=cotizacion_id, admin_id=admin_id)
        db.add(x)
    elif x.revocado_en:
        x.revocado_en, x.origen, x.compra_id, x.cotizacion_id, x.admin_id = None, origen, compra_id, cotizacion_id, admin_id
    db.flush()
    return x


def precio_con_iva(db: Session, c: m.AcCurso) -> dict:
    from ..comercial import base as cm  # IVA general configurado en Comercial

    iva_pct = cm.config(db).iva_pct
    sub = Decimal(c.precio or 0).quantize(cm.CENT)
    iva = (sub * iva_pct / 100).quantize(cm.CENT)
    return {"subtotal": cm.txt(sub), "iva_pct": cm.txt(iva_pct), "iva": cm.txt(iva), "total": cm.txt(sub + iva)}


# ------------------------------------------------------------------ límite de cursos propios

def limite(db: Session, org_id: int) -> dict:
    conf = config(db)
    org = db.get(m.Organizacion, org_id)
    extra = org.ac_cursos_extra or 0 if org else 0
    usados = db.scalar(select(func.count(m.AcCurso.id)).where(m.AcCurso.organizacion_id == org_id, m.AcCurso.estado != "archivado")) or 0
    tope = conf.cursos_incluidos + extra
    return {"incluidos": conf.cursos_incluidos, "adicionales": extra, "limite": tope, "usados": usados, "disponibles": max(tope - usados, 0)}


def exigir_lugar(db: Session, org_id: int, cuantos: int = 1) -> None:
    lim = limite(db, org_id)
    if lim["usados"] + cuantos > lim["limite"]:
        raise HTTPException(409, {"codigo": "limite_cursos", "limite": lim,
                                  "mensaje": f"Su plan incluye {lim['limite']} cursos propios y ya tiene {lim['usados']}. "
                                             "Contrate cursos adicionales con Nomira o archive un curso que ya no use."})


# ------------------------------------------------------------------ espacio para videos y SCORM

def _alcance(db: Session, org_id: int) -> tuple[str, int]:
    """Qué se mide y cuánto cabe.

    - Si Nomira fijó a mano un espacio para Academia: solo videos + SCORM contra ese límite.
    - Si el despacho tiene un plan asignado en Comercial: TODO su espacio (expedientes, evidencia,
      Academia…) contra el almacenamiento contratado (paquete + bloques adicionales).
    - Si no: solo videos + SCORM contra el espacio general de Academia.
    """
    org = db.get(m.Organizacion, org_id)
    if org and org.ac_cuota_medios_mb is not None:
        return "academia", org.ac_cuota_medios_mb * 1024 * 1024
    gb = almacen.contratado_gb(db, org_id)
    if gb:
        return "despacho", gb * almacen.GB
    return "academia", config(db).cuota_medios_mb * 1024 * 1024


def cuota_bytes(db: Session, org_id: int) -> int:
    return _alcance(db, org_id)[1]


def uso_academia(db: Session, org_id: int) -> int:
    cursos = select(m.AcCurso.id).where(m.AcCurso.organizacion_id == org_id)
    return int(db.scalar(select(func.coalesce(func.sum(func.coalesce(m.AcLeccion.video_tamano, 0) + func.coalesce(m.AcLeccion.scorm_tamano, 0)), 0))
                         .where(m.AcLeccion.curso_id.in_(cursos))) or 0)


def uso_bytes(db: Session, org_id: int, fresco: bool = False) -> int:
    if _alcance(db, org_id)[0] == "despacho":
        return almacen.uso_bytes(org_id, fresco=fresco)
    return uso_academia(db, org_id)


def espacio(db: Session, org_id: int) -> dict:
    conf = config(db)
    alcance, cuota = _alcance(db, org_id)
    return {"usado_mb": round(uso_bytes(db, org_id) / 1048576, 1), "cuota_mb": cuota // 1048576, "alcance": alcance,
            "video_max_mb": conf.video_max_mb, "scorm_max_mb": conf.scorm_max_mb}


def exigir_espacio(db: Session, org_id: int, nuevo: int, liberado: int = 0) -> None:
    """Se llama con el archivo nuevo YA guardado en disco (si no cabe, quien llama lo borra)."""
    alcance, cuota = _alcance(db, org_id)
    extra = 0 if alcance == "despacho" else nuevo  # medido en disco, el archivo nuevo ya cuenta
    if uso_bytes(db, org_id, fresco=True) - liberado + extra > cuota:
        e = espacio(db, org_id)
        almacen.olvidar(org_id)  # quien llama borra el archivo que no cupo
        if e["alcance"] == "despacho":
            raise HTTPException(413, f"Ya no hay espacio en el almacenamiento de su plan ({e['usado_mb']:,.0f} de {e['cuota_mb']:,} MB usados). "
                                     "Contrate almacenamiento adicional con Nomira o use un enlace de YouTube o Vimeo.")
        raise HTTPException(413, f"No hay espacio suficiente para videos y SCORM ({e['usado_mb']} de {e['cuota_mb']} MB usados). "
                                 "Pida más espacio a Nomira o use un enlace de YouTube o Vimeo.")



# ------------------------------------------------------------------ URL firmadas (video y SCORM)

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def firmar(tipo: str, leccion_id: int, usuario_id: int, segundos: int = DURACION_FIRMA_S) -> str:
    datos = _b64(json.dumps({"t": tipo, "l": leccion_id, "u": usuario_id, "e": int(time.time()) + segundos}, separators=(",", ":")).encode())
    firma = hmac.new(ajustes().jwt_secreto.encode(), f"medios:{datos}".encode(), hashlib.sha256).digest()[:18]
    return f"{datos}.{_b64(firma)}"


def verificar(token: str, tipo: str) -> dict:
    try:
        datos, firma = token.split(".", 1)
        esperado = hmac.new(ajustes().jwt_secreto.encode(), f"medios:{datos}".encode(), hashlib.sha256).digest()[:18]
        if not hmac.compare_digest(_unb64(firma), esperado):
            raise ValueError
        d = json.loads(_unb64(datos))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(404, "No encontrado.")
    if d.get("t") != tipo or d.get("e", 0) < time.time():
        raise HTTPException(404, "El enlace venció. Recargue la lección.")
    return d


# ------------------------------------------------------------------ copiar cursos (catálogo y entregas)

def copiar_contenido(db: Session, src: m.AcCurso, dst: m.AcCurso) -> None:
    """Copia (o actualiza) módulos, lecciones y preguntas de `src` en `dst`. Las lecciones se
    emparejan por origen: el avance de quien ya tomó el curso se conserva; lo que se quitó del
    original se archiva (no se borra)."""
    mods_src = db.scalars(select(m.AcModulo).where(m.AcModulo.curso_id == src.id, m.AcModulo.archivado_en.is_(None))
                          .order_by(m.AcModulo.orden, m.AcModulo.id)).all()
    mods_dst = {mo.titulo: mo for mo in db.scalars(select(m.AcModulo).where(m.AcModulo.curso_id == dst.id))}
    previas = {x.origen_leccion_id: x for x in db.scalars(select(m.AcLeccion).where(m.AcLeccion.curso_id == dst.id)) if x.origen_leccion_id}
    vistas: set[int] = set()
    campos = ("titulo", "orden", "texto", "video_url", "sesion_url", "transcripcion", "recursos", "actividad", "archivo_ruta", "archivo_nombre",
              "archivo_formato", "archivo_tamano", "video_ruta", "video_nombre", "video_formato", "video_tamano", "scorm_dir", "scorm_inicio",
              "scorm_version", "scorm_tamano", "duracion_min")
    for i, mo in enumerate(mods_src):
        nm = mods_dst.get(mo.titulo)
        if nm is None:
            nm = m.AcModulo(curso_id=dst.id, titulo=mo.titulo, orden=i)
            db.add(nm)
            db.flush()
        nm.orden, nm.archivado_en = i, None
        for x in base.lecciones(db, src.id):
            if x.modulo_id != mo.id:
                continue
            y = previas.get(x.id)
            if y is None:
                y = m.AcLeccion(curso_id=dst.id, modulo_id=nm.id, titulo=x.titulo, origen_leccion_id=x.id)
                db.add(y)
            y.modulo_id, y.archivado_en = nm.id, None
            for k in campos:
                setattr(y, k, getattr(x, k))
            vistas.add(x.id)
    for oid, y in previas.items():
        if oid not in vistas and not y.archivado_en:
            y.archivado_en = m.ahora()
    for p in db.scalars(select(m.AcPregunta).where(m.AcPregunta.curso_id == dst.id, m.AcPregunta.archivado_en.is_(None))):
        p.archivado_en = m.ahora()
    for p in base.preguntas(db, src.id):
        db.add(m.AcPregunta(curso_id=dst.id, texto=p.texto, opciones=p.opciones, correcta=p.correcta, explicacion=p.explicacion, orden=p.orden))
    db.flush()


CAMPOS_CURSO = ("titulo", "materia", "roles", "instructor", "institucion", "descripcion", "duracion_min", "modalidad", "juridico",
                "calificacion_minima", "reconocimiento")


def publicar_en_catalogo(db: Session, src: m.AcCurso, acceso: str, precio: Decimal | None) -> m.AcCurso:
    """Crea o actualiza el curso global (organizacion_id vacío) a partir del curso de la cuenta editora."""
    if src.estado != "publicado":
        raise HTTPException(409, "Primero publique el curso en la cuenta editora (así queda revisado).")
    if not base.lecciones(db, src.id):
        raise HTTPException(422, "El curso no tiene lecciones.")
    dst = db.scalar(select(m.AcCurso).where(m.AcCurso.organizacion_id.is_(None), m.AcCurso.origen_curso_id == src.id))
    nuevo = dst is None
    if nuevo:
        dst = m.AcCurso(organizacion_id=None, origen_curso_id=src.id, titulo=src.titulo, materia=src.materia, estado="publicado", version=1)
        db.add(dst)
        db.flush()
    for k in CAMPOS_CURSO:
        setattr(dst, k, getattr(src, k))
    dst.acceso, dst.precio = acceso, precio if acceso == "pago" else None
    dst.estado, dst.archivado_en = "publicado", None
    dst.revisado_en, dst.publicado_en = src.revisado_en, m.ahora()
    copiar_contenido(db, src, dst)
    if not nuevo:
        base.tocar(dst)
    return dst


def entregar_a_despacho(db: Session, src: m.AcCurso, org_id: int) -> m.AcCurso:
    """Copia un curso de la cuenta editora a un despacho, como BORRADOR que el despacho revisa y publica."""
    exigir_lugar(db, org_id)
    dst = m.AcCurso(organizacion_id=org_id, titulo=src.titulo, materia=src.materia, estado="borrador", version=1, entregado_por_nomira=True,
                    asistido_ia=src.asistido_ia)
    db.add(dst)
    db.flush()
    for k in CAMPOS_CURSO:
        setattr(dst, k, getattr(src, k))
    copiar_contenido(db, src, dst)
    for y in db.scalars(select(m.AcLeccion).where(m.AcLeccion.curso_id == dst.id)):
        y.origen_leccion_id = None  # la copia ya es del despacho
    return dst
