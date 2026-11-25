"""Compra directa de módulos: en prueba se encienden gratis; fuera de prueba, Stripe con cargo mensual y el módulo
se enciende solo con el pago confirmado por webhook (importe exacto). Cancelación definitiva apaga sin borrar."""
import hashlib
import hmac
import json
import time
from datetime import date, timedelta

import pytest

from app import models as m
from app.config import ajustes
from app.services import modulos
from app.services.comercial import stripe as st


def _firmar(cuerpo: bytes) -> str:
    t = int(time.time())
    return f"t={t},v1=" + hmac.new(b"whsec_prueba", f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()


def _evento(cliente, tipo: str, obj: dict, eid: str):
    cuerpo = json.dumps({"id": eid, "type": tipo, "livemode": False, "data": {"object": obj}}).encode()
    return cliente.post("/api/comercial/stripe/webhook", content=cuerpo, headers={"Stripe-Signature": _firmar(cuerpo)})


@pytest.fixture
def stripe_prueba(monkeypatch):
    monkeypatch.setattr(ajustes(), "stripe_secret_key", "sk_test_123")
    monkeypatch.setattr(ajustes(), "stripe_webhook_secret", "whsec_prueba")
    monkeypatch.setattr(ajustes(), "stripe_modo", "prueba")
    llamadas = []
    monkeypatch.setattr(st, "crear_suscripcion", lambda **kw: llamadas.append(kw) or {"id": f"cs_test_{len(llamadas)}", "url": "https://checkout.stripe.test/x"})
    monkeypatch.setattr(st, "cancelar_al_final", lambda sid: llamadas.append({"cancelar": sid}) or {})
    return llamadas


def test_tienda_y_compra_con_webhook(org, cliente, stripe_prueba, db):
    t = org.c.get("/api/organizacion/modulos/tienda", headers=org.h).json()
    rh = next(x for x in t["modulos"] if x["clave"] == "rh")
    assert rh["activo"] is False and rh["precio"] == "590.00" and rh["total"] == "684.40" and t["es_admin"] and not t["en_prueba"]
    r = org.c.post("/api/organizacion/modulos/rh/contratar", headers=org.h, json={})
    assert r.status_code == 200 and r.json()["url"].startswith("https://checkout.stripe.test")
    kw = stripe_prueba[-1]
    assert str(kw["total_mensual"]) == "684.40"
    assert kw["metadata"]["tipo"] == "modulo" and kw["metadata"]["modulo"] == "rh"
    assert not modulos.estado(db, org.org_id)["rh"]["activo"]  # aún no se enciende sin pago
    # importe distinto: no se aplica
    _evento(cliente, "checkout.session.completed", {"id": "cs_test_1", "payment_status": "paid", "amount_total": 100, "currency": "mxn",
                                                    "subscription": "sub_1", "metadata": {"tipo": "modulo"}}, "evt_1")
    db.expire_all()
    assert not modulos.estado(db, org.org_id)["rh"]["activo"]
    # pago correcto: se enciende
    _evento(cliente, "checkout.session.completed", {"id": "cs_test_1", "payment_status": "paid", "amount_total": 68440, "currency": "mxn",
                                                    "subscription": "sub_1", "metadata": {"tipo": "modulo"}}, "evt_2")
    db.expire_all()
    assert modulos.estado(db, org.org_id)["rh"]["activo"]
    t = org.c.get("/api/organizacion/modulos/tienda", headers=org.h).json()
    assert next(x for x in t["modulos"] if x["clave"] == "rh")["suscripcion"]["estado"] == "activa"
    assert org.c.post("/api/organizacion/modulos/rh/contratar", headers=org.h, json={}).json()["activado"]  # ya contratado: solo enciende
    # cobro fallido y luego cancelación definitiva de Stripe: se apaga
    _evento(cliente, "invoice.payment_failed", {"subscription": "sub_1"}, "evt_3")
    db.expire_all()
    assert db.query(m.MdSuscripcion).one().estado == "pago_fallido" and modulos.estado(db, org.org_id)["rh"]["activo"]
    _evento(cliente, "customer.subscription.deleted", {"id": "sub_1"}, "evt_4")
    db.expire_all()
    assert db.query(m.MdSuscripcion).one().estado == "cancelada" and not modulos.estado(db, org.org_id)["rh"]["contratado"]


def test_cancelar_desde_nomira(org, cliente, stripe_prueba, db):
    org.c.post("/api/organizacion/modulos/agenda/contratar", headers=org.h, json={})
    _evento(cliente, "checkout.session.completed", {"id": "cs_test_1", "payment_status": "paid", "amount_total": 103240, "currency": "mxn",
                                                    "subscription": "sub_9", "metadata": {"tipo": "modulo"}}, "evt_a")
    r = org.c.post("/api/organizacion/modulos/agenda/cancelar", headers=org.h, json={})
    assert r.status_code == 200 and stripe_prueba[-1] == {"cancelar": "sub_9"}
    db.expire_all()
    assert db.query(m.MdSuscripcion).one().estado == "cancelando" and modulos.estado(db, org.org_id)["agenda"]["activo"]


def test_en_prueba_se_enciende_gratis(org, stripe_prueba, db):
    o = db.get(m.Organizacion, org.org_id)
    o.origen = "registro"
    db.add(m.PeriodoSuscripcion(organizacion_id=o.id, plan="prueba", inicio=date.today(), fin=date.today() + timedelta(days=1)))
    db.commit()
    r = org.c.post("/api/organizacion/modulos/leads/contratar", headers=org.h, json={}).json()
    assert r == {"activado": True, "en_prueba": True} and not stripe_prueba
    db.expire_all()
    assert modulos.estado(db, org.org_id)["leads"]["activo"] and "leads" in db.get(m.Organizacion, org.org_id).modulos_prueba


def test_solo_administrador(org, cliente, db):
    from app.security import hash_contrasena
    db.add(m.Usuario(organizacion_id=org.org_id, email="consulta@x.test", nombre="Consulta", hash_contrasena=hash_contrasena("Clave-de-prueba-123"), rol="consulta"))
    db.commit()
    t = cliente.post("/api/auth/login", json={"email": "consulta@x.test", "contrasena": "Clave-de-prueba-123"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    assert cliente.get("/api/organizacion/modulos/tienda", headers=h).json()["es_admin"] is False
    assert cliente.post("/api/organizacion/modulos/rh/contratar", headers=h, json={}).status_code == 403
