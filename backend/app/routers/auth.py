import re
import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, ip_cliente, solo_admin, usuario_actual
from ..freno import FrenoAcceso
from ..models import ahora
from ..services import dos_pasos, fotos, modulos
from ..security import ROLES, crear_token, gastar_tiempo_de_verificacion, hash_contrasena, verificar_contrasena

router = APIRouter(prefix="/api", tags=["autenticación y usuarios"])
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_intentos = FrenoAcceso()  # freno en memoria contra fuerza bruta (vea app/freno.py)


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


class PerfilCambio(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)


class CambioContrasena(BaseModel):
    actual: str = Field(max_length=128)
    nueva: str = Field(min_length=10, max_length=128)


def _u(u: m.Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "email": u.email, "rol": u.rol, "activo": u.activo,
            "organizacion_id": u.organizacion_id, "creado_en": u.creado_en.isoformat(),
            "foto": fotos.data_url(u.foto), "dos_pasos": dos_pasos.activo(u)}


def _de_mi_org(db: Session, uid: int, u: m.Usuario) -> m.Usuario:
    x = db.scalar(select(m.Usuario).where(m.Usuario.id == uid, m.Usuario.organizacion_id == u.organizacion_id,
                                          m.Usuario.eliminado_en.is_(None)))
    if not x:
        raise HTTPException(404, "No encontrado.")
    return x


def _otros_admins_activos(db: Session, x: m.Usuario) -> int:
    return db.scalar(select(func.count()).select_from(m.Usuario).where(
        m.Usuario.organizacion_id == x.organizacion_id, m.Usuario.rol == "administrador",
        m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None), m.Usuario.id != x.id))


def _leer_foto(archivo: UploadFile) -> bytes:
    datos = archivo.file.read(fotos.MAX_BYTES + 1)
    try:
        return fotos.procesar(datos)
    except fotos.FotoInvalida as e:
        raise HTTPException(422, str(e))


def _email(e: str) -> str:
    e = e.strip().lower()
    if not _RE_EMAIL.match(e) or len(e) > 254:
        raise HTTPException(422, "Correo electrónico inválido.")
    return e


@router.post("/auth/login")
def login(c: Credenciales, request: Request, db: Session = Depends(get_db)):
    email = c.email.strip().lower()
    ip = ip_cliente(request) or "-"
    if _intentos.bloqueado(ip, email):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    u = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if u and u.activo:
        valida = verificar_contrasena(c.contrasena, u.hash_contrasena)
    else:
        gastar_tiempo_de_verificacion(c.contrasena)  # mismo tiempo exista o no el correo
        valida = False
    if not valida:
        _intentos.fallo(ip, email)
        auditar(db, None, "login_fallido", request=request, organizacion_id=u.organizacion_id if u else None)
        db.commit()
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    _intentos.exito(ip, email)
    org = db.get(m.Organizacion, u.organizacion_id)
    if org.estado != "activa":  # solo se dice tras validar la contraseña: no revela cuentas
        auditar(db, u, "login_rechazado_suspension", request=request)
        db.commit()
        raise HTTPException(403, "La cuenta de su organización está suspendida. Contacte a soporte de Nomira.")
    if dos_pasos.activo(u):  # contraseña correcta: falta el código de la app
        auditar(db, u, "login_paso_1", request=request)
        db.commit()
        return {"requiere_codigo": True, "reto": dos_pasos.crear_reto("usuario", u.id, u.sesion_version)}
    auditar(db, u, "login", request=request)
    db.commit()
    return _sesion(db, u, org)


def _sesion(db: Session, u: m.Usuario, org: m.Organizacion) -> dict:
    return {"token": crear_token(u.id, u.organizacion_id, u.sesion_version), "usuario": _u(u),
            "organizacion": org.nombre, "modulos": modulos.activos(db, u.organizacion_id)}


class SegundoPaso(BaseModel):
    reto: str = Field(max_length=2000)
    codigo: str = Field(max_length=20)


@router.post("/auth/login/codigo")
def login_codigo(d: SegundoPaso, request: Request, db: Session = Depends(get_db)):
    """Segundo paso: código de 6 dígitos de la app (o uno de respaldo). El reto caduca en 5 minutos."""
    ip = ip_cliente(request) or "-"
    datos = dos_pasos.leer_reto(d.reto, "usuario")
    if not datos:
        raise HTTPException(401, "El inicio de sesión caducó. Vuelva a escribir su contraseña.")
    llave = f"2p:{datos['sub']}"
    if _intentos.bloqueado(ip, llave):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    u = db.get(m.Usuario, int(datos["sub"]))
    if not u or not u.activo or u.eliminado_en or u.sesion_version != datos.get("ver") or not dos_pasos.activo(u):
        raise HTTPException(401, "El inicio de sesión caducó. Vuelva a escribir su contraseña.")
    via = dos_pasos.verificar(u, d.codigo)
    if not via:
        _intentos.fallo(ip, llave)
        auditar(db, u, "login_codigo_fallido", request=request)
        db.commit()
        raise HTTPException(401, "Código incorrecto o ya usado.")
    _intentos.exito(ip, llave)
    org = db.get(m.Organizacion, u.organizacion_id)
    if org.estado != "activa":
        raise HTTPException(403, "La cuenta de su organización está suspendida. Contacte a soporte de Nomira.")
    auditar(db, u, "login", request=request, detalle={"dos_pasos": via})
    db.commit()
    r = _sesion(db, u, org)
    if via == "respaldo":
        r["aviso"] = f"Usó un código de respaldo. Le quedan {len(u.totp_respaldo or [])}."
    return r


@router.get("/publico")
def publico(db: Session = Depends(get_db)):
    """Datos no sensibles para la página de inicio. Por defecto NO se publican precios; si Nomira lo
    elige, solo el «desde» (el precio más bajo de los paquetes activos), nunca el desglose."""
    from ..services.comercial import base as cm

    digitos = re.sub(r"\D", "", ajustes().whatsapp_contacto)
    desde = None
    c = db.scalar(select(m.CmConfig))
    if c and c.precios_publicos == "desde":
        minimo = db.scalar(select(func.min(m.CmPaquete.precio_mensual)).where(m.CmPaquete.estado == "activo"))
        desde = cm.txt(minimo) if minimo is not None else None
    return {"permitir_registro": ajustes().permitir_registro, "whatsapp": digitos if 10 <= len(digitos) <= 15 else None,
            "precio_desde": desde}


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
    return {"token": crear_token(u.id, org.id, u.sesion_version), "usuario": _u(u), "organizacion": org.nombre,
            "modulos": modulos.activos(db, org.id)}


@router.get("/auth/yo")
def yo(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return {"usuario": _u(u), "organizacion": db.get(m.Organizacion, u.organizacion_id).nombre,
            "ia_habilitada": ajustes().ia_habilitada, "max_mb_archivo": ajustes().max_mb_archivo,
            "permitir_registro": ajustes().permitir_registro, "modulos": modulos.activos(db, u.organizacion_id)}


@router.get("/usuarios")
def listar(u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    return [_u(x) for x in db.scalars(select(m.Usuario).where(
        m.Usuario.organizacion_id == u.organizacion_id, m.Usuario.eliminado_en.is_(None)).order_by(m.Usuario.nombre))]


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
    x = _de_mi_org(db, uid, u)
    if d.rol is not None and d.rol not in ROLES:
        raise HTTPException(422, "Rol inválido.")
    deja_de_ser_admin = x.rol == "administrador" and x.activo and (
        (d.rol is not None and d.rol != "administrador") or d.activo is False)
    if deja_de_ser_admin:
        if not _otros_admins_activos(db, x):
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
        if not d.activo:
            x.sesion_version += 1  # al reactivarlo no reviven sus sesiones anteriores
    if d.contrasena:
        x.hash_contrasena = hash_contrasena(d.contrasena)
        x.sesion_version += 1  # cierra todas sus sesiones abiertas
        cambios["contrasena"] = "cambiada"
    auditar(db, u, "usuario_modificado", "usuario", x.id, cambios, request)
    db.commit()
    return _u(x)


@router.delete("/usuarios/{uid}")
def eliminar(uid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Baja lógica: deja de aparecer y de poder entrar. Su correo queda libre para darlo de alta
    de nuevo; correcciones, validaciones y auditoría conservan quién hizo cada cosa."""
    x = _de_mi_org(db, uid, u)
    if x.id == u.id:
        raise HTTPException(409, "No puede eliminar su propia cuenta.")
    if x.rol == "administrador" and x.activo and not _otros_admins_activos(db, x):
        raise HTTPException(409, "La organización debe conservar al menos un administrador activo.")
    auditar(db, u, "usuario_eliminado", "usuario", x.id, {"email": x.email, "rol": x.rol}, request)
    x.email = f"eliminado-{x.id}-{secrets.token_hex(4)}@baja.invalid"  # libera el correo (es único)
    x.activo, x.foto, x.eliminado_en = False, None, ahora()
    x.hash_contrasena = "!"  # ningún hash bcrypt coincide con esto
    x.sesion_version += 1
    db.commit()
    return {"ok": True}


@router.post("/usuarios/{uid}/foto")
def foto_de_usuario(uid: int, request: Request, archivo: UploadFile = File(...),
                          u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    x = _de_mi_org(db, uid, u)
    x.foto = _leer_foto(archivo)
    auditar(db, u, "usuario_foto", "usuario", x.id, request=request)
    db.commit()
    return _u(x)


@router.delete("/usuarios/{uid}/foto")
def quitar_foto_de_usuario(uid: int, request: Request, u: m.Usuario = Depends(solo_admin),
                           db: Session = Depends(get_db)):
    x = _de_mi_org(db, uid, u)
    x.foto = None
    auditar(db, u, "usuario_foto_quitada", "usuario", x.id, request=request)
    db.commit()
    return _u(x)


# ---------- mi perfil (cualquier rol) ----------

@router.patch("/auth/yo")
def cambiar_perfil(d: PerfilCambio, request: Request, u: m.Usuario = Depends(usuario_actual),
                   db: Session = Depends(get_db)):
    u.nombre = d.nombre.strip()
    auditar(db, u, "perfil_modificado", "usuario", u.id, {"nombre": True}, request)
    db.commit()
    return _u(u)


@router.post("/auth/yo/contrasena")
def cambiar_mi_contrasena(d: CambioContrasena, request: Request, u: m.Usuario = Depends(usuario_actual),
                          db: Session = Depends(get_db)):
    """Exige la contraseña actual. Cierra las demás sesiones y devuelve un token nuevo para esta."""
    if not verificar_contrasena(d.actual, u.hash_contrasena):
        raise HTTPException(422, "La contraseña actual no es correcta.")
    if d.nueva == d.actual:
        raise HTTPException(422, "La nueva contraseña debe ser distinta de la actual.")
    u.hash_contrasena = hash_contrasena(d.nueva)
    u.sesion_version += 1
    auditar(db, u, "contrasena_cambiada", "usuario", u.id, request=request)
    db.commit()
    return {"token": crear_token(u.id, u.organizacion_id, u.sesion_version), "usuario": _u(u)}


@router.post("/auth/yo/foto")
def mi_foto(request: Request, archivo: UploadFile = File(...), u: m.Usuario = Depends(usuario_actual),
                  db: Session = Depends(get_db)):
    u.foto = _leer_foto(archivo)
    auditar(db, u, "perfil_foto", "usuario", u.id, request=request)
    db.commit()
    return _u(u)


@router.delete("/auth/yo/foto")
def quitar_mi_foto(request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    u.foto = None
    auditar(db, u, "perfil_foto_quitada", "usuario", u.id, request=request)
    db.commit()
    return _u(u)


@router.get("/auditoria")
def auditoria(limite: int = 200, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    filas = db.scalars(select(m.Auditoria).where(m.Auditoria.organizacion_id == u.organizacion_id)
                       .order_by(m.Auditoria.id.desc()).limit(min(max(limite, 1), 1000)))
    return [{"id": a.id, "fecha": a.fecha.isoformat(), "usuario": a.usuario_email, "accion": a.accion,
             "entidad": a.entidad, "entidad_id": a.entidad_id, "detalle": a.detalle, "ip": a.ip} for a in filas]


# ------------------------------------------------------------------ verificación en dos pasos

class ConContrasena(BaseModel):
    contrasena: str = Field(max_length=128)


class ConCodigo(BaseModel):
    codigo: str = Field(max_length=20)


class QuitarDosPasos(BaseModel):
    contrasena: str = Field(max_length=128)
    codigo: str = Field(max_length=20)


@router.get("/auth/yo/dos-pasos")
def mis_dos_pasos(u: m.Usuario = Depends(usuario_actual)):
    return dos_pasos.estado(u)


@router.post("/auth/yo/dos-pasos/preparar")
def preparar_dos_pasos(d: ConContrasena, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if dos_pasos.activo(u):
        raise HTTPException(409, "La verificación en dos pasos ya está activa.")
    if not verificar_contrasena(d.contrasena, u.hash_contrasena):
        raise HTTPException(422, "La contraseña no es correcta.")
    secreto = dos_pasos.preparar(u)
    auditar(db, u, "dos_pasos_preparado", request=request)
    db.commit()
    url = dos_pasos.uri(u.email, secreto)
    return {"secreto": secreto, "uri": url, "qr_svg": dos_pasos.qr_svg(url)}


@router.post("/auth/yo/dos-pasos/activar")
def activar_dos_pasos(d: ConCodigo, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    cods = dos_pasos.activar(u, d.codigo)
    if not cods:
        raise HTTPException(422, "El código no coincide. Revise que la hora de su celular sea automática e intente con el código nuevo.")
    auditar(db, u, "dos_pasos_activado", request=request)
    db.commit()
    return {"codigos_respaldo": cods, **dos_pasos.estado(u)}


@router.post("/auth/yo/dos-pasos/respaldo")
def nuevos_respaldo(d: ConCodigo, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if not dos_pasos.activo(u) or dos_pasos.verificar(u, d.codigo) != "app":
        raise HTTPException(422, "Escriba el código actual de su app.")
    cods, u.totp_respaldo = dos_pasos.codigos_respaldo()
    auditar(db, u, "dos_pasos_respaldo_nuevos", request=request)
    db.commit()
    return {"codigos_respaldo": cods, **dos_pasos.estado(u)}


@router.post("/auth/yo/dos-pasos/desactivar")
def desactivar_dos_pasos(d: QuitarDosPasos, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if not dos_pasos.activo(u):
        raise HTTPException(409, "La verificación en dos pasos no está activa.")
    if not verificar_contrasena(d.contrasena, u.hash_contrasena) or not dos_pasos.verificar(u, d.codigo):
        raise HTTPException(422, "La contraseña o el código no son correctos.")
    dos_pasos.quitar(u)
    auditar(db, u, "dos_pasos_desactivado", request=request)
    db.commit()
    return dos_pasos.estado(u)


@router.post("/usuarios/{uid}/dos-pasos/quitar")
def quitar_dos_pasos_de_usuario(uid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Para quien perdió su celular y sus códigos de respaldo. Cierra sus sesiones; al entrar podrá activarla de nuevo."""
    x = _de_mi_org(db, uid, u)
    if x.id == u.id:
        raise HTTPException(409, "Para su propia cuenta use Mi perfil.")
    dos_pasos.quitar(x)
    x.sesion_version += 1
    auditar(db, u, "dos_pasos_quitado_por_admin", "usuario", x.id, request=request)
    db.commit()
    return _u(x)


@router.post("/auth/yo/cerrar-sesiones")
def cerrar_sesiones(request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Cierra la sesión en todos los demás navegadores y dispositivos; esta sigue abierta con un token nuevo."""
    u.sesion_version += 1
    auditar(db, u, "sesiones_cerradas", request=request)
    db.commit()
    return {"token": crear_token(u.id, u.organizacion_id, u.sesion_version), "usuario": _u(u)}
