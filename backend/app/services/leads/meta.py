"""Integraciones OFICIALES de Meta para Nomira Leads. Sin WhatsApp Web, scraping ni envíos masivos.

- WhatsApp Business Platform (Cloud API): el despacho registra su número empresarial. Se puede
  responder con texto libre solo dentro de las 24 h siguientes al último mensaje del prospecto (regla
  de Meta); fuera de esa ventana, solo con una plantilla aprobada. Cada envío lo decide una persona.
- Anuncios de clientes potenciales (Lead Ads de Facebook e Instagram): Meta avisa por webhook y
  Nomira consulta los datos del formulario con el token de la página del despacho.
Ambos usan la app de Meta de la plataforma: WHATSAPP_APP_SECRET valida la firma de cada webhook y
WHATSAPP_VERIFY_TOKEN registra la URL. Los tokens del despacho se guardan cifrados.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ...config import ajustes
from ..afore.cifrado import descifrar  # cifrado común del servidor (no depende del módulo AFORE activo)


class MetaError(Exception):
    pass


def faltantes_plataforma() -> list[str]:
    a = ajustes()
    falta = []
    if not a.whatsapp_app_secret:
        falta.append("WHATSAPP_APP_SECRET (secreto de la app de Meta, para validar los avisos que envía Meta)")
    if not a.whatsapp_verify_token:
        falta.append("WHATSAPP_VERIFY_TOKEN (para registrar las URL de aviso en Meta)")
    return falta


def firma_valida(cuerpo: bytes, firma: str | None) -> bool:
    secreto = ajustes().whatsapp_app_secret
    if not secreto or not firma or not firma.startswith("sha256="):
        return False
    return hmac.compare_digest(hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest(), firma[7:])


def _graph(ruta: str) -> str:
    return f"https://graph.facebook.com/{ajustes().whatsapp_api_version}/{ruta.lstrip('/')}"


def _respuesta(r: httpx.Response, que: str) -> dict:
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    if r.status_code >= 300:
        err = datos.get("error") or {}
        raise MetaError(f"{que} ({r.status_code}): {err.get('message') or r.text[:200]}")
    return datos


# ---------- WhatsApp ----------

def wa_conectado(cfg: m.LdConfig | None) -> bool:
    return bool(cfg and cfg.wa_phone_number_id and cfg.wa_token_cifrado)


def ultima_entrada(db: Session, prospecto_id: int) -> m.LdMensaje | None:
    return db.scalar(select(m.LdMensaje).where(m.LdMensaje.prospecto_id == prospecto_id, m.LdMensaje.canal == "whatsapp",
                                              m.LdMensaje.direccion == "entrante").order_by(m.LdMensaje.creado_en.desc()))


def ventana_abierta(db: Session, prospecto_id: int) -> bool:
    x = ultima_entrada(db, prospecto_id)
    return bool(x and m.ahora() - x.creado_en < timedelta(hours=24))


def _enviar(cfg: m.LdConfig, cuerpo: dict) -> str:
    token = descifrar(cfg.wa_token_cifrado)
    if not token:
        raise MetaError("No se pudo leer el token de WhatsApp: vuelva a conectarlo en Configuración.")
    try:
        r = httpx.post(_graph(f"{cfg.wa_phone_number_id}/messages"), json={"messaging_product": "whatsapp", **cuerpo},
                       headers={"Authorization": f"Bearer {token}"}, timeout=20)
    except httpx.HTTPError as e:
        raise MetaError(f"No se pudo conectar con WhatsApp ({type(e).__name__}).") from e
    datos = _respuesta(r, "WhatsApp rechazó el envío")
    try:
        return datos["messages"][0]["id"]
    except (KeyError, IndexError, TypeError):
        raise MetaError("WhatsApp no devolvió el identificador del mensaje.")


def enviar_texto(cfg: m.LdConfig, tel: str, texto: str) -> str:
    return _enviar(cfg, {"to": tel, "type": "text", "text": {"body": texto, "preview_url": False}})


def enviar_plantilla(cfg: m.LdConfig, tel: str, nombre: str) -> str:
    return _enviar(cfg, {"to": tel, "type": "template", "template": {
        "name": cfg.wa_plantilla, "language": {"code": cfg.wa_plantilla_idioma or "es_MX"},
        "components": [{"type": "body", "parameters": [{"type": "text", "text": nombre}]}]}})


# ---------- Anuncios de clientes potenciales (Facebook e Instagram) ----------

def meta_conectado(cfg: m.LdConfig | None) -> bool:
    return bool(cfg and cfg.meta_page_id and cfg.meta_token_cifrado)


def suscribir_pagina(page_id: str, token: str) -> str | None:
    """Suscribe la página del despacho a los avisos de formularios (leadgen). Devuelve el nombre de la página."""
    try:
        r = httpx.post(_graph(f"{page_id}/subscribed_apps"), params={"subscribed_fields": "leadgen", "access_token": token}, timeout=20)
        _respuesta(r, "Meta no aceptó la suscripción de la página")
        r2 = httpx.get(_graph(page_id), params={"fields": "name", "access_token": token}, timeout=20)
        return _respuesta(r2, "Meta no devolvió los datos de la página").get("name")
    except httpx.HTTPError as e:
        raise MetaError(f"No se pudo conectar con Meta ({type(e).__name__}).") from e


def obtener_lead(cfg: m.LdConfig, leadgen_id: str) -> dict:
    token = descifrar(cfg.meta_token_cifrado)
    if not token:
        raise MetaError("No se pudo leer el token de la página.")
    try:
        r = httpx.get(_graph(leadgen_id), params={"access_token": token, "fields":
                      "field_data,created_time,ad_id,ad_name,adset_name,campaign_id,campaign_name,form_id,platform"}, timeout=20)
    except httpx.HTTPError as e:
        raise MetaError(f"No se pudo conectar con Meta ({type(e).__name__}).") from e
    return _respuesta(r, "Meta no devolvió el formulario")


def campos_lead(datos: dict) -> dict:
    """Convierte field_data de Meta a {nombre, telefono, email, ciudad, descripcion}."""
    f = {(x.get("name") or "").lower(): (x.get("values") or [""])[0] for x in datos.get("field_data") or []}
    nombre = f.get("full_name") or " ".join(x for x in (f.get("first_name"), f.get("last_name")) if x)
    otros = [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in f.items()
             if k not in ("full_name", "first_name", "last_name", "phone_number", "email", "city") and v]
    return {"nombre": nombre, "telefono": f.get("phone_number"), "email": f.get("email"), "ciudad": f.get("city"),
            "descripcion": "\n".join(otros)[:4000] or None}
