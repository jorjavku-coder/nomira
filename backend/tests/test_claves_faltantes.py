"""Claves faltantes: el catálogo se carga y, opcionalmente, se completa a mano antes de activarlo."""
from decimal import Decimal

from app import models as m
from app.sinteticos import BASE, crear_pdf, recibo

FALTANTE = ("9876", "BONO ESPECIAL", "1000.00")


def _expediente_con_clave_faltante(org):
    eid = org.expediente()
    org.subir(eid, crear_pdf([recibo("01-15 de Enero de 2025", BASE + [FALTANTE], num="1"),
                              recibo("16-31 de Enero de 2025", BASE + [FALTANTE], num="2")]))
    return eid


def _borrador(org):
    return org.c.post(f"/api/catalogos/{org.catalogo_id}/versiones", headers=org.h,
                      json={"copiar_de_version_id": org.version_id}).json()


def _resultado(org, eid):
    return org.c.get(f"/api/expedientes/{eid}/resultado", headers=org.h).json()


def test_flujo_completo_clave_faltante(org, db):
    eid = _expediente_con_clave_faltante(org)
    antes = _resultado(org, eid)
    fuera = [x for x in antes["excluidos"] if x["clave"] == "9876"]
    assert len(fuera) == 2 and fuera[0]["motivo"] == "La clave no está en el catálogo autorizado"

    v = _borrador(org)
    # 1) La app sugiere la clave que apareció en los recibos, con su descripción leída
    sug = org.c.get(f"/api/catalogos/versiones/{v['id']}/sugerencias", headers=org.h).json()
    assert sug[0] == {"clave": "9876", "descripcion": "BONO ESPECIAL", "apariciones": 2, "expedientes": 1}
    assert not any(s["clave"] in ("0102", "0104", "0603") for s in sug)  # las que ya están no se sugieren

    # 2) Se agregan varias de una vez (la que ya existía se omite, no es error)
    r = org.c.post(f"/api/catalogos/versiones/{v['id']}/entradas/lote", headers=org.h, json={"entradas": [
        {"clave": "9876", "descripcion": "BONO ESPECIAL"}, {"clave": "9877", "descripcion": "AYUDA DE DESPENSA EXTRA"},
        {"clave": "0102", "descripcion": "SUELDO BASE"}]})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["agregadas"] == ["9876", "9877"] and d["omitidas"] == ["0102"] and d["agregadas_manual"] == 2
    marcadas = [e for e in d["entradas"] if e["agregada_manual"]]
    assert [e["clave"] for e in marcadas] == ["9876", "9877"]
    assert d["entradas"][-1]["agregada_manual"]  # las agregadas a mano van al final de la lista
    assert org.c.get(f"/api/catalogos/versiones/{v['id']}/sugerencias", headers=org.h).json() == []

    # 3) Al activar, el expediente en revisión pasa a la versión nueva y la clave ya cuenta
    info = org.c.get(f"/api/catalogos/versiones/{v['id']}", headers=org.h).json()
    assert info["expedientes_por_actualizar"] == 1
    act = org.c.post(f"/api/catalogos/versiones/{v['id']}/activar", headers=org.h,
                     json={"confirmo_revision": True, "actualizar_expedientes": True}).json()
    assert act["estado"] == "activo" and act["expedientes_actualizados"] == 1
    despues = _resultado(org, eid)
    assert not [x for x in despues["excluidos"] if x["clave"] == "9876"]
    assert Decimal(despues["total_expediente"]) == Decimal(antes["total_expediente"]) + Decimal("2000.00")
    a = db.query(m.Auditoria).filter_by(accion="catalogo_version_activada").order_by(m.Auditoria.id.desc()).first()
    assert a.detalle["expedientes_actualizados"] == [eid] and a.detalle["agregadas_manual"] == 2


def test_activar_sin_actualizar_no_toca_expedientes(org, db):
    eid = _expediente_con_clave_faltante(org)
    v = _borrador(org)
    org.c.post(f"/api/catalogos/versiones/{v['id']}/entradas/lote", headers=org.h,
               json={"entradas": [{"clave": "9876", "descripcion": "BONO ESPECIAL"}]})
    act = org.c.post(f"/api/catalogos/versiones/{v['id']}/activar", headers=org.h, json={"confirmo_revision": True}).json()
    assert act["expedientes_actualizados"] == 0
    assert db.get(m.Expediente, eid).catalogo_version_id == org.version_id


def test_validados_nunca_cambian_de_catalogo(org, db):
    eid = _expediente_con_clave_faltante(org)
    assert org.c.post(f"/api/expedientes/{eid}/validar", headers=org.h, json={"acepta_faltantes": True}).status_code == 200
    congelado = _resultado(org, eid)["total_expediente"]
    v = _borrador(org)
    org.c.post(f"/api/catalogos/versiones/{v['id']}/entradas/lote", headers=org.h,
               json={"entradas": [{"clave": "9876", "descripcion": "BONO ESPECIAL"}]})
    assert org.c.get(f"/api/catalogos/versiones/{v['id']}", headers=org.h).json()["expedientes_por_actualizar"] == 0
    act = org.c.post(f"/api/catalogos/versiones/{v['id']}/activar", headers=org.h,
                     json={"confirmo_revision": True, "actualizar_expedientes": True}).json()
    assert act["expedientes_actualizados"] == 0
    db.expire_all()
    assert db.get(m.Expediente, eid).catalogo_version_id == org.version_id
    assert _resultado(org, eid)["total_expediente"] == congelado


def test_lote_con_errores_no_guarda_nada(org):
    v = _borrador(org)
    total = v["entradas_total"]
    r = org.c.post(f"/api/catalogos/versiones/{v['id']}/entradas/lote", headers=org.h, json={"entradas": [
        {"clave": "9876", "descripcion": "BONO"}, {"clave": "98A6", "descripcion": "MAL"},
        {"clave": "9876", "descripcion": "REPETIDA"}, {"clave": "9878", "descripcion": "   "}]})
    assert r.status_code == 422
    msg = r.json()["detail"]
    assert "No se guardó nada" in msg and "fila 2" in msg and "fila 3" in msg and "fila 4" in msg
    assert org.c.get(f"/api/catalogos/versiones/{v['id']}", headers=org.h).json()["entradas_total"] == total


def test_lote_solo_en_borrador_y_solo_admin(org, org2):
    activa = org.version_id
    r = org.c.post(f"/api/catalogos/versiones/{activa}/entradas/lote", headers=org.h,
                   json={"entradas": [{"clave": "9876", "descripcion": "X"}]})
    assert r.status_code == 409  # la versión activa es inmutable
    v = _borrador(org)
    h_ana = org.usuario("analista", "ana@org1.test")
    assert org.c.post(f"/api/catalogos/versiones/{v['id']}/entradas/lote", headers=h_ana,
                      json={"entradas": [{"clave": "9876", "descripcion": "X"}]}).status_code == 403
    assert org.c.get(f"/api/catalogos/versiones/{v['id']}/sugerencias", headers=org2.h).status_code == 404


def test_sugerencias_no_mezclan_organizaciones(org, org2):
    _expediente_con_clave_faltante(org)
    v2 = org2.c.post(f"/api/catalogos/{org2.catalogo_id}/versiones", headers=org2.h,
                     json={"copiar_de_version_id": org2.version_id}).json()
    assert org2.c.get(f"/api/catalogos/versiones/{v2['id']}/sugerencias", headers=org2.h).json() == []


def test_la_marca_se_conserva_al_copiar(org):
    v = _borrador(org)
    org.c.post(f"/api/catalogos/versiones/{v['id']}/entradas", headers=org.h, json={"clave": "9876", "descripcion": "BONO"})
    org.c.post(f"/api/catalogos/versiones/{v['id']}/activar", headers=org.h, json={"confirmo_revision": True})
    copia = org.c.post(f"/api/catalogos/{org.catalogo_id}/versiones", headers=org.h,
                       json={"copiar_de_version_id": v["id"]}).json()
    assert copia["agregadas_manual"] == 1
