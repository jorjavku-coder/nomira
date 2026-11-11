from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import ajustes

ROLES = ("administrador", "analista", "consulta")


def hash_contrasena(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode()[:72], bcrypt.gensalt(rounds=12)).decode()


def verificar_contrasena(contrasena: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(contrasena.encode()[:72], hash_.encode())
    except ValueError:
        return False


def crear_token(usuario_id: int, organizacion_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ajustes().jwt_minutos)
    return jwt.encode({"sub": str(usuario_id), "org": organizacion_id, "exp": exp},
                      ajustes().jwt_secreto, algorithm="HS256")


def leer_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, ajustes().jwt_secreto, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
