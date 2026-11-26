"""Avisos automáticos de Nomira Connect (fase 2).

Flujo: una acción del despacho (o el reloj) ENCOLA un aviso por canal con una llave única → el ciclo de fondo lo
ENVÍA en horario permitido, con reintentos. Reglas:
- Solo se avisa de seguimientos publicados, con avisos encendidos, de despachos con el módulo activo.
- Nunca se incluye la nota interna ni el texto de las notas: el aviso dice QUÉ cambió y manda al portal seguro.
- WhatsApp solo por la API oficial de Meta, con plantilla aprobada, número conectado y consentimiento del cliente.
  Si falta algo, el aviso queda «omitido» con el motivo (no se simula el envío).
- La actualización preventiva distingue la última revisión del despacho del último movimiento judicial
  y nunca afirma una revisión que no está registrada.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models as m
from .. import correo, envios, modulos, plantillas_correo
from ..afore import identificadores, mensajes as af_msj, whatsapp
from ..agenda.base import ZONA, hoy
from . import base as cb
from . import portal

log = logging.getLogger("nomira.connect")

HORA_INICIO, HORA_FIN = 8, 20  # hora de la Ciudad de México: no se envía de noche
DEMORA_ETAPA = timedelta(minutes=5)  # si el abogado mueve varias etapas seguidas, sale un solo aviso con la última
ESPERAS = [timedelta(minutes=15), timedelta(hours=1), timedelta(hours=4)]  # reintentos; después queda en error
DIAS_ENLACE = 14
PLANTILLA_WA = ("Hola, {{1}}. Tenemos una actualización sobre su asunto {{2}}: {{3}}. "
                "Consulte el seguimiento completo en su portal seguro: {{4}}")
TIPOS = {"etapa": "Cambio de etapa", "accion": "Necesitamos algo de usted", "movimiento": "Nuevo movimiento", "mensaje": "Mensaje del despacho",
         "audiencia": "Recordatorio de audiencia", "preventiva": "Actualización sin movimientos", "cierre": "Cierre del asunto"}


def config(db: Session, org: int) -> m.CnConfig:
    c = db.scalar(select(m.CnConfig).where(m.CnConfig.organizacion_id == org))
    if c is None:
        c = m.CnConfig(organizacion_id=org, avisos_activos=True, canal_correo=True, canal_whatsapp=False, preventiva_dias=15,
                       recordar_audiencias=True, wa_idioma="es_MX", wa_aprobada=False)
        db.add(c)
        db.flush()
    return c


def preferencia(db: Session, cliente: m.CrCliente, crear: bool = False) -> m.CnPreferencia | None:
    p = db.scalar(select(m.CnPreferencia).where(m.CnPreferencia.cliente_id == cliente.id))
    if p is None and crear:
        p = m.CnPreferencia(organizacion_id=cliente.organizacion_id, cliente_id=cliente.id, correo=True, whatsapp=False)
        db.add(p)
        db.flush()
    return p


def estado_whatsapp(db: Session, org: int) -> dict:
    """Qué le falta al despacho para avisar por WhatsApp (se muestra tal cual en Configuración)."""
    cfg, wa = config(db, org), db.scalar(select(m.AfConfig).where(m.AfConfig.organizacion_id == org))
    falta = []
    if not whatsapp.conectado(wa):
        falta.append("Conectar el número de WhatsApp Business del despacho (Meta).")
    if not cfg.wa_plantilla:
        falta.append("Escribir el nombre de la plantilla de aviso creada en Meta.")
    elif not cfg.wa_aprobada:
        falta.append("Confirmar que Meta aprobó la plantilla.")
    return {"conectado": whatsapp.conectado(wa), "numero": wa.wa_numero if wa else None, "listo": not falta, "falta": falta,
            "plantilla_sugerida": PLANTILLA_WA}


def en_horario(dt: datetime) -> datetime:
    """Mueve la hora de envío dentro de 8:00–20:00 (Ciudad de México)."""
    local = dt.astimezone(ZONA)
    if local.hour < HORA_INICIO:
        local = datetime.combine(local.date(), time(HORA_INICIO), ZONA)
    elif local.hour >= HORA_FIN:
        local = datetime.combine(local.date() + timedelta(days=1), time(HORA_INICIO), ZONA)
    return local


def encolar(db: Session, org: int, cliente_id: int | None, s: m.CnSeguimiento | None, tipo: str, resumen: str, datos: dict, llave: str,
            u: m.Usuario | None = None, demora: timedelta = timedelta(0), reemplazar: bool = False) -> list[m.CnAviso]:
    """Crea un aviso pendiente por cada canal que el despacho tiene encendido. No envía nada."""
    if not cliente_id:
        return []
    cfg = config(db, org)
    if not cfg.avisos_activos:
        return []
    if s is not None and (not s.visible_cliente or not s.avisos):
        return []
    canales = [c for c, on in (("correo", cfg.canal_correo), ("whatsapp", cfg.canal_whatsapp)) if on]
    cuando = en_horario(m.ahora() + demora)
    nuevos = []
    for canal in canales:
        k = f"{llave}:{canal}"[:120]
        if db.scalar(select(m.CnAviso.id).where(m.CnAviso.llave == k)):
            continue
        if reemplazar and s is not None:
            for viejo in db.scalars(select(m.CnAviso).where(m.CnAviso.seguimiento_id == s.id, m.CnAviso.canal == canal,
                                                           m.CnAviso.tipo.in_(("etapa", "accion")), m.CnAviso.estado == "pendiente",
                                                           m.CnAviso.intentos == 0)):
                viejo.estado, viejo.motivo = "omitido", "Lo reemplazó un aviso más reciente del mismo asunto."
        a = m.CnAviso(organizacion_id=org, cliente_id=cliente_id, seguimiento_id=s.id if s else None, tipo=tipo, canal=canal, llave=k,
                      datos=datos, resumen=resumen[:300], estado="pendiente", intentos=0, programado_en=cuando, creado_por_id=u.id if u else None)
        db.add(a)
        nuevos.append(a)
    db.flush()
    return nuevos


# ------------------------------------------------------------------ disparadores (los llama el router)

def por_etapa(db: Session, s: m.CnSeguimiento, a: m.AgAsunto, e: m.CnEtapa, anterior: str | None, evento_id: int, u: m.Usuario) -> None:
    if e.estado == "atencion":
        tipo, resumen = "accion", f"necesitamos algo de usted ({e.nombre})"
    elif e.estado == "actual":
        tipo, resumen = "etapa", f"su asunto avanzó a la etapa «{e.nombre}»"
    elif e.estado == "completada":
        tipo, resumen = "etapa", f"se completó la etapa «{e.nombre}»"
    elif e.estado in ("incidencia", "suspendida"):
        tipo, resumen = "etapa", "hay una novedad que su abogado le explica en el portal"
    else:
        return
    encolar(db, s.organizacion_id, a.cr_cliente_id, s, tipo, resumen,
            {"asunto": a.titulo, "anterior": anterior, "nueva": e.nombre, "estado": e.estado}, f"evento:{evento_id}", u,
            demora=DEMORA_ETAPA, reemplazar=True)


def por_movimiento(db, s, a, evento_id, u):
    encolar(db, s.organizacion_id, a.cr_cliente_id, s, "movimiento", "hay un nuevo movimiento en su expediente",
            {"asunto": a.titulo}, f"evento:{evento_id}", u)


def por_accion(db, s, a, evento_id, u):
    encolar(db, s.organizacion_id, a.cr_cliente_id, s, "accion", "necesitamos algo de usted", {"asunto": a.titulo}, f"evento:{evento_id}", u)


def por_cierre(db, s, a, evento_id, u):
    encolar(db, s.organizacion_id, a.cr_cliente_id, s, "cierre", "su asunto concluyó", {"asunto": a.titulo}, f"evento:{evento_id}", u)


def por_mensaje(db: Session, org: int, cliente_id: int, mensaje_id: int, u: m.Usuario) -> None:
    """Respuesta del despacho: avisa solo si el cliente tiene al menos un seguimiento publicado con avisos."""
    s = db.scalar(select(m.CnSeguimiento).join(m.AgAsunto, m.AgAsunto.id == m.CnSeguimiento.asunto_id)
                  .where(m.AgAsunto.cr_cliente_id == cliente_id, m.CnSeguimiento.organizacion_id == org,
                         m.CnSeguimiento.visible_cliente.is_(True), m.CnSeguimiento.avisos.is_(True)).limit(1))
    if s:
        encolar(db, org, cliente_id, None, "mensaje", "tiene un mensaje nuevo de su despacho", {"asunto": None}, f"msg:{mensaje_id}", u)


# ------------------------------------------------------------------ generación automática (reloj)

def generar(db: Session) -> dict:
    """Actualizaciones preventivas y recordatorios de audiencia. Idempotente (llaves por fecha/evento)."""
    n_prev = n_aud = 0
    ahora = m.ahora()
    cfgs: dict[int, m.CnConfig] = {}
    filas = db.execute(select(m.CnSeguimiento, m.AgAsunto).join(m.AgAsunto, m.AgAsunto.id == m.CnSeguimiento.asunto_id)
                       .where(m.CnSeguimiento.visible_cliente.is_(True), m.CnSeguimiento.avisos.is_(True),
                              m.CnSeguimiento.estado == "activo", m.AgAsunto.cr_cliente_id.is_not(None))).all()
    activos: dict[int, bool] = {}
    for s, a in filas:
        if s.organizacion_id not in activos:
            org = db.get(m.Organizacion, s.organizacion_id)
            activos[s.organizacion_id] = bool(org and org.estado == "activa" and "connect" in modulos.activos(db, s.organizacion_id))
        if not activos[s.organizacion_id]:
            continue
        cfg = cfgs.get(s.organizacion_id) or cfgs.setdefault(s.organizacion_id, config(db, s.organizacion_id))
        if not cfg.avisos_activos:
            continue
        dias = cfg.preventiva_dias if s.preventiva_dias is None else s.preventiva_dias
        if dias and dias > 0:
            refs = [x for x in (s.publico_actualizado_en, s.ultima_preventiva_en, s.creado_en) if x]
            ref = max(r if r.tzinfo else r.replace(tzinfo=ahora.tzinfo) for r in refs)
            if ahora - ref >= timedelta(days=dias):
                etapa = next((e for e in cb.etapas_de(db, s) if e.estado in ("actual", "atencion", "incidencia", "suspendida")), None)
                datos = {"asunto": a.titulo, "etapa": etapa.nombre if etapa else None, "dias": dias,
                         "ultimo_movimiento": s.ultimo_movimiento_fecha.isoformat() if s.ultimo_movimiento_fecha else None,
                         "ultima_revision": s.ultima_revision_en.isoformat() if s.ultima_revision_en else None,
                         "accion": bool(s.accion_cliente) or bool(etapa and etapa.estado == "atencion")}
                resumen = f"sin movimientos nuevos; sigue en la etapa «{etapa.nombre}»" if etapa else "sin movimientos nuevos"
                if encolar(db, s.organizacion_id, a.cr_cliente_id, s, "preventiva", resumen, datos, f"prev:{s.id}:{hoy().isoformat()}"):
                    n_prev += 1
                s.ultima_preventiva_en = ahora  # aunque no haya canal: evita revisarlo en cada vuelta
        if cfg.recordar_audiencias and s.mostrar_audiencias:
            for ev in db.scalars(select(m.AgEvento).where(m.AgEvento.asunto_id == a.id, m.AgEvento.tipo == "audiencia", m.AgEvento.estado == "pendiente",
                                                         m.AgEvento.fecha >= hoy() + timedelta(days=1), m.AgEvento.fecha <= hoy() + timedelta(days=2))):
                fecha = ev.fecha.strftime("%d/%m/%Y") + (f" a las {ev.hora} h" if ev.hora else "")
                if encolar(db, s.organizacion_id, a.cr_cliente_id, s, "audiencia", f"recordatorio de audiencia el {fecha}",
                           {"asunto": a.titulo, "fecha": ev.fecha.isoformat(), "hora": ev.hora}, f"aud:{ev.id}:{ev.fecha.isoformat()}"):
                    n_aud += 1
    db.commit()
    return {"preventivas": n_prev, "audiencias": n_aud}


# ------------------------------------------------------------------ envío

def _omitir(av: m.CnAviso, motivo: str) -> str:
    av.estado, av.motivo = "omitido", motivo[:300]
    return "omitido"


def _lineas(av: m.CnAviso) -> tuple[str, list[str], bool]:
    """Título, párrafos y si el cliente debe hacer algo. Solo datos públicos."""
    d = av.datos or {}
    asunto = d.get("asunto")
    if av.tipo == "etapa":
        if d.get("estado") in ("incidencia", "suspendida"):
            return "Hay una novedad en su asunto", ["Su abogado registró una novedad en su asunto y se la explica en su portal."], False
        p = []
        if d.get("anterior") and d.get("estado") == "actual":
            p.append(f"Etapa anterior: {d['anterior']}.")
        p.append(f"Nueva etapa: {d.get('nueva')}." if d.get("estado") == "actual" else f"Etapa completada: {d.get('nueva')}.")
        p.append("Por el momento no necesita realizar ninguna acción adicional.")
        return "Tenemos una actualización sobre su asunto", p, False
    if av.tipo == "accion":
        return "Necesitamos algo de usted", ["Su abogado le pidió algo para continuar con su asunto. Entre a su portal para ver qué es."], True
    if av.tipo == "movimiento":
        return "Hay un nuevo movimiento en su expediente", ["Su abogado registró un nuevo movimiento. El detalle está en su portal."], False
    if av.tipo == "mensaje":
        return "Tiene un mensaje nuevo", ["Su despacho le respondió. Lea el mensaje en su portal."], False
    if av.tipo == "cierre":
        return "Su asunto concluyó", ["Su abogado marcó su asunto como concluido. En su portal puede ver el resumen."], False
    if av.tipo == "audiencia":
        f = datetime.fromisoformat(d["fecha"]).strftime("%d/%m/%Y")
        return "Recordatorio de audiencia", [f"Su asunto tiene una audiencia el {f}" + (f" a las {d['hora']} h." if d.get("hora") else "."),
                                            "Su abogado le confirmará si necesita asistir."], False
    if av.tipo == "preventiva":
        p = [f"Actualmente su expediente continúa en la etapa: {d['etapa']}." if d.get("etapa") else "Su asunto sigue en trámite.",
             "Desde nuestra última actualización no tenemos registrados nuevos movimientos."]
        if d.get("ultimo_movimiento"):
            p.append(f"Último movimiento judicial confirmado: {datetime.fromisoformat(d['ultimo_movimiento']).strftime('%d/%m/%Y')}.")
        if d.get("ultima_revision"):  # solo si existe la revisión registrada
            p.append(f"Su despacho registró la última revisión de su expediente el {datetime.fromisoformat(d['ultima_revision']).astimezone(ZONA).strftime('%d/%m/%Y')}.")
        p.append("Recuerde revisar en su portal lo que necesitamos de usted." if d.get("accion")
                 else "No necesita realizar ninguna acción adicional. Le avisaremos cuando exista una novedad.")
        return "Le compartimos una actualización sobre su asunto", p, bool(d.get("accion"))
    return "Actualización de su asunto", [], False


def enviar_uno(db: Session, av: m.CnAviso) -> str:
    c = db.get(m.CrCliente, av.cliente_id)
    org = db.get(m.Organizacion, av.organizacion_id)
    if not c or not org or org.estado != "activa" or c.organizacion_id != av.organizacion_id:
        return _omitir(av, "El cliente o el despacho ya no están activos.")
    if "connect" not in modulos.activos(db, av.organizacion_id):
        return _omitir(av, "El módulo Nomira Connect está apagado.")
    cfg = config(db, av.organizacion_id)
    if not cfg.avisos_activos:
        return _omitir(av, "Los avisos automáticos están apagados.")
    if av.seguimiento_id:
        s = db.get(m.CnSeguimiento, av.seguimiento_id)
        if not s or not s.visible_cliente or not s.avisos:
            return _omitir(av, "El seguimiento ya no está publicado o sus avisos se apagaron.")
    pref = preferencia(db, c)
    nombre = c.nombre.split()[0] if c.tipo == "fisica" else c.nombre
    titulo, parrafos, accion = _lineas(av)
    asunto = (av.datos or {}).get("asunto")
    if av.canal == "correo":
        if not cfg.canal_correo:
            return _omitir(av, "El despacho apagó los avisos por correo.")
        if not c.email:
            return _omitir(av, "El cliente no tiene correo.")
        if pref and not pref.correo:
            return _omitir(av, "El cliente pidió no recibir avisos por correo.")
        if not correo.configurado():
            return _omitir(av, "El envío de correos no está configurado.")
        _, _, url = portal.nuevo_acceso(db, c, None, DIAS_ENLACE, origen="aviso")
        a_html, html, texto = plantillas_correo.connect_aviso(org.nombre, nombre, asunto, titulo, parrafos, url, accion)
        r = envios.registrar_y_enviar(db, f"cn_{av.tipo}", [c.email], a_html, html, texto, organizacion_id=av.organizacion_id,
                                      llave=f"cn_aviso:{av.id}:{av.intentos}")
        if r is None:
            return "pendiente"  # otro proceso lo está enviando
        if r.estado != "enviado":
            raise RuntimeError(r.error or "El proveedor de correo no aceptó el envío.")
        av.referencia = f"correo:{r.id}"
    else:
        if not cfg.canal_whatsapp:
            return _omitir(av, "El despacho apagó los avisos por WhatsApp.")
        ew = estado_whatsapp(db, av.organizacion_id)
        if not ew["listo"]:
            return _omitir(av, "WhatsApp pendiente de configurar: " + " ".join(ew["falta"]))
        if not pref or not pref.whatsapp:
            return _omitir(av, "El cliente no ha aceptado recibir avisos por WhatsApp.")
        tel = identificadores.telefono(c.telefono)
        if not tel:
            return _omitir(av, "El cliente no tiene un teléfono válido.")
        _, _, url = portal.nuevo_acceso(db, c, None, DIAS_ENLACE, origen="aviso")
        afc = af_msj.config(db, av.organizacion_id)
        av.referencia = "wa:" + whatsapp.enviar_plantilla(afc, tel, cfg.wa_plantilla, cfg.wa_idioma or "es_MX",
                                                          [nombre[:60], (asunto or "su asunto")[:120], av.resumen[:200], url])
    av.estado, av.enviado_en, av.motivo = "enviado", m.ahora(), None
    return "enviado"


def enviar_pendientes(db: Session, limite: int = 50) -> dict:
    cuenta = {"enviado": 0, "omitido": 0, "error": 0, "reintento": 0}
    ids = list(db.scalars(select(m.CnAviso.id).where(m.CnAviso.estado == "pendiente", m.CnAviso.programado_en <= m.ahora())
                          .order_by(m.CnAviso.programado_en, m.CnAviso.id).limit(limite)))
    for aid in ids:
        av = db.scalar(select(m.CnAviso).where(m.CnAviso.id == aid, m.CnAviso.estado == "pendiente").with_for_update(skip_locked=True))
        if av is None:
            continue
        try:
            r = enviar_uno(db, av)
            if r in cuenta:
                cuenta[r] += 1
        except (whatsapp.WhatsAppError, RuntimeError, IntegrityError) as e:
            db.rollback()
            av = db.get(m.CnAviso, aid)
            av.intentos += 1
            av.motivo = str(e)[:300]
            if av.intentos > len(ESPERAS):
                av.estado = "error"
                cuenta["error"] += 1
            else:
                av.programado_en = en_horario(m.ahora() + ESPERAS[av.intentos - 1])
                cuenta["reintento"] += 1
            log.warning("Aviso de Connect %s no enviado (intento %s): %s", aid, av.intentos, type(e).__name__)
        db.commit()
    return cuenta


def ciclo(db: Session) -> dict:
    """Una vuelta del proceso de fondo: un solo proceso a la vez (candado de la base)."""
    if not db.scalar(text("SELECT pg_try_advisory_lock(7310042)")):
        return {}
    try:
        g = generar(db)
        e = enviar_pendientes(db)
        return {**g, **e}
    finally:
        db.execute(text("SELECT pg_advisory_unlock(7310042)"))
        db.commit()
