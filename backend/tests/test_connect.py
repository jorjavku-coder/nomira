"""Nomira Connect (fase 1): plantillas, seguimiento por etapas, portal del cliente y mensajes.

Criterios de aceptación cubiertos: un cliente nunca ve asuntos de otro cliente ni de otro despacho; una nota
privada nunca sale al portal; un cambio de etapa queda en la bitácora; personalizar las etapas de un asunto no
afecta la plantilla ni otros asuntos; el cliente puede pedir atención humana; el módulo se respeta."""
import re

import pytest
from sqlalchemy import select

from app import models as m
from app.db import SessionLocal

from .test_agenda import buzon  # noqa: F401
from .test_evidencia import activar

C = "/api/connect"
P = "/api/mi-portal"
SECRETO = "ESTRATEGIA-INTERNA-SECRETA"


@pytest.fixture
def cn(org, plataforma):
    activar(plataforma, org, "connect")
    return org


def cliente_dir(o, nombre="María Ficticia López", email="maria@cliente.test"):
    r = o.c.post("/api/clientes", headers=o.h, json={"nombre": nombre, "email": email, "telefono": "5512345678"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def seguimiento(o, cid, base="pensiones", titulo="Pensión ISSEMYM de María"):
    r = o.c.post(f"{C}/seguimientos", headers=o.h, json={"titulo": titulo, "numero": "456/2026", "cliente_id": cid, "materia": "seguridad_social",
                                                         "base": base})
    assert r.status_code == 201, r.text
    return o.c.get(f"{C}/seguimientos/{r.json()['id']}", headers=o.h).json()


def enlace(o, cid):
    r = o.c.post(f"{C}/clientes/{cid}/enlaces", headers=o.h, json={"dias": 30})
    assert r.status_code == 201, r.text
    return r.json()["url"].split("#")[1]


def entrar(o, token, buzon):
    e = o.c.post(f"{P}/estado", headers={"X-Enlace": token}).json()
    assert e["verificado"] is False and e["requiere_codigo"] is True
    assert o.c.post(f"{P}/codigo", headers={"X-Enlace": token}).status_code == 200
    cod = re.search(r"\b(\d{6})\b", buzon[-1]["texto"]).group(1)
    s = o.c.post(f"{P}/verificar", headers={"X-Enlace": token}, json={"codigo": cod}).json()["sesion"]
    return {"X-Enlace": token, "X-Sesion": s}


def test_modulo_requerido(org):
    assert org.c.get(f"{C}/resumen", headers=org.h).status_code == 403


def test_plantillas_de_fabrica(cn):
    p = cn.c.get(f"{C}/plantillas", headers=cn.h).json()
    claves = {b["clave"] for b in p["base"]}
    assert {"pensiones", "laboral", "familiar", "amparo", "notarial", "corporativo", "civil", "mercantil", "fiscal", "administrativo",
            "penal", "migratorio", "inmobiliario", "propiedad_intelectual"} <= claves
    assert all(e["explicacion"] for b in p["base"] for e in b["etapas"])


def test_flujo_completo_y_privacidad(cn, buzon):
    cid = cliente_dir(cn)
    s = seguimiento(cn, cid)
    assert s["etapas"][0]["estado"] == "actual" and all(e["estado"] == "pendiente" for e in s["etapas"][1:])
    assert s["visible_cliente"] is False
    token = enlace(cn, cid)
    h = entrar(cn, token, buzon)
    # sin publicar, el cliente no ve el asunto
    assert cn.c.post(f"{P}/estado", headers=h).json()["asuntos"] == []
    sid = s["id"]
    cn.c.put(f"{C}/seguimientos/{sid}", headers=cn.h, json={"visible_cliente": True, "mostrar_pagos": True})
    # mover a «Presentación de la demanda» con nota pública e interna
    etapa = next(e for e in s["etapas"] if e["nombre"] == "Presentación de la demanda")
    r = cn.c.post(f"{C}/seguimientos/{sid}/etapa", headers=cn.h, json={"etapa_id": etapa["id"], "estado": "actual",
                                                                       "nota_publica": "Presentamos su demanda el día de hoy.",
                                                                       "nota_interna": SECRETO})
    assert r.status_code == 200, r.text
    x = r.json()
    previas = [e for e in x["etapas"] if e["id"] != etapa["id"] and x["etapas"].index(e) < [y["id"] for y in x["etapas"]].index(etapa["id"])]
    assert all(e["estado"] == "completada" for e in previas)
    assert next(e for e in x["etapas"] if e["id"] == etapa["id"])["nota_interna"] == SECRETO  # el despacho sí la ve
    # el cliente ve la etapa actual, la nota pública y el historial; NUNCA la nota interna
    cn.c.post(f"{C}/seguimientos/{sid}/movimiento", headers=cn.h, json={"fecha": "2026-11-20", "texto": "El tribunal recibió la demanda."})
    v = cn.c.post(f"{P}/estado", headers=h)
    assert SECRETO not in v.text and "nota_interna" not in v.text
    a = v.json()["asuntos"][0]
    assert a["etapa_actual"]["nombre"] == "Presentación de la demanda" and a["etapa_actual"]["nota"] == "Presentamos su demanda el día de hoy."
    assert a["ultimo_movimiento"]["texto"] == "El tribunal recibió la demanda." and a["numero"] == "456/2026"
    assert any(t["titulo"] == "Nueva etapa: Presentación de la demanda" for t in a["historial"])
    assert "porcentaje" not in v.text and v.json()["pagos"] is not None
    # bitácora
    with SessionLocal() as db:
        assert db.scalar(select(m.Auditoria).where(m.Auditoria.accion == "cn_etapa_cambiada"))
    # revisión registrada distinta del último movimiento
    cn.c.post(f"{C}/seguimientos/{sid}/revisado", headers=cn.h)
    a = cn.c.post(f"{P}/estado", headers=h).json()["asuntos"][0]
    assert a["ultima_revision"] and a["ultimo_movimiento"]["fecha"] == "2026-11-20"


def test_aislamiento_entre_clientes_y_despachos(cn, org2, plataforma, buzon):
    ana, beto = cliente_dir(cn, "Ana Ficticia", "ana@c.test"), cliente_dir(cn, "Beto Ficticio", "beto@c.test")
    sa, sb = seguimiento(cn, ana, titulo="Asunto de Ana"), seguimiento(cn, beto, titulo="Asunto de Beto")
    for s in (sa, sb):
        cn.c.put(f"{C}/seguimientos/{s['id']}", headers=cn.h, json={"visible_cliente": True})
    h = entrar(cn, enlace(cn, ana), buzon)
    v = cn.c.post(f"{P}/estado", headers=h).json()
    assert [x["asunto"] for x in v["asuntos"]] == ["Asunto de Ana"] and "Beto" not in str(v)
    # no puede escribir sobre el asunto de otro cliente
    assert cn.c.post(f"{P}/mensajes", headers=h, json={"texto": "Hola", "asunto_id": sb["id"]}).status_code == 404
    # otro despacho no ve ni toca nada
    activar(plataforma, org2, "connect")
    assert org2.c.get(f"{C}/seguimientos/{sa['id']}", headers=org2.h).status_code == 404
    assert org2.c.post(f"{C}/clientes/{ana}/enlaces", headers=org2.h, json={}).status_code == 404
    assert org2.c.get(f"{C}/mensajes/{ana}", headers=org2.h).status_code == 404
    assert all(f["asunto"] not in ("Asunto de Ana", "Asunto de Beto") for f in org2.c.get(f"{C}/resumen", headers=org2.h).json()["asuntos"])
    # enlace revocado deja de funcionar
    acc = cn.c.get(f"{C}/clientes/{ana}/enlaces", headers=cn.h).json()["enlaces"][0]
    cn.c.post(f"{C}/enlaces/{acc['id']}/revocar", headers=cn.h)
    assert cn.c.post(f"{P}/estado", headers=h).status_code == 410


def test_codigo_obligatorio(cn, buzon):
    cid = cliente_dir(cn)
    token = enlace(cn, cid)
    assert cn.c.post(f"{P}/mensajes", headers={"X-Enlace": token}, json={"texto": "Hola"}).status_code == 401
    cn.c.post(f"{P}/codigo", headers={"X-Enlace": token})
    assert cn.c.post(f"{P}/verificar", headers={"X-Enlace": token}, json={"codigo": "000000"}).status_code == 422


def test_mensajes_y_atencion_humana(cn, buzon):
    cid = cliente_dir(cn)
    s = seguimiento(cn, cid)
    cn.c.put(f"{C}/seguimientos/{s['id']}", headers=cn.h, json={"visible_cliente": True})
    h = entrar(cn, enlace(cn, cid), buzon)
    r = cn.c.post(f"{P}/mensajes", headers=h, json={"texto": "¿Me pueden llamar mañana?", "motivo": "llamada", "asunto_id": s["id"]})
    assert r.status_code == 201, r.text
    # el despacho recibe aviso por correo SIN el texto del mensaje
    aviso = buzon[-1]
    assert "Mensaje nuevo" in aviso["asunto"] and "llamar mañana" not in aviso["texto"]
    b = cn.c.get(f"{C}/mensajes", headers=cn.h).json()
    assert b["hilos"][0]["nuevos"] == 1 and b["hilos"][0]["motivo"] == "Pide una llamada"
    assert cn.c.get(f"{C}/resumen", headers=cn.h).json()["mensajes_nuevos"] == 1
    hilo = cn.c.get(f"{C}/mensajes/{cid}", headers=cn.h).json()
    assert hilo["mensajes"][0]["asunto"] == "Pensión ISSEMYM de María"
    cn.c.post(f"{C}/mensajes/{cid}", headers=cn.h, json={"texto": "Claro, le llamamos a las 10."})
    assert cn.c.get(f"{C}/resumen", headers=cn.h).json()["mensajes_nuevos"] == 0
    v = cn.c.post(f"{P}/estado", headers=h).json()
    assert v["mensajes"][-1]["autor"] == "despacho" and v["mensajes"][-1]["texto"] == "Claro, le llamamos a las 10."
    assert v["mensajes"][0]["atendido"] is True and v["mensajes_nuevos"] == 1


def test_personalizar_no_afecta_plantilla_ni_otros(cn):
    cid = cliente_dir(cn)
    r = cn.c.post(f"{C}/plantillas", headers=cn.h, json={"nombre": "Laboral del despacho", "especialidad": "laboral",
                                                         "etapas": [{"nombre": "Recepción"}, {"nombre": "Demanda"}, {"nombre": "Cierre"}]})
    pid = r.json()["id"]
    a1 = cn.c.post(f"{C}/seguimientos", headers=cn.h, json={"titulo": "Uno", "cliente_id": cid, "plantilla_id": pid}).json()["id"]
    a2 = cn.c.post(f"{C}/seguimientos", headers=cn.h, json={"titulo": "Dos", "cliente_id": cid, "plantilla_id": pid}).json()["id"]
    e1 = cn.c.get(f"{C}/seguimientos/{a1}", headers=cn.h).json()["etapas"]
    nuevas = [{"id": e1[0]["id"], "nombre": "Recepción"}, {"nombre": "Conciliación", "opcional": True}, {"id": e1[1]["id"], "nombre": "Demanda"},
              {"id": e1[2]["id"], "nombre": "Cierre"}]
    x = cn.c.put(f"{C}/seguimientos/{a1}/etapas", headers=cn.h, json={"etapas": nuevas}).json()
    assert [e["nombre"] for e in x["etapas"]] == ["Recepción", "Conciliación", "Demanda", "Cierre"]
    assert x["etapas"][0]["estado"] == "actual"  # se conserva el avance
    assert [e["nombre"] for e in cn.c.get(f"{C}/seguimientos/{a2}", headers=cn.h).json()["etapas"]] == ["Recepción", "Demanda", "Cierre"]
    p = next(p for p in cn.c.get(f"{C}/plantillas", headers=cn.h).json()["propias"] if p["id"] == pid)
    assert [e["nombre"] for e in p["etapas"]] == ["Recepción", "Demanda", "Cierre"]
    # regresar a una etapa anterior
    x = cn.c.post(f"{C}/seguimientos/{a1}/etapa", headers=cn.h, json={"etapa_id": x["etapas"][2]["id"], "estado": "actual"}).json()
    x = cn.c.post(f"{C}/seguimientos/{a1}/etapa", headers=cn.h, json={"etapa_id": x["etapas"][1]["id"], "estado": "actual"}).json()
    assert [e["estado"] for e in x["etapas"]] == ["completada", "actual", "pendiente", "pendiente"]


def test_publicar_exige_cliente_y_consulta_no_edita(cn):
    r = cn.c.post(f"{C}/seguimientos", headers=cn.h, json={"titulo": "Sin cliente", "base": "amparo"}).json()
    assert cn.c.put(f"{C}/seguimientos/{r['id']}", headers=cn.h, json={"visible_cliente": True}).status_code == 409
    h = cn.usuario("consulta", "consulta@org1.test")
    assert cn.c.get(f"{C}/seguimientos/{r['id']}", headers=h).status_code == 200
    assert cn.c.post(f"{C}/seguimientos/{r['id']}/revisado", headers=h).status_code == 403


def test_vincular_cliente_desde_connect(cn, org2, plataforma):
    r = cn.c.post(f"{C}/seguimientos", headers=cn.h, json={"titulo": "Sin cliente", "base": "civil"}).json()
    cid = cliente_dir(cn)
    activar(plataforma, org2, "connect")
    ajeno = cliente_dir(org2, "Ajeno Ficticio", "ajeno@c.test")
    assert cn.c.put(f"{C}/seguimientos/{r['id']}", headers=cn.h, json={"cliente_id": ajeno}).status_code == 404
    x = cn.c.put(f"{C}/seguimientos/{r['id']}", headers=cn.h, json={"cliente_id": cid}).json()
    assert x["cliente"]["id"] == cid
    assert cn.c.put(f"{C}/seguimientos/{r['id']}", headers=cn.h, json={"visible_cliente": True}).json()["visible_cliente"] is True


def test_vitrina_de_la_cuenta_demo_una_sola_vez(org):
    from app.services.connect import vitrina
    with SessionLocal() as db:
        o = db.get(m.Organizacion, org.org_id)
        o.nombre = "Despacho Piloto Nomira (datos ficticios)"
        db.commit()
        email = db.scalar(select(m.Usuario.email).where(m.Usuario.organizacion_id == org.org_id).limit(1))
        assert vitrina.sembrar(db, email) is True
        assert vitrina.sembrar(db, email) is False  # no duplica
        assert db.get(m.Organizacion, org.org_id).nombre == "Despacho Nomira"
        segs = db.scalars(select(m.CnSeguimiento).where(m.CnSeguimiento.organizacion_id == org.org_id)).all()
        assert len(segs) == 5 and all(s.visible_cliente for s in segs)
        assert not db.scalar(select(m.CnAviso.id))  # no inventa avisos enviados
        assert not db.scalar(select(m.CrCliente.id).where(m.CrCliente.organizacion_id == org.org_id, m.CrCliente.email.is_not(None)))
