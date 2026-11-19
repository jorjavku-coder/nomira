"""Envío con bitácora: bienvenida de clientes y recordatorios de vencimiento.

Cada correo queda en correos_enviados (sin el cuerpo). Los recordatorios llevan una «llave» única
por periodo, así que aunque corran dos procesos a la vez o el servicio se reinicie, cada cliente
recibe un solo aviso por periodo. Si el envío falla, la llave se libera para reintentar después.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from . import correo, suscripciones as sus
from .plantillas_correo import bienvenida, recordatorio_vencimiento

log = logging.getLogger("nomira.correos")
MAX_ERRORES_DIA = 3


def registrar_y_enviar(db: Session, tipo: str, destinatarios: list[str], asunto: str, html: str, texto: str, *,
                       organizacion_id: int | None = None, periodo_id: int | None = None,
                       llave: str | None = None) -> m.CorreoEnviado | None:
    """Devuelve el registro, o None si esa llave ya se había enviado."""
    r = m.CorreoEnviado(tipo=tipo, organizacion_id=organizacion_id, periodo_id=periodo_id, llave=llave,
                        destinatarios=", ".join(destinatarios)[:1000], asunto=asunto[:300], estado="enviando")
    db.add(r)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    try:
        correo.enviar(destinatarios, asunto, html, texto)
        r.estado = "enviado"
    except correo.CorreoError as e:
        r.estado, r.error, r.llave = "error", str(e)[:2000], None
        log.warning("No se envió el correo %s a %s: %s", tipo, r.destinatarios, e)
    except Exception as e:  # nunca romper la petición que lo originó
        r.estado, r.error, r.llave = "error", f"Error inesperado: {type(e).__name__}", None
        log.exception("Error inesperado al enviar el correo %s", tipo)
    db.commit()
    return r


def enviar_bienvenida(db: Session, o: m.Organizacion, acceso: dict) -> dict:
    fin_prueba = db.scalar(select(m.PeriodoSuscripcion.fin).where(
        m.PeriodoSuscripcion.organizacion_id == o.id, m.PeriodoSuscripcion.plan == "prueba"))
    asunto, html, texto = bienvenida(acceso["nombre"], o.nombre, acceso["email"], acceso["contrasena_temporal"], fin_prueba)
    r = registrar_y_enviar(db, "bienvenida", [acceso["email"]], asunto, html, texto, organizacion_id=o.id)
    return {"enviado": r.estado == "enviado", "destinatario": acceso["email"], "error": r.error}


def _administradores(db: Session, oid: int) -> list[m.Usuario]:
    return list(db.scalars(select(m.Usuario).where(
        m.Usuario.organizacion_id == oid, m.Usuario.rol == "administrador", m.Usuario.activo.is_(True),
        m.Usuario.eliminado_en.is_(None)).order_by(m.Usuario.id)))


def recordatorios_pendientes(db: Session, ref: date | None = None) -> list[dict]:
    """Planes de pago vigentes que vencen dentro de RECORDATORIO_DIAS (o menos), sin renovación
    registrada y sin aviso ya enviado. Incluye a los que «se brincaron» el día exacto (servicio
    dormido, por ejemplo): el aviso sale en cuanto vuelve a correr."""
    dias_aviso = ajustes().recordatorio_dias
    if dias_aviso <= 0:
        return []
    ref = ref or sus.hoy()
    periodos = db.scalars(select(m.PeriodoSuscripcion).where(
        m.PeriodoSuscripcion.plan != "prueba", m.PeriodoSuscripcion.inicio <= ref, m.PeriodoSuscripcion.fin >= ref,
        m.PeriodoSuscripcion.fin <= ref + timedelta(days=dias_aviso))).all()
    salida = []
    for p in periodos:
        o = db.get(m.Organizacion, p.organizacion_id)
        if not o or o.estado != "activa":
            continue
        renovado = db.scalar(select(m.PeriodoSuscripcion.id).where(
            m.PeriodoSuscripcion.organizacion_id == o.id, m.PeriodoSuscripcion.inicio > p.fin).limit(1))
        if renovado:
            continue
        if db.scalar(select(m.CorreoEnviado.id).where(m.CorreoEnviado.llave == f"recordatorio:{p.id}")):
            continue
        errores = db.scalar(select(func.count()).select_from(m.CorreoEnviado).where(
            m.CorreoEnviado.periodo_id == p.id, m.CorreoEnviado.estado == "error",
            m.CorreoEnviado.creado_en >= m.ahora() - timedelta(hours=24)))
        admins = _administradores(db, o.id)
        salida.append({"organizacion": o, "periodo": p, "admins": admins, "dias": (p.fin - ref).days,
                       "en_pausa": errores >= MAX_ERRORES_DIA})
    return salida


def ejecutar_recordatorios(db: Session, ref: date | None = None) -> list[dict]:
    resultados = []
    for x in recordatorios_pendientes(db, ref):
        o, p, admins = x["organizacion"], x["periodo"], x["admins"]
        base = {"cliente": o.nombre, "organizacion_id": o.id, "vence": p.fin.isoformat()}
        if not admins:
            resultados.append({**base, "estado": "omitido", "detalle": "No tiene administradores activos."})
            continue
        if x["en_pausa"]:
            resultados.append({**base, "estado": "omitido", "detalle": "Falló 3 veces en 24 h; se reintentará después."})
            continue
        if not correo.configurado():
            resultados.append({**base, "estado": "omitido", "detalle": "El envío de correos no está configurado."})
            continue
        asunto, html, texto = recordatorio_vencimiento(
            admins[0].nombre if len(admins) == 1 else "equipo", o.nombre, sus.PLANES[p.plan][0], p.fin, x["dias"])
        r = registrar_y_enviar(db, "recordatorio_vencimiento", [u.email for u in admins], asunto, html, texto,
                               organizacion_id=o.id, periodo_id=p.id, llave=f"recordatorio:{p.id}")
        if r is None:
            continue  # otro proceso lo envió en ese instante
        resultados.append({**base, "estado": r.estado, "detalle": r.error or r.destinatarios})
    return resultados
