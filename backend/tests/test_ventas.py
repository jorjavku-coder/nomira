"""Ventas de Nomira (CRM del panel de la plataforma): solicitudes del sitio que entran solas, contactos, oportunidades,
etapas, actividades y tareas, campañas con resultados, liga con cotizaciones y permisos."""
from datetime import timedelta

from app import models as m
from app.db import SessionLocal

from .test_comercial import nueva

V = "/api/plataforma/ventas"


def equipo(plataforma, cliente, email="ventas@nomira.test"):
    r = plataforma.c.post("/api/plataforma/admins", headers=plataforma.h, json={"nombre": "Vendedora Uno", "email": email})
    assert r.status_code == 201, r.text
    t = cliente.post("/api/plataforma/login", json={"email": email, "contrasena": r.json()["acceso"]["contrasena_temporal"]}).json()["token"]
    return {"Authorization": f"Bearer {t}"}, r.json()["admin"]["id"]


def op(p, **kw):
    datos = {"titulo": "Despacho Ficticio · plan Medio", "valor_mensual": "3490", "contacto": {"nombre": "Lic. Ana Prospecto", "despacho": "Despacho Ficticio SC",
                                                                                         "email": "ana@ficticio.test", "telefono": "5512345678", "origen": "referido"}, **kw}
    r = p.c.post(f"{V}/oportunidades", headers=p.h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()


def test_solicitud_del_sitio_entra_a_ventas(plataforma, cliente):
    r = cliente.post("/api/solicitudes", json={"tipo": "suscripcion", "nombre": "Pedro Interesado", "empresa": "Bufete Demo", "email": "Pedro@Bufete.test",
                                               "telefono": "5511112222", "mensaje": "Quiero una demo", "acepta_contacto": True})
    assert r.status_code == 201, r.text
    t = plataforma.c.get(f"{V}/tablero", headers=plataforma.h).json()
    nuevo = t["columnas"]["nuevo"]
    assert len(nuevo) == 1 and nuevo[0]["titulo"] == "Suscripción · Bufete Demo" and nuevo[0]["contacto"]["email"] == "pedro@bufete.test"
    o = plataforma.c.get(f"{V}/oportunidades/{nuevo[0]['id']}", headers=plataforma.h).json()
    assert [a["titulo"] for a in o["actividades"]] == ["Primer contacto con el prospecto", "Llegó una solicitud desde el sitio"]
    assert o["actividades"][0]["es_tarea"] and o["actividades"][1]["detalle"] == "Quiero una demo"
    # importar de nuevo no duplica; una segunda solicitud con el mismo correo usa el mismo contacto
    assert plataforma.c.post(f"{V}/importar-solicitudes", headers=plataforma.h).json() == {"nuevas": 0}
    cliente.post("/api/solicitudes", json={"tipo": "informes", "nombre": "Pedro", "email": "pedro@bufete.test", "acepta_contacto": True})
    assert len(plataforma.c.get(f"{V}/contactos", headers=plataforma.h).json()) == 1
    # registrar una llamada lo pasa a «contactado» y marca la solicitud como atendida
    plataforma.c.post(f"{V}/actividades", headers=plataforma.h, json={"oportunidad_id": o["id"], "tipo": "llamada", "titulo": "Llamada inicial"})
    x = plataforma.c.get(f"{V}/oportunidades/{o['id']}", headers=plataforma.h).json()
    assert x["etapa"] == "contactado" and x["propietario"] == "Dueño de Nomira"
    assert not any(a["es_tarea"] and not a["completada_en"] for a in x["actividades"])  # el primer contacto quedó hecho
    with SessionLocal() as s:
        assert s.get(m.Solicitud, s.get(m.VtOportunidad, o["id"]).solicitud_id).estado == "atendida"


def test_embudo_etapas_y_cierre(plataforma):
    o = op(plataforma)
    assert o["etapa"] == "nuevo" and o["probabilidad"] == 10 and o["contacto"]["nombre"] == "Lic. Ana Prospecto"
    assert plataforma.c.post(f"{V}/oportunidades/{o['id']}/etapa", headers=plataforma.h, json={"etapa": "perdido"}).status_code == 422
    x = plataforma.c.post(f"{V}/oportunidades/{o['id']}/etapa", headers=plataforma.h, json={"etapa": "demo"}).json()
    assert x["etapa"] == "demo" and x["actividades"][0]["titulo"] == "Etapa: Nuevo → Demo agendada"
    o2 = op(plataforma, titulo="Otro despacho", valor_mensual="1790", contacto={"nombre": "Luis Otro", "email": "luis@otro.test"})
    plataforma.c.post(f"{V}/oportunidades/{o2['id']}/etapa", headers=plataforma.h, json={"etapa": "perdido", "motivo": "precio", "nota": "Muy caro"})
    r = plataforma.c.get(f"{V}/resumen", headers=plataforma.h).json()
    assert r["pipeline"] == "3490.00" and r["ponderado"] == "1396.00" and r["abiertas"] == 1 and r["conversion_90"] == 0
    assert r["motivos_perdida"] == [{"motivo": "Precio", "n": 1}]
    plataforma.c.post(f"{V}/oportunidades/{o['id']}/etapa", headers=plataforma.h, json={"etapa": "ganado"})
    r = plataforma.c.get(f"{V}/resumen", headers=plataforma.h).json()
    assert r["ganadas_mes"] == 1 and r["mrr_ganado_mes"] == "3490.00" and r["conversion_90"] == 50
    t = plataforma.c.get(f"{V}/tablero", headers=plataforma.h).json()
    assert len(t["columnas"]["ganado"]) == 1 and len(t["columnas"]["perdido"]) == 1 and t["totales"]["ganado"]["valor"] == "3490.00"


def test_tareas(plataforma, cliente):
    hv, vid = equipo(plataforma, cliente)
    o = op(plataforma)
    manana = (m.ahora() + timedelta(days=1)).isoformat()
    ayer = (m.ahora() - timedelta(days=1)).isoformat()
    plataforma.c.post(f"{V}/actividades", headers=plataforma.h, json={"oportunidad_id": o["id"], "tipo": "tarea", "titulo": "Enviar propuesta", "vence_en": manana, "asignado_id": vid})
    plataforma.c.post(f"{V}/actividades", headers=plataforma.h, json={"oportunidad_id": o["id"], "tipo": "llamada", "titulo": "Seguimiento", "vence_en": ayer})
    mias = cliente.get(f"{V}/actividades", headers=hv).json()
    assert [x["titulo"] for x in mias] == ["Enviar propuesta"] and not mias[0]["vencida"]
    yo = plataforma.c.get(f"{V}/actividades", headers=plataforma.h).json()
    assert [x["titulo"] for x in yo] == ["Seguimiento"] and yo[0]["vencida"]
    assert plataforma.c.get(f"{V}/contador", headers=plataforma.h).json()["tareas_vencidas"] == 1
    done = plataforma.c.post(f"{V}/actividades/{yo[0]['id']}/completar", headers=plataforma.h, json={"resultado": "Quedó de responder"}).json()
    assert done["completada_en"] and done["resultado"] == "Quedó de responder"
    assert plataforma.c.get(f"{V}/actividades", headers=plataforma.h).json() == []
    # quien no la creó no la borra; el historial automático no se borra
    assert cliente.delete(f"{V}/actividades/{yo[0]['id']}", headers=hv).status_code == 403
    sistema = plataforma.c.get(f"{V}/oportunidades/{o['id']}", headers=plataforma.h).json()["actividades"][-1]
    assert sistema["tipo"] == "sistema" and plataforma.c.delete(f"{V}/actividades/{sistema['id']}", headers=plataforma.h).status_code == 409
    # un contacto que pidió no ser contactado
    ct = o["contacto"]["id"]
    c = plataforma.c.get(f"{V}/contactos/{ct}", headers=plataforma.h).json()
    plataforma.c.put(f"{V}/contactos/{ct}", headers=plataforma.h, json={**{k: c[k] for k in ("nombre", "despacho", "email", "telefono", "origen")}, "no_contactar": True})
    assert plataforma.c.post(f"{V}/actividades", headers=plataforma.h, json={"contacto_id": ct, "tipo": "llamada", "titulo": "Llamada"}).status_code == 409


def test_campanas_con_resultados(plataforma):
    c = plataforma.c.post(f"{V}/campanas", headers=plataforma.h, json={"nombre": "Facebook nov", "canal": "facebook", "presupuesto": "6000",
                                                                        "utm_campaign": "fb-nov"}).json()
    o1 = op(plataforma, campana_id=c["id"])
    op(plataforma, titulo="Bufete B", campana_id=c["id"], contacto={"nombre": "B Uno", "email": "b@b.test", "campana_id": c["id"]})
    op(plataforma, titulo="Bufete C", campana_id=c["id"], contacto={"nombre": "C Uno", "email": "c@c.test", "campana_id": c["id"]})
    plataforma.c.post(f"{V}/oportunidades/{o1['id']}/etapa", headers=plataforma.h, json={"etapa": "ganado"})
    x = plataforma.c.get(f"{V}/campanas", headers=plataforma.h).json()[0]
    assert (x["oportunidades"], x["ganadas"], x["abiertas"], x["conversion"]) == (3, 1, 2, 33)
    assert x["costo_por_lead"] == "2000.00" and x["costo_por_cliente"] == "6000.00" and x["mrr_ganado"] == "3490.00"
    assert plataforma.c.post(f"{V}/campanas", headers=plataforma.h, json={"nombre": "X", "canal": "tv"}).status_code == 422


def test_contactos_duplicados_y_borrado(plataforma, cliente):
    o = op(plataforma)
    r = plataforma.c.post(f"{V}/contactos", headers=plataforma.h, json={"nombre": "Ana Otra", "email": "ANA@ficticio.test"})
    assert r.status_code == 409 and "Lic. Ana Prospecto" in r.json()["detail"]
    assert plataforma.c.get(f"{V}/contactos?q=ficticio", headers=plataforma.h).json()[0]["oportunidades_abiertas"] == 1
    hv, _ = equipo(plataforma, cliente)
    assert cliente.delete(f"{V}/contactos/{o['contacto']['id']}", headers=hv).status_code == 403
    assert plataforma.c.delete(f"{V}/contactos/{o['contacto']['id']}", headers=plataforma.h).json() == {"ok": True}
    assert plataforma.c.get(f"{V}/oportunidades/{o['id']}", headers=plataforma.h).status_code == 404


def test_cotizacion_mueve_la_oportunidad(plataforma, cliente):
    o = op(plataforma)
    hv, _ = equipo(plataforma, cliente)
    # el equipo de ventas (no superadministrador) puede cotizar desde la oportunidad
    class P:
        c, h = cliente, hv
    cot = nueva(P, oportunidad_id=o["id"])
    assert cot["oportunidad_id"] == o["id"]
    det = plataforma.c.get(f"{V}/oportunidades/{o['id']}", headers=plataforma.h).json()
    assert det["cotizaciones"][0]["folio"] == cot["folio"] and det["cotizaciones"][0]["total"]
    assert any(a["titulo"] == f"Cotización {cot['folio']} creada" for a in det["actividades"])
    with SessionLocal() as s:
        s.get(m.CmCotizacion, cot["id"]).estado = "enviada"
        s.commit()
    assert plataforma.c.get(f"{V}/oportunidades/{o['id']}", headers=plataforma.h).json()["etapa"] == "propuesta"
    with SessionLocal() as s:
        s.get(m.CmCotizacion, cot["id"]).estado = "pagada"
        s.commit()
    g = plataforma.c.get(f"{V}/oportunidades/{o['id']}", headers=plataforma.h).json()
    assert g["etapa"] == "ganado" and g["cerrada_en"]
    # pero registrar pagos y convertir en cliente sigue siendo del superadministrador
    assert cliente.post(f"/api/plataforma/comercial/cotizaciones/{cot['id']}/pagos", headers=hv, json={}).status_code == 403
    assert cliente.put("/api/plataforma/comercial/config", headers=hv, json={}).status_code == 403


def test_solo_el_panel(org, cliente):
    assert cliente.get(f"{V}/tablero").status_code == 401
    assert org.c.get(f"{V}/tablero", headers=org.h).status_code == 401
