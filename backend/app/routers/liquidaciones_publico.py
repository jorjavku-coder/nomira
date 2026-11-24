"""Calculadora pública de finiquito y liquidación (sitio web, sin sesión).

Herramienta gratuita para el sitio: no guarda nada, no pide datos personales y tiene límite por IP.
Usa el mismo motor que el módulo del despacho."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..deps import ip_cliente
from ..freno import Ventana
from ..services.agenda.base import hoy
from ..services.liquidacion import motor
from .liquidaciones import DatosIn, _motor

router = APIRouter(prefix="/api/publico", tags=["Calculadora pública"])
_por_ip = Ventana(40, 600)


@router.post("/finiquito")
def finiquito(d: DatosIn, request: Request):
    ip = ip_cliente(request) or "?"
    if _por_ip.excedida(ip):
        raise HTTPException(429, "Demasiados cálculos seguidos. Espere unos minutos.")
    _por_ip.registrar(ip)
    if len(d.horas_extra) > 10 or d.otros:
        raise HTTPException(422, "La calculadora gratuita admite hasta 10 periodos de horas extra.")
    try:
        return motor.calcular(_motor(d), hoy())
    except motor.ErrorDatos as e:
        raise HTTPException(422, str(e))
