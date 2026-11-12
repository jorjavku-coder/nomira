from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, obtener, puede_editar
from ..services import ia_adaptador
from ..services.verificacion_ia import verificar_en_segundo_plano
from .documentos import expediente_editable

router = APIRouter(prefix="/api", tags=["IA opcional"])


@router.post("/filas/{fid}/sugerencia-ia")
def sugerencia(fid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Propone una relectura. NO modifica nada: aplicar la sugerencia exige una corrección humana."""
    if not ajustes().ia_habilitada:
        raise HTTPException(404, "El respaldo de IA está deshabilitado en esta instalación.")
    f = db.get(m.Fila, fid)
    if not f:
        raise HTTPException(404, "No encontrado.")
    r = obtener(db, m.Recibo, f.recibo_id, u)
    pag = db.scalar(select(m.Pagina).where(m.Pagina.documento_id == r.documento_id,
                                           m.Pagina.numero == r.pagina_numero))
    auditar(db, u, "ia_consulta_externa", "fila", f.id, {"modelo": ajustes().ia_modelo,
                                                         "nota": "se envió el texto de una página"}, request)
    db.commit()
    try:
        s = ia_adaptador.sugerir_fila(pag.texto if pag else "", f.tipo, f.orden,
                                      {"clave": f.clave_leida, "importe": f.importe_leido_texto})
    except Exception as e:
        raise HTTPException(502, f"El servicio de IA no respondió de forma válida ({type(e).__name__}).")
    if s is None:
        return {"sugerencia": None}
    return {"sugerencia": s.model_dump(), "aviso": "Sugerencia sin validar. Compárela con el original antes de aplicarla."}


@router.post("/expedientes/{eid}/verificar-ia")
def verificar(eid: int, request: Request, tareas: BackgroundTasks, u: m.Usuario = Depends(puede_editar),
              db: Session = Depends(get_db)):
    """Lanza la segunda lectura con IA de todos los recibos. Envía la IMAGEN de cada recibo al
    proveedor de IA configurado; por eso exige activación explícita y queda en auditoría."""
    if not ajustes().ia_habilitada:
        raise HTTPException(404, "La verificación con IA está deshabilitada en esta instalación.")
    exp = expediente_editable(db, eid, u)
    if (exp.verificacion_ia or {}).get("estado") == "en_curso":
        raise HTTPException(409, "Ya hay una verificación en curso.")
    n = db.scalar(select(func.count()).select_from(m.Recibo).where(m.Recibo.expediente_id == exp.id))
    if not n:
        raise HTTPException(409, "El expediente no tiene recibos procesados.")
    exp.verificacion_ia = {"estado": "en_curso", "total": n, "hechos": 0, "modelo": ajustes().ia_modelo, "error": None}
    auditar(db, u, "ia_verificacion_iniciada", "expediente", exp.id,
            {"recibos": n, "modelo": ajustes().ia_modelo, "nota": "se envían imágenes de recibos a un servicio externo"}, request)
    db.commit()
    tareas.add_task(verificar_en_segundo_plano, exp.id)
    return exp.verificacion_ia
