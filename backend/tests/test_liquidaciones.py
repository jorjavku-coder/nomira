"""Liquidaciones LFT: motor de cálculo con casos resueltos a mano, tablas por fecha (vacaciones 2023, jornada 2027-2030,
salarios caídos 2012, salario mínimo por zona) y la API (guardar, exposición por asunto, CSV, permisos y aislamiento)."""
from datetime import date
from decimal import Decimal as D

import pytest

from app.services.liquidacion import motor
from app.services.liquidacion.motor import Datos, OtroConcepto, PeriodoExtra, calcular

from .test_evidencia import activar

L = "/api/liquidaciones"
HOY = date(2026, 11, 23)


def conceptos(r):
    return {c["clave"]: c["importe"] for s in r["secciones"] for c in s["conceptos"]}


def test_renuncia_tres_anios():
    r = calcular(Datos(fecha_ingreso=date(2023, 1, 16), fecha_baja=date(2026, 7, 15), causa="renuncia", salario_diario=D("400")), HOY)
    c = conceptos(r)
    assert r["antiguedad"]["anios_completos"] == 3 and r["antiguedad"]["dias_ultimo_anio"] == 181
    assert r["salarios"]["vacaciones_dias_anio"] == 18  # 4.º año con la tabla 2023
    assert c == {"aguinaldo": "3221.92", "vacaciones": "3570.41", "prima_vacacional": "892.60"}
    assert r["total"] == "7684.93"
    assert any("15 años" in a for a in r["avisos"])  # sin prima de antigüedad


def test_despido_injustificado_frontera_con_tope():
    r = calcular(Datos(fecha_ingreso=date(2016, 6, 1), fecha_baja=date(2026, 5, 31), causa="despido_injustificado", salario_diario=D("1000"),
                       zona="frontera", fecha_calculo=date(2026, 11, 30), incluir_20_dias=True), HOY)
    c = conceptos(r)
    assert r["antiguedad"]["anios"] == "10" and r["salarios"]["integrado"] == "1056.16"
    assert r["salarios"]["minimo"] == "440.87" and r["salarios"]["tope_prima"] == "881.74"
    assert c["prima_antiguedad"] == "105808.80"  # 12 × 10 × 881.74 (tope de 2 mínimos de la frontera)
    assert c["tres_meses"] == "95054.40" and c["veinte_dias"] == "211232.00"
    assert c["salarios_caidos"] == "193277.28"  # 183 días
    assert "intereses" not in c
    assert c["vacaciones"] == "22000.00" and c["prima_vacacional"] == "5500.00" and c["aguinaldo"] == "6205.48"
    assert r["total"] == "639077.96"


def test_salarios_caidos_tope_e_intereses_y_regimen_anterior():
    r = calcular(Datos(fecha_ingreso=date(2020, 3, 1), fecha_baja=date(2026, 2, 28), causa="despido_injustificado", salario_diario=D("500"),
                       fecha_calculo=date(2027, 8, 30)), HOY)
    c = conceptos(r)
    sdi = D(r["salarios"]["integrado"])
    assert c["salarios_caidos"] == str((sdi * 365).quantize(D("0.01")))
    assert c["intereses"] == str((sdi * 450 * D("0.02") * D("6.10")).quantize(D("0.01")))
    assert "veinte_dias" not in c and any("reinstalar" in a for a in r["avisos"])
    viejo = calcular(Datos(fecha_ingreso=date(2005, 1, 1), fecha_baja=date(2011, 6, 30), causa="despido_injustificado", salario_diario=D("200"),
                           salario_minimo=D("59.82"), fecha_calculo=date(2013, 6, 30)), HOY)
    cv = conceptos(viejo)
    assert "intereses" not in cv and cv["salarios_caidos"] == str((D(viejo["salarios"]["integrado"]) * 731).quantize(D("0.01")))


def test_tablas_por_fecha():
    assert [motor.dias_vacaciones(n, date(2024, 1, 1)) for n in (1, 2, 5, 6, 10, 11, 16, 21)] == [12, 14, 20, 22, 22, 24, 26, 28]
    assert [motor.dias_vacaciones(n, date(2022, 1, 1)) for n in (1, 4, 5, 9, 10, 15)] == [6, 12, 14, 14, 16, 18]
    assert motor.jornada_legal(2026) == (48, 9) and motor.jornada_legal(2028) == (44, 10) and motor.jornada_legal(2031) == (40, 12)
    r = calcular(Datos(fecha_ingreso=date(2017, 7, 1), fecha_baja=date(2022, 6, 30), causa="renuncia", salario_diario=D("300")), HOY)
    assert r["salarios"]["vacaciones_dias_anio"] == 14 and conceptos(r)["vacaciones"] == "4200.00"  # tabla anterior a 2023
    # salario mínimo de un año que aún no está en la tabla: usa el último y avisa
    r = calcular(Datos(fecha_ingreso=date(2020, 1, 1), fecha_baja=date(2027, 3, 1), causa="despido_justificado", salario_diario=D("300")), HOY)
    assert r["salarios"]["minimo_anio"] == 2026 and any("2027" in a for a in r["avisos"])


def test_horas_extra_reforma_40_horas():
    r = calcular(Datos(fecha_ingreso=date(2020, 1, 1), fecha_baja=date(2028, 2, 15), causa="renuncia", salario_diario=D("480"),
                       horas_extra=[PeriodoExtra(date(2028, 1, 3), date(2028, 1, 30), D("60"))]), HOY)
    c = conceptos(r)
    assert c["horas_extra_1_2028"] == "9120.00"  # 4 semanas × (10 dobles + 6 triples) × $60
    # nocturna en 2026: jornada de 42 h; un periodo que cruza el año se parte con la tabla de cada año
    r = calcular(Datos(fecha_ingreso=date(2020, 1, 1), fecha_baja=date(2027, 1, 31), causa="renuncia", salario_diario=D("700"), tipo_jornada="nocturna",
                       horas_extra=[PeriodoExtra(date(2026, 12, 4), date(2027, 1, 14), D("50"))]), HOY)
    c = conceptos(r)
    assert c["horas_extra_1_2026"] == "6400.00"  # 4 semanas × 8 h (50 − 42) × 2 × $100 (700/7)
    assert c["horas_extra_1_2027"] == "3200.00"  # 2 semanas × 8 h × 2 × $100
    r = calcular(Datos(fecha_ingreso=date(2020, 1, 1), fecha_baja=date(2026, 6, 30), causa="renuncia", salario_diario=D("300"),
                       horas_extra=[PeriodoExtra(date(2025, 1, 1), date(2025, 1, 28), D("50"))], otros=[OtroConcepto("PTU", D("1500"))]), HOY)
    assert any("prescritas" in a for a in r["avisos"]) and conceptos(r)["otro_1"] == "1500.00"


def test_prima_de_antiguedad_y_errores():
    r = calcular(Datos(fecha_ingreso=date(2010, 1, 1), fecha_baja=date(2026, 6, 30), causa="renuncia", salario_diario=D("400")), HOY)
    assert conceptos(r)["prima_antiguedad"] == str((12 * (16 + D(181) / 365) * D(r["salarios"]["integrado"])).quantize(D("0.01")))
    assert D(r["salarios"]["integrado"]) < D("630.08")  # no rebasa el tope: se usa el integrado
    with pytest.raises(motor.ErrorDatos):
        calcular(Datos(fecha_ingreso=date(2026, 6, 1), fecha_baja=date(2026, 1, 1), causa="renuncia", salario_diario=D("400")), HOY)


DATOS = {"fecha_ingreso": "2020-03-01", "fecha_baja": "2026-02-28", "causa": "despido_injustificado", "salario_diario": "500",
         "fecha_calculo": "2026-08-31", "horas_extra": [{"desde": "2026-01-05", "hasta": "2026-02-01", "horas_semana": "54"}]}


def test_api_guardar_exposicion_y_csv(org):
    prev = org.c.post(f"{L}/calcular", headers=org.h, json=DATOS)
    assert prev.status_code == 200, prev.text
    a = org.c.post("/api/clientes", headers=org.h, json={"nombre": "Empresa Ficticia SA de CV"}).json()
    r = org.c.post(f"{L}", headers=org.h, json={"trabajador": "Pedro Actor Ficticio", "patron": "Empresa Ficticia", "cr_cliente_id": a["id"],
                                               "datos": DATOS, "propuesta": "60000", "autorizado": "80000"})
    assert r.status_code == 201, r.text
    x = r.json()
    assert x["total"] == prev.json()["total"] and x["propuesta_pct"] and x["cliente"]["nombre"] == "Empresa Ficticia SA de CV"
    assert x["titulo"].startswith("Despido injustificado")
    # editar: cambia la causa y se vuelve a calcular
    y = org.c.put(f"{L}/{x['id']}", headers=org.h, json={"trabajador": "Pedro Actor Ficticio", "datos": {**DATOS, "causa": "renuncia"}}).json()
    assert D(y["total"]) < D(x["total"]) and y["causa"] == "renuncia"
    lista = org.c.get(f"{L}?q=pedro", headers=org.h).json()["calculos"]
    assert [c["id"] for c in lista] == [x["id"]]
    csv = org.c.get(f"{L}/{x['id']}/csv", headers=org.h)
    assert csv.status_code == 200 and "Prima vacacional" in csv.text and "TOTAL" in csv.text
    assert org.c.post(f"{L}/calcular", headers=org.h, json={**DATOS, "fecha_baja": "2019-01-01"}).status_code == 422


def test_api_exposicion_por_asunto(org, plataforma):
    activar(plataforma, org, "agenda")
    asunto = org.c.post("/api/agenda/asuntos", headers=org.h, json={"titulo": "Actores vs. Empresa Ficticia", "materia": "laboral"}).json()
    for n in ("Ana Actora", "Beto Actor"):
        assert org.c.post(L, headers=org.h, json={"trabajador": n, "ag_asunto_id": asunto["id"], "datos": DATOS, "propuesta": "50000"}).status_code == 201
    e = org.c.get(f"{L}/exposicion?asunto={asunto['id']}", headers=org.h).json()
    assert len(e["calculos"]) == 2 and D(e["total"]) == 2 * D(e["calculos"][0]["total"]) and e["propuesta"] == "100000.00"
    assert org.c.get(f"{L}/tablas", headers=org.h).json()["asuntos"][0]["id"] == asunto["id"]


def test_permisos_modulo_y_aislamiento(org, org2, plataforma):
    x = org.c.post(L, headers=org.h, json={"trabajador": "Pedro Actor Ficticio", "datos": DATOS}).json()
    assert org2.c.get(f"{L}/{x['id']}", headers=org2.h).status_code == 404
    assert org2.c.delete(f"{L}/{x['id']}", headers=org2.h).status_code == 404
    otro = org2.c.post("/api/clientes", headers=org2.h, json={"nombre": "Ajeno"}).json()
    assert org.c.post(L, headers=org.h, json={"trabajador": "X", "cr_cliente_id": otro["id"], "datos": DATOS}).status_code == 422
    consulta = org.usuario("consulta", "consulta@org1.test")
    assert org.c.get(f"{L}/{x['id']}", headers=consulta).status_code == 200
    assert org.c.post(L, headers=consulta, json={"trabajador": "X", "datos": DATOS}).status_code == 403
    activar(plataforma, org, "agenda")
    activar(plataforma, org, "nomina", contratado=False)
    assert org.c.get(L, headers=org.h).status_code == 403
    activar(plataforma, org, "nomina")
    assert org.c.delete(f"{L}/{x['id']}", headers=org.h).json() == {"ok": True}
