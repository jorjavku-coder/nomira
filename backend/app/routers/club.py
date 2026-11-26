"""Club Nomira para los usuarios de los despachos: beneficios vigentes, credencial digital y canje."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import usuario_actual
from ..services.club import base as cb

router = APIRouter(prefix="/api/club", tags=["Club Nomira"])


def _b(b: m.AlBeneficio, a: m.AlAliado, con_canje: bool = False) -> dict:
    d = {"id": b.id, "titulo": b.titulo, "resumen": b.resumen, "descripcion": b.descripcion, "categoria": b.categoria,
         "categoria_texto": cb.CATEGORIAS.get(b.categoria, b.categoria), "canje": b.canje, "canje_texto": cb.CANJES.get(b.canje, b.canje),
         "condiciones": b.condiciones, "cobertura": b.cobertura, "vigente_hasta": b.vigente_hasta.isoformat() if b.vigente_hasta else None,
         "destacado": b.destacado, "aliado": {"id": a.id, "nombre": a.nombre, "giro": a.giro, "sitio": a.sitio, "logo": bool(a.logo_actualizado)}}
    if con_canje:
        d["codigo"], d["enlace"] = b.codigo, b.enlace
    return d


@router.get("")
def club(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = cb.credencial(db, u)
    o = db.get(m.Organizacion, u.organizacion_id)
    vig = cb.miembro_vigente(db, u)
    db.commit()
    return {"beneficios": [_b(b, a) for b, a in cb.visibles(db)], "categorias": cb.CATEGORIAS,
            "credencial": {"codigo": c.codigo, "nombre": u.nombre, "despacho": o.nombre, "vigente": vig,
                           "verificar": ajustes().url_publica.rstrip("/") + f"/club/verificar/{c.codigo}"}}


class Uso(BaseModel):
    tipo: str  # vista | canje


@router.post("/beneficios/{bid}/uso")
def uso(bid: int, d: Uso, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Registra la vista o el canje y, al canjear, entrega el código o el enlace (solo a miembros vigentes)."""
    if d.tipo not in ("vista", "canje"):
        raise HTTPException(422, "Tipo no válido.")
    par = next(((b, a) for b, a in cb.visibles(db) if b.id == bid), None)
    if not par:
        raise HTTPException(404, "Este beneficio ya no está disponible.")
    b, a = par
    if d.tipo == "canje" and not cb.miembro_vigente(db, u):
        raise HTTPException(403, "Los beneficios del Club están disponibles con un plan vigente de Nomira.")
    cb.registrar_uso(db, b, u, d.tipo)
    db.commit()
    return _b(b, a, con_canje=d.tipo == "canje")
