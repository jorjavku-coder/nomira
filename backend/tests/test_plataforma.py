"""Panel de la plataforma: cuentas de clientes, solicitudes y soporte, SIN acceso a expedientes."""
import json
import os
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app import models as m
from app.config import ajustes
from app.main import app
from app.services.plataforma import asegurar_admin_inicial
from app.sinteticos import BASE, crear_pdf, recibo

PUBLICAS = {("POST", "/api/auth/login"), ("POST", "/api/auth/registro"), ("GET", "/api/publico"),
            ("GET", "/api/salud"), ("POST", "/api/solicitudes"),
            # Carga de documentos del cliente: no usa sesión sino el enlace (X-Enlace); sin él, 404.
            ("POST", "/api/subida/estado"), ("POST", "/api/subida/codigo"), ("POST", "/api/subida/verificar"),
            ("POST", "/api/subida/archivos"),
            # Nomira AFORE: portal del cliente (enlace) y webhook de WhatsApp (firma de Meta)
            ("POST", "/api/portal-afore/estado"), ("POST", "/api/portal-afore/codigo"), ("POST", "/api/portal-afore/verificar"),
            ("POST", "/api/portal-afore/documentos"), ("POST", "/api/portal-afore/preferencias"),
            ("GET", "/api/whatsapp/webhook"), ("POST", "/api/whatsapp/webhook"),
            # Nomira Leads: formulario de contacto (enlace), entrada de otros sistemas (clave) y anuncios de Meta (firma)
            ("POST", "/api/leads-publico/formulario/info"), ("POST", "/api/leads-publico/formulario"), ("POST", "/api/leads-entrada"),
            ("GET", "/api/meta/webhook"), ("POST", "/api/meta/webhook"),
            # Centro Legal: documentos publicados y solicitudes ARCO (sin sesión)
            ("GET", "/api/legal/documentos"), ("GET", "/api/legal/documentos/{clave}"), ("POST", "/api/legal/arco"),
            # Comercial: propuesta del prospecto (enlace X-Enlace; sin él, 404) y webhook de Stripe (firma)
            ("POST", "/api/propuesta"), ("POST", "/api/propuesta/pdf"), ("POST", "/api/propuesta/ajustes"),
            ("POST", "/api/propuesta/aceptar"), ("POST", "/api/propuesta/pagar"), ("POST", "/api/comercial/stripe/webhook")}


def test_propuesta_sin_enlace_no_da_nada(cliente, plataforma, org):
    for ruta in ("/api/propuesta", "/api/propuesta/pdf", "/api/propuesta/ajustes", "/api/propuesta/aceptar", "/api/propuesta/pagar"):
        for h in ({}, plataforma.h, org.h):
            r = cliente.post(ruta, headers=h, json={"mensaje": "hola hola", "nombre": "Ana", "version": 1, "acepto": True, "metodo": "spei"})
            assert r.status_code in (404, 422) and set(r.json()) == {"detail"}, ruta
    assert cliente.post("/api/comercial/stripe/webhook", content=b"{}").status_code == 400  # sin firma


def test_rutas_de_subida_sin_enlace_no_dan_nada(cliente, plataforma):
    for ruta in ("/api/subida/estado", "/api/subida/codigo", "/api/subida/verificar"):
        for h in ({}, plataforma.h):
            r = cliente.post(ruta, headers=h, json={"codigo": "123456"})
            assert r.status_code == 404 and set(r.json()) == {"detail"}, ruta


def _rutas(prefijo_plataforma: bool):
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api"):
            continue
        if r.path.startswith("/api/plataforma") != prefijo_plataforma:
            continue
        for metodo in r.methods - {"HEAD", "OPTIONS"}:
            if (metodo, r.path) not in PUBLICAS and (metodo, r.path) != ("POST", "/api/plataforma/login"):
                yield metodo, re.sub(r"\{[^}]+\}", "1", r.path)


def _con_expediente(org):
    eid = org.expediente(nombre="EJEMPLO SINTETICO MARIA FERNANDA")
    org.subir(eid, crear_pdf([recibo("01-15 de Enero de 2025", BASE, num="1")]))
    return eid


# ---------- aislamiento: la plataforma NO ve expedientes ----------

def test_la_sesion_de_plataforma_no_abre_ninguna_ruta_de_clientes(org, plataforma):
    _con_expediente(org)  # existe el expediente 1, documento 1, recibo 1…: un 404 no taparía nada
    rutas = list(_rutas(False))
    assert len(rutas) > 40  # se revisan TODAS las rutas de la app de clientes
    for metodo, ruta in rutas:
        r = plataforma.c.request(metodo, ruta, headers=plataforma.h, json={})
        assert r.status_code == 401, f"{metodo} {ruta} respondió {r.status_code} con sesión de plataforma"


def test_la_sesion_de_un_cliente_no_abre_el_panel(org, plataforma):
    h_analista = org.usuario("analista", "ana@org1.test")
    for metodo, ruta in _rutas(True):
        for h in (org.h, h_analista):
            r = org.c.request(metodo, ruta, headers=h, json={})
            assert r.status_code == 401, f"{metodo} {ruta} respondió {r.status_code} con sesión de cliente"


def test_el_panel_solo_ve_numeros_no_el_contenido(org, plataforma):
    _con_expediente(org)
    org.c.post("/api/auth/login", json={"email": "admin1@org1.test", "contrasena": "Contrasena-Segura-1"})
    respuestas = [plataforma.c.get(r, headers=plataforma.h) for r in
                  ("/api/plataforma/resumen", "/api/plataforma/clientes", f"/api/plataforma/clientes/{org.org_id}")]
    assert all(r.status_code == 200 for r in respuestas)
    texto = json.dumps([r.json() for r in respuestas], ensure_ascii=False)
    for secreto in ("MARIA FERNANDA", "SUELDO BASE", "7505", "trabajador", "recibos.pdf"):
        assert secreto not in texto, secreto
    c = next(x for x in respuestas[1].json() if x["id"] == org.org_id)
    assert c["expedientes"] == 1 and c["usuarios"] == 1 and c["ultimo_acceso"]


# ---------- clientes ----------

def test_alta_de_cliente_con_contrasena_temporal(plataforma, cliente, db):
    r = plataforma.c.post("/api/plataforma/clientes", headers=plataforma.h, json={
        "organizacion": "Despacho Nuevo", "admin_nombre": "Rosa Cliente", "admin_email": "Rosa@Nuevo.test"})
    assert r.status_code == 201
    acceso = r.json()["acceso"]
    assert acceso["email"] == "rosa@nuevo.test" and acceso["contrasena_temporal"].startswith("Nomira-")
    login = cliente.post("/api/auth/login", json={"email": "rosa@nuevo.test", "contrasena": acceso["contrasena_temporal"]})
    assert login.status_code == 200 and login.json()["usuario"]["rol"] == "administrador"
    # El cliente ve en SU auditoría que la cuenta la creó soporte de Nomira
    h = {"Authorization": "Bearer " + login.json()["token"]}
    acciones = [(a["usuario"], a["accion"]) for a in cliente.get("/api/auditoria", headers=h).json()]
    assert ("Soporte Nomira (dueno@nomira.test)", "cliente_creado") in acciones
    # Correo repetido
    assert plataforma.c.post("/api/plataforma/clientes", headers=plataforma.h, json={
        "organizacion": "Otro", "admin_nombre": "Otra Persona", "admin_email": "rosa@nuevo.test"}).status_code == 409


def test_suspender_y_reactivar(org, plataforma):
    h_ana = org.usuario("analista", "ana@org1.test")
    r = plataforma.c.patch(f"/api/plataforma/clientes/{org.org_id}", headers=plataforma.h,
                           json={"estado": "suspendida", "motivo": "Falta de pago"})
    assert r.json()["estado"] == "suspendida" and r.json()["motivo_suspension"] == "Falta de pago"
    for h in (org.h, h_ana):  # sus sesiones se cierran al momento
        assert org.c.get("/api/expedientes", headers=h).status_code == 401
    login = org.c.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": "Contrasena-Segura-1"})
    assert login.status_code == 403 and "suspendida" in login.json()["detail"]
    mala = org.c.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": "equivocada"})
    assert mala.status_code == 401  # con contraseña mala no se revela la suspensión
    plataforma.c.patch(f"/api/plataforma/clientes/{org.org_id}", headers=plataforma.h, json={"estado": "activa"})
    assert org.c.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": "Contrasena-Segura-1"}).status_code == 200


def test_eliminar_cliente_borra_todo_y_respeta_a_los_demas(org, org2, plataforma, db):
    _con_expediente(org)
    eid2 = _con_expediente(org2)
    org.c.post("/api/soporte", headers=org.h, json={"asunto": "Ayuda", "texto": "Hola"})
    carpeta = Path(ajustes().storage_dir) / str(org.org_id)
    assert carpeta.exists()
    mal = plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/eliminar", headers=plataforma.h,
                            json={"confirmar_nombre": "otro nombre"})
    assert mal.status_code == 422
    nombre = db.get(m.Organizacion, org.org_id).nombre
    r = plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/eliminar", headers=plataforma.h,
                          json={"confirmar_nombre": nombre})
    assert r.json() == {"ok": True, "expedientes_borrados": 1}
    db.expire_all()
    assert db.get(m.Organizacion, org.org_id) is None
    for modelo in (m.Usuario, m.Expediente, m.Documento, m.Recibo, m.Catalogo, m.TicketSoporte):
        assert db.query(modelo).filter(modelo.organizacion_id == org.org_id).count() == 0, modelo
    assert not carpeta.exists()
    assert org.c.get("/api/expedientes", headers=org.h).status_code == 401
    # El otro cliente sigue intacto
    assert org2.c.get(f"/api/expedientes/{eid2}", headers=org2.h).status_code == 200
    a = db.query(m.Auditoria).filter_by(accion="cliente_eliminado").one()
    assert a.detalle["nombre"] == nombre and a.organizacion_id is None


# ---------- soporte a usuarios ----------

def test_restablecer_contrasena_y_desbloquear(org, plataforma):
    h_ana = org.usuario("analista", "ana@org1.test")
    uid = next(u["id"] for u in org.c.get("/api/usuarios", headers=org.h).json() if u["email"] == "ana@org1.test")
    for _ in range(8):
        org.c.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": "olvidada"})
    assert org.c.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": "Contrasena-Segura-1"}).status_code == 429
    r = plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/usuarios/1/desbloquear", headers=plataforma.h)
    assert r.status_code == 200
    r = plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/usuarios/{uid}/desbloquear", headers=plataforma.h)
    assert r.json() == {"ok": True, "estaba_bloqueado": True}
    assert org.c.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": "Contrasena-Segura-1"}).status_code == 200
    temporal = plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/usuarios/{uid}/restablecer",
                                 headers=plataforma.h).json()["acceso"]["contrasena_temporal"]
    assert org.c.get("/api/expedientes", headers=h_ana).status_code == 401  # sesiones cerradas
    assert org.c.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": "Contrasena-Segura-1"}).status_code == 401
    assert org.c.post("/api/auth/login", json={"email": "ana@org1.test", "contrasena": temporal}).status_code == 200


def test_usuario_de_otro_cliente_no_se_toca_por_la_ruta_equivocada(org, org2, plataforma):
    uid2 = org2.usuario_id
    r = plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/usuarios/{uid2}/restablecer", headers=plataforma.h)
    assert r.status_code == 404


def test_agregar_usuario_a_un_cliente_y_desactivarlo(org, plataforma, cliente):
    r = plataforma.c.post(f"/api/plataforma/clientes/{org.org_id}/usuarios", headers=plataforma.h,
                          json={"nombre": "Nuevo Admin", "email": "nuevo@org1.test", "rol": "administrador"})
    acceso = r.json()["acceso"]
    t = cliente.post("/api/auth/login", json={"email": "nuevo@org1.test", "contrasena": acceso["contrasena_temporal"]}).json()["token"]
    det = plataforma.c.get(f"/api/plataforma/clientes/{org.org_id}", headers=plataforma.h).json()
    uid = next(u["id"] for u in det["usuarios_detalle"] if u["email"] == "nuevo@org1.test")
    plataforma.c.patch(f"/api/plataforma/clientes/{org.org_id}/usuarios/{uid}", headers=plataforma.h, json={"activo": False})
    assert cliente.get("/api/expedientes", headers={"Authorization": f"Bearer {t}"}).status_code == 401


# ---------- mensajes de soporte ----------

def test_conversacion_de_soporte(org, org2, plataforma):
    t = org.c.post("/api/soporte", headers=org.h, json={"asunto": "No puedo subir un PDF", "texto": "Me sale error."}).json()
    assert t["conversacion"][0]["autor_nombre"] == "Admin 1"
    lista = plataforma.c.get("/api/plataforma/soporte", headers=plataforma.h).json()
    assert lista[0]["leido_plataforma"] is False and lista[0]["organizacion"]
    assert plataforma.c.get("/api/plataforma/resumen", headers=plataforma.h).json()["tickets_sin_leer"] == 1
    plataforma.c.get(f"/api/plataforma/soporte/{t['id']}", headers=plataforma.h)  # al abrirlo queda leído
    assert plataforma.c.get("/api/plataforma/resumen", headers=plataforma.h).json()["tickets_sin_leer"] == 0
    r = plataforma.c.post(f"/api/plataforma/soporte/{t['id']}/mensajes", headers=plataforma.h, json={"texto": "Ya lo revisamos."})
    assert r.json()["conversacion"][-1]["autor_nombre"] == "Soporte Nomira"
    assert org.c.get("/api/soporte/sin-leer", headers=org.h).json() == {"total": 1}
    det = org.c.get(f"/api/soporte/{t['id']}", headers=org.h).json()
    assert [x["autor_tipo"] for x in det["conversacion"]] == ["cliente", "plataforma"]
    assert org.c.get("/api/soporte/sin-leer", headers=org.h).json() == {"total": 0}
    # Otra organización no ve ni responde la conversación
    assert org2.c.get(f"/api/soporte/{t['id']}", headers=org2.h).status_code == 404
    assert org2.c.post(f"/api/soporte/{t['id']}/mensajes", headers=org2.h, json={"texto": "x"}).status_code == 404
    assert org2.c.get("/api/soporte", headers=org2.h).json() == []
    # Cerrar y reabrir al escribir
    assert org.c.patch(f"/api/soporte/{t['id']}", headers=org.h).json()["estado"] == "cerrado"
    assert org.c.post(f"/api/soporte/{t['id']}/mensajes", headers=org.h, json={"texto": "Otra duda"}).json()["estado"] == "abierto"


def test_nomira_inicia_una_conversacion(org, plataforma):
    r = plataforma.c.post("/api/plataforma/soporte", headers=plataforma.h,
                          json={"organizacion_id": org.org_id, "asunto": "Mantenimiento", "texto": "El sábado habrá mantenimiento."})
    assert r.status_code == 201
    assert org.c.get("/api/soporte/sin-leer", headers=org.h).json() == {"total": 1}


# ---------- solicitudes ----------

def test_convertir_solicitud_en_cliente(plataforma, cliente, db):
    cliente.post("/api/solicitudes", json={"tipo": "suscripcion", "nombre": "Luis Prospecto", "empresa": "Bufete Luis",
                                           "email": "luis@bufete.test", "acepta_contacto": True})
    sid = db.query(m.Solicitud).one().id
    r = plataforma.c.post(f"/api/plataforma/solicitudes/{sid}/convertir", headers=plataforma.h, json={
        "organizacion": "Bufete Luis", "admin_nombre": "Luis Prospecto", "admin_email": "luis@bufete.test"})
    assert r.status_code == 201
    db.expire_all()
    s = db.get(m.Solicitud, sid)
    assert s.estado == "atendida" and "Convertida en cliente" in s.nota


# ---------- cuentas de la plataforma ----------

def test_admin_inicial_desde_variables(db, monkeypatch):
    monkeypatch.setattr(ajustes(), "plataforma_admin_email", "Jefa@Nomira.test")
    monkeypatch.setattr(ajustes(), "plataforma_admin_contrasena", "corta")
    asegurar_admin_inicial(db)
    assert db.query(m.AdminPlataforma).count() == 0  # contraseña muy corta: no se crea
    monkeypatch.setattr(ajustes(), "plataforma_admin_contrasena", "Una-Contrasena-Larga-1")
    asegurar_admin_inicial(db)
    a = db.query(m.AdminPlataforma).one()
    assert a.email == "jefa@nomira.test"
    hash_original = a.hash_contrasena
    monkeypatch.setattr(ajustes(), "plataforma_admin_contrasena", "Otra-Contrasena-Larga-2")
    asegurar_admin_inicial(db)  # ya existe: no se toca su contraseña
    db.expire_all()
    assert db.query(m.AdminPlataforma).one().hash_contrasena == hash_original


def test_administradores_de_la_plataforma(plataforma, cliente):
    r = plataforma.c.post("/api/plataforma/admins", headers=plataforma.h, json={"nombre": "Socio", "email": "socio@nomira.test"})
    acceso = r.json()["acceso"]
    login = cliente.post("/api/plataforma/login", json={"email": "socio@nomira.test", "contrasena": acceso["contrasena_temporal"]})
    h_socio = {"Authorization": "Bearer " + login.json()["token"]}
    yo = plataforma.c.get("/api/plataforma/yo", headers=plataforma.h).json()["admin"]["id"]
    assert plataforma.c.patch(f"/api/plataforma/admins/{yo}", headers=plataforma.h, json={"activo": False}).status_code == 409
    plataforma.c.patch(f"/api/plataforma/admins/{r.json()['admin']['id']}", headers=plataforma.h, json={"activo": False})
    assert cliente.get("/api/plataforma/resumen", headers=h_socio).status_code == 401
    # Un usuario de cliente no puede entrar por el acceso de la plataforma
    assert cliente.post("/api/plataforma/login", json={"email": "admin1@org1.test", "contrasena": "Contrasena-Segura-1"}).status_code == 401


def test_cambiar_mi_contrasena_de_plataforma(plataforma, cliente):
    r = plataforma.c.post("/api/plataforma/yo/contrasena", headers=plataforma.h,
                          json={"actual": plataforma.CONTRASENA, "nueva": "Nueva-Clave-Plataforma-9"})
    assert r.status_code == 200
    assert cliente.get("/api/plataforma/yo", headers=plataforma.h).status_code == 401  # sesión vieja cerrada
    assert cliente.get("/api/plataforma/yo", headers={"Authorization": "Bearer " + r.json()["token"]}).status_code == 200


def test_freno_del_acceso_a_la_plataforma(plataforma, cliente):
    for _ in range(5):
        cliente.post("/api/plataforma/login", json={"email": plataforma.EMAIL, "contrasena": "mala"})
    r = cliente.post("/api/plataforma/login", json={"email": plataforma.EMAIL, "contrasena": plataforma.CONTRASENA})
    assert r.status_code == 429


@pytest.mark.parametrize("token", ["", "basura", "Bearer x.y.z"])
def test_tokens_invalidos(cliente, token):
    assert cliente.get("/api/plataforma/resumen", headers={"Authorization": token}).status_code == 401
