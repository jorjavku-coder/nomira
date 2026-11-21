"""Rutas públicas de Nomira Leads (sin sesión de usuario):

1. Formulario de contacto (/api/leads-publico/formulario): lo que el despacho publica en su sitio, en
   sus redes sociales, en un correo o en un anuncio. El enlace (en el fragmento #) identifica al
   despacho o a la campaña; los datos llegan en el cuerpo, nunca en la URL. Exige consentimiento.
2. Entrada para otros sistemas (/api/leads-entrada): Zapier, Make, su sitio web o el webhook de
   formularios de Google Ads. Se autentica con la clave del despacho (solo se guarda su huella).
3. Anuncios de clientes potenciales de Meta (/api/meta/webhook): Facebook e Instagram avisan, se
   valida la firma y Nomira consulta el formulario con el token de la página del despacho.
Ninguna de estas rutas responde con asesoría ni envía mensajes: solo registra al prospecto.
"""
from __future__ import annotations

import hmac
import json
import logging
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, ip_cliente
from ..freno import Ventana
from ..services import modulos
from ..services.leads import base, meta
from ..services.leads import catalogos as cat
from ..services.leads.whatsapp_entrada import primera_vez

router = APIRouter(tags=["Nomira Leads — público"])
log = logging.getLogger("nomira.leads")
_fallos_ip = Ventana(30, 900)  # enlaces o claves inválidos
_altas_ip = Ventana(8, 3600)  # formularios enviados por IP y hora


def _org_activa(db: Session, org_id: int) -> bool:
    org = db.get(m.Organizacion, org_id)
    return bool(org and org.estado == "activa" and "leads" in modulos.activos(db, org_id))


def _destino(db: Session, request: Request, token: str | None) -> tuple[m.LdConfig, m.LdCampana | None]:
    ip = ip_cliente(request) or "?"
    if _fallos_ip.excedida(ip):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    cfg, camp = None, None
    if token and 16 <= len(token) <= 60:
        camp = db.scalar(select(m.LdCampana).where(m.LdCampana.enlace_token == token))
        if camp:
            cfg = base.config(db, camp.organizacion_id)
            if not camp.activa:
                raise HTTPException(410, "Esta campaña ya terminó. Puede comunicarse directamente con el despacho.")
        else:
            cfg = db.scalar(select(m.LdConfig).where(m.LdConfig.formulario_token == token, m.LdConfig.formulario_activo.is_(True)))
    if cfg is None:
        _fallos_ip.registrar(ip)
        raise HTTPException(404, "Este formulario no existe o ya no está disponible.")
    if not _org_activa(db, cfg.organizacion_id):
        raise HTTPException(410, "Este formulario ya no está disponible.")
    return cfg, camp


@router.post("/api/leads-publico/formulario/info")
def info_formulario(request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    cfg, camp = _destino(db, request, x_enlace)
    org = db.get(m.Organizacion, cfg.organizacion_id)
    db.commit()
    return {"despacho": org.nombre, "materias": base.materias(cfg), "campana": camp.nombre if camp else None,
            "aviso_privacidad_url": cfg.aviso_privacidad_url,
            "preferencias": {k: v for k, v in cat.PREFERENCIAS.items() if k != "ninguno"}}


class FormularioIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    telefono: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=254)
    ciudad: str | None = Field(None, max_length=120)
    materia: str | None = Field(None, max_length=120)
    descripcion: str | None = Field(None, max_length=2000)
    preferencia: str = "whatsapp"
    acepta: bool = False
    sitio_web: str | None = Field(None, max_length=200)  # campo trampa: las personas no lo ven
    utm: dict[str, str] | None = None


_UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


def _utm(v: dict | None) -> dict | None:
    if not v:
        return None
    r = {k: str(v[k])[:120] for k in _UTM if v.get(k)}
    return r or None


def _canal_de_utm(utm: dict | None) -> str | None:
    fuente = ((utm or {}).get("utm_source") or "").lower()
    for clave in ("facebook", "instagram", "tiktok", "linkedin", "google", "whatsapp"):
        if clave in fuente or (clave == "facebook" and fuente in ("fb", "meta")) or (clave == "instagram" and fuente == "ig"):
            return clave
    if fuente in ("email", "correo", "newsletter", "mailchimp", "brevo"):
        return "correo"
    return None


@router.post("/api/leads-publico/formulario", status_code=201)
def enviar_formulario(d: FormularioIn, request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    cfg, camp = _destino(db, request, x_enlace)
    ip = ip_cliente(request) or "?"
    if _altas_ip.excedida(ip):
        raise HTTPException(429, "Recibimos varias solicitudes desde su conexión. Intente más tarde.")
    _altas_ip.registrar(ip)
    if d.sitio_web:  # robot: se responde igual para no darle pistas
        return {"ok": True}
    if not d.acepta:
        raise HTTPException(422, "Para que el despacho le contacte necesitamos su autorización.")
    tel = base.telefono(d.telefono) if d.telefono else None
    email = (d.email or "").strip().lower() or None
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "El correo no parece válido.")
    if not tel and not email:
        raise HTTPException(422, "Escriba un teléfono o un correo para que puedan responderle.")
    utm = _utm(d.utm)
    if not camp and utm and utm.get("utm_campaign"):
        camp = base.campana_por_codigo(db, cfg.organizacion_id, utm["utm_campaign"])
    canal = (camp.canal if camp else None) or _canal_de_utm(utm) or "sitio_web"
    canales = (["whatsapp", "llamada"] if tel else []) + (["correo"] if email else [])
    p, nuevo = base.alta_externa(db, cfg.organizacion_id, nombre=d.nombre, tel=tel, email=email, ciudad=d.ciudad, materia=d.materia,
                                 descripcion=d.descripcion, canal=canal, campana=camp, entrada="formulario",
                                 origen={"utm": utm} if utm else None, consentimiento=canales, medio="formulario_web",
                                 preferencia=d.preferencia)
    auditar(db, None, "ld_formulario_recibido", "ld_prospecto", p.id, {"nuevo": nuevo, "campana_id": camp.id if camp else None},
            request, organizacion_id=cfg.organizacion_id)
    db.commit()
    return {"ok": True}


# ---------- otros sistemas (Zapier, Make, Google Ads, sitio web) ----------

def _google(datos: dict) -> dict:
    """Formato del webhook de formularios de clientes potenciales de Google Ads."""
    col = {(c.get("column_id") or "").upper(): c.get("string_value") for c in datos.get("user_column_data") or []}
    nombre = col.get("FULL_NAME") or " ".join(x for x in (col.get("FIRST_NAME"), col.get("LAST_NAME")) if x)
    otros = [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in col.items()
             if k not in ("FULL_NAME", "FIRST_NAME", "LAST_NAME", "PHONE_NUMBER", "EMAIL", "CITY") and v]
    return {"nombre": nombre, "telefono": col.get("PHONE_NUMBER"), "email": col.get("EMAIL"), "ciudad": col.get("CITY"),
            "descripcion": "\n".join(otros) or None, "canal": "google", "campana_externa": str(datos.get("campaign_id") or "") or None,
            "consentimiento": True, "prueba": bool(datos.get("is_test")), "id": datos.get("lead_id")}


@router.post("/api/leads-entrada", status_code=201)
async def entrada(request: Request, x_nomira_clave: str | None = Header(None), db: Session = Depends(get_db)):
    ip = ip_cliente(request) or "?"
    if _fallos_ip.excedida(ip):
        raise HTTPException(429, "Demasiados intentos.")
    try:
        datos = json.loads(await request.body() or b"{}")
    except ValueError:
        raise HTTPException(400, "JSON inválido.")
    if not isinstance(datos, dict):
        raise HTTPException(400, "Se esperaba un objeto JSON.")
    clave = x_nomira_clave or datos.get("google_key") or ""
    cfg = db.scalar(select(m.LdConfig).where(m.LdConfig.entrada_clave_hash == base.huella(clave))) if 10 <= len(clave) <= 100 else None
    if cfg is None:
        _fallos_ip.registrar(ip)
        raise HTTPException(401, "Clave inválida.")
    if not _org_activa(db, cfg.organizacion_id):
        raise HTTPException(410, "Nomira Leads no está activo para esta organización.")
    d = _google(datos) if "user_column_data" in datos else {
        "nombre": datos.get("nombre") or datos.get("name"), "telefono": datos.get("telefono") or datos.get("phone"),
        "email": datos.get("email") or datos.get("correo"), "ciudad": datos.get("ciudad") or datos.get("city"),
        "descripcion": datos.get("descripcion") or datos.get("mensaje") or datos.get("message"), "materia": datos.get("materia"),
        "canal": datos.get("canal") or _canal_de_utm(datos), "campana": datos.get("campana") or datos.get("utm_campaign"),
        "consentimiento": datos.get("consentimiento") is True, "id": datos.get("id")}
    if d.get("prueba"):
        return {"ok": True, "prueba": True}
    if d.get("id") and not primera_vez(db, f"entrada:{cfg.organizacion_id}:{str(d['id'])[:120]}"):
        return {"ok": True, "duplicado": True}
    tel = base.telefono(str(d["telefono"])) if d.get("telefono") else None
    email = (str(d.get("email") or "")).strip().lower()[:254] or None
    if not tel and not email:
        raise HTTPException(422, "Se requiere un teléfono o un correo.")
    camp = base.campana_por_codigo(db, cfg.organizacion_id, d.get("campana"))
    if not camp and d.get("campana_externa"):
        camp = db.scalar(select(m.LdCampana).where(m.LdCampana.organizacion_id == cfg.organizacion_id, m.LdCampana.id_externo == d["campana_externa"]))
    canal = d.get("canal") if d.get("canal") in cat.CANALES else None
    canales = ((["whatsapp", "llamada"] if tel else []) + (["correo"] if email else [])) if d.get("consentimiento") else None
    p, nuevo = base.alta_externa(db, cfg.organizacion_id, nombre=str(d.get("nombre") or "")[:200], tel=tel, email=email,
                                 ciudad=str(d.get("ciudad") or "")[:120] or None, materia=str(d.get("materia") or "")[:120] or None,
                                 descripcion=str(d.get("descripcion") or "")[:4000] or None, canal=canal or "otro", campana=camp,
                                 entrada="integracion", origen={"utm": _utm(datos)} if _utm(datos) else None, consentimiento=canales,
                                 medio="integracion")
    auditar(db, None, "ld_integracion_recibida", "ld_prospecto", p.id, {"nuevo": nuevo}, request, organizacion_id=cfg.organizacion_id)
    db.commit()
    return {"ok": True, "prospecto_id": p.id, "nuevo": nuevo}


# ---------- anuncios de clientes potenciales de Meta (Facebook e Instagram) ----------

@router.get("/api/meta/webhook")
def meta_verificar(modo: str | None = Query(None, alias="hub.mode"), token: str | None = Query(None, alias="hub.verify_token"),
                   reto: str | None = Query(None, alias="hub.challenge")):
    esperado = ajustes().whatsapp_verify_token
    if modo == "subscribe" and esperado and token and hmac.compare_digest(token, esperado):
        return Response(reto or "", media_type="text/plain")
    raise HTTPException(403, "Verificación inválida.")


@router.post("/api/meta/webhook")
async def meta_webhook(request: Request, db: Session = Depends(get_db)):
    cuerpo = await request.body()
    if not meta.firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "Firma inválida.")
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        raise HTTPException(400, "JSON inválido.")
    for ent in datos.get("entry", []):
        for cambio in ent.get("changes", []):
            if cambio.get("field") != "leadgen":
                continue
            v = cambio.get("value") or {}
            page, lead = str(v.get("page_id") or ent.get("id") or ""), str(v.get("leadgen_id") or "")
            cfg = db.scalar(select(m.LdConfig).where(m.LdConfig.meta_page_id == page)) if page else None
            if not cfg or not lead or not meta.meta_conectado(cfg) or not _org_activa(db, cfg.organizacion_id):
                continue
            if not primera_vez(db, f"leadgen:{lead}"):
                continue
            try:
                info = meta.obtener_lead(cfg, lead)
            except meta.MetaError as e:
                log.warning("No se pudo leer un formulario de Meta: %s", type(e).__name__)
                continue
            c = meta.campos_lead(info)
            canal = "instagram" if (info.get("platform") or "").lower() in ("ig", "instagram") else "facebook"
            camp = None
            if info.get("campaign_id"):
                camp = db.scalar(select(m.LdCampana).where(m.LdCampana.organizacion_id == cfg.organizacion_id,
                                                           m.LdCampana.id_externo == str(info["campaign_id"])))
                if camp is None:  # campaña nueva en Meta: se registra para atribuir los siguientes prospectos
                    camp = m.LdCampana(organizacion_id=cfg.organizacion_id, nombre=(info.get("campaign_name") or f"Campaña de Meta {info['campaign_id']}")[:160],
                                       canal=canal, codigo=base.codigo(), enlace_token=base.token_publico(), id_externo=str(info["campaign_id"]),
                                       activa=True, notas="Creada automáticamente al recibir un formulario de Meta.")
                    db.add(camp)
                    db.flush()
            tel = None
            try:
                tel = base.telefono(c["telefono"]) if c["telefono"] else None
            except HTTPException:
                pass
            email = (c["email"] or "").strip().lower() or None
            canales = (["whatsapp", "llamada"] if tel else []) + (["correo"] if email else [])
            base.alta_externa(db, cfg.organizacion_id, nombre=c["nombre"], tel=tel, email=email, ciudad=c["ciudad"], descripcion=c["descripcion"],
                              canal=canal, campana=camp, entrada="meta", consentimiento=canales, medio="formulario_meta",
                              origen={"anuncio": {k: info.get(k) for k in ("ad_name", "adset_name", "form_id") if info.get(k)}})
    db.commit()
    return {"ok": True}
