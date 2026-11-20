"""Diploma (o constancia) de Academia en PDF, horizontal, con el logo del despacho, folio y un código
QR que lleva a la página pública de verificación. No es una certificación oficial, acreditación
profesional ni aval institucional: así lo dice el propio documento."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .constancia import _ajustar, _fecha

MARINO, MARINO_900, TURQUESA, TURQUESA_700 = HexColor("#123048"), HexColor("#0A1B2B"), HexColor("#01B2A6"), HexColor("#047A72")
DORADO, GRIS, CREMA = HexColor("#B88A2E"), HexColor("#64748B"), HexColor("#FCF9F4")
LOGO_NOMIRA = Path(__file__).resolve().parents[1] / "comercial" / "logo.png"


def _qr(c: canvas.Canvas, url: str, x: float, y: float, tam: float) -> None:
    w = QrCodeWidget(url, barLevel="M")
    b = w.getBounds()
    d = Drawing(tam, tam, transform=[tam / (b[2] - b[0]), 0, 0, tam / (b[3] - b[1]), 0, 0])
    d.add(w)
    renderPDF.draw(d, c, x, y)


def pdf(*, participante: str, curso: str, organizacion: str, fecha: datetime, folio: str, duracion_min: int | None, instructor: str | None,
        calificacion: int | None, url_verificacion: str, tipo: str = "diploma", logo_png: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    w, h = landscape(letter)
    c = canvas.Canvas(buf, pagesize=(w, h))
    titulo = "Diploma" if tipo == "diploma" else "Constancia de participación"
    c.setTitle(f"{titulo} — {curso}")
    c.setAuthor(organizacion)
    c.setFillColor(CREMA)
    c.rect(0, 0, w, h, stroke=0, fill=1)
    # marco
    c.setFillColor(MARINO_900)
    c.rect(0, h - 70, w, 70, stroke=0, fill=1)
    c.setFillColor(TURQUESA)
    c.rect(0, h - 74, w, 4, stroke=0, fill=1)
    c.setStrokeColor(DORADO)
    c.setLineWidth(1.2)
    c.rect(26, 26, w - 52, h - 122)
    c.setLineWidth(0.5)
    c.rect(32, 32, w - 64, h - 134)
    # encabezado: logo del despacho (si lo tiene) y de Nomira
    if logo_png:
        try:
            img = ImageReader(io.BytesIO(logo_png))
            iw, ih = img.getSize()
            alto = 42
            c.drawImage(img, 40, h - 56, width=alto * iw / ih, height=alto, mask="auto", preserveAspectRatio=True)
        except Exception:
            pass
    else:
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(40, h - 42, organizacion.upper()[:60])
    if LOGO_NOMIRA.exists():
        c.drawImage(str(LOGO_NOMIRA), w - 40 - 108, h - 50, width=108, height=108 * 111 / 399, mask="auto")
    # cuerpo
    c.setFillColor(TURQUESA_700)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(w / 2, h - 128, organizacion.upper()[:90] + " OTORGA EL PRESENTE")
    c.setFillColor(MARINO)
    c.setFont("Helvetica-Bold", 40 if tipo == "diploma" else 30)
    c.drawCentredString(w / 2, h - 185, titulo.upper() if tipo == "diploma" else titulo)
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 225, "a")
    c.setFillColor(MARINO)
    t = _ajustar(c, participante, "Helvetica-Bold", 30, w - 200)
    c.setFont("Helvetica-Bold", t)
    c.drawCentredString(w / 2, h - 272, participante)
    c.setStrokeColor(DORADO)
    c.setLineWidth(0.8)
    c.line(w / 2 - 220, h - 285, w / 2 + 220, h - 285)
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 318, "por haber concluido satisfactoriamente el curso" if tipo == "diploma" else "por haber completado el curso")
    c.setFillColor(MARINO)
    t = _ajustar(c, f"«{curso}»", "Helvetica-Bold", 21, w - 200)
    c.setFont("Helvetica-Bold", t)
    c.drawCentredString(w / 2, h - 355, f"«{curso}»")
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 11.5)
    detalles = [_fecha(fecha)]
    if duracion_min:
        horas = duracion_min / 60
        detalles.append(f"{horas:g} h" if duracion_min >= 60 else f"{duracion_min} min")
    if calificacion is not None:
        detalles.append(f"Calificación {calificacion}/100")
    c.drawCentredString(w / 2, h - 390, "   ·   ".join(detalles))
    # firma del instructor
    if instructor:
        c.setStrokeColor(MARINO)
        c.setLineWidth(0.6)
        c.line(w / 2 - 110, 118, w / 2 + 110, 118)
        c.setFillColor(MARINO)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawCentredString(w / 2, 104, instructor[:70])
        c.setFillColor(GRIS)
        c.setFont("Helvetica", 9)
        c.drawCentredString(w / 2, 92, "Instructor(a) o autor(a)")
    # verificación
    _qr(c, url_verificacion, w - 32 - 86, 40, 80)
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 8.5)
    c.drawRightString(w - 32 - 92, 92, f"Folio {folio}")
    c.drawRightString(w - 32 - 92, 80, "Verifique su autenticidad con el código QR")
    c.drawRightString(w - 32 - 92, 68, url_verificacion[:70])
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(40, 46, "Reconocimiento interno de capacitación emitido con Nomira Academia.")
    c.drawString(40, 36, "No es una certificación oficial, una acreditación profesional ni un aval de ninguna institución.")
    c.showPage()
    c.save()
    return buf.getvalue()
