"""Panel de quien opera Nomira: solicitudes de prospectos, cuentas de clientes y soporte.

Aislamiento: las sesiones de este panel solo valen aquí (vea security.leer_token_plataforma) y
este módulo nunca lee expedientes, recibos ni documentos; solo los cuenta. Toda acción sobre la
cuenta de un cliente queda en SU auditoría como «Soporte Nomira», para que el cliente la vea.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..freno import FrenoAcceso
from ..security import (ROLES, crear_token_plataforma, gastar_tiempo_de_verificacion, hash_contrasena,
                        leer_token_plataforma, verificar_contrasena)
from ..services import correo, dos_pasos, envios, modulos, plantillas_correo
from ..services import suscripciones as sus
from ..services.plataforma import borrar_archivos, contrasena_temporal, eliminar_organizacion
from . import auth as auth_clientes
from .solicitudes import Atencion, _s

router = APIRouter(prefix="/api/plataforma", tags=["plataforma"])
_bearer = HTTPBearer(auto_error=False)
_intentos = FrenoAcceso(por_cuenta=5, por_ip=20)
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- sesión ----------

def admin_plataforma(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                     db: Session = Depends(get_db)) -> m.AdminPlataforma:
    datos = leer_token_plataforma(cred.credentials) if cred else None
    if not datos:
        raise HTTPException(401, "Sesión inválida o vencida.")
    a = db.get(m.AdminPlataforma, int(datos["sub"]))
    if not a or not a.activo or a.sesion_version != datos.get("ver", 0):
        raise HTTPException(401, "Sesión inválida o vencida.")
    return a


ROLES_PLATAFORMA = {"superadministrador": "Superadministrador", "soporte": "Soporte"}


def superadmin(a: m.AdminPlataforma = Depends(admin_plataforma)) -> m.AdminPlataforma:
    """Solo el superadministrador de Nomira (módulo Comercial, roles de la plataforma)."""
    if a.rol != "superadministrador":
        raise HTTPException(403, "Solo un superadministrador de Nomira puede hacer esto.")
    return a


def _registrar(db: Session, a: m.AdminPlataforma, accion: str, request: Request | None = None, *,
               organizacion_id: int | None = None, entidad: str | None = None, entidad_id: int | None = None,
               detalle: dict | None = None) -> None:
    db.add(m.Auditoria(organizacion_id=organizacion_id, usuario_id=None, usuario_email=f"Soporte Nomira ({a.email})",
                       accion=accion, entidad=entidad, entidad_id=entidad_id, detalle=detalle, ip=ip_cliente(request)))


def _email(valor: str) -> str:
    e = valor.strip().lower()
    if not _RE_EMAIL.match(e):
        raise HTTPException(422, "Correo electrónico inválido.")
    return e


def _a(a: m.AdminPlataforma) -> dict:
    return {"id": a.id, "nombre": a.nombre, "email": a.email, "activo": a.activo, "rol": a.rol,
            "creado_en": a.creado_en.isoformat(), "ultimo_acceso": a.ultimo_acceso.isoformat() if a.ultimo_acceso else None,
            "dos_pasos": dos_pasos.activo(a)}


class Credenciales(BaseModel):
    email: str = Field(max_length=254)
    contrasena: str = Field(max_length=128)


class CambioContrasena(BaseModel):
    actual: str = Field(max_length=128)
    nueva: str = Field(min_length=12, max_length=128)


@router.post("/login")
def login(c: Credenciales, request: Request, db: Session = Depends(get_db)):
    email = c.email.strip().lower()
    ip = ip_cliente(request) or "-"
    if _intentos.bloqueado(ip, email):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    a = db.scalar(select(m.AdminPlataforma).where(m.AdminPlataforma.email == email))
    if a and a.activo:
        valida = verificar_contrasena(c.contrasena, a.hash_contrasena)
    else:
        gastar_tiempo_de_verificacion(c.contrasena)
        valida = False
    if not valida:
        _intentos.fallo(ip, email)
        db.add(m.Auditoria(usuario_email=f"plataforma:{email}", accion="plataforma_login_fallido", ip=ip[:60]))
        db.commit()
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    _intentos.exito(ip, email)
    if dos_pasos.activo(a):
        _registrar(db, a, "plataforma_login_paso_1", request)
        db.commit()
        return {"requiere_codigo": True, "reto": dos_pasos.crear_reto("plataforma", a.id, a.sesion_version)}
    a.ultimo_acceso = m.ahora()
    _registrar(db, a, "plataforma_login", request)
    db.commit()
    return {"token": crear_token_plataforma(a.id, a.sesion_version), "admin": _a(a)}


class SegundoPaso(BaseModel):
    reto: str = Field(max_length=2000)
    codigo: str = Field(max_length=20)


@router.post("/login/codigo")
def login_codigo(d: SegundoPaso, request: Request, db: Session = Depends(get_db)):
    ip = ip_cliente(request) or "-"
    datos = dos_pasos.leer_reto(d.reto, "plataforma")
    if not datos:
        raise HTTPException(401, "El inicio de sesión caducó. Vuelva a escribir su contraseña.")
    llave = f"2p:{datos['sub']}"
    if _intentos.bloqueado(ip, llave):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    a = db.get(m.AdminPlataforma, int(datos["sub"]))
    if not a or not a.activo or a.sesion_version != datos.get("ver") or not dos_pasos.activo(a):
        raise HTTPException(401, "El inicio de sesión caducó. Vuelva a escribir su contraseña.")
    via = dos_pasos.verificar(a, d.codigo)
    if not via:
        _intentos.fallo(ip, llave)
        _registrar(db, a, "plataforma_login_codigo_fallido", request)
        db.commit()
        raise HTTPException(401, "Código incorrecto o ya usado.")
    _intentos.exito(ip, llave)
    a.ultimo_acceso = m.ahora()
    _registrar(db, a, "plataforma_login", request, detalle={"dos_pasos": via})
    db.commit()
    r = {"token": crear_token_plataforma(a.id, a.sesion_version), "admin": _a(a)}
    if via == "respaldo":
        r["aviso"] = f"Usó un código de respaldo. Le quedan {len(a.totp_respaldo or [])}."
    return r


@router.get("/yo")
def yo(a: m.AdminPlataforma = Depends(admin_plataforma)):
    return {"admin": _a(a)}


@router.post("/yo/contrasena")
def mi_contrasena(d: CambioContrasena, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                  db: Session = Depends(get_db)):
    if not verificar_contrasena(d.actual, a.hash_contrasena):
        raise HTTPException(422, "La contraseña actual no es correcta.")
    if d.nueva == d.actual:
        raise HTTPException(422, "La nueva contraseña debe ser distinta de la actual.")
    a.hash_contrasena = hash_contrasena(d.nueva)
    a.sesion_version += 1
    _registrar(db, a, "plataforma_contrasena_cambiada", request)
    db.commit()
    return {"token": crear_token_plataforma(a.id, a.sesion_version), "admin": _a(a)}


# ---------- resumen ----------

@router.get("/resumen")
def resumen(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    contar = lambda q: db.scalar(select(func.count()).select_from(q.subquery()))  # noqa: E731
    return {
        "solicitudes_nuevas": contar(select(m.Solicitud.id).where(m.Solicitud.estado == "nueva")),
        "clientes_activos": contar(select(m.Organizacion.id).where(m.Organizacion.estado == "activa")),
        "clientes_suspendidos": contar(select(m.Organizacion.id).where(m.Organizacion.estado != "activa")),
        "tickets_abiertos": contar(select(m.TicketSoporte.id).where(m.TicketSoporte.estado == "abierto")),
        "tickets_sin_leer": contar(select(m.TicketSoporte.id).where(m.TicketSoporte.leido_plataforma.is_(False))),
        "usuarios_activos": contar(select(m.Usuario.id).where(m.Usuario.activo.is_(True))),
        "arco_pendientes": contar(select(m.LgSolicitud.id).where(m.LgSolicitud.estado.not_in(("atendida", "improcedente")))),
        **_conteo_suscripciones(db),
    }


def _periodos_por_org(db: Session, ids: list[int] | None = None) -> dict[int, list[m.PeriodoSuscripcion]]:
    q = select(m.PeriodoSuscripcion)
    if ids is not None:
        q = q.where(m.PeriodoSuscripcion.organizacion_id.in_(ids))
    grupos: dict[int, list] = defaultdict(list)
    for p in db.scalars(q):
        grupos[p.organizacion_id].append(p)
    return grupos


def _conteo_suscripciones(db: Session) -> dict:
    grupos = _periodos_por_org(db)
    estados = [sus.estado(grupos.get(oid, []))["estado"] for oid in db.scalars(select(m.Organizacion.id))]
    pendientes = sum(sus.estado(ps)["pagos_pendientes"] for ps in grupos.values())
    return {"en_prueba": estados.count("prueba"), "por_vencer": estados.count("por_vencer"),
            "vencidas": estados.count("vencida"), "sin_plan": estados.count("sin_plan"), "pagos_pendientes": pendientes}


# ---------- solicitudes de prospectos ----------

@router.get("/solicitudes")
def solicitudes(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    return [_s(x) for x in db.scalars(select(m.Solicitud).order_by(m.Solicitud.id.desc()).limit(500))]


@router.patch("/solicitudes/{sid}")
def atender(sid: int, d: Atencion, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
            db: Session = Depends(get_db)):
    x = db.get(m.Solicitud, sid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    if d.estado not in ("nueva", "atendida"):
        raise HTTPException(422, "Estado inválido.")
    x.estado, x.nota = d.estado, d.nota
    x.atendida_en = m.ahora() if d.estado == "atendida" else None
    _registrar(db, a, "solicitud_atendida", request, entidad="solicitud", entidad_id=x.id, detalle={"estado": d.estado})
    db.commit()
    return _s(x)


# ---------- clientes (organizaciones) ----------

class ClienteNuevo(BaseModel):
    organizacion: str = Field(min_length=2, max_length=200)
    admin_nombre: str = Field(min_length=2, max_length=200)
    admin_email: str = Field(max_length=254)
    plan: str | None = "prueba"  # periodo inicial desde hoy; None = sin plan por ahora
    enviar_correo: bool = True  # correo de bienvenida con su acceso
    modulos: list[str] | None = None  # contratados al dar de alta; None = solo Nómina y prestaciones


class PeriodoNuevo(BaseModel):
    plan: str
    inicio: date
    monto: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    pagado: bool = False
    nota: str | None = Field(None, max_length=500)


class PeriodoCambio(BaseModel):
    pagado: bool | None = None
    monto: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    nota: str | None = Field(None, max_length=500)


class ClienteCambio(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=200)
    estado: str | None = None
    motivo: str | None = Field(None, max_length=300)


class Eliminacion(BaseModel):
    confirmar_nombre: str


class UsuarioNuevo(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    email: str = Field(max_length=254)
    rol: str = "administrador"


class UsuarioCambio(BaseModel):
    activo: bool


def _cliente(db: Session, cid: int) -> m.Organizacion:
    o = db.get(m.Organizacion, cid)
    if not o:
        raise HTTPException(404, "Cliente no encontrado.")
    return o


def _metricas(db: Session, ids: list[int] | None = None) -> dict[int, dict]:
    """Solo números: nunca contenido de expedientes."""
    def por_org(col, *filtros, agregado=None):
        q = select(col, agregado if agregado is not None else func.count()).group_by(col)
        for f in filtros:
            q = q.where(f)
        if ids is not None:
            q = q.where(col.in_(ids))
        return dict(db.execute(q).all())
    vivos = m.Usuario.eliminado_en.is_(None)
    return {
        "usuarios": por_org(m.Usuario.organizacion_id, vivos),
        "usuarios_activos": por_org(m.Usuario.organizacion_id, vivos, m.Usuario.activo.is_(True)),
        "expedientes": por_org(m.Expediente.organizacion_id),
        "ultimo_acceso": por_org(m.Auditoria.organizacion_id, m.Auditoria.accion == "login",
                                 agregado=func.max(m.Auditoria.fecha)),
        "tickets_abiertos": por_org(m.TicketSoporte.organizacion_id, m.TicketSoporte.estado == "abierto"),
    }


def _c(o: m.Organizacion, met: dict, periodos: list | None = None) -> dict:
    ult = met["ultimo_acceso"].get(o.id)
    return {"suscripcion": sus.estado(periodos or []), "id": o.id, "nombre": o.nombre, "estado": o.estado, "motivo_suspension": o.motivo_suspension,
            "creado_en": o.creado_en.isoformat(), "usuarios": met["usuarios"].get(o.id, 0),
            "usuarios_activos": met["usuarios_activos"].get(o.id, 0), "expedientes": met["expedientes"].get(o.id, 0),
            "ultimo_acceso": ult.isoformat() if ult else None, "tickets_abiertos": met["tickets_abiertos"].get(o.id, 0)}


def _crear_cliente(db: Session, a: m.AdminPlataforma, d: ClienteNuevo, request: Request) -> dict:
    email = _email(d.admin_email)
    if db.scalar(select(m.Usuario.id).where(m.Usuario.email == email)):
        raise HTTPException(409, f"El correo {email} ya tiene una cuenta en Nomira.")
    o = m.Organizacion(nombre=d.organizacion.strip())
    db.add(o)
    db.flush()
    temporal = contrasena_temporal()
    u = m.Usuario(organizacion_id=o.id, email=email, nombre=d.admin_nombre.strip(),
                  hash_contrasena=hash_contrasena(temporal), rol="administrador")
    db.add(u)
    db.flush()
    _registrar(db, a, "cliente_creado", request, organizacion_id=o.id, entidad="organizacion", entidad_id=o.id,
               detalle={"administrador": email})
    if d.modulos is not None:
        if not d.modulos or set(d.modulos) - set(modulos.MODULOS):
            raise HTTPException(422, "Elija al menos un módulo válido.")
        for clave in d.modulos:  # primero se activan los elegidos, para no dejarla nunca sin módulos
            modulos.fijar(db, o.id, clave, contratado=True, activo=True)
        for clave in set(modulos.MODULOS) - set(d.modulos):
            modulos.fijar(db, o.id, clave, contratado=False)
    periodos = []
    if d.plan:
        periodos = [_crear_periodo(db, a, o, PeriodoNuevo(plan=d.plan, inicio=sus.hoy()), request)]
    return {"cliente": _c(o, _metricas(db, [o.id]), periodos),
            "acceso": {"email": email, "nombre": u.nombre, "contrasena_temporal": temporal}}


@router.get("/clientes")
def clientes(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    orgs = db.scalars(select(m.Organizacion).order_by(m.Organizacion.nombre)).all()
    met = _metricas(db)
    periodos = _periodos_por_org(db)
    return [_c(o, met, periodos.get(o.id)) for o in orgs]


@router.post("/clientes", status_code=201)
def crear_cliente(d: ClienteNuevo, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                  db: Session = Depends(get_db)):
    r = _crear_cliente(db, a, d, request)
    db.commit()
    return _con_bienvenida(db, r, d)


def _con_bienvenida(db: Session, r: dict, d: ClienteNuevo) -> dict:
    """El correo sale DESPUÉS de guardar: si fallara el alta, no se manda nada."""
    if not d.enviar_correo:
        return {**r, "correo": None}
    return {**r, "correo": envios.enviar_bienvenida(db, db.get(m.Organizacion, r["cliente"]["id"]), r["acceso"])}


@router.post("/solicitudes/{sid}/convertir", status_code=201)
def convertir(sid: int, d: ClienteNuevo, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
              db: Session = Depends(get_db)):
    """Da de alta como cliente a quien envió la solicitud y la marca atendida."""
    x = db.get(m.Solicitud, sid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    r = _crear_cliente(db, a, d, request)
    x.estado, x.atendida_en = "atendida", m.ahora()
    x.nota = ((x.nota + "\n") if x.nota else "") + f"Convertida en cliente #{r['cliente']['id']} ({d.organizacion.strip()})."
    db.commit()
    return _con_bienvenida(db, r, d)


@router.get("/clientes/{cid}")
def cliente(cid: int, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    o = _cliente(db, cid)
    ultimos = dict(db.execute(select(m.Auditoria.usuario_id, func.max(m.Auditoria.fecha))
                              .where(m.Auditoria.organizacion_id == o.id, m.Auditoria.accion == "login")
                              .group_by(m.Auditoria.usuario_id)).all())
    usuarios = db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == o.id, m.Usuario.eliminado_en.is_(None))
                          .order_by(m.Usuario.rol, m.Usuario.nombre)).all()
    return {**_c(o, _metricas(db, [o.id]), _periodos_por_org(db, [o.id]).get(o.id)),
            "modulos": modulos.estado(db, o.id),
            "curp_oficial_autorizado": bool(db.scalar(select(m.AfConfig.curp_oficial_autorizado).where(m.AfConfig.organizacion_id == o.id))),
            "usuarios_detalle": [
        {"id": u.id, "nombre": u.nombre, "email": u.email, "rol": u.rol, "activo": u.activo,
         "ultimo_acceso": ultimos[u.id].isoformat() if u.id in ultimos else None} for u in usuarios]}


@router.patch("/clientes/{cid}")
def cambiar_cliente(cid: int, d: ClienteCambio, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                    db: Session = Depends(get_db)):
    o = _cliente(db, cid)
    cambios = {}
    if d.nombre and d.nombre.strip() != o.nombre:
        cambios["nombre"] = [o.nombre, d.nombre.strip()]
        o.nombre = d.nombre.strip()
    if d.estado is not None and d.estado != o.estado:
        if d.estado not in ("activa", "suspendida"):
            raise HTTPException(422, "Estado inválido.")
        cambios["estado"] = [o.estado, d.estado]
        o.estado = d.estado
        o.motivo_suspension = ((d.motivo or "").strip()[:300] or None) if d.estado == "suspendida" else None
        if d.estado == "suspendida":  # cierra de inmediato todas sus sesiones
            for u in db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == o.id)):
                u.sesion_version += 1
    if cambios:
        _registrar(db, a, "cliente_modificado", request, organizacion_id=o.id, entidad="organizacion",
                   entidad_id=o.id, detalle=cambios)
    db.commit()
    return _c(o, _metricas(db, [o.id]), _periodos_por_org(db, [o.id]).get(o.id))


class Contratacion(BaseModel):
    contratado: bool


@router.patch("/clientes/{cid}/modulos/{modulo}")
def contratar_modulo(cid: int, modulo: str, d: Contratacion, request: Request,
                     a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    """Marca un módulo como contratado (queda activo) o no contratado (se oculta; sus datos se conservan)."""
    o = _cliente(db, cid)
    nuevo = modulos.fijar(db, o.id, modulo, contratado=d.contratado)
    _registrar(db, a, "modulo_contratado" if d.contratado else "modulo_retirado", request, organizacion_id=o.id,
               entidad="organizacion", entidad_id=o.id, detalle={"modulo": modulo})
    db.commit()
    return nuevo


class CurpOficial(BaseModel):
    autorizado: bool


@router.patch("/clientes/{cid}/curp-oficial")
def autorizar_curp_oficial(cid: int, d: CurpOficial, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                           db: Session = Depends(get_db)):
    """Nomira AFORE: habilita la consulta oficial de CURP para un despacho que acreditó su autorización.
    Sin credenciales del servicio en el servidor sigue deshabilitada."""
    from ..services.afore import curp_oficial, mensajes as af_msj

    o = _cliente(db, cid)
    cfg = af_msj.config(db, o.id)
    cfg.curp_oficial_autorizado = d.autorizado
    _registrar(db, a, "curp_oficial_autorizada" if d.autorizado else "curp_oficial_retirada", request, organizacion_id=o.id,
               entidad="organizacion", entidad_id=o.id)
    db.commit()
    ok, motivo = curp_oficial.disponible(cfg)
    return {"autorizado": cfg.curp_oficial_autorizado, "disponible": ok, "motivo": motivo}


@router.post("/clientes/{cid}/eliminar")
def eliminar_cliente(cid: int, d: Eliminacion, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                     db: Session = Depends(get_db)):
    """Borra la cuenta del cliente con todos sus datos. Exige escribir el nombre exacto."""
    o = _cliente(db, cid)
    if d.confirmar_nombre.strip() != o.nombre:
        raise HTTPException(422, "Escriba el nombre exacto del cliente para confirmar.")
    nombre = o.nombre
    n = eliminar_organizacion(db, o)
    _registrar(db, a, "cliente_eliminado", request, entidad="organizacion", entidad_id=cid,
               detalle={"nombre": nombre, "expedientes_borrados": n})  # sin organizacion_id: ya no existe
    db.commit()
    borrar_archivos(cid)
    return {"ok": True, "expedientes_borrados": n}


def _usuario_de(db: Session, cid: int, uid: int) -> m.Usuario:
    u = db.scalar(select(m.Usuario).where(m.Usuario.id == uid, m.Usuario.organizacion_id == cid,
                                          m.Usuario.eliminado_en.is_(None)))
    if not u:
        raise HTTPException(404, "Usuario no encontrado.")
    return u


@router.post("/clientes/{cid}/usuarios", status_code=201)
def agregar_usuario(cid: int, d: UsuarioNuevo, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                    db: Session = Depends(get_db)):
    o = _cliente(db, cid)
    if d.rol not in ROLES:
        raise HTTPException(422, "Rol inválido.")
    email = _email(d.email)
    if db.scalar(select(m.Usuario.id).where(m.Usuario.email == email)):
        raise HTTPException(409, f"El correo {email} ya tiene una cuenta en Nomira.")
    temporal = contrasena_temporal()
    u = m.Usuario(organizacion_id=o.id, email=email, nombre=d.nombre.strip(), hash_contrasena=hash_contrasena(temporal),
                  rol=d.rol)
    db.add(u)
    db.flush()
    _registrar(db, a, "usuario_creado", request, organizacion_id=o.id, entidad="usuario", entidad_id=u.id,
               detalle={"email": email, "rol": d.rol})
    db.commit()
    return {"acceso": {"email": email, "nombre": u.nombre, "contrasena_temporal": temporal}}


@router.post("/clientes/{cid}/usuarios/{uid}/restablecer")
def restablecer(cid: int, uid: int, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                db: Session = Depends(get_db)):
    """Contraseña temporal nueva: cierra sus sesiones y quita el bloqueo por intentos."""
    u = _usuario_de(db, cid, uid)
    temporal = contrasena_temporal()
    u.hash_contrasena = hash_contrasena(temporal)
    u.sesion_version += 1
    auth_clientes._intentos.desbloquear_correo(u.email)
    _registrar(db, a, "contrasena_restablecida", request, organizacion_id=cid, entidad="usuario", entidad_id=u.id)
    db.commit()
    return {"acceso": {"email": u.email, "nombre": u.nombre, "contrasena_temporal": temporal}}


@router.post("/clientes/{cid}/usuarios/{uid}/desbloquear")
def desbloquear(cid: int, uid: int, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                db: Session = Depends(get_db)):
    u = _usuario_de(db, cid, uid)
    n = auth_clientes._intentos.desbloquear_correo(u.email)
    _registrar(db, a, "usuario_desbloqueado", request, organizacion_id=cid, entidad="usuario", entidad_id=u.id)
    db.commit()
    return {"ok": True, "estaba_bloqueado": n > 0}


@router.patch("/clientes/{cid}/usuarios/{uid}")
def cambiar_usuario(cid: int, uid: int, d: UsuarioCambio, request: Request,
                    a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    u = _usuario_de(db, cid, uid)
    if u.activo != d.activo:
        u.activo = d.activo
        if not d.activo:
            u.sesion_version += 1
        _registrar(db, a, "usuario_modificado", request, organizacion_id=cid, entidad="usuario", entidad_id=u.id,
                   detalle={"activo": d.activo})
        db.commit()
    return {"ok": True}


# ---------- suscripciones (periodos de venta) ----------

def _crear_periodo(db: Session, a: m.AdminPlataforma, o: m.Organizacion, d: PeriodoNuevo,
                   request: Request) -> m.PeriodoSuscripcion:
    if d.plan not in sus.PLANES:
        raise HTTPException(422, "Plan inválido: use prueba, mensual, semestral o anual.")
    existentes = db.scalars(select(m.PeriodoSuscripcion).where(m.PeriodoSuscripcion.organizacion_id == o.id)).all()
    if d.plan == "prueba" and any(p.plan == "prueba" for p in existentes):
        raise HTTPException(409, "Este cliente ya tuvo su prueba gratuita.")
    if d.inicio < sus.hoy() - timedelta(days=366):
        raise HTTPException(422, "La fecha de inicio es de hace más de un año; revise la fecha.")
    fin = sus.calcular_fin(d.plan, d.inicio)
    for p in existentes:
        if d.inicio <= p.fin and p.inicio <= fin:
            raise HTTPException(409, f"Se encima con el periodo {sus.PLANES[p.plan][0].lower()} del "
                                     f"{p.inicio:%d/%m/%Y} al {p.fin:%d/%m/%Y}. Elija otra fecha de inicio.")
    p = m.PeriodoSuscripcion(organizacion_id=o.id, plan=d.plan, inicio=d.inicio, fin=fin, monto=d.monto,
                             pagado=d.pagado and d.plan != "prueba",
                             pagado_en=sus.hoy() if d.pagado and d.plan != "prueba" else None,
                             nota=(d.nota or "").strip() or None, creado_por_id=a.id)
    db.add(p)
    db.flush()
    _registrar(db, a, "suscripcion_registrada", request, organizacion_id=o.id, entidad="periodo", entidad_id=p.id,
               detalle={"plan": d.plan, "inicio": d.inicio.isoformat(), "fin": fin.isoformat()})
    return p


def _periodo(db: Session, pid: int) -> m.PeriodoSuscripcion:
    p = db.get(m.PeriodoSuscripcion, pid)
    if not p:
        raise HTTPException(404, "Periodo no encontrado.")
    return p


def _suscripcion(db: Session, cid: int) -> dict:
    ps = _periodos_por_org(db, [cid]).get(cid, [])
    ref = sus.hoy()
    avisos = db.scalars(select(m.CorreoEnviado).where(m.CorreoEnviado.organizacion_id == cid,
                                                      m.CorreoEnviado.tipo == "recordatorio_vencimiento")
                        .order_by(m.CorreoEnviado.id.desc()).limit(10)).all()
    return {**sus.estado(ps, ref), "periodos": [sus.p_dict(p, ref) for p in sorted(ps, key=lambda p: (p.inicio, p.id), reverse=True)],
            "recordatorios": [{"periodo_id": c.periodo_id, "estado": c.estado, "fecha": c.creado_en.isoformat(),
                               "destinatarios": c.destinatarios, "error": c.error} for c in avisos],
            "planes": [{"clave": k, "nombre": v[0], "fin_si_inicia_hoy": sus.calcular_fin(k, ref).isoformat()}
                       for k, v in sus.PLANES.items()]}


@router.get("/clientes/{cid}/suscripcion")
def suscripcion(cid: int, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    _cliente(db, cid)
    return _suscripcion(db, cid)


@router.post("/clientes/{cid}/periodos", status_code=201)
def registrar_periodo(cid: int, d: PeriodoNuevo, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                      db: Session = Depends(get_db)):
    _crear_periodo(db, a, _cliente(db, cid), d, request)
    db.commit()
    return _suscripcion(db, cid)


@router.patch("/periodos/{pid}")
def cambiar_periodo(pid: int, d: PeriodoCambio, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                    db: Session = Depends(get_db)):
    p = _periodo(db, pid)
    cambios = d.model_dump(exclude_unset=True)
    if "pagado" in cambios and p.plan != "prueba":
        p.pagado, p.pagado_en = d.pagado, (sus.hoy() if d.pagado else None)
    if "monto" in cambios:
        p.monto = d.monto
    if "nota" in cambios:
        p.nota = (d.nota or "").strip() or None
    _registrar(db, a, "suscripcion_modificada", request, organizacion_id=p.organizacion_id, entidad="periodo",
               entidad_id=p.id, detalle={k: str(v) for k, v in cambios.items()})
    db.commit()
    return _suscripcion(db, p.organizacion_id)


@router.delete("/periodos/{pid}")
def borrar_periodo(pid: int, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                   db: Session = Depends(get_db)):
    """Para corregir un periodo capturado por error."""
    p = _periodo(db, pid)
    cid = p.organizacion_id
    _registrar(db, a, "suscripcion_borrada", request, organizacion_id=cid, entidad="periodo", entidad_id=p.id,
               detalle={"plan": p.plan, "inicio": p.inicio.isoformat(), "fin": p.fin.isoformat()})
    db.delete(p)
    db.commit()
    return _suscripcion(db, cid)


@router.get("/suscripciones")
def suscripciones(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    """Todos los clientes con su situación de venta, para la pantalla «Suscripciones»."""
    grupos = _periodos_por_org(db)
    ref = sus.hoy()
    salida = []
    for o in db.scalars(select(m.Organizacion).order_by(m.Organizacion.nombre)):
        ps = grupos.get(o.id, [])
        salida.append({"id": o.id, "nombre": o.nombre, "estado_cuenta": o.estado, **sus.estado(ps, ref),
                       "total_cobrado": str(sum((p.monto or 0) for p in ps if p.pagado))})
    return salida


# ---------- correos ----------

class CorreoPrueba(BaseModel):
    destinatario: str = Field(max_length=254)


TIPOS_PLATAFORMA = ("bienvenida", "recordatorio_vencimiento", "prueba")


def _c_dict(c: m.CorreoEnviado, nombres: dict) -> dict:
    return {"id": c.id, "tipo": c.tipo, "cliente": nombres.get(c.organizacion_id), "organizacion_id": c.organizacion_id,
            "destinatarios": c.destinatarios, "asunto": c.asunto, "estado": c.estado, "error": c.error,
            "fecha": c.creado_en.isoformat()}


@router.get("/correos")
def correos(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    nombres = dict(db.execute(select(m.Organizacion.id, m.Organizacion.nombre)).all())
    pend = envios.recordatorios_pendientes(db)
    return {"config": correo.descripcion(),
            "pendientes": [{"cliente": x["organizacion"].nombre, "organizacion_id": x["organizacion"].id,
                            "vence": x["periodo"].fin.isoformat(), "dias": x["dias"],
                            "destinatarios": [u.email for u in x["admins"]]} for x in pend],
            "historial": [_c_dict(c, nombres) for c in db.scalars(
                # Solo correos de la plataforma: los que un despacho envía a SUS clientes no son de su incumbencia.
                select(m.CorreoEnviado).where(m.CorreoEnviado.tipo.in_(TIPOS_PLATAFORMA))
                .order_by(m.CorreoEnviado.id.desc()).limit(200))]}


@router.post("/correos/prueba")
def correo_de_prueba(d: CorreoPrueba, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                     db: Session = Depends(get_db)):
    """Envía la plantilla de bienvenida con datos de ejemplo para comprobar la configuración."""
    destino = _email(d.destinatario)
    asunto, html, texto = plantillas_correo.bienvenida("Laura Ejemplo", "Despacho de Ejemplo", "laura@ejemplo.com",
                                                      "Nomira-Ab3d-Ef6h-Jk9m", sus.hoy() + timedelta(days=6))
    r = envios.registrar_y_enviar(db, "prueba", [destino], "[Prueba] " + asunto, html, texto)
    _registrar(db, a, "correo_prueba", request, detalle={"destinatario": destino, "estado": r.estado})
    db.commit()
    return {"enviado": r.estado == "enviado", "error": r.error}


@router.post("/recordatorios/ejecutar")
def ejecutar_recordatorios(request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                           db: Session = Depends(get_db)):
    """Lo mismo que hace la revisión automática, pero al momento."""
    resultados = envios.ejecutar_recordatorios(db)
    _registrar(db, a, "recordatorios_ejecutados", request, detalle={"enviados": sum(r["estado"] == "enviado" for r in resultados)})
    db.commit()
    return resultados


@router.get("/correos/vista-previa/{tipo}", response_class=HTMLResponse)
def vista_previa(tipo: str, a: m.AdminPlataforma = Depends(admin_plataforma)):
    """La plantilla con datos de ejemplo, para verla en el panel."""
    hoy = sus.hoy()
    if tipo == "bienvenida":
        _, html, _ = plantillas_correo.bienvenida("Laura Ejemplo", "Despacho de Ejemplo", "laura@ejemplo.com",
                                                 "Nomira-Ab3d-Ef6h-Jk9m", hoy + timedelta(days=6))
    elif tipo == "recordatorio":
        _, html, _ = plantillas_correo.recordatorio_vencimiento("Laura Ejemplo", "Despacho de Ejemplo", "Mensual",
                                                               hoy + timedelta(days=7), 7)
    else:
        raise HTTPException(404, "No encontrado.")
    return HTMLResponse(html)


# ---------- soporte ----------

class Mensaje(BaseModel):
    texto: str = Field(min_length=1, max_length=5000)


class TicketNuevo(BaseModel):
    organizacion_id: int
    asunto: str = Field(min_length=2, max_length=200)
    texto: str = Field(min_length=1, max_length=5000)


class TicketCambio(BaseModel):
    estado: str


def t_resumen(t: m.TicketSoporte, org_nombre: str | None = None) -> dict:
    ultimo = t.mensajes[-1] if t.mensajes else None
    return {"id": t.id, "organizacion_id": t.organizacion_id, "organizacion": org_nombre, "asunto": t.asunto,
            "estado": t.estado, "creado_en": t.creado_en.isoformat(), "actualizado_en": t.actualizado_en.isoformat(),
            "leido_cliente": t.leido_cliente, "leido_plataforma": t.leido_plataforma, "mensajes": len(t.mensajes),
            "ultimo": {"autor_tipo": ultimo.autor_tipo, "autor_nombre": ultimo.autor_nombre,
                       "texto": ultimo.texto[:160]} if ultimo else None}


def t_detalle(t: m.TicketSoporte, org_nombre: str | None = None) -> dict:
    return {**t_resumen(t, org_nombre), "conversacion": [
        {"id": x.id, "autor_tipo": x.autor_tipo, "autor_nombre": x.autor_nombre, "texto": x.texto,
         "creado_en": x.creado_en.isoformat()} for x in t.mensajes]}


def _ticket(db: Session, tid: int) -> m.TicketSoporte:
    t = db.get(m.TicketSoporte, tid)
    if not t:
        raise HTTPException(404, "No encontrado.")
    return t


@router.get("/soporte")
def tickets(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    nombres = dict(db.execute(select(m.Organizacion.id, m.Organizacion.nombre)).all())
    ts = db.scalars(select(m.TicketSoporte).order_by(m.TicketSoporte.actualizado_en.desc()).limit(500)).all()
    return [t_resumen(t, nombres.get(t.organizacion_id)) for t in ts]


@router.post("/soporte", status_code=201)
def iniciar(d: TicketNuevo, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
            db: Session = Depends(get_db)):
    """Conversación que inicia Nomira (p. ej. para avisar algo a un cliente)."""
    o = _cliente(db, d.organizacion_id)
    t = m.TicketSoporte(organizacion_id=o.id, asunto=d.asunto.strip(), leido_cliente=False, leido_plataforma=True)
    t.mensajes.append(m.MensajeSoporte(autor_tipo="plataforma", autor_nombre="Soporte Nomira", admin_id=a.id,
                                       texto=d.texto.strip()))
    db.add(t)
    db.flush()
    _registrar(db, a, "soporte_iniciado", request, organizacion_id=o.id, entidad="ticket", entidad_id=t.id)
    db.commit()
    return t_detalle(t, o.nombre)


@router.get("/soporte/{tid}")
def ticket(tid: int, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    t = _ticket(db, tid)
    if not t.leido_plataforma:
        t.leido_plataforma = True
        db.commit()
    return t_detalle(t, db.get(m.Organizacion, t.organizacion_id).nombre)


@router.post("/soporte/{tid}/mensajes", status_code=201)
def responder(tid: int, d: Mensaje, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
              db: Session = Depends(get_db)):
    t = _ticket(db, tid)
    t.mensajes.append(m.MensajeSoporte(autor_tipo="plataforma", autor_nombre="Soporte Nomira", admin_id=a.id,
                                       texto=d.texto.strip()))
    t.estado, t.leido_cliente, t.leido_plataforma, t.actualizado_en = "abierto", False, True, m.ahora()
    _registrar(db, a, "soporte_respondido", request, organizacion_id=t.organizacion_id, entidad="ticket", entidad_id=t.id)
    db.commit()
    return t_detalle(t, db.get(m.Organizacion, t.organizacion_id).nombre)


@router.patch("/soporte/{tid}")
def estado_ticket(tid: int, d: TicketCambio, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                  db: Session = Depends(get_db)):
    t = _ticket(db, tid)
    if d.estado not in ("abierto", "cerrado"):
        raise HTTPException(422, "Estado inválido.")
    t.estado = d.estado
    _registrar(db, a, f"soporte_{d.estado}", request, organizacion_id=t.organizacion_id, entidad="ticket", entidad_id=t.id)
    db.commit()
    return t_detalle(t, db.get(m.Organizacion, t.organizacion_id).nombre)


# ---------- administradores de la plataforma ----------

class AdminNuevo(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    email: str = Field(max_length=254)
    rol: str = "soporte"


class AdminCambio(BaseModel):
    activo: bool | None = None
    rol: str | None = None


@router.get("/admins")
def admins(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    return [_a(x) for x in db.scalars(select(m.AdminPlataforma).order_by(m.AdminPlataforma.nombre))]


@router.post("/admins", status_code=201)
def crear_admin(d: AdminNuevo, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                db: Session = Depends(get_db)):
    email = _email(d.email)
    if db.scalar(select(m.AdminPlataforma.id).where(m.AdminPlataforma.email == email)):
        raise HTTPException(409, "Ese correo ya es administrador de la plataforma.")
    if d.rol not in ROLES_PLATAFORMA:
        raise HTTPException(422, "Rol inválido.")
    if d.rol == "superadministrador" and a.rol != "superadministrador":
        raise HTTPException(403, "Solo un superadministrador puede crear otro superadministrador.")
    temporal = contrasena_temporal()
    x = m.AdminPlataforma(email=email, nombre=d.nombre.strip(), hash_contrasena=hash_contrasena(temporal), rol=d.rol)
    db.add(x)
    db.flush()
    _registrar(db, a, "plataforma_admin_creado", request, entidad="admin_plataforma", entidad_id=x.id,
               detalle={"email": email, "rol": d.rol})
    db.commit()
    return {"admin": _a(x), "acceso": {"email": email, "nombre": x.nombre, "contrasena_temporal": temporal}}


@router.patch("/admins/{aid}")
def cambiar_admin(aid: int, d: AdminCambio, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma),
                  db: Session = Depends(get_db)):
    x = db.get(m.AdminPlataforma, aid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    if x.rol == "superadministrador" and a.rol != "superadministrador":
        raise HTTPException(403, "Solo un superadministrador puede modificar a otro superadministrador.")
    if d.rol is not None and d.rol != x.rol:
        if d.rol not in ROLES_PLATAFORMA:
            raise HTTPException(422, "Rol inválido.")
        if a.rol != "superadministrador":
            raise HTTPException(403, "Solo un superadministrador puede cambiar roles.")
        if x.id == a.id:
            raise HTTPException(409, "No puede cambiar su propio rol.")
        antes, x.rol = x.rol, d.rol
        x.sesion_version += 1  # la sesión abierta vuelve a pedir acceso con el rol nuevo
        _registrar(db, a, "plataforma_admin_rol", request, entidad="admin_plataforma", entidad_id=x.id,
                   detalle={"antes": antes, "despues": d.rol})
        db.commit()
    if d.activo is None:
        return _a(x)
    if x.id == a.id and not d.activo:
        raise HTTPException(409, "No puede desactivar su propia cuenta.")
    if x.activo != d.activo:
        x.activo = d.activo
        if not d.activo:
            x.sesion_version += 1
        _registrar(db, a, "plataforma_admin_modificado", request, entidad="admin_plataforma", entidad_id=x.id,
                   detalle={"activo": d.activo})
        db.commit()
    return _a(x)


# ---------- verificación en dos pasos del panel ----------

class ConContrasena(BaseModel):
    contrasena: str = Field(max_length=128)


class ConCodigo(BaseModel):
    codigo: str = Field(max_length=20)


class QuitarDosPasos(BaseModel):
    contrasena: str = Field(max_length=128)
    codigo: str = Field(max_length=20)


@router.get("/yo/dos-pasos")
def mis_dos_pasos(a: m.AdminPlataforma = Depends(admin_plataforma)):
    return dos_pasos.estado(a)


@router.post("/yo/dos-pasos/preparar")
def preparar_dos_pasos(d: ConContrasena, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    if dos_pasos.activo(a):
        raise HTTPException(409, "La verificación en dos pasos ya está activa.")
    if not verificar_contrasena(d.contrasena, a.hash_contrasena):
        raise HTTPException(422, "La contraseña no es correcta.")
    secreto = dos_pasos.preparar(a)
    _registrar(db, a, "plataforma_dos_pasos_preparado", request)
    db.commit()
    url = dos_pasos.uri(a.email, secreto, "Nomira Panel")
    return {"secreto": secreto, "uri": url, "qr_svg": dos_pasos.qr_svg(url)}


@router.post("/yo/dos-pasos/activar")
def activar_dos_pasos(d: ConCodigo, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    cods = dos_pasos.activar(a, d.codigo)
    if not cods:
        raise HTTPException(422, "El código no coincide. Revise que la hora de su celular sea automática e intente con el código nuevo.")
    _registrar(db, a, "plataforma_dos_pasos_activado", request)
    db.commit()
    return {"codigos_respaldo": cods, **dos_pasos.estado(a)}


@router.post("/yo/dos-pasos/respaldo")
def nuevos_respaldo(d: ConCodigo, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    if not dos_pasos.activo(a) or dos_pasos.verificar(a, d.codigo) != "app":
        raise HTTPException(422, "Escriba el código actual de su app.")
    cods, a.totp_respaldo = dos_pasos.codigos_respaldo()
    _registrar(db, a, "plataforma_dos_pasos_respaldo", request)
    db.commit()
    return {"codigos_respaldo": cods, **dos_pasos.estado(a)}


@router.post("/yo/dos-pasos/desactivar")
def desactivar_dos_pasos(d: QuitarDosPasos, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    if not dos_pasos.activo(a):
        raise HTTPException(409, "La verificación en dos pasos no está activa.")
    if not verificar_contrasena(d.contrasena, a.hash_contrasena) or not dos_pasos.verificar(a, d.codigo):
        raise HTTPException(422, "La contraseña o el código no son correctos.")
    dos_pasos.quitar(a)
    _registrar(db, a, "plataforma_dos_pasos_desactivado", request)
    db.commit()
    return dos_pasos.estado(a)


@router.post("/admins/{aid}/dos-pasos/quitar")
def quitar_dos_pasos_admin(aid: int, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    x = db.get(m.AdminPlataforma, aid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    if x.id == a.id:
        raise HTTPException(409, "Para su propia cuenta use Mi cuenta.")
    dos_pasos.quitar(x)
    x.sesion_version += 1
    _registrar(db, a, "plataforma_dos_pasos_quitado", request, entidad="admin_plataforma", entidad_id=x.id)
    db.commit()
    return _a(x)


@router.post("/yo/cerrar-sesiones")
def cerrar_sesiones(request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    a.sesion_version += 1
    _registrar(db, a, "plataforma_sesiones_cerradas", request)
    db.commit()
    return {"token": crear_token_plataforma(a.id, a.sesion_version), "admin": _a(a)}
