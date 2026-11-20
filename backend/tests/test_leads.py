"""Nomira Leads: independencia, alta rápida y borradores, bandeja, tablero y etapas, próximos pasos,
consentimiento, mensajes con revisión humana (sin fingir envíos), campañas por WhatsApp, correo y
redes sociales (formulario, otros sistemas, anuncios de Meta), contratación, reportes, exportación,
anonimización y aislamiento entre organizaciones."""
import hashlib
import hmac
import json
from datetime import date, timedelta

import pytest

from app import models as m
from app.config import ajustes
from app.services import correo
from app.services.leads import meta

from .test_evidencia import activar

HOY = date.today()


@pytest.fixture
def ld(org, plataforma):
    activar(plataforma, org, "leads")
    return org


def alta(o, **kw):
    datos = {"nombre": "Laura Prospecto Ficticia", "telefono": "55 1111 2222", "email": "laura@prospecto.test", "canal": "facebook",
             "materia": "Laboral", "ciudad": "CDMX", "descripcion": "La despidieron sin pagarle su finiquito.",
             "consentimiento": ["whatsapp", "llamada"], "consentimiento_medio": "verbal",
             "proxima": {"tipo": "llamada", "fecha": HOY.isoformat(), "descripcion": "Primera llamada"}, **kw}
    r = o.c.post("/api/leads/prospectos", headers=o.h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()


def _firmar(cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(b"secreto-app", cuerpo, hashlib.sha256).hexdigest()


def test_modulo_independiente_y_protegido(org, plataforma):
    assert org.c.get("/api/leads/bandeja", headers=org.h).status_code == 403  # no contratado
    activar(plataforma, org, "leads")
    # Funciona sin Nómina, Evidencia ni AFORE
    assert org.c.patch("/api/organizacion/modulos/nomina", headers=org.h, json={"activo": False}).status_code == 200
    p = alta(org)
    assert p["etapa"] == "Nuevo" and p["proxima"]["tipo"] == "llamada"
    assert org.c.get("/api/expedientes", headers=org.h).status_code == 403
    assert org.c.get("/api/afore/casos", headers=org.h).status_code == 403
    # el administrador puede desactivarlo sin perder datos
    assert org.c.patch("/api/organizacion/modulos/leads", headers=org.h, json={"activo": False}).status_code == 409  # último módulo activo
    org.c.patch("/api/organizacion/modulos/nomina", headers=org.h, json={"activo": True})
    org.c.patch("/api/organizacion/modulos/leads", headers=org.h, json={"activo": False})
    assert org.c.get(f"/api/leads/prospectos/{p['id']}", headers=org.h).status_code == 403
    org.c.patch("/api/organizacion/modulos/leads", headers=org.h, json={"activo": True})
    assert org.c.get(f"/api/leads/prospectos/{p['id']}", headers=org.h).json()["nombre"] == "Laura Prospecto Ficticia"


def test_alta_rapida_borrador_y_validaciones(ld):
    r = ld.c.post("/api/leads/prospectos", headers=ld.h, json={"nombre": "Sin datos"})
    assert r.status_code == 422 and "borrador" in r.json()["detail"]
    b = ld.c.post("/api/leads/prospectos", headers=ld.h, json={"nombre": "Pedro", "borrador": True}).json()
    assert b["borrador"] is True
    assert ld.c.patch(f"/api/leads/prospectos/{b['id']}", headers=ld.h, json={"borrador": False}).status_code == 422
    ld.c.patch(f"/api/leads/prospectos/{b['id']}", headers=ld.h, json={"telefono": "5533334444"})
    ld.c.post(f"/api/leads/prospectos/{b['id']}/acciones", headers=ld.h, json={"tipo": "llamada", "fecha": HOY.isoformat()})
    x = ld.c.patch(f"/api/leads/prospectos/{b['id']}", headers=ld.h, json={"borrador": False}).json()
    assert x["borrador"] is False and x["telefono"] == "525533334444"
    assert ld.c.post("/api/leads/prospectos", headers=ld.h, json={"nombre": "X", "telefono": "12", "borrador": True}).status_code == 422
    # El historial dice qué cambió, sin copiar el dato personal
    hist = " ".join(h["texto"] or "" for h in x["historial"])
    assert "Teléfono" in hist and "5533334444" not in hist


def test_bandeja_tablero_etapas_y_motivo(ld):
    p = alta(ld)
    b = ld.c.get("/api/leads/bandeja", headers=ld.h).json()
    assert b["grupos"]["nuevos"]["total"] == 1 and b["grupos"]["seguimientos"]["total"] == 0
    f = b["grupos"]["nuevos"]["filas"][0]
    assert f["nombre"] and f["necesita"] and f["responsable"] == "Admin 1" and f["proxima"]["tipo_texto"] == "Llamar"
    # Cada indicador abre su lista
    assert ld.c.post("/api/leads/prospectos/consulta", headers=ld.h, json={"vista": "nuevos"}).json()["total"] == 1
    cat = ld.c.get("/api/leads/catalogos", headers=ld.h).json()
    et = {e["clave"]: e["id"] for e in cat["etapas"]}
    # completar el paso registra la primera respuesta
    a = p["proxima"]["id"]
    x = ld.c.post(f"/api/leads/acciones/{a}/completar", headers=ld.h, json={"resultado": "Le interesa", "siguiente": {
        "tipo": "consulta", "fecha": (HOY + timedelta(days=2)).isoformat(), "hora": "10:30"}}).json()
    assert x["primera_respuesta_en"] and x["proxima"]["tipo"] == "consulta"
    x = ld.c.post(f"/api/leads/prospectos/{p['id']}/etapa", headers=ld.h, json={"etapa_id": et["consulta_agendada"], "nota": "Agendada"}).json()
    assert x["etapa"] == "Consulta agendada" and x["historial"][0]["usuario"] == "Admin 1"
    b = ld.c.get("/api/leads/bandeja", headers=ld.h).json()
    assert b["grupos"]["nuevos"]["total"] == 0 and b["grupos"]["citas"]["total"] == 1
    # no contratado exige motivo y cancela los recordatorios
    assert ld.c.post(f"/api/leads/prospectos/{p['id']}/etapa", headers=ld.h, json={"etapa_id": et["no_contratado"]}).status_code == 422
    assert ld.c.post(f"/api/leads/prospectos/{p['id']}/etapa", headers=ld.h, json={"etapa_id": et["contratado"]}).status_code == 422
    x = ld.c.post(f"/api/leads/prospectos/{p['id']}/etapa", headers=ld.h, json={"etapa_id": et["no_contratado"], "motivo": "Precio"}).json()
    assert x["motivo_perdida"] == "Precio" and x["proxima"] is None
    # etapas configurables
    nuevas = ld.c.post("/api/leads/etapas", headers=ld.h, json={"nombre": "Documentos recibidos"}).json()
    assert [e["nombre"] for e in nuevas][-3:] == ["Documentos recibidos", "Contratado", "No contratado"]
    abiertas = [e["id"] for e in nuevas if e["tipo"] == "abierta"]
    r = ld.c.post("/api/leads/etapas/orden", headers=ld.h, json={"ids": abiertas[::-1]}).json()
    assert r[0]["nombre"] == "Documentos recibidos" and r[-1]["nombre"] == "No contratado"
    ld.c.patch(f"/api/leads/etapas/{et['contactado']}", headers=ld.h, json={"nombre": "Primer contacto"})
    assert ld.c.patch(f"/api/leads/etapas/{et['contratado']}", headers=ld.h, json={"archivada": True}).status_code == 409
    t = ld.c.get("/api/leads/tablero", headers=ld.h).json()
    assert "Primer contacto" in [c["nombre"] for c in t["columnas"]]
    assert sum(c["total"] for c in t["columnas"]) == 1


def test_sin_actividad_y_seguimientos(ld, db):
    p = alta(ld, proxima={"tipo": "llamada", "fecha": (HOY - timedelta(days=1)).isoformat()})
    b = ld.c.get("/api/leads/bandeja", headers=ld.h).json()
    assert b["grupos"]["nuevos"]["total"] == 1  # todavía no se le responde
    ld.c.post(f"/api/leads/acciones/{p['proxima']['id']}/completar", headers=ld.h, json={})
    b = ld.c.get("/api/leads/bandeja", headers=ld.h).json()
    assert b["grupos"]["sin_actividad"]["total"] == 1  # respondido pero sin próximo paso
    ld.c.post(f"/api/leads/prospectos/{p['id']}/acciones", headers=ld.h, json={"tipo": "seguimiento", "fecha": (HOY - timedelta(days=3)).isoformat()})
    b = ld.c.get("/api/leads/bandeja", headers=ld.h).json()
    assert b["grupos"]["seguimientos"]["total"] == 1 and b["grupos"]["seguimientos"]["filas"][0]["proxima"]["vencida"] is True


def test_mensajes_sin_fingir_envios_y_revision_humana(ld, monkeypatch, db):
    p = alta(ld, consentimiento=[])
    # sin consentimiento ni integración: no se envía, se explica qué falta
    r = ld.c.post(f"/api/leads/prospectos/{p['id']}/mensajes", headers=ld.h, json={"canal": "whatsapp", "texto": "Hola"})
    assert r.status_code == 409 and len(r.json()["detail"]["faltantes"]) >= 2
    # registrar una respuesta enviada fuera de Nomira (enlace de WhatsApp) no la marca «enviada»
    x = ld.c.post(f"/api/leads/prospectos/{p['id']}/mensajes", headers=ld.h, json={"canal": "whatsapp", "texto": "Hola", "modo": "manual"}).json()
    assert x["mensajes"][-1]["estado"] == "manual" and x["primera_respuesta_en"]
    # con WhatsApp conectado: texto libre solo dentro de las 24 h siguientes a su último mensaje
    ld.c.post(f"/api/leads/prospectos/{p['id']}/consentimientos", headers=ld.h, json={"canal": "whatsapp", "medio": "verbal"})
    r = ld.c.put("/api/leads/config/whatsapp", headers=ld.h, json={"phone_number_id": "2223334", "numero": "+52 55 9999 0000",
                                                                    "token": "EAAG-token-secreto-de-prueba-123456", "plantilla": "primer_contacto"})
    assert r.status_code == 200 and "EAAG" not in r.text
    r = ld.c.post(f"/api/leads/prospectos/{p['id']}/mensajes", headers=ld.h, json={"canal": "whatsapp", "texto": "Hola"})
    assert r.status_code == 409 and "24 h" in " ".join(r.json()["detail"]["faltantes"])
    enviados = []
    monkeypatch.setattr(meta, "enviar_plantilla", lambda cfg, tel, nombre: enviados.append(("plantilla", tel, nombre)) or "wamid.P1")
    monkeypatch.setattr(meta, "enviar_texto", lambda cfg, tel, texto: enviados.append(("texto", tel, texto)) or "wamid.T1")
    x = ld.c.post(f"/api/leads/prospectos/{p['id']}/mensajes", headers=ld.h, json={"canal": "whatsapp", "modo": "plantilla"}).json()
    assert enviados == [("plantilla", "525511112222", "Laura")] and x["mensajes"][-1]["estado"] == "enviado"
    # error del proveedor: queda «falló», nunca «enviado»
    monkeypatch.setattr(meta, "enviar_plantilla", lambda *a: (_ for _ in ()).throw(meta.MetaError("plantilla pausada")))
    r = ld.c.post(f"/api/leads/prospectos/{p['id']}/mensajes", headers=ld.h, json={"canal": "whatsapp", "modo": "plantilla"})
    assert r.status_code == 502
    assert db.query(m.LdMensaje).filter_by(estado="fallido").count() == 1
    # correo: necesita consentimiento de correo
    monkeypatch.setattr(correo, "configurado", lambda: True)
    r = ld.c.post(f"/api/leads/prospectos/{p['id']}/mensajes", headers=ld.h, json={"canal": "correo", "texto": "Hola"})
    assert r.status_code == 409
    # pidió no ser contactado
    ld.c.patch(f"/api/leads/prospectos/{p['id']}", headers=ld.h, json={"preferencia_contacto": "ninguno"})
    r = ld.c.post(f"/api/leads/prospectos/{p['id']}/mensajes", headers=ld.h, json={"canal": "whatsapp", "modo": "plantilla"})
    assert "pidió no ser contactado" in " ".join(r.json()["detail"]["faltantes"])


def test_whatsapp_entrante_crea_atribuye_y_vincula(ld, plataforma, cliente, monkeypatch, db):
    monkeypatch.setattr(ajustes(), "whatsapp_app_secret", "secreto-app")
    ld.c.put("/api/leads/config/whatsapp", headers=ld.h, json={"phone_number_id": "2223334", "token": "EAAG-token-secreto-de-prueba-123456"})
    camp = ld.c.post("/api/leads/campanas", headers=ld.h, json={"nombre": "Anuncio despidos noviembre", "canal": "facebook", "inversion": "3000"}).json()

    def evento(**valor):
        cuerpo = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "2223334"}, **valor}}]}]}).encode()
        return cliente.post("/api/whatsapp/webhook", content=cuerpo, headers={"X-Hub-Signature-256": _firmar(cuerpo)})
    # número desconocido + código de campaña → prospecto nuevo atribuido a la campaña
    r = evento(contacts=[{"wa_id": "5215577778888", "profile": {"name": "Mario Ficticio"}}],
               messages=[{"id": "wamid.N1", "from": "5215577778888", "type": "text", "text": {"body": f"Hola, quiero información (ref: {camp['codigo']})"}}])
    assert r.status_code == 200
    evento(messages=[{"id": "wamid.N1", "from": "5215577778888", "type": "text", "text": {"body": "repetido"}}])  # idempotente
    p = db.query(m.LdProspecto).filter_by(nombre="Mario Ficticio").one()
    assert (p.canal, p.campana_id, p.entrada, p.telefono) == ("facebook", camp["id"], "whatsapp", "525577778888")
    assert db.query(m.LdMensaje).filter_by(prospecto_id=p.id).count() == 1
    # segundo mensaje: se vincula al mismo prospecto y aparece «por responder» tras el primer contacto
    ld.c.post(f"/api/leads/prospectos/{p.id}/mensajes", headers=ld.h, json={"canal": "whatsapp", "texto": "Le llamo", "modo": "manual"})
    evento(messages=[{"id": "wamid.N2", "from": "5215577778888", "type": "text", "text": {"body": "¿A qué hora?"}}])
    b = ld.c.get("/api/leads/bandeja", headers=ld.h).json()
    assert b["grupos"]["responder"]["total"] == 1
    # dentro de las 24 h ya puede responder con texto libre
    monkeypatch.setattr(meta, "enviar_texto", lambda cfg, tel, texto: "wamid.T9")
    x = ld.c.post(f"/api/leads/prospectos/{p.id}/mensajes", headers=ld.h, json={"canal": "whatsapp", "texto": "A las 5"}).json()
    assert x["mensajes"][-1]["estado"] == "enviado" and x["sin_responder"] == 0
    evento(statuses=[{"id": "wamid.T9", "status": "read"}])
    evento(statuses=[{"id": "wamid.T9", "status": "delivered"}])  # tarde: no retrocede
    db.expire_all()
    assert db.query(m.LdMensaje).filter_by(proveedor_id="wamid.T9").one().estado == "leido"
    # «BAJA» revoca el consentimiento de WhatsApp
    evento(messages=[{"id": "wamid.N3", "from": "5215577778888", "type": "text", "text": {"body": "BAJA"}}])
    assert ld.c.get(f"/api/leads/prospectos/{p.id}", headers=ld.h).json()["consiente"]["whatsapp"] is False


def test_mismo_numero_en_afore_y_leads(ld, plataforma, cliente, monkeypatch, db):
    """Si el despacho conecta el mismo número en ambos módulos, sus clientes AFORE siguen en AFORE."""
    monkeypatch.setattr(ajustes(), "whatsapp_app_secret", "secreto-app")
    activar(plataforma, ld, "afore")
    ld.c.put("/api/afore/config/whatsapp", headers=ld.h, json={"phone_number_id": "777888", "token": "EAAG-token-secreto-de-prueba-123456"})
    ld.c.put("/api/leads/config/whatsapp", headers=ld.h, json={"phone_number_id": "777888", "token": "EAAG-token-secreto-de-prueba-123456"})
    ld.c.post("/api/afore/clientes", headers=ld.h, json={"nombre": "Cliente Afore", "telefono": "5512345678"})

    def evento(n, tel):
        cuerpo = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "777888"},
                                                               "messages": [{"id": n, "from": tel, "type": "text", "text": {"body": "Hola"}}]}}]}]}).encode()
        cliente.post("/api/whatsapp/webhook", content=cuerpo, headers={"X-Hub-Signature-256": _firmar(cuerpo)})
    evento("w1", "5215512345678")
    evento("w2", "5215500001111")
    assert db.query(m.AfMensaje).filter_by(proveedor_id="w1").count() == 1
    assert db.query(m.LdMensaje).filter_by(proveedor_id="w2").count() == 1 and db.query(m.LdMensaje).filter_by(proveedor_id="w1").count() == 0


def test_formulario_publico_para_campanas_de_correo_y_redes(ld, cliente, db):
    camp = ld.c.post("/api/leads/campanas", headers=ld.h, json={"nombre": "Boletín de noviembre", "canal": "correo"}).json()
    token = camp["enlace_formulario"].split("#")[1]
    assert "/contacto#" in camp["enlace_formulario"] and camp["utm"].startswith("utm_source=correo")
    h = {"X-Enlace": token}
    info = cliente.post("/api/leads-publico/formulario/info", headers=h).json()
    assert info["despacho"] == "Org 1" and info["campana"] == "Boletín de noviembre" and "Laboral" in info["materias"]
    datos = {"nombre": "Ana Formulario", "telefono": "5544445555", "descripcion": "Pensión", "materia": "Familiar"}
    assert cliente.post("/api/leads-publico/formulario", headers=h, json=datos).status_code == 422  # sin autorización
    r = cliente.post("/api/leads-publico/formulario", headers=h, json={**datos, "acepta": True, "utm": {"utm_source": "newsletter"}})
    assert r.status_code == 201 and r.json() == {"ok": True}  # no devuelve datos
    p = db.query(m.LdProspecto).filter_by(nombre="Ana Formulario").one()
    assert (p.canal, p.campana_id, p.entrada) == ("correo", camp["id"], "formulario")
    cons = {c.canal: c.medio for c in db.query(m.LdConsentimiento).filter_by(prospecto_id=p.id)}
    assert cons == {"whatsapp": "formulario_web", "llamada": "formulario_web"}
    # si vuelve a escribir no se duplica: se agrega al historial
    cliente.post("/api/leads-publico/formulario", headers=h, json={**datos, "acepta": True, "descripcion": "Otra duda"})
    assert db.query(m.LdProspecto).filter_by(nombre="Ana Formulario").count() == 1
    # formulario general + utm de redes sociales → canal Instagram
    cfg = ld.c.get("/api/leads/config", headers=ld.h).json()
    tg = cfg["formulario"]["enlace"].split("#")[1]
    cliente.post("/api/leads-publico/formulario", headers={"X-Enlace": tg}, json={"nombre": "Beto Redes", "email": "beto@x.test", "acepta": True,
                                                                                 "utm": {"utm_source": "ig", "utm_medium": "social"}})
    b = db.query(m.LdProspecto).filter_by(nombre="Beto Redes").one()
    assert b.canal == "instagram" and b.origen_detalle == {"utm": {"utm_source": "ig", "utm_medium": "social"}}
    # campo trampa (robots) y enlaces inválidos o campañas terminadas
    cliente.post("/api/leads-publico/formulario", headers={"X-Enlace": tg}, json={"nombre": "Robot", "email": "r@x.test", "acepta": True, "sitio_web": "spam"})
    assert db.query(m.LdProspecto).filter_by(nombre="Robot").count() == 0
    assert cliente.post("/api/leads-publico/formulario/info", headers={"X-Enlace": "x" * 24}).status_code == 404
    ld.c.patch(f"/api/leads/campanas/{camp['id']}", headers=ld.h, json={"activa": False})
    assert cliente.post("/api/leads-publico/formulario/info", headers=h).status_code == 410
    ld.c.patch("/api/leads/config", headers=ld.h, json={"formulario_activo": False})
    assert cliente.post("/api/leads-publico/formulario/info", headers={"X-Enlace": tg}).status_code == 404


def test_entrada_de_otros_sistemas_y_google_ads(ld, cliente, db):
    assert cliente.post("/api/leads-entrada", json={"nombre": "X", "telefono": "5511112222"}).status_code == 401
    r = ld.c.post("/api/leads/config/entrada", headers=ld.h).json()
    clave = r["clave"]
    assert r["entrada"]["configurada"] and clave not in ld.c.get("/api/leads/config", headers=ld.h).text  # solo se muestra una vez
    camp = ld.c.post("/api/leads/campanas", headers=ld.h, json={"nombre": "TikTok jóvenes", "canal": "tiktok"}).json()
    r = cliente.post("/api/leads-entrada", headers={"X-Nomira-Clave": clave},
                     json={"name": "Zapier Lead", "phone": "5512121212", "campana": camp["codigo"], "consentimiento": True, "id": "zap-1"})
    assert r.status_code == 201 and r.json()["nuevo"]
    cliente.post("/api/leads-entrada", headers={"X-Nomira-Clave": clave}, json={"name": "Zapier Lead", "phone": "5512121212", "id": "zap-1"})
    p = db.query(m.LdProspecto).filter_by(nombre="Zapier Lead").one()
    assert (p.canal, p.campana_id, p.entrada) == ("tiktok", camp["id"], "integracion")
    assert db.query(m.LdActividad).filter_by(prospecto_id=p.id, tipo="solicitud").count() == 0  # el reintento con el mismo id se ignora
    # webhook de formularios de Google Ads (la clave va en google_key)
    g = {"google_key": clave, "lead_id": "g-1", "campaign_id": 987, "user_column_data": [
        {"column_id": "FULL_NAME", "string_value": "Gina Google"}, {"column_id": "EMAIL", "string_value": "gina@x.test"},
        {"column_id": "SERVICIO", "string_value": "Divorcio"}]}
    assert cliente.post("/api/leads-entrada", json=g).status_code == 201
    gp = db.query(m.LdProspecto).filter_by(nombre="Gina Google").one()
    assert gp.canal == "google" and "Divorcio" in gp.descripcion
    assert cliente.post("/api/leads-entrada", json={**g, "lead_id": "g-2", "is_test": True}).json()["prueba"] is True
    ld.c.delete("/api/leads/config/entrada", headers=ld.h)
    assert cliente.post("/api/leads-entrada", headers={"X-Nomira-Clave": clave}, json={"name": "Y", "phone": "5500000000"}).status_code == 401


def test_anuncios_de_facebook_e_instagram(ld, cliente, monkeypatch, db):
    r = ld.c.put("/api/leads/config/meta", headers=ld.h, json={"page_id": "11122233", "token": "EAAP-token-pagina-de-prueba-12345"})
    assert r.status_code == 409  # falta configurar el servidor: no se finge la conexión
    monkeypatch.setattr(ajustes(), "whatsapp_app_secret", "secreto-app")
    monkeypatch.setattr(ajustes(), "whatsapp_verify_token", "verifica-123")
    monkeypatch.setattr(meta, "suscribir_pagina", lambda page, token: "Despacho Ficticio")
    r = ld.c.put("/api/leads/config/meta", headers=ld.h, json={"page_id": "11122233", "token": "EAAP-token-pagina-de-prueba-12345"})
    assert r.status_code == 200 and r.json()["meta"]["pagina"] == "Despacho Ficticio" and "EAAP" not in r.text
    assert cliente.get("/api/meta/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verifica-123", "hub.challenge": "7"}).text == "7"
    monkeypatch.setattr(meta, "obtener_lead", lambda cfg, lid: {
        "platform": "ig", "campaign_id": "555", "campaign_name": "Pensiones IG", "ad_name": "Anuncio 1",
        "field_data": [{"name": "full_name", "values": ["Irma Instagram"]}, {"name": "phone_number", "values": ["+52 55 6767 6767"]},
                       {"name": "¿qué_necesitas?", "values": ["Revisar mi pensión"]}]})
    cuerpo = json.dumps({"object": "page", "entry": [{"id": "11122233", "changes": [{"field": "leadgen", "value": {"leadgen_id": "L1", "page_id": "11122233"}}]}]}).encode()
    assert cliente.post("/api/meta/webhook", content=cuerpo, headers={"X-Hub-Signature-256": "sha256=malo"}).status_code == 401
    cliente.post("/api/meta/webhook", content=cuerpo, headers={"X-Hub-Signature-256": _firmar(cuerpo)})
    cliente.post("/api/meta/webhook", content=cuerpo, headers={"X-Hub-Signature-256": _firmar(cuerpo)})  # Meta reintenta
    p = db.query(m.LdProspecto).filter_by(nombre="Irma Instagram").one()
    camp = db.get(m.LdCampana, p.campana_id)
    assert (p.canal, p.telefono, camp.nombre, camp.id_externo) == ("instagram", "525567676767", "Pensiones IG", "555")
    assert "Revisar mi pensión" in p.descripcion and db.query(m.LdProspecto).count() == 1


def test_contratar_reportes_y_costo_por_cliente(ld, plataforma, db):
    camp = ld.c.post("/api/leads/campanas", headers=ld.h, json={"nombre": "Google búsqueda", "canal": "google", "inversion": "4,500.00"}).json()
    p1 = alta(ld, campana_id=camp["id"], canal="otro")
    alta(ld, nombre="Otro Prospecto", telefono="5590909090", email=None, campana_id=camp["id"], canal="otro")
    p3 = alta(ld, nombre="Tercero", telefono="5580808080", email=None, canal="referido")
    assert ld.c.post(f"/api/leads/prospectos/{p1['id']}/contratar", headers=ld.h, json={"servicio": "Demanda laboral", "crear_en": "evidencia"}).status_code == 409
    activar(plataforma, ld, "evidencia")
    r = ld.c.post(f"/api/leads/prospectos/{p1['id']}/contratar", headers=ld.h, json={"servicio": "Demanda laboral", "crear_en": "evidencia", "referencia": "LAB-01"})
    assert r.status_code == 200, r.text
    x = r.json()
    assert x["etapa_tipo"] == "ganada" and x["destino"].startswith("/evidencia/") and x["proxima"] is None
    ev = db.get(m.EvAsunto, x["ev_asunto_id"])
    assert ev.cliente == "Laura Prospecto Ficticia" and ev.tipo_caso == "Laboral"  # sin capturar de nuevo
    et = {e["clave"]: e["id"] for e in ld.c.get("/api/leads/catalogos", headers=ld.h).json()["etapas"]}
    ld.c.post(f"/api/leads/prospectos/{p3['id']}/etapa", headers=ld.h, json={"etapa_id": et["no_contratado"], "motivo": "Fuera de especialidad"})
    rep = ld.c.get("/api/leads/reportes", headers=ld.h).json()
    g = next(c for c in rep["por_campana"] if c["campana_id"] == camp["id"])
    assert (g["recibidos"], g["contratados"], g["inversion"], g["costo_por_cliente"], g["costo_por_prospecto"]) == (2, 1, "4500.00", "4500.00", "2250.00")
    assert {c["canal"]: c["recibidos"] for c in rep["por_canal"]} == {"google": 2, "referido": 1}
    assert rep["motivos_perdida"] == [{"motivo": "Fuera de especialidad", "total": 1}]
    assert rep["total"]["contratados"] == 1 and rep["aviso_origen"] is None
    # vista de contratados en la bandeja
    assert ld.c.get("/api/leads/bandeja", headers=ld.h).json()["grupos"]["contratados"]["total"] == 1


def test_permisos_datos_exportar_anonimizar(ld, org2, db):
    p = alta(ld)
    consulta = ld.usuario("consulta", "consulta@org1.test")
    analista = ld.usuario("analista", "analista@org1.test")
    v = ld.c.get(f"/api/leads/prospectos/{p['id']}", headers=consulta).json()
    assert v["telefono"].startswith("••••") and "laura@" not in json.dumps(v)
    assert ld.c.post("/api/leads/prospectos", headers=consulta, json={"nombre": "X", "borrador": True}).status_code == 403
    assert ld.c.get("/api/leads/exportar", headers=consulta).status_code == 403
    # el analista exporta solo lo suyo; el administrador todo
    r = ld.c.get("/api/leads/exportar?formato=csv", headers=analista)
    assert r.status_code == 200 and "Laura" not in r.text
    r = ld.c.get("/api/leads/exportar?formato=csv", headers=ld.h)
    assert "Laura Prospecto Ficticia" in r.text and "525511112222" in r.text
    assert ld.c.get("/api/leads/exportar?formato=xlsx", headers=ld.h).headers["content-type"].startswith("application/vnd.openxml")
    # protección de fórmulas en CSV
    alta(ld, nombre="=HYPERLINK(1)", telefono="5500001111", email=None)
    assert "'=HYPERLINK" in ld.c.get("/api/leads/exportar?formato=csv", headers=ld.h).text
    # aislamiento entre organizaciones
    assert org2.c.get(f"/api/leads/prospectos/{p['id']}", headers=org2.h).status_code in (403, 404)
    # cambios de responsable quedan registrados
    uid = ld.c.get("/api/leads/catalogos", headers=ld.h).json()["usuarios"]
    an = next(x["id"] for x in uid if x["nombre"] == "Analista")
    ld.c.patch(f"/api/leads/prospectos/{p['id']}", headers=ld.h, json={"responsable_id": an})
    assert db.query(m.Auditoria).filter_by(accion="ld_responsable_cambiado").count() == 1
    # anonimizar: conserva estadística, borra datos personales
    assert ld.c.post(f"/api/leads/prospectos/{p['id']}/anonimizar", headers=analista).status_code == 403
    assert ld.c.post(f"/api/leads/prospectos/{p['id']}/anonimizar", headers=ld.h).status_code == 200
    db.expire_all()
    x = db.get(m.LdProspecto, p["id"])
    assert (x.telefono, x.email, x.descripcion) == (None, None, None) and x.canal == "facebook" and x.nombre.startswith("Prospecto anonimizado")
    assert ld.c.patch(f"/api/leads/prospectos/{p['id']}", headers=ld.h, json={"nombre": "Otro"}).status_code == 409
    assert ld.c.get("/api/leads/reportes", headers=ld.h).json()["total"]["recibidos"] == 2
    assert ld.c.delete(f"/api/leads/prospectos/{p['id']}", headers=ld.h).status_code == 200
    assert db.query(m.LdProspecto).filter_by(id=p["id"]).count() == 0


def test_eliminar_organizacion_borra_leads_y_academia(ld, plataforma, db):
    alta(ld)
    activar(plataforma, ld, "academia")
    cid = ld.c.post("/api/academia/admin/cursos", headers=ld.h, json={"titulo": "Curso interno", "materia": "Procesos"}).json()["id"]
    r = plataforma.c.post(f"/api/plataforma/clientes/{ld.org_id}/eliminar", headers=plataforma.h, json={"confirmar_nombre": "Org 1"})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.query(m.LdProspecto).count() == 0 and db.get(m.AcCurso, cid) is None
    assert db.query(m.AcCurso).filter(m.AcCurso.organizacion_id.is_(None)).count() >= 1  # los cursos de Nomira se conservan


def test_aviso_de_privacidad_del_despacho(ld, cliente, db):
    assert ld.c.get("/api/leads/catalogos", headers=ld.h).json()["falta_aviso_privacidad"] is True
    cfg = ld.c.get("/api/leads/config", headers=ld.h).json()
    token = cfg["formulario"]["enlace"].split("#")[1]
    assert cliente.post("/api/leads-publico/formulario/info", headers={"X-Enlace": token}).json()["aviso_privacidad_url"] is None
    # solo direcciones https completas; nada de javascript: ni texto suelto
    for malo in ("javascript:alert(1)", "http://despacho.test/aviso", "aviso de privacidad", "https://sin-punto"):
        assert ld.c.patch("/api/leads/config", headers=ld.h, json={"aviso_privacidad_url": malo}).status_code == 422, malo
    consulta = ld.usuario("consulta", "consulta.aviso@org1.test")
    assert ld.c.patch("/api/leads/config", headers=consulta, json={"aviso_privacidad_url": "https://despacho.test/aviso"}).status_code == 403
    r = ld.c.patch("/api/leads/config", headers=ld.h, json={"aviso_privacidad_url": " https://despacho.test/aviso-de-privacidad "})
    assert r.status_code == 200 and r.json()["aviso_privacidad_url"] == "https://despacho.test/aviso-de-privacidad"
    assert cliente.post("/api/leads-publico/formulario/info", headers={"X-Enlace": token}).json()["aviso_privacidad_url"] == "https://despacho.test/aviso-de-privacidad"
    assert ld.c.get("/api/leads/catalogos", headers=ld.h).json()["falta_aviso_privacidad"] is False
    # la bitácora registra qué campo cambió, no el valor
    ult = db.query(m.Auditoria).filter_by(accion="ld_config_actualizada").order_by(m.Auditoria.id.desc()).first()
    assert "despacho.test" not in json.dumps(ult.detalle, default=str)
    assert ld.c.patch("/api/leads/config", headers=ld.h, json={"aviso_privacidad_url": ""}).json()["aviso_privacidad_url"] is None
