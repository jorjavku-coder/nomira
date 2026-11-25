"""Correos: bienvenida con el acceso del cliente y recordatorio 7 días antes del vencimiento."""
import asyncio
from datetime import timedelta

import pytest

from app import models as m
from app.config import ajustes
from app.services import correo, envios, suscripciones as sus


@pytest.fixture
def buzon(monkeypatch):
    """Sustituye el envío real: guarda lo que se habría mandado."""
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto: enviados.append(
        {"para": dest, "asunto": asunto, "html": html, "texto": texto}))
    monkeypatch.setattr(ajustes(), "url_publica", "https://nomirasoft.com")
    return enviados


def _cliente(plataforma, **extra):
    datos = {"organizacion": "Despacho Méndez", "admin_nombre": "Laura Méndez", "admin_email": "laura@mendez.test", **extra}
    r = plataforma.c.post("/api/plataforma/clientes", headers=plataforma.h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- bienvenida ----------

def test_bienvenida_al_dar_de_alta(plataforma, buzon, db):
    r = _cliente(plataforma)
    assert r["correo"] == {"enviado": True, "destinatario": "laura@mendez.test", "error": None}
    (c,) = buzon
    temporal = r["acceso"]["contrasena_temporal"]
    assert c["para"] == ["laura@mendez.test"] and "Bienvenido a Nomira, Laura" in c["asunto"]
    for parte in (c["html"], c["texto"]):
        assert temporal in parte and "laura@mendez.test" in parte and "Despacho Méndez" in parte
        assert "https://nomirasoft.com/login" in parte
    fin = (sus.hoy() + timedelta(days=1))
    assert "prueba gratuita" in c["html"] and f"{fin.day} de" in c["html"]
    assert 'src="https://nomirasoft.com/correo/logo.png"' in c["html"]
    # La bitácora no guarda el cuerpo (ni la contraseña)
    reg = db.query(m.CorreoEnviado).one()
    assert reg.estado == "enviado" and reg.tipo == "bienvenida" and temporal not in (reg.asunto + reg.destinatarios)


def test_convertir_solicitud_envia_bienvenida(plataforma, buzon, cliente, db):
    cliente.post("/api/solicitudes", json={"tipo": "suscripcion", "nombre": "Luis Prospecto", "email": "luis@bufete.test",
                                           "acepta_contacto": True})
    sid = db.query(m.Solicitud).one().id
    r = plataforma.c.post(f"/api/plataforma/solicitudes/{sid}/convertir", headers=plataforma.h, json={
        "organizacion": "Bufete Luis", "admin_nombre": "Luis Prospecto", "admin_email": "luis@bufete.test"}).json()
    assert r["correo"]["enviado"] and buzon[0]["para"] == ["luis@bufete.test"]


def test_sin_correo_si_se_desmarca(plataforma, buzon):
    assert _cliente(plataforma, enviar_correo=False)["correo"] is None
    assert buzon == []


def test_datos_del_cliente_se_escapan(plataforma, buzon):
    _cliente(plataforma, organizacion="<script>alert(1)</script> & Cía")
    assert "<script>" not in buzon[0]["html"] and "&lt;script&gt;" in buzon[0]["html"]


def test_si_el_envio_falla_el_cliente_se_crea_igual(plataforma, monkeypatch, db):
    def falla(*_):
        raise correo.CorreoError("El servidor de correo rechazó el usuario o la contraseña.")
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "enviar", falla)
    r = _cliente(plataforma)
    assert r["cliente"]["id"] and r["acceso"]["contrasena_temporal"]
    assert r["correo"]["enviado"] is False and "rechazó" in r["correo"]["error"]
    assert db.query(m.CorreoEnviado).one().estado == "error"


def test_sin_configurar(plataforma):
    r = _cliente(plataforma)
    assert r["correo"]["enviado"] is False and "no está configurado" in r["correo"]["error"]


# ---------- recordatorios ----------

def _venta(plataforma, cid, plan="mensual", hace=25):
    inicio = sus.hoy() - timedelta(days=hace)
    r = plataforma.c.post(f"/api/plataforma/clientes/{cid}/periodos", headers=plataforma.h, json={"plan": plan, "inicio": inicio.isoformat()})
    assert r.status_code == 201, r.text
    return r.json()


def test_recordatorio_7_dias_antes_una_sola_vez(plataforma, buzon, db):
    cid = _cliente(plataforma, plan=None, enviar_correo=False)["cliente"]["id"]
    _venta(plataforma, cid, "mensual", hace=30)        # vence en ~0-1 días: dentro de la ventana
    plataforma.c.post(f"/api/plataforma/clientes/{cid}/usuarios", headers=plataforma.h,
                      json={"nombre": "Otro Admin", "email": "otro@mendez.test", "rol": "administrador"})
    plataforma.c.post(f"/api/plataforma/clientes/{cid}/usuarios", headers=plataforma.h,
                      json={"nombre": "Analista", "email": "analista@mendez.test", "rol": "analista"})
    pend = plataforma.c.get("/api/plataforma/correos", headers=plataforma.h).json()["pendientes"]
    assert len(pend) == 1 and sorted(pend[0]["destinatarios"]) == ["laura@mendez.test", "otro@mendez.test"]
    res = plataforma.c.post("/api/plataforma/recordatorios/ejecutar", headers=plataforma.h).json()
    assert [r["estado"] for r in res] == ["enviado"]
    (c,) = buzon
    assert sorted(c["para"]) == ["laura@mendez.test", "otro@mendez.test"]  # solo administradores
    assert "Su plan de Nomira vence" in c["asunto"] and "Despacho Méndez" in c["html"]
    # Segunda vez: nada (ni por la revisión automática)
    assert plataforma.c.post("/api/plataforma/recordatorios/ejecutar", headers=plataforma.h).json() == []
    assert envios.ejecutar_recordatorios(db) == [] and len(buzon) == 1
    s = plataforma.c.get(f"/api/plataforma/clientes/{cid}/suscripcion", headers=plataforma.h).json()
    assert s["recordatorios"][0]["estado"] == "enviado"


@pytest.mark.parametrize("dias_para_vencer,toca", [(8, False), (7, True), (3, True), (0, True)])
def test_ventana_de_aviso(plataforma, buzon, db, dias_para_vencer, toca):
    cid = _cliente(plataforma, plan=None, enviar_correo=False)["cliente"]["id"]
    # Periodo mensual que termina dentro de `dias_para_vencer` días
    fin = sus.hoy() + timedelta(days=dias_para_vencer)
    inicio = sus.sumar_meses(fin + timedelta(days=1), -1)
    p = m.PeriodoSuscripcion(organizacion_id=cid, plan="mensual", inicio=inicio, fin=fin)
    db.add(p)
    db.commit()
    assert (len(envios.recordatorios_pendientes(db)) == 1) is toca


def test_no_se_avisa_si_ya_renovo_esta_en_prueba_o_suspendido(plataforma, buzon, db):
    cid = _cliente(plataforma, enviar_correo=False)["cliente"]["id"]            # en prueba (vence pronto): no
    assert envios.recordatorios_pendientes(db) == []
    s = _venta(plataforma, cid, "mensual", hace=-7)                            # al terminar la prueba
    cid2 = _cliente(plataforma, organizacion="Otro", admin_email="b@otro.test", plan=None, enviar_correo=False)["cliente"]["id"]
    _venta(plataforma, cid2, "mensual", hace=27)
    assert len(envios.recordatorios_pendientes(db)) == 1
    renov = plataforma.c.get(f"/api/plataforma/clientes/{cid2}/suscripcion", headers=plataforma.h).json()["sugerido_inicio"]
    plataforma.c.post(f"/api/plataforma/clientes/{cid2}/periodos", headers=plataforma.h, json={"plan": "anual", "inicio": renov})
    assert envios.recordatorios_pendientes(db) == []                           # ya renovó
    cid3 = _cliente(plataforma, organizacion="Tercero", admin_email="c@t.test", plan=None, enviar_correo=False)["cliente"]["id"]
    _venta(plataforma, cid3, "mensual", hace=27)
    plataforma.c.patch(f"/api/plataforma/clientes/{cid3}", headers=plataforma.h, json={"estado": "suspendida"})
    assert envios.recordatorios_pendientes(db) == []                           # cuenta suspendida
    assert s  # (el periodo posterior a la prueba no vence pronto)


def test_si_falla_se_reintenta_y_luego_hace_pausa(plataforma, monkeypatch, db):
    cid = _cliente(plataforma, plan=None, enviar_correo=False)["cliente"]["id"]
    _venta(plataforma, cid, "mensual", hace=27)
    intentos = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    def falla(*_):
        intentos.append(1)
        raise correo.CorreoError("Sin conexión.")
    monkeypatch.setattr(correo, "enviar", falla)
    for _ in range(3):
        assert envios.ejecutar_recordatorios(db)[0]["estado"] == "error"
    r = envios.ejecutar_recordatorios(db)
    assert r[0]["estado"] == "omitido" and "3 veces" in r[0]["detalle"] and len(intentos) == 3


# ---------- proveedores ----------

def test_resend(monkeypatch):
    llamadas = []

    class Resp:
        def __init__(self, codigo, cuerpo):
            self.status_code, self._c, self.text = codigo, cuerpo, str(cuerpo)
        def json(self):
            return self._c
    respuesta = [Resp(200, {"id": "x"})]
    monkeypatch.setattr(correo.httpx, "post", lambda url, **kw: (llamadas.append((url, kw)), respuesta[0])[1])
    for k, v in {"entorno": "produccion", "correo_proveedor": "resend", "resend_api_key": "re_123", "correo_remitente": "Nomira <hola@nomirasoft.com>",
                 "correo_responder_a": "hola@nomirasoft.com"}.items():
        monkeypatch.setattr(ajustes(), k, v)
    correo.enviar(["a@b.test"], "Asunto", "<p>hola</p>", "hola")
    url, kw = llamadas[0]
    assert url == "https://api.resend.com/emails" and kw["headers"]["Authorization"] == "Bearer re_123"
    assert kw["json"] == {"from": "Nomira <hola@nomirasoft.com>", "to": ["a@b.test"], "subject": "Asunto",
                          "html": "<p>hola</p>", "text": "hola", "reply_to": "hola@nomirasoft.com"}
    respuesta[0] = Resp(403, {"message": "The nomirasoft.com domain is not verified."})
    with pytest.raises(correo.CorreoError, match="not verified"):
        correo.enviar(["a@b.test"], "Asunto", "<p>hola</p>", "hola")


def test_smtp(monkeypatch):
    enviados = []

    class FalsoSMTP:
        def __init__(self, host, puerto, **kw):
            self.host = host
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def login(self, u, c):
            assert (u, c) == ("hola@nomirasoft.com", "secreta")
        def send_message(self, msg):
            enviados.append(msg)
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", FalsoSMTP)
    for k, v in {"entorno": "produccion", "correo_proveedor": "smtp", "smtp_host": "mail.nomirasoft.com", "smtp_puerto": 465,
                 "smtp_usuario": "hola@nomirasoft.com", "smtp_contrasena": "secreta",
                 "correo_remitente": "Nomira <hola@nomirasoft.com>"}.items():
        monkeypatch.setattr(ajustes(), k, v)
    correo.enviar(["a@b.test"], "Bienvenido", "<p>hola</p>", "hola")
    msg = enviados[0]
    assert msg["From"] == "Nomira <hola@nomirasoft.com>" and msg["To"] == "a@b.test" and msg["Subject"] == "Bienvenido"
    assert [p.get_content_type() for p in msg.iter_parts()] == ["text/plain", "text/html"]

    def bloqueado(*a, **k):
        raise TimeoutError()
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", bloqueado)
    with pytest.raises(correo.CorreoError, match="plan gratuito de Render"):
        correo.enviar(["a@b.test"], "x", "x", "x")


# ---------- panel ----------

def test_panel_de_correos(plataforma, buzon):
    for tipo in ("bienvenida", "recordatorio"):
        r = plataforma.c.get(f"/api/plataforma/correos/vista-previa/{tipo}", headers=plataforma.h)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html") and "nomira" in r.text
    r = plataforma.c.post("/api/plataforma/correos/prueba", headers=plataforma.h, json={"destinatario": "yo@nomirasoft.com"})
    assert r.json() == {"enviado": True, "error": None} and buzon[0]["asunto"].startswith("[Prueba]")
    datos = plataforma.c.get("/api/plataforma/correos", headers=plataforma.h).json()
    assert datos["config"]["configurado"] is True and datos["historial"][0]["tipo"] == "prueba"


def test_revision_automatica(monkeypatch):
    from app import main
    corridas = []
    monkeypatch.setattr(main.correo, "configurado", lambda: True)
    monkeypatch.setattr(main, "_una_revision", lambda: corridas.append(1))

    async def correr():
        t = asyncio.create_task(main._revisar_recordatorios(espera_inicial=0, cada=0.05))
        await asyncio.sleep(0.12)
        t.cancel()
    asyncio.run(correr())
    assert len(corridas) >= 2
