"""Verificación en dos pasos con códigos de 6 dígitos (TOTP, RFC 6238), compatible con Google
Authenticator, Microsoft Authenticator, 1Password, Authy, etc.

- El secreto se guarda CIFRADO (misma clave que los datos sensibles de AFORE).
- Un código ya usado no se acepta de nuevo (se guarda el último paso de 30 s aceptado).
- Códigos de respaldo de un solo uso, guardados con hash (nunca en claro).
- El inicio de sesión en dos pasos usa un «reto» firmado que caduca en 5 minutos.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt

from ..config import ajustes
from .afore.cifrado import cifrar, descifrar

PASO = 30
DIGITOS = 6
EMISOR = "Nomira"
AUD_RETO = "nomira-reto-2p"


def nuevo_secreto() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _codigo(secreto: str, paso: int) -> str:
    clave = base64.b32decode(secreto + "=" * (-len(secreto) % 8), casefold=True)
    h = hmac.new(clave, struct.pack(">Q", paso), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    n = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** DIGITOS
    return str(n).zfill(DIGITOS)


def paso_valido(secreto: str, codigo: str, ultimo: int | None, ahora: float | None = None) -> int | None:
    """Devuelve el paso aceptado (para guardarlo) o None. Tolera ±1 paso de desfase del reloj."""
    codigo = "".join(c for c in (codigo or "") if c.isdigit())
    if len(codigo) != DIGITOS:
        return None
    actual = int((ahora if ahora is not None else time.time()) // PASO)
    for p in (actual - 1, actual, actual + 1):
        if (ultimo is None or p > ultimo) and hmac.compare_digest(_codigo(secreto, p), codigo):
            return p
    return None


def uri(email: str, secreto: str, emisor: str = EMISOR) -> str:
    return f"otpauth://totp/{quote(emisor)}:{quote(email)}?secret={secreto}&issuer={quote(emisor)}&digits={DIGITOS}&period={PASO}"


def qr_svg(texto: str) -> str:
    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    w = QrCodeWidget(texto)
    x1, y1, x2, y2 = w.getBounds()
    lado = 220
    d = Drawing(lado, lado, transform=[lado / (x2 - x1), 0, 0, lado / (y2 - y1), 0, 0])
    d.add(w)
    return renderSVG.drawToString(d)


def _huella(codigo: str) -> str:
    return hmac.new(ajustes().jwt_secreto.encode(), codigo.replace("-", "").lower().encode(), hashlib.sha256).hexdigest()


def codigos_respaldo(n: int = 8) -> tuple[list[str], list[str]]:
    """(códigos para mostrar UNA vez, huellas para guardar)."""
    cods = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(n)]
    return cods, [_huella(c) for c in cods]


# ------------------------------------------------------------------ sobre un usuario o administrador

def activo(x) -> bool:
    return bool(x.totp_activo_en and x.totp_secreto_cifrado)


def preparar(x) -> str:
    """Guarda un secreto nuevo SIN activarlo (falta confirmar con un código)."""
    s = nuevo_secreto()
    x.totp_secreto_cifrado, x.totp_activo_en, x.totp_ultimo_paso, x.totp_respaldo = cifrar(s), None, None, None
    return s


def verificar(x, codigo: str) -> str | None:
    """Acepta un código de la app o uno de respaldo. Devuelve 'app' | 'respaldo' | None y actualiza el registro."""
    s = descifrar(x.totp_secreto_cifrado) if x.totp_secreto_cifrado else None
    if not s:
        return None
    p = paso_valido(s, codigo, x.totp_ultimo_paso)
    if p is not None:
        x.totp_ultimo_paso = p
        return "app"
    h = _huella((codigo or "").strip())
    quedan = list(x.totp_respaldo or [])
    if activo(x) and any(hmac.compare_digest(h, y) for y in quedan):
        x.totp_respaldo = [y for y in quedan if not hmac.compare_digest(h, y)]
        return "respaldo"
    return None


def activar(x, codigo: str) -> list[str] | None:
    if activo(x) or not x.totp_secreto_cifrado:
        return None
    s = descifrar(x.totp_secreto_cifrado)
    p = paso_valido(s, codigo, None) if s else None
    if p is None:
        return None
    cods, huellas = codigos_respaldo()
    x.totp_activo_en, x.totp_ultimo_paso, x.totp_respaldo = datetime.now(timezone.utc), p, huellas
    return cods


def quitar(x) -> None:
    x.totp_secreto_cifrado = x.totp_activo_en = x.totp_ultimo_paso = x.totp_respaldo = None


def estado(x) -> dict:
    return {"activo": activo(x), "desde": x.totp_activo_en.isoformat() if x.totp_activo_en else None,
            "respaldo_restantes": len(x.totp_respaldo or []) if activo(x) else 0}


# ------------------------------------------------------------------ reto de inicio de sesión

def crear_reto(tipo: str, sujeto_id: int, version: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    return jwt.encode({"sub": str(sujeto_id), "t": tipo, "ver": version, "aud": AUD_RETO, "exp": exp,
                       "jti": secrets.token_hex(8)}, ajustes().jwt_secreto, algorithm="HS256")


def leer_reto(reto: str, tipo: str) -> dict | None:
    try:
        d = jwt.decode(reto, ajustes().jwt_secreto, algorithms=["HS256"], audience=AUD_RETO, options={"require": ["aud", "exp", "sub"]})
    except jwt.PyJWTError:
        return None
    return d if d.get("t") == tipo else None
