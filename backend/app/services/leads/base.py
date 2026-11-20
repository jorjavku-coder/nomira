"""Utilidades de Nomira Leads: configuración, etapas, teléfonos y alta de prospectos desde
cualquier fuente (manual, formulario, WhatsApp, anuncios de Meta u otros sistemas)."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from . import catalogos as cat

_ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def huella(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def token_publico() -> str:
    return secrets.token_urlsafe(18)


def codigo() -> str:
    return "".join(secrets.choice(_ALFABETO) for _ in range(6))


def telefono(v: str | None) -> str | None:
    """Solo dígitos; los números mexicanos de 10 dígitos se guardan con el 52 del país."""
    d = re.sub(r"\D", "", v or "")
    if not d:
        return None
    if len(d) == 10:
        d = "52" + d
    if len(d) == 13 and d.startswith("521"):  # formato anterior de móviles en México
        d = "52" + d[3:]
    if not 10 <= len(d) <= 15:
        from fastapi import HTTPException
        raise HTTPException(422, "El teléfono no parece válido: escriba 10 dígitos o el número con lada de país.")
    return d


def enmascarar_tel(t: str | None) -> str | None:
    return f"•••• •• {t[-4:]}" if t else None


def enmascarar_email(e: str | None) -> str | None:
    if not e or "@" not in e:
        return None
    u, d = e.split("@", 1)
    return f"{u[:1]}•••@{d}"


def config(db: Session, org_id: int) -> m.LdConfig:
    c = db.scalar(select(m.LdConfig).where(m.LdConfig.organizacion_id == org_id))
    if c is None:
        c = m.LdConfig(organizacion_id=org_id, dias_sin_actividad=7, formulario_token=token_publico(), formulario_activo=True,
                       wa_plantilla_idioma="es_MX")
        db.add(c)
        db.flush()
    return c


def materias(cfg: m.LdConfig) -> list[str]:
    return cfg.materias or cat.MATERIAS_DEFECTO


def motivos(cfg: m.LdConfig) -> list[str]:
    return cfg.motivos_perdida or cat.MOTIVOS_DEFECTO


def etapas(db: Session, org_id: int, todas: bool = False) -> list[m.LdEtapa]:
    q = select(m.LdEtapa).where(m.LdEtapa.organizacion_id == org_id)
    xs = db.scalars(q.order_by(m.LdEtapa.orden, m.LdEtapa.id)).all()
    if not xs:
        for i, (clave, nombre, tipo) in enumerate(cat.ETAPAS_DEFECTO):
            db.add(m.LdEtapa(organizacion_id=org_id, clave=clave, nombre=nombre, tipo=tipo, orden=i, archivada=False))
        db.flush()
        xs = db.scalars(q.order_by(m.LdEtapa.orden, m.LdEtapa.id)).all()
    return [x for x in xs if todas or not x.archivada]


def etapa_inicial(db: Session, org_id: int) -> m.LdEtapa:
    return next(e for e in etapas(db, org_id) if e.tipo == "abierta")


def etapa_tipo(db: Session, org_id: int, tipo: str) -> m.LdEtapa:
    return next(e for e in etapas(db, org_id, todas=True) if e.tipo == tipo)


def actividad(db: Session, p: m.LdProspecto, tipo: str, texto: str | None, usuario: m.Usuario | None = None, **detalle) -> None:
    db.add(m.LdActividad(organizacion_id=p.organizacion_id, prospecto_id=p.id, tipo=tipo, texto=texto, detalle=detalle or None,
                         usuario_id=usuario.id if usuario else None))
    p.ultima_actividad_en = m.ahora()


def consentir(db: Session, p: m.LdProspecto, canales: list[str], medio: str, usuario: m.Usuario | None = None,
              finalidad: str = cat.FINALIDAD) -> None:
    activos = {c.canal for c in db.scalars(select(m.LdConsentimiento).where(m.LdConsentimiento.prospecto_id == p.id,
                                                                           m.LdConsentimiento.revocado_en.is_(None)))}
    for canal in canales:
        if canal in cat.CANALES_CONSENTIMIENTO and canal not in activos:
            db.add(m.LdConsentimiento(organizacion_id=p.organizacion_id, prospecto_id=p.id, canal=canal, finalidad=finalidad[:300],
                                      medio=medio, registrado_por_id=usuario.id if usuario else None))


def consiente(db: Session, prospecto_id: int, canal: str) -> bool:
    return bool(db.scalar(select(m.LdConsentimiento.id).where(m.LdConsentimiento.prospecto_id == prospecto_id, m.LdConsentimiento.canal == canal,
                                                             m.LdConsentimiento.revocado_en.is_(None))))


def campana_por_codigo(db: Session, org_id: int, texto: str | None) -> m.LdCampana | None:
    """Busca un código de campaña (p. ej. «ref: K7M2QX») o el nombre exacto de una campaña."""
    if not texto:
        return None
    t = texto.strip()
    for cod in re.findall(r"\b[A-HJ-NP-Z2-9]{6}\b", t.upper()):
        c = db.scalar(select(m.LdCampana).where(m.LdCampana.organizacion_id == org_id, m.LdCampana.codigo == cod))
        if c:
            return c
    return db.scalar(select(m.LdCampana).where(m.LdCampana.organizacion_id == org_id, m.LdCampana.nombre == t[:160]))


def existente(db: Session, org_id: int, tel: str | None, email: str | None) -> m.LdProspecto | None:
    """Un prospecto ABIERTO con el mismo teléfono o correo (solo si hay uno: si hay varios, no se adivina)."""
    if not tel and not email:
        return None
    abiertas = [e.id for e in etapas(db, org_id, todas=True) if e.tipo == "abierta"]
    cands = db.scalars(select(m.LdProspecto).where(m.LdProspecto.organizacion_id == org_id, m.LdProspecto.etapa_id.in_(abiertas),
                                                  m.LdProspecto.anonimizado_en.is_(None))).all()
    hits = [p for p in cands if (tel and p.telefono and p.telefono[-10:] == tel[-10:]) or (email and p.email and p.email.lower() == email.lower())]
    return hits[0] if len(hits) == 1 else None


def alta_externa(db: Session, org_id: int, *, nombre: str | None, tel: str | None, email: str | None, ciudad: str | None = None,
                 materia: str | None = None, descripcion: str | None = None, canal: str = "otro", campana: m.LdCampana | None = None,
                 entrada: str, origen: dict | None = None, consentimiento: list[str] | None = None, medio: str = "formulario_web",
                 preferencia: str | None = None) -> tuple[m.LdProspecto, bool]:
    """Registra un prospecto que llegó solo. Si ya existe uno abierto con el mismo contacto, se agrega
    la nueva solicitud a su historial en lugar de duplicarlo. Devuelve (prospecto, es_nuevo)."""
    if campana and canal == "otro":
        canal = campana.canal
    canal = canal if canal in cat.CANALES else "otro"
    p = existente(db, org_id, tel, email)
    nuevo = p is None
    if nuevo:
        p = m.LdProspecto(organizacion_id=org_id, nombre=(nombre or "").strip()[:200] or "Sin nombre", telefono=tel, email=email,
                          ciudad=(ciudad or "")[:120] or None, materia=(materia or "")[:120] or None, descripcion=(descripcion or "")[:4000] or None,
                          canal=canal, campana_id=campana.id if campana else None, origen_detalle=origen or None, entrada=entrada,
                          etapa_id=etapa_inicial(db, org_id).id, borrador=False,
                          preferencia_contacto=preferencia if preferencia in cat.PREFERENCIAS else ("whatsapp" if tel else "correo"))
        db.add(p)
        db.flush()
        actividad(db, p, "alta", f"Llegó por {cat.CANALES.get(canal, canal)}" + (f" · campaña «{campana.nombre}»" if campana else ""),
                  entrada=entrada)
        # todo prospecto activo tiene un próximo paso: responder hoy (solo un recordatorio, no envía nada)
        db.add(m.LdAccion(organizacion_id=org_id, prospecto_id=p.id, tipo="mensaje" if tel else "seguimiento", fecha=hoy(),
                          descripcion="Responder la solicitud", recordatorio=True))
    else:
        actividad(db, p, "solicitud", (descripcion or "Volvió a escribir.")[:4000], entrada=entrada, canal=canal,
                  campana=campana.nombre if campana else None)
        p.email = p.email or email
        p.telefono = p.telefono or tel
    if consentimiento:
        consentir(db, p, consentimiento, medio)
    return p, nuevo


def proxima(db: Session, prospecto_id: int) -> m.LdAccion | None:
    return db.scalar(select(m.LdAccion).where(m.LdAccion.prospecto_id == prospecto_id, m.LdAccion.completada_en.is_(None),
                                             m.LdAccion.cancelada.is_(False)).order_by(m.LdAccion.fecha, m.LdAccion.hora, m.LdAccion.id))


def hoy() -> date:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Mexico_City")).date()
