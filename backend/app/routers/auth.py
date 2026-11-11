import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, solo_admin, usuario_actual
from ..security import ROLES, crear_token, hash_contrasena, verificar_contrasena

router = APIRouter(prefix="/api", tags=["autenticación y usuarios"])
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_intentos: dict[str, list[float]] = {}  # freno simple en memoria contra fuerza bruta


class Credenciales(BaseModel):
    email: str
    contrasena: str


class Registro(BaseModel):
    organizacion: str = Field(min_length=2, max_length=200)
    nombre: str = Field(min_length=2, max_length=200)
    email: str
    contrasena: str = Field(min_length=10, max_length=128)


class UsuarioNuevo(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    email: str
    contrasena: str = Field(min_length=10, max_length=128)
    rol: str


class UsuarioCambio(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=200)
    rol: str | None = None
    activo: bool | None = None
    contrasena: str | None = Field(None, min_length=10, max_length=128)


def _u(u: m.Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "email": u.email, "rol": u.rol, "activo": u.activo,
            "organizacion_id": u.organizacion_id, "creado_en": u.creado_en.isoformat()}


def _email(e: str) -> str:
    e = e.strip().lower()
    if not _RE_EMAIL.match(e) or len(e) > 254:
        raise HTTPException(422, "Correo electrónico inválido.")
    return e


@router.post("/auth/login")
def login(c: Credenciales, request: Request, db: Session = Depends(get_db)):
    email = c.email.strip().lower()
    llave = f"{request.client.host if request.client else '-'}|{email}"
    ahora = time.time()
    recientes = [t for t in _intentos.get(llave, []) if ahora - t < 300]
    if len(recientes) >= 8:
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    u = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not u or not u.activo or not verificar_contrasena(c.contrasena, u.hash_contrasena):
        _intentos[llave] = recientes + [ahora]
        auditar(db, None, "login_fallido", request=request, organizacion_id=u.organizacion_id if u else None)
        db.commit()
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    _intentos.pop(llave, None)
    auditar(db, u, "login", request=request)
    db.commit()
    org = db.get(m.Organizacion, u.organizacion_id)
    return {"token": crear_token(u.id, u.organizacion_id), "usuario": _u(u), "organizacion": org.nombre}


@router.post("/auth/registro", status_code=201)
def registro(r: Registro, request: Request, db: Session = Depends(get_db)):
    """Alta de una organización nueva con su primer administrador."""
    if not ajustes().permitir_registro:
        raise HTTPException(403, "El registro de organizaciones está deshabilitado.")
    email = _email(r.email)
    if db.scalar(select(m.Usuario.id).where(m.Usuario.email == email)):
        raise HTTPException(409, "Ese correo ya está registrado.")
    org = m.Organizacion(nombre=r.organizacion.strip())
    db.add(org)
    db.flush()
    u = m.Usuario(organizacion_id=org.id, email=email, nombre=r.nombre.strip(),
                  hash_contrasena=hash_contrasena(r.contrasena), rol="administrador")
    db.add(u)
    db.flush()
    auditar(db, u, "organizacion_creada", "organizacion", org.id, request=request)
    db.commit()
    return {"token": crear_token(u.id, org.id), "usuario": _u(u), "organizacion": org.nombre}


@router.get("/auth/yo")
def yo(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return {"usuario": _u(u), "organizacion": db.get(m.Organizacion, u.organizacion_id).nombre,
            "ia_habilitada": ajustes().ia_habilitada, "max_mb_archivo": ajustes().max_mb_archivo}


@router.get("/usuarios")
def listar(u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    return [_u(x) for x in db.scalars(select(m.Usuario).where(
        m.Usuario.organizacion_id == u.organizacion_id).order_by(m.Usuario.nombre))]


@router.post("/usuarios", status_code=201)
def crear(d: UsuarioNuevo, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    if d.rol not in ROLES:
        raise HTTPException(422, "Rol inválido.")
    email = _email(d.email)
    if db.scalar(select(m.Usuario.id).where(m.Usuario.email == email)):
        raise HTTPException(409, "Ese correo ya está registrado.")
    nuevo = m.Usuario(organizacion_id=u.organizacion_id, email=email, nombre=d.nombre.strip(),
                      hash_contrasena=hash_contrasena(d.contrasena), rol=d.rol)
    db.add(nuevo)
    db.flush()
    auditar(db, u, "usuario_creado", "usuario", nuevo.id, {"rol": d.rol}, request)
    db.commit()
    return _u(nuevo)


@router.patch("/usuarios/{uid}")
def cambiar(uid: int, d: UsuarioCambio, request: Request, u: m.Usuario = Depends(solo_admin),
            db: Session = Depends(get_db)):
    x = db.scalar(select(m.Usuario).where(m.Usuario.id == uid, m.Usuario.organizacion_id == u.organizacion_id))
    if not x:
        raise HTTPException(404, "No encontrado.")
    if d.rol is not None and d.rol not in ROLES:
        raise HTTPException(422, "Rol inválido.")
    deja_de_ser_admin = x.rol == "administrador" and x.activo and (
        (d.rol is not None and d.rol != "administrador") or d.activo is False)
    if deja_de_ser_admin:
        otros = db.scalar(select(func.count()).select_from(m.Usuario).where(
            m.Usuario.organizacion_id == u.organizacion_id, m.Usuario.rol == "administrador",
            m.Usuario.activo.is_(True), m.Usuario.id != x.id))
        if not otros:
            raise HTTPException(409, "La organización debe conservar al menos un administrador activo.")
    cambios = {}
    if d.nombre is not None:
        x.nombre = d.nombre.strip()
        cambios["nombre"] = True
    if d.rol is not None and d.rol != x.rol:
        cambios["rol"] = [x.rol, d.rol]
        x.rol = d.rol
    if d.activo is not None and d.activo != x.activo:
        cambios["activo"] = d.activo
        x.activo = d.activo
    if d.contrasena:
        x.hash_contrasena = hash_contrasena(d.contrasena)
        cambios["contrasena"] = "cambiada"
    auditar(db, u, "usuario_modificado", "usuario", x.id, cambios, request)
    db.commit()
    return _u(x)


@router.get("/auditoria")
def auditoria(limite: int = 200, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    filas = db.scalars(select(m.Auditoria).where(m.Auditoria.organizacion_id == u.organizacion_id)
                       .order_by(m.Auditoria.id.desc()).limit(min(max(limite, 1), 1000)))
    return [{"id": a.id, "fecha": a.fecha.isoformat(), "usuario": a.usuario_email, "accion": a.accion,
             "entidad": a.entidad, "entidad_id": a.entidad_id, "detalle": a.detalle} for a in filas]
