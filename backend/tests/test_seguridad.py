"""Acceso: freno contra fuerza bruta, IP real, tiempo constante y revocación de sesiones."""
import pytest

from app import models as m
from app.config import ajustes
from app.freno import FrenoAcceso, Ventana
from app.routers import auth

BUENA = "Contrasena-Segura-1"


def _login(c, email, contrasena, ip=None):
    h = {"True-Client-IP": ip} if ip else {}
    return c.post("/api/auth/login", json={"email": email, "contrasena": contrasena}, headers=h)


@pytest.fixture
def ip_por_encabezado(monkeypatch):
    monkeypatch.setattr(ajustes(), "ip_cliente_encabezado", "True-Client-IP")


# ---------- freno (unidad, con reloj simulado) ----------

class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_ventana_vence_y_no_crece_sin_limite():
    reloj = Reloj()
    v = Ventana(maximo=3, segundos=60, max_llaves=100, reloj=reloj)
    for _ in range(3):
        v.registrar("a")
    assert v.excedida("a")
    reloj.t += 61
    assert not v.excedida("a") and len(v) == 0  # la llave vencida se elimina al consultarla
    for i in range(1000):  # muchas llaves distintas: la memoria queda acotada
        v.registrar(f"ip{i}")
    assert len(v) <= 100
    assert v.excedida("ip999") is False and "ip999" in v._eventos  # conserva las más recientes


def test_freno_por_cuenta_y_por_ip():
    reloj = Reloj()
    f = FrenoAcceso(por_cuenta=3, por_ip=5, segundos=60, segundos_ip=60, reloj=reloj)
    for _ in range(3):
        f.fallo("1.1.1.1", "ana@x")
    assert f.bloqueado("1.1.1.1", "ana@x")
    assert not f.bloqueado("2.2.2.2", "ana@x")  # otra IP no queda bloqueada por culpa del atacante
    f.fallo("1.1.1.1", "beto@x")
    f.fallo("1.1.1.1", "carla@x")
    assert f.bloqueado("1.1.1.1", "dora@x")  # «rociar» una contraseña por muchas cuentas también se frena
    reloj.t += 61
    assert not f.bloqueado("1.1.1.1", "dora@x")


# ---------- por la API ----------

def test_atacante_no_bloquea_al_usuario_legitimo(cliente, org, ip_por_encabezado):
    email = "admin1@org1.test"
    for _ in range(8):
        assert _login(cliente, email, "incorrecta", ip="203.0.113.9").status_code == 401
    assert _login(cliente, email, BUENA, ip="203.0.113.9").status_code == 429
    assert _login(cliente, email, BUENA, ip="198.51.100.7").status_code == 200


def test_rociado_de_contrasenas_desde_una_ip(cliente, org, ip_por_encabezado):
    for i in range(40):
        _login(cliente, f"nadie{i}@x.test", "Verano2025!", ip="203.0.113.50")
    assert _login(cliente, "admin1@org1.test", BUENA, ip="203.0.113.50").status_code == 429
    assert _login(cliente, "admin1@org1.test", BUENA, ip="198.51.100.8").status_code == 200


def test_ip_real_en_auditoria_y_encabezado_invalido(cliente, org, db, ip_por_encabezado):
    _login(cliente, "admin1@org1.test", BUENA, ip="198.51.100.20")
    _login(cliente, "admin1@org1.test", BUENA, ip="no-es-una-ip")
    ips = [a.ip for a in db.query(m.Auditoria).filter_by(accion="login").order_by(m.Auditoria.id)]
    assert ips[-2] == "198.51.100.20"
    assert ips[-1] == "testclient"  # valor inválido: se usa la IP de la conexión


def test_sin_encabezado_configurado_se_ignora(cliente, org, db):
    _login(cliente, "admin1@org1.test", BUENA, ip="198.51.100.20")
    assert db.query(m.Auditoria).filter_by(accion="login").one().ip == "testclient"


def test_correo_inexistente_hace_el_mismo_trabajo(cliente, org, monkeypatch):
    llamadas = []
    monkeypatch.setattr(auth, "gastar_tiempo_de_verificacion", lambda c: llamadas.append(c))
    assert _login(cliente, "no-existe@x.test", "algo").status_code == 401
    assert llamadas == ["algo"]
    assert _login(cliente, "admin1@org1.test", "incorrecta").status_code == 401
    assert llamadas == ["algo"]  # con un usuario real se verifica contra su propio hash


def test_cambio_de_contrasena_cierra_sesiones(cliente, org):
    h_ana = org.usuario("analista", "ana@org1.test")
    assert cliente.get("/api/expedientes", headers=h_ana).status_code == 200
    uid = next(u["id"] for u in cliente.get("/api/usuarios", headers=org.h).json() if u["email"] == "ana@org1.test")
    r = cliente.patch(f"/api/usuarios/{uid}", headers=org.h, json={"contrasena": "Otra-Contrasena-9"})
    assert r.status_code == 200
    assert cliente.get("/api/expedientes", headers=h_ana).status_code == 401
    nuevo = _login(cliente, "ana@org1.test", "Otra-Contrasena-9").json()["token"]
    assert cliente.get("/api/expedientes", headers={"Authorization": f"Bearer {nuevo}"}).status_code == 200


def test_reactivar_no_revive_sesiones_viejas(cliente, org):
    h_ana = org.usuario("analista", "ana@org1.test")
    uid = next(u["id"] for u in cliente.get("/api/usuarios", headers=org.h).json() if u["email"] == "ana@org1.test")
    cliente.patch(f"/api/usuarios/{uid}", headers=org.h, json={"activo": False})
    cliente.patch(f"/api/usuarios/{uid}", headers=org.h, json={"activo": True})
    assert cliente.get("/api/expedientes", headers=h_ana).status_code == 401
    assert _login(cliente, "ana@org1.test", BUENA).status_code == 200


def test_token_anterior_sin_version_sigue_valido(cliente, org):
    """Los tokens emitidos antes de esta versión no traen «ver»: valen mientras nada cambie."""
    import jwt
    from datetime import datetime, timedelta, timezone
    t = jwt.encode({"sub": str(org.usuario_id), "org": org.org_id,
                    "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                   ajustes().jwt_secreto, algorithm="HS256")
    assert cliente.get("/api/auth/yo", headers={"Authorization": f"Bearer {t}"}).status_code == 200
