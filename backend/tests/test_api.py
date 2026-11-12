"""Flujo completo por la API: persistencia, seguridad multi-organización, revisión y exportación."""
import io
from decimal import Decimal

import pymupdf
from openpyxl import load_workbook

from app import models as m
from app.sinteticos import BASE, CASO_ACEPTACION, crear_pdf, recibo

ENE1, ENE2, FEB1 = "01-15 de Enero de 2025", "16-31 de Enero de 2025", "01-15 de Febrero de 2025"


def _pdf_trimestre(extra=()):
    return crear_pdf([recibo(ENE1, CASO_ACEPTACION, num="1"), recibo(ENE2, BASE, num="2"),
                      recibo(FEB1, BASE, num="3"), *extra])


# ---------- flujo y persistencia ----------

def test_flujo_completo_y_paginas_no_son_quincenas(org, db):
    eid = org.expediente()
    assert org.c.get(f"/api/expedientes/{eid}", headers=org.h).json()["estado"] == "nuevo"
    assert org.subir(eid, _pdf_trimestre())[0]["aceptado"]
    exp = org.c.get(f"/api/expedientes/{eid}", headers=org.h).json()
    assert exp["estado"] == "pendiente_revision" and exp["quincenas_esperadas"] == 6
    doc = org.c.get(f"/api/expedientes/{eid}/documentos", headers=org.h).json()[0]
    assert (doc["paginas"], doc["paginas_recibo"], doc["paginas_informativas"]) == (6, 3, 3)
    res = org.resultado(eid)
    assert [q["estado"] for q in res["quincenas"]] == ["con_prestaciones"] * 3 + ["faltante"] * 3
    assert res["quincenas"][0]["total"] == "10408.60" and res["quincenas"][1]["total"] == "10810.00"
    assert res["total_expediente"] == "32028.60" and res["provisional"] and res["puede_validarse"]
    assert res["catalogo"]["version"] == 1
    # Importes persistidos como NUMERIC/Decimal y claves como texto
    f = db.query(m.Fila).filter_by(clave="0102").first()
    assert isinstance(f.importe, Decimal) and f.clave_leida == "0102"
    assert str(m.Fila.__table__.c.importe.type) == "NUMERIC(14, 2)"


def test_archivo_identico_se_rechaza_y_reintento_no_duplica(org, db):
    eid = org.expediente()
    datos = _pdf_trimestre()
    did = org.subir(eid, datos)[0]["documento_id"]
    repetido = org.subir(eid, datos, "otro_nombre.pdf")[0]
    assert not repetido["aceptado"] and repetido["duplicado_de"] == did
    antes = org.resultado(eid)["total_expediente"]
    for _ in range(2):
        r = org.c.post(f"/api/documentos/{did}/reintentar", headers=org.h, json={"forzar": True})
        assert r.status_code == 200, r.text
    assert db.query(m.Recibo).count() == 3 and db.query(m.Pagina).count() == 6
    assert org.resultado(eid)["total_expediente"] == antes
    assert org.c.post(f"/api/documentos/{did}/reintentar", headers=org.h, json={}).status_code == 409


def test_validacion_de_archivos(org):
    eid = org.expediente()
    def sube(nombre, datos):
        return org.c.post(f"/api/expedientes/{eid}/documentos", headers=org.h,
                          files=[("archivos", (nombre, datos, "application/pdf"))]).json()[0]
    assert not sube("virus.exe", b"MZ....")["aceptado"]
    assert not sube("falso.pdf", b"<html>no soy pdf</html>")["aceptado"]
    assert not sube("roto.pdf", b"%PDF-1.7 basura")["aceptado"]
    assert not sube("../../etc/passwd.pdf", b"x")["aceptado"]
    assert org.c.get(f"/api/expedientes/{eid}", headers=org.h).json()["estado"] == "nuevo"


def test_documento_con_error_queda_registrado_y_es_reintentable(org, db, monkeypatch):
    from app.services import procesamiento
    eid = org.expediente()

    def falla(*a, **k):
        raise RuntimeError("fallo simulado de lectura")
    monkeypatch.setattr(procesamiento, "extraer_pagina", falla)
    did = org.subir(eid, _pdf_trimestre())[0]["documento_id"]
    doc = org.c.get(f"/api/expedientes/{eid}/documentos", headers=org.h).json()[0]
    assert doc["estado"] == "error" and "fallo simulado" in doc["error"]
    assert org.c.get(f"/api/expedientes/{eid}", headers=org.h).json()["estado"] == "error"
    assert not org.resultado(eid)["puede_validarse"]
    monkeypatch.undo()
    assert org.c.post(f"/api/documentos/{did}/reintentar", headers=org.h, json={}).status_code == 200
    assert org.resultado(eid)["total_expediente"] == "32028.60" and db.query(m.Recibo).count() == 3


# ---------- revisión, correcciones y validación ----------

def test_pendientes_bloquean_validacion_y_correccion_queda_registrada(org, db):
    eid = org.expediente()
    org.subir(eid, crear_pdf([recibo(ENE1, BASE + [("0512", "DESPENSA", None)], total_percepciones="11293.75")]))
    res = org.resultado(eid)
    assert res["pendientes"][0]["motivo"] == "Importe faltante o ilegible" and not res["puede_validarse"]
    r = org.c.post(f"/api/expedientes/{eid}/validar", headers=org.h, json={"acepta_faltantes": True})
    assert r.status_code == 409 and "pendiente" in r.json()["detail"]["mensaje"]

    fid = res["pendientes"][0]["fila_id"]
    assert org.c.post(f"/api/filas/{fid}/corregir", headers=org.h, json={"importe": "483.75"}).status_code == 422  # sin motivo
    assert org.c.post(f"/api/filas/{fid}/corregir", headers=org.h,
                      json={"importe": "483.755", "motivo": "tres decimales"}).status_code == 422
    r = org.c.post(f"/api/filas/{fid}/corregir", headers=org.h,
                   json={"importe": "483.75", "motivo": "Importe visible en el original"})
    assert r.status_code == 200, r.text
    res = org.resultado(eid)
    assert res["quincenas"][0]["total"] == "11293.75" and res["puede_validarse"]
    c = res["trazabilidad"]["correcciones"][0]
    assert (c["campo"], c["valor_anterior"], c["valor_nuevo"], c["usuario"]) == ("importe", None, "483.75", "admin1@org1.test")
    assert c["motivo"] and c["fecha"] and c["referencia"]["pagina"] == 1
    f = db.get(m.Fila, fid)
    assert f.importe_leido_texto is None and f.corregida  # la lectura original se conserva


def test_corregir_lectura_no_modifica_el_catalogo(org, db):
    eid = org.expediente()
    org.subir(eid, crear_pdf([recibo(ENE1, BASE)]))
    antes = db.query(m.CatalogoEntrada).count()
    fid = org.resultado(eid)["incluidos"][0]["fila_id"]
    org.c.post(f"/api/filas/{fid}/corregir", headers=org.h, json={"clave": "0199", "motivo": "La clave real es 0199"})
    res = org.resultado(eid)
    assert db.query(m.CatalogoEntrada).count() == antes and not db.query(m.CatalogoEntrada).filter_by(clave="0199").count()
    assert [x["clave"] for x in res["excluidos"]] == ["0199"] and res["quincenas"][0]["total"] == "3305.00"


def test_duplicado_complementario_y_decision(org):
    eid = org.expediente()
    org.subir(eid, crear_pdf([recibo(ENE1, BASE, num="9"), recibo(ENE1, BASE, num="9"),
                              recibo(ENE2, BASE, num="10"), recibo(ENE2, [("0609", "DESPENSA EXTRA", "1200.00")], num="10")]))
    res = org.resultado(eid)
    tipos = sorted(a["tipo"] for a in res["alertas"] if a["bloqueante"])
    assert tipos == ["complementario", "posible_duplicado"]
    assert res["quincenas"][0]["total"] == "10810.00" and res["quincenas"][1]["total"] == "12010.00"
    for a in [a for a in res["alertas"] if a["bloqueante"]]:
        decision = "excluir" if a["tipo"] == "posible_duplicado" else "incluir"
        r = org.c.post(f"/api/recibos/{a['recibo_id']}/decision", headers=org.h,
                       json={"decision": decision, "motivo": "Revisado contra el original"})
        assert r.status_code == 200
    res = org.resultado(eid)
    assert res["puede_validarse"] and res["total_expediente"] == "22820.00"
    assert len(res["trazabilidad"]["correcciones"]) == 2


def test_validar_congela_resultado_y_catalogo_versionado(org, db):
    eid = org.expediente()
    org.subir(eid, _pdf_trimestre())
    r = org.c.post(f"/api/expedientes/{eid}/validar", headers=org.h, json={})
    assert r.status_code == 409 and len(r.json()["detail"]["faltantes"]) == 3  # exige reconocer faltantes
    r = org.c.post(f"/api/expedientes/{eid}/validar", headers=org.h, json={"acepta_faltantes": True, "notas": "ok"})
    assert r.status_code == 200 and r.json()["estado_validacion"]["validado"]
    assert org.c.get(f"/api/expedientes/{eid}", headers=org.h).json()["estado"] == "validado"

    # La versión activa es inmutable
    eid_entrada = db.query(m.CatalogoEntrada).filter_by(clave="0102").one().id
    assert org.c.patch(f"/api/catalogos/entradas/{eid_entrada}", headers=org.h, json={"activo": False}).status_code == 409
    # Nueva versión sin 0102, activada: el expediente validado NO cambia
    v2 = org.c.post(f"/api/catalogos/{org.catalogo_id}/versiones", headers=org.h,
                    json={"copiar_de_version_id": org.version_id}).json()
    e0102 = next(e for e in v2["entradas"] if e["clave"] == "0102")
    assert org.c.patch(f"/api/catalogos/entradas/{e0102['id']}", headers=org.h, json={"activo": False}).status_code == 200
    assert org.c.post(f"/api/catalogos/versiones/{v2['id']}/activar", headers=org.h,
                      json={"confirmo_revision": True}).status_code == 200
    res = org.resultado(eid)
    assert res["total_expediente"] == "32028.60" and res["catalogo"]["version"] == 1 and not res["provisional"]
    # Validado = solo lectura hasta reabrir
    fid = res["incluidos"][0]["fila_id"]
    assert org.c.post(f"/api/filas/{fid}/corregir", headers=org.h, json={"importe": "1.00", "motivo": "prueba"}).status_code == 409
    assert org.c.post(f"/api/expedientes/{eid}/documentos", headers=org.h,
                      files=[("archivos", ("x.pdf", crear_pdf([recibo(FEB1, BASE)]), "application/pdf"))]).status_code == 409
    assert org.c.post(f"/api/expedientes/{eid}/reabrir", headers=org.h, json={"motivo": "Cambio de catálogo"}).status_code == 200
    # Cambiar de versión es explícito y auditado; entonces sí cambia el resultado
    assert org.c.patch(f"/api/expedientes/{eid}", headers=org.h, json={"catalogo_version_id": v2["id"]}).status_code == 200
    res = org.resultado(eid)
    assert res["catalogo"]["version"] == 2 and res["total_expediente"] == "9803.20" and res["provisional"]
    acciones = [a.accion for a in db.query(m.Auditoria).order_by(m.Auditoria.id)]
    for esperada in ("expediente_validado", "catalogo_version_activada", "expediente_reabierto", "expediente_modificado"):
        assert esperada in acciones


def test_catalogo_borrador_no_se_puede_usar_ni_activar_sin_revision(org):
    v = org.c.post(f"/api/catalogos/{org.catalogo_id}/versiones", headers=org.h, json={}).json()
    r = org.c.post("/api/expedientes", headers=org.h, json={
        "trabajador_nombre": "X Y", "periodo_inicio": "2025-01-01", "periodo_fin": "2025-01-31", "catalogo_version_id": v["id"]})
    assert r.status_code == 409
    assert org.c.post(f"/api/catalogos/versiones/{v['id']}/entradas", headers=org.h,
                      json={"clave": "102", "descripcion": "SIN CERO"}).status_code == 422
    org.c.post(f"/api/catalogos/versiones/{v['id']}/entradas", headers=org.h, json={"clave": "0102", "descripcion": "SUELDO BASE"})
    assert org.c.post(f"/api/catalogos/versiones/{v['id']}/activar", headers=org.h, json={"confirmo_revision": False}).status_code == 422
    ok = org.c.post(f"/api/catalogos/versiones/{v['id']}/activar", headers=org.h, json={"confirmo_revision": True}).json()
    assert ok["estado"] == "activo" and ok["entradas"][0]["clave"] == "0102"


def test_ocr_de_catalogo_crea_borrador_con_marcas(org):
    import shutil, pytest
    from tests.test_aceptacion import PDF_CATALOGO
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract no está instalado")
    r = org.c.post(f"/api/catalogos/{org.catalogo_id}/versiones/ocr", headers=org.h,
                   files={"archivo": ("Prestaciones.pdf", PDF_CATALOGO.read_bytes(), "application/pdf")})
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["estado"] == "borrador" and v["entradas_total"] == 124 and v["por_revisar"] > 0
    r = org.c.post(f"/api/catalogos/versiones/{v['id']}/activar", headers=org.h, json={"confirmo_revision": True})
    assert r.status_code == 409 and "por revisar" in r.json()["detail"]


# ---------- exportaciones ----------

def test_exportaciones_coinciden_con_el_resultado(org):
    eid = org.expediente()
    org.subir(eid, _pdf_trimestre())
    res = org.resultado(eid)
    r = org.c.get(f"/api/expedientes/{eid}/exportar/excel", headers=org.h)
    assert r.status_code == 200 and "PROVISIONAL" in r.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Resumen", "Formato quincenal", "Desglose por quincena", "Acumulado por prestación",
                             "Excluidos", "Alertas", "Trazabilidad"]
    fq = list(wb["Formato quincenal"].iter_rows(values_only=True))
    assert fq[0] == ("Quincena 1", None) and fq[1] == ("Del 1 de enero al 15 de enero de 2025", None)
    assert fq[2] == ("Sueldo base", Decimal("7215.40")) or (fq[2][0], Decimal(str(fq[2][1]))) == ("Sueldo base", Decimal("7215.40"))
    assert [Decimal(str(f[1])) for f in fq if f[0] and str(f[0]).startswith("TOTAL")] == [Decimal(q["total"]) for q in res["quincenas"] if q["estado"] != "faltante"]
    assert sum(1 for f in fq if f[0] and "FALTANTE" in str(f[0])) == 3
    ws = wb["Desglose por quincena"]
    filas = list(ws.iter_rows(values_only=True))
    assert filas[0] == ("Quincena", "Fecha inicial", "Fecha final", "Clave", "Concepto", "Importe", "Total de la quincena")
    conceptos = [f for f in filas[1:] if f[3]]
    totales = [f for f in filas[1:] if f[6] is not None]
    assert [(f[3], Decimal(str(f[5]))) for f in conceptos] == [(x["clave"], Decimal(x["importe"])) for x in res["incluidos"]]
    assert all(isinstance(f[3], str) and len(f[3]) == 4 for f in conceptos)  # «0102» sigue siendo texto
    assert [Decimal(str(f[6])) for f in totales] == [Decimal(q["total"]) for q in res["quincenas"] if q["estado"] != "faltante"]
    assert sum(Decimal(str(f[5])) for f in conceptos) == Decimal(res["total_expediente"])
    assert sum(1 for f in filas if f[4] and "FALTANTE" in str(f[4])) == 3
    assert filas[1][1].strftime("%d/%m/%Y") == "01/01/2025" and ws["B2"].number_format == "DD/MM/YYYY"
    acum = list(wb["Acumulado por prestación"].iter_rows(min_row=2, values_only=True))
    assert {a[0]: Decimal(str(a[4])) for a in acum[:-1]} == {a["clave"]: Decimal(a["total"]) for a in res["acumulado_por_clave"]}
    assert Decimal(str(acum[-1][4])) == Decimal(res["total_expediente"])
    resumen = {a: b for a, b in wb["Resumen"].iter_rows(values_only=True) if a}
    assert Decimal(str(resumen["TOTAL DEL EXPEDIENTE (MXN)"])) == Decimal(res["total_expediente"])
    assert "PROVISIONAL" in resumen["Estado de validación"] and "quincena en que" in resumen["Política de retroactivos"]
    assert len(list(wb["Excluidos"].iter_rows(min_row=2))) == len(res["excluidos"]) == 4

    r = org.c.get(f"/api/expedientes/{eid}/exportar/pdf", headers=org.h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    texto = " ".join(p.get_text() for p in pymupdf.open(stream=r.content, filetype="pdf"))
    for esperado in ("PROVISIONAL", "$10,408.60", "$32,028.60", "versión 1", "quincena en que", "01/01/2025", "FALTANTE"):
        assert esperado in texto, esperado
    org.c.post(f"/api/expedientes/{eid}/validar", headers=org.h, json={"acepta_faltantes": True})
    r = org.c.get(f"/api/expedientes/{eid}/exportar/pdf", headers=org.h)
    texto = " ".join(p.get_text() for p in pymupdf.open(stream=r.content, filetype="pdf"))
    assert "VALIDADO por admin1@org1.test" in texto and "PROVISIONAL" not in texto and "validado" in r.headers["content-disposition"]


# ---------- seguridad ----------

def test_aislamiento_entre_organizaciones(org, org2, db):
    eid = org.expediente()
    did = org.subir(eid, _pdf_trimestre())[0]["documento_id"]
    rid = db.query(m.Recibo).first().id
    fid = db.query(m.Fila).first().id
    assert org2.c.get("/api/expedientes", headers=org2.h).json() == []
    gets = [f"/api/expedientes/{eid}", f"/api/expedientes/{eid}/resultado", f"/api/expedientes/{eid}/documentos",
            f"/api/expedientes/{eid}/recibos", f"/api/expedientes/{eid}/correcciones",
            f"/api/expedientes/{eid}/exportar/excel", f"/api/expedientes/{eid}/exportar/pdf",
            f"/api/documentos/{did}/archivo", f"/api/documentos/{did}/paginas/1/imagen", f"/api/recibos/{rid}",
            f"/api/catalogos/versiones/{org.version_id}"]
    for url in gets:
        assert org2.c.get(url, headers=org2.h).status_code == 404, url
        assert org.c.get(url, headers=org.h).status_code == 200, url
        assert org.c.get(url).status_code == 401, url
    m_ = {"motivo": "intento ajeno"}
    posts = [(f"/api/filas/{fid}/corregir", {"importe": "1.00", **m_}), (f"/api/filas/{fid}/confirmar", m_),
             (f"/api/recibos/{rid}/decision", {"decision": "excluir", **m_}), (f"/api/expedientes/{eid}/validar", {}),
             (f"/api/expedientes/{eid}/reabrir", m_), (f"/api/documentos/{did}/reintentar", {"forzar": True}),
             (f"/api/catalogos/versiones/{org.version_id}/activar", {"confirmo_revision": True}),
             (f"/api/catalogos/{org.catalogo_id}/versiones", {})]
    for url, cuerpo in posts:
        assert org2.c.post(url, headers=org2.h, json=cuerpo).status_code == 404, url
    assert org2.c.delete(f"/api/documentos/{did}", headers=org2.h).status_code == 404
    assert org2.c.post(f"/api/expedientes/{eid}/documentos", headers=org2.h,
                       files=[("archivos", ("a.pdf", _pdf_trimestre(), "application/pdf"))]).status_code == 404
    # No se puede crear un expediente con el catálogo de otra organización
    r = org2.c.post("/api/expedientes", headers=org2.h, json={
        "trabajador_nombre": "X Y", "periodo_inicio": "2025-01-01", "periodo_fin": "2025-01-31",
        "catalogo_version_id": org.version_id})
    assert r.status_code == 404
    assert all(u["email"].endswith("org2.test") for u in org2.c.get("/api/usuarios", headers=org2.h).json())
    assert all(a["usuario"] in (None, "admin2@org2.test") for a in org2.c.get("/api/auditoria", headers=org2.h).json())
    assert org.resultado(eid)["total_expediente"] == "32028.60"  # nada cambió


def test_roles(org):
    eid = org.expediente()
    org.subir(eid, _pdf_trimestre())
    analista, consulta = org.usuario("analista", "ana@org1.test"), org.usuario("consulta", "con@org1.test")
    fid = org.resultado(eid)["incluidos"][0]["fila_id"]
    # Consulta: lee y descarga, no modifica
    assert org.c.get(f"/api/expedientes/{eid}/resultado", headers=consulta).status_code == 200
    assert org.c.get(f"/api/expedientes/{eid}/exportar/excel", headers=consulta).status_code == 200
    for url, cuerpo in [(f"/api/filas/{fid}/corregir", {"importe": "1.00", "motivo": "x y z"}),
                        (f"/api/expedientes/{eid}/validar", {"acepta_faltantes": True}),
                        ("/api/expedientes", {"trabajador_nombre": "A B", "periodo_inicio": "2025-01-01",
                                              "periodo_fin": "2025-01-31", "catalogo_version_id": org.version_id})]:
        assert org.c.post(url, headers=consulta, json=cuerpo).status_code == 403, url
    # Analista: opera expedientes, pero no usuarios ni catálogos
    assert org.c.post(f"/api/expedientes/{eid}/validar", headers=analista, json={"acepta_faltantes": True}).status_code == 200
    assert org.c.get("/api/usuarios", headers=analista).status_code == 403
    assert org.c.get("/api/auditoria", headers=analista).status_code == 403
    assert org.c.post("/api/catalogos", headers=analista, json={"nombre": "Otro"}).status_code == 403
    assert org.c.post(f"/api/catalogos/{org.catalogo_id}/versiones", headers=analista, json={}).status_code == 403
    # Usuario desactivado pierde acceso de inmediato; siempre queda un administrador
    uid = next(u["id"] for u in org.c.get("/api/usuarios", headers=org.h).json() if u["email"] == "ana@org1.test")
    org.c.patch(f"/api/usuarios/{uid}", headers=org.h, json={"activo": False})
    assert org.c.get("/api/expedientes", headers=analista).status_code == 401
    assert org.c.patch(f"/api/usuarios/{org.usuario_id}", headers=org.h, json={"rol": "consulta"}).status_code == 409


def test_autenticacion(cliente, org, db):
    u = db.query(m.Usuario).first()
    assert u.hash_contrasena.startswith("$2") and "Contrasena" not in u.hash_contrasena
    assert cliente.post("/api/auth/login", json={"email": u.email, "contrasena": "incorrecta"}).status_code == 401
    assert cliente.get("/api/expedientes", headers={"Authorization": "Bearer token.falso.xyz"}).status_code == 401
    assert cliente.post("/api/auth/registro", json={"organizacion": "Z", "nombre": "Z", "email": "z@z.test",
                                                    "contrasena": "corta"}).status_code == 422
    for _ in range(8):
        cliente.post("/api/auth/login", json={"email": u.email, "contrasena": "incorrecta"})
    assert cliente.post("/api/auth/login", json={"email": u.email, "contrasena": "Contrasena-Segura-1"}).status_code == 429


def test_auditoria_sin_datos_personales(org, db):
    eid = org.expediente(nombre="EJEMPLO SINTETICO MARIA FERNANDA")
    org.subir(eid, _pdf_trimestre())
    org.c.get(f"/api/expedientes/{eid}/exportar/excel", headers=org.h)
    registros = db.query(m.Auditoria).all()
    assert {"organizacion_creada", "expediente_creado", "documento_cargado", "exportacion_excel"} <= {a.accion for a in registros}
    volcado = " ".join(str(a.detalle) for a in registros)
    assert "EJEMPLO" not in volcado and "900000001" not in volcado


def test_ia_apagada_por_defecto(org, db):
    eid = org.expediente()
    org.subir(eid, crear_pdf([recibo(ENE1, BASE)]))
    fid = db.query(m.Fila).first().id
    assert org.c.post(f"/api/filas/{fid}/sugerencia-ia", headers=org.h).status_code == 404
    assert org.c.get("/api/auth/yo", headers=org.h).json()["ia_habilitada"] is False


def test_demo_sintetica(db):
    from app.services.calculo import quincenas_esperadas  # noqa: F401
    from app.services.resultados import calcular_expediente
    from app.services.semilla import sembrar_demo
    assert sembrar_demo(db)["creado"] and not sembrar_demo(db)["creado"]
    limpio, inc = db.query(m.Expediente).order_by(m.Expediente.id).all()
    r1 = calcular_expediente(db, limpio)
    assert r1["puede_validarse"] and [q["total"] for q in r1["quincenas"]] == ["10810.00", "12510.00"] * 3
    r2 = calcular_expediente(db, inc)
    tipos = {a["tipo"] for a in r2["alertas"]}
    assert {"fila_pendiente", "posible_duplicado", "complementario", "otro_trabajador", "plazas", "quincenas_faltantes"} <= tipos
    assert r2["quincenas"][0]["plazas"][0]["total"] == "10408.60"
    assert [q["estado"] for q in r2["quincenas"]][2] == "cero" and r2["faltantes"][0]["quincena"] == "2025-04-Q1"


def test_exportacion_con_plazas_separadas_no_las_suma(org):
    eid = org.expediente(fin="2025-01-15")
    org.subir(eid, crear_pdf([recibo(ENE1, BASE, num="1"), recibo(ENE1, [("0102", "SUELDO BASE", "3100.00")], num="2",
                                                                    plaza="990000000000002")]))
    assert "plazas" in [a["tipo"] for a in org.resultado(eid)["alertas"] if a["bloqueante"]]
    org.c.patch(f"/api/expedientes/{eid}", headers=org.h, json={"decision_plazas": "separar"})
    res = org.resultado(eid)
    assert res["total_expediente"] is None and res["puede_validarse"]
    wb = load_workbook(io.BytesIO(org.c.get(f"/api/expedientes/{eid}/exportar/excel", headers=org.h).content))
    filas = list(wb["Desglose por quincena"].iter_rows(values_only=True))
    assert filas[0][3] == "Plaza"
    assert sorted(Decimal(str(f[7])) for f in filas[1:] if f[7] is not None) == [Decimal("3100.00"), Decimal("10810.00")]
    resumen = {a: b for a, b in wb["Resumen"].iter_rows(values_only=True) if a}
    assert "TOTAL DEL EXPEDIENTE (MXN)" not in resumen and Decimal(str(resumen["Plaza 990000000000002"])) == Decimal("3100.00")
    org.c.patch(f"/api/expedientes/{eid}", headers=org.h, json={"decision_plazas": "consolidar"})
    assert org.resultado(eid)["total_expediente"] == "13910.00"


def test_prelectura_propone_datos_sin_guardar_nada(org, org2, db):
    pdf = crear_pdf([recibo(ENE2, BASE, num="2"), recibo("01-15 de Marzo de 2025", BASE, num="5"),
                     recibo(FEB1, BASE, num="3"), recibo(ENE2, BASE, num="9", nombre="OTRA PERSONA FICTICIA",
                                                         clave_servidor="900000999")])
    r = org.c.post("/api/expedientes/prelectura", headers=org.h, files=[("archivos", ("r.pdf", pdf, "application/pdf"))])
    assert r.status_code == 200, r.text
    d = r.json()
    s = d["sugerencia"]
    assert (s["nombre"], s["identificador_laboral"]) == ("EJEMPLO SINTETICO MARIA FERNANDA", "900000001")
    assert (s["periodo_inicio"], s["periodo_fin"], s["recibos"]) == ("2025-01-16", "2025-03-15", 3)
    assert s["quincenas_en_periodo"] == 4 and [q["quincena"] for q in s["quincenas_sin_recibo"]] == ["2025-02-Q2"]
    assert d["archivos"][0] == {"nombre": "r.pdf", "paginas": 8, "recibos": 4, "informativas": 4, "sin_clasificar": 0, "ocr": 0}
    assert len(d["trabajadores"]) == 2 and any("2 trabajadores" in a for a in d["avisos"])
    assert db.query(m.Documento).count() == 0 and db.query(m.Recibo).count() == 0  # nada persistido
    # El detalle de auditoría no lleva datos personales
    a = db.query(m.Auditoria).filter_by(accion="prelectura_pdf").one()
    assert a.detalle == {"archivos": 1, "recibos": 4}
    # Sin recibos: no inventa datos
    vacio = org.c.post("/api/expedientes/prelectura", headers=org.h,
                       files=[("archivos", ("v.pdf", PDF_INFO, "application/pdf"))]).json()
    assert vacio["sugerencia"] is None and vacio["total_recibos"] == 0
    # Roles y validación de archivo
    consulta = org.usuario("consulta", "con2@org1.test")
    assert org.c.post("/api/expedientes/prelectura", headers=consulta, files=[("archivos", ("r.pdf", pdf, "application/pdf"))]).status_code == 403
    assert org.c.post("/api/expedientes/prelectura", headers=org.h, files=[("archivos", ("x.pdf", b"no pdf", "application/pdf"))]).status_code == 415
    # El expediente creado con la propuesta suma exactamente los recibos del trabajador propuesto
    eid = org.expediente(ini=s["periodo_inicio"], fin=s["periodo_fin"], nombre=s["nombre"], identificador_laboral=s["identificador_laboral"])
    org.subir(eid, pdf)
    res = org.resultado(eid)
    assert res["total_expediente"] == "32430.00" and res["periodo_detectado"] == {"inicio": "2025-01-16", "fin": "2025-03-15"}


def _pdf_informativo():
    import io as _io
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from app.sinteticos import _dibujar_informativa
    b = _io.BytesIO()
    c = canvas.Canvas(b, pagesize=letter)
    _dibujar_informativa(c)
    c.save()
    return b.getvalue()


PDF_INFO = _pdf_informativo()


# ---------- verificación con IA (cliente simulado: no se llama a ningún servicio externo) ----------

class _ClienteFalso:
    """Imita client.messages.parse devolviendo lecturas preparadas; registra lo que se le envía."""
    def __init__(self, lecturas):
        self.lecturas, self.llamadas, self.messages = list(lecturas), [], self

    def parse(self, **kw):
        self.llamadas.append(kw)
        lectura = self.lecturas.pop(0)
        if isinstance(lectura, Exception):
            raise lectura
        return type("R", (), {"stop_reason": "end_turn" if lectura is not None else "refusal", "parsed_output": lectura})()


def test_verificacion_ia_solo_compara_y_nunca_cambia_importes(org, db, monkeypatch):
    from app.config import ajustes
    from app.services import ia_adaptador as ia
    from app.services.verificacion_ia import verificar_expediente
    eid = org.expediente()
    org.subir(eid, crear_pdf([recibo(ENE1, BASE, num="1"), recibo(ENE2, BASE, num="2"), recibo(FEB1, BASE, num="3")]))
    assert org.c.post(f"/api/expedientes/{eid}/verificar-ia", headers=org.h).status_code == 404  # apagada por defecto
    antes = org.resultado(eid)
    assert antes["ia"]["habilitada"] is False and antes["ia"]["recibos"] == {"sin_verificar": 3}
    monkeypatch.setattr(ajustes(), "ia_habilitada", True)
    filas = lambda *xs: [ia.FilaIA(clave=c, importe=i) for c, i in xs]  # noqa: E731
    bien = ia.LecturaIA(legible=True, percepciones=filas(("0102", "7505.00"), ("0104", "2505.00"), ("0603", "800.00")), total_percepciones="10810.00")
    mal = ia.LecturaIA(legible=True, percepciones=filas(("0102", "7505.00"), ("0104", "2550.00"), ("0603", "800.00"), ("0512", "483.75")), total_percepciones="10810.00")
    cliente = _ClienteFalso([bien, mal, None])
    assert verificar_expediente(db, eid, cliente)["estado"] == "terminada"
    # Se envía la imagen como dato y la instrucción de ignorar instrucciones incrustadas
    k = cliente.llamadas[0]
    assert k["messages"][0]["content"][0]["type"] == "image" and "DATOS" in k["system"] and k["output_format"] is ia.LecturaIA
    res = org.resultado(eid)
    assert res["ia"]["recibos"] == {"coincide": 1, "discrepancia": 1, "no_legible": 1}
    assert [q["ia"] for q in res["quincenas"][:3]] == ["coincide", "discrepancia", "discrepancia"]
    alertas = [a for a in res["alertas"] if a["tipo"] == "verificacion_ia"]
    assert len(alertas) == 2 and all(a["bloqueante"] for a in alertas) and not res["puede_validarse"]
    assert "el sistema leyó 2505.00 y la IA leyó 2550.00" in alertas[0]["mensaje"] and "0512" in alertas[0]["mensaje"]
    # La IA no tocó nada: mismos importes, mismo total, mismas filas
    assert res["total_expediente"] == antes["total_expediente"] == "32430.00"
    assert [(x["clave"], x["importe"]) for x in res["incluidos"]] == [(x["clave"], x["importe"]) for x in antes["incluidos"]]
    assert db.query(m.Fila).filter_by(corregida=True).count() == 0 and db.query(m.CatalogoEntrada).filter_by(clave="2550").count() == 0
    # Una persona resuelve: confirma un recibo y corrige el otro (lo que deja la verificación desactualizada)
    r2, r3 = alertas[0]["recibo_id"], alertas[1]["recibo_id"]
    org.c.post(f"/api/recibos/{r2}/decision", headers=org.h, json={"decision": "incluir", "motivo": "Original revisado: 2,505.00 es correcto"})
    fid = next(x["fila_id"] for x in res["incluidos"] if x["recibo_id"] == r3 and x["clave"] == "0603")
    org.c.post(f"/api/filas/{fid}/corregir", headers=org.h, json={"concepto": "DIAS CIVICOS (revisado)", "motivo": "Sin cambio de importe"})
    res = org.resultado(eid)
    assert [a for a in res["alertas"] if a["tipo"] == "verificacion_ia"][0]["recibo_id"] == r3  # concepto no cambia la huella
    org.c.post(f"/api/filas/{fid}/corregir", headers=org.h, json={"importe": "801.00", "motivo": "Prueba de caducidad"})
    res = org.resultado(eid)
    assert res["recibos"][str(r3)]["ia"]["estado"] == "desactualizada"
    assert not [a for a in res["alertas"] if a["tipo"] == "verificacion_ia"]
    # Reverificar solo reenvía lo que cambió
    cliente2 = _ClienteFalso([ia.LecturaIA(legible=True, percepciones=filas(("0102", "7505.00"), ("0104", "2505.00"), ("0603", "801.00")))])
    verificar_expediente(db, eid, cliente2)
    assert len(cliente2.llamadas) == 1 and org.resultado(eid)["ia"]["recibos"] == {"coincide": 2, "discrepancia": 1}
    # Auditoría y endpoint con IA activa
    monkeypatch.setattr(ia, "crear_cliente", lambda: _ClienteFalso([bien] * 3))
    assert org.c.post(f"/api/expedientes/{eid}/verificar-ia", headers=org.h).status_code == 200
    assert "ia_verificacion_iniciada" in [a.accion for a in db.query(m.Auditoria)]


def test_verificacion_ia_se_detiene_si_el_servicio_falla(org, db, monkeypatch):
    from app.config import ajustes
    from app.services.verificacion_ia import comparar, verificar_expediente
    eid = org.expediente()
    org.subir(eid, _pdf_trimestre())
    monkeypatch.setattr(ajustes(), "ia_habilitada", True)
    r = verificar_expediente(db, eid, _ClienteFalso([RuntimeError("sin credenciales")] * 3))
    assert r["estado"] == "error" and "3 recibos seguidos" in r["error"]
    res = org.resultado(eid)
    assert res["ia"]["recibos"] == {"error": 3} and res["total_expediente"] == "32028.60"
    assert not [a for a in res["alertas"] if a["tipo"] == "verificacion_ia"]  # un fallo del servicio no bloquea
    assert comparar([("0102", Decimal("1.00"))], None) == ("no_legible", ["La IA no pudo leer el recibo con certeza."])
