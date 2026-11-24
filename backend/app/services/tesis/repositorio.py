"""Sincronización con el Repositorio de datos abiertos de la SCJN (API JSON).

- Base: ``TESIS_REPOSITORIO_URL`` (…/repositorio-scjn/api/v1). Rutas: ``tesis/count``, ``tesis/ids?page=N&size=1000``, ``tesis/{id}``.
- Cortesía: una solicitud por segundo como máximo, identificándose como Nomira, por tandas.
- Si la SCJN responde con una verificación anti-robots (Incapsula/Imperva), HTML en lugar de JSON, 403 o 429, la
  sincronización SE DETIENE y lo informa en el panel. Nomira no intenta saltarse esa protección: en ese caso se cargan
  las tesis con los archivos oficiales desde el panel.
- Se descargan primero las más recientes y solo se guardan las épocas desde ``TESIS_EPOCA_MINIMA`` (por defecto, Décima).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ...config import ajustes
from . import base as tb

log = logging.getLogger("nomira.tesis")
AGENTE = "Nomira/1.0 (biblioteca de tesis para despachos; +https://nomirasoft.com)"
EPOCAS = {"primera": 1, "segunda": 2, "tercera": 3, "cuarta": 4, "quinta": 5, "sexta": 6, "séptima": 7, "septima": 7, "octava": 8, "novena": 9,
          "décima": 10, "decima": 10, "undécima": 11, "undecima": 11, "duodécima": 12, "duodecima": 12}
SEGUIDAS_VIEJAS = 400  # tras tantas tesis seguidas de épocas que no se guardan, se da por terminada la carga inicial


class Bloqueada(Exception):
    pass


def numero_epoca(epoca: str | None) -> int | None:
    t = (epoca or "").strip().lower()
    for nombre, n in EPOCAS.items():
        if t.startswith(nombre):
            return n
    return None


def estado(db: Session) -> m.JSincronizacion:
    e = db.scalar(select(m.JSincronizacion).limit(1))
    if e is None:
        e = m.JSincronizacion(estado="pendiente" if ajustes().tesis_sincronizar else "apagada")
        db.add(e)
        db.flush()
    return e


def _pedir(cliente: httpx.Client, ruta: str, **params):
    try:
        r = cliente.get(f"{ajustes().tesis_repositorio_url.rstrip('/')}/{ruta}", params=params or None, timeout=30)
    except httpx.HTTPError as e:
        raise ConnectionError(type(e).__name__)
    tipo = r.headers.get("content-type", "")
    if r.status_code in (403, 429) or "incapsula" in r.text[:3000].lower() or (r.status_code == 200 and "json" not in tipo):
        raise Bloqueada(f"La SCJN respondió con una verificación o bloqueo (HTTP {r.status_code}).")
    if r.status_code == 404:
        return None
    if r.status_code >= 300:
        raise ConnectionError(f"HTTP {r.status_code}")
    return r.json()


def _ids(j) -> list[int]:
    if isinstance(j, dict):
        for k in ("content", "ids", "data", "items", "resultados"):
            if isinstance(j.get(k), list):
                j = j[k]
                break
    salida = []
    for x in j if isinstance(j, list) else []:
        v = x.get("id") or x.get("registroDigital") if isinstance(x, dict) else x
        try:
            salida.append(int(v))
        except (TypeError, ValueError):
            continue
    return salida


def correr(db: Session, maximo: int | None = None, cliente: httpx.Client | None = None, pausa: float = 1.0) -> m.JSincronizacion:
    """Una tanda: lista de registros (si hace falta) y descarga de hasta ``maximo`` tesis. Se puede llamar seguido."""
    e = estado(db)
    ahora = datetime.now(timezone.utc)
    if not ajustes().tesis_sincronizar:
        e.estado, e.mensaje = "apagada", "La sincronización automática está apagada (TESIS_SINCRONIZAR)."
        db.commit()
        return e
    if e.proximo_intento and e.proximo_intento > ahora:
        return e
    maximo = maximo or ajustes().tesis_por_tanda
    propio = cliente is None
    cliente = cliente or httpx.Client(headers={"User-Agent": AGENTE, "Accept": "application/json"})
    try:
        if not e.pendientes and (e.estado != "al_dia" or not e.ultima_corrida or e.ultima_corrida < ahora - timedelta(days=7)):
            total = _pedir(cliente, "tesis/count")
            e.total_remoto = int(total.get("count", total.get("total", 0)) if isinstance(total, dict) else total)
            remotos: list[int] = []
            pagina = 0
            while pagina < 2000:
                lote = _ids(_pedir(cliente, "tesis/ids", page=pagina, size=1000) or [])
                if not lote:
                    break
                remotos += lote
                pagina += 1
                time.sleep(pausa / 2)
            tengo = set(db.scalars(select(m.JTesis.registro)))
            e.pendientes = sorted((r for r in set(remotos) if r not in tengo), reverse=True)
            e.estado = "descargando" if e.pendientes else "al_dia"
        pendientes = list(e.pendientes or [])
        viejas = 0
        hechas = 0
        minima = ajustes().tesis_epoca_minima
        while pendientes and hechas < maximo:
            reg = pendientes.pop(0)
            j = _pedir(cliente, f"tesis/{reg}")
            hechas += 1
            datos = tb.desde_json(j) if j else None
            if datos is None:
                if j:
                    raise ValueError("formato no reconocido: " + ", ".join(sorted(j)[:20]) if isinstance(j, dict) else "formato no reconocido")
                continue
            datos["registro"] = datos["registro"] or reg
            n = numero_epoca(datos.get("epoca"))
            if n is not None and n < minima:
                e.omitidas += 1
                viejas += 1
                if viejas >= SEGUIDAS_VIEJAS:  # ya llegamos a las épocas antiguas
                    e.omitidas += len(pendientes)
                    pendientes = []
                    break
                continue
            viejas = 0
            tb.guardar(db, [datos], "repositorio", f"{ajustes().tesis_repositorio_url.rstrip('/')}/tesis/{reg}")
            e.descargadas += 1
            if hechas % 50 == 0:
                e.pendientes = pendientes
                db.commit()
            time.sleep(pausa)
        e.pendientes = pendientes
        e.estado = "descargando" if pendientes else "al_dia"
        e.mensaje = None
        e.proximo_intento = None
    except Bloqueada as x:
        e.estado, e.mensaje, e.proximo_intento = "bloqueada", f"{x} Use «Cargar archivos oficiales» mientras tanto.", ahora + timedelta(hours=24)
        log.warning("tesis: sincronización detenida por la SCJN")
    except (ConnectionError, ValueError) as x:
        e.estado, e.mensaje, e.proximo_intento = "error", f"No se pudo sincronizar ({x}).", ahora + timedelta(hours=6)
        log.warning("tesis: error de sincronización (%s)", x)
    finally:
        if propio:
            cliente.close()
    e.ultima_corrida = ahora
    db.commit()
    return e
