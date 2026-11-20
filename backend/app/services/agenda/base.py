"""Reglas comunes de Nomira Agenda Jurídica: catálogos, calendarios, estados y alertas."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .dias import Calendario

ZONA = ZoneInfo("America/Mexico_City")
MATERIAS = {"laboral": "Laboral", "civil": "Civil", "mercantil": "Mercantil", "familiar": "Familiar", "penal": "Penal",
            "amparo": "Amparo", "administrativo": "Administrativo", "fiscal": "Fiscal", "agrario": "Agrario",
            "seguridad_social": "Seguridad social", "otra": "Otra"}
JURISDICCIONES = {"federal": "Federal", "estatal": "Estatal (fuero común)"}
ENTIDADES = ["Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua", "Ciudad de México",
             "Coahuila", "Colima", "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán",
             "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa",
             "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas"]
TIPOS_ACTUACION = {"notificacion": "Notificación", "acuerdo": "Acuerdo", "promocion": "Promoción presentada",
                   "audiencia": "Audiencia celebrada", "resolucion": "Resolución o sentencia", "requerimiento": "Requerimiento", "otra": "Otra"}
TIPOS_EVENTO = {"plazo": "Plazo", "audiencia": "Audiencia", "actividad": "Actividad"}
PRIORIDADES = {"normal": "Normal", "alta": "Alta", "critica": "Crítica"}
ALERTAS_PLAZO = [5, 3, 1, 0]
ALERTAS_AUDIENCIA = [7, 1, 0]


def hoy() -> date:
    return datetime.now(ZONA).date()


def ahora_local() -> datetime:
    return datetime.now(ZONA)


def config(db: Session, org_id: int) -> m.AgConfig:
    c = db.scalar(select(m.AgConfig).where(m.AgConfig.organizacion_id == org_id))
    if c is None:
        c = m.AgConfig(organizacion_id=org_id, alertas_plazo=ALERTAS_PLAZO, alertas_audiencia=ALERTAS_AUDIENCIA,
                       resumen_diario=True, hora_resumen=7)
        db.add(c)
        db.flush()
    return c


def limpiar_alertas(v) -> list[int]:
    try:
        xs = sorted({int(x) for x in (v or [])}, reverse=True)
    except (TypeError, ValueError):
        xs = []
    return [x for x in xs if 0 <= x <= 90][:6]


def alertas_de(db: Session, e: m.AgEvento) -> list[int]:
    if e.alertas is not None:
        return limpiar_alertas(e.alertas)
    c = config(db, e.organizacion_id)
    return limpiar_alertas(c.alertas_audiencia if e.tipo == "audiencia" else c.alertas_plazo)


# ------------------------------------------------------------------ calendarios

def calendario(db: Session, cal_id: int | None, org_id: int) -> Calendario:
    if not cal_id:
        return Calendario(nombre="Sin calendario del tribunal (solo fines de semana y art. 74 LFT)")
    c = db.get(m.AgCalendario, cal_id)
    if not c or c.organizacion_id != org_id:
        return Calendario(nombre="Sin calendario del tribunal (solo fines de semana y art. 74 LFT)")
    dias = list(db.scalars(select(m.AgDia).where(m.AgDia.calendario_id == c.id)))
    semana = c.dias_semana_inhabiles if c.dias_semana_inhabiles is not None else [5, 6]
    return Calendario(nombre=c.nombre, semana_inhabil=tuple(semana), lft=c.incluir_descanso_lft,
                      inhabiles={d.fecha: d.motivo for d in dias if d.tipo == "inhabil"},
                      habilitados={d.fecha: d.motivo for d in dias if d.tipo == "habil"})


def calendario_de_evento(db: Session, e: m.AgEvento) -> int | None:
    if e.asunto_id:
        a = db.get(m.AgAsunto, e.asunto_id)
        if a and a.calendario_id:
            return a.calendario_id
    return config(db, e.organizacion_id).calendario_id


# ------------------------------------------------------------------ estado de un evento

def situacion(e: m.AgEvento, ref: date | None = None) -> str:
    """vencido | hoy | proximo | futuro | cumplido | cancelado"""
    if e.estado != "pendiente":
        return e.estado
    ref = ref or hoy()
    d = (e.fecha - ref).days
    if d < 0:
        return "vencido"
    if d == 0:
        return "hoy"
    return "proximo" if d <= 7 else "futuro"


def pendientes_de_validar(e: m.AgEvento) -> bool:
    return e.tipo == "plazo" and e.estado == "pendiente" and e.validado_en is None


def involucrados(e: m.AgEvento) -> list[int]:
    ids = [e.responsable_id] if e.responsable_id else []
    ids += [int(x) for x in (e.apoyo_ids or []) if int(x) not in ids]
    return ids


def supervisores(db: Session, org_id: int) -> list[m.Usuario]:
    c = config(db, org_id)
    if c.escalar_a_id:
        u = db.get(m.Usuario, c.escalar_a_id)
        if u and u.activo and not u.eliminado_en and u.organizacion_id == org_id:
            return [u]
    return list(db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == org_id, m.Usuario.rol == "administrador",
                                                   m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None))))


def alertas_vigentes(db: Session, e: m.AgEvento, ref: date | None = None) -> list[dict]:
    """Qué avisos le tocan HOY a este evento. Escalonado:
    1) avisos anticipados al responsable y apoyos (según los días configurados);
    2) el día del vencimiento, si sigue pendiente, también a quien supervisa;
    3) si venció sin marcarse como cumplido, a quien supervisa y al responsable;
    4) sin responsable asignado, avisa a quien supervisa desde el primer aviso."""
    if e.estado != "pendiente":
        return []
    ref = ref or hoy()
    faltan = (e.fecha - ref).days
    avisos = alertas_de(db, e)
    res = []
    if faltan < 0:
        res.append({"nivel": "vencido", "clave": "vencido", "a": "todos"})
        return res
    tocan = [k for k in avisos if k >= faltan]
    if tocan:
        k = min(tocan)
        res.append({"nivel": "hoy" if faltan == 0 else "anticipado", "clave": f"d{k}", "a": "equipo" if e.responsable_id else "todos"})
    if faltan == 0:
        res.append({"nivel": "escalado", "clave": "escalado", "a": "supervision"})
    return res
