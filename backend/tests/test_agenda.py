"""Nomira Agenda Jurídica: cálculo asistido de días hábiles (siempre con desglose y validación del abogado),
calendarios judiciales capturados por el despacho, asuntos, plazos, audiencias, alertas escalonadas,
vista diaria, calendario externo privado y aislamiento por organización."""
from datetime import date, datetime, timedelta

import pytest

from app import models as m
from app.config import ajustes
from app.services import correo
from app.services.agenda import avisos, base
from app.services.agenda.dias import Calendario, calcular, descanso_lft

from .test_evidencia import activar

A = "/api/agenda"


@pytest.fixture
def ag(org, plataforma):
    activar(plataforma, org, "agenda")
    return org


@pytest.fixture
def buzon(monkeypatch):
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto, **kw: enviados.append({"para": dest, "asunto": asunto, "texto": texto}))
    monkeypatch.setattr(ajustes(), "url_publica", "https://nomirasoft.com")
    return enviados


def asunto(o, **kw):
    r = o.c.post(f"{A}/asuntos", headers=o.h, json={"titulo": "Pérez vs. Empresa Ficticia", "numero": "123/2026", "materia": "laboral",
                                                     "tribunal": "Tribunal Laboral Ficticio", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def evento(o, **kw):
    r = o.c.post(f"{A}/eventos", headers=o.h, json={"tipo": "actividad", "titulo": "Revisar acuerdo", "fecha": base.hoy().isoformat(), **kw})
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ cálculo

def test_descanso_obligatorio_lft():
    d = descanso_lft(2026)
    assert date(2026, 2, 2) in d and date(2026, 3, 16) in d and date(2026, 11, 16) in d and date(2026, 12, 25) in d
    assert date(2030, 10, 1) in descanso_lft(2030) and date(2027, 10, 1) not in descanso_lft(2027)


def test_calculo_habiles_con_desglose():
    r = calcular(Calendario(), date(2026, 11, 12), 5, "habiles", "dia_habil_siguiente")
    # jueves 12 → surte efectos viernes 13 → inicia martes 17 (sáb, dom y lunes 16 inhábiles) → 17,18,19,20,23
    assert r["efectos"] == "2026-11-13" and r["inicio"] == "2026-11-17" and r["vence"] == "2026-11-23"
    assert r["contados"] == ["2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23"]
    assert any("art. 74 LFT" in s["motivo"] for s in r["saltados"]) and "validarlo un abogado" in r["aviso"]


def test_calculo_con_vacaciones_y_dia_habilitado():
    cal = Calendario(inhabiles={date(2026, 12, 21) + timedelta(days=i): "Vacaciones del tribunal" for i in range(12)},
                     habilitados={date(2026, 12, 19): "Sábado habilitado"})
    r = calcular(cal, date(2026, 12, 17), 3, "habiles", "mismo_dia")
    # efectos jueves 17 → inicia viernes 18 → 18, sáb 19 (habilitado), y tras vacaciones lunes 4 de enero
    assert r["contados"] == ["2026-12-18", "2026-12-19", "2027-01-04"] and r["vence"] == "2027-01-04"
    r = calcular(cal, date(2026, 12, 10), 10, "naturales", "mismo_dia")
    assert r["vence"] == "2027-01-04" and "se recorre" in " ".join(r["pasos"])  # 11 + 9 días = 20 dic (domingo) → recorre
    with pytest.raises(ValueError):
        calcular(cal, date(2026, 12, 10), 10, "naturales", "cuando_sea")


# ------------------------------------------------------------------ acceso

def test_modulo_y_aislamiento(org, org2, plataforma):
    assert org.c.get(f"{A}/hoy", headers=org.h).status_code == 403  # sin contratar
    activar(plataforma, org, "agenda")
    activar(plataforma, org2, "agenda")
    a = asunto(org)
    assert org2.c.get(f"{A}/asuntos/{a['id']}", headers=org2.h).status_code == 404
    assert org2.c.post(f"{A}/eventos", headers=org2.h, json={"tipo": "plazo", "titulo": "Intruso", "fecha": "2026-12-01", "asunto_id": a["id"]}).status_code == 404
    assert org2.c.get(f"{A}/asuntos", headers=org2.h).json() == []


def test_roles(ag):
    hc = ag.usuario("consulta", "consulta@org1.test")
    assert ag.c.post(f"{A}/asuntos", headers=hc, json={"titulo": "No debe", "materia": "civil"}).status_code == 403
    yo = ag.c.get(f"{A}/catalogos", headers=hc).json()["yo"]
    e = evento(ag, responsable_id=yo)
    assert ag.c.post(f"{A}/eventos/{e['id']}/cumplir", headers=hc, json={"nota": "Hecho"}).json()["estado"] == "cumplido"
    otro = evento(ag)
    assert ag.c.post(f"{A}/eventos/{otro['id']}/cumplir", headers=hc, json={}).status_code == 403
    assert ag.c.put(f"{A}/config", headers=hc, json={}).status_code == 403


# ------------------------------------------------------------------ calendarios y plazos

def test_calendario_del_tribunal_y_plazo_validado(ag, db):
    r = ag.c.post(f"{A}/calendarios", headers=ag.h, json={"nombre": "Tribunal Laboral Ficticio", "jurisdiccion": "estatal", "entidad": "Jalisco",
                                                         "fuente": "Circular ficticia 1/2026"})
    assert r.status_code == 201, r.text
    cal = r.json()
    r = ag.c.post(f"{A}/calendarios/{cal['id']}/dias", headers=ag.h, json={"desde": "2026-11-18", "hasta": "2026-11-19", "motivo": "Suspensión de labores"})
    assert r.status_code == 201 and r.json()["agregados"] == 2
    dias = r.json()["dias"]
    assert any(x["origen"] == "lft" and x["fecha"] == "2026-11-16" for x in dias) and sum(x["origen"] == "capturado" for x in dias) == 2
    assert ag.c.post(f"{A}/calendarios/{cal['id']}/dias", headers=ag.h, json={"desde": "2026-01-01", "hasta": "2026-06-01", "motivo": "Demasiado"}).status_code == 422

    a = asunto(ag, calendario_id=cal["id"], jurisdiccion="estatal", entidad="Jalisco")
    act = ag.c.post(f"{A}/asuntos/{a['id']}/actuaciones", headers=ag.h, json={"fecha": "2026-11-11", "tipo": "acuerdo",
                                                                              "descripcion": "Se tiene por presentada la demanda", "notificada_en": "2026-11-12"}).json()
    calculo = {"notificacion": "2026-11-12", "dias": 5, "tipo_dias": "habiles", "surte_efectos": "dia_habil_siguiente"}
    prev = ag.c.post(f"{A}/calcular", headers=ag.h, json={**calculo, "asunto_id": a["id"]}).json()
    assert prev["vence"] == "2026-11-25" and prev["calendario"] == "Tribunal Laboral Ficticio"  # 17, 20, 23, 24, 25 (18 y 19 suspendidos)
    e = ag.c.post(f"{A}/eventos", headers=ag.h, json={"tipo": "plazo", "titulo": "Contestar requerimiento", "asunto_id": a["id"],
                                                     "actuacion_id": act["actuacion_id"], "calculo": calculo}).json()
    assert e["fecha"] == "2026-11-25" and e["por_validar"] and e["calculo"]["contados"][-1] == "2026-11-25"
    v = ag.c.post(f"{A}/eventos/{e['id']}/validar", headers=ag.h).json()
    assert v["validado"] and v["validado_por"] == "Admin 1" and not v["por_validar"]
    # el abogado decide otra fecha: se respeta, se anota el ajuste y se pierde la validación
    body = {"tipo": "plazo", "titulo": "Contestar requerimiento", "asunto_id": a["id"], "calculo": calculo, "fecha": "2026-11-24"}
    x = ag.c.patch(f"{A}/eventos/{e['id']}", headers=ag.h, json=body).json()
    assert x["fecha"] == "2026-11-24" and x["calculo"]["ajuste_manual"] == "2026-11-24" and not x["validado"]
    # no se concluye un asunto con pendientes
    assert ag.c.post(f"{A}/asuntos/{a['id']}/estado", headers=ag.h, json={"estado": "concluido"}).status_code == 409
    assert ag.c.post(f"{A}/eventos/{e['id']}/cancelar", headers=ag.h, json={"nota": "x"}).status_code == 422
    ag.c.post(f"{A}/eventos/{e['id']}/cancelar", headers=ag.h, json={"nota": "Se desistió la contraparte"})
    assert ag.c.post(f"{A}/asuntos/{a['id']}/estado", headers=ag.h, json={"estado": "concluido"}).json()["estado"] == "concluido"
    assert db.query(m.Auditoria).filter(m.Auditoria.accion == "ag_plazo_validado").count() == 1


def test_audiencia_con_conflicto_y_vista_diaria(ag):
    yo = ag.c.get(f"{A}/catalogos", headers=ag.h).json()["yo"]
    hoy = base.hoy()
    evento(ag, tipo="audiencia", titulo="Audiencia preliminar", hora="10:00", enlace="https://meet.google.com/abc-defg-hij", responsable_id=yo)
    r = evento(ag, tipo="audiencia", titulo="Audiencia de juicio", hora="12:00", responsable_id=yo)
    assert r["conflictos"] == ["Audiencia preliminar a las 10:00"]
    evento(ag, tipo="plazo", titulo="Plazo vencido", fecha=(hoy - timedelta(days=2)).isoformat(), responsable_id=yo)
    evento(ag, tipo="plazo", titulo="Plazo próximo", fecha=(hoy + timedelta(days=3)).isoformat())
    assert ag.c.post(f"{A}/eventos", headers=ag.h, json={"tipo": "audiencia", "titulo": "Mal", "fecha": hoy.isoformat(), "enlace": "http://x"}).status_code == 422
    v = ag.c.get(f"{A}/hoy", headers=ag.h).json()
    assert [x["titulo"] for x in v["vencidos"]] == ["Plazo vencido"] and len(v["hoy"]) == 2 and [x["titulo"] for x in v["proximos"]] == ["Plazo próximo"]
    assert v["hoy"][0]["plataforma"]["clave"] == "meet" and len(v["sin_responsable"]) == 1
    assert ag.c.get(f"{A}/contador", headers=ag.h).json()["total"] == 3
    csv = ag.c.get(f"{A}/exportar.csv", headers=ag.h)
    assert csv.status_code == 200 and "Audiencia de juicio" in csv.text


# ------------------------------------------------------------------ alertas escalonadas

def test_alertas_escalonadas(ag, db, buzon):
    yo = ag.c.get(f"{A}/catalogos", headers=ag.h).json()["yo"]
    h_an = ag.usuario("analista", "analista@org1.test")
    analista = ag.c.get(f"{A}/catalogos", headers=h_an).json()["yo"]
    hoy = base.hoy()
    e = evento(ag, tipo="plazo", titulo="Ofrecer pruebas", fecha=(hoy + timedelta(days=1)).isoformat(), responsable_id=analista)
    a_las = lambda d, h: datetime.combine(d, datetime.min.time(), tzinfo=base.ZONA).replace(hour=h)
    r = avisos.ejecutar(db, a_las(hoy, 9))
    assert r["avisos"] == 1 and r["correos"] == 1 and buzon[0]["para"] == ["analista@org1.test"] and "Ofrecer pruebas" in buzon[0]["texto"]
    assert avisos.ejecutar(db, a_las(hoy, 10))["avisos"] == 0  # no se repite
    # el día del vencimiento: primero al responsable; a mediodía, si sigue pendiente, a quien supervisa
    manana = hoy + timedelta(days=1)
    assert avisos.ejecutar(db, a_las(manana, 9))["avisos"] == 1
    r = avisos.ejecutar(db, a_las(manana, 13))
    assert r["avisos"] == 1 and buzon[-1]["para"] == ["admin1@org1.test"] and "sigue pendiente" in buzon[-1]["texto"]
    # venció sin cumplirse: a ambos
    r = avisos.ejecutar(db, a_las(manana + timedelta(days=1), 9))
    assert r["avisos"] == 2
    # cumplido: ya no hay avisos
    ag.c.post(f"{A}/eventos/{e['id']}/cumplir", headers=h_an, json={})
    assert avisos.ejecutar(db, a_las(manana + timedelta(days=2), 9))["avisos"] == 0
    # cada quien puede desactivar los correos (el aviso sigue en Nomira)
    assert ag.c.put(f"{A}/preferencias", headers=h_an, json={"resumen_diario": False, "alertas_correo": False}).status_code == 200
    evento(ag, tipo="plazo", titulo="Otro", fecha=hoy.isoformat(), responsable_id=analista)
    antes = len(buzon)
    r = avisos.ejecutar(db, a_las(hoy, 9))
    assert r["avisos"] == 1 and len(buzon) == antes
    assert ag.c.get(f"{A}/hoy", headers=h_an).json()["avisos"]


def test_resumen_diario_una_vez(ag, db, buzon):
    yo = ag.c.get(f"{A}/catalogos", headers=ag.h).json()["yo"]
    evento(ag, tipo="audiencia", titulo="Audiencia de hoy", hora="11:00", responsable_id=yo, alertas=[])
    hoy = base.hoy()
    t = datetime.combine(hoy, datetime.min.time(), tzinfo=base.ZONA)
    assert avisos.ejecutar(db, t.replace(hour=6))["resumenes"] == 0  # antes de la hora configurada
    assert avisos.ejecutar(db, t.replace(hour=7))["resumenes"] == 1
    assert avisos.ejecutar(db, t.replace(hour=8))["resumenes"] == 0
    assert any("Su agenda del" in x["asunto"] for x in buzon)


# ------------------------------------------------------------------ calendario externo

def test_feed_privado(ag, cliente):
    yo = ag.c.get(f"{A}/catalogos", headers=ag.h).json()["yo"]
    a = asunto(ag)
    evento(ag, tipo="audiencia", titulo="Audiencia con nombre del cliente", hora="10:00", asunto_id=a["id"], responsable_id=yo)
    url = ag.c.post(f"{A}/preferencias/feed", headers=ag.h).json()["url"]
    ruta = "/api/agenda-feed/" + url.split("/api/agenda-feed/")[1]
    r = cliente.get(ruta)
    assert r.status_code == 200 and "BEGIN:VEVENT" in r.text and "123/2026" in r.text and "nombre del cliente" not in r.text  # reservado
    ag.c.put(f"{A}/preferencias", headers=ag.h, json={"resumen_diario": True, "alertas_correo": True, "feed_detalle": "completo"})
    assert "nombre del cliente" in cliente.get(ruta).text
    ag.c.delete(f"{A}/preferencias/feed", headers=ag.h)
    assert cliente.get(ruta).status_code == 404
    assert cliente.get("/api/agenda-feed/inventado.ics").status_code == 404


def test_precio_en_comercial(plataforma):
    cat = plataforma.c.get("/api/plataforma/comercial/catalogo", headers=plataforma.h).json()
    assert next(p for p in cat["precios"] if p["clave"] == "modulo:agenda")["precio_mensual"] == "890.00"
    assert any(x["clave"] == "agenda" for x in cat["modulos"])
