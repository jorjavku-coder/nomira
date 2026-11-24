"""Panel de la plataforma: estado de la biblioteca de tesis, sincronizar ahora y cargar archivos oficiales de la SCJN."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import SessionLocal, get_db
from ..services.tesis import base as tb, repositorio as rp
from .plataforma import _registrar, admin_plataforma

router = APIRouter(prefix="/api/plataforma/tesis", tags=["Plataforma — Tesis"])


def _estado(db: Session) -> dict:
    e = rp.estado(db)
    por_origen = dict(db.execute(select(m.JTesis.origen, func.count()).group_by(m.JTesis.origen)).all())
    return {"total": tb.total(db), "por_origen": por_origen, "estado": e.estado, "mensaje": e.mensaje, "total_remoto": e.total_remoto,
            "pendientes": len(e.pendientes or []), "descargadas": e.descargadas, "omitidas": e.omitidas,
            "ultima_corrida": e.ultima_corrida.isoformat() if e.ultima_corrida else None,
            "proximo_intento": e.proximo_intento.isoformat() if e.proximo_intento else None,
            "sincronizar": ajustes().tesis_sincronizar, "fuente": ajustes().tesis_repositorio_url, "epoca_minima": ajustes().tesis_epoca_minima}


@router.get("")
def estado(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    r = _estado(db)
    db.commit()
    return r


def _tanda() -> None:
    with SessionLocal() as db:
        rp.correr(db, maximo=100)


@router.post("/sincronizar")
def sincronizar(request: Request, tareas: BackgroundTasks, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    """Pide una tanda corta ahora (ignora la espera tras un error). Si la SCJN bloquea, solo se informa."""
    e = rp.estado(db)
    e.proximo_intento = None
    _registrar(db, a, "tesis_sincronizar", request)
    db.commit()
    tareas.add_task(_tanda)
    return {"ok": True}


@router.post("/importar")
async def importar(request: Request, archivo: UploadFile = File(...), a: m.AdminPlataforma = Depends(admin_plataforma),
                   db: Session = Depends(get_db)):
    contenido = await archivo.read(tb.MAX_IMPORTACION + 1)
    try:
        tesis, origen = tb.leer_archivo(archivo.filename or "", contenido)
    except tb.ArchivoNoValido as e:
        raise HTTPException(413, str(e))
    except Exception:
        raise HTTPException(422, "No se pudo leer el archivo. Suba el PDF semanal de tesis de la SCJN o archivos JSON del Repositorio.")
    if not tesis:
        raise HTTPException(422, "No encontramos tesis en el archivo (cada una debe traer su «Registro digital»).")
    n = tb.guardar(db, tesis, origen, archivo.filename)
    _registrar(db, a, "tesis_importadas", request, detalle={"archivo": (archivo.filename or "")[:120], "tesis": n, "origen": origen})
    db.commit()
    return {"importadas": n, "origen": origen, "ejemplos": [{"registro": t["registro"], "rubro": t["rubro"][:160]} for t in tesis[:5]],
            **_estado(db)}
