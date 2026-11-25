"""Registro en línea con prueba gratuita de 7 días, inicio de sesión con Google y recuperación de contraseña.

- Registro con correo: se confirma con un código de 6 dígitos que llega al correo. Nada se guarda en la base
  hasta confirmar: los datos viajan en un «reto» firmado (con «aud», así nunca sirve como sesión) y el código
  se compara con un HMAC que solo el servidor puede calcular.
- Con Google: el correo ya viene verificado por Google (flujo de código de autorización en el servidor).
- La organización elige hasta 3 módulos para su prueba (dato comercial: entra a Ventas como lead).
- Al terminar la prueba sin plan, el uso se bloquea (los datos se conservan) solo para cuentas de registro.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from . import correo, envios, modulos, plantillas_correo
from . import suscripciones as sus
from .ventas import base as ventas

AUD = "nomira-registro"
MAX_MODULOS = 3
MINUTOS_CODIGO = 15
SIN_CONTRASENA = "!google"  # nunca coincide con un hash válido: la cuenta entra solo con Google hasta que elija contraseña


def _firmar(datos: dict, minutos: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return jwt.encode({**datos, "aud": AUD, "exp": exp, "jti": secrets.token_hex(8)}, ajustes().jwt_secreto, algorithm="HS256")


def leer(token: str, tipo: str) -> dict | None:
    try:
        d = jwt.decode(token, ajustes().jwt_secreto, algorithms=["HS256"], audience=AUD, options={"require": ["aud", "exp"]})
    except jwt.PyJWTError:
        return None
    return d if d.get("t") == tipo else None


def _hmac(codigo: str, jti: str) -> str:
    return hmac.new(ajustes().jwt_secreto.encode(), f"{jti}:{codigo}".encode(), hashlib.sha256).hexdigest()


def reto_con_codigo(tipo: str, datos: dict) -> tuple[str, str]:
    """Devuelve (reto, código). El código no viaja en el reto: solo su HMAC con la llave del servidor."""
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    sal = secrets.token_hex(8)
    return _firmar({**datos, "t": tipo, "sal": sal, "h": _hmac(codigo, sal)}, MINUTOS_CODIGO), codigo


def codigo_valido(d: dict, codigo: str) -> bool:
    codigo = "".join(ch for ch in (codigo or "") if ch.isdigit())
    return len(codigo) == 6 and hmac.compare_digest(d.get("h", ""), _hmac(codigo, d.get("sal", "")))


def token_google(datos: dict) -> str:
    """Correo verificado por Google que aún no tiene cuenta: completa su registro en 30 minutos."""
    return _firmar({**datos, "t": "google_registro"}, 30)


def canje_google(usuario_id: int, version: int) -> str:
    """Pase de un solo uso (2 minutos) que el navegador cambia por la sesión. No es una sesión: lleva «aud»."""
    return _firmar({"t": "google_entrar", "sub": str(usuario_id), "ver": version}, 2)


def registro_abierto(db: Session) -> bool:
    c = db.scalar(select(m.CmConfig))
    return c.registro_prueba if c else True


def validar_modulos(lista: list[str]) -> list[str]:
    elegidos = [x for x in dict.fromkeys(lista or []) if x]
    if not elegidos:
        raise HTTPException(422, "Elija al menos un módulo para su prueba.")
    if len(elegidos) > MAX_MODULOS:
        raise HTTPException(422, f"Puede elegir hasta {MAX_MODULOS} módulos para la prueba gratuita.")
    for x in elegidos:
        if x not in modulos.MODULOS:
            raise HTTPException(422, "Módulo desconocido.")
    return elegidos


def enviar_codigo(db: Session, email: str, nombre: str, codigo: str, para: str) -> None:
    if not correo.configurado():
        raise HTTPException(503, "El envío de correos no está disponible en este momento. Entre con Google o escríbanos para darle de alta.")
    asunto, html, texto = plantillas_correo.codigo_cuenta(nombre, codigo, MINUTOS_CODIGO, para)
    r = envios.registrar_y_enviar(db, f"codigo_{para}", [email], asunto, html, texto)
    if r is not None and r.estado != "enviado":
        raise HTTPException(502, "No pudimos enviar el correo. Revise la dirección o intente más tarde.")


def crear_cuenta(db: Session, *, organizacion: str, nombre: str, email: str, hash_contrasena: str, elegidos: list[str],
                 telefono: str | None, via: str, google_sub: str | None = None, ip: str | None = None,
                 acepta_whatsapp: bool = False) -> m.Usuario:
    """Organización + primer administrador + módulos elegidos + prueba de 7 días + lead en Ventas. No hace commit."""
    if db.scalar(select(m.Usuario.id).where(m.Usuario.email == email)):
        raise HTTPException(409, "Ese correo ya tiene cuenta. Inicie sesión o recupere su contraseña.")
    org = m.Organizacion(nombre=organizacion, origen="registro", modulos_prueba=elegidos)
    db.add(org)
    db.flush()
    u = m.Usuario(organizacion_id=org.id, email=email, nombre=nombre, hash_contrasena=hash_contrasena, rol="administrador",
                  google_sub=google_sub)
    db.add(u)
    db.flush()
    for clave in elegidos:  # solo los elegidos quedan contratados y activos durante la prueba
        modulos.fijar(db, org.id, clave, contratado=True, activo=True)
    for clave in modulos.MODULOS:
        if clave not in elegidos:
            modulos.fijar(db, org.id, clave, contratado=False)
    inicio = sus.hoy()
    fin = sus.calcular_fin("prueba", inicio)
    db.add(m.PeriodoSuscripcion(organizacion_id=org.id, plan="prueba", inicio=inicio, fin=fin, pagado=False,
                                nota=f"Prueba en línea ({'Google' if via == 'google' else 'correo'})"))
    nombres = [modulos.MODULOS[x]["nombre"] for x in elegidos]
    sol = m.Solicitud(tipo="prueba", nombre=nombre, empresa=organizacion, email=email, telefono=telefono, acepta_whatsapp=bool(telefono and acepta_whatsapp), ip=(ip or "")[:60] or None,
                      mensaje=f"Se registró en línea con prueba gratuita de 7 días ({'con Google' if via == 'google' else 'con su correo'}). "
                              f"Módulos elegidos: {', '.join(nombres)}. La prueba termina el {fin.isoformat()}.")
    db.add(sol)
    db.flush()
    ventas.desde_solicitud(db, sol)
    if correo.configurado():
        asunto, html, texto = plantillas_correo.bienvenida_prueba(nombre, organizacion, fin, nombres)
        try:
            envios.registrar_y_enviar(db, "bienvenida_prueba", [email], asunto, html, texto, organizacion_id=org.id, llave=f"bienvenida_prueba:{org.id}")
        except Exception:  # el correo de bienvenida no impide crear la cuenta
            pass
    try:  # aviso por WhatsApp solo si lo autorizó (y si el WhatsApp de Nomira está conectado)
        from . import whatsapp_nomira
        whatsapp_nomira.aviso(db, "bienvenida", org.id, [email], [nombre, organizacion, fin.strftime("%d/%m/%Y")], f"bienvenida:{org.id}")
    except Exception:
        pass
    return u


def estado_prueba(db: Session, org: m.Organizacion) -> dict | None:
    """Solo para cuentas de registro: {estado, bloqueada, dias_restantes, fin, modulos}."""
    if org.origen != "registro":
        return None
    ps = list(db.scalars(select(m.PeriodoSuscripcion).where(m.PeriodoSuscripcion.organizacion_id == org.id)))
    e = sus.estado(ps)
    return {"estado": e["estado"], "bloqueada": e["estado"] in ("vencida", "sin_plan"), "dias_restantes": e.get("dias_restantes"),
            "fin": e.get("fin"), "plan": e.get("plan"), "modulos": org.modulos_prueba or []}
