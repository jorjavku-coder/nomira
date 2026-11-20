"""Módulo Comercial: solo superadministrador, cálculo en el servidor, versiones congeladas, envío sin
simular, enlace seguro del cliente, pagos (transferencia confirmada por Nomira y Stripe en modo de
prueba con firma e idempotencia) y asignación a la organización sin borrar datos."""
import hashlib
import hmac
import json
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from app import models as m
from app.config import ajustes
from app.services import correo
from app.services.comercial import base as cm
from app.services.comercial import stripe as st

R = "/api/plataforma/comercial"


@pytest.fixture
def buzon(monkeypatch):
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "modo_prueba", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto, adjuntos=None: enviados.append(
        {"para": dest, "asunto": asunto, "html": html, "texto": texto, "adjuntos": adjuntos}))
    monkeypatch.setattr(ajustes(), "url_publica", "https://nomirasoft.com")
    return enviados


def catalogo(p):
    r = p.c.get(f"{R}/catalogo", headers=p.h)
    assert r.status_code == 200, r.text
    return r.json()


def paquete(p, clave):
    return next(x for x in catalogo(p)["paquetes"] if x["clave"] == clave)


def nueva(p, **kw):
    cat = catalogo(p)
    basico = next(x for x in cat["paquetes"] if x["clave"] == "basico")
    datos = {"contacto": "Lic. Ana Prospecto", "despacho": "Despacho Ficticio SC", "email": "ana@despacho.test", "telefono": "55 1234 5678",
             "necesidad": "Calcular prestaciones y dar seguimiento a prospectos.", "notas_internas": "NOTA-SECRETA-INTERNA",
             "entrada": {"paquete_id": basico["id"], "modulos": ["nomina"], "periodicidad": "mensual", "condiciones_pago": "Pago anticipado"},
             **kw}
    r = p.c.post(f"{R}/cotizaciones", headers=p.h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()


def enviar(p, cid, **kw):
    return p.c.post(f"{R}/cotizaciones/{cid}/enviar", headers=p.h, json={"confirmacion": "Enviar cotización", **kw})


def token_de(det):
    return det["enlace"]["url"].split("#")[1]


def test_solo_superadministrador(plataforma, org, cliente):
    # un usuario de despacho no entra (su token no sirve en /api/plataforma)
    assert org.c.get(f"{R}/catalogo", headers=org.h).status_code == 401
    assert cliente.get(f"{R}/catalogo").status_code == 401
    # un administrador de soporte de la plataforma tampoco, aunque esté autenticado
    r = plataforma.c.post("/api/plataforma/admins", headers=plataforma.h, json={"nombre": "Soporte Uno", "email": "soporte@nomira.test"})
    assert r.status_code == 201 and r.json()["admin"]["rol"] == "soporte"
    temporal = r.json()["acceso"]["contrasena_temporal"]
    t = cliente.post("/api/plataforma/login", json={"email": "soporte@nomira.test", "contrasena": temporal}).json()["token"]
    hs = {"Authorization": f"Bearer {t}"}
    for metodo, ruta in (("get", "/catalogo"), ("get", "/cotizaciones"), ("get", "/resumen"), ("post", "/calcular"), ("put", "/config")):
        assert getattr(cliente, metodo)(f"{R}{ruta}", headers=hs, **({"json": {}} if metodo != "get" else {})).status_code == 403, ruta
    # soporte no puede crear superadministradores ni cambiar roles
    assert cliente.post("/api/plataforma/admins", headers=hs, json={"nombre": "X Y", "email": "x@nomira.test", "rol": "superadministrador"}).status_code == 403
    sid = r.json()["admin"]["id"]
    assert cliente.patch(f"/api/plataforma/admins/{sid}", headers=hs, json={"rol": "superadministrador"}).status_code == 403
    # el superadministrador sí lo promueve (y la sesión anterior deja de valer)
    assert plataforma.c.patch(f"/api/plataforma/admins/{sid}", headers=plataforma.h, json={"rol": "superadministrador"}).json()["rol"] == "superadministrador"
    assert cliente.get(f"{R}/catalogo", headers=hs).status_code == 401


def test_catalogo_inicial_editable_con_historial(plataforma, db):
    cat = catalogo(plataforma)
    precios = {p["clave"]: p["precio_mensual"] for p in cat["paquetes"]}
    assert precios == {"basico": "1790.00", "medio": "3490.00", "premium": "5990.00"}
    extras = {p["clave"]: p["precio_mensual"] for p in cat["precios"]}
    assert extras["modulo:afore"] == "1190.00" and extras["usuario"] == "119.00" and extras["almacenamiento"] == "299.00"
    assert cat["config"]["precios_publicos"] == "ocultos" and cat["integraciones"]["formas_pago"] == []
    b = paquete(plataforma, "basico")
    r = plataforma.c.patch(f"{R}/paquetes/{b['id']}", headers=plataforma.h, json={**b, "precio_mensual": "1890", "iva_pct": None})
    assert r.status_code == 200 and r.json()["precio_mensual"] == "1890.00"
    h = plataforma.c.get(f"{R}/historial-precios", headers=plataforma.h).json()
    assert h[0]["campo"] == "precio_mensual" and h[0]["antes"] == "1790.00" and h[0]["despues"] == "1890.00" and h[0]["por"] == "Dueño de Nomira"
    # un segundo catálogo no vuelve a sembrar ni pisa el cambio
    assert paquete(plataforma, "basico")["precio_mensual"] == "1890.00"
    assert db.query(m.CmPaquete).count() == 3


def test_calculo_en_el_servidor(plataforma):
    medio = paquete(plataforma, "medio")
    e = {"paquete_id": medio["id"], "modulos": ["nomina", "evidencia", "afore", "leads"], "incluidos": ["nomina", "evidencia", "afore"],
         "usuarios_extra": 2, "bloques_extra": 1, "periodicidad": "mensual", "total": "1.00", "subtotal": "1.00",
         "servicios": [{"clave": "capacitacion", "precio": "1500"}, {"clave": "configuracion", "precio": "0"}]}
    c = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": e}).json()
    # 3490 + Leads 690 + 2×119 + 1×299 = 4717 al mes; + capacitación 1500 única = 6217; IVA 16 % = 994.72
    assert c["mensual"] == "4717.00" and c["subtotal"] == "6217.00" and c["iva"] == "994.72" and c["total"] == "7211.72"
    assert c["usuarios"]["total"] == 17 and c["almacenamiento"]["total_gb"] == 125 and c["asuntos_estimados"] is None
    anual = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": {**e, "periodicidad": "anual", "servicios": []}}).json()
    assert anual["subtotal"] == "56604.00"
    # descuentos: requieren motivo y respetan el máximo autorizado
    r = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": {**e, "descuento": {"tipo": "porcentaje", "valor": "10"}}})
    assert r.status_code == 422 and "motivo" in r.json()["detail"]
    r = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": {**e, "descuento": {"tipo": "porcentaje", "valor": "50", "motivo": "Cliente fundador"}}})
    assert r.status_code == 422 and "máximo" in r.json()["detail"]
    ok = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": {**e, "descuento": {"tipo": "porcentaje", "valor": "10", "motivo": "Cliente fundador"}}}).json()
    assert ok["descuento"]["importe"] == "621.70" and ok["base_iva"] == "5595.30"
    # Básico: un módulo incluido; el segundo se cobra como adicional
    b = paquete(plataforma, "basico")
    r = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": {"paquete_id": b["id"], "modulos": ["nomina", "afore"]}}).json()
    assert [x["incluido"] for x in r["modulos"]] == [True, False] and r["mensual"] == "2980.00"
    # el estimado de asuntos es solo referencia y aparece únicamente si Nomira lo configura
    conf = catalogo(plataforma)["config"]
    plataforma.c.put(f"{R}/config", headers=plataforma.h, json={**conf, "mb_promedio_por_asunto": 50})
    r = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": {"paquete_id": b["id"], "modulos": ["nomina"]}}).json()
    assert r["asuntos_estimados"] == 409


def test_flujo_completo_transferencia(plataforma, buzon, cliente, org, db):
    c = nueva(plataforma)
    assert c["estado"] == "borrador" and c["folio"].startswith(f"COT-{datetime.now().year}-") and c["version"]["calculo"]["total"] == "2076.40"
    pdf = plataforma.c.get(f"{R}/cotizaciones/{c['id']}/pdf", headers=plataforma.h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert plataforma.c.post(f"{R}/cotizaciones/{c['id']}/estado", headers=plataforma.h, json={"estado": "revision"}).json()["estado"] == "revision"
    # sin la confirmación explícita no se envía
    assert plataforma.c.post(f"{R}/cotizaciones/{c['id']}/enviar", headers=plataforma.h, json={"confirmacion": "ok"}).status_code == 422
    r = enviar(plataforma, c["id"], mensaje="Hola Ana, aquí su propuesta.")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["estado"] == "enviada" and d["envio"]["prueba"] is True and d["enlace"]["url"].startswith("https://nomirasoft.com/propuesta#")
    correo_ = buzon[-1]
    assert c["folio"] in correo_["asunto"] and "Hola Ana, aquí su propuesta." in correo_["texto"] and "$2,076.40" in correo_["texto"]
    assert correo_["adjuntos"][0][0] == f"{c['folio']}-v1.pdf" and correo_["adjuntos"][0][1].startswith(b"%PDF")
    assert "NOTA-SECRETA-INTERNA" not in correo_["html"] + correo_["texto"]

    tok = token_de(d)
    h = {"X-Enlace": tok}
    v = cliente.post("/api/propuesta", headers=h).json()
    assert v["disponible"] and v["folio"] == c["folio"] and v["calculo"]["total"] == "2076.40"
    assert "NOTA-SECRETA-INTERNA" not in json.dumps(v) and "email" not in v["cliente"]
    assert v["puede_aceptar"] and not v["puede_pagar"] and v["formas_pago"] == []
    assert cliente.post("/api/propuesta", headers={"X-Enlace": "x" * 40}).status_code == 404
    assert cliente.post("/api/propuesta/pdf", headers=h).content.startswith(b"%PDF")
    assert cliente.post("/api/propuesta/ajustes", headers=h, json={"mensaje": "¿Pueden incluir Leads?"}).status_code == 200
    # aceptación: casilla obligatoria y versión vigente
    assert cliente.post("/api/propuesta/aceptar", headers=h, json={"nombre": "Ana Prospecto", "version": 1, "acepto": False}).status_code == 422
    a = cliente.post("/api/propuesta/aceptar", headers=h, json={"nombre": "Ana Prospecto", "cargo": "Socia", "version": 1, "acepto": True})
    assert a.status_code == 200 and a.json()["estado"] == "aceptada"
    # la transferencia reportada por el cliente NO marca pagada
    assert cliente.post("/api/propuesta/pagar", headers=h, json={"metodo": "spei"}).status_code == 422  # no está habilitada
    det = plataforma.c.get(f"{R}/cotizaciones/{c['id']}", headers=plataforma.h).json()
    tipos = [e["tipo"] for e in det["eventos"]]
    assert {"creada", "lista_revision", "enviada", "vista", "ajuste_solicitado", "aceptada"} <= set(tipos)
    acept = next(e for e in det["eventos"] if e["tipo"] == "aceptada")
    assert acept["detalle"]["version"] == 1 and acept["detalle"]["huella"] == det["versiones"][0]["huella"]
    # pago parcial y luego total, confirmados por el superadministrador
    p1 = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/pagos", headers=plataforma.h,
                           json={"metodo": "spei", "monto": "1000", "fecha_pago": date.today().isoformat(), "referencia": "SPEI-1"})
    assert p1.json()["estado"] == "pendiente_pago"
    p2 = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/pagos", headers=plataforma.h,
                           json={"metodo": "spei", "monto": "1076.40", "fecha_pago": date.today().isoformat(), "referencia": "SPEI-2"}).json()
    assert p2["estado"] == "pagada" and p2["pagado"] == "2076.40" and p2["acciones"]["convertir"]
    # asignación: activa módulos sin desactivar los que ya tenía, crea el periodo y registra capacidades
    org.c.patch("/api/organizacion/modulos/nomina", headers=org.h, json={"activo": True})
    oid = org.org_id
    conv = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/convertir", headers=plataforma.h, json={"organizacion_id": oid}).json()
    assert conv["asignacion"]["usuarios"] == 5 and conv["asignacion"]["almacenamiento_gb"] == 20 and conv["asignacion"]["origen"] == "pago"
    periodo = db.query(m.PeriodoSuscripcion).filter_by(organizacion_id=oid).order_by(m.PeriodoSuscripcion.id.desc()).first()
    assert periodo.plan == "mensual" and periodo.pagado and str(periodo.monto) == "2076.40"
    assert plataforma.c.post(f"{R}/cotizaciones/{c['id']}/convertir", headers=plataforma.h, json={"organizacion_id": oid}).status_code == 409
    # impago: cambia el estado comercial, nunca borra datos
    aid = conv["asignacion"]["id"]
    assert plataforma.c.patch(f"{R}/asignaciones/{aid}", headers=plataforma.h, json={"estado": "impago"}).json()["estado"] == "impago"
    assert org.c.get("/api/expedientes", headers=org.h).status_code == 200
    res = plataforma.c.get(f"{R}/resumen", headers=plataforma.h).json()
    assert res["importes"]["cobrado"]["monto"] == "2076.40" and res["importes"]["aceptado"]["n"] == 1
    assert db.query(m.Auditoria).filter(m.Auditoria.accion.like("comercial_%")).count() >= 5


def test_sin_correo_no_se_simula_envio(plataforma, monkeypatch, cliente):
    monkeypatch.setattr(correo, "configurado", lambda: False)
    c = nueva(plataforma)
    r = enviar(plataforma, c["id"])
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "correo_no_configurado"
    det = plataforma.c.get(f"{R}/cotizaciones/{c['id']}", headers=plataforma.h).json()
    assert det["estado"] == "borrador" and det["enviada_en"] is None
    vista = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/vista-correo", headers=plataforma.h, json={"mensaje": "Texto para copiar"}).json()
    assert vista["correo"]["configurado"] is False and "Texto para copiar" in vista["texto"]
    # el administrador puede mandarla por fuera y dejar constancia (no se dice que la envió Nomira)
    d = enviar(plataforma, c["id"], manual=True).json()
    assert d["estado"] == "enviada" and d["eventos"][0]["tipo"] == "enviada_manual"


def test_versiones_congeladas_y_cambios(plataforma, buzon, cliente):
    c = nueva(plataforma)
    d = enviar(plataforma, c["id"]).json()
    tok = token_de(d)
    # cambiar precios del catálogo NO altera la versión enviada
    b = paquete(plataforma, "basico")
    plataforma.c.patch(f"{R}/paquetes/{b['id']}", headers=plataforma.h, json={**b, "precio_mensual": "2500", "iva_pct": None})
    assert cliente.post("/api/propuesta", headers={"X-Enlace": tok}).json()["calculo"]["total"] == "2076.40"
    # editar una enviada crea la versión 2 con constancia de cambios
    medio = paquete(plataforma, "medio")
    cuerpo = {"contacto": c["contacto"], "despacho": c["despacho"], "email": c["email"],
              "entrada": {"paquete_id": medio["id"], "modulos": ["nomina", "leads"], "periodicidad": "mensual"}}
    e = plataforma.c.put(f"{R}/cotizaciones/{c['id']}", headers=plataforma.h, json=cuerpo).json()
    assert e["version_actual"] == 2 and e["estado"] == "borrador" and len(e["versiones"]) == 2
    assert any("Básico → Medio" in x for x in e["version"]["cambios"]) and any(x.startswith("Total:") for x in e["version"]["cambios"])
    assert e["versiones"][1]["total"] == "2076.40"  # la v1 intacta
    # el cliente sigue viendo la v1 hasta que se envíe la v2, y no puede aceptar una versión vieja después
    assert cliente.post("/api/propuesta", headers={"X-Enlace": tok}).json()["version"] == 1
    enviar(plataforma, c["id"])
    assert cliente.post("/api/propuesta", headers={"X-Enlace": tok}).json()["version"] == 2
    r = cliente.post("/api/propuesta/aceptar", headers={"X-Enlace": tok}, json={"nombre": "Ana", "version": 1, "acepto": True})
    assert r.status_code == 409
    # duplicar crea otra cotización en borrador con precios actuales
    dup = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/duplicar", headers=plataforma.h).json()
    assert dup["folio"] != c["folio"] and dup["estado"] == "borrador"
    lista = plataforma.c.get(f"{R}/cotizaciones?q=Ficticio", headers=plataforma.h).json()
    assert len(lista) == 2 and plataforma.c.get(f"{R}/cotizaciones?estado=borrador", headers=plataforma.h).json()[0]["folio"] == dup["folio"]


def test_enlace_vencido_revocado_y_cancelado(plataforma, buzon, cliente, db):
    c = nueva(plataforma)
    d = enviar(plataforma, c["id"]).json()
    tok = token_de(d)
    plataforma.c.post(f"{R}/cotizaciones/{c['id']}/enlace", headers=plataforma.h, json={"accion": "revocar"})
    r = cliente.post("/api/propuesta", headers={"X-Enlace": tok}).json()
    assert r["disponible"] is False and r["motivo"] == "revocado" and "contacto" in r and "calculo" not in r
    d = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/enlace", headers=plataforma.h, json={"accion": "regenerar"}).json()
    nuevo = token_de(d)
    assert nuevo != tok and cliente.post("/api/propuesta", headers={"X-Enlace": tok}).status_code == 404  # el anterior ya no existe
    # vencimiento
    x = db.get(m.CmCotizacion, c["id"])
    x.vence_en = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    r = cliente.post("/api/propuesta", headers={"X-Enlace": nuevo}).json()
    assert r["disponible"] is False and r["motivo"] == "vencida"
    assert cliente.post("/api/propuesta/aceptar", headers={"X-Enlace": nuevo}, json={"nombre": "Ana", "version": 1, "acepto": True}).status_code == 409
    assert plataforma.c.get(f"{R}/cotizaciones/{c['id']}", headers=plataforma.h).json()["estado"] == "vencida"
    # cancelada
    c2 = nueva(plataforma)
    t2 = token_de(enviar(plataforma, c2["id"]).json())
    plataforma.c.post(f"{R}/cotizaciones/{c2['id']}/cancelar", headers=plataforma.h, json={"motivo": "El prospecto desistió"})
    assert cliente.post("/api/propuesta", headers={"X-Enlace": t2}).json()["motivo"] == "cancelada"


def test_formas_de_pago_solo_completas(plataforma):
    conf = catalogo(plataforma)["config"]
    r = plataforma.c.put(f"{R}/config", headers=plataforma.h, json={**conf, "spei_habilitado": True, "pago_tarjeta": True})
    i = r.json()["integraciones"]
    assert i["formas_pago"] == [] and len(i["faltantes_pago"]) == 2  # sin datos bancarios ni Stripe: deshabilitadas
    assert plataforma.c.put(f"{R}/config", headers=plataforma.h, json={**conf, "spei_clabe": "123"}).status_code == 422
    r = plataforma.c.put(f"{R}/config", headers=plataforma.h, json={**conf, "spei_habilitado": True, "spei_banco": "Banco Ficticio",
                                                                  "spei_titular": "Nomira Ficticia SA de CV", "spei_clabe": "000000000000000000"})
    assert [f["clave"] for f in r.json()["integraciones"]["formas_pago"]] == ["spei"]
    assert r.json()["integraciones"]["stripe"]["conectado"] is False


def test_stripe_modo_prueba_firma_e_idempotencia(plataforma, buzon, cliente, monkeypatch, db):
    monkeypatch.setattr(ajustes(), "stripe_secret_key", "sk_live_no_se_acepta")
    assert cm.stripe_estado()["conectado"] is False and "prueba" in cm.stripe_estado()["motivo"]
    monkeypatch.setattr(ajustes(), "stripe_secret_key", "sk_test_ficticia")
    monkeypatch.setattr(ajustes(), "stripe_webhook_secret", "whsec_ficticio")
    conf = catalogo(plataforma)["config"]
    plataforma.c.put(f"{R}/config", headers=plataforma.h, json={**conf, "pago_tarjeta": True})
    c = nueva(plataforma)
    tok = token_de(enviar(plataforma, c["id"]).json())
    h = {"X-Enlace": tok}
    assert cliente.post("/api/propuesta/pagar", headers=h, json={"metodo": "tarjeta"}).status_code == 409  # primero aceptar
    cliente.post("/api/propuesta/aceptar", headers=h, json={"nombre": "Ana Prospecto", "version": 1, "acepto": True})
    llamadas = []

    def falsa(**kw):
        llamadas.append(kw)
        return {"id": "cs_test_123", "url": "https://checkout.stripe.com/c/pay/cs_test_123"}
    monkeypatch.setattr(st, "crear_sesion", falsa)
    r = cliente.post("/api/propuesta/pagar", headers=h, json={"metodo": "tarjeta", "total": "1.00"})
    assert r.json()["url"].startswith("https://checkout.stripe.com/") and str(llamadas[0]["total"]) == "2076.40"
    assert plataforma.c.get(f"{R}/cotizaciones/{c['id']}", headers=plataforma.h).json()["estado"] == "pendiente_pago"

    def webhook(evento, secreto="whsec_ficticio"):
        cuerpo = json.dumps(evento).encode()
        t = int(time.time())
        firma = hmac.new(secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
        return cliente.post("/api/comercial/stripe/webhook", content=cuerpo, headers={"Stripe-Signature": f"t={t},v1={firma}", "Content-Type": "application/json"})

    ev = {"id": "evt_1", "type": "checkout.session.completed", "livemode": False,
          "data": {"object": {"id": "cs_test_123", "payment_status": "paid", "amount_total": 207640, "currency": "mxn", "payment_intent": "pi_1"}}}
    assert webhook(ev, secreto="whsec_otro").status_code == 400  # firma inválida: no se aplica
    assert plataforma.c.get(f"{R}/cotizaciones/{c['id']}", headers=plataforma.h).json()["estado"] == "pendiente_pago"
    # importe distinto: no se marca pagada
    malo = {**ev, "id": "evt_0", "data": {"object": {**ev["data"]["object"], "amount_total": 100}}}
    assert webhook(malo).status_code == 200
    assert plataforma.c.get(f"{R}/cotizaciones/{c['id']}", headers=plataforma.h).json()["estado"] == "pendiente_pago"
    assert webhook(ev).status_code == 200
    det = plataforma.c.get(f"{R}/cotizaciones/{c['id']}", headers=plataforma.h).json()
    assert det["estado"] == "pagada" and det["pagado"] == "2076.40"
    assert webhook(ev).json().get("duplicado") is True  # el mismo evento no se aplica dos veces
    assert db.query(m.CmPago).filter_by(cotizacion_id=c["id"], estado="confirmado").count() == 1
    # los eventos en modo real se ignoran
    assert webhook({**ev, "id": "evt_live", "livemode": True}).json().get("ignorado") == "modo_real"


def test_precios_publicos(plataforma, cliente):
    assert cliente.get("/api/publico").json()["precio_desde"] is None  # por defecto no se publican
    conf = catalogo(plataforma)["config"]
    plataforma.c.put(f"{R}/config", headers=plataforma.h, json={**conf, "precios_publicos": "desde"})
    assert cliente.get("/api/publico").json()["precio_desde"] == "1790.00"


def test_promocional_requiere_motivo(plataforma, buzon, org, db):
    c = nueva(plataforma)
    enviar(plataforma, c["id"])
    oid = org.org_id
    r = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/convertir", headers=plataforma.h, json={"organizacion_id": oid})
    assert r.status_code == 409  # sin pago
    r = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/convertir", headers=plataforma.h, json={"organizacion_id": oid, "promocional": True})
    assert r.status_code == 422
    r = plataforma.c.post(f"{R}/cotizaciones/{c['id']}/convertir", headers=plataforma.h,
                          json={"organizacion_id": oid, "promocional": True, "motivo": "Piloto aprobado por dirección", "confirmo": True})
    assert r.status_code == 200 and r.json()["asignacion"]["origen"] == "promocional"
    assert not db.query(m.PeriodoSuscripcion).filter_by(organizacion_id=oid).order_by(m.PeriodoSuscripcion.id.desc()).first().pagado
