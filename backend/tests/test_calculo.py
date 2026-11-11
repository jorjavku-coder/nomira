"""Reglas de cálculo (motor puro, sin base de datos)."""
from datetime import date
from decimal import Decimal

from app.services.calculo import (FilaCalc, ParametrosExpediente, ReciboCalc, calcular, quincena_de,
                                  quincenas_esperadas)
from app.services.lector_recibos import parsear_importe, parsear_periodo

CAT = {"0102": ("SUELDO BASE", True), "0104": ("COMPENSACIÓN", True), "0603": ("DIAS CÍVICOS", True),
       "1609": ("RETROACTIVO DE DESPENSA EXTRAORDINARIA DE FIN DE AÑO", True),
       "1610": ("RETROACTIVO DE GRATIFICACIÓN POR CONVENIO/INCENTIVO POR CONVENIO", True),
       "1616": ("RETROACTIVO DE APOYO DE FIN DE AÑO", True), "0900": ("FONDO DE AHORRO", False),
       "5408": ("CLAVE QUE COINCIDE CON UNA DEDUCCIÓN", True)}
NOMBRE = "EJEMPLO SINTETICO MARIA"
_id = iter(range(1, 10**6))


def P(ini=date(2025, 1, 1), fin=date(2025, 1, 31), n=2, **kw):
    return ParametrosExpediente(NOMBRE, None, ini, fin, n, **kw)


def R(filas, ini=date(2025, 1, 1), fin=date(2025, 1, 15), plaza="P1", nombre=NOMBRE, num="1", doc=1, total=None, **kw):
    fs = []
    for i, f in enumerate(filas, start=1):
        tipo, clave, imp = (f if len(f) == 3 else ("percepcion", *f))
        fs.append(FilaCalc(next(_id), tipo, i, clave, f"CONCEPTO {clave}", None if imp is None else Decimal(imp)))
    rid = next(_id)
    return ReciboCalc(rid, doc, "sint.pdf", rid, num, nombre, "900000001", plaza, ini, fin,
                      None if total is None else Decimal(total), None, filas=fs, **kw)


def test_coincidencia_exacta_y_ceros_iniciales():
    res = calcular(P(), [R([("0102", "100.00"), ("102", "50.00"), ("00102", "50.00"), ("0102 ", "5.00")])], CAT)
    assert [x["clave"] for x in res["incluidos"]] == ["0102"]
    assert res["total_expediente"] == "100.00"
    # «102» tiene formato inválido (no son 4 dígitos) => pendiente, jamás se equipara a 0102
    assert {x["clave"] for x in res["pendientes"]} == {"102", "00102", "0102 "}
    assert all(isinstance(k, str) for k in CAT)


def test_no_autoriza_por_semejanza_de_nombre():
    r = R([("1633", "1937.00"), ("1638", "1360.00"), ("1609", "1497.50")])
    r.filas[0].concepto = "RETROACTIVO DE GRATIFICACIÓN POR CONVENIO/INCENTIVO POR CONVENIO"  # idéntico al de 1610
    res = calcular(P(), [r], CAT)
    assert [x["clave"] for x in res["incluidos"]] == ["1609"]
    assert {x["clave"]: x["motivo"] for x in res["excluidos"]} == {
        "1633": "La clave no está en el catálogo autorizado", "1638": "La clave no está en el catálogo autorizado"}


def test_sumas_decimales_exactas():
    res = calcular(P(), [R([("0102", "0.10"), ("0104", "0.20"), ("0603", "1234567.89")])], CAT)
    assert res["total_expediente"] == "1234568.19"
    assert Decimal(res["quincenas"][0]["total"]) == Decimal("0.10") + Decimal("0.20") + Decimal("1234567.89")


def test_deducciones_nunca_se_suman_aunque_la_clave_coincida():
    res = calcular(P(), [R([("0102", "100.00"), ("deduccion", "5408", "999.00"), ("deduccion", "0102", "999.00")])], CAT)
    assert res["total_expediente"] == "100.00"
    assert len(res["incluidos"]) == 1 and not res["excluidos"]


def test_clave_inactiva_y_desconocida_se_excluyen():
    res = calcular(P(), [R([("0900", "10.00"), ("7777", "20.00"), ("0102", "1.00")])], CAT)
    motivos = {x["clave"]: x["motivo"] for x in res["excluidos"]}
    assert motivos == {"0900": "Clave inactiva en el catálogo", "7777": "La clave no está en el catálogo autorizado"}
    assert res["total_expediente"] == "1.00"


def test_importe_faltante_es_pendiente_no_cero():
    res = calcular(P(), [R([("0102", None), ("0104", "10.00")])], CAT)
    assert res["pendientes"][0]["clave"] == "0102" and res["pendientes"][0]["importe"] is None
    assert res["provisional"] and res["resumen"]["alertas_bloqueantes"] == 1
    assert res["quincenas"][0]["provisional"] and res["quincenas"][0]["total"] == "10.00"


def test_importe_negativo_conserva_signo_y_exige_confirmacion():
    r = R([("0102", "100.00"), ("0104", "-30.00")])
    res = calcular(P(), [r], CAT)
    assert res["pendientes"][0]["importe"] == "-30.00"
    r.filas[1].confirmada = True
    res = calcular(P(), [r], CAT)
    assert res["total_expediente"] == "70.00" and res["incluidos"][1]["negativo"] and not res["pendientes"]


def test_lectura_ocr_dudosa_queda_pendiente_hasta_confirmar():
    r = R([("0102", "100.00")])
    r.filas[0].confianza = 40
    assert calcular(P(), [r], CAT)["pendientes"]
    r.filas[0].confirmada = True
    assert calcular(P(), [r], CAT)["total_expediente"] == "100.00"


def test_retroactivo_conserva_clave_y_quincena_de_pago():
    res = calcular(P(), [R([("1609", "500.00")], date(2025, 1, 16), date(2025, 1, 31))], CAT)
    x = res["incluidos"][0]
    assert (x["clave"], x["quincena"], x["retroactivo"]) == ("1609", "2025-01-Q2", True)
    assert res["quincenas"][0]["estado"] == "faltante" and res["quincenas"][1]["total"] == "500.00"
    assert "quincena en que" in res["politica_retroactivos"]


def test_duplicado_exacto_no_se_suma_ni_se_elimina_solo():
    a, b = R([("0102", "100.00")], num="7"), R([("0102", "100.00")], num="7", doc=2)
    res = calcular(P(), [a, b], CAT)
    assert res["total_expediente"] == "100.00"
    assert [al["tipo"] for al in res["alertas"] if al["bloqueante"]] == ["posible_duplicado"]
    assert res["recibos"][str(b.id)]["estado"] == "pendiente"
    b.decision = "excluir"
    assert not [al for al in calcular(P(), [a, b], CAT)["alertas"] if al["bloqueante"]]
    b.decision = "incluir"  # el revisor decide que sí era un pago distinto
    assert calcular(P(), [a, b], CAT)["total_expediente"] == "200.00"


def test_complementario_mismo_periodo_se_conserva_y_pide_confirmacion():
    a, b = R([("0102", "100.00")], num="7"), R([("0104", "40.00")], num="7")  # mismo número de recibo
    res = calcular(P(), [a, b], CAT)
    assert res["total_expediente"] == "140.00"
    assert [al["tipo"] for al in res["alertas"] if al["bloqueante"]] == ["complementario"]
    b.decision = "incluir"
    assert not calcular(P(), [a, b], CAT)["provisional"]


def test_mismo_numero_de_recibo_en_periodos_distintos_no_es_duplicado():
    a = R([("0102", "100.00")], num="0000001")
    b = R([("0102", "100.00")], date(2025, 1, 16), date(2025, 1, 31), num="0000001")
    res = calcular(P(), [a, b], CAT)
    assert res["total_expediente"] == "200.00" and not res["provisional"]
    assert "num_recibo_repetido" in [al["tipo"] for al in res["alertas"]]


def test_faltante_vs_cero():
    res = calcular(P(fin=date(2025, 2, 15), n=3), [
        R([("7777", "50.00")]), R([("0102", "10.00")], date(2025, 1, 16), date(2025, 1, 31))], CAT)
    estados = [(q["quincena"], q["estado"], q["total"]) for q in res["quincenas"]]
    assert estados == [("2025-01-Q1", "cero", "0.00"), ("2025-01-Q2", "con_prestaciones", "10.00"),
                       ("2025-02-Q1", "faltante", "0.00")]
    assert [f["quincena"] for f in res["faltantes"]] == ["2025-02-Q1"]
    assert res["resumen"]["quincenas_en_cero"] == 1 and res["resumen"]["quincenas_faltantes"] == 1
    assert not res["provisional"]  # una faltante se informa; no se inventa ni bloquea por sí sola


def test_no_inventa_quincenas_para_llegar_a_las_esperadas():
    res = calcular(P(n=72), [R([("0102", "10.00")])], CAT)
    assert len(res["quincenas"]) == 2
    assert "quincenas_esperadas" in [a["tipo"] for a in res["alertas"]]


def test_recibo_de_otro_trabajador_no_se_mezcla():
    res = calcular(P(), [R([("0102", "100.00")]), R([("0102", "900.00")], nombre="OTRA PERSONA FICTICIA")], CAT)
    assert res["total_expediente"] == "100.00"
    assert [a["tipo"] for a in res["alertas"] if a["bloqueante"]] == ["otro_trabajador"]
    assert res["excluidos"][0]["motivo"] == "El recibo corresponde a otro trabajador"


def test_identificador_laboral_manda_sobre_el_nombre():
    p = ParametrosExpediente("NOMBRE CON ERRATA", "900000001", date(2025, 1, 1), date(2025, 1, 31), 2)
    assert calcular(p, [R([("0102", "100.00")])], CAT)["total_expediente"] == "100.00"
    p.identificador_laboral = "123"
    assert calcular(p, [R([("0102", "100.00")])], CAT)["total_expediente"] == "0.00"


def test_plazas_separadas_hasta_que_se_decida():
    rs = [R([("0102", "100.00")], plaza="P1"), R([("0102", "60.00")], plaza="P2")]
    res = calcular(P(), rs, CAT)
    assert "plazas" in [a["tipo"] for a in res["alertas"] if a["bloqueante"]]
    assert res["total_expediente"] is None and {p["plaza"]: p["total"] for p in res["plazas"]} == {"P1": "100.00", "P2": "60.00"}
    assert not any(a["tipo"] in ("posible_duplicado", "complementario") for a in res["alertas"])
    assert calcular(P(decision_plazas="consolidar"), rs, CAT)["total_expediente"] == "160.00"
    sep = calcular(P(decision_plazas="separar"), rs, CAT)
    assert sep["total_expediente"] is None and not sep["provisional"]
    assert [pz["total"] for pz in sep["quincenas"][0]["plazas"]] == ["100.00", "60.00"]


def test_fuera_de_periodo_y_periodo_no_quincenal():
    res = calcular(P(), [R([("0102", "5.00")], date(2024, 12, 1), date(2024, 12, 15)),
                         R([("0102", "7.00")], date(2025, 1, 1), date(2025, 1, 31)),
                         R([("0102", "9.00")], None, None)], CAT)
    assert res["total_expediente"] == "0.00"
    tipos = [a["tipo"] for a in res["alertas"]]
    assert tipos.count("periodo_invalido") == 2 and "fuera_de_periodo" in tipos


def test_descuadre_contra_total_del_recibo():
    res = calcular(P(), [R([("0102", "100.00"), ("7777", "1.00")], total="150.00")], CAT)
    assert "descuadre" in [a["tipo"] for a in res["alertas"] if a["bloqueante"]]
    assert not calcular(P(), [R([("0102", "100.00"), ("7777", "1.00")], total="101.00")], CAT)["provisional"]


def test_quincenas_y_periodos():
    assert len(quincenas_esperadas(date(2023, 1, 1), date(2025, 12, 31))) == 72
    assert quincena_de(date(2024, 2, 16), date(2024, 2, 29)) == (2024, 2, 2)
    assert quincena_de(date(2025, 2, 16), date(2025, 2, 27)) is None
    assert parsear_periodo("16-28 de Febrero de 2026")[1:] == (date(2026, 2, 16), date(2026, 2, 28))
    assert parsear_periodo("31-15 de Enero de 2026") is None and parsear_periodo("sin periodo") is None


def test_parseo_estricto_de_importes():
    assert parsear_importe("$7,215.40") == Decimal("7215.40")
    assert parsear_importe("-$1,000.00") == parsear_importe("($1,000.00)") == parsear_importe("$1,000.00-") == Decimal("-1000.00")
    for dudoso in ("", None, "$7.215,40", "$1,23.00", "7215", "$7,215.4O", "$ ", "1,000"):
        assert parsear_importe(dudoso) is None, dudoso
    assert isinstance(parsear_importe("$0.10"), Decimal)
