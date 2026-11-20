"""Centro Legal (público y para usuarios). Muestra solo versiones PUBLICADAS de documentos que
cargó quien opera Nomira; nunca genera ni resume textos legales. La evidencia de aceptación es
mínima: usuario u organización, documento, versión, evento y fecha (sin IP ni contenido)."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, ip_cliente, solo_admin, usuario_actual
from ..freno import Ventana
from ..services import legal as lg

router = APIRouter(prefix="/api/legal", tags=["Centro Legal"])
_arco_ip = Ventana(5, 3600)
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def version_resumen(v: m.LgVersion | None) -> dict | None:
    if v is None:
        return None
    return {"id": v.id, "version": v.version, "titulo": v.titulo, "vigente_desde": v.vigente_desde.isoformat() if v.vigente_desde else None,
            "publicado_en": v.publicado_en.isoformat() if v.publicado_en else None, "resumen_cambios": v.resumen_cambios,
            "requiere_aceptacion": v.requiere_aceptacion, "estado": v.estado, "sha256": v.sha256}


def contacto(db: Session) -> dict:
    c = lg.config(db)
    return {"correo_privacidad": c.correo_privacidad, "responsable_datos": c.responsable_datos, "marketing_habilitado": c.marketing_habilitado}


@router.get("/documentos")
def documentos(db: Session = Depends(get_db)):
    r = {"documentos": [{"clave": k, **{x: d[x] for x in ("titulo", "descripcion")}, "vigente": version_resumen(lg.vigente(db, k))}
                        for k, d in lg.DOCUMENTOS.items()], "contacto": contacto(db)}
    db.commit()
    return r


@router.get("/documentos/{clave}")
def documento(clave: str, version_id: int | None = None, db: Session = Depends(get_db)):
    if clave not in lg.DOCUMENTOS:
        raise HTTPException(404, "Documento desconocido.")
    historial = lg.publicadas(db, clave)
    v = next((x for x in historial if x.id == version_id), None) if version_id else lg.vigente(db, clave)
    if version_id and v is None:
        raise HTTPException(404, "Esa versión no existe o no fue publicada.")
    actual = lg.vigente(db, clave)
    r = {"clave": clave, "titulo": lg.DOCUMENTOS[clave]["titulo"], "descripcion": lg.DOCUMENTOS[clave]["descripcion"],
         "version": {**version_resumen(v), "contenido": v.contenido, "es_vigente": bool(actual and v.id == actual.id)} if v else None,
         "historial": [version_resumen(x) for x in historial], "contacto": contacto(db)}
    db.commit()
    return r


# ---------- solicitudes ARCO ----------

class ArcoIn(BaseModel):
    tipo: str
    relacion: str
    despacho: str | None = Field(None, max_length=200)
    nombre: str = Field(min_length=3, max_length=200)
    email: str = Field(max_length=254)
    descripcion: str = Field(min_length=10, max_length=4000)
    confirmo: bool = False
    sitio_web: str | None = Field(None, max_length=200)  # trampa para robots


@router.post("/arco", status_code=201)
def solicitud_arco(d: ArcoIn, request: Request, db: Session = Depends(get_db)):
    """Registra la solicitud y devuelve un folio. No la da por atendida: la atiende una persona."""
    ip = ip_cliente(request) or "-"
    if _arco_ip.excedida(ip):
        raise HTTPException(429, "Recibimos varias solicitudes desde su conexión. Intente más tarde.")
    _arco_ip.registrar(ip)
    if d.sitio_web:
        return {"folio": None, "ok": True}
    if d.tipo not in lg.TIPOS_ARCO or d.relacion not in lg.RELACIONES:
        raise HTTPException(422, "Elija el tipo de solicitud y su relación con Nomira.")
    email = d.email.strip().lower()
    if not _RE_EMAIL.match(email):
        raise HTTPException(422, "El correo no parece válido.")
    if not d.confirmo:
        raise HTTPException(422, "Confirme que los datos son suyos o que representa legalmente a su titular.")
    f = lg.folio()
    while db.scalar(select(m.LgSolicitud.id).where(m.LgSolicitud.folio == f)):
        f = lg.folio()
    hoy = m.ahora().date()
    s = m.LgSolicitud(folio=f, tipo=d.tipo, relacion=d.relacion, despacho=(d.despacho or "").strip()[:200] or None, nombre=d.nombre.strip(),
                      email=email, descripcion=d.descripcion.strip(), estado="recibida", vence_en=lg.sumar_dias_habiles(hoy, 20))
    db.add(s)
    db.flush()
    db.add(m.LgSolicitudNota(solicitud_id=s.id, estado="recibida", nota="Solicitud recibida por el Centro Legal."))
    db.commit()
    return {"folio": s.folio, "ok": True}


# ---------- aceptación del usuario ----------

@router.get("/pendientes")
def pendientes(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    vs = lg.pendientes_usuario(db, u)
    cfg = lg.config(db)
    r = {"pendientes": [{**version_resumen(v), "documento": v.documento, "evento": lg.DOCUMENTOS[v.documento]["evento"],
                         "documento_titulo": lg.DOCUMENTOS[v.documento]["titulo"]} for v in vs],
         "marketing": {"habilitado": cfg.marketing_habilitado, "actual": lg.marketing_actual(db, u.id)},
         "anexo_pendiente": bool(u.rol == "administrador" and lg.anexo_pendiente(db, u.organizacion_id))}
    db.commit()
    return r


class Aceptacion(BaseModel):
    version_ids: list[int]
    marketing: bool | None = None  # None: no se preguntó
    contexto: str = "inicio_sesion"


@router.post("/aceptar")
def aceptar(d: Aceptacion, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if d.contexto not in ("inicio_sesion", "perfil"):
        raise HTTPException(422, "Contexto inválido.")
    for vid in dict.fromkeys(d.version_ids):
        v = db.get(m.LgVersion, vid)
        if not v or v.estado != "publicada" or v.documento not in ("terminos", "privacidad") or lg.vigente(db, v.documento).id != v.id:
            raise HTTPException(409, "Ese documento cambió. Vuelva a cargar la página para ver la versión vigente.")
        db.add(m.LgEvento(version_id=v.id, documento=v.documento, evento=lg.DOCUMENTOS[v.documento]["evento"], contexto=d.contexto,
                          usuario_id=u.id, organizacion_id=u.organizacion_id))
    if d.marketing is not None:
        cfg = lg.config(db)
        if not cfg.marketing_habilitado:
            raise HTTPException(409, "Nomira no envía información comercial.")
        if d.marketing != lg.marketing_actual(db, u.id):
            pv = lg.vigente(db, "privacidad")
            db.add(m.LgEvento(version_id=pv.id if pv else None, documento="privacidad", evento="marketing_otorgado" if d.marketing else "marketing_revocado",
                              contexto=d.contexto, usuario_id=u.id, organizacion_id=u.organizacion_id))
    auditar(db, u, "legal_aceptacion", "lg_version", None, {"versiones": d.version_ids, "marketing": d.marketing}, request)
    db.commit()
    return pendientes(u, db)


@router.get("/mis-registros")
def mis_registros(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    evs = db.scalars(select(m.LgEvento).where(m.LgEvento.usuario_id == u.id).order_by(m.LgEvento.creado_en.desc())).all()
    vs = {v.id: v for v in db.scalars(select(m.LgVersion).where(m.LgVersion.id.in_({e.version_id for e in evs if e.version_id})))}
    return [{"id": e.id, "documento": e.documento, "documento_titulo": lg.DOCUMENTOS.get(e.documento, {}).get("titulo", e.documento),
             "evento": e.evento, "evento_texto": lg.EVENTOS.get(e.evento, e.evento), "version": vs[e.version_id].version if e.version_id in vs else None,
             "version_id": e.version_id, "creado_en": e.creado_en.isoformat()} for e in evs]


# ---------- anexo de tratamiento (por organización) ----------

@router.get("/organizacion")
def organizacion(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    v = lg.vigente(db, "anexo_tratamiento")
    evs = db.scalars(select(m.LgEvento).where(m.LgEvento.documento == "anexo_tratamiento", m.LgEvento.organizacion_id == u.organizacion_id,
                                             m.LgEvento.evento == "aceptacion").order_by(m.LgEvento.creado_en.desc())).all()
    nombres = dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == u.organizacion_id)).all())
    vs = {x.id: x.version for x in db.scalars(select(m.LgVersion).where(m.LgVersion.id.in_({e.version_id for e in evs if e.version_id})))}
    return {"anexo": version_resumen(v), "pendiente": version_resumen(lg.anexo_pendiente(db, u.organizacion_id)),
            "aceptaciones": [{"version": vs.get(e.version_id), "usuario": nombres.get(e.usuario_id), "creado_en": e.creado_en.isoformat()} for e in evs],
            "puede_aceptar": u.rol == "administrador"}


class AnexoIn(BaseModel):
    version_id: int


@router.post("/organizacion/anexo")
def aceptar_anexo(d: AnexoIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    v = lg.vigente(db, "anexo_tratamiento")
    if not v or v.id != d.version_id:
        raise HTTPException(409, "El anexo cambió. Vuelva a cargar la página para ver la versión vigente.")
    db.add(m.LgEvento(version_id=v.id, documento="anexo_tratamiento", evento="aceptacion", contexto="organizacion", usuario_id=u.id,
                      organizacion_id=u.organizacion_id))
    auditar(db, u, "legal_anexo_aceptado", "lg_version", v.id, {"version": v.version}, request)
    db.commit()
    return organizacion(u, db)
