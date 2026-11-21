"""Eliminar catálogos y versiones: solo si ningún expediente los usa, solo administradores, solo de la propia organización."""
from app import models as m


def test_eliminar_catalogo_y_version(org, org2, db):
    cats = org.c.get("/api/catalogos", headers=org.h).json()
    usado = cats[0]
    org.expediente(nombre="EJEMPLO SINTETICO")  # usa el catálogo de referencia
    usado = next(c for c in org.c.get("/api/catalogos", headers=org.h).json() if c["id"] == usado["id"])
    assert usado["expedientes"] == 1
    r = org.c.delete(f"/api/catalogos/{usado['id']}", headers=org.h)
    assert r.status_code == 409 and "1 expediente" in r.json()["detail"]
    v_usada = next(v for v in usado["versiones"] if v["expedientes"])
    assert org.c.delete(f"/api/catalogos/versiones/{v_usada['id']}", headers=org.h).status_code == 409

    nuevo = org.c.post("/api/catalogos", headers=org.h, json={"nombre": "Prueba 2026"}).json()
    v = org.c.post(f"/api/catalogos/{nuevo['id']}/versiones", headers=org.h, json={}).json()
    analista = org.usuario("analista", "ana@org1.test")
    assert org.c.delete(f"/api/catalogos/{nuevo['id']}", headers=analista).status_code == 403
    assert org2.c.delete(f"/api/catalogos/{nuevo['id']}", headers=org2.h).status_code == 404
    assert org.c.delete(f"/api/catalogos/versiones/{v['id']}", headers=org.h).json()["catalogo_id"] == nuevo["id"]
    assert org.c.delete(f"/api/catalogos/{nuevo['id']}", headers=org.h).status_code == 200
    assert all(c["id"] != nuevo["id"] for c in org.c.get("/api/catalogos", headers=org.h).json())
    assert db.query(m.Auditoria).filter(m.Auditoria.accion == "catalogo_eliminado").count() == 1
