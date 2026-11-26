"""Club Nomira en público: verificar una credencial, el logotipo de un aliado y el formulario «Quiero ser aliado»."""
from __future__ import annotations

import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..freno import Ventana
from ..services.club import base as cb

router = APIRouter(prefix="/api/club-publico", tags=["Club Nomira — público"])
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RE_TEL = re.compile(r"^[\d\s()+.\-]{7,25}$")
_RE_COD = re.compile(r"^NM-[A-Z2-9]{4}-[A-Z2-9]{4}$")
_verif = Ventana(60, 3600)
_envios: dict[str, list[float]] = {}


@router.get("/verificar/{codigo}")
def verificar(codigo: str, request: Request, db: Session = Depends(get_db)):
    """Para el comercio: ¿esta credencial es de un miembro vigente? Muestra nombre y despacho, nada más."""
    ip = ip_cliente(request) or "?"
    if _verif.excedida(ip):
        raise HTTPException(429, "Demasiadas consultas. Intente más tarde.")
    _verif.registrar(ip)
    codigo = codigo.strip().upper()
    c = db.scalar(select(m.AlCredencial).where(m.AlCredencial.codigo == codigo)) if _RE_COD.match(codigo) else None
    if not c:
        return {"valida": False, "mensaje": "No encontramos esta credencial."}
    u = db.get(m.Usuario, c.usuario_id)
    if not cb.miembro_vigente(db, u):
        return {"valida": False, "mensaje": "Esta credencial no está vigente."}
    o = db.get(m.Organizacion, u.organizacion_id)
    return {"valida": True, "nombre": u.nombre, "despacho": o.nombre, "codigo": c.codigo}


@router.get("/logos/{aid}")
def logo(aid: int, db: Session = Depends(get_db)):
    a = db.get(m.AlAliado, aid)
    if not a or a.estado != "activo" or not a.logo:
        raise HTTPException(404, "Sin logotipo.")
    return Response(a.logo, media_type="image/png", headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"})


class Postulacion(BaseModel):
    empresa: str = Field(min_length=2, max_length=200)
    giro: str | None = Field(None, max_length=120)
    nombre: str = Field(min_length=2, max_length=200)
    email: str = Field(max_length=254)
    telefono: str | None = Field(None, max_length=40)
    propuesta: str | None = Field(None, max_length=2000)
    acepta_contacto: bool
    sitio_web: str | None = Field(None, max_length=200)  # trampa para bots: debe llegar vacío


def _limpio(s: str | None) -> str | None:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s or "").strip()
    return s or None


@router.post("/aliados", status_code=201)
def postular(d: Postulacion, request: Request, db: Session = Depends(get_db)):
    ip = ip_cliente(request) or "-"
    ahora = time.time()
    recientes = [t for t in _envios.get(ip, []) if ahora - t < 3600]
    if len(recientes) >= 5:
        raise HTTPException(429, "Recibimos varias solicitudes desde su conexión. Intente más tarde.")
    if not d.acepta_contacto:
        raise HTTPException(422, "Debe aceptar que le contactemos para atender su solicitud.")
    email = d.email.strip().lower()
    if not _RE_EMAIL.match(email):
        raise HTTPException(422, "Correo electrónico inválido.")
    tel = _limpio(d.telefono)
    if tel and not _RE_TEL.match(tel):
        raise HTTPException(422, "Teléfono inválido.")
    _envios[ip] = recientes + [ahora]
    if _limpio(d.sitio_web):
        return {"ok": True}
    db.add(m.AlSolicitud(empresa=_limpio(d.empresa), giro=_limpio(d.giro), nombre=_limpio(d.nombre), email=email, telefono=tel,
                         propuesta=_limpio(d.propuesta), estado="nueva", ip=ip[:60]))
    db.commit()
    return {"ok": True}
