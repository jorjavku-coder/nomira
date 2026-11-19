"""API de Nomira Evidencia. Todas las rutas exigen el módulo activo para la organización (vea main.py)
y toda lectura o escritura se filtra por la organización del usuario."""
from __future__ import annotations

import hashlib
import os
from datetime import date
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
from ..services.evidencia import analisis, reporte
from ..services.evidencia.lectura import TIPOS_DISPONIBLES, abrir, detectar_formato
from ..services.evidencia.procesamiento import procesar_en_segundo_plano

router = APIRouter(prefix="/api/evidencia", tags=["Nomira Evidencia"])
PRIVADO = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
EXT = {"pdf": "pdf", "png": "png", "jpeg": "jpg", "webp": "webp"}
MIME = {"pdf": "application/pdf", "png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}
ESTADOS_HECHO = {"por_revisar": "Por revisar", "confirmado": "Confirmado", "editado": "Editado por usuario",
                 "descartado": "Descartado"}
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


def _nombres(db: Session, org_id: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org_id)).all())


def hecho_dict(h: m.EvHecho, nombres: dict[int, str] | None = None) -> dict:
    nombres = nombres or {}
    return {"id": h.id, "descripcion": h.descripcion, "fecha": h.fecha.isoformat() if h.fecha else None,
            "fecha_texto": h.fecha_texto, "personas": h.personas or [], "importe": str(h.importe) if h.importe is not None else None,
            "dato": h.dato, "documento_id": h.documento_id, "pagina": h.pagina, "fragmento": h.fragmento, "bbox": h.bbox,
            "confianza": h.confianza, "origen": h.origen, "estado": h.estado, "estado_texto": ESTADOS_HECHO[h.estado],
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
            "sha256": d.sha256, "hechos": (conteo or {}).get(d.id, 0)}


def panel(db: Session, a: m.EvAsunto) -> dict:
    """Todo lo que la pantalla del asunto necesita, calculado en un solo lugar (lo usa también la exportación)."""
    nombres = _nombres(db, a.organizacion_id)
    docs = db.scalars(select(m.EvDocumento).where(m.EvDocumento.asunto_id == a.id).order_by(m.EvDocumento.id)).all()
    hechos = db.scalars(select(m.EvHecho).where(m.EvHecho.asunto_id == a.id)
                        .order_by(m.EvHecho.fecha.nulls_last(), m.EvHecho.id)).all()
    puntos = db.scalars(select(m.EvPunto).where(m.EvPunto.asunto_id == a.id).order_by(m.EvPunto.orden, m.EvPunto.id)).all()
    pend = db.scalars(select(m.EvPendiente).where(m.EvPendiente.asunto_id == a.id)
                      .order_by(m.EvPendiente.fecha_seguimiento.nulls_last(), m.EvPendiente.id)).all()
    conteo = {}
    for h in hechos:
        if h.documento_id and h.estado != "descartado":
            conteo[h.documento_id] = conteo.get(h.documento_id, 0) + 1
    hs = [hecho_dict(h, nombres) for h in hechos]
    contra = analisis.contradicciones(hs, set(a.contradicciones_descartadas or []))
    en_conflicto = {i for c in contra for i in c["hechos"]}
    por_id = {h["id"]: h for h in hs}
    docs_d = [documento_dict(d, nombres, conteo) for d in docs]
    nombre_doc = {d["id"]: d["nombre"] for d in docs_d}
    puntos_d = []
    for p in puntos:
        vs = [{"id": v.id, "hecho_id": v.hecho_id, "documento_id": v.documento_id, "documento": nombre_doc.get(v.documento_id),
               "pagina": v.pagina, "nota": v.nota, "hecho": por_id.get(v.hecho_id)} for v in p.vinculos]
        puntos_d.append({"id": p.id, "descripcion": p.descripcion, "estado": p.estado, "estado_texto": ESTADOS_PUNTO[p.estado],
                         "estado_decidido_por": nombres.get(p.estado_decidido_por_id),
                         "estado_decidido_en": p.estado_decidido_en.isoformat() if p.estado_decidido_en else None,
                         "notas": p.notas, "vinculos": vs, "sugerencia": analisis.sugerir_estado_punto(vs, en_conflicto)})
    cuenta = {k: sum(1 for h in hs if h["estado"] == k) for k in ESTADOS_HECHO}
    return {
        "asunto": asunto_dict(a, nombres),
        "documentos": docs_d,
        "hechos": hs,
        "cronologia": analisis.cronologia(hs, contra),
        "contradicciones": contra,
        "puntos": puntos_d,
        "pendientes": [pendiente_dict(x) for x in pend],
        "resumen": {"documentos": len(docs), "documentos_por_revisar": sum(1 for d in docs if d.estado in ("requiere_revision", "error")),
                    "documentos_en_proceso": sum(1 for d in docs if d.estado in ("pendiente", "procesando")),
                    "documentos_sin_clasificar": sum(1 for d in docs if d.tipo is None and d.estado not in ("pendiente", "procesando")),
                    "hechos": cuenta, "contradicciones": len(contra),
                    "puntos": {k: sum(1 for p in puntos if p.estado == k) for k in ESTADOS_PUNTO},
                    "pendientes_abiertos": sum(1 for x in pend if x.estado in ("pendiente", "solicitado"))},
        "catalogos": {"tipos_documento": TIPOS_DISPONIBLES, "estados_hecho": ESTADOS_HECHO, "estados_punto": ESTADOS_PUNTO,
                      "estados_pendiente": ESTADOS_PENDIENTE},
    }


def asunto_dict(a: m.EvAsunto, nombres: dict[int, str]) -> dict:
    return {"id": a.id, "nombre": a.nombre, "cliente": a.cliente, "tipo_caso": a.tipo_caso, "jurisdiccion": a.jurisdiccion,
            "identificador_interno": a.identificador_interno, "responsable_id": a.responsable_id,
            "responsable": nombres.get(a.responsable_id), "notas": a.notas, "campos": a.campos or {},
            "creado_por": nombres.get(a.creado_por_id), "creado_en": a.creado_en.isoformat(),
            "actualizado_en": a.actualizado_en.isoformat()}


def pendiente_dict(x: m.EvPendiente) -> dict:
    return {"id": x.id, "descripcion": x.descripcion, "responsable": x.responsable,
            "fecha_seguimiento": x.fecha_seguimiento.isoformat() if x.fecha_seguimiento else None,
            "estado": x.estado, "estado_texto": ESTADOS_PENDIENTE[x.estado], "nota": x.nota,
            "vencido": bool(x.fecha_seguimiento and x.fecha_seguimiento < date.today() and x.estado in ("pendiente", "solicitado"))}


# ---------- asuntos ----------

class AsuntoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    cliente: str | None = Field(None, max_length=200)
    tipo_caso: str | None = Field(None, max_length=120)
    jurisdiccion: str | None = Field(None, max_length=160)
    identificador_interno: str | None = Field(None, max_length=80)
    responsable_id: int | None = None
    notas: str | None = Field(None, max_length=5000)
    campos: dict[str, str] | None = None


class AsuntoCambio(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=200)
    cliente: str | None = Field(None, max_length=200)
    tipo_caso: str | None = Field(None, max_length=120)
    jurisdiccion: str | None = Field(None, max_length=160)
    identificador_interno: str | None = Field(None, max_length=80)
    responsable_id: int | None = None
    notas: str | None = Field(None, max_length=5000)
    campos: dict[str, str] | None = None


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
    sin_ev = contar(m.EvPunto, m.EvPunto.estado == "pendiente_evidencia")
    nombres = _nombres(db, u.organizacion_id)
    return [{**asunto_dict(a, nombres), "documentos": docs.get(a.id, 0), "hechos_por_revisar": por_revisar.get(a.id, 0),
             "hechos_confirmados": confirmados.get(a.id, 0), "pendientes_abiertos": pend.get(a.id, 0),
             "puntos_sin_evidencia": sin_ev.get(a.id, 0)} for a in asuntos]


@router.post("/asuntos", status_code=201)
def crear(d: AsuntoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = m.EvAsunto(organizacion_id=u.organizacion_id, nombre=d.nombre.strip(), cliente=_txt(d.cliente, 200),
                   tipo_caso=_txt(d.tipo_caso, 120), jurisdiccion=_txt(d.jurisdiccion, 160),
                   identificador_interno=_txt(d.identificador_interno, 80),
                   responsable_id=_responsable(db, d.responsable_id, u), notas=_txt(d.notas, 5000),
                   campos=_campos(d.campos), creado_por_id=u.id)
    db.add(a)
    db.flush()
    auditar(db, u, "ev_asunto_creado", "ev_asunto", a.id, request=request)
    db.commit()
    return asunto_dict(a, _nombres(db, u.organizacion_id))


@router.get("/asuntos/{aid}")
def ver(aid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return panel(db, _asunto(db, aid, u))


@router.patch("/asuntos/{aid}")
def cambiar(aid: int, d: AsuntoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _asunto(db, aid, u)
    datos = d.model_dump(exclude_unset=True)
    limites = {"nombre": 200, "cliente": 200, "tipo_caso": 120, "jurisdiccion": 160, "identificador_interno": 80, "notas": 5000}
    cambios = []
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
    antes = {"tipo": doc.tipo, "fecha": doc.fecha_documento.isoformat() if doc.fecha_documento else None}
    doc.tipo, doc.fecha_documento, doc.clasificado_por_id = d.tipo.strip(), d.fecha_documento, u.id
    auditar(db, u, "ev_documento_clasificado", "ev_documento", doc.id,
            {"antes": antes, "tipo": doc.tipo, "sugerido": doc.tipo_sugerido}, request)
    db.commit()
    return documento_dict(doc)


@router.post("/documentos/{did}/reprocesar")
def reprocesar(did: int, request: Request, tareas: BackgroundTasks, u: m.Usuario = Depends(puede_editar),
               db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    if doc.estado in ("pendiente", "procesando"):
        raise HTTPException(409, "El documento ya se está leyendo.")
    auditar(db, u, "ev_documento_releido", "ev_documento", doc.id, request=request)
    db.commit()
    tareas.add_task(procesar_en_segundo_plano, doc.id)
    return {"ok": True}


@router.delete("/documentos/{did}")
def borrar_documento(did: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
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
    auditar(db, u, "ev_documento_eliminado", "ev_documento", doc.id, {"sha256": doc.sha256}, request)
    db.delete(doc)
    db.commit()
    try:
        os.unlink(ruta)
    except OSError:
        pass
    return {"ok": True}


@router.get("/documentos/{did}/archivo")
def descargar(did: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    auditar(db, u, "ev_documento_descargado", "ev_documento", doc.id, request=request)
    db.commit()
    return Response(Path(doc.ruta).read_bytes(), media_type=MIME[doc.formato], headers={
        **PRIVADO, "Content-Disposition": f'attachment; filename="evidencia-{doc.id}.{EXT[doc.formato]}"'})


@router.get("/documentos/{did}/paginas/{numero}/imagen")
def imagen(did: int, numero: int, dpi: int = 110, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    doc = _de_asunto(db, m.EvDocumento, did, u)
    try:
        with abrir(doc.ruta, doc.formato) as pdf:
            if not 1 <= numero <= pdf.page_count:
                raise HTTPException(404, "Página inexistente.")
            pagina = pdf[numero - 1]
            png = pagina.get_pixmap(dpi=min(max(dpi, 50), 200)).tobytes("png")
            ancho, alto = pagina.rect.width, pagina.rect.height
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(409, "No se pudo mostrar el documento. Descargue el original.")
    return Response(png, media_type="image/png", headers={
        **PRIVADO, "X-Pagina-Ancho": f"{ancho:.2f}", "X-Pagina-Alto": f"{alto:.2f}", "X-Paginas": str(doc.num_paginas or 1),
        "Access-Control-Expose-Headers": "X-Pagina-Ancho, X-Pagina-Alto, X-Paginas"})


# ---------- hechos ----------

class HechoIn(BaseModel):
    descripcion: str = Field(min_length=3, max_length=2000)
    fecha: date | None = None
    personas: list[str] | None = None
    importe: str | None = Field(None, max_length=30)
    dato: str | None = Field(None, max_length=300)
    documento_id: int | None = None
    pagina: int | None = Field(None, ge=1, le=10000)
    fragmento: str | None = Field(None, max_length=2000)


class HechoCambio(BaseModel):
    descripcion: str | None = Field(None, min_length=3, max_length=2000)
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


def _personas(v: list[str] | None) -> list[str] | None:
    limpio = [p.strip()[:120] for p in (v or []) if p and p.strip()][:20]
    return limpio or None


@router.post("/asuntos/{aid}/hechos", status_code=201)
def crear_hecho(aid: int, d: HechoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Hecho capturado por una persona. Con documento fuente queda confirmado; sin fuente queda
    «por revisar» y no puede confirmarse hasta que se le asigne una."""
    a = _asunto(db, aid, u)
    doc_id, pagina = _fuente(db, a, d.documento_id, d.pagina, u)
    h = m.EvHecho(organizacion_id=u.organizacion_id, asunto_id=a.id, descripcion=d.descripcion.strip(), fecha=d.fecha,
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
    for k in ("descripcion", "fecha", "personas", "importe", "dato"):
        if k not in datos:
            continue
        v = datos[k]
        v = v.strip() if k == "descripcion" and v else _importe(v) if k == "importe" else _personas(v) if k == "personas" \
            else _txt(v, 300) if k == "dato" else v
        if k == "descripcion" and not v:
            continue
        if v != getattr(h, k):
            setattr(h, k, v)
            cambios.append(k)
    if not cambios:
        raise HTTPException(422, "No hay cambios que registrar.")
    # Lo editado por una persona cuenta como revisado, pero solo si conserva una fuente localizable.
    h.estado = "editado" if h.documento_id else "por_revisar"
    h.revisado_por_id, h.revisado_en = u.id, m.ahora()
    auditar(db, u, "ev_hecho_editado", "ev_hecho", h.id, {"asunto_id": h.asunto_id, "campos": cambios}, request)
    db.commit()
    return hecho_dict(h, _nombres(db, u.organizacion_id))


def _cambiar_estado(db: Session, u: m.Usuario, request: Request, h: m.EvHecho, accion: str) -> None:
    if accion == "confirmar":
        if not h.documento_id:
            raise HTTPException(409, "No puede confirmarse un hecho sin documento fuente. Asígnele uno o descártelo.")
        h.estado = "editado" if h.estado == "editado" else "confirmado"
    elif accion == "descartar":
        h.estado = "descartado"
    else:  # reabrir
        h.estado = "por_revisar"
    h.revisado_por_id, h.revisado_en = u.id, m.ahora()
    nombre = {"confirmar": "ev_hecho_confirmado", "descartar": "ev_hecho_descartado", "reabrir": "ev_hecho_reabierto"}[accion]
    auditar(db, u, nombre, "ev_hecho", h.id, {"asunto_id": h.asunto_id}, request)


@router.post("/hechos/{hid}/{accion}")
def estado_hecho(hid: int, accion: str, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    if accion not in ("confirmar", "descartar", "reabrir"):
        raise HTTPException(404, "Acción desconocida.")
    h = _de_asunto(db, m.EvHecho, hid, u)
    _cambiar_estado(db, u, request, h, accion)
    db.commit()
    return hecho_dict(h, _nombres(db, u.organizacion_id))


@router.post("/asuntos/{aid}/hechos/{accion}")
def estado_varios(aid: int, accion: str, d: Ids, request: Request, u: m.Usuario = Depends(puede_editar),
                  db: Session = Depends(get_db)):
    """Confirmar o descartar varios hechos seleccionados por la persona que revisa."""
    if accion not in ("confirmar", "descartar"):
        raise HTTPException(404, "Acción desconocida.")
    a = _asunto(db, aid, u)
    hechos = db.scalars(select(m.EvHecho).where(m.EvHecho.id.in_(d.ids), m.EvHecho.asunto_id == a.id,
                                                m.EvHecho.organizacion_id == u.organizacion_id)).all()
    if len(hechos) != len(set(d.ids)):
        raise HTTPException(404, "Algún hecho no existe en este asunto.")
    sin_fuente = [h.id for h in hechos if accion == "confirmar" and not h.documento_id]
    if sin_fuente:
        raise HTTPException(409, f"{len(sin_fuente)} hecho(s) no tienen documento fuente y no pueden confirmarse.")
    for h in hechos:
        _cambiar_estado(db, u, request, h, accion)
    db.commit()
    return {"ok": True, "n": len(hechos)}


class Par(BaseModel):
    par: str = Field(pattern=r"^\d+-\d+$")


@router.post("/asuntos/{aid}/contradicciones/revisada")
def contradiccion_revisada(aid: int, d: Par, request: Request, u: m.Usuario = Depends(puede_editar),
                           db: Session = Depends(get_db)):
    """La persona revisó el par y decidió que no es una contradicción relevante. No cambia los hechos."""
    a = _asunto(db, aid, u)
    a.contradicciones_descartadas = sorted(set(a.contradicciones_descartadas or []) | {d.par})
    auditar(db, u, "ev_contradiccion_revisada", "ev_asunto", a.id, {"par": d.par}, request)
    db.commit()
    return {"ok": True}


# ---------- matriz de evidencia ----------

class PuntoIn(BaseModel):
    descripcion: str = Field(min_length=3, max_length=2000)
    notas: str | None = Field(None, max_length=3000)


class PuntoCambio(BaseModel):
    descripcion: str | None = Field(None, min_length=3, max_length=2000)
    notas: str | None = Field(None, max_length=3000)
    estado: str | None = None


class VinculoIn(BaseModel):
    hecho_id: int | None = None
    documento_id: int | None = None
    pagina: int | None = Field(None, ge=1, le=10000)
    nota: str | None = Field(None, max_length=500)


def _punto_dict(db: Session, p: m.EvPunto) -> dict:
    a = db.get(m.EvAsunto, p.asunto_id)
    return next(x for x in panel(db, a)["puntos"] if x["id"] == p.id)


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
    return _punto_dict(db, p)


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
        auditar(db, u, "ev_punto_estado", "ev_punto", p.id, {"antes": p.estado, "despues": datos["estado"]}, request)
        p.estado, p.estado_decidido_por_id, p.estado_decidido_en = datos["estado"], u.id, m.ahora()
    db.commit()
    return _punto_dict(db, p)


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
    v = m.EvVinculo(punto_id=p.id, hecho_id=d.hecho_id, documento_id=doc_id, pagina=pagina, nota=_txt(d.nota, 500),
                    creado_por_id=u.id)
    db.add(v)
    db.flush()
    auditar(db, u, "ev_vinculo_agregado", "ev_punto", p.id, {"hecho_id": d.hecho_id, "documento_id": doc_id}, request)
    db.commit()
    db.refresh(p)
    return _punto_dict(db, p)


@router.delete("/vinculos/{vid}")
def desvincular(vid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    v = db.get(m.EvVinculo, vid)
    if not v:
        raise HTTPException(404, "No encontrado.")
    p = _de_asunto(db, m.EvPunto, v.punto_id, u)
    auditar(db, u, "ev_vinculo_eliminado", "ev_punto", p.id, {"documento_id": v.documento_id}, request)
    db.delete(v)
    db.commit()
    db.refresh(p)
    return _punto_dict(db, p)


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
    auditar(db, u, "ev_pendiente_modificado", "ev_pendiente", x.id, {"campos": list(datos)}, request)
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
    datos = panel(db, a)
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
