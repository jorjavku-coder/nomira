"""Club Nomira: reglas de visibilidad de beneficios, credencial digital y métricas agregadas."""
from __future__ import annotations

import secrets
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models as m
from .. import suscripciones as sus

CATEGORIAS = {
    "salud": "Salud y seguros", "oficina": "Oficina y papelería", "tecnologia": "Tecnología", "capacitacion": "Capacitación",
    "finanzas": "Finanzas y contabilidad", "autos": "Autos y movilidad", "viajes": "Viajes y hoteles", "restaurantes": "Restaurantes",
    "bienestar": "Bienestar y deporte", "otros": "Otros",
}
CANJES = {"codigo": "Código de descuento", "enlace": "Enlace del aliado", "credencial": "Presentando la credencial digital"}
_ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I/L para dictarlo sin errores


def hoy() -> date:
    return sus.hoy()


def visibles(db: Session) -> list[tuple[m.AlBeneficio, m.AlAliado]]:
    """Publicados, dentro de vigencia y de aliados activos."""
    h = hoy()
    q = (select(m.AlBeneficio, m.AlAliado).join(m.AlAliado, m.AlAliado.id == m.AlBeneficio.aliado_id)
         .where(m.AlBeneficio.estado == "publicado", m.AlAliado.estado == "activo",
                (m.AlBeneficio.vigente_desde.is_(None)) | (m.AlBeneficio.vigente_desde <= h),
                (m.AlBeneficio.vigente_hasta.is_(None)) | (m.AlBeneficio.vigente_hasta >= h))
         .order_by(m.AlBeneficio.destacado.desc(), m.AlBeneficio.actualizado_en.desc()))
    return [(b, a) for b, a in db.execute(q).all()]


def miembro_vigente(db: Session, u: m.Usuario) -> bool:
    """Usuario activo de un despacho activo con plan vigente (incluye la prueba)."""
    if not u or not u.activo or u.eliminado_en:
        return False
    o = db.get(m.Organizacion, u.organizacion_id)
    if not o or o.estado != "activa":
        return False
    periodos = db.scalars(select(m.PeriodoSuscripcion).where(m.PeriodoSuscripcion.organizacion_id == o.id)).all()
    return sus.estado(list(periodos))["estado"] in ("prueba", "activa", "por_vencer")


def credencial(db: Session, u: m.Usuario) -> m.AlCredencial:
    c = db.scalar(select(m.AlCredencial).where(m.AlCredencial.usuario_id == u.id))
    if c:
        return c
    for _ in range(5):
        cod = "NM-" + "".join(secrets.choice(_ALFABETO) for _ in range(4)) + "-" + "".join(secrets.choice(_ALFABETO) for _ in range(4))
        try:
            with db.begin_nested():
                c = m.AlCredencial(usuario_id=u.id, codigo=cod)
                db.add(c)
            return c
        except IntegrityError:
            existente = db.scalar(select(m.AlCredencial).where(m.AlCredencial.usuario_id == u.id))
            if existente:
                return existente
    raise RuntimeError("No se pudo generar la credencial.")


def registrar_uso(db: Session, b: m.AlBeneficio, u: m.Usuario, tipo: str) -> None:
    """Una vista y un canje por usuario, beneficio y día (para no inflar las métricas)."""
    h = hoy()
    if db.scalar(select(m.AlUso.id).where(m.AlUso.beneficio_id == b.id, m.AlUso.usuario_id == u.id, m.AlUso.tipo == tipo, m.AlUso.dia == h)):
        return
    try:
        with db.begin_nested():
            db.add(m.AlUso(beneficio_id=b.id, organizacion_id=u.organizacion_id, usuario_id=u.id, tipo=tipo, dia=h))
    except IntegrityError:
        pass  # otra pestaña lo registró en el mismo instante


def metricas(db: Session, desde: date | None = None) -> dict[int, dict]:
    """Por beneficio: vistas, canjes y despachos distintos que canjearon. Solo conteos."""
    q = select(m.AlUso.beneficio_id, m.AlUso.tipo, func.count(m.AlUso.id), func.count(func.distinct(m.AlUso.organizacion_id)))
    if desde:
        q = q.where(m.AlUso.dia >= desde)
    out: dict[int, dict] = {}
    for bid, tipo, n, orgs in db.execute(q.group_by(m.AlUso.beneficio_id, m.AlUso.tipo)).all():
        d = out.setdefault(bid, {"vistas": 0, "canjes": 0, "despachos": 0})
        if tipo == "vista":
            d["vistas"] = n
        else:
            d["canjes"], d["despachos"] = n, orgs
    return out
