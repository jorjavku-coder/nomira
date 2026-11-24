"""Cupones de descuento y perfil de ejecutivo comercial: alta con límites por rol, vigencia, suspensión, aplicación en la
cotización (panel) y en la propuesta del cliente antes de aceptar, conteo de usos al pagarse y acceso restringido."""
import json
from datetime import date, timedelta

from app.services import suscripciones as sus

from .test_comercial import buzon, catalogo, enviar, nueva, token_de  # noqa: F401

C = "/api/plataforma/comercial"
CU = f"{C}/cupones"


def nuevo_admin(plataforma, rol, email):
    r = plataforma.c.post("/api/plataforma/admins", headers=plataforma.h, json={"nombre": f"Persona {rol}", "email": email, "rol": rol})
    assert r.status_code == 201, r.text
    acc = r.json()["acceso"]
    t = plataforma.c.post("/api/plataforma/login", json={"email": email, "contrasena": acc["contrasena_temporal"]})
    assert t.status_code == 200, t.text
    return {"Authorization": f"Bearer {t.json()['token']}"}


def cupon(p, h=None, **kw):
    datos = {"codigo": "blackday 2026", "descripcion": "Campaña Black Friday", "tipo": "porcentaje", "valor": "20", **kw}
    return p.c.post(CU, headers=h or p.h, json=datos)


def test_alta_vigencia_y_suspension(plataforma):
    r = cupon(plataforma)
    assert r.status_code == 201, r.text
    x = r.json()
    assert x["codigo"] == "BLACKDAY2026" and x["vigencia"] == "activo"
    assert cupon(plataforma).status_code == 409  # código repetido
    assert cupon(plataforma, codigo="mal código!").status_code == 422
    assert cupon(plataforma, codigo="CIENTO", valor="150").status_code == 422
    hoy = sus.hoy()
    prog = cupon(plataforma, codigo="ENERO", inicia_en=(hoy + timedelta(days=5)).isoformat()).json()
    venc = cupon(plataforma, codigo="VIEJO", vence_en=(hoy - timedelta(days=1)).isoformat()).json()
    assert prog["vigencia"] == "programado" and venc["vigencia"] == "vencido"
    s = plataforma.c.post(f"{CU}/{x['id']}/estado", headers=plataforma.h, json={"estado": "suspendido"}).json()
    assert s["vigencia"] == "suspendido"
    cat = catalogo(plataforma)
    basico = next(p for p in cat["paquetes"] if p["clave"] == "basico")
    e = {"paquete_id": basico["id"], "modulos": ["nomina"], "periodicidad": "mensual", "cupon": "blackday2026"}
    r = plataforma.c.post(f"{C}/calcular", headers=plataforma.h, json={"entrada": e})
    assert r.status_code == 422 and "no está disponible" in r.text
    plataforma.c.post(f"{CU}/{x['id']}/estado", headers=plataforma.h, json={"estado": "activo"})
    calc = plataforma.c.post(f"{C}/calcular", headers=plataforma.h, json={"entrada": e}).json()
    assert calc["cupon"]["importe"] == "358.00" and calc["base_iva"] == "1432.00" and calc["total"] == "1661.12"
    assert plataforma.c.post(f"{C}/calcular", headers=plataforma.h, json={"entrada": {**e, "cupon": "VIEJO"}}).status_code == 422
    # monto fijo, con mínimo
    cupon(plataforma, codigo="MIL", tipo="monto", valor="1000", minimo="5000")
    assert "a partir de" in plataforma.c.post(f"{C}/calcular", headers=plataforma.h, json={"entrada": {**e, "cupon": "MIL"}}).text
    # borrar solo si no se ha usado
    assert plataforma.c.delete(f"{CU}/{venc['id']}", headers=plataforma.h).json() == {"ok": True}


def test_cupon_en_cotizacion_y_en_la_propuesta(plataforma, buzon, cliente, db):  # noqa: F811
    cupon(plataforma, usos_maximos=1)
    # en el panel, al preparar la cotización
    cat = catalogo(plataforma)
    basico = next(p for p in cat["paquetes"] if p["clave"] == "basico")
    entrada = {"paquete_id": basico["id"], "modulos": ["nomina"], "periodicidad": "mensual"}
    c = nueva(plataforma, entrada=entrada)
    assert enviar(plataforma, c["id"]).status_code == 200
    det = plataforma.c.get(f"{C}/cotizaciones/{c['id']}", headers=plataforma.h).json()
    h = {"X-Enlace": token_de(det)}
    v = cliente.post("/api/propuesta", headers=h).json()
    assert v["calculo"]["total"] == "2076.40" and v["version"] == 1
    assert cliente.post("/api/propuesta/cupon", headers=h, json={"codigo": "NOEXISTE"}).status_code == 422
    r = cliente.post("/api/propuesta/cupon", headers=h, json={"codigo": " blackday2026 "})
    assert r.status_code == 200, r.text
    v2 = r.json()
    assert v2["version"] == 2 and v2["calculo"]["cupon"]["codigo"] == "BLACKDAY2026" and v2["calculo"]["total"] == "1661.12"
    assert "descripcion" not in json.dumps(v2["calculo"]["cupon"]) and "Black Friday" not in json.dumps(v2)
    assert cliente.post("/api/propuesta/cupon", headers=h, json={"codigo": "BLACKDAY2026"}).status_code == 409  # ya tiene uno
    assert cliente.post("/api/propuesta", headers=h).json()["version"] == 2
    assert cliente.post("/api/propuesta/pdf", headers=h).content.startswith(b"%PDF")
    a = cliente.post("/api/propuesta/aceptar", headers=h, json={"nombre": "Ana Prospecto", "version": 2, "acepto": True})
    assert a.status_code == 200, a.text
    assert cliente.post("/api/propuesta/cupon", headers=h, json={"codigo": "BLACKDAY2026"}).status_code == 409  # ya aceptada
    p = plataforma.c.post(f"{C}/cotizaciones/{c['id']}/pagos", headers=plataforma.h,
                          json={"metodo": "spei", "monto": "1661.12", "fecha_pago": date.today().isoformat(), "referencia": "SPEI-1"}).json()
    assert p["estado"] == "pagada"
    lista = plataforma.c.get(CU, headers=plataforma.h).json()["cupones"]
    b = next(x for x in lista if x["codigo"] == "BLACKDAY2026")
    assert b["usos"] == 1 and b["vigencia"] == "agotado"
    assert plataforma.c.delete(f"{CU}/{b['id']}", headers=plataforma.h).status_code == 409
    # ya agotado: otra cotización no puede usarlo
    assert plataforma.c.post(f"{C}/calcular", headers=plataforma.h, json={"entrada": {**entrada, "cupon": "BLACKDAY2026"}}).status_code == 422


def test_perfil_ejecutivo_comercial(plataforma, org):
    h = nuevo_admin(plataforma, "ejecutivo_comercial", "ejecutivo@nomira.test")
    yo = plataforma.c.get("/api/plataforma/yo", headers=h).json()["admin"]
    assert yo["rol"] == "ejecutivo_comercial"
    # sí: ventas, solicitudes, cotizaciones y cupones
    for ruta in ("/api/plataforma/ventas/tablero", "/api/plataforma/solicitudes", f"{C}/catalogo", f"{C}/cotizaciones", CU, "/api/plataforma/resumen"):
        assert plataforma.c.get(ruta, headers=h).status_code == 200, ruta
    # no: cuentas de clientes, soporte, correos, administradores, legal, paquetes ni configuración comercial
    for ruta in ("/api/plataforma/clientes", "/api/plataforma/soporte", "/api/plataforma/correos", "/api/plataforma/admins",
                 "/api/plataforma/suscripciones", "/api/plataforma/legal/documentos", f"{C}/almacenamiento", f"{C}/historial-precios", f"{C}/resumen", "/api/plataforma/academia/config"):
        assert plataforma.c.get(ruta, headers=h).status_code == 403, ruta
    # cupones: solo porcentaje y hasta el máximo autorizado (20 % por omisión)
    assert cupon(plataforma, h, codigo="EJEC10", valor="10").status_code == 201
    assert cupon(plataforma, h, codigo="EJEC50", valor="50").status_code == 403
    assert cupon(plataforma, h, codigo="EJECMONTO", tipo="monto", valor="500").status_code == 403
    alto = cupon(plataforma, codigo="SUPER40", valor="40").json()
    plataforma.c.post(f"{CU}/{alto['id']}/estado", headers=plataforma.h, json={"estado": "suspendido"})
    assert plataforma.c.post(f"{CU}/{alto['id']}/estado", headers=h, json={"estado": "activo"}).status_code == 403
    assert plataforma.c.post(f"{CU}/{alto['id']}/estado", headers=h, json={"estado": "suspendido"}).status_code == 200
    # soporte ve los cupones pero no los administra
    hs = nuevo_admin(plataforma, "soporte", "soporte@nomira.test")
    assert plataforma.c.get(CU, headers=hs).status_code == 200
    assert cupon(plataforma, hs, codigo="SOPORTE5", valor="5").status_code == 403
    # un ejecutivo no puede crear administradores ni cambiar roles
    assert plataforma.c.post("/api/plataforma/admins", headers=h, json={"nombre": "X Y", "email": "x@y.test", "rol": "soporte"}).status_code == 403
