"""Crecimiento de Nomira: puntos, premios (descuentos y meses de regalo), referidos y juegos.

Reglas que protegen el negocio y la confianza:
- Los meses de regalo se agregan como periodo «cortesía» al final del plan pagado. Si el despacho nunca ha
  pagado, el premio espera a su primer pago (así un premio nunca sustituye la primera compra).
- Los descuentos son cupones de un solo uso, con vencimiento, que se aplican en la siguiente propuesta.
- Topes anuales por despacho para meses ganados en juegos y por invitar.
- Todo premio sale de un sorteo transparente (probabilidades visibles) o de reglas fijas (trivia, tienda).
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models as m
from .. import suscripciones as sus
from .preguntas import PREGUNTAS

PLANES_DE_PAGO = ("mensual", "semestral", "anual")
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
DIAS_CUPON = 90

RULETA_FABRICA = [  # etiqueta, tipo, valor, peso (de 1000), tope mensual en todo Nomira
    ("20 puntos", "puntos", 20, 380, None), ("50 puntos", "puntos", 50, 250, None), ("100 puntos", "puntos", 100, 120, None),
    ("5% de descuento", "descuento", 5, 120, None), ("10% de descuento", "descuento", 10, 70, None),
    ("1 mes gratis", "meses", 1, 45, 20), ("3 meses gratis", "meses", 3, 12, 5), ("6 meses gratis", "meses", 6, 3, 2),
]
TIENDA_FABRICA = [  # etiqueta, tipo, valor, costo en puntos
    ("10% de descuento", "descuento", 10, 500), ("15% de descuento", "descuento", 15, 900),
    ("1 mes gratis", "meses", 1, 1500), ("3 meses gratis", "meses", 3, 4000), ("6 meses gratis", "meses", 6, 7500),
]


def hoy() -> date:
    return sus.hoy()


def config(db: Session) -> m.CxConfig:
    c = db.scalar(select(m.CxConfig))
    if not c:
        c = m.CxConfig(juegos_activos=True, ruleta_activa=False, puntos_por_acierto=10, preguntas_por_dia=3, tope_puntos_dia_org=60,
                       tope_meses_anual=6, referidos_activos=True, meses_referido=1, tope_referidos_anual=12, casos_activos=True)
        db.add(c)
        db.flush()
        sembrar(db, c)
    return c


def sembrar(db: Session, c: m.CxConfig | None = None) -> None:
    """Preguntas, casillas de la ruleta y artículos de la tienda de fábrica. Idempotente (se llama en cada arranque)."""
    if c is None:
        config(db)
    claves = set(db.scalars(select(m.CxPregunta.clave).where(m.CxPregunta.clave.is_not(None))).all())
    for clave, materia, texto, opciones, correcta, explicacion in PREGUNTAS:
        if clave not in claves:
            db.add(m.CxPregunta(clave=clave, materia=materia, texto=texto, opciones=opciones, correcta=correcta, explicacion=explicacion, activa=True))
    if not db.scalar(select(func.count()).select_from(m.CxPremio)):
        for i, (et, tipo, valor, peso, tope) in enumerate(RULETA_FABRICA):
            db.add(m.CxPremio(lugar="ruleta", etiqueta=et, tipo=tipo, valor=valor, peso=peso, tope_mensual=tope, orden=i, activo=True, costo=0))
        for i, (et, tipo, valor, costo) in enumerate(TIENDA_FABRICA):
            db.add(m.CxPremio(lugar="tienda", etiqueta=et, tipo=tipo, valor=valor, costo=costo, orden=i, activo=True, peso=0))
    db.flush()


def candado(db: Session, org_id: int) -> None:
    """Serializa giros, canjes y puntos de un despacho (evita doble gasto con dos clics al mismo tiempo)."""
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": 7_700_000_000 + org_id})


# ---------------------------------------------------------------- puntos

def saldo(db: Session, org_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(m.CxMovimiento.puntos), 0)).where(m.CxMovimiento.organizacion_id == org_id)) or 0)


def puntos_hoy(db: Session, org_id: int, origen: str = "trivia") -> int:
    return int(db.scalar(select(func.coalesce(func.sum(m.CxMovimiento.puntos), 0)).where(
        m.CxMovimiento.organizacion_id == org_id, m.CxMovimiento.origen == origen, m.CxMovimiento.dia == hoy())) or 0)


def mover(db: Session, org_id: int, usuario_id: int | None, origen: str, puntos: int, detalle: str) -> m.CxMovimiento:
    x = m.CxMovimiento(organizacion_id=org_id, usuario_id=usuario_id, origen=origen, puntos=puntos, detalle=detalle[:200], dia=hoy())
    db.add(x)
    db.flush()
    return x


# ---------------------------------------------------------------- suscripción: ¿ya pagó alguna vez?

def periodos(db: Session, org_id: int) -> list[m.PeriodoSuscripcion]:
    return list(db.scalars(select(m.PeriodoSuscripcion).where(m.PeriodoSuscripcion.organizacion_id == org_id)
                           .order_by(m.PeriodoSuscripcion.inicio, m.PeriodoSuscripcion.id)).all())


def ya_pago(db: Session, org_id: int) -> bool:
    return any(p.plan in PLANES_DE_PAGO and p.pagado for p in periodos(db, org_id))


def plan_pagado_vigente(db: Session, org_id: int) -> bool:
    """Plan de pago o de regalo vigente (no prueba) y al menos un pago real en su historial."""
    return ya_pago(db, org_id) and sus.estado(periodos(db, org_id))["estado"] in ("activa", "por_vencer")


# ---------------------------------------------------------------- recompensas

def meses_del_anio(db: Session, org_id: int, origenes: tuple[str, ...]) -> int:
    desde = datetime.combine(hoy() - timedelta(days=365), datetime.min.time())
    return int(db.scalar(select(func.coalesce(func.sum(m.CxRecompensa.valor), 0)).where(
        m.CxRecompensa.organizacion_id == org_id, m.CxRecompensa.tipo == "meses", m.CxRecompensa.origen.in_(origenes),
        m.CxRecompensa.creado_en >= desde)) or 0)


def _cupon(db: Session, org: m.Organizacion, pct: int, descripcion: str) -> m.CmCupon:
    for _ in range(6):
        codigo = "PREMIO-" + "".join(secrets.choice(ALFABETO) for _ in range(6))
        try:
            with db.begin_nested():
                c = m.CmCupon(codigo=codigo, descripcion=f"{descripcion} · {org.nombre}"[:300], tipo="porcentaje", valor=Decimal(pct),
                              aplica_a="todo", inicia_en=hoy(), vence_en=hoy() + timedelta(days=DIAS_CUPON), usos_maximos=1, estado="activo")
                db.add(c)
            return c
        except IntegrityError:
            continue
    raise RuntimeError("No se pudo generar un código de cupón único.")


def _agregar_meses(db: Session, org_id: int, meses: int, nota: str) -> m.PeriodoSuscripcion:
    ps = periodos(db, org_id)
    inicio = max(hoy(), max((p.fin for p in ps), default=hoy() - timedelta(days=1)) + timedelta(days=1))
    p = m.PeriodoSuscripcion(organizacion_id=org_id, plan="cortesia", inicio=inicio, fin=sus.sumar_meses(inicio, meses) - timedelta(days=1),
                             monto=Decimal("0"), pagado=True, pagado_en=hoy(), nota=nota[:500])
    db.add(p)
    db.flush()
    return p


def _aplicar(db: Session, r: m.CxRecompensa) -> None:
    p = _agregar_meses(db, r.organizacion_id, r.valor, f"Meses de regalo: {r.descripcion}")
    r.estado, r.periodo_id, r.aplicada_en = "aplicada", p.id, m.ahora()


def otorgar(db: Session, org_id: int, origen: str, tipo: str, valor: int, descripcion: str) -> m.CxRecompensa:
    """Crea la recompensa. Descuento: cupón listo para usar. Meses: se aplican ya si el despacho ha pagado; si no, al primer pago."""
    org = db.get(m.Organizacion, org_id)
    r = m.CxRecompensa(organizacion_id=org_id, origen=origen, tipo=tipo, valor=valor, descripcion=descripcion[:200], estado="pendiente")
    db.add(r)
    db.flush()
    if tipo == "descuento":
        c = _cupon(db, org, valor, descripcion)
        r.cupon_id, r.estado = c.id, "disponible"
    elif ya_pago(db, org_id):
        _aplicar(db, r)
    return r


def al_pagar(db: Session, org_id: int) -> None:
    """Se llama cuando un despacho queda con un plan PAGADO. Aplica los meses que tenía guardados y premia la invitación."""
    if not ya_pago(db, org_id):
        return
    for r in db.scalars(select(m.CxRecompensa).where(m.CxRecompensa.organizacion_id == org_id, m.CxRecompensa.tipo == "meses",
                                                     m.CxRecompensa.estado == "pendiente").order_by(m.CxRecompensa.id)).all():
        _aplicar(db, r)
    ref = db.scalar(select(m.CxReferido).where(m.CxReferido.referido_id == org_id, m.CxReferido.estado == "registrado"))
    if not ref:
        return
    c = config(db)
    ref.estado, ref.premiado_en = "premiado", m.ahora()
    if not c.referidos_activos or c.meses_referido < 1:
        return
    nuevo = db.get(m.Organizacion, org_id)
    otorgar(db, org_id, "invitado", "meses", c.meses_referido, "Bienvenida por llegar con una invitación")
    if meses_del_anio(db, ref.referidor_id, ("referido",)) + c.meses_referido <= c.tope_referidos_anual:
        otorgar(db, ref.referidor_id, "referido", "meses", c.meses_referido, f"Invitó a {nuevo.nombre}")


def vista_recompensa(db: Session, r: m.CxRecompensa) -> dict:
    d = {"id": r.id, "origen": r.origen, "tipo": r.tipo, "valor": r.valor, "descripcion": r.descripcion, "estado": r.estado,
         "creado_en": r.creado_en.isoformat()}
    if r.cupon_id:
        c = db.get(m.CmCupon, r.cupon_id)
        if c:
            d["cupon"] = {"codigo": c.codigo, "vence_en": c.vence_en.isoformat() if c.vence_en else None, "usado": bool(c.usos)}
            if c.usos:
                d["estado"] = "usada"
            elif c.vence_en and c.vence_en < hoy():
                d["estado"] = "vencida"
    if r.periodo_id:
        p = db.get(m.PeriodoSuscripcion, r.periodo_id)
        if p:
            d["periodo"] = {"inicio": p.inicio.isoformat(), "fin": p.fin.isoformat()}
    return d


# ---------------------------------------------------------------- invitaciones (referidos)

def invitacion(db: Session, org_id: int) -> m.CxInvitacion:
    x = db.scalar(select(m.CxInvitacion).where(m.CxInvitacion.organizacion_id == org_id))
    if x:
        return x
    for _ in range(6):
        codigo = "".join(secrets.choice(ALFABETO) for _ in range(6))
        try:
            with db.begin_nested():
                x = m.CxInvitacion(organizacion_id=org_id, codigo=codigo)
                db.add(x)
            return x
        except IntegrityError:
            continue
    raise RuntimeError("No se pudo generar el código de invitación.")


def buscar_invitacion(db: Session, codigo: str | None) -> m.CxInvitacion | None:
    codigo = "".join(ch for ch in (codigo or "").upper() if ch.isalnum())[:12]
    if len(codigo) < 4:
        return None
    return db.scalar(select(m.CxInvitacion).where(m.CxInvitacion.codigo == codigo))


def registrar_referido(db: Session, org_nueva_id: int, codigo: str | None) -> bool:
    """Liga al despacho recién creado con quien lo invitó (solo al registrarse, una vez)."""
    if not codigo or not config(db).referidos_activos:
        return False
    inv = buscar_invitacion(db, codigo)
    if not inv or inv.organizacion_id == org_nueva_id:
        return False
    org = db.get(m.Organizacion, inv.organizacion_id)
    if not org or org.estado != "activa":
        return False
    db.add(m.CxReferido(referidor_id=inv.organizacion_id, referido_id=org_nueva_id, estado="registrado"))
    db.flush()
    return True
