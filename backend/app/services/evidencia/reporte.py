"""Exportación de Nomira Evidencia a PDF (ReportLab) y Excel (openpyxl), a partir del MISMO panel
que muestra la pantalla. Solo incluye hechos revisados por una persona; los demás se cuentan."""
from __future__ import annotations

import io
from datetime import date, datetime
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ...config import ajustes

AZUL, TURQUESA_CLARO = "123048", "E5F8F6"
AVISO = ("Documento de trabajo generado con Nomira Evidencia. Organiza documentos y hechos revisados por "
         "personas; no contiene conclusiones ni valoraciones jurídicas.")


def _f(iso: str | None) -> str:
    return date.fromisoformat(iso[:10]).strftime("%d/%m/%Y") if iso else "—"


def _fh(d: datetime) -> str:
    return d.astimezone(ZoneInfo(ajustes().zona_horaria)).strftime("%d/%m/%Y %H:%M")


def _mxn(v: str | None) -> str:
    """Importe en texto decimal exacto → «$1,234.56» sin pasar por float."""
    if v is None:
        return ""
    neg = v.startswith("-")
    ent, _, dec = v.lstrip("-").partition(".")
    return ("-" if neg else "") + f"${int(ent):,}.{(dec + '00')[:2]}"


def _revision(h: dict) -> str:
    if h["origen"] == "manual":
        return f"Capturado por {h['creado_por'] or 'usuario'}"
    if h["estado"] == "editado":
        return f"Propuesto por Nomira · editado por {h['revisado_por'] or 'usuario'}"
    return f"Propuesto por Nomira · confirmado por {h['revisado_por'] or 'usuario'}"


def _fuente(h_o_v: dict, docs: dict[int, dict]) -> str:
    d = docs.get(h_o_v.get("documento_id"))
    if not d:
        return "Sin documento"
    return f"D{d['id']} · {d['nombre']}" + (f", p. {h_o_v['pagina']}" if h_o_v.get("pagina") else "")


def _hechos_por_id(datos: dict) -> dict[int, dict]:
    return {h["id"]: h for h in datos["hechos"]}


# ---------------------------------------------------------------- PDF

def _estilos():
    est = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=est["Title"], textColor=colors.HexColor("#" + AZUL), fontSize=20, alignment=0, leading=24),
        "h2": ParagraphStyle("h2", parent=est["Heading2"], textColor=colors.HexColor("#" + AZUL), fontSize=13, spaceBefore=6),
        "n": ParagraphStyle("n", parent=est["BodyText"], fontSize=9, leading=12),
        "c": ParagraphStyle("c", parent=est["BodyText"], fontSize=8, leading=10),
        "gris": ParagraphStyle("g", parent=est["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#64748B")),
    }


def _P(s, st):
    return Paragraph(str(s if s is not None else "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), st)


def _tabla(filas, anchos, cabecera=True):
    t = Table(filas, colWidths=anchos, repeatRows=1 if cabecera else 0)
    estilo = [("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1"))]
    if cabecera:
        estilo += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + AZUL)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                   ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(estilo))
    return t


def _documento(meta: dict, titulo: str, elementos: list) -> bytes:
    buf = io.BytesIO()
    pie_txt = f"Nomira Evidencia · {meta['organizacion']} · Generado el {_fh(meta['generado_en'])} por {meta['generado_por']}"

    def pie(canvas, doc):
        canvas.saveState()
        if meta.get("logo") and doc.page == 1:
            from reportlab.lib.utils import ImageReader
            try:
                img = ImageReader(io.BytesIO(meta["logo"]))
                w, h = img.getSize()
                f = min(4.2 * cm / w, 1.9 * cm / h)
                canvas.drawImage(img, letter[0] - 2 * cm - w * f, letter[1] - 1.5 * cm - h * f, w * f, h * f, mask="auto")
            except Exception:
                pass
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, 1.2 * cm, pie_txt[:150])
        canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(buf, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.8 * cm, title=titulo).build(elementos, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()


def _portada(datos: dict, meta: dict, est: dict, titulo: str) -> list:
    a = datos["asunto"]
    filas = [["Asunto", _P(a["nombre"], est["n"])], ["Cliente", _P(a["cliente"], est["n"])],
             ["Tipo de caso", _P(a["tipo_caso"], est["n"])], ["Jurisdicción", _P(a.get("jurisdiccion_texto") or a["jurisdiccion"], est["n"])],
             ["Identificador interno", _P(a["identificador_interno"], est["n"])], ["Responsable", _P(a["responsable"], est["n"])]]
    filas += [[_P(k, est["n"]), _P(v, est["n"])] for k, v in (a.get("campos") or {}).items()]
    filas += [["Organización", _P(meta["organizacion"], est["n"])],
              ["Generado", _P(f"{_fh(meta['generado_en'])} por {meta['generado_por']} ({meta['generado_por_email']})", est["n"])]]
    t = Table(filas, colWidths=[4.2 * cm, 13.3 * cm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    return [Paragraph(titulo, est["h1"]), Spacer(1, 4), t, Spacer(1, 8), _P(AVISO, est["gris"])]


def pdf(datos: dict, meta: dict) -> bytes:
    est = _estilos()
    docs = {d["id"]: d for d in datos["documentos"]}
    hechos = _hechos_por_id(datos)
    r = datos["resumen"]
    el = _portada(datos, meta, est, "Expediente probatorio")
    el += [Spacer(1, 6), _P(f"{r['documentos']} documento(s) · {r['hechos']['confirmado'] + r['hechos']['editado']} hecho(s) "
                           f"revisado(s) · {r['hechos']['por_revisar']} propuesto(s) sin revisar (no incluidos) · "
                           f"{r['diferencias_pendientes']} posible(s) diferencia(s) por revisar · {r['pendientes_abiertos']} pendiente(s) abierto(s)", est["n"])]

    el += [PageBreak(), Paragraph("1. Índice de documentos", est["h2"])]
    filas = [["Ref.", "Documento", "Tipo", "Fecha", "Págs.", "Lectura", "Cargado por"]]
    for d in datos["documentos"]:
        tipo = d["tipo"] or (f"{d['tipo_sugerido']} (sugerido, sin revisar)" if d["tipo_sugerido"] else "Sin clasificar")
        fecha = _f(d["fecha_documento"]) if d["fecha_documento"] else (f"{_f(d['fecha_sugerida'])} (sug.)" if d["fecha_sugerida"] else "—")
        el_estado = {"leido": "Leído", "requiere_revision": "Requiere revisión", "error": "No legible", "recibido": "Del cliente, sin aceptar",
                     "pendiente": "En proceso", "procesando": "En proceso"}[d["estado"]] + \
            (" · RESTRINGIDO" if d.get("visibilidad") == "restringido" else "")
        filas.append([f"D{d['id']}", _P(d["nombre"], est["c"]), _P(tipo, est["c"]), _P(fecha, est["c"]), d["paginas"] or "—",
                      el_estado, _P(d["subido_por"], est["c"])])
    el.append(_tabla(filas, [1.1 * cm, 5 * cm, 3.2 * cm, 2.2 * cm, 1.1 * cm, 2.2 * cm, 2.7 * cm]) if len(filas) > 1
              else _P("Sin documentos.", est["n"]))

    el += [Spacer(1, 10), Paragraph("2. Cronología de hechos revisados", est["h2"])]
    cr = datos["cronologia"]
    if not cr["eventos"] and not cr["sin_fecha"]:
        el.append(_P("No hay hechos revisados todavía.", est["n"]))
    else:
        filas = [["Fecha", "Hecho", "Fuente", "Revisión"]]
        for h in cr["eventos"] + cr["sin_fecha"]:
            desc = h["descripcion"] + (f" · Importe: {_mxn(h['importe'])}" if h["importe"] else "") + \
                (f" · Personas: {', '.join(h['personas'])}" if h["personas"] else "") + \
                (" · POSIBLE DIFERENCIA ENTRE FUENTES" if h["contradicciones"] else "")
            filas.append([_f(h["fecha"]) if h["fecha"] else "Sin fecha", _P(desc, est["c"]), _P(_fuente(h, docs), est["c"]),
                          _P(_revision(h), est["c"])])
        el.append(_tabla(filas, [2 * cm, 8 * cm, 4 * cm, 3.5 * cm]))
    if datos["contradicciones"]:
        el += [Spacer(1, 8), Paragraph("Posibles diferencias entre fuentes", est["h2"]),
               _P("Nomira señala datos que parecen distintos; no decide cuál es correcto. La columna «Decisión» la registra el abogado.", est["gris"])]
        filas = [["Versión A", "Versión B", "Decisión"]]
        for c in datos["contradicciones"]:
            a, b = (hechos[i] for i in c["hechos"])
            fila = []
            for h in (a, b):
                fila.append(_P(f"{_f(h['fecha']) if h['fecha'] else 'Sin fecha'} — {h['descripcion']} [{_fuente(h, docs)}]", est["c"]))
            filas.append(fila + [_P(c.get("decision_texto") or "Pendiente de revisar", est["c"])])
        el.append(_tabla(filas, [7 * cm, 7 * cm, 3.5 * cm]))

    el += [Spacer(1, 10), Paragraph("3. Matriz de evidencia", est["h2"]),
           _P("El estado de cada punto lo decide el abogado. Las sugerencias del sistema no se incluyen como decisiones.", est["gris"])]
    if not datos["puntos"]:
        el.append(_P("No se han registrado hechos por acreditar.", est["n"]))
    else:
        filas = [["Hecho que se busca acreditar", "Estado (decisión del abogado)", "Evidencia vinculada"]]
        for p in datos["puntos"]:
            ev = "\n".join(f"• [{v.get('relacion_texto', 'Sin evaluar')}] {(v['hecho']['descripcion'][:140] + ' — ') if v.get('hecho') else ''}{_fuente(v, docs)}"
                           + (f" ({v['nota']})" if v["nota"] else "") for v in p["vinculos"]) or "Sin evidencia vinculada"
            decidido = p["estado_texto"] + (f"\n{p['estado_decidido_por']}, {_f(p['estado_decidido_en'])}" if p["estado_decidido_por"] else "\n(sin decisión registrada)")
            filas.append([_P(p["descripcion"] + (f"\nNotas: {p['notas']}" if p["notas"] else ""), est["c"]),
                          _P(decidido, est["c"]), _P(ev, est["c"])])
        el.append(_tabla(filas, [6 * cm, 3.5 * cm, 8 * cm]))

    el += [Spacer(1, 10), Paragraph("4. Pendientes", est["h2"])]
    el += _tabla_pendientes(datos, est, internas=True)
    return _documento(meta, f"Expediente probatorio {datos['asunto']['id']}", el)


def _tabla_pendientes(datos: dict, est: dict, internas: bool) -> list:
    pend = [x for x in datos["pendientes"] if internas or x["estado"] in ("pendiente", "solicitado")]
    if not pend:
        return [_P("No hay pendientes registrados.", est["n"])]
    cab = ["Documento o dato", "Responsable", "Seguimiento", "Estado"] + (["Nota interna"] if internas else [])
    filas = [cab]
    for x in pend:
        fila = [_P(x["descripcion"], est["c"]), _P(x["responsable"], est["c"]), _f(x["fecha_seguimiento"]), x["estado_texto"]]
        if internas:
            fila.append(_P(x["nota"], est["c"]))
        filas.append(fila)
    anchos = [6 * cm, 3 * cm, 2.3 * cm, 2.2 * cm, 4 * cm] if internas else [9 * cm, 3.5 * cm, 2.5 * cm, 2.5 * cm]
    return [_tabla(filas, anchos)]


def pdf_pendientes(datos: dict, meta: dict) -> bytes:
    """Lista para compartir con el cliente: solo lo que sigue abierto y sin notas internas."""
    est = _estilos()
    a = datos["asunto"]
    el = [Paragraph("Documentos e información pendientes", est["h1"]), Spacer(1, 4),
          _P(f"Asunto: {a['nombre']}" + (f" · Cliente: {a['cliente']}" if a["cliente"] else ""), est["n"]),
          _P(f"{meta['organizacion']} · {_fh(meta['generado_en'])}", est["gris"]), Spacer(1, 10)]
    el += _tabla_pendientes(datos, est, internas=False)
    return _documento(meta, f"Pendientes del asunto {a['id']}", el)


# ---------------------------------------------------------------- Excel

def _hoja(wb, titulo, cab, anchos):
    ws = wb.create_sheet(titulo)
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a
    ws.freeze_panes = "A2"
    return ws


def _envolver(ws):
    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")


def excel(datos: dict, meta: dict, solo_pendientes: bool = False) -> bytes:
    wb = Workbook()
    docs = {d["id"]: d for d in datos["documentos"]}
    a = datos["asunto"]
    ws = wb.active
    ws.title = "Portada"
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 80
    for fila in [("Nomira Evidencia — " + ("Pendientes" if solo_pendientes else "Expediente probatorio"), None),
                 ("Asunto", a["nombre"]), ("Cliente", a["cliente"]),
                 *([] if solo_pendientes else [("Tipo de caso", a["tipo_caso"]), ("Jurisdicción", a.get("jurisdiccion_texto") or a["jurisdiccion"]),
                                               ("Identificador interno", a["identificador_interno"]), ("Responsable", a["responsable"]),
                                               *[(k, v) for k, v in (a.get("campos") or {}).items()]]),
                 ("Organización", meta["organizacion"]),
                 ("Generado", f"{_fh(meta['generado_en'])} por {meta['generado_por']} ({meta['generado_por_email']})"),
                 ("Aviso", AVISO)]:
        ws.append([fila[0], None if fila[1] is None and fila[0].startswith("Nomira") else (fila[1] or "—")])
    ws["A1"].font = Font(bold=True, size=14, color=AZUL)
    for fila in ws.iter_rows(min_row=2):
        fila[0].font = Font(bold=True)
        fila[1].alignment = Alignment(wrap_text=True, vertical="top")

    if solo_pendientes:
        ws2 = _hoja(wb, "Pendientes", ["Documento o dato", "Responsable", "Seguimiento", "Estado"], [70, 26, 14, 14])
        for x in datos["pendientes"]:
            if x["estado"] in ("pendiente", "solicitado"):
                ws2.append([x["descripcion"], x["responsable"], date.fromisoformat(x["fecha_seguimiento"]) if x["fecha_seguimiento"] else None,
                            x["estado_texto"]])
        for f in ws2.iter_rows(min_row=2):
            f[2].number_format = "DD/MM/YYYY"
        _envolver(ws2)
        return _guardar(wb)

    ws = _hoja(wb, "Índice de documentos", ["Ref.", "Documento", "Tipo (revisado)", "Tipo sugerido", "Fecha", "Páginas",
                                            "Lectura", "Cargado por", "SHA-256"], [7, 40, 22, 22, 12, 9, 16, 22, 66])
    for d in datos["documentos"]:
        ws.append([f"D{d['id']}", d["nombre"], d["tipo"], d["tipo_sugerido"],
                   date.fromisoformat(d["fecha_documento"]) if d["fecha_documento"] else None, d["paginas"],
                   d["estado"], d["subido_por"], d["sha256"]])
    for f in ws.iter_rows(min_row=2):
        f[4].number_format = "DD/MM/YYYY"

    ws = _hoja(wb, "Cronología", ["Fecha", "Hecho", "Personas", "Importe", "Documento", "Página", "Fragmento de origen",
                                  "Revisión", "Posible contradicción"], [12, 60, 26, 14, 34, 8, 60, 34, 14])
    for h in datos["cronologia"]["eventos"] + datos["cronologia"]["sin_fecha"]:
        d = docs.get(h["documento_id"]) or {}
        ws.append([date.fromisoformat(h["fecha"]) if h["fecha"] else "Sin fecha", h["descripcion"], ", ".join(h["personas"]),
                   float(h["importe"]) if h["importe"] else None, f"D{d.get('id')} · {d.get('nombre')}" if d else None,
                   h["pagina"], h["fragmento"], _revision(h), "Sí" if h["contradicciones"] else ""])
    for f in ws.iter_rows(min_row=2):
        f[0].number_format = "DD/MM/YYYY"
        f[3].number_format = '"$"#,##0.00'
    _envolver(ws)

    ws = _hoja(wb, "Matriz de evidencia", ["Hecho que se busca acreditar", "Estado (decisión del abogado)", "Decidido por",
                                          "Evidencia", "Documento", "Página", "Nota"], [50, 24, 24, 60, 34, 8, 30])
    for p in datos["puntos"]:
        vs = p["vinculos"] or [None]
        for v in vs:
            d = docs.get(v["documento_id"]) if v else None
            ws.append([p["descripcion"], p["estado_texto"], p["estado_decidido_por"] or "(sin decisión)",
                       (v["hecho"]["descripcion"] if v and v.get("hecho") else ("Documento" if v else "Sin evidencia vinculada")),
                       f"D{d['id']} · {d['nombre']}" if d else None, v["pagina"] if v else None, v["nota"] if v else None])
    _envolver(ws)

    ws = _hoja(wb, "Pendientes", ["Documento o dato", "Responsable", "Seguimiento", "Estado", "Nota interna"], [60, 26, 14, 14, 40])
    for x in datos["pendientes"]:
        ws.append([x["descripcion"], x["responsable"], date.fromisoformat(x["fecha_seguimiento"]) if x["fecha_seguimiento"] else None,
                   x["estado_texto"], x["nota"]])
    for f in ws.iter_rows(min_row=2):
        f[2].number_format = "DD/MM/YYYY"
    _envolver(ws)

    ws = _hoja(wb, "Hechos sin revisar", ["Aviso", "Hecho propuesto", "Tipo de dato", "Quién lo afirma", "Documento", "Página",
                                         "Lectura"], [26, 70, 22, 30, 34, 8, 40])
    for h in datos["hechos"]:
        if h["estado"] == "por_revisar":
            d = docs.get(h["documento_id"]) or {}
            ws.append(["PROPUESTA SIN REVISAR — no es un hecho verificado", h["descripcion"], h.get("tipo_dato_texto"),
                       h.get("atribucion"), f"D{d.get('id')} · {d.get('nombre')}" if d else "Sin documento", h["pagina"],
                       (h.get("calidad") or {}).get("lectura")])
    _envolver(ws)
    return _guardar(wb)


def _guardar(wb) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
