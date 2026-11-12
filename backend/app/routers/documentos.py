import hashlib
import os
from pathlib import Path

import pymupdf
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, obtener, puede_editar, usuario_actual
from ..services.procesamiento import procesar_en_segundo_plano, recalcular_estado

router = APIRouter(prefix="/api", tags=["documentos"])
PRIVADO = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


def leer_pdf_subido(archivo: UploadFile) -> bytes:
    """Valida tipo y tamaño. No confía en la extensión ni en el Content-Type declarados."""
    limite = ajustes().max_mb_archivo * 1024 * 1024
    datos = archivo.file.read(limite + 1)
    if len(datos) > limite:
        raise HTTPException(413, f"El archivo excede {ajustes().max_mb_archivo} MB.")
    if not (archivo.filename or "").lower().endswith(".pdf") or not datos.startswith(b"%PDF-"):
        raise HTTPException(415, "Solo se aceptan archivos PDF.")
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
    return datos


def archivo_disponible(doc: m.Documento) -> Path:
    """Ruta del PDF original. En alojamientos con disco temporal (p. ej. la demo en Render) el
    archivo puede haberse perdido aunque el registro siga en la base: se informa con claridad."""
    ruta = Path(doc.ruta)
    if not ruta.is_file():
        raise HTTPException(410, "El archivo original ya no está disponible en el servidor. "
                                 "Elimine el documento y vuelva a cargarlo.")
    return ruta


def expediente_editable(db: Session, eid: int, u: m.Usuario) -> m.Expediente:
    exp = obtener(db, m.Expediente, eid, u)
    if exp.estado == "validado":
        raise HTTPException(409, "El expediente está validado. Reábralo para modificarlo.")
    return exp


def _doc(d: m.Documento, db: Session) -> dict:
    tipos = dict(db.execute(select(m.Pagina.tipo, func.count()).where(m.Pagina.documento_id == d.id)
                            .group_by(m.Pagina.tipo)).all())
    ocr = db.scalar(select(func.count()).select_from(m.Pagina).where(
        m.Pagina.documento_id == d.id, m.Pagina.metodo == "ocr"))
    return {"id": d.id, "nombre": d.nombre_original, "sha256": d.sha256, "tamano_bytes": d.tamano_bytes,
            "estado": d.estado, "error": d.error, "intentos": d.intentos, "paginas": d.num_paginas,
            "paginas_recibo": tipos.get("recibo", 0), "paginas_informativas": tipos.get("informativa", 0),
            "paginas_desconocidas": tipos.get("desconocida", 0), "paginas_ocr": ocr,
            "creado_en": d.creado_en.isoformat()}


@router.get("/expedientes/{eid}/documentos")
def listar(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    exp = obtener(db, m.Expediente, eid, u)
    return [_doc(d, db) for d in exp.documentos]


@router.post("/expedientes/{eid}/documentos", status_code=201)
def subir(eid: int, request: Request, tareas: BackgroundTasks, archivos: list[UploadFile] = File(...),
          u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    exp = expediente_editable(db, eid, u)
    if len(archivos) > 100:
        raise HTTPException(413, "Máximo 100 archivos por carga.")
    resultado = []
    for archivo in archivos:
        nombre = os.path.basename(archivo.filename or "documento.pdf")[:300]
        try:
            datos = leer_pdf_subido(archivo)
        except HTTPException as e:
            resultado.append({"nombre": nombre, "aceptado": False, "motivo": e.detail})
            continue
        sha = hashlib.sha256(datos).hexdigest()
        previo = db.scalar(select(m.Documento).where(m.Documento.expediente_id == exp.id, m.Documento.sha256 == sha))
        if previo:
            resultado.append({"nombre": nombre, "aceptado": False, "duplicado_de": previo.id,
                              "motivo": f"Archivo idéntico a «{previo.nombre_original}» (mismo SHA-256). No se cargó de nuevo."})
            continue
        carpeta = Path(ajustes().storage_dir) / str(u.organizacion_id) / str(exp.id)
        carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
        ruta = carpeta / f"{sha}.pdf"  # el nombre en disco nunca proviene del usuario
        ruta.write_bytes(datos)
        os.chmod(ruta, 0o600)
        d = m.Documento(organizacion_id=u.organizacion_id, expediente_id=exp.id, nombre_original=nombre, sha256=sha,
                        tamano_bytes=len(datos), ruta=str(ruta), subido_por_id=u.id)
        db.add(d)
        db.flush()
        auditar(db, u, "documento_cargado", "documento", d.id, {"sha256": sha, "bytes": len(datos)}, request)
        resultado.append({"nombre": nombre, "aceptado": True, "documento_id": d.id})
    recalcular_estado(db, exp)
    db.commit()
    for r in resultado:
        if r["aceptado"]:
            tareas.add_task(procesar_en_segundo_plano, r["documento_id"])
    return resultado


class Reintento(BaseModel):
    forzar: bool = False


@router.post("/documentos/{did}/reintentar")
def reintentar(did: int, d: Reintento, request: Request, tareas: BackgroundTasks,
               u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    doc = obtener(db, m.Documento, did, u)
    exp = expediente_editable(db, doc.expediente_id, u)
    if doc.estado in ("pendiente", "procesando"):
        raise HTTPException(409, "El documento ya está en proceso.")
    if doc.estado == "procesado":
        if not d.forzar:
            raise HTTPException(409, "El documento ya fue procesado. Use «forzar» para volver a leerlo.")
        hay = db.scalar(select(func.count()).select_from(m.Correccion).join(
            m.Recibo, m.Correccion.recibo_id == m.Recibo.id).where(m.Recibo.documento_id == doc.id))
        if hay:
            auditar(db, u, "reproceso_descarta_correcciones", "documento", doc.id, {"correcciones": hay}, request)
    doc.estado = "pendiente"
    doc.error = None
    recalcular_estado(db, exp)
    auditar(db, u, "documento_reintento", "documento", doc.id, {"forzar": d.forzar}, request)
    db.commit()
    tareas.add_task(procesar_en_segundo_plano, doc.id)
    return _doc(doc, db)


@router.delete("/documentos/{did}")
def eliminar(did: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    doc = obtener(db, m.Documento, did, u)
    exp = expediente_editable(db, doc.expediente_id, u)
    if doc.estado == "procesando":
        raise HTTPException(409, "Espere a que termine el procesamiento.")
    ruta = doc.ruta
    auditar(db, u, "documento_eliminado", "documento", doc.id, {"sha256": doc.sha256}, request)
    db.delete(doc)
    db.flush()
    recalcular_estado(db, exp)
    db.commit()
    try:
        os.unlink(ruta)
    except OSError:
        pass
    return {"ok": True}


@router.get("/documentos/{did}/archivo")
def descargar(did: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    doc = obtener(db, m.Documento, did, u)
    ruta = archivo_disponible(doc)
    auditar(db, u, "documento_descargado", "documento", doc.id, request=request)
    db.commit()
    # FileResponse lo envía por partes: no carga el PDF completo en memoria.
    return FileResponse(ruta, media_type="application/pdf", headers={
        **PRIVADO, "Content-Disposition": f'attachment; filename="documento-{doc.id}.pdf"'})


@router.get("/documentos/{did}/paginas/{numero}/imagen")
def imagen_pagina(did: int, numero: int, dpi: int = 110, u: m.Usuario = Depends(usuario_actual),
                  db: Session = Depends(get_db)):
    doc = obtener(db, m.Documento, did, u)
    with pymupdf.open(archivo_disponible(doc)) as pdf:
        if not 1 <= numero <= pdf.page_count:
            raise HTTPException(404, "Página inexistente.")
        pagina = pdf[numero - 1]
        png = pagina.get_pixmap(dpi=min(max(dpi, 50), 200)).tobytes("png")
        ancho, alto = pagina.rect.width, pagina.rect.height
    return Response(png, media_type="image/png", headers={
        **PRIVADO, "X-Pagina-Ancho": f"{ancho:.2f}", "X-Pagina-Alto": f"{alto:.2f}",
        "Access-Control-Expose-Headers": "X-Pagina-Ancho, X-Pagina-Alto"})


class Clasificacion(BaseModel):
    tipo: str
    motivo: str = Field(min_length=3, max_length=500)


@router.post("/documentos/{did}/paginas/{numero}/clasificar")
def clasificar(did: int, numero: int, d: Clasificacion, request: Request, u: m.Usuario = Depends(puede_editar),
               db: Session = Depends(get_db)):
    """Permite declarar «informativa» una página que no pudo clasificarse."""
    doc = obtener(db, m.Documento, did, u)
    expediente_editable(db, doc.expediente_id, u)
    if d.tipo != "informativa":
        raise HTTPException(422, "Solo puede marcarse como informativa.")
    pag = db.scalar(select(m.Pagina).where(m.Pagina.documento_id == doc.id, m.Pagina.numero == numero))
    if not pag or pag.tipo != "desconocida":
        raise HTTPException(409, "La página no está pendiente de clasificar.")
    pag.tipo = "informativa"
    db.add(m.Correccion(organizacion_id=u.organizacion_id, expediente_id=doc.expediente_id, entidad="pagina",
                        campo="tipo", valor_anterior="desconocida", valor_nuevo="informativa", motivo=d.motivo,
                        usuario_id=u.id, usuario_email=u.email,
                        referencia={"documento": doc.nombre_original, "pagina": numero}))
    auditar(db, u, "pagina_clasificada", "documento", doc.id, {"pagina": numero}, request)
    db.commit()
    return {"ok": True}
