"""Extracción por página: texto nativo si existe; OCR (Tesseract) si no hay texto suficiente.

Ambos caminos producen la misma estructura (palabras con coordenadas en puntos de página),
de modo que el lector de recibos no necesita saber de dónde vino el texto.
"""
from __future__ import annotations

import io
import statistics
import unicodedata
from dataclasses import dataclass, field

import pymupdf

from ..config import ajustes


@dataclass
class Palabra:
    x0: float
    y0: float
    x1: float
    y1: float
    texto: str
    conf: int | None = None  # confianza OCR 0-100; None = texto nativo
    grupo: tuple | None = None  # (bloque, línea) del PDF nativo: delimita celdas con exactitud

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def alto(self) -> float:
        return self.y1 - self.y0


@dataclass
class PaginaExtraida:
    numero: int
    ancho: float
    alto: float
    metodo: str  # texto | ocr
    palabras: list[Palabra] = field(default_factory=list)
    confianza: int | None = None

    @property
    def texto(self) -> str:
        return "\n".join(" ".join(p.texto for p in ln) for ln in agrupar_lineas(self.palabras))


def normalizar(s: str) -> str:
    """Mayúsculas sin acentos, para comparar etiquetas (no para autorizar claves)."""
    s = unicodedata.normalize("NFD", s.upper())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def agrupar_lineas(palabras: list[Palabra]) -> list[list[Palabra]]:
    if not palabras:
        return []
    alto = statistics.median(p.alto for p in palabras) or 8.0
    lineas: list[list[Palabra]] = []
    for p in sorted(palabras, key=lambda p: (p.cy, p.x0)):
        if lineas and abs(p.cy - statistics.fmean(q.cy for q in lineas[-1])) <= alto * 0.55:
            lineas[-1].append(p)
        else:
            lineas.append([p])
    return [sorted(ln, key=lambda p: p.x0) for ln in lineas]


def quitar_lineas(img, largo_min: int):
    """Borra trazos rectos largos (bordes de tabla), que degradan mucho el OCR de tablas."""
    import numpy as np
    from PIL import Image

    a = np.array(img.convert("L"))
    salida = a.copy()
    for transponer in (False, True):
        m = (a < 140).T if transponer else (a < 140)
        corrida = np.zeros(m.shape, dtype=np.int32)
        c = np.zeros(m.shape[0], dtype=np.int32)
        for j in range(m.shape[1]):
            c = np.where(m[:, j], c + 1, 0)
            corrida[:, j] = c
        mascara = np.zeros(m.shape, dtype=bool)
        c = np.zeros(m.shape[0], dtype=np.int32)
        for j in range(m.shape[1] - 1, -1, -1):
            c = np.where(m[:, j], np.maximum(c, corrida[:, j]), 0)
            mascara[:, j] = c >= largo_min
        salida[mascara.T if transponer else mascara] = 255
    return Image.fromarray(salida)


def _ocr_imagen(img, escala: float, psm: int = 6) -> list[Palabra]:
    import pytesseract

    datos = pytesseract.image_to_data(
        img, lang=ajustes().ocr_idioma, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    palabras = []
    for i, txt in enumerate(datos["text"]):
        txt = txt.strip()
        conf = int(float(datos["conf"][i]))
        if not txt or conf < 0:
            continue
        x, y, w, h = (datos[k][i] for k in ("left", "top", "width", "height"))
        palabras.append(Palabra(x * escala, y * escala, (x + w) * escala, (y + h) * escala, txt, conf))
    return palabras


def ocr_pagina(pagina: pymupdf.Page, dpi: int | None = None, psm: int = 6,
               sin_lineas: bool = False) -> list[Palabra]:
    from PIL import Image

    dpi = dpi or ajustes().ocr_dpi
    pix = pagina.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    if sin_lineas:
        img = quitar_lineas(img, int(dpi * 0.35))
    return _ocr_imagen(img, 72.0 / dpi, psm)


def extraer_pagina(pagina: pymupdf.Page, numero: int, psm: int = 6,
                   sin_lineas: bool = False) -> PaginaExtraida:
    r = pagina.rect
    nativas = [Palabra(w[0], w[1], w[2], w[3], w[4], None, (w[5], w[6]))
               for w in pagina.get_text("words") if w[4].strip()]
    if sum(len(p.texto) for p in nativas) >= ajustes().ocr_min_caracteres:
        return PaginaExtraida(numero, r.width, r.height, "texto", nativas)
    palabras = ocr_pagina(pagina, psm=psm, sin_lineas=sin_lineas)
    conf = round(statistics.fmean(p.conf for p in palabras)) if palabras else 0
    return PaginaExtraida(numero, r.width, r.height, "ocr", palabras, conf)


def abrir_pdf(ruta: str) -> pymupdf.Document:
    doc = pymupdf.open(ruta)
    if not doc.is_pdf:
        raise ValueError("El archivo no es un PDF válido.")
    if doc.needs_pass:
        raise ValueError("El PDF está protegido con contraseña.")
    return doc
