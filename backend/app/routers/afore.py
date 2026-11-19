"""API de Nomira AFORE para el despacho. Todas las rutas exigen el módulo activo (vea main.py), se
filtran por organización y respetan los casos restringidos. Nomira organiza información: no decide
derechos, beneficiarios, estrategia ni resultados."""
from __future__ import annotations

import hashlib
import io
import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, puede_editar, solo_admin, usuario_actual
from ..services import modulos
from ..services.afore import catalogos as cat
from ..services.afore import curp_oficial, mensajes as msj, portal, revision, whatsapp
from ..services.afore.cifrado import cifrar, descifrar
from ..services.afore.identificadores import (enmascarar_telefono, limpiar, pista_curp, pista_nss, revisar_curp, revisar_nss,
                                              telefono)
from ..services.evidencia import solicitudes as sol
from .evidencia import EXT, MIME, PRIVADO, _leer_archivo, puede_ver

router = APIRouter(prefix="/api/afore", tags=["Nomira AFORE"])
AFOREWEB = "https://www.aforeweb.com.mx/localiza-tu-afore"


# ---------- utilidades y permisos ----------

def _txt(v: str | None, n: int) -> str | None:
    v = (v or "").strip()
    return v[:n] or None


def _nombres(db: Session, org: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org)).all())


def _puede_ver_caso(u: m.Usuario, c: m.AfCaso) -> bool:
    return not c.restringido or u.rol == "administrador" or u.id in (c.responsable_id, c.creado_por_id, c.siguiente_responsable_id)


def _casos_visibles(db: Session, u: m.Usuario):
    q = select(m.AfCaso).where(m.AfCaso.organizacion_id == u.organizacion_id)
    if u.rol != "administrador":
        q = q.where((m.AfCaso.restringido.is_(False)) | (m.AfCaso.responsable_id == u.id) | (m.AfCaso.creado_por_id == u.id)
                    | (m.AfCaso.siguiente_responsable_id == u.id))
    return q


def _caso(db: Session, cid: int, u: m.Usuario) -> m.AfCaso:
    c = db.get(m.AfCaso, cid)
    if not c or c.organizacion_id != u.organizacion_id or not _puede_ver_caso(u, c):
        raise HTTPException(404, "No encontrado.")
    return c


def _de_org(db: Session, modelo, oid: int, u: m.Usuario):
    x = db.get(modelo, oid)
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    if hasattr(x, "caso_id") and x.caso_id:
        _caso(db, x.caso_id, u)
    return x


def _cliente(db: Session, cid: int, u: m.Usuario) -> m.AfCliente:
    return _de_org(db, m.AfCliente, cid, u)


def _responsable(db: Session, uid: int | None, u: m.Usuario) -> int | None:
    if uid is None:
        return None
    x = db.get(m.Usuario, uid)
    if not x or x.organizacion_id != u.organizacion_id or x.eliminado_en:
        raise HTTPException(422, "El responsable debe ser un usuario de su organización.")
    return x.id


def _aud(db, u, accion, entidad, eid, caso_id=None, request=None, **detalle):
    auditar(db, u, accion, entidad, eid, {**({"caso_id": caso_id} if caso_id else {}), **detalle}, request)


def _cfg(db, u):
    return msj.config(db, u.organizacion_id)


def tipos(db: Session, org: int) -> dict[str, str]:
    cfg = db.scalar(select(m.AfConfig).where(m.AfConfig.organizacion_id == org))
    extra = {f"extra:{i}": t for i, t in enumerate((cfg.tipos_extra if cfg else None) or [])}
    return {**{k: v for k, v in cat.TIPOS_PROBLEMA.items() if k != "otro"}, **extra, "otro": cat.TIPOS_PROBLEMA["otro"]}


def checklist_de(db: Session, org: int, tipo: str) -> list[str]:
    cfg = db.scalar(select(m.AfConfig).where(m.AfConfig.organizacion_id == org))
    propios = (cfg.checklists or {}) if cfg else {}
    return propios.get(tipo) or cat.CHECKLIST_DEFECTO.get(tipo) or cat.CHECKLIST_DEFECTO["otro"]


# ---------- representaciones ----------

def cliente_dict(c: m.AfCliente, db: Session, completo: bool = False) -> dict:
    cons = db.scalars(select(m.AfConsentimiento).where(m.AfConsentimiento.cliente_id == c.id).order_by(m.AfConsentimiento.id.desc())).all()
    d = {"id": c.id, "nombre": c.nombre, "telefono": c.telefono if completo else enmascarar_telefono(c.telefono),
         "telefono_mascara": enmascarar_telefono(c.telefono), "email": c.email,
         "curp": c.curp_pista and f"{c.curp_pista.split('…')[0]}••••••••••••{c.curp_pista.split('…')[-1]}",
         "nss": c.nss_pista and f"•••••••{c.nss_pista.lstrip('…')}", "tiene_curp": bool(c.curp_cifrado), "tiene_nss": bool(c.nss_cifrado),
         "titular_estado": c.titular_estado, "titular_estado_texto": cat.TITULAR.get(c.titular_estado),
         "relacion": c.relacion, "relacion_texto": cat.RELACIONES.get(c.relacion), "preferencia_contacto": c.preferencia_contacto,
         "consentimientos": [{"id": x.id, "canal": x.canal, "alcance": x.alcance, "medio": x.medio, "otorgado_en": x.otorgado_en.isoformat(),
                              "revocado_en": x.revocado_en.isoformat() if x.revocado_en else None, "revocado_medio": x.revocado_medio}
                             for x in cons],
         "consiente": {k: any(x.canal == k and not x.revocado_en for x in cons) for k in ("whatsapp", "correo")},
         "creado_en": c.creado_en.isoformat()}
    if completo:
        d["notas"] = c.notas
    return d


def caso_dict(c: m.AfCaso, db: Session, nombres: dict, cliente: m.AfCliente | None = None, extra: dict | None = None) -> dict:
    cliente = cliente or db.get(m.AfCliente, c.cliente_id)
    t = tipos(db, c.organizacion_id)
    return {"id": c.id, "cliente_id": c.cliente_id, "cliente": cliente.nombre if cliente else None, "titular_nombre": c.titular_nombre,
            "estado": c.estado, "estado_texto": cat.ESTADOS_CASO.get(c.estado, c.estado), "tipo_problema": c.tipo_problema,
            "tipo_texto": (c.tipo_otro or t.get(c.tipo_problema, "Otro")) if c.tipo_problema == "otro" else t.get(c.tipo_problema, c.tipo_problema),
            "tipo_otro": c.tipo_otro, "datos": c.datos or {}, "identificador_interno": c.identificador_interno,
            "responsable_id": c.responsable_id, "responsable": nombres.get(c.responsable_id), "restringido": c.restringido,
            "siguiente_actividad": c.siguiente_actividad, "siguiente_fecha": c.siguiente_fecha.isoformat() if c.siguiente_fecha else None,
            "siguiente_responsable_id": c.siguiente_responsable_id, "siguiente_responsable": nombres.get(c.siguiente_responsable_id),
            "portal_visible": c.portal_visible, "estado_publico": c.estado_publico, "siguiente_paso_publico": c.siguiente_paso_publico,
            "publico_actualizado_en": c.publico_actualizado_en.isoformat() if c.publico_actualizado_en else None,
            "creado_por": nombres.get(c.creado_por_id), "creado_en": c.creado_en.isoformat(), "actualizado_en": c.actualizado_en.isoformat(),
            **(extra or {})}


def _monto(v) -> str | None:
    if v in (None, ""):
        return None
    try:
        d = Decimal(str(v).replace("$", "").replace(",", "").strip())
    except InvalidOperation:
        raise HTTPException(422, "Monto inválido. Use el formato 1234.56")
    if not d.is_finite() or abs(d) >= Decimal("1e12"):
        raise HTTPException(422, "Monto inválido.")
    return str(d.quantize(Decimal("0.01")))


def _datos(entrada: dict | None, previos: dict | None = None) -> dict:
    """Cada dato del caso lleva su estado: informado, «No lo sé», «Pendiente de confirmar» o «No aplica»."""
    salida = dict(previos or {})
    for k, v in (entrada or {}).items():
        if k not in cat.CAMPOS_DATO or not isinstance(v, dict):
            continue
        estado = v.get("estado") or ("informado" if v.get("valor") not in (None, "") else "pendiente")
        if estado not in cat.ESTADOS_DATO:
            raise HTTPException(422, "Estado de dato inválido.")
        valor = v.get("valor") if estado == "informado" else None
        valor = _monto(valor) if k in cat.CAMPOS_MONTO else _txt(valor, 200)
        salida[k] = {"valor": valor, "estado": estado if (valor or estado != "informado") else "pendiente"}
    return salida


def _avisar(db: Session, caso: m.AfCaso, clave: str, origen: str, u: m.Usuario | None):
    """Mensaje operativo al cliente (requiere aprobación salvo que el despacho lo haya hecho automático).
    No se duplica si ya hay uno igual sin enviar para el mismo caso."""
    previo = db.scalar(select(m.AfMensaje.id).where(m.AfMensaje.caso_id == caso.id, m.AfMensaje.plantilla == clave,
                                                    m.AfMensaje.estado.in_(("borrador", "esperando_aprobacion"))))
    if previo:
        return None
    cliente = db.get(m.AfCliente, caso.cliente_id)
    return msj.generar(db, caso.organizacion_id, cliente, caso, clave, origen, u)


# ---------- catálogos y resumen ----------

@router.get("/catalogos")
def catalogos(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    cfg = _cfg(db, u)
    t = tipos(db, u.organizacion_id)
    db.commit()
    return {"tipos": t, "checklists": {k: checklist_de(db, u.organizacion_id, k) for k in t},
            "estados_requisito": cat.ESTADOS_REQUISITO, "estados_caso": cat.ESTADOS_CASO, "relaciones": cat.RELACIONES,
            "titular": cat.TITULAR, "contacto": cat.CONTACTO, "estados_dato": cat.ESTADOS_DATO, "campos_dato": cat.CAMPOS_DATO,
            "instituciones": cat.INSTITUCIONES, "afores": cat.AFORES, "tipos_actividad": cat.TIPOS_ACTIVIDAD,
            "tipos_plazo": cat.TIPOS_PLAZO, "estados_mensaje": msj.ESTADOS, "aforeweb": AFOREWEB,
            "reglas_plazo": cfg.reglas_plazo or [], "evidencia_activa": "evidencia" in modulos.activos(db, u.organizacion_id),
            "whatsapp_conectado": whatsapp.conectado(cfg), "responsables": [
                {"id": x.id, "nombre": x.nombre} for x in db.scalars(select(m.Usuario).where(
                    m.Usuario.organizacion_id == u.organizacion_id, m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None),
                    m.Usuario.rol != "consulta").order_by(m.Usuario.nombre))]}


def _esperando(db: Session, ids: list[int]) -> dict[int, date]:
    """Casos con una solicitud/queja sin respuesta posterior: fecha de la solicitud más antigua pendiente."""
    res: dict[int, date] = {}
    if not ids:
        return res
    acts = db.scalars(select(m.AfActividad).where(m.AfActividad.caso_id.in_(ids)).order_by(m.AfActividad.fecha, m.AfActividad.id)).all()
    respondidas = {a.responde_a_id for a in acts if a.responde_a_id}
    ultima_resp: dict[int, date] = {}
    for a in acts:
        if a.tipo == "respuesta_recibida":
            ultima_resp[a.caso_id] = a.fecha
    for a in acts:
        if a.tipo in ("solicitud_enviada", "queja") and a.id not in respondidas and (a.caso_id not in ultima_resp or ultima_resp[a.caso_id] < a.fecha):
            res.setdefault(a.caso_id, a.fecha)
    return res


@router.get("/resumen")
def resumen(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """¿Qué requiere atención ahora? Cada grupo trae los elementos para abrirlos directamente."""
    hoy = date.today()
    casos = db.scalars(_casos_visibles(db, u).where(m.AfCaso.estado != "cerrado")).all()
    ids = [c.id for c in casos]
    porid = {c.id: c for c in casos}
    clientes = {c.id: c for c in db.scalars(select(m.AfCliente).where(m.AfCliente.organizacion_id == u.organizacion_id))}
    ref = lambda c, nota="": {"caso_id": c.id, "cliente": clientes[c.cliente_id].nombre, "tipo": tipos(db, u.organizacion_id).get(c.tipo_problema, c.tipo_problema), "nota": nota}  # noqa: E731
    reqs = db.scalars(select(m.AfRequisito).where(m.AfRequisito.caso_id.in_(ids or [0]))).all()
    docs_pend: dict[int, int] = {}
    por_revisar: dict[int, int] = {}
    for r in reqs:
        if r.estado in ("solicitado", "requiere_correccion"):
            docs_pend[r.caso_id] = docs_pend.get(r.caso_id, 0) + 1
        if r.estado in ("recibido", "por_revisar"):
            por_revisar[r.caso_id] = por_revisar.get(r.caso_id, 0) + 1
    esperando = _esperando(db, ids)
    hace7 = hoy - timedelta(days=7)
    respuestas = db.scalars(select(m.AfActividad).where(m.AfActividad.caso_id.in_(ids or [0]), m.AfActividad.tipo == "respuesta_recibida",
                                                        m.AfActividad.fecha >= hace7).order_by(m.AfActividad.fecha.desc())).all()
    nuevos_cliente = db.scalars(select(m.AfDocumento).where(m.AfDocumento.caso_id.in_(ids or [0]), m.AfDocumento.origen == "cliente",
                                                            m.AfDocumento.recepcion_confirmada_en.is_(None))).all()
    plazos = db.scalars(select(m.AfPlazo).where(m.AfPlazo.caso_id.in_(ids or [0]), m.AfPlazo.completado_en.is_(None),
                                                m.AfPlazo.fecha <= hoy + timedelta(days=3)).order_by(m.AfPlazo.fecha)).all()
    seguimientos = [{**ref(porid[p.caso_id], cat.TIPOS_PLAZO[p.tipo]), "descripcion": p.descripcion, "fecha": p.fecha.isoformat(),
                     "vencido": p.fecha < hoy} for p in plazos]
    seguimientos += [{**ref(c, "Siguiente actividad"), "descripcion": c.siguiente_actividad, "fecha": c.siguiente_fecha.isoformat(),
                      "vencido": c.siguiente_fecha < hoy} for c in casos if c.siguiente_fecha and c.siguiente_fecha <= hoy + timedelta(days=3)]
    mensajes = db.scalars(select(m.AfMensaje).where(m.AfMensaje.organizacion_id == u.organizacion_id,
                                                    m.AfMensaje.estado.in_(("esperando_aprobacion", "fallido", "por_asignar", "borrador")))
                          .order_by(m.AfMensaje.id.desc())).all()
    mensajes = [x for x in mensajes if not x.caso_id or x.caso_id in porid]
    return {
        "documentos_pendientes": [{**ref(porid[k]), "n": n} for k, n in docs_pend.items()],
        "documentos_por_revisar": [{**ref(porid[k]), "n": n} for k, n in por_revisar.items()]
                                  + [{**ref(porid[d.caso_id], "Enviado por el cliente"), "documento": d.nombre_original, "documento_id": d.id}
                                     for d in nuevos_cliente],
        "sin_siguiente_actividad": [ref(c) for c in casos if c.estado != "borrador" and not c.siguiente_actividad],
        "esperando_respuesta": [{**ref(porid[k]), "desde": f.isoformat(), "dias": (hoy - f).days} for k, f in sorted(esperando.items(), key=lambda x: x[1])],
        "respuestas_recientes": [{**ref(porid[a.caso_id]), "fecha": a.fecha.isoformat(), "institucion": a.institucion, "folio": a.folio} for a in respuestas],
        "seguimientos": sorted(seguimientos, key=lambda x: x["fecha"]),
        "mensajes": {"por_aprobar": sum(1 for x in mensajes if x.estado == "esperando_aprobacion"),
                     "con_error": sum(1 for x in mensajes if x.estado == "fallido"),
                     "por_asignar": sum(1 for x in mensajes if x.estado == "por_asignar"),
                     "borradores": sum(1 for x in mensajes if x.estado == "borrador")},
        "borradores": [ref(c) for c in casos if c.estado == "borrador"],
    }


# ---------- clientes ----------

class ClienteIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    telefono: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=254)
    curp: str | None = Field(None, max_length=30)
    nss: str | None = Field(None, max_length=20)
    titular_estado: str = "vive"
    relacion: str = "titular"
    preferencia_contacto: str = "correo"
    notas: str | None = Field(None, max_length=3000)


class ClienteCambio(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=200)
    telefono: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=254)
    curp: str | None = Field(None, max_length=30)
    nss: str | None = Field(None, max_length=20)
    titular_estado: str | None = None
    relacion: str | None = None
    preferencia_contacto: str | None = None
    notas: str | None = Field(None, max_length=3000)


def _aplicar_cliente(c: m.AfCliente, datos: dict) -> dict:
    """Valida y guarda; devuelve la revisión local de CURP/NSS (no bloquea: el abogado decide)."""
    revisiones = {}
    for k, catalogo in (("titular_estado", cat.TITULAR), ("relacion", cat.RELACIONES), ("preferencia_contacto", cat.CONTACTO)):
        if k in datos and datos[k] is not None:
            if datos[k] not in catalogo:
                raise HTTPException(422, f"Valor inválido para {k}.")
            setattr(c, k, datos[k])
    if "nombre" in datos and datos["nombre"]:
        c.nombre = datos["nombre"].strip()
    if "telefono" in datos:
        t = telefono(datos["telefono"])
        if datos["telefono"] and not t:
            raise HTTPException(422, "Teléfono inválido: escriba 10 dígitos (o con lada de país).")
        c.telefono = t
    if "email" in datos:
        e = (datos["email"] or "").strip().lower() or None
        if e and not sol.email_valido(e):
            raise HTTPException(422, "Correo inválido.")
        c.email = e
    if "curp" in datos:
        v = limpiar(datos["curp"]) or None
        c.curp_cifrado, c.curp_pista = (cifrar(v), pista_curp(v)) if v else (None, None)
        if v:
            revisiones["curp"] = revisar_curp(v)
    if "nss" in datos:
        v = "".join(ch for ch in (datos["nss"] or "") if ch.isdigit()) or None
        c.nss_cifrado, c.nss_pista = (cifrar(v), pista_nss(v)) if v else (None, None)
        if v:
            revisiones["nss"] = revisar_nss(v)
    if "notas" in datos:
        c.notas = _txt(datos["notas"], 3000)
    return revisiones


@router.get("/clientes")
def listar_clientes(q: str | None = None, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    query = select(m.AfCliente).where(m.AfCliente.organizacion_id == u.organizacion_id).order_by(m.AfCliente.nombre)
    if q:
        query = query.where(m.AfCliente.nombre.ilike(f"%{q.strip()[:60]}%"))
    clientes = db.scalars(query).all()
    visibles = {c.id for c in db.scalars(_casos_visibles(db, u))}
    n = dict(db.execute(select(m.AfCaso.cliente_id, func.count()).where(m.AfCaso.id.in_(visibles or [0])).group_by(m.AfCaso.cliente_id)).all())
    return [{**cliente_dict(c, db), "casos": n.get(c.id, 0)} for c in clientes]


@router.post("/clientes", status_code=201)
def crear_cliente(d: ClienteIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = m.AfCliente(organizacion_id=u.organizacion_id, nombre=d.nombre.strip(), creado_por_id=u.id)
    rev = _aplicar_cliente(c, d.model_dump())
    db.add(c)
    db.flush()
    _aud(db, u, "af_cliente_creado", "af_cliente", c.id, request=request)  # sin CURP/NSS en la bitácora
    db.commit()
    return {**cliente_dict(c, db, True), "revision": rev}


@router.get("/clientes/{cid}")
def ver_cliente(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    nombres = _nombres(db, u.organizacion_id)
    casos = db.scalars(_casos_visibles(db, u).where(m.AfCaso.cliente_id == c.id).order_by(m.AfCaso.id.desc())).all()
    accesos = db.scalars(select(m.AfAcceso).where(m.AfAcceso.cliente_id == c.id).order_by(m.AfAcceso.id.desc()).limit(10)).all()
    return {**cliente_dict(c, db, completo=u.rol != "consulta"), "casos": [caso_dict(x, db, nombres, c) for x in casos],
            "accesos": [{"id": a.id, "estado": portal.estado(a), "pista": a.token_pista, "expira_en": a.expira_en.isoformat(),
                         "requiere_codigo": a.requiere_codigo, "ultimo_uso_en": a.ultimo_uso_en.isoformat() if a.ultimo_uso_en else None,
                         "creado_por": nombres.get(a.creado_por_id), "creado_en": a.creado_en.isoformat()} for a in accesos]}


@router.patch("/clientes/{cid}")
def cambiar_cliente(cid: int, d: ClienteCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    datos = d.model_dump(exclude_unset=True)
    rev = _aplicar_cliente(c, datos)
    _aud(db, u, "af_cliente_modificado", "af_cliente", c.id, request=request, campos=sorted(datos))
    db.commit()
    return {**cliente_dict(c, db, True), "revision": rev}


class Revelar(BaseModel):
    campo: str


@router.post("/clientes/{cid}/revelar")
def revelar(cid: int, d: Revelar, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Muestra CURP o NSS completos a quien lo necesita para trabajar; queda registrado quién y cuándo."""
    c = _cliente(db, cid, u)
    if d.campo not in ("curp", "nss"):
        raise HTTPException(422, "Campo inválido.")
    valor = descifrar(c.curp_cifrado if d.campo == "curp" else c.nss_cifrado)
    _aud(db, u, "af_dato_sensible_mostrado", "af_cliente", c.id, request=request, campo=d.campo)
    db.commit()
    return {"valor": valor, "revision": (revisar_curp if d.campo == "curp" else revisar_nss)(valor) if valor else None}


class ConsentimientoIn(BaseModel):
    canal: str
    alcance: str = Field("Actualizaciones de su trámite y avisos del despacho", max_length=300)
    medio: str = Field("verbal", max_length=40)


@router.post("/clientes/{cid}/consentimientos", status_code=201)
def dar_consentimiento(cid: int, d: ConsentimientoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    if d.canal not in ("whatsapp", "correo"):
        raise HTTPException(422, "Canal inválido.")
    if msj.consentimiento(db, c.id, d.canal):
        raise HTTPException(409, "Ya tiene un consentimiento vigente para ese canal.")
    x = m.AfConsentimiento(organizacion_id=u.organizacion_id, cliente_id=c.id, canal=d.canal, alcance=d.alcance.strip(),
                           medio=d.medio.strip(), registrado_por_id=u.id)
    db.add(x)
    db.flush()
    _aud(db, u, "af_consentimiento_registrado", "af_cliente", c.id, request=request, canal=d.canal, medio=d.medio)
    db.commit()
    return cliente_dict(c, db, True)


@router.post("/consentimientos/{xid}/revocar")
def revocar_consentimiento(xid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _de_org(db, m.AfConsentimiento, xid, u)
    if x.revocado_en:
        raise HTTPException(409, "Ya estaba revocado.")
    x.revocado_en, x.revocado_medio = m.ahora(), "despacho"
    _aud(db, u, "af_consentimiento_revocado", "af_cliente", x.cliente_id, request=request, canal=x.canal)
    db.commit()
    return cliente_dict(db.get(m.AfCliente, x.cliente_id), db, True)


class AccesoIn(BaseModel):
    dias: int = 7
    requiere_codigo: bool = True


@router.post("/clientes/{cid}/acceso", status_code=201)
def crear_acceso(cid: int, d: AccesoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Enlace al portal del cliente (se muestra una sola vez). Con código, el cliente lo confirma por correo."""
    c = _cliente(db, cid, u)
    if d.dias not in (1, 3, 7, 14, 30):
        raise HTTPException(422, "Vigencia inválida.")
    if d.requiere_codigo and not c.email:
        raise HTTPException(422, "Para pedir código, el cliente necesita un correo registrado.")
    a, _, enlace = portal.nuevo_acceso(db, c, u, d.dias, d.requiere_codigo)
    _aud(db, u, "af_acceso_creado", "af_cliente", c.id, request=request, pista=a.token_pista, dias=d.dias)
    db.commit()
    return {"enlace": enlace, "expira_en": a.expira_en.isoformat(), "requiere_codigo": a.requiere_codigo}


@router.post("/accesos/{aid}/revocar")
def revocar_acceso(aid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _de_org(db, m.AfAcceso, aid, u)
    a.revocado_en = a.revocado_en or m.ahora()
    _aud(db, u, "af_acceso_revocado", "af_cliente", a.cliente_id, request=request, pista=a.token_pista)
    db.commit()
    return {"ok": True}


# ---------- casos ----------

class CasoIn(BaseModel):
    cliente_id: int
    tipo_problema: str
    tipo_otro: str | None = Field(None, max_length=200)
    titular_nombre: str | None = Field(None, max_length=200)
    datos: dict | None = None
    identificador_interno: str | None = Field(None, max_length=80)
    responsable_id: int | None = None
    restringido: bool = False
    siguiente_actividad: str | None = Field(None, max_length=300)
    siguiente_fecha: date | None = None
    resumen_interno: str | None = Field(None, max_length=5000)
    borrador: bool = True


class CasoCambio(BaseModel):
    tipo_problema: str | None = None
    tipo_otro: str | None = Field(None, max_length=200)
    titular_nombre: str | None = Field(None, max_length=200)
    datos: dict | None = None
    identificador_interno: str | None = Field(None, max_length=80)
    responsable_id: int | None = None
    restringido: bool | None = None
    estado: str | None = None
    siguiente_actividad: str | None = Field(None, max_length=300)
    siguiente_fecha: date | None = None
    siguiente_responsable_id: int | None = None
    resumen_interno: str | None = Field(None, max_length=5000)


def _requisitos_iniciales(db: Session, c: m.AfCaso):
    for i, nombre in enumerate(checklist_de(db, c.organizacion_id, c.tipo_problema)):
        db.add(m.AfRequisito(organizacion_id=c.organizacion_id, caso_id=c.id, nombre=nombre[:200], estado="no_solicitado", orden=i))


@router.post("/casos", status_code=201)
def crear_caso(d: CasoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    cl = _cliente(db, d.cliente_id, u)
    if d.tipo_problema not in tipos(db, u.organizacion_id):
        raise HTTPException(422, "Tipo de problema inválido.")
    c = m.AfCaso(organizacion_id=u.organizacion_id, cliente_id=cl.id, tipo_problema=d.tipo_problema, tipo_otro=_txt(d.tipo_otro, 200),
                 titular_nombre=_txt(d.titular_nombre, 200), datos=_datos(d.datos), identificador_interno=_txt(d.identificador_interno, 80),
                 responsable_id=_responsable(db, d.responsable_id, u), restringido=d.restringido,
                 siguiente_actividad=_txt(d.siguiente_actividad, 300), siguiente_fecha=d.siguiente_fecha,
                 siguiente_responsable_id=_responsable(db, d.responsable_id, u) if d.siguiente_actividad else None,
                 resumen_interno=_txt(d.resumen_interno, 5000), estado="borrador" if d.borrador else "abierto", creado_por_id=u.id)
    db.add(c)
    db.flush()
    _requisitos_iniciales(db, c)
    _aud(db, u, "af_caso_creado", "af_caso", c.id, c.id, request, tipo=c.tipo_problema, estado=c.estado)
    if c.estado == "abierto":
        _avisar(db, c, "solicitud_recibida", "caso_abierto", u)
    db.commit()
    return caso_dict(c, db, _nombres(db, u.organizacion_id), cl)


@router.get("/casos")
def listar_casos(filtro: str | None = None, tipo: str | None = None, afore: str | None = None, responsable_id: int | None = None,
                 estado: str | None = None, esperando_dias: int | None = None, docs_pendientes: bool = False, q: str | None = None,
                 u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Lista y reporte: filtros por tipo, AFORE, responsable, estado, tiempo esperando respuesta y
    documentos pendientes. Los montos son DATOS CAPTURADOS, no verificados por Nomira."""
    return _filas(db, u, filtro, tipo, afore, responsable_id, estado, esperando_dias, docs_pendientes, q)


def _filas(db, u, filtro=None, tipo=None, afore=None, responsable_id=None, estado=None, esperando_dias=None, docs_pendientes=False, q=None):
    query = _casos_visibles(db, u).order_by(m.AfCaso.actualizado_en.desc())
    if tipo:
        query = query.where(m.AfCaso.tipo_problema == tipo)
    if responsable_id:
        query = query.where(m.AfCaso.responsable_id == responsable_id)
    if estado:
        query = query.where(m.AfCaso.estado == estado)
    casos = db.scalars(query).all()
    ids = [c.id for c in casos]
    clientes = {c.id: c for c in db.scalars(select(m.AfCliente).where(m.AfCliente.organizacion_id == u.organizacion_id))}
    pend = dict(db.execute(select(m.AfRequisito.caso_id, func.count()).where(
        m.AfRequisito.caso_id.in_(ids or [0]), m.AfRequisito.estado.in_(("solicitado", "requiere_correccion", "no_solicitado"))).group_by(m.AfRequisito.caso_id)).all())
    esperando = _esperando(db, ids)
    hoy = date.today()
    nombres = _nombres(db, u.organizacion_id)
    filas = []
    for c in casos:
        datos = c.datos or {}
        af = (datos.get("afore") or {}).get("valor")
        if afore and (af or "").lower() != afore.lower():
            continue
        dias = (hoy - esperando[c.id]).days if c.id in esperando else None
        if esperando_dias is not None and (dias is None or dias < esperando_dias):
            continue
        if docs_pendientes and not pend.get(c.id):
            continue
        cl = clientes.get(c.cliente_id)
        if q and q.lower() not in (cl.nombre if cl else "").lower() and q.lower() not in (c.identificador_interno or "").lower():
            continue
        if filtro == "sin_siguiente" and (c.estado in ("borrador", "cerrado") or c.siguiente_actividad):
            continue
        if filtro == "esperando" and dias is None:
            continue
        if filtro == "docs_pendientes" and not pend.get(c.id):
            continue
        if filtro == "borradores" and c.estado != "borrador":
            continue
        if filtro == "abiertos" and c.estado in ("cerrado",):
            continue
        filas.append(caso_dict(c, db, nombres, cl, {"afore": af, "documentos_pendientes": pend.get(c.id, 0), "dias_esperando": dias,
                                                    "montos": {k: datos.get(k) for k in cat.CAMPOS_MONTO}}))
    return filas


@router.get("/casos/{cid}")
def ver_caso(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    nombres = _nombres(db, u.organizacion_id)
    cl = db.get(m.AfCliente, c.cliente_id)
    reqs = db.scalars(select(m.AfRequisito).where(m.AfRequisito.caso_id == c.id).order_by(m.AfRequisito.orden, m.AfRequisito.id)).all()
    docs = db.scalars(select(m.AfDocumento).where(m.AfDocumento.caso_id == c.id).order_by(m.AfDocumento.id.desc())).all()
    acts = db.scalars(select(m.AfActividad).where(m.AfActividad.caso_id == c.id).order_by(m.AfActividad.fecha.desc(), m.AfActividad.id.desc())).all()
    plazos = db.scalars(select(m.AfPlazo).where(m.AfPlazo.caso_id == c.id).order_by(m.AfPlazo.fecha)).all()
    mens = db.scalars(select(m.AfMensaje).where(m.AfMensaje.caso_id == c.id).order_by(m.AfMensaje.id.desc())).all()
    cfg = _cfg(db, u)
    ok_curp, motivo_curp = curp_oficial.disponible(cfg)
    db.commit()
    return {
        "caso": caso_dict(c, db, nombres, cl),
        "cliente": cliente_dict(cl, db, completo=False),
        "requisitos": [requisito_dict(r, nombres) for r in reqs],
        "documentos": [documento_dict(d, nombres) for d in docs],
        "actividades": [actividad_dict(a, nombres) for a in acts],
        "plazos": [plazo_dict(p, nombres) for p in plazos],
        "mensajes": [mensaje_dict(x, nombres) for x in mens],
        "curp_oficial": {"disponible": ok_curp, "motivo": motivo_curp},
        "puede_aprobar": _puede_aprobar(u, c),
    }


def requisito_dict(r, nombres):
    return {"id": r.id, "nombre": r.nombre, "estado": r.estado, "estado_texto": cat.ESTADOS_REQUISITO[r.estado], "visible_cliente": r.visible_cliente,
            "nota": r.nota, "nota_cliente": r.nota_cliente, "actualizado_por": nombres.get(r.actualizado_por_id),
            "actualizado_en": r.actualizado_en.isoformat()}


def documento_dict(d, nombres):
    return {"id": d.id, "nombre": d.nombre_original, "origen": d.origen, "requisito_id": d.requisito_id, "visible_cliente": d.visible_cliente,
            "estado": d.estado, "formato": d.formato, "tamano_bytes": d.tamano_bytes, "ev_documento_id": d.ev_documento_id,
            "recepcion_confirmada_en": d.recepcion_confirmada_en.isoformat() if d.recepcion_confirmada_en else None,
            "datos_capturados": d.datos_capturados or {}, "subido_por": nombres.get(d.subido_por_id) or ("Cliente" if d.origen == "cliente" else None),
            "creado_en": d.creado_en.isoformat()}


def actividad_dict(a, nombres):
    return {"id": a.id, "tipo": a.tipo, "tipo_texto": cat.TIPOS_ACTIVIDAD.get(a.tipo, a.tipo), "institucion": a.institucion, "canal": a.canal,
            "folio": a.folio, "fecha": a.fecha.isoformat(), "resumen": a.resumen, "documento_id": a.documento_id, "responde_a_id": a.responde_a_id,
            "responsable": nombres.get(a.responsable_id), "creado_por": nombres.get(a.creado_por_id), "creado_en": a.creado_en.isoformat(),
            "modificado_por": nombres.get(a.modificado_por_id), "modificado_en": a.modificado_en.isoformat() if a.modificado_en else None}


def plazo_dict(p, nombres):
    return {"id": p.id, "tipo": p.tipo, "tipo_texto": cat.TIPOS_PLAZO[p.tipo], "descripcion": p.descripcion, "fecha": p.fecha.isoformat(),
            "fuente": p.fuente, "regla": p.regla, "responsable": nombres.get(p.responsable_id),
            "confirmado_por": nombres.get(p.confirmado_por_id), "confirmado_en": p.confirmado_en.isoformat() if p.confirmado_en else None,
            "completado_en": p.completado_en.isoformat() if p.completado_en else None, "vencido": not p.completado_en and p.fecha < date.today()}


def mensaje_dict(x, nombres, clientes: dict | None = None):
    return {"id": x.id, "canal": x.canal, "direccion": x.direccion, "plantilla": x.plantilla, "texto": x.texto, "estado": x.estado,
            "estado_texto": msj.ESTADOS.get(x.estado, x.estado), "motivo": x.motivo, "error": x.error, "origen": x.origen,
            "caso_id": x.caso_id, "cliente_id": x.cliente_id, "cliente": (clientes or {}).get(x.cliente_id),
            "telefono": enmascarar_telefono(x.telefono), "creado_por": nombres.get(x.creado_por_id), "creado_en": x.creado_en.isoformat(),
            "aprobado_por": nombres.get(x.aprobado_por_id), "enviado_en": x.enviado_en.isoformat() if x.enviado_en else None,
            "entregado_en": x.entregado_en.isoformat() if x.entregado_en else None, "leido_en": x.leido_en.isoformat() if x.leido_en else None}


@router.patch("/casos/{cid}")
def cambiar_caso(cid: int, d: CasoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    datos = d.model_dump(exclude_unset=True)
    antes_estado = c.estado
    if "tipo_problema" in datos and datos["tipo_problema"] not in tipos(db, u.organizacion_id):
        raise HTTPException(422, "Tipo de problema inválido.")
    if "estado" in datos and datos["estado"] not in cat.ESTADOS_CASO:
        raise HTTPException(422, "Estado inválido.")
    if "restringido" in datos and u.rol != "administrador" and u.id != c.responsable_id:
        raise HTTPException(403, "Solo un administrador o el responsable puede cambiar la restricción del caso.")
    for k, v in datos.items():
        if k == "datos":
            v = _datos(v, c.datos)
        elif k in ("responsable_id", "siguiente_responsable_id"):
            v = _responsable(db, v, u)
        elif k in ("tipo_otro", "titular_nombre", "identificador_interno", "siguiente_actividad", "resumen_interno"):
            v = _txt(v, 5000 if k == "resumen_interno" else 300)
        setattr(c, k, v)
    if c.siguiente_actividad and not c.siguiente_responsable_id:
        c.siguiente_responsable_id = c.responsable_id
    _aud(db, u, "af_caso_modificado", "af_caso", c.id, c.id, request, campos=sorted(datos),
         **({"antes": antes_estado, "despues": c.estado} if "estado" in datos else {}))
    if antes_estado == "borrador" and c.estado == "abierto":
        _avisar(db, c, "solicitud_recibida", "caso_abierto", u)
    db.commit()
    return caso_dict(c, db, _nombres(db, u.organizacion_id))


@router.get("/casos/{cid}/revision")
def revision_caso(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    cl = db.get(m.AfCliente, c.cliente_id)
    return revision.revisar(db, c, cl, descifrar(cl.curp_cifrado), descifrar(cl.nss_cifrado))


@router.get("/casos/{cid}/historial")
def historial_caso(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    regs = db.scalars(select(m.Auditoria).where(m.Auditoria.organizacion_id == u.organizacion_id, m.Auditoria.accion.like("af_%"),
                                                m.Auditoria.detalle["caso_id"].as_integer() == c.id).order_by(m.Auditoria.id.desc()).limit(300)).all()
    nombres = _nombres(db, u.organizacion_id)
    return [{"fecha": r.fecha.isoformat(), "accion": r.accion, "usuario": nombres.get(r.usuario_id) or r.usuario_email or "Cliente (portal)",
             "detalle": {k: v for k, v in (r.detalle or {}).items() if k != "caso_id"}} for r in regs]


# ---------- checklist ----------

class RequisitoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    visible_cliente: bool = True


class RequisitoCambio(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=200)
    estado: str | None = None
    visible_cliente: bool | None = None
    nota: str | None = Field(None, max_length=500)
    nota_cliente: str | None = Field(None, max_length=300)


@router.post("/casos/{cid}/requisitos", status_code=201)
def agregar_requisito(cid: int, d: RequisitoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    orden = (db.scalar(select(func.max(m.AfRequisito.orden)).where(m.AfRequisito.caso_id == c.id)) or 0) + 1
    r = m.AfRequisito(organizacion_id=u.organizacion_id, caso_id=c.id, nombre=d.nombre.strip(), visible_cliente=d.visible_cliente,
                      orden=orden, estado="no_solicitado", actualizado_por_id=u.id)
    db.add(r)
    db.flush()
    _aud(db, u, "af_requisito_agregado", "af_requisito", r.id, c.id, request, nombre=r.nombre)
    db.commit()
    return requisito_dict(r, _nombres(db, u.organizacion_id))


@router.patch("/requisitos/{rid}")
def cambiar_requisito(rid: int, d: RequisitoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    r = _de_org(db, m.AfRequisito, rid, u)
    datos = d.model_dump(exclude_unset=True)
    if "estado" in datos and datos["estado"] not in cat.ESTADOS_REQUISITO:
        raise HTTPException(422, "Estado inválido.")
    antes = r.estado
    for k, v in datos.items():
        setattr(r, k, v.strip() if isinstance(v, str) else v)
    r.actualizado_por_id, r.actualizado_en = u.id, m.ahora()
    _aud(db, u, "af_requisito_modificado", "af_requisito", r.id, r.caso_id, request, nombre=r.nombre,
         **({"antes": antes, "despues": r.estado} if "estado" in datos else {}))
    if datos.get("estado") in ("solicitado", "requiere_correccion") and antes != datos["estado"] and r.visible_cliente:
        _avisar(db, db.get(m.AfCaso, r.caso_id), "falta_documentacion", "documento_solicitado", u)
    db.commit()
    return requisito_dict(r, _nombres(db, u.organizacion_id))


@router.delete("/requisitos/{rid}")
def quitar_requisito(rid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    r = _de_org(db, m.AfRequisito, rid, u)
    _aud(db, u, "af_requisito_quitado", "af_requisito", r.id, r.caso_id, request, nombre=r.nombre)
    db.delete(r)
    db.commit()
    return {"ok": True}


# ---------- documentos ----------

def guardar_archivo(db: Session, caso: m.AfCaso, archivo: UploadFile) -> tuple[str, str, bytes, str]:
    datos, formato = _leer_archivo(archivo)
    sha = hashlib.sha256(datos).hexdigest()
    carpeta = Path(ajustes().storage_dir) / str(caso.organizacion_id) / "afore" / str(caso.id)
    carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
    ruta = carpeta / f"{sha}.{EXT[formato]}"
    ruta.write_bytes(datos)
    os.chmod(ruta, 0o600)
    return str(ruta), formato, datos, sha


@router.post("/casos/{cid}/documentos", status_code=201)
def subir_documento(cid: int, request: Request, archivo: UploadFile = File(...), requisito_id: int | None = Form(None),
                    visible_cliente: bool = Form(False), u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    if requisito_id:
        r = _de_org(db, m.AfRequisito, requisito_id, u)
        if r.caso_id != c.id:
            raise HTTPException(422, "El requisito no es de este caso.")
    ruta, formato, datos, sha = guardar_archivo(db, c, archivo)
    d = m.AfDocumento(organizacion_id=u.organizacion_id, caso_id=c.id, requisito_id=requisito_id, nombre_original=os.path.basename(archivo.filename or "documento")[:300],
                      sha256=sha, ruta=ruta, formato=formato, tamano_bytes=len(datos), origen="despacho", visible_cliente=visible_cliente,
                      estado="recibido", recepcion_confirmada_en=m.ahora(), subido_por_id=u.id)
    db.add(d)
    db.flush()
    if requisito_id:
        r.estado, r.actualizado_por_id, r.actualizado_en = ("por_revisar" if r.estado in ("no_solicitado", "solicitado", "requiere_correccion") else r.estado), u.id, m.ahora()
    _aud(db, u, "af_documento_cargado", "af_documento", d.id, c.id, request, sha256=sha)
    db.commit()
    return documento_dict(d, _nombres(db, u.organizacion_id))


class DocumentoCambio(BaseModel):
    estado: str | None = None
    visible_cliente: bool | None = None
    confirmar_recepcion: bool | None = None
    requisito_id: int | None = None
    datos_capturados: dict | None = None


@router.patch("/documentos/{did}")
def cambiar_documento(did: int, d: DocumentoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    doc = _de_org(db, m.AfDocumento, did, u)
    datos = d.model_dump(exclude_unset=True)
    caso = db.get(m.AfCaso, doc.caso_id)
    if "estado" in datos:
        if datos["estado"] not in ("recibido", "aceptado", "requiere_correccion"):
            raise HTTPException(422, "Estado inválido.")
        doc.estado = datos["estado"]
        if doc.requisito_id:
            r = db.get(m.AfRequisito, doc.requisito_id)
            r.estado = {"aceptado": "aceptado", "requiere_correccion": "requiere_correccion"}.get(doc.estado, "por_revisar")
            r.actualizado_por_id, r.actualizado_en = u.id, m.ahora()
    if "visible_cliente" in datos:
        doc.visible_cliente = bool(datos["visible_cliente"])
    if "requisito_id" in datos:
        if datos["requisito_id"]:
            r = _de_org(db, m.AfRequisito, datos["requisito_id"], u)
            if r.caso_id != doc.caso_id:
                raise HTTPException(422, "El requisito no es de este caso.")
        doc.requisito_id = datos["requisito_id"]
    if "datos_capturados" in datos:
        limpio = {k: _txt(str(v), 120) for k, v in (datos["datos_capturados"] or {}).items()
                  if k in ("nombre", "curp", "nss", "fecha_nacimiento", "fecha_documento", "folio") and v}
        doc.datos_capturados = limpio or None
    if datos.get("confirmar_recepcion") and not doc.recepcion_confirmada_en:
        doc.recepcion_confirmada_en = m.ahora()
        if doc.origen == "cliente":
            _avisar(db, caso, "documento_recibido", "recepcion_confirmada", u)
    _aud(db, u, "af_documento_modificado", "af_documento", doc.id, doc.caso_id, request,
         campos=sorted(k for k in datos if k != "datos_capturados") + (["datos_capturados"] if "datos_capturados" in datos else []))
    db.commit()
    return documento_dict(doc, _nombres(db, u.organizacion_id))


@router.get("/documentos/{did}/archivo")
def descargar(did: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    doc = _de_org(db, m.AfDocumento, did, u)
    if doc.ev_documento_id and not doc.ruta:
        ev = db.get(m.EvDocumento, doc.ev_documento_id)
        if not ev or not puede_ver(u, db.get(m.EvAsunto, ev.asunto_id), ev):
            raise HTTPException(404, "No encontrado.")
        ruta, formato = ev.ruta, ev.formato
    else:
        ruta, formato = doc.ruta, doc.formato
    if not ruta or not Path(ruta).exists():
        raise HTTPException(410, "El archivo no está disponible en el servidor.")
    _aud(db, u, "af_documento_descargado", "af_documento", doc.id, doc.caso_id, request)
    db.commit()
    return Response(Path(ruta).read_bytes(), media_type=MIME[formato], headers={
        **PRIVADO, "Content-Disposition": f'attachment; filename="afore-{doc.id}.{EXT[formato]}"'})


@router.delete("/documentos/{did}")
def borrar_documento(did: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    doc = _de_org(db, m.AfDocumento, did, u)
    ruta = doc.ruta
    _aud(db, u, "af_documento_eliminado", "af_documento", doc.id, doc.caso_id, request, nombre=doc.nombre_original)
    db.delete(doc)
    db.commit()
    if ruta and not db.scalar(select(m.AfDocumento.id).where(m.AfDocumento.ruta == ruta)):
        try:
            os.unlink(ruta)
        except OSError:
            pass
    return {"ok": True}


# ---------- seguimiento: actividades y plazos ----------

class ActividadIn(BaseModel):
    tipo: str
    fecha: date
    institucion: str | None = Field(None, max_length=120)
    canal: str | None = Field(None, max_length=60)
    folio: str | None = Field(None, max_length=80)
    resumen: str | None = Field(None, max_length=5000)
    documento_id: int | None = None
    responde_a_id: int | None = None
    responsable_id: int | None = None


@router.post("/casos/{cid}/actividades", status_code=201)
def agregar_actividad(cid: int, d: ActividadIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    a = m.AfActividad(organizacion_id=u.organizacion_id, caso_id=c.id, creado_por_id=u.id)
    _aplicar_actividad(db, u, c, a, d.model_dump())
    db.add(a)
    db.flush()
    _aud(db, u, "af_actividad_registrada", "af_actividad", a.id, c.id, request, tipo=a.tipo, folio=a.folio)
    if a.tipo == "respuesta_recibida":
        _avisar(db, c, "respuesta_registrada", "respuesta_registrada", u)
    if a.tipo in ("solicitud_enviada", "queja") and c.estado == "abierto":
        c.estado = "esperando"
    db.commit()
    return actividad_dict(a, _nombres(db, u.organizacion_id))


def _aplicar_actividad(db, u, c, a, datos):
    if "tipo" in datos and datos["tipo"] not in cat.TIPOS_ACTIVIDAD:
        raise HTTPException(422, "Tipo de actividad inválido.")
    for k in ("documento_id", "responde_a_id"):
        if datos.get(k):
            x = _de_org(db, m.AfDocumento if k == "documento_id" else m.AfActividad, datos[k], u)
            if x.caso_id != c.id:
                raise HTTPException(422, "Debe pertenecer a este caso.")
    for k, v in datos.items():
        if k == "responsable_id":
            v = _responsable(db, v, u)
        elif isinstance(v, str):
            v = _txt(v, 5000)
        setattr(a, k, v)


@router.patch("/actividades/{aid}")
def cambiar_actividad(aid: int, d: ActividadIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _de_org(db, m.AfActividad, aid, u)
    c = db.get(m.AfCaso, a.caso_id)
    antes = {"folio": a.folio, "fecha": a.fecha.isoformat(), "tipo": a.tipo}
    _aplicar_actividad(db, u, c, a, d.model_dump(exclude_unset=True))
    a.modificado_por_id, a.modificado_en = u.id, m.ahora()
    _aud(db, u, "af_actividad_modificada", "af_actividad", a.id, c.id, request, antes=antes)
    db.commit()
    return actividad_dict(a, _nombres(db, u.organizacion_id))


class PlazoIn(BaseModel):
    tipo: str
    descripcion: str = Field(min_length=2, max_length=300)
    fecha: date
    fuente: str | None = Field(None, max_length=300)
    regla: str | None = Field(None, max_length=120)
    responsable_id: int | None = None


@router.post("/casos/{cid}/plazos", status_code=201)
def agregar_plazo(cid: int, d: PlazoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Un «plazo legal confirmado» exige que el abogado lo confirme y cite la fuente; Nomira no trae
    plazos legales de fábrica. Las reglas del despacho solo sugieren fechas «estimadas»."""
    c = _caso(db, cid, u)
    if d.tipo not in cat.TIPOS_PLAZO:
        raise HTTPException(422, "Tipo de fecha inválido.")
    if d.tipo == "legal_confirmado" and not (d.fuente or "").strip():
        raise HTTPException(422, "Un plazo legal confirmado necesita su fuente (ley, artículo u oficio).")
    p = m.AfPlazo(organizacion_id=u.organizacion_id, caso_id=c.id, tipo=d.tipo, descripcion=d.descripcion.strip(), fecha=d.fecha,
                  fuente=_txt(d.fuente, 300), regla=_txt(d.regla, 120), responsable_id=_responsable(db, d.responsable_id, u) or c.responsable_id,
                  creado_por_id=u.id)
    if d.tipo == "legal_confirmado":
        p.confirmado_por_id, p.confirmado_en = u.id, m.ahora()
    db.add(p)
    db.flush()
    _aud(db, u, "af_plazo_registrado", "af_plazo", p.id, c.id, request, tipo=p.tipo, fecha=p.fecha.isoformat())
    db.commit()
    return plazo_dict(p, _nombres(db, u.organizacion_id))


class PlazoCambio(BaseModel):
    accion: str  # confirmar_legal | completar | reabrir
    fuente: str | None = Field(None, max_length=300)


@router.post("/plazos/{pid}")
def accion_plazo(pid: int, d: PlazoCambio, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _de_org(db, m.AfPlazo, pid, u)
    if d.accion == "confirmar_legal":
        if not (d.fuente or p.fuente):
            raise HTTPException(422, "Indique la fuente del plazo legal.")
        p.tipo, p.fuente, p.confirmado_por_id, p.confirmado_en = "legal_confirmado", _txt(d.fuente, 300) or p.fuente, u.id, m.ahora()
    elif d.accion == "completar":
        p.completado_en = m.ahora()
    elif d.accion == "reabrir":
        p.completado_en = None
    else:
        raise HTTPException(422, "Acción inválida.")
    _aud(db, u, "af_plazo_" + d.accion, "af_plazo", p.id, p.caso_id, request)
    db.commit()
    return plazo_dict(p, _nombres(db, u.organizacion_id))


# ---------- AFORE y CURP ----------

class Nota(BaseModel):
    nota: str | None = Field(None, max_length=500)


@router.post("/casos/{cid}/localizacion")
def registrar_localizacion(cid: int, d: Nota, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Flujo guiado de «Localiza tu AFORE» en el sitio oficial (no se automatiza ni se raspa). Registra
    quién la inició y cuándo, y agrega al checklist el resultado que el cliente recibirá en SU correo."""
    c = _caso(db, cid, u)
    a = m.AfActividad(organizacion_id=u.organizacion_id, caso_id=c.id, tipo="localizacion_afore", fecha=date.today(), canal="AforeWeb",
                      institucion="CONSAR (AforeWeb)", resumen=_txt(d.nota, 500) or "Se indicó al cliente cómo consultar en AforeWeb; el resultado llega a su correo.",
                      creado_por_id=u.id, responsable_id=u.id)
    db.add(a)
    nombre = "Resultado de «Localiza tu AFORE» (correo recibido)"
    r = db.scalar(select(m.AfRequisito).where(m.AfRequisito.caso_id == c.id, m.AfRequisito.nombre == nombre))
    if not r:
        r = m.AfRequisito(organizacion_id=u.organizacion_id, caso_id=c.id, nombre=nombre, estado="solicitado", visible_cliente=True,
                          nota_cliente="Entre a aforeweb.com.mx, elija «Localiza tu AFORE», capture su NSS o CURP y su correo. "
                                       "Suba aquí el correo o la captura con el resultado.",
                          orden=-1, actualizado_por_id=u.id)
        db.add(r)
    db.flush()
    _aud(db, u, "af_localizacion_registrada", "af_actividad", a.id, c.id, request)
    db.commit()
    return {"aforeweb": AFOREWEB, "actividad": actividad_dict(a, _nombres(db, u.organizacion_id))}


class ConsultaCurp(BaseModel):
    finalidad: str = Field(min_length=5, max_length=300)
    consentimiento: bool


@router.post("/casos/{cid}/curp-oficial")
def curp_oficial_consulta(cid: int, d: ConsultaCurp, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Consulta oficial SOLO en el contexto de un caso, con finalidad y consentimiento. Sin
    configuración responde «Validación oficial no configurada» (y no simula nada)."""
    c = _caso(db, cid, u)
    if not d.consentimiento:
        raise HTTPException(422, "Registre el consentimiento de la persona antes de consultar.")
    cl = db.get(m.AfCliente, c.cliente_id)
    curp = descifrar(cl.curp_cifrado)
    if not curp:
        raise HTTPException(422, "El cliente no tiene CURP registrada.")
    cfg = _cfg(db, u)
    reg = m.AfConsultaCurp(organizacion_id=u.organizacion_id, caso_id=c.id, usuario_id=u.id, finalidad=d.finalidad.strip(),
                           consentimiento=True, resultado="no_configurado")
    db.add(reg)
    try:
        r = curp_oficial.consultar(cfg, curp)
        reg.resultado = "consultado"
        respuesta = {"oficial": True, "estatus": r["estatus"]}
    except curp_oficial.NoConfigurada as e:
        respuesta = {"oficial": False, "mensaje": str(e), "revision_local": revisar_curp(curp)}
    except Exception:
        reg.resultado = "error"
        respuesta = {"oficial": False, "mensaje": "El servicio oficial no respondió. Intente más tarde o continúe con revisión manual."}
    db.flush()
    _aud(db, u, "af_consulta_curp", "af_caso", c.id, c.id, request, resultado=reg.resultado)
    db.commit()
    return respuesta


# ---------- portal: lo que el despacho decide compartir ----------

class Publicar(BaseModel):
    portal_visible: bool
    estado_publico: str | None = Field(None, max_length=500)
    siguiente_paso_publico: str | None = Field(None, max_length=500)
    notificar: bool = False


@router.post("/casos/{cid}/publicar")
def publicar(cid: int, d: Publicar, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    c.portal_visible, c.estado_publico, c.siguiente_paso_publico = d.portal_visible, _txt(d.estado_publico, 500), _txt(d.siguiente_paso_publico, 500)
    c.publico_actualizado_en = m.ahora()
    _aud(db, u, "af_portal_actualizado", "af_caso", c.id, c.id, request, visible=d.portal_visible)
    generado = None
    if d.notificar and d.portal_visible:
        generado = _avisar(db, c, "actualizacion_portal", "portal_actualizado", u)
    db.commit()
    return {"caso": caso_dict(c, db, _nombres(db, u.organizacion_id)),
            "mensaje": mensaje_dict(generado, _nombres(db, u.organizacion_id)) if generado else None}


# ---------- mensajes ----------

def _puede_aprobar(u: m.Usuario, c: m.AfCaso | None) -> bool:
    return u.rol == "administrador" or (c is not None and u.id == c.responsable_id)


@router.get("/mensajes")
def listar_mensajes(bandeja: str = "pendientes", u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    estados = {"pendientes": ("esperando_aprobacion", "borrador", "fallido"), "por_aprobar": ("esperando_aprobacion",), "borradores": ("borrador",),
               "errores": ("fallido",), "por_asignar": ("por_asignar",), "enviados": ("enviado", "entregado", "leido"),
               "recibidos": ("recibido", "por_asignar"), "todos": None}.get(bandeja, ())
    q = select(m.AfMensaje).where(m.AfMensaje.organizacion_id == u.organizacion_id).order_by(m.AfMensaje.id.desc()).limit(300)
    if estados is not None:
        q = q.where(m.AfMensaje.estado.in_(estados))
    visibles = {c.id for c in db.scalars(_casos_visibles(db, u))}
    clientes = dict(db.execute(select(m.AfCliente.id, m.AfCliente.nombre).where(m.AfCliente.organizacion_id == u.organizacion_id)).all())
    nombres = _nombres(db, u.organizacion_id)
    cfg = _cfg(db, u)
    filas = [mensaje_dict(x, nombres, clientes) for x in db.scalars(q) if not x.caso_id or x.caso_id in visibles]
    db.commit()
    return {"mensajes": filas, "whatsapp_conectado": whatsapp.conectado(cfg), "faltan_plataforma": whatsapp.faltantes_plataforma()}


class MensajeIn(BaseModel):
    plantilla: str
    canal: str | None = None


@router.post("/casos/{cid}/mensajes", status_code=201)
def nuevo_mensaje(cid: int, d: MensajeIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    cl = db.get(m.AfCliente, c.cliente_id)
    if d.plantilla not in msj.PLANTILLAS:
        raise HTTPException(422, "Plantilla desconocida.")
    if d.canal and d.canal not in ("whatsapp", "correo"):
        raise HTTPException(422, "Canal inválido.")
    canal = d.canal or msj.canal_para(db, cl) or (cl.preferencia_contacto if cl.preferencia_contacto in ("whatsapp", "correo") else "correo")
    x = msj.generar(db, u.organizacion_id, cl, c, d.plantilla, "manual", u, canal=canal)
    _aud(db, u, "af_mensaje_creado", "af_mensaje", x.id, c.id, request, estado=x.estado, canal=x.canal)
    db.commit()
    return mensaje_dict(x, _nombres(db, u.organizacion_id))


def _mensaje(db, mid, u) -> m.AfMensaje:
    x = db.get(m.AfMensaje, mid)
    if not x or x.organizacion_id != u.organizacion_id or (x.caso_id and not _puede_ver_caso(u, db.get(m.AfCaso, x.caso_id))):
        raise HTTPException(404, "No encontrado.")
    return x


class TextoMensaje(BaseModel):
    texto: str = Field(min_length=5, max_length=1000)


@router.patch("/mensajes/{mid}")
def editar_mensaje(mid: int, d: TextoMensaje, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _mensaje(db, mid, u)
    if x.estado not in ("borrador", "esperando_aprobacion", "fallido"):
        raise HTTPException(409, "Solo se editan mensajes que no se han enviado.")
    msj.revisar_texto(d.texto.replace(msj.ENLACE, "{enlace}"))
    x.texto = d.texto.strip()
    _aud(db, u, "af_mensaje_editado", "af_mensaje", x.id, x.caso_id, request)
    db.commit()
    return mensaje_dict(x, _nombres(db, u.organizacion_id))


class Asignar(BaseModel):
    cliente_id: int
    caso_id: int | None = None


@router.post("/mensajes/{mid}/asignar")
def asignar_mensaje(mid: int, d: Asignar, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Una persona asocia un mensaje recibido a un cliente/caso. No cambia el estado del caso."""
    x = _mensaje(db, mid, u)
    if x.direccion != "entrante":
        raise HTTPException(409, "Solo se asignan mensajes recibidos.")
    cl = _cliente(db, d.cliente_id, u)
    if d.caso_id:
        c = _caso(db, d.caso_id, u)
        if c.cliente_id != cl.id:
            raise HTTPException(422, "El caso no es de ese cliente.")
    x.cliente_id, x.caso_id, x.estado, x.asignado_por_id = cl.id, d.caso_id, "recibido", u.id
    _aud(db, u, "af_mensaje_asignado", "af_mensaje", x.id, d.caso_id, request)
    db.commit()
    return mensaje_dict(x, _nombres(db, u.organizacion_id))


@router.post("/mensajes/{mid}/{accion}")
def accion_mensaje(mid: int, accion: str, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """aprobar (y enviar) · reintentar · cancelar · revisar (recalcula qué falta)."""
    x = _mensaje(db, mid, u)
    caso = db.get(m.AfCaso, x.caso_id) if x.caso_id else None
    if accion in ("aprobar", "reintentar"):
        if not _puede_aprobar(u, caso):
            raise HTTPException(403, "Solo un administrador o el abogado responsable del caso puede aprobar mensajes.")
        if x.direccion != "saliente" or x.estado not in ("esperando_aprobacion", "borrador", "fallido"):
            raise HTTPException(409, "Este mensaje no se puede enviar.")
        x.estado = "esperando_aprobacion" if x.estado == "fallido" else x.estado
        msj.enviar(db, x, u)
    elif accion == "cancelar":
        if x.estado not in ("borrador", "esperando_aprobacion", "fallido"):
            raise HTTPException(409, "Solo se cancelan mensajes que no se han enviado.")
        x.estado = "cancelado"
    elif accion == "revisar":
        msj.actualizar_estado(db, x)
    else:
        raise HTTPException(404, "Acción desconocida.")
    _aud(db, u, f"af_mensaje_{accion}", "af_mensaje", x.id, x.caso_id, request, estado=x.estado, canal=x.canal)
    db.commit()
    return mensaje_dict(x, _nombres(db, u.organizacion_id))


# ---------- configuración ----------

@router.get("/config")
def ver_config(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    cfg = _cfg(db, u)
    pls = msj.plantillas(db, u.organizacion_id)
    ok_curp, motivo_curp = curp_oficial.disponible(cfg)
    db.commit()
    return {"whatsapp": {"conectado": whatsapp.conectado(cfg), "phone_number_id": cfg.wa_phone_number_id, "waba_id": cfg.wa_waba_id,
                         "numero": cfg.wa_numero, "token": "guardado (cifrado)" if cfg.wa_token_cifrado else None,
                         "conectado_en": cfg.wa_conectado_en.isoformat() if cfg.wa_conectado_en else None,
                         "faltan_plataforma": whatsapp.faltantes_plataforma(),
                         "webhook": ajustes().url_publica.rstrip("/") + "/api/whatsapp/webhook"},
            "curp_oficial": {"disponible": ok_curp, "motivo": motivo_curp},
            "plantillas": [{"clave": p.clave, "nombre": p.nombre, "texto": p.texto, "wa_nombre": p.wa_nombre, "wa_idioma": p.wa_idioma,
                            "wa_aprobada": p.wa_aprobada, "envio": p.envio} for p in sorted(pls.values(), key=lambda p: list(msj.PLANTILLAS).index(p.clave))],
            "checklists": {k: checklist_de(db, u.organizacion_id, k) for k in tipos(db, u.organizacion_id)},
            "checklists_propios": sorted((cfg.checklists or {}).keys()), "tipos_extra": cfg.tipos_extra or [],
            "reglas_plazo": cfg.reglas_plazo or []}


class WhatsAppIn(BaseModel):
    phone_number_id: str = Field(min_length=5, max_length=40, pattern=r"^\d+$")
    waba_id: str | None = Field(None, max_length=40)
    numero: str | None = Field(None, max_length=30)
    token: str = Field(min_length=20, max_length=1000)


@router.put("/config/whatsapp")
def conectar_whatsapp(d: WhatsAppIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Registra el número empresarial de WhatsApp Business Platform del despacho. El token se guarda
    cifrado y no vuelve a mostrarse."""
    cfg = _cfg(db, u)
    cfg.wa_phone_number_id, cfg.wa_waba_id, cfg.wa_numero = d.phone_number_id, _txt(d.waba_id, 40), _txt(d.numero, 30)
    cfg.wa_token_cifrado, cfg.wa_conectado_por_id, cfg.wa_conectado_en = cifrar(d.token.strip()), u.id, m.ahora()
    auditar(db, u, "af_whatsapp_conectado", "af_config", cfg.id, {"phone_number_id": d.phone_number_id}, request)
    db.commit()
    return ver_config(u, db)


@router.delete("/config/whatsapp")
def desconectar_whatsapp(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cfg = _cfg(db, u)
    cfg.wa_phone_number_id = cfg.wa_waba_id = cfg.wa_numero = cfg.wa_token_cifrado = None
    auditar(db, u, "af_whatsapp_desconectado", "af_config", cfg.id, None, request)
    db.commit()
    return ver_config(u, db)


class PlantillaCambio(BaseModel):
    texto: str | None = Field(None, min_length=10, max_length=1000)
    wa_nombre: str | None = Field(None, max_length=120)
    wa_idioma: str | None = Field(None, max_length=10)
    wa_aprobada: bool | None = None
    envio: str | None = None


@router.patch("/plantillas/{clave}")
def cambiar_plantilla(clave: str, d: PlantillaCambio, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    p = msj.plantillas(db, u.organizacion_id).get(clave)
    if not p:
        raise HTTPException(404, "Plantilla desconocida.")
    datos = d.model_dump(exclude_unset=True)
    if "texto" in datos and datos["texto"]:
        msj.revisar_texto(datos["texto"])
    if "envio" in datos and datos["envio"] not in ("aprobacion", "automatico"):
        raise HTTPException(422, "Envío inválido.")
    for k, v in datos.items():
        setattr(p, k, v.strip() if isinstance(v, str) else v)
    p.actualizado_por_id = u.id
    auditar(db, u, "af_plantilla_modificada", "af_plantilla", p.id, {"clave": clave, "campos": sorted(datos)}, request)
    db.commit()
    return {"ok": True}


class ConfigCambio(BaseModel):
    checklists: dict[str, list[str]] | None = None
    tipos_extra: list[str] | None = Field(None, max_length=30)
    reglas_plazo: list[dict] | None = Field(None, max_length=50)


@router.patch("/config")
def cambiar_config(d: ConfigCambio, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cfg = _cfg(db, u)
    datos = d.model_dump(exclude_unset=True)
    if "tipos_extra" in datos:
        cfg.tipos_extra = [t.strip()[:120] for t in datos["tipos_extra"] if t and t.strip()] or None
    if "checklists" in datos:
        validos = tipos(db, u.organizacion_id)
        propios = dict(cfg.checklists or {})
        for k, lista in datos["checklists"].items():
            if k not in validos:
                raise HTTPException(422, f"Tipo desconocido: {k}")
            limpio = [x.strip()[:200] for x in lista if x and x.strip()][:60]
            if limpio:
                propios[k] = limpio
            else:
                propios.pop(k, None)  # vacío = volver a los valores de fábrica
        cfg.checklists = propios or None
    if "reglas_plazo" in datos:
        reglas = []
        for r in datos["reglas_plazo"]:
            try:
                dias = int(r.get("dias"))
            except (TypeError, ValueError):
                raise HTTPException(422, "Cada regla necesita un número de días.")
            if not (r.get("nombre") or "").strip():
                raise HTTPException(422, "Cada regla necesita un nombre.")
            reglas.append({"nombre": r["nombre"].strip()[:120], "dias": max(1, min(dias, 3650)), "fuente": _txt(r.get("fuente"), 300),
                           "revisado_en": _txt(r.get("revisado_en"), 20)})
        cfg.reglas_plazo = reglas or None
    auditar(db, u, "af_config_modificada", "af_config", cfg.id, {"campos": sorted(datos)}, request)
    db.commit()
    return ver_config(u, db)


# ---------- Nomira Evidencia (opcional) ----------

def _exigir_evidencia(db, u):
    if "evidencia" not in modulos.activos(db, u.organizacion_id):
        raise HTTPException(409, "Nomira Evidencia no está activo para su organización.")


@router.get("/casos/{cid}/evidencia")
def evidencia_vinculada(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    activa = "evidencia" in modulos.activos(db, u.organizacion_id)
    vinculos = db.scalars(select(m.AfVinculoEvidencia).where(m.AfVinculoEvidencia.caso_id == c.id)).all() if activa else []
    salida = []
    for v in vinculos:
        d = db.get(m.EvDocumento, v.ev_documento_id) if v.ev_documento_id else None
        h = db.get(m.EvHecho, v.ev_hecho_id) if v.ev_hecho_id else None
        doc = d or (db.get(m.EvDocumento, h.documento_id) if h and h.documento_id else None)
        if doc and not puede_ver(u, db.get(m.EvAsunto, doc.asunto_id), doc):
            continue  # se respeta la visibilidad de Evidencia
        salida.append({"id": v.id, "documento": doc.nombre_original if doc else None, "documento_id": doc.id if doc else None,
                       "asunto_id": doc.asunto_id if doc else (h.asunto_id if h else None),
                       "hecho": h.descripcion if h else None, "hecho_fecha": h.fecha.isoformat() if h and h.fecha else None, "nota": v.nota})
    opciones = []
    if activa:
        for a in db.scalars(select(m.EvAsunto).where(m.EvAsunto.organizacion_id == u.organizacion_id).order_by(m.EvAsunto.nombre)):
            docs = [d for d in db.scalars(select(m.EvDocumento).where(m.EvDocumento.asunto_id == a.id, m.EvDocumento.estado != "recibido"))
                    if puede_ver(u, a, d)]
            visibles = {d.id for d in docs}
            hechos = db.scalars(select(m.EvHecho).where(m.EvHecho.asunto_id == a.id, m.EvHecho.estado.in_(("confirmado", "editado")))).all()
            opciones.append({"asunto_id": a.id, "asunto": a.nombre, "documentos": [{"id": d.id, "nombre": d.nombre_original} for d in docs],
                             "hechos": [{"id": h.id, "descripcion": h.descripcion, "fecha": h.fecha.isoformat() if h.fecha else None}
                                        for h in hechos if h.documento_id in visibles]})
    return {"activa": activa, "vinculos": salida, "opciones": opciones}


class VinculoEv(BaseModel):
    ev_documento_id: int | None = None
    ev_hecho_id: int | None = None
    nota: str | None = Field(None, max_length=300)


@router.post("/casos/{cid}/evidencia", status_code=201)
def vincular_evidencia(cid: int, d: VinculoEv, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _caso(db, cid, u)
    _exigir_evidencia(db, u)
    if bool(d.ev_documento_id) == bool(d.ev_hecho_id):
        raise HTTPException(422, "Elija un documento o un hecho.")
    if d.ev_hecho_id:
        h = db.get(m.EvHecho, d.ev_hecho_id)
        if not h or h.organizacion_id != u.organizacion_id or h.estado not in ("confirmado", "editado"):
            raise HTTPException(404, "Hecho no encontrado o sin revisar.")
        doc = db.get(m.EvDocumento, h.documento_id) if h.documento_id else None
    else:
        doc = db.get(m.EvDocumento, d.ev_documento_id)
        if not doc or doc.organizacion_id != u.organizacion_id:
            raise HTTPException(404, "Documento no encontrado.")
    if doc and not puede_ver(u, db.get(m.EvAsunto, doc.asunto_id), doc):
        raise HTTPException(404, "Documento no encontrado.")
    v = m.AfVinculoEvidencia(organizacion_id=u.organizacion_id, caso_id=c.id, ev_documento_id=d.ev_documento_id, ev_hecho_id=d.ev_hecho_id,
                             nota=_txt(d.nota, 300), creado_por_id=u.id)
    db.add(v)
    db.flush()
    _aud(db, u, "af_evidencia_vinculada", "af_caso", c.id, c.id, request, ev_documento_id=d.ev_documento_id, ev_hecho_id=d.ev_hecho_id)
    db.commit()
    return {"ok": True, "id": v.id}


@router.delete("/evidencia/{vid}")
def desvincular_evidencia(vid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    v = _de_org(db, m.AfVinculoEvidencia, vid, u)
    _aud(db, u, "af_evidencia_desvinculada", "af_caso", v.caso_id, v.caso_id, request)
    db.delete(v)
    db.commit()
    return {"ok": True}


# ---------- reporte ----------

@router.get("/reportes/excel")
def reporte_excel(tipo: str | None = None, afore: str | None = None, responsable_id: int | None = None, estado: str | None = None,
                  esperando_dias: int | None = None, docs_pendientes: bool = False, request: Request = None,
                  u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    filas = _filas(db, u, None, tipo, afore, responsable_id, estado, esperando_dias, docs_pendientes)
    wb = Workbook()
    ws = wb.active
    ws.title = "Casos AFORE"
    ws.append(["Reporte interno de gestión. Los montos son DATOS CAPTURADOS (informados), no verificados por Nomira; "
               "no son proyecciones ni promesas de recuperación."])
    ws["A1"].font = Font(bold=True, color="B45309")
    ws.append(["Caso", "Cliente", "Tipo de problema", "AFORE", "Estado", "Responsable", "Días esperando respuesta", "Documentos pendientes",
               "Monto que el cliente dice reclamar (capturado)", "Monto reportado por la AFORE (capturado)", "Monto entregado (capturado)",
               "Siguiente actividad", "Fecha"])
    for c in ws[2]:
        c.font = Font(bold=True)
    for f in filas:
        mo = f["montos"]
        val = lambda k: (mo.get(k) or {}).get("valor") or cat.ESTADOS_DATO.get((mo.get(k) or {}).get("estado"), "")  # noqa: E731
        ws.append([f["id"], f["cliente"], f["tipo_texto"], f["afore"], f["estado_texto"], f["responsable"], f["dias_esperando"],
                   f["documentos_pendientes"], val("monto_cliente"), val("monto_afore"), val("monto_entregado"), f["siguiente_actividad"],
                   f["siguiente_fecha"]])
    auditar(db, u, "af_reporte_exportado", None, None, {"filas": len(filas)}, request)
    db.commit()
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={**PRIVADO, "Content-Disposition": 'attachment; filename="casos-afore.xlsx"', "Access-Control-Expose-Headers": "Content-Disposition"})
