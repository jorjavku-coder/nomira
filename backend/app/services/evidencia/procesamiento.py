"""Procesamiento persistente e idempotente de documentos de Evidencia (mismo patrón que Nómina).

Reprocesar sustituye solo lo automático y aún sin revisar: los hechos que una persona ya confirmó,
editó o descartó se conservan."""
from __future__ import annotations

import logging

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from ... import models as m
from ...db import SessionLocal
from .lectura import leer

log = logging.getLogger("nomira.evidencia")


def procesar(db: Session, documento_id: int) -> None:
    tomado = db.execute(
        update(m.EvDocumento).where(m.EvDocumento.id == documento_id,
                                    m.EvDocumento.estado.in_(("pendiente", "error", "requiere_revision", "leido")))
        .values(estado="procesando", error=None, intentos=m.EvDocumento.intentos + 1)).rowcount
    db.commit()
    if not tomado:
        return
    doc = db.get(m.EvDocumento, documento_id)
    try:
        lectura = leer(doc.ruta, doc.formato)
        db.execute(delete(m.EvPagina).where(m.EvPagina.documento_id == doc.id))
        db.execute(delete(m.EvHecho).where(m.EvHecho.documento_id == doc.id, m.EvHecho.origen == "automatico",
                                           m.EvHecho.estado == "por_revisar"))
        for pe in lectura.paginas:
            db.add(m.EvPagina(documento_id=doc.id, numero=pe.numero, metodo=pe.metodo, texto=pe.texto,
                              confianza_ocr=pe.confianza, ancho=round(pe.ancho, 2), alto=round(pe.alto, 2)))
        for h in lectura.hechos:
            propuesta = {"descripcion": h.descripcion, "fecha": h.fecha.isoformat() if h.fecha else None,
                         "importe": str(h.importe) if h.importe is not None else None, "personas": h.personas}
            db.add(m.EvHecho(
                organizacion_id=doc.organizacion_id, asunto_id=doc.asunto_id, descripcion=h.descripcion,
                fecha=h.fecha, fecha_texto=h.fecha_texto, personas=h.personas or None, importe=h.importe,
                dato=h.dato, documento_id=doc.id, pagina=h.pagina, fragmento=h.fragmento, bbox=h.bbox,
                confianza=h.confianza, origen="automatico", estado="por_revisar", original=propuesta))
        doc.num_paginas = len(lectura.paginas)
        doc.tipo_sugerido = lectura.tipo_sugerido
        doc.fecha_sugerida = lectura.fecha_sugerida
        if lectura.paginas_dudosas:
            doc.estado = "requiere_revision"
            doc.error = ("No se pudo leer con suficiente confianza: página(s) "
                         + ", ".join(map(str, lectura.paginas_dudosas[:20])) + ". Revise el original.")
        else:
            doc.estado = "leido"
        doc.leido_en = m.ahora()
        db.commit()
    except Exception as e:
        db.rollback()
        doc = db.get(m.EvDocumento, documento_id)
        doc.estado = "error"
        doc.error = f"No se pudo leer el archivo ({type(e).__name__}). Puede seguir organizando el asunto manualmente."
        db.commit()
        log.warning("Documento de evidencia %s falló: %s", documento_id, type(e).__name__)  # sin contenido


def procesar_en_segundo_plano(documento_id: int) -> None:
    with SessionLocal() as db:
        procesar(db, documento_id)


def recuperar_interrumpidos() -> int:
    with SessionLocal() as db:
        n = db.execute(update(m.EvDocumento).where(m.EvDocumento.estado == "procesando").values(
            estado="error", error="Lectura interrumpida por reinicio del servicio. Use «Volver a leer».")).rowcount
        db.commit()
        return n
