"""Nomira AFORE: independencia, alta guiada, checklist, seguimiento, portal del cliente, mensajes con
consentimiento y aprobación, WhatsApp oficial (sin fingir envíos), CURP/NSS protegidos y aislamiento."""
import hashlib
import hmac
import json
import re
from datetime import date, timedelta

import pytest

from app import models as m
from app.config import ajustes
from app.services import correo
from app.services.afore import whatsapp
from app.services.afore.identificadores import revisar_curp, revisar_nss

from .test_evidencia import CONTRATO, activar

CURP = "HEGG560427MVZRRL04"  # ejemplo público de RENAPO
NSS = "12345678903"


@pytest.fixture
def af(org, plataforma):
    activar(plataforma, org, "afore")
    return org


@pytest.fixture
def buzon(monkeypatch):
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto: enviados.append({"para": dest, "asunto": asunto, "texto": texto}))
    monkeypatch.setattr(ajustes(), "url_publica", "https://nomirasoft.com")
    return enviados


def alta(af, **kw):
    r = af.c.post("/api/afore/clientes", headers=af.h, json={"nombre": "Rosa Ficticia López", "telefono": "55 1234 5678",
                                                             "email": "rosa@cliente.test", "curp": CURP, "nss": NSS, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def caso(af, cid, **kw):
    r = af.c.post("/api/afore/casos", headers=af.h, json={"cliente_id": cid, "tipo_problema": "inconformidad_saldo", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_modulo_independiente_y_protegido(org, plataforma, db):
    assert org.c.get("/api/afore/casos", headers=org.h).status_code == 403  # no contratado
    activar(plataforma, org, "afore")
    assert org.c.get("/api/afore/casos", headers=org.h).status_code == 200
    # Funciona sin Nómina ni Evidencia
    org.c.patch("/api/organizacion/modulos/nomina", headers=org.h, json={"activo": False})
    assert org.c.get("/api/afore/catalogos", headers=org.h).json()["evidencia_activa"] is False
    c = alta(org)
    assert caso(org, c["id"])["estado"] == "borrador"
    assert org.c.get("/api/expedientes", headers=org.h).status_code == 403
    org.c.patch("/api/organizacion/modulos/nomina", headers=org.h, json={"activo": True})
    activar(plataforma, org, "afore", contratado=False)
    assert org.c.get("/api/afore/casos", headers=org.h).status_code == 403
    assert db.query(m.AfCaso).count() == 1  # desactivar no borra


def test_curp_y_nss_protegidos(af, db):
    assert revisar_curp(CURP)["valida_formato"] and not revisar_curp("HEGG560427MVZRRL05")["valida_formato"]
    assert revisar_nss(NSS)["valida_formato"] and not revisar_nss("12345678901")["valida_formato"]
    r = alta(af)
    assert r["curp"] == "HEGG••••••••••••04" and r["nss"] == "•••••••8903" and r["revision"]["curp"]["valida_formato"]
    assert "revisión local" in r["revision"]["curp"]["detalle"]
    fila = db.query(m.AfCliente).one()
    assert CURP not in (fila.curp_cifrado or "") and NSS not in (fila.nss_cifrado or "")  # cifrados en la base
    lista = af.c.get("/api/afore/clientes", headers=af.h).json()
    assert CURP not in json.dumps(lista) and "5512345678" not in json.dumps(lista)
    v = af.c.post(f"/api/afore/clientes/{r['id']}/revelar", headers=af.h, json={"campo": "curp"}).json()
    assert v["valor"] == CURP
    acc = db.query(m.Auditoria).filter_by(accion="af_dato_sensible_mostrado").one()
    assert CURP not in json.dumps(acc.detalle) and not any(CURP in json.dumps(a.detalle or {}) for a in db.query(m.Auditoria))
    consulta = af.c.get("/api/afore/clientes", headers=af.usuario("consulta", "c@org1.test"))
    assert consulta.status_code == 200
    # Validación oficial: no configurada, no se finge
    cs = caso(af, r["id"])
    x = af.c.post(f"/api/afore/casos/{cs['id']}/curp-oficial", headers=af.h, json={"finalidad": "Integrar expediente", "consentimiento": True}).json()
    assert x["oficial"] is False and "no configurada" in x["mensaje"] and x["revision_local"]["valida_formato"]
    assert af.c.post(f"/api/afore/casos/{cs['id']}/curp-oficial", headers=af.h, json={"finalidad": "Integrar", "consentimiento": False}).status_code == 422
    assert db.query(m.AfConsultaCurp).one().resultado == "no_configurado"


def test_alta_guiada_checklist_y_revision(af, db):
    cl = alta(af, curp=None, nss=None)
    c = caso(af, cl["id"], tipo_problema="beneficiario_fallecimiento", datos={
        "afore": {"valor": "Coppel"}, "monto_cliente": {"valor": "150,000.50"}, "monto_afore": {"estado": "no_lo_se"},
        "institucion": {"estado": "pendiente"}, "regimen": {"estado": "no_aplica"}}, borrador=True)
    assert c["datos"]["monto_cliente"] == {"valor": "150000.50", "estado": "informado"}
    assert c["datos"]["monto_afore"] == {"valor": None, "estado": "no_lo_se"}
    d = af.c.get(f"/api/afore/casos/{c['id']}", headers=af.h).json()
    nombres = [r["nombre"] for r in d["requisitos"]]
    assert "Acta de defunción del titular" in nombres and all(r["estado"] == "no_solicitado" for r in d["requisitos"])
    # El checklist se edita por caso y por despacho
    r = af.c.post(f"/api/afore/casos/{c['id']}/requisitos", headers=af.h, json={"nombre": "Carta de la AFORE"}).json()
    assert af.c.patch(f"/api/afore/requisitos/{r['id']}", headers=af.h, json={"estado": "no_aplica"}).json()["estado_texto"] == "No aplica"
    af.c.patch("/api/afore/config", headers=af.h, json={"checklists": {"separacion_cuentas": ["Solo esto"]}, "tipos_extra": ["Devolución IMSS"]})
    cat = af.c.get("/api/afore/catalogos", headers=af.h).json()
    assert cat["checklists"]["separacion_cuentas"] == ["Solo esto"] and "Devolución IMSS" in cat["tipos"].values()
    # Revisión del expediente: faltantes, sin probabilidades
    rv = af.c.get(f"/api/afore/casos/{c['id']}/revision", headers=af.h).json()
    assert any("CURP o NSS" in x for x in rv["faltan_datos"]) and any("fallecimiento" in x for x in rv["faltan_datos"])
    assert any("Acta de defunción" in x for x in rv["faltan_documentos"]) and not rv["listo_para_avanzar"]
    assert "probabilidad" in rv["progreso"]["explicacion"] and rv["progreso"]["porcentaje_recibidos"] == 0
    assert any("Monto que el cliente" in x and "no verificado" in x for x in rv["revision_abogado"])
    # Posible inconsistencia entre lo capturado de un documento y lo registrado
    doc = af.c.post(f"/api/afore/casos/{c['id']}/documentos", headers=af.h, files={"archivo": ("acta.pdf", CONTRATO, "application/pdf")}).json()
    af.c.patch(f"/api/afore/documentos/{doc['id']}", headers=af.h, json={"datos_capturados": {"nombre": "Rosa Ficticia Lopes"}})
    rv = af.c.get(f"/api/afore/casos/{c['id']}/revision", headers=af.h).json()
    assert any(x.startswith("Posible inconsistencia: el nombre") for x in rv["inconsistencias"])
    # Abrir el caso (de borrador a en atención)
    assert af.c.patch(f"/api/afore/casos/{c['id']}", headers=af.h, json={"estado": "abierto"}).json()["estado_texto"] == "En atención"


def test_seguimiento_folios_plazos_y_resumen(af, db):
    cl = alta(af)
    c = caso(af, cl["id"], borrador=False)
    hoy = date.today()
    s = af.c.post(f"/api/afore/casos/{c['id']}/actividades", headers=af.h, json={
        "tipo": "solicitud_enviada", "fecha": (hoy - timedelta(days=12)).isoformat(), "institucion": "Coppel", "canal": "Sucursal"}).json()
    assert af.c.get(f"/api/afore/casos/{c['id']}", headers=af.h).json()["caso"]["estado"] == "esperando"
    res = af.c.get("/api/afore/resumen", headers=af.h).json()
    assert [x["dias"] for x in res["esperando_respuesta"]] == [12] and res["sin_siguiente_actividad"][0]["caso_id"] == c["id"]
    rv = af.c.get(f"/api/afore/casos/{c['id']}/revision", headers=af.h).json()
    assert any("sin folio" in x for x in rv["folios_pendientes"])
    af.c.patch(f"/api/afore/actividades/{s['id']}", headers=af.h, json={"tipo": "solicitud_enviada", "fecha": s["fecha"], "folio": "F-123"})
    act = af.c.get(f"/api/afore/casos/{c['id']}", headers=af.h).json()["actividades"][0]
    assert act["folio"] == "F-123" and act["modificado_por"] == "Admin 1"
    af.c.post(f"/api/afore/casos/{c['id']}/actividades", headers=af.h, json={"tipo": "respuesta_recibida", "fecha": hoy.isoformat(), "responde_a_id": s["id"]})
    res = af.c.get("/api/afore/resumen", headers=af.h).json()
    assert res["esperando_respuesta"] == [] and len(res["respuestas_recientes"]) == 1
    # Plazos: el legal exige fuente y confirmación; ninguno viene de fábrica
    assert af.c.post(f"/api/afore/casos/{c['id']}/plazos", headers=af.h, json={"tipo": "legal_confirmado", "descripcion": "Respuesta", "fecha": hoy.isoformat()}).status_code == 422
    p = af.c.post(f"/api/afore/casos/{c['id']}/plazos", headers=af.h, json={"tipo": "estimado", "descripcion": "Respuesta de la AFORE",
                                                                            "fecha": (hoy + timedelta(days=2)).isoformat(), "regla": "Regla del despacho"}).json()
    assert p["tipo_texto"].startswith("Fecha estimada") and p["confirmado_por"] is None
    p = af.c.post(f"/api/afore/plazos/{p['id']}", headers=af.h, json={"accion": "confirmar_legal", "fuente": "Oficio de la AFORE"}).json()
    assert p["tipo"] == "legal_confirmado" and p["confirmado_por"] == "Admin 1"
    assert af.c.get("/api/afore/resumen", headers=af.h).json()["seguimientos"][0]["descripcion"] == "Respuesta de la AFORE"
    # Localización de AFORE: flujo guiado al sitio oficial, sin automatizar
    r = af.c.post(f"/api/afore/casos/{c['id']}/localizacion", headers=af.h, json={}).json()
    assert r["aforeweb"].startswith("https://www.aforeweb.com.mx")
    req = next(x for x in af.c.get(f"/api/afore/casos/{c['id']}", headers=af.h).json()["requisitos"] if "Localiza" in x["nombre"])
    assert req["estado"] == "solicitado"
    hist = af.c.get(f"/api/afore/casos/{c['id']}/historial", headers=af.h).json()
    assert {"af_actividad_registrada", "af_actividad_modificada", "af_plazo_registrado", "af_localizacion_registrada"} <= {h["accion"] for h in hist}


def test_mensajes_requieren_consentimiento_y_aprobacion_y_nunca_se_fingen(af, buzon, db):
    cl = alta(af, preferencia_contacto="whatsapp")
    c = caso(af, cl["id"], borrador=False)
    # Sin consentimiento: no se genera nada automáticamente
    assert db.query(m.AfMensaje).count() == 0
    af.c.post(f"/api/afore/clientes/{cl['id']}/consentimientos", headers=af.h, json={"canal": "whatsapp", "medio": "escrito"})
    req = af.c.get(f"/api/afore/casos/{c['id']}", headers=af.h).json()["requisitos"][0]
    af.c.patch(f"/api/afore/requisitos/{req['id']}", headers=af.h, json={"estado": "solicitado"})
    x = db.query(m.AfMensaje).one()
    # WhatsApp sin integración ni plantilla aprobada: borrador con el motivo, nunca «enviado»
    assert x.estado == "borrador" and "WhatsApp no está conectado" in x.motivo and "aprobada por Meta" in x.motivo
    assert "[enlace seguro al portal]" in x.texto and CURP not in x.texto and "Rosa" in x.texto
    r = af.c.post(f"/api/afore/mensajes/{x.id}/aprobar", headers=af.h).json()
    assert r["estado"] == "borrador" and r["enviado_en"] is None
    # Con correo (consentido) sí sale, pero solo cuando el abogado aprueba
    af.c.post(f"/api/afore/clientes/{cl['id']}/consentimientos", headers=af.h, json={"canal": "correo"})
    m2 = af.c.post(f"/api/afore/casos/{c['id']}/mensajes", headers=af.h, json={"plantilla": "actualizacion_portal", "canal": "correo"}).json()
    assert m2["estado"] == "esperando_aprobacion" and buzon == []
    analista = af.usuario("analista", "ana@org1.test")
    assert af.c.post(f"/api/afore/mensajes/{m2['id']}/aprobar", headers=analista).status_code == 403  # no es responsable
    r = af.c.post(f"/api/afore/mensajes/{m2['id']}/aprobar", headers=af.h).json()
    assert r["estado"] == "enviado" and r["aprobado_por"] == "Admin 1" and len(buzon) == 1
    enlace = re.search(r"https://nomirasoft.com/portal#(\S+)", buzon[0]["texto"])
    assert enlace and enlace[1] not in r["texto"]  # el token no se guarda en el mensaje
    # Plantillas sin datos sensibles
    assert af.c.patch("/api/afore/plantillas/recordatorio", headers=af.h, json={"texto": "Hola {nombre}, tu NSS 12345678903"}).status_code == 422
    assert af.c.patch("/api/afore/plantillas/recordatorio", headers=af.h, json={"texto": "Hola {nombre}, tu saldo es $5,000"}).status_code == 422
    assert af.c.patch("/api/afore/plantillas/recordatorio", headers=af.h, json={"texto": "Hola {nombre}, tu CURP es {curp}"}).status_code == 422
    # Revocar el consentimiento deja los nuevos mensajes como borrador
    cons = next(k for k in af.c.get(f"/api/afore/clientes/{cl['id']}", headers=af.h).json()["consentimientos"] if k["canal"] == "correo")
    af.c.post(f"/api/afore/consentimientos/{cons['id']}/revocar", headers=af.h)
    m3 = af.c.post(f"/api/afore/casos/{c['id']}/mensajes", headers=af.h, json={"plantilla": "recordatorio", "canal": "correo"}).json()
    assert m3["estado"] == "borrador" and "consentimiento" in m3["motivo"]


def _firmar(cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(b"secreto-app", cuerpo, hashlib.sha256).hexdigest()


def test_whatsapp_oficial_envio_webhook_idempotente_y_por_asignar(af, monkeypatch, cliente, db):
    http = cliente
    monkeypatch.setattr(ajustes(), "whatsapp_app_secret", "secreto-app")
    monkeypatch.setattr(ajustes(), "whatsapp_verify_token", "verifica-123")
    monkeypatch.setattr(ajustes(), "url_publica", "https://nomirasoft.com")
    cl = alta(af, preferencia_contacto="whatsapp")
    c = caso(af, cl["id"], borrador=False)
    af.c.post(f"/api/afore/clientes/{cl['id']}/consentimientos", headers=af.h, json={"canal": "whatsapp"})
    r = af.c.put("/api/afore/config/whatsapp", headers=af.h, json={"phone_number_id": "1098765", "numero": "+52 55 0000 0000",
                                                                   "token": "EAAG-token-secreto-de-prueba-123456"})
    assert r.status_code == 200 and "EAAG" not in r.text and r.json()["whatsapp"]["token"] == "guardado (cifrado)"
    af.c.patch("/api/afore/plantillas/actualizacion_portal", headers=af.h, json={"wa_nombre": "actualizacion_tramite", "wa_aprobada": True})
    llamadas = []

    def falso(cfg, tel, nombre, idioma, params):
        llamadas.append((tel, nombre, params))
        return "wamid.ABC"
    monkeypatch.setattr(whatsapp, "enviar_plantilla", falso)
    x = af.c.post(f"/api/afore/casos/{c['id']}/publicar", headers=af.h, json={
        "portal_visible": True, "estado_publico": "Se presentó la solicitud", "notificar": True}).json()["mensaje"]
    assert x["estado"] == "esperando_aprobacion" and llamadas == []  # por omisión requiere aprobación
    x = af.c.post(f"/api/afore/mensajes/{x['id']}/aprobar", headers=af.h).json()
    assert x["estado"] == "enviado" and llamadas[0][0] == "525512345678" and llamadas[0][2][0] == "Rosa"
    assert llamadas[0][2][1].startswith("https://nomirasoft.com/portal#")
    # Webhook: verificación, firma, estados en orden, idempotencia
    assert http.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verifica-123", "hub.challenge": "42"}).text == "42"
    assert http.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "otro", "hub.challenge": "42"}).status_code == 403

    def evento(**valor):
        cuerpo = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "1098765"}, **valor}}]}]}).encode()
        return http.post("/api/whatsapp/webhook", content=cuerpo, headers={"X-Hub-Signature-256": _firmar(cuerpo), "Content-Type": "application/json"})
    assert http.post("/api/whatsapp/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=malo"}).status_code == 401
    evento(statuses=[{"id": "wamid.ABC", "status": "read"}])
    evento(statuses=[{"id": "wamid.ABC", "status": "delivered"}])  # llega tarde: no retrocede
    evento(statuses=[{"id": "wamid.ABC", "status": "read"}])  # repetido: se ignora
    msj = db.query(m.AfMensaje).filter_by(proveedor_id="wamid.ABC").one()
    db.refresh(msj)
    assert msj.estado == "leido" and msj.leido_en and msj.entregado_en
    # Entrantes: se asocian si hay certeza; si no, quedan «Por asignar»; nunca cambian el caso
    estado_antes = db.get(m.AfCaso, c["id"]).estado
    evento(messages=[{"id": "wamid.IN1", "from": "5215512345678", "type": "text", "text": {"body": "Ya mandé mi INE"}}])
    evento(messages=[{"id": "wamid.IN1", "from": "5215512345678", "type": "text", "text": {"body": "Ya mandé mi INE"}}])
    evento(messages=[{"id": "wamid.IN2", "from": "5219999999999", "type": "text", "text": {"body": "Hola"}}])
    entrantes = {x.proveedor_id: x for x in db.query(m.AfMensaje).filter_by(direccion="entrante")}
    assert set(entrantes) == {"wamid.IN1", "wamid.IN2"}
    assert (entrantes["wamid.IN1"].estado, entrantes["wamid.IN1"].caso_id) == ("recibido", c["id"])
    assert entrantes["wamid.IN2"].estado == "por_asignar" and entrantes["wamid.IN2"].cliente_id is None
    db.expire_all()
    assert db.get(m.AfCaso, c["id"]).estado == estado_antes
    r = af.c.post(f"/api/afore/mensajes/{entrantes['wamid.IN2'].id}/asignar", headers=af.h, json={"cliente_id": cl["id"], "caso_id": c["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "recibido"
    # «BAJA» revoca el consentimiento de WhatsApp
    evento(messages=[{"id": "wamid.IN3", "from": "5215512345678", "type": "text", "text": {"body": "Baja"}}])
    assert af.c.get(f"/api/afore/clientes/{cl['id']}", headers=af.h).json()["consiente"]["whatsapp"] is False


def test_portal_del_cliente_solo_ve_lo_autorizado(af, buzon, cliente, db):
    http = cliente
    cl = alta(af)
    c = caso(af, cl["id"], borrador=False, resumen_interno="NOTA PRIVADA: estrategia")
    d = af.c.get(f"/api/afore/casos/{c['id']}", headers=af.h).json()
    pedido, oculto = d["requisitos"][0], d["requisitos"][1]
    af.c.patch(f"/api/afore/requisitos/{pedido['id']}", headers=af.h, json={"estado": "solicitado", "nota": "interna secreta"})
    af.c.patch(f"/api/afore/requisitos/{oculto['id']}", headers=af.h, json={"estado": "solicitado", "visible_cliente": False})
    af.c.post(f"/api/afore/casos/{c['id']}/documentos", headers=af.h, files={"archivo": ("interno.pdf", CONTRATO, "application/pdf")})
    acc = af.c.post(f"/api/afore/clientes/{cl['id']}/acceso", headers=af.h, json={"dias": 7, "requiere_codigo": True}).json()
    token = acc["enlace"].split("#")[1]
    H = {"X-Enlace": token}
    e = http.post("/api/portal-afore/estado", headers=H).json()
    assert e["verificado"] is False and "casos" not in e
    http.post("/api/portal-afore/codigo", headers=H)
    codigo = re.search(r"(\d{6})", buzon[-1]["asunto"])[1]
    HS = {**H, "X-Sesion": http.post("/api/portal-afore/verificar", headers=H, json={"codigo": codigo}).json()["sesion"]}
    e = http.post("/api/portal-afore/estado", headers=HS).json()
    assert e["casos"] == []  # el despacho aún no publica el caso
    af.c.post(f"/api/afore/casos/{c['id']}/publicar", headers=af.h, json={"portal_visible": True, "estado_publico": "Revisando su documentación",
                                                                          "siguiente_paso_publico": "Envíe su identificación"})
    e = http.post("/api/portal-afore/estado", headers=HS).json()
    texto = json.dumps(e, ensure_ascii=False)
    assert e["casos"][0]["estado"] == "Revisando su documentación" and [x["nombre"] for x in e["casos"][0]["documentos_pedidos"]] == [pedido["nombre"]]
    for secreto in ("NOTA PRIVADA", "interna secreta", "interno.pdf", CURP, NSS, oculto["nombre"]):
        assert secreto not in texto, secreto
    r = http.post("/api/portal-afore/documentos", headers=HS, data={"requisito_id": pedido["id"]},
                  files={"archivo": ("ine.pdf", CONTRATO, "application/pdf")})
    assert r.status_code == 201
    assert http.post("/api/portal-afore/documentos", headers=HS, data={"requisito_id": oculto["id"]},
                     files={"archivo": ("x.pdf", CONTRATO, "application/pdf")}).status_code == 404
    doc = next(x for x in af.c.get(f"/api/afore/casos/{c['id']}", headers=af.h).json()["documentos"] if x["origen"] == "cliente")
    assert af.c.get("/api/afore/resumen", headers=af.h).json()["documentos_por_revisar"]
    af.c.patch(f"/api/afore/documentos/{doc['id']}", headers=af.h, json={"confirmar_recepcion": True, "estado": "aceptado"})
    e = http.post("/api/portal-afore/estado", headers=HS).json()
    propio = next(x for x in e["casos"][0]["documentos"] if x["enviado_por_usted"])
    assert propio["recepcion_confirmada_en"] and e["casos"][0]["documentos_pedidos"][0]["estado"] == "Recibido y revisado"
    # Preferencias: el cliente revoca o da su consentimiento
    http.post("/api/portal-afore/preferencias", headers=HS, json={"correo": True, "whatsapp": False})
    assert af.c.get(f"/api/afore/clientes/{cl['id']}", headers=af.h).json()["consiente"] == {"whatsapp": False, "correo": True}
    http.post("/api/portal-afore/preferencias", headers=HS, json={"correo": False})
    cons = af.c.get(f"/api/afore/clientes/{cl['id']}", headers=af.h).json()["consentimientos"]
    assert cons[0]["revocado_medio"] == "portal"
    # Revocar el acceso lo inutiliza
    aid = af.c.get(f"/api/afore/clientes/{cl['id']}", headers=af.h).json()["accesos"][0]["id"]
    af.c.post(f"/api/afore/accesos/{aid}/revocar", headers=af.h)
    assert http.post("/api/portal-afore/estado", headers=HS).status_code == 410


def test_aislamiento_casos_restringidos_y_roles(af, org2, plataforma, db):
    cl = alta(af)
    c = caso(af, cl["id"], restringido=True)
    abierto = caso(af, cl["id"])
    ana = af.usuario("analista", "ana@org1.test")
    ids = [x["id"] for x in af.c.get("/api/afore/casos", headers=ana).json()]
    assert ids == [abierto["id"]] and af.c.get(f"/api/afore/casos/{c['id']}", headers=ana).status_code == 404
    con = af.usuario("consulta", "con@org1.test")
    assert af.c.post("/api/afore/clientes", headers=con, json={"nombre": "X Y"}).status_code == 403
    assert af.c.post(f"/api/afore/clientes/{cl['id']}/revelar", headers=con, json={"campo": "curp"}).status_code == 403
    activar(plataforma, org2, "afore")
    for ruta in (f"/api/afore/casos/{abierto['id']}", f"/api/afore/clientes/{cl['id']}", f"/api/afore/casos/{abierto['id']}/revision"):
        assert org2.c.get(ruta, headers=org2.h).status_code == 404
    assert org2.c.get("/api/afore/casos", headers=org2.h).json() == []
    # El reporte respeta permisos y aclara que los montos son datos capturados
    af.c.patch(f"/api/afore/casos/{abierto['id']}", headers=af.h, json={"datos": {"monto_cliente": {"valor": "1000"}, "afore": {"valor": "SURA"}}})
    r = af.c.get("/api/afore/reportes/excel", headers=ana)
    import io

    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(r.content)).active
    assert "DATOS CAPTURADOS" in ws["A1"].value and ws.max_row == 3  # aviso + encabezado + 1 caso visible
    assert [x["id"] for x in af.c.get("/api/afore/casos", headers=af.h, params={"afore": "sura"}).json()] == [abierto["id"]]
    # Borrar la organización borra su información AFORE
    plataforma.c.post(f"/api/plataforma/clientes/{af.org_id}/eliminar", headers=plataforma.h, json={"confirmar_nombre": "Org 1"})
    assert db.query(m.AfCaso).count() == 0 and db.query(m.AfCliente).count() == 0


def test_vinculo_opcional_con_evidencia(af, plataforma, db):
    cl = alta(af)
    c = caso(af, cl["id"])
    assert af.c.get(f"/api/afore/casos/{c['id']}/evidencia", headers=af.h).json()["activa"] is False
    assert af.c.post(f"/api/afore/casos/{c['id']}/evidencia", headers=af.h, json={"ev_documento_id": 1}).status_code == 409
    activar(plataforma, af, "evidencia")
    aid = af.c.post("/api/evidencia/asuntos", headers=af.h, json={"nombre": "Asunto"}).json()["id"]
    af.c.post(f"/api/evidencia/asuntos/{aid}/documentos", headers=af.h, files=[("archivos", ("contrato.pdf", CONTRATO, "application/pdf"))])
    op = af.c.get(f"/api/afore/casos/{c['id']}/evidencia", headers=af.h).json()["opciones"]
    did = op[0]["documentos"][0]["id"]
    assert af.c.post(f"/api/afore/casos/{c['id']}/evidencia", headers=af.h, json={"ev_documento_id": did}).status_code == 201
    v = af.c.get(f"/api/afore/casos/{c['id']}/evidencia", headers=af.h).json()["vinculos"]
    assert v[0]["documento"] == "contrato.pdf" and db.query(m.AfDocumento).count() == 0  # no se duplica el archivo
    # Respeta la visibilidad de Evidencia
    af.c.patch(f"/api/evidencia/documentos/{did}/visibilidad", headers=af.h, json={"visibilidad": "restringido"})
    ana = af.usuario("analista", "ana@org1.test")
    assert af.c.get(f"/api/afore/casos/{c['id']}/evidencia", headers=ana).json()["vinculos"] == []


def test_demo_afore(db):
    from app.services.afore import demo
    from app.services.semilla import sembrar_demo
    sembrar_demo(db)
    assert demo.sembrar(db) is True and demo.sembrar(db) is False
    assert db.query(m.AfCaso).count() == 2 and db.query(m.AfRequisito).count() > 10
