"""WhatsApp de Nomira (la empresa): mensajes que entran a Ventas, respuesta en la ventana de 24 h y avisos con plantilla
solo a quien los autorizó."""
import hashlib
import hmac
import json
from datetime import date, timedelta

from app import models as m
from app.config import ajustes
from app.services import envios
from app.services import whatsapp_nomira as wn

V = "/api/plataforma/ventas"


def _firmar(cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(b"secreto-app", cuerpo, hashlib.sha256).hexdigest()


def _conectar(monkeypatch, enviados: list):
    monkeypatch.setattr(ajustes(), "whatsapp_app_secret", "secreto-app")
    monkeypatch.setattr(ajustes(), "whatsapp_nomira_phone_id", "9990001")
    monkeypatch.setattr(ajustes(), "whatsapp_nomira_token", "EAAG-token-de-prueba")
    monkeypatch.setattr(wn, "_enviar", lambda cuerpo: enviados.append(cuerpo) or f"wamid.S{len(enviados)}")


def _evento(cliente, **valor):
    cuerpo = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "9990001"}, **valor}}]}]}).encode()
    return cliente.post("/api/whatsapp/webhook", content=cuerpo, headers={"X-Hub-Signature-256": _firmar(cuerpo)})


def test_formato_de_telefono():
    assert wn.destino("55 1234 5678") == "525512345678"
    assert wn.destino("+52 1 55 1234 5678") == "525512345678"
    assert wn.destino("123") is None
    assert wn.diez("5215512345678") == wn.diez("(55) 1234-5678") == "5512345678"


def test_mensaje_entrante_crea_lead_y_respuesta_en_24h(plataforma, cliente, monkeypatch, db):
    enviados = []
    # apagado: el panel lo dice y no deja responder
    e = plataforma.c.get(f"{V}/whatsapp/estado", headers=plataforma.h).json()
    assert e["configurado"] is False and any("WHATSAPP_NOMIRA_TOKEN" in x for x in e["faltan"])
    _conectar(monkeypatch, enviados)
    r = _evento(cliente, contacts=[{"wa_id": "5215577778888", "profile": {"name": "Lic. Rosa Ficticia"}}],
                messages=[{"id": "wamid.A1", "from": "5215577778888", "type": "text", "text": {"body": "Hola, quiero informes de Nomira"}}])
    assert r.status_code == 200
    _evento(cliente, messages=[{"id": "wamid.A1", "from": "5215577778888", "type": "text", "text": {"body": "repetido"}}])  # idempotente
    ls = plataforma.c.get(f"{V}/leads", headers=plataforma.h).json()
    assert [(x["nombre"], x["origen"]) for x in ls] == [("Lic. Rosa Ficticia", "whatsapp")] and ls[0]["tarea"]
    c = plataforma.c.get(f"{V}/contactos/{ls[0]['id']}", headers=plataforma.h).json()
    assert c["telefono"] == "5577778888" and c["whatsapp_abierto"] is True and c["acepta_whatsapp"] is False
    recibidos = [a for a in c["actividades"] if a["titulo"] == "Mensaje recibido"]
    assert len(recibidos) == 1 and recibidos[0]["detalle"] == "Hola, quiero informes de Nomira"
    # el mismo teléfono escrito distinto se reconoce: no duplica el contacto
    _evento(cliente, messages=[{"id": "wamid.A2", "from": "525577778888", "type": "image", "image": {"id": "x"}}])
    assert len(plataforma.c.get(f"{V}/leads", headers=plataforma.h).json()) == 1
    # respuesta desde el panel dentro de las 24 h
    r = plataforma.c.post(f"{V}/contactos/{c['id']}/whatsapp", headers=plataforma.h, json={"texto": "¡Hola Rosa! Le llamo en 10 minutos."})
    assert r.status_code == 201, r.text
    assert enviados[-1] == {"to": "525577778888", "type": "text", "text": {"body": "¡Hola Rosa! Le llamo en 10 minutos.", "preview_url": False}}
    # pasadas 24 h, Meta no deja texto libre
    ct = db.get(m.VtContacto, c["id"])
    ct.whatsapp_ultimo_entrante = m.ahora() - timedelta(hours=25)
    db.commit()
    r = plataforma.c.post(f"{V}/contactos/{c['id']}/whatsapp", headers=plataforma.h, json={"texto": "¿Sigue interesada?"})
    assert r.status_code == 409 and "24 horas" in r.json()["detail"]
    assert len(enviados) == 1
    # número de un despacho que no es el de Nomira: no entra a Ventas
    cuerpo = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "otro"},
                                                           "messages": [{"id": "wamid.X", "from": "5215500000000", "type": "text", "text": {"body": "hola"}}]}}]}]}).encode()
    assert cliente.post("/api/whatsapp/webhook", content=cuerpo, headers={"X-Hub-Signature-256": _firmar(cuerpo)}).status_code == 200
    assert len(plataforma.c.get(f"{V}/leads", headers=plataforma.h).json()) == 1


def test_avisos_solo_con_autorizacion_y_baja(plataforma, cliente, monkeypatch, db):
    enviados = []
    _conectar(monkeypatch, enviados)
    # registro con teléfono y casilla de WhatsApp → bienvenida con plantilla
    from app.services import registro as rg
    u = rg.crear_cuenta(db, organizacion="Despacho Ficticio WA", nombre="Lic. Pablo Prueba", email="pablo@ficticio.test", hash_contrasena="x",
                        elegidos=rg.validar_modulos(["agenda"]), telefono="55 4444 3333", via="correo", acepta_whatsapp=True)
    db.commit()
    assert enviados[-1]["type"] == "template" and enviados[-1]["to"] == "525544443333"
    assert enviados[-1]["template"]["name"] == "nomira_bienvenida"
    assert [p["text"] for p in enviados[-1]["template"]["components"][0]["parameters"]][:2] == ["Lic. Pablo Prueba", "Despacho Ficticio WA"]
    # sin la casilla → no se manda nada aunque haya teléfono
    rg.crear_cuenta(db, organizacion="Otro Despacho", nombre="Lic. Sin Permiso", email="sin@ficticio.test", hash_contrasena="x",
                    elegidos=rg.validar_modulos(["agenda"]), telefono="5533332222", via="correo")
    db.commit()
    assert len(enviados) == 1
    # vencimiento del plan → plantilla de vencimiento, una sola vez
    oid = u.organizacion_id
    hoy = date.today()
    db.add(m.PeriodoSuscripcion(organizacion_id=oid, plan="mensual", inicio=hoy - timedelta(days=25), fin=hoy + timedelta(days=3), pagado=True))
    db.commit()
    envios.ejecutar_recordatorios(db)
    envios.ejecutar_recordatorios(db)
    vence = [x for x in enviados if x.get("template", {}).get("name") == "nomira_vencimiento"]
    assert len(vence) == 1
    # escribe «BAJA» → deja de recibir avisos
    _evento(cliente, messages=[{"id": "wamid.B1", "from": "5215544443333", "type": "text", "text": {"body": "Baja"}}])
    db.expire_all()
    ct = wn.contacto_por_telefono(db, "5544443333")
    assert ct.acepta_whatsapp is False
    assert wn.aviso(db, "vencimiento", oid, ["pablo@ficticio.test"], ["a", "b", "c"], "otra-llave").startswith("omitido")
