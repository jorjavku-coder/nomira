"""Vigilancia de estrados digitales (TRIJAEM) en Nomira Agenda: expedientes vigilados, cotejo de la lista del día
(texto o PDF), consulta automática configurable, sin duplicados, avisos, paso al historial del asunto y aislamiento."""
from datetime import date, datetime, timedelta

import httpx
import pymupdf
import pytest

from app import models as m
from app.config import ajustes
from app.db import SessionLocal
from app.services.agenda import base, estrados as est

from .test_agenda import A, ag, asunto, buzon  # noqa: F401
from .test_evidencia import activar

LISTA = """TRIBUNAL DE JUSTICIA ADMINISTRATIVA DEL ESTADO DE MÉXICO
Primera Sala Regional · Lista de acuerdos
1. JA-0123/2026  ACTOR: EMPRESA FICTICIA SA DE CV
   Se tiene por presentada la promoción y se da vista a la contraparte por tres días.
2. 999/2026  ACTOR: OTRA PERSONA
   Se admite la demanda.
"""


def vigilar(o, aid, expediente="123/2026", sala=None):
    r = o.c.put(f"{A}/asuntos/{aid}/vigilancia", headers=o.h, json={"expediente": expediente, "sala": sala})
    assert r.status_code == 200, r.text
    return r.json()


def test_clave_expediente():
    assert est.clave_expediente("JA-0123/2026") == (123, 2026) == est.clave_expediente("123 / 2026")
    assert est.clave_expediente("RA-45/2025-II") == (45, 2025)
    assert est.clave_expediente("sin número") is None and est.clave_expediente("12/26") is None
    assert est.misma_sala("Primera Sala Regional", "primera sala regional de Toluca") and est.misma_sala(None, "X")
    assert not est.misma_sala("Primera Sala", "Tercera Sala")


def test_vigilar_y_cotejar_lista(ag, buzon):
    a = asunto(ag)
    v = vigilar(ag, a["id"], "JA-123/2026")
    assert v["expediente"] == "JA-123/2026" and v["ultimo_estado"] == "pendiente"
    assert ag.c.get(f"{A}/asuntos/{a['id']}", headers=ag.h).json()["vigilancia"]["id"] == v["id"]
    assert ag.c.put(f"{A}/asuntos/{a['id']}/vigilancia", headers=ag.h, json={"expediente": "sin numero"}).status_code == 422

    hoy = base.hoy()
    r = ag.c.post(f"{A}/estrados/cotejar", headers=ag.h, json={"fecha": hoy.isoformat(), "texto": LISTA}).json()
    assert r["encontrados"] == 1 and len(r["nuevas"]) == 1 and r["revisados"] == 1
    p = r["nuevas"][0]
    assert "da vista a la contraparte" in p["descripcion"] and "999/2026" not in p["descripcion"] and p["origen"] == "manual" and p["surte_efectos"] > hoy.isoformat()
    # pegar la misma lista no duplica
    r2 = ag.c.post(f"{A}/estrados/cotejar", headers=ag.h, json={"fecha": hoy.isoformat(), "texto": LISTA}).json()
    assert r2["nuevas"] == [] and r2["ya_registradas"] == 1
    # quien coteja ya está enterado: no se le manda correo a sí mismo
    assert buzon == []
    # pasar al historial del asunto como notificación por estrados
    x = ag.c.post(f"{A}/publicaciones/{p['id']}/actuacion", headers=ag.h).json()
    act = ag.c.get(f"{A}/asuntos/{a['id']}", headers=ag.h).json()["actuaciones"]
    assert act[0]["id"] == x["actuacion_id"] and act[0]["tipo"] == "notificacion" and act[0]["notificada_en"] == hoy.isoformat()
    assert ag.c.post(f"{A}/publicaciones/{p['id']}/actuacion", headers=ag.h).status_code == 409


def test_sala_distinta_no_coincide(ag):
    a = asunto(ag)
    vigilar(ag, a["id"], "123/2026", sala="Tercera Sala Regional")
    r = ag.c.post(f"{A}/estrados/cotejar", headers=ag.h, json={"fecha": base.hoy().isoformat(), "texto": LISTA, "sala": "Primera Sala Regional"}).json()
    assert r["encontrados"] == 0
    r = ag.c.post(f"{A}/estrados/cotejar", headers=ag.h, json={"fecha": base.hoy().isoformat(), "texto": LISTA, "sala": "Tercera Sala Regional"}).json()
    assert r["encontrados"] == 1


def test_cotejar_pdf(ag):
    a = asunto(ag)
    vigilar(ag, a["id"])
    doc = pymupdf.open()
    pag = doc.new_page()
    y = 72
    for ln in LISTA.splitlines():
        pag.insert_text((50, y), ln.replace("É", "E"), fontsize=9)
        y += 14
    pdf = doc.tobytes()
    r = ag.c.post(f"{A}/estrados/cotejar-pdf", headers=ag.h, files={"archivo": ("lista.pdf", pdf, "application/pdf")},
                  data={"fecha": base.hoy().isoformat()})
    assert r.status_code == 200, r.text
    assert r.json()["encontrados"] == 1
    assert ag.c.post(f"{A}/estrados/cotejar-pdf", headers=ag.h, files={"archivo": ("x.pdf", b"hola", "application/pdf")},
                     data={"fecha": base.hoy().isoformat()}).status_code == 422


def test_aviso_al_responsable_y_vistas(ag, buzon):
    a = asunto(ag)
    vig = vigilar(ag, a["id"])
    hab = ag.usuario("analista", "abogada@org1.test")
    yo2 = ag.c.get(f"{A}/catalogos", headers=hab).json()["yo"]
    ag.c.patch(f"{A}/asuntos/{a['id']}", headers=ag.h, json={**{k: a[k] for k in ("titulo", "numero", "materia", "tribunal", "jurisdiccion")}, "responsable_id": yo2})
    p = ag.c.post(f"{A}/vigilancias/{vig['id']}/publicaciones", headers=ag.h,
                  json={"fecha_publicacion": base.hoy().isoformat(), "descripcion": "Acuerdo que requiere al actor."})
    assert p.status_code == 201, p.text
    assert [c["para"] for c in buzon] == [["abogada@org1.test"]]
    assert "Acuerdo que requiere" not in buzon[0]["texto"]  # el correo no lleva el contenido del acuerdo
    assert ag.c.get(f"{A}/estrados", headers=hab).json()["sin_ver"] == 1
    assert ag.c.get(f"{A}/contador", headers=hab).json()["total"] >= 1
    ag.c.post(f"{A}/publicaciones/{p.json()['id']}/vista", headers=hab)
    assert ag.c.get(f"{A}/estrados", headers=hab).json()["sin_ver"] == 0
    assert ag.c.post(f"{A}/vigilancias/{vig['id']}/publicaciones", headers=ag.h,
                     json={"fecha_publicacion": (base.hoy() + timedelta(days=2)).isoformat(), "descripcion": "Futuro"}).status_code == 422


def test_consulta_automatica_configurable(ag, buzon, monkeypatch):
    a = asunto(ag)
    vig = vigilar(ag, a["id"], "123/2026", sala="Primera Sala Regional")
    # sin configurar: se dice claramente y el proceso no hace nada
    assert ag.c.post(f"{A}/vigilancias/{vig['id']}/revisar", headers=ag.h).status_code == 409
    assert ag.c.get(f"{A}/estrados", headers=ag.h).json()["automatica"] is False
    with SessionLocal() as db:
        assert est.ejecutar(db, datetime(2026, 11, 23, 10, tzinfo=base.ZONA), pausa=0)["revisadas"] == 0

    pedidas = []

    def responder(req: httpx.Request):
        pedidas.append(str(req.url))
        return httpx.Response(200, json={"data": [
            {"numeroExpediente": "123/2026", "sala": "Primera Sala Regional", "fechaPublicacion": "20/11/2026", "sintesis": "Se fija fecha de audiencia."},
            {"numeroExpediente": "123/2026", "sala": "Cuarta Sala Regional", "fechaPublicacion": "20/11/2026", "sintesis": "Otro juicio con el mismo número."},
            {"numeroExpediente": "777/2026", "fechaPublicacion": "20/11/2026", "sintesis": "Otro expediente."}]})

    real = httpx.Client
    monkeypatch.setattr(est.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(responder), **kw))
    monkeypatch.setattr(ajustes(), "trijaem_estrados_api", "https://evil.example/api?e={expediente}")
    assert ag.c.post(f"{A}/vigilancias/{vig['id']}/revisar", headers=ag.h).json()["vigilancia"]["ultimo_estado"] == "sin_conexion"
    assert pedidas == []  # a otra dirección nunca se le pregunta
    with SessionLocal() as db:
        db.get(m.AgVigilancia, vig["id"]).ultima_revision = None
        db.commit()
    monkeypatch.setattr(ajustes(), "trijaem_estrados_api", "https://trijaem.gob.mx/servicios/api/estrados?expediente={expediente}")
    # fuera de horario (domingo) no consulta
    with SessionLocal() as db:
        assert est.ejecutar(db, datetime(2026, 11, 22, 10, tzinfo=base.ZONA), pausa=0)["revisadas"] == 0
    with SessionLocal() as db:
        r = est.ejecutar(db, datetime(2026, 11, 23, 10, tzinfo=base.ZONA), pausa=0)
    assert r == {"revisadas": 1, "nuevas": 1, "correos": 1}
    assert pedidas == ["https://trijaem.gob.mx/servicios/api/estrados?expediente=123%2F2026"]
    pubs = ag.c.get(f"{A}/estrados", headers=ag.h).json()["publicaciones"]
    assert [p["descripcion"] for p in pubs] == ["Se fija fecha de audiencia."] and pubs[0]["fecha_publicacion"] == "2026-11-20"
    # recién revisado: la siguiente ronda no lo vuelve a consultar; si se fuerza, no duplica
    with SessionLocal() as db:
        assert est.ejecutar(db, datetime(2026, 11, 23, 10, tzinfo=base.ZONA), pausa=0)["revisadas"] == 0
    assert ag.c.post(f"{A}/vigilancias/{vig['id']}/revisar", headers=ag.h).json()["nuevas"] == 0


def test_error_del_tribunal_queda_registrado(ag, monkeypatch):
    a = asunto(ag)
    vig = vigilar(ag, a["id"])
    real = httpx.Client
    monkeypatch.setattr(est.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>")), **kw))
    monkeypatch.setattr(ajustes(), "trijaem_estrados_api", "https://trijaem.gob.mx/x?e={expediente}")
    v = ag.c.post(f"{A}/vigilancias/{vig['id']}/revisar", headers=ag.h).json()["vigilancia"]
    assert v["ultimo_estado"] == "error" and "formato" in v["ultimo_error"]


def test_aislamiento_y_roles(ag, org2, plataforma):
    activar(plataforma, org2, "agenda")
    a = asunto(ag)
    vig = vigilar(ag, a["id"])
    p = ag.c.post(f"{A}/vigilancias/{vig['id']}/publicaciones", headers=ag.h, json={"fecha_publicacion": base.hoy().isoformat(), "descripcion": "Acuerdo."}).json()
    assert org2.c.put(f"{A}/asuntos/{a['id']}/vigilancia", headers=org2.h, json={"expediente": "1/2026"}).status_code == 404
    assert org2.c.post(f"{A}/publicaciones/{p['id']}/vista", headers=org2.h).status_code == 404
    assert org2.c.delete(f"{A}/vigilancias/{vig['id']}", headers=org2.h).status_code == 404
    assert org2.c.get(f"{A}/estrados", headers=org2.h).json()["publicaciones"] == []
    # org2 pega una lista con el mismo número: no toca al otro despacho
    assert org2.c.post(f"{A}/estrados/cotejar", headers=org2.h, json={"fecha": base.hoy().isoformat(), "texto": LISTA}).status_code == 409
    hc = ag.usuario("consulta", "consulta@org1.test")
    assert ag.c.post(f"{A}/estrados/cotejar", headers=hc, json={"fecha": base.hoy().isoformat(), "texto": LISTA}).status_code == 403
    assert ag.c.get(f"{A}/estrados", headers=hc).status_code == 200
    assert ag.c.delete(f"{A}/vigilancias/{vig['id']}", headers=ag.h).json() == {"ok": True}
