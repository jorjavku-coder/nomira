"""Mensajes de WhatsApp que llegan al número del despacho conectado en Nomira Leads.

- Si el teléfono corresponde a UN prospecto abierto, el mensaje se vincula a él (y a su responsable).
- Si no existe, se crea un prospecto nuevo con canal WhatsApp; si viene de un anuncio «clic a
  WhatsApp» de Meta o trae un código de campaña («ref: K7M2QX»), se atribuye a esa campaña.
- Si hay varios prospectos posibles, queda «por asignar»: Nomira no adivina.
- «BAJA» revoca el consentimiento de WhatsApp. Nunca se responde automáticamente.
"""
from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from . import base

ESTADOS = {"sent": "enviado", "delivered": "entregado", "read": "leido", "failed": "fallido"}
_ORDEN = ["enviado", "entregado", "leido"]


def primera_vez(db: Session, llave: str) -> bool:
    try:
        with db.begin_nested():
            db.add(m.LdEventoExterno(llave=llave[:200]))
            db.flush()
        return True
    except IntegrityError:
        return False


def config_por_numero(db: Session, phone_number_id: str | None) -> m.LdConfig | None:
    if not phone_number_id:
        return None
    cfg = db.scalar(select(m.LdConfig).where(m.LdConfig.wa_phone_number_id == phone_number_id))
    if not cfg or not cfg.wa_token_cifrado:
        return None
    org = db.get(m.Organizacion, cfg.organizacion_id)
    if not org or org.estado != "activa" or "leads" not in modulos.activos(db, cfg.organizacion_id):
        return None
    return cfg


def estado(db: Session, cfg: m.LdConfig, st: dict) -> None:
    wamid, est = st.get("id"), ESTADOS.get(st.get("status") or "")
    if not wamid or not est or not primera_vez(db, f"wa-st:{wamid}:{est}"):
        return
    x = db.scalar(select(m.LdMensaje).where(m.LdMensaje.proveedor_id == wamid, m.LdMensaje.organizacion_id == cfg.organizacion_id))
    if not x:
        return
    if est == "fallido":
        x.estado = "fallido"
        x.error = "; ".join((e.get("title") or e.get("message") or "") for e in st.get("errors", []))[:1000] or "WhatsApp informó una falla."
    elif x.estado not in _ORDEN or _ORDEN.index(est) > _ORDEN.index(x.estado):
        x.estado = est
    if est == "entregado":
        x.entregado_en = x.entregado_en or m.ahora()
    if est == "leido":
        x.leido_en = x.leido_en or m.ahora()


def _plano(t: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", t.lower().strip()) if unicodedata.category(ch) != "Mn")


def entrante(db: Session, cfg: m.LdConfig, mensaje: dict, contactos: list | None = None) -> None:
    wamid = mensaje.get("id")
    if not wamid or not primera_vez(db, f"wa-in:{wamid}"):
        return
    org = cfg.organizacion_id
    tel = "".join(ch for ch in (mensaje.get("from") or "") if ch.isdigit())
    try:
        tel = base.telefono(tel) or tel
    except Exception:
        pass
    texto = ((mensaje.get("text") or {}).get("body") or f"[{mensaje.get('type', 'mensaje')} sin texto]")[:4000]
    perfil = next((((c.get("profile") or {}).get("name")) for c in (contactos or []) if c.get("wa_id") == mensaje.get("from")), None)
    abiertas = [e.id for e in base.etapas(db, org, todas=True) if e.tipo == "abierta"]
    todos = [p for p in db.scalars(select(m.LdProspecto).where(m.LdProspecto.organizacion_id == org, m.LdProspecto.anonimizado_en.is_(None)))
             if p.telefono and tel and p.telefono[-10:] == tel[-10:]]
    abiertos = [p for p in todos if p.etapa_id in abiertas]
    x = m.LdMensaje(organizacion_id=org, canal="whatsapp", direccion="entrante", texto=texto, estado="recibido", telefono=tel or None,
                    proveedor_id=wamid, respondido=False)
    if len(abiertos) == 1:
        p = abiertos[0]
        base.actividad(db, p, "mensaje", "Escribió por WhatsApp")
    elif len(abiertos) > 1:  # varios prospectos abiertos con ese número: no se adivina
        x.estado, p = "por_asignar", None
    else:
        ref = mensaje.get("referral") or {}
        campana = base.campana_por_codigo(db, org, texto)
        if not campana and ref.get("source_id"):
            campana = db.scalar(select(m.LdCampana).where(m.LdCampana.organizacion_id == org, m.LdCampana.id_externo == str(ref["source_id"])))
        origen = {"anuncio": {k: ref.get(k) for k in ("source_type", "source_id", "headline") if ref.get(k)}} if ref else None
        if todos:  # ya fue prospecto (cerrado): se abre una nueva oportunidad con su historial aparte
            origen = {**(origen or {}), "antes": [p.id for p in todos]}
        p, _ = base.alta_externa(db, org, nombre=perfil, tel=tel or None, email=None,
                                 canal=campana.canal if campana else "whatsapp", campana=campana, entrada="whatsapp",
                                 origen=origen, descripcion=texto)
        p.responsable_id = p.responsable_id or (todos[0].responsable_id if todos else None)
    if p is not None:
        x.prospecto_id = p.id
        if _plano(texto) not in ("baja", "stop", "cancelar", "no mas mensajes"):
            base.consentir(db, p, ["whatsapp"], "mensaje", finalidad="Responder la consulta que inició por WhatsApp")
        else:
            for c in db.scalars(select(m.LdConsentimiento).where(m.LdConsentimiento.prospecto_id == p.id, m.LdConsentimiento.canal == "whatsapp",
                                                                 m.LdConsentimiento.revocado_en.is_(None))):
                c.revocado_en, c.revocado_medio = m.ahora(), "mensaje"
            base.actividad(db, p, "consentimiento", "Pidió no recibir más mensajes de WhatsApp («BAJA»)")
            x.respondido = True
    db.add(x)
    db.flush()
