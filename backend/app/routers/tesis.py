"""Buscador de tesis del Semanario Judicial de la Federación para todos los despachos (biblioteca común)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import usuario_actual
from ..services.tesis import base as tb, repositorio as rp

router = APIRouter(prefix="/api/tesis", tags=["Tesis del SJF"])


@router.get("")
def buscar(q: str = "", tipo: str | None = None, epoca: str | None = None, instancia: str | None = None, pagina: int = 1,
           u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    pagina = max(1, min(pagina, 50))
    filas, n = tb.buscar(db, q, tipo, epoca, instancia, limite=20, desde=(pagina - 1) * 20)
    e = rp.estado(db)
    db.commit()
    return {"resultados": [tb.a_dict(t, completo=False) for t in filas], "total": n, "pagina": pagina, "en_biblioteca": tb.total(db),
            "sincronizacion": e.estado, "actualizada": e.ultima_corrida.isoformat() if e.ultima_corrida else None}


@router.get("/{registro}")
def ver(registro: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    t = db.get(m.JTesis, registro)
    if not t:
        raise HTTPException(404, "Esa tesis no está en la biblioteca de Nomira. Consúltela en el Semanario Judicial de la Federación.")
    return tb.a_dict(t)


@router.get("/{registro}/pdf")
def pdf(registro: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    t = db.get(m.JTesis, registro)
    if not t:
        raise HTTPException(404, "Tesis no encontrada.")
    return Response(tb.ficha_pdf(t), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="tesis-{registro}.pdf"'})
