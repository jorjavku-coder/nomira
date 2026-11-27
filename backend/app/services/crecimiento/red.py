"""«Quiero que un abogado revise mi caso»: la calculadora pública de finiquito le entrega el caso a UN despacho
de la red de Nomira en el estado de la persona (por turnos), como prospecto de su módulo de Prospectos.

- Solo participan despachos que lo pidieron, con plan pagado vigente y el módulo de Prospectos activo.
- La persona da su autorización expresa para que ese despacho la contacte; nada se envía a nadie más.
- Si en su estado no hay despacho disponible, el formulario ni siquiera se muestra (no guardamos datos que no
  podamos atender).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import models as m
from .. import correo, envios, modulos, plantillas_correo
from ..leads import base as leads
from . import base

ESTADOS_MX = {
    "AGS": "Aguascalientes", "BC": "Baja California", "BCS": "Baja California Sur", "CAM": "Campeche", "CHIS": "Chiapas",
    "CHIH": "Chihuahua", "CDMX": "Ciudad de México", "COAH": "Coahuila", "COL": "Colima", "DGO": "Durango", "MEX": "Estado de México",
    "GTO": "Guanajuato", "GRO": "Guerrero", "HGO": "Hidalgo", "JAL": "Jalisco", "MICH": "Michoacán", "MOR": "Morelos", "NAY": "Nayarit",
    "NL": "Nuevo León", "OAX": "Oaxaca", "PUE": "Puebla", "QRO": "Querétaro", "QROO": "Quintana Roo", "SLP": "San Luis Potosí",
    "SIN": "Sinaloa", "SON": "Sonora", "TAB": "Tabasco", "TAMS": "Tamaulipas", "TLAX": "Tlaxcala", "VER": "Veracruz", "YUC": "Yucatán",
    "ZAC": "Zacatecas",
}


def requisitos(db: Session, org_id: int) -> dict:
    """Qué le falta a un despacho para recibir casos."""
    org = db.get(m.Organizacion, org_id)
    return {"plan": base.plan_pagado_vigente(db, org_id), "prospectos": "leads" in modulos.activos(db, org_id),
            "activa": bool(org and org.estado == "activa")}


def _este_mes(db: Session, org_id: int) -> int:
    h = base.hoy()
    return int(db.scalar(select(func.count()).select_from(m.CxCaso).where(
        m.CxCaso.organizacion_id == org_id, m.CxCaso.creado_en >= datetime(h.year, h.month, 1))) or 0)


def candidatos(db: Session, estado: str) -> list[m.CxRed]:
    """Despachos que pueden recibir un caso de ese estado, del que lleva más tiempo sin recibir al más reciente."""
    xs = [r for r in db.scalars(select(m.CxRed).where(m.CxRed.activo.is_(True))).all() if estado in (r.estados or [])]
    xs = [r for r in xs if all(requisitos(db, r.organizacion_id).values())
          and (r.tope_mensual is None or _este_mes(db, r.organizacion_id) < r.tope_mensual)]
    return sorted(xs, key=lambda r: (r.ultimo_en is not None, r.ultimo_en or datetime.min, r.id))


def disponible(db: Session, estado: str) -> bool:
    return base.config(db).casos_activos and estado in ESTADOS_MX and bool(candidatos(db, estado))


def entregar(db: Session, *, estado: str, nombre: str, tel: str | None, email: str | None, mensaje: str | None,
             resumen: str | None) -> m.CxCaso | None:
    """Asigna el caso al siguiente despacho y lo crea como prospecto. None si no hay despacho disponible."""
    xs = candidatos(db, estado)
    if not xs:
        return None
    r = xs[0]
    r.ultimo_en = m.ahora()
    partes = [f"Llegó desde la calculadora de finiquito de Nomira ({ESTADOS_MX[estado]})."]
    if resumen:
        partes.append(resumen)
    if mensaje:
        partes.append(f"Su mensaje: {mensaje}")
    canales = (["whatsapp", "llamada"] if tel else []) + (["correo"] if email else [])
    p, _ = leads.alta_externa(db, r.organizacion_id, nombre=nombre, tel=tel, email=email, ciudad=ESTADOS_MX[estado], materia="Laboral",
                              descripcion="\n".join(partes), canal="nomira", entrada="nomira", consentimiento=canales,
                              medio="formulario_web", preferencia="whatsapp" if tel else "correo")
    caso = m.CxCaso(estado_mx=estado, organizacion_id=r.organizacion_id, prospecto_id=p.id)
    db.add(caso)
    db.flush()
    _avisar(db, r.organizacion_id, caso.id)
    return caso


def _avisar(db: Session, org_id: int, caso_id: int) -> None:
    """Correo a los administradores del despacho: solo que tienen un caso nuevo (sin datos de la persona)."""
    if not correo.configurado():
        return
    admins = db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == org_id, m.Usuario.rol == "administrador",
                                               m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None))).all()
    if not admins:
        return
    asunto, html, texto = plantillas_correo.caso_nomira(db.get(m.Organizacion, org_id).nombre)
    try:
        envios.registrar_y_enviar(db, "caso_nomira", [a.email for a in admins], asunto, html, texto, organizacion_id=org_id,
                                  llave=f"caso_nomira:{caso_id}")
    except Exception:  # el aviso no impide registrar el caso
        pass
