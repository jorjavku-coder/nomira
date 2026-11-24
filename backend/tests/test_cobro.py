"""Cobro en línea y CFDI con las cuentas del propio despacho: llaves cifradas y nunca devueltas, liga por lo pendiente,
pago registrado una sola vez al confirmarse en Stripe, factura con desglose y retenciones, cancelación, permisos y aislamiento."""
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest

from app import models as m
from app.services.clientes import cobro as cob

C = "/api/clientes"
S = "/api/cobro"
STRIPE = "sk_test_" + "a" * 24
FACT = "sk_test_" + "b" * 24


class Falso:
    """Simula Stripe y Facturapi. Guarda lo que recibe para revisarlo."""

    def __init__(self):
        self.llamadas = []
        self.sesiones = {}
        self.n = 0

    def responder(self, metodo, url, **kw):
        self.llamadas.append((metodo, url, kw))
        req = httpx.Request(metodo, url)
        if "stripe.com" in url:
            if url.endswith("/checkout/sessions") and metodo == "GET":
                return httpx.Response(200, json={"data": []}, request=req)
            if url.endswith("/checkout/sessions") and metodo == "POST":
                self.n += 1
                sid = f"cs_test_{self.n}"
                self.sesiones[sid] = {"id": sid, "url": f"https://checkout.stripe.com/c/pay/{sid}", "payment_status": "unpaid", "status": "open",
                                      "expires_at": 1900000000}
                return httpx.Response(200, json=self.sesiones[sid], request=req)
            if url.endswith("/expire"):
                sid = url.split("/")[-2]
                self.sesiones[sid]["status"] = "expired"
                return httpx.Response(200, json=self.sesiones[sid], request=req)
            sid = url.rsplit("/", 1)[-1]
            return httpx.Response(200, json=self.sesiones[sid], request=req)
        if "facturapi" in url:
            if metodo == "GET" and url.endswith("/invoices"):
                return httpx.Response(200, json={"data": []}, request=req)
            if metodo == "POST" and url.endswith("/invoices"):
                return httpx.Response(200, json={"id": "inv_1", "uuid": "AAAA-BBBB", "series": "A", "folio_number": 7, "total": 5000.0}, request=req)
            if metodo == "DELETE":
                return httpx.Response(200, json={"status": "canceled"}, request=req)
            if url.endswith("/pdf"):
                return httpx.Response(200, content=b"%PDF-1.4 falso", request=req)
            if url.endswith("/email"):
                return httpx.Response(200, json={"ok": True}, request=req)
        return httpx.Response(404, json={}, request=req)


@pytest.fixture
def api(monkeypatch):
    f = Falso()
    monkeypatch.setattr(httpx, "get", lambda url, **kw: f.responder("GET", url, **kw))
    monkeypatch.setattr(httpx, "post", lambda url, **kw: f.responder("POST", url, **kw))
    monkeypatch.setattr(httpx, "delete", lambda url, **kw: f.responder("DELETE", url, **kw))
    return f


def cliente(o, **kw):
    r = o.c.post(C, headers=o.h, json={"nombre": "Comercializadora Ejemplo SA de CV", "tipo": "moral", "rfc": "CEJ800101AB1", "email": "pagos@ejemplo.test",
                                       "codigo_postal": "06600", "regimen_fiscal": "601 General de Ley Personas Morales", **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def conectar(o):
    r = o.c.put(f"{S}/config", headers=o.h, json={"stripe_llave": STRIPE, "facturapi_llave": FACT, "clave_producto": "80121600"})
    assert r.status_code == 200, r.text
    return r.json()


def test_configuracion_cifrada_y_sin_llaves_visibles(org, api, db):
    c = org.c.get(f"{S}/config", headers=org.h).json()
    assert c["stripe"]["conectado"] is False and c["facturapi"]["conectado"] is False
    assert org.c.put(f"{S}/config", headers=org.h, json={"stripe_llave": "pk_live_123"}).status_code == 422  # llave pública: no
    r = conectar(org)
    assert r["stripe"]["conectado"] and r["stripe"]["prueba"] and r["facturapi"]["conectado"]
    texto = org.c.get(f"{S}/config", headers=org.h).text
    assert STRIPE not in texto and FACT not in texto
    fila = db.query(m.CrConfigCobro).one()
    assert STRIPE not in (fila.stripe_llave_cifrada or "") and cob.descifrar(fila.stripe_llave_cifrada) == STRIPE
    aud = db.query(m.Auditoria).filter_by(accion="cobro_configuracion").one()
    assert STRIPE not in str(aud.detalle)
    analista = org.usuario("analista", "analista-cobro@ejemplo.test")
    assert org.c.put(f"{S}/config", headers=analista, json={"stripe_llave": ""}).status_code == 403
    assert org.c.put(f"{S}/config", headers=org.h, json={"stripe_llave": ""}).json()["stripe"]["conectado"] is False


def test_liga_de_pago_registra_el_pago_una_vez(org, org2, api, db):
    cid = cliente(org)
    assert org.c.post(f"{S}/clientes/{cid}/ligas", headers=org.h, json={}).status_code == 422  # sin Stripe conectado
    conectar(org)
    g = org.c.post(f"{C}/{cid}/cargos", headers=org.h, json={"concepto": "Anticipo amparo", "monto": "5000", "vence": (date.today() + timedelta(days=5)).isoformat()})
    assert g.status_code == 201, g.text
    gid = g.json()["cargos"][0]["id"]
    assert org.c.post(f"{S}/clientes/{cid}/ligas", headers=org.h, json={"cargo_id": gid, "monto": "6000"}).status_code == 422  # más que lo pendiente
    r = org.c.post(f"{S}/clientes/{cid}/ligas", headers=org.h, json={"cargo_id": gid})
    assert r.status_code == 201, r.text
    liga = r.json()
    assert liga["monto"] == "5000.00" and liga["url"].startswith("https://checkout.stripe.com/")
    enviado = [k for mt, u, k in api.llamadas if mt == "POST" and u.endswith("/checkout/sessions")][0]
    assert enviado["data"]["line_items[0][price_data][unit_amount]"] == "500000" and enviado["auth"][0] == STRIPE
    assert org2.c.get(f"{S}/clientes/{cid}", headers=org2.h).status_code == 404  # aislamiento
    v = org.c.get(f"{S}/clientes/{cid}", headers=org.h).json()
    assert v["ligas"][0]["estado"] == "pendiente" and v["pagos_nuevos"] == 0
    api.sesiones["cs_test_1"].update(payment_status="paid", payment_intent="pi_123")
    v = org.c.get(f"{S}/clientes/{cid}", headers=org.h).json()
    assert v["pagos_nuevos"] == 1 and v["ligas"][0]["estado"] == "pagada" and v["ligas"][0]["url"] is None
    assert org.c.get(f"{S}/clientes/{cid}", headers=org.h).json()["pagos_nuevos"] == 0  # no se duplica
    pagos = db.query(m.CrPago).filter_by(cliente_id=cid).all()
    assert len(pagos) == 1 and pagos[0].metodo == "en_linea" and pagos[0].referencia == "pi_123" and pagos[0].cargo_id == gid
    cta = org.c.get(f"{C}/{cid}", headers=org.h).json()
    assert cta["cargos"][0]["estado"] == "pagado"
    assert org.c.post(f"{S}/ligas/{liga['id']}/cancelar", headers=org.h).status_code == 409


def test_cancelar_liga(org, api):
    cid = cliente(org)
    conectar(org)
    org.c.post(f"{C}/{cid}/cargos", headers=org.h, json={"concepto": "Iguala", "monto": "1200", "vence": date.today().isoformat()})
    liga = org.c.post(f"{S}/clientes/{cid}/ligas", headers=org.h, json={"monto": "500"}).json()
    r = org.c.post(f"{S}/ligas/{liga['id']}/cancelar", headers=org.h)
    assert r.status_code == 200 and r.json()["estado"] == "cancelada"


def test_regimen_por_nombre():
    assert cob.regimen(m.CrCliente(regimen_fiscal="General de Ley Personas Morales")) == "601"
    assert cob.regimen(m.CrCliente(regimen_fiscal="Régimen Simplificado de Confianza")) == "626"
    assert cob.regimen(m.CrCliente(regimen_fiscal="612 - Personas Físicas")) == "612"
    assert cob.regimen(m.CrCliente(regimen_fiscal="algo")) is None


def test_desglose_retenciones():
    d = cob.desglose(Decimal("5000"), "ninguna", True)
    assert d["subtotal"] + d["iva"] == d["total"] and abs(d["total"] - Decimal("5000")) <= Decimal("0.01")
    d = cob.desglose(Decimal("5000"), "honorarios", True)
    assert d["ret_isr"] > 0 and d["ret_iva"] > 0 and abs(d["total"] - Decimal("5000")) <= Decimal("0.02")
    assert cob.desglose(Decimal("5000"), "honorarios", False)["ret_isr"] == 0  # persona física: sin retención


def test_factura_de_un_pago(org, org2, api, db):
    cid = cliente(org, rfc=None)
    org.c.post(f"{C}/{cid}/cargos", headers=org.h, json={"concepto": "Contestación de demanda", "monto": "5000", "vence": date.today().isoformat()})
    pid = org.c.post(f"{C}/{cid}/pagos", headers=org.h, json={"monto": "5000", "fecha": date.today().isoformat(), "metodo": "transferencia"}).json()["pago_id"]
    assert org.c.post(f"{S}/pagos/{pid}/factura", headers=org.h, json={}).status_code == 422  # sin Facturapi
    org.c.put(f"{S}/config", headers=org.h, json={"facturapi_llave": FACT, "retenciones": "honorarios"})
    r = org.c.post(f"{S}/pagos/{pid}/factura", headers=org.h, json={})
    assert r.status_code == 422 and "RFC" in r.json()["detail"] and "clave de producto" in r.json()["detail"]
    org.c.put(f"{C}/{cid}", headers=org.h, json={"nombre": "Comercializadora Ejemplo SA de CV", "tipo": "moral", "rfc": "CEJ800101AB1",
                                                 "codigo_postal": "06600", "regimen_fiscal": "601", "email": "pagos@ejemplo.test"})
    org.c.put(f"{S}/config", headers=org.h, json={"clave_producto": "80121600"})
    assert org2.c.post(f"{S}/pagos/{pid}/factura", headers=org2.h, json={}).status_code == 404
    r = org.c.post(f"{S}/pagos/{pid}/factura", headers=org.h, json={"uso": "G03"})
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["uuid"] == "AAAA-BBBB" and f["serie_folio"] == "A7" and f["prueba"] is True
    cuerpo = [k for mt, u, k in api.llamadas if mt == "POST" and u.endswith("/invoices")][0]["json"]
    assert cuerpo["customer"]["tax_id"] == "CEJ800101AB1" and cuerpo["customer"]["tax_system"] == "601" and cuerpo["customer"]["address"]["zip"] == "06600"
    assert cuerpo["payment_form"] == "03" and cuerpo["payment_method"] == "PUE"
    item = cuerpo["items"][0]["product"]
    assert item["product_key"] == "80121600" and any(t.get("withholding") and t["type"] == "ISR" for t in item["taxes"])
    assert org.c.post(f"{S}/pagos/{pid}/factura", headers=org.h, json={}).status_code == 409  # una vigente por pago
    pdf = org.c.get(f"{S}/facturas/{f['id']}/pdf", headers=org.h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert org.c.post(f"{S}/facturas/{f['id']}/enviar", headers=org.h, json={}).json()["ok"] is True
    assert org.c.post(f"{S}/facturas/{f['id']}/cancelar", headers=org.h, json={"motivo": "01"}).status_code == 422
    c = org.c.post(f"{S}/facturas/{f['id']}/cancelar", headers=org.h, json={"motivo": "02"})
    assert c.status_code == 200 and c.json()["estado"] == "cancelada"
    v = org.c.get(f"{S}/clientes/{cid}", headers=org.h).json()
    assert v["facturas"][0]["estado"] == "cancelada" and v["faltantes_factura"] == []
