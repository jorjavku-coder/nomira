"""Activa el Asistente IA en la organización de demostración (una sola vez). Sin IA configurada, la pantalla lo indica."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin or db.scalar(select(m.OrganizacionModulo.id).where(m.OrganizacionModulo.organizacion_id == admin.organizacion_id,
                                                                    m.OrganizacionModulo.modulo == "asistente")):
        return False
    modulos.fijar(db, admin.organizacion_id, "asistente", contratado=True, activo=True)
    db.commit()
    return True
