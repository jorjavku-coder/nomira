"""Verificación en dos pasos (despachos y panel), cierre de sesiones en todos los
dispositivos y protección de las cuentas de demostración en producción."""
import time

from app import models as m
from app.config import ajustes
from app.security import hash_contrasena
from app.services import dos_pasos
from app.services.semilla import proteger_demo

EMAIL, CLAVE = "admin1@org1.test", "Contrasena-Segura-1"


def _codigo(secreto, desfase=0):
    return dos_pasos._codigo(secreto, int(time.time() // 30) + desfase)


def _activar(c, h, ruta, contrasena):
    assert c.post(f"{ruta}/preparar", headers=h, json={"contrasena": "equivocada"}).status_code == 422
    r = c.post(f"{ruta}/preparar", headers=h, json={"contrasena": contrasena}).json()
    assert r["uri"].startswith("otpauth://totp/") and "<svg" in r["qr_svg"]
    assert c.post(f"{ruta}/activar", headers=h, json={"codigo": "000000"}).status_code == 422
    a = c.post(f"{ruta}/activar", headers=h, json={"codigo": _codigo(r["secreto"], -1)}).json()
    assert a["activo"] and len(a["codigos_respaldo"]) == 8
    return r["secreto"], a["codigos_respaldo"]


def test_rfc6238():
    import base64
    s = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert dos_pasos._codigo(s, 59 // 30) == "287082" and dos_pasos._codigo(s, 1111111109 // 30) == "081804"


def test_dos_pasos_despacho(org, cliente, db):
    secreto, respaldo = _activar(org.c, org.h, "/api/auth/yo/dos-pasos", CLAVE)
    r = cliente.post("/api/auth/login", json={"email": EMAIL, "contrasena": CLAVE}).json()
    assert r["requiere_codigo"] and "token" not in r
    # el reto no sirve como sesión
    assert cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {r['reto']}"}).status_code == 401
    assert cliente.post("/api/auth/login/codigo", json={"reto": r["reto"], "codigo": "123456"}).status_code == 401
    ok = cliente.post("/api/auth/login/codigo", json={"reto": r["reto"], "codigo": _codigo(secreto)})
    assert ok.status_code == 200 and ok.json()["usuario"]["dos_pasos"]
    # el mismo código no se acepta dos veces
    r2 = cliente.post("/api/auth/login", json={"email": EMAIL, "contrasena": CLAVE}).json()
    assert cliente.post("/api/auth/login/codigo", json={"reto": r2["reto"], "codigo": _codigo(secreto)}).status_code == 401
    # código de respaldo: una sola vez
    x = cliente.post("/api/auth/login/codigo", json={"reto": r2["reto"], "codigo": respaldo[0]}).json()
    assert "token" in x and "Le quedan 7" in x["aviso"]
    r3 = cliente.post("/api/auth/login", json={"email": EMAIL, "contrasena": CLAVE}).json()
    assert cliente.post("/api/auth/login/codigo", json={"reto": r3["reto"], "codigo": respaldo[0]}).status_code == 401
    # demasiados códigos equivocados: freno
    for _ in range(8):
        cliente.post("/api/auth/login/codigo", json={"reto": r3["reto"], "codigo": "000000"})
    assert cliente.post("/api/auth/login/codigo", json={"reto": r3["reto"], "codigo": respaldo[1]}).status_code == 429
    assert db.query(m.Auditoria).filter(m.Auditoria.accion == "login_codigo_fallido").count() >= 8
    # el secreto se guarda cifrado
    u = db.query(m.Usuario).filter_by(email=EMAIL).one()
    assert secreto not in (u.totp_secreto_cifrado or "") and all(c not in str(u.totp_respaldo) for c in respaldo)


def test_admin_quita_dos_pasos_a_quien_perdio_el_celular(org, cliente):
    h2 = org.usuario("analista", "ana@org1.test")
    _activar(org.c, h2, "/api/auth/yo/dos-pasos", CLAVE)
    uid = org.c.get("/api/auth/yo", headers=h2).json()["usuario"]["id"]
    assert org.c.post(f"/api/usuarios/{uid}/dos-pasos/quitar", headers=h2).status_code == 403
    x = org.c.post(f"/api/usuarios/{uid}/dos-pasos/quitar", headers=org.h).json()
    assert x["dos_pasos"] is False
    assert org.c.get("/api/auth/yo", headers=h2).status_code == 401  # se cerraron sus sesiones
    assert "token" in cliente.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": CLAVE}).json()


def test_desactivar_exige_contrasena_y_codigo(org):
    secreto, _ = _activar(org.c, org.h, "/api/auth/yo/dos-pasos", CLAVE)
    R = "/api/auth/yo/dos-pasos/desactivar"
    assert org.c.post(R, headers=org.h, json={"contrasena": CLAVE, "codigo": "000000"}).status_code == 422
    assert org.c.post(R, headers=org.h, json={"contrasena": CLAVE, "codigo": _codigo(secreto, 1)}).json()["activo"] is False


def test_cerrar_sesiones_en_todos_los_dispositivos(org, cliente):
    otra = cliente.post("/api/auth/login", json={"email": EMAIL, "contrasena": CLAVE}).json()["token"]
    nuevo = org.c.post("/api/auth/yo/cerrar-sesiones", headers=org.h).json()["token"]
    assert cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {otra}"}).status_code == 401
    assert cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {nuevo}"}).status_code == 200


def test_dos_pasos_panel(plataforma, cliente):
    secreto, _ = _activar(plataforma.c, plataforma.h, "/api/plataforma/yo/dos-pasos", plataforma.CONTRASENA)
    r = cliente.post("/api/plataforma/login", json={"email": plataforma.EMAIL, "contrasena": plataforma.CONTRASENA}).json()
    assert r["requiere_codigo"]
    assert cliente.post("/api/auth/login/codigo", json={"reto": r["reto"], "codigo": _codigo(secreto)}).status_code == 401  # reto de otro tipo
    ok = cliente.post("/api/plataforma/login/codigo", json={"reto": r["reto"], "codigo": _codigo(secreto)})
    assert ok.status_code == 200 and ok.json()["admin"]["dos_pasos"]
    assert cliente.get("/api/plataforma/yo", headers={"Authorization": f"Bearer {ok.json()['token']}"}).status_code == 200


def test_cuentas_demo_en_produccion(db, monkeypatch):
    org = m.Organizacion(nombre="Demo")
    db.add(org)
    db.flush()
    db.add(m.Usuario(organizacion_id=org.id, email="admin@demo.local", nombre="Admin Demo", rol="administrador",
                     hash_contrasena=hash_contrasena("Demo-Quincena-2025")))
    db.commit()
    assert proteger_demo(db) == "sin_cambios"  # fuera de producción no toca nada
    monkeypatch.setattr(ajustes(), "entorno", "produccion")
    monkeypatch.setattr(ajustes(), "demo_contrasena", "")
    assert proteger_demo(db) == "demo_desactivada"
    u = db.query(m.Usuario).filter_by(email="admin@demo.local").one()
    assert u.activo is False
    monkeypatch.setattr(ajustes(), "demo_contrasena", "Otra-Contrasena-Privada-1")
    assert proteger_demo(db) == "contrasena_demo_aplicada"
    db.refresh(u)
    assert u.activo is True
    assert proteger_demo(db) == "sin_cambios"
