"""Lectura determinista de un comprobante de percepciones y deducciones.

Se guía por coordenadas: localiza los encabezados CLAVE / CONCEPTO / IMPORTE y asigna cada
palabra a su columna. No interpreta ni «arregla» valores: lo que no se lee con certeza
queda como None y la fila se marca pendiente más adelante.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from .extraccion import PaginaExtraida, Palabra, agrupar_lineas, normalizar

MESES = {m: i + 1 for i, m in enumerate(
    ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
     "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"])}
MESES["SETIEMBRE"] = 9

_RE_PERIODO = re.compile(r"\b(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+DE\s+([A-Z]+)\s+DE\s+(\d{4})\b")
_RE_IMPORTE = re.compile(r"^(\d{1,3}(?:,\d{3})+|\d+)\.\d{2}$")
_RE_PARECE_IMPORTE = re.compile(r"^[-(]?\$?[-(]?\d[\d.,]*\)?-?$")


@dataclass
class FilaLeida:
    tipo: str  # percepcion | deduccion
    orden: int
    clave: str | None
    concepto: str | None
    importe_texto: str | None
    importe: Decimal | None
    confianza: int | None
    bbox: list[float]


@dataclass
class ReciboLeido:
    num_recibo: str | None = None
    trabajador_nombre: str | None = None
    clave_servidor: str | None = None
    plaza: str | None = None
    periodo_texto: str | None = None
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    total_percepciones: Decimal | None = None
    total_deducciones: Decimal | None = None
    total_neto: Decimal | None = None
    confianza: int | None = None
    filas: list[FilaLeida] = field(default_factory=list)


def parsear_importe(texto: str | None) -> Decimal | None:
    """Convierte «$1,234.56» en Decimal. Conserva el signo («-$5.00», «($5.00)», «5.00-»).
    Devuelve None ante cualquier formato dudoso: nunca adivina ni devuelve cero."""
    if texto is None:
        return None
    t = texto.replace(" ", "").replace("−", "-")
    negativo = False
    if t.startswith("(") and t.endswith(")"):
        negativo, t = True, t[1:-1]
    if t.endswith("-"):
        negativo, t = True, t[:-1]
    if t.startswith("-"):
        negativo, t = True, t[1:]
    t = t.removeprefix("$")
    if t.startswith("-"):
        negativo, t = True, t[1:]
    if not _RE_IMPORTE.match(t):
        return None
    try:
        v = Decimal(t.replace(",", ""))
    except InvalidOperation:
        return None
    return -v if negativo else v


def parsear_periodo(texto: str) -> tuple[str, date, date] | None:
    m = _RE_PERIODO.search(normalizar(texto))
    if not m:
        return None
    d1, d2, mes, anio = int(m[1]), int(m[2]), MESES.get(m[3]), int(m[4])
    if not mes:
        return None
    try:
        ini, fin = date(anio, mes, d1), date(anio, mes, d2)
    except ValueError:
        return None
    if fin < ini:
        return None
    return m[0], ini, fin


def clasificar_pagina(pe: PaginaExtraida) -> str:
    t = normalizar(pe.texto)
    if _tablas(pe):
        return "recibo"
    if "ESTRUCTURA DE CLAVE" in t or "TIPOS DE INDICADOR" in t or "DESCRIPCION DE LOS INDICADORES" in t:
        return "informativa"
    if "COMPROBANTE DE PERCEPCIONES" in t or "PERIODO DE PAGO" in t:
        return "desconocida"  # parece recibo pero no se localizó la tabla: revisión humana
    if len(t.strip()) < 20:
        return "desconocida"
    return "informativa"


def _tablas(pe: PaginaExtraida) -> list[dict]:
    """Localiza cada juego de encabezados CLAVE · CONCEPTO · IMPORTE en una misma línea."""
    tablas = []
    for ln in agrupar_lineas(pe.palabras):
        norm = [normalizar(p.texto).strip(".:") for p in ln]
        i = 0
        while i < len(ln):
            if norm[i] == "CLAVE":
                try:
                    j = norm.index("CONCEPTO", i + 1)
                    k = norm.index("IMPORTE", j + 1)
                except ValueError:
                    break
                if "CLAVE" in norm[i + 1:k]:
                    i += 1
                    continue
                tablas.append({"x_clave": ln[i].x0, "x_concepto": ln[j].x0, "x_imp0": ln[k].x0,
                               "x_imp1": ln[k].x1, "y": max(p.y1 for p in ln[i:k + 1])})
                i = k + 1
            else:
                i += 1
    tablas.sort(key=lambda t: t["x_clave"])
    # Título sobre cada tabla; si no se lee, izquierda = percepciones (formato del comprobante)
    for n, t in enumerate(tablas):
        titulo = None
        for p in pe.palabras:
            if t["y"] - 45 < p.cy < t["y"] - 8 and t["x_clave"] <= p.cx <= t["x_imp1"]:
                s = normalizar(p.texto)
                if s in ("PERCEPCIONES", "DEDUCCIONES"):
                    titulo = "percepcion" if s == "PERCEPCIONES" else "deduccion"
        t["tipo"] = titulo or ("percepcion" if n == 0 else "deduccion")
        t["x_fin"] = tablas[n + 1]["x_clave"] - 4 if n + 1 < len(tablas) else t["x_imp1"] + 20
    return tablas[:2] if len(tablas) >= 2 and {t["tipo"] for t in tablas[:2]} == {"percepcion", "deduccion"} else (
        tablas[:1] if len(tablas) == 1 else [])


def _segmentos(linea: list[Palabra]) -> list[list[Palabra]]:
    """Divide una línea en celdas: por (bloque, línea) nativo o, con OCR, por huecos amplios."""
    segs: list[list[Palabra]] = []
    for p in linea:
        if segs:
            ant = segs[-1][-1]
            mismo = (p.grupo == ant.grupo) if p.grupo is not None else (p.x0 - ant.x1) < max(p.alto, ant.alto) * 1.1
            if mismo:
                segs[-1].append(p)
                continue
        segs.append([p])
    return segs


def _buscar_etiqueta(lineas: list[list[Palabra]], etiqueta: str) -> tuple[int, float, float] | None:
    objetivo = etiqueta.split()
    for n, ln in enumerate(lineas):
        norm = [normalizar(p.texto).strip(".:") for p in ln]
        for i in range(len(ln) - len(objetivo) + 1):
            if norm[i:i + len(objetivo)] == objetivo:
                # Evita confundir «CLAVE» de tabla o «TOTAL DE PERCEPCIONES» con otra etiqueta
                return n, ln[i].x0, ln[i + len(objetivo) - 1].x1
    return None


def _valor_bajo(lineas: list[list[Palabra]], etiqueta: str) -> list[Palabra] | None:
    hallada = _buscar_etiqueta(lineas, etiqueta)
    if not hallada:
        return None
    n, x0, x1 = hallada
    cx = (x0 + x1) / 2
    y_et = max(p.y1 for p in lineas[n])
    for sig in lineas[n + 1:n + 3]:
        if min(p.y0 for p in sig) - y_et > 30:
            break
        segs = _segmentos(sig)
        mejor = min(segs, key=lambda s: abs((s[0].x0 + s[-1].x1) / 2 - cx))
        if abs((mejor[0].x0 + mejor[-1].x1) / 2 - cx) <= max(60.0, (x1 - x0)):
            return mejor
    return None


def _txt(seg: list[Palabra] | None) -> str | None:
    return " ".join(p.texto for p in seg).strip() or None if seg else None


def leer_recibo(pe: PaginaExtraida) -> ReciboLeido | None:
    tablas = _tablas(pe)
    if not tablas:
        return None
    r = ReciboLeido()
    lineas = agrupar_lineas(pe.palabras)
    y_tabla = min(t["y"] for t in tablas)
    cabecera = [ln for ln in lineas if ln[0].cy < y_tabla - 20]

    r.num_recibo = _txt(_valor_bajo(cabecera, "DE RECIBO"))
    if r.num_recibo and not re.fullmatch(r"[\w-]{1,20}", r.num_recibo):
        r.num_recibo = None
    r.trabajador_nombre = _txt(_valor_bajo(cabecera, "NOMBRE"))
    cs = _txt(_valor_bajo(cabecera, "CLAVE DE SERVIDOR"))
    r.clave_servidor = cs if cs and re.fullmatch(r"\d{4,15}", cs) else None
    pz = _txt(_valor_bajo(cabecera, "PLAZA"))
    r.plaza = pz if pz and re.fullmatch(r"[\dA-Z-]{6,30}", pz) else None

    per = parsear_periodo(_txt(_valor_bajo(cabecera, "PERIODO DE PAGO")) or "")
    if not per:  # respaldo: el patrón «DD-DD de Mes de AAAA» solo aparece en el periodo
        per = parsear_periodo(" ".join(p.texto for ln in cabecera for p in ln))
    if per:
        r.periodo_texto, r.periodo_inicio, r.periodo_fin = per

    r.total_percepciones = parsear_importe(_txt(_valor_bajo(cabecera, "TOTAL DE PERCEPCIONES")))
    r.total_deducciones = parsear_importe(_txt(_valor_bajo(cabecera, "TOTAL DE DEDUCCIONES")))
    r.total_neto = parsear_importe(_txt(_valor_bajo(cabecera, "TOTAL NETO")))

    # Límite inferior de las tablas: el recuadro «SE REALIZÓ EL ABONO…»
    y_fin = pe.alto
    for ln in lineas:
        s = normalizar(" ".join(p.texto for p in ln))
        if ln[0].cy > y_tabla + 5 and ("ABONO EN LA CUENTA" in s or "SE REALIZO EL" in s):
            y_fin = min(p.y0 for p in ln) - 2
            break

    for t in tablas:
        zona = [p for p in pe.palabras
                if t["y"] + 1 < p.cy < y_fin and t["x_clave"] - 8 <= p.cx < t["x_fin"]]
        orden = 0
        for ln in agrupar_lineas(zona):
            claves = [p for p in ln if p.x0 < t["x_concepto"] - 3]
            resto = [p for p in ln if p not in claves]
            # Columna de importe: alineada a la derecha bajo «IMPORTE». Si el texto ahí no es un
            # importe válido se conserva tal cual (importe_texto) y la fila quedará pendiente.
            imps = [p for p in resto if abs(p.x1 - t["x_imp1"]) < 8
                    or (p.x1 > t["x_imp0"] - 30 and _RE_PARECE_IMPORTE.match(p.texto))]
            concepto = [p for p in resto if p not in imps]
            if not claves and not imps:
                # Texto suelto dentro del recuadro: no es fila si no trae clave ni importe
                if sum(c.isalnum() for p in concepto for c in p.texto) < 4:
                    continue
            orden += 1
            imp_txt = "".join(p.texto for p in imps) or None
            confs = [p.conf for p in claves + imps if p.conf is not None]
            r.filas.append(FilaLeida(
                tipo=t["tipo"], orden=orden,
                clave="".join(p.texto for p in claves) or None,
                concepto=" ".join(p.texto for p in concepto) or None,
                importe_texto=imp_txt, importe=parsear_importe(imp_txt),
                confianza=min(confs) if confs else None,
                bbox=[round(v, 1) for v in (min(p.x0 for p in ln), min(p.y0 for p in ln),
                                            max(p.x1 for p in ln), max(p.y1 for p in ln))]))
    confs = [f.confianza for f in r.filas if f.confianza is not None]
    r.confianza = min(confs) if confs else pe.confianza
    return r


def limites_quincena(anio: int, mes: int, mitad: int) -> tuple[date, date]:
    if mitad == 1:
        return date(anio, mes, 1), date(anio, mes, 15)
    return date(anio, mes, 16), date(anio, mes, calendar.monthrange(anio, mes)[1])
