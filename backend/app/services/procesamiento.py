"""Procesamiento persistente e idempotente de documentos.

Cada documento tiene su propio estado y error. Reintentar borra SOLO lo derivado de ese
documento y lo vuelve a generar dentro de una transacción: nunca duplica recibos.
"""
from __future__ import annotations

import logging

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .. import models as m
from ..db import SessionLocal
from .extraccion import abrir_pdf, extraer_pagina
from .lector_recibos import clasificar_pagina, leer_recibo
from ..config import ajustes

log = logging.getLogger("quincena.procesamiento")


def recalcular_estado(db: Session, exp: m.Expediente) -> None:
    estados = list(db.scalars(select(m.Documento.estado).where(m.Documento.expediente_id == exp.id)))
    if not estados:
        nuevo = "nuevo"
    elif any(e in ("pendiente", "procesando") for e in estados):
        nuevo = "procesando"
    elif all(e == "error" for e in estados):
        nuevo = "error"
    elif exp.estado == "validado" and exp.resultado_validado is not None:
        nuevo = "validado"
    else:
        nuevo = "pendiente_revision"
    exp.estado = nuevo


def invalidar_validacion(exp: m.Expediente) -> bool:
    """Cualquier cambio posterior a la validación la revoca de forma explícita."""
    if exp.estado == "validado" or exp.resultado_validado is not None:
        exp.resultado_validado = None
        exp.validado_por_id = None
        exp.validado_en = None
        exp.estado = "pendiente_revision"
        return True
    return False


def procesar_documento(db: Session, documento_id: int) -> None:
    # Toma el documento de forma atómica: dos trabajadores no procesan el mismo a la vez.
    tomado = db.execute(
        update(m.Documento).where(m.Documento.id == documento_id, m.Documento.estado.in_(("pendiente", "error")))
        .values(estado="procesando", error=None, intentos=m.Documento.intentos + 1)).rowcount
    db.commit()
    if not tomado:
        return
    doc = db.get(m.Documento, documento_id)
    try:
        db.execute(delete(m.Recibo).where(m.Recibo.documento_id == doc.id))
        db.execute(delete(m.Pagina).where(m.Pagina.documento_id == doc.id))
        with abrir_pdf(doc.ruta) as pdf:
            if pdf.page_count > ajustes().max_paginas_pdf:
                raise ValueError(f"El PDF excede el máximo de {ajustes().max_paginas_pdf} páginas.")
            doc.num_paginas = pdf.page_count
            for n, pagina in enumerate(pdf, start=1):
                pe = extraer_pagina(pagina, n)
                tipo = clasificar_pagina(pe)
                db.add(m.Pagina(documento_id=doc.id, numero=n, tipo=tipo, metodo=pe.metodo, texto=pe.texto,
                                ancho=round(pe.ancho, 2), alto=round(pe.alto, 2), confianza_ocr=pe.confianza))
                leido = leer_recibo(pe) if tipo == "recibo" else None
                if not leido:
                    continue
                rec = m.Recibo(
                    organizacion_id=doc.organizacion_id, expediente_id=doc.expediente_id, documento_id=doc.id,
                    pagina_numero=n, num_recibo=leido.num_recibo, trabajador_nombre=leido.trabajador_nombre,
                    clave_servidor=leido.clave_servidor, plaza=leido.plaza, periodo_texto=leido.periodo_texto,
                    periodo_inicio=leido.periodo_inicio, periodo_fin=leido.periodo_fin,
                    total_percepciones=leido.total_percepciones, total_deducciones=leido.total_deducciones,
                    total_neto=leido.total_neto, confianza=leido.confianza)
                for f in leido.filas:
                    rec.filas.append(m.Fila(
                        tipo=f.tipo, orden=f.orden, clave_leida=f.clave, concepto_leido=f.concepto,
                        importe_leido_texto=f.importe_texto, clave=f.clave, concepto=f.concepto,
                        importe=f.importe, confianza=f.confianza, bbox=f.bbox))
                db.add(rec)
        doc.estado = "procesado"
        doc.procesado_en = m.ahora()
        db.commit()
    except Exception as e:  # el error queda en el documento; no tumba al resto
        db.rollback()
        doc = db.get(m.Documento, documento_id)
        doc.estado = "error"
        doc.error = f"{type(e).__name__}: {str(e)[:400]}"
        db.commit()
        log.warning("Documento %s falló: %s", documento_id, type(e).__name__)  # sin contenido del PDF
    exp = db.get(m.Expediente, doc.expediente_id)
    recalcular_estado(db, exp)
    db.commit()


def procesar_en_segundo_plano(documento_id: int) -> None:
    with SessionLocal() as db:
        procesar_documento(db, documento_id)


def recuperar_interrumpidos() -> int:
    """Al arrancar: lo que quedó «procesando» por un reinicio pasa a error reintentable."""
    with SessionLocal() as db:
        n = db.execute(update(m.Documento).where(m.Documento.estado == "procesando").values(
            estado="error", error="Procesamiento interrumpido por reinicio del servicio. Reintente.")).rowcount
        if n:
            for exp in db.scalars(select(m.Expediente).where(m.Expediente.estado == "procesando")):
                recalcular_estado(db, exp)
        for exp in db.scalars(select(m.Expediente).where(m.Expediente.verificacion_ia.isnot(None))):
            if (exp.verificacion_ia or {}).get("estado") == "en_curso":
                exp.verificacion_ia = {**exp.verificacion_ia, "estado": "error",
                                       "error": "Verificación interrumpida por reinicio del servicio. Vuelva a lanzarla."}
        db.commit()
        return n
