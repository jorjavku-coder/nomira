"""PDF de la cotización con la marca de Nomira (mismo logotipo y colores que los correos).

Solo muestra lo que ve el cliente: nada de notas internas, motivos de descuento, costos ni márgenes.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

MARINO, MARINO_900, TURQUESA, TURQUESA_700 = HexColor("#123048"), HexColor("#0A1B2B"), HexColor("#01B2A6"), HexColor("#047A72")
CREMA, CREMA_300, GRIS, TEXTO = HexColor("#FCF9F4"), HexColor("#E7E1D6"), HexColor("#64748B"), HexColor("#334155")
LOGO = Path(__file__).with_name("logo.png")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
ZONA = ZoneInfo("America/Mexico_City")

_e = {
    "normal": ParagraphStyle("n", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=TEXTO),
    "chico": ParagraphStyle("c", fontName="Helvetica", fontSize=8, leading=11, textColor=GRIS),
    "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=MARINO, spaceBefore=10, spaceAfter=5),
    "etiqueta": ParagraphStyle("e", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=TURQUESA_700),
    "fuerte": ParagraphStyle("f", fontName="Helvetica-Bold", fontSize=9.5, leading=13.5, textColor=MARINO),
    "der": ParagraphStyle("d", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=TEXTO, alignment=TA_RIGHT),
    "der_fuerte": ParagraphStyle("df", fontName="Helvetica-Bold", fontSize=9.5, leading=13.5, textColor=MARINO, alignment=TA_RIGHT),
    "total": ParagraphStyle("to", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=white, alignment=TA_RIGHT),
    "total_izq": ParagraphStyle("ti", fontName="Helvetica-Bold", fontSize=11, leading=17, textColor=white),
    "cab": ParagraphStyle("cb", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=white),
    "cab_der": ParagraphStyle("cbd", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=white, alignment=TA_RIGHT),
}


def pesos(v) -> str:
    d = Decimal(str(v or 0))
    return f"${d:,.2f}"


def pct(v) -> str:
    d = Decimal(str(v or 0)).normalize()
    return f"{d:f}"


def fecha_larga(d: date | datetime | str | None, hora: bool = False) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        d = datetime.fromisoformat(d) if "T" in d else date.fromisoformat(d)
    if isinstance(d, datetime):
        d = d.astimezone(ZONA)
        base = f"{d.day} de {MESES[d.month - 1]} de {d.year}"
        return f"{base}, {d:%H:%M} h (hora del centro de México)" if hora else base
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _p(t: str | None, estilo: str = "normal") -> Paragraph:
    return Paragraph(escape(t or "").replace("\n", "<br/>"), _e[estilo])


def _bloque(titulo: str, filas: list[str | None]) -> list:
    filas = [f for f in filas if f]
    return [_p(titulo.upper(), "etiqueta"), Spacer(0, 2)] + [_p(f) for f in filas]


def generar(*, folio: str, version: int, emision: date | str | None, vence_en: datetime, cliente: dict, necesidad: str | None,
            calculo: dict, entrada: dict, nomira: dict, preparada_por: str | None, borrador: bool = False) -> bytes:
    buf = io.BytesIO()
    pie_notas = (nomira.get("notas_pie") or "").strip()

    def fondo(c, doc):
        w, h = letter
        c.saveState()
        c.setFillColor(MARINO_900)
        c.rect(0, h - 30 * mm, w, 30 * mm, stroke=0, fill=1)
        c.setFillColor(TURQUESA)
        c.rect(0, h - 31.2 * mm, w, 1.2 * mm, stroke=0, fill=1)
        if LOGO.exists():
            c.drawImage(str(LOGO), 18 * mm, h - 22 * mm, width=42 * mm, height=42 * mm * 111 / 399, mask="auto")
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 15)
        c.drawRightString(w - 18 * mm, h - 14 * mm, "Cotización")
        c.setFont("Helvetica", 9)
        c.drawRightString(w - 18 * mm, h - 19.5 * mm, f"Folio {folio} · versión {version}")
        if emision:
            c.drawRightString(w - 18 * mm, h - 24 * mm, f"Emitida el {fecha_larga(emision)}")
        if borrador:
            c.setFillColor(HexColor("#F59E0B"))
            c.setFont("Helvetica-Bold", 9)
            c.drawString(70 * mm, h - 15 * mm, "VISTA PREVIA — NO ENVIADA")
        c.setFillColor(GRIS)
        c.setFont("Helvetica", 7.5)
        if pie_notas:
            c.drawString(18 * mm, 12 * mm, pie_notas[:150])
        c.drawRightString(w - 18 * mm, 12 * mm, f"{folio} · página {doc.page}")
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=38 * mm, bottomMargin=20 * mm,
                            title=f"Cotización {folio}", author=nomira.get("nombre_comercial") or "Nomira")
    ancho = letter[0] - 36 * mm
    h: list = []

    de = _bloque("De", [nomira.get("nombre_comercial"), nomira.get("razon_social"), f"RFC {nomira['rfc']}" if nomira.get("rfc") else None,
                        nomira.get("domicilio"), nomira.get("correo_ventas"), nomira.get("telefono"), nomira.get("sitio_web")])
    para = _bloque("Para", [cliente.get("despacho"), f"Atención: {cliente.get('contacto')}", cliente.get("email"), cliente.get("telefono")])
    t = Table([[de, para]], colWidths=[ancho / 2, ancho / 2])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    h += [t, Spacer(0, 6)]

    vig = Table([[_p(f"Vigencia: válida hasta el {fecha_larga(vence_en, hora=True)}", "fuerte")]], colWidths=[ancho])
    vig.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor("#E5F8F6")), ("BOX", (0, 0), (-1, -1), 0.6, TURQUESA),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    h += [vig]

    if necesidad:
        h += [_p("Lo que nos compartió", "titulo"), _p(necesidad)]

    paq, per = calculo["paquete"], calculo["periodicidad"]
    h += [_p(f"Paquete {paq['nombre']} · cobro {per['nombre'].lower()}", "titulo")]
    filas_mod = [[_p("Módulo", "cab"), _p("Condición", "cab")]]
    for x in calculo["modulos"]:
        filas_mod.append([_p(x["nombre"]), _p("Incluido en el paquete" if x["incluido"] else f"Adicional · {pesos(x['unitario'])} al mes")])
    us, al = calculo["usuarios"], calculo["almacenamiento"]
    filas_mod.append([_p("Usuarios internos", "fuerte"), _p(f"{us['total']} ({us['incluidos']} incluidos" + (f" + {us['adicionales']} adicionales)" if us["adicionales"] else ")"))])
    filas_mod.append([_p("Almacenamiento", "fuerte"), _p(f"{al['total_gb']} GB ({al['incluido_gb']} GB incluidos" + (f" + {al['bloques']} bloque(s) de {al['gb_bloque']} GB)" if al["bloques"] else ")"))])
    tm = Table(filas_mod, colWidths=[ancho * 0.45, ancho * 0.55])
    tm.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), MARINO), ("LINEBELOW", (0, 1), (-1, -1), 0.4, CREMA_300),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    h += [tm, Spacer(0, 3), _p("Los clientes que invite al portal no cuentan como usuarios internos.", "chico")]
    if calculo.get("asuntos_estimados"):
        h += [_p(f"Como referencia aproximada, el almacenamiento alcanza para unos {calculo['asuntos_estimados']:,} asuntos. "
                 "No es un límite de contratación: no se cobra por expediente.", "chico")]

    h += [_p("Desglose", "titulo")]
    filas = [[_p("Concepto", "cab"), _p("Cant.", "cab_der"), _p("Precio", "cab_der"), _p("Meses", "cab_der"), _p("Importe", "cab_der")]]
    for ln in calculo["lineas"]:
        concepto = escape(ln["concepto"]) + (f"<br/><font size=7.5 color='#64748B'>{escape(ln['detalle'])}</font>" if ln.get("detalle") else "")
        filas.append([Paragraph(concepto, _e["normal"]), _p(str(ln["cantidad"]), "der"),
                      _p(pesos(ln["unitario"]) + (" /mes" if ln["tipo"] == "recurrente" else ""), "der"),
                      _p(str(ln["meses"]) if ln.get("meses") else "Pago único", "der"), _p(pesos(ln["importe"]), "der")])
    td = Table(filas, colWidths=[ancho * 0.42, ancho * 0.08, ancho * 0.18, ancho * 0.12, ancho * 0.2], repeatRows=1)
    td.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), MARINO), ("LINEBELOW", (0, 1), (-1, -1), 0.4, CREMA_300),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    h += [td, Spacer(0, 6)]

    tot = [[_p("Subtotal"), _p(pesos(calculo["subtotal"]), "der")]]
    if calculo.get("descuento"):
        tot.append([_p("Descuento"), _p("-" + pesos(calculo["descuento"]["importe"]), "der")])
    tot.append([_p(f"IVA ({pct(calculo['iva_pct'])}%)"), _p(pesos(calculo["iva"]), "der")])
    tot.append([_p("Total MXN", "total_izq"), _p(pesos(calculo["total"]), "total")])
    tt = Table(tot, colWidths=[ancho * 0.25, ancho * 0.25], hAlign="RIGHT")
    tt.setStyle(TableStyle([("BACKGROUND", (0, -1), (-1, -1), TURQUESA_700), ("LINEBELOW", (0, 0), (-1, -2), 0.4, CREMA_300),
                            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    h += [KeepTogether([tt])]
    if per["meses"] > 1:
        h += [Spacer(0, 2), _p(f"Equivale a {pesos(calculo['mensual'])} al mes antes de IVA, cobrados por periodo {per['nombre'].lower()}.", "chico")]

    cond = []
    if entrada.get("condiciones_pago"):
        cond.append(("Condiciones de pago", entrada["condiciones_pago"]))
    if entrada.get("fecha_limite_pago"):
        cond.append(("Fecha límite de pago", fecha_larga(entrada["fecha_limite_pago"])))
    if entrada.get("terminos"):
        cond.append(("Términos", entrada["terminos"]))
    if entrada.get("observaciones"):
        cond.append(("Observaciones", entrada["observaciones"]))
    if nomira.get("condiciones"):
        cond.append(("Condiciones comerciales", nomira["condiciones"]))
    if cond:
        h += [_p("Condiciones", "titulo")]
        for t_, v in cond:
            h += [_p(t_, "fuerte"), _p(v), Spacer(0, 3)]

    h += [_p("Formas de pago", "titulo")]
    fp = nomira.get("formas_pago") or []
    if not fp:
        h += [_p("Le compartiremos las formas de pago al confirmar su contratación.")]
    for f in fp:
        if f["clave"] == "spei":
            h += [_p(f["nombre"], "fuerte"), _p(f"Banco: {f['banco']} · Titular: {f['titular']} · CLABE: {f['clabe']}"), _p(f.get("instrucciones")), Spacer(0, 3)]
        else:
            h += [_p(f["nombre"], "fuerte"), _p(f.get("instrucciones")), Spacer(0, 3)]

    h += [_p("Cómo contratar o pedir ajustes", "titulo"),
          _p(nomira.get("instrucciones_contratar") or "Use el enlace de su propuesta para aceptarla o pedir ajustes, o responda al correo con el que la recibió.")]
    contacto = " · ".join(x for x in (nomira.get("correo_ventas"), nomira.get("telefono"), nomira.get("sitio_web")) if x)
    if contacto or preparada_por:
        h += [Spacer(0, 6), _p(" · ".join(x for x in (f"Preparada por {preparada_por}" if preparada_por else None, contacto or None) if x), "chico")]
    h += [Spacer(0, 4), _p("Esta cotización no incluye asesoría jurídica. Los precios están en pesos mexicanos.", "chico")]
    doc.build(h, onFirstPage=fondo, onLaterPages=fondo)
    return buf.getvalue()
