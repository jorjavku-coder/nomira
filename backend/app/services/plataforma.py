"""Operaciones de quien opera Nomira sobre las cuentas de sus clientes.

Nada aquí lee el contenido de expedientes, recibos ni documentos: solo se cuentan o, al
eliminar una cuenta, se borran completos.
"""
from __future__ import annotations

import logging
import secrets
import shutil
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..security import hash_contrasena

log = logging.getLogger("nomira.plataforma")
_LETRAS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin caracteres ambiguos


def contrasena_temporal() -> str:
    """Fácil de dictar por teléfono: Nomira-xxxx-xxxx-xxxx (≈71 bits)."""
    bloques = ["".join(secrets.choice(_LETRAS) for _ in range(4)) for _ in range(3)]
    return "Nomira-" + "-".join(bloques)


def eliminar_organizacion(db: Session, org: m.Organizacion) -> int:
    """Borra la organización y TODO lo suyo: expedientes, PDF, catálogos, usuarios, soporte y
    auditoría. No se puede deshacer. Devuelve cuántos expedientes se borraron. No hace commit:
    lo hace quien llama, y los archivos se borran con borrar_archivos() después del commit."""
    oid = org.id
    n = db.query(m.Expediente).filter(m.Expediente.organizacion_id == oid).count()
    db.execute(delete(m.TicketSoporte).where(m.TicketSoporte.organizacion_id == oid))  # mensajes: CASCADE
    db.execute(delete(m.PeriodoSuscripcion).where(m.PeriodoSuscripcion.organizacion_id == oid))
    # Nomira AFORE: mensajes, casos (requisitos, documentos, cronología, plazos: CASCADE), accesos y clientes
    for modelo in (m.AfMensaje, m.AfCaso, m.AfAcceso, m.AfConsentimiento, m.AfCliente, m.AfPlantilla, m.AfConfig):
        db.execute(delete(modelo).where(modelo.organizacion_id == oid))
    # Nomira Leads y Nomira Academia
    for modelo in (m.LdMensaje, m.LdProspecto, m.LdCampana, m.LdEtapa, m.LdConfig, m.AcSesion, m.AcAsignacion, m.AcAvance,
                   m.AcInstructor, m.AcEquipo):
        db.execute(delete(modelo).where(modelo.organizacion_id == oid))
    for c in db.scalars(select(m.AcCurso.id).where(m.AcCurso.organizacion_id == oid)).all():
        db.execute(delete(m.AcCurso).where(m.AcCurso.id == c))  # módulos, lecciones y preguntas: CASCADE
    db.execute(delete(m.EvAsunto).where(m.EvAsunto.organizacion_id == oid))  # documentos, hechos, matriz, pendientes: CASCADE
    db.execute(delete(m.OrganizacionModulo).where(m.OrganizacionModulo.organizacion_id == oid))
    db.execute(delete(m.Correccion).where(m.Correccion.organizacion_id == oid))
    db.execute(delete(m.Recibo).where(m.Recibo.organizacion_id == oid))  # filas: CASCADE
    db.execute(delete(m.Documento).where(m.Documento.organizacion_id == oid))  # páginas: CASCADE
    db.execute(delete(m.Expediente).where(m.Expediente.organizacion_id == oid))
    db.execute(delete(m.CatalogoVersion).where(m.CatalogoVersion.organizacion_id == oid))  # entradas: CASCADE
    db.execute(delete(m.Catalogo).where(m.Catalogo.organizacion_id == oid))
    db.execute(delete(m.Auditoria).where(m.Auditoria.organizacion_id == oid))
    db.execute(delete(m.Usuario).where(m.Usuario.organizacion_id == oid))
    db.execute(delete(m.Organizacion).where(m.Organizacion.id == oid))
    db.expire_all()
    return n


def borrar_archivos(organizacion_id: int) -> None:
    shutil.rmtree(Path(ajustes().storage_dir) / str(organizacion_id), ignore_errors=True)


def asegurar_admin_inicial(db: Session) -> None:
    """Crea el primer administrador de la plataforma con PLATAFORMA_ADMIN_EMAIL/CONTRASENA si
    todavía no existe ese correo. Nunca cambia la contraseña de una cuenta que ya existe."""
    email = ajustes().plataforma_admin_email.strip().lower()
    contrasena = ajustes().plataforma_admin_contrasena
    if not email:
        return
    if db.scalar(select(m.AdminPlataforma.id).where(m.AdminPlataforma.email == email)):
        return
    if len(contrasena) < 12:
        log.warning("PLATAFORMA_ADMIN_CONTRASENA debe tener al menos 12 caracteres: no se creó el administrador.")
        return
    db.add(m.AdminPlataforma(email=email, nombre="Administrador de Nomira", hash_contrasena=hash_contrasena(contrasena),
                             rol="superadministrador"))
    db.commit()
    log.info("Se creó el administrador de la plataforma %s.", email)
