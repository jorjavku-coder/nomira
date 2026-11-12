"""Generador de comprobantes SINTÉTICOS (personas y datos ficticios) con la misma disposición
general que un comprobante de percepciones y deducciones. Se usa en pruebas y en la demo.
Ningún dato real de documentos de clientes debe entrar aquí."""
from __future__ import annotations

import io
from decimal import Decimal

import pymupdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

DEDUCCIONES_BASE = [("5408", "IMPUESTO SOBRE LA RENTA", "950.00"), ("5540", "CUOTAS DE SERVICIOS DE SALUD", "450.00")]


def _mxn(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str) and not v.replace(".", "").replace("-", "").isdigit():
        return v  # texto literal (p. ej. un importe mal impreso a propósito)
    d = Decimal(v)
    return ("-" if d < 0 else "") + f"${abs(d):,.2f}"


def recibo(periodo: str, percepciones: list[tuple], *, num="0000100", nombre="EJEMPLO SINTETICO MARIA FERNANDA",
           clave_servidor="900000001", plaza="990000000000001", deducciones=None, total_percepciones=None) -> dict:
    return {"periodo": periodo, "percepciones": percepciones, "num": num, "nombre": nombre,
            "clave_servidor": clave_servidor, "plaza": plaza,
            "deducciones": DEDUCCIONES_BASE if deducciones is None else deducciones,
            "total_percepciones": total_percepciones}


def _suma(filas) -> Decimal:
    t = Decimal("0.00")
    for f in filas:
        try:
            t += Decimal(f[2])
        except Exception:
            pass
    return t


def _dibujar_recibo(c: canvas.Canvas, r: dict):
    W, H = letter
    y = lambda v: H - v  # noqa: E731  (coordenadas desde arriba)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(540, y(22), "NÚM. DE RECIBO")
    c.setFont("Helvetica", 7)
    c.drawCentredString(540, y(34), r["num"])
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(W / 2, y(82), "COMPROBANTE DE PERCEPCIONES Y DEDUCCIONES")

    def banda(yy, celdas):
        for x, etiqueta, valor in celdas:
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(x, y(yy), etiqueta)
            c.setFont("Helvetica", 7)
            c.drawCentredString(x, y(yy + 16), valor)

    banda(104, [(100, "NOMBRE", r["nombre"]), (290, "DEPENDENCIA", "DEPENDENCIA FICTICIA"),
                (430, "CLAVE DE ISSEMyM", "000000"), (525, "CLAVE DE SERVIDOR", r["clave_servidor"])])
    banda(142, [(100, "UNIDAD ADMINISTRATIVA", "UNIDAD DE DEMOSTRACION"), (270, "PUESTO", "PUESTO FICTICIO"),
                (390, "PLAZA", r["plaza"]), (475, "CURP", "XXXX000000XXXXXX00"), (550, "RFC", "XXXX000000XX0")])
    banda(180, [(145, "CÓDIGO PUESTO", "Z0000000"), (220, "CCT", "00XXX0000X"), (285, "L-PAGO", "0000000Z"),
                (365, "PERIODO DE PAGO", r["periodo"]), (458, "CÓDIGO DE UNIDAD", "00000000000000Z")])
    tp = r["total_percepciones"] if r["total_percepciones"] is not None else _suma(r["percepciones"])
    td = _suma(r["deducciones"])
    banda(222, [(187, "TOTAL DE PERCEPCIONES", _mxn(tp)), (291, "TOTAL DE DEDUCCIONES", _mxn(td)),
                (395, "TOTAL NETO", _mxn(Decimal(tp) - td))])

    for x0, titulo, filas in ((63, "PERCEPCIONES", r["percepciones"]), (308, "DEDUCCIONES", r["deducciones"])):
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x0 + 117, y(278), titulo)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x0, y(297), "CLAVE")
        c.drawString(x0 + 34, y(297), "CONCEPTO")
        c.drawRightString(x0 + 231, y(297), "IMPORTE")
        for i, (clave, concepto, importe) in enumerate(filas):
            yy = y(312 + i * 10)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawString(x0, yy, clave or "")
            c.setFont("Helvetica", 6.5)
            c.drawString(x0 + 34, yy, concepto or "")
            c.setFont("Helvetica-Bold", 6.5)
            c.drawRightString(x0 + 231, yy, _mxn(importe))
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, y(585), "SE REALIZÓ EL ABONO EN LA CUENTA NÚM. 00000000000000 EL DÍA: (dato ficticio)")
    c.setFont("Helvetica", 9)
    c.setFillGray(0.6)
    c.drawCentredString(W / 2, y(640), "DOCUMENTO SINTÉTICO DE DEMOSTRACIÓN — SIN VALOR")
    c.setFillGray(0)


def _dibujar_informativa(c: canvas.Canvas):
    W, H = letter
    c.setFont("Helvetica-Bold", 11)
    c.drawString(60, H - 80, "ESTRUCTURA DE CLAVE")
    c.setFont("Helvetica", 9)
    for i, linea in enumerate(["INDICADOR   CLAVE", "TIPOS DE INDICADOR", "DESCRIPCIÓN DE LOS INDICADORES",
                               "0 PERCEPCIÓN FIJA, ingreso bruto cobrado en la quincena actual.",
                               "1 PERCEPCIÓN RETROACTIVA, pago de una percepción no pagada en quincenas anteriores.",
                               "5 DEDUCCIÓN FIJA, descuento aplicado en la quincena actual."]):
        c.drawString(60, H - 110 - i * 16, linea)


def crear_pdf(recibos: list[dict], *, informativas: bool = True, escaneado: bool = False) -> bytes:
    """PDF con texto nativo; con escaneado=True, cada página es solo imagen (obliga a OCR)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter, invariant=1)  # bytes reproducibles
    for r in recibos:
        _dibujar_recibo(c, r)
        c.showPage()
        if informativas:
            _dibujar_informativa(c)
            c.showPage()
    c.save()
    datos = buf.getvalue()
    if not escaneado:
        return datos
    origen = pymupdf.open(stream=datos, filetype="pdf")
    salida = pymupdf.open()
    for pag in origen:
        pix = pag.get_pixmap(dpi=200)
        nueva = salida.new_page(width=pag.rect.width, height=pag.rect.height)
        nueva.insert_image(nueva.rect, stream=pix.tobytes("png"))
    return salida.tobytes(no_new_id=True, deflate=True)  # sin identificador aleatorio: bytes reproducibles


# Réplica sintética del caso de aceptación (mismas claves e importes; persona ficticia).
CASO_ACEPTACION = [
    ("0102", "SUELDO BASE", "7215.40"), ("0136", "FORTALECIMIENTO AL SALARIO DOC", "1591.85"),
    ("0302", "PRIMA POR AÑOS DE SERVICIO DE", "459.00"), ("0303", "ESTUDIOS SUPERIORES MAGIS", "504.00"),
    ("0322", "LABORES DOCENTES", "707.95"), ("0512", "DESPENSA", "483.75"),
    ("1609", "RETR DESPEN EXTRA FIN A DOC", "1497.50"), ("1633", "RETR INCENTIVO POR CONVENIO MA", "1937.00"),
    ("1638", "RETR APOYO FIN DE AÑO MAGISTER", "1360.00")]
BASE = [("0102", "SUELDO BASE", "7505.00"), ("0104", "COMPENSACION", "2505.00"), ("0603", "DIAS CIVICOS", "800.00")]
