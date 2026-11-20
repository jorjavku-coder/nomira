"""API de Nomira Leads para el despacho. Todas las rutas exigen el módulo activo (vea main.py) y se
filtran por organización. Los datos de contacto se enmascaran para el rol «consulta». Ningún
recordatorio envía mensajes solo: cada envío lo decide una persona. Nomira no da asesoría jurídica
al prospecto ni promete que generará clientes: organiza la atención y muestra de dónde llegan."""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, puede_editar, solo_admin, usuario_actual
from ..services import correo, envios, modulos
from ..services.afore.cifrado import cifrar
from ..services.leads import base, meta
from ..services.leads import catalogos as cat
from ..services.plantillas_correo import _base, escape

router = APIRouter(prefix="/api/leads", tags=["Nomira Leads"])
PRIVADO = {"Cache-Control": "no-store"}


# ---------- utilidades y permisos ----------

def _txt(v: str | None, n: int) -> str | None:
    v = (v or "").strip()
    return v[:n] or None


def _nombres(db: Session, org: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org)).all())


def _ve_datos(u: m.Usuario) -> bool:
    return u.rol != "consulta"


def _prospecto(db: Session, pid: int, u: m.Usuario) -> m.LdProspecto:
    p = db.get(m.LdProspecto, pid)
    if not p or p.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return p


def _de_org(db: Session, modelo, oid: int, u: m.Usuario):
    x = db.get(modelo, oid)
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return x


def _responsable(db: Session, uid: int | None, u: m.Usuario) -> int | None:
    if uid is None:
        return None
    x = db.get(m.Usuario, uid)
    if not x or x.organizacion_id != u.organizacion_id or x.eliminado_en or not x.activo:
        raise HTTPException(422, "El responsable debe ser un usuario activo de su organización.")
    return x.id


def _campana(db: Session, cid: int | None, u: m.Usuario) -> m.LdCampana | None:
    return _de_org(db, m.LdCampana, cid, u) if cid else None


def _no_anonimizado(p: m.LdProspecto):
    if p.anonimizado_en:
        raise HTTPException(409, "Este prospecto fue anonimizado: ya no se puede modificar.")


def _etapas(db, u) -> dict[int, m.LdEtapa]:
    return {e.id: e for e in base.etapas(db, u.organizacion_id, todas=True)}


def _email(v: str | None) -> str | None:
    v = (v or "").strip().lower()
    if not v:
        return None
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v) or len(v) > 254:
        raise HTTPException(422, "El correo no parece válido.")
    return v


def _respondido(p: m.LdProspecto):
    if p.primera_respuesta_en is None:
        p.primera_respuesta_en = m.ahora()


def enlace_formulario(token: str) -> str:
    return f"{ajustes().url_publica.rstrip('/')}/contacto#{token}"


def enlace_whatsapp(cfg: m.LdConfig, c: m.LdCampana | None = None) -> str | None:
    if not cfg.wa_numero:
        return None
    from urllib.parse import quote
    num = re.sub(r"\D", "", cfg.wa_numero)
    texto = "Hola, quiero información" + (f" (ref: {c.codigo})" if c else "")
    return f"https://wa.me/{num}?text={quote(texto)}"


# ---------- representaciones ----------

def accion_dict(a: m.LdAccion | None, nombres: dict) -> dict | None:
    if a is None:
        return None
    hoy = base.hoy()
    return {"id": a.id, "tipo": a.tipo, "tipo_texto": cat.TIPOS_ACCION.get(a.tipo, a.tipo), "descripcion": a.descripcion,
            "fecha": a.fecha.isoformat(), "hora": a.hora, "responsable_id": a.responsable_id, "responsable": nombres.get(a.responsable_id),
            "recordatorio": a.recordatorio, "vencida": a.completada_en is None and not a.cancelada and a.fecha < hoy,
            "hoy": a.fecha == hoy, "completada_en": a.completada_en.isoformat() if a.completada_en else None, "resultado": a.resultado,
            "completada_por": nombres.get(a.completada_por_id), "cancelada": a.cancelada}


def fila(p: m.LdProspecto, db: Session, u: m.Usuario, nombres: dict, etapas: dict, campanas: dict, proxima=None,
         sin_responder: int = 0) -> dict:
    e = etapas.get(p.etapa_id)
    ver = _ve_datos(u)
    return {"id": p.id, "nombre": p.nombre, "telefono": p.telefono if ver else base.enmascarar_tel(p.telefono),
            "email": p.email if ver else base.enmascarar_email(p.email), "ciudad": p.ciudad, "materia": p.materia,
            "necesita": (p.descripcion or "")[:160] or None, "canal": p.canal, "canal_texto": cat.CANALES.get(p.canal, p.canal),
            "campana_id": p.campana_id, "campana": campanas.get(p.campana_id), "entrada": p.entrada,
            "responsable_id": p.responsable_id, "responsable": nombres.get(p.responsable_id),
            "etapa_id": p.etapa_id, "etapa": e.nombre if e else None, "etapa_tipo": e.tipo if e else None, "borrador": p.borrador,
            "proxima": accion_dict(proxima, nombres), "sin_responder": sin_responder, "primera_respuesta_en": p.primera_respuesta_en.isoformat() if p.primera_respuesta_en else None,
            "ultima_actividad_en": p.ultima_actividad_en.isoformat(), "creado_en": p.creado_en.isoformat(),
            "contratado_en": p.contratado_en.isoformat() if p.contratado_en else None, "motivo_perdida": p.motivo_perdida,
            "anonimizado": bool(p.anonimizado_en)}


def _contexto(db, u):
    return (_nombres(db, u.organizacion_id), _etapas(db, u),
            dict(db.execute(select(m.LdCampana.id, m.LdCampana.nombre).where(m.LdCampana.organizacion_id == u.organizacion_id)).all()))


def _proximas(db, ids: list[int]) -> dict[int, m.LdAccion]:
    res: dict[int, m.LdAccion] = {}
    if not ids:
        return res
    for a in db.scalars(select(m.LdAccion).where(m.LdAccion.prospecto_id.in_(ids), m.LdAccion.completada_en.is_(None),
                                                 m.LdAccion.cancelada.is_(False)).order_by(m.LdAccion.fecha, m.LdAccion.hora, m.LdAccion.id)):
        res.setdefault(a.prospecto_id, a)
    return res


def _sin_responder(db, org: int) -> dict[int, int]:
    res: dict[int, int] = {}
    for pid in db.scalars(select(m.LdMensaje.prospecto_id).where(m.LdMensaje.organizacion_id == org, m.LdMensaje.direccion == "entrante",
                                                                m.LdMensaje.respondido.is_(False), m.LdMensaje.prospecto_id.is_not(None))):
        res[pid] = res.get(pid, 0) + 1
    return res


# ---------- catálogos ----------

@router.get("/catalogos")
def catalogos(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    etapas = base.etapas(db, u.organizacion_id)
    usuarios = db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == u.organizacion_id, m.Usuario.activo.is_(True),
                                                  m.Usuario.eliminado_en.is_(None)).order_by(m.Usuario.nombre)).all()
    camp = db.scalars(select(m.LdCampana).where(m.LdCampana.organizacion_id == u.organizacion_id).order_by(m.LdCampana.nombre)).all()
    db.commit()
    return {"canales": cat.CANALES, "etapas": [{"id": e.id, "nombre": e.nombre, "tipo": e.tipo, "clave": e.clave} for e in etapas],
            "materias": base.materias(cfg), "motivos": base.motivos(cfg), "tipos_accion": cat.TIPOS_ACCION, "preferencias": cat.PREFERENCIAS,
            "canales_consentimiento": cat.CANALES_CONSENTIMIENTO, "medios_consentimiento": cat.MEDIOS_CONSENTIMIENTO,
            "estados_mensaje": cat.ESTADOS_MENSAJE, "finalidad": cat.FINALIDAD,
            "usuarios": [{"id": x.id, "nombre": x.nombre} for x in usuarios],
            "campanas": [{"id": c.id, "nombre": c.nombre, "canal": c.canal, "activa": c.activa} for c in camp],
            "puede_editar": u.rol in ("administrador", "analista"), "es_admin": u.rol == "administrador", "ve_datos": _ve_datos(u),
            "whatsapp_conectado": meta.wa_conectado(cfg), "correo_configurado": correo.configurado(),
            "modulos": modulos.activos(db, u.organizacion_id), "dias_sin_actividad": cfg.dias_sin_actividad}


# ---------- bandeja ----------

VISTAS = {"nuevos": "Prospectos nuevos", "responder": "Consultas que requieren respuesta", "citas": "Citas próximas",
          "seguimientos": "Seguimientos pendientes", "sin_actividad": "Sin actividad reciente o sin próximo paso",
          "contratados": "Clientes contratados", "borradores": "Borradores", "abiertos": "Todos los prospectos abiertos",
          "no_contratados": "No contratados", "todos": "Todos"}


def _seleccion(db: Session, u: m.Usuario, vista: str | None) -> list[m.LdProspecto]:
    org = u.organizacion_id
    et = _etapas(db, u)
    abiertas = {i for i, e in et.items() if e.tipo == "abierta"}
    q = select(m.LdProspecto).where(m.LdProspecto.organizacion_id == org, m.LdProspecto.anonimizado_en.is_(None))
    xs = db.scalars(q.order_by(m.LdProspecto.creado_en.desc())).all()
    vista = vista or "abiertos"
    hoy = base.hoy()
    if vista == "todos":
        return xs
    if vista == "borradores":
        return [p for p in xs if p.borrador]
    if vista == "contratados":
        return [p for p in xs if et.get(p.etapa_id) and et[p.etapa_id].tipo == "ganada"]
    if vista == "no_contratados":
        return [p for p in xs if et.get(p.etapa_id) and et[p.etapa_id].tipo == "perdida"]
    activos = [p for p in xs if p.etapa_id in abiertas]
    if vista == "abiertos":
        return activos
    activos = [p for p in activos if not p.borrador]
    if vista == "nuevos":
        return [p for p in activos if p.primera_respuesta_en is None]
    if vista == "responder":
        sr = _sin_responder(db, org)
        return [p for p in activos if sr.get(p.id) and p.primera_respuesta_en is not None]
    prox = _proximas(db, [p.id for p in activos])
    if vista == "citas":
        r = [p for p in activos if p.id in prox and _cita(db, p.id, hoy)]
        return sorted(r, key=lambda p: (_cita(db, p.id, hoy).fecha, _cita(db, p.id, hoy).hora or ""))
    if vista == "seguimientos":
        # los nuevos (sin primera respuesta) ya aparecen en su propio grupo
        r = [p for p in activos if p.id in prox and prox[p.id].fecha <= hoy and p.primera_respuesta_en is not None]
        return sorted(r, key=lambda p: prox[p.id].fecha)
    if vista == "sin_actividad":
        limite = m.ahora() - timedelta(days=base.config(db, org).dias_sin_actividad)
        return [p for p in activos if p.primera_respuesta_en is not None and (p.id not in prox or p.ultima_actividad_en < limite)]
    raise HTTPException(422, "Vista desconocida.")


def _cita(db, pid: int, hoy: date) -> m.LdAccion | None:
    return db.scalar(select(m.LdAccion).where(m.LdAccion.prospecto_id == pid, m.LdAccion.tipo == "consulta", m.LdAccion.completada_en.is_(None),
                                             m.LdAccion.cancelada.is_(False), m.LdAccion.fecha >= hoy, m.LdAccion.fecha <= hoy + timedelta(days=14))
                     .order_by(m.LdAccion.fecha, m.LdAccion.hora))


def _filas(db, u, xs) -> list[dict]:
    nombres, et, camp = _contexto(db, u)
    prox = _proximas(db, [p.id for p in xs])
    sr = _sin_responder(db, u.organizacion_id)
    return [fila(p, db, u, nombres, et, camp, prox.get(p.id), sr.get(p.id, 0)) for p in xs]


@router.get("/bandeja")
def bandeja(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    grupos = {}
    for v in ("nuevos", "responder", "citas", "seguimientos", "sin_actividad", "contratados"):
        xs = _seleccion(db, u, v)
        if v == "contratados":
            desde = m.ahora() - timedelta(days=90)
            xs = [p for p in xs if p.contratado_en and p.contratado_en >= desde]
        grupos[v] = {"titulo": VISTAS[v], "total": len(xs), "filas": _filas(db, u, xs[:6])}
    por_asignar = db.query(m.LdMensaje).filter(m.LdMensaje.organizacion_id == u.organizacion_id, m.LdMensaje.estado == "por_asignar").count()
    borradores = len(_seleccion(db, u, "borradores"))
    db.commit()
    return {"grupos": grupos, "por_asignar": por_asignar, "borradores": borradores}


class Consulta(BaseModel):
    vista: str | None = None
    etapa_id: int | None = None
    responsable_id: int | None = None
    materia: str | None = None
    canal: str | None = None
    campana_id: int | None = None
    q: str | None = Field(None, max_length=120)  # se envía en el cuerpo: nunca teléfonos o correos en la URL


@router.post("/prospectos/consulta")
def consultar(d: Consulta, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if d.vista and d.vista not in VISTAS:
        raise HTTPException(422, "Vista desconocida.")
    xs = _seleccion(db, u, d.vista or ("todos" if d.etapa_id else "abiertos"))
    if d.etapa_id:
        xs = [p for p in xs if p.etapa_id == d.etapa_id]
    if d.responsable_id:
        xs = [p for p in xs if p.responsable_id == d.responsable_id]
    if d.materia:
        xs = [p for p in xs if p.materia == d.materia]
    if d.canal:
        xs = [p for p in xs if p.canal == d.canal]
    if d.campana_id:
        xs = [p for p in xs if p.campana_id == d.campana_id]
    if d.q and d.q.strip():
        t = d.q.strip().lower()
        dig = re.sub(r"\D", "", t)
        xs = [p for p in xs if t in p.nombre.lower() or (p.email and t in p.email.lower()) or (len(dig) >= 4 and p.telefono and dig in p.telefono)
              or (p.descripcion and t in p.descripcion.lower())]
    filas = _filas(db, u, xs[:500])
    db.commit()
    return {"vista": d.vista, "titulo": VISTAS.get(d.vista or "abiertos"), "total": len(xs), "filas": filas}


@router.get("/tablero")
def tablero(responsable_id: int | None = None, materia: str | None = None, canal: str | None = None,
            u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Columnas por etapa. Los cerrados (contratado / no contratado) solo de los últimos 60 días."""
    xs = _seleccion(db, u, "todos")
    xs = [p for p in xs if (not responsable_id or p.responsable_id == responsable_id) and (not materia or p.materia == materia)
          and (not canal or p.canal == canal)]
    et = base.etapas(db, u.organizacion_id)
    limite = m.ahora() - timedelta(days=60)
    filas = {f["id"]: f for f in _filas(db, u, xs)}
    cols = []
    for e in et:
        ps = [p for p in xs if p.etapa_id == e.id and (e.tipo == "abierta" or p.actualizado_en >= limite)]
        cols.append({"id": e.id, "nombre": e.nombre, "tipo": e.tipo, "total": len(ps), "tarjetas": [filas[p.id] for p in ps]})
    db.commit()
    return {"columnas": cols}


# ---------- prospectos ----------

class ProximaIn(BaseModel):
    tipo: str
    fecha: date
    hora: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    descripcion: str | None = Field(None, max_length=300)
    responsable_id: int | None = None
    recordatorio: bool = True


class ProspectoIn(BaseModel):
    nombre: str | None = Field(None, max_length=200)
    telefono: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=254)
    canal: str = "otro"
    campana_id: int | None = None
    materia: str | None = Field(None, max_length=120)
    ciudad: str | None = Field(None, max_length=120)
    descripcion: str | None = Field(None, max_length=4000)
    responsable_id: int | None = None
    preferencia_contacto: str = "whatsapp"
    consentimiento: list[str] = []
    consentimiento_medio: str = "verbal"
    proxima: ProximaIn | None = None
    borrador: bool = False


def _validar_accion(db, u, a: ProximaIn) -> None:
    if a.tipo not in cat.TIPOS_ACCION:
        raise HTTPException(422, "Tipo de próximo paso inválido.")
    _responsable(db, a.responsable_id, u)


def _nueva_accion(db, u, p: m.LdProspecto, a: ProximaIn) -> m.LdAccion:
    _validar_accion(db, u, a)
    x = m.LdAccion(organizacion_id=u.organizacion_id, prospecto_id=p.id, tipo=a.tipo, fecha=a.fecha, hora=a.hora,
                   descripcion=_txt(a.descripcion, 300), responsable_id=a.responsable_id or p.responsable_id or u.id,
                   recordatorio=a.recordatorio, creado_por_id=u.id)
    db.add(x)
    db.flush()
    base.actividad(db, p, "accion", f"Próximo paso: {cat.TIPOS_ACCION[a.tipo]} el {a.fecha.strftime('%d/%m/%Y')}{' a las ' + a.hora if a.hora else ''}"
                   + (f" — {x.descripcion}" if x.descripcion else ""), u)
    return x


@router.post("/prospectos", status_code=201)
def crear(d: ProspectoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    tel, email = base.telefono(d.telefono), _email(d.email)
    nombre = _txt(d.nombre, 200)
    if d.canal not in cat.CANALES or d.preferencia_contacto not in cat.PREFERENCIAS:
        raise HTTPException(422, "Canal o preferencia de contacto inválidos.")
    if d.consentimiento_medio not in cat.MEDIOS_CONSENTIMIENTO:
        raise HTTPException(422, "Medio de consentimiento inválido.")
    if not d.borrador:
        falta = [t for ok, t in ((nombre, "el nombre"), (tel or email, "un teléfono o correo"), (d.proxima, "el próximo paso")) if not ok]
        if falta:
            raise HTTPException(422, f"Para guardarlo falta {', '.join(falta)}. Si aún no los tiene, guárdelo como borrador.")
    camp = _campana(db, d.campana_id, u)
    p = m.LdProspecto(organizacion_id=u.organizacion_id, nombre=nombre or "Sin nombre", telefono=tel, email=email, ciudad=_txt(d.ciudad, 120),
                      materia=_txt(d.materia, 120), descripcion=_txt(d.descripcion, 4000), canal=camp.canal if camp and d.canal == "otro" else d.canal,
                      campana_id=camp.id if camp else None, entrada="manual", responsable_id=_responsable(db, d.responsable_id, u) or u.id,
                      etapa_id=base.etapa_inicial(db, u.organizacion_id).id, borrador=d.borrador, preferencia_contacto=d.preferencia_contacto,
                      creado_por_id=u.id)
    db.add(p)
    db.flush()
    base.actividad(db, p, "alta", "Registrado como borrador" if d.borrador else "Prospecto registrado", u)
    if d.consentimiento:
        base.consentir(db, p, d.consentimiento, d.consentimiento_medio, u)
    if d.proxima:
        _nueva_accion(db, u, p, d.proxima)
    auditar(db, u, "ld_prospecto_creado", "ld_prospecto", p.id, {"canal": p.canal, "borrador": p.borrador}, request)
    db.commit()
    return ver(p.id, u, db)


@router.get("/prospectos/{pid}")
def ver(pid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    p = _prospecto(db, pid, u)
    nombres, et, camp = _contexto(db, u)
    acciones = db.scalars(select(m.LdAccion).where(m.LdAccion.prospecto_id == p.id).order_by(m.LdAccion.fecha.desc(), m.LdAccion.id.desc())).all()
    pend = [a for a in acciones if not a.completada_en and not a.cancelada]
    pend.sort(key=lambda a: (a.fecha, a.hora or "", a.id))
    acts = db.scalars(select(m.LdActividad).where(m.LdActividad.prospecto_id == p.id).order_by(m.LdActividad.creado_en.desc(), m.LdActividad.id.desc())).all()
    cons = db.scalars(select(m.LdConsentimiento).where(m.LdConsentimiento.prospecto_id == p.id).order_by(m.LdConsentimiento.id.desc())).all()
    msjs = db.scalars(select(m.LdMensaje).where(m.LdMensaje.prospecto_id == p.id).order_by(m.LdMensaje.creado_en)).all()
    cfg = base.config(db, u.organizacion_id)
    d = fila(p, db, u, nombres, et, camp, pend[0] if pend else None, sum(1 for x in msjs if x.direccion == "entrante" and not x.respondido))
    ver_datos = _ve_datos(u)
    d.update({
        "descripcion": p.descripcion, "preferencia_contacto": p.preferencia_contacto, "motivo_nota": p.motivo_nota,
        "origen_detalle": p.origen_detalle, "servicio_contratado": p.servicio_contratado, "asunto_titulo": p.asunto_titulo,
        "asunto_referencia": p.asunto_referencia, "ev_asunto_id": p.ev_asunto_id, "af_caso_id": p.af_caso_id,
        "creado_por": nombres.get(p.creado_por_id),
        "pendientes": [accion_dict(a, nombres) for a in pend],
        "acciones": [accion_dict(a, nombres) for a in acciones if a.completada_en or a.cancelada],
        "historial": [{"id": a.id, "tipo": a.tipo, "texto": a.texto, "detalle": a.detalle, "usuario": nombres.get(a.usuario_id),
                       "creado_en": a.creado_en.isoformat()} for a in acts],
        "consentimientos": [{"id": c.id, "canal": c.canal, "canal_texto": cat.CANALES_CONSENTIMIENTO.get(c.canal, c.canal), "finalidad": c.finalidad,
                             "medio": c.medio, "medio_texto": cat.MEDIOS_CONSENTIMIENTO.get(c.medio, c.medio), "otorgado_en": c.otorgado_en.isoformat(),
                             "registrado_por": nombres.get(c.registrado_por_id), "revocado_en": c.revocado_en.isoformat() if c.revocado_en else None,
                             "revocado_medio": c.revocado_medio} for c in cons],
        "consiente": {k: any(c.canal == k and not c.revocado_en for c in cons) for k in cat.CANALES_CONSENTIMIENTO},
        "mensajes": [mensaje_dict(x, nombres, ver_datos) for x in msjs],
        "whatsapp": {"conectado": meta.wa_conectado(cfg), "ventana_abierta": meta.ventana_abierta(db, p.id),
                     "plantilla": cfg.wa_plantilla, "enlace_directo": bool(p.telefono) and ver_datos},
        "correo_configurado": correo.configurado(),
    })
    db.commit()
    return d


def mensaje_dict(x: m.LdMensaje, nombres: dict, ver_datos: bool = True) -> dict:
    return {"id": x.id, "prospecto_id": x.prospecto_id, "canal": x.canal, "direccion": x.direccion, "texto": x.texto, "estado": x.estado,
            "estado_texto": cat.ESTADOS_MENSAJE.get(x.estado, x.estado), "error": x.error, "respondido": x.respondido,
            "telefono": (x.telefono if ver_datos else base.enmascarar_tel(x.telefono)), "creado_por": nombres.get(x.creado_por_id),
            "creado_en": x.creado_en.isoformat(), "enviado_en": x.enviado_en.isoformat() if x.enviado_en else None,
            "entregado_en": x.entregado_en.isoformat() if x.entregado_en else None, "leido_en": x.leido_en.isoformat() if x.leido_en else None}


class ProspectoCambio(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=200)
    telefono: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=254)
    canal: str | None = None
    campana_id: int | None = None
    materia: str | None = Field(None, max_length=120)
    ciudad: str | None = Field(None, max_length=120)
    descripcion: str | None = Field(None, max_length=4000)
    responsable_id: int | None = None
    preferencia_contacto: str | None = None
    borrador: bool | None = None


CAMPOS = {"nombre": "Nombre", "telefono": "Teléfono", "email": "Correo", "canal": "Canal de origen", "campana_id": "Campaña", "materia": "Materia",
          "ciudad": "Ciudad", "descripcion": "Descripción", "preferencia_contacto": "Preferencia de contacto"}


@router.patch("/prospectos/{pid}")
def cambiar(pid: int, d: ProspectoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _prospecto(db, pid, u)
    _no_anonimizado(p)
    datos = d.model_dump(exclude_unset=True)
    nombres = _nombres(db, u.organizacion_id)
    cambiados = []
    if "telefono" in datos:
        datos["telefono"] = base.telefono(datos["telefono"])
    if "email" in datos:
        datos["email"] = _email(datos["email"])
    if "canal" in datos and datos["canal"] not in cat.CANALES:
        raise HTTPException(422, "Canal inválido.")
    if "preferencia_contacto" in datos and datos["preferencia_contacto"] not in cat.PREFERENCIAS:
        raise HTTPException(422, "Preferencia inválida.")
    if "campana_id" in datos:
        _campana(db, datos["campana_id"], u)
    for k, txt in CAMPOS.items():
        if k in datos:
            v = datos[k].strip() if isinstance(datos[k], str) else datos[k]
            v = v if v != "" else None
            if k == "nombre" and not v:
                continue
            if v != getattr(p, k):
                setattr(p, k, v)
                cambiados.append(txt)
    if "responsable_id" in datos and datos["responsable_id"] != p.responsable_id:
        nuevo = _responsable(db, datos["responsable_id"], u)
        base.actividad(db, p, "responsable", f"Responsable: {nombres.get(p.responsable_id) or 'sin asignar'} → {nombres.get(nuevo) or 'sin asignar'}", u)
        auditar(db, u, "ld_responsable_cambiado", "ld_prospecto", p.id, {"de": p.responsable_id, "a": nuevo}, request)
        p.responsable_id = nuevo
    if datos.get("borrador") is False and p.borrador:
        if not (p.nombre and p.nombre != "Sin nombre" and (p.telefono or p.email)):
            raise HTTPException(422, "Para completar el alta falta el nombre y un teléfono o correo.")
        if not base.proxima(db, p.id):
            raise HTTPException(422, "Para completar el alta defina el próximo paso.")
        p.borrador = False
        base.actividad(db, p, "dato", "Alta completada (ya no es borrador)", u)
    if cambiados:
        # El historial dice QUÉ cambió, sin copiar los datos personales
        base.actividad(db, p, "dato", "Datos actualizados: " + ", ".join(cambiados), u, campos=cambiados)
        auditar(db, u, "ld_prospecto_actualizado", "ld_prospecto", p.id, {"campos": cambiados}, request)
    db.commit()
    return ver(p.id, u, db)


class EtapaCambio(BaseModel):
    etapa_id: int
    nota: str | None = Field(None, max_length=500)
    motivo: str | None = Field(None, max_length=120)
    motivo_nota: str | None = Field(None, max_length=500)


@router.post("/prospectos/{pid}/etapa")
def mover(pid: int, d: EtapaCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _prospecto(db, pid, u)
    _no_anonimizado(p)
    et = _etapas(db, u)
    nueva, antes = et.get(d.etapa_id), et.get(p.etapa_id)
    if not nueva or nueva.archivada:
        raise HTTPException(422, "Etapa inválida.")
    if nueva.id == p.etapa_id:
        return ver(p.id, u, db)
    if nueva.tipo == "ganada":
        raise HTTPException(422, "Para marcarlo como contratado use «Registrar contratación»: así se guarda el servicio y el asunto.")
    if nueva.tipo == "perdida":
        if not _txt(d.motivo, 120):
            raise HTTPException(422, "Indique el motivo por el que no se contrató o no se atendió.")
        p.motivo_perdida, p.motivo_nota = _txt(d.motivo, 120), _txt(d.motivo_nota, 500)
        for a in db.scalars(select(m.LdAccion).where(m.LdAccion.prospecto_id == p.id, m.LdAccion.completada_en.is_(None), m.LdAccion.cancelada.is_(False))):
            a.cancelada = True  # un prospecto cerrado no debe seguir generando recordatorios
    else:
        p.motivo_perdida = p.motivo_nota = None
        if antes and antes.tipo == "ganada":
            p.contratado_en = None
    if antes and antes.tipo == "abierta" and nueva.tipo == "abierta" and nueva.orden > antes.orden:
        _respondido(p)
    texto = f"Etapa: {antes.nombre if antes else '—'} → {nueva.nombre}" + (f" · Motivo: {p.motivo_perdida}" if nueva.tipo == "perdida" else "")
    base.actividad(db, p, "etapa", texto + (f"\n{d.nota.strip()}" if d.nota and d.nota.strip() else ""), u, de=antes.id if antes else None, a=nueva.id)
    p.etapa_id = nueva.id
    auditar(db, u, "ld_etapa_cambiada", "ld_prospecto", p.id, {"de": antes.nombre if antes else None, "a": nueva.nombre}, request)
    db.commit()
    return ver(p.id, u, db)


class Nota(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


@router.post("/prospectos/{pid}/notas", status_code=201)
def nota(pid: int, d: Nota, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _prospecto(db, pid, u)
    _no_anonimizado(p)
    base.actividad(db, p, "nota", d.texto.strip(), u)
    db.commit()
    return ver(p.id, u, db)


# ---------- próximos pasos ----------

@router.post("/prospectos/{pid}/acciones", status_code=201)
def nueva_accion(pid: int, d: ProximaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _prospecto(db, pid, u)
    _no_anonimizado(p)
    a = _nueva_accion(db, u, p, d)
    auditar(db, u, "ld_accion_creada", "ld_accion", a.id, {"prospecto_id": p.id, "tipo": a.tipo}, request)
    db.commit()
    return ver(p.id, u, db)


class Completar(BaseModel):
    resultado: str | None = Field(None, max_length=500)
    siguiente: ProximaIn | None = None


@router.post("/acciones/{aid}/completar")
def completar(aid: int, d: Completar, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _de_org(db, m.LdAccion, aid, u)
    p = _prospecto(db, a.prospecto_id, u)
    if a.completada_en or a.cancelada:
        raise HTTPException(409, "Ese paso ya estaba cerrado.")
    a.completada_en, a.completada_por_id, a.resultado = m.ahora(), u.id, _txt(d.resultado, 500)
    if a.tipo in ("llamada", "mensaje", "consulta", "propuesta"):
        _respondido(p)
    base.actividad(db, p, "accion", f"Hecho: {cat.TIPOS_ACCION.get(a.tipo, a.tipo)}" + (f" — Resultado: {a.resultado}" if a.resultado else ""), u)
    if d.siguiente:
        _nueva_accion(db, u, p, d.siguiente)
    auditar(db, u, "ld_accion_completada", "ld_accion", a.id, {"prospecto_id": p.id}, request)
    db.commit()
    return ver(p.id, u, db)


@router.post("/acciones/{aid}/cancelar")
def cancelar_accion(aid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _de_org(db, m.LdAccion, aid, u)
    p = _prospecto(db, a.prospecto_id, u)
    if a.completada_en or a.cancelada:
        raise HTTPException(409, "Ese paso ya estaba cerrado.")
    a.cancelada = True
    base.actividad(db, p, "accion", f"Cancelado: {cat.TIPOS_ACCION.get(a.tipo, a.tipo)} del {a.fecha.strftime('%d/%m/%Y')}", u)
    db.commit()
    return ver(p.id, u, db)


# ---------- consentimientos ----------

class ConsentimientoIn(BaseModel):
    canal: str
    medio: str
    finalidad: str | None = Field(None, max_length=300)


@router.post("/prospectos/{pid}/consentimientos", status_code=201)
def dar_consentimiento(pid: int, d: ConsentimientoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _prospecto(db, pid, u)
    _no_anonimizado(p)
    if d.canal not in cat.CANALES_CONSENTIMIENTO or d.medio not in cat.MEDIOS_CONSENTIMIENTO:
        raise HTTPException(422, "Canal o medio inválido.")
    if base.consiente(db, p.id, d.canal):
        raise HTTPException(409, "Ya hay un consentimiento vigente para ese canal.")
    base.consentir(db, p, [d.canal], d.medio, u, _txt(d.finalidad, 300) or cat.FINALIDAD)
    base.actividad(db, p, "consentimiento", f"Autorizó el contacto por {cat.CANALES_CONSENTIMIENTO[d.canal]} ({cat.MEDIOS_CONSENTIMIENTO[d.medio]})", u)
    auditar(db, u, "ld_consentimiento_registrado", "ld_prospecto", p.id, {"canal": d.canal, "medio": d.medio}, request)
    db.commit()
    return ver(p.id, u, db)


class Revocar(BaseModel):
    medio: str = "verbal"


@router.post("/consentimientos/{cid}/revocar")
def revocar(cid: int, d: Revocar, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _de_org(db, m.LdConsentimiento, cid, u)
    p = _prospecto(db, c.prospecto_id, u)
    if c.revocado_en:
        raise HTTPException(409, "Ya estaba revocado.")
    c.revocado_en, c.revocado_medio = m.ahora(), (d.medio or "verbal")[:30]
    base.actividad(db, p, "consentimiento", f"Revocó el contacto por {cat.CANALES_CONSENTIMIENTO.get(c.canal, c.canal)}", u)
    auditar(db, u, "ld_consentimiento_revocado", "ld_prospecto", p.id, {"canal": c.canal}, request)
    db.commit()
    return ver(p.id, u, db)


# ---------- mensajes ----------

class MensajeIn(BaseModel):
    canal: str  # whatsapp | correo
    texto: str = Field("", max_length=4000)
    modo: str = "enviar"  # enviar (por la integración) | manual (lo envió desde su WhatsApp o correo) | plantilla
    asunto: str | None = Field(None, max_length=150)


def _faltantes_envio(db, p: m.LdProspecto, d: MensajeIn, cfg: m.LdConfig) -> list[str]:
    falta = []
    if p.preferencia_contacto == "ninguno":
        falta.append("El prospecto pidió no ser contactado.")
    if not base.consiente(db, p.id, d.canal):
        falta.append(f"No hay consentimiento vigente para contactarlo por {cat.CANALES_CONSENTIMIENTO.get(d.canal, d.canal)}.")
    if d.canal == "whatsapp":
        if not p.telefono:
            falta.append("No tiene teléfono registrado.")
        if not meta.wa_conectado(cfg):
            falta.append("WhatsApp Business Platform no está conectado (Leads → Configuración).")
        elif d.modo == "plantilla" and not cfg.wa_plantilla:
            falta.append("No hay una plantilla aprobada por Meta registrada en Configuración.")
        elif d.modo == "enviar" and not meta.ventana_abierta(db, p.id):
            falta.append("Pasaron más de 24 h desde su último mensaje (o nunca escribió): WhatsApp solo permite iniciar la conversación con una plantilla aprobada.")
    else:
        if not p.email:
            falta.append("No tiene correo registrado.")
        if not correo.configurado():
            falta.append("El envío de correos no está configurado en el servidor.")
    return falta


@router.post("/prospectos/{pid}/mensajes", status_code=201)
def enviar_mensaje(pid: int, d: MensajeIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Cada envío lo decide una persona (revisión humana). «manual» solo registra que se respondió fuera
    de Nomira (p. ej. con el enlace de WhatsApp): Nomira no puede confirmar ese envío."""
    p = _prospecto(db, pid, u)
    _no_anonimizado(p)
    if d.canal not in ("whatsapp", "correo") or d.modo not in ("enviar", "manual", "plantilla"):
        raise HTTPException(422, "Canal o modo inválido.")
    texto = d.texto.strip()
    if d.modo != "plantilla" and not texto:
        raise HTTPException(422, "Escriba el mensaje.")
    cfg = base.config(db, u.organizacion_id)
    x = m.LdMensaje(organizacion_id=u.organizacion_id, prospecto_id=p.id, canal=d.canal, direccion="saliente", estado="manual",
                    texto=texto or f"[Plantilla «{cfg.wa_plantilla}»]", telefono=p.telefono if d.canal == "whatsapp" else None, creado_por_id=u.id)
    if d.modo != "manual":
        falta = _faltantes_envio(db, p, d, cfg)
        if falta:
            raise HTTPException(409, {"mensaje": "No se puede enviar todavía.", "faltantes": falta})
        try:
            if d.canal == "whatsapp":
                x.proveedor_id = (meta.enviar_plantilla(cfg, p.telefono, p.nombre.split()[0]) if d.modo == "plantilla"
                                  else meta.enviar_texto(cfg, p.telefono, texto))
            else:
                org = db.get(m.Organizacion, u.organizacion_id)
                html = _base(texto[:90], f'<p style="margin:0;white-space:pre-line">{escape(texto)}</p>',
                             pie=f"Recibe este correo porque solicitó información a {org.nombre}. Si ya no desea recibir mensajes, responda «BAJA».")
                r = envios.registrar_y_enviar(db, "ld_mensaje", [p.email], _txt(d.asunto, 150) or f"{org.nombre}: respuesta a su consulta", html, texto,
                                              organizacion_id=u.organizacion_id)
                if r.estado != "enviado":
                    raise meta.MetaError(r.error or "No se pudo enviar el correo.")
            x.estado, x.enviado_en = "enviado", m.ahora()
        except meta.MetaError as e:
            x.estado, x.error = "fallido", str(e)[:1000]
    db.add(x)
    if x.estado != "fallido":
        _respondido(p)
        for e in db.scalars(select(m.LdMensaje).where(m.LdMensaje.prospecto_id == p.id, m.LdMensaje.direccion == "entrante",
                                                      m.LdMensaje.respondido.is_(False))):
            e.respondido = True
    base.actividad(db, p, "mensaje", {"manual": f"Respuesta registrada por {cat.CANALES[d.canal]} (enviada fuera de Nomira)",
                                      "enviar": f"Mensaje enviado por {cat.CANALES[d.canal]}", "plantilla": "Plantilla de WhatsApp enviada"}[d.modo]
                   + (" — FALLÓ" if x.estado == "fallido" else ""), u)
    db.flush()
    auditar(db, u, "ld_mensaje", "ld_mensaje", x.id, {"prospecto_id": p.id, "canal": d.canal, "modo": d.modo, "estado": x.estado}, request)
    db.commit()
    if x.estado == "fallido":
        raise HTTPException(502, f"No se pudo enviar: {x.error}")
    return ver(p.id, u, db)


@router.get("/mensajes")
def mensajes(bandeja: str = "por_asignar", u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    q = select(m.LdMensaje).where(m.LdMensaje.organizacion_id == u.organizacion_id)
    if bandeja == "por_asignar":
        q = q.where(m.LdMensaje.estado == "por_asignar")
    elif bandeja == "sin_responder":
        q = q.where(m.LdMensaje.direccion == "entrante", m.LdMensaje.respondido.is_(False), m.LdMensaje.prospecto_id.is_not(None))
    else:
        raise HTTPException(422, "Bandeja desconocida.")
    xs = db.scalars(q.order_by(m.LdMensaje.creado_en.desc()).limit(200)).all()
    nombres = _nombres(db, u.organizacion_id)
    pros = {p.id: p.nombre for p in db.scalars(select(m.LdProspecto).where(m.LdProspecto.id.in_([x.prospecto_id for x in xs if x.prospecto_id])))}
    return [{**mensaje_dict(x, nombres, _ve_datos(u)), "prospecto": pros.get(x.prospecto_id)} for x in xs]


class Asignar(BaseModel):
    prospecto_id: int | None = None
    crear: bool = False
    nombre: str | None = Field(None, max_length=200)


@router.post("/mensajes/{mid}/asignar")
def asignar_mensaje(mid: int, d: Asignar, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _de_org(db, m.LdMensaje, mid, u)
    if x.estado != "por_asignar":
        raise HTTPException(409, "Ese mensaje ya está asignado.")
    if d.crear:
        p, _ = base.alta_externa(db, u.organizacion_id, nombre=d.nombre, tel=x.telefono, email=None, canal="whatsapp", entrada="whatsapp",
                                 descripcion=x.texto)
        p.responsable_id = p.responsable_id or u.id
    elif d.prospecto_id:
        p = _prospecto(db, d.prospecto_id, u)
    else:
        raise HTTPException(422, "Elija un prospecto o cree uno nuevo.")
    x.prospecto_id, x.estado = p.id, "recibido"
    base.actividad(db, p, "mensaje", "Mensaje de WhatsApp asociado a este prospecto", u)
    auditar(db, u, "ld_mensaje_asignado", "ld_mensaje", x.id, {"prospecto_id": p.id}, request)
    db.commit()
    return {"ok": True, "prospecto_id": p.id}


@router.post("/mensajes/{mid}/atendido")
def mensaje_atendido(mid: int, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _de_org(db, m.LdMensaje, mid, u)
    x.respondido = True
    db.commit()
    return {"ok": True}


# ---------- contratación ----------

class Contratar(BaseModel):
    servicio: str = Field(min_length=2, max_length=200)
    asunto_titulo: str | None = Field(None, max_length=200)
    referencia: str | None = Field(None, max_length=80)
    nota: str | None = Field(None, max_length=1000)
    crear_en: str | None = None  # evidencia | afore (opcional: solo si ese módulo está activo)


@router.post("/prospectos/{pid}/contratar")
def contratar(pid: int, d: Contratar, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Convierte el prospecto en cliente con sus datos (sin capturarlos de nuevo). Si el despacho
    también usa Evidencia o AFORE, puede abrir ahí el asunto; Leads no depende de esos módulos."""
    p = _prospecto(db, pid, u)
    _no_anonimizado(p)
    if p.borrador:
        raise HTTPException(422, "Complete el alta del prospecto antes de registrar la contratación.")
    activos = modulos.activos(db, u.organizacion_id)
    if d.crear_en and d.crear_en not in activos:
        raise HTTPException(409, "Ese módulo no está activo para su organización.")
    ganada = base.etapa_tipo(db, u.organizacion_id, "ganada")
    antes = db.get(m.LdEtapa, p.etapa_id)
    titulo = _txt(d.asunto_titulo, 200) or f"{d.servicio.strip()} — {p.nombre}"[:200]
    p.etapa_id, p.contratado_en, p.servicio_contratado = ganada.id, m.ahora(), d.servicio.strip()
    p.asunto_titulo, p.asunto_referencia, p.motivo_perdida, p.motivo_nota = titulo, _txt(d.referencia, 80), None, None
    _respondido(p)
    for a in db.scalars(select(m.LdAccion).where(m.LdAccion.prospecto_id == p.id, m.LdAccion.completada_en.is_(None), m.LdAccion.cancelada.is_(False))):
        a.cancelada = True
    destino = None
    if d.crear_en == "evidencia":
        ev = m.EvAsunto(organizacion_id=u.organizacion_id, nombre=titulo, cliente=p.nombre, tipo_caso=p.materia,
                        identificador_interno=p.asunto_referencia, responsable_id=p.responsable_id,
                        notas=f"Creado desde Nomira Leads. Servicio contratado: {p.servicio_contratado}.", creado_por_id=u.id)
        db.add(ev)
        db.flush()
        p.ev_asunto_id, destino = ev.id, f"/evidencia/{ev.id}"
    elif d.crear_en == "afore":
        cl = m.AfCliente(organizacion_id=u.organizacion_id, nombre=p.nombre, telefono=p.telefono, email=p.email,
                         preferencia_contacto=p.preferencia_contacto if p.preferencia_contacto in ("whatsapp", "correo") else "correo",
                         notas="Creado desde Nomira Leads.", creado_por_id=u.id)
        db.add(cl)
        db.flush()
        caso = m.AfCaso(organizacion_id=u.organizacion_id, cliente_id=cl.id, tipo_problema="otro", tipo_otro=p.servicio_contratado[:200],
                        identificador_interno=p.asunto_referencia, responsable_id=p.responsable_id, estado="borrador", creado_por_id=u.id,
                        resumen_interno=p.descripcion)
        db.add(caso)
        db.flush()
        p.af_caso_id, destino = caso.id, f"/afore/casos/{caso.id}"
    base.actividad(db, p, "conversion", f"Contratado: {p.servicio_contratado}" + (f"\n{d.nota.strip()}" if d.nota and d.nota.strip() else "")
                   + ({"evidencia": " · Asunto abierto en Nomira Evidencia", "afore": " · Caso abierto en Nomira AFORE (borrador)"}.get(d.crear_en or "", "")),
                   u, de=antes.id if antes else None, a=ganada.id)
    auditar(db, u, "ld_contratado", "ld_prospecto", p.id, {"crear_en": d.crear_en, "canal": p.canal, "campana_id": p.campana_id}, request)
    db.commit()
    return {**ver(p.id, u, db), "destino": destino}


# ---------- eliminar o anonimizar ----------

@router.post("/prospectos/{pid}/anonimizar")
def anonimizar(pid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Borra los datos personales y conserva solo lo estadístico (canal, campaña, etapa y fechas)."""
    p = _prospecto(db, pid, u)
    _no_anonimizado(p)
    p.nombre, p.telefono, p.email, p.ciudad, p.descripcion = f"Prospecto anonimizado #{p.id}", None, None, None, None
    p.origen_detalle, p.motivo_nota, p.asunto_titulo, p.servicio_contratado = None, None, None, ("Servicio contratado" if p.contratado_en else None)
    p.anonimizado_en = m.ahora()
    for a in db.scalars(select(m.LdActividad).where(m.LdActividad.prospecto_id == p.id)):
        a.texto, a.detalle = None, None
    for a in db.scalars(select(m.LdAccion).where(m.LdAccion.prospecto_id == p.id)):
        a.descripcion, a.resultado = None, None
        if not a.completada_en:
            a.cancelada = True
    for x in db.scalars(select(m.LdMensaje).where(m.LdMensaje.prospecto_id == p.id)):
        x.texto, x.telefono, x.error = "[eliminado]", None, None
    db.add(m.LdActividad(organizacion_id=p.organizacion_id, prospecto_id=p.id, tipo="anonimizado", texto="Datos personales eliminados", usuario_id=u.id))
    auditar(db, u, "ld_prospecto_anonimizado", "ld_prospecto", p.id, None, request)
    db.commit()
    return {"ok": True}


@router.delete("/prospectos/{pid}")
def eliminar(pid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    p = _prospecto(db, pid, u)
    for x in db.scalars(select(m.LdMensaje).where(m.LdMensaje.prospecto_id == p.id)):
        db.delete(x)
    db.delete(p)  # acciones, historial y consentimientos: CASCADE
    auditar(db, u, "ld_prospecto_eliminado", "ld_prospecto", pid, None, request)
    db.commit()
    return {"ok": True}


# ---------- etapas del tablero ----------

class EtapaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)


@router.post("/etapas", status_code=201)
def crear_etapa(d: EtapaIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    et = base.etapas(db, u.organizacion_id, todas=True)
    ultima_abierta = max((e.orden for e in et if e.tipo == "abierta"), default=0)
    for e in et:  # la nueva etapa queda antes de «Contratado» y «No contratado»
        if e.tipo != "abierta":
            e.orden += 1
    x = m.LdEtapa(organizacion_id=u.organizacion_id, nombre=d.nombre.strip(), tipo="abierta", orden=ultima_abierta + 1, archivada=False)
    db.add(x)
    db.flush()
    auditar(db, u, "ld_etapa_creada", "ld_etapa", x.id, {"nombre": x.nombre}, request)
    db.commit()
    return catalogos(u, db)["etapas"]


class EtapaEdicion(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=80)
    archivada: bool | None = None


@router.patch("/etapas/{eid}")
def editar_etapa(eid: int, d: EtapaEdicion, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    e = _de_org(db, m.LdEtapa, eid, u)
    if d.nombre:
        auditar(db, u, "ld_etapa_renombrada", "ld_etapa", e.id, {"de": e.nombre, "a": d.nombre.strip()}, request)
        e.nombre = d.nombre.strip()
    if d.archivada is not None and d.archivada != e.archivada:
        if e.tipo != "abierta":
            raise HTTPException(409, "«Contratado» y «No contratado» no se pueden quitar (solo renombrar).")
        if d.archivada:
            if db.query(m.LdProspecto).filter(m.LdProspecto.etapa_id == e.id).count():
                raise HTTPException(409, "Hay prospectos en esta etapa: muévalos antes de quitarla.")
            if sum(1 for x in base.etapas(db, u.organizacion_id) if x.tipo == "abierta") <= 1:
                raise HTTPException(409, "Debe quedar al menos una etapa abierta.")
        e.archivada = d.archivada
        auditar(db, u, "ld_etapa_archivada" if d.archivada else "ld_etapa_restaurada", "ld_etapa", e.id, None, request)
    db.commit()
    return catalogos(u, db)["etapas"]


class Orden(BaseModel):
    ids: list[int]


@router.post("/etapas/orden")
def ordenar_etapas(d: Orden, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    et = {e.id: e for e in base.etapas(db, u.organizacion_id)}
    abiertas = [i for i in d.ids if i in et and et[i].tipo == "abierta"]
    if sorted(abiertas) != sorted(i for i, e in et.items() if e.tipo == "abierta"):
        raise HTTPException(422, "Incluya todas las etapas abiertas, una sola vez.")
    for i, eid in enumerate(abiertas):
        et[eid].orden = i
    for j, e in enumerate(sorted((e for e in et.values() if e.tipo != "abierta"), key=lambda e: e.tipo != "ganada")):
        e.orden = len(abiertas) + j
    auditar(db, u, "ld_etapas_ordenadas", None, None, {"ids": abiertas}, request)
    db.commit()
    return catalogos(u, db)["etapas"]


# ---------- campañas y fuentes ----------

def _dinero(v) -> Decimal | None:
    if v in (None, ""):
        return None
    try:
        d = Decimal(str(v).replace(",", "").replace("$", "").strip()).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise HTTPException(422, "La inversión debe ser una cantidad (por ejemplo 2500.00).")
    if d < 0:
        raise HTTPException(422, "La inversión no puede ser negativa.")
    return d


def campana_dict(c: m.LdCampana, cfg: m.LdConfig, stats: dict | None = None) -> dict:
    return {"id": c.id, "nombre": c.nombre, "canal": c.canal, "canal_texto": cat.CANALES.get(c.canal, c.canal), "codigo": c.codigo,
            "id_externo": c.id_externo, "inversion": str(c.inversion) if c.inversion is not None else None,
            "inicio": c.inicio.isoformat() if c.inicio else None, "fin": c.fin.isoformat() if c.fin else None, "activa": c.activa, "notas": c.notas,
            "enlace_formulario": enlace_formulario(c.enlace_token), "enlace_whatsapp": enlace_whatsapp(cfg, c),
            "utm": f"utm_source={c.canal}&utm_campaign={c.codigo}", "creado_en": c.creado_en.isoformat(), **(stats or {})}


@router.get("/campanas")
def listar_campanas(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    cs = db.scalars(select(m.LdCampana).where(m.LdCampana.organizacion_id == u.organizacion_id).order_by(m.LdCampana.activa.desc(), m.LdCampana.creado_en.desc())).all()
    rep = {r["campana_id"]: r for r in _reporte(db, u, None, None)["por_campana"]}
    db.commit()
    return {"campanas": [campana_dict(c, cfg, {k: v for k, v in rep.get(c.id, {}).items() if k not in ("campana_id", "nombre", "canal")}) for c in cs],
            "formulario_general": enlace_formulario(cfg.formulario_token) if cfg.formulario_activo else None,
            "whatsapp_general": enlace_whatsapp(cfg)}


class CampanaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
    canal: str
    inversion: str | None = Field(None, max_length=20)
    inicio: date | None = None
    fin: date | None = None
    notas: str | None = Field(None, max_length=500)
    id_externo: str | None = Field(None, max_length=80)
    activa: bool = True


@router.post("/campanas", status_code=201)
def crear_campana(d: CampanaIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    if d.canal not in cat.CANALES:
        raise HTTPException(422, "Canal inválido.")
    cod = base.codigo()
    while db.scalar(select(m.LdCampana.id).where(m.LdCampana.organizacion_id == u.organizacion_id, m.LdCampana.codigo == cod)):
        cod = base.codigo()
    c = m.LdCampana(organizacion_id=u.organizacion_id, nombre=d.nombre.strip(), canal=d.canal, codigo=cod, enlace_token=base.token_publico(),
                    inversion=_dinero(d.inversion), inicio=d.inicio, fin=d.fin, notas=_txt(d.notas, 500), id_externo=_txt(d.id_externo, 80),
                    activa=d.activa, creado_por_id=u.id)
    db.add(c)
    db.flush()
    auditar(db, u, "ld_campana_creada", "ld_campana", c.id, {"canal": c.canal}, request)
    db.commit()
    return campana_dict(c, base.config(db, u.organizacion_id))


class CampanaCambio(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=160)
    canal: str | None = None
    inversion: str | None = Field(None, max_length=20)
    inicio: date | None = None
    fin: date | None = None
    notas: str | None = Field(None, max_length=500)
    id_externo: str | None = Field(None, max_length=80)
    activa: bool | None = None


@router.patch("/campanas/{cid}")
def cambiar_campana(cid: int, d: CampanaCambio, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    c = _de_org(db, m.LdCampana, cid, u)
    datos = d.model_dump(exclude_unset=True)
    if "canal" in datos and datos["canal"] not in cat.CANALES:
        raise HTTPException(422, "Canal inválido.")
    if "inversion" in datos:
        datos["inversion"] = _dinero(datos["inversion"])
    for k, v in datos.items():
        setattr(c, k, v.strip() if isinstance(v, str) and k != "inversion" else v)
    auditar(db, u, "ld_campana_actualizada", "ld_campana", c.id, {"campos": sorted(datos)}, request)
    db.commit()
    return campana_dict(c, base.config(db, u.organizacion_id))


@router.post("/campanas/{cid}/renovar-enlace")
def renovar_enlace_campana(cid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    c = _de_org(db, m.LdCampana, cid, u)
    c.enlace_token = base.token_publico()
    auditar(db, u, "ld_campana_enlace_renovado", "ld_campana", c.id, None, request)
    db.commit()
    return campana_dict(c, base.config(db, u.organizacion_id))


# ---------- reportes ----------

def _reporte(db: Session, u: m.Usuario, desde: date | None, hasta: date | None) -> dict:
    org = u.organizacion_id
    et = _etapas(db, u)
    q = select(m.LdProspecto).where(m.LdProspecto.organizacion_id == org, m.LdProspecto.borrador.is_(False))
    xs = db.scalars(q).all()
    if desde:
        xs = [p for p in xs if base_fecha(p.creado_en) >= desde]
    if hasta:
        xs = [p for p in xs if base_fecha(p.creado_en) <= hasta]
    ids = [p.id for p in xs]
    consultas: dict[int, dict] = {}
    if ids:
        for a in db.scalars(select(m.LdAccion).where(m.LdAccion.prospecto_id.in_(ids), m.LdAccion.tipo == "consulta")):
            c = consultas.setdefault(a.prospecto_id, {"agendada": False, "realizada": False})
            c["agendada"] = True
            c["realizada"] = c["realizada"] or bool(a.completada_en)
    claves_realizada = {"consulta_realizada", "propuesta_enviada"}

    def met(grupo: list[m.LdProspecto]) -> dict:
        tipo = lambda p: et[p.etapa_id].tipo if p.etapa_id in et else "abierta"  # noqa: E731
        ganados = [p for p in grupo if tipo(p) == "ganada"]
        realizadas = [p for p in grupo if consultas.get(p.id, {}).get("realizada") or (et.get(p.etapa_id) and et[p.etapa_id].clave in claves_realizada)
                      or tipo(p) == "ganada"]
        agendadas = [p for p in grupo if consultas.get(p.id, {}).get("agendada") or p in realizadas]
        horas = [(p.primera_respuesta_en - p.creado_en).total_seconds() / 3600 for p in grupo if p.primera_respuesta_en]
        return {"recibidos": len(grupo), "consultas_agendadas": len(agendadas), "consultas_realizadas": len(realizadas), "contratados": len(ganados),
                "no_contratados": sum(1 for p in grupo if tipo(p) == "perdida"),
                "conversion": round(100 * len(ganados) / len(grupo), 1) if grupo else None,
                "primera_respuesta_horas": round(sum(horas) / len(horas), 1) if horas else None}

    por_canal = []
    for canal in sorted({p.canal for p in xs}, key=lambda c: list(cat.CANALES).index(c) if c in cat.CANALES else 99):
        por_canal.append({"canal": canal, "canal_texto": cat.CANALES.get(canal, canal), **met([p for p in xs if p.canal == canal])})
    camps = db.scalars(select(m.LdCampana).where(m.LdCampana.organizacion_id == org)).all()
    por_campana = []
    for c in camps:
        mm = met([p for p in xs if p.campana_id == c.id])
        costo = (c.inversion / mm["contratados"]).quantize(Decimal("0.01")) if c.inversion is not None and mm["contratados"] else None
        costo_p = (c.inversion / mm["recibidos"]).quantize(Decimal("0.01")) if c.inversion is not None and mm["recibidos"] else None
        por_campana.append({"campana_id": c.id, "nombre": c.nombre, "canal": c.canal, **mm,
                            "inversion": str(c.inversion) if c.inversion is not None else None,
                            "costo_por_cliente": str(costo) if costo is not None else None, "costo_por_prospecto": str(costo_p) if costo_p is not None else None})
    motivos: dict[str, int] = {}
    for p in xs:
        if p.etapa_id in et and et[p.etapa_id].tipo == "perdida":
            k = p.motivo_perdida or "Sin motivo registrado"
            motivos[k] = motivos.get(k, 0) + 1
    cfg = base.config(db, org)
    integraciones = meta.wa_conectado(cfg) or meta.meta_conectado(cfg) or bool(cfg.entrada_clave_hash)
    return {"total": met(xs), "por_canal": por_canal, "por_campana": sorted(por_campana, key=lambda r: -r["recibidos"]),
            "motivos_perdida": sorted(({"motivo": k, "total": v} for k, v in motivos.items()), key=lambda r: -r["total"]),
            "sin_origen": sum(1 for p in xs if p.canal == "otro" and not p.campana_id),
            "aviso_origen": None if integraciones or camps else
            "Aún no hay campañas ni integraciones conectadas: el origen de cada prospecto depende de lo que capture su equipo. "
            "Cree una campaña o conecte una fuente en «Campañas» y «Configuración»."}


def base_fecha(dt: datetime) -> date:
    from zoneinfo import ZoneInfo
    return dt.astimezone(ZoneInfo("America/Mexico_City")).date()


@router.get("/reportes")
def reportes(desde: date | None = None, hasta: date | None = None, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = _reporte(db, u, desde, hasta)
    db.commit()
    return r


# ---------- exportar ----------

def _celda(v) -> str:
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v  # evita fórmulas al abrirlo en Excel


@router.get("/exportar")
def exportar(formato: str = "xlsx", vista: str = "todos", request: Request = None, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Administradores: todos los prospectos. Analistas: solo los que tienen asignados."""
    if formato not in ("xlsx", "csv") or vista not in VISTAS:
        raise HTTPException(422, "Formato o vista inválidos.")
    xs = _seleccion(db, u, vista)
    if u.rol != "administrador":
        xs = [p for p in xs if p.responsable_id == u.id]
    filas = _filas(db, u, xs)
    cab = ["Folio", "Nombre", "Teléfono", "Correo", "Ciudad", "Materia", "Canal", "Campaña", "Etapa", "Responsable", "Próximo paso", "Fecha",
           "Registrado", "Contratado", "Motivo (no contratado)"]
    datos = [[f["id"], f["nombre"], f["telefono"], f["email"], f["ciudad"], f["materia"], f["canal_texto"], f["campana"], f["etapa"], f["responsable"],
              (f["proxima"] or {}).get("tipo_texto"), (f["proxima"] or {}).get("fecha"), f["creado_en"][:10], (f["contratado_en"] or "")[:10] or None,
              f["motivo_perdida"]] for f in filas]
    auditar(db, u, "ld_exportado", None, None, {"formato": formato, "filas": len(datos), "vista": vista}, request)
    db.commit()
    if formato == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cab)
        for r in datos:
            w.writerow([_celda(v) for v in r])
        return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={**PRIVADO, "Content-Disposition": 'attachment; filename="prospectos.csv"', "Access-Control-Expose-Headers": "Content-Disposition"})
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Prospectos"
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in datos:
        ws.append([_celda(v) if isinstance(v, str) else v for v in r])
    out = io.BytesIO()
    wb.save(out)
    return Response(out.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={**PRIVADO, "Content-Disposition": 'attachment; filename="prospectos.xlsx"', "Access-Control-Expose-Headers": "Content-Disposition"})


# ---------- configuración e integraciones ----------

@router.get("/config")
def ver_config(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    url = ajustes().url_publica.rstrip("/")
    falta = meta.faltantes_plataforma()
    db.commit()
    return {"materias": base.materias(cfg), "motivos_perdida": base.motivos(cfg), "dias_sin_actividad": cfg.dias_sin_actividad,
            "formulario": {"activo": cfg.formulario_activo, "enlace": enlace_formulario(cfg.formulario_token)},
            "entrada": {"configurada": bool(cfg.entrada_clave_hash), "pista": cfg.entrada_clave_pista, "url": f"{url}/api/leads-entrada"},
            "whatsapp": {"conectado": meta.wa_conectado(cfg), "phone_number_id": cfg.wa_phone_number_id, "numero": cfg.wa_numero,
                         "plantilla": cfg.wa_plantilla, "plantilla_idioma": cfg.wa_plantilla_idioma,
                         "conectado_en": cfg.wa_conectado_en.isoformat() if cfg.wa_conectado_en else None,
                         "webhook": f"{url}/api/whatsapp/webhook", "faltan_plataforma": falta},
            "meta": {"conectado": meta.meta_conectado(cfg), "page_id": cfg.meta_page_id, "pagina": cfg.meta_page_nombre,
                     "conectado_en": cfg.meta_conectado_en.isoformat() if cfg.meta_conectado_en else None,
                     "webhook": f"{url}/api/meta/webhook", "faltan_plataforma": falta},
            "correo": {"configurado": correo.configurado()}}


class ConfigCambio(BaseModel):
    materias: list[str] | None = None
    motivos_perdida: list[str] | None = None
    dias_sin_actividad: int | None = Field(None, ge=1, le=90)
    formulario_activo: bool | None = None


def _lista(v: list[str], n: int) -> list[str]:
    limpia = []
    for x in v:
        x = (x or "").strip()[:n]
        if x and x not in limpia:
            limpia.append(x)
    return limpia[:60]


@router.patch("/config")
def cambiar_config(d: ConfigCambio, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    datos = d.model_dump(exclude_unset=True)
    if "materias" in datos:
        cfg.materias = _lista(datos["materias"], 120) or None
    if "motivos_perdida" in datos:
        cfg.motivos_perdida = _lista(datos["motivos_perdida"], 120) or None
    if datos.get("dias_sin_actividad"):
        cfg.dias_sin_actividad = datos["dias_sin_actividad"]
    if "formulario_activo" in datos:
        cfg.formulario_activo = bool(datos["formulario_activo"])
    auditar(db, u, "ld_config_actualizada", "ld_config", cfg.id, {"campos": sorted(datos)}, request)
    db.commit()
    return ver_config(u, db)


@router.post("/config/formulario/renovar")
def renovar_formulario(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    cfg.formulario_token = base.token_publico()
    auditar(db, u, "ld_formulario_renovado", "ld_config", cfg.id, None, request)
    db.commit()
    return ver_config(u, db)


@router.post("/config/entrada")
def nueva_clave_entrada(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Clave para que otros sistemas (Zapier, Make, Google Ads, su sitio web) envíen prospectos.
    Se muestra UNA sola vez; Nomira guarda solo su huella."""
    import secrets
    cfg = base.config(db, u.organizacion_id)
    clave = "nld_" + secrets.token_urlsafe(24)
    cfg.entrada_clave_hash, cfg.entrada_clave_pista = base.huella(clave), clave[-4:]
    auditar(db, u, "ld_clave_entrada_generada", "ld_config", cfg.id, None, request)
    db.commit()
    return {**ver_config(u, db), "clave": clave}


@router.delete("/config/entrada")
def quitar_clave_entrada(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    cfg.entrada_clave_hash = cfg.entrada_clave_pista = None
    auditar(db, u, "ld_clave_entrada_revocada", "ld_config", cfg.id, None, request)
    db.commit()
    return ver_config(u, db)


class WhatsAppIn(BaseModel):
    phone_number_id: str = Field(min_length=5, max_length=40, pattern=r"^\d+$")
    numero: str | None = Field(None, max_length=30)
    token: str | None = Field(None, min_length=20, max_length=1000)  # vacío: conserva el guardado
    plantilla: str | None = Field(None, max_length=120, pattern=r"^[a-z0-9_]*$")
    plantilla_idioma: str | None = Field(None, max_length=10)


@router.put("/config/whatsapp")
def conectar_whatsapp(d: WhatsAppIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    if not d.token and not cfg.wa_token_cifrado:
        raise HTTPException(422, "Falta el token de acceso.")
    otro = db.scalar(select(m.LdConfig).where(m.LdConfig.wa_phone_number_id == d.phone_number_id, m.LdConfig.organizacion_id != u.organizacion_id))
    if otro:
        raise HTTPException(409, "Ese número ya está conectado en otra organización.")
    cfg.wa_phone_number_id, cfg.wa_numero = d.phone_number_id, _txt(d.numero, 30)
    cfg.wa_plantilla, cfg.wa_plantilla_idioma = _txt(d.plantilla, 120), _txt(d.plantilla_idioma, 10) or "es_MX"
    if d.token:
        cfg.wa_token_cifrado = cifrar(d.token.strip())
    cfg.wa_conectado_en = m.ahora()
    auditar(db, u, "ld_whatsapp_conectado", "ld_config", cfg.id, {"phone_number_id": d.phone_number_id}, request)
    db.commit()
    return ver_config(u, db)


@router.delete("/config/whatsapp")
def desconectar_whatsapp(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    cfg.wa_phone_number_id = cfg.wa_numero = cfg.wa_token_cifrado = cfg.wa_plantilla = cfg.wa_conectado_en = None
    auditar(db, u, "ld_whatsapp_desconectado", "ld_config", cfg.id, None, request)
    db.commit()
    return ver_config(u, db)


class MetaIn(BaseModel):
    page_id: str = Field(min_length=5, max_length=40, pattern=r"^\d+$")
    token: str = Field(min_length=20, max_length=1000)


@router.put("/config/meta")
def conectar_meta(d: MetaIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Conecta los anuncios de clientes potenciales: Nomira suscribe la página a los avisos de Meta.
    Si Meta rechaza el token o la página, no se guarda nada."""
    if meta.faltantes_plataforma():
        raise HTTPException(409, {"mensaje": "Falta configurar el servidor de Nomira para recibir avisos de Meta.", "faltantes": meta.faltantes_plataforma()})
    otro = db.scalar(select(m.LdConfig).where(m.LdConfig.meta_page_id == d.page_id, m.LdConfig.organizacion_id != u.organizacion_id))
    if otro:
        raise HTTPException(409, "Esa página ya está conectada en otra organización.")
    try:
        nombre = meta.suscribir_pagina(d.page_id, d.token.strip())
    except meta.MetaError as e:
        raise HTTPException(502, str(e))
    cfg = base.config(db, u.organizacion_id)
    cfg.meta_page_id, cfg.meta_page_nombre, cfg.meta_token_cifrado, cfg.meta_conectado_en = d.page_id, _txt(nombre, 200), cifrar(d.token.strip()), m.ahora()
    auditar(db, u, "ld_meta_conectado", "ld_config", cfg.id, {"page_id": d.page_id}, request)
    db.commit()
    return ver_config(u, db)


@router.delete("/config/meta")
def desconectar_meta(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cfg = base.config(db, u.organizacion_id)
    cfg.meta_page_id = cfg.meta_page_nombre = cfg.meta_token_cifrado = cfg.meta_conectado_en = None
    auditar(db, u, "ld_meta_desconectado", "ld_config", cfg.id, None, request)
    db.commit()
    return ver_config(u, db)
