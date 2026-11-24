"""Módulo Comercial: catálogo de paquetes, cálculo de cotizaciones, versiones y estados.

Reglas:
- Todo importe se calcula AQUÍ, en el servidor, con Decimal. Lo que mande el navegador como importe
  se ignora.
- Una versión enviada queda congelada (precios, datos de Nomira y formas de pago). Cambiar precios del
  catálogo no altera cotizaciones ya enviadas.
- Las notas internas nunca forman parte de lo que ve el cliente.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import text, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models as m
from ...config import ajustes
from ..afore.cifrado import cifrar, descifrar
from ..modulos import MODULOS

CENT = Decimal("0.01")
ESTADOS = {"borrador": "Borrador", "revision": "Lista para revisión", "enviada": "Enviada", "vista": "Vista por el cliente",
           "aceptada": "Aceptada", "pendiente_pago": "Pendiente de pago", "pagada": "Pagada", "vencida": "Vencida",
           "cancelada": "Cancelada"}
EDITABLES = ("borrador", "revision")
ABIERTAS_CLIENTE = ("enviada", "vista")  # el cliente puede aceptar o pedir ajustes
PERIODICIDADES = {"mensual": ("Mensual", 1), "semestral": ("Semestral", 6), "anual": ("Anual", 12)}
SERVICIOS = {"configuracion": "Configuración inicial", "migracion": "Migración de información",
             "capacitacion": "Capacitación", "soporte": "Soporte adicional"}
EVENTOS = {
    "creada": "Cotización creada", "editada": "Borrador editado", "nueva_version": "Nueva versión creada",
    "lista_revision": "Marcada como lista para revisión", "devuelta_borrador": "Regresada a borrador",
    "enviada": "Enviada por correo", "enviada_manual": "Marcada como enviada por fuera de Nomira",
    "envio_fallido": "El correo no se pudo enviar", "enlace_generado": "Enlace del cliente generado",
    "enlace_revocado": "Enlace del cliente revocado", "vista": "El cliente consultó la propuesta",
    "ajuste_solicitado": "El cliente pidió ajustes", "aceptada": "El cliente registró su aceptación",
    "pago_iniciado": "Pago con tarjeta iniciado", "transferencia_reportada": "El cliente indicó que pagará o pagó por transferencia",
    "pago_registrado": "Pago registrado", "pagada": "Pagada", "vencida": "Venció", "cancelada": "Cancelada",
    "duplicada": "Duplicada", "convertida": "Asignada a la organización", "descargada": "PDF descargado",
}

# Valores INICIALES (editables desde el panel); se crean solo si el catálogo está vacío.
PAQUETES_INICIALES = [
    {"clave": "basico", "nombre": "Básico", "precio_mensual": "1790", "modulos_incluidos": 1, "usuarios": 5, "almacenamiento_gb": 10, "orden": 1},
    {"clave": "medio", "nombre": "Medio", "precio_mensual": "3490", "modulos_incluidos": 3, "usuarios": 15, "almacenamiento_gb": 30, "orden": 2},
    {"clave": "premium", "nombre": "Premium", "precio_mensual": "5990", "modulos_incluidos": 5, "usuarios": 30, "almacenamiento_gb": 75, "orden": 3},
]
PRECIOS_INICIALES = [
    {"clave": "modulo:nomina", "nombre": "Nómina y prestaciones", "precio_mensual": "950"},
    {"clave": "modulo:evidencia", "nombre": "Nomira Evidencia", "precio_mensual": "950"},
    {"clave": "modulo:afore", "nombre": "Nomira AFORE", "precio_mensual": "1190"},
    {"clave": "modulo:leads", "nombre": "Nomira Leads", "precio_mensual": "690"},
    {"clave": "modulo:academia", "nombre": "Nomira Academia", "precio_mensual": "590"},
    {"clave": "modulo:agenda", "nombre": "Nomira Agenda Jurídica", "precio_mensual": "890"},
    {"clave": "modulo:escrituracion", "nombre": "Nomira Escrituración", "precio_mensual": "1490"},
    {"clave": "usuario", "nombre": "Usuario interno adicional", "precio_mensual": "119"},
    {"clave": "almacenamiento", "nombre": "Almacenamiento adicional (bloque)", "precio_mensual": "299", "unidad_gb": 25},
    {"clave": "curso_adicional", "nombre": "Curso propio adicional (Academia)", "precio_mensual": "99"},
]


def ahora() -> datetime:
    return m.ahora()


def dinero(v) -> Decimal:
    try:
        d = Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(422, "Importe inválido.")
    if d < 0 or d > Decimal("10000000"):
        raise HTTPException(422, "Importe fuera de rango.")
    return d


def txt(v: Decimal | None) -> str | None:
    return None if v is None else f"{v:.2f}"


def config(db: Session) -> m.CmConfig:
    c = db.scalar(select(m.CmConfig))
    if c is None:
        c = m.CmConfig(nombre_comercial="Nomira", iva_pct=Decimal("16"), vigencia_dias=15, descuento_maximo_pct=Decimal("20"),
                       periodicidades=["mensual", "anual"], precios_publicos="ocultos", aceptacion_en_linea=True)
        db.add(c)
        db.flush()
    return c


def asegurar_catalogo(db: Session) -> None:
    """Crea los paquetes y precios iniciales solo si no existe ninguno. Nunca pisa cambios.
    Un candado de la base evita que dos peticiones simultáneas (p. ej. la primera vez que se abre
    «Paquetes y precios») creen el catálogo dos veces."""
    db.execute(text("SELECT pg_advisory_xact_lock(4202611)"))
    config(db)
    if not db.scalar(select(func.count(m.CmPaquete.id))):
        for p in PAQUETES_INICIALES:
            db.add(m.CmPaquete(**{**p, "precio_mensual": Decimal(p["precio_mensual"])}, ciclo="mensual", estado="activo"))
    existentes = set(db.scalars(select(m.CmPrecio.clave)))
    for p in PRECIOS_INICIALES:
        if p["clave"] not in existentes:
            db.add(m.CmPrecio(**{**p, "precio_mensual": Decimal(p["precio_mensual"]), "activo": p.get("activo", True)}))
    db.flush()


# ------------------------------------------------------------------ Stripe (modo de prueba o real)

PREFIJOS_STRIPE = {"prueba": ("sk_test_", "rk_test_"), "real": ("rk_live_", "sk_live_")}


def stripe_modo() -> str:
    m = (ajustes().stripe_modo or "prueba").strip().lower()
    return m if m in PREFIJOS_STRIPE else "invalido"


def stripe_estado() -> dict:
    """Stripe solo queda conectado si el MODO elegido y el tipo de LLAVE coinciden."""
    a = ajustes()
    llave, secreto, modo = a.stripe_secret_key.strip(), a.stripe_webhook_secret.strip(), stripe_modo()
    if modo == "invalido":
        return {"conectado": False, "modo": None, "motivo": "STRIPE_MODO debe ser «prueba» o «real»."}
    if not llave:
        return {"conectado": False, "modo": modo, "motivo": "Pago en línea pendiente de configuración."}
    if not llave.startswith(PREFIJOS_STRIPE[modo]):
        if modo == "prueba":
            motivo = "Se rechazó la llave: STRIPE_MODO=prueba solo acepta llaves de prueba (sk_test_ o rk_test_)."
        else:
            motivo = "Se rechazó la llave: STRIPE_MODO=real solo acepta llaves reales (rk_live_ o sk_live_)."
        return {"conectado": False, "modo": modo, "motivo": motivo}
    if not secreto.startswith("whsec_"):
        return {"conectado": False, "modo": modo, "motivo": "Falta el secreto del webhook de Stripe (STRIPE_WEBHOOK_SECRET)."}
    return {"conectado": True, "modo": modo, "motivo": None}


def formas_pago(c: m.CmConfig) -> list[dict]:
    """Solo las formas de pago habilitadas Y completas. Sin datos, la opción no aparece."""
    res = []
    if c.pago_tarjeta and stripe_estado()["conectado"]:
        res.append({"clave": "tarjeta", "nombre": "Tarjeta (pago en línea)", "instrucciones": "Pago seguro procesado por Stripe. Nomira no guarda datos de su tarjeta."})
    if c.spei_habilitado and c.spei_banco and c.spei_titular and c.spei_clabe and len(c.spei_clabe) == 18:
        res.append({"clave": "spei", "nombre": "Transferencia SPEI", "banco": c.spei_banco, "titular": c.spei_titular, "clabe": c.spei_clabe,
                    "instrucciones": c.spei_instrucciones or "Use el folio de la cotización como referencia."})
    if c.otro_habilitado and c.otro_nombre and c.otro_instrucciones:
        res.append({"clave": "otro", "nombre": c.otro_nombre, "instrucciones": c.otro_instrucciones})
    return res


def datos_nomira(c: m.CmConfig) -> dict:
    """Lo que se congela en la versión al enviarse (y se muestra en PDF, correo y enlace)."""
    return {"nombre_comercial": c.nombre_comercial or "Nomira", "razon_social": c.razon_social, "rfc": c.rfc, "domicilio": c.domicilio,
            "correo_ventas": c.correo_ventas, "telefono": c.telefono, "sitio_web": c.sitio_web, "condiciones": c.condiciones,
            "instrucciones_contratar": c.instrucciones_contratar, "notas_pie": c.notas_pie, "formas_pago": formas_pago(c),
            "aceptacion_en_linea": c.aceptacion_en_linea}


# ------------------------------------------------------------------ cálculo

def periodicidades_habilitadas(c: m.CmConfig) -> list[str]:
    return [p for p in (c.periodicidades or ["mensual"]) if p in PERIODICIDADES] or ["mensual"]


def _entero(v, campo: str, maximo: int) -> int:
    try:
        n = int(v or 0)
    except (TypeError, ValueError):
        raise HTTPException(422, f"{campo}: número inválido.")
    if n < 0 or n > maximo:
        raise HTTPException(422, f"{campo}: debe estar entre 0 y {maximo}.")
    return n


def calcular(db: Session, e: dict) -> dict:
    """Desglose completo a partir de la entrada del constructor. Lanza 422 si algo no cuadra."""
    c = config(db)
    paq = db.get(m.CmPaquete, int(e.get("paquete_id") or 0)) if e.get("paquete_id") else None
    if not paq:
        raise HTTPException(422, "Elija un paquete.")
    if paq.estado != "activo":
        raise HTTPException(422, f"El paquete «{paq.nombre}» no está activo.")
    precios = {p.clave: p for p in db.scalars(select(m.CmPrecio))}
    modulos = [x for x in dict.fromkeys(e.get("modulos") or []) if x]
    for x in modulos:
        if x not in MODULOS:
            raise HTTPException(422, "Módulo desconocido.")
    if not modulos:
        raise HTTPException(422, "Elija al menos un módulo.")
    incluidos = [x for x in dict.fromkeys(e.get("incluidos") or []) if x in modulos]
    if not e.get("incluidos"):
        incluidos = modulos[: paq.modulos_incluidos]
    if len(incluidos) > paq.modulos_incluidos:
        raise HTTPException(422, f"El paquete {paq.nombre} incluye {paq.modulos_incluidos} módulo(s); los demás se cobran como adicionales.")
    per = e.get("periodicidad") or "mensual"
    if per not in periodicidades_habilitadas(c):
        raise HTTPException(422, "Periodicidad no habilitada.")
    nombre_per, meses = PERIODICIDADES[per]
    usuarios_extra = _entero(e.get("usuarios_extra"), "Usuarios adicionales", 1000)
    bloques = _entero(e.get("bloques_extra"), "Bloques de almacenamiento", 200)

    lineas, mod_detalle = [], []
    mensual = paq.precio_mensual
    lineas.append({"concepto": f"Paquete {paq.nombre}", "detalle": f"{paq.modulos_incluidos} módulo(s), {paq.usuarios} usuarios internos, {paq.almacenamiento_gb} GB",
                   "cantidad": 1, "unitario": txt(paq.precio_mensual), "tipo": "recurrente"})
    for x in modulos:
        inc = x in incluidos
        p = precios.get(f"modulo:{x}")
        if not inc and (not p or not p.activo):
            raise HTTPException(422, f"{MODULOS[x]['nombre']} no tiene precio de módulo adicional activo.")
        mod_detalle.append({"clave": x, "nombre": MODULOS[x]["nombre"], "incluido": inc, "unitario": None if inc else txt(p.precio_mensual)})
        if not inc:
            mensual += p.precio_mensual
            lineas.append({"concepto": f"Módulo adicional: {MODULOS[x]['nombre']}", "detalle": None, "cantidad": 1,
                           "unitario": txt(p.precio_mensual), "tipo": "recurrente"})
    cursos_extra = _entero(e.get("cursos_extra"), "Cursos propios adicionales", 500)
    gb_bloque = 0
    for clave, n, etiqueta in (("usuario", usuarios_extra, "Usuarios internos adicionales"), ("almacenamiento", bloques, "Almacenamiento adicional"),
                               ("curso_adicional", cursos_extra, "Cursos propios adicionales (Academia)")):
        if not n:
            continue
        p = precios.get(clave)
        if not p or not p.activo:
            raise HTTPException(422, f"{etiqueta}: no hay precio activo.")
        if clave == "almacenamiento":
            gb_bloque = p.unidad_gb or 0
        mensual += p.precio_mensual * n
        lineas.append({"concepto": etiqueta, "detalle": f"Bloques de {gb_bloque} GB" if clave == "almacenamiento" else None,
                       "cantidad": n, "unitario": txt(p.precio_mensual), "tipo": "recurrente"})
    for ln in lineas:
        ln["meses"] = meses
        ln["importe"] = txt(Decimal(ln["unitario"]) * ln["cantidad"] * meses)

    unico = Decimal("0")
    cursos = []
    for cid in list(dict.fromkeys(e.get("cursos_nomira") or []))[:50]:
        cur = db.get(m.AcCurso, int(cid)) if str(cid).isdigit() else None
        if not cur or cur.organizacion_id is not None or cur.acceso != "pago" or cur.precio is None or cur.estado != "publicado":
            raise HTTPException(422, "Uno de los cursos de Academia elegidos ya no está a la venta.")
        cursos.append({"id": cur.id, "titulo": cur.titulo, "precio": txt(cur.precio)})
        unico += cur.precio
        lineas.append({"concepto": f"Curso de Nomira Academia: {cur.titulo}"[:200], "detalle": "Acceso para todo el despacho (pago único)",
                       "cantidad": 1, "unitario": txt(cur.precio), "meses": None, "importe": txt(cur.precio), "tipo": "unico"})
    servicios = []
    for s in e.get("servicios") or []:
        if not isinstance(s, dict) or s.get("clave") not in SERVICIOS:
            continue
        precio = dinero(s.get("precio") or 0)
        desc = (s.get("descripcion") or "").strip()[:300] or None
        servicios.append({"clave": s["clave"], "nombre": SERVICIOS[s["clave"]], "descripcion": desc, "precio": txt(precio)})
        unico += precio
        lineas.append({"concepto": SERVICIOS[s["clave"]], "detalle": desc or ("Sin costo" if not precio else None), "cantidad": 1,
                       "unitario": txt(precio), "meses": None, "importe": txt(precio), "tipo": "unico"})

    recurrente = (mensual * meses).quantize(CENT)
    subtotal = recurrente + unico
    d = e.get("descuento") or {}
    descuento, desc_info = Decimal("0"), None
    if d and dinero(d.get("valor") or 0) > 0:
        motivo = (d.get("motivo") or "").strip()
        if len(motivo) < 5:
            raise HTTPException(422, "Todo descuento requiere un motivo (mínimo 5 caracteres).")
        maximo = c.descuento_maximo_pct or Decimal("0")
        if d.get("tipo") == "monto":
            descuento = dinero(d.get("valor"))
            pct = (descuento / subtotal * 100) if subtotal else Decimal("100")
        else:
            pct = dinero(d.get("valor"))
            descuento = (subtotal * pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        if pct > maximo:
            raise HTTPException(422, f"El descuento supera el máximo autorizado ({maximo}%). Ajuste el máximo en Configuración si está aprobado.")
        desc_info = {"tipo": "monto" if d.get("tipo") == "monto" else "porcentaje", "valor": txt(dinero(d.get("valor"))),
                     "motivo": motivo[:300], "importe": txt(descuento)}
    base = subtotal - descuento
    iva_pct = paq.iva_pct if paq.iva_pct is not None else c.iva_pct
    iva = (base * iva_pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    total = base + iva
    total_gb = paq.almacenamiento_gb + bloques * gb_bloque
    asuntos = (total_gb * 1024) // c.mb_promedio_por_asunto if c.mb_promedio_por_asunto else None
    return {
        "paquete": {"id": paq.id, "clave": paq.clave, "nombre": paq.nombre, "precio_mensual": txt(paq.precio_mensual),
                    "modulos_incluidos": paq.modulos_incluidos, "usuarios": paq.usuarios, "almacenamiento_gb": paq.almacenamiento_gb},
        "periodicidad": {"clave": per, "nombre": nombre_per, "meses": meses},
        "modulos": mod_detalle,
        "usuarios": {"incluidos": paq.usuarios, "adicionales": usuarios_extra, "total": paq.usuarios + usuarios_extra},
        "almacenamiento": {"incluido_gb": paq.almacenamiento_gb, "bloques": bloques, "gb_bloque": gb_bloque, "total_gb": total_gb},
        "asuntos_estimados": asuntos,
        "servicios": servicios, "cursos": cursos, "cursos_extra": cursos_extra,
        "lineas": lineas,
        "mensual": txt(mensual), "recurrente": txt(recurrente), "unico": txt(unico),
        "subtotal": txt(subtotal), "descuento": desc_info, "base_iva": txt(base), "iva_pct": txt(iva_pct), "iva": txt(iva),
        "total": txt(total), "moneda": "MXN",
    }


def limpiar_entrada(e: dict) -> dict:
    """Solo los campos que entiende el constructor; los importes del navegador se descartan."""
    d = e.get("descuento") or None
    return {
        "paquete_id": e.get("paquete_id"), "modulos": list(e.get("modulos") or [])[:10], "incluidos": list(e.get("incluidos") or [])[:10],
        "usuarios_extra": e.get("usuarios_extra") or 0, "bloques_extra": e.get("bloques_extra") or 0,
        "cursos_nomira": [int(x) for x in (e.get("cursos_nomira") or []) if str(x).isdigit()][:50], "cursos_extra": e.get("cursos_extra") or 0,
        "periodicidad": e.get("periodicidad") or "mensual",
        "servicios": [{"clave": s.get("clave"), "descripcion": (s.get("descripcion") or "")[:300], "precio": str(s.get("precio") or 0)}
                      for s in (e.get("servicios") or [])[:4] if isinstance(s, dict)],
        "descuento": {"tipo": d.get("tipo"), "valor": str(d.get("valor") or 0), "motivo": (d.get("motivo") or "")[:300]} if d else None,
        "emision": e.get("emision"), "condiciones_pago": (e.get("condiciones_pago") or "")[:2000] or None,
        "fecha_limite_pago": e.get("fecha_limite_pago") or None,
        "terminos": (e.get("terminos") or "")[:6000] or None, "observaciones": (e.get("observaciones") or "")[:3000] or None,
        "mensaje": (e.get("mensaje") or "")[:4000] or None, "asunto": (e.get("asunto") or "")[:200] or None,
    }


# ------------------------------------------------------------------ cotizaciones

def folio_nuevo(db: Session) -> str:
    anio = ahora().year
    n = db.scalar(select(func.count(m.CmCotizacion.id)).where(m.CmCotizacion.folio.like(f"COT-{anio}-%"))) or 0
    while True:
        n += 1
        f = f"COT-{anio}-{n:04d}"
        if not db.scalar(select(m.CmCotizacion.id).where(m.CmCotizacion.folio == f)):
            return f


def version(db: Session, c: m.CmCotizacion, numero: int | None = None) -> m.CmVersion | None:
    return db.scalar(select(m.CmVersion).where(m.CmVersion.cotizacion_id == c.id, m.CmVersion.numero == (numero or c.version_actual)))


def version_enviada(db: Session, c: m.CmCotizacion) -> m.CmVersion | None:
    """La última versión que el cliente recibió (la que ve en su enlace)."""
    return db.scalar(select(m.CmVersion).where(m.CmVersion.cotizacion_id == c.id, m.CmVersion.enviada_en.is_not(None))
                     .order_by(m.CmVersion.numero.desc()))


def evento(db: Session, c: m.CmCotizacion, tipo: str, actor: str = "admin", admin: m.AdminPlataforma | None = None,
           detalle: dict | None = None, version_num: int | None = None) -> None:
    db.add(m.CmEvento(cotizacion_id=c.id, version=version_num or c.version_actual, tipo=tipo, actor=actor,
                      admin_id=admin.id if admin else None, detalle=detalle))


def aplicar_calculo(v: m.CmVersion, calc: dict) -> None:
    v.calculo = calc
    v.subtotal, v.iva, v.total = Decimal(calc["subtotal"]), Decimal(calc["iva"]), Decimal(calc["total"])
    v.descuento = Decimal(calc["descuento"]["importe"]) if calc.get("descuento") else Decimal("0")


def _resumen_cambio(a: dict, b: dict) -> list[str]:
    res = []
    if a["paquete"]["nombre"] != b["paquete"]["nombre"]:
        res.append(f"Paquete: {a['paquete']['nombre']} → {b['paquete']['nombre']}")
    ma = {x["nombre"] for x in a["modulos"]}
    mb = {x["nombre"] for x in b["modulos"]}
    if ma != mb:
        if mb - ma:
            res.append("Módulos agregados: " + ", ".join(sorted(mb - ma)))
        if ma - mb:
            res.append("Módulos quitados: " + ", ".join(sorted(ma - mb)))
    if a["usuarios"]["total"] != b["usuarios"]["total"]:
        res.append(f"Usuarios internos: {a['usuarios']['total']} → {b['usuarios']['total']}")
    if a["almacenamiento"]["total_gb"] != b["almacenamiento"]["total_gb"]:
        res.append(f"Almacenamiento: {a['almacenamiento']['total_gb']} GB → {b['almacenamiento']['total_gb']} GB")
    if a["periodicidad"]["clave"] != b["periodicidad"]["clave"]:
        res.append(f"Periodicidad: {a['periodicidad']['nombre']} → {b['periodicidad']['nombre']}")
    if (a.get("descuento") or {}).get("importe") != (b.get("descuento") or {}).get("importe"):
        res.append(f"Descuento: ${(a.get('descuento') or {}).get('importe') or '0.00'} → ${(b.get('descuento') or {}).get('importe') or '0.00'}")
    if [s["clave"] + s["precio"] for s in a.get("servicios", [])] != [s["clave"] + s["precio"] for s in b.get("servicios", [])]:
        res.append("Servicios adicionales modificados")
    if [x["id"] for x in a.get("cursos", [])] != [x["id"] for x in b.get("cursos", [])] or a.get("cursos_extra", 0) != b.get("cursos_extra", 0):
        res.append("Cursos de Academia modificados")
    if a["total"] != b["total"]:
        res.append(f"Total: ${a['total']} → ${b['total']}")
    return res


def cambios_entre(anterior: m.CmVersion, nueva: m.CmVersion, vence_antes: datetime | None, vence_ahora: datetime) -> list[str]:
    res = _resumen_cambio(anterior.calculo, nueva.calculo)
    ea, eb = anterior.entrada or {}, nueva.entrada or {}
    for k, t in (("condiciones_pago", "Condiciones de pago"), ("terminos", "Términos"), ("observaciones", "Observaciones"),
                 ("fecha_limite_pago", "Fecha límite de pago"), ("mensaje", "Mensaje de presentación")):
        if (ea.get(k) or None) != (eb.get(k) or None):
            res.append(f"{t} modificado")
    if vence_antes and vence_antes != vence_ahora:
        res.append("Vigencia modificada")
    return res or ["Sin cambios de contenido"]


def huella_version(c: m.CmCotizacion, v: m.CmVersion) -> str:
    contenido = {"folio": c.folio, "version": v.numero, "cliente": {"contacto": c.contacto, "despacho": c.despacho, "email": c.email},
                 "calculo": v.calculo, "entrada": {k: v.entrada.get(k) for k in ("condiciones_pago", "fecha_limite_pago", "terminos", "observaciones", "emision")},
                 "nomira": v.nomira, "vence_en": c.vence_en.isoformat()}
    return hashlib.sha256(json.dumps(contenido, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def actualizar_vencidas(db: Session) -> int:
    """Las cotizaciones enviadas o vistas cuya vigencia pasó quedan «vencidas» (con evento)."""
    n = 0
    for c in db.scalars(select(m.CmCotizacion).where(m.CmCotizacion.estado.in_(ABIERTAS_CLIENTE), m.CmCotizacion.vence_en < ahora())):
        c.estado = "vencida"
        evento(db, c, "vencida", actor="sistema")
        n += 1
    if n:
        db.flush()
    return n


# ------------------------------------------------------------------ enlace seguro del cliente

def huella_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generar_enlace(c: m.CmCotizacion) -> str:
    token = secrets.token_urlsafe(32)
    c.enlace_huella, c.enlace_cifrado = huella_token(token), cifrar(token)
    c.enlace_revocado_en = None
    c.enlace_vence_en = c.vence_en + timedelta(days=30)  # después de vencer, aún se muestra el aviso y el contacto
    return token


def url_enlace(c: m.CmCotizacion) -> str | None:
    if not c.enlace_cifrado or c.enlace_revocado_en:
        return None
    token = descifrar(c.enlace_cifrado)
    return f"{ajustes().url_publica.rstrip('/')}/propuesta#{token}" if token else None


def por_token(db: Session, token: str | None) -> m.CmCotizacion:
    if not token or len(token) < 20 or len(token) > 100:
        raise HTTPException(404, "Este enlace no existe.")
    c = db.scalar(select(m.CmCotizacion).where(m.CmCotizacion.enlace_huella == huella_token(token)))
    if not c:
        raise HTTPException(404, "Este enlace no existe.")
    return c


def fecha_iso(v: str | None, campo: str) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise HTTPException(422, f"{campo}: fecha inválida.")


def guardar_con_folio(db: Session, c: m.CmCotizacion) -> None:
    for _ in range(5):
        c.folio = folio_nuevo(db)
        try:
            with db.begin_nested():
                db.add(c)
                db.flush()
            return
        except IntegrityError:
            continue
    raise HTTPException(409, "No se pudo asignar un folio; intente de nuevo.")
