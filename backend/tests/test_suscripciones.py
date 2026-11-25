"""Control de periodos de venta: prueba de 2 días, mensual, semestral y anual."""
from datetime import date, timedelta

import pytest

from app import models as m
from app.services import suscripciones as sus


# ---------- fechas ----------

@pytest.mark.parametrize("plan,inicio,fin", [
    ("prueba", date(2026, 11, 17), date(2026, 11, 18)),      # 2 días contando el primero
    ("mensual", date(2026, 11, 17), date(2026, 12, 16)),
    ("mensual", date(2026, 1, 31), date(2026, 2, 27)),        # 31 ene + 1 mes = 28 feb → termina el 27
    ("mensual", date(2028, 1, 31), date(2028, 2, 28)),        # año bisiesto: 29 feb → termina el 28
    ("mensual", date(2026, 12, 1), date(2026, 12, 31)),
    ("semestral", date(2026, 8, 31), date(2027, 2, 27)),
    ("anual", date(2026, 11, 17), date(2027, 11, 16)),
    ("anual", date(2028, 2, 29), date(2029, 2, 27)),
])
def test_calcular_fin(plan, inicio, fin):
    assert sus.calcular_fin(plan, inicio) == fin


def _p(plan, inicio, pagado=False, monto=None):
    return m.PeriodoSuscripcion(id=hash((plan, inicio)) % 10000, plan=plan, inicio=inicio,
                                fin=sus.calcular_fin(plan, inicio), pagado=pagado, monto=monto)


def test_estados():
    hoy = date(2026, 11, 17)
    assert sus.estado([], hoy)["estado"] == "sin_plan"
    e = sus.estado([_p("prueba", date(2026, 11, 16))], hoy)
    assert e["estado"] == "prueba" and e["dias_restantes"] == 1 and e["fin"] == "2026-11-17"
    assert sus.estado([_p("mensual", date(2026, 11, 1), True)], hoy)["estado"] == "activa"
    e = sus.estado([_p("mensual", date(2026, 10, 25), True)], hoy)   # vence el 24 nov: faltan 8 días
    assert e["estado"] == "activa" and e["dias_restantes"] == 8
    e = sus.estado([_p("mensual", date(2026, 10, 24), True)], hoy)   # vence el 23 nov: faltan 7 días
    assert e["estado"] == "por_vencer" and e["dias_restantes"] == 7
    # Con la renovación ya registrada, no hay alarma
    e = sus.estado([_p("mensual", date(2026, 10, 24), True), _p("mensual", date(2026, 11, 24))], hoy)
    assert e["estado"] == "activa" and e["siguiente"]["inicio"] == "2026-11-24"
    e = sus.estado([_p("prueba", date(2026, 11, 1))], hoy)
    assert e["estado"] == "vencida" and e["dias_vencida"] == 15
    assert sus.estado([_p("anual", date(2026, 12, 1))], hoy)["estado"] == "programada"
    e = sus.estado([_p("mensual", date(2026, 11, 1), monto=1500)], hoy)
    assert e["pagos_pendientes"] == 1 and e["monto_pendiente"] == "1500"


def test_sugerencia_de_renovacion():
    hoy = date(2026, 11, 17)
    assert sus.estado([_p("mensual", date(2026, 11, 1))], hoy)["sugerido_inicio"] == "2026-12-01"  # al día siguiente del fin
    assert sus.estado([_p("mensual", date(2026, 1, 1))], hoy)["sugerido_inicio"] == "2026-11-17"   # vencido hace tiempo: hoy


# ---------- API ----------

def _crear(plataforma, **extra):
    r = plataforma.c.post("/api/plataforma/clientes", headers=plataforma.h, json={
        "organizacion": "Despacho Prueba", "admin_nombre": "Ana Cliente", "admin_email": "ana@prueba.test", **extra})
    assert r.status_code == 201, r.text
    return r.json()["cliente"]["id"]


def test_cliente_nuevo_empieza_en_prueba(plataforma):
    cid = _crear(plataforma)
    s = plataforma.c.get(f"/api/plataforma/clientes/{cid}/suscripcion", headers=plataforma.h).json()
    hoy = sus.hoy()
    assert s["estado"] == "prueba" and s["dias_restantes"] == 2
    assert s["fin"] == (hoy + timedelta(days=1)).isoformat()
    assert [p["plan"] for p in s["periodos"]] == ["prueba"]
    assert {p["clave"] for p in s["planes"]} == {"prueba", "mensual", "semestral", "anual"}
    # Sin plan si así se pide
    cid2 = plataforma.c.post("/api/plataforma/clientes", headers=plataforma.h, json={
        "organizacion": "Otro", "admin_nombre": "Beto", "admin_email": "beto@otro.test", "plan": None}).json()["cliente"]["id"]
    assert plataforma.c.get(f"/api/plataforma/clientes/{cid2}/suscripcion", headers=plataforma.h).json()["estado"] == "sin_plan"


def test_vender_renovar_y_cobrar(plataforma, db):
    cid = _crear(plataforma)
    s = plataforma.c.get(f"/api/plataforma/clientes/{cid}/suscripcion", headers=plataforma.h).json()
    inicio = s["sugerido_inicio"]  # el día siguiente a que termina la prueba
    assert inicio == (sus.hoy() + timedelta(days=2)).isoformat()
    r = plataforma.c.post(f"/api/plataforma/clientes/{cid}/periodos", headers=plataforma.h,
                          json={"plan": "semestral", "inicio": inicio, "monto": "5400.00", "nota": "Factura A-12"})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["estado"] == "prueba" and s["siguiente"]["plan"] == "semestral" and s["pagos_pendientes"] == 1
    semestral = next(p for p in s["periodos"] if p["plan"] == "semestral")
    assert semestral["fin"] == sus.calcular_fin("semestral", date.fromisoformat(inicio)).isoformat()
    # Registrar el pago
    s = plataforma.c.patch(f"/api/plataforma/periodos/{semestral['id']}", headers=plataforma.h, json={"pagado": True}).json()
    assert s["pagos_pendientes"] == 0
    pagado = next(p for p in s["periodos"] if p["plan"] == "semestral")
    assert pagado["pagado"] and pagado["pagado_en"] == sus.hoy().isoformat()
    lista = plataforma.c.get("/api/plataforma/suscripciones", headers=plataforma.h).json()
    fila = next(x for x in lista if x["id"] == cid)
    assert fila["total_cobrado"] == "5400.00"
    # Queda en la auditoría del cliente
    assert db.query(m.Auditoria).filter_by(organizacion_id=cid, accion="suscripcion_registrada").count() == 2


def test_reglas(plataforma):
    cid = _crear(plataforma)
    hoy = sus.hoy()
    url = f"/api/plataforma/clientes/{cid}/periodos"
    otra_prueba = plataforma.c.post(url, headers=plataforma.h, json={"plan": "prueba", "inicio": (hoy + timedelta(days=30)).isoformat()})
    assert otra_prueba.status_code == 409 and "ya tuvo" in otra_prueba.json()["detail"]
    encima = plataforma.c.post(url, headers=plataforma.h, json={"plan": "mensual", "inicio": (hoy + timedelta(days=1)).isoformat()})
    assert encima.status_code == 409 and "Se encima" in encima.json()["detail"]
    assert plataforma.c.post(url, headers=plataforma.h, json={"plan": "trimestral", "inicio": hoy.isoformat()}).status_code == 422
    assert plataforma.c.post(url, headers=plataforma.h, json={"plan": "mensual", "inicio": "2020-01-01"}).status_code == 422
    assert plataforma.c.post(url, headers=plataforma.h, json={"plan": "mensual", "inicio": (hoy + timedelta(days=7)).isoformat(),
                                                             "monto": "-5"}).status_code == 422


def test_borrar_periodo_y_resumen(plataforma):
    cid = _crear(plataforma)
    s = plataforma.c.get(f"/api/plataforma/clientes/{cid}/suscripcion", headers=plataforma.h).json()
    res = plataforma.c.get("/api/plataforma/resumen", headers=plataforma.h).json()
    assert res["en_prueba"] == 1
    s = plataforma.c.delete(f"/api/plataforma/periodos/{s['periodos'][0]['id']}", headers=plataforma.h).json()
    assert s["estado"] == "sin_plan"
    assert plataforma.c.get("/api/plataforma/resumen", headers=plataforma.h).json()["sin_plan"] >= 1


def test_eliminar_cliente_con_periodos(plataforma):
    cid = _crear(plataforma)
    r = plataforma.c.post(f"/api/plataforma/clientes/{cid}/eliminar", headers=plataforma.h, json={"confirmar_nombre": "Despacho Prueba"})
    assert r.status_code == 200


def test_clientes_no_ven_ni_tocan_suscripciones(org, plataforma):
    cid = _crear(plataforma)
    for ruta in (f"/api/plataforma/clientes/{cid}/suscripcion", "/api/plataforma/suscripciones"):
        assert org.c.get(ruta, headers=org.h).status_code == 401
