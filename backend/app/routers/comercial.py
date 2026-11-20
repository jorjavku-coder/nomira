"""Módulo Comercial del panel de la plataforma: paquetes, precios, cotizaciones y configuración.

Exclusivo del SUPERADMINISTRADOR de Nomira (dependencia `superadmin` en cada ruta). Los usuarios de
los despachos no tienen ninguna ruta aquí: su sesión no sirve en /api/plataforma.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..services import correo, envios, modulos, suscripciones as sus
from ..services.comercial import base as cm
from ..services.comercial import correo as cm_correo
from ..services.comercial import pdf as cm_pdf
from .plataforma import _registrar, superadmin

router = APIRouter(prefix="/api/plataforma/comercial", tags=["Plataforma — Comercial"], dependencies=[Depends(superadmin)])
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CONFIRMACION = "Enviar cotización"


def _txt(v: Decimal | None) -> str | None:
    return cm.txt(v)


def _iso(d) -> str | None:
    return d.isoformat() if d else None


def _admins(db: Session) -> dict[int, str]:
    return dict(db.execute(select(m.AdminPlataforma.id, m.AdminPlataforma.nombre)).all())


# ------------------------------------------------------------------ catálogo y configuración

def paquete_dict(p: m.CmPaquete) -> dict:
    return {"id": p.id, "clave": p.clave, "nombre": p.nombre, "descripcion": p.descripcion, "precio_mensual": _txt(p.precio_mensual),
            "modulos_incluidos": p.modulos_incluidos, "usuarios": p.usuarios, "almacenamiento_gb": p.almacenamiento_gb, "ciclo": p.ciclo,
            "iva_pct": _txt(p.iva_pct), "estado": p.estado, "orden": p.orden}


def precio_dict(p: m.CmPrecio) -> dict:
    return {"id": p.id, "clave": p.clave, "nombre": p.nombre, "precio_mensual": _txt(p.precio_mensual), "unidad_gb": p.unidad_gb, "activo": p.activo}


CAMPOS_CONFIG = ("nombre_comercial", "razon_social", "rfc", "domicilio", "correo_ventas", "telefono", "sitio_web", "condiciones",
                 "instrucciones_contratar", "notas_pie", "asunto_correo", "mensaje_presentacion", "spei_banco", "spei_titular",
                 "spei_clabe", "spei_instrucciones", "otro_nombre", "otro_instrucciones")


def config_dict(c: m.CmConfig) -> dict:
    d = {k: getattr(c, k) for k in CAMPOS_CONFIG}
    d.update({"iva_pct": _txt(c.iva_pct), "vigencia_dias": c.vigencia_dias, "descuento_maximo_pct": _txt(c.descuento_maximo_pct),
              "periodicidades": cm.periodicidades_habilitadas(c), "mb_promedio_por_asunto": c.mb_promedio_por_asunto,
              "aceptacion_en_linea": c.aceptacion_en_linea, "precios_publicos": c.precios_publicos, "pago_tarjeta": c.pago_tarjeta,
              "spei_habilitado": c.spei_habilitado, "otro_habilitado": c.otro_habilitado,
              "actualizado_en": _iso(c.actualizado_en)})
    return d


def _integraciones(c: m.CmConfig) -> dict:
    st = cm.stripe_estado()
    spei_completo = bool(c.spei_banco and c.spei_titular and c.spei_clabe and len(c.spei_clabe) == 18)
    return {"correo": {"configurado": correo.configurado(), "prueba": correo.modo_prueba() if correo.configurado() else False,
                       "proveedor": correo.descripcion()["proveedor"]},
            "stripe": st,
            "formas_pago": cm.formas_pago(c),
            "faltantes_pago": [x for x in (
                None if (not c.pago_tarjeta or st["conectado"]) else f"Tarjeta: {st['motivo']}",
                None if (not c.spei_habilitado or spei_completo) else "Transferencia SPEI: faltan banco, titular o CLABE de 18 dígitos.",
                None if (not c.otro_habilitado or (c.otro_nombre and c.otro_instrucciones)) else "Otra forma de pago: faltan nombre o instrucciones.",
            ) if x]}


@router.get("/catalogo")
def catalogo(db: Session = Depends(get_db)):
    cm.asegurar_catalogo(db)
    c = cm.config(db)
    db.commit()
    return {"paquetes": [paquete_dict(p) for p in db.scalars(select(m.CmPaquete).order_by(m.CmPaquete.orden, m.CmPaquete.id))],
            "precios": [precio_dict(p) for p in db.scalars(select(m.CmPrecio).order_by(m.CmPrecio.id))],
            "modulos": [{"clave": k, "nombre": v["nombre"]} for k, v in modulos.MODULOS.items()],
            "periodicidades": [{"clave": k, "nombre": cm.PERIODICIDADES[k][0], "meses": cm.PERIODICIDADES[k][1]} for k in cm.periodicidades_habilitadas(c)],
            "servicios": [{"clave": k, "nombre": v} for k, v in cm.SERVICIOS.items()], "estados": cm.ESTADOS,
            "config": config_dict(c), "integraciones": _integraciones(c), "confirmacion": CONFIRMACION,
            "cursos_academia": [{"id": x.id, "titulo": x.titulo, "precio": _txt(x.precio)} for x in db.scalars(
                select(m.AcCurso).where(m.AcCurso.organizacion_id.is_(None), m.AcCurso.acceso == "pago", m.AcCurso.estado == "publicado",
                                        m.AcCurso.precio.is_not(None)).order_by(m.AcCurso.titulo))]}


class ConfigIn(BaseModel):
    nombre_comercial: str = Field(min_length=2, max_length=120)
    razon_social: str | None = Field(None, max_length=200)
    rfc: str | None = Field(None, max_length=13)
    domicilio: str | None = Field(None, max_length=400)
    correo_ventas: str | None = Field(None, max_length=254)
    telefono: str | None = Field(None, max_length=40)
    sitio_web: str | None = Field(None, max_length=200)
    iva_pct: Decimal = Field(Decimal("16"), ge=0, le=30)
    vigencia_dias: int = Field(15, ge=1, le=120)
    descuento_maximo_pct: Decimal = Field(Decimal("20"), ge=0, le=100)
    periodicidades: list[str] = ["mensual", "anual"]
    condiciones: str | None = Field(None, max_length=6000)
    instrucciones_contratar: str | None = Field(None, max_length=3000)
    notas_pie: str | None = Field(None, max_length=150)
    mb_promedio_por_asunto: int | None = Field(None, ge=1, le=100_000)
    asunto_correo: str | None = Field(None, max_length=200)
    mensaje_presentacion: str | None = Field(None, max_length=4000)
    aceptacion_en_linea: bool = True
    precios_publicos: str = "ocultos"
    pago_tarjeta: bool = False
    spei_habilitado: bool = False
    spei_banco: str | None = Field(None, max_length=80)
    spei_titular: str | None = Field(None, max_length=200)
    spei_clabe: str | None = Field(None, max_length=18)
    spei_instrucciones: str | None = Field(None, max_length=2000)
    otro_habilitado: bool = False
    otro_nombre: str | None = Field(None, max_length=80)
    otro_instrucciones: str | None = Field(None, max_length=2000)


@router.put("/config")
def guardar_config(d: ConfigIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = cm.config(db)
    datos = d.model_dump()
    for k in CAMPOS_CONFIG:
        v = datos[k]
        datos[k] = v.strip() or None if isinstance(v, str) else v
    if datos["correo_ventas"] and not _RE_EMAIL.match(datos["correo_ventas"]):
        raise HTTPException(422, "Correo de ventas inválido.")
    if datos["rfc"] and not re.fullmatch(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}", datos["rfc"].upper()):
        raise HTTPException(422, "RFC inválido.")
    if datos["spei_clabe"] and not re.fullmatch(r"\d{18}", datos["spei_clabe"]):
        raise HTTPException(422, "La CLABE debe tener 18 dígitos.")
    if datos["precios_publicos"] not in ("ocultos", "desde"):
        raise HTTPException(422, "Opción de precios públicos inválida.")
    pers = [p for p in dict.fromkeys(datos["periodicidades"]) if p in cm.PERIODICIDADES]
    if not pers:
        raise HTTPException(422, "Habilite al menos una periodicidad.")
    antes = {k: getattr(c, k) for k in ("spei_clabe", "spei_banco", "spei_titular", "iva_pct", "descuento_maximo_pct", "precios_publicos")}
    for k, v in datos.items():
        if k == "periodicidades":
            v = pers
        elif k == "rfc" and v:
            v = v.upper()
        setattr(c, k, v)
    c.actualizado_en = cm.ahora()
    cambiados = sorted(k for k, v in antes.items() if v != getattr(c, k))
    _registrar(db, a, "comercial_config_actualizada", request, entidad="cm_config", entidad_id=c.id,
               detalle={"campos_sensibles_cambiados": cambiados})  # nunca se registra la CLABE
    db.commit()
    return {"config": config_dict(c), "integraciones": _integraciones(c)}


# ------------------------------------------------------------------ paquetes y precios

class PaqueteIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(None, max_length=500)
    precio_mensual: Decimal = Field(ge=0, le=1_000_000)
    modulos_incluidos: int = Field(ge=1, le=len(modulos.MODULOS))
    usuarios: int = Field(ge=1, le=10_000)
    almacenamiento_gb: int = Field(ge=1, le=100_000)
    ciclo: str = "mensual"
    iva_pct: Decimal | None = Field(None, ge=0, le=30)
    orden: int = 0


def _historial(db: Session, entidad: str, eid: int, a: m.AdminPlataforma, antes: dict, despues: dict) -> list[str]:
    cambios = []
    for k, v in despues.items():
        va = antes.get(k)
        sa = _txt(va) if isinstance(va, Decimal) else (None if va is None else str(va))
        sb = _txt(v) if isinstance(v, Decimal) else (None if v is None else str(v))
        if sa != sb:
            db.add(m.CmCambioPrecio(entidad=entidad, entidad_id=eid, campo=k, antes=sa, despues=sb, admin_id=a.id))
            cambios.append(k)
    return cambios


@router.post("/paquetes", status_code=201)
def crear_paquete(d: PaqueteIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    if d.ciclo not in cm.PERIODICIDADES:
        raise HTTPException(422, "Ciclo inválido.")
    clave = re.sub(r"[^a-z0-9]+", "-", d.nombre.lower()).strip("-")[:30] or "paquete"
    base, n = clave, 1
    while db.scalar(select(m.CmPaquete.id).where(m.CmPaquete.clave == clave)):
        n += 1
        clave = f"{base}-{n}"
    p = m.CmPaquete(clave=clave, **{**d.model_dump(), "nombre": d.nombre.strip()}, estado="inactivo")
    db.add(p)
    db.flush()
    _historial(db, "paquete", p.id, a, {}, {"precio_mensual": p.precio_mensual})
    _registrar(db, a, "comercial_paquete_creado", request, entidad="cm_paquete", entidad_id=p.id, detalle={"nombre": p.nombre})
    db.commit()
    return paquete_dict(p)


@router.patch("/paquetes/{pid}")
def editar_paquete(pid: int, d: PaqueteIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    p = db.get(m.CmPaquete, pid)
    if not p:
        raise HTTPException(404, "No encontrado.")
    if p.estado == "archivado":
        raise HTTPException(409, "El paquete está archivado; reactívelo para editarlo.")
    if d.ciclo not in cm.PERIODICIDADES:
        raise HTTPException(422, "Ciclo inválido.")
    datos = {**d.model_dump(), "nombre": d.nombre.strip()}
    antes = {k: getattr(p, k) for k in datos}
    for k, v in datos.items():
        setattr(p, k, v)
    cambios = _historial(db, "paquete", p.id, a, antes, datos)
    if cambios:
        _registrar(db, a, "comercial_paquete_editado", request, entidad="cm_paquete", entidad_id=p.id, detalle={"campos": cambios})
    db.commit()
    return paquete_dict(p)


class EstadoPaqueteIn(BaseModel):
    estado: str


@router.post("/paquetes/{pid}/estado")
def estado_paquete(pid: int, d: EstadoPaqueteIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    p = db.get(m.CmPaquete, pid)
    if not p:
        raise HTTPException(404, "No encontrado.")
    if d.estado not in ("activo", "inactivo", "archivado"):
        raise HTTPException(422, "Estado inválido.")
    if d.estado != p.estado:
        _historial(db, "paquete", p.id, a, {"estado": p.estado}, {"estado": d.estado})
        p.estado = d.estado
        _registrar(db, a, "comercial_paquete_estado", request, entidad="cm_paquete", entidad_id=p.id, detalle={"estado": d.estado})
        db.commit()
    return paquete_dict(p)


class PrecioIn(BaseModel):
    precio_mensual: Decimal = Field(ge=0, le=1_000_000)
    activo: bool = True
    unidad_gb: int | None = Field(None, ge=1, le=10_000)


@router.patch("/precios/{pid}")
def editar_precio(pid: int, d: PrecioIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    p = db.get(m.CmPrecio, pid)
    if not p:
        raise HTTPException(404, "No encontrado.")
    datos = d.model_dump()
    if p.clave != "almacenamiento":
        datos.pop("unidad_gb")
    elif not datos.get("unidad_gb"):
        raise HTTPException(422, "Indique los GB de cada bloque.")
    antes = {k: getattr(p, k) for k in datos}
    for k, v in datos.items():
        setattr(p, k, v)
    cambios = _historial(db, "precio", p.id, a, antes, datos)
    if cambios:
        _registrar(db, a, "comercial_precio_editado", request, entidad="cm_precio", entidad_id=p.id, detalle={"clave": p.clave, "campos": cambios})
    db.commit()
    return precio_dict(p)


@router.get("/historial-precios")
def historial_precios(db: Session = Depends(get_db)):
    nombres = _admins(db)
    paq = dict(db.execute(select(m.CmPaquete.id, m.CmPaquete.nombre)).all())
    pre = dict(db.execute(select(m.CmPrecio.id, m.CmPrecio.nombre)).all())
    filas = db.scalars(select(m.CmCambioPrecio).order_by(m.CmCambioPrecio.creado_en.desc(), m.CmCambioPrecio.id.desc()).limit(300))
    return [{"id": x.id, "entidad": x.entidad, "nombre": (paq if x.entidad == "paquete" else pre).get(x.entidad_id, "—"), "campo": x.campo,
             "antes": x.antes, "despues": x.despues, "por": nombres.get(x.admin_id), "fecha": x.creado_en.isoformat()} for x in filas]


# ------------------------------------------------------------------ resumen

@router.get("/resumen")
def resumen(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    cm.actualizar_vencidas(db)
    db.commit()
    hoy = sus.hoy()
    desde = desde or hoy.replace(day=1)
    hasta = hasta or hoy
    ini = datetime.combine(desde, datetime.min.time(), tzinfo=timezone.utc)
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    conteos = dict(db.execute(select(m.CmCotizacion.estado, func.count(m.CmCotizacion.id)).group_by(m.CmCotizacion.estado)).all())
    proximas = db.scalar(select(func.count(m.CmCotizacion.id)).where(m.CmCotizacion.estado.in_(cm.ABIERTAS_CLIENTE),
                                                                     m.CmCotizacion.vence_en <= cm.ahora() + timedelta(days=3))) or 0
    cotizado = db.scalar(select(func.coalesce(func.sum(m.CmVersion.total), 0)).where(m.CmVersion.enviada_en >= ini, m.CmVersion.enviada_en < fin))
    n_cotizado = db.scalar(select(func.count(m.CmVersion.id)).where(m.CmVersion.enviada_en >= ini, m.CmVersion.enviada_en < fin)) or 0
    aceptadas = db.scalars(select(m.CmCotizacion).where(m.CmCotizacion.aceptada_en >= ini, m.CmCotizacion.aceptada_en < fin)).all()
    aceptado = sum((cm.version_enviada(db, c).total for c in aceptadas if cm.version_enviada(db, c)), Decimal("0"))
    cobrado = db.scalar(select(func.coalesce(func.sum(m.CmPago.monto), 0)).where(m.CmPago.estado == "confirmado", m.CmPago.confirmado_en >= ini,
                                                                                m.CmPago.confirmado_en < fin))
    n_cobrado = db.scalar(select(func.count(m.CmPago.id)).where(m.CmPago.estado == "confirmado", m.CmPago.confirmado_en >= ini,
                                                                m.CmPago.confirmado_en < fin)) or 0
    ajustes_pend = db.scalar(select(func.count(m.CmEvento.id)).join(m.CmCotizacion, m.CmCotizacion.id == m.CmEvento.cotizacion_id).where(
        m.CmEvento.tipo == "ajuste_solicitado", m.CmCotizacion.estado.in_(cm.ABIERTAS_CLIENTE))) or 0
    orgs = dict(db.execute(select(m.Organizacion.id, m.Organizacion.nombre)).all())
    asig = db.scalars(select(m.CmAsignacion).order_by(m.CmAsignacion.creado_en.desc()).limit(20)).all()
    return {"periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
            "estados": [{"clave": k, "nombre": v, "n": conteos.get(k, 0)} for k, v in cm.ESTADOS.items()],
            "total_cotizaciones": sum(conteos.values()), "proximas_a_vencer": proximas, "ajustes_pendientes": ajustes_pend,
            "importes": {"cotizado": {"monto": _txt(Decimal(cotizado)), "n": n_cotizado},
                         "aceptado": {"monto": _txt(aceptado), "n": len(aceptadas)},
                         "cobrado": {"monto": _txt(Decimal(cobrado)), "n": n_cobrado}},
            "asignaciones": [asignacion_dict(x, orgs) for x in asig]}


def asignacion_dict(x: m.CmAsignacion, orgs: dict) -> dict:
    return {"id": x.id, "organizacion_id": x.organizacion_id, "organizacion": orgs.get(x.organizacion_id), "cotizacion_id": x.cotizacion_id,
            "paquete": x.paquete, "modulos": x.modulos, "usuarios": x.usuarios, "almacenamiento_gb": x.almacenamiento_gb,
            "periodicidad": x.periodicidad, "monto": _txt(x.monto), "inicio": x.inicio.isoformat(), "renovacion": x.renovacion.isoformat(),
            "estado": x.estado, "origen": x.origen, "motivo": x.motivo}


class AsignacionCambio(BaseModel):
    estado: str


@router.patch("/asignaciones/{aid}")
def cambiar_asignacion(aid: int, d: AsignacionCambio, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    """Cambia solo el ESTADO comercial. Nunca borra ni oculta expedientes ni documentos."""
    x = db.get(m.CmAsignacion, aid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    if d.estado not in ("activa", "impago", "vencida", "cancelada"):
        raise HTTPException(422, "Estado inválido.")
    antes, x.estado = x.estado, d.estado
    _registrar(db, a, "comercial_asignacion_estado", request, organizacion_id=x.organizacion_id, entidad="cm_asignacion", entidad_id=x.id,
               detalle={"antes": antes, "despues": d.estado})
    db.commit()
    return asignacion_dict(x, dict(db.execute(select(m.Organizacion.id, m.Organizacion.nombre)).all()))


# ------------------------------------------------------------------ cotizaciones

class CalculoIn(BaseModel):
    entrada: dict


@router.post("/calcular")
def calcular(d: CalculoIn, db: Session = Depends(get_db)):
    """Vista previa del importe. El servidor calcula todo; los importes del navegador no se usan."""
    cm.asegurar_catalogo(db)
    r = cm.calcular(db, cm.limpiar_entrada(d.entrada))
    db.commit()
    return r


class CotizacionIn(BaseModel):
    contacto: str = Field(min_length=2, max_length=200)
    despacho: str = Field(min_length=2, max_length=200)
    email: str = Field(max_length=254)
    telefono: str | None = Field(None, max_length=40)
    pais: str = "MX"
    moneda: str = "MXN"
    necesidad: str | None = Field(None, max_length=1000)
    notas_internas: str | None = Field(None, max_length=5000)
    vence_en: datetime | None = None
    preparada_por: str | None = Field(None, max_length=200)
    entrada: dict


def _validar_cliente(d: CotizacionIn) -> str:
    email = d.email.strip().lower()
    if not _RE_EMAIL.match(email):
        raise HTTPException(422, "Correo electrónico inválido.")
    if d.pais != "MX" or d.moneda != "MXN":
        raise HTTPException(422, "Por ahora solo se cotiza en México y en pesos (MXN).")
    if d.telefono and not re.fullmatch(r"[\d\s+()\-]{7,40}", d.telefono):
        raise HTTPException(422, "Teléfono inválido.")
    return email


def _vence(d: CotizacionIn, c: m.CmConfig) -> datetime:
    v = d.vence_en or (cm.ahora() + timedelta(days=c.vigencia_dias)).replace(hour=23, minute=59, second=0, microsecond=0)
    if v.tzinfo is None:
        from zoneinfo import ZoneInfo
        v = v.replace(tzinfo=ZoneInfo("America/Mexico_City"))
    return v


def _entrada_validada(db: Session, e: dict) -> tuple[dict, dict]:
    entrada = cm.limpiar_entrada(e)
    cm.fecha_iso(entrada.get("emision"), "Fecha de emisión")
    cm.fecha_iso(entrada.get("fecha_limite_pago"), "Fecha límite de pago")
    return entrada, cm.calcular(db, entrada)


@router.post("/cotizaciones", status_code=201)
def crear_cotizacion(d: CotizacionIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    cm.asegurar_catalogo(db)
    conf = cm.config(db)
    email = _validar_cliente(d)
    entrada, calc = _entrada_validada(db, d.entrada)
    entrada["emision"] = entrada.get("emision") or sus.hoy().isoformat()
    c = m.CmCotizacion(estado="borrador", contacto=d.contacto.strip(), despacho=d.despacho.strip(), email=email,
                       telefono=(d.telefono or "").strip() or None, pais="MX", moneda="MXN", necesidad=(d.necesidad or "").strip() or None,
                       notas_internas=(d.notas_internas or "").strip() or None, version_actual=1, vence_en=_vence(d, conf), creado_por_id=a.id)
    cm.guardar_con_folio(db, c)
    v = m.CmVersion(cotizacion_id=c.id, numero=1, entrada=entrada, preparada_por=(d.preparada_por or a.nombre)[:200], creado_por_id=a.id)
    cm.aplicar_calculo(v, calc)
    db.add(v)
    cm.evento(db, c, "creada", admin=a)
    _registrar(db, a, "comercial_cotizacion_creada", request, entidad="cm_cotizacion", entidad_id=c.id, detalle={"folio": c.folio})
    db.commit()
    return detalle(c.id, db)


@router.get("/cotizaciones")
def listar(q: str | None = None, estado: str | None = None, limite: int = Query(100, le=300), db: Session = Depends(get_db)):
    cm.actualizar_vencidas(db)
    db.commit()
    s = select(m.CmCotizacion).order_by(m.CmCotizacion.actualizado_en.desc(), m.CmCotizacion.id.desc()).limit(limite)
    if estado:
        s = s.where(m.CmCotizacion.estado == estado)
    if q and q.strip():
        t = f"%{q.strip()[:80]}%"
        s = s.where(or_(m.CmCotizacion.folio.ilike(t), m.CmCotizacion.despacho.ilike(t), m.CmCotizacion.contacto.ilike(t),
                        m.CmCotizacion.email.ilike(t)))
    res = []
    for c in db.scalars(s):
        v = cm.version(db, c)
        res.append({"id": c.id, "folio": c.folio, "estado": c.estado, "estado_texto": cm.ESTADOS[c.estado], "contacto": c.contacto,
                    "despacho": c.despacho, "email": c.email, "version": c.version_actual, "paquete": v.calculo["paquete"]["nombre"] if v else None,
                    "total": _txt(v.total) if v else None, "vence_en": c.vence_en.isoformat(), "creado_en": c.creado_en.isoformat(),
                    "enviada_en": _iso(c.enviada_en), "actualizado_en": c.actualizado_en.isoformat()})
    return res


def _cot(db: Session, cid: int) -> m.CmCotizacion:
    c = db.get(m.CmCotizacion, cid)
    if not c:
        raise HTTPException(404, "No encontrado.")
    return c


def _acciones(c: m.CmCotizacion, v: m.CmVersion | None) -> dict:
    e = c.estado
    return {"editar": e in ("borrador", "revision", "enviada", "vista", "vencida"),
            "editar_crea_version": e in ("enviada", "vista", "vencida"),
            "marcar_revision": e == "borrador", "regresar_borrador": e == "revision",
            "enviar": e in cm.EDITABLES, "cancelar": e not in ("cancelada", "pagada"),
            "registrar_pago": e in ("enviada", "vista", "aceptada", "pendiente_pago"),
            "convertir": e == "pagada" and not c.convertida_en,
            "asignar_promocional": e in ("enviada", "vista", "aceptada", "pendiente_pago") and not c.convertida_en,
            "enlace": bool(v and c.enviada_en) and e not in ("cancelada",)}


@router.get("/cotizaciones/{cid}")
def detalle(cid: int, db: Session = Depends(get_db)):
    c = _cot(db, cid)
    nombres = _admins(db)
    versiones = db.scalars(select(m.CmVersion).where(m.CmVersion.cotizacion_id == c.id).order_by(m.CmVersion.numero.desc())).all()
    v = next((x for x in versiones if x.numero == c.version_actual), None)
    eventos = db.scalars(select(m.CmEvento).where(m.CmEvento.cotizacion_id == c.id).order_by(m.CmEvento.creado_en.desc(), m.CmEvento.id.desc())).all()
    pagos = db.scalars(select(m.CmPago).where(m.CmPago.cotizacion_id == c.id).order_by(m.CmPago.creado_en.desc())).all()
    asig = db.scalar(select(m.CmAsignacion).where(m.CmAsignacion.cotizacion_id == c.id))
    orgs = dict(db.execute(select(m.Organizacion.id, m.Organizacion.nombre)).all())
    pagado = sum((p.monto or 0 for p in pagos if p.estado == "confirmado"), Decimal("0"))
    enviada = cm.version_enviada(db, c)
    return {
        "id": c.id, "folio": c.folio, "estado": c.estado, "estado_texto": cm.ESTADOS[c.estado], "contacto": c.contacto, "despacho": c.despacho,
        "email": c.email, "telefono": c.telefono, "pais": c.pais, "moneda": c.moneda, "necesidad": c.necesidad, "notas_internas": c.notas_internas,
        "vence_en": c.vence_en.isoformat(), "creado_en": c.creado_en.isoformat(), "creado_por": nombres.get(c.creado_por_id),
        "enviada_en": _iso(c.enviada_en), "vista_en": _iso(c.vista_en), "aceptada_en": _iso(c.aceptada_en), "pagada_en": _iso(c.pagada_en),
        "cancelada_en": _iso(c.cancelada_en), "convertida_en": _iso(c.convertida_en), "version_actual": c.version_actual,
        "version_enviada": enviada.numero if enviada else None,
        "version": {"numero": v.numero, "entrada": v.entrada, "calculo": v.calculo, "preparada_por": v.preparada_por, "cambios": v.cambios,
                    "enviada_en": _iso(v.enviada_en), "huella": v.huella} if v else None,
        "versiones": [{"numero": x.numero, "total": _txt(x.total), "paquete": x.calculo["paquete"]["nombre"], "creado_en": x.creado_en.isoformat(),
                       "enviada_en": _iso(x.enviada_en), "cambios": x.cambios, "huella": x.huella, "preparada_por": x.preparada_por,
                       "creado_por": nombres.get(x.creado_por_id)} for x in versiones],
        "eventos": [{"id": x.id, "tipo": x.tipo, "texto": cm.EVENTOS.get(x.tipo, x.tipo), "actor": x.actor, "por": nombres.get(x.admin_id),
                     "version": x.version, "detalle": x.detalle, "fecha": x.creado_en.isoformat()} for x in eventos],
        "pagos": [{"id": p.id, "version": p.version, "metodo": p.metodo, "estado": p.estado, "monto": _txt(p.monto), "referencia": p.referencia,
                   "fecha_pago": _iso(p.fecha_pago), "registrado_por": nombres.get(p.registrado_por_id), "confirmado_en": _iso(p.confirmado_en)}
                  for p in pagos],
        "pagado": _txt(pagado),
        "enlace": {"url": cm.url_enlace(c), "vence_en": _iso(c.enlace_vence_en), "revocado_en": _iso(c.enlace_revocado_en),
                   "existe": bool(c.enlace_huella)},
        "asignacion": asignacion_dict(asig, orgs) if asig else None,
        "acciones": _acciones(c, v),
    }


@router.put("/cotizaciones/{cid}")
def editar(cid: int, d: CotizacionIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = _cot(db, cid)
    if not _acciones(c, None)["editar"]:
        raise HTTPException(409, f"Una cotización {cm.ESTADOS[c.estado].lower()} no se puede editar. Duplíquela para hacer una nueva.")
    conf = cm.config(db)
    email = _validar_cliente(d)
    entrada, calc = _entrada_validada(db, d.entrada)
    v = cm.version(db, c)
    entrada["emision"] = entrada.get("emision") or (v.entrada.get("emision") if v else None) or sus.hoy().isoformat()
    vence_antes = c.vence_en
    nueva = v.enviada_en is not None
    if nueva:  # la versión enviada queda intacta; se crea la siguiente
        c.version_actual += 1
        v = m.CmVersion(cotizacion_id=c.id, numero=c.version_actual, entrada=entrada, creado_por_id=a.id)
        db.add(v)
        c.estado = "borrador"
    v.entrada = entrada
    v.preparada_por = (d.preparada_por or v.preparada_por or a.nombre)[:200]
    cm.aplicar_calculo(v, calc)
    c.contacto, c.despacho, c.email = d.contacto.strip(), d.despacho.strip(), email
    c.telefono, c.necesidad = (d.telefono or "").strip() or None, (d.necesidad or "").strip() or None
    c.notas_internas = (d.notas_internas or "").strip() or None
    c.vence_en = _vence(d, conf)
    c.actualizado_en = cm.ahora()
    db.flush()
    previa = cm.version_enviada(db, c)
    if previa and previa.numero != v.numero:
        v.cambios = cm.cambios_entre(previa, v, vence_antes, c.vence_en)
    cm.evento(db, c, "nueva_version" if nueva else "editada", admin=a, detalle={"cambios": v.cambios} if nueva else None)
    _registrar(db, a, "comercial_cotizacion_nueva_version" if nueva else "comercial_cotizacion_editada", request, entidad="cm_cotizacion",
               entidad_id=c.id, detalle={"folio": c.folio, "version": c.version_actual})
    db.commit()
    return detalle(c.id, db)


class EstadoIn(BaseModel):
    estado: str


@router.post("/cotizaciones/{cid}/estado")
def cambiar_estado(cid: int, d: EstadoIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = _cot(db, cid)
    if d.estado == "revision" and c.estado == "borrador":
        tipo = "lista_revision"
    elif d.estado == "borrador" and c.estado == "revision":
        tipo = "devuelta_borrador"
    else:
        raise HTTPException(409, "Ese cambio de estado no está permitido.")
    c.estado, c.actualizado_en = d.estado, cm.ahora()
    cm.evento(db, c, tipo, admin=a)
    _registrar(db, a, f"comercial_cotizacion_{tipo}", request, entidad="cm_cotizacion", entidad_id=c.id, detalle={"folio": c.folio})
    db.commit()
    return detalle(c.id, db)


@router.post("/cotizaciones/{cid}/duplicar", status_code=201)
def duplicar(cid: int, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    o = _cot(db, cid)
    v = cm.version(db, o)
    conf = cm.config(db)
    entrada = {**v.entrada, "emision": sus.hoy().isoformat()}
    calc = cm.calcular(db, entrada)  # precios actuales del catálogo
    c = m.CmCotizacion(estado="borrador", contacto=o.contacto, despacho=o.despacho, email=o.email, telefono=o.telefono, pais=o.pais,
                       moneda=o.moneda, necesidad=o.necesidad, notas_internas=o.notas_internas, version_actual=1,
                       vence_en=(cm.ahora() + timedelta(days=conf.vigencia_dias)).replace(hour=23, minute=59, second=0, microsecond=0),
                       creado_por_id=a.id)
    cm.guardar_con_folio(db, c)
    nv = m.CmVersion(cotizacion_id=c.id, numero=1, entrada=entrada, preparada_por=a.nombre, creado_por_id=a.id)
    cm.aplicar_calculo(nv, calc)
    db.add(nv)
    cm.evento(db, c, "creada", admin=a, detalle={"duplicada_de": o.folio})
    cm.evento(db, o, "duplicada", admin=a, detalle={"nueva": c.folio})
    _registrar(db, a, "comercial_cotizacion_duplicada", request, entidad="cm_cotizacion", entidad_id=c.id, detalle={"de": o.folio, "folio": c.folio})
    db.commit()
    return detalle(c.id, db)


class MotivoIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


@router.post("/cotizaciones/{cid}/cancelar")
def cancelar(cid: int, d: MotivoIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = _cot(db, cid)
    if c.estado in ("cancelada", "pagada"):
        raise HTTPException(409, "Esta cotización no se puede cancelar.")
    c.estado, c.cancelada_en, c.actualizado_en = "cancelada", cm.ahora(), cm.ahora()
    cm.evento(db, c, "cancelada", admin=a, detalle={"motivo": d.motivo.strip()})
    _registrar(db, a, "comercial_cotizacion_cancelada", request, entidad="cm_cotizacion", entidad_id=c.id, detalle={"folio": c.folio})
    db.commit()
    return detalle(c.id, db)


def _pdf_version(db: Session, c: m.CmCotizacion, v: m.CmVersion) -> bytes:
    nomira = v.nomira or cm.datos_nomira(cm.config(db))
    return cm_pdf.generar(folio=c.folio, version=v.numero, emision=v.entrada.get("emision"), vence_en=c.vence_en,
                          cliente={"contacto": c.contacto, "despacho": c.despacho, "email": c.email, "telefono": c.telefono},
                          necesidad=c.necesidad, calculo=v.calculo, entrada=v.entrada, nomira=nomira, preparada_por=v.preparada_por,
                          borrador=v.enviada_en is None)


@router.get("/cotizaciones/{cid}/pdf")
def pdf(cid: int, version: int | None = None, db: Session = Depends(get_db)):
    c = _cot(db, cid)
    v = cm.version(db, c, version)
    if not v:
        raise HTTPException(404, "Versión no encontrada.")
    return Response(_pdf_version(db, c, v), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{c.folio}-v{v.numero}.pdf"', "Cache-Control": "no-store"})


class CorreoIn(BaseModel):
    mensaje: str | None = Field(None, max_length=4000)
    asunto: str | None = Field(None, max_length=200)


def _correo(db: Session, c: m.CmCotizacion, v: m.CmVersion, d: CorreoIn, url: str | None) -> tuple[str, str, str]:
    conf = cm.config(db)
    nomira = v.nomira or cm.datos_nomira(conf)
    return cm_correo.armar(folio=c.folio, contacto=c.contacto, despacho=c.despacho,
                           mensaje=d.mensaje or v.entrada.get("mensaje") or conf.mensaje_presentacion, calculo=v.calculo, vence_en=c.vence_en,
                           url=url, nomira=nomira, asunto_plantilla=d.asunto or v.entrada.get("asunto") or conf.asunto_correo, con_pdf=True)


@router.post("/cotizaciones/{cid}/vista-correo")
def vista_correo(cid: int, d: CorreoIn, db: Session = Depends(get_db)):
    c = _cot(db, cid)
    v = cm.version(db, c)
    url = cm.url_enlace(c) or f"{cm.ajustes().url_publica.rstrip('/')}/propuesta#…"
    asunto, html, texto = _correo(db, c, v, d, url)
    return {"asunto": asunto, "html": html, "texto": texto, "para": c.email,
            "mensaje": d.mensaje or v.entrada.get("mensaje") or cm.config(db).mensaje_presentacion or cm_correo.MENSAJE_INICIAL,
            "correo": {"configurado": correo.configurado(), "prueba": correo.modo_prueba() if correo.configurado() else False}}


class EnviarIn(BaseModel):
    confirmacion: str
    mensaje: str | None = Field(None, max_length=4000)
    asunto: str | None = Field(None, max_length=200)
    manual: bool = False  # el administrador la mandó por fuera (sin correo configurado)


@router.post("/cotizaciones/{cid}/enviar")
def enviar(cid: int, d: EnviarIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = _cot(db, cid)
    if d.confirmacion != CONFIRMACION:
        raise HTTPException(422, f"Confirme explícitamente «{CONFIRMACION}».")
    if c.estado not in cm.EDITABLES:
        raise HTTPException(409, "Solo se envían cotizaciones en borrador o listas para revisión.")
    if c.vence_en <= cm.ahora() + timedelta(minutes=30):
        raise HTTPException(422, "La fecha de vencimiento ya pasó o está muy próxima. Ajústela antes de enviar.")
    v = cm.version(db, c)
    nuevo = cm.calcular(db, v.entrada)
    if nuevo["total"] != v.calculo["total"]:
        cm.aplicar_calculo(v, nuevo)
        db.commit()
        raise HTTPException(409, "Los precios del catálogo cambiaron desde que se editó el borrador. Ya se actualizó el cálculo: revise la vista previa y envíe de nuevo.")
    if not d.manual and not correo.configurado():
        raise HTTPException(409, {"codigo": "correo_no_configurado",
                                  "mensaje": "El correo no está configurado: no se envió nada. Descargue el PDF y copie el texto del correo, o configure el correo."})
    conf = cm.config(db)
    v.entrada = {**v.entrada, "mensaje": (d.mensaje or "").strip() or v.entrada.get("mensaje"), "asunto": (d.asunto or "").strip() or v.entrada.get("asunto")}
    v.nomira = cm.datos_nomira(conf)
    if not c.enlace_huella or c.enlace_revocado_en or (c.enlace_vence_en and c.enlace_vence_en < c.vence_en):
        cm.generar_enlace(c)
        cm.evento(db, c, "enlace_generado", admin=a)
    c.enlace_vence_en = c.vence_en + timedelta(days=30)
    url = cm.url_enlace(c)
    v.huella = cm.huella_version(c, v)
    correo_info = None
    if not d.manual:
        asunto, html, texto = _correo(db, c, v, CorreoIn(), url)
        archivo = (f"{c.folio}-v{v.numero}.pdf", _pdf_version_final(db, c, v), "application/pdf")
        db.flush()
        r = envios.registrar_y_enviar(db, "cotizacion", [c.email], asunto, html, texto, adjuntos=[archivo])
        if r.estado != "enviado":
            cm.evento(db, c, "envio_fallido", admin=a, detalle={"error": (r.error or "")[:300]})
            db.commit()
            raise HTTPException(502, f"No se pudo enviar el correo: {r.error}. La cotización sigue como {cm.ESTADOS[c.estado].lower()}.")
        correo_info = {"prueba": correo.modo_prueba()}
    v.enviada_en = c.enviada_en = c.actualizado_en = cm.ahora()
    c.estado = "enviada"
    cm.evento(db, c, "enviada_manual" if d.manual else "enviada", admin=a,
              detalle={"version": v.numero, "huella": v.huella, **({"modo_prueba": True} if correo_info and correo_info["prueba"] else {})})
    _registrar(db, a, "comercial_cotizacion_enviada", request, entidad="cm_cotizacion", entidad_id=c.id,
               detalle={"folio": c.folio, "version": v.numero, "manual": d.manual})
    db.commit()
    return {**detalle(c.id, db), "envio": {"manual": d.manual, "prueba": bool(correo_info and correo_info["prueba"])}}


def _pdf_version_final(db: Session, c: m.CmCotizacion, v: m.CmVersion) -> bytes:
    """PDF tal como lo recibirá el cliente (sin la marca de vista previa)."""
    nomira = v.nomira or cm.datos_nomira(cm.config(db))
    return cm_pdf.generar(folio=c.folio, version=v.numero, emision=v.entrada.get("emision"), vence_en=c.vence_en,
                          cliente={"contacto": c.contacto, "despacho": c.despacho, "email": c.email, "telefono": c.telefono},
                          necesidad=c.necesidad, calculo=v.calculo, entrada=v.entrada, nomira=nomira, preparada_por=v.preparada_por)


class EnlaceIn(BaseModel):
    accion: str  # revocar | regenerar


@router.post("/cotizaciones/{cid}/enlace")
def enlace(cid: int, d: EnlaceIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = _cot(db, cid)
    if not c.enviada_en:
        raise HTTPException(409, "La cotización aún no se ha enviado.")
    if d.accion == "revocar":
        c.enlace_revocado_en = cm.ahora()
        cm.evento(db, c, "enlace_revocado", admin=a)
    elif d.accion == "regenerar":
        cm.generar_enlace(c)
        cm.evento(db, c, "enlace_generado", admin=a, detalle={"regenerado": True})
    else:
        raise HTTPException(422, "Acción inválida.")
    _registrar(db, a, f"comercial_enlace_{d.accion}", request, entidad="cm_cotizacion", entidad_id=c.id, detalle={"folio": c.folio})
    db.commit()
    return detalle(c.id, db)


class PagoIn(BaseModel):
    metodo: str  # spei | otro | tarjeta (si Stripe no lo registró)
    monto: Decimal = Field(gt=0, le=10_000_000)
    fecha_pago: date
    referencia: str = Field(min_length=2, max_length=120)


@router.post("/cotizaciones/{cid}/pagos", status_code=201)
def registrar_pago(cid: int, d: PagoIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    """El superadministrador confirma que RECIBIÓ el pago (un comprobante del cliente no basta)."""
    c = _cot(db, cid)
    if c.estado not in ("enviada", "vista", "aceptada", "pendiente_pago"):
        raise HTTPException(409, f"No se registran pagos en una cotización {cm.ESTADOS[c.estado].lower()}.")
    if d.metodo not in ("spei", "otro", "tarjeta"):
        raise HTTPException(422, "Forma de pago inválida.")
    if d.fecha_pago > sus.hoy():
        raise HTTPException(422, "La fecha de pago no puede ser futura.")
    v = cm.version_enviada(db, c)
    p = m.CmPago(cotizacion_id=c.id, version=v.numero, metodo=d.metodo, estado="confirmado", monto=cm.dinero(d.monto),
                 referencia=d.referencia.strip(), fecha_pago=d.fecha_pago, registrado_por_id=a.id, confirmado_en=cm.ahora())
    db.add(p)
    db.flush()
    _aplicar_pagos(db, c, v, actor="admin", admin=a)
    cm.evento(db, c, "pago_registrado", admin=a, detalle={"metodo": d.metodo, "monto": _txt(p.monto), "referencia": p.referencia,
                                                           "fecha_pago": d.fecha_pago.isoformat()})
    _registrar(db, a, "comercial_pago_registrado", request, entidad="cm_cotizacion", entidad_id=c.id,
               detalle={"folio": c.folio, "metodo": d.metodo, "monto": _txt(p.monto)})
    db.commit()
    return detalle(c.id, db)


def _aplicar_pagos(db: Session, c: m.CmCotizacion, v: m.CmVersion, actor: str, admin: m.AdminPlataforma | None = None) -> None:
    db.flush()  # la sesión no hace autoflush: el pago recién confirmado debe contar en la suma
    pagado = db.scalar(select(func.coalesce(func.sum(m.CmPago.monto), 0)).where(m.CmPago.cotizacion_id == c.id, m.CmPago.estado == "confirmado"))
    if Decimal(pagado) >= v.total and c.estado != "pagada":
        c.estado, c.pagada_en = "pagada", cm.ahora()
        cm.evento(db, c, "pagada", actor=actor, admin=admin, detalle={"pagado": _txt(Decimal(pagado))})
    elif c.estado in ("enviada", "vista", "aceptada"):
        c.estado = "pendiente_pago"
    c.actualizado_en = cm.ahora()


class ConvertirIn(BaseModel):
    organizacion_id: int
    inicio: date | None = None
    promocional: bool = False
    motivo: str | None = Field(None, max_length=300)
    confirmo: bool = False


PLAN_SUSCRIPCION = {"mensual": "mensual", "semestral": "semestral", "anual": "anual"}


@router.post("/cotizaciones/{cid}/convertir")
def convertir(cid: int, d: ConvertirIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    """Asigna el paquete a una organización: activa módulos, registra capacidades y crea el periodo.
    Solo con pago confirmado, o como asignación promocional con motivo y confirmación explícita."""
    c = _cot(db, cid)
    if c.convertida_en:
        raise HTTPException(409, "Esta cotización ya se asignó.")
    if d.promocional:
        if not d.confirmo or not (d.motivo or "").strip() or len(d.motivo.strip()) < 5:
            raise HTTPException(422, "Una asignación promocional requiere motivo y confirmación.")
        if c.estado not in ("enviada", "vista", "aceptada", "pendiente_pago"):
            raise HTTPException(409, "No se puede asignar en este estado.")
    elif c.estado != "pagada":
        raise HTTPException(409, "Solo se asigna una cotización PAGADA (o como asignación promocional aprobada).")
    org = db.get(m.Organizacion, d.organizacion_id)
    if not org:
        raise HTTPException(404, "Organización no encontrada. Dé de alta al despacho en «Clientes» primero.")
    v = cm.version_enviada(db, c)
    calc = v.calculo
    inicio = d.inicio or sus.hoy()
    plan = PLAN_SUSCRIPCION[calc["periodicidad"]["clave"]]
    fin = sus.calcular_fin(plan, inicio)
    periodo = m.PeriodoSuscripcion(organizacion_id=org.id, plan=plan, inicio=inicio, fin=fin, monto=v.total, pagado=not d.promocional,
                                   pagado_en=c.pagada_en.date() if c.pagada_en else None,
                                   nota=f"Cotización {c.folio} v{v.numero}" + (" · promocional" if d.promocional else ""), creado_por_id=a.id)
    db.add(periodo)
    db.flush()
    mods = [x["clave"] for x in calc["modulos"]]
    for clave in mods:  # solo AGREGA módulos: nunca desactiva ni oculta los que ya tenía
        modulos.fijar(db, org.id, clave, contratado=True, activo=True)
    from ..services.academia import lms
    for x in calc.get("cursos") or []:  # cursos de Nomira con costo incluidos en la cotización
        cur = db.get(m.AcCurso, x["id"])
        if cur:
            lms.otorgar(db, org.id, cur, "comercial", cotizacion_id=c.id, admin_id=a.id)
    if calc.get("cursos_extra"):
        org.ac_cursos_extra = max(org.ac_cursos_extra or 0, int(calc["cursos_extra"]))
    asig = m.CmAsignacion(organizacion_id=org.id, cotizacion_id=c.id, periodo_id=periodo.id, paquete=calc["paquete"]["nombre"], modulos=mods,
                          usuarios=calc["usuarios"]["total"], almacenamiento_gb=calc["almacenamiento"]["total_gb"],
                          periodicidad=calc["periodicidad"]["clave"], monto=v.total, inicio=inicio, renovacion=fin + timedelta(days=1),
                          estado="activa", origen="promocional" if d.promocional else "pago",
                          motivo=d.motivo.strip() if d.promocional else None, creado_por_id=a.id)
    db.add(asig)
    c.convertida_en, c.organizacion_id, c.actualizado_en = cm.ahora(), org.id, cm.ahora()
    cm.evento(db, c, "convertida", admin=a, detalle={"organizacion": org.nombre, "promocional": d.promocional, "modulos": mods})
    _registrar(db, a, "comercial_cotizacion_convertida", request, organizacion_id=org.id, entidad="cm_cotizacion", entidad_id=c.id,
               detalle={"folio": c.folio, "promocional": d.promocional, "modulos": mods})
    db.commit()
    return detalle(c.id, db)
