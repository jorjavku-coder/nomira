"""Accesos del cliente a su portal: mismo diseño que las solicitudes de Evidencia (token aleatorio en el
fragmento de la URL, solo se guarda su huella, vencimiento, revocación y código opcional por correo)."""
from __future__ import annotations

from datetime import timedelta

import jwt

from ... import models as m
from ...config import ajustes
from ..evidencia import solicitudes as sol

AUDIENCIA = "nomira-portal-afore"


def nuevo_acceso(db, cliente: m.AfCliente, usuario: m.Usuario | None, dias: int = 7, requiere_codigo: bool | None = None):
    token = sol.nuevo_token()
    a = m.AfAcceso(organizacion_id=cliente.organizacion_id, cliente_id=cliente.id, token_hash=sol.huella(token), token_pista=token[:4],
                   requiere_codigo=bool(cliente.email) if requiere_codigo is None else requiere_codigo,
                   expira_en=m.ahora() + timedelta(days=dias), codigo_intentos=0, codigos_enviados=0,
                   creado_por_id=usuario.id if usuario else None)
    db.add(a)
    db.flush()
    return a, token, ajustes().url_publica.rstrip("/") + "/portal#" + token


def estado(a: m.AfAcceso) -> str:
    if a.revocado_en:
        return "revocado"
    if sol._aware(a.expira_en) <= m.ahora():
        return "vencido"
    return "activo"


def crear_sesion(a: m.AfAcceso) -> str:
    from datetime import datetime, timezone

    exp = datetime.now(timezone.utc) + timedelta(minutes=60)
    return jwt.encode({"sub": str(a.id), "aud": AUDIENCIA, "th": a.token_hash[:16], "exp": exp}, ajustes().jwt_secreto, algorithm="HS256")


def sesion_valida(token: str | None, a: m.AfAcceso) -> bool:
    if not token:
        return False
    try:
        d = jwt.decode(token, ajustes().jwt_secreto, algorithms=["HS256"], audience=AUDIENCIA)
    except jwt.PyJWTError:
        return False
    return d.get("sub") == str(a.id) and d.get("th") == a.token_hash[:16]
