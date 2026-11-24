"""Registro en línea con prueba gratuita, entrar con Google y recuperar la contraseña (sin sesión).

Vea services/registro.py. Todos los pasos tienen freno por IP y por correo."""
from __future__ import annotations

import re
import secrets
from urllib.parse import quote, urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, ip_cliente, usuario_actual
from ..freno import FrenoAcceso, Ventana
from ..security import gastar_tiempo_de_verificacion, hash_contrasena
from ..services import dos_pasos, modulos
from ..services import registro as rg
from ..services.ventas import base as ventas
from .auth import _email, _sesion

router = APIRouter(prefix="/api/auth", tags=["registro y acceso"])
_por_ip = Ventana(20, 3600)  # registros y códigos pedidos por IP en una hora
_intentos = FrenoAcceso(por_cuenta=5, por_ip=30)
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
COOKIE = "nomira_g"


def _freno(request: Request) -> str:
    ip = ip_cliente(request) or "-"
    if _por_ip.excedida(ip):
        raise HTTPException(429, "Demasiadas solicitudes desde su conexión. Intente más tarde.")
    _por_ip.registrar(ip)
    return ip


def _texto(v: str | None, n: int) -> str | None:
    v = re.sub(r"\s+", " ", v or "").strip()
    return v[:n] or None


def _abierto(db: Session) -> None:
    if not rg.registro_abierto(db):
        raise HTTPException(403, "El registro en línea no está disponible. Solicite informes y le damos de alta.")


# ------------------------------------------------------------------ registro con correo

class RegistroIn(BaseModel):
    organizacion: str = Field(min_length=2, max_length=200)
    nombre: str = Field(min_length=2, max_length=200)
    email: str = Field(max_length=254)
    telefono: str | None = Field(None, max_length=40)
    contrasena: str = Field(min_length=10, max_length=128)
    modulos: list[str] = Field(default_factory=list, max_length=10)
    acepto: bool = False


@router.post("/registro")
def registro(d: RegistroIn, request: Request, db: Session = Depends(get_db)):
    """Paso 1: valida y manda un código al correo. La cuenta se crea al confirmar el código."""
    _abierto(db)
    _freno(request)
    if not d.acepto:
        raise HTTPException(422, "Acepte los términos y el aviso de privacidad para continuar.")
    email = _email(d.email)
    elegidos = rg.validar_modulos(d.modulos)
    if db.scalar(select(m.Usuario.id).where(m.Usuario.email == email)):
        raise HTTPException(409, "Ese correo ya tiene cuenta. Inicie sesión o recupere su contraseña.")
    tel = _texto(d.telefono, 40)
    if tel and not re.fullmatch(r"[\d\s+()\-]{7,40}", tel):
        raise HTTPException(422, "Teléfono inválido.")
    datos = {"org": _texto(d.organizacion, 200), "nombre": _texto(d.nombre, 200), "email": email, "tel": tel,
             "hc": hash_contrasena(d.contrasena), "mods": elegidos}
    reto, codigo = rg.reto_con_codigo("registro", datos)
    rg.enviar_codigo(db, email, datos["nombre"], codigo, "registro")
    db.commit()
    return {"reto": reto, "email": email, "minutos": rg.MINUTOS_CODIGO}


class CodigoIn(BaseModel):
    reto: str = Field(max_length=4000)
    codigo: str = Field(max_length=12)


@router.post("/registro/verificar", status_code=201)
def registro_verificar(d: CodigoIn, request: Request, db: Session = Depends(get_db)):
    _abierto(db)
    datos = rg.leer(d.reto, "registro")
    if not datos:
        raise HTTPException(401, "El código venció. Vuelva a llenar el registro.")
    ip, llave = ip_cliente(request) or "-", f"reg:{datos['email']}"
    if _intentos.bloqueado(ip, llave):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    if not rg.codigo_valido(datos, d.codigo):
        _intentos.fallo(ip, llave)
        raise HTTPException(401, "Código incorrecto.")
    _intentos.exito(ip, llave)
    u = rg.crear_cuenta(db, organizacion=datos["org"], nombre=datos["nombre"], email=datos["email"], hash_contrasena=datos["hc"],
                        elegidos=rg.validar_modulos(datos["mods"]), telefono=datos.get("tel"), via="correo", ip=ip)
    auditar(db, u, "organizacion_creada", "organizacion", u.organizacion_id, {"via": "registro_correo", "modulos": datos["mods"]}, request)
    db.commit()
    return _sesion(db, u, db.get(m.Organizacion, u.organizacion_id))


class RetoIn(BaseModel):
    reto: str = Field(max_length=4000)


@router.post("/registro/reenviar")
def registro_reenviar(d: RetoIn, request: Request, db: Session = Depends(get_db)):
    _freno(request)
    datos = rg.leer(d.reto, "registro")
    if not datos:
        raise HTTPException(401, "El registro venció. Vuelva a llenarlo.")
    limpio = {k: datos[k] for k in ("org", "nombre", "email", "tel", "hc", "mods")}
    reto, codigo = rg.reto_con_codigo("registro", limpio)
    rg.enviar_codigo(db, datos["email"], datos["nombre"], codigo, "registro")
    db.commit()
    return {"reto": reto, "email": datos["email"], "minutos": rg.MINUTOS_CODIGO}


# ------------------------------------------------------------------ Google

def _google_listo() -> bool:
    a = ajustes()
    return bool(a.google_client_id and a.google_client_secret)


def _redirect_uri() -> str:
    return ajustes().url_publica.rstrip("/") + "/api/auth/google/callback"


def _a_login(fragmento: str) -> RedirectResponse:
    r = RedirectResponse(ajustes().url_publica.rstrip("/") + "/login#" + fragmento, status_code=303)
    r.delete_cookie(COOKIE, path="/api/auth/google")
    return r


@router.get("/google/inicio")
def google_inicio(modo: str = "entrar"):
    if not _google_listo():
        raise HTTPException(404, "Entrar con Google no está disponible.")
    nonce = secrets.token_urlsafe(24)
    estado = rg._firmar({"t": "google_estado", "n": nonce, "modo": "registro" if modo == "registro" else "entrar"}, 10)
    url = GOOGLE_AUTH + "?" + urlencode({"client_id": ajustes().google_client_id, "redirect_uri": _redirect_uri(), "response_type": "code",
                                         "scope": "openid email profile", "state": estado, "prompt": "select_account"})
    r = RedirectResponse(url, status_code=303)
    r.set_cookie(COOKIE, nonce, max_age=600, httponly=True, secure=ajustes().entorno == "produccion", samesite="lax", path="/api/auth/google")
    return r


def _identidad(code: str) -> dict:
    """Cambia el código por el id_token. Viene directo de Google por HTTPS con nuestro secreto: se validan
    emisor, audiencia, vigencia y correo verificado (la firma la garantiza el canal)."""
    a = ajustes()
    try:
        r = httpx.post(GOOGLE_TOKEN, data={"code": code, "client_id": a.google_client_id, "client_secret": a.google_client_secret,
                                           "redirect_uri": _redirect_uri(), "grant_type": "authorization_code"}, timeout=15)
        r.raise_for_status()
        tok = r.json()["id_token"]
        d = jwt.decode(tok, options={"verify_signature": False, "require": ["exp", "aud", "iss", "sub"]},
                       audience=a.google_client_id, algorithms=["RS256"])
    except (httpx.HTTPError, KeyError, ValueError, jwt.PyJWTError):
        raise HTTPException(502, "google")
    if d.get("iss") not in ("accounts.google.com", "https://accounts.google.com") or not d.get("email_verified") or not d.get("email"):
        raise HTTPException(502, "google")
    return d


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None,
                    db: Session = Depends(get_db)):
    if error or not code or not state:
        return _a_login("google_error=cancelado")
    est = rg.leer(state, "google_estado")
    if not est or not secrets.compare_digest(est.get("n", ""), request.cookies.get(COOKIE, "")):
        return _a_login("google_error=vencido")
    try:
        g = _identidad(code)
    except HTTPException:
        return _a_login("google_error=google")
    email, sub = g["email"].strip().lower(), str(g["sub"])
    u = db.scalar(select(m.Usuario).where(m.Usuario.google_sub == sub)) or db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if u:
        if u.google_sub and u.google_sub != sub:
            return _a_login("google_error=otra_cuenta")
        if not u.activo or u.eliminado_en:
            return _a_login("google_error=inactivo")
        if not u.google_sub:
            u.google_sub = sub
            auditar(db, u, "google_vinculado", "usuario", u.id, request=request)
            db.commit()
        return _a_login("google=" + quote(rg.canje_google(u.id, u.sesion_version)))
    if not rg.registro_abierto(db):
        return _a_login("google_error=sin_cuenta")
    t = rg.token_google({"email": email, "sub": sub, "nombre": _texto(g.get("name"), 200) or email.split("@")[0]})
    return _a_login("registro_google=" + quote(t))


class CanjeIn(BaseModel):
    pase: str = Field(max_length=2000)


@router.post("/google/canjear")
def google_canjear(d: CanjeIn, request: Request, db: Session = Depends(get_db)):
    datos = rg.leer(d.pase, "google_entrar")
    u = db.get(m.Usuario, int(datos["sub"])) if datos else None
    if not u or not u.activo or u.eliminado_en or u.sesion_version != datos.get("ver"):
        raise HTTPException(401, "El inicio de sesión con Google venció. Intente de nuevo.")
    org = db.get(m.Organizacion, u.organizacion_id)
    if org.estado != "activa":
        raise HTTPException(403, "La cuenta de su organización está suspendida. Contacte a soporte de Nomira.")
    if dos_pasos.activo(u):
        auditar(db, u, "login_paso_1", request=request, detalle={"via": "google"})
        db.commit()
        return {"requiere_codigo": True, "reto": dos_pasos.crear_reto("usuario", u.id, u.sesion_version)}
    auditar(db, u, "login", request=request, detalle={"via": "google"})
    db.commit()
    return _sesion(db, u, org)


class RegistroGoogleIn(BaseModel):
    token: str = Field(max_length=4000)
    organizacion: str = Field(min_length=2, max_length=200)
    nombre: str | None = Field(None, max_length=200)
    telefono: str | None = Field(None, max_length=40)
    modulos: list[str] = Field(default_factory=list, max_length=10)
    acepto: bool = False


@router.post("/registro/google", status_code=201)
def registro_google(d: RegistroGoogleIn, request: Request, db: Session = Depends(get_db)):
    _abierto(db)
    ip = _freno(request)
    g = rg.leer(d.token, "google_registro")
    if not g:
        raise HTTPException(401, "El registro con Google venció. Vuelva a elegir «Continuar con Google».")
    if not d.acepto:
        raise HTTPException(422, "Acepte los términos y el aviso de privacidad para continuar.")
    tel = _texto(d.telefono, 40)
    if tel and not re.fullmatch(r"[\d\s+()\-]{7,40}", tel):
        raise HTTPException(422, "Teléfono inválido.")
    if db.scalar(select(m.Usuario.id).where(m.Usuario.google_sub == g["sub"])):
        raise HTTPException(409, "Esa cuenta de Google ya tiene acceso. Inicie sesión.")
    u = rg.crear_cuenta(db, organizacion=_texto(d.organizacion, 200), nombre=_texto(d.nombre, 200) or g["nombre"], email=g["email"],
                        hash_contrasena=rg.SIN_CONTRASENA, elegidos=rg.validar_modulos(d.modulos), telefono=tel, via="google",
                        google_sub=g["sub"], ip=ip)
    auditar(db, u, "organizacion_creada", "organizacion", u.organizacion_id, {"via": "registro_google", "modulos": d.modulos}, request)
    db.commit()
    return _sesion(db, u, db.get(m.Organizacion, u.organizacion_id))


# ------------------------------------------------------------------ recuperar contraseña

class RecuperarIn(BaseModel):
    email: str = Field(max_length=254)


@router.post("/recuperar")
def recuperar(d: RecuperarIn, request: Request, db: Session = Depends(get_db)):
    """Siempre responde igual (no revela si el correo tiene cuenta). Solo si existe se manda el código."""
    _freno(request)
    email = _email(d.email)
    u = db.scalar(select(m.Usuario).where(m.Usuario.email == email, m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None)))
    reto, codigo = rg.reto_con_codigo("recuperar", {"sub": str(u.id) if u else "0", "ver": u.sesion_version if u else 0, "email": email})
    if u:
        try:
            rg.enviar_codigo(db, email, u.nombre, codigo, "recuperar")
        except HTTPException as e:
            if e.status_code == 503:
                raise
        auditar(db, u, "recuperar_contrasena_pedido", "usuario", u.id, request=request)
        db.commit()
    return {"reto": reto, "minutos": rg.MINUTOS_CODIGO,
            "mensaje": "Si ese correo tiene cuenta en Nomira, le enviamos un código. Revise también su carpeta de spam."}


class CambiarIn(BaseModel):
    reto: str = Field(max_length=4000)
    codigo: str = Field(max_length=12)
    nueva: str = Field(min_length=10, max_length=128)


@router.post("/recuperar/cambiar")
def recuperar_cambiar(d: CambiarIn, request: Request, db: Session = Depends(get_db)):
    datos = rg.leer(d.reto, "recuperar")
    if not datos:
        raise HTTPException(401, "El código venció. Pida uno nuevo.")
    ip, llave = ip_cliente(request) or "-", f"rec:{datos.get('email')}"
    if _intentos.bloqueado(ip, llave):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    u = db.get(m.Usuario, int(datos["sub"])) if datos.get("sub", "0") != "0" else None
    if not u or not rg.codigo_valido(datos, d.codigo) or u.sesion_version != datos.get("ver") or not u.activo:
        gastar_tiempo_de_verificacion(d.nueva)
        _intentos.fallo(ip, llave)
        raise HTTPException(401, "Código incorrecto o vencido.")
    _intentos.exito(ip, llave)
    u.hash_contrasena = hash_contrasena(d.nueva)
    u.sesion_version += 1  # cierra las sesiones abiertas
    auditar(db, u, "contrasena_restablecida", "usuario", u.id, request=request)
    db.commit()
    return {"ok": True, "mensaje": "Listo. Ya puede entrar con su contraseña nueva."}


# ------------------------------------------------------------------ prueba gratuita

@router.get("/prueba")
def prueba(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return {"prueba": rg.estado_prueba(db, db.get(m.Organizacion, u.organizacion_id))}


class ContratarIn(BaseModel):
    mensaje: str | None = Field(None, max_length=1000)


@router.post("/prueba/contratar")
def contratar(d: ContratarIn, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """El despacho pide contratar: entra a Ventas como solicitud de suscripción con los módulos que probó."""
    _freno(request)
    org = db.get(m.Organizacion, u.organizacion_id)
    probados = ", ".join(modulos.MODULOS[x]["nombre"] for x in (org.modulos_prueba or []) if x in modulos.MODULOS)
    sol = m.Solicitud(tipo="suscripcion", nombre=u.nombre, empresa=org.nombre, email=u.email, ip=(ip_cliente(request) or "")[:60] or None,
                      mensaje=f"Quiere contratar después de su prueba gratuita. Módulos que probó: {probados or '—'}."
                              + (f"\n{d.mensaje.strip()}" if d.mensaje and d.mensaje.strip() else ""))
    db.add(sol)
    db.flush()
    ventas.desde_solicitud(db, sol)
    auditar(db, u, "pidio_contratar", "organizacion", org.id, request=request)
    db.commit()
    return {"ok": True, "mensaje": "¡Gracias! Un asesor de Nomira le contactará para activar su plan. Su información se conserva."}
