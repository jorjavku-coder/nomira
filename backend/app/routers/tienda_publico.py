"""Precios públicos y carrito (sin sesión): la persona arma su plan en /precios y recibe al instante su
cotización formal (folio, PDF y enlace para aceptarla y pagarla). Todos los importes los calcula el servidor
con el catálogo vigente; solo se publica si Nomira eligió «precios completos» en Comercial > Configuración."""
from __future__ import annotations

import re
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..freno import Ventana
from ..services import correo, envios, modulos
from ..services import suscripciones as sus
from ..services.comercial import base as cm
from ..services.ventas import base as ventas
from .comercial import CorreoIn, _correo, _pdf_version_final

router = APIRouter(prefix="/api/precios", tags=["Precios y carrito"])
_calculos_ip = Ventana(120, 600)
_cotizar_ip = Ventana(5, 3600)
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _publicados(db: Session) -> m.CmConfig:
    cm.asegurar_catalogo(db)
    c = cm.config(db)
    if c.precios_publicos != "completos":
        raise HTTPException(404, "Los precios no están publicados. Solicite una cotización.")
    return c


def _freno(v: Ventana, request: Request) -> None:
    ip = ip_cliente(request) or "?"
    if v.excedida(ip):
        raise HTTPException(429, "Demasiadas solicitudes seguidas. Espere unos minutos.")
    v.registrar(ip)


def _entrada(d: "CarritoIn") -> dict:
    """Solo lo que la persona puede elegir: nada de descuentos manuales, servicios ni condiciones."""
    return cm.limpiar_entrada({"paquete_id": d.paquete_id, "modulos": d.modulos, "periodicidad": d.periodicidad,
                               "usuarios_extra": d.usuarios_extra, "bloques_extra": d.bloques_extra, "cupon": d.cupon})


@router.get("")
def catalogo(db: Session = Depends(get_db)):
    c = _publicados(db)
    precios = {p.clave: p for p in db.scalars(select(m.CmPrecio).where(m.CmPrecio.activo.is_(True)))}
    datos = {
        "paquetes": [{"id": p.id, "nombre": p.nombre, "descripcion": p.descripcion, "precio_mensual": cm.txt(p.precio_mensual),
                      "modulos_incluidos": p.modulos_incluidos, "usuarios": p.usuarios, "almacenamiento_gb": p.almacenamiento_gb}
                     for p in db.scalars(select(m.CmPaquete).where(m.CmPaquete.estado == "activo").order_by(m.CmPaquete.orden, m.CmPaquete.id))],
        "modulos": [{"clave": k, "nombre": v["nombre"], "descripcion": v.get("descripcion"),
                     "precio_adicional": cm.txt(precios[f"modulo:{k}"].precio_mensual) if f"modulo:{k}" in precios else None}
                    for k, v in modulos.MODULOS.items()],
        "usuario_extra": cm.txt(precios["usuario"].precio_mensual) if "usuario" in precios else None,
        "almacenamiento": {"precio": cm.txt(precios["almacenamiento"].precio_mensual), "gb": precios["almacenamiento"].unidad_gb}
        if "almacenamiento" in precios else None,
        "periodicidades": [{"clave": k, "nombre": cm.PERIODICIDADES[k][0], "meses": cm.PERIODICIDADES[k][1]} for k in cm.periodicidades_habilitadas(c)],
        "iva_pct": cm.txt(c.iva_pct), "formas_pago": [f["nombre"] for f in cm.formas_pago(c)], "vigencia_dias": c.vigencia_dias,
    }
    db.commit()
    return datos


class CarritoIn(BaseModel):
    paquete_id: int
    modulos: list[str] = Field(default_factory=list, max_length=10)
    periodicidad: str = "mensual"
    usuarios_extra: int = Field(0, ge=0, le=200)
    bloques_extra: int = Field(0, ge=0, le=40)
    cupon: str | None = Field(None, max_length=40)


@router.post("/calcular")
def calcular(d: CarritoIn, request: Request, db: Session = Depends(get_db)):
    _freno(_calculos_ip, request)
    _publicados(db)
    r = cm.calcular(db, _entrada(d))  # el cupón se valida y aplica igual que en una propuesta
    db.commit()
    return r


class CotizarIn(CarritoIn):
    contacto: str = Field(min_length=2, max_length=200)
    despacho: str = Field(min_length=2, max_length=200)
    email: str = Field(max_length=254)
    telefono: str | None = Field(None, max_length=40)
    acepto: bool = False
    sitio_web: str | None = Field(None, max_length=200)  # campo trampa


@router.post("/cotizar", status_code=201)
def cotizar(d: CotizarIn, request: Request, db: Session = Depends(get_db)):
    """Crea la cotización, la «envía» (folio, PDF, enlace seguro) y devuelve el enlace para aceptarla y pagarla."""
    _freno(_cotizar_ip, request)
    if d.sitio_web:
        raise HTTPException(422, "No se pudo procesar la solicitud.")
    conf = _publicados(db)
    if not d.acepto:
        raise HTTPException(422, "Acepte el aviso de privacidad para recibir su cotización.")
    email = d.email.strip().lower()
    if not _RE_EMAIL.match(email):
        raise HTTPException(422, "Correo electrónico inválido.")
    tel = (d.telefono or "").strip() or None
    if tel and not re.fullmatch(r"[\d\s+()\-]{7,40}", tel):
        raise HTTPException(422, "Teléfono inválido.")
    entrada = _entrada(d)
    entrada["emision"] = sus.hoy().isoformat()
    calc = cm.calcular(db, entrada)
    vence = (cm.ahora().astimezone(ZoneInfo("America/Mexico_City")) + timedelta(days=conf.vigencia_dias)).replace(hour=23, minute=59, second=0, microsecond=0)
    c = m.CmCotizacion(estado="borrador", contacto=" ".join(d.contacto.split()), despacho=" ".join(d.despacho.split()), email=email,
                       telefono=tel, pais="MX", moneda="MXN", necesidad="Armó su plan en la página de precios de nomirasoft.com.",
                       version_actual=1, vence_en=vence)
    cm.guardar_con_folio(db, c)
    v = m.CmVersion(cotizacion_id=c.id, numero=1, entrada=entrada, preparada_por="Nomira (en línea)")
    cm.aplicar_calculo(v, calc)
    db.add(v)
    cm.evento(db, c, "creada", actor="cliente", detalle={"origen": "precios"})
    v.nomira = cm.datos_nomira(conf)
    cm.generar_enlace(c)
    url = cm.url_enlace(c)
    db.flush()
    v.huella = cm.huella_version(c, v)
    enviado = False
    if correo.configurado():
        asunto, html, texto = _correo(db, c, v, CorreoIn(), url)
        try:
            r = envios.registrar_y_enviar(db, "cotizacion", [c.email], asunto, html, texto,
                                          adjuntos=[(f"{c.folio}-v1.pdf", _pdf_version_final(db, c, v), "application/pdf")])
            enviado = r is not None and r.estado == "enviado"
        except Exception:  # sin correo, la persona igual ve su cotización en pantalla
            enviado = False
    v.enviada_en = c.enviada_en = c.actualizado_en = cm.ahora()
    c.estado = "enviada"
    cm.evento(db, c, "enviada" if enviado else "enviada_manual", actor="cliente", detalle={"version": 1, "huella": v.huella, "origen": "precios"})
    sol = m.Solicitud(tipo="suscripcion", nombre=c.contacto, empresa=c.despacho, email=email, telefono=tel, ip=(ip_cliente(request) or "")[:60] or None,
                      mensaje=f"Armó su plan en Precios y recibió la cotización {c.folio} por ${float(calc['total']):,.2f} (IVA incluido).")
    db.add(sol)
    db.flush()
    ventas.desde_solicitud(db, sol)
    db.commit()
    return {"folio": c.folio, "total": calc["total"], "url": url, "correo_enviado": enviado}
