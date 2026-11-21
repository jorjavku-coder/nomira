"""Envío de avisos escalonados y del resumen diario de la agenda.

- Cada aviso se registra una sola vez (tabla ag_avisos con llave única): repetir la revisión es seguro
  aunque haya varios procesos o el servicio haya estado dormido.
- El aviso se ve en Nomira aunque el correo no esté configurado; el correo sale solo si lo está y la
  persona no lo desactivó.
- Los correos llevan lo mínimo para actuar (asunto, tipo y fecha) y un enlace a Nomira.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models as m
from .. import correo, envios, modulos
from ..plantillas_correo import _base, _boton, _url, escape, fecha_larga
from . import base

log = logging.getLogger("nomira.agenda")
HORA_ESCALAR = 12  # el día del vencimiento, si sigue pendiente a mediodía, se avisa a quien supervisa
NIVEL_TXT = {"anticipado": "Próximo a vencer", "hoy": "Vence hoy", "escalado": "Vence hoy y sigue pendiente", "vencido": "Venció sin marcarse como cumplido"}


def _pref(db: Session, uid: int) -> m.AgPreferencia | None:
    return db.scalar(select(m.AgPreferencia).where(m.AgPreferencia.usuario_id == uid))


def _activos(db: Session, org_id: int, ids) -> dict[int, m.Usuario]:
    if not ids:
        return {}
    return {u.id: u for u in db.scalars(select(m.Usuario).where(m.Usuario.id.in_(list(ids)), m.Usuario.organizacion_id == org_id,
                                                               m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None)))}


def _linea(db: Session, e: m.AgEvento, nivel: str | None = None) -> tuple[str, str]:
    a = db.get(m.AgAsunto, e.asunto_id) if e.asunto_id else None
    asunto = f"{a.titulo}{f' · {a.numero}' if a.numero else ''}" if a else "Sin asunto"
    cuando = fecha_larga(e.fecha) + (f", {e.hora} h" if e.hora else "")
    extra = " · cálculo sin validar" if base.pendientes_de_validar(e) and e.calculo else ""
    etiqueta = f"{NIVEL_TXT[nivel]} · " if nivel else ""
    html = (f'<li style="margin:0 0 10px"><b>{escape(base.TIPOS_EVENTO[e.tipo])}: {escape(e.titulo)}</b><br>'
            f'<span style="color:#64748b;font-size:14px">{escape(etiqueta)}{escape(cuando)} · {escape(asunto)}{escape(extra)}</span></li>')
    return html, f"- {base.TIPOS_EVENTO[e.tipo]}: {e.titulo} — {etiqueta}{cuando} — {asunto}{extra}"


def correo_avisos(db: Session, u: m.Usuario, items: list[tuple[m.AgEvento, str]]) -> tuple[str, str, str]:
    graves = sum(1 for _, n in items if n in ("vencido", "escalado"))
    asunto = (f"⚠️ {graves} pendiente(s) vencido(s) o por vencer hoy" if graves else f"Agenda: {len(items)} aviso(s) de plazos y audiencias")
    filas = [_linea(db, e, n) for e, n in items]
    html = _base(asunto, f"""<h1 style="margin:0 0 12px;font-size:22px;color:#123048">Hola, {escape(u.nombre.split()[0])}</h1>
<p>Estos pendientes de la agenda de su despacho requieren atención:</p><ul style="padding-left:18px">{''.join(h for h, _ in filas)}</ul>
{_boton("Abrir mi agenda", _url("/agenda"))}
<p style="font-size:13px;color:#64748b">Las fechas calculadas con Nomira son un apoyo: confírmelas con la ley aplicable y el calendario oficial del tribunal. Puede ajustar estos avisos en Agenda → Mis avisos.</p>""")
    texto = f"Hola, {u.nombre}\n\nPendientes de la agenda:\n" + "\n".join(t for _, t in filas) + f"\n\nAbrir mi agenda: {_url('/agenda')}\n"
    return asunto, html, texto


def correo_resumen(db: Session, u: m.Usuario, grupos: dict[str, list[m.AgEvento]], ref) -> tuple[str, str, str]:
    titulos = {"vencido": "Vencidos sin cumplir", "hoy": "Hoy", "proximo": "Próximos 3 días"}
    n = sum(len(v) for v in grupos.values())
    asunto = f"Su agenda del {fecha_larga(ref)}: {n} pendiente(s)"
    bloques, texto = [], [f"Hola, {u.nombre}. Su agenda de hoy:"]
    for k in ("vencido", "hoy", "proximo"):
        if grupos.get(k):
            filas = [_linea(db, e) for e in grupos[k]]
            bloques.append(f'<h2 style="margin:18px 0 6px;font-size:16px;color:#123048">{titulos[k]} ({len(filas)})</h2><ul style="padding-left:18px">{"".join(h for h, _ in filas)}</ul>')
            texto += [f"\n{titulos[k]}:"] + [t for _, t in filas]
    html = _base(asunto, f"""<h1 style="margin:0 0 12px;font-size:22px;color:#123048">Buenos días, {escape(u.nombre.split()[0])}</h1>
{''.join(bloques)}{_boton("Ver mi agenda de hoy", _url("/agenda"))}
<p style="font-size:13px;color:#64748b">Puede dejar de recibir este resumen en Agenda → Mis avisos.</p>""")
    return asunto, html, "\n".join(texto) + f"\n\n{_url('/agenda')}\n"


def _registrar(db: Session, e: m.AgEvento, uid: int, aviso: dict) -> bool:
    try:
        with db.begin_nested():
            db.add(m.AgAviso(organizacion_id=e.organizacion_id, evento_id=e.id, usuario_id=uid, clave=aviso["clave"], nivel=aviso["nivel"],
                             fecha_evento=e.fecha))
        return True
    except IntegrityError:
        return False


def ejecutar(db: Session, ahora=None) -> dict:
    ahora = ahora or base.ahora_local()
    ref = ahora.date()
    enviar = correo.configurado()
    total = {"avisos": 0, "correos": 0, "resumenes": 0}
    orgs = [o.id for o in db.scalars(select(m.Organizacion).where(m.Organizacion.estado == "activa"))]
    for oid in orgs:
        if "agenda" not in modulos.activos(db, oid):
            continue
        conf = base.config(db, oid)
        eventos = list(db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == oid, m.AgEvento.estado == "pendiente",
                                                           m.AgEvento.fecha >= ref - timedelta(days=30), m.AgEvento.fecha <= ref + timedelta(days=90))))
        sups = [u.id for u in base.supervisores(db, oid)]
        por_usuario: dict[int, list] = defaultdict(list)
        for e in eventos:
            for a in base.alertas_vigentes(db, e, ref):
                if a["nivel"] == "escalado" and ahora.hour < HORA_ESCALAR:
                    continue
                equipo = base.involucrados(e)
                dest = equipo if a["a"] == "equipo" else sups if a["a"] == "supervision" else list(dict.fromkeys(equipo + sups))
                for uid in dest:
                    if _registrar(db, e, uid, a):
                        total["avisos"] += 1
                        por_usuario[uid].append((e, a["nivel"]))
        db.commit()
        usuarios = _activos(db, oid, por_usuario.keys())
        for uid, items in por_usuario.items():
            u = usuarios.get(uid)
            p = _pref(db, uid)
            if not u or not enviar or (p and not p.alertas_correo):
                continue
            asunto, html, texto = correo_avisos(db, u, items)
            r = envios.registrar_y_enviar(db, "agenda_aviso", [u.email], asunto, html, texto, organizacion_id=oid)
            if r and r.estado == "enviado":
                total["correos"] += 1
                db.query(m.AgAviso).filter(m.AgAviso.usuario_id == uid, m.AgAviso.evento_id.in_([e.id for e, _ in items]),
                                           m.AgAviso.fecha_evento.in_([e.fecha for e, _ in items])).update({"correo": True}, synchronize_session=False)
                db.commit()
        if enviar and conf.resumen_diario and ahora.hour >= conf.hora_resumen:
            total["resumenes"] += _resumenes(db, oid, ref)
    return total


def _resumenes(db: Session, oid: int, ref) -> int:
    eventos = list(db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == oid, m.AgEvento.estado == "pendiente",
                                                       m.AgEvento.fecha >= ref - timedelta(days=30), m.AgEvento.fecha <= ref + timedelta(days=3))
                              .order_by(m.AgEvento.fecha, m.AgEvento.hora)))
    sups = {u.id for u in base.supervisores(db, oid)}
    n = 0
    for u in db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == oid, m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None))):
        p = _pref(db, u.id)
        if p and not p.resumen_diario:
            continue
        grupos: dict[str, list] = defaultdict(list)
        for e in eventos:
            s = base.situacion(e, ref)
            mio = u.id in base.involucrados(e) or (u.id in sups and (s == "vencido" or not e.responsable_id))
            if mio:
                grupos["proximo" if s in ("proximo", "futuro") else s].append(e)
        if not grupos:
            continue
        asunto, html, texto = correo_resumen(db, u, grupos, ref)
        r = envios.registrar_y_enviar(db, "agenda_resumen", [u.email], asunto, html, texto, organizacion_id=oid, llave=f"agres:{u.id}:{ref.isoformat()}")
        if r and r.estado == "enviado":
            n += 1
    return n
