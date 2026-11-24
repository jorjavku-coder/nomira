"""Registro en línea con prueba gratuita de 7 días (hasta 3 módulos), confirmación por código, entrar con Google,
recuperar contraseña y bloqueo al terminar la prueba (solo cuentas de registro; los datos se conservan)."""
import re
from datetime import timedelta
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from app import models as m
from app.config import ajustes
from app.routers import acceso
from app.services import correo
from app.services import suscripciones as sus

A = "/api/auth"


@pytest.fixture
def buzon(monkeypatch):
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "modo_prueba", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto, adjuntos=None: enviados.append({"para": dest, "asunto": asunto, "texto": texto}))
    return enviados


def codigo(buzon):
    return re.search(r"\b(\d{6})\b", buzon[-1]["texto"]).group(1)


DATOS = {"organizacion": "Despacho Prueba Ficticio", "nombre": "Lic. Laura Ficticia", "email": "laura@despacho-prueba.test",
         "telefono": "55 1111 2222", "contrasena": "Contrasena-Segura-9", "modulos": ["nomina", "agenda", "leads"], "acepto": True}


def registrar(cliente, buzon, **kw):
    r = cliente.post(f"{A}/registro", json={**DATOS, **kw})
    assert r.status_code == 200, r.text
    v = cliente.post(f"{A}/registro/verificar", json={"reto": r.json()["reto"], "codigo": codigo(buzon)})
    assert v.status_code == 201, v.text
    return v.json()


def test_registro_con_correo_y_prueba(cliente, buzon, db):
    assert cliente.post(f"{A}/registro", json={**DATOS, "modulos": ["nomina", "agenda", "leads", "afore"]}).status_code == 422
    assert cliente.post(f"{A}/registro", json={**DATOS, "modulos": []}).status_code == 422
    assert cliente.post(f"{A}/registro", json={**DATOS, "acepto": False}).status_code == 422
    r = cliente.post(f"{A}/registro", json=DATOS).json()
    assert buzon[-1]["para"] == [DATOS["email"]] and "Confirme su correo" in buzon[-1]["asunto"]
    assert db.query(m.Usuario).filter_by(email=DATOS["email"]).count() == 0  # nada se guarda antes de confirmar
    # el reto no sirve como sesión ni revela el código
    assert cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {r['reto']}"}).status_code == 401
    assert codigo(buzon) not in r["reto"]
    assert cliente.post(f"{A}/registro/verificar", json={"reto": r["reto"], "codigo": "000000" if codigo(buzon) != "000000" else "111111"}).status_code == 401
    s = cliente.post(f"{A}/registro/verificar", json={"reto": r["reto"], "codigo": codigo(buzon)})
    assert s.status_code == 201, s.text
    s = s.json()
    assert sorted(s["modulos"]) == ["agenda", "leads", "nomina"]
    assert s["prueba"]["estado"] == "prueba" and s["prueba"]["dias_restantes"] == 7 and not s["prueba"]["bloqueada"]
    assert "Bienvenido a Nomira" in buzon[-1]["asunto"]
    h = {"Authorization": f"Bearer {s['token']}"}
    assert cliente.get("/api/agenda/asuntos", headers=h).status_code == 200
    assert cliente.get("/api/afore/casos", headers=h).status_code == 403  # no lo eligió
    org = db.get(m.Organizacion, s["usuario"]["organizacion_id"])
    assert org.origen == "registro" and org.modulos_prueba == ["nomina", "agenda", "leads"]
    sol = db.query(m.Solicitud).filter_by(email=DATOS["email"]).one()
    assert sol.tipo == "prueba" and "Agenda" in sol.mensaje
    ct = db.query(m.VtContacto).filter_by(email=DATOS["email"]).one()
    assert ct.fase == "mql" and ct.origen == "prueba"
    # el mismo correo no se registra dos veces
    assert cliente.post(f"{A}/registro", json=DATOS).status_code == 409
    # y entra con su contraseña
    assert cliente.post(f"{A}/login", json={"email": DATOS["email"], "contrasena": DATOS["contrasena"]}).status_code == 200


def test_fin_de_la_prueba_bloquea_sin_borrar(cliente, buzon, db, org):
    s = registrar(cliente, buzon)
    h = {"Authorization": f"Bearer {s['token']}"}
    p = db.query(m.PeriodoSuscripcion).filter_by(organizacion_id=s["usuario"]["organizacion_id"]).one()
    p.inicio, p.fin = sus.hoy() - timedelta(days=10), sus.hoy() - timedelta(days=3)
    db.commit()
    r = cliente.get("/api/agenda/asuntos", headers=h)
    assert r.status_code == 402 and r.json()["detail"]["codigo"] == "prueba_terminada"
    yo = cliente.get(f"{A}/yo", headers=h).json()
    assert yo["prueba"]["bloqueada"] and yo["prueba"]["estado"] == "vencida"
    c = cliente.post(f"{A}/prueba/contratar", headers=h, json={"mensaje": "Queremos el plan Medio"})
    assert c.status_code == 200
    assert db.query(m.Solicitud).filter_by(email=DATOS["email"], tipo="suscripcion").count() == 1
    # al registrar un plan pagado vuelve a funcionar
    db.add(m.PeriodoSuscripcion(organizacion_id=s["usuario"]["organizacion_id"], plan="mensual", inicio=sus.hoy(),
                                fin=sus.calcular_fin("mensual", sus.hoy()), pagado=True))
    db.commit()
    assert cliente.get("/api/agenda/asuntos", headers=h).status_code == 200
    # las cuentas que da de alta Nomira (sin periodos) no se bloquean
    assert cliente.get("/api/expedientes", headers=org.h).status_code == 200


def test_recuperar_contrasena(cliente, buzon, org):
    n = len(buzon)
    r = cliente.post(f"{A}/recuperar", json={"email": "nadie@nada.test"})
    assert r.status_code == 200 and len(buzon) == n  # misma respuesta, sin correo
    falso = r.json()["reto"]
    assert cliente.post(f"{A}/recuperar/cambiar", json={"reto": falso, "codigo": "123456", "nueva": "Otra-Contrasena-1"}).status_code == 401
    r = cliente.post(f"{A}/recuperar", json={"email": "admin1@org1.test"}).json()
    assert "Restablezca" in buzon[-1]["asunto"]
    ok = cliente.post(f"{A}/recuperar/cambiar", json={"reto": r["reto"], "codigo": codigo(buzon), "nueva": "Nueva-Contrasena-77"})
    assert ok.status_code == 200, ok.text
    assert cliente.get("/api/expedientes", headers=org.h).status_code == 401  # cerró las sesiones abiertas
    assert cliente.post(f"{A}/login", json={"email": "admin1@org1.test", "contrasena": "Contrasena-Segura-1"}).status_code == 401
    assert cliente.post(f"{A}/login", json={"email": "admin1@org1.test", "contrasena": "Nueva-Contrasena-77"}).status_code == 200
    # el mismo código no sirve dos veces (la sesión cambió de versión)
    assert cliente.post(f"{A}/recuperar/cambiar", json={"reto": r["reto"], "codigo": codigo(buzon), "nueva": "Otra-Mas-12345"}).status_code == 401


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(ajustes(), "google_client_id", "cliente-ficticio.apps.googleusercontent.com")
    monkeypatch.setattr(ajustes(), "google_client_secret", "secreto-ficticio")
    monkeypatch.setattr(ajustes(), "url_publica", "https://nomirasoft.com")
    identidad = {"email": "pedro@gmail.test", "sub": "1234567890", "name": "Pedro Google Ficticio"}
    monkeypatch.setattr(acceso, "_identidad", lambda code: {**identidad, "email_verified": True})
    return identidad


def _por_google(cliente, modo="entrar"):
    r = cliente.get(f"{A}/google/inicio?modo={modo}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("https://accounts.google.com/")
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["redirect_uri"] == ["https://nomirasoft.com/api/auth/google/callback"] and q["scope"] == ["openid email profile"]
    cb = cliente.get(f"{A}/google/callback", params={"code": "c", "state": q["state"][0]}, follow_redirects=False)
    assert cb.status_code == 303
    frag = cb.headers["location"].split("#", 1)[1]
    clave, valor = frag.split("=", 1)
    return clave, unquote(valor)


def test_google_registro_y_entrada(cliente, google, db, org):
    assert cliente.get("/api/publico").json()["google"] is True
    # sin la cookie del inicio, el callback no acepta el estado (protección CSRF)
    r = cliente.get(f"{A}/google/inicio", follow_redirects=False)
    estado = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    cliente.cookies.clear()
    cb = cliente.get(f"{A}/google/callback", params={"code": "c", "state": estado}, follow_redirects=False)
    assert "google_error=vencido" in cb.headers["location"]
    clave, token = _por_google(cliente, "registro")
    assert clave == "registro_google"
    assert cliente.post(f"{A}/registro/google", json={"token": token, "organizacion": "Bufete Google", "modulos": ["a", "b", "c", "d"], "acepto": True}).status_code == 422
    s = cliente.post(f"{A}/registro/google", json={"token": token, "organizacion": "Bufete Google", "modulos": ["escrituracion"], "acepto": True})
    assert s.status_code == 201, s.text
    assert s.json()["modulos"] == ["escrituracion"] and s.json()["usuario"]["email"] == "pedro@gmail.test"
    # la cuenta de Google no tiene contraseña: con contraseña no entra
    assert cliente.post(f"{A}/login", json={"email": "pedro@gmail.test", "contrasena": "!google"}).status_code == 401
    clave, pase = _por_google(cliente)
    assert clave == "google"
    e = cliente.post(f"{A}/google/canjear", json={"pase": pase})
    assert e.status_code == 200 and e.json()["usuario"]["email"] == "pedro@gmail.test"
    # un usuario que ya existía con ese correo queda vinculado al entrar con Google
    google["email"], google["sub"] = "admin1@org1.test", "999"
    clave, pase = _por_google(cliente)
    assert clave == "google" and cliente.post(f"{A}/google/canjear", json={"pase": pase}).json()["usuario"]["email"] == "admin1@org1.test"
    assert db.query(m.Usuario).filter_by(email="admin1@org1.test").one().google_sub == "999"
    # otra cuenta de Google con el mismo correo no entra
    google["sub"] = "otro"
    assert _por_google(cliente)[0] == "google_error"


def test_registro_cerrado(cliente, plataforma, buzon, db):
    plataforma.c.get("/api/plataforma/comercial/catalogo", headers=plataforma.h)  # crea la configuración comercial
    c = db.query(m.CmConfig).one()
    c.registro_prueba = False
    db.commit()
    assert cliente.post(f"{A}/registro", json=DATOS).status_code == 403
    assert cliente.get("/api/publico").json()["permitir_registro"] is False
