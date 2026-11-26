"""Club Nomira: Nomira da de alta aliados y beneficios; los despachos ven solo lo publicado y vigente; el código se
entrega solo a miembros con plan vigente; la credencial se verifica en público; las métricas son conteos."""
from datetime import date, timedelta

import pytest

from app import models as m
from app.db import SessionLocal

P = "/api/plataforma/club"
C = "/api/club"
PUB = "/api/club-publico"


def plan(org, plan="mensual", dias=30):
    with SessionLocal() as db:
        db.add(m.PeriodoSuscripcion(organizacion_id=org.org_id, plan=plan, inicio=date.today() - timedelta(days=1),
                                    fin=date.today() + timedelta(days=dias), pagado=True))
        db.commit()


@pytest.fixture
def aliado(plataforma):
    r = plataforma.c.post(f"{P}/aliados", headers=plataforma.h, json={"nombre": "Óptica Ficticia", "giro": "Salud visual", "estado": "activo",
                                                                     "sitio": "https://optica.ejemplo.test", "contacto_email": "ventas@optica.test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def beneficio(plataforma, aliado, **kw):
    datos = {"aliado_id": aliado, "titulo": "Lentes con descuento", "resumen": "20% de descuento", "categoria": "salud", "canje": "codigo",
             "codigo": "NOMIRA20", "estado": "publicado", "condiciones": "Válido en sucursales participantes.", **kw}
    r = plataforma.c.post(f"{P}/beneficios", headers=plataforma.h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_solo_lo_publicado_vigente_y_de_aliados_activos(org, plataforma, aliado):
    plan(org)
    b1 = beneficio(plataforma, aliado)
    beneficio(plataforma, aliado, titulo="Borrador", estado="borrador")
    beneficio(plataforma, aliado, titulo="Vencido", vigente_hasta=(date.today() - timedelta(days=1)).isoformat())
    beneficio(plataforma, aliado, titulo="Futuro", vigente_desde=(date.today() + timedelta(days=5)).isoformat())
    r = org.c.get(C, headers=org.h).json()
    assert [b["id"] for b in r["beneficios"]] == [b1]
    assert "codigo" not in r["beneficios"][0]  # el código no viaja en la lista
    # aliado pausado: desaparecen sus beneficios
    plataforma.c.put(f"{P}/aliados/{aliado}", headers=plataforma.h, json={"nombre": "Óptica Ficticia", "estado": "pausado"})
    assert org.c.get(C, headers=org.h).json()["beneficios"] == []


def test_canje_entrega_el_codigo_y_cuenta_sin_duplicar(org, plataforma, aliado):
    plan(org)
    b = beneficio(plataforma, aliado)
    for _ in range(3):
        assert org.c.post(f"{C}/beneficios/{b}/uso", headers=org.h, json={"tipo": "vista"}).status_code == 200
    r = org.c.post(f"{C}/beneficios/{b}/uso", headers=org.h, json={"tipo": "canje"})
    assert r.json()["codigo"] == "NOMIRA20"
    org.c.post(f"{C}/beneficios/{b}/uso", headers=org.h, json={"tipo": "canje"})
    met = next(x for x in plataforma.c.get(P, headers=plataforma.h).json()["beneficios"] if x["id"] == b)["metricas"]
    assert met == {"vistas": 1, "canjes": 1, "despachos": 1}  # una vista y un canje por persona al día


def test_sin_plan_vigente_no_hay_canje(org, plataforma, aliado):
    b = beneficio(plataforma, aliado)
    r = org.c.get(C, headers=org.h).json()
    assert r["credencial"]["vigente"] is False and len(r["beneficios"]) == 1  # puede verlos
    assert org.c.post(f"{C}/beneficios/{b}/uso", headers=org.h, json={"tipo": "canje"}).status_code == 403


def test_credencial_y_verificacion_publica(org, plataforma):
    plan(org, "prueba", 2)
    c = org.c.get(C, headers=org.h).json()["credencial"]
    assert c["codigo"].startswith("NM-") and c["vigente"] is True
    assert org.c.get(C, headers=org.h).json()["credencial"]["codigo"] == c["codigo"]  # siempre la misma
    v = org.c.get(f"{PUB}/verificar/{c['codigo']}").json()
    assert v["valida"] is True and v["nombre"] == c["nombre"] and set(v) == {"valida", "nombre", "despacho", "codigo"}
    assert org.c.get(f"{PUB}/verificar/NM-AAAA-AAAA").json()["valida"] is False
    with SessionLocal() as db:
        db.get(m.Organizacion, org.org_id).estado = "suspendida"
        db.commit()
    assert org.c.get(f"{PUB}/verificar/{c['codigo']}").json()["valida"] is False


def test_postulacion_de_empresa_y_bot(org, plataforma):
    base = {"empresa": "Papelería Ficticia", "nombre": "Ana Ejemplo", "email": "ana@papeleria.test", "acepta_contacto": True,
            "propuesta": "10% en papelería para despachos"}
    assert org.c.post(f"{PUB}/aliados", json={**base, "sitio_web": "http://spam"}).status_code == 201  # trampa: no se guarda
    assert org.c.post(f"{PUB}/aliados", json=base).status_code == 201
    assert org.c.post(f"{PUB}/aliados", json={**base, "acepta_contacto": False}).status_code == 422
    s = plataforma.c.get(P, headers=plataforma.h).json()["solicitudes"]
    assert len(s) == 1 and s[0]["empresa"] == "Papelería Ficticia" and s[0]["estado"] == "nueva"
    r = plataforma.c.post(f"{P}/aliados", headers=plataforma.h, json={"nombre": "Papelería Ficticia", "solicitud_id": s[0]["id"]})
    assert r.json()["estado"] == "prospecto"
    assert plataforma.c.get(P, headers=plataforma.h).json()["solicitudes"][0]["estado"] == "aliado"


def test_validaciones_y_permisos(org, plataforma, aliado):
    assert plataforma.c.post(f"{P}/beneficios", headers=plataforma.h, json={
        "aliado_id": aliado, "titulo": "Sin código", "resumen": "10%", "categoria": "salud", "canje": "codigo"}).status_code == 422
    assert plataforma.c.post(f"{P}/beneficios", headers=plataforma.h, json={
        "aliado_id": aliado, "titulo": "Enlace inseguro", "resumen": "10%", "categoria": "salud", "canje": "enlace",
        "enlace": "javascript:alert(1)"}).status_code == 422
    # los usuarios de un despacho no entran al panel del Club
    assert org.c.get(P, headers=org.h).status_code == 401
    assert org.c.get(C).status_code == 401
