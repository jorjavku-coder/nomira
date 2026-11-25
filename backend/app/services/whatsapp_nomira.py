"""WhatsApp de NOMIRA (la empresa, no un despacho) con la Cloud API oficial de Meta.

- Entrada: cada mensaje que llega al número de Nomira entra a Ventas. Si el teléfono no es de un contacto,
  se crea un lead (MQL) con origen «WhatsApp» y una tarea de primer contacto; si ya existe, se agrega a su historial.
- Respuesta desde el panel: texto libre solo dentro de las 24 h siguientes al último mensaje de la persona (regla de Meta).
- Avisos automáticos (bienvenida a la prueba y vencimiento del plan): solo con plantillas aprobadas por Meta y solo a
  quien aceptó recibirlos por WhatsApp al registrarse. Si alguien escribe «BAJA», deja de recibirlos.

Todo queda apagado mientras falten WHATSAPP_NOMIRA_PHONE_ID y WHATSAPP_NOMIRA_TOKEN. Los registros nunca llevan
teléfonos ni textos de los mensajes.
"""
from __future__ import annotations

import logging
import unicodedata
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from .ventas import base as vb

log = logging.getLogger("nomira.whatsapp")
VENTANA = timedelta(hours=24)
PALABRAS_BAJA = {"baja", "stop", "alto", "cancelar", "no molestar", "no me escriban"}


class WaNomiraError(Exception):
    pass


def configurado() -> bool:
    a = ajustes()
    return bool(a.whatsapp_nomira_phone_id and a.whatsapp_nomira_token)


def faltantes() -> list[str]:
    a = ajustes()
    falta = []
    if not a.whatsapp_nomira_phone_id:
        falta.append("WHATSAPP_NOMIRA_PHONE_ID (identificador del número en Meta)")
    if not a.whatsapp_nomira_token:
        falta.append("WHATSAPP_NOMIRA_TOKEN (token permanente del usuario del sistema de Meta)")
    if not a.whatsapp_app_secret:
        falta.append("WHATSAPP_APP_SECRET (secreto de la app de Meta, para recibir mensajes)")
    if not a.whatsapp_verify_token:
        falta.append("WHATSAPP_VERIFY_TOKEN (palabra que usted inventa para registrar el webhook en Meta)")
    return falta


def es_numero_nomira(phone_number_id: str | None) -> bool:
    pid = ajustes().whatsapp_nomira_phone_id
    return bool(pid and phone_number_id and str(phone_number_id) == pid)


def diez(tel: str | None) -> str:
    """Los últimos 10 dígitos (número nacional de México) para comparar teléfonos escritos de distintas formas."""
    d = "".join(ch for ch in (tel or "") if ch.isdigit())
    return d[-10:] if len(d) >= 10 else ""


def destino(tel: str | None) -> str | None:
    """Formato que pide Meta: lada de país sin «+». México: 52 + 10 dígitos (sin el «1» antiguo de celulares)."""
    d = "".join(ch for ch in (tel or "") if ch.isdigit())
    if len(d) == 10:
        return "52" + d
    if len(d) == 13 and d.startswith("521"):
        return "52" + d[3:]
    if 11 <= len(d) <= 15:
        return d
    return None


def _enviar(cuerpo: dict) -> str:
    if not configurado():
        raise WaNomiraError("El WhatsApp de Nomira no está configurado.")
    a = ajustes()
    url = f"https://graph.facebook.com/{a.whatsapp_api_version}/{a.whatsapp_nomira_phone_id}/messages"
    try:
        r = httpx.post(url, json={"messaging_product": "whatsapp", **cuerpo},
                       headers={"Authorization": f"Bearer {a.whatsapp_nomira_token}"}, timeout=20)
    except httpx.HTTPError as e:
        raise WaNomiraError(f"No hubo conexión con WhatsApp ({type(e).__name__}).") from e
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    if r.status_code >= 300:
        err = datos.get("error") or {}
        raise WaNomiraError(f"WhatsApp rechazó el mensaje ({r.status_code}): {err.get('message') or 'sin detalle'}")
    return ((datos.get("messages") or [{}])[0]).get("id") or ""


def enviar_texto(tel: str, texto: str) -> str:
    to = destino(tel)
    if not to:
        raise WaNomiraError("El teléfono no es válido para WhatsApp.")
    return _enviar({"to": to, "type": "text", "text": {"body": texto[:4096], "preview_url": False}})


def enviar_plantilla(tel: str, plantilla: str, parametros: list[str]) -> str:
    to = destino(tel)
    if not to:
        raise WaNomiraError("El teléfono no es válido para WhatsApp.")
    comp = [{"type": "body", "parameters": [{"type": "text", "text": str(p)[:200]} for p in parametros]}] if parametros else []
    return _enviar({"to": to, "type": "template",
                    "template": {"name": plantilla, "language": {"code": ajustes().whatsapp_nomira_idioma}, "components": comp}})


# ---------------------------------------------------------------- entrada


def _primera_vez(db: Session, llave: str) -> bool:
    try:
        with db.begin_nested():
            db.add(m.AfEventoWebhook(llave=llave[:200]))
            db.flush()
        return True
    except IntegrityError:
        return False


def _texto(msg: dict) -> str:
    t = msg.get("type")
    if t == "text":
        return (msg.get("text") or {}).get("body") or ""
    if t == "button":
        return (msg.get("button") or {}).get("text") or ""
    if t == "interactive":
        i = msg.get("interactive") or {}
        return (i.get("button_reply") or i.get("list_reply") or {}).get("title") or ""
    nombres = {"image": "una imagen", "document": "un documento", "audio": "un audio", "video": "un video",
               "sticker": "un sticker", "location": "una ubicación", "contacts": "un contacto"}
    return f"[Envió {nombres.get(t, 'un mensaje')}: ábralo en WhatsApp Manager]"


def _plano(t: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", t.lower().strip(" .!¡")) if unicodedata.category(ch) != "Mn")


def contacto_por_telefono(db: Session, tel: str) -> m.VtContacto | None:
    d = diez(tel)
    if not d:
        return None
    for c in db.scalars(select(m.VtContacto).where(m.VtContacto.telefono.is_not(None)).order_by(m.VtContacto.id)):
        if diez(c.telefono) == d:
            return c
    return None


def entrante(db: Session, msg: dict, contactos: list | None) -> m.VtContacto | None:
    """Un mensaje que llegó al número de Nomira. Idempotente por id de mensaje. No hace commit."""
    wamid, tel = msg.get("id"), msg.get("from") or ""
    if not wamid or not diez(tel) or not _primera_vez(db, f"nomira:msg:{wamid}"):
        return None
    perfil = next((((c.get("profile") or {}).get("name")) for c in (contactos or []) if c.get("wa_id") == tel), None)
    texto = _texto(msg)[:4000]
    ct = contacto_por_telefono(db, tel)
    nuevo = ct is None
    if nuevo:
        ct = m.VtContacto(nombre=(perfil or f"WhatsApp {diez(tel)}")[:200], telefono=diez(tel), origen="whatsapp", fase="mql",
                          notas="Llegó escribiendo al WhatsApp de Nomira.")
        db.add(ct)
        db.flush()
    elif ct.fase == "descartado" and not ct.no_contactar:
        ct.fase, ct.motivo_descarte = "mql", None  # volvió a escribir: regresa a leads
    ct.whatsapp_ultimo_entrante = m.ahora()
    op = db.scalar(select(m.VtOportunidad).where(m.VtOportunidad.contacto_id == ct.id, m.VtOportunidad.etapa.in_(vb.ABIERTAS)).limit(1))
    vb.actividad(db, ct.id, op.id if op else None, "whatsapp", "Mensaje recibido", texto or None)
    if _plano(texto) in PALABRAS_BAJA:
        ct.acepta_whatsapp = False
        vb.actividad(db, ct.id, op.id if op else None, "sistema", "Pidió no recibir avisos por WhatsApp", None)
    if nuevo:
        vb.actividad(db, ct.id, None, "tarea", "Primer contacto con el prospecto", None, vence_en=m.ahora() + timedelta(hours=24))
    return ct


def ventana_abierta(ct: m.VtContacto) -> bool:
    return bool(ct.whatsapp_ultimo_entrante and m.ahora() - ct.whatsapp_ultimo_entrante < VENTANA)


def responder(db: Session, ct: m.VtContacto, texto: str, admin_id: int | None) -> m.VtActividad:
    """Respuesta escrita por una persona en el panel. No hace commit."""
    if not ct.telefono:
        raise WaNomiraError("El contacto no tiene teléfono.")
    if not ventana_abierta(ct):
        raise WaNomiraError("Pasaron más de 24 horas desde su último mensaje: Meta solo permite escribirle con una plantilla "
                            "aprobada. Llámele o espere a que vuelva a escribir.")
    enviar_texto(ct.telefono, texto)
    op = db.scalar(select(m.VtOportunidad).where(m.VtOportunidad.contacto_id == ct.id, m.VtOportunidad.etapa.in_(vb.ABIERTAS)).limit(1))
    return vb.actividad(db, ct.id, op.id if op else None, "whatsapp", "Mensaje enviado", texto, admin_id)


# ---------------------------------------------------------------- avisos automáticos


def _contacto_de_org(db: Session, org_id: int, correos: list[str]) -> m.VtContacto | None:
    c = db.scalar(select(m.VtContacto).where(m.VtContacto.organizacion_id == org_id, m.VtContacto.telefono.is_not(None)).limit(1))
    if c is None and correos:
        from sqlalchemy import func
        c = db.scalar(select(m.VtContacto).where(func.lower(m.VtContacto.email).in_([x.lower() for x in correos]),
                                                 m.VtContacto.telefono.is_not(None)).limit(1))
    return c


def aviso(db: Session, tipo: str, org_id: int, correos: list[str], parametros: list[str], llave: str) -> str:
    """Manda un aviso de cuenta con plantilla. Devuelve «enviado», «omitido: …» o «error: …». Nunca lanza."""
    if not configurado():
        return "omitido: WhatsApp de Nomira sin configurar"
    ct = _contacto_de_org(db, org_id, correos)
    if ct is None or not ct.acepta_whatsapp or ct.no_contactar:
        return "omitido: sin teléfono o sin autorización para WhatsApp"
    a = ajustes()
    plantilla = a.whatsapp_nomira_plantilla_bienvenida if tipo == "bienvenida" else a.whatsapp_nomira_plantilla_vencimiento
    if not plantilla:
        return "omitido: sin plantilla"
    if not _primera_vez(db, f"nomira:aviso:{llave}"):
        return "omitido: ya se había enviado"
    try:
        enviar_plantilla(ct.telefono, plantilla, parametros)
    except WaNomiraError as e:
        log.warning("No se envió el aviso de WhatsApp %s: %s", tipo, type(e).__name__)
        db.execute(m.AfEventoWebhook.__table__.delete().where(m.AfEventoWebhook.llave == f"nomira:aviso:{llave}"[:200]))
        return f"error: {e}"
    vb.actividad(db, ct.id, None, "whatsapp", "Aviso automático por WhatsApp: " + ("bienvenida" if tipo == "bienvenida" else "vencimiento del plan"),
                 f"Plantilla «{plantilla}».")
    return "enviado"
