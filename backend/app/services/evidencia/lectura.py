"""Lectura de documentos de Evidencia: PDF o imagen → páginas con texto (nativo u OCR) →
clasificación sugerida y hechos propuestos con su fuente (documento, página, fragmento y zona).

Todo lo que produce este módulo es una PROPUESTA: los hechos quedan «por revisar» y la
clasificación como «sugerida» hasta que una persona los confirme. Nada se inventa: un hecho solo
se propone a partir de una frase que existe en el documento.
"""
from __future__ import annotations

import io
import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

import pymupdf

from ...config import ajustes
from ..extraccion import PaginaExtraida, Palabra, agrupar_lineas, extraer_pagina

MESES = {m: i + 1 for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                          "septiembre", "octubre", "noviembre", "diciembre"])}
MESES["setiembre"] = 9
_RE_FECHA_LARGA = re.compile(r"\b(\d{1,2}|primero)\s+de\s+(" + "|".join(MESES) + r")\s+(?:de|del)\s+(?:a[nñ]o\s+)?(\d{4})\b")
_RE_FECHA_NUM = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_RE_FECHA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_RE_IMPORTE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?|\b(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})\s*(?:pesos|m\.?\s?n\.?|mxn)\b")
_TITULOS = r"(?:C\.|Sr\.|Sra\.|Srita\.|Lic\.|Licda\.|Ing\.|Dr\.|Dra\.|Mtro\.|Mtra\.|Arq\.|Contador|el señor|la señora|ciudadano|ciudadana)"
_RE_PERSONA = re.compile(_TITULOS + r"\s+((?:[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+)(?:\s+(?:de|del|la|los|las|y)?\s*[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,4})")

# Tipo sugerido: primera coincidencia en orden de prioridad (texto normalizado, sin acentos).
TIPOS = [
    ("Recibo de nómina", ["comprobante de percepciones", "recibo de nomina", "percepciones y deducciones"]),
    ("Factura / CFDI", ["comprobante fiscal digital", "cfdi", "factura"]),
    ("Contrato", ["contrato"]),
    ("Finiquito / liquidación", ["finiquito", "liquidacion"]),
    ("Aviso de terminación", ["aviso de rescision", "aviso de terminacion", "terminacion de la relacion"]),
    ("Renuncia", ["renuncia"]),
    ("Demanda", ["demanda", "escrito inicial"]),
    ("Resolución / sentencia", ["sentencia", "laudo", "resolucion"]),
    ("Acta", ["acta"]),
    ("Estado de cuenta", ["estado de cuenta"]),
    ("Constancia", ["constancia"]),
    ("Identificación", ["credencial para votar", "instituto nacional electoral", "pasaporte"]),
    ("Oficio", ["oficio"]),
    ("Correo o mensaje", ["asunto:", "de:", "para:", "enviado:", "remitente"]),
]
TIPOS_DISPONIBLES = [t for t, _ in TIPOS] + ["Comprobante de pago", "Fotografía", "Otro"]
MAX_HECHOS_POR_DOCUMENTO = 200
# No terminan una oración: «Lic.», «C.», «S.A.», «M.N.», «C.V.», «No.», viñetas «1.»
_RE_ABREVIATURA = re.compile(r"(?:[A-ZÁÉÍÓÚ][a-záéíóú]{0,4}\.|(?:[A-ZÁÉÍÓÚa-z]\.){1,4}|\d{1,2}\.)")


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# ---------- apertura del archivo ----------

def detectar_formato(datos: bytes) -> str | None:
    if datos.startswith(b"%PDF-"):
        return "pdf"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if datos.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp"
    return None


def abrir(ruta: str, formato: str) -> pymupdf.Document:
    """Abre el original SIN modificarlo. Las imágenes se pasan a PNG en memoria para leerlas."""
    if formato == "pdf":
        doc = pymupdf.open(ruta)
        if not doc.is_pdf or doc.needs_pass:
            raise ValueError("El PDF no se puede abrir (dañado o protegido con contraseña).")
        return doc
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 60_000_000
    with Image.open(ruta) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    return pymupdf.open(stream=buf.getvalue(), filetype="png")


# ---------- hechos propuestos ----------

@dataclass
class HechoPropuesto:
    descripcion: str
    pagina: int
    fragmento: str
    bbox: list[float]
    confianza: int | None
    fecha: date | None = None
    fecha_texto: str | None = None
    importe: Decimal | None = None
    personas: list[str] = field(default_factory=list)
    dato: str | None = None


def buscar_fechas(texto: str) -> list[tuple[date, str]]:
    """Fechas válidas en el texto, en orden de aparición, con el texto tal como aparece."""
    t = normalizar(texto)
    hallazgos: list[tuple[int, date, str]] = []
    for m_ in _RE_FECHA_LARGA.finditer(t):
        dia = 1 if m_[1] == "primero" else int(m_[1])
        hallazgos.append((m_.start(), (dia, MESES[m_[2]], int(m_[3])), texto[m_.start():m_.end()]))
    for m_ in _RE_FECHA_NUM.finditer(t):  # formato mexicano: día/mes/año
        hallazgos.append((m_.start(), (int(m_[1]), int(m_[2]), int(m_[3])), texto[m_.start():m_.end()]))
    for m_ in _RE_FECHA_ISO.finditer(t):
        hallazgos.append((m_.start(), (int(m_[3]), int(m_[2]), int(m_[1])), texto[m_.start():m_.end()]))
    res = []
    for _, (d, mes, anio), crudo in sorted(hallazgos, key=lambda h: h[0]):
        if not 1900 <= anio <= 2100:
            continue
        try:
            res.append((date(anio, mes, d), crudo))
        except ValueError:
            continue  # 31/02/2024 y similares: no se inventa una fecha parecida
    return res


def buscar_importe(texto: str) -> Decimal | None:
    m_ = _RE_IMPORTE.search(texto.lower())
    if not m_:
        return None
    entero, dec = (m_[1], m_[2]) if m_[1] else (m_[3], m_[4])
    try:
        return Decimal(entero.replace(",", "") + "." + (dec or "00"))
    except InvalidOperation:
        return None


def buscar_personas(texto: str) -> list[str]:
    vistas = []
    for m_ in _RE_PERSONA.finditer(texto):
        nombre = re.sub(r"\s+", " ", m_[1]).strip(" ,.;")
        if nombre and nombre not in vistas:
            vistas.append(nombre)
    return vistas[:6]


def _parrafos(pe: PaginaExtraida) -> list[list[Palabra]]:
    """Agrupa líneas cercanas en párrafos (el texto de un hecho suele ocupar varias líneas)."""
    lineas = agrupar_lineas(pe.palabras)
    if not lineas:
        return []
    alto = statistics.median(p.alto for p in pe.palabras) or 8.0
    parrafos, actual, fondo = [], [], None
    for ln in lineas:
        tope = min(p.y0 for p in ln)
        if actual and fondo is not None and tope - fondo > alto * 0.9:
            parrafos.append(actual)
            actual = []
        actual.extend(ln)
        fondo = max(p.y1 for p in ln)
    if actual:
        parrafos.append(actual)
    return parrafos


def _oraciones(parrafo: list[Palabra]) -> list[list[Palabra]]:
    res, actual = [], []
    for p in parrafo:
        actual.append(p)
        if re.search(r"[.;]$", p.texto) and not _RE_ABREVIATURA.fullmatch(p.texto.strip("(),")):
            res.append(actual)
            actual = []
    if actual:
        res.append(actual)
    return res


def proponer_hechos(pe: PaginaExtraida) -> list[HechoPropuesto]:
    """Una propuesta por oración que contenga una fecha o un importe."""
    hechos, vistas = [], set()
    for parrafo in _parrafos(pe):
        for oracion in _oraciones(parrafo):
            texto = re.sub(r"\s+", " ", " ".join(p.texto for p in oracion)).strip()
            if len(texto) < 12:
                continue
            fechas = buscar_fechas(texto)
            importe = buscar_importe(texto)
            if not fechas and importe is None:
                continue
            clave = normalizar(texto)
            if clave in vistas:
                continue
            vistas.add(clave)
            confs = [p.conf for p in oracion if p.conf is not None]
            h = HechoPropuesto(
                descripcion=texto[:600], pagina=pe.numero, fragmento=texto[:1500],
                bbox=[round(v, 1) for v in (min(p.x0 for p in oracion), min(p.y0 for p in oracion),
                                            max(p.x1 for p in oracion), max(p.y1 for p in oracion))],
                confianza=min(confs) if confs else None, importe=importe, personas=buscar_personas(texto))
            if fechas:
                h.fecha, h.fecha_texto = fechas[0]
                otras = [crudo for _, crudo in fechas[1:]]
                if otras:
                    h.dato = "Otras fechas en el texto: " + ", ".join(otras)
            hechos.append(h)
    return hechos


def sugerir_tipo(texto: str) -> str | None:
    t = normalizar(texto[:6000])
    if "asunto:" in t and ("de:" in t or "para:" in t):  # encabezado de correo
        return "Correo o mensaje"
    for tipo, claves in TIPOS:
        if any(c in t for c in claves):
            return tipo
    return None


@dataclass
class Lectura:
    paginas: list[PaginaExtraida]
    hechos: list[HechoPropuesto]
    tipo_sugerido: str | None
    fecha_sugerida: date | None
    paginas_dudosas: list[int]


def leer(ruta: str, formato: str) -> Lectura:
    minimo = ajustes().ocr_confianza_minima
    paginas, hechos, dudosas = [], [], []
    with abrir(ruta, formato) as doc:
        if doc.page_count > ajustes().max_paginas_pdf:
            raise ValueError(f"El documento excede {ajustes().max_paginas_pdf} páginas.")
        for n, pagina in enumerate(doc, start=1):
            pe = extraer_pagina(pagina, n)
            paginas.append(pe)
            texto = pe.texto.strip()
            if len(texto) < 20 or (pe.metodo == "ocr" and (pe.confianza or 0) < minimo):
                dudosas.append(n)
            hechos.extend(proponer_hechos(pe))
    texto_inicio = "\n".join(p.texto for p in paginas[:2])
    fechas = buscar_fechas(paginas[0].texto) if paginas else []
    return Lectura(paginas, hechos[:MAX_HECHOS_POR_DOCUMENTO], sugerir_tipo(texto_inicio),
                   fechas[0][0] if fechas else None, dudosas)
