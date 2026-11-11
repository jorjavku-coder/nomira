from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, obtener, puede_editar
from ..services import ia_adaptador

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
