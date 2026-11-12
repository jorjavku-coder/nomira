"""Puente entre la base de datos y el motor de cálculo."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..config import ajustes
from .calculo import FilaCalc, ParametrosExpediente, ReciboCalc, calcular


def _ctx(db: Session, exp: m.Expediente) -> dict:
    v = exp.catalogo_version
    return {
        "expediente": {
            "id": exp.id, "trabajador_nombre": exp.trabajador_nombre,
            "identificador_laboral": exp.identificador_laboral,
            "periodo_inicio": exp.periodo_inicio.isoformat(), "periodo_fin": exp.periodo_fin.isoformat(),
            "quincenas_esperadas": exp.quincenas_esperadas, "decision_plazas": exp.decision_plazas,
        },
        "catalogo": {"id": v.catalogo_id, "nombre": v.catalogo.nombre, "version_id": v.id,
                     "version": v.numero, "estado": v.estado,
                     "claves_activas": sum(1 for e in v.entradas if e.activo)},
    }


def calcular_expediente(db: Session, exp: m.Expediente) -> dict:
    """Resultado vigente. Si el expediente está validado devuelve la instantánea congelada."""
    if exp.estado == "validado" and exp.resultado_validado:
        return exp.resultado_validado
    recibos = db.scalars(select(m.Recibo).where(m.Recibo.expediente_id == exp.id)
                         .options(selectinload(m.Recibo.filas), selectinload(m.Recibo.documento))).all()
    rc = [ReciboCalc(
        id=r.id, documento_id=r.documento_id, documento_nombre=r.documento.nombre_original,
        pagina=r.pagina_numero, num_recibo=r.num_recibo, trabajador_nombre=r.trabajador_nombre,
        clave_servidor=r.clave_servidor, plaza=r.plaza, periodo_inicio=r.periodo_inicio,
        periodo_fin=r.periodo_fin, total_percepciones=r.total_percepciones,
        total_deducciones=r.total_deducciones, decision=r.decision,
        filas=[FilaCalc(f.id, f.tipo, f.orden, f.clave, f.concepto, f.importe, f.confianza,
                        f.corregida, f.confirmada) for f in r.filas]) for r in recibos]
    catalogo = {e.clave: (e.descripcion, e.activo) for e in exp.catalogo_version.entradas}
    params = ParametrosExpediente(
        exp.trabajador_nombre, exp.identificador_laboral, exp.periodo_inicio, exp.periodo_fin,
        exp.quincenas_esperadas, exp.decision_plazas, ajustes().clave_regex, ajustes().ocr_confianza_minima)
    res = calcular(params, rc, catalogo)

    # Periodo que cubren los recibos de este trabajador (para proponer ampliar el expediente).
    from .calculo import mismo_trabajador
    from .prelectura import rango_quincenal
    rango = rango_quincenal([(r.periodo_inicio, r.periodo_fin) for r in rc
                             if r.decision != "excluir" and mismo_trabajador(params, r)])
    res["periodo_detectado"] = {"inicio": rango[0].isoformat(), "fin": rango[1].isoformat()} if rango else None

    def bloquea(tipo, mensaje, **ref):
        res["alertas"].append({"tipo": tipo, "mensaje": mensaje, "bloqueante": True, **ref})

    for d in exp.documentos:
        if d.estado == "error":
            bloquea("documento_error", f"El documento «{d.nombre_original}» no pudo procesarse. "
                    "Reinténtelo o elimínelo.", documento_id=d.id)
        elif d.estado in ("pendiente", "procesando"):
            bloquea("documento_en_proceso", f"El documento «{d.nombre_original}» sigue en proceso.",
                    documento_id=d.id)
    sin_clasificar = db.execute(
        select(m.Pagina.numero, m.Documento.id, m.Documento.nombre_original)
        .join(m.Documento, m.Pagina.documento_id == m.Documento.id)
        .where(m.Documento.expediente_id == exp.id, m.Pagina.tipo == "desconocida")).all()
    for num, doc_id, nombre in sin_clasificar:
        bloquea("pagina_sin_clasificar", f"La página {num} de «{nombre}» no pudo clasificarse como recibo "
                "ni como informativa. Revísela.", documento_id=doc_id, pagina=num)
    if exp.catalogo_version.estado == "borrador":
        bloquea("catalogo_no_validado", "El catálogo seleccionado no ha sido validado.")
    if not exp.documentos:
        bloquea("sin_documentos", "El expediente no tiene comprobantes cargados.")
    res["resumen"]["alertas_bloqueantes"] = sum(1 for a in res["alertas"] if a["bloqueante"])
    res["provisional"] = True  # solo deja de serlo al validarse
    res["puede_validarse"] = res["resumen"]["alertas_bloqueantes"] == 0
    res["estado_validacion"] = {"validado": False, "por": None, "fecha": None, "notas": None}
    res.update(_ctx(db, exp))
    return res


def trazabilidad(db: Session, exp: m.Expediente) -> dict:
    cors = db.scalars(select(m.Correccion).where(m.Correccion.expediente_id == exp.id)
                      .order_by(m.Correccion.fecha)).all()
    return {
        "documentos": [{"id": d.id, "nombre": d.nombre_original, "sha256": d.sha256, "paginas": d.num_paginas,
                        "estado": d.estado, "cargado": d.creado_en.isoformat()} for d in exp.documentos],
        "correcciones": [{"id": c.id, "fecha": c.fecha.isoformat(), "usuario": c.usuario_email,
                          "entidad": c.entidad, "campo": c.campo, "valor_anterior": c.valor_anterior,
                          "valor_nuevo": c.valor_nuevo, "motivo": c.motivo, "referencia": c.referencia,
                          "fila_id": c.fila_id, "recibo_id": c.recibo_id} for c in cors],
    }


def resultado_completo(db: Session, exp: m.Expediente) -> dict:
    res = calcular_expediente(db, exp)
    if "trazabilidad" not in res:
        res = {**res, "trazabilidad": trazabilidad(db, exp)}
    return res
