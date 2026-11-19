"""Mensajes al cliente con aprobación humana.

Reglas:
- Solo se generan si el cliente dio consentimiento para algún canal.
- Si falta algo (consentimiento, teléfono, integración, plantilla aprobada…) quedan como BORRADOR con
  el motivo; nunca se finge un envío.
- Por omisión TODA plantilla requiere aprobación del abogado; el despacho puede marcar alguna como
  «automática», y aun así solo sale si todo lo necesario está listo.
- El texto guardado no incluye el enlace: «[enlace seguro al portal]» se reemplaza al enviar por un
  acceso nuevo con vencimiento. Los mensajes no llevan CURP, NSS, saldos ni datos familiares.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import correo, envios
from ..plantillas_correo import _base, escape
from . import portal, whatsapp
from .catalogos import PLANTILLAS

ENLACE = "[enlace seguro al portal]"
ESTADOS = {"borrador": "Borrador", "esperando_aprobacion": "Esperando aprobación", "enviado": "Enviado", "entregado": "Entregado",
           "leido": "Leído", "fallido": "Falló", "cancelado": "Cancelado", "recibido": "Recibido", "por_asignar": "Por asignar"}
_SENSIBLE = [(re.compile(r"[A-Z]{4}\d{6}[HMX][A-Z]{5}[0-9A-Z]\d", re.I), "una CURP"), (re.compile(r"\d{8,}"), "números largos (NSS, cuentas)"),
             (re.compile(r"\$\s?\d"), "cantidades de dinero")]


def revisar_texto(texto: str) -> None:
    """Las plantillas solo pueden usar {nombre} y {enlace} y no deben contener datos sensibles."""
    from fastapi import HTTPException

    for rx, que in _SENSIBLE:
        if rx.search(texto):
            raise HTTPException(422, f"El mensaje no debe incluir {que}. Use el portal seguro para los detalles.")
    otras = set(re.findall(r"\{(\w+)\}", texto)) - {"nombre", "enlace"}
    if otras:
        raise HTTPException(422, "Solo puede usar {nombre} y {enlace} en las plantillas.")


def plantillas(db: Session, org_id: int) -> dict[str, m.AfPlantilla]:
    """Plantillas del despacho; las que faltan se crean con el texto de fábrica (requieren aprobación)."""
    actuales = {p.clave: p for p in db.scalars(select(m.AfPlantilla).where(m.AfPlantilla.organizacion_id == org_id))}
    for clave, (nombre, texto) in PLANTILLAS.items():
        if clave not in actuales:
            actuales[clave] = m.AfPlantilla(organizacion_id=org_id, clave=clave, nombre=nombre, texto=texto, envio="aprobacion",
                                            wa_idioma="es_MX", wa_aprobada=False)
            db.add(actuales[clave])
    db.flush()
    return actuales


def config(db: Session, org_id: int) -> m.AfConfig:
    c = db.scalar(select(m.AfConfig).where(m.AfConfig.organizacion_id == org_id))
    if c is None:
        c = m.AfConfig(organizacion_id=org_id, curp_oficial_autorizado=False)
        db.add(c)
        db.flush()
    return c


def consentimiento(db: Session, cliente_id: int, canal: str) -> m.AfConsentimiento | None:
    return db.scalar(select(m.AfConsentimiento).where(m.AfConsentimiento.cliente_id == cliente_id, m.AfConsentimiento.canal == canal,
                                                      m.AfConsentimiento.revocado_en.is_(None)).order_by(m.AfConsentimiento.id.desc()))


def canal_para(db: Session, c: m.AfCliente) -> str | None:
    """El canal preferido si tiene consentimiento; si no, cualquiera con consentimiento."""
    orden = [c.preferencia_contacto] + [x for x in ("whatsapp", "correo") if x != c.preferencia_contacto]
    return next((x for x in orden if x in ("whatsapp", "correo") and consentimiento(db, c.id, x)), None)


def faltantes(db: Session, msj: m.AfMensaje, c: m.AfCliente | None, p: m.AfPlantilla | None) -> list[str]:
    falta = []
    if c is None:
        return ["El mensaje no tiene cliente asignado."]
    if not consentimiento(db, c.id, msj.canal):
        falta.append(f"El cliente no ha dado (o revocó) su consentimiento para recibir mensajes por {msj.canal}.")
    if msj.canal == "whatsapp":
        cfg = config(db, msj.organizacion_id)
        if not c.telefono:
            falta.append("El cliente no tiene un teléfono registrado.")
        if not whatsapp.conectado(cfg):
            falta.append("WhatsApp no está conectado: registre el número empresarial y el token en Configuración.")
        if not p or not p.wa_nombre or not p.wa_aprobada:
            falta.append("La plantilla no está registrada como aprobada por Meta (nombre de la plantilla aprobada).")
    else:
        if not c.email:
            falta.append("El cliente no tiene correo registrado.")
        if not correo.configurado():
            falta.append("El envío de correos no está configurado en el servidor.")
    return falta


def generar(db: Session, org_id: int, cliente: m.AfCliente, caso: m.AfCaso | None, clave: str, origen: str,
            usuario: m.Usuario | None, canal: str | None = None, texto: str | None = None) -> m.AfMensaje | None:
    """Crea el mensaje: borrador (si falta algo), esperando aprobación o, si la plantilla es automática
    y todo está listo, lo envía. Sin consentimiento en ningún canal no crea nada."""
    canal = canal or canal_para(db, cliente)
    if canal is None:
        return None
    pls = plantillas(db, org_id)
    p = pls.get(clave)
    base = texto or (p.texto if p else "")
    revisar_texto(base)
    msj = m.AfMensaje(organizacion_id=org_id, cliente_id=cliente.id, caso_id=caso.id if caso else None, canal=canal, direccion="saliente",
                      plantilla=clave, texto=base.replace("{nombre}", cliente.nombre.split()[0]).replace("{enlace}", ENLACE),
                      estado="borrador", origen=origen, telefono=cliente.telefono, creado_por_id=usuario.id if usuario else None)
    db.add(msj)
    db.flush()
    actualizar_estado(db, msj, cliente, p)
    if msj.estado == "esperando_aprobacion" and p and p.envio == "automatico":
        enviar(db, msj, None)
    return msj


def actualizar_estado(db: Session, msj: m.AfMensaje, c: m.AfCliente | None = None, p: m.AfPlantilla | None = None) -> None:
    if msj.estado not in ("borrador", "esperando_aprobacion", "fallido"):
        return
    c = c or (db.get(m.AfCliente, msj.cliente_id) if msj.cliente_id else None)
    p = p or plantillas(db, msj.organizacion_id).get(msj.plantilla or "")
    falta = faltantes(db, msj, c, p)
    if msj.estado != "fallido":
        msj.estado = "borrador" if falta else "esperando_aprobacion"
    msj.motivo = " ".join(falta) or None


def enviar(db: Session, msj: m.AfMensaje, usuario: m.Usuario | None) -> m.AfMensaje:
    """Envía de verdad o deja el mensaje como fallido con el error del proveedor."""
    c = db.get(m.AfCliente, msj.cliente_id) if msj.cliente_id else None
    p = plantillas(db, msj.organizacion_id).get(msj.plantilla or "")
    falta = faltantes(db, msj, c, p)
    if falta:
        msj.estado, msj.motivo = "borrador", " ".join(falta)
        return msj
    if usuario:
        msj.aprobado_por_id, msj.aprobado_en = usuario.id, m.ahora()
    acceso, enlace = (None, None)
    if ENLACE in msj.texto:
        acceso, _, enlace = portal.nuevo_acceso(db, c, usuario, dias=7)
    texto = msj.texto.replace(ENLACE, enlace or "")
    try:
        if msj.canal == "whatsapp":
            params = [c.nombre.split()[0]] + ([enlace] if enlace else [])
            msj.proveedor_id = whatsapp.enviar_plantilla(config(db, msj.organizacion_id), c.telefono, p.wa_nombre, p.wa_idioma, params)
        else:
            org = db.get(m.Organizacion, msj.organizacion_id)
            html = _base(texto[:90], f'<p style="margin:0;white-space:pre-line">{escape(texto)}</p>',
                         pie=f"Recibe este correo porque autorizó a {org.nombre} a enviarle actualizaciones.")
            r = envios.registrar_y_enviar(db, "af_mensaje", [c.email], f"{org.nombre}: actualización de su trámite", html, texto,
                                          organizacion_id=msj.organizacion_id)
            if r.estado != "enviado":
                raise whatsapp.WhatsAppError(r.error or "No se pudo enviar el correo.")
        msj.estado, msj.enviado_en, msj.error, msj.motivo = "enviado", m.ahora(), None, None
    except whatsapp.WhatsAppError as e:
        msj.estado, msj.error = "fallido", str(e)[:1000]
        if acceso:
            acceso.revocado_en = m.ahora()
    return msj
