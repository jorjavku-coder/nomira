from datetime import datetime, timedelta, timezone
from functools import lru_cache

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


@lru_cache
def _hash_señuelo() -> str:
    return hash_contrasena("contraseña-señuelo-que-nunca-coincide")


def gastar_tiempo_de_verificacion(contrasena: str) -> None:
    """Hace el mismo trabajo que una verificación real cuando el usuario no existe o está
    inactivo, para que el tiempo de respuesta no revele qué correos están registrados."""
    verificar_contrasena(contrasena, _hash_señuelo())


def crear_token(usuario_id: int, organizacion_id: int, version: int = 0) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ajustes().jwt_minutos)
    return jwt.encode({"sub": str(usuario_id), "org": organizacion_id, "ver": version, "exp": exp},
                      ajustes().jwt_secreto, algorithm="HS256")


def leer_token(token: str) -> dict | None:
    """Token de un usuario de una organización cliente. Rechaza los de la plataforma: llevan
    «aud» y PyJWT no acepta un «aud» que no se pidió."""
    try:
        return jwt.decode(token, ajustes().jwt_secreto, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


AUDIENCIA_PLATAFORMA = "nomira-plataforma"


def crear_token_plataforma(admin_id: int, version: int = 0) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ajustes().jwt_minutos)
    return jwt.encode({"sub": str(admin_id), "tipo": "plataforma", "aud": AUDIENCIA_PLATAFORMA, "ver": version,
                       "exp": exp}, ajustes().jwt_secreto, algorithm="HS256")


def leer_token_plataforma(token: str) -> dict | None:
    """Solo acepta tokens emitidos para el panel de la plataforma (exige «aud»)."""
    try:
        datos = jwt.decode(token, ajustes().jwt_secreto, algorithms=["HS256"], audience=AUDIENCIA_PLATAFORMA,
                           options={"require": ["aud", "exp", "sub"]})
    except jwt.PyJWTError:
        return None
    return datos if datos.get("tipo") == "plataforma" else None
