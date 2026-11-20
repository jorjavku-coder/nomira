"""Centro Legal: catálogo de documentos, versión vigente y aceptaciones pendientes.

Los textos NO se escriben aquí: los carga quien opera Nomira desde el panel, ya aprobados por el
responsable de Nomira y su abogado. Si un documento no tiene versión publicada, el sitio lo
muestra «en preparación» y no se pide aceptarlo."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m

# clave: (título, para quién, qué se registra al aceptarlo)
DOCUMENTOS: dict[str, dict] = {
    "terminos": {"titulo": "Términos y condiciones", "descripcion": "Condiciones de uso del servicio de Nomira.",
                 "evento": "aceptacion", "quien": "usuario"},
    "privacidad": {"titulo": "Aviso de privacidad", "descripcion": "Cómo trata Nomira los datos personales de los que es responsable.",
                   "evento": "lectura", "quien": "usuario"},
    "privacidad_simplificado": {"titulo": "Aviso de privacidad simplificado", "descripcion": "Versión breve que se muestra junto a los formularios.",
                                "evento": None, "quien": None},
    "cookies": {"titulo": "Cookies y tecnologías similares", "descripcion": "Qué guarda el sitio en su navegador y para qué.",
                "evento": None, "quien": None},
    "anexo_tratamiento": {"titulo": "Anexo de tratamiento de datos para despachos",
                          "descripcion": "Condiciones con las que Nomira trata, por cuenta de cada despacho, los datos de sus clientes.",
                          "evento": "aceptacion", "quien": "organizacion"},
    "subencargados": {"titulo": "Proveedores que tratan datos (subencargados)", "descripcion": "Lista de proveedores que participan en el servicio.",
                      "evento": None, "quien": None},
    "uso_aceptable": {"titulo": "Uso aceptable y seguridad", "descripcion": "Qué no se permite hacer en Nomira y cómo reportar un problema de seguridad.",
                      "evento": None, "quien": None},
    "anexo_ia": {"titulo": "Inteligencia artificial e integraciones",
                 "descripcion": "Qué información se envía a cada proveedor conectado y cómo deben revisarse las sugerencias de la IA.",
                 "evento": None, "quien": None},
}
EVENTOS = {"aceptacion": "Aceptó", "lectura": "Confirmó haber leído", "marketing_otorgado": "Aceptó recibir información comercial",
           "marketing_revocado": "Retiró su consentimiento para información comercial", "aviso_mostrado": "Se le mostró el aviso"}
TIPOS_ARCO = {"acceso": "Acceso", "rectificacion": "Rectificación", "cancelacion": "Cancelación", "oposicion": "Oposición",
              "revocacion": "Revocación del consentimiento", "limitacion": "Limitar el uso o la divulgación"}
RELACIONES = {"usuario": "Uso Nomira en mi trabajo (usuario de un despacho)", "cliente_despacho": "Soy cliente de un despacho que usa Nomira",
              "prospecto": "Pedí informes a Nomira", "otro": "Otro"}
ESTADOS_ARCO = {"recibida": "Recibida", "en_revision": "En revisión", "requiere_informacion": "Se pidió información o identificación",
                "remitida_al_despacho": "Remitida al despacho responsable", "atendida": "Atendida", "improcedente": "Improcedente"}
_LETRAS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def vigente(db: Session, documento: str) -> m.LgVersion | None:
    return db.scalar(select(m.LgVersion).where(m.LgVersion.documento == documento, m.LgVersion.estado == "publicada")
                     .order_by(m.LgVersion.publicado_en.desc(), m.LgVersion.id.desc()))


def publicadas(db: Session, documento: str) -> list[m.LgVersion]:
    return db.scalars(select(m.LgVersion).where(m.LgVersion.documento == documento, m.LgVersion.estado.in_(("publicada", "retirada")),
                                               m.LgVersion.publicado_en.is_not(None)).order_by(m.LgVersion.publicado_en.desc())).all()


def config(db: Session) -> m.LgConfig:
    c = db.scalar(select(m.LgConfig))
    if c is None:
        c = m.LgConfig(marketing_habilitado=False)
        db.add(c)
        db.flush()
    return c


def hace_falta(db: Session, documento: str, previa: m.LgEvento | None) -> m.LgVersion | None:
    """Versión vigente que hay que aceptar, o None. Si ya se aceptó una anterior, solo se pide otra vez
    cuando alguna versión publicada después se marcó como «requiere nueva aceptación»."""
    v = vigente(db, documento)
    if v is None:
        return None
    if previa is None:
        return v
    if previa.version_id == v.id:
        return None
    anterior = db.get(m.LgVersion, previa.version_id) if previa.version_id else None
    desde = anterior.publicado_en if anterior and anterior.publicado_en else previa.creado_en
    posteriores = [x for x in publicadas(db, documento) if x.publicado_en and x.publicado_en > desde]
    return v if any(x.requiere_aceptacion for x in posteriores) else None


def pendientes_usuario(db: Session, u: m.Usuario) -> list[m.LgVersion]:
    res = []
    for clave in ("terminos", "privacidad"):
        evento = DOCUMENTOS[clave]["evento"]
        previa = db.scalar(select(m.LgEvento).where(m.LgEvento.documento == clave, m.LgEvento.evento == evento,
                                                   m.LgEvento.usuario_id == u.id).order_by(m.LgEvento.creado_en.desc(), m.LgEvento.id.desc()))
        v = hace_falta(db, clave, previa)
        if v:
            res.append(v)
    return res


def anexo_pendiente(db: Session, organizacion_id: int) -> m.LgVersion | None:
    previa = db.scalar(select(m.LgEvento).where(m.LgEvento.documento == "anexo_tratamiento", m.LgEvento.evento == "aceptacion",
                                               m.LgEvento.organizacion_id == organizacion_id)
                       .order_by(m.LgEvento.creado_en.desc(), m.LgEvento.id.desc()))
    return hace_falta(db, "anexo_tratamiento", previa)


def marketing_actual(db: Session, usuario_id: int) -> bool:
    e = db.scalar(select(m.LgEvento).where(m.LgEvento.usuario_id == usuario_id, m.LgEvento.evento.in_(("marketing_otorgado", "marketing_revocado")))
                  .order_by(m.LgEvento.creado_en.desc(), m.LgEvento.id.desc()))
    return bool(e and e.evento == "marketing_otorgado")


def sumar_dias_habiles(inicio: date, dias: int) -> date:
    """Referencia de plazo en días hábiles (lunes a viernes). No descuenta días festivos: el plazo
    legal exacto lo confirma la persona que atiende la solicitud."""
    d, n = inicio, 0
    while n < dias:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return d


def folio() -> str:
    return "ARCO-" + "".join(secrets.choice(_LETRAS) for _ in range(6))
