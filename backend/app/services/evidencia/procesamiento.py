"""Procesamiento persistente e idempotente de documentos de Evidencia (mismo patrón que Nómina).

Reprocesar sustituye solo lo automático y aún sin revisar: los hechos que una persona ya confirmó,
editó o descartó se conservan."""
from __future__ import annotations

import logging

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ... import models as m
from ...db import SessionLocal
from .lectura import leer

log = logging.getLogger("nomira.evidencia")


def procesar(db: Session, documento_id: int) -> None:
    tomado = db.execute(
        update(m.EvDocumento).where(m.EvDocumento.id == documento_id,
                                    # «recibido» (enviado por un cliente) no se lee hasta que una persona lo acepta
                                    m.EvDocumento.estado.in_(("pendiente", "error", "requiere_revision", "leido")))
        .values(estado="procesando", error=None, intentos=m.EvDocumento.intentos + 1)).rowcount
    db.commit()
    if not tomado:
        return
    doc = db.get(m.EvDocumento, documento_id)
    try:
        lectura = leer(doc.ruta, doc.formato)
        anteriores = db.scalars(select(m.EvHecho).where(m.EvHecho.documento_id == doc.id, m.EvHecho.origen == "automatico")).all()
        # Lo que ya revisó una persona (validado, editado o descartado) se conserva y NO se vuelve a proponer.
        revisados = [h for h in anteriores if h.estado != "por_revisar"]
        propuestas_previas = {_clave(h) for h in anteriores if h.estado == "por_revisar"}
        db.execute(delete(m.EvPagina).where(m.EvPagina.documento_id == doc.id))
        db.execute(delete(m.EvHecho).where(m.EvHecho.documento_id == doc.id, m.EvHecho.origen == "automatico",
                                           m.EvHecho.estado == "por_revisar"))
        for pe in lectura.paginas:
            db.add(m.EvPagina(documento_id=doc.id, numero=pe.numero, metodo=pe.metodo, texto=pe.texto,
                              confianza_ocr=pe.confianza, ancho=round(pe.ancho, 2), alto=round(pe.alto, 2)))
        nuevas = omitidas = 0
        for h in lectura.hechos:
            clave = _clave(h)
            if any(_equivalente(h, r) for r in revisados):
                omitidas += 1  # equivalente a algo que una persona ya revisó
                continue
            nuevas += clave not in propuestas_previas
            propuesta = {"descripcion": h.descripcion, "tipo_dato": h.tipo_dato, "valor_original": h.valor_original,
                         "fecha": h.fecha.isoformat() if h.fecha else None,
                         "importe": str(h.importe) if h.importe is not None else None, "personas": h.personas,
                         "atribucion": h.atribucion, "motivo_calidad": h.motivo_calidad}
            db.add(m.EvHecho(
                organizacion_id=doc.organizacion_id, asunto_id=doc.asunto_id, descripcion=h.descripcion,
                fecha=h.fecha, fecha_texto=h.fecha_texto, personas=h.personas or None, importe=h.importe,
                dato=h.dato, tipo_dato=h.tipo_dato, tema=h.tema, valor_original=h.valor_original, valor=h.valor,
                atribucion=h.atribucion, calidad=h.calidad,
                documento_id=doc.id, pagina=h.pagina, fragmento=h.fragmento, bbox=h.bbox,
                confianza=h.confianza, origen="automatico", estado="por_revisar", original=propuesta))
        doc.resumen_lectura = {"fecha": m.ahora().isoformat(), "relectura": bool(anteriores), "propuestas": len(lectura.hechos) - omitidas,
                               "nuevas": nuevas if anteriores else len(lectura.hechos) - omitidas, "ya_revisadas": omitidas,
                               "conservadas": sum(1 for h in anteriores if h.estado != "por_revisar")}
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


def _clave(h, pagina: int | None = None) -> tuple:
    """Dos propuestas son equivalentes si dicen el mismo dato, en la misma página, con el mismo texto."""
    g = (lambda k: h.get(k)) if isinstance(h, dict) else (lambda k: getattr(h, k, None))
    fecha, importe = g("fecha"), g("importe")
    return (g("tipo_dato") or "otro", pagina if pagina is not None else g("pagina"), str(fecha) if fecha else None,
            str(importe) if importe is not None else None, " ".join((g("descripcion") or "").lower().split())[:200])


def _equivalente(nueva, previa: m.EvHecho) -> bool:
    """¿La propuesta nueva dice lo mismo que un hecho que una persona ya revisó? Se compara con lo que
    Nomira había propuesto originalmente (si la persona lo editó) y con el texto de origen."""
    if nueva.pagina != previa.pagina:
        return False
    orig = previa.original or {}
    for fecha, importe, desc in ((previa.fecha, previa.importe, previa.descripcion),
                                 (orig.get("fecha"), orig.get("importe"), orig.get("descripcion"))):
        if (str(nueva.fecha) if nueva.fecha else None) != (str(fecha) if fecha else None):
            continue
        if (str(nueva.importe) if nueva.importe is not None else None) != (str(importe) if importe is not None else None):
            continue
        norm = lambda t: " ".join((t or "").lower().split())  # noqa: E731
        if norm(nueva.descripcion) == norm(desc) or norm(nueva.fragmento) == norm(previa.fragmento) \
                or (norm(nueva.descripcion) and norm(nueva.descripcion) in norm(previa.fragmento)):
            return True
    return False


def procesar_en_segundo_plano(documento_id: int) -> None:
    with SessionLocal() as db:
        procesar(db, documento_id)


def recuperar_interrumpidos() -> int:
    with SessionLocal() as db:
        n = db.execute(update(m.EvDocumento).where(m.EvDocumento.estado == "procesando").values(
            estado="error", error="Lectura interrumpida por reinicio del servicio. Use «Volver a leer».")).rowcount
        db.commit()
        return n
