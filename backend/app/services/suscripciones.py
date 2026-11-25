"""Periodos de venta de cada cliente: prueba gratuita de 2 días, mensual, semestral y anual.

Fechas inclusivas: un plan mensual que inicia el 17 de noviembre cubre hasta el 16 de diciembre.
El estado se calcula siempre a partir del historial; no se guarda (no puede desincronizarse).
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .. import models as m
from ..config import ajustes

PLANES = {  # clave: (nombre, meses; None = días fijos)
    "prueba": ("Prueba gratuita (2 días)", None),
    "mensual": ("Mensual", 1),
    "semestral": ("Semestral", 6),
    "anual": ("Anual", 12),
}
DIAS_PRUEBA = 2
AVISO_DIAS = 7  # «por vencer» cuando faltan 7 días o menos


def hoy() -> date:
    return datetime.now(ZoneInfo(ajustes().zona_horaria)).date()


def sumar_meses(d: date, meses: int) -> date:
    """Mismo día N meses después; si ese mes es más corto, el último día del mes (31 ene + 1 = 28/29 feb)."""
    total = d.month - 1 + meses
    anio, mes = d.year + total // 12, total % 12 + 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def calcular_fin(plan: str, inicio: date) -> date:
    _, meses = PLANES[plan]
    if meses is None:
        return inicio + timedelta(days=DIAS_PRUEBA - 1)
    return sumar_meses(inicio, meses) - timedelta(days=1)


def p_dict(p: m.PeriodoSuscripcion, ref: date | None = None) -> dict:
    ref = ref or hoy()
    situacion = "vigente" if p.inicio <= ref <= p.fin else "futuro" if p.inicio > ref else "terminado"
    return {"id": p.id, "plan": p.plan, "plan_nombre": PLANES[p.plan][0], "inicio": p.inicio.isoformat(),
            "fin": p.fin.isoformat(), "monto": str(p.monto) if p.monto is not None else None, "pagado": p.pagado,
            "pagado_en": p.pagado_en.isoformat() if p.pagado_en else None, "nota": p.nota, "situacion": situacion,
            "creado_en": p.creado_en.isoformat() if p.creado_en else None}


def estado(periodos: list[m.PeriodoSuscripcion], ref: date | None = None) -> dict:
    """Resumen para el panel. `estado` es uno de: sin_plan, prueba, activa, por_vencer, vencida, programada."""
    ref = ref or hoy()
    ps = sorted(periodos, key=lambda p: (p.inicio, p.id))
    vigente = next((p for p in reversed(ps) if p.inicio <= ref <= p.fin), None)
    futuros = [p for p in ps if p.inicio > ref]
    pendientes = [p for p in ps if p.plan != "prueba" and not p.pagado]
    base = {"tuvo_prueba": any(p.plan == "prueba" for p in ps), "pagos_pendientes": len(pendientes),
            "monto_pendiente": str(sum((p.monto or 0) for p in pendientes)) if pendientes else None,
            "siguiente": p_dict(futuros[0], ref) if futuros else None,
            "sugerido_inicio": max(ref, ps[-1].fin + timedelta(days=1)).isoformat() if ps else ref.isoformat()}
    if vigente:
        dias = (vigente.fin - ref).days
        if vigente.plan == "prueba":
            e = "prueba"
        elif dias < AVISO_DIAS and not futuros:  # con la renovación ya registrada no hay alarma
            e = "por_vencer"
        else:
            e = "activa"
        return {**base, "estado": e, "plan": vigente.plan, "plan_nombre": PLANES[vigente.plan][0],
                "inicio": vigente.inicio.isoformat(), "fin": vigente.fin.isoformat(), "dias_restantes": dias + 1}
    if futuros:
        return {**base, "estado": "programada", "plan": futuros[0].plan, "plan_nombre": PLANES[futuros[0].plan][0],
                "inicio": futuros[0].inicio.isoformat(), "fin": futuros[0].fin.isoformat(), "dias_restantes": None}
    if ps:
        ult = ps[-1]
        return {**base, "estado": "vencida", "plan": ult.plan, "plan_nombre": PLANES[ult.plan][0],
                "inicio": ult.inicio.isoformat(), "fin": ult.fin.isoformat(), "dias_vencida": (ref - ult.fin).days}
    return {**base, "estado": "sin_plan", "plan": None, "plan_nombre": None, "inicio": None, "fin": None}
