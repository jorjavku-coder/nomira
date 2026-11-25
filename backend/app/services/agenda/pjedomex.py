"""Poder Judicial del Estado de México (PJEdomex): calendario oficial y accesos a sus sistemas.

Calendario: el PJEdomex publica su calendario oficial como datos abiertos (el mismo archivo que usa la página
www.pjedomex.gob.mx/calendario.html): /assets/data/calendario-base-AAAA.json, con «dias_especiales» (inhábil o festivo)
y «periodos» (vacaciones). Nomira lo lee una vez al día, sin contraseñas ni CAPTCHA, y actualiza los calendarios que
el despacho conectó. Solo cuentan como inhábiles los días marcados «inhabil» y los periodos de vacaciones: un día
«festivo» (p. ej. Día de las Madres) no suspende labores salvo que también venga como inhábil.

Los días que el despacho capturó a mano nunca se tocan. Si el tribunal quita un día del archivo, Nomira lo quita
también (solo los que trajo del archivo).

Accesos: los sistemas con usuario y contraseña (Tribunal Electrónico, consulta de acuerdos con FEJEM, correo
institucional) se abren en la página oficial; Nomira NO guarda contraseñas ni entra en nombre del abogado.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m

log = logging.getLogger("nomira.pjedomex")
CLAVE = "pjedomex"
NOMBRE = "Poder Judicial del Estado de México (calendario oficial)"
FUENTE = "https://www.pjedomex.gob.mx/calendario.html"
URL_DATOS = "https://www.pjedomex.gob.mx/assets/data/calendario-base-{anio}.json"
CADA = timedelta(hours=20)  # una vez al día basta: el calendario cambia pocas veces al año

ACCESOS = [  # sistemas oficiales que el abogado abre con SU cuenta (verificados en nov. 2026)
    {"clave": "tribunal", "nombre": "Tribunal Electrónico", "url": "https://tribunalelectronico.pjedomex.gob.mx/",
     "para": "Consultar el expediente electrónico, presentar demandas y promociones.", "cuenta": "Usuario y contraseña del abogado"},
    {"clave": "acuerdos", "nombre": "Consulta de acuerdos", "url": "https://consultaboletin.pjedomex.gob.mx/consultaEspecifica",
     "para": "Buscar los acuerdos de un expediente por juzgado, número y año.", "cuenta": "Firma electrónica FEJEM"},
    {"clave": "boletin", "nombre": "Boletín Judicial", "url": "https://consultaboletin.pjedomex.gob.mx/",
     "para": "Revisar el boletín del día por juzgado.", "cuenta": "Público"},
    {"clave": "correo", "nombre": "Correo institucional (notificaciones)", "url": "https://mail.pjedomex.gob.mx/static/login/",
     "para": "Ver las notificaciones electrónicas que envía el juzgado.", "cuenta": "Correo y contraseña del abogado"},
    {"clave": "fejem", "nombre": "Firmar documentos (FEJEM)", "url": "https://gestion.pjedomex.gob.mx/gestion2/gestion3/vistas/gestion/firmaelectronica/frmFirmaElectronicaExterno.php?cveSistema=72",
     "para": "Firmar electrónicamente promociones y documentos.", "cuenta": "Firma electrónica FEJEM"},
    {"clave": "pagos", "nombre": "Fondo Auxiliar (pagos)", "url": "https://fondospropios.pjedomex.gob.mx/vista/pagotarjeta/frmPagosTarjeta.php",
     "para": "Pagar depósitos y servicios del Poder Judicial.", "cuenta": "Pago con tarjeta en el sitio oficial"},
    {"clave": "calendario", "nombre": "Calendario oficial", "url": FUENTE, "para": "Días inhábiles y periodos vacacionales.", "cuenta": "Público"},
]


class SinDatos(Exception):
    pass


def descargar(anio: int) -> dict | None:
    """El archivo del año, o None si el tribunal todavía no lo publica (404). Lanza SinDatos si no responde bien."""
    try:
        r = httpx.get(URL_DATOS.format(anio=anio), timeout=20, headers={"User-Agent": "Nomira (agenda juridica; calendario oficial)"},
                      follow_redirects=True)
    except httpx.HTTPError as e:
        raise SinDatos(f"No hubo conexión con el PJEdomex ({type(e).__name__}).") from e
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise SinDatos(f"El PJEdomex respondió {r.status_code}.")
    try:
        datos = r.json()
    except ValueError as e:
        raise SinDatos("El PJEdomex no devolvió el calendario en el formato esperado.") from e
    if not isinstance(datos, dict) or not isinstance(datos.get("dias_especiales", []), list):
        raise SinDatos("El calendario del PJEdomex cambió de formato.")
    return datos


def _fecha(x) -> date | None:
    try:
        return date.fromisoformat(str(x)[:10])
    except ValueError:
        return None


def dias_inhabiles(datos: dict) -> dict[date, str]:
    """Fecha → motivo. Inhábiles sueltos + cada día de los periodos de vacaciones. Ignora «festivo» solo."""
    res: dict[date, str] = {}
    for d in datos.get("dias_especiales") or []:
        f = _fecha(d.get("fecha"))
        if f and (d.get("tipo") or "").lower() == "inhabil":
            res.setdefault(f, (d.get("titulo") or "Día inhábil")[:200])
    for p in datos.get("periodos") or []:
        ini, fin = _fecha(p.get("inicio")), _fecha(p.get("fin"))
        if not ini or not fin or fin < ini or (fin - ini).days > 62:
            continue
        motivo = (p.get("titulo") or "Periodo vacacional")[:200]
        f = ini
        while f <= fin:
            res[f] = motivo  # el periodo manda sobre «suspensión de labores» suelta (mismo efecto)
            f += timedelta(days=1)
    return res


def aplicar(db: Session, cal: m.AgCalendario, dias: dict[date, str], anios: list[int]) -> dict:
    """Pone en el calendario los días oficiales de esos años. No toca los capturados por el despacho."""
    desde, hasta = date(min(anios), 1, 1), date(max(anios), 12, 31)
    existentes = {x.fecha: x for x in db.scalars(select(m.AgDia).where(m.AgDia.calendario_id == cal.id, m.AgDia.fecha >= desde,
                                                                       m.AgDia.fecha <= hasta))}
    nuevos = cambiados = quitados = 0
    for f, motivo in dias.items():
        if not desde <= f <= hasta:
            continue
        x = existentes.get(f)
        if x is None:
            db.add(m.AgDia(calendario_id=cal.id, fecha=f, tipo="inhabil", motivo=motivo, origen=CLAVE))
            nuevos += 1
        elif x.origen == CLAVE and (x.motivo != motivo or x.tipo != "inhabil"):
            x.motivo, x.tipo = motivo, "inhabil"
            cambiados += 1
    for f, x in existentes.items():
        if x.origen == CLAVE and f not in dias and f.year in anios:
            db.delete(x)  # el tribunal lo quitó de su calendario
            quitados += 1
    cal.sincronizado_en, cal.sincronizacion_error = m.ahora(), None
    if nuevos or cambiados or quitados:
        cal.actualizado_en = m.ahora()
    return {"nuevos": nuevos, "cambiados": cambiados, "quitados": quitados}


def _anios(hoy: date | None = None) -> list[int]:
    hoy = hoy or date.today()
    return [hoy.year, hoy.year + 1]


def bajar_anios(anios: list[int]) -> tuple[dict[date, str], list[int]]:
    """Días de los años publicados. Devuelve (días, años que sí existían)."""
    dias: dict[date, str] = {}
    publicados = []
    for a in anios:
        datos = descargar(a)
        if datos is None:
            continue
        publicados.append(a)
        dias.update(dias_inhabiles(datos))
    return dias, publicados


def conectar(db: Session, org_id: int) -> tuple[m.AgCalendario, dict]:
    """Crea (o reutiliza) el calendario oficial del despacho y lo llena. No hace commit."""
    cal = db.scalar(select(m.AgCalendario).where(m.AgCalendario.organizacion_id == org_id, m.AgCalendario.oficial == CLAVE))
    if cal is None:
        cal = m.AgCalendario(organizacion_id=org_id, nombre=NOMBRE, jurisdiccion="estatal", entidad="Estado de México",
                             descripcion="Se actualiza solo una vez al día con el calendario oficial que publica el PJEdomex.",
                             fuente=FUENTE, dias_semana_inhabiles=[5, 6], incluir_descanso_lft=False, oficial=CLAVE)
        db.add(cal)
        db.flush()
    cal.activo = True
    try:
        dias, publicados = bajar_anios(_anios())
    except SinDatos as e:
        cal.sincronizacion_error = str(e)[:300]
        return cal, {"error": str(e)}
    if not publicados:
        cal.sincronizacion_error = "El PJEdomex todavía no publica el calendario de este año."
        return cal, {"error": cal.sincronizacion_error}
    r = aplicar(db, cal, dias, publicados)
    return cal, {**r, "anios": publicados}


def sincronizar_si_toca(db: Session, ahora: datetime | None = None) -> dict:
    """Para la revisión periódica: una vez al día actualiza todos los calendarios conectados. Hace commit."""
    ahora = ahora or m.ahora()
    cals = list(db.scalars(select(m.AgCalendario).where(m.AgCalendario.oficial == CLAVE, m.AgCalendario.activo.is_(True))))
    pendientes = [c for c in cals if not c.sincronizado_en or ahora - c.sincronizado_en >= CADA]
    if not pendientes:
        return {"calendarios": 0}
    try:
        dias, publicados = bajar_anios(_anios(ahora.date()))
    except SinDatos as e:
        for c in pendientes:
            c.sincronizacion_error = str(e)[:300]
        db.commit()
        log.warning("Calendario PJEdomex: %s", e)
        return {"calendarios": 0, "error": str(e)}
    total = {"nuevos": 0, "cambiados": 0, "quitados": 0}
    for c in pendientes:
        if publicados:
            for k, v in aplicar(db, c, dias, publicados).items():
                total[k] += v
        else:
            c.sincronizado_en = ahora
    db.commit()
    return {"calendarios": len(pendientes), **total}
