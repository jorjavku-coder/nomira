"""Nomira Escrituración: expediente con etapas y requisitos por acto, partes desde Clientes, vigencias y semáforo
«listo para firmar», enlaces de seguimiento (qué se ve y qué no), subida de documentos por el cliente, avisos y aislamiento."""
from datetime import date, datetime, timedelta

import pymupdf
import pytest

from app import models as m
from app.db import SessionLocal

from .test_agenda import buzon  # noqa: F401
from .test_evidencia import activar

E = "/api/escrituracion"
S = "/api/seguimiento"
HOY = date.today()


def pdf(texto="documento"):
    d = pymupdf.open()
    d.new_page().insert_text((50, 72), texto)
    return d.tobytes()


@pytest.fixture
def no(org, plataforma):
    activar(plataforma, org, "escrituracion")
    return org


def compraventa(o, **kw):
    cli = o.c.post("/api/clientes", headers=o.h, json={"nombre": "Ana Compradora Ficticia", "email": "ana@compra.test", "telefono": "5511112222"}).json()
    r = o.c.post(f"{E}/expedientes", headers=o.h, json={
        "acto": "compraventa", "titulo": "Casa en Calle Ficticia 10", "inmueble": "Calle Ficticia 10, Toluca, Edo. Méx.", "valor_operacion": "2500000",
        "notas": "NOTA-INTERNA-SECRETA", "partes": [{"rol": "comprador", "cr_cliente_id": cli["id"]},
                                                    {"rol": "vendedor", "nombre": "Bruno Vendedor Ficticio", "email": "bruno@vende.test", "casado": True}], **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_plantillas_y_semaforo(no):
    e = compraventa(no)
    assert e["folio"] == f"ESC-{HOY.year}-0001" and e["acto_texto"] == "Compraventa de inmueble"
    assert [h["clave"] for h in e["hitos"]][:3] == ["documentos", "avaluo", "certificados"] and e["hitos"][-1]["clave"] == "entregado"
    reqs = e["requisitos"]
    de = {}
    for r in reqs:
        de.setdefault(r["de"], []).append(r["clave"])
    assert de["Inmueble / operación"] == ["antecedente", "predial", "agua", "libertad_gravamen", "avaluo"]
    assert "matrimonio" in de["Bruno Vendedor Ficticio"] and "matrimonio" not in de["Ana Compradora Ficticia"]
    assert e["semaforo"]["color"] == "rojo" and len(e["semaforo"]["faltan"]) == len(reqs)
    # todo validado pero sin cita: amarillo; con cita: verde
    for r in reqs:
        no.c.put(f"{E}/requisitos/{r['id']}", headers=no.h, json={"estado": "validado", "obligatorio": True, "vigencia_dias": r["vigencia_dias"],
                                                                   "expedido_en": HOY.isoformat() if r["vigencia_dias"] else None})
    x = no.c.get(f"{E}/expedientes/{e['id']}", headers=no.h).json()
    assert x["semaforo"]["color"] == "amarillo" and "falta agendar" in x["semaforo"]["texto"]
    lib = next(r for r in x["requisitos"] if r["clave"] == "libertad_gravamen")
    assert lib["vence_en"] == (HOY + timedelta(days=30)).isoformat()
    cita = datetime.combine(HOY + timedelta(days=10), datetime.min.time()).isoformat()
    datos = {k: x[k] for k in ("titulo", "inmueble")} | {"acto": "compraventa", "cita_firma": cita, "cita_lugar": "Oficinas de la notaría"}
    assert no.c.put(f"{E}/expedientes/{e['id']}", headers=no.h, json=datos).json()["semaforo"]["color"] == "verde"
    # la firma es después de que vence el certificado: rojo por vencido
    datos["cita_firma"] = datetime.combine(HOY + timedelta(days=40), datetime.min.time()).isoformat()
    y = no.c.put(f"{E}/expedientes/{e['id']}", headers=no.h, json=datos).json()
    assert y["semaforo"]["color"] == "rojo" and {v["nombre"] for v in y["semaforo"]["vencidos"]} == {"Constancia de no adeudo de agua", "Certificado de libertad de gravamen"}
    # rechazar exige decir qué corregir
    assert no.c.put(f"{E}/requisitos/{lib['id']}", headers=no.h, json={"estado": "rechazado"}).status_code == 422


def test_otros_actos(no):
    t = no.c.post(f"{E}/expedientes", headers=no.h, json={"acto": "testamento", "titulo": "Testamento de Carlos Ficticio",
                                                          "partes": [{"rol": "testador", "nombre": "Carlos Ficticio"}]}).json()
    assert [h["clave"] for h in t["hitos"]] == ["documentos", "proyecto", "firma", "aviso", "entregado"]
    assert all(r["de"] == "Carlos Ficticio" for r in t["requisitos"]) and t["folio"].endswith("0001")
    c = no.c.post(f"{E}/expedientes", headers=no.h, json={"acto": "compraventa_credito", "titulo": "Depto con crédito",
                                                          "partes": [{"rol": "acreditante", "nombre": "Banco Ficticio", "tipo": "moral"}]}).json()
    assert "banco" in [h["clave"] for h in c["hitos"]] and "carta_banco" in [r["clave"] for r in c["requisitos"]]
    assert not any(r["de"] == "Banco Ficticio" for r in c["requisitos"]) and c["folio"].endswith("0002")


def test_partes_desde_clientes_con_sus_documentos(no):
    cli = no.c.post("/api/clientes", headers=no.h, json={"nombre": "Luis Con Documentos", "email": "luis@doc.test"}).json()
    no.c.post(f"/api/clientes/{cli['id']}/documentos", headers=no.h, files={"archivo": ("ine.pdf", pdf(), "application/pdf")}, data={"tipo": "identificacion"})
    e = no.c.post(f"{E}/expedientes", headers=no.h, json={"acto": "poder", "titulo": "Poder general", "partes": [{"rol": "poderdante", "cr_cliente_id": cli["id"]}]}).json()
    p = e["partes"][0]
    assert p["nombre"] == "Luis Con Documentos" and p["email"] == "luis@doc.test"
    ine = next(r for r in e["requisitos"] if r["clave"] == "identificacion")
    assert ine["estado"] == "recibido" and "Clientes" in ine["nota"]
    assert no.c.post(f"{E}/expedientes", headers=no.h, json={"acto": "poder", "titulo": "X Y Z", "partes": [{"rol": "poderdante"}]}).status_code == 422


def test_enlace_de_seguimiento(no, cliente, buzon):
    e = compraventa(no)
    comprador = next(p for p in e["partes"] if p["rol"] == "comprador")
    vendedor = next(p for p in e["partes"] if p["rol"] == "vendedor")
    lc = no.c.post(f"{E}/expedientes/{e['id']}/accesos", headers=no.h, json={"tipo": "parte", "parte_id": comprador["id"]}).json()
    lv = no.c.post(f"{E}/expedientes/{e['id']}/accesos", headers=no.h, json={"tipo": "parte", "parte_id": vendedor["id"], "avisar": False}).json()
    lb = no.c.post(f"{E}/expedientes/{e['id']}/accesos", headers=no.h, json={"tipo": "banco", "nombre": "Banco Ficticio"}).json()
    tc, tv, tb = (x["enlace"].split("#")[1] for x in (lc, lv, lb))
    assert cliente.post(f"{S}/estado").status_code == 404
    assert cliente.post(f"{S}/estado", headers={"X-Enlace": "x" * 40}).status_code == 404
    v = cliente.post(f"{S}/estado", headers={"X-Enlace": tc}).json()
    texto = str(v)
    assert v["para"] == "Ana Compradora Ficticia" and v["acto"] == "Compraventa de inmueble" and v["avance"]["porcentaje"] == 0
    assert "NOTA-INTERNA-SECRETA" not in texto and "2500000" not in texto and "bruno@vende.test" not in texto
    # cada quien ve sus documentos: el comprador no ve los del inmueble; el vendedor sí; el banco solo consulta
    assert {d["de"] for d in v["documentos"]} == {"Ana Compradora Ficticia"}
    vv = cliente.post(f"{S}/estado", headers={"X-Enlace": tv}).json()
    assert {d["de"] for d in vv["documentos"]} == {"Bruno Vendedor Ficticio", "Inmueble / operación"}
    vb = cliente.post(f"{S}/estado", headers={"X-Enlace": tb}).json()
    assert vb["documentos"] == [] and vb["puede_subir"] is False
    # el comprador sube su INE: queda «recibido» del cliente; no puede subir lo del inmueble
    ine = next(d for d in v["documentos"] if "Identificación" in d["nombre"])
    r = cliente.post(f"{S}/documentos", headers={"X-Enlace": tc}, files={"archivo": ("ine.pdf", pdf("INE"), "application/pdf")}, data={"requisito_id": ine["id"]})
    assert r.status_code == 201, r.text
    avaluo = next(x for x in e["requisitos"] if x["clave"] == "avaluo")
    assert cliente.post(f"{S}/documentos", headers={"X-Enlace": tc}, files={"archivo": ("a.pdf", pdf(), "application/pdf")}, data={"requisito_id": avaluo["id"]}).status_code == 404
    assert cliente.post(f"{S}/documentos", headers={"X-Enlace": tc}, files={"archivo": ("a.exe", b"MZ\x90", "application/pdf")}, data={"requisito_id": ine["id"]}).status_code == 415
    x = no.c.get(f"{E}/expedientes/{e['id']}", headers=no.h).json()
    ri = next(r for r in x["requisitos"] if r["id"] == ine["id"])
    assert ri["estado"] == "recibido" and ri["origen"] == "cliente" and x["del_cliente"] == 1
    assert no.c.get(f"{E}/requisitos/{ine['id']}/archivo", headers=no.h).content.startswith(b"%PDF")
    # rechazo visible para el cliente con lo que hay que corregir
    no.c.put(f"{E}/requisitos/{ine['id']}", headers=no.h, json={"estado": "rechazado", "nota": "La INE está vencida"})
    d = next(d for d in cliente.post(f"{S}/estado", headers={"X-Enlace": tc}).json()["documentos"] if d["id"] == ine["id"])
    assert d["estado"] == "rechazado" and d["nota"] == "La INE está vencida"
    # avance: al marcar una etapa visible como hecha se avisa por correo (solo a quien tiene avisos y correo)
    h = next(h for h in x["hitos"] if h["clave"] == "documentos")
    no.c.put(f"{E}/hitos/{h['id']}", headers=no.h, json={"estado": "hecho", "nota_publica": "Ya tenemos todo, gracias.", "visible_cliente": True})
    assert [c["para"] for c in buzon] == [["ana@compra.test"]] and "Documentos recibidos" in buzon[0]["asunto"]
    v2 = cliente.post(f"{S}/estado", headers={"X-Enlace": tc}).json()
    assert v2["etapas"][0]["estado"] == "hecho" and v2["etapas"][0]["nota"] == "Ya tenemos todo, gracias." and v2["avance"]["porcentaje"] == 10
    # etapa oculta no sale; el folio del Registro solo cuando ya se ingresó
    av = next(h for h in x["hitos"] if h["clave"] == "avaluo")
    no.c.put(f"{E}/hitos/{av['id']}", headers=no.h, json={"estado": "en_proceso", "visible_cliente": False})
    assert "Avalúo" not in [s["nombre"] for s in cliente.post(f"{S}/estado", headers={"X-Enlace": tc}).json()["etapas"]]
    datos = {"acto": "compraventa", "titulo": x["titulo"], "folio_registro": "P-123/2026"}
    no.c.put(f"{E}/expedientes/{e['id']}", headers=no.h, json=datos)
    assert cliente.post(f"{S}/estado", headers={"X-Enlace": tc}).json()["folio_registro"] is None
    reg = next(h for h in x["hitos"] if h["clave"] == "registro")
    no.c.put(f"{E}/hitos/{reg['id']}", headers=no.h, json={"estado": "hecho", "visible_cliente": True})
    assert cliente.post(f"{S}/estado", headers={"X-Enlace": tc}).json()["folio_registro"] == "P-123/2026"
    # revocar
    no.c.post(f"{E}/accesos/{lc['id']}/revocar", headers=no.h)
    assert cliente.post(f"{S}/estado", headers={"X-Enlace": tc}).status_code == 410
    acc = no.c.get(f"{E}/expedientes/{e['id']}", headers=no.h).json()["accesos"]
    assert {a["estado"] for a in acc} == {"revocado", "activo"} and next(a for a in acc if a["id"] == lv["id"])["visitas"] == 1


def test_modulo_y_aislamiento(org, org2, plataforma, cliente):
    assert org.c.get(f"{E}/expedientes", headers=org.h).status_code == 403  # módulo no contratado
    activar(plataforma, org, "escrituracion")
    activar(plataforma, org2, "escrituracion")
    e = compraventa(org)
    assert org2.c.get(f"{E}/expedientes/{e['id']}", headers=org2.h).status_code == 404
    assert org2.c.put(f"{E}/requisitos/{e['requisitos'][0]['id']}", headers=org2.h, json={"estado": "validado"}).status_code == 404
    assert org2.c.post(f"{E}/expedientes/{e['id']}/accesos", headers=org2.h, json={"tipo": "banco", "nombre": "X Y"}).status_code == 404
    consulta = org.usuario("consulta", "consulta@org1.test")
    assert org.c.get(f"{E}/expedientes/{e['id']}", headers=consulta).status_code == 200
    assert org.c.post(f"{E}/expedientes/{e['id']}/accesos", headers=consulta, json={"tipo": "banco", "nombre": "X Y"}).status_code == 403
    # si la notaría deja de tener el módulo, los enlaces dejan de funcionar
    t = org.c.post(f"{E}/expedientes/{e['id']}/accesos", headers=org.h, json={"tipo": "banco", "nombre": "Banco"}).json()["enlace"].split("#")[1]
    assert cliente.post(f"{S}/estado", headers={"X-Enlace": t}).status_code == 200
    activar(plataforma, org, "escrituracion", contratado=False)
    assert cliente.post(f"{S}/estado", headers={"X-Enlace": t}).status_code == 410
