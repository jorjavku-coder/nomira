"""Acceso del cliente a su portal de Nomira Connect. Mismo diseño que AFORE y Evidencia: token aleatorio en el
fragmento de la URL (no viaja al servidor en la barra), solo se guarda su huella, vence, se puede revocar y pide
un código al correo del cliente cuando lo tiene."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from ... import models as m
from ...config import ajustes
from ..evidencia import solicitudes as sol

AUDIENCIA = "nomira-connect-portal"
DESFASE_CODIGO = 20_000_000  # separa las huellas de código de las de otros portales


def nuevo_acceso(db, c: m.CrCliente, u: m.Usuario | None, dias: int = 30):
    token = sol.nuevo_token()
    a = m.CnAcceso(organizacion_id=c.organizacion_id, cliente_id=c.id, token_hash=sol.huella(token), token_pista=token[:4],
                   requiere_codigo=bool(c.email), expira_en=m.ahora() + timedelta(days=dias), codigo_intentos=0, codigos_enviados=0,
                   visitas=0, creado_por_id=u.id if u else None)
    db.add(a)
    db.flush()
    return a, token, ajustes().url_publica.rstrip("/") + "/mi-asunto#" + token


def estado(a: m.CnAcceso) -> str:
    if a.revocado_en:
        return "revocado"
    if sol._aware(a.expira_en) <= m.ahora():
        return "vencido"
    return "activo"


def crear_sesion(a: m.CnAcceso) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=60)
    return jwt.encode({"sub": str(a.id), "aud": AUDIENCIA, "th": a.token_hash[:16], "exp": exp}, ajustes().jwt_secreto, algorithm="HS256")


def sesion_valida(token: str | None, a: m.CnAcceso) -> bool:
    if not token:
        return False
    try:
        d = jwt.decode(token, ajustes().jwt_secreto, algorithms=["HS256"], audience=AUDIENCIA)
    except jwt.PyJWTError:
        return False
    return d.get("sub") == str(a.id) and d.get("th") == a.token_hash[:16]
