"""Centro Legal: documentos versionados e inmutables al publicarse, aceptación con evidencia mínima,
nueva aceptación solo cuando la versión lo pide, aviso simplificado junto al formulario, marketing
opcional, anexo de tratamiento por despacho y solicitudes ARCO sin darlas por atendidas solas."""
from app import models as m

TEXTO = "Texto aprobado por el responsable de Nomira y su abogado. " * 3


def borrador(p, documento="terminos", version="1.0", **kw):
    r = p.c.post("/api/plataforma/legal/versiones", headers=p.h, json={"documento": documento, "version": version, "contenido": TEXTO, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def publicar(p, vid):
    r = p.c.post(f"/api/plataforma/legal/versiones/{vid}/publicar", headers=p.h,
                 json={"confirmo_aprobacion": True, "aprobado_por": "Responsable de Nomira y Lic. Abogado Ficticio"})
    assert r.status_code == 200, r.text
    return r.json()


def test_sin_textos_aprobados_no_se_inventa_nada(cliente, org):
    r = cliente.get("/api/legal/documentos").json()
    assert all(d["vigente"] is None for d in r["documentos"])
    assert cliente.get("/api/legal/documentos/terminos").json()["version"] is None
    assert org.c.get("/api/legal/pendientes", headers=org.h).json()["pendientes"] == []  # nada que aceptar


def test_publicacion_exige_aprobacion_y_es_inmutable(plataforma, cliente, db):
    v = borrador(plataforma)
    assert cliente.get("/api/legal/documentos/terminos").json()["version"] is None  # borrador: no es público
    r = plataforma.c.post(f"/api/plataforma/legal/versiones/{v['id']}/publicar", headers=plataforma.h, json={"confirmo_aprobacion": False})
    assert r.status_code == 422
    p = publicar(plataforma, v["id"])
    assert p["estado"] == "publicada" and len(p["sha256"]) == 64 and p["aprobado_por"].startswith("Responsable")
    assert plataforma.c.patch(f"/api/plataforma/legal/versiones/{v['id']}", headers=plataforma.h, json={"contenido": TEXTO + "cambio"}).status_code == 409
    assert plataforma.c.delete(f"/api/plataforma/legal/versiones/{v['id']}", headers=plataforma.h).status_code == 409
    pub = cliente.get("/api/legal/documentos/terminos").json()
    assert pub["version"]["contenido"] == TEXTO and pub["version"]["es_vigente"]
    v2 = publicar(plataforma, borrador(plataforma, version="1.1", resumen_cambios="Ajuste de redacción")["id"])
    h = cliente.get("/api/legal/documentos/terminos").json()
    assert h["version"]["version"] == "1.1" and [x["version"] for x in h["historial"]] == ["1.1", "1.0"]
    vieja = cliente.get(f"/api/legal/documentos/terminos?version_id={v['id']}").json()["version"]
    assert vieja["contenido"] == TEXTO and vieja["es_vigente"] is False
    assert db.query(m.Auditoria).filter_by(accion="legal_version_publicada").count() == 2
    assert v2["id"] != v["id"]


def test_aceptacion_evidencia_y_nueva_aceptacion_solo_si_se_pide(plataforma, org, db):
    t1 = publicar(plataforma, borrador(plataforma)["id"])
    p1 = publicar(plataforma, borrador(plataforma, "privacidad")["id"])
    pend = org.c.get("/api/legal/pendientes", headers=org.h).json()["pendientes"]
    assert {(x["documento"], x["evento"]) for x in pend} == {("terminos", "aceptacion"), ("privacidad", "lectura")}
    r = org.c.post("/api/legal/aceptar", headers=org.h, json={"version_ids": [t1["id"], p1["id"]]}).json()
    assert r["pendientes"] == []
    ev = db.query(m.LgEvento).filter_by(documento="terminos").one()
    assert (ev.version_id, ev.evento, ev.contexto, ev.usuario_id is not None) == (t1["id"], "aceptacion", "inicio_sesion", True)
    assert not hasattr(ev, "ip")  # evidencia mínima: sin IP ni contenido
    # Cambio menor: no se vuelve a pedir
    publicar(plataforma, borrador(plataforma, version="1.1")["id"])
    assert org.c.get("/api/legal/pendientes", headers=org.h).json()["pendientes"] == []
    # La versión aceptada sigue siendo la 1.0 (no se modifica retroactivamente)
    regs = org.c.get("/api/legal/mis-registros", headers=org.h).json()
    assert {r["version"] for r in regs if r["documento"] == "terminos"} == {"1.0"}
    # Cambio que requiere nueva aceptación
    t3 = publicar(plataforma, borrador(plataforma, version="2.0", requiere_aceptacion=True)["id"])
    pend = org.c.get("/api/legal/pendientes", headers=org.h).json()["pendientes"]
    assert [x["id"] for x in pend] == [t3["id"]]
    # Aceptar una versión que ya no es la vigente se rechaza
    assert org.c.post("/api/legal/aceptar", headers=org.h, json={"version_ids": [t1["id"]]}).status_code == 409
    org.c.post("/api/legal/aceptar", headers=org.h, json={"version_ids": [t3["id"]]})
    assert org.c.get("/api/legal/pendientes", headers=org.h).json()["pendientes"] == []
    csv = plataforma.c.get("/api/plataforma/legal/evidencia?formato=csv", headers=plataforma.h).text
    assert "admin1@org1.test" in csv and t3["sha256"] in csv


def test_marketing_opcional_solo_si_esta_habilitado(plataforma, org, db):
    assert org.c.post("/api/legal/aceptar", headers=org.h, json={"version_ids": [], "marketing": True}).status_code == 409
    plataforma.c.put("/api/plataforma/legal/config", headers=plataforma.h, json={"correo_privacidad": "privacidad@nomira.test", "marketing_habilitado": True})
    r = org.c.post("/api/legal/aceptar", headers=org.h, json={"version_ids": [], "marketing": True, "contexto": "perfil"}).json()
    assert r["marketing"]["actual"] is True
    r = org.c.post("/api/legal/aceptar", headers=org.h, json={"version_ids": [], "marketing": False, "contexto": "perfil"}).json()
    assert r["marketing"]["actual"] is False
    assert [e.evento for e in db.query(m.LgEvento).order_by(m.LgEvento.id)] == ["marketing_otorgado", "marketing_revocado"]


def test_aviso_simplificado_en_formulario_de_informes(plataforma, cliente, db):
    av = publicar(plataforma, borrador(plataforma, "privacidad_simplificado")["id"])
    datos = {"tipo": "informes", "nombre": "Prospecto Ficticio", "email": "p@x.test", "acepta_contacto": True, "aviso_version_id": av["id"], "marketing": True}
    assert cliente.post("/api/solicitudes", json=datos).status_code == 201
    evs = db.query(m.LgEvento).all()
    assert [(e.documento, e.evento) for e in evs] == [("privacidad_simplificado", "aviso_mostrado")]  # marketing no habilitado: no se registra


def test_anexo_de_tratamiento_por_despacho(plataforma, org, db):
    assert org.c.get("/api/legal/organizacion", headers=org.h).json()["anexo"] is None
    an = publicar(plataforma, borrador(plataforma, "anexo_tratamiento")["id"])
    r = org.c.get("/api/legal/organizacion", headers=org.h).json()
    assert r["pendiente"]["id"] == an["id"] and r["puede_aceptar"]
    analista = org.usuario("analista", "ana@org1.test")
    assert org.c.post("/api/legal/organizacion/anexo", headers=analista, json={"version_id": an["id"]}).status_code == 403
    r = org.c.post("/api/legal/organizacion/anexo", headers=org.h, json={"version_id": an["id"]}).json()
    assert r["pendiente"] is None and r["aceptaciones"][0]["usuario"] == "Admin 1"
    assert org.c.get("/api/legal/organizacion", headers=analista).json()["pendiente"] is None  # la aceptación es del despacho


def test_solicitudes_arco(cliente, plataforma):
    base = {"tipo": "acceso", "relacion": "cliente_despacho", "despacho": "Despacho X", "nombre": "Titular Ficticio",
            "email": "titular@x.test", "descripcion": "Quiero saber qué datos míos tienen."}
    assert cliente.post("/api/legal/arco", json=base).status_code == 422  # falta confirmar
    r = cliente.post("/api/legal/arco", json={**base, "confirmo": True})
    assert r.status_code == 201 and r.json()["folio"].startswith("ARCO-") and set(r.json()) == {"folio", "ok"}
    lista = plataforma.c.get("/api/plataforma/legal/arco", headers=plataforma.h).json()["solicitudes"]
    s = lista[0]
    assert s["estado"] == "recibida" and s["vence_en"] and s["atendida_en"] is None
    assert plataforma.c.get("/api/plataforma/resumen", headers=plataforma.h).json()["arco_pendientes"] == 1
    # No se puede cerrar sin describir qué se hizo
    assert plataforma.c.post(f"/api/plataforma/legal/arco/{s['id']}", headers=plataforma.h, json={"estado": "atendida"}).status_code == 422
    plataforma.c.post(f"/api/plataforma/legal/arco/{s['id']}", headers=plataforma.h,
                      json={"estado": "remitida_al_despacho", "nota": "Es cliente del despacho X (responsable); se le remitió y se informó al titular."})
    s = plataforma.c.get("/api/plataforma/legal/arco", headers=plataforma.h).json()["solicitudes"][0]
    assert s["estado"] == "remitida_al_despacho" and s["atendida_en"] is None and len(s["notas"]) == 2
