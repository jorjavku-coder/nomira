"""WhatsApp Business Platform — Cloud API OFICIAL de Meta. No hay WhatsApp Web, emulación ni QR.

Cada despacho registra su propio número empresarial (phone_number_id) y su token de acceso, que se
guarda cifrado y nunca vuelve al navegador. Los webhooks llegan a la app de Meta de la plataforma:
se valida su firma (X-Hub-Signature-256 con WHATSAPP_APP_SECRET) y cada evento se procesa una sola vez.
"""
from __future__ import annotations

import hashlib
import hmac

import httpx

from ...config import ajustes
from .cifrado import descifrar


class WhatsAppError(Exception):
    pass


def faltantes_plataforma() -> list[str]:
    a = ajustes()
    falta = []
    if not a.whatsapp_app_secret:
        falta.append("WHATSAPP_APP_SECRET (secreto de la app de Meta, para validar los webhooks)")
    if not a.whatsapp_verify_token:
        falta.append("WHATSAPP_VERIFY_TOKEN (para registrar el webhook en Meta)")
    return falta


def conectado(cfg) -> bool:
    return bool(cfg and cfg.wa_phone_number_id and cfg.wa_token_cifrado)


def firma_valida(cuerpo: bytes, firma: str | None) -> bool:
    secreto = ajustes().whatsapp_app_secret
    if not secreto or not firma or not firma.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma[7:])


def enviar_plantilla(cfg, telefono: str, nombre_plantilla: str, idioma: str, parametros: list[str]) -> str:
    """Envía una plantilla aprobada por Meta. Devuelve el id del mensaje (wamid) o lanza WhatsAppError."""
    token = descifrar(cfg.wa_token_cifrado)
    if not token:
        raise WhatsAppError("No se pudo leer el token de WhatsApp: vuelva a conectarlo en Configuración.")
    url = f"https://graph.facebook.com/{ajustes().whatsapp_api_version}/{cfg.wa_phone_number_id}/messages"
    cuerpo = {"messaging_product": "whatsapp", "to": telefono, "type": "template",
              "template": {"name": nombre_plantilla, "language": {"code": idioma},
                           "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in parametros]}]}}
    try:
        r = httpx.post(url, json=cuerpo, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    except httpx.HTTPError as e:
        raise WhatsAppError(f"No se pudo conectar con WhatsApp ({type(e).__name__}).") from e
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    if r.status_code >= 300:
        err = (datos.get("error") or {})
        raise WhatsAppError(f"WhatsApp rechazó el envío ({r.status_code}): {err.get('message') or r.text[:200]}")
    try:
        return datos["messages"][0]["id"]
    except (KeyError, IndexError, TypeError):
        raise WhatsAppError("WhatsApp no devolvió el identificador del mensaje.")
