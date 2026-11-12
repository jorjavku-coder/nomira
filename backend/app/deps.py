"""Dependencias comunes: usuario actual, roles y acceso SIEMPRE filtrado por organización."""
import ipaddress

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .config import ajustes
from .db import get_db
from .security import leer_token

_bearer = HTTPBearer(auto_error=False)


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                   db: Session = Depends(get_db)) -> m.Usuario:
    datos = leer_token(cred.credentials) if cred else None
    if not datos:
        raise HTTPException(401, "Sesión inválida o vencida.")
    u = db.get(m.Usuario, int(datos["sub"]))
    if (not u or not u.activo or u.organizacion_id != datos.get("org")
            or u.sesion_version != datos.get("ver", 0)):
        raise HTTPException(401, "Sesión inválida o vencida.")
    return u


def ip_cliente(request: Request | None) -> str | None:
    """IP del cliente. Solo se cree al encabezado configurado (lo pone un proxy de confianza);
    si falta o no es una IP válida, se usa la de la conexión."""
    if request is None:
        return None
    encabezado = ajustes().ip_cliente_encabezado.strip()
    if encabezado:
        valor = (request.headers.get(encabezado) or "").split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(valor))
        except ValueError:
            pass
    return request.client.host if request.client else None


def requiere(*roles: str):
    def dep(u: m.Usuario = Depends(usuario_actual)) -> m.Usuario:
        if u.rol not in roles:
            raise HTTPException(403, "Su rol no permite esta operación.")
        return u
    return dep


puede_editar = requiere("administrador", "analista")
solo_admin = requiere("administrador")


def obtener(db: Session, modelo, id_: int, u: m.Usuario):
    """Carga una entidad solo si pertenece a la organización del usuario. Responde 404
    (no 403) para no revelar la existencia de datos de otras organizaciones."""
    obj = db.scalar(select(modelo).where(modelo.id == id_, modelo.organizacion_id == u.organizacion_id))
    if obj is None:
        raise HTTPException(404, "No encontrado.")
    return obj


def auditar(db: Session, u: m.Usuario | None, accion: str, entidad: str | None = None,
            entidad_id: int | None = None, detalle: dict | None = None, request: Request | None = None,
            organizacion_id: int | None = None):
    """Registro de auditoría. El detalle no debe contener datos personales de los recibos."""
    db.add(m.Auditoria(
        organizacion_id=u.organizacion_id if u else organizacion_id, usuario_id=u.id if u else None,
        usuario_email=u.email if u else None, accion=accion, entidad=entidad, entidad_id=entidad_id,
        detalle=detalle, ip=ip_cliente(request)))
