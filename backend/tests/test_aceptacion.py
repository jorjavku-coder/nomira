"""Caso de aceptación: recibo del 1 al 15 de diciembre de 2025 con el catálogo adjunto.

- Siempre: réplica SINTÉTICA del recibo (mismas claves e importes, persona ficticia).
- OCR del catálogo real (Prestaciones.pdf no contiene datos personales).
- Opcional: el PDF real de comprobantes, que NO vive en el repositorio. Para ejecutarlo:
    QC_COMPROBANTES_REALES=/ruta/Comprobantes.pdf pytest tests/test_aceptacion.py
"""
import os
import re
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from app.services.calculo import FilaCalc, ParametrosExpediente, ReciboCalc, calcular
from app.services.catalogo_ocr import extraer_catalogo
from app.services.extraccion import extraer_pagina
from app.services.lector_recibos import leer_recibo
from app.services.semilla import leer_referencia
from app.sinteticos import CASO_ACEPTACION, crear_pdf, recibo

PDF_CATALOGO = Path(__file__).resolve().parents[2] / "datos" / "catalogo" / "Prestaciones.pdf"
INCLUIDAS = {"0102": "7215.40", "0303": "504.00", "0322": "707.95", "0512": "483.75", "1609": "1497.50"}
EXCLUIDAS = {"0136": "1591.85", "0302": "459.00", "1633": "1937.00", "1638": "1360.00"}
TOTAL = "10408.60"


def _verificar(res):
    q = next(q for q in res["quincenas"] if q["quincena"] == "2025-12-Q1")
    assert {c["clave"]: c["importe"] for pz in q["plazas"] for c in pz["conceptos"]} == INCLUIDAS
    assert q["total"] == TOTAL
    exc = {x["clave"]: (x["importe"], x["motivo"]) for x in res["excluidos"] if x["quincena"] == "2025-12-Q1"}
    assert exc == {k: (v, "La clave no está en el catálogo autorizado") for k, v in EXCLUIDAS.items()}
    assert not [p for p in res["pendientes"] if p["quincena"] == "2025-12-Q1"]


def _calcular(datos_pdf, nombre=None):
    recibos, fid = [], 0
    with pymupdf.open(stream=datos_pdf, filetype="pdf") as d:
        for n, pag in enumerate(d, start=1):
            r = leer_recibo(extraer_pagina(pag, n))
            if not r:
                continue
            filas = []
            for f in r.filas:
                fid += 1
                filas.append(FilaCalc(fid, f.tipo, f.orden, f.clave, f.concepto, f.importe, f.confianza))
            recibos.append(ReciboCalc(n, 1, "x.pdf", n, r.num_recibo, r.trabajador_nombre, r.clave_servidor, r.plaza,
                                      r.periodo_inicio, r.periodo_fin, r.total_percepciones, r.total_deducciones,
                                      filas=filas))
    catalogo = {c: (d, True) for c, d in leer_referencia()}
    p = ParametrosExpediente(nombre or recibos[0].trabajador_nombre, None, date(2025, 12, 1), date(2025, 12, 15), 1)
    return calcular(p, recibos, catalogo), recibos


def test_catalogo_de_referencia():
    ref = dict(leer_referencia())
    assert len(ref) == 124 and all(re.fullmatch(r"\d{4}", c) for c in ref)
    assert set(INCLUIDAS) <= set(ref) and not set(EXCLUIDAS) & set(ref)
    assert "1610" in ref and "1616" in ref and "1633" not in ref and "1638" not in ref


def test_caso_de_aceptacion_replica_sintetica():
    res, _ = _calcular(crear_pdf([recibo("01-15 de Diciembre de 2025", CASO_ACEPTACION)]))
    _verificar(res)
    assert res["total_expediente"] == TOTAL and sum(map(Decimal, INCLUIDAS.values())) == Decimal(TOTAL)


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract no está instalado")
def test_ocr_del_catalogo_real_es_borrador_revisable():
    """El OCR no sustituye la validación humana: debe marcar lo dudoso y no inventar claves."""
    leidas = extraer_catalogo(str(PDF_CATALOGO))
    ref = dict(leer_referencia())
    validas = {e.clave for e in leidas if re.fullmatch(r"\d{4}", e.clave)}
    assert validas <= set(ref), f"El OCR produjo claves inexistentes: {validas - set(ref)}"
    assert len(validas) >= 120
    # Toda clave de la referencia que el OCR no leyó bien debe aparecer marcada para revisión
    marcadas = [e for e in leidas if e.requiere_revision]
    assert len(leidas) == len(ref)
    assert all(e.requiere_revision for e in leidas if e.clave not in ref)
    assert len(marcadas) >= len(set(ref) - validas)
    # Las claves del caso de aceptación se leen correctamente
    assert set(INCLUIDAS) <= validas and not set(EXCLUIDAS) & validas


@pytest.mark.skipif(not os.environ.get("QC_COMPROBANTES_REALES"), reason="Defina QC_COMPROBANTES_REALES para usar el PDF real")
def test_caso_de_aceptacion_pdf_real():
    datos = Path(os.environ["QC_COMPROBANTES_REALES"]).read_bytes()
    with pymupdf.open(stream=datos, filetype="pdf") as d:
        paginas = d.page_count
    res, recibos = _calcular(datos)
    assert len(recibos) * 2 == paginas  # cada recibo trae su página informativa: páginas != quincenas
    _verificar(res)
    for r in recibos:  # control de integridad: lo leído cuadra con los totales impresos
        assert sum(f.importe for f in r.filas if f.tipo == "percepcion") == r.total_percepciones
        assert sum(f.importe for f in r.filas if f.tipo == "deduccion") == r.total_deducciones
