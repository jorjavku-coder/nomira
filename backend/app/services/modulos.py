"""Módulos de Nomira por organización.

- «contratado»: lo decide quien opera la plataforma (panel de Soporte Nomira).
- «activo»: lo decide el administrador del despacho, solo entre los módulos contratados.
Sin registro en la tabla, se aplica el valor por defecto: así las cuentas que ya existían siguen
con Nómina y Prestaciones como hasta ahora. Desactivar un módulo oculta y protege sus rutas, pero
no borra ningún dato.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db

MODULOS = {
    "nomina": {"nombre": "Nómina y prestaciones", "descripcion": "Desglose de prestaciones por quincena a partir de comprobantes de nómina.",
               "por_defecto": True},
    "evidencia": {"nombre": "Nomira Evidencia", "descripcion": "Expediente probatorio: documentos, hechos con fuente, cronología, matriz de evidencia y pendientes.",
                  "por_defecto": False},
}


def estado(db: Session, organizacion_id: int) -> dict[str, dict]:
    filas = {f.modulo: f for f in db.scalars(select(m.OrganizacionModulo)
                                             .where(m.OrganizacionModulo.organizacion_id == organizacion_id))}
    res = {}
    for clave, info in MODULOS.items():
        f = filas.get(clave)
        contratado = f.contratado if f else info["por_defecto"]
        activo = (f.activo if f else info["por_defecto"]) and contratado
        res[clave] = {"clave": clave, "nombre": info["nombre"], "descripcion": info["descripcion"],
                      "contratado": contratado, "activo": activo}
    return res


def activos(db: Session, organizacion_id: int) -> list[str]:
    return [k for k, v in estado(db, organizacion_id).items() if v["activo"]]


def fijar(db: Session, organizacion_id: int, modulo: str, *, contratado: bool | None = None,
          activo: bool | None = None) -> dict:
    """Cambia un módulo. No hace commit. Valida que la organización conserve al menos uno activo."""
    if modulo not in MODULOS:
        raise HTTPException(422, "Módulo desconocido.")
    actual = estado(db, organizacion_id)
    f = db.scalar(select(m.OrganizacionModulo).where(m.OrganizacionModulo.organizacion_id == organizacion_id,
                                                     m.OrganizacionModulo.modulo == modulo))
    if f is None:
        f = m.OrganizacionModulo(organizacion_id=organizacion_id, modulo=modulo,
                                 contratado=actual[modulo]["contratado"], activo=actual[modulo]["activo"])
        db.add(f)
    if contratado is not None:
        f.contratado = contratado
        if not contratado:
            f.activo = False
        elif activo is None and not actual[modulo]["contratado"]:
            f.activo = True  # al contratarlo queda disponible de inmediato
    if activo is not None:
        if activo and not f.contratado:
            raise HTTPException(409, "Ese módulo no está contratado para su organización. Contacte a soporte de Nomira.")
        f.activo = activo
    db.flush()
    nuevo = estado(db, organizacion_id)
    if not any(v["activo"] for v in nuevo.values()):
        raise HTTPException(409, "La organización debe conservar al menos un módulo activo.")
    return nuevo


def requiere_modulo(modulo: str):
    """Dependencia de FastAPI: rechaza la petición si el módulo no está activo para la organización."""
    from ..deps import usuario_actual

    def dep(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)) -> m.Usuario:
        if not estado(db, u.organizacion_id)[modulo]["activo"]:
            raise HTTPException(403, f"El módulo «{MODULOS[modulo]['nombre']}» no está activo para su organización.")
        return u
    return dep
