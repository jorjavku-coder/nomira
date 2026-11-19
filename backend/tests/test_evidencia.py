"""Nomira Evidencia: independencia de módulos, trazabilidad de hechos, revisión humana,
aislamiento entre organizaciones y exportaciones. Documentos 100 % ficticios."""
import io
import shutil

import pymupdf
import pytest
from openpyxl import load_workbook

from app import models as m
from app.services.evidencia import demo
from app.sinteticos import BASE, crear_pdf, recibo

DOCS = demo.documentos()
CONTRATO = DOCS["contrato_individual_ficticio.pdf"]
AVISO = DOCS["aviso_de_terminacion_ficticio.pdf"]
CORREO_PNG = DOCS["correo_recursos_humanos_ficticio.png"]
requiere_ocr = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract no está instalado")


def activar(plataforma, org, modulo, contratado=True):
    r = plataforma.c.patch(f"/api/plataforma/clientes/{org.org_id}/modulos/{modulo}", headers=plataforma.h,
                           json={"contratado": contratado})
    assert r.status_code == 200, r.text
    return r.json()


def asunto(org, nombre="Asunto ficticio", **kw):
    r = org.c.post("/api/evidencia/asuntos", headers=org.h, json={"nombre": nombre, **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def subir(org, aid, *archivos):
    r = org.c.post(f"/api/evidencia/asuntos/{aid}/documentos", headers=org.h,
                   files=[("archivos", (n, d, "application/octet-stream")) for n, d in archivos])
    assert r.status_code == 201, r.text
    return r.json()


def panel(org, aid):
    r = org.c.get(f"/api/evidencia/asuntos/{aid}", headers=org.h)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- módulos: independencia y activación ----------

def test_modulos_independientes_y_protegidos(org, org2, plataforma, db):
    # Sin contratar: Evidencia no existe para la organización (backend y menú)
    ev_mod = org.c.get("/api/organizacion", headers=org.h).json()["modulos"]["evidencia"]
    assert (ev_mod["nombre"], ev_mod["contratado"], ev_mod["activo"]) == ("Nomira Evidencia", False, False)
    assert org.c.get("/api/evidencia/asuntos", headers=org.h).status_code == 403
    assert org.c.patch("/api/organizacion/modulos/evidencia", headers=org.h, json={"activo": True}).status_code == 409

    # Solo Evidencia: se contrata Evidencia y se retira Nómina
    activar(plataforma, org, "evidencia")
    activar(plataforma, org, "nomina", contratado=False)
    login = org.c.post("/api/auth/login", json={"email": "admin1@org1.test", "contrasena": "Contrasena-Segura-1"}).json()
    assert login["modulos"] == ["evidencia"]
    assert org.c.get("/api/evidencia/asuntos", headers=org.h).status_code == 200
    for metodo, ruta in [("GET", "/api/expedientes"), ("GET", "/api/catalogos"), ("POST", "/api/expedientes/prelectura"),
                         ("GET", "/api/expedientes/1/resultado"), ("GET", "/api/documentos/1/archivo")]:
        assert org.c.request(metodo, ruta, headers=org.h).status_code == 403, ruta
    aid = asunto(org, "Solo evidencia")
    subir(org, aid, ("contrato.pdf", CONTRATO))
    p = panel(org, aid)
    assert p["documentos"][0]["estado"] == "leido" and p["hechos"]  # funciona sin el módulo de nómina
    r = org.c.get(f"/api/evidencia/asuntos/{aid}/exportar/pdf", headers=org.h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")

    # Solo Nómina (la otra organización): todo igual que antes y Evidencia cerrado
    assert org2.c.get("/api/expedientes", headers=org2.h).status_code == 200
    assert org2.c.get("/api/evidencia/asuntos", headers=org2.h).status_code == 403

    # Ambos: se vuelve a contratar Nómina; ninguno depende del otro
    activar(plataforma, org, "nomina")
    assert org.c.get("/api/expedientes", headers=org.h).status_code == 200
    assert org.c.get("/api/evidencia/asuntos", headers=org.h).status_code == 200

    # El administrador desactiva Evidencia: rutas cerradas, datos intactos; al reactivarlo siguen ahí
    assert org.c.patch("/api/organizacion/modulos/evidencia", headers=org.h, json={"activo": False}).status_code == 200
    assert org.c.get(f"/api/evidencia/asuntos/{aid}", headers=org.h).status_code == 403
    assert db.query(m.EvAsunto).filter_by(id=aid).count() == 1 and db.query(m.EvHecho).count() > 0
    assert org.c.patch("/api/organizacion/modulos/evidencia", headers=org.h, json={"activo": True}).status_code == 200
    assert panel(org, aid)["asunto"]["nombre"] == "Solo evidencia"
    # Nunca sin módulos; y solo el administrador cambia módulos
    assert org.c.patch("/api/organizacion/modulos/evidencia", headers=org.h, json={"activo": False}).status_code == 200
    r = org.c.patch("/api/organizacion/modulos/nomina", headers=org.h, json={"activo": False})
    assert r.status_code == 409 and "al menos un módulo" in r.json()["detail"]
    analista = org.usuario("analista", "ana@org1.test")
    assert org.c.patch("/api/organizacion/modulos/evidencia", headers=analista, json={"activo": True}).status_code == 403
    acciones = {a.accion for a in db.query(m.Auditoria)}
    assert {"modulo_contratado", "modulo_retirado", "modulo_activado", "modulo_desactivado"} <= acciones


def test_alta_de_cliente_con_modulos_elegidos(plataforma, db):
    r = plataforma.c.post("/api/plataforma/clientes", headers=plataforma.h, json={
        "organizacion": "Despacho Probatorio", "admin_nombre": "Laura", "admin_email": "laura@probatorio.test",
        "modulos": ["evidencia"]})
    assert r.status_code == 201, r.text
    cid = r.json()["cliente"]["id"]
    det = plataforma.c.get(f"/api/plataforma/clientes/{cid}", headers=plataforma.h).json()["modulos"]
    assert (det["evidencia"]["activo"], det["nomina"]["contratado"]) == (True, False)
    assert plataforma.c.post("/api/plataforma/clientes", headers=plataforma.h, json={
        "organizacion": "X", "admin_nombre": "X", "admin_email": "x@x.test", "modulos": ["inventado"]}).status_code == 422


# ---------- lectura, trazabilidad y revisión humana ----------

@pytest.fixture
def ev(org, plataforma):
    activar(plataforma, org, "evidencia")
    return org


def test_lectura_propone_hechos_con_fuente_y_nada_confirmado(ev, db):
    aid = asunto(ev, cliente="Cliente ficticio", tipo_caso="Laboral", campos={"Contraparte": "Empresa ficticia"})
    res = subir(ev, aid, ("contrato.pdf", CONTRATO), ("aviso.pdf", AVISO))
    assert all(r["aceptado"] for r in res)
    repetido = subir(ev, aid, ("otra-vez.pdf", CONTRATO))[0]
    assert not repetido["aceptado"] and "idéntico" in repetido["motivo"]
    p = panel(ev, aid)
    contrato = next(d for d in p["documentos"] if d["nombre"] == "contrato.pdf")
    assert (contrato["estado"], contrato["tipo_sugerido"], contrato["fecha_sugerida"], contrato["clasificado"]) == \
        ("leido", "Contrato", "2020-01-15", False)
    hechos = p["hechos"]
    assert hechos and all(h["estado"] == "por_revisar" for h in hechos)  # nada se confirma solo
    assert all(h["documento_id"] and h["pagina"] == 1 and h["fragmento"] and h["bbox"] for h in hechos)
    inicio = next(h for h in hechos if "inicia el 15 de enero" in h["descripcion"])
    assert inicio["fecha"] == "2020-01-15" and inicio["fecha_texto"] == "15 de enero de 2020"
    salario = next(h for h in hechos if "salario" in h["descripcion"].lower())
    assert salario["importe"] == "18500.00" and salario["fecha"] is None
    # «En la Ciudad de México, el 15 de enero de 2020, celebran el presente contrato…»: es la fecha DEL
    # DOCUMENTO (no un evento del caso) y el lugar va en una propuesta aparte
    comparecen = next(h for h in hechos if "celebran" in h["fragmento"] and h["tipo_dato"] == "fecha_documento")
    assert comparecen["personas"] == ["Roberto Ejemplo Pérez", "Juan Demo Ficticio"]
    assert (comparecen["valor_original"], comparecen["valor"]) == ("15 de enero de 2020", "15 ene 2020")
    lugar = next(h for h in hechos if h["tipo_dato"] == "lugar")
    assert lugar["valor"] == "Ciudad de México" and "15 de enero" not in lugar["descripcion"]
    assert (inicio["tipo_dato"], inicio["tema"]) == ("fecha_evento", "inicio_relacion")
    assert (salario["tipo_dato"], salario["tema"]) == ("importe", "salario")
    # Cada frase propuesta existe literalmente en el documento (no se inventa texto)
    texto = " ".join(" ".join(pg.texto.split()) for pg in db.query(m.EvPagina).all())
    assert all(" ".join(h["fragmento"].split()) in texto for h in hechos)
    # Sin hechos revisados, la cronología está vacía
    assert p["cronologia"] == {"eventos": [], "sin_fecha": []}
    # Clasificar el documento (corrección humana) queda en auditoría
    r = ev.c.patch(f"/api/evidencia/documentos/{contrato['id']}", headers=ev.h, json={"tipo": "Contrato laboral", "fecha_documento": "2020-01-15"})
    assert r.status_code == 200 and r.json()["clasificado"]
    assert {"ev_documento_cargado", "ev_documento_clasificado"} <= {a.accion for a in db.query(m.Auditoria)}


@requiere_ocr
def test_imagen_se_lee_con_ocr_y_contradiccion_se_senala_sin_decidir(ev):
    aid = asunto(ev)
    subir(ev, aid, ("contrato.pdf", CONTRATO), ("correo.png", CORREO_PNG))
    p = panel(ev, aid)
    correo = next(d for d in p["documentos"] if d["nombre"] == "correo.png")
    assert correo["estado"] == "leido" and correo["formato"] == "png" and correo["tipo_sugerido"] == "Correo o mensaje"
    a = next(h for h in p["hechos"] if "inicia el 15 de enero" in h["descripcion"])
    b = next(h for h in p["hechos"] if h["documento_id"] == correo["id"] and h["fecha"] == "2020-02-01")
    assert "OCR" in b["calidad"]["lectura"] and "confianza" not in b  # viene de OCR; sin porcentajes
    r = ev.c.post(f"/api/evidencia/asuntos/{aid}/hechos/confirmar", headers=ev.h, json={"ids": [a["id"], b["id"]]})
    assert r.status_code == 200
    p = panel(ev, aid)
    assert [c["hechos"] for c in p["contradicciones"]] == [[a["id"], b["id"]]] and p["contradicciones"][0]["difieren"] == ["fecha"]
    eventos = p["cronologia"]["eventos"]
    assert [e["fecha"] for e in eventos] == ["2020-01-15", "2020-02-01"]  # ambas versiones, ordenadas, ninguna elegida
    assert all(e["contradicciones"] for e in eventos)
    # Matriz: sugiere «contradictorio», pero el estado lo decide una persona
    pid = ev.c.post(f"/api/evidencia/asuntos/{aid}/puntos", headers=ev.h, json={"descripcion": "Fecha de ingreso"}).json()["id"]
    for h in (a, b):
        ev.c.post(f"/api/evidencia/puntos/{pid}/vinculos", headers=ev.h, json={"hecho_id": h["id"]})
    punto = panel(ev, aid)["puntos"][0]
    assert (punto["estado"], punto["sugerencia"]["estado"]) == ("pendiente_evidencia", "contradictorio")
    assert all(v["documento_id"] and v["pagina"] for v in punto["vinculos"])
    # La persona revisa el par y lo marca como revisado: deja de señalarse; los hechos no cambian
    ev.c.post(f"/api/evidencia/asuntos/{aid}/contradicciones/revisada", headers=ev.h, json={"par": p["contradicciones"][0]["par"]})
    p = panel(ev, aid)
    assert [c["decision_texto"] for c in p["contradicciones"]] == ["No aplica"] and p["resumen"]["diferencias_pendientes"] == 0
    assert len(p["cronologia"]["eventos"]) == 2 and not any(e["contradicciones"] for e in p["cronologia"]["eventos"])


def test_hechos_manuales_edicion_y_confirmacion(ev, db):
    aid = asunto(ev)
    subir(ev, aid, ("contrato.pdf", CONTRATO))
    doc = panel(ev, aid)["documentos"][0]["id"]
    # Sin fuente: queda por revisar y no puede confirmarse
    r = ev.c.post(f"/api/evidencia/asuntos/{aid}/hechos", headers=ev.h, json={"descripcion": "El cliente dice que trabajó horas extra", "fecha": "2024-03-01"})
    sin_fuente = r.json()
    assert sin_fuente["estado"] == "por_revisar" and sin_fuente["origen"] == "manual"
    r = ev.c.post(f"/api/evidencia/hechos/{sin_fuente['id']}/confirmar", headers=ev.h)
    assert r.status_code == 409 and "sin documento fuente" in r.json()["detail"]
    assert all(e["id"] != sin_fuente["id"] for e in panel(ev, aid)["cronologia"]["eventos"])
    # Con fuente: confirmado por quien lo capturó
    r = ev.c.post(f"/api/evidencia/asuntos/{aid}/hechos", headers=ev.h, json={
        "descripcion": "Firma del contrato", "fecha": "2020-01-15", "documento_id": doc, "pagina": 1, "importe": "1,000.50"})
    manual = r.json()
    assert (manual["estado"], manual["importe"], manual["revisado_por"]) == ("confirmado", "1000.50", "Admin 1")
    assert ev.c.post(f"/api/evidencia/asuntos/{aid}/hechos", headers=ev.h, json={
        "descripcion": "Página inexistente", "documento_id": doc, "pagina": 9}).status_code == 422
    # Editar una propuesta automática la deja «Editado por usuario» y conserva la propuesta original
    auto = next(h for h in panel(ev, aid)["hechos"] if h["origen"] == "automatico" and h["tipo_dato"] == "fecha_evento")
    r = ev.c.patch(f"/api/evidencia/hechos/{auto['id']}", headers=ev.h, json={"descripcion": "Inicio de la relación laboral", "fecha": "2020-01-15"})
    editado = r.json()
    assert editado["estado"] == "editado" and editado["original"]["descripcion"] == auto["descripcion"]
    assert any(e["id"] == editado["id"] for e in panel(ev, aid)["cronologia"]["eventos"])
    # Descartar lo saca de la cronología; reabrir lo devuelve a revisión
    ev.c.post(f"/api/evidencia/hechos/{editado['id']}/descartar", headers=ev.h)
    assert all(e["id"] != editado["id"] for e in panel(ev, aid)["cronologia"]["eventos"])
    assert ev.c.post(f"/api/evidencia/hechos/{editado['id']}/reabrir", headers=ev.h).json()["estado"] == "por_revisar"
    # Solo se vinculan a la matriz hechos revisados
    pid = ev.c.post(f"/api/evidencia/asuntos/{aid}/puntos", headers=ev.h, json={"descripcion": "Inicio"}).json()["id"]
    assert ev.c.post(f"/api/evidencia/puntos/{pid}/vinculos", headers=ev.h, json={"hecho_id": editado["id"]}).status_code == 409
    assert ev.c.post(f"/api/evidencia/puntos/{pid}/vinculos", headers=ev.h, json={"documento_id": doc, "pagina": 1}).status_code == 201
    r = ev.c.patch(f"/api/evidencia/puntos/{pid}", headers=ev.h, json={"estado": "respaldado"}).json()
    assert (r["estado"], r["estado_decidido_por"]) == ("respaldado", "Admin 1")
    assert ev.c.patch(f"/api/evidencia/puntos/{pid}", headers=ev.h, json={"estado": "ganado"}).status_code == 422
    # El documento fuente no se puede borrar mientras sostiene hechos revisados o la matriz
    r = ev.c.delete(f"/api/evidencia/documentos/{doc}", headers=ev.h)
    assert r.status_code == 409
    acciones = {a.accion for a in db.query(m.Auditoria)}
    assert {"ev_hecho_capturado", "ev_hecho_editado", "ev_hecho_descartado", "ev_hecho_reabierto",
            "ev_vinculo_agregado", "ev_punto_estado"} <= acciones


def test_archivos_invalidos_e_ilegibles(ev):
    aid = asunto(ev)
    res = subir(ev, aid, ("virus.exe", b"MZ\x90\x00"), ("falso.pdf", b"%PDF-1.7 basura"), ("rota.png", b"\x89PNG\r\n\x1a\n000"))
    assert [r["aceptado"] for r in res] == [False, False, False]
    # Una página en blanco no se puede leer: queda «requiere revisión» y se puede seguir trabajando
    blanco = pymupdf.open()
    blanco.new_page()
    subir(ev, aid, ("escaneo_en_blanco.pdf", blanco.tobytes()))
    d = panel(ev, aid)["documentos"][0]
    assert d["estado"] == "requiere_revision" and "página(s) 1" in d["error"]
    assert ev.c.post(f"/api/evidencia/asuntos/{aid}/pendientes", headers=ev.h, json={"descripcion": "Volver a escanear"}).status_code == 201


def test_pendientes_y_exportaciones(ev, db):
    aid = asunto(ev, nombre="Asunto exportable", cliente="Cliente ficticio")
    subir(ev, aid, ("contrato.pdf", CONTRATO))
    p = panel(ev, aid)
    inicio = next(h for h in p["hechos"] if "inicia el 15 de enero" in h["descripcion"])
    ev.c.post(f"/api/evidencia/hechos/{inicio['id']}/confirmar", headers=ev.h)
    sin_revisar = next(h for h in p["hechos"] if h["estado"] == "por_revisar" and h["id"] != inicio["id"])
    descartado = next(h for h in p["hechos"] if h["id"] not in (inicio["id"], sin_revisar["id"]))
    ev.c.post(f"/api/evidencia/hechos/{descartado['id']}/descartar", headers=ev.h)
    ev.c.post(f"/api/evidencia/asuntos/{aid}/puntos", headers=ev.h, json={"descripcion": "Prima vacacional"})
    ev.c.post(f"/api/evidencia/asuntos/{aid}/pendientes", headers=ev.h, json={
        "descripcion": "Recibos de 2024", "responsable": "Cliente", "fecha_seguimiento": "2026-12-04", "nota": "NOTA INTERNA SECRETA"})
    x = ev.c.post(f"/api/evidencia/asuntos/{aid}/pendientes", headers=ev.h, json={"descripcion": "Constancia ya entregada"}).json()
    assert ev.c.patch(f"/api/evidencia/pendientes/{x['id']}", headers=ev.h, json={"estado": "recibido"}).json()["estado"] == "recibido"
    assert ev.c.patch(f"/api/evidencia/pendientes/{x['id']}", headers=ev.h, json={"estado": "inventado"}).status_code == 422

    r = ev.c.get(f"/api/evidencia/asuntos/{aid}/exportar/pdf", headers=ev.h)
    texto = " ".join(pg.get_text() for pg in pymupdf.open(stream=r.content, filetype="pdf"))
    plano = " ".join(texto.split())
    assert "Asunto exportable" in plano and "Índice de documentos" in plano and "Matriz de evidencia" in plano
    assert "inicia el 15 de enero de 2020" in plano and "confirmado por Admin 1" in plano
    assert sin_revisar["descripcion"][:40] not in plano and descartado["descripcion"][:40] not in plano
    assert "propuesto(s) sin revisar (no incluidos)" in plano and "Generado" in plano and "admin1@org1.test" in plano
    assert "contrato.pdf, p. 1" in plano  # referencia a archivo y página

    wb = load_workbook(io.BytesIO(ev.c.get(f"/api/evidencia/asuntos/{aid}/exportar/excel", headers=ev.h).content))
    assert wb.sheetnames == ["Portada", "Índice de documentos", "Cronología", "Matriz de evidencia", "Pendientes", "Hechos sin revisar"]
    crono = list(wb["Cronología"].iter_rows(min_row=2, values_only=True))
    assert len(crono) == 1 and crono[0][5] == 1 and "confirmado" in crono[0][7]
    sin = list(wb["Hechos sin revisar"].iter_rows(min_row=2, values_only=True))
    assert sin and all(f[0].startswith("PROPUESTA SIN REVISAR") for f in sin)
    assert all(descartado["descripcion"] != f[1] for f in sin)

    # Lista para el cliente: solo lo abierto y sin notas internas
    r = ev.c.get(f"/api/evidencia/asuntos/{aid}/exportar/pdf?solo=pendientes", headers=ev.h)
    plano = " ".join(" ".join(pg.get_text() for pg in pymupdf.open(stream=r.content, filetype="pdf")).split())
    assert "Recibos de 2024" in plano and "Constancia ya entregada" not in plano and "SECRETA" not in plano
    wb = load_workbook(io.BytesIO(ev.c.get(f"/api/evidencia/asuntos/{aid}/exportar/excel?solo=pendientes", headers=ev.h).content))
    assert wb.sheetnames == ["Portada", "Pendientes"]
    assert [f[0] for f in wb["Pendientes"].iter_rows(min_row=2, values_only=True)] == ["Recibos de 2024"]
    assert {"ev_exportacion_pdf", "ev_exportacion_excel_pendientes"} <= {a.accion for a in db.query(m.Auditoria)}


# ---------- seguridad ----------

def test_aislamiento_y_roles(ev, org2, plataforma, db):
    activar(plataforma, org2, "evidencia")
    aid = asunto(ev)
    subir(ev, aid, ("contrato.pdf", CONTRATO))
    p = panel(ev, aid)
    did, hid = p["documentos"][0]["id"], p["hechos"][0]["id"]
    pid = ev.c.post(f"/api/evidencia/asuntos/{aid}/puntos", headers=ev.h, json={"descripcion": "Punto"}).json()["id"]
    xid = ev.c.post(f"/api/evidencia/asuntos/{aid}/pendientes", headers=ev.h, json={"descripcion": "Pend"}).json()["id"]
    assert org2.c.get("/api/evidencia/asuntos", headers=org2.h).json() == []
    for metodo, ruta, cuerpo in [
        ("GET", f"/api/evidencia/asuntos/{aid}", None), ("PATCH", f"/api/evidencia/asuntos/{aid}", {"nombre": "Hackeado"}),
        ("GET", f"/api/evidencia/documentos/{did}/archivo", None), ("GET", f"/api/evidencia/documentos/{did}/paginas/1/imagen", None),
        ("PATCH", f"/api/evidencia/documentos/{did}", {"tipo": "Otro"}), ("POST", f"/api/evidencia/hechos/{hid}/confirmar", None),
        ("PATCH", f"/api/evidencia/hechos/{hid}", {"descripcion": "Cambiado"}), ("PATCH", f"/api/evidencia/puntos/{pid}", {"estado": "respaldado"}),
        ("POST", f"/api/evidencia/puntos/{pid}/vinculos", {"documento_id": did}), ("DELETE", f"/api/evidencia/pendientes/{xid}", None),
        ("GET", f"/api/evidencia/asuntos/{aid}/exportar/pdf", None), ("POST", f"/api/evidencia/asuntos/{aid}/documentos", None),
    ]:
        r = org2.c.request(metodo, ruta, headers=org2.h, json=cuerpo)
        assert r.status_code in (404, 422), f"{metodo} {ruta}: {r.status_code}"
        if r.status_code == 422:  # solo validación del cuerpo, nunca acceso
            assert metodo == "POST" and ruta.endswith("/documentos")
    # Un hecho no puede tomar como fuente un documento de otra organización
    aid2 = asunto(org2)
    assert org2.c.post(f"/api/evidencia/asuntos/{aid2}/hechos", headers=org2.h, json={"descripcion": "Ajeno", "documento_id": did}).status_code == 404
    assert panel(ev, aid)["asunto"]["nombre"] == "Asunto ficticio"
    # Consulta: lee y exporta, no modifica
    consulta = ev.usuario("consulta", "con@org1.test")
    assert ev.c.get(f"/api/evidencia/asuntos/{aid}", headers=consulta).status_code == 200
    assert ev.c.get(f"/api/evidencia/asuntos/{aid}/exportar/excel", headers=consulta).status_code == 200
    assert ev.c.post(f"/api/evidencia/hechos/{hid}/confirmar", headers=consulta).status_code == 403
    assert ev.c.post("/api/evidencia/asuntos", headers=consulta, json={"nombre": "No"}).status_code == 403
    # Eliminar un asunto: solo administrador y con el nombre exacto
    analista = ev.usuario("analista", "ana@org1.test")
    assert ev.c.post(f"/api/evidencia/asuntos/{aid}/eliminar", headers=analista, json={"confirmar_nombre": "Asunto ficticio"}).status_code == 403
    assert ev.c.post(f"/api/evidencia/asuntos/{aid}/eliminar", headers=ev.h, json={"confirmar_nombre": "otro"}).status_code == 422
    assert ev.c.post(f"/api/evidencia/asuntos/{aid}/eliminar", headers=ev.h, json={"confirmar_nombre": "Asunto ficticio"}).status_code == 200
    assert db.query(m.EvDocumento).filter_by(asunto_id=aid).count() == 0


def test_eliminar_cliente_borra_evidencia(ev, plataforma, db):
    aid = asunto(ev)
    subir(ev, aid, ("contrato.pdf", CONTRATO))
    r = plataforma.c.post(f"/api/plataforma/clientes/{ev.org_id}/eliminar", headers=plataforma.h, json={"confirmar_nombre": "Org 1"})
    assert r.status_code == 200, r.text
    assert db.query(m.EvAsunto).count() == 0 and db.query(m.EvHecho).count() == 0
    assert db.query(m.OrganizacionModulo).filter_by(organizacion_id=ev.org_id).count() == 0


def test_demo_de_evidencia(db, cliente):
    from app.services.semilla import sembrar_demo
    sembrar_demo(db)
    assert demo.sembrar(db) is True and demo.sembrar(db) is False  # una sola vez
    a = db.query(m.EvAsunto).one()
    assert db.query(m.EvDocumento).filter_by(asunto_id=a.id).count() == 4
    assert db.query(m.EvHecho).filter(m.EvHecho.estado == "confirmado").count() >= 3
    assert db.query(m.EvPendiente).count() == 3
    # Si el disco se borra, los documentos ficticios se regeneran idénticos
    import os
    for d in db.query(m.EvDocumento):
        os.unlink(d.ruta)
    assert demo.restaurar_archivos(db) == {"restaurados": 4, "perdidos": 0}


def test_nomina_sigue_igual_sin_evidencia(org):
    """Una organización solo con Nómina usa el sistema exactamente como antes."""
    eid = org.expediente()
    org.subir(eid, crear_pdf([recibo("01-15 de Enero de 2025", BASE, num="1")]))
    assert org.resultado(eid)["quincenas"][0]["total"] == "10810.00"
