"""Extrae un borrador de catálogo (clave · descripción) de un PDF, con OCR si es imagen.

El resultado SIEMPRE es un borrador para validación humana: las entradas dudosas se marcan
`requiere_revision` y nada se corrige por semejanza ni se inventa.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from ..config import ajustes
from .extraccion import Palabra, abrir_pdf, agrupar_lineas, extraer_pagina, normalizar

_BASURA = "|[]{}_—–=~«»"


@dataclass
class EntradaLeida:
    clave: str
    descripcion: str
    confianza: int | None
    requiere_revision: bool
    nota: str | None
    pagina: int


def _limpia(p: Palabra) -> str:
    return p.texto.strip(_BASURA + " ")


def extraer_catalogo(ruta: str) -> list[EntradaLeida]:
    re_clave = re.compile(ajustes().clave_regex)
    minimo = ajustes().ocr_confianza_minima
    entradas: list[EntradaLeida] = []
    with abrir_pdf(ruta) as doc:
        if doc.page_count > 60:
            raise ValueError("El catálogo excede 60 páginas.")
        for n, pagina in enumerate(doc, start=1):
            pe = extraer_pagina(pagina, n, psm=11, sin_lineas=True)
            palabras = [p for p in pe.palabras if _limpia(p)]
            claves_x = [p.x0 for p in palabras if re_clave.match(_limpia(p))]
            if not claves_x:
                continue
            x_col = statistics.median(claves_x)
            alto = statistics.median(p.alto for p in palabras)
            col_clave = [p for p in palabras if abs(p.x0 - x_col) < 18 and p.x1 < x_col + 60]
            x_desc = max(p.x1 for p in col_clave) + 2
            # Anclas: cada token de la columna de claves (válido o no) abre una entrada
            anclas = [p for p in col_clave if normalizar(_limpia(p)) != "CLAVE"]
            if not anclas:
                continue
            y_min = min(a.y0 for a in anclas) - alto * 1.6
            y_max = max(a.y1 for a in anclas) + alto * 1.6
            desc = [p for p in palabras if p.x0 >= x_desc and y_min < p.cy < y_max]
            por_ancla: dict[int, list[list[Palabra]]] = {i: [] for i in range(len(anclas))}
            huerfanas = []
            for ln in agrupar_lineas(desc):
                if normalizar(" ".join(_limpia(p) for p in ln)).startswith("DESCRIPCION"):
                    continue
                cy = statistics.fmean(p.cy for p in ln)
                i = min(range(len(anclas)), key=lambda i: abs(anclas[i].cy - cy))
                (por_ancla[i] if abs(anclas[i].cy - cy) <= alto * 1.4 else huerfanas).append(ln)
            for i, a in enumerate(anclas):
                clave = _limpia(a)
                lineas = sorted(por_ancla[i], key=lambda ln: ln[0].cy)
                texto = " ".join(_limpia(p) for ln in lineas for p in ln if _limpia(p))
                texto = re.sub(r"\s+", " ", texto).strip()
                confs = [p.conf for ln in lineas for p in ln if p.conf is not None]
                if a.conf is not None:
                    confs.append(a.conf)
                conf = min(confs) if confs else None
                notas = []
                if not re_clave.match(clave):
                    notas.append("clave con formato inesperado")
                if not texto:
                    notas.append("sin descripción legible")
                if a.conf is not None and a.conf < minimo:
                    notas.append(f"clave leída con confianza baja ({a.conf})")
                elif conf is not None and conf < minimo:
                    notas.append(f"descripción con confianza baja ({conf})")
                entradas.append(EntradaLeida(clave, texto, conf, bool(notas), "; ".join(notas) or None, n))
            for ln in huerfanas:
                entradas.append(EntradaLeida(
                    "", " ".join(_limpia(p) for p in ln), None, True, "texto sin clave asociada", n))
    # Claves repetidas: se conservan todas marcadas; decidir es tarea humana
    vistas: dict[str, int] = {}
    for e in entradas:
        vistas[e.clave] = vistas.get(e.clave, 0) + 1
    for e in entradas:
        if e.clave and vistas[e.clave] > 1:
            e.requiere_revision = True
            e.nota = "; ".join(filter(None, [e.nota, "clave repetida en el documento"]))
    return entradas
