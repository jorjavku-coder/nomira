import os
import tempfile

URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://qc:qc@localhost:5432/quincena_test")
os.environ["DATABASE_URL"] = URL
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="qc_test_")
os.environ["JWT_SECRETO"] = "secreto-solo-para-pruebas-0123456789abcdef"
os.environ["IA_HABILITADA"] = "false"
os.environ["CORREOS_PLATAFORMA"] = "admin1@org1.test"

from sqlalchemy import create_engine, text as _text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

assert "test" in URL, "Las pruebas deben usar una base de datos de pruebas (su contenido se borra)."
try:  # crea la base de pruebas si no existe (p. ej. dentro de Docker Compose)
    _u = make_url(URL)
    with create_engine(_u.set(database="postgres"), isolation_level="AUTOCOMMIT").connect() as _c:
        if not _c.execute(_text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _u.database}).scalar():
            _c.execute(_text(f'CREATE DATABASE "{_u.database}"'))
except Exception:
    pass

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models as m  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import auth  # noqa: E402
from app.services.semilla import crear_catalogo_referencia  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _esquema():
    assert "test" in URL, "Las pruebas deben usar una base de datos de pruebas."
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _limpiar():
    with engine.begin() as c:
        c.execute(text("TRUNCATE " + ", ".join(t.name for t in Base.metadata.sorted_tables) + " RESTART IDENTITY CASCADE"))
    auth._intentos.clear()
    from app.routers import solicitudes
    solicitudes._envios.clear()
    yield


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


class Org:
    def __init__(self, cliente, n):
        r = cliente.post("/api/auth/registro", json={"organizacion": f"Org {n}", "nombre": f"Admin {n}",
                                                     "email": f"admin{n}@org{n}.test", "contrasena": "Contrasena-Segura-1"})
        assert r.status_code == 201, r.text
        self.c = cliente
        self.h = {"Authorization": f"Bearer {r.json()['token']}"}
        self.org_id = r.json()["usuario"]["organizacion_id"]
        self.usuario_id = r.json()["usuario"]["id"]
        with SessionLocal() as s:
            v = crear_catalogo_referencia(s, self.org_id, self.usuario_id)
            s.commit()
            self.version_id, self.catalogo_id = v.id, v.catalogo_id

    def expediente(self, ini="2025-01-01", fin="2025-03-31", nombre="EJEMPLO SINTETICO MARIA FERNANDA", **kw):
        r = self.c.post("/api/expedientes", headers=self.h, json={
            "trabajador_nombre": nombre, "periodo_inicio": ini, "periodo_fin": fin,
            "catalogo_version_id": self.version_id, **kw})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def subir(self, eid, datos: bytes, nombre="recibos.pdf"):
        r = self.c.post(f"/api/expedientes/{eid}/documentos", headers=self.h,
                        files=[("archivos", (nombre, datos, "application/pdf"))])
        assert r.status_code == 201, r.text
        return r.json()

    def resultado(self, eid):
        r = self.c.get(f"/api/expedientes/{eid}/resultado", headers=self.h)
        assert r.status_code == 200, r.text
        return r.json()

    def usuario(self, rol, email):
        r = self.c.post("/api/usuarios", headers=self.h, json={
            "nombre": rol.title(), "email": email, "contrasena": "Contrasena-Segura-1", "rol": rol})
        assert r.status_code == 201, r.text
        t = self.c.post("/api/auth/login", json={"email": email, "contrasena": "Contrasena-Segura-1"}).json()["token"]
        return {"Authorization": f"Bearer {t}"}


@pytest.fixture
def org(cliente):
    return Org(cliente, 1)


@pytest.fixture
def org2(cliente):
    return Org(cliente, 2)
