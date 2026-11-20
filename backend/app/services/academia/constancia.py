"""Constancia de PARTICIPACIÓN en PDF. No es una certificación oficial, acreditación profesional ni
aval institucional: así lo dice el propio documento."""
from __future__ import annotations

import io
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MARINO, TURQUESA, GRIS = HexColor("#0F2A44"), HexColor("#0E8C8C"), HexColor("#64748B")


def _fecha(d: datetime) -> str:
    d = d.astimezone(ZoneInfo("America/Mexico_City"))
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _ajustar(c: canvas.Canvas, texto: str, fuente: str, tam: float, ancho: float) -> float:
    while tam > 10 and c.stringWidth(texto, fuente, tam) > ancho:
        tam -= 1
    return tam


def pdf(*, participante: str, curso: str, organizacion: str, fecha: datetime, folio: str, duracion_min: int | None,
        instructor: str | None, calificacion: int | None) -> bytes:
    buf = io.BytesIO()
    w, h = landscape(letter)
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setTitle(f"Constancia de participación — {curso}")
    c.setAuthor(organizacion)
    c.setStrokeColor(TURQUESA)
    c.setLineWidth(3)
    c.rect(28, 28, w - 56, h - 56)
    c.setLineWidth(0.8)
    c.rect(36, 36, w - 72, h - 72)
    c.setFillColor(MARINO)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(w / 2, h - 90, organizacion.upper()[:90])
    c.setFillColor(TURQUESA)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(w / 2, h - 150, "Constancia de participación")
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 195, "Se hace constar que")
    c.setFillColor(MARINO)
    t = _ajustar(c, participante, "Helvetica-Bold", 26, w - 160)
    c.setFont("Helvetica-Bold", t)
    c.drawCentredString(w / 2, h - 235, participante)
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 275, "completó el curso")
    c.setFillColor(MARINO)
    t = _ajustar(c, f"«{curso}»", "Helvetica-Bold", 20, w - 160)
    c.setFont("Helvetica-Bold", t)
    c.drawCentredString(w / 2, h - 308, f"«{curso}»")
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 12)
    detalles = [f"Fecha de conclusión: {_fecha(fecha)}"]
    if duracion_min:
        detalles.append(f"Duración estimada: {duracion_min} min")
    if calificacion is not None:
        detalles.append(f"Calificación del cuestionario: {calificacion} / 100")
    c.drawCentredString(w / 2, h - 345, "   ·   ".join(detalles))
    if instructor:
        c.drawCentredString(w / 2, h - 365, f"Instructor o autor: {instructor[:90]}")
    c.setFont("Helvetica", 10)
    c.drawString(60, 92, f"Folio: {folio}")
    c.drawRightString(w - 60, 92, "Emitida con Nomira Academia")
    c.setFont("Helvetica-Oblique", 8.5)
    c.drawCentredString(w / 2, 62, "Constancia de participación interna. No es una certificación oficial, una acreditación profesional ni un aval "
                                   "de ninguna institución.")
    c.showPage()
    c.save()
    return buf.getvalue()
