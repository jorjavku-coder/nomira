"""Puente entre la base de datos y el motor de cálculo."""
from __future__ import annotations

from collections import defaultdict

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


def _congelado(exp: m.Expediente) -> bool:
    return exp.estado == "validado" and bool(exp.resultado_validado)


def _consulta_recibos():
    return select(m.Recibo).options(selectinload(m.Recibo.filas), selectinload(m.Recibo.documento))


def _consulta_sin_clasificar():
    return (select(m.Pagina.numero, m.Documento.id, m.Documento.nombre_original, m.Documento.expediente_id)
            .join(m.Documento, m.Pagina.documento_id == m.Documento.id).where(m.Pagina.tipo == "desconocida"))


def calcular_expediente(db: Session, exp: m.Expediente, recibos: list[m.Recibo] | None = None,
                        sin_clasificar: list[tuple] | None = None) -> dict:
    """Resultado vigente. Si el expediente está validado devuelve la instantánea congelada.
    `recibos` y `sin_clasificar` pueden llegar precargados (vea calcular_varios)."""
    if _congelado(exp):
        return exp.resultado_validado
    if recibos is None:
        recibos = db.scalars(_consulta_recibos().where(m.Recibo.expediente_id == exp.id)).all()
    if sin_clasificar is None:
        sin_clasificar = db.execute(_consulta_sin_clasificar().where(m.Documento.expediente_id == exp.id)).all()
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

    # Verificación opcional con IA: solo agrega avisos; no cambia ningún importe.
    from .verificacion_ia import resumen as resumen_ia
    res["ia"], ia_por_recibo, alertas_ia = resumen_ia(recibos, exp)
    q_de = {int(k): v["quincena"] for k, v in res["recibos"].items()}
    for k, v in res["recibos"].items():
        v["ia"] = ia_por_recibo.get(int(k))
    for a in alertas_ia:
        if res["recibos"][str(a["recibo_id"])]["estado"] == "incluido":
            res["alertas"].append({**a, "quincena": q_de.get(a["recibo_id"])})
    for q in res["quincenas"]:
        estados = [ia_por_recibo[r]["estado"] for r in q["recibos"] if r in ia_por_recibo]
        q["ia"] = ("discrepancia" if any(e in ("discrepancia", "no_legible") for e in estados)
                   else "coincide" if estados and all(e == "coincide" for e in estados) else None)
        if q["ia"] == "discrepancia" and any(a.get("quincena") == q["quincena"] for a in res["alertas"] if a["tipo"] == "verificacion_ia"):
            q["provisional"] = True

    def bloquea(tipo, mensaje, **ref):
        res["alertas"].append({"tipo": tipo, "mensaje": mensaje, "bloqueante": True, **ref})

    for d in exp.documentos:
        if d.estado == "error":
            bloquea("documento_error", f"El documento «{d.nombre_original}» no pudo procesarse. "
                    "Reinténtelo o elimínelo.", documento_id=d.id)
        elif d.estado in ("pendiente", "procesando"):
            bloquea("documento_en_proceso", f"El documento «{d.nombre_original}» sigue en proceso.",
                    documento_id=d.id)
    for num, doc_id, nombre, _ in sin_clasificar:
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


def calcular_varios(db: Session, exps: list[m.Expediente]) -> dict[int, dict]:
    """Igual que calcular_expediente para varios expedientes, con un número fijo de consultas.
    Conviene precargar en `exps` documentos y catálogo (vea routers/expedientes.py)."""
    ids = [e.id for e in exps if not _congelado(e)]
    recibos: dict[int, list] = defaultdict(list)
    sin_clasificar: dict[int, list] = defaultdict(list)
    if ids:
        for r in db.scalars(_consulta_recibos().where(m.Recibo.expediente_id.in_(ids))):
            recibos[r.expediente_id].append(r)
        for fila in db.execute(_consulta_sin_clasificar().where(m.Documento.expediente_id.in_(ids))):
            sin_clasificar[fila[3]].append(fila)
    return {e.id: calcular_expediente(db, e, recibos[e.id], sin_clasificar[e.id]) for e in exps}


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
