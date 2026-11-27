"""Gana con Nomira: trivia con puntos y topes, tienda, ruleta (apagada de fábrica, un giro por semana), meses de regalo que
esperan al primer pago, invitaciones entre despachos y casos de la calculadora entregados a UN despacho de la red."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from app.services.crecimiento import base, juegos

P = "/api/premios"
PP = "/api/plataforma/crecimiento"


def plan(org, dias=30):
    with SessionLocal() as db:
        db.add(m.PeriodoSuscripcion(organizacion_id=org.org_id, plan="mensual", inicio=date.today() - timedelta(days=1),
                                    fin=date.today() + timedelta(days=dias), pagado=True, monto=1000))
        db.commit()


def puntos(org, n):
    with SessionLocal() as db:
        base.mover(db, org.org_id, None, "ajuste", n, "Prueba")
        db.commit()


def periodos(org_id):
    with SessionLocal() as db:
        return [(p.plan, p.inicio, p.fin) for p in base.periodos(db, org_id)]


def test_trivia_da_puntos_una_vez_y_respeta_el_tope(org):
    d = org.c.get(P, headers=org.h).json()
    assert len(d["trivia"]) == 3 and d["puntos"] == 0
    assert "respuesta" not in d["trivia"][0] and "correcta" not in d["trivia"][0]  # la respuesta no viaja antes de contestar
    with SessionLocal() as db:
        correctas = {p.id: p.correcta for p in db.scalars(select(m.CxPregunta)).all()}
    q = d["trivia"][0]
    r = org.c.post(f"{P}/trivia/{q['id']}", headers=org.h, json={"elegida": correctas[q["id"]]}).json()
    assert r["correcta"] and r["puntos"] == 10 and r["puntos_total"] == 10
    assert org.c.post(f"{P}/trivia/{q['id']}", headers=org.h, json={"elegida": 0}).status_code == 409
    otra = next(pid for pid in correctas if pid not in [x["id"] for x in d["trivia"]])
    assert org.c.post(f"{P}/trivia/{otra}", headers=org.h, json={"elegida": 0}).status_code == 409  # no es de hoy
    q2 = d["trivia"][1]
    r = org.c.post(f"{P}/trivia/{q2['id']}", headers=org.h, json={"elegida": (correctas[q2["id"]] + 1) % 4}).json()
    assert not r["correcta"] and r["puntos"] == 0 and r["explicacion"]
    # las mismas preguntas todo el día, ya con su respuesta
    d2 = org.c.get(P, headers=org.h).json()
    assert [x["id"] for x in d2["trivia"]] == [x["id"] for x in d["trivia"]] and d2["trivia"][0]["respuesta"]["correcta"]
    # tope diario por despacho
    puntos(org, 0)
    with SessionLocal() as db:
        base.config(db).tope_puntos_dia_org = 10
        db.commit()
    q3 = d["trivia"][2]
    r = org.c.post(f"{P}/trivia/{q3['id']}", headers=org.h, json={"elegida": correctas[q3["id"]]}).json()
    assert r["correcta"] and r["puntos"] == 0 and r["tope_alcanzado"]


def test_meses_de_regalo_esperan_al_primer_pago(org, plataforma):
    tienda = org.c.get(P, headers=org.h).json()["tienda"]
    mes = next(x for x in tienda if x["tipo"] == "meses" and x["valor"] == 1)
    assert org.c.post(f"{P}/tienda/{mes['id']}", headers=org.h).status_code == 409  # sin puntos
    puntos(org, 2000)
    r = org.c.post(f"{P}/tienda/{mes['id']}", headers=org.h).json()
    assert r["recompensa"]["estado"] == "pendiente" and r["puntos_total"] == 500
    assert periodos(org.org_id) == []
    # el despacho paga su primer plan: el mes de regalo se agrega al final
    inicio = date.today()
    s = plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/periodos", headers=plataforma.h,
                          json={"plan": "mensual", "inicio": inicio.isoformat(), "monto": "1000", "pagado": True})
    assert s.status_code in (200, 201), s.text
    ps = periodos(org.org_id)
    assert [p[0] for p in ps] == ["mensual", "cortesia"] and ps[1][1] == ps[0][2] + timedelta(days=1)
    rec = org.c.get(P, headers=org.h).json()["recompensas"][0]
    assert rec["estado"] == "aplicada" and rec["periodo"]["inicio"] == ps[1][1].isoformat()
    # nadie captura «cortesía» a mano
    assert plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/periodos", headers=plataforma.h,
                             json={"plan": "cortesia", "inicio": (date.today() + timedelta(days=200)).isoformat()}).status_code == 422


def test_descuento_es_un_cupon_de_un_uso(org):
    puntos(org, 600)
    d = next(x for x in org.c.get(P, headers=org.h).json()["tienda"] if x["tipo"] == "descuento" and x["valor"] == 10)
    r = org.c.post(f"{P}/tienda/{d['id']}", headers=org.h).json()["recompensa"]
    assert r["estado"] == "disponible" and r["cupon"]["codigo"].startswith("PREMIO-")
    with SessionLocal() as db:
        c = db.scalar(select(m.CmCupon).where(m.CmCupon.codigo == r["cupon"]["codigo"]))
        assert c.usos_maximos == 1 and c.valor == 10 and c.vence_en > date.today()


def test_solo_administradores_canjean(org):
    h = org.usuario("analista", "analista@org1.test")
    puntos(org, 2000)
    art = org.c.get(P, headers=h).json()["tienda"][0]
    assert org.c.post(f"{P}/tienda/{art['id']}", headers=h).status_code == 403


def test_ruleta_apagada_de_fabrica_y_un_giro_por_semana(org, plataforma, monkeypatch):
    assert org.c.post(f"{P}/ruleta", headers=org.h).status_code == 409
    d = plataforma.c.get(PP, headers=plataforma.h).json()
    assert d["config"]["ruleta_activa"] is False and abs(sum(x["probabilidad"] for x in d["probabilidades"]) - 100) < 0.1
    plataforma.c.put(f"{PP}/config", headers=plataforma.h, json={**d["config"], "ruleta_activa": True, "ruleta_permiso": "PERMISO-PRUEBA"})
    # solo dejamos «6 meses» para saber qué sale
    for x in d["ruleta"]:
        plataforma.c.put(f"{PP}/premios/{x['id']}", headers=plataforma.h, json={**x, "activo": x["etiqueta"] == "6 meses gratis"})
    r = org.c.post(f"{P}/ruleta", headers=org.h).json()
    assert r["premio"]["etiqueta"] == "6 meses gratis" and r["recompensa"]["estado"] == "pendiente"
    assert org.c.post(f"{P}/ruleta", headers=org.h).status_code == 409  # misma semana
    # otra semana: ya alcanzó el tope anual de 6 meses → sale la casilla más común aunque esté sola la de meses
    monkeypatch.setattr(juegos, "semana", lambda d=None: "2099-W01")
    r = org.c.post(f"{P}/ruleta", headers=org.h).json()
    assert r["premio"]["tipo"] == "puntos" and r["puntos_total"] == juegos.CONSOLACION


def test_invitacion_premia_a_ambos_cuando_el_invitado_paga(org, plataforma, cliente, monkeypatch):
    from app.services import correo
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "modo_prueba", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto, adjuntos=None: enviados.append(texto))
    plan(org)
    codigo = org.c.get(P, headers=org.h).json()["invitacion"]["codigo"]
    assert cliente.get(f"/api/invitacion/{codigo}").json()["despacho"] == "Org 1"
    assert cliente.get("/api/invitacion/ZZZZZZ").status_code == 404
    import re
    r = cliente.post("/api/auth/registro", json={"organizacion": "Despacho Invitado Ficticio", "nombre": "Lic. Ficticia", "email": "inv@despacho.test",
                                                  "contrasena": "Contrasena-Segura-9", "modulos": ["agenda"], "acepto": True, "invitacion": codigo})
    assert r.status_code == 200, r.text
    v = cliente.post("/api/auth/registro/verificar", json={"reto": r.json()["reto"], "codigo": re.search(r"\b(\d{6})\b", enviados[-1]).group(1)})
    assert v.status_code == 201, v.text
    nueva = v.json()["usuario"]["organizacion_id"]
    refs = org.c.get(P, headers=org.h).json()["invitacion"]["referidos"]
    assert refs == [{"despacho": "Despacho Invitado Ficticio", "estado": "registrado", "desde": date.today().isoformat()}]
    s = plataforma.c.post(f"/api/plataforma/clientes/{nueva}/periodos", headers=plataforma.h,
                          json={"plan": "mensual", "inicio": (date.today() + timedelta(days=2)).isoformat(), "monto": "1000", "pagado": True})
    assert s.status_code in (200, 201), s.text
    assert [p[0] for p in periodos(nueva)] == ["prueba", "mensual", "cortesia"]
    assert [p[0] for p in periodos(org.org_id)] == ["mensual", "cortesia"]
    assert org.c.get(P, headers=org.h).json()["invitacion"]["referidos"][0]["estado"] == "premiado"


def test_caso_de_la_calculadora_llega_a_un_despacho_de_la_red(org, org2, plataforma, cliente):
    from tests.test_evidencia import activar
    assert cliente.get("/api/publico/abogados?estado=CDMX").json()["disponible"] is False
    datos = {"estado": "CDMX", "nombre": "Persona Ficticia", "telefono": "55 1234 5678", "acepta": True,
             "calculo": {"fecha_ingreso": "2020-01-01", "fecha_baja": "2025-06-01", "causa": "despido_injustificado", "salario_diario": "500"}}
    assert cliente.post("/api/publico/quiero-abogado", json=datos).status_code == 409
    # sin plan pagado ni Prospectos no puede entrar a la red
    assert org.c.put(f"{P}/red", headers=org.h, json={"activo": True, "estados": ["CDMX"]}).status_code == 409
    for o in (org, org2):
        plan(o)
        activar(plataforma, o, "leads")
        assert o.c.put(f"{P}/red", headers=o.h, json={"activo": True, "estados": ["CDMX", "MEX"]}).status_code == 200
    assert cliente.get("/api/publico/abogados?estado=CDMX").json()["disponible"] is True
    assert cliente.post("/api/publico/quiero-abogado", json={**datos, "acepta": False}).status_code == 422
    r1 = cliente.post("/api/publico/quiero-abogado", json=datos).json()
    r2 = cliente.post("/api/publico/quiero-abogado", json={**datos, "telefono": "55 9999 0000"}).json()
    assert {r1["despacho"], r2["despacho"]} == {"Org 1", "Org 2"}  # por turnos
    with SessionLocal() as db:
        ps = db.scalars(select(m.LdProspecto).where(m.LdProspecto.canal == "nomira")).all()
        assert len(ps) == 2 and all("total estimado" in p.descripcion for p in ps)
        assert {p.organizacion_id for p in ps} == {org.org_id, org2.org_id}
        assert db.scalar(select(m.LdConsentimiento).where(m.LdConsentimiento.prospecto_id == ps[0].id))
    # el panel solo ve conteos y nombres de despachos
    d = plataforma.c.get(PP, headers=plataforma.h).json()
    assert d["cifras"]["casos"] == 2 and "Persona Ficticia" not in str(d) and "1234" not in str(d)
