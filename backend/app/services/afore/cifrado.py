"""Cifrado de datos sensibles en reposo (CURP, NSS, token de WhatsApp). La clave vive solo en el
servidor: AFORE_CLAVE_CIFRADO o, si no se define, una derivada de JWT_SECRETO."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ...config import ajustes


def _fernet() -> Fernet:
    a = ajustes()
    base = a.afore_clave_cifrado or ("nomira-afore:" + a.jwt_secreto)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(base.encode()).digest()))


def cifrar(v: str | None) -> str | None:
    return _fernet().encrypt(v.encode()).decode() if v else None


def descifrar(v: str | None) -> str | None:
    if not v:
        return None
    try:
        return _fernet().decrypt(v.encode()).decode()
    except InvalidToken:
        return None
