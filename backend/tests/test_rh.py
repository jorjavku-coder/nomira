"""Recursos humanos: módulo de pago, empresas (propia y cliente), empleados, vacaciones LFT, incidencias, avisos con acuse,
documentos, nómina de control (faltas, prima vacacional, Excel, PDF), portal del empleado con NIP y aislamiento."""
from datetime import date, timedelta

import pymupdf
import pytest

from app import models as m
from app.services.rh import base as rb

from .test_evidencia import activar

R = "/api/rh"
P = "/api/portal-rh"


def pdf():
    d = pymupdf.open()
    d.new_page().insert_text((50, 72), "INE")
    return d.tobytes()


@pytest.fixture
def rh(org, plataforma):
    activar(plataforma, org, "rh")
    return org


def alta(o, empresa_id, **kw):
    datos = {"empresa_id": empresa_id, "nombre": "Ana Ejemplo Ruiz", "puesto": "Abogada", "fecha_ingreso": str(date.today() - timedelta(days=3 * 365 + 20)),
             "salario_diario": "800", "rfc": "EERA900101AB1", "curp": "EERA900101MDFJZN09", "nss": "12345678901", **kw}
    r = o.c.post(f"{R}/empleados", headers=o.h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()


def test_modulo_de_pago_y_vacaciones(org, plataforma):
    assert org.c.get(f"{R}/resumen", headers=org.h).status_code == 403
    activar(plataforma, org, "rh")
    res = org.c.get(f"{R}/resumen", headers=org.h).json()
    assert res["empresas"][0]["propia"] is True  # el despacho mismo
    assert [rb.dias_por_anio(n) for n in (1, 2, 5, 6, 10, 11, 16)] == [12, 14, 20, 22, 22, 24, 26]
    e = alta(org, res["empresas"][0]["id"])
    v = org.c.get(f"{R}/empleados/{e['id']}", headers=org.h).json()["vacaciones"]
    assert v["anios"] == 3 and v["derecho"] == 16 and v["disponibles"] == 16
    assert org.c.post(f"{R}/empleados", headers=org.h, json={**{"empresa_id": res["empresas"][0]["id"], "nombre": "X Y Z", "fecha_ingreso": "2024-01-01",
                                                                 "salario_diario": "1"}, "curp": "MAL"}).status_code == 422


def test_flujo_completo_portal(rh, org2, cliente, db):
    propia = rh.c.get(f"{R}/resumen", headers=rh.h).json()["empresas"][0]["id"]
    cli = rh.c.post(f"{R}/empresas", headers=rh.h, json={"nombre": "Comercializadora Cliente SA", "periodicidad": "quincenal"}).json()
    e = alta(rh, cli["id"])
    assert org2.c.get(f"{R}/empleados/{e['id']}", headers=org2.h).status_code in (403, 404)  # aislamiento (org2 sin módulo o sin acceso)
    # aviso para todas las empresas, con acuse
    av = rh.c.post(f"{R}/avisos", headers=rh.h, json={"titulo": "Día de asueto", "cuerpo": "El lunes no se labora.", "requiere_acuse": True}).json()
    assert av["destinatarios"] == 1 and av["leidos"] == 0
    # portal
    acceso = rh.c.post(f"{R}/empleados/{e['id']}/portal", headers=rh.h).json()
    token, nip = acceso["url"].rsplit("/", 1)[1], acceso["nip"]
    assert len(nip) == 6 and db.get(m.RhEmpleado, e["id"]).portal_nip_hash != nip
    assert cliente.get(f"{P}/acceso/{token}").json()["nombre"] == "Ana"
    assert cliente.post(f"{P}/acceso/{token}/entrar", json={"nip": "000000" if nip != "000000" else "111111"}).status_code == 401
    ses = cliente.post(f"{P}/acceso/{token}/entrar", json={"nip": nip}).json()["sesion"]
    hp = {"Authorization": f"Bearer {ses}"}
    assert cliente.get("/api/organizacion", headers=hp).status_code == 401  # la sesión del portal no sirve en Nomira
    yo = cliente.get(f"{P}/yo", headers=hp).json()
    assert yo["empresa"] == "Comercializadora Cliente SA" and yo["avisos"][0]["requiere_acuse"] and not yo["avisos"][0]["leido"]
    assert {f["tipo"] for f in yo["faltantes"]} >= {"ine", "curp"}
    cliente.post(f"{P}/avisos/{av['id']}/acuse", headers=hp)
    cliente.post(f"{P}/avisos/{av['id']}/acuse", headers=hp)  # dos veces no duplica
    assert rh.c.get(f"{R}/avisos", headers=rh.h).json()["avisos"][0]["leidos"] == 1
    # solicitud de vacaciones (lunes a miércoles de la próxima semana: 3 días hábiles)
    lunes = date.today() + timedelta(days=7 - date.today().weekday())
    s = cliente.post(f"{P}/solicitudes", headers=hp, data={"tipo": "vacaciones", "desde": str(lunes), "hasta": str(lunes + timedelta(days=2))})
    assert s.status_code == 201 and s.json()["dias"] == 3 and s.json()["estado"] == "pendiente"
    assert cliente.post(f"{P}/solicitudes", headers=hp, data={"tipo": "vacaciones", "desde": str(lunes), "hasta": str(lunes + timedelta(days=60))}).status_code == 422
    assert cliente.post(f"{P}/solicitudes", headers=hp, data={"tipo": "falta", "desde": str(lunes), "hasta": str(lunes)}).status_code == 422
    pend = rh.c.get(f"{R}/incidencias", headers=rh.h).json()["incidencias"]
    assert len(pend) == 1 and pend[0]["empleado"] == "Ana Ejemplo Ruiz"
    assert rh.c.post(f"{R}/incidencias/{pend[0]['id']}/resolver", headers=rh.h, json={"aprobar": False}).status_code == 422  # rechazo sin motivo
    rh.c.post(f"{R}/incidencias/{pend[0]['id']}/resolver", headers=rh.h, json={"aprobar": True})
    assert rh.c.get(f"{R}/empleados/{e['id']}", headers=rh.h).json()["vacaciones"]["disponibles"] == 13
    # documento desde el portal queda por revisar; RH lo acepta
    d = cliente.post(f"{P}/documentos", headers=hp, data={"tipo": "ine"}, files={"archivo": ("ine.pdf", pdf(), "application/pdf")})
    assert d.status_code == 201 and d.json()["estado"] == "por_revisar"
    assert cliente.post(f"{P}/documentos", headers=hp, data={"tipo": "ine"}, files={"archivo": ("x.exe", b"MZ", "application/x")}).status_code == 422
    rh.c.post(f"{R}/documentos/{d.json()['id']}/revisar", headers=rh.h, json={"aceptar": True})
    assert "ine" not in rh.c.get(f"{R}/empleados/{e['id']}", headers=rh.h).json()["faltantes"]
    # nómina: periodo con una falta y las vacaciones aprobadas
    rh.c.post(f"{R}/empleados/{e['id']}/incidencias", headers=rh.h, json={"tipo": "falta", "desde": str(lunes + timedelta(days=3)), "hasta": str(lunes + timedelta(days=3))})
    per = rh.c.post(f"{R}/periodos", headers=rh.h, json={"empresa_id": cli["id"], "inicio": str(lunes), "fin": str(lunes + timedelta(days=14)),
                                                          "fecha_pago": str(lunes + timedelta(days=14))})
    assert per.status_code == 201, per.text
    rec = per.json()["recibos"][0]
    assert rec["faltas"] == 1 and rec["dias_pagados"] == 14
    assert rec["percepciones"][0] == {"concepto": "Sueldo", "importe": "11200.00"}
    assert rec["percepciones"][1]["concepto"].startswith("Prima vacacional") and rec["percepciones"][1]["importe"] == "600.00"  # 800 × 3 × 25 %
    assert rh.c.post(f"{R}/periodos", headers=rh.h, json={"empresa_id": cli["id"], "inicio": str(lunes), "fin": str(lunes + timedelta(days=5)),
                                                          "fecha_pago": str(lunes)}).status_code == 409  # se cruza
    r = rh.c.put(f"{R}/recibos/{rec['id']}", headers=rh.h, json={"percepciones": rec["percepciones"] + [{"concepto": "Bono", "importe": "500"}],
                                                                 "deducciones": [{"concepto": "ISR retenido", "importe": "1200"}]})
    assert r.json()["neto"] == "11100.00"
    assert cliente.get(f"{P}/yo", headers=hp).json()["recibos"] == []  # en borrador no lo ve el empleado
    rh.c.post(f"{R}/periodos/{per.json()['id']}/cerrar", headers=rh.h)
    assert rh.c.put(f"{R}/recibos/{rec['id']}", headers=rh.h, json={"percepciones": [], "deducciones": []}).status_code == 409
    recibos = cliente.get(f"{P}/yo", headers=hp).json()["recibos"]
    assert recibos[0]["neto"] == "11100.00"
    pdf_r = cliente.get(f"{P}/recibos/{recibos[0]['id']}/pdf", headers=hp)
    with pymupdf.open(stream=pdf_r.content, filetype="pdf") as doc:
        t = "".join(p.get_text() for p in doc)
    assert "Ana Ejemplo Ruiz" in t and "11,100.00" in t and "No es un comprobante" in t
    xl = rh.c.get(f"{R}/periodos/{per.json()['id']}/excel", headers=rh.h)
    assert xl.status_code == 200 and xl.content[:2] == b"PK"
    # baja: corta el portal
    rh.c.post(f"{R}/empleados/{e['id']}/baja", headers=rh.h, json={"fecha": str(date.today()), "motivo": "Renuncia voluntaria"})
    assert cliente.get(f"{P}/yo", headers=hp).status_code == 401 and cliente.get(f"{P}/acceso/{token}").status_code == 404
    aud = db.query(m.Auditoria).filter(m.Auditoria.accion.like("rh_%")).all()
    assert not any("Ana" in str(a.detalle) or "11100" in str(a.detalle) for a in aud)  # bitácora sin datos personales ni importes
    assert propia != cli["id"]


def test_nip_con_freno(rh, cliente):
    e = alta(rh, rh.c.get(f"{R}/resumen", headers=rh.h).json()["empresas"][0]["id"], nombre="Luis Prueba Freno")
    token = rh.c.post(f"{R}/empleados/{e['id']}/portal", headers=rh.h).json()["url"].rsplit("/", 1)[1]
    codigos = [cliente.post(f"{P}/acceso/{token}/entrar", json={"nip": "999999x"}).status_code for _ in range(7)]
    assert codigos[:5] == [401] * 5 and codigos[-1] == 429  # tras 5 NIP equivocados se bloquea 15 minutos
