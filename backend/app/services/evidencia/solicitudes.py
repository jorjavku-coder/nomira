"""Solicitudes de documentos al cliente: un enlace que SOLO permite subir archivos a un asunto.

Seguridad:
- El token es aleatorio (256 bits) y no se guarda: solo su huella SHA-256 y 4 caracteres para
  reconocerlo. Viaja en el fragmento de la URL (/subir#token), que el navegador nunca envía al
  servidor, y de ahí en un encabezado: no aparece en registros de acceso ni en el historial del proxy.
- Vence (el abogado elige la vigencia), se puede revocar y tiene un tope de archivos.
- Opcionalmente exige un código de un solo uso enviado al correo destinatario: el código se guarda
  como HMAC, vence en 10 minutos y admite 5 intentos.
- Lo que llega queda «recibido» y no se lee hasta que una persona lo acepta.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from ... import models as m
from ...config import ajustes

AUDIENCIA = "nomira-subida"
CODIGO_MINUTOS = 10
CODIGO_INTENTOS = 5
CODIGO_ESPERA_SEGUNDOS = 60
CODIGOS_MAXIMOS = 15
SESION_MINUTOS = 60
MAX_POR_ENVIO = 10
VIGENCIAS = (1, 3, 7, 14, 30)
_RE_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def enlace(token: str) -> str:
    return ajustes().url_publica.rstrip("/") + "/subir#" + token


def email_valido(e: str) -> bool:
    return bool(_RE_EMAIL.match(e))


def enmascarar(email: str) -> str:
    """l•••a@g•••.com: el cliente reconoce su correo sin que el enlace revele la dirección completa."""
    usuario, _, dominio = email.partition("@")
    nombre, _, ext = dominio.rpartition(".")
    tapar = lambda s: (s[:1] + "•••" + (s[-1:] if len(s) > 2 else "")) if s else s  # noqa: E731
    return f"{tapar(usuario)}@{tapar(nombre)}.{ext}"


def _aware(d: datetime | None) -> datetime | None:
    return d.replace(tzinfo=timezone.utc) if d is not None and d.tzinfo is None else d


def estado(s: m.EvSolicitud, ahora: datetime | None = None) -> str:
    ahora = ahora or m.ahora()
    if s.revocada_en:
        return "revocada"
    if _aware(s.expira_en) <= ahora:
        return "vencida"
    if s.archivos_recibidos >= s.max_archivos:
        return "completa"
    return "activa"


ESTADOS = {"activa": "Activa", "vencida": "Vencida", "revocada": "Revocada", "completa": "Límite de archivos alcanzado"}


def solicitud_dict(s: m.EvSolicitud, nombres: dict[int, str] | None = None) -> dict:
    """Para el abogado (nunca incluye el token ni su huella)."""
    nombres = nombres or {}
    e = estado(s)
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {"id": s.id, "email": s.email, "mensaje": s.mensaje, "documentos": s.documentos or [], "estado": e,
            "estado_texto": ESTADOS[e], "pista": s.token_pista, "requiere_codigo": s.requiere_codigo,
            "max_archivos": s.max_archivos, "archivos_recibidos": s.archivos_recibidos, "expira_en": iso(s.expira_en),
            "revocada_en": iso(s.revocada_en), "revocada_por": nombres.get(s.revocada_por_id),
            "creado_por": nombres.get(s.creado_por_id), "creado_en": iso(s.creado_en),
            "primer_acceso_en": iso(s.primer_acceso_en), "ultimo_acceso_en": iso(s.ultimo_acceso_en),
            "ultima_carga_en": iso(s.ultima_carga_en), "utilizada": s.archivos_recibidos > 0}


# ---------- código de un solo uso ----------

def nuevo_codigo() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def huella_codigo(solicitud_id: int, codigo: str) -> str:
    return hmac.new(ajustes().jwt_secreto.encode(), f"{solicitud_id}:{codigo}".encode(), hashlib.sha256).hexdigest()


def codigo_correcto(s: m.EvSolicitud, codigo: str) -> bool:
    if not s.codigo_hash or not s.codigo_expira_en or _aware(s.codigo_expira_en) <= m.ahora():
        return False
    return hmac.compare_digest(s.codigo_hash, huella_codigo(s.id, codigo.strip()))


# ---------- sesión de carga (tras verificar el código) ----------

def crear_sesion(s: m.EvSolicitud) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=SESION_MINUTOS)
    return jwt.encode({"sub": str(s.id), "aud": AUDIENCIA, "th": s.token_hash[:16], "exp": exp},
                      ajustes().jwt_secreto, algorithm="HS256")


def sesion_valida(token_sesion: str | None, s: m.EvSolicitud) -> bool:
    """Debe ser de ESTE enlace: el panel de clientes y el de la plataforma rechazan este tipo de token
    (llevan otra audiencia), y este no sirve para otro enlace."""
    if not token_sesion:
        return False
    try:
        datos = jwt.decode(token_sesion, ajustes().jwt_secreto, algorithms=["HS256"], audience=AUDIENCIA)
    except jwt.PyJWTError:
        return False
    return datos.get("sub") == str(s.id) and datos.get("th") == s.token_hash[:16]
