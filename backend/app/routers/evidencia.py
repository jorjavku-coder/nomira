"""API de Nomira Evidencia. Todas las rutas exigen el módulo activo para la organización (vea main.py)
y toda lectura o escritura se filtra por la organización del usuario."""
from __future__ import annotations

import hashlib
import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, obtener, puede_editar, solo_admin, usuario_actual
from ..services.evidencia import analisis, jurisdiccion, reporte
from ..services import correo, envios, plantillas_correo
from ..services.evidencia import solicitudes as sol
from ..services.evidencia.lectura import (ETIQUETA_TEMA, TIPOS_DATO, TIPOS_DISPONIBLES, TIPOS_FECHA_DE_HECHO, abrir,
                                          detectar_formato, fecha_corta, normalizar)
from ..services.evidencia.procesamiento import procesar_en_segundo_plano

router = APIRouter(prefix="/api/evidencia", tags=["Nomira Evidencia"])
PRIVADO = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
EXT = {"pdf": "pdf", "png": "png", "jpeg": "jpg", "webp": "webp"}
MIME = {"pdf": "application/pdf", "png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}
# Toda propuesta es un «hecho candidato». Confirmar significa que una persona revisó que el dato está bien
# tomado del documento; NO que sea verdadero, relevante, admisible ni suficiente.
ESTADOS_HECHO = {"por_revisar": "Propuesto por Nomira", "confirmado": "Confirmado por una persona",
                 "editado": "Editado por una persona", "descartado": "Descartado"}
VISIBILIDAD = {"interno": "Interno del despacho", "compartible": "Compartible con el cliente", "restringido": "Restringido"}
RELACIONES = {"sin_evaluar": "Sin evaluar", "apoya": "Apoya", "contradice": "Contradice", "no_basta": "No basta"}
ESTADOS_PUNTO = {"pendiente_evidencia": "Pendiente de evidencia", "respaldado": "Respaldado",
                 "parcial": "Parcialmente respaldado", "contradictorio": "Contradictorio"}
ESTADOS_PENDIENTE = {"pendiente": "Pendiente", "solicitado": "Solicitado", "recibido": "Recibido", "cancelado": "Cancelado"}


# ---------- utilidades ----------

def _txt(v: str | None, maximo: int) -> str | None:
    v = (v or "").strip()
    return v[:maximo] or None


def _importe(v: str | None) -> Decimal | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        d = Decimal(str(v).strip().replace("$", "").replace(",", ""))
    except InvalidOperation:
        raise HTTPException(422, "Importe inválido. Use el formato 1234.56")
    if not d.is_finite() or d.as_tuple().exponent < -2 or abs(d) >= Decimal("1e12"):
        raise HTTPException(422, "El importe admite como máximo 2 decimales.")
    return d.quantize(Decimal("0.01"))


def _asunto(db: Session, aid: int, u: m.Usuario) -> m.EvAsunto:
    return obtener(db, m.EvAsunto, aid, u)


def _de_asunto(db: Session, modelo, oid: int, u: m.Usuario):
    """Entidad hija (documento, hecho, punto, pendiente) de la organización del usuario."""
    return obtener(db, modelo, oid, u)


def _responsable(db: Session, uid: int | None, u: m.Usuario) -> int | None:
    if uid is None:
        return None
    x = db.get(m.Usuario, uid)
    if not x or x.organizacion_id != u.organizacion_id or getattr(x, "eliminado_en", None):
        raise HTTPException(422, "El responsable debe ser un usuario de su organización.")
    return x.id


def puede_ver(u: m.Usuario, a: m.EvAsunto, d: m.EvDocumento) -> bool:
    """Documento restringido: solo administradores, el responsable del asunto y quien lo cargó."""
    return d.visibilidad != "restringido" or u.rol == "administrador" or u.id in (a.responsable_id, d.subido_por_id)


def _exigir_visible(db: Session, u: m.Usuario, d: m.EvDocumento) -> m.EvAsunto:
    a = db.get(m.EvAsunto, d.asunto_id)
    if not puede_ver(u, a, d):
        raise HTTPException(404, "No encontrado.")  # como si no existiera, igual que entre organizaciones
    return a


def legibilidad(metodo: str | None, conf: int | None) -> str | None:
    """Señal de lectura en palabras (sin porcentajes que parezcan certeza)."""
    if metodo == "texto" or (metodo is None and conf is None):
        return "Texto digital del PDF: se leyó tal cual."
    if conf is None:
        return None
    if conf >= 85:
        return "Leído con OCR (imagen escaneada): legible."
    if conf >= 70:
        return "Leído con OCR: legibilidad media; compare con el original."
    return "Leído con OCR: poco legible; compare con el original antes de usarlo."


def _calidad(h: m.EvHecho) -> dict:
    """Qué se pudo identificar de la propuesta y qué no, en palabras."""
    si, no = [], []
    tipo = h.tipo_dato or "otro"
    if h.fecha:
        si.append("una fecha" + {"fecha_documento": " (del documento)", "fecha_mencionada": " (mencionada por una persona)",
                                 "fecha_evento": " (de un evento)"}.get(tipo, ""))
        if tipo == "fecha_indeterminada":
            no.append("si la fecha es del documento o de un evento")
    if h.importe is not None:
        si.append("una cantidad")
    if tipo in TIPOS_FECHA_DE_HECHO + ("importe",):
        (si if h.tema else no).append(f"de qué trata ({ETIQUETA_TEMA[h.tema].lower()})" if h.tema and h.tema in ETIQUETA_TEMA else "de qué evento trata")
        (si if h.atribucion else no).append("quién lo afirma" if h.atribucion else "quién lo afirma")
    if h.personas:
        si.append("personas mencionadas")
    motivo = (h.original or {}).get("motivo_calidad") if h.origen == "automatico" else None
    return {"nivel": h.calidad or "buena", "identificado": si, "no_identificado": no, "motivo": motivo,
            "lectura": legibilidad(None, h.confianza) if h.confianza is not None else ("Texto digital del PDF." if h.origen == "automatico" else None)}


def _nombres(db: Session, org_id: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org_id)).all())


def hecho_dict(h: m.EvHecho, nombres: dict[int, str] | None = None) -> dict:
    nombres = nombres or {}
    tipo = h.tipo_dato or "otro"
    tema_txt = ETIQUETA_TEMA.get(h.tema) if h.tema else None
    if h.tema and h.tema.startswith("rol:"):
        tema_txt = h.tema[4:].capitalize()
    estado_txt = ESTADOS_HECHO[h.estado] + (" · no relevante para este asunto" if h.estado == "descartado" and h.motivo_descarte == "no_relevante" else "")
    return {"id": h.id, "descripcion": h.descripcion, "fecha": h.fecha.isoformat() if h.fecha else None,
            "tipo_dato": tipo, "tipo_dato_texto": TIPOS_DATO.get(tipo, "Otro"), "tema": h.tema, "tema_texto": tema_txt,
            "atribucion": h.atribucion, "calidad": _calidad(h), "motivo_descarte": h.motivo_descarte,
            "valor_original": h.valor_original or h.fecha_texto,
            "valor": h.valor or (fecha_corta(h.fecha) if h.fecha else None),
            "fecha_texto": h.fecha_texto, "personas": h.personas or [], "importe": str(h.importe) if h.importe is not None else None,
            "dato": h.dato, "documento_id": h.documento_id, "pagina": h.pagina, "fragmento": h.fragmento, "bbox": h.bbox,
            "origen": h.origen, "estado": h.estado, "estado_texto": estado_txt,
            "original": h.original, "revisado_por": nombres.get(h.revisado_por_id),
            "revisado_en": h.revisado_en.isoformat() if h.revisado_en else None,
            "creado_por": nombres.get(h.creado_por_id), "creado_en": h.creado_en.isoformat()}


def documento_dict(d: m.EvDocumento, nombres: dict[int, str] | None = None, conteo: dict | None = None) -> dict:
    nombres = nombres or {}
    return {"id": d.id, "nombre": d.nombre_original, "formato": d.formato, "tamano_bytes": d.tamano_bytes,
            "estado": d.estado, "error": d.error, "intentos": d.intentos, "paginas": d.num_paginas,
            "tipo": d.tipo, "tipo_sugerido": d.tipo_sugerido, "clasificado": d.tipo is not None,
            "fecha_documento": d.fecha_documento.isoformat() if d.fecha_documento else None,
            "fecha_sugerida": d.fecha_sugerida.isoformat() if d.fecha_sugerida else None,
            "subido_por": nombres.get(d.subido_por_id), "creado_en": d.creado_en.isoformat(),
            "sha256": d.sha256, "hechos": (conteo or {}).get(d.id, 0), "origen": d.origen,
            "visibilidad": d.visibilidad, "visibilidad_texto": VISIBILIDAD.get(d.visibilidad, d.visibilidad),
            "solicitado_como": d.solicitado_como, "resumen_lectura": d.resumen_lectura,
            "solicitud_id": d.solicitud_id, "aceptado_por": nombres.get(d.aceptado_por_id),
            "aceptado_en": d.aceptado_en.isoformat() if d.aceptado_en else None}


def panel(db: Session, a: m.EvAsunto, u: m.Usuario) -> dict:
    """Todo lo que la pantalla del asunto necesita, calculado en un solo lugar (lo usa también la
    exportación). Respeta la visibilidad: lo restringido que el usuario no puede ver no aparece."""
    nombres = _nombres(db, a.organizacion_id)
    todos = db.scalars(select(m.EvDocumento).where(m.EvDocumento.asunto_id == a.id).order_by(m.EvDocumento.id)).all()
    docs = [d for d in todos if puede_ver(u, a, d)]
    visibles = {d.id for d in docs}
    hechos = [h for h in db.scalars(select(m.EvHecho).where(m.EvHecho.asunto_id == a.id)
                                    .order_by(m.EvHecho.fecha.nulls_last(), m.EvHecho.id)).all()
              if h.documento_id is None or h.documento_id in visibles]
    puntos = db.scalars(select(m.EvPunto).where(m.EvPunto.asunto_id == a.id).order_by(m.EvPunto.orden, m.EvPunto.id)).all()
    pend = db.scalars(select(m.EvPendiente).where(m.EvPendiente.asunto_id == a.id)
                      .order_by(m.EvPendiente.fecha_seguimiento.nulls_last(), m.EvPendiente.id)).all()
    conteo = {}
    for h in hechos:
        if h.documento_id and h.estado != "descartado":
            conteo[h.documento_id] = conteo.get(h.documento_id, 0) + 1
    hs = [hecho_dict(h, nombres) for h in hechos]
    contra = analisis.contradicciones(hs, set(a.contradicciones_descartadas or []), a.decisiones_diferencias or {}, ETIQUETA_TEMA)
    for c in contra:
        if c["decision"] and c["decision"].get("por"):
            c["decision"] = {**c["decision"], "por_nombre": nombres.get(c["decision"]["por"])}
    abiertas = [c for c in contra if c["estado"] == "pendiente" or c["contradiccion"]]
    en_conflicto = {i for c in abiertas for i in c["hechos"]}
    por_id = {h["id"]: h for h in hs}
    sols = db.scalars(select(m.EvSolicitud).where(m.EvSolicitud.asunto_id == a.id).order_by(m.EvSolicitud.id.desc())).all()
    docs_d = [documento_dict(d, nombres, conteo) for d in docs]
    _relacionados(db, docs_d)
    nombre_doc = {d["id"]: d["nombre"] for d in docs_d}
    puntos_d = []
    for p in puntos:
        vs = [{"id": v.id, "hecho_id": v.hecho_id, "documento_id": v.documento_id, "documento": nombre_doc.get(v.documento_id),
               "pagina": v.pagina, "nota": v.nota, "hecho": por_id.get(v.hecho_id), "relacion": v.relacion,
               "relacion_texto": RELACIONES.get(v.relacion, v.relacion), "relacion_por": nombres.get(v.relacion_por_id),
               "relacion_en": v.relacion_en.isoformat() if v.relacion_en else None}
              for v in p.vinculos if v.documento_id in visibles]
        ocultos = sum(1 for v in p.vinculos if v.documento_id not in visibles)
        puntos_d.append({"id": p.id, "descripcion": p.descripcion, "estado": p.estado, "estado_texto": ESTADOS_PUNTO[p.estado],
                         "estado_decidido_por": nombres.get(p.estado_decidido_por_id),
                         "estado_decidido_en": p.estado_decidido_en.isoformat() if p.estado_decidido_en else None,
                         "notas": p.notas, "vinculos": vs, "vinculos_restringidos": ocultos,
                         "sugerencia": analisis.sugerir_estado_punto(vs, en_conflicto)})
    cuenta = {k: sum(1 for h in hs if h["estado"] == k) for k in ESTADOS_HECHO}
    pend_d = [pendiente_dict(x) for x in pend]
    return {
        "asunto": asunto_dict(a, nombres),
        "documentos": docs_d,
        "hechos": hs,
        "cronologia": analisis.cronologia(hs, contra),
        "contradicciones": contra,
        "puntos": puntos_d,
        "pendientes": pend_d,
        "solicitudes": [sol.solicitud_dict(x, nombres) for x in sols],
        "resumen": {"documentos": len(docs), "documentos_por_revisar": sum(1 for d in docs if d.estado in ("requiere_revision", "error")),
                    "documentos_en_proceso": sum(1 for d in docs if d.estado in ("pendiente", "procesando")),
                    "documentos_recibidos": sum(1 for d in docs if d.estado == "recibido"),
                    "documentos_restringidos_ocultos": len(todos) - len(docs),
                    "solicitudes_activas": sum(1 for x in sols if sol.estado(x) == "activa"),
                    "documentos_sin_clasificar": sum(1 for d in docs if d.tipo is None and d.estado not in ("pendiente", "procesando", "recibido")),
                    "hechos": cuenta, "contradicciones": len(abiertas),
                    "diferencias_pendientes": sum(1 for c in contra if c["estado"] == "pendiente"),
                    "diferencias_resueltas": sum(1 for c in contra if c["estado"] == "resuelta"),
                    "puntos": {k: sum(1 for p in puntos if p.estado == k) for k in ESTADOS_PUNTO},
                    "puntos_sin_vinculos": sum(1 for p in puntos_d if not p["vinculos"]),
                    "pendientes_abiertos": sum(1 for x in pend if x.estado in ("pendiente", "solicitado")),
                    "pendientes_vencidos": sum(1 for x in pend_d if x["vencido"]),
                    "pendientes_proximos": sum(1 for x in pend_d if x["proximo"])},
        "catalogos": {"tipos_documento": TIPOS_DISPONIBLES, "estados_hecho": ESTADOS_HECHO, "estados_punto": ESTADOS_PUNTO,
                      "tipos_dato": TIPOS_DATO, "temas": ETIQUETA_TEMA, "correo_configurado": correo.configurado(),
                      "decisiones": analisis.DECISIONES, "visibilidad": VISIBILIDAD, "relaciones": RELACIONES,
                      "ambitos": jurisdiccion.AMBITOS, "entidades": jurisdiccion.ENTIDADES,
                      "estados_pendiente": ESTADOS_PENDIENTE},
    }


def _palabras(texto: str) -> set[str]:
    return {w for w in normalizar(texto).split() if len(w) > 2}


def _relacionados(db: Session, docs: list[dict]) -> None:
    """Posibles duplicados (texto casi idéntico) y posibles versiones (texto muy parecido) entre los
    documentos del asunto, comparando las primeras páginas leídas. Nunca se fusionan ni se borran:
    se señalan, y en cada grupo se indica el que se cargó al último (no necesariamente el vigente)."""
    ids = [d["id"] for d in docs if d["estado"] in ("leido", "requiere_revision")]
    for d in docs:
        d["relacionados"] = []
    if len(ids) < 2:
        return
    textos: dict[int, list[str]] = {}
    for did, texto in db.execute(select(m.EvPagina.documento_id, m.EvPagina.texto).where(
            m.EvPagina.documento_id.in_(ids), m.EvPagina.numero <= 3).order_by(m.EvPagina.documento_id, m.EvPagina.numero)):
        textos.setdefault(did, []).append(texto or "")
    palabras = {i: _palabras(" ".join(t)) for i, t in textos.items()}
    por_id = {d["id"]: d for d in docs}
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            pa, pb = palabras.get(a, set()), palabras.get(b, set())
            if len(pa) < 15 or len(pb) < 15:
                continue
            sim = len(pa & pb) / len(pa | pb)
            tipo = "duplicado" if sim >= 0.9 else "version" if sim >= 0.55 else None
            if tipo:
                for x, y in ((a, b), (b, a)):
                    reciente = por_id[y]["creado_en"] > por_id[x]["creado_en"]
                    por_id[x]["relacionados"].append({"id": y, "nombre": por_id[y]["nombre"], "tipo": tipo,
                                                      "similitud": round(sim, 2), "es_mas_reciente": reciente})


def asunto_dict(a: m.EvAsunto, nombres: dict[int, str]) -> dict:
    return {"id": a.id, "nombre": a.nombre, "cliente": a.cliente, "tipo_caso": a.tipo_caso, "jurisdiccion": a.jurisdiccion,
            "jurisdiccion_texto": jurisdiccion.texto(a), "ambito": a.ambito, "entidad_federativa": a.entidad_federativa,
            "municipio_distrito": a.municipio_distrito, "organo": a.organo, "expediente_judicial": a.expediente_judicial,
            "identificador_interno": a.identificador_interno, "responsable_id": a.responsable_id,
            "responsable": nombres.get(a.responsable_id), "notas": a.notas, "campos": a.campos or {},
            "creado_por": nombres.get(a.creado_por_id), "creado_en": a.creado_en.isoformat(),
            "actualizado_en": a.actualizado_en.isoformat()}


def pendiente_dict(x: m.EvPendiente) -> dict:
    return {"id": x.id, "descripcion": x.descripcion, "responsable": x.responsable,
            "fecha_seguimiento": x.fecha_seguimiento.isoformat() if x.fecha_seguimiento else None,
            "estado": x.estado, "estado_texto": ESTADOS_PENDIENTE[x.estado], "nota": x.nota,
            "vencido": bool(x.fecha_seguimiento and x.fecha_seguimiento < date.today() and x.estado in ("pendiente", "solicitado")),
            "proximo": bool(x.fecha_seguimiento and date.today() <= x.fecha_seguimiento <= date.today() + timedelta(days=3)
                            and x.estado in ("pendiente", "solicitado"))}


# ---------- asuntos ----------

class AsuntoIn(BaseModel):
    ambito: str | None = None
    entidad_federativa: str | None = Field(None, max_length=40)
    municipio_distrito: str | None = Field(None, max_length=160)
    organo: str | None = Field(None, max_length=200)
    expediente_judicial: str | None = Field(None, max_length=80)
    nombre: str = Field(min_length=2, max_length=200)
    cliente: str | None = Field(None, max_length=200)
    tipo_caso: str | None = Field(None, max_length=120)
    jurisdiccion: str | None = Field(None, max_length=160)
    identificador_interno: str | None = Field(None, max_length=80)
    responsable_id: int | None = None
    notas: str | None = Field(None, max_length=5000)
    campos: dict[str, str] | None = None


class AsuntoCambio(BaseModel):
    ambito: str | None = None
    entidad_federativa: str | None = Field(None, max_length=40)
    municipio_distrito: str | None = Field(None, max_length=160)
    organo: str | None = Field(None, max_length=200)
    expediente_judicial: str | None = Field(None, max_length=80)
    nombre: str | None = Field(None, min_length=2, max_length=200)
    cliente: str | None = Field(None, max_length=200)
    tipo_caso: str | None = Field(None, max_length=120)
    jurisdiccion: str | None = Field(None, max_length=160)
    identificador_interno: str | None = Field(None, max_length=80)
    responsable_id: int | None = None
    notas: str | None = Field(None, max_length=5000)
    campos: dict[str, str] | None = None


def _jurisdiccion(datos: dict) -> dict:
    """Valida los campos de jurisdicción presentes. Ninguno es obligatorio."""
    salida = {}
    if "ambito" in datos:
        v = datos["ambito"] or None
        if v and v not in jurisdiccion.AMBITOS:
            raise HTTPException(422, "Ámbito inválido: federal o local.")
        salida["ambito"] = v
    if "entidad_federativa" in datos:
        v = (datos["entidad_federativa"] or "").strip() or None
        if v and v not in jurisdiccion.ENTIDADES:
            raise HTTPException(422, "Elija una entidad federativa de la lista.")
        salida["entidad_federativa"] = v
    for k, n in (("municipio_distrito", 160), ("organo", 200), ("expediente_judicial", 80)):
        if k in datos:
            salida[k] = _txt(datos[k], n)
    return salida


def _campos(c: dict | None) -> dict | None:
    if not c:
        return None
    if len(c) > 20:
        raise HTTPException(422, "Máximo 20 campos adicionales.")
    limpio = {_txt(k, 60): _txt(v, 300) for k, v in c.items() if _txt(k, 60)}
    return {k: v for k, v in limpio.items() if v} or None


@router.get("/responsables")
def responsables(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Usuarios activos de la organización que pueden ser responsables de un asunto."""
    us = db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == u.organizacion_id, m.Usuario.activo.is_(True),
                                            m.Usuario.eliminado_en.is_(None)).order_by(m.Usuario.nombre))
    return [{"id": x.id, "nombre": x.nombre} for x in us]


@router.get("/asuntos")
def listar(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    asuntos = db.scalars(select(m.EvAsunto).where(m.EvAsunto.organizacion_id == u.organizacion_id)
                         .order_by(m.EvAsunto.actualizado_en.desc())).all()
    ids = [a.id for a in asuntos]
    def contar(modelo, *filtros):
        q = select(modelo.asunto_id, func.count()).where(modelo.asunto_id.in_(ids)).group_by(modelo.asunto_id)
        for f in filtros:
            q = q.where(f)
        return dict(db.execute(q).all()) if ids else {}
    docs = contar(m.EvDocumento)
    por_revisar = contar(m.EvHecho, m.EvHecho.estado == "por_revisar")
    confirmados = contar(m.EvHecho, m.EvHecho.estado.in_(analisis.REVISADOS))
    pend = contar(m.EvPendiente, m.EvPendiente.estado.in_(("pendiente", "solicitado")))
    recibidos = contar(m.EvDocumento, m.EvDocumento.estado == "recibido")
    sin_ev = contar(m.EvPunto, m.EvPunto.estado == "pendiente_evidencia")
    nombres = _nombres(db, u.organizacion_id)
    return [{**asunto_dict(a, nombres), "documentos": docs.get(a.id, 0), "hechos_por_revisar": por_revisar.get(a.id, 0),
             "hechos_confirmados": confirmados.get(a.id, 0), "pendientes_abiertos": pend.get(a.id, 0),
             "puntos_sin_evidencia": sin_ev.get(a.id, 0), "documentos_recibidos": recibidos.get(a.id, 0)} for a in asuntos]


@router.post("/asuntos", status_code=201)
def crear(d: AsuntoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = m.EvAsunto(organizacion_id=u.organizacion_id, nombre=d.nombre.strip(), cliente=_txt(d.cliente, 200),
                   tipo_caso=_txt(d.tipo_caso, 120), jurisdiccion=_txt(d.jurisdiccion, 160),
                   identificador_interno=_txt(d.identificador_interno, 80),
                   responsable_id=_responsable(db, d.responsable_id, u), notas=_txt(d.notas, 5000),
                   campos=_campos(d.campos), creado_por_id=u.id,
                   **_jurisdiccion(d.model_dump(include={"ambito", "entidad_federativa", "municipio_distrito", "organo",
                                                         "expediente_judicial"})))
    db.add(a)
    db.flush()
    auditar(db, u, "ev_asunto_creado", "ev_asunto", a.id, request=request)
    db.commit()
    return asunto_dict(a, _nombres(db, u.organizacion_id))


@router.get("/asuntos/{aid}")
def ver(aid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return panel(db, _asunto(db, aid, u), u)


@router.patch("/asuntos/{aid}")
def cambiar(aid: int, d: AsuntoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _asunto(db, aid, u)
    datos = d.model_dump(exclude_unset=True)
    for k, v in _jurisdiccion(datos).items():
        datos.pop(k)
        if v != getattr(a, k):
            setattr(a, k, v)
    limites = {"nombre": 200, "cliente": 200, "tipo_caso": 120, "jurisdiccion": 160, "identificador_interno": 80, "notas": 5000}
    cambios = [k for k in ("ambito", "entidad_federativa", "municipio_distrito", "organo", "expediente_judicial")
               if k in d.model_fields_set]
    for k, v in datos.items():
        if k == "responsable_id":
            v = _responsable(db, v, u)
        elif k == "campos":
            v = _campos(v)
        elif k == "nombre":
            if not v:
                continue
            v = v.strip()
        else:
            v = _txt(v, limites[k])
        if v != getattr(a, k):
            setattr(a, k, v)
            cambios.append(k)
    auditar(db, u, "ev_asunto_modificado", "ev_asunto", a.id, {"campos": cambios}, request)
    db.commit()
    return asunto_dict(a, _nombres(db, u.organizacion_id))


class Confirmacion(BaseModel):
    confirmar_nombre: str = Field(max_length=200)


@router.post("/asuntos/{aid}/eliminar")
def eliminar(aid: int, d: Confirmacion, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    a = _asunto(db, aid, u)
    if d.confirmar_nombre.strip() != a.nombre:
        raise HTTPException(422, "Escriba el nombre exacto del asunto para confirmar.")
    rutas = [r for (r,) in db.execute(select(m.EvDocumento.ruta).where(m.EvDocumento.asunto_id == a.id))]
    auditar(db, u, "ev_asunto_eliminado", "ev_asunto", a.id, {"documentos": len(rutas)}, request)
    db.delete(a)
    db.commit()
    for r in rutas:
        try:
            os.unlink(r)
        except OSError:
            pass
    return {"ok": True}


# ---------- documentos ----------

def _leer_archivo(archivo: UploadFile) -> tuple[bytes, str]:
    limite = ajustes().max_mb_archivo * 1024 * 1024
    datos = archivo.file.read(limite + 1)
    if len(datos) > limite:
        raise HTTPException(413, f"El archivo excede {ajustes().max_mb_archivo} MB.")
    formato = detectar_formato(datos)
    if formato is None:
        raise HTTPException(415, "Solo se aceptan PDF o imágenes PNG, JPG o WebP.")
    if formato == "pdf":
        try:
            with pymupdf.open(stream=datos, filetype="pdf") as d:
                if d.needs_pass:
                    raise HTTPException(422, "El PDF está protegido con contraseña.")
                if d.page_count == 0:
                    raise HTTPException(422, "El PDF no tiene páginas.")
                if d.page_count > ajustes().max_paginas_pdf:
                    raise HTTPException(413, f"El PDF excede {ajustes().max_paginas_pdf} páginas.")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "El archivo no es un PDF legible.")
    else:
        import io

        from PIL import Image
        try:
            Image.MAX_IMAGE_PIXELS = 60_000_000
            with Image.open(io.BytesIO(datos)) as img:
                img.verify()
        except Exception:
            raise HTTPException(415, "La imagen está dañada o no es válida.")
    return datos, formato


@router.post("/asuntos/{aid}/documentos", status_code=201)
def subir(aid: int, request: Request, tareas: BackgroundTasks, archivos: list[UploadFile] = File(...),
          u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _asunto(db, aid, u)
    if len(archivos) > 50:
        raise HTTPException(413, "Máximo 50 archivos por carga.")
    res = []
    for archivo in archivos:
        nombre = os.path.basename(archivo.filename or "documento")[:300]
        try:
            datos, formato = _leer_archivo(archivo)
        except HTTPException as e:
            res.append({"nombre": nombre, "aceptado": False, "motivo": e.detail})
            continue
        sha = hashlib.sha256(datos).hexdigest()
        previo = db.scalar(select(m.EvDocumento).where(m.EvDocumento.asunto_id == a.id, m.EvDocumento.sha256 == sha))
        if previo:
            res.append({"nombre": nombre, "aceptado": False, "duplicado_de": previo.id,
                        "motivo": f"Archivo idéntico a «{previo.nombre_original}». No se cargó de nuevo."})
            continue
        carpeta = Path(ajustes().storage_dir) / str(u.organizacion_id) / "evidencia" / str(a.id)
        carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
        ruta = carpeta / f"{sha}.{EXT[formato]}"  # el original se guarda tal cual, con nombre propio del sistema
        ruta.write_bytes(datos)
        os.chmod(ruta, 0o600)
        d = m.EvDocumento(organizacion_id=u.organizacion_id, asunto_id=a.id, nombre_original=nombre, sha256=sha,
                          tamano_bytes=len(datos), formato=formato, ruta=str(ruta), subido_por_id=u.id)
        db.add(d)
        db.flush()
        auditar(db, u, "ev_documento_cargado", "ev_documento", d.id, {"asunto_id": a.id, "sha256": sha}, request)
        res.append({"nombre": nombre, "aceptado": True, "documento_id": d.id})
    a.actualizado_en = m.ahora()
    db.commit()
    for r in res:
        if r["aceptado"]:
            tareas.add_task(procesar_en_segundo_plano, r["documento_id"])
    return res


class Clasificacion(BaseModel):
    tipo: str = Field(min_length=2, max_length=60)
    fecha_documento: date | None = None


@router.patch("/documentos/{did}")
def clasificar(did: int, d: Clasificacion, request: Request, u: m.Usuario = Depends(puede_editar),
               db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    _exigir_visible(db, u, doc)
    antes = {"tipo": doc.tipo, "fecha": doc.fecha_documento.isoformat() if doc.fecha_documento else None}
    doc.tipo, doc.fecha_documento, doc.clasificado_por_id = d.tipo.strip(), d.fecha_documento, u.id
    auditar(db, u, "ev_documento_clasificado", "ev_documento", doc.id,
            {"asunto_id": doc.asunto_id, "antes": antes, "tipo": doc.tipo, "sugerido": doc.tipo_sugerido}, request)
    db.commit()
    return documento_dict(doc)


class Visibilidad(BaseModel):
    visibilidad: str


@router.patch("/documentos/{did}/visibilidad")
def cambiar_visibilidad(did: int, d: Visibilidad, request: Request, u: m.Usuario = Depends(puede_editar),
                        db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    _exigir_visible(db, u, doc)
    if d.visibilidad not in VISIBILIDAD:
        raise HTTPException(422, "Visibilidad inválida.")
    antes, doc.visibilidad = doc.visibilidad, d.visibilidad
    auditar(db, u, "ev_documento_visibilidad", "ev_documento", doc.id,
            {"asunto_id": doc.asunto_id, "antes": antes, "visibilidad": d.visibilidad}, request)
    db.commit()
    return documento_dict(doc)


@router.post("/documentos/{did}/reprocesar")
def reprocesar(did: int, request: Request, tareas: BackgroundTasks, u: m.Usuario = Depends(puede_editar),
               db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    _exigir_visible(db, u, doc)
    if doc.estado in ("pendiente", "procesando"):
        raise HTTPException(409, "El documento ya se está leyendo.")
    if doc.estado == "recibido":
        raise HTTPException(409, "Primero acepte el documento enviado por el cliente.")
    auditar(db, u, "ev_documento_releido", "ev_documento", doc.id, {"asunto_id": doc.asunto_id}, request)
    db.commit()
    tareas.add_task(procesar_en_segundo_plano, doc.id)
    return {"ok": True}


@router.post("/documentos/{did}/aceptar")
def aceptar_documento(did: int, request: Request, tareas: BackgroundTasks, u: m.Usuario = Depends(puede_editar),
                      db: Session = Depends(get_db)):
    """Un documento enviado por el cliente pasa a lectura solo cuando una persona lo acepta."""
    doc = _de_asunto(db, m.EvDocumento, did, u)
    _exigir_visible(db, u, doc)
    if doc.estado != "recibido":
        raise HTTPException(409, "Este documento no está pendiente de aceptación.")
    doc.estado, doc.aceptado_por_id, doc.aceptado_en = "pendiente", u.id, m.ahora()
    auditar(db, u, "ev_documento_aceptado", "ev_documento", doc.id, {"asunto_id": doc.asunto_id}, request)
    db.commit()
    tareas.add_task(procesar_en_segundo_plano, doc.id)
    return {"ok": True}


@router.delete("/documentos/{did}")
def borrar_documento(did: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    _exigir_visible(db, u, doc)
    revisados = db.scalar(select(func.count()).select_from(m.EvHecho).where(
        m.EvHecho.documento_id == doc.id, m.EvHecho.estado.in_(analisis.REVISADOS)))
    vinculos = db.scalar(select(func.count()).select_from(m.EvVinculo).where(m.EvVinculo.documento_id == doc.id))
    if revisados or vinculos:
        raise HTTPException(409, f"Este documento es la fuente de {revisados} hecho(s) revisado(s) y {vinculos} vínculo(s) "
                                 "de la matriz. Descarte esos hechos o quite los vínculos antes de eliminarlo.")
    if doc.estado == "procesando":
        raise HTTPException(409, "Espere a que termine la lectura.")
    db.execute(delete(m.EvHecho).where(m.EvHecho.documento_id == doc.id))
    ruta = doc.ruta
    auditar(db, u, "ev_documento_rechazado" if doc.estado == "recibido" else "ev_documento_eliminado", "ev_documento",
            doc.id, {"asunto_id": doc.asunto_id, "sha256": doc.sha256, "origen": doc.origen}, request)
    db.delete(doc)
    db.commit()
    try:
        os.unlink(ruta)
    except OSError:
        pass
    return {"ok": True}


# ---------- solicitudes de documentos al cliente ----------

class SolicitudIn(BaseModel):
    email: str = Field(max_length=254)
    mensaje: str | None = Field(None, max_length=2000)
    documentos: list[str] | None = Field(None, max_length=30)
    dias: int = 7
    requiere_codigo: bool = True
    max_archivos: int = Field(20, ge=1, le=50)


@router.post("/asuntos/{aid}/solicitudes", status_code=201)
def crear_solicitud(aid: int, d: SolicitudIn, request: Request, u: m.Usuario = Depends(puede_editar),
                    db: Session = Depends(get_db)):
    """Crea un enlace para que el cliente SUBA documentos y se lo envía por correo. El enlace se
    devuelve una sola vez (para copiarlo si hace falta); después solo se conoce su huella."""
    a = _asunto(db, aid, u)
    email = d.email.strip().lower()
    if not sol.email_valido(email):
        raise HTTPException(422, "Escriba un correo válido.")
    if d.dias not in sol.VIGENCIAS:
        raise HTTPException(422, "Vigencia inválida.")
    documentos = [x.strip()[:200] for x in (d.documentos or []) if x and x.strip()][:30]
    token = sol.nuevo_token()
    s = m.EvSolicitud(organizacion_id=u.organizacion_id, asunto_id=a.id, email=email, mensaje=_txt(d.mensaje, 2000),
                      documentos=documentos or None, token_hash=sol.huella(token), token_pista=token[:4],
                      requiere_codigo=d.requiere_codigo, max_archivos=d.max_archivos, archivos_recibidos=0,
                      expira_en=m.ahora() + timedelta(days=d.dias), codigo_intentos=0, codigos_enviados=0, creado_por_id=u.id)
    db.add(s)
    db.flush()
    auditar(db, u, "ev_solicitud_creada", "ev_solicitud", s.id, {"asunto_id": a.id, "email": email, "dias": d.dias,
            "requiere_codigo": d.requiere_codigo, "pista": s.token_pista}, request)
    db.commit()
    org = db.get(m.Organizacion, u.organizacion_id)
    asunto_c, html, texto = plantillas_correo.solicitud_documentos(org.nombre, u.nombre, sol.enlace(token), s.expira_en.date(),
                                                                   s.mensaje, documentos, s.requiere_codigo)
    r = envios.registrar_y_enviar(db, "ev_solicitud", [email], asunto_c, html, texto, organizacion_id=u.organizacion_id)
    return {"solicitud": sol.solicitud_dict(s, _nombres(db, u.organizacion_id)), "enlace": sol.enlace(token),
            "correo": {"enviado": r.estado == "enviado", "error": r.error, "prueba": correo.modo_prueba()}}


@router.post("/solicitudes/{sid}/revocar")
def revocar_solicitud(sid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    s = _de_asunto(db, m.EvSolicitud, sid, u)
    if s.revocada_en:
        raise HTTPException(409, "El enlace ya estaba revocado.")
    s.revocada_en, s.revocada_por_id = m.ahora(), u.id
    s.codigo_hash = None
    auditar(db, u, "ev_solicitud_revocada", "ev_solicitud", s.id, {"asunto_id": s.asunto_id, "pista": s.token_pista}, request)
    db.commit()
    return sol.solicitud_dict(s, _nombres(db, u.organizacion_id))


@router.get("/documentos/{did}/archivo")
def descargar(did: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    _exigir_visible(db, u, doc)
    auditar(db, u, "ev_documento_descargado", "ev_documento", doc.id, {"asunto_id": doc.asunto_id}, request)
    db.commit()
    return Response(Path(doc.ruta).read_bytes(), media_type=MIME[doc.formato], headers={
        **PRIVADO, "Content-Disposition": f'attachment; filename="evidencia-{doc.id}.{EXT[doc.formato]}"'})


def _cache_pagina(doc: m.EvDocumento, numero: int, dpi: int) -> Path:
    """Vista generada de una página (no el original). Se guarda para no volver a dibujarla: en un
    servidor con poco CPU, dibujar cada vez hacía que el visor tardara mucho."""
    return Path(ajustes().storage_dir) / "cache" / "evidencia" / f"{doc.id}-{doc.sha256[:16]}-{numero}-{dpi}.png"


@router.get("/documentos/{did}/paginas/{numero}/imagen")
def imagen(did: int, numero: int, dpi: int = 110, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    _exigir_visible(db, u, doc)
    dpi = min(max(dpi, 50), 200)
    cache = _cache_pagina(doc, numero, dpi)
    if not Path(doc.ruta).exists():
        raise HTTPException(410, "El archivo original no está disponible en el servidor. Si es un documento de "
                                 "demostración se restaurará en un momento; si no, vuelva a cargarlo.")
    if cache.exists():
        png = cache.read_bytes()
    else:
        try:
            with abrir(doc.ruta, doc.formato) as pdf:
                if not 1 <= numero <= pdf.page_count:
                    raise HTTPException(404, f"El documento no tiene página {numero}.")
                png = pdf[numero - 1].get_pixmap(dpi=dpi).tobytes("png")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(409, "No se pudo mostrar esta página. Descargue el original para revisarlo.")
        try:
            cache.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            cache.write_bytes(png)
            os.chmod(cache, 0o600)
        except OSError:
            pass
    return Response(png, media_type="image/png", headers={**PRIVADO, "X-Paginas": str(doc.num_paginas or 1),
                                                          "Access-Control-Expose-Headers": "X-Paginas"})


@router.get("/documentos/{did}/paginas/{numero}/texto")
def texto_pagina(did: int, numero: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Texto que Nomira leyó de la página (del PDF o por OCR). Es una lectura, no el original."""
    doc = _de_asunto(db, m.EvDocumento, did, u)
    _exigir_visible(db, u, doc)
    pg = db.scalar(select(m.EvPagina).where(m.EvPagina.documento_id == doc.id, m.EvPagina.numero == numero))
    if pg is None:
        return {"texto": None, "metodo": None, "legibilidad": None,
                "aviso": "Esta página aún no se ha leído." if doc.estado in ("recibido", "pendiente", "procesando") else "Sin texto leído."}
    return {"texto": pg.texto, "metodo": pg.metodo, "legibilidad": legibilidad(pg.metodo, pg.confianza_ocr)}


# ---------- hechos ----------

class HechoIn(BaseModel):
    descripcion: str = Field(min_length=3, max_length=2000)
    tipo_dato: str | None = None
    fecha: date | None = None
    personas: list[str] | None = None
    importe: str | None = Field(None, max_length=30)
    dato: str | None = Field(None, max_length=300)
    documento_id: int | None = None
    pagina: int | None = Field(None, ge=1, le=10000)
    fragmento: str | None = Field(None, max_length=2000)


class HechoCambio(BaseModel):
    descripcion: str | None = Field(None, min_length=3, max_length=2000)
    tipo_dato: str | None = None
    fecha: date | None = None
    personas: list[str] | None = None
    importe: str | None = Field(None, max_length=30)
    dato: str | None = Field(None, max_length=300)
    documento_id: int | None = None
    pagina: int | None = Field(None, ge=1, le=10000)


class Ids(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


def _fuente(db: Session, a: m.EvAsunto, documento_id: int | None, pagina: int | None, u: m.Usuario):
    if documento_id is None:
        return None, None
    doc = _de_asunto(db, m.EvDocumento, documento_id, u)
    if doc.asunto_id != a.id:
        raise HTTPException(422, "El documento fuente debe pertenecer a este asunto.")
    if pagina is not None and doc.num_paginas and pagina > doc.num_paginas:
        raise HTTPException(422, f"El documento solo tiene {doc.num_paginas} página(s).")
    return doc.id, pagina


def _tipo_dato(v: str | None) -> str | None:
    if v is None:
        return None
    if v not in TIPOS_DATO:
        raise HTTPException(422, "Tipo de dato inválido.")
    return v


def _personas(v: list[str] | None) -> list[str] | None:
    limpio = [p.strip()[:120] for p in (v or []) if p and p.strip()][:20]
    return limpio or None


@router.post("/asuntos/{aid}/hechos", status_code=201)
def crear_hecho(aid: int, d: HechoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Hecho capturado por una persona. Con documento fuente queda confirmado; sin fuente queda
    «por revisar» y no puede confirmarse hasta que se le asigne una."""
    a = _asunto(db, aid, u)
    doc_id, pagina = _fuente(db, a, d.documento_id, d.pagina, u)
    tipo = _tipo_dato(d.tipo_dato) or ("fecha_evento" if d.fecha else "importe" if d.importe else "otro")
    h = m.EvHecho(organizacion_id=u.organizacion_id, asunto_id=a.id, descripcion=d.descripcion.strip(), fecha=d.fecha,
                  tipo_dato=tipo, valor=fecha_corta(d.fecha) if d.fecha else None,
                  personas=_personas(d.personas), importe=_importe(d.importe), dato=_txt(d.dato, 300),
                  documento_id=doc_id, pagina=pagina, fragmento=_txt(d.fragmento, 2000), origen="manual",
                  estado="confirmado" if doc_id else "por_revisar", creado_por_id=u.id)
    if doc_id:
        h.revisado_por_id, h.revisado_en = u.id, m.ahora()
    db.add(h)
    db.flush()
    auditar(db, u, "ev_hecho_capturado", "ev_hecho", h.id, {"asunto_id": a.id, "con_fuente": bool(doc_id)}, request)
    db.commit()
    return hecho_dict(h, _nombres(db, u.organizacion_id))


@router.patch("/hechos/{hid}")
def editar_hecho(hid: int, d: HechoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    h = _de_asunto(db, m.EvHecho, hid, u)
    a = db.get(m.EvAsunto, h.asunto_id)
    datos = d.model_dump(exclude_unset=True)
    cambios = []
    if "documento_id" in datos or "pagina" in datos:
        doc_id, pagina = _fuente(db, a, datos.get("documento_id", h.documento_id), datos.get("pagina", h.pagina), u)
        if (doc_id, pagina) != (h.documento_id, h.pagina):
            h.documento_id, h.pagina, h.bbox = doc_id, pagina, None if doc_id != h.documento_id else h.bbox
            cambios.append("fuente")
    antes, despues = {}, {}
    for k in ("descripcion", "tipo_dato", "fecha", "personas", "importe", "dato"):
        if k not in datos:
            continue
        v = datos[k]
        v = v.strip() if k == "descripcion" and v else _importe(v) if k == "importe" else _personas(v) if k == "personas" \
            else _txt(v, 300) if k == "dato" else _tipo_dato(v) if k == "tipo_dato" else v
        if k in ("descripcion", "tipo_dato") and not v:
            continue
        if v != getattr(h, k):
            antes[k], despues[k] = _para_historial(getattr(h, k)), _para_historial(v)
            setattr(h, k, v)
            cambios.append(k)
    if "fecha" in cambios:
        h.valor = fecha_corta(h.fecha) if h.fecha else None
    if not cambios:
        raise HTTPException(422, "No hay cambios que registrar.")
    # Lo editado por una persona cuenta como revisado, pero solo si conserva una fuente localizable.
    h.estado = "editado" if h.documento_id else "por_revisar"
    h.revisado_por_id, h.revisado_en = u.id, m.ahora()
    auditar(db, u, "ev_hecho_editado", "ev_hecho", h.id,
            {"asunto_id": h.asunto_id, "campos": cambios, "antes": antes, "despues": despues}, request)
    db.commit()
    return hecho_dict(h, _nombres(db, u.organizacion_id))


def _para_historial(v):
    if v is None or isinstance(v, (str, int, list)):
        return v[:300] if isinstance(v, str) else v
    return str(v)


def _cambiar_estado(db: Session, u: m.Usuario, request: Request, h: m.EvHecho, accion: str) -> None:
    accion = "confirmar" if accion == "validar" else accion
    antes_estado = h.estado
    if accion == "confirmar":
        if not h.documento_id:
            raise HTTPException(409, "No puede confirmarse un hecho sin documento fuente. Asígnele uno o descártelo.")
        h.estado = "editado" if h.estado == "editado" else "confirmado"
    elif accion in ("descartar", "no_relevante"):
        h.estado = "descartado"
        h.motivo_descarte = "no_relevante" if accion == "no_relevante" else None
    else:  # reabrir
        h.estado, h.motivo_descarte = "por_revisar", None
    h.revisado_por_id, h.revisado_en = u.id, m.ahora()
    nombre = {"confirmar": "ev_hecho_confirmado", "descartar": "ev_hecho_descartado", "no_relevante": "ev_hecho_no_relevante",
              "reabrir": "ev_hecho_reabierto"}[accion]
    auditar(db, u, nombre, "ev_hecho", h.id, {"asunto_id": h.asunto_id, "antes": antes_estado, "despues": h.estado}, request)


@router.post("/hechos/{hid}/{accion}")
def estado_hecho(hid: int, accion: str, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    if accion not in ("confirmar", "validar", "descartar", "no_relevante", "reabrir"):
        raise HTTPException(404, "Acción desconocida.")
    h = _de_asunto(db, m.EvHecho, hid, u)
    if h.documento_id:
        _exigir_visible(db, u, db.get(m.EvDocumento, h.documento_id))
    _cambiar_estado(db, u, request, h, accion)
    db.commit()
    return hecho_dict(h, _nombres(db, u.organizacion_id))


@router.post("/asuntos/{aid}/hechos/{accion}")
def estado_varios(aid: int, accion: str, d: Ids, request: Request, u: m.Usuario = Depends(puede_editar),
                  db: Session = Depends(get_db)):
    """Validar o descartar varias propuestas seleccionadas por la persona que revisa."""
    if accion not in ("confirmar", "validar", "descartar", "no_relevante"):
        raise HTTPException(404, "Acción desconocida.")
    a = _asunto(db, aid, u)
    hechos = db.scalars(select(m.EvHecho).where(m.EvHecho.id.in_(d.ids), m.EvHecho.asunto_id == a.id,
                                                m.EvHecho.organizacion_id == u.organizacion_id)).all()
    if len(hechos) != len(set(d.ids)):
        raise HTTPException(404, "Algún hecho no existe en este asunto.")
    sin_fuente = [h.id for h in hechos if accion in ("confirmar", "validar") and not h.documento_id]
    if sin_fuente:
        raise HTTPException(409, f"{len(sin_fuente)} hecho(s) no tienen documento fuente y no pueden confirmarse.")
    for h in hechos:
        _cambiar_estado(db, u, request, h, accion)
    db.commit()
    return {"ok": True, "n": len(hechos)}


class Par(BaseModel):
    par: str = Field(pattern=r"^\d+-\d+$")


class Decision(BaseModel):
    par: str = Field(pattern=r"^\d+-\d+$")
    decision: str | None = None  # None = volver a «pendiente»
    nota: str | None = Field(None, max_length=1000)


def _decidir(db: Session, u: m.Usuario, request: Request, a: m.EvAsunto, par: str, decision: str | None, nota: str | None):
    if decision is not None and decision not in analisis.DECISIONES:
        raise HTTPException(422, "Decisión inválida.")
    ids = {int(x) for x in par.split("-")}
    if db.scalar(select(func.count()).select_from(m.EvHecho).where(m.EvHecho.id.in_(ids), m.EvHecho.asunto_id == a.id)) != 2:
        raise HTTPException(404, "Esa pareja de hechos no pertenece a este asunto.")
    decisiones = dict(a.decisiones_diferencias or {})
    antes = (decisiones.get(par) or {}).get("decision") or ("no_aplica" if par in (a.contradicciones_descartadas or []) else None)
    a.contradicciones_descartadas = [x for x in (a.contradicciones_descartadas or []) if x != par] or None
    if decision is None:
        decisiones.pop(par, None)
    else:
        decisiones[par] = {"decision": decision, "por": u.id, "en": m.ahora().isoformat(), "nota": _txt(nota, 1000)}
    a.decisiones_diferencias = decisiones
    auditar(db, u, "ev_diferencia_decidida" if decision else "ev_diferencia_reabierta", "ev_asunto", a.id,
            {"par": par, "antes": antes, "decision": decision, "nota": _txt(nota, 300)}, request)
    db.commit()


@router.post("/asuntos/{aid}/diferencias")
def decidir_diferencia(aid: int, d: Decision, request: Request, u: m.Usuario = Depends(puede_editar),
                       db: Session = Depends(get_db)):
    """El abogado decide sobre una posible diferencia: «Son eventos distintos», «Diferencia aclarada»,
    «Contradicción confirmada» o «No aplica». No modifica ninguno de los hechos ni la matriz."""
    _decidir(db, u, request, _asunto(db, aid, u), d.par, d.decision, d.nota)
    return {"ok": True}


@router.post("/asuntos/{aid}/contradicciones/{accion}")
def contradiccion(aid: int, accion: str, d: Par, request: Request, u: m.Usuario = Depends(puede_editar),
                  db: Session = Depends(get_db)):
    """Compatibilidad con la versión anterior de la pantalla."""
    mapa = {"confirmar": "contradiccion", "descartar": "no_aplica", "revisada": "no_aplica", "reabrir": None}
    if accion not in mapa:
        raise HTTPException(404, "Acción desconocida.")
    _decidir(db, u, request, _asunto(db, aid, u), d.par, mapa[accion], None)
    return {"ok": True}


ACCIONES_HISTORIAL = {
    "ev_hecho_capturado": "Capturado manualmente", "ev_hecho_editado": "Editado por una persona",
    "ev_hecho_confirmado": "Confirmado por una persona", "ev_hecho_descartado": "Descartado",
    "ev_hecho_no_relevante": "Descartado: no relevante para este asunto", "ev_hecho_reabierto": "Devuelto a revisión",
}


@router.get("/hechos/{hid}/historial")
def historial_hecho(hid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Quién hizo cada cambio a un hecho (de la auditoría), empezando por su origen."""
    h = _de_asunto(db, m.EvHecho, hid, u)
    regs = db.scalars(select(m.Auditoria).where(m.Auditoria.organizacion_id == u.organizacion_id, m.Auditoria.entidad == "ev_hecho",
                                                m.Auditoria.entidad_id == h.id).order_by(m.Auditoria.id)).all()
    salida = []
    if h.origen == "automatico":
        salida.append({"fecha": h.creado_en.isoformat(), "accion": "Propuesto automáticamente por Nomira", "usuario": None,
                       "detalle": h.original})
    nombres = _nombres(db, u.organizacion_id)
    for r in regs:
        salida.append({"fecha": r.fecha.isoformat(), "accion": ACCIONES_HISTORIAL.get(r.accion, r.accion),
                       "usuario": nombres.get(r.usuario_id) or r.usuario_email, "detalle": {k: v for k, v in (r.detalle or {}).items() if k != "asunto_id"}})
    return salida


ACCIONES_ASUNTO = {
    "ev_asunto_creado": "Creó el asunto", "ev_asunto_modificado": "Modificó los datos del asunto",
    "ev_documento_cargado": "Cargó un documento", "ev_documento_clasificado": "Clasificó un documento",
    "ev_documento_visibilidad": "Cambió la visibilidad de un documento", "ev_documento_releido": "Pidió volver a leer un documento",
    "ev_documento_eliminado": "Eliminó un documento", "ev_documento_recibido_cliente": "El cliente envió un documento",
    "ev_documento_aceptado": "Aceptó un documento del cliente", "ev_documento_rechazado": "Rechazó un documento del cliente",
    "ev_hecho_capturado": "Capturó un hecho", "ev_hecho_editado": "Editó un hecho", "ev_hecho_confirmado": "Confirmó un hecho",
    "ev_hecho_descartado": "Descartó un hecho", "ev_hecho_no_relevante": "Marcó un hecho como no relevante",
    "ev_hecho_reabierto": "Devolvió un hecho a revisión", "ev_diferencia_decidida": "Decidió sobre una posible diferencia",
    "ev_diferencia_reabierta": "Reabrió una posible diferencia", "ev_contradiccion_revisada": "Revisó una posible contradicción",
    "ev_punto_creado": "Agregó un punto a la matriz", "ev_punto_estado": "Decidió el estado de un punto",
    "ev_punto_eliminado": "Quitó un punto de la matriz", "ev_vinculo_agregado": "Vinculó evidencia a un punto",
    "ev_vinculo_relacion": "Evaluó una fuente de la matriz", "ev_vinculo_eliminado": "Quitó evidencia de un punto",
    "ev_pendiente_creado": "Agregó un pendiente", "ev_pendiente_modificado": "Modificó un pendiente",
    "ev_pendiente_eliminado": "Eliminó un pendiente", "ev_solicitud_creada": "Solicitó documentos al cliente",
    "ev_solicitud_revocada": "Revocó un enlace de solicitud", "ev_solicitud_abierta": "El cliente abrió el enlace",
    "ev_solicitud_codigo_enviado": "Se envió un código al cliente", "ev_solicitud_verificada": "El cliente verificó su correo",
    "ev_exportacion_pdf": "Exportó a PDF", "ev_exportacion_excel": "Exportó a Excel",
    "ev_exportacion_pdf_pendientes": "Exportó la lista de pendientes (PDF)", "ev_exportacion_excel_pendientes": "Exportó la lista de pendientes (Excel)",
    "ev_documento_descargado": "Descargó un original",
}
_DETALLE_VISIBLE = ("decision", "antes", "despues", "campos", "nota", "email", "dias", "tipo", "visibilidad", "relacion", "par")


@router.get("/asuntos/{aid}/historial")
def historial_asunto(aid: int, limite: int = 300, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Quién hizo qué en el asunto y cuándo (de la auditoría). Nunca incluye tokens ni contenido de documentos."""
    a = _asunto(db, aid, u)
    q = select(m.Auditoria).where(m.Auditoria.organizacion_id == u.organizacion_id, m.Auditoria.accion.like("ev_%"),
                                  ((m.Auditoria.entidad == "ev_asunto") & (m.Auditoria.entidad_id == a.id))
                                  | (m.Auditoria.detalle["asunto_id"].as_integer() == a.id)).order_by(m.Auditoria.id.desc())
    nombres = _nombres(db, u.organizacion_id)
    return [{"fecha": r.fecha.isoformat(), "accion": ACCIONES_ASUNTO.get(r.accion, r.accion), "codigo": r.accion,
             "usuario": nombres.get(r.usuario_id) or r.usuario_email or ("Cliente (enlace)" if "solicitud" in r.accion or "cliente" in r.accion else "Nomira"),
             "entidad": r.entidad, "entidad_id": r.entidad_id,
             "detalle": {k: v for k, v in (r.detalle or {}).items() if k in _DETALLE_VISIBLE}}
            for r in db.scalars(q.limit(min(max(limite, 1), 1000)))]


@router.get("/asuntos/{aid}/buscar")
def buscar(aid: int, q: str, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Búsqueda de texto (sin distinguir acentos ni mayúsculas) en lo que Nomira leyó de los documentos
    del asunto que el usuario puede ver. Cada resultado indica documento, página y fragmento."""
    a = _asunto(db, aid, u)
    termino = normalizar(" ".join(q.split()))[:100]
    if len(termino) < 2:
        raise HTTPException(422, "Escriba al menos 2 caracteres.")
    docs = {d.id: d for d in db.scalars(select(m.EvDocumento).where(m.EvDocumento.asunto_id == a.id)) if puede_ver(u, a, d)}
    res, total = [], 0
    filas = db.execute(select(m.EvPagina.documento_id, m.EvPagina.numero, m.EvPagina.texto).where(
        m.EvPagina.documento_id.in_(list(docs) or [0])).order_by(m.EvPagina.documento_id, m.EvPagina.numero))
    for did, numero, texto in filas:
        plano = normalizar(texto or "")
        pos = plano.find(termino)
        if pos < 0:
            continue
        n = plano.count(termino)
        total += n
        if len(res) < 200:
            ini, fin = max(pos - 90, 0), min(pos + len(termino) + 90, len(texto))
            antes, despues = texto[ini:pos], texto[pos + len(termino):fin]
            res.append({"documento_id": did, "documento": docs[did].nombre_original, "pagina": numero, "coincidencias": n,
                        "antes": ("…" if ini else "") + " ".join(antes.split()) + (" " if antes[-1:].isspace() else ""),
                        "coincidencia": texto[pos:pos + len(termino)],
                        "despues": (" " if despues[:1].isspace() else "") + " ".join(despues.split()) + ("…" if fin < len(texto) else "")})
    return {"termino": q, "resultados": res, "total": total,
            "aviso": None if docs else "No hay documentos leídos en este asunto."}


@router.get("/documentos/{a_id}/comparar/{b_id}")
def comparar(a_id: int, b_id: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Compara el texto leído de dos documentos del mismo asunto (línea por línea). Ambos originales se
    conservan; esto no indica cuál es la versión vigente."""
    import difflib

    da, dbb = _de_asunto(db, m.EvDocumento, a_id, u), _de_asunto(db, m.EvDocumento, b_id, u)
    if da.asunto_id != dbb.asunto_id:
        raise HTTPException(422, "Solo se comparan documentos del mismo asunto.")
    _exigir_visible(db, u, da), _exigir_visible(db, u, dbb)

    def lineas(d: m.EvDocumento) -> list[str]:
        txt = db.scalars(select(m.EvPagina.texto).where(m.EvPagina.documento_id == d.id).order_by(m.EvPagina.numero)).all()
        return [ln.strip() for t in txt for ln in (t or "").splitlines() if ln.strip()][:3000]

    la, lb = lineas(da), lineas(dbb)
    if not la or not lb:
        raise HTTPException(409, "Ambos documentos deben estar leídos para compararlos.")
    salida = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=la, b=lb, autojunk=False).get_opcodes():
        if op == "equal":
            salida += [{"tipo": "igual", "texto": t} for t in la[i1:i2]]
        else:
            salida += [{"tipo": "solo_a", "texto": t} for t in la[i1:i2]] + [{"tipo": "solo_b", "texto": t} for t in lb[j1:j2]]
    reciente = da if da.creado_en >= dbb.creado_en else dbb
    return {"a": {"id": da.id, "nombre": da.nombre_original, "creado_en": da.creado_en.isoformat()},
            "b": {"id": dbb.id, "nombre": dbb.nombre_original, "creado_en": dbb.creado_en.isoformat()},
            "mas_reciente_id": reciente.id, "lineas": salida[:4000],
            "cambios": sum(1 for x in salida if x["tipo"] != "igual")}


# ---------- matriz de evidencia ----------

class PuntoIn(BaseModel):
    descripcion: str = Field(min_length=3, max_length=2000)
    notas: str | None = Field(None, max_length=3000)


class PuntoCambio(BaseModel):
    descripcion: str | None = Field(None, min_length=3, max_length=2000)
    notas: str | None = Field(None, max_length=3000)
    estado: str | None = None


class VinculoIn(BaseModel):
    relacion: str = "sin_evaluar"
    hecho_id: int | None = None
    documento_id: int | None = None
    pagina: int | None = Field(None, ge=1, le=10000)
    nota: str | None = Field(None, max_length=500)


def _punto_dict(db: Session, p: m.EvPunto, u: m.Usuario) -> dict:
    a = db.get(m.EvAsunto, p.asunto_id)
    return next(x for x in panel(db, a, u)["puntos"] if x["id"] == p.id)


@router.post("/asuntos/{aid}/puntos", status_code=201)
def crear_punto(aid: int, d: PuntoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _asunto(db, aid, u)
    orden = (db.scalar(select(func.max(m.EvPunto.orden)).where(m.EvPunto.asunto_id == a.id)) or 0) + 1
    p = m.EvPunto(organizacion_id=u.organizacion_id, asunto_id=a.id, descripcion=d.descripcion.strip(),
                  notas=_txt(d.notas, 3000), orden=orden, creado_por_id=u.id)
    db.add(p)
    db.flush()
    auditar(db, u, "ev_punto_creado", "ev_punto", p.id, {"asunto_id": a.id}, request)
    db.commit()
    return _punto_dict(db, p, u)


@router.patch("/puntos/{pid}")
def cambiar_punto(pid: int, d: PuntoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _de_asunto(db, m.EvPunto, pid, u)
    datos = d.model_dump(exclude_unset=True)
    if datos.get("descripcion"):
        p.descripcion = datos["descripcion"].strip()
    if "notas" in datos:
        p.notas = _txt(datos["notas"], 3000)
    if datos.get("estado") and datos["estado"] != p.estado:
        if datos["estado"] not in ESTADOS_PUNTO:
            raise HTTPException(422, "Estado inválido.")
        auditar(db, u, "ev_punto_estado", "ev_punto", p.id, {"asunto_id": p.asunto_id, "antes": p.estado, "despues": datos["estado"]}, request)
        p.estado, p.estado_decidido_por_id, p.estado_decidido_en = datos["estado"], u.id, m.ahora()
    db.commit()
    return _punto_dict(db, p, u)


@router.delete("/puntos/{pid}")
def borrar_punto(pid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _de_asunto(db, m.EvPunto, pid, u)
    auditar(db, u, "ev_punto_eliminado", "ev_punto", p.id, {"asunto_id": p.asunto_id}, request)
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/puntos/{pid}/vinculos", status_code=201)
def vincular(pid: int, d: VinculoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _de_asunto(db, m.EvPunto, pid, u)
    a = db.get(m.EvAsunto, p.asunto_id)
    if d.hecho_id:
        h = _de_asunto(db, m.EvHecho, d.hecho_id, u)
        if h.asunto_id != a.id:
            raise HTTPException(422, "El hecho debe pertenecer a este asunto.")
        if h.estado not in analisis.REVISADOS or not h.documento_id:
            raise HTTPException(409, "Solo pueden vincularse hechos confirmados por una persona y con documento fuente.")
        doc_id, pagina = h.documento_id, h.pagina
    elif d.documento_id:
        doc_id, pagina = _fuente(db, a, d.documento_id, d.pagina, u)
    else:
        raise HTTPException(422, "Elija un hecho confirmado o un documento.")
    if any(v.hecho_id == d.hecho_id and v.documento_id == doc_id and v.pagina == pagina for v in p.vinculos):
        raise HTTPException(409, "Esa evidencia ya está vinculada a este punto.")
    if d.relacion not in RELACIONES:
        raise HTTPException(422, "Relación inválida.")
    _exigir_visible(db, u, db.get(m.EvDocumento, doc_id))
    v = m.EvVinculo(punto_id=p.id, hecho_id=d.hecho_id, documento_id=doc_id, pagina=pagina, nota=_txt(d.nota, 500),
                    relacion=d.relacion, creado_por_id=u.id)
    if d.relacion != "sin_evaluar":
        v.relacion_por_id, v.relacion_en = u.id, m.ahora()
    db.add(v)
    db.flush()
    auditar(db, u, "ev_vinculo_agregado", "ev_punto", p.id, {"asunto_id": p.asunto_id, "hecho_id": d.hecho_id, "documento_id": doc_id, "relacion": d.relacion}, request)
    db.commit()
    db.refresh(p)
    return _punto_dict(db, p, u)


class RelacionIn(BaseModel):
    relacion: str


@router.patch("/vinculos/{vid}")
def evaluar_vinculo(vid: int, d: RelacionIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """El abogado indica si esta fuente apoya, contradice o no basta para el punto. Nomira no lo decide."""
    v = db.get(m.EvVinculo, vid)
    if not v:
        raise HTTPException(404, "No encontrado.")
    p = _de_asunto(db, m.EvPunto, v.punto_id, u)
    if d.relacion not in RELACIONES:
        raise HTTPException(422, "Relación inválida.")
    auditar(db, u, "ev_vinculo_relacion", "ev_punto", p.id, {"asunto_id": p.asunto_id, "antes": v.relacion, "relacion": d.relacion}, request)
    v.relacion, v.relacion_por_id, v.relacion_en = d.relacion, u.id, m.ahora()
    db.commit()
    db.refresh(p)
    return _punto_dict(db, p, u)


@router.delete("/vinculos/{vid}")
def desvincular(vid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    v = db.get(m.EvVinculo, vid)
    if not v:
        raise HTTPException(404, "No encontrado.")
    p = _de_asunto(db, m.EvPunto, v.punto_id, u)
    auditar(db, u, "ev_vinculo_eliminado", "ev_punto", p.id, {"asunto_id": p.asunto_id, "documento_id": v.documento_id}, request)
    db.delete(v)
    db.commit()
    db.refresh(p)
    return _punto_dict(db, p, u)


# ---------- pendientes ----------

class PendienteIn(BaseModel):
    descripcion: str = Field(min_length=3, max_length=2000)
    responsable: str | None = Field(None, max_length=200)
    fecha_seguimiento: date | None = None
    estado: str = "pendiente"
    nota: str | None = Field(None, max_length=3000)


class PendienteCambio(BaseModel):
    descripcion: str | None = Field(None, min_length=3, max_length=2000)
    responsable: str | None = Field(None, max_length=200)
    fecha_seguimiento: date | None = None
    estado: str | None = None
    nota: str | None = Field(None, max_length=3000)


@router.post("/asuntos/{aid}/pendientes", status_code=201)
def crear_pendiente(aid: int, d: PendienteIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _asunto(db, aid, u)
    if d.estado not in ESTADOS_PENDIENTE:
        raise HTTPException(422, "Estado inválido.")
    x = m.EvPendiente(organizacion_id=u.organizacion_id, asunto_id=a.id, descripcion=d.descripcion.strip(),
                      responsable=_txt(d.responsable, 200), fecha_seguimiento=d.fecha_seguimiento, estado=d.estado,
                      nota=_txt(d.nota, 3000), creado_por_id=u.id)
    db.add(x)
    db.flush()
    auditar(db, u, "ev_pendiente_creado", "ev_pendiente", x.id, {"asunto_id": a.id}, request)
    db.commit()
    return pendiente_dict(x)


@router.patch("/pendientes/{xid}")
def cambiar_pendiente(xid: int, d: PendienteCambio, request: Request, u: m.Usuario = Depends(puede_editar),
                      db: Session = Depends(get_db)):
    x = _de_asunto(db, m.EvPendiente, xid, u)
    datos = d.model_dump(exclude_unset=True)
    if "estado" in datos and datos["estado"] not in ESTADOS_PENDIENTE:
        raise HTTPException(422, "Estado inválido.")
    for k, v in datos.items():
        if k == "descripcion":
            if not v:
                continue
            v = v.strip()
        elif k in ("responsable", "nota"):
            v = _txt(v, 200 if k == "responsable" else 3000)
        setattr(x, k, v)
    auditar(db, u, "ev_pendiente_modificado", "ev_pendiente", x.id, {"asunto_id": x.asunto_id, "campos": list(datos)}, request)
    db.commit()
    return pendiente_dict(x)


@router.delete("/pendientes/{xid}")
def borrar_pendiente(xid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _de_asunto(db, m.EvPendiente, xid, u)
    auditar(db, u, "ev_pendiente_eliminado", "ev_pendiente", x.id, {"asunto_id": x.asunto_id}, request)
    db.delete(x)
    db.commit()
    return {"ok": True}


# ---------- exportación ----------

@router.get("/asuntos/{aid}/exportar/{formato}")
def exportar(aid: int, formato: str, request: Request, solo: str | None = None,
             u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """formato: pdf | excel. Con ?solo=pendientes genera la lista para compartir con el cliente
    (sin notas internas)."""
    if formato not in ("pdf", "excel") or solo not in (None, "pendientes"):
        raise HTTPException(404, "Formato desconocido.")
    a = _asunto(db, aid, u)
    datos = panel(db, a, u)
    org = db.get(m.Organizacion, u.organizacion_id)
    meta = {"organizacion": org.nombre, "logo": org.logo, "generado_por": u.nombre, "generado_por_email": u.email,
            "generado_en": m.ahora()}
    auditar(db, u, f"ev_exportacion_{formato}" + ("_pendientes" if solo else ""), "ev_asunto", a.id, request=request)
    db.commit()
    if formato == "pdf":
        cuerpo = reporte.pdf_pendientes(datos, meta) if solo else reporte.pdf(datos, meta)
        tipo, ext = "application/pdf", "pdf"
    else:
        cuerpo = reporte.excel(datos, meta, solo_pendientes=bool(solo))
        tipo, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    nombre = f"evidencia-{a.id}-{'pendientes' if solo else 'expediente'}.{ext}"
    return Response(cuerpo, media_type=tipo, headers={**PRIVADO, "Content-Disposition": f'attachment; filename="{nombre}"',
                                                      "Access-Control-Expose-Headers": "Content-Disposition"})
