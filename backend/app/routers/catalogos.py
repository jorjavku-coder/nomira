import hashlib
import os
import re
import tempfile
from collections import Counter

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


class Lote(BaseModel):
    entradas: list[EntradaIn] = Field(min_length=1, max_length=500)


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
         "entradas_total": len(v.entradas), "por_revisar": sum(1 for e in v.entradas if e.requiere_revision),
         "agregadas_manual": sum(1 for e in v.entradas if e.agregada_manual)}
    if con_entradas:
        d["entradas"] = [{"id": e.id, "clave": e.clave, "descripcion": e.descripcion, "activo": e.activo,
                          "confianza": e.confianza, "requiere_revision": e.requiere_revision, "nota": e.nota,
                          "pagina": e.pagina, "agregada_manual": e.agregada_manual}
                         for e in sorted(v.entradas, key=lambda e: (e.agregada_manual, e.pagina or 0, e.clave, e.id))]
    return d


def _expedientes_por_actualizar(db: Session, v: m.CatalogoVersion) -> list[m.Expediente]:
    """Expedientes sin validar que usan OTRA versión de este mismo catálogo."""
    otras = [x.id for x in v.catalogo.versiones if x.id != v.id]
    if not otras:
        return []
    return list(db.scalars(select(m.Expediente).where(
        m.Expediente.organizacion_id == v.organizacion_id, m.Expediente.catalogo_version_id.in_(otras),
        m.Expediente.estado != "validado")))


def _siguiente(db: Session, catalogo_id: int) -> int:
    return (db.scalar(select(func.max(m.CatalogoVersion.numero)).where(
        m.CatalogoVersion.catalogo_id == catalogo_id)) or 0) + 1


def _borrador(db: Session, vid: int, u: m.Usuario) -> m.CatalogoVersion:
    v = obtener(db, m.CatalogoVersion, vid, u)
    if v.estado != "borrador":
        raise HTTPException(409, "Una versión activa o archivada es inmutable. Cree una versión nueva para "
                                 "cambiar el catálogo.")
    return v


def _usos(db: Session, version_ids: list[int]) -> dict[int, int]:
    """Cuántos expedientes usan cada versión (una versión en uso no se puede eliminar)."""
    if not version_ids:
        return {}
    return dict(db.execute(select(m.Expediente.catalogo_version_id, func.count(m.Expediente.id))
                           .where(m.Expediente.catalogo_version_id.in_(version_ids))
                           .group_by(m.Expediente.catalogo_version_id)).all())


@router.get("")
def listar(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    cats = list(db.scalars(select(m.Catalogo).where(m.Catalogo.organizacion_id == u.organizacion_id)
                           .order_by(m.Catalogo.nombre)))
    usos = _usos(db, [v.id for c in cats for v in c.versiones])
    return [{"id": c.id, "nombre": c.nombre, "expedientes": sum(usos.get(v.id, 0) for v in c.versiones),
             "versiones": [{**_v(v), "expedientes": usos.get(v.id, 0)} for v in c.versiones]} for c in cats]


@router.get("/{cid}/expedientes")
def expedientes_que_lo_usan(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Expedientes que impiden eliminar el catálogo (para mostrarlos y poder ir a ellos)."""
    c = obtener(db, m.Catalogo, cid, u)
    ids = [v.id for v in c.versiones]
    filas = db.scalars(select(m.Expediente).where(m.Expediente.organizacion_id == u.organizacion_id,
                                                  m.Expediente.catalogo_version_id.in_(ids)).order_by(m.Expediente.id.desc())) if ids else []
    return [{"id": e.id, "nombre": e.trabajador_nombre, "estado": e.estado} for e in filas]


@router.delete("/{cid}")
def eliminar_catalogo(cid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Elimina el catálogo con todas sus versiones, SOLO si ningún expediente lo usa: un expediente
    calculado con un catálogo debe poder mostrar siempre con qué claves se calculó."""
    c = obtener(db, m.Catalogo, cid, u)
    n = sum(_usos(db, [v.id for v in c.versiones]).values())
    if n:
        raise HTTPException(409, f"No se puede eliminar: {n} expediente(s) usan este catálogo. "
                                 "Elimine esos expedientes o cámbielos a otro catálogo primero.")
    auditar(db, u, "catalogo_eliminado", "catalogo", c.id, {"nombre": c.nombre, "versiones": len(c.versiones)}, request)
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.delete("/versiones/{vid}")
def eliminar_version(vid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    v = obtener(db, m.CatalogoVersion, vid, u)
    n = _usos(db, [v.id]).get(v.id, 0)
    if n:
        raise HTTPException(409, f"No se puede eliminar: {n} expediente(s) usan esta versión.")
    cid = v.catalogo_id
    auditar(db, u, "catalogo_version_eliminada", "catalogo_version", v.id, {"numero": v.numero, "estado": v.estado}, request)
    db.delete(v)
    db.commit()
    return {"ok": True, "catalogo_id": cid}


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
                                                requiere_revision=e.requiere_revision, nota=e.nota, pagina=e.pagina,
                                                agregada_manual=e.agregada_manual))
    db.add(v)
    db.flush()
    auditar(db, u, "catalogo_version_creada", "catalogo_version", v.id, {"origen": v.origen}, request)
    db.commit()
    return _v(v, True)


@router.get("/versiones/{vid}")
def ver_version(vid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    v = obtener(db, m.CatalogoVersion, vid, u)
    d = _v(v, True)
    if v.estado == "borrador":
        d["expedientes_por_actualizar"] = len(_expedientes_por_actualizar(db, v))
    return d


@router.get("/versiones/{vid}/sugerencias")
def sugerencias(vid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Claves de percepción que ya aparecieron en recibos de la organización y NO están en esta
    versión: son las que el cálculo deja fuera por «no estar en el catálogo autorizado»."""
    v = obtener(db, m.CatalogoVersion, vid, u)
    presentes = {e.clave for e in v.entradas}
    filas = db.execute(
        select(m.Fila.clave, m.Fila.concepto, m.Recibo.expediente_id)
        .join(m.Recibo, m.Fila.recibo_id == m.Recibo.id)
        .join(m.Expediente, m.Recibo.expediente_id == m.Expediente.id)
        .where(m.Expediente.organizacion_id == u.organizacion_id, m.Fila.tipo == "percepcion",
               m.Fila.clave.is_not(None))).all()
    patron = re.compile(ajustes().clave_regex)
    grupos: dict[str, dict] = {}
    for clave, concepto, eid in filas:
        clave = clave.strip()
        if clave in presentes or not patron.match(clave):
            continue
        g = grupos.setdefault(clave, {"conceptos": Counter(), "expedientes": set(), "apariciones": 0})
        g["apariciones"] += 1
        g["expedientes"].add(eid)
        if concepto and concepto.strip():
            g["conceptos"][concepto.strip()] += 1
    salida = [{"clave": c, "descripcion": g["conceptos"].most_common(1)[0][0] if g["conceptos"] else "",
               "apariciones": g["apariciones"], "expedientes": len(g["expedientes"])} for c, g in grupos.items()]
    return sorted(salida, key=lambda s: (-s["expedientes"], -s["apariciones"], s["clave"]))[:200]


@router.post("/versiones/{vid}/entradas", status_code=201)
def agregar_entrada(vid: int, d: EntradaIn, request: Request, u: m.Usuario = Depends(solo_admin),
                    db: Session = Depends(get_db)):
    v = _borrador(db, vid, u)
    clave = _clave_valida(d.clave)
    if any(e.clave == clave for e in v.entradas):
        raise HTTPException(409, f"La clave {clave} ya existe en esta versión.")
    v.entradas.append(m.CatalogoEntrada(clave=clave, descripcion=d.descripcion.strip(), activo=d.activo,
                                        agregada_manual=True))
    auditar(db, u, "catalogo_entrada_agregada", "catalogo_version", v.id, {"clave": clave}, request)
    db.commit()
    return _v(v, True)


@router.post("/versiones/{vid}/entradas/lote", status_code=201)
def agregar_lote(vid: int, d: Lote, request: Request, u: m.Usuario = Depends(solo_admin),
                 db: Session = Depends(get_db)):
    """Claves faltantes de una sola vez. Todo o nada: si alguna fila tiene un problema no se guarda
    ninguna y se dice cuál. Las que ya están en el catálogo se omiten (no es un error)."""
    v = _borrador(db, vid, u)
    existentes = {e.clave for e in v.entradas}
    patron = re.compile(ajustes().clave_regex)
    nuevas, omitidas, errores, en_lote = [], [], [], set()
    for i, e in enumerate(d.entradas, start=1):
        clave, desc = e.clave.strip(), e.descripcion.strip()
        if not patron.match(clave):
            errores.append(f"fila {i}: la clave «{clave}» no tiene el formato esperado (4 dígitos)")
        elif not desc:
            errores.append(f"fila {i}: falta la descripción de la clave {clave}")
        elif clave in en_lote:
            errores.append(f"fila {i}: la clave {clave} está repetida en la lista")
        elif clave in existentes:
            omitidas.append(clave)
        else:
            nuevas.append((clave, desc[:400], e.activo))
        en_lote.add(clave)
    if errores:
        raise HTTPException(422, "No se guardó nada. Corrija: " + "; ".join(errores[:8])
                            + (f" (y {len(errores) - 8} más)" if len(errores) > 8 else "") + ".")
    for clave, desc, activo in nuevas:
        v.entradas.append(m.CatalogoEntrada(clave=clave, descripcion=desc, activo=activo, agregada_manual=True))
    auditar(db, u, "catalogo_claves_faltantes_agregadas", "catalogo_version", v.id,
            {"claves": [c for c, _, _ in nuevas], "omitidas": omitidas}, request)
    db.commit()
    return {**_v(v, True), "agregadas": [c for c, _, _ in nuevas], "omitidas": omitidas}


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
    # Pasa a esta versión los expedientes SIN validar que usan otra versión de este catálogo,
    # para que se recalculen con las claves nuevas. Los validados nunca cambian.
    actualizar_expedientes: bool = False


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
    actualizados = []
    if d.actualizar_expedientes:
        for e in _expedientes_por_actualizar(db, v):
            auditar(db, u, "expediente_modificado", "expediente", e.id,
                    {"catalogo_version_id": [e.catalogo_version_id, v.id], "motivo": "activación de catálogo"}, request)
            e.catalogo_version_id = v.id
            actualizados.append(e.id)
    auditar(db, u, "catalogo_version_activada", "catalogo_version", v.id,
            {"entradas": len(v.entradas), "agregadas_manual": sum(e.agregada_manual for e in v.entradas),
             "expedientes_actualizados": actualizados}, request)
    db.commit()
    return {**_v(v, True), "expedientes_actualizados": len(actualizados)}
