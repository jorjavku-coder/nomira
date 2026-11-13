"""Panel de usuarios (baja, fotos, contraseña), mi perfil y eliminación de expedientes."""
import io
import os

from PIL import Image

from app import models as m
from app.sinteticos import BASE, crear_pdf, recibo

BUENA = "Contrasena-Segura-1"


def _imagen(formato="PNG", tam=(800, 600), modo="RGB", exif_rotada=False) -> bytes:
    im = Image.new(modo, tam, (200, 30, 30) if modo == "RGB" else (200, 30, 30, 128))
    b = io.BytesIO()
    if exif_rotada:
        exif = Image.Exif()
        exif[0x0112] = 6  # orientación: girar 90°
        im.save(b, "JPEG", exif=exif)
    else:
        im.save(b, formato)
    return b.getvalue()


def _uid(org, email):
    return next(u["id"] for u in org.c.get("/api/usuarios", headers=org.h).json() if u["email"] == email)


def _login(c, email, contrasena=BUENA):
    return c.post("/api/auth/login", json={"email": email, "contrasena": contrasena})


# ---------- baja de usuarios ----------

def test_eliminar_usuario(org, db):
    h_ana = org.usuario("analista", "ana@org1.test")
    uid = _uid(org, "ana@org1.test")
    assert org.c.delete(f"/api/usuarios/{uid}", headers=org.h).json() == {"ok": True}
    assert "ana@org1.test" not in [u["email"] for u in org.c.get("/api/usuarios", headers=org.h).json()]
    assert org.c.get("/api/expedientes", headers=h_ana).status_code == 401  # su sesión se cierra
    assert _login(org.c, "ana@org1.test").status_code == 401
    # El correo queda libre para volver a darlo de alta
    r = org.c.post("/api/usuarios", headers=org.h, json={"nombre": "Ana", "email": "ana@org1.test",
                                                         "contrasena": BUENA, "rol": "consulta"})
    assert r.status_code == 201
    assert _login(org.c, "ana@org1.test").status_code == 200
    # Ya no se puede modificar ni volver a eliminar al usuario dado de baja
    assert org.c.patch(f"/api/usuarios/{uid}", headers=org.h, json={"activo": True}).status_code == 404
    assert org.c.delete(f"/api/usuarios/{uid}", headers=org.h).status_code == 404
    # La auditoría guarda a quién se eliminó
    a = db.query(m.Auditoria).filter_by(accion="usuario_eliminado").one()
    assert a.detalle["email"] == "ana@org1.test"


def test_no_se_elimina_a_si_mismo_ni_al_ultimo_admin(org):
    assert org.c.delete(f"/api/usuarios/{org.usuario_id}", headers=org.h).status_code == 409
    org.usuario("administrador", "beto@org1.test")
    h_beto = {"Authorization": "Bearer " + _login(org.c, "beto@org1.test").json()["token"]}
    # Beto elimina al admin original: válido porque queda Beto
    assert org.c.delete(f"/api/usuarios/{org.usuario_id}", headers=h_beto).status_code == 200


def test_solo_admin_y_solo_su_organizacion(org, org2):
    h_ana = org.usuario("analista", "ana@org1.test")
    uid = _uid(org, "ana@org1.test")
    assert org.c.delete(f"/api/usuarios/{org.usuario_id}", headers=h_ana).status_code == 403
    assert org.c.delete(f"/api/usuarios/{uid}", headers=org2.h).status_code == 404
    assert org.c.post(f"/api/usuarios/{uid}/foto", headers=org2.h,
                      files={"archivo": ("a.png", _imagen(), "image/png")}).status_code == 404


# ---------- fotos ----------

def test_foto_propia_y_del_admin(org, db):
    h_ana = org.usuario("analista", "ana@org1.test")
    r = org.c.post("/api/auth/yo/foto", headers=h_ana, files={"archivo": ("yo.png", _imagen(), "image/png")})
    assert r.status_code == 200 and r.json()["foto"].startswith("data:image/jpeg;base64,")
    u = db.query(m.Usuario).filter_by(email="ana@org1.test").one()
    im = Image.open(io.BytesIO(u.foto))
    assert im.size == (256, 256) and im.format == "JPEG" and not im.getexif()  # sin metadatos
    assert org.c.get("/api/auth/yo", headers=h_ana).json()["usuario"]["foto"]
    assert org.c.delete("/api/auth/yo/foto", headers=h_ana).json()["foto"] is None
    # El administrador puede ponerle foto a otro usuario
    uid = _uid(org, "ana@org1.test")
    r = org.c.post(f"/api/usuarios/{uid}/foto", headers=org.h, files={"archivo": ("a.webp", _imagen("WEBP"), "image/webp")})
    assert r.status_code == 200 and r.json()["foto"]
    assert org.c.delete(f"/api/usuarios/{uid}/foto", headers=org.h).json()["foto"] is None
    # El analista no puede cambiar la foto de otros
    assert org.c.post(f"/api/usuarios/{org.usuario_id}/foto", headers=h_ana,
                      files={"archivo": ("a.png", _imagen(), "image/png")}).status_code == 403


def test_foto_con_transparencia_y_girada(org, db):
    assert org.c.post("/api/auth/yo/foto", headers=org.h, files={
        "archivo": ("t.png", _imagen("PNG", modo="RGBA"), "image/png")}).status_code == 200
    assert org.c.post("/api/auth/yo/foto", headers=org.h, files={
        "archivo": ("cel.jpg", _imagen(tam=(400, 100), exif_rotada=True), "image/jpeg")}).status_code == 200


def test_foto_invalida(org):
    for nombre, datos in [("x.png", b"no soy imagen"), ("x.pdf", b"%PDF-1.7 ..."),
                          ("grande.png", b"\x89PNG" + b"0" * (5 * 1024 * 1024 + 10))]:
        r = org.c.post("/api/auth/yo/foto", headers=org.h, files={"archivo": (nombre, datos, "image/png")})
        assert r.status_code == 422, nombre
    bmp = io.BytesIO()
    Image.new("RGB", (10, 10)).save(bmp, "BMP")
    assert org.c.post("/api/auth/yo/foto", headers=org.h,
                      files={"archivo": ("x.bmp", bmp.getvalue(), "image/bmp")}).status_code == 422


# ---------- mi perfil ----------

def test_cambiar_mi_nombre_y_contrasena(org):
    h_ana = org.usuario("consulta", "ana@org1.test")  # cualquier rol puede editar su perfil
    assert org.c.patch("/api/auth/yo", headers=h_ana, json={"nombre": "Ana María"}).json()["nombre"] == "Ana María"
    otra_sesion = {"Authorization": "Bearer " + _login(org.c, "ana@org1.test").json()["token"]}
    mal = org.c.post("/api/auth/yo/contrasena", headers=h_ana, json={"actual": "equivocada", "nueva": "Nueva-Contrasena-7"})
    assert mal.status_code == 422 and "actual" in mal.json()["detail"]
    igual = org.c.post("/api/auth/yo/contrasena", headers=h_ana, json={"actual": BUENA, "nueva": BUENA})
    assert igual.status_code == 422
    corta = org.c.post("/api/auth/yo/contrasena", headers=h_ana, json={"actual": BUENA, "nueva": "corta"})
    assert corta.status_code == 422
    r = org.c.post("/api/auth/yo/contrasena", headers=h_ana, json={"actual": BUENA, "nueva": "Nueva-Contrasena-7"})
    assert r.status_code == 200
    nuevo = {"Authorization": "Bearer " + r.json()["token"]}
    assert org.c.get("/api/auth/yo", headers=nuevo).status_code == 200  # esta sesión sigue
    assert org.c.get("/api/auth/yo", headers=otra_sesion).status_code == 401  # las demás se cierran
    assert _login(org.c, "ana@org1.test", "Nueva-Contrasena-7").status_code == 200


# ---------- expedientes ----------

def _con_documento(org):
    eid = org.expediente()
    org.subir(eid, crear_pdf([recibo("01-15 de Enero de 2025", BASE, num="1")]))
    return eid


def test_editar_expediente(org):
    eid = org.expediente()
    r = org.c.patch(f"/api/expedientes/{eid}", headers=org.h, json={
        "trabajador_nombre": "OTRO NOMBRE", "identificador_laboral": "123", "periodo_inicio": "2025-01-01",
        "periodo_fin": "2025-06-30"})
    assert r.status_code == 200
    e = r.json()
    assert (e["trabajador_nombre"], e["identificador_laboral"], e["quincenas_esperadas"]) == ("OTRO NOMBRE", "123", 12)


def test_eliminar_expediente(org, db):
    eid = _con_documento(org)
    ruta = db.query(m.Documento).filter_by(expediente_id=eid).one().ruta
    rid = db.query(m.Recibo).filter_by(expediente_id=eid).first().id
    fid = db.query(m.Fila).filter_by(recibo_id=rid).first().id
    org.c.post(f"/api/filas/{fid}/corregir", headers=org.h, json={"importe": "1.00", "motivo": "prueba"})
    assert os.path.exists(ruta)
    assert org.c.delete(f"/api/expedientes/{eid}", headers=org.h).json() == {"ok": True}
    assert org.c.get(f"/api/expedientes/{eid}", headers=org.h).status_code == 404
    db.expire_all()
    assert db.query(m.Documento).count() == db.query(m.Recibo).count() == db.query(m.Fila).count() == 0
    assert db.query(m.Pagina).count() == db.query(m.Correccion).count() == 0
    assert not os.path.exists(ruta)
    assert db.query(m.Auditoria).filter_by(accion="expediente_eliminado", entidad_id=eid).count() == 1


def test_eliminar_expediente_permisos(org, org2, db):
    eid = _con_documento(org)
    h_consulta = org.usuario("consulta", "carla@org1.test")
    h_analista = org.usuario("analista", "ana@org1.test")
    assert org.c.delete(f"/api/expedientes/{eid}", headers=h_consulta).status_code == 403
    assert org.c.delete(f"/api/expedientes/{eid}", headers=org2.h).status_code == 404
    # Validado: el analista no puede; el administrador sí
    assert org.c.post(f"/api/expedientes/{eid}/validar", headers=org.h, json={"acepta_faltantes": True}).status_code == 200
    assert org.c.delete(f"/api/expedientes/{eid}", headers=h_analista).status_code == 403
    assert org.c.delete(f"/api/expedientes/{eid}", headers=org.h).status_code == 200
    # Sin validar, el analista sí puede
    otro = org.expediente()
    assert org.c.delete(f"/api/expedientes/{otro}", headers=h_analista).status_code == 200


def test_no_se_elimina_mientras_procesa(org, db):
    eid = _con_documento(org)
    d = db.query(m.Documento).filter_by(expediente_id=eid).one()
    d.estado = "procesando"
    db.commit()
    assert org.c.delete(f"/api/expedientes/{eid}", headers=org.h).status_code == 409
