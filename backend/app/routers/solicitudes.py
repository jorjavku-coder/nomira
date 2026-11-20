"""Formulario público de informes y suscripción. La bandeja está en el panel de la plataforma
(routers/plataforma.py), al que no entra ningún usuario de una organización cliente."""
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..services import legal as lg

router = APIRouter(prefix="/api", tags=["solicitudes"])
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RE_TEL = re.compile(r"^[\d\s()+.\-]{7,25}$")
_envios: dict[str, list[float]] = {}  # freno simple en memoria por IP
VOLUMENES = {"1-10", "11-50", "51-200", "200+"}


class SolicitudNueva(BaseModel):
    tipo: str
    nombre: str = Field(min_length=2, max_length=200)
    empresa: str | None = Field(None, max_length=200)
    email: str = Field(max_length=254)
    telefono: str | None = Field(None, max_length=40)
    expedientes_mes: str | None = None
    mensaje: str | None = Field(None, max_length=2000)
    acepta_contacto: bool
    sitio_web: str | None = Field(None, max_length=200)  # trampa para bots: debe llegar vacío
    aviso_version_id: int | None = None  # aviso de privacidad simplificado que vio la persona (Centro Legal)
    marketing: bool = False  # consentimiento OPCIONAL para información comercial (solo si Nomira lo habilitó)


class Atencion(BaseModel):
    estado: str
    nota: str | None = Field(None, max_length=2000)


def _limpio(s: str | None) -> str | None:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s or "").strip()
    return s or None


@router.post("/solicitudes", status_code=201)
def crear(d: SolicitudNueva, request: Request, db: Session = Depends(get_db)):
    ip = ip_cliente(request) or "-"  # no se confía en X-Forwarded-For: el navegador puede falsificarlo
    ahora = time.time()
    recientes = [t for t in _envios.get(ip, []) if ahora - t < 3600]
    if len(recientes) >= 5:
        raise HTTPException(429, "Recibimos varias solicitudes desde su conexión. Intente más tarde.")
    if d.tipo not in ("informes", "suscripcion"):
        raise HTTPException(422, "Seleccione si desea informes o una suscripción.")
    if not d.acepta_contacto:
        raise HTTPException(422, "Debe aceptar que le contactemos para atender su solicitud.")
    email = d.email.strip().lower()
    if not _RE_EMAIL.match(email):
        raise HTTPException(422, "Correo electrónico inválido.")
    tel = _limpio(d.telefono)
    if tel and not _RE_TEL.match(tel):
        raise HTTPException(422, "Teléfono inválido.")
    if d.expedientes_mes and d.expedientes_mes not in VOLUMENES:
        raise HTTPException(422, "Volumen inválido.")
    _envios[ip] = recientes + [ahora]
    if _limpio(d.sitio_web):  # un bot llenó el campo oculto: se responde igual, sin guardar
        return {"ok": True}
    sol = m.Solicitud(tipo=d.tipo, nombre=_limpio(d.nombre), empresa=_limpio(d.empresa), email=email, telefono=tel,
                      expedientes_mes=d.expedientes_mes or None, mensaje=_limpio(d.mensaje), ip=ip[:60])
    db.add(sol)
    db.flush()
    # Evidencia mínima: qué versión del aviso se mostró junto al formulario y, si aplica, el consentimiento opcional
    aviso = lg.vigente(db, "privacidad_simplificado")
    if aviso and d.aviso_version_id == aviso.id:
        db.add(m.LgEvento(version_id=aviso.id, documento="privacidad_simplificado", evento="aviso_mostrado", contexto="formulario_informes",
                          solicitud_id=sol.id))
    if d.marketing and lg.config(db).marketing_habilitado:
        pv = lg.vigente(db, "privacidad")
        db.add(m.LgEvento(version_id=pv.id if pv else None, documento="privacidad", evento="marketing_otorgado", contexto="formulario_informes",
                          solicitud_id=sol.id))
    db.commit()
    return {"ok": True}


def _s(x: m.Solicitud) -> dict:
    return {"id": x.id, "tipo": x.tipo, "nombre": x.nombre, "empresa": x.empresa, "email": x.email,
            "telefono": x.telefono, "expedientes_mes": x.expedientes_mes, "mensaje": x.mensaje, "estado": x.estado,
            "nota": x.nota, "creado_en": x.creado_en.isoformat(),
            "atendida_en": x.atendida_en.isoformat() if x.atendida_en else None}
