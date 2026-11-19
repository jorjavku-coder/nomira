"""Asunto de demostración de Nomira Evidencia con documentos 100 % ficticios (reproducibles byte a
byte, para poder regenerarlos si el disco del servicio de demostración se borra)."""
from __future__ import annotations

import hashlib
import io
import os
from datetime import date
from pathlib import Path

import pymupdf
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ...config import ajustes
from .. import modulos
from .procesamiento import procesar

_T = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=13, leading=17, spaceAfter=10)
_N = ParagraphStyle("n", fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=8)


def _pdf(titulo: str, parrafos: list[str]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=2.5 * cm, rightMargin=2.5 * cm, topMargin=2.5 * cm,
                            bottomMargin=2.5 * cm, invariant=1, title=titulo)
    doc.build([Paragraph(titulo, _T), Spacer(1, 4)] + [Paragraph(p, _N) for p in parrafos]
              + [Spacer(1, 18), Paragraph("DOCUMENTO FICTICIO DE DEMOSTRACIÓN — SIN VALOR", _N)])
    return buf.getvalue()


def _imagen(pdf: bytes) -> bytes:
    """Una «fotografía» del documento (PNG sin capa de texto): obliga a leerlo con OCR."""
    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        return d[0].get_pixmap(dpi=150, colorspace=pymupdf.csGRAY).tobytes("png")


def documentos() -> dict[str, bytes]:
    contrato = _pdf("CONTRATO INDIVIDUAL DE TRABAJO POR TIEMPO INDETERMINADO", [
        "En la Ciudad de México, el 15 de enero de 2020, celebran el presente contrato por una parte EMPRESA "
        "FICTICIA DEMO, S.A. de C.V., representada por el Lic. Roberto Ejemplo Pérez, y por la otra el C. Juan Demo "
        "Ficticio, a quien se denominará el trabajador.",
        "PRIMERA. La relación de trabajo inicia el 15 de enero de 2020 y será por tiempo indeterminado.",
        "SEGUNDA. El trabajador desempeñará el puesto de analista administrativo en el domicilio de la empresa.",
        "TERCERA. El salario mensual será de $18,500.00 M.N., pagadero por quincenas vencidas.",
        "CUARTA. La jornada será de lunes a viernes, de 9:00 a 18:00 horas, con una hora para tomar alimentos.",
    ])
    aviso = _pdf("AVISO DE TERMINACIÓN DE LA RELACIÓN DE TRABAJO", [
        "Ciudad de México, a 30 de junio de 2025.",
        "C. Juan Demo Ficticio. Presente.",
        "Por medio del presente se le comunica que la empresa da por terminada la relación de trabajo con efectos "
        "a partir del 30 de junio de 2025.",
        "Atentamente, Lic. Roberto Ejemplo Pérez, representante legal.",
    ])
    correo = _imagen(_pdf("Correo electrónico", [
        "De: recursos.humanos@empresa-ficticia.test",
        "Para: juan.demo@correo-ficticio.test",
        "Fecha: 02/07/2025",
        "Asunto: Constancia de periodo laborado",
        "Estimado Juan: le confirmamos que la relación de trabajo inició el 1 de febrero de 2020 y que su último "
        "día laborado fue el 30 de junio de 2025.",
        "Saludos cordiales, Departamento de Recursos Humanos.",
    ]))
    finiquito = _pdf("RECIBO DE FINIQUITO", [
        "Recibí de EMPRESA FICTICIA DEMO, S.A. de C.V. la cantidad de $42,300.00 M.N. por concepto de finiquito, "
        "el 5 de julio de 2025.",
        "El pago comprende partes proporcionales de aguinaldo, vacaciones y prima vacacional.",
        "Firma: C. Juan Demo Ficticio.",
    ])
    return {"contrato_individual_ficticio.pdf": contrato, "aviso_de_terminacion_ficticio.pdf": aviso,
            "correo_recursos_humanos_ficticio.png": correo, "recibo_de_finiquito_ficticio.pdf": finiquito}


def documentos_divorcio() -> dict[str, bytes]:
    """Asunto familiar ficticio («divorcio de Laura»). Sirve para comprobar que Nomira distingue la
    fecha de un documento de la fecha del evento que describe, y que solo compara el mismo dato."""
    entrevista = _pdf("ENTREVISTA INICIAL CON LA CLIENTE", [
        "Fecha de la entrevista: 3 de febrero de 2026.",
        "Cliente: Laura Ficticia Ramírez.",
        "La cliente refiere que contrajo matrimonio con el señor Mario Demo Torres el 14 de mayo de 2015.",
        "Indica que la separación de hecho ocurrió el 10 de enero de 2026, cuando el señor Mario Demo Torres "
        "salió del domicilio conyugal.",
        "Señala que tienen dos hijos menores de edad que viven con ella.",
        "Refiere que él aportaba $8,000.00 M.N. mensuales para los gastos del hogar.",
    ])
    convenio = _pdf("BORRADOR DE CONVENIO DE DIVORCIO", [
        "Toluca, Estado de México, a 12 de febrero de 2026. Estado del documento: borrador para revisión.",
        "Nota editorial: la fecha de este borrador (12 de febrero de 2026) es la fecha en que se elaboró; "
        "la fecha del documento no equivale a la fecha de los hechos que describe.",
        "PRIMERA. Las partes manifiestan que viven separadas desde el 12 de enero de 2026.",
        "SEGUNDA. El señor Mario Demo Torres aportará una pensión alimenticia de $9,500.00 M.N. mensuales.",
        "TERCERA. La guarda y custodia de los hijos menores quedará a cargo de la señora Laura Ficticia Ramírez.",
    ])
    conversacion = _imagen(_pdf("Conversación simulada (mensajes)", [
        "Fecha de la conversación: 20/01/2026.",
        "Laura: Mario, desde que nos separamos el 12 de enero de 2026 no me has dado dinero para los niños.",
        "Mario: Te deposito la próxima semana.",
    ]))
    return {"entrevista_inicial_ficticia.pdf": entrevista, "borrador_convenio_ficticio.pdf": convenio,
            "conversacion_simulada_ficticia.png": conversacion}


def _guardar(db: Session, a: m.EvAsunto, nombre: str, datos: bytes, usuario_id: int) -> m.EvDocumento:
    from .lectura import detectar_formato

    formato = detectar_formato(datos)
    sha = hashlib.sha256(datos).hexdigest()
    carpeta = Path(ajustes().storage_dir) / str(a.organizacion_id) / "evidencia" / str(a.id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{sha}.{'jpg' if formato == 'jpeg' else formato}"
    ruta.write_bytes(datos)
    d = m.EvDocumento(organizacion_id=a.organizacion_id, asunto_id=a.id, nombre_original=nombre, sha256=sha,
                      tamano_bytes=len(datos), formato=formato, ruta=str(ruta), subido_por_id=usuario_id)
    db.add(d)
    db.commit()
    procesar(db, d.id)
    db.refresh(d)
    return d


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    """Activa Evidencia en la organización de demostración y crea un asunto de ejemplo. Solo lo hace
    una vez: si el módulo ya tiene un registro para esa organización (aunque esté desactivado), no toca nada."""
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin:
        return False
    oid = admin.organizacion_id
    if db.scalar(select(m.OrganizacionModulo.id).where(m.OrganizacionModulo.organizacion_id == oid,
                                                       m.OrganizacionModulo.modulo == "evidencia")):
        return False
    modulos.fijar(db, oid, "evidencia", contratado=True, activo=True)
    a = m.EvAsunto(organizacion_id=oid, nombre="Juan Demo Ficticio vs. Empresa Ficticia Demo", cliente="Juan Demo Ficticio",
                   tipo_caso="Laboral", jurisdiccion="Ciudad de México", identificador_interno="DEMO-001",
                   responsable_id=admin.id, notas="Asunto de demostración con documentos ficticios.", creado_por_id=admin.id,
                   campos={"Contraparte": "Empresa Ficticia Demo, S.A. de C.V."})
    db.add(a)
    db.commit()
    docs = {nombre: _guardar(db, a, nombre, datos, admin.id) for nombre, datos in documentos().items()}
    tipos = {"contrato_individual_ficticio.pdf": ("Contrato", date(2020, 1, 15)),
             "aviso_de_terminacion_ficticio.pdf": ("Aviso de terminación", date(2025, 6, 30)),
             "correo_recursos_humanos_ficticio.png": ("Correo o mensaje", date(2025, 7, 2))}
    for nombre, (tipo, fecha) in tipos.items():  # el recibo de finiquito queda sin clasificar a propósito
        docs[nombre].tipo, docs[nombre].fecha_documento, docs[nombre].clasificado_por_id = tipo, fecha, admin.id
    hechos = db.scalars(select(m.EvHecho).where(m.EvHecho.asunto_id == a.id)).all()

    def confirmar(doc: str, contiene: str) -> m.EvHecho | None:
        for h in hechos:
            if h.documento_id == docs[doc].id and contiene.lower() in h.descripcion.lower():
                h.estado, h.revisado_por_id, h.revisado_en = "confirmado", admin.id, m.ahora()
                return h
        return None

    inicio_contrato = confirmar("contrato_individual_ficticio.pdf", "relación de trabajo inicia")
    salario = confirmar("contrato_individual_ficticio.pdf", "salario mensual")
    terminacion = confirmar("aviso_de_terminacion_ficticio.pdf", "da por terminada")
    inicio_correo = confirmar("correo_recursos_humanos_ficticio.png", "inició")
    p1 = m.EvPunto(organizacion_id=oid, asunto_id=a.id, descripcion="Fecha de inicio de la relación de trabajo", orden=1,
                   creado_por_id=admin.id)
    p2 = m.EvPunto(organizacion_id=oid, asunto_id=a.id, descripcion="Salario mensual pactado", orden=2, creado_por_id=admin.id,
                   estado="respaldado", estado_decidido_por_id=admin.id, estado_decidido_en=m.ahora())
    p3 = m.EvPunto(organizacion_id=oid, asunto_id=a.id, descripcion="Pago de la prima vacacional de 2024", orden=3,
                   creado_por_id=admin.id)
    p4 = m.EvPunto(organizacion_id=oid, asunto_id=a.id, descripcion="Fecha de terminación de la relación de trabajo", orden=4,
                   creado_por_id=admin.id)
    db.add_all([p1, p2, p3, p4])
    db.flush()
    for p, h in ((p1, inicio_contrato), (p1, inicio_correo), (p2, salario), (p4, terminacion)):
        if h:
            db.add(m.EvVinculo(punto_id=p.id, hecho_id=h.id, documento_id=h.documento_id, pagina=h.pagina, creado_por_id=admin.id))
    db.add_all([
        m.EvPendiente(organizacion_id=oid, asunto_id=a.id, descripcion="Recibos de nómina de 2024 (todas las quincenas)",
                      responsable="Cliente", fecha_seguimiento=date(2026, 12, 4), estado="solicitado", creado_por_id=admin.id,
                      nota="Pedirlos también en formato XML."),
        m.EvPendiente(organizacion_id=oid, asunto_id=a.id, descripcion="Constancia de semanas cotizadas",
                      responsable="Cliente", fecha_seguimiento=date(2026, 12, 11), estado="pendiente", creado_por_id=admin.id),
        m.EvPendiente(organizacion_id=oid, asunto_id=a.id, descripcion="Comprobante de pago de la prima vacacional de 2024",
                      responsable="Admin Demo", estado="pendiente", creado_por_id=admin.id),
    ])
    db.commit()
    return True


def sembrar_divorcio(db: Session, email: str = "admin@demo.local") -> bool:
    """Segundo asunto de demostración (familiar). Se crea una sola vez y solo si la organización de
    demostración tiene Evidencia activo. Los hechos quedan por revisar: son para practicar la validación."""
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin or "evidencia" not in modulos.activos(db, admin.organizacion_id):
        return False
    oid = admin.organizacion_id
    if db.scalar(select(m.EvAsunto.id).where(m.EvAsunto.organizacion_id == oid, m.EvAsunto.identificador_interno == "DEMO-002")):
        return False
    a = m.EvAsunto(organizacion_id=oid, nombre="Divorcio de Laura Ficticia Ramírez", cliente="Laura Ficticia Ramírez",
                   tipo_caso="Familiar", jurisdiccion="Toluca, Estado de México", identificador_interno="DEMO-002",
                   responsable_id=admin.id, notas="Asunto de demostración con documentos ficticios.", creado_por_id=admin.id,
                   campos={"Contraparte": "Mario Demo Torres"})
    db.add(a)
    db.commit()
    for nombre, datos in documentos_divorcio().items():
        _guardar(db, a, nombre, datos, admin.id)
    db.add_all([
        m.EvPendiente(organizacion_id=oid, asunto_id=a.id, descripcion="Acta de matrimonio", responsable="Cliente",
                      estado="pendiente", creado_por_id=admin.id),
        m.EvPendiente(organizacion_id=oid, asunto_id=a.id, descripcion="Actas de nacimiento de los hijos",
                      responsable="Cliente", estado="pendiente", creado_por_id=admin.id),
    ])
    db.commit()
    return True


def restaurar_archivos(db: Session) -> dict:
    """Tras un reinicio con disco temporal: regenera los documentos ficticios por su huella; los
    demás quedan en error para que se vuelvan a cargar (nada se inventa)."""
    demo = {hashlib.sha256(d).hexdigest(): d for d in [*documentos().values(), *documentos_divorcio().values()]}
    restaurados = perdidos = 0
    for d in db.scalars(select(m.EvDocumento)):
        if Path(d.ruta).exists():
            continue
        if d.sha256 in demo:
            Path(d.ruta).parent.mkdir(parents=True, exist_ok=True)
            Path(d.ruta).write_bytes(demo[d.sha256])
            restaurados += 1
        elif d.estado != "error":
            d.estado, d.error = "error", "El archivo original ya no está disponible en el servicio de demostración. Vuelva a cargarlo."
            perdidos += 1
    db.commit()
    return {"restaurados": restaurados, "perdidos": perdidos}
