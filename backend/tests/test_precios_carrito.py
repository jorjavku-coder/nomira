"""Precios públicos con carrito: solo si Nomira los publica; el servidor calcula todo (sin descuentos manuales); al
comprar se crea y envía una cotización formal con enlace para aceptarla y pagarla, y la persona entra a Ventas."""
import pytest
from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from app.services import correo
from app.services.comercial import base as cm


def publicar(valor="completos"):
    with SessionLocal() as db:
        cm.asegurar_catalogo(db)
        cm.config(db).precios_publicos = valor
        db.commit()


def paquete_id(cliente):
    return cliente.get("/api/precios").json()["paquetes"][0]["id"]


@pytest.fixture
def buzon(monkeypatch):
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "modo_prueba", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto, adjuntos=None: enviados.append({"para": dest, "adjuntos": adjuntos}))
    return enviados


def test_ocultos_no_se_publican(cliente):
    publicar("ocultos")
    assert cliente.get("/api/precios").status_code == 404
    assert cliente.get("/api/publico").json()["precios"] is False


def test_calculo_del_servidor_e_ignora_descuentos(cliente):
    publicar()
    assert cliente.get("/api/publico").json()["precios"] is True
    cat = cliente.get("/api/precios").json()
    assert cat["paquetes"] and any(x["precio_adicional"] for x in cat["modulos"])
    pid = cat["paquetes"][0]["id"]
    r = cliente.post("/api/precios/calcular", json={"paquete_id": pid, "modulos": ["agenda", "connect"], "usuarios_extra": 2,
                                                    "descuento": {"tipo": "porcentaje", "valor": "90", "motivo": "regalo"}}).json()
    assert r["descuento"] is None and float(r["total"]) > 0
    assert [x["incluido"] for x in r["modulos"]] == [True, False]  # Básico incluye 1
    assert cliente.post("/api/precios/calcular", json={"paquete_id": pid, "modulos": []}).status_code == 422
    assert cliente.post("/api/precios/calcular", json={"paquete_id": pid, "modulos": ["agenda"], "cupon": "NOEXISTE"}).status_code == 422


def test_comprar_crea_y_envia_la_cotizacion(cliente, buzon):
    publicar()
    pid = paquete_id(cliente)
    datos = {"paquete_id": pid, "modulos": ["agenda"], "contacto": "Lic. Ficticia", "despacho": "Despacho Ficticio", "email": "compra@despacho.test",
             "acepto": True}
    assert cliente.post("/api/precios/cotizar", json={**datos, "acepto": False}).status_code == 422
    r = cliente.post("/api/precios/cotizar", json=datos)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["folio"].startswith("COT-") and j["correo_enviado"] and "/propuesta#" in j["url"]
    assert buzon[-1]["para"] == ["compra@despacho.test"] and buzon[-1]["adjuntos"][0][0].endswith(".pdf")
    token = j["url"].split("#", 1)[1]
    p = cliente.post("/api/propuesta", headers={"X-Enlace": token})
    assert p.status_code == 200, p.text
    with SessionLocal() as db:
        c = db.scalar(select(m.CmCotizacion).where(m.CmCotizacion.folio == j["folio"]))
        assert c.estado in ("enviada", "vista") and c.creado_por_id is None
        assert db.scalar(select(m.VtContacto).where(m.VtContacto.email == "compra@despacho.test"))


def test_sin_correo_igual_entrega_el_enlace(cliente):
    publicar()
    r = cliente.post("/api/precios/cotizar", json={"paquete_id": paquete_id(cliente), "modulos": ["agenda"], "contacto": "Ana", "despacho": "Desp",
                                                   "email": "ana@desp.test", "acepto": True}).json()
    assert r["correo_enviado"] is False and r["url"]
