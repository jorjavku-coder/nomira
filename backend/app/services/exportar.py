"""Exportación a Excel (openpyxl) y PDF (ReportLab) a partir del MISMO dict de resultados
que muestra la pantalla: no se recalcula nada aquí."""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from ..config import ajustes
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

AZUL = "12305A"
TURQUESA = "14B8A6"
FMT_MXN = '"$"#,##0.00'
ESTADOS_Q = {"con_prestaciones": "Con prestaciones", "cero": "Sin prestaciones autorizadas ($0.00)",
             "faltante": "FALTANTE (sin comprobante)", "pendiente": "Pendiente de revisión"}


def fecha_mx(iso: str | None) -> str:
    """Fechas en formato mexicano; las que llevan hora se muestran en la zona configurada."""
    if not iso:
        return ""
    if "T" not in iso:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    d = datetime.fromisoformat(iso)
    if d.tzinfo is not None:
        d = d.astimezone(ZoneInfo(ajustes().zona_horaria))
    return d.strftime("%d/%m/%Y %H:%M")


def mxn(v: str | Decimal | None) -> str:
    return "—" if v is None else f"${Decimal(v):,.2f}"


def _estado(res: dict) -> str:
    ev = res["estado_validacion"]
    if ev["validado"]:
        return f"VALIDADO por {ev['por']} el {fecha_mx(ev['fecha'])}"
    return "PROVISIONAL — no validado" + (
        f" ({res['resumen']['alertas_bloqueantes']} pendiente(s) por resolver)"
        if res["resumen"]["alertas_bloqueantes"] else "")


def _hoja(wb: Workbook, titulo: str, encabezados: list[str], anchos: list[int]):
    ws = wb.create_sheet(titulo)
    ws.append(encabezados)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a
    ws.freeze_panes = "A2"
    return ws


def _d(v: str | None):
    return None if v is None else Decimal(v)


def _fecha(iso: str):
    return date.fromisoformat(iso)


def generar_excel(res: dict) -> bytes:
    wb = Workbook()
    exp, cat, r = res["expediente"], res["catalogo"], res["resumen"]
    varias_plazas = len(res["plazas"]) > 1

    ws = wb.active
    ws.title = "Resumen"
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 70
    filas = [
        ("Quincena Clara — Resumen del expediente", None),
        ("Estado de validación", _estado(res)),
        ("Expediente", exp["id"]),
        ("Trabajador", exp["trabajador_nombre"]),
        ("Identificador laboral", exp["identificador_laboral"] or "—"),
        ("Periodo de análisis", f"{fecha_mx(exp['periodo_inicio'])} al {fecha_mx(exp['periodo_fin'])}"),
        ("Catálogo", f"{cat['nombre']} — versión {cat['version']} ({cat['claves_activas']} claves activas)"),
        ("Política de retroactivos", res["politica_retroactivos"]),
        ("Quincenas esperadas", r["quincenas_esperadas"]),
        ("Quincenas con comprobante", r["quincenas_con_recibo"]),
        ("Quincenas faltantes", r["quincenas_faltantes"]),
        ("Quincenas con $0.00 autorizado", r["quincenas_en_cero"]),
        ("Filas incluidas / excluidas / pendientes",
         f"{r['filas_incluidas']} / {r['filas_excluidas']} / {r['filas_pendientes']}"),
        ("Alertas por resolver", r["alertas_bloqueantes"]),
    ]
    for a, b in filas:
        ws.append([a, b])
    ws["A1"].font = Font(bold=True, size=14, color=AZUL)
    for row in ws.iter_rows(min_row=2, max_col=1):
        row[0].font = Font(bold=True)
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=2):
        row[0].alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
    if res["consolidado"]:
        ws.append(["TOTAL DEL EXPEDIENTE (MXN)", _d(res["total_expediente"])])
        ws.cell(ws.max_row, 2).number_format = FMT_MXN
        ws.cell(ws.max_row, 2).font = ws.cell(ws.max_row, 1).font = Font(bold=True, size=12)
    else:
        ws.append(["Totales por plaza (no consolidados)", None])
    if varias_plazas or not res["consolidado"]:
        for pz in res["plazas"]:
            ws.append([f"Plaza {pz['plaza']}", _d(pz["total"])])
            ws.cell(ws.max_row, 2).number_format = FMT_MXN
    if res["faltantes"]:
        ws.append([])
        ws.append(["Quincenas faltantes", None])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
        for f in res["faltantes"]:
            ws.append([f["etiqueta"], f"{fecha_mx(f['inicio'])} al {fecha_mx(f['fin'])}"])

    # Desglose: Quincena · Fecha inicial · Fecha final · Clave · Concepto · Importe · Total de la quincena
    enc = ["Quincena", "Fecha inicial", "Fecha final", "Clave", "Concepto", "Importe", "Total de la quincena"]
    anchos = [34, 13, 13, 9, 62, 15, 20]
    if varias_plazas:
        enc.insert(3, "Plaza")
        anchos.insert(3, 20)
    ws = _hoja(wb, "Desglose por quincena", enc, anchos)
    ci = enc.index("Importe") + 1
    negrita = Font(bold=True)
    for q in res["quincenas"]:
        base = [f"Quincena {q['numero']} — {q['etiqueta']}", _fecha(q["inicio"]), _fecha(q["fin"])]
        relleno = [""] if varias_plazas else []
        for pz in q["plazas"]:
            for c in pz["conceptos"]:
                ws.append(base + ([pz["plaza"]] if varias_plazas else []) +
                          [c["clave"], c["concepto_catalogo"], _d(c["importe"]), None])
        if q["estado"] in ("faltante", "pendiente"):
            ws.append(base + relleno + ["", ESTADOS_Q[q["estado"]], None, None])
            ws.cell(ws.max_row, ci - 1).font = Font(italic=True, color="B45309")
        else:
            nota = "TOTAL" + (" (provisional)" if q["provisional"] else "") + (
                " — sin prestaciones autorizadas" if q["estado"] == "cero" else "")
            if res["consolidado"]:
                lineas = [(relleno, nota, q["total"])]
            else:  # plazas separadas: un total por plaza, sin sumarlas entre sí
                lineas = [([pz["plaza"]], f"{nota} — plaza {pz['plaza']}", pz["total"]) for pz in q["plazas"]] \
                    or [(relleno, nota, q["total"])]
            for rel, texto, total in lineas:
                ws.append(base + rel + ["", texto, None, _d(total)])
                for c in ws[ws.max_row]:
                    c.font = negrita
                    c.fill = PatternFill("solid", fgColor="E6FAF7")
    for row in ws.iter_rows(min_row=2):
        row[1].number_format = row[2].number_format = "DD/MM/YYYY"
        row[ci - 1].number_format = row[ci].number_format = FMT_MXN
        row[ci - 3].number_format = "@"

    ws = _hoja(wb, "Acumulado por prestación", ["Clave", "Concepto (catálogo)", "Retroactivo", "Apariciones", "Total"],
               [9, 66, 12, 12, 18])
    for a in res["acumulado_por_clave"]:
        ws.append([a["clave"], a["concepto_catalogo"], "Sí" if a["retroactivo"] else "No",
                   a["apariciones"], _d(a["total"])])
    ws.append(["", "TOTAL" if res["consolidado"] else "TOTAL (suma de plazas no consolidadas)", "", "",
               sum((Decimal(a["total"]) for a in res["acumulado_por_clave"]), Decimal("0.00"))])
    for c in ws[ws.max_row]:
        c.font = negrita
    for row in ws.iter_rows(min_row=2):
        row[0].number_format = "@"
        row[4].number_format = FMT_MXN

    ws = _hoja(wb, "Excluidos", ["Quincena", "Clave", "Concepto original", "Importe", "Motivo", "Plaza",
                                 "Documento", "Página"], [14, 9, 44, 15, 48, 20, 34, 8])
    for x in res["excluidos"]:
        ws.append([x["quincena"] or "—", x["clave"], x["concepto_original"], _d(x["importe"]), x["motivo"],
                   x["plaza"], x["documento"], x["pagina"]])
    for row in ws.iter_rows(min_row=2):
        row[1].number_format = "@"
        row[3].number_format = FMT_MXN

    ws = _hoja(wb, "Alertas", ["Tipo", "¿Impide validar?", "Mensaje", "Quincena", "Página", "Clave", "Importe leído"],
               [24, 16, 90, 14, 8, 9, 15])
    pend = {x["fila_id"]: x for x in res["pendientes"]}
    for a in res["alertas"]:
        f = pend.get(a.get("fila_id"), {})
        ws.append([a["tipo"], "Sí" if a["bloqueante"] else "No", a["mensaje"], a.get("quincena") or "",
                   a.get("pagina") or "", f.get("clave") or "", _d(f.get("importe"))])
    for row in ws.iter_rows(min_row=2):
        row[2].alignment = Alignment(wrap_text=True, vertical="top")
        row[6].number_format = FMT_MXN

    ws = _hoja(wb, "Trazabilidad", ["Sección", "Fecha", "Usuario", "Elemento", "Campo", "Valor anterior",
                                    "Valor nuevo", "Motivo / detalle"], [16, 18, 28, 44, 14, 20, 20, 60])
    tz = res.get("trazabilidad", {"documentos": [], "correcciones": []})
    ev = res["estado_validacion"]
    if ev["validado"]:
        ws.append(["Validación", fecha_mx(ev["fecha"]), ev["por"], f"Expediente {exp['id']}", "", "", "",
                   ev.get("notas") or ""])
    for d in tz["documentos"]:
        ws.append(["Documento", fecha_mx(d["cargado"]), "", d["nombre"], "", "", "",
                   f"SHA-256 {d['sha256']} · {d['paginas'] or '?'} páginas · {d['estado']}"])
    for c in tz["correcciones"]:
        ref = c.get("referencia") or {}
        elem = f"{ref.get('documento', '')} p.{ref.get('pagina', '')} clave {ref.get('clave_leida', '')}".strip()
        ws.append(["Corrección", fecha_mx(c["fecha"]), c["usuario"], elem, c["campo"], c["valor_anterior"],
                   c["valor_nuevo"], c["motivo"]])
    for x in res["incluidos"]:
        ws.append(["Fila incluida", "", "", f"{x['documento']} p.{x['pagina']}", "clave", "", x["clave"],
                   f"{x['quincena']} · {x['concepto_original'] or '(sin concepto)'} · {mxn(x['importe'])}"
                   + (" · corregida" if x["corregida"] else "")])
    for row in ws.iter_rows(min_row=2):
        row[6].number_format = row[5].number_format = "@"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generar_pdf(res: dict) -> bytes:
    exp, cat, r = res["expediente"], res["catalogo"], res["resumen"]
    validado = res["estado_validacion"]["validado"]
    buf = io.BytesIO()
    est = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=est["Title"], textColor=colors.HexColor("#" + AZUL), fontSize=18, alignment=0)
    h2 = ParagraphStyle("h2", parent=est["Heading2"], textColor=colors.HexColor("#" + AZUL), fontSize=12)
    n = ParagraphStyle("n", parent=est["BodyText"], fontSize=9, leading=12)
    chico = ParagraphStyle("c", parent=n, fontSize=8, leading=10)

    def pie(canvas, doc):
        canvas.saveState()
        if not validado:
            canvas.setFont("Helvetica-Bold", 60)
            canvas.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.10))
            canvas.translate(letter[0] / 2, letter[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, "PROVISIONAL")
            canvas.rotate(-45)
            canvas.translate(-letter[0] / 2, -letter[1] / 2)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, 1.2 * cm, f"Quincena Clara · Expediente {exp['id']} · {_estado(res)}")
        canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    def tabla(datos, anchos, total_rows=(), derecha=()):
        t = Table(datos, colWidths=anchos, repeatRows=1)
        estilo = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + AZUL)),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
                  ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                  ("VALIGN", (0, 0), (-1, -1), "TOP")]
        for c in derecha:
            estilo.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
        for i in total_rows:
            estilo += [("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
                       ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#E6FAF7"))]
        t.setStyle(TableStyle(estilo))
        return t

    P = lambda s, st=chico: Paragraph(str(s).replace("&", "&amp;").replace("<", "&lt;"), st)  # noqa: E731
    el = [Paragraph("Quincena Clara — Cálculo de prestaciones", h1),
          Paragraph(f"<b>Estado de validación:</b> {_estado(res)}", n), Spacer(1, 6)]
    datos = [["Expediente", str(exp["id"])], ["Trabajador", P(exp["trabajador_nombre"])],
             ["Identificador laboral", exp["identificador_laboral"] or "—"],
             ["Periodo de análisis", f"{fecha_mx(exp['periodo_inicio'])} al {fecha_mx(exp['periodo_fin'])}"],
             ["Catálogo y versión", P(f"{cat['nombre']} — versión {cat['version']} ({cat['claves_activas']} claves activas)")],
             ["Política de retroactivos", P(res["politica_retroactivos"])],
             ["Quincenas", f"{r['quincenas_esperadas']} esperadas · {r['quincenas_con_recibo']} con comprobante · "
                           f"{r['quincenas_faltantes']} faltantes · {r['quincenas_en_cero']} en $0.00"],
             ["Total del expediente", mxn(res["total_expediente"]) + " MXN" if res["consolidado"]
              else "Plazas no consolidadas: " + "; ".join(f"{p['plaza']}: {mxn(p['total'])}" for p in res["plazas"])]]
    t = Table(datos, colWidths=[4.2 * cm, 13.3 * cm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                           ("FONTNAME", (1, -1), (1, -1), "Helvetica-Bold")]))
    el += [t, Spacer(1, 10), Paragraph("Desglose por quincena", h2)]

    filas = [["Quincena", "Periodo", "Clave", "Concepto", "Importe", "Total quincena"]]
    totales = []
    for q in res["quincenas"]:
        per = f"{fecha_mx(q['inicio'])} – {fecha_mx(q['fin'])}"
        nombre = P(f"{q['numero']}. {q['etiqueta']}")
        for pz in q["plazas"]:
            for c in pz["conceptos"]:
                concepto = c["concepto_catalogo"] + (f" [plaza {pz['plaza']}]" if len(res["plazas"]) > 1 else "")
                filas.append([nombre, per, c["clave"], P(concepto), mxn(c["importe"]), ""])
                nombre, per = "", ""
        if q["estado"] in ("faltante", "pendiente"):
            filas.append([nombre, per, "", P(ESTADOS_Q[q["estado"]]), "—", "—"])
        else:
            nota = "TOTAL" + (" (provisional)" if q["provisional"] else "") + (
                " — sin prestaciones autorizadas" if q["estado"] == "cero" else "")
            lineas = [(nota, q["total"])] if res["consolidado"] or not q["plazas"] else [
                (f"{nota} plaza {pz['plaza']}", pz["total"]) for pz in q["plazas"]]
            for texto, total in lineas:
                filas.append([nombre, per, "", P(texto), "", mxn(total)])
                nombre, per = "", ""
                totales.append(len(filas) - 1)
    el.append(tabla(filas, [3.6 * cm, 3.5 * cm, 1.1 * cm, 5.3 * cm, 2 * cm, 2.2 * cm], totales, (4, 5)))

    el += [Spacer(1, 10), Paragraph("Acumulado por prestación", h2)]
    filas = [["Clave", "Concepto (catálogo)", "Apariciones", "Total"]]
    for a in res["acumulado_por_clave"]:
        filas.append([a["clave"], P(a["concepto_catalogo"]), a["apariciones"], mxn(a["total"])])
    filas.append(["", "TOTAL", "", mxn(sum((Decimal(a["total"]) for a in res["acumulado_por_clave"]), Decimal("0.00")))])
    el.append(tabla(filas, [1.5 * cm, 11 * cm, 2.2 * cm, 3 * cm], [len(filas) - 1], (2, 3)))

    if res["faltantes"]:
        el += [Spacer(1, 10), Paragraph("Quincenas faltantes (sin comprobante; no se les asignó importe)", h2)]
        el.append(Paragraph("; ".join(f["etiqueta"] for f in res["faltantes"]), n))
    if res["alertas"]:
        el += [Spacer(1, 10), Paragraph("Alertas", h2)]
        filas = [["Impide validar", "Mensaje"]] + [["Sí" if a["bloqueante"] else "No", P(a["mensaje"])]
                                                   for a in res["alertas"][:200]]
        el.append(tabla(filas, [2.5 * cm, 15.2 * cm]))
    el += [Spacer(1, 10), Paragraph(
        f"Se excluyeron {r['filas_excluidas']} fila(s) de percepciones por no coincidir exactamente con una clave "
        "activa del catálogo. Las deducciones, el total neto y los totales del recibo nunca se suman. "
        "El detalle de exclusiones y la trazabilidad completa están en el archivo de Excel.", chico)]

    SimpleDocTemplate(buf, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.8 * cm, title=f"Expediente {exp['id']}").build(el, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()
