"""Poder Judicial de la Federación: Lista de acuerdos de Juzgados de Distrito y Tribunales de Circuito.

La consulta pública (dgej.cjf.gob.mx/SiseInternet/consulta/busquedaacuerdos.aspx) está protegida con reCAPTCHA:
Nomira NO la consulta en automático ni intenta evadir esa protección. Lo que hace:
- Lista de circuitos (fija) y de órganos jurisdiccionales por circuito: se lee de la misma página (las listas
  desplegables son públicas y no piden reCAPTCHA) y se guarda en memoria 24 h. Si no responde, el abogado escribe
  el nombre del órgano a mano.
- Revisión diaria asistida: agrupa los expedientes vigilados por órgano para que el abogado haga UNA búsqueda por
  órgano (la consulta oficial acepta varios expedientes separados por coma) y pegue el resultado en «Cotejar».
"""
from __future__ import annotations

import html
import re
import time

import httpx

CONSULTA = "https://www.dgej.cjf.gob.mx/SiseInternet/consulta/busquedaacuerdos.aspx"
CIRCUITOS = {  # valor en la consulta oficial → nombre (leído de la página en noviembre de 2026)
    "1": "Primer Circuito", "2": "Segundo Circuito", "3": "Tercer Circuito", "4": "Cuarto Circuito", "5": "Quinto Circuito",
    "6": "Sexto Circuito", "7": "Séptimo Circuito", "8": "Octavo Circuito", "9": "Noveno Circuito", "10": "Décimo Circuito",
    "41": "Décimo Primer Circuito", "43": "Décimo Segundo Circuito", "46": "Décimo Tercer Circuito", "38": "Décimo Cuarto Circuito",
    "42": "Décimo Quinto Circuito", "45": "Décimo Sexto Circuito", "44": "Décimo Séptimo Circuito", "40": "Décimo Octavo Circuito",
    "39": "Décimo Noveno Circuito", "20": "Vigésimo Circuito", "51": "Vigésimo Primer Circuito", "53": "Vigésimo Segundo Circuito",
    "56": "Vigésimo Tercer Circuito", "48": "Vigésimo Cuarto Circuito", "52": "Vigésimo Quinto Circuito", "55": "Vigésimo Sexto Circuito",
    "54": "Vigésimo Séptimo Circuito", "50": "Vigésimo Octavo Circuito", "49": "Vigésimo Noveno Circuito", "30": "Trigésimo Circuito",
    "47": "Trigésimo Primer Circuito", "109": "Trigésimo Segundo Circuito",
}
CACHE_SEG = 24 * 3600
_cache: dict[str, tuple[float, list[dict]]] = {}
_OCULTO = re.compile(r'<input[^>]+type="hidden"[^>]*>', re.I)
_ATTR = re.compile(r'(name|value)="([^"]*)"', re.I)
_CERRADO = re.compile(r"\(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}")


class SinCatalogo(Exception):
    pass


def _ocultos(pagina: str) -> dict[str, str]:
    r = {}
    for tag in _OCULTO.findall(pagina):
        a = dict((k.lower(), html.unescape(v)) for k, v in _ATTR.findall(tag))
        if a.get("name"):
            r[a["name"]] = a.get("value", "")
    return r


def leer_organos(pagina: str) -> list[dict]:
    """Opciones de la lista «Órgano Jurisdiccional» (sin los órganos que ya concluyeron funciones)."""
    m = re.search(r'<select[^>]+id="FiltroOrgano_ddlOrgano"[^>]*>(.*?)</select>', pagina, re.S | re.I)
    if not m:
        return []
    r = []
    for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', m.group(1), re.S | re.I):
        nombre = re.sub(r"\s+", " ", html.unescape(t)).strip()
        if v and v != "0" and nombre and not _CERRADO.search(nombre):
            r.append({"id": v.strip()[:10], "nombre": nombre[:200]})
    return r


def organos(circuito: str, cliente: httpx.Client | None = None) -> list[dict]:
    if circuito not in CIRCUITOS:
        raise SinCatalogo("Circuito desconocido.")
    hit = _cache.get(circuito)
    if hit and time.time() - hit[0] < CACHE_SEG:
        return hit[1]
    propio = cliente is None
    c = cliente or httpx.Client(timeout=8, headers={"User-Agent": "Nomira/1.0 (catalogo de organos)"}, follow_redirects=True)
    try:
        p = c.get(CONSULTA)
        p.raise_for_status()
        datos = {**_ocultos(p.text), "__EVENTTARGET": "FiltroOrgano$ddlCircuito", "__EVENTARGUMENT": "",
                 "FiltroOrgano$rblTipoFiltro": "1", "FiltroOrgano$ddlCircuito": circuito}
        r = c.post(CONSULTA, data=datos)
        r.raise_for_status()
        lista = leer_organos(r.text)
    except httpx.HTTPError as e:
        raise SinCatalogo(str(e)[:200])
    finally:
        if propio:
            c.close()
    if not lista:
        raise SinCatalogo("La página del PJF no devolvió órganos.")
    _cache[circuito] = (time.time(), lista)
    return lista
