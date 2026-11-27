"""Rutas públicas de crecimiento (sin sesión):
- /api/invitacion/{codigo}: a qué despacho pertenece una invitación (solo su nombre).
- /api/publico/abogados: si hay un despacho de la red disponible en un estado (sí o no).
- /api/publico/quiero-abogado: la persona que calculó su finiquito pide que un abogado revise su caso.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, ip_cliente
from ..freno import Ventana
from ..services.agenda.base import hoy
from ..services.crecimiento import base, red
from ..services.leads import base as leads
from ..services.liquidacion import motor
from .liquidaciones import DatosIn, _motor

router = APIRouter(tags=["Crecimiento — público"])
_consultas_ip = Ventana(60, 600)
_casos_ip = Ventana(5, 3600)


def _freno(v: Ventana, request: Request) -> None:
    ip = ip_cliente(request) or "?"
    if v.excedida(ip):
        raise HTTPException(429, "Demasiadas solicitudes seguidas. Intente más tarde.")
    v.registrar(ip)


@router.get("/api/invitacion/{codigo}")
def invitacion(codigo: str, request: Request, db: Session = Depends(get_db)):
    _freno(_consultas_ip, request)
    inv = base.buscar_invitacion(db, codigo)
    org = db.get(m.Organizacion, inv.organizacion_id) if inv else None
    if not org or org.estado != "activa" or not base.config(db).referidos_activos:
        raise HTTPException(404, "Esta invitación no existe o ya no está vigente.")
    c = base.config(db)
    db.commit()
    return {"despacho": org.nombre, "codigo": inv.codigo, "meses": c.meses_referido}


@router.get("/api/publico/abogados")
def hay_abogado(request: Request, estado: str = Query(..., max_length=4), db: Session = Depends(get_db)):
    _freno(_consultas_ip, request)
    return {"estados": red.ESTADOS_MX, "activo": base.config(db).casos_activos, "disponible": red.disponible(db, estado)}


class CasoIn(BaseModel):
    estado: str = Field(max_length=4)
    nombre: str = Field(min_length=2, max_length=200)
    telefono: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=254)
    mensaje: str | None = Field(None, max_length=1000)
    acepta: bool = False
    calculo: DatosIn | None = None
    sitio_web: str | None = Field(None, max_length=200)  # campo trampa


@router.post("/api/publico/quiero-abogado", status_code=201)
def quiero_abogado(d: CasoIn, request: Request, db: Session = Depends(get_db)):
    _freno(_casos_ip, request)
    if d.sitio_web:  # robot: misma respuesta, sin hacer nada
        return {"ok": True, "despacho": None}
    if not d.acepta:
        raise HTTPException(422, "Necesitamos su autorización para que un despacho le contacte.")
    if d.estado not in red.ESTADOS_MX:
        raise HTTPException(422, "Elija su estado.")
    tel = leads.telefono(d.telefono) if d.telefono else None
    email = (d.email or "").strip().lower() or None
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "El correo no parece válido.")
    if not tel and not email:
        raise HTTPException(422, "Escriba un teléfono o un correo para que puedan contactarle.")
    resumen = None
    if d.calculo:
        try:
            r = motor.calcular(_motor(d.calculo), hoy())
            resumen = (f"Su cálculo: {r['causa_nombre']}; ingreso {d.calculo.fecha_ingreso}, baja {d.calculo.fecha_baja}, "
                       f"salario diario ${float(d.calculo.salario_diario):,.2f}; total estimado ${float(r['total']):,.2f}.")
        except Exception:  # un cálculo incompleto no impide pedir ayuda
            resumen = None
    if not base.config(db).casos_activos:
        raise HTTPException(409, "Por ahora no estamos recibiendo casos. Intente más tarde.")
    caso = red.entregar(db, estado=d.estado, nombre=" ".join(d.nombre.split())[:200], tel=tel, email=email,
                        mensaje=(d.mensaje or "").strip()[:1000] or None, resumen=resumen)
    if not caso:
        raise HTTPException(409, "En este momento no hay un despacho disponible en su estado. Sus datos no se guardaron.")
    org = db.get(m.Organizacion, caso.organizacion_id)
    auditar(db, None, "caso_nomira_asignado", "cx_caso", caso.id, {"estado": d.estado}, request, organizacion_id=org.id)
    db.commit()
    return {"ok": True, "despacho": org.nombre}
