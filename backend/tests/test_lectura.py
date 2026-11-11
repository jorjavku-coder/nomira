"""Lectura de comprobantes sintéticos: texto nativo y OCR."""
import shutil
from decimal import Decimal

import pymupdf
import pytest

from app.services.extraccion import extraer_pagina
from app.services.lector_recibos import clasificar_pagina, leer_recibo
from app.sinteticos import BASE, CASO_ACEPTACION, crear_pdf, recibo

requiere_ocr = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract no está instalado")


def _paginas(datos):
    with pymupdf.open(stream=datos, filetype="pdf") as d:
        return [extraer_pagina(p, i) for i, p in enumerate(d, start=1)]


def test_recibo_nativo_columnas_y_cabecera():
    pags = _paginas(crear_pdf([recibo("01-15 de Diciembre de 2025", CASO_ACEPTACION, num="0012345")]))
    assert [clasificar_pagina(p) for p in pags] == ["recibo", "informativa"]
    assert pags[0].metodo == "texto" and leer_recibo(pags[1]) is None
    r = leer_recibo(pags[0])
    assert (r.num_recibo, r.clave_servidor, r.plaza) == ("0012345", "900000001", "990000000000001")
    assert r.trabajador_nombre == "EJEMPLO SINTETICO MARIA FERNANDA"
    assert (r.periodo_inicio.isoformat(), r.periodo_fin.isoformat()) == ("2025-12-01", "2025-12-15")
    perc = [(f.clave, f.importe) for f in r.filas if f.tipo == "percepcion"]
    assert perc == [(c, Decimal(i)) for c, _, i in CASO_ACEPTACION]
    assert [f.clave for f in r.filas if f.tipo == "deduccion"] == ["5408", "5540"]
    assert r.total_percepciones == Decimal("15756.45") == sum(i for _, i in perc)
    assert r.filas[0].clave == "0102" and isinstance(r.filas[0].clave, str)  # cero inicial intacto
    assert all(len(f.bbox) == 4 for f in r.filas)
    # Encabezados y totales no son filas
    assert not any(f.clave in ("CLAVE", None) for f in r.filas)


def test_fila_sin_importe_o_sin_concepto_no_se_convierte_en_cero():
    filas = BASE + [("0512", "DESPENSA", None), ("1730", None, "710.00"), ("0607", "BONO", "$1,2X0.00")]
    r = leer_recibo(_paginas(crear_pdf([recibo("16-28 de Febrero de 2025", filas)]))[0])
    por_clave = {f.clave: f for f in r.filas if f.tipo == "percepcion"}
    assert por_clave["0512"].importe is None and por_clave["0512"].importe_texto is None
    assert por_clave["1730"].importe == Decimal("710.00") and por_clave["1730"].concepto is None
    assert por_clave["0607"].importe is None and por_clave["0607"].importe_texto == "$1,2X0.00"


@requiere_ocr
def test_recibo_escaneado_usa_ocr_y_lee_lo_mismo():
    datos = crear_pdf([recibo("01-15 de Diciembre de 2025", CASO_ACEPTACION, num="0012345")],
                      informativas=True, escaneado=True)
    pags = _paginas(datos)
    assert [p.metodo for p in pags] == ["ocr", "ocr"]
    assert [clasificar_pagina(p) for p in pags] == ["recibo", "informativa"]
    r = leer_recibo(pags[0])
    assert [(f.clave, f.importe) for f in r.filas if f.tipo == "percepcion"] == [
        (c, Decimal(i)) for c, _, i in CASO_ACEPTACION]
    assert r.periodo_inicio.isoformat() == "2025-12-01" and r.plaza == "990000000000001"
    assert r.total_percepciones == Decimal("15756.45")
    assert all(f.confianza is not None for f in r.filas)
