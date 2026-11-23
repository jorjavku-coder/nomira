"""Vigilancia de estrados digitales (TRIJAEM) en Nomira Agenda: expedientes vigilados, cotejo de la lista del día
(texto o PDF), consulta automática configurable, sin duplicados, avisos, paso al historial del asunto y aislamiento."""
import json
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


_CLIENTE_REAL = httpx.Client


def _tribunal(monkeypatch, responder):
    monkeypatch.setattr(est.httpx, "Client", lambda **kw: _CLIENTE_REAL(transport=httpx.MockTransport(responder), **kw))


def fila(**kw):
    return {"UNE": "922/2025", "fecha_acuerdo": "2026-11-05", "fecha_registro_ok": base.hoy().isoformat(), "id_acuerdo": "1577686",
            "no_expediente": "491/2026", "no_promocion": "811204", "nombreSala": "Tercera Sección de la Sala Superior Ecatepec de Morelos",
            "id_sala": "12", "TEJA": "https://trijaem.gob.mx/api/aws/doc.pdf", "nombreJuicio": "Recurso de Revisión", **kw}


def test_revision_automatica_trijaem(ag, buzon, monkeypatch):
    pedidas = []
    respuesta = {"data": [
        fila(),
        fila(id_acuerdo="1400000", fecha_registro_ok="2026-09-22", fecha_acuerdo="2026-09-20", no_promocion="700000"),  # antecedente
        fila(id_acuerdo="999", id_sala="4"),  # otra sala con el mismo número
        fila(id_acuerdo="998", no_expediente="777/2026"),
    ], "error": {"code": 0, "message": ""}}

    def responder(req: httpx.Request):
        pedidas.append((str(req.url), req.headers["content-type"], json.loads(req.content)))
        return httpx.Response(200, json=respuesta)

    _tribunal(monkeypatch, responder)
    a = asunto(ag)
    r = ag.c.put(f"{A}/asuntos/{a['id']}/vigilancia", headers=ag.h,
                 json={"expediente": "JA-0491/2026", "id_sala": "12", "promociones": ["811204", " 811204 ", ""]}).json()
    # al activarla se revisa de inmediato, con el formato exacto que usa la página del tribunal
    assert pedidas == [(est.URL_TRIJAEM, "application/x-www-form-urlencoded", {"no_expediente": "491/2026", "id_sala": "12"})]
    assert r["ultimo_estado"] == "ok" and r["sala"].startswith("Tercera Sección") and r["promociones"] == ["811204"]
    pubs = {p["promocion"]: p for p in ag.c.get(f"{A}/estrados", headers=ag.h).json()["publicaciones"]}
    assert set(pubs) == {"811204", "700000"}
    assert pubs["811204"]["vista"] is False and pubs["811204"]["de_mi_promocion"] and pubs["811204"]["enlace"].startswith("https://trijaem.gob.mx/")
    assert pubs["700000"]["vista"] is True  # lo de septiembre queda como antecedente, sin aviso
    assert pubs["811204"]["fecha_acuerdo"] == "2026-11-05" and "promoción 811204" in pubs["811204"]["descripcion"]
    assert buzon == []  # quien la activó ya lo está viendo
    # la ronda periódica no repite lo ya revisado y no duplica
    with SessionLocal() as db:
        assert est.ejecutar(db, datetime(2026, 11, 23, 10, tzinfo=base.ZONA), pausa=0)["revisadas"] == 0
        db.get(m.AgVigilancia, r["id"]).ultima_revision = None
        db.commit()
    respuesta["data"].append(fila(id_acuerdo="1600000", no_promocion="820000"))
    with SessionLocal() as db:
        assert est.ejecutar(db, datetime(2026, 11, 22, 10, tzinfo=base.ZONA), pausa=0)["revisadas"] == 0  # domingo
        assert est.ejecutar(db, datetime(2026, 11, 23, 10, tzinfo=base.ZONA), pausa=0) == {"revisadas": 1, "nuevas": 1, "correos": 1}
    assert buzon[0]["para"] == ["admin1@org1.test"] and "Exp. JA-0491/2026" in buzon[0]["texto"]


def test_sin_sala_o_apagada(ag, monkeypatch):
    _tribunal(monkeypatch, lambda r: pytest.fail("no debe consultar"))
    a = asunto(ag)
    v = vigilar(ag, a["id"], "491/2026", sala="Escrita a mano")
    assert ag.c.post(f"{A}/vigilancias/{v['id']}/revisar", headers=ag.h).status_code == 409
    assert ag.c.put(f"{A}/asuntos/{a['id']}/vigilancia", headers=ag.h, json={"expediente": "491/2026", "id_sala": "99"}).status_code == 422
    monkeypatch.setattr(ajustes(), "trijaem_estrados_activo", False)
    ag.c.put(f"{A}/asuntos/{a['id']}/vigilancia", headers=ag.h, json={"expediente": "491/2026", "id_sala": "1"})
    assert ag.c.get(f"{A}/estrados", headers=ag.h).json()["automatica"] is False
    with SessionLocal() as db:
        assert est.ejecutar(db, datetime(2026, 11, 23, 10, tzinfo=base.ZONA), pausa=0)["revisadas"] == 0


def test_error_del_tribunal_queda_registrado(ag, monkeypatch):
    _tribunal(monkeypatch, lambda r: httpx.Response(500, text=""))
    a = asunto(ag)
    v = ag.c.put(f"{A}/asuntos/{a['id']}/vigilancia", headers=ag.h, json={"expediente": "491/2026", "id_sala": "12"}).json()
    assert v["ultimo_estado"] == "error" and "500" in v["ultimo_error"]
    _tribunal(monkeypatch, lambda r: httpx.Response(200, text="<html>"))
    v = ag.c.post(f"{A}/vigilancias/{v['id']}/revisar", headers=ag.h).json()["vigilancia"]
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
