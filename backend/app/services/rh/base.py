"""Recursos humanos para el despacho y para las empresas a las que les lleva RH.

- Vacaciones según el artículo 76 de la Ley Federal del Trabajo (reforma de 2023): 12 días al cumplir el primer año,
  +2 por año hasta 20 al quinto, y +2 cada cinco años después. Prima vacacional mínima de 25 % (art. 80).
- La nómina es de CONTROL: sueldo por días pagados, descuentos por faltas y permisos sin goce, prima vacacional y los
  conceptos que RH capture (bonos, ISR o IMSS retenidos que le dé su contador). No calcula impuestos ni timbra CFDI.
- Portal del empleado: enlace personal + NIP de 6 dígitos (solo se guardan sus huellas).
"""
from __future__ import annotations

import hashlib
import io
import math
import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ...config import ajustes
from ...security import hash_contrasena

CENT = Decimal("0.01")
TIPOS = {"vacaciones": "Vacaciones", "permiso": "Permiso con goce de sueldo", "permiso_sin_goce": "Permiso sin goce de sueldo",
         "incapacidad": "Incapacidad (IMSS)", "falta": "Falta injustificada", "retardo": "Retardo"}
DESCUENTAN = {"falta", "permiso_sin_goce"}  # restan días pagados en la nómina
PIDE_EMPLEADO = {"vacaciones", "permiso", "permiso_sin_goce", "incapacidad"}
DOCUMENTOS = {"ine": "INE", "curp": "CURP", "csf": "Constancia de situación fiscal (RFC)", "nss": "Número de Seguridad Social",
              "domicilio": "Comprobante de domicilio", "acta": "Acta de nacimiento", "estudios": "Comprobante de estudios o cédula",
              "contrato": "Contrato de trabajo", "alta_imss": "Alta en el IMSS", "otro": "Otro"}
REQUERIDOS = ["ine", "curp", "csf", "nss", "domicilio", "acta", "contrato"]
PERIODICIDAD = {"semanal": ("Semanal", 7), "catorcenal": ("Catorcenal", 14), "quincenal": ("Quincenal", 15), "mensual": ("Mensual", 30)}
CONTRATOS = {"indeterminado": "Por tiempo indeterminado", "determinado": "Por tiempo determinado", "prueba": "A prueba",
             "capacitacion": "Capacitación inicial", "obra": "Por obra determinada", "honorarios": "Honorarios (no es relación laboral)"}
MAX_ARCHIVO = 10 * 1024 * 1024
AUD_PORTAL = "nomira-rh-portal"


def d2(x) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ vacaciones (LFT art. 76)

def dias_por_anio(n: int) -> int:
    if n <= 0:
        return 0
    if n <= 5:
        return 10 + 2 * n
    return 20 + 2 * math.ceil((n - 5) / 5)


def aniversario(ingreso: date, anios: int) -> date:
    try:
        return ingreso.replace(year=ingreso.year + anios)
    except ValueError:  # 29 de febrero
        return ingreso.replace(year=ingreso.year + anios, day=28)


def anios_cumplidos(ingreso: date, hoy: date) -> int:
    n = hoy.year - ingreso.year - ((hoy.month, hoy.day) < (ingreso.month, ingreso.day))
    return max(n, 0)


def vacaciones(db: Session, e: m.RhEmpleado, hoy: date | None = None) -> dict:
    """Saldo del periodo vacacional en curso: días del último aniversario menos los ya aprobados desde entonces."""
    hoy = hoy or date.today()
    n = anios_cumplidos(e.fecha_ingreso, hoy)
    proximo = aniversario(e.fecha_ingreso, n + 1)
    if n == 0:
        return {"anios": 0, "derecho": 0, "tomados": 0, "pendientes_aprobar": 0, "disponibles": 0, "desde": None, "proximo_aniversario": proximo.isoformat(),
                "dias_proximo": dias_por_anio(1), "prima": "25 %"}
    inicio = aniversario(e.fecha_ingreso, n)
    filas = db.scalars(select(m.RhIncidencia).where(m.RhIncidencia.empleado_id == e.id, m.RhIncidencia.tipo == "vacaciones",
                                                    m.RhIncidencia.desde >= inicio, m.RhIncidencia.estado.in_(("aprobada", "pendiente")))).all()
    tomados = sum((f.dias for f in filas if f.estado == "aprobada"), Decimal(0))
    pendientes = sum((f.dias for f in filas if f.estado == "pendiente"), Decimal(0))
    derecho = dias_por_anio(n)
    return {"anios": n, "derecho": derecho, "tomados": float(tomados), "pendientes_aprobar": float(pendientes),
            "disponibles": float(Decimal(derecho) - tomados), "desde": inicio.isoformat(), "proximo_aniversario": proximo.isoformat(),
            "dias_proximo": dias_por_anio(n + 1), "prima": "25 %"}


def dias_laborables(desde: date, hasta: date) -> int:
    """Días de lunes a viernes entre dos fechas (RH puede ajustar el número si su semana es distinta)."""
    n, d = 0, desde
    while d <= hasta:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


# ------------------------------------------------------------------ nómina de control

def armar_recibo(db: Session, p: m.RhPeriodo, e: m.RhEmpleado) -> dict:
    """Propuesta inicial del recibo: sueldo por días pagados menos faltas y permisos sin goce; prima vacacional si hubo vacaciones."""
    emp = db.get(m.RhEmpresa, p.empresa_id)
    base_dias = Decimal(PERIODICIDAD.get(emp.periodicidad, ("", 15))[1])
    inc = db.scalars(select(m.RhIncidencia).where(m.RhIncidencia.empleado_id == e.id, m.RhIncidencia.estado == "aprobada",
                                                  m.RhIncidencia.desde <= p.fin, m.RhIncidencia.hasta >= p.inicio)).all()

    def dentro(i: m.RhIncidencia) -> Decimal:  # parte de la incidencia que cae en el periodo
        total = Decimal(max((i.hasta - i.desde).days + 1, 1))
        cruce = Decimal((min(i.hasta, p.fin) - max(i.desde, p.inicio)).days + 1)
        return (i.dias * cruce / total).quantize(Decimal("0.1"))

    faltas = sum((dentro(i) for i in inc if i.tipo in DESCUENTAN), Decimal(0))
    vac = sum((dentro(i) for i in inc if i.tipo == "vacaciones"), Decimal(0))
    incap = sum((dentro(i) for i in inc if i.tipo == "incapacidad"), Decimal(0))
    # ingreso o baja a mitad del periodo
    if e.fecha_ingreso > p.inicio:
        base_dias = max(Decimal((p.fin - e.fecha_ingreso).days + 1), Decimal(0))
    if e.fecha_baja and e.fecha_baja < p.fin:
        base_dias = max(base_dias - Decimal((p.fin - e.fecha_baja).days), Decimal(0))
    pagados = max(base_dias - faltas, Decimal(0))
    percepciones = [{"concepto": "Sueldo", "importe": str(d2(e.salario_diario * pagados))}]
    if vac:
        percepciones.append({"concepto": f"Prima vacacional 25 % ({vac} días)", "importe": str(d2(e.salario_diario * vac * Decimal("0.25")))})
    notas = []
    if incap:
        notas.append(f"{incap} días de incapacidad en el periodo: revise si el patrón los paga (el IMSS cubre el subsidio).")
    return {"dias_pagados": pagados, "faltas": faltas, "percepciones": percepciones, "deducciones": [], "notas": notas}


def neto(percepciones: list, deducciones: list) -> Decimal:
    return d2(sum((Decimal(str(x["importe"])) for x in percepciones), Decimal(0)) - sum((Decimal(str(x["importe"])) for x in deducciones), Decimal(0)))


def recibo_pdf(r: m.RhRecibo, e: m.RhEmpleado, emp: m.RhEmpresa, p: m.RhPeriodo) -> bytes:
    from html import escape as x

    import pymupdf

    def filas(items):
        return "".join(f"<tr><td>{x(i['concepto'])}</td><td class='n'>${Decimal(str(i['importe'])):,.2f}</td></tr>" for i in items) or "<tr><td>—</td><td></td></tr>"
    html = (f"<h1>Recibo de nómina</h1><p class='c'>{x(emp.nombre)}{' · RFC ' + x(emp.rfc) if emp.rfc else ''}"
            f"{' · Registro patronal ' + x(emp.registro_patronal) if emp.registro_patronal else ''}</p>"
            f"<p><b>{x(e.nombre)}</b>{' · ' + x(e.puesto) if e.puesto else ''}<br/>"
            f"{'RFC ' + x(e.rfc) + ' · ' if e.rfc else ''}{'CURP ' + x(e.curp) + ' · ' if e.curp else ''}{'NSS ' + x(e.nss) if e.nss else ''}</p>"
            f"<p>Periodo del {p.inicio:%d/%m/%Y} al {p.fin:%d/%m/%Y} · Pago: {p.fecha_pago:%d/%m/%Y} · Días pagados: {r.dias_pagados}"
            f"{' · Faltas: ' + str(r.faltas) if r.faltas else ''} · Salario diario: ${e.salario_diario:,.2f}</p>"
            f"<h2>Percepciones</h2><table>{filas(r.percepciones)}</table><h2>Deducciones</h2><table>{filas(r.deducciones)}</table>"
            f"<p class='neto'>Neto a pagar: ${r.neto:,.2f}</p>"
            "<p class='c'>Recibo de control interno generado con Nomira. No es un comprobante fiscal (CFDI de nómina).</p>"
            "<p style='margin-top:40px'>______________________________<br/>Firma de conformidad</p>")
    css = ("body{font-family:sans-serif;font-size:10pt} h1{font-size:15pt;margin:0 0 4px 0} h2{font-size:11pt;margin:12px 0 4px 0}"
           " table{width:100%;border-collapse:collapse} td{border-bottom:1px solid #ddd;padding:3px 0} .n{text-align:right}"
           " .c{color:#475569;font-size:8.5pt} .neto{font-size:13pt;font-weight:bold;margin-top:10px}")
    historia = pymupdf.Story(html=html, user_css=css)
    salida = io.BytesIO()
    w = pymupdf.DocumentWriter(salida)
    mas = True
    while mas:
        dev = w.begin_page(pymupdf.paper_rect("letter"))
        mas, _ = historia.place(pymupdf.paper_rect("letter") + (55, 55, -55, -55))
        historia.draw(dev)
        w.end_page()
    w.close()
    return salida.getvalue()


def excel_periodo(db: Session, p: m.RhPeriodo) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    recibos = db.scalars(select(m.RhRecibo).where(m.RhRecibo.periodo_id == p.id)).all()
    conceptos_p = sorted({c["concepto"] for r in recibos for c in r.percepciones})
    conceptos_d = sorted({c["concepto"] for r in recibos for c in r.deducciones})
    wb = Workbook()
    ws = wb.active
    ws.title = "Nómina"
    ws.append([f"Periodo {p.inicio:%d/%m/%Y} al {p.fin:%d/%m/%Y} · pago {p.fecha_pago:%d/%m/%Y} · control interno (no es CFDI)"])
    enc = ["Empleado", "RFC", "CURP", "NSS", "Puesto", "Salario diario", "Días pagados", "Faltas", *conceptos_p, "Total percepciones", *conceptos_d,
           "Total deducciones", "Neto"]
    ws.append(enc)
    for c in ws[2]:
        c.font = Font(bold=True)
    for r in sorted(recibos, key=lambda r: db.get(m.RhEmpleado, r.empleado_id).nombre):
        e = db.get(m.RhEmpleado, r.empleado_id)
        pv = {c["concepto"]: float(c["importe"]) for c in r.percepciones}
        dv = {c["concepto"]: float(c["importe"]) for c in r.deducciones}
        ws.append([e.nombre, e.rfc, e.curp, e.nss, e.puesto, float(e.salario_diario), float(r.dias_pagados), float(r.faltas),
                   *[pv.get(c, 0) for c in conceptos_p], sum(pv.values()), *[dv.get(c, 0) for c in conceptos_d], sum(dv.values()), float(r.neto)])
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


# ------------------------------------------------------------------ archivos

def guardar_archivo(org_id: int, empleado_id: int, nombre: str, contenido: bytes) -> tuple[str, str]:
    if len(contenido) > MAX_ARCHIVO:
        raise ValueError("El archivo pesa más de 10 MB.")
    if contenido.startswith(b"%PDF"):
        ext = ".pdf"
    elif contenido[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif contenido[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    else:
        raise ValueError("Suba un PDF o una foto (JPG o PNG).")
    rel = Path(str(org_id), "rh", str(empleado_id), f"{uuid.uuid4().hex}{ext}")
    destino = Path(ajustes().storage_dir, rel)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    limpio = re.sub(r"[^\w.\- ]+", "", Path(nombre or "documento").stem)[:80] or "documento"
    return str(rel), f"{limpio}{ext}"


def ruta(rel: str) -> Path:
    return Path(ajustes().storage_dir, rel)


MIME = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".png": "image/png"}


# ------------------------------------------------------------------ portal del empleado

def huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def nuevo_acceso(e: m.RhEmpleado) -> tuple[str, str]:
    """Genera enlace y NIP nuevos; invalida los anteriores y las sesiones abiertas."""
    token = secrets.token_urlsafe(24)
    nip = f"{secrets.randbelow(10**6):06d}"
    e.portal_token_hash, e.portal_nip_hash = huella(token), hash_contrasena(nip)
    e.portal_version = (e.portal_version or 0) + 1
    return token, nip


def enlace_portal(token: str) -> str:
    return f"{ajustes().url_publica.rstrip('/')}/mi-rh/{token}"


def token_sesion(e: m.RhEmpleado) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    return jwt.encode({"sub": str(e.id), "org": e.organizacion_id, "ver": e.portal_version, "aud": AUD_PORTAL, "exp": exp},
                      ajustes().jwt_secreto, algorithm="HS256")


def leer_sesion(token: str) -> dict | None:
    try:
        return jwt.decode(token, ajustes().jwt_secreto, algorithms=["HS256"], audience=AUD_PORTAL)
    except jwt.PyJWTError:
        return None


def empresa_propia(db: Session, org: m.Organizacion) -> m.RhEmpresa:
    e = db.scalar(select(m.RhEmpresa).where(m.RhEmpresa.organizacion_id == org.id, m.RhEmpresa.propia.is_(True)))
    if e is None:
        e = m.RhEmpresa(organizacion_id=org.id, nombre=org.nombre[:200], propia=True)
        db.add(e)
        db.flush()
    return e


def avisos_vigentes(db: Session, org_id: int, empresa_id: int, hoy: date | None = None) -> list[m.RhAviso]:
    hoy = hoy or date.today()
    q = select(m.RhAviso).where(m.RhAviso.organizacion_id == org_id, (m.RhAviso.empresa_id.is_(None)) | (m.RhAviso.empresa_id == empresa_id),
                                (m.RhAviso.vigente_hasta.is_(None)) | (m.RhAviso.vigente_hasta >= hoy))
    return list(db.scalars(q.order_by(m.RhAviso.fijado.desc(), m.RhAviso.creado_en.desc())).all())
