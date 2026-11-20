"""Academia como LMS: límite de cursos propios, catálogo de Nomira con costo (compra en línea con
Stripe, por cotización y cortesía), entrega de cursos, importación (enlaces, Excel, SCORM), videos
subidos con URL firmada, diploma con verificación pública y sesiones de Zoom/Meet."""
import hashlib
import hmac
import io
import json
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from openpyxl import load_workbook

from app import models as m
from app.config import ajustes
from app.services.academia import importar
from app.services.comercial import stripe as st

from .test_academia import armado, curso, leccion
from .test_evidencia import activar

P = "/api/plataforma/academia"


@pytest.fixture
def ac(org, plataforma):
    activar(plataforma, org, "academia")
    return org


@pytest.fixture
def editora(ac, org2, plataforma):
    """org = cuenta editora de Nomira; org2 = despacho cliente."""
    activar(plataforma, org2, "academia")
    conf = plataforma.c.get(f"{P}/config", headers=plataforma.h).json()["config"]
    r = plataforma.c.put(f"{P}/config", headers=plataforma.h, json={**conf, "org_editora_id": ac.org_id})
    assert r.status_code == 200, r.text
    return ac


def publicar_con_costo(plataforma, editora, precio="500"):
    c = armado(editora)
    r = plataforma.c.post(f"{P}/editora/{c['id']}/publicar", headers=plataforma.h, json={"acceso": "pago", "precio": precio})
    assert r.status_code == 200, r.text
    g = next(x for x in r.json()["catalogo"] if x["origen_curso_id"] == c["id"])
    return c, g


def leccion_simple_publicada(o, **kw):
    c = curso(o, titulo="Curso corto")
    c = leccion(o, c["modulos"][0]["id"], titulo="Única", **kw)
    r = o.c.post(f"/api/academia/admin/cursos/{c['id']}/publicar", headers=o.h, json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_limite_de_cursos_propios(ac, plataforma):
    ids = [curso(ac, titulo=f"Curso {i}")["id"] for i in range(5)]
    r = ac.c.post("/api/academia/admin/cursos", headers=ac.h, json={"titulo": "Sexto curso", "materia": "General"})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "limite_cursos"
    assert "Contrate cursos adicionales" in r.json()["detail"]["mensaje"]
    assert ac.c.post(f"/api/academia/admin/cursos/{ids[0]}/duplicar", headers=ac.h).status_code == 409
    lim = ac.c.get("/api/academia/admin/cursos", headers=ac.h).json()["limite"]
    assert lim == {"incluidos": 5, "adicionales": 0, "limite": 5, "usados": 5, "disponibles": 0}
    # archivar libera un lugar; restaurarlo cuando está lleno no se permite
    ac.c.post(f"/api/academia/admin/cursos/{ids[0]}/archivar", headers=ac.h)
    nuevo = curso(ac, titulo="Reemplazo")
    assert ac.c.post(f"/api/academia/admin/cursos/{ids[0]}/restaurar", headers=ac.h).status_code == 409
    # Nomira da cursos adicionales desde su panel
    r = plataforma.c.patch(f"{P}/organizaciones/{ac.org_id}", headers=plataforma.h, json={"ac_cursos_extra": 1, "ac_cuota_medios_mb": None})
    assert r.json()["limite"]["limite"] == 6
    assert curso(ac, titulo="Ahora sí")["id"] != nuevo["id"]


def test_curso_con_costo_compra_en_linea(editora, org2, plataforma, cliente, monkeypatch, db):
    c, g = publicar_con_costo(plataforma, editora)
    assert g["acceso"] == "pago" and g["precio"] == "500.00" and g["lecciones"] == 2
    cat = org2.c.get("/api/academia/cursos", headers=org2.h).json()["cursos"]
    t = next(x for x in cat if x["id"] == g["id"])
    assert t["acceso"] == {"tipo": "pago", "tiene_acceso": False, "precio": {"subtotal": "500.00", "iva_pct": "16.00", "iva": "80.00", "total": "580.00"}}
    # sin acceso: ve el temario, pero no el contenido
    det = org2.c.get(f"/api/academia/cursos/{g['id']}", headers=org2.h).json()
    lid = det["modulos"][0]["lecciones"][0]["id"]
    assert org2.c.post(f"/api/academia/cursos/{g['id']}/iniciar", headers=org2.h).status_code == 402
    assert org2.c.get(f"/api/academia/lecciones/{lid}", headers=org2.h).json()["detail"]["codigo"] == "curso_de_pago"
    assert org2.c.post(f"/api/academia/admin/cursos/{g['id']}/duplicar", headers=org2.h).status_code == 409
    # sin Stripe conectado no hay compra en línea; sí la solicitud por cotización (llega a Soporte)
    r = org2.c.post(f"/api/academia/cursos/{g['id']}/comprar", headers=org2.h)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "pago_no_disponible"
    r = org2.c.post(f"/api/academia/cursos/{g['id']}/solicitar", headers=org2.h, json={"mensaje": "Para 10 personas"})
    assert r.status_code == 200 and db.get(m.TicketSoporte, r.json()["ticket_id"]).organizacion_id == org2.org_id
    # con Stripe (modo de prueba): sesión por el total con IVA calculado en el servidor
    monkeypatch.setattr(ajustes(), "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(ajustes(), "stripe_webhook_secret", "whsec_x")
    llamadas = []
    monkeypatch.setattr(st, "crear_checkout", lambda **kw: llamadas.append(kw) or {"id": "cs_test_curso", "url": "https://checkout.stripe.com/c/pay/cs_test_curso"})
    r = org2.c.post(f"/api/academia/cursos/{g['id']}/comprar", headers=org2.h)
    assert r.json()["url"].startswith("https://checkout.stripe.com/") and str(llamadas[0]["total"]) == "580.00"
    assert llamadas[0]["metadata"]["tipo"] == "curso"

    def webhook(ev):
        cuerpo = json.dumps(ev).encode()
        ts = int(time.time())
        firma = hmac.new(b"whsec_x", f"{ts}.".encode() + cuerpo, hashlib.sha256).hexdigest()
        return cliente.post("/api/comercial/stripe/webhook", content=cuerpo, headers={"Stripe-Signature": f"t={ts},v1={firma}"})

    obj = {"id": "cs_test_curso", "payment_status": "paid", "amount_total": 100, "currency": "mxn"}
    webhook({"id": "evt_c0", "type": "checkout.session.completed", "livemode": False, "data": {"object": obj}})
    assert org2.c.post(f"/api/academia/cursos/{g['id']}/iniciar", headers=org2.h).status_code == 402  # importe distinto: no se aplica
    webhook({"id": "evt_c1", "type": "checkout.session.completed", "livemode": False, "data": {"object": {**obj, "amount_total": 58000}}})
    assert org2.c.post(f"/api/academia/cursos/{g['id']}/iniciar", headers=org2.h).status_code == 200
    assert org2.c.get(f"/api/academia/lecciones/{lid}", headers=org2.h).status_code == 200
    assert webhook({"id": "evt_c1", "type": "checkout.session.completed", "livemode": False, "data": {"object": {**obj, "amount_total": 58000}}}).json()["duplicado"]
    assert org2.c.post(f"/api/academia/cursos/{g['id']}/comprar", headers=org2.h).status_code == 409  # ya lo tiene
    # un despacho sin compra sigue sin acceso
    assert db.query(m.AcAcceso).filter_by(curso_id=g["id"]).count() == 1


def test_republicar_actualiza_sin_perder_avance(editora, org2, plataforma, db):
    c, g = publicar_con_costo(plataforma, editora)
    plataforma.c.post(f"{P}/organizaciones/{org2.org_id}/accesos", headers=plataforma.h, json={"curso_id": g["id"]})  # cortesía
    det = org2.c.get(f"/api/academia/cursos/{g['id']}", headers=org2.h).json()
    lid = det["modulos"][0]["lecciones"][0]["id"]
    org2.c.post(f"/api/academia/cursos/{g['id']}/iniciar", headers=org2.h)
    assert org2.c.post(f"/api/academia/lecciones/{lid}/completar", headers=org2.h).status_code == 200
    # la editora agrega una lección y Nomira vuelve a publicar
    leccion(editora, c["modulos"][0]["id"], titulo="Nueva lección")
    editora.c.post(f"/api/academia/admin/cursos/{c['id']}/publicar", headers=editora.h, json={})
    r = plataforma.c.post(f"{P}/editora/{c['id']}/publicar", headers=plataforma.h, json={"acceso": "pago", "precio": "650"})
    g2 = next(x for x in r.json()["catalogo"] if x["id"] == g["id"])
    assert g2["lecciones"] == 3 and g2["version"] > g["version"] and g2["precio"] == "650.00"
    det = org2.c.get(f"/api/academia/cursos/{g['id']}", headers=org2.h).json()
    assert det["modulos"][0]["lecciones"][0]["id"] == lid and det["modulos"][0]["lecciones"][0]["completada"]
    # revocar el acceso no borra el avance
    plataforma.c.delete(f"{P}/organizaciones/{org2.org_id}/accesos/{g['id']}", headers=plataforma.h)
    assert org2.c.get(f"/api/academia/lecciones/{lid}", headers=org2.h).status_code == 402
    assert db.query(m.AcAvance).filter_by(curso_id=g["id"]).count() == 1


def test_entregar_curso_a_un_despacho(editora, org2, plataforma):
    c = armado(editora)
    r = plataforma.c.post(f"{P}/editora/{c['id']}/entregar", headers=plataforma.h, json={"organizacion_id": org2.org_id})
    assert r.status_code == 200, r.text
    lista = org2.c.get("/api/academia/admin/cursos", headers=org2.h).json()
    x = next(k for k in lista["cursos"] if k["id"] == r.json()["curso_id"])
    assert x["estado"] == "borrador" and x["entregado_por_nomira"] and x["origen"] == "despacho" and lista["limite"]["usados"] == 1
    # un curso que no es de la cuenta editora no se entrega
    otro = curso(org2, titulo="Propio")
    assert plataforma.c.post(f"{P}/editora/{otro['id']}/entregar", headers=plataforma.h, json={"organizacion_id": org2.org_id}).status_code == 404


def test_cotizacion_con_cursos_de_academia(editora, org2, plataforma):
    _, g = publicar_con_costo(plataforma, editora)
    R = "/api/plataforma/comercial"
    cat = plataforma.c.get(f"{R}/catalogo", headers=plataforma.h).json()
    assert [x["id"] for x in cat["cursos_academia"]] == [g["id"]]
    basico = next(x for x in cat["paquetes"] if x["clave"] == "basico")
    e = {"paquete_id": basico["id"], "modulos": ["academia"], "cursos_nomira": [g["id"]], "cursos_extra": 2}
    pc = next(x for x in cat["precios"] if x["clave"] == "curso_adicional")
    assert pc["activo"] is True and pc["precio_mensual"] == "99.00"  # precio sugerido inicial
    plataforma.c.patch(f"{R}/precios/{pc['id']}", headers=plataforma.h, json={"precio_mensual": "150", "activo": False})
    r = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": e})
    assert r.status_code == 422 and "precio activo" in r.json()["detail"]  # sin precio activo no se cotiza
    plataforma.c.patch(f"{R}/precios/{pc['id']}", headers=plataforma.h, json={"precio_mensual": "150", "activo": True})
    calc = plataforma.c.post(f"{R}/calcular", headers=plataforma.h, json={"entrada": e}).json()
    # 1790 + 2×150 al mes + curso 500 único = 2590 → IVA 414.40 → 3004.40
    assert calc["subtotal"] == "2590.00" and calc["total"] == "3004.40" and calc["cursos"][0]["id"] == g["id"]
    cot = plataforma.c.post(f"{R}/cotizaciones", headers=plataforma.h, json={"contacto": "Ana", "despacho": "Org 2", "email": "a@org2.test", "entrada": e}).json()
    plataforma.c.post(f"{R}/cotizaciones/{cot['id']}/enviar", headers=plataforma.h, json={"confirmacion": "Enviar cotización", "manual": True})
    r = plataforma.c.post(f"{R}/cotizaciones/{cot['id']}/convertir", headers=plataforma.h,
                          json={"organizacion_id": org2.org_id, "promocional": True, "motivo": "Piloto aprobado", "confirmo": True})
    assert r.status_code == 200, r.text
    assert org2.c.post(f"/api/academia/cursos/{g['id']}/iniciar", headers=org2.h).status_code == 200
    assert org2.c.get("/api/academia/admin/cursos", headers=org2.h).json()["limite"]["limite"] == 7


def test_importar_enlaces(ac, monkeypatch):
    monkeypatch.setattr(importar, "titulo_oembed", lambda url: "Video uno" if "AAAAAAAAAAA" in url else None)
    r = ac.c.post("/api/academia/admin/importar/enlaces", headers=ac.h, json={
        "materia": "Laboral", "enlaces": "https://www.youtube.com/watch?v=AAAAAAAAAAA\nhttps://vimeo.com/123456 https://youtu.be/BBBBBBBBBBB"})
    assert r.status_code == 201, r.text
    c = r.json()
    ls = c["modulos"][0]["lecciones"]
    assert c["estado"] == "borrador" and [x["titulo"] for x in ls] == ["Video uno", "Lección 2", "Lección 3"]
    assert ls[1]["video_url"] == "https://vimeo.com/123456"
    assert ac.c.post("/api/academia/admin/importar/enlaces", headers=ac.h, json={"enlaces": "http://inseguro.test/v"}).status_code == 422
    r = ac.c.post("/api/academia/admin/importar/enlaces", headers=ac.h, json={"enlaces": "https://www.youtube.com/playlist?list=PL123"})
    assert r.status_code == 422 and "listas" in r.json()["detail"]


def test_importar_excel(ac):
    r = ac.c.get("/api/academia/admin/importar/plantilla", headers=ac.h)
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content))
    assert {"Curso", "Lecciones", "Preguntas", "Instrucciones"} <= set(wb.sheetnames)
    ws = wb["Lecciones"]
    ws.append(["Módulo 2", "Segunda lección", "", "Texto de la segunda", 10, "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = ac.c.post("/api/academia/admin/importar/excel", headers=ac.h,
                  files={"archivo": ("curso.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["titulo"] == "Atención a clientes" and [mo["titulo"] for mo in c["modulos"]] == ["Bienvenida", "Módulo 2"]
    assert c["calificacion_minima"] == 70 and len(c["preguntas"]) == 1 and c["preguntas"][0]["correcta"] == 1
    assert c["modulos"][0]["lecciones"][0]["recursos"][0]["url"] == "https://ejemplo.com/guia.pdf"
    # errores claros, con la fila
    ws.append(["X", "", "https://www.youtube.com/watch?v=CCCCCCCCCCC", "", "", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = ac.c.post("/api/academia/admin/importar/excel", headers=ac.h, files={"archivo": ("c.xlsx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 422 and "fila 4" in r.json()["detail"]
    assert ac.c.post("/api/academia/admin/importar/excel", headers=ac.h, files={"archivo": ("c.xlsx", b"no", "x")}).status_code == 422


MANIFEST = """<?xml version="1.0"?>
<manifest identifier="m1" xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
 <metadata><schema>ADL SCORM</schema><schemaversion>1.2</schemaversion></metadata>
 <organizations default="o1"><organization identifier="o1"><title>Curso SCORM de prueba</title>
  <item identifier="i1" identifierref="r1"><title>Unidad 1</title></item>
  <item identifier="i2" identifierref="r2"><title>Unidad 2</title></item>
 </organization></organizations>
 <resources>
  <resource identifier="r1" type="webcontent" adlcp:scormtype="sco" href="u1/index.html"><file href="u1/index.html"/></resource>
  <resource identifier="r2" type="webcontent" adlcp:scormtype="sco" href="u2/index.html"><file href="u2/index.html"/></resource>
 </resources>
</manifest>"""


def zip_scorm(extra: dict | None = None, manifest: str | None = MANIFEST) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        if manifest:
            z.writestr("imsmanifest.xml", manifest)
        z.writestr("u1/index.html", "<html><head><title>U1</title></head><body><script src='app.js'></script>Unidad 1</body></html>")
        z.writestr("u1/app.js", "var x = 1;")
        z.writestr("u2/index.html", "<html><head></head><body>Unidad 2</body></html>")
        for k, v in (extra or {}).items():
            z.writestr(k, v)
    return buf.getvalue()


def test_importar_scorm_y_reproducir(ac, cliente):
    malos = (zip_scorm(manifest=None), zip_scorm({"../fuera.txt": "x"}), b"no es zip")
    for z in malos:
        assert ac.c.post("/api/academia/admin/importar/scorm", headers=ac.h, files={"archivo": ("p.zip", z, "application/zip")}).status_code == 422
    r = ac.c.post("/api/academia/admin/importar/scorm", headers=ac.h, files={"archivo": ("p.zip", zip_scorm(), "application/zip")})
    assert r.status_code == 201, r.text
    c = r.json()
    ls = c["modulos"][0]["lecciones"]
    assert c["titulo"] == "Curso SCORM de prueba" and [x["titulo"] for x in ls] == ["Unidad 1", "Unidad 2"]
    assert ls[0]["scorm"]["version"] == "1.2" and ls[0]["scorm"]["inicio"] == "u1/index.html"
    ac.c.post(f"/api/academia/admin/cursos/{c['id']}/publicar", headers=ac.h, json={})
    ac.c.post(f"/api/academia/cursos/{c['id']}/iniciar", headers=ac.h)
    v = ac.c.get(f"/api/academia/lecciones/{ls[0]['id']}", headers=ac.h).json()
    url = v["scorm"]["url"]
    assert url.startswith("/api/academia-medios/scorm/") and url.endswith("/u1/index.html")
    h = cliente.get(url)  # sin encabezado de sesión: la URL firmada basta
    assert h.status_code == 200 and "sandbox allow-scripts" in h.headers["content-security-policy"]
    assert b"window.API=api12" in h.content and b"Unidad 1" in h.content and b'"cmi.core.student_name": "Admin 1"' in h.content
    assert cliente.get(url.replace("index.html", "app.js")).text == "var x = 1;"
    assert cliente.get(url.replace("u1/index.html", "../../../etc/passwd")).status_code == 404
    token = url.split("/")[4]
    assert cliente.get(url.replace(token, token[:-3] + "AAA")).status_code == 404
    # el paquete reporta «completed» en la Unidad 1 y «passed» con 90 en la Unidad 2
    r = ac.c.put(f"/api/academia/lecciones/{ls[0]['id']}/scorm", headers=ac.h, json={"datos": {"cmi.core.lesson_status": "completed",
                                                                                                  "cmi.suspend_data": "abc", "otra": "x"}})
    assert r.json()["leccion_completada"] and not r.json()["curso_completado"]
    r = ac.c.put(f"/api/academia/lecciones/{ls[1]['id']}/scorm", headers=ac.h, json={"datos": {"cmi.core.lesson_status": "passed",
                                                                                                  "cmi.core.score.raw": "90"}})
    assert r.json()["curso_completado"] and r.json()["calificacion"] == 90
    # al volver, el paquete recibe lo guardado (para retomar)
    v = ac.c.get(f"/api/academia/lecciones/{ls[0]['id']}", headers=ac.h).json()
    assert b'"cmi.suspend_data": "abc"' in cliente.get(v["scorm"]["url"]).content and b'"otra"' not in cliente.get(v["scorm"]["url"]).content


def test_video_subido_con_url_firmada(ac, cliente, plataforma):
    c = curso(ac)
    c = leccion(ac, c["modulos"][0]["id"], titulo="Con video")
    lid = c["modulos"][0]["lecciones"][0]["id"]
    mp4 = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40
    assert ac.c.post(f"/api/academia/admin/lecciones/{lid}/video", headers=ac.h, files={"archivo": ("v.exe", mp4, "x")}).status_code == 415
    assert ac.c.post(f"/api/academia/admin/lecciones/{lid}/video", headers=ac.h, files={"archivo": ("v.mp4", b"no video" * 10, "video/mp4")}).status_code == 415
    r = ac.c.post(f"/api/academia/admin/lecciones/{lid}/video", headers=ac.h, files={"archivo": ("clase.mp4", mp4, "video/mp4")})
    assert r.status_code == 200 and r.json()["modulos"][0]["lecciones"][0]["video_subido"]["tamano"] == len(mp4)
    v = ac.c.get(f"/api/academia/lecciones/{lid}", headers=ac.h).json()
    url = v["video_subido"]["url"]
    r = cliente.get(url)
    assert r.status_code == 200 and r.content == mp4 and r.headers["content-type"] == "video/mp4"
    r = cliente.get(url, headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    # sin espacio disponible no se sube
    plataforma.c.patch(f"{P}/organizaciones/{ac.org_id}", headers=plataforma.h, json={"ac_cursos_extra": 0, "ac_cuota_medios_mb": 0})
    r = ac.c.post(f"/api/academia/admin/lecciones/{lid}/video", headers=ac.h, files={"archivo": ("otro.mp4", mp4, "video/mp4")})
    assert r.status_code == 413 and "espacio" in r.json()["detail"]


def test_diploma_y_verificacion_publica(ac, cliente):
    c = leccion_simple_publicada(ac)
    lid = c["modulos"][0]["lecciones"][0]["id"]
    ac.c.post(f"/api/academia/cursos/{c['id']}/iniciar", headers=ac.h)
    r = ac.c.post(f"/api/academia/lecciones/{lid}/completar", headers=ac.h).json()
    assert r["completado"]
    pdf = ac.c.get(f"/api/academia/constancias/{r['avance_id']}", headers=ac.h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and "diploma-" in pdf.headers["content-disposition"]
    folio = ac.c.get(f"/api/academia/cursos/{c['id']}", headers=ac.h).json()["constancia_folio"]
    v = cliente.get(f"/api/academia-publico/verificar/{folio}").json()
    assert v["valido"] and v["participante"] == "Admin 1" and v["curso"] == "Curso corto" and v["organizacion"] == "Org 1"
    assert cliente.get("/api/academia-publico/verificar/NA-XXXX-XXXX").status_code == 404


def test_sesiones_zoom_meet_y_calendario(ac):
    c = curso(ac)
    inicio = datetime.now(timezone.utc) + timedelta(minutes=10)
    r = ac.c.post(f"/api/academia/admin/cursos/{c['id']}/sesiones", headers=ac.h,
                  json={"titulo": "Clase en vivo", "inicio": inicio.isoformat(), "duracion_min": 60, "enlace": "https://us02web.zoom.us/j/123456789"})
    s = r.json()["sesiones"][0]
    assert s["plataforma"] == {"clave": "zoom", "nombre": "Zoom"} and s["unirse_activo"] is True
    assert s["google_calendar"].startswith("https://calendar.google.com/calendar/render?action=TEMPLATE")
    ics = ac.c.get(f"/api/academia/sesiones/{s['id']}/calendario.ics", headers=ac.h)
    assert ics.status_code == 200 and "BEGIN:VEVENT" in ics.text and "zoom.us" in ics.text and ics.headers["content-type"].startswith("text/calendar")
    r = ac.c.post(f"/api/academia/admin/cursos/{c['id']}/sesiones", headers=ac.h,
                  json={"titulo": "Otra", "inicio": (inicio + timedelta(days=2)).isoformat(), "enlace": "https://meet.google.com/abc-defg-hij"})
    s2 = next(x for x in r.json()["sesiones"] if x["titulo"] == "Otra")
    assert s2["plataforma"]["clave"] == "meet" and s2["unirse_activo"] is False
