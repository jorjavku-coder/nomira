import hashlib
import os
import re
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, obtener, puede_editar, solo_admin, usuario_actual
from ..services.catalogo_ocr import extraer_catalogo
from .documentos import leer_pdf_subido

router = APIRouter(prefix="/api/catalogos", tags=["catálogos"])


class CatalogoNuevo(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)


class EntradaIn(BaseModel):
    clave: str = Field(min_length=1, max_length=12)
    descripcion: str = Field(min_length=1, max_length=400)
    activo: bool = True


class EntradaCambio(BaseModel):
    clave: str | None = Field(None, min_length=1, max_length=12)
    descripcion: str | None = Field(None, min_length=1, max_length=400)
    activo: bool | None = None
    revisada: bool | None = None


class VersionNueva(BaseModel):
    copiar_de_version_id: int | None = None
    notas: str | None = None


def _clave_valida(clave: str) -> str:
    clave = clave.strip()
    if not re.match(ajustes().clave_regex, clave):
        raise HTTPException(422, f"La clave «{clave}» no cumple el formato esperado (4 dígitos, como texto).")
    return clave


def _v(v: m.CatalogoVersion, con_entradas=False) -> dict:
    d = {"id": v.id, "catalogo_id": v.catalogo_id, "catalogo": v.catalogo.nombre, "numero": v.numero,
         "estado": v.estado, "origen": v.origen, "archivo_nombre": v.archivo_nombre, "notas": v.notas,
         "creado_en": v.creado_en.isoformat(), "validado_en": v.validado_en.isoformat() if v.validado_en else None,
         "entradas_total": len(v.entradas), "por_revisar": sum(1 for e in v.entradas if e.requiere_revision)}
    if con_entradas:
        d["entradas"] = [{"id": e.id, "clave": e.clave, "descripcion": e.descripcion, "activo": e.activo,
                          "confianza": e.confianza, "requiere_revision": e.requiere_revision, "nota": e.nota,
                          "pagina": e.pagina} for e in sorted(v.entradas, key=lambda e: (e.pagina or 0, e.clave, e.id))]
    return d


def _siguiente(db: Session, catalogo_id: int) -> int:
    return (db.scalar(select(func.max(m.CatalogoVersion.numero)).where(
        m.CatalogoVersion.catalogo_id == catalogo_id)) or 0) + 1


def _borrador(db: Session, vid: int, u: m.Usuario) -> m.CatalogoVersion:
    v = obtener(db, m.CatalogoVersion, vid, u)
    if v.estado != "borrador":
        raise HTTPException(409, "Una versión activa o archivada es inmutable. Cree una versión nueva para "
                                 "cambiar el catálogo.")
    return v


@router.get("")
def listar(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    cats = db.scalars(select(m.Catalogo).where(m.Catalogo.organizacion_id == u.organizacion_id)
                      .order_by(m.Catalogo.nombre))
    return [{"id": c.id, "nombre": c.nombre, "versiones": [_v(v) for v in c.versiones]} for c in cats]


@router.post("", status_code=201)
def crear(d: CatalogoNuevo, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    c = m.Catalogo(organizacion_id=u.organizacion_id, nombre=d.nombre.strip())
    db.add(c)
    db.flush()
    auditar(db, u, "catalogo_creado", "catalogo", c.id, request=request)
    db.commit()
    return {"id": c.id, "nombre": c.nombre, "versiones": []}


@router.post("/{cid}/versiones/ocr", status_code=201)
def version_desde_pdf(cid: int, request: Request, archivo: UploadFile = File(...),
                      u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Lee el PDF del catálogo (OCR si es imagen) y crea un BORRADOR para validación humana."""
    c = obtener(db, m.Catalogo, cid, u)
    datos = leer_pdf_subido(archivo)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(datos)
    try:
        leidas = extraer_catalogo(tmp.name)
    except Exception as e:
        raise HTTPException(422, f"No se pudo leer el catálogo: {type(e).__name__}.")
    finally:
        os.unlink(tmp.name)
    if not leidas:
        raise HTTPException(422, "No se detectó ninguna clave en el documento.")
    v = m.CatalogoVersion(catalogo_id=c.id, organizacion_id=u.organizacion_id, numero=_siguiente(db, c.id),
                          origen="ocr", archivo_nombre=(archivo.filename or "catalogo.pdf")[:300],
                          archivo_sha256=hashlib.sha256(datos).hexdigest(), creado_por_id=u.id)
    vistas = set()
    for n, e in enumerate(leidas):
        clave = e.clave or f"?{n}"
        if clave in vistas:  # no se descarta: se conserva con marca para que decida una persona
            clave = f"{clave[:8]}~{n}"
        vistas.add(clave)
        v.entradas.append(m.CatalogoEntrada(clave=clave, descripcion=e.descripcion or "(sin descripción)",
                                            confianza=e.confianza, requiere_revision=e.requiere_revision,
                                            nota=e.nota, pagina=e.pagina))
    db.add(v)
    db.flush()
    auditar(db, u, "catalogo_version_ocr", "catalogo_version", v.id,
            {"entradas": len(leidas), "por_revisar": sum(e.requiere_revision for e in leidas)}, request)
    db.commit()
    return _v(v, True)


@router.post("/{cid}/versiones", status_code=201)
def version_nueva(cid: int, d: VersionNueva, request: Request, u: m.Usuario = Depends(solo_admin),
                  db: Session = Depends(get_db)):
    c = obtener(db, m.Catalogo, cid, u)
    v = m.CatalogoVersion(catalogo_id=c.id, organizacion_id=u.organizacion_id, numero=_siguiente(db, c.id),
                          origen="manual", notas=d.notas, creado_por_id=u.id)
    if d.copiar_de_version_id:
        base = obtener(db, m.CatalogoVersion, d.copiar_de_version_id, u)
        v.origen = "copia"
        v.notas = d.notas or f"Copia de la versión {base.numero}"
        for e in base.entradas:
            v.entradas.append(m.CatalogoEntrada(clave=e.clave, descripcion=e.descripcion, activo=e.activo,
                                                requiere_revision=e.requiere_revision, nota=e.nota, pagina=e.pagina))
    db.add(v)
    db.flush()
    auditar(db, u, "catalogo_version_creada", "catalogo_version", v.id, {"origen": v.origen}, request)
    db.commit()
    return _v(v, True)


@router.get("/versiones/{vid}")
def ver_version(vid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _v(obtener(db, m.CatalogoVersion, vid, u), True)


@router.post("/versiones/{vid}/entradas", status_code=201)
def agregar_entrada(vid: int, d: EntradaIn, request: Request, u: m.Usuario = Depends(solo_admin),
                    db: Session = Depends(get_db)):
    v = _borrador(db, vid, u)
    clave = _clave_valida(d.clave)
    if any(e.clave == clave for e in v.entradas):
        raise HTTPException(409, f"La clave {clave} ya existe en esta versión.")
    v.entradas.append(m.CatalogoEntrada(clave=clave, descripcion=d.descripcion.strip(), activo=d.activo))
    auditar(db, u, "catalogo_entrada_agregada", "catalogo_version", v.id, {"clave": clave}, request)
    db.commit()
    return _v(v, True)


@router.patch("/entradas/{eid}")
def cambiar_entrada(eid: int, d: EntradaCambio, request: Request, u: m.Usuario = Depends(solo_admin),
                    db: Session = Depends(get_db)):
    e = db.get(m.CatalogoEntrada, eid)
    if not e:
        raise HTTPException(404, "No encontrado.")
    v = _borrador(db, e.version_id, u)
    cambios = {}
    if d.clave is not None and d.clave.strip() != e.clave:
        clave = _clave_valida(d.clave)
        if any(x.clave == clave and x.id != e.id for x in v.entradas):
            raise HTTPException(409, f"La clave {clave} ya existe en esta versión.")
        cambios["clave"] = [e.clave, clave]
        e.clave = clave
    if d.descripcion is not None and d.descripcion.strip() != e.descripcion:
        cambios["descripcion"] = [e.descripcion, d.descripcion.strip()]
        e.descripcion = d.descripcion.strip()
    if d.activo is not None and d.activo != e.activo:
        cambios["activo"] = d.activo
        e.activo = d.activo
    if d.revisada:
        _clave_valida(e.clave)
        e.requiere_revision = False
        cambios["revisada"] = True
    auditar(db, u, "catalogo_entrada_modificada", "catalogo_version", v.id, {"clave": e.clave, **cambios}, request)
    db.commit()
    return _v(v, True)


@router.delete("/entradas/{eid}")
def borrar_entrada(eid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    e = db.get(m.CatalogoEntrada, eid)
    if not e:
        raise HTTPException(404, "No encontrado.")
    v = _borrador(db, e.version_id, u)
    auditar(db, u, "catalogo_entrada_eliminada", "catalogo_version", v.id, {"clave": e.clave}, request)
    v.entradas.remove(e)
    db.commit()
    return _v(v, True)


class Activacion(BaseModel):
    confirmo_revision: bool


@router.post("/versiones/{vid}/activar")
def activar(vid: int, d: Activacion, request: Request, u: m.Usuario = Depends(solo_admin),
            db: Session = Depends(get_db)):
    """Validación humana: solo entonces la versión puede usarse en expedientes."""
    v = _borrador(db, vid, u)
    if not d.confirmo_revision:
        raise HTTPException(422, "Debe confirmar que revisó el catálogo contra el documento fuente.")
    if not v.entradas:
        raise HTTPException(409, "La versión no tiene entradas.")
    pend = [e.clave for e in v.entradas if e.requiere_revision]
    if pend:
        raise HTTPException(409, f"Hay {len(pend)} entrada(s) por revisar: {', '.join(pend[:10])}.")
    malas = [e.clave for e in v.entradas if not re.match(ajustes().clave_regex, e.clave)]
    if malas:
        raise HTTPException(409, f"Claves con formato inválido: {', '.join(malas[:10])}.")
    for otra in v.catalogo.versiones:
        if otra.estado == "activo":
            otra.estado = "archivado"  # sigue ligada a sus expedientes; nada cambia para ellos
    v.estado = "activo"
    v.validado_por_id = u.id
    v.validado_en = m.ahora()
    auditar(db, u, "catalogo_version_activada", "catalogo_version", v.id, {"entradas": len(v.entradas)}, request)
    db.commit()
    return _v(v, True)
