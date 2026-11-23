"""Clientes del despacho: directorio, alta desde constancia fiscal y Excel, vínculos con los módulos (Agenda,
Evidencia, AFORE, Leads, Nómina), documentos, honorarios, pagos con recibo, recordatorio y aislamiento."""
import io
from datetime import date, timedelta
from decimal import Decimal

import pymupdf
from openpyxl import Workbook

from app import models as m
from app.db import SessionLocal
from app.services.clientes import base as cb, lectura

from .test_agenda import buzon  # noqa: F401
from .test_evidencia import activar

C = "/api/clientes"
HOY = date.today()


def nuevo(o, **kw):
    r = o.c.post(C, headers=o.h, json={"nombre": "Juana Ejemplo Pérez", "email": "juana@ejemplo.test", "telefono": "5512345678", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def pdf(lineas: list[str]) -> bytes:
    doc = pymupdf.open()
    pag = doc.new_page()
    y = 50
    for ln in lineas:
        pag.insert_text((40, y), ln, fontsize=9)
        y += 13
    return doc.tobytes()


CSF = ["CONSTANCIA DE SITUACION FISCAL", "SERVICIO DE ADMINISTRACION TRIBUTARIA", "Cedula de Identificacion Fiscal",
       "RFC:", "EEPJ800101AB1", "CURP:", "EEPJ800101MMCXRN09", "Nombre (s):", "JUANA", "Primer Apellido:", "EJEMPLO",
       "Segundo Apellido:", "PEREZ", "Datos del domicilio registrado", "Codigo Postal:50000", "Tipo de Vialidad: CALLE",
       "Nombre de Vialidad: HIDALGO", "Numero Exterior: 10", "Numero Interior:", "Nombre de la Colonia: CENTRO",
       "Nombre de la Localidad: TOLUCA", "Nombre del Municipio o Demarcacion Territorial: TOLUCA",
       "Nombre de la Entidad Federativa: MEXICO", "Regimenes:", "Regimen Fecha Inicio Fecha Fin",
       "Regimen de Sueldos y Salarios e Ingresos Asimilados a Salarios 01/01/2010"]


def test_importe_con_letra():
    assert cb.importe_con_letra(Decimal("1234.50")) == "MIL DOSCIENTOS TREINTA Y CUATRO PESOS 50/100 M.N."
    assert cb.importe_con_letra(Decimal("1")) == "UN PESO 00/100 M.N."
    assert cb.importe_con_letra(Decimal("2000000")) == "DOS MILLONES DE PESOS 00/100 M.N."
    assert cb.importe_con_letra(Decimal("121")) == "CIENTO VEINTIUN PESOS 00/100 M.N."
    assert cb.sumar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_leer_constancia(org):
    r = org.c.post(f"{C}/leer-constancia", headers=org.h, files={"archivo": ("csf.pdf", pdf(CSF), "application/pdf")})
    assert r.status_code == 200, r.text
    d = r.json()["datos"]
    assert r.json()["es_constancia"]
    assert d["tipo"] == "fisica" and d["nombre"] == "JUANA EJEMPLO PEREZ" and d["rfc"] == "EEPJ800101AB1" and d["curp"] == "EEPJ800101MMCXRN09"
    assert d["codigo_postal"] == "50000" and d["domicilio"].startswith("CALLE HIDALGO 10, CENTRO, TOLUCA")
    assert d["regimen_fiscal"].startswith("Regimen de Sueldos y Salarios")
    moral = lectura.leer_constancia("\n".join(["CONSTANCIA DE SITUACION FISCAL", "RFC: EFI2001017A3", "Denominación/Razón Social: EMPRESA FICTICIA",
                                                "Régimen Capital: SOCIEDAD ANONIMA DE CAPITAL VARIABLE", "Código Postal: 06600"]))["datos"]
    assert moral["tipo"] == "moral" and moral["nombre"] == "EMPRESA FICTICIA SOCIEDAD ANONIMA DE CAPITAL VARIABLE" and moral["curp"] is None
    assert org.c.post(f"{C}/leer-constancia", headers=org.h, files={"archivo": ("x.pdf", b"hola", "application/pdf")}).status_code == 422


def test_alta_edicion_y_duplicados(org):
    c = nuevo(org, rfc="eepj800101ab1", curp="EEPJ800101MMCXRN09", etiquetas=["Laboral", "laboral ", ""])
    assert c["rfc"] == "EEPJ800101AB1" and c["curp_pista"] and "curp" not in c and c["etiquetas"] == ["Laboral", "laboral"]
    with SessionLocal() as s:
        x = s.get(m.CrCliente, c["id"])
        assert x.curp_cifrado and "EEPJ800101" not in x.curp_cifrado and cb.curp(x) == "EEPJ800101MMCXRN09"
    assert org.c.post(C, headers=org.h, json={"nombre": "Otra", "rfc": "XXX"}).status_code == 422
    r = org.c.post(C, headers=org.h, json={"nombre": "Otra persona", "rfc": "EEPJ800101AB1"})
    assert r.status_code == 409 and "Juana" in r.json()["detail"]
    assert org.c.post(C, headers=org.h, json={"nombre": "juana  ejemplo  PÉREZ"}).status_code == 409
    assert org.c.post(f"{C}?permitir_duplicado=true", headers=org.h, json={"nombre": "Juana Ejemplo Pérez"}).status_code == 201
    e = org.c.put(f"{C}/{c['id']}", headers=org.h, json={"nombre": "Juana Ejemplo Pérez", "rfc": "EEPJ800101AB1", "email": "nuevo@ejemplo.test"}).json()
    assert e["email"] == "nuevo@ejemplo.test" and e["curp_pista"]  # la CURP se conserva si no se envía
    assert org.c.get(f"{C}/buscar?q=juana", headers=org.h).json()[0]["nombre"] == "Juana Ejemplo Pérez"


def test_importar_excel(org):
    nuevo(org)
    wb = Workbook()
    ws = wb.active
    ws.append(["Nombre o razón social", "Tipo", "RFC", "Correo", "Teléfono", "CP"])
    ws.append(["Empresa Ficticia SA de CV", "moral", "EFI2001017A3", "contacto@ficticia.test", 5555555555, 6600])
    ws.append(["Juana Ejemplo Pérez", "física", "", "", "", ""])  # repetida
    ws.append(["Pedro Prueba", "física", "MAL", "", "", ""])  # RFC inválido
    ws.append(["Luis Demo", "", "", "luis@demo.test", "", ""])
    b = io.BytesIO()
    wb.save(b)
    archivo = {"archivo": ("clientes.xlsx", b.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    v = org.c.post(f"{C}/importar", headers=org.h, files=archivo, data={"confirmar": "false"}).json()
    assert (v["nuevos"], v["repetidos"], v["errores"], v["guardado"]) == (2, 1, 1, False), v
    assert len(org.c.get(C, headers=org.h).json()["clientes"]) == 1
    r = org.c.post(f"{C}/importar", headers=org.h, files=archivo, data={"confirmar": "true"}).json()
    assert r["nuevos"] == 2 and r["guardado"]
    lista = {c["nombre"]: c for c in org.c.get(C, headers=org.h).json()["clientes"]}
    assert lista["Empresa Ficticia SA de CV"]["tipo"] == "moral" and lista["Empresa Ficticia SA de CV"]["codigo_postal"] == "06600"
    assert org.c.get(f"{C}/importar/plantilla", headers=org.h).status_code == 200
    csv = "nombre;correo\nAna CSV;ana@csv.test\n".encode()
    assert org.c.post(f"{C}/importar", headers=org.h, files={"archivo": ("c.csv", csv, "text/csv")}, data={"confirmar": "true"}).json()["nuevos"] == 1


def test_vinculos_con_modulos(org, plataforma):
    for mod in ("agenda", "evidencia", "afore", "leads"):
        activar(plataforma, org, mod)
    c = nuevo(org, curp="EEPJ800101MMCXRN09")
    ag = org.c.post("/api/agenda/asuntos", headers=org.h, json={"titulo": "Pérez vs. Empresa", "materia": "laboral", "cr_cliente_id": c["id"]}).json()
    assert ag["cr_cliente_id"] == c["id"] and ag["cliente"] == "Juana Ejemplo Pérez"
    ev = org.c.post("/api/evidencia/asuntos", headers=org.h, json={"nombre": "Carpeta Pérez", "cr_cliente_id": c["id"], "cliente": "otro"}).json()
    assert ev["cliente"] == "Juana Ejemplo Pérez" and ev["cr_cliente_id"] == c["id"]
    af = org.c.post("/api/afore/clientes", headers=org.h, json={"nombre": "Juana Ejemplo Pérez", "cr_cliente_id": c["id"]})
    assert af.status_code == 201, af.text
    assert af.json()["email"] == "juana@ejemplo.test" and af.json()["tiene_curp"]
    eid = org.expediente(nombre="JUANA EJEMPLO PEREZ", cr_cliente_id=c["id"])
    v = org.c.get(f"{C}/{c['id']}", headers=org.h).json()["vinculos"]
    assert sorted(x["modulo"] for x in v) == ["afore", "agenda", "evidencia", "nomina"]
    assert next(x for x in v if x["modulo"] == "nomina")["ruta"] == f"/expedientes/{eid}"
    # el nombre en Evidencia sigue al directorio
    org.c.put(f"{C}/{c['id']}", headers=org.h, json={"nombre": "Juana E. Pérez"})
    assert org.c.get(f"/api/evidencia/asuntos/{ev['id']}", headers=org.h).json()["asunto"]["cliente"] == "Juana E. Pérez"
    # desligar desde Clientes
    assert org.c.put(f"{C}/vinculos/modulo", headers=org.h, json={"modulo": "agenda", "id": ag["id"], "cliente_id": None}).json() == {"ok": True}
    assert org.c.get(f"/api/agenda/asuntos/{ag['id']}", headers=org.h).json()["cr_cliente_id"] is None
    # no se puede borrar si está ligado
    assert org.c.delete(f"{C}/{c['id']}", headers=org.h).status_code == 409


def test_leads_contratar_da_de_alta(org, plataforma):
    activar(plataforma, org, "leads")
    activar(plataforma, org, "evidencia")
    p = org.c.post("/api/leads/prospectos", headers=org.h, json={"nombre": "Mario Prospecto", "telefono": "5511112222", "email": "mario@p.test",
                                                                  "canal": "otro", "proxima": {"tipo": "llamada", "fecha": HOY.isoformat(), "descripcion": "Llamar"}})
    assert p.status_code == 201, p.text
    r = org.c.post(f"/api/leads/prospectos/{p.json()['id']}/contratar", headers=org.h, json={"servicio": "Demanda laboral", "crear_en": "evidencia"})
    assert r.status_code == 200, r.text
    cid = r.json()["cr_cliente_id"]
    c = org.c.get(f"{C}/{cid}", headers=org.h).json()
    assert c["nombre"] == "Mario Prospecto" and c["origen"] == "leads" and c["email"] == "mario@p.test"
    assert sorted(x["modulo"] for x in c["vinculos"]) == ["evidencia", "leads"]


def test_sugerencias_unen_lo_capturado(org, plataforma):
    activar(plataforma, org, "evidencia")
    org.c.post("/api/evidencia/asuntos", headers=org.h, json={"nombre": "Carpeta 1", "cliente": "Rosa Sinlista"})
    org.c.post("/api/evidencia/asuntos", headers=org.h, json={"nombre": "Carpeta 2", "cliente": "ROSA  SINLISTA"})
    org.expediente(nombre="Rosa Sinlista")
    s = org.c.get(f"{C}/sugerencias/modulos", headers=org.h).json()
    g = next(x for x in s if x["clave"] == "ROSA SINLISTA")
    assert len(g["items"]) == 3 and g["cliente_existente"] is None
    r = org.c.post(f"{C}/sugerencias/unir", headers=org.h, json={"nombre": g["nombre"], "items": g["items"]}).json()
    assert len(org.c.get(f"{C}/{r['cliente_id']}", headers=org.h).json()["vinculos"]) == 3
    assert not any(x["clave"] == "ROSA SINLISTA" for x in org.c.get(f"{C}/sugerencias/modulos", headers=org.h).json())


def test_documentos(org):
    c = nuevo(org)
    r = org.c.post(f"{C}/{c['id']}/documentos", headers=org.h, files={"archivo": ("ine.pdf", pdf(["INE de prueba"]), "application/pdf")},
                   data={"tipo": "identificacion"})
    assert r.status_code == 201, r.text
    assert org.c.post(f"{C}/{c['id']}/documentos", headers=org.h, files={"archivo": ("x.exe", b"MZ\x90\x00", "application/pdf")},
                      data={"tipo": "otro"}).status_code == 422
    docs = org.c.get(f"{C}/{c['id']}", headers=org.h).json()["documentos"]
    assert docs[0]["tipo_texto"] == "Identificación oficial"
    a = org.c.get(f"{C}/documentos/{docs[0]['id']}/archivo", headers=org.h)
    assert a.status_code == 200 and a.content.startswith(b"%PDF") and a.headers["cache-control"] == "private, no-store"
    assert org.c.delete(f"{C}/documentos/{docs[0]['id']}", headers=org.h).json() == {"ok": True}


def test_honorarios_pagos_y_recibo(org, buzon):
    c = nuevo(org)
    cid = c["id"]
    org.c.post(f"{C}/{cid}/cargos", headers=org.h, json={"concepto": "Anticipo demanda", "monto": "5000", "vence": (HOY - timedelta(days=10)).isoformat()})
    r = org.c.post(f"{C}/{cid}/cargos", headers=org.h, json={"concepto": "Iguala", "monto": "2000.50", "vence": (HOY + timedelta(days=5)).isoformat(),
                                                              "repetir_meses": 3}).json()
    assert [x["concepto"] for x in r["cargos"]] == ["Anticipo demanda", "Iguala (1/3)", "Iguala (2/3)", "Iguala (3/3)"]
    assert r["cuenta"]["cargado"] == "11001.50" and r["cuenta"]["vencido"] == "5000.00" and r["cuenta"]["saldo"] == "11001.50"
    # pago a cuenta: va a lo más antiguo
    p = org.c.post(f"{C}/{cid}/pagos", headers=org.h, json={"monto": "6000", "fecha": HOY.isoformat(), "metodo": "transferencia", "referencia": "SPEI 123"}).json()
    est = {x["concepto"]: x for x in p["cargos"]}
    assert est["Anticipo demanda"]["estado"] == "pagado" and est["Iguala (1/3)"]["estado"] == "parcial" and est["Iguala (1/3)"]["pagado"] == "1000.00"
    assert p["cuenta"]["vencido"] == "0.00" and p["cuenta"]["saldo"] == "5001.50" and p["pagos"][0]["folio"] == 1
    # pago a un cargo específico
    tercero = est["Iguala (3/3)"]["id"]
    q = org.c.post(f"{C}/{cid}/pagos", headers=org.h, json={"monto": "2000.50", "fecha": HOY.isoformat(), "metodo": "efectivo", "cargo_id": tercero}).json()
    assert {x["concepto"]: x["estado"] for x in q["cargos"]}["Iguala (3/3)"] == "pagado" and q["pagos"][0]["folio"] == 2
    rec = org.c.get(f"{C}/pagos/{q['pago_id']}/recibo", headers=org.h).json()
    assert rec["folio"] == 2 and rec["monto_letra"] == "DOS MIL PESOS 50/100 M.N." and rec["concepto"] == "Iguala (3/3)" and rec["saldo_despues"] == "3001.00"
    assert org.c.post(f"{C}/{cid}/pagos", headers=org.h, json={"monto": "10", "fecha": (HOY + timedelta(days=1)).isoformat()}).status_code == 422
    # resumen general
    t = org.c.get(C, headers=org.h).json()["totales"]
    assert t["por_cobrar"] == "3001.00" and t["vencido"] == "0.00" and Decimal(t["cobrado_mes"]) == Decimal("8000.50")
    # cancelar un pago: solo administrador, con motivo; el folio no se reutiliza
    ana = org.usuario("analista", "analista@org1.test")
    assert org.c.post(f"{C}/pagos/{p['pago_id']}/cancelar", headers=ana, json={"motivo": "Duplicado"}).status_code == 403
    x = org.c.post(f"{C}/pagos/{p['pago_id']}/cancelar", headers=org.h, json={"motivo": "Transferencia rechazada"}).json()
    assert x["cuenta"]["vencido"] == "5000.00"
    assert org.c.post(f"{C}/{cid}/pagos", headers=org.h, json={"monto": "1", "fecha": HOY.isoformat()}).json()["pagos"][0]["folio"] == 3
    # recordatorio: vista previa y envío
    v = org.c.post(f"{C}/{cid}/recordatorio", headers=org.h, json={"mensaje": "Gracias por su preferencia."}).json()
    assert v["para"] == "juana@ejemplo.test" and "Anticipo demanda" in v["texto"] and buzon == []
    assert org.c.post(f"{C}/{cid}/recordatorio", headers=org.h, json={"enviar": True}).json()["ok"]
    assert buzon[0]["para"] == ["juana@ejemplo.test"] and "recordatorio de pago" in buzon[0]["asunto"]
    # cancelar un cargo: lo pagado a él queda a cuenta
    y = org.c.post(f"{C}/cargos/{tercero}/cancelar", headers=org.h, json={"motivo": "Se condonó"}).json()
    assert {g["concepto"]: g["estado"] for g in y["cargos"]}["Iguala (3/3)"] == "cancelado"
    assert org.c.delete(f"{C}/{cid}", headers=org.h).status_code == 409  # tiene pagos


def test_roles_y_aislamiento(org, org2):
    c = nuevo(org)
    consulta = org.usuario("consulta", "consulta@org1.test")
    assert org.c.get(f"{C}/{c['id']}", headers=consulta).status_code == 200
    assert org.c.post(C, headers=consulta, json={"nombre": "No puede"}).status_code == 403
    assert org.c.post(f"{C}/{c['id']}/pagos", headers=consulta, json={"monto": "1", "fecha": HOY.isoformat()}).status_code == 403
    assert org2.c.get(f"{C}/{c['id']}", headers=org2.h).status_code == 404
    assert org2.c.post(f"{C}/{c['id']}/pagos", headers=org2.h, json={"monto": "1", "fecha": HOY.isoformat()}).status_code == 404
    assert org2.c.get(f"{C}/buscar", headers=org2.h).json() == []
    assert org2.c.post("/api/expedientes", headers=org2.h, json={"trabajador_nombre": "X Y", "periodo_inicio": "2025-01-01", "periodo_fin": "2025-01-31",
                                                                  "catalogo_version_id": org2.version_id, "cr_cliente_id": c["id"]}).status_code == 404
    assert org.c.delete(f"{C}/{c['id']}", headers=org.h).json() == {"ok": True}
