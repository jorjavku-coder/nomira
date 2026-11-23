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


def test_solicitud_del_sitio_entra_como_lead_mql(plataforma, cliente):
    r = cliente.post("/api/solicitudes", json={"tipo": "suscripcion", "nombre": "Pedro Interesado", "empresa": "Bufete Demo", "email": "Pedro@Bufete.test",
                                               "telefono": "5511112222", "mensaje": "Quiero una demo", "acepta_contacto": True})
    assert r.status_code == 201, r.text
    # entra a Leads (MQL), no al embudo
    t = plataforma.c.get(f"{V}/tablero", headers=plataforma.h).json()
    assert sum(len(v) for v in t["columnas"].values()) == 0
    ls = plataforma.c.get(f"{V}/leads", headers=plataforma.h).json()
    assert [x["email"] for x in ls] == ["pedro@bufete.test"] and ls[0]["fase"] == "mql" and ls[0]["tarea"]
    assert plataforma.c.get(f"{V}/contador", headers=plataforma.h).json()["nuevas"] == 1
    lid = ls[0]["id"]
    assert plataforma.c.post(f"{V}/importar-solicitudes", headers=plataforma.h).json() == {"nuevas": 0}
    cliente.post("/api/solicitudes", json={"tipo": "informes", "nombre": "Pedro", "email": "pedro@bufete.test", "acepta_contacto": True})
    assert len(plataforma.c.get(f"{V}/leads", headers=plataforma.h).json()) == 1
    # un correo enviado o una llamada sin respuesta NO lo califica
    plataforma.c.post(f"{V}/actividades", headers=plataforma.h, json={"contacto_id": lid, "tipo": "intento", "titulo": "No contestó"})
    plataforma.c.post(f"{V}/actividades", headers=plataforma.h, json={"contacto_id": lid, "tipo": "correo", "titulo": "Le mandé presentación"})
    l2 = plataforma.c.get(f"{V}/leads", headers=plataforma.h).json()[0]
    assert l2["fase"] == "mql" and l2["intentos"] == 2
    assert plataforma.c.get(f"{V}/contador", headers=plataforma.h).json()["nuevas"] == 0
    # una llamada efectiva sí: pasa a SQL y abre su oportunidad en «Contactado» con todo el historial
    plataforma.c.post(f"{V}/actividades", headers=plataforma.h, json={"contacto_id": lid, "tipo": "llamada", "titulo": "Hablamos 10 minutos"})
    c = plataforma.c.get(f"{V}/contactos/{lid}", headers=plataforma.h).json()
    assert c["fase"] == "sql" and c["calificacion"] == "llamada" and c["propietario"] == "Dueño de Nomira"
    assert plataforma.c.get(f"{V}/leads", headers=plataforma.h).json() == []
    o = plataforma.c.get(f"{V}/oportunidades/{c['oportunidades'][0]['id']}", headers=plataforma.h).json()
    assert o["etapa"] == "contactado" and o["titulo"] == "Bufete Demo"
    titulos = [a["titulo"] for a in o["actividades"]]
    assert "Calificado como SQL: llamada efectiva" in titulos and "No contestó" in titulos and "Llegó una solicitud desde el sitio (suscripción)" in titulos
    assert not any(a["es_tarea"] and not a["completada_en"] for a in o["actividades"])  # el primer contacto quedó hecho
    with SessionLocal() as s:
        assert s.get(m.Solicitud, s.get(m.VtOportunidad, o["id"]).solicitud_id).estado == "atendida"


def test_leads_importar_calificar_y_descartar(plataforma):
    import io
    from openpyxl import Workbook, load_workbook
    plataforma.c.post(f"{V}/leads", headers=plataforma.h, json={"nombre": "Ya Existe", "email": "ya@existe.test"})
    wb = Workbook()
    ws = wb.active
    ws.append(["Nombre", "Despacho", "Correo", "Teléfono", "Ciudad", "Abogados", "Especialidad"])
    ws.append(["Lic. Uno", "Bufete Uno", "uno@b.test", 5511111111, "Toluca", 4, "Laboral"])
    ws.append(["Lic. Dos", "Bufete Dos", "", "55 2222 2222", "", "", ""])
    ws.append(["Lic. Uno bis", "", "UNO@b.test", "", "", "", ""])  # repetido en el archivo
    ws.append(["Ya Existe", "", "ya@existe.test", "", "", "", ""])  # ya está en el CRM
    ws.append(["Mal", "", "no-es-correo", "", "", "", ""])
    b = io.BytesIO()
    wb.save(b)
    arch = {"archivo": ("leads.xlsx", b.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    c = plataforma.c.post(f"{V}/campanas", headers=plataforma.h, json={"nombre": "Prospección LinkedIn", "canal": "linkedin"}).json()
    v = plataforma.c.post(f"{V}/leads/importar", headers=plataforma.h, files=arch, data={"confirmar": "false"}).json()
    assert (v["nuevos"], v["repetidos"], v["errores"]) == (2, 2, 1), v
    assert len(plataforma.c.get(f"{V}/leads", headers=plataforma.h).json()) == 1
    r = plataforma.c.post(f"{V}/leads/importar", headers=plataforma.h, files=arch, data={"confirmar": "true", "campana_id": str(c["id"])}).json()
    assert r["nuevos"] == 2
    ls = {x["nombre"]: x for x in plataforma.c.get(f"{V}/leads", headers=plataforma.h).json()}
    assert ls["Lic. Uno"]["abogados"] == 4 and ls["Lic. Uno"]["campana"] == "Prospección LinkedIn" and ls["Lic. Uno"]["origen"] == "prospeccion"
    assert ls["Lic. Dos"]["telefono"] == "55 2222 2222"
    # exportar a Excel
    x = plataforma.c.get(f"{V}/leads/exportar", headers=plataforma.h)
    assert x.status_code == 200 and load_workbook(io.BytesIO(x.content)).active.max_row == 4
    assert plataforma.c.get(f"{V}/leads/plantilla", headers=plataforma.h).status_code == 200
    # calificar exige contacto real
    uno = ls["Lic. Uno"]["id"]
    assert plataforma.c.post(f"{V}/leads/{uno}/calificar", headers=plataforma.h, json={"via": "correo"}).status_code == 422
    q = plataforma.c.post(f"{V}/leads/{uno}/calificar", headers=plataforma.h, json={"via": "respuesta", "detalle": "Aceptó la reunión por correo",
                                                                                  "titulo": "Bufete Uno · plan Medio", "valor_mensual": "3490"}).json()
    o = plataforma.c.get(f"{V}/oportunidades/{q['oportunidad_id']}", headers=plataforma.h).json()
    assert o["titulo"] == "Bufete Uno · plan Medio" and o["valor_mensual"] == "3490.00" and o["campana_id"] == c["id"]
    assert plataforma.c.get(f"{V}/contactos", headers=plataforma.h).json()[0]["nombre"] == "Lic. Uno"
    # descartar y reactivar
    dos = ls["Lic. Dos"]["id"]
    assert plataforma.c.post(f"{V}/leads/{dos}/descartar", headers=plataforma.h, json={"motivo": "no_contactar"}).json()["no_contactar"]
    assert [x["nombre"] for x in plataforma.c.get(f"{V}/leads?estado=descartado", headers=plataforma.h).json()] == ["Lic. Dos"]
    assert plataforma.c.post(f"{V}/leads/{dos}/reactivar", headers=plataforma.h).json()["fase"] == "mql"
    r = plataforma.c.get(f"{V}/resumen", headers=plataforma.h).json()
    assert r["mql"] == 2 and r["sql_mes"] == 1 and r["mql_a_sql_90"] == 33


def test_embudo_etapas_y_cierre(plataforma):
    o = op(plataforma)
    assert o["etapa"] == "contactado" and o["probabilidad"] == 20 and o["contacto"]["nombre"] == "Lic. Ana Prospecto"
    assert plataforma.c.post(f"{V}/oportunidades/{o['id']}/etapa", headers=plataforma.h, json={"etapa": "perdido"}).status_code == 422
    x = plataforma.c.post(f"{V}/oportunidades/{o['id']}/etapa", headers=plataforma.h, json={"etapa": "demo"}).json()
    assert x["etapa"] == "demo" and x["actividades"][0]["titulo"] == "Etapa: Contactado (SQL) → Demo agendada"
    o2 = op(plataforma, titulo="Otro despacho", valor_mensual="1790", contacto={"nombre": "Luis Otro", "email": "luis@otro.test"})
    plataforma.c.post(f"{V}/oportunidades/{o2['id']}/etapa", headers=plataforma.h, json={"etapa": "perdido", "motivo": "precio", "nota": "Muy caro"})
    r = plataforma.c.get(f"{V}/resumen", headers=plataforma.h).json()
    assert r["pipeline"] == "3490.00" and r["ponderado"] == "1396.00" and r["abiertas"] == 1 and r["conversion_90"] == 0
    assert plataforma.c.get(f"{V}/contactos/{o['contacto']['id']}", headers=plataforma.h).json()["fase"] == "sql"  # abrir oportunidad = calificar
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
