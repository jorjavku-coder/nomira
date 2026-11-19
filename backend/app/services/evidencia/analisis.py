"""Cronología, posibles contradicciones y sugerencias para la matriz. Funciones puras.

Nada aquí emite conclusiones jurídicas: solo ordena hechos ya revisados por una persona y señala
datos que PARECEN incompatibles para que el abogado los revise.
"""
from __future__ import annotations

import re
from itertools import combinations

from .lectura import MESES, normalizar

REVISADOS = ("confirmado", "editado")
_VACIAS = set("""el la los las un una unos unas de del al a en y o u que se su sus por para con sin sobre
entre como fue era son ser sera seran este esta estos estas ese esa dicho dicha mismo misma cual quien cuyo
fecha dia dias mes ano anos cantidad pesos moneda nacional""".split()) | set(MESES)


def raices(texto: str) -> set[str]:
    """Palabras de contenido truncadas a 5 letras («inicia» e «inició» coinciden)."""
    return {w[:5] for w in re.findall(r"[a-zñ]+", normalizar(texto)) if len(w) >= 4 and w not in _VACIAS}


def similitud(a: str, b: str) -> float:
    """Proporción de palabras de contenido compartidas respecto al texto más corto (0 a 1).
    Exige al menos 3 en común: frases muy cortas no bastan para sospechar una contradicción."""
    ra, rb = raices(a), raices(b)
    comunes = ra & rb
    if len(comunes) < 3:
        return 0.0
    return len(comunes) / min(len(ra), len(rb))


def contradicciones(hechos: list[dict], descartadas: set[str] | None = None, umbral: float = 0.5) -> list[dict]:
    """Pares de hechos revisados, de documentos distintos, que describen algo muy parecido pero con
    fecha o importe diferentes. No decide cuál es correcto."""
    descartadas = descartadas or set()
    revisados = [h for h in hechos if h["estado"] in REVISADOS and h.get("documento_id")]
    res = []
    for a, b in combinations(sorted(revisados, key=lambda h: h["id"]), 2):
        if a["documento_id"] == b["documento_id"]:
            continue
        par = f"{a['id']}-{b['id']}"
        if par in descartadas:
            continue
        motivos = []
        if a.get("fecha") and b.get("fecha") and a["fecha"] != b["fecha"]:
            motivos.append("fecha")
        if a.get("importe") is not None and b.get("importe") is not None and a["importe"] != b["importe"]:
            motivos.append("importe")
        if not motivos:
            continue
        sim = similitud(a["descripcion"], b["descripcion"])
        if sim >= umbral:
            res.append({"par": par, "hechos": [a["id"], b["id"]], "difieren": motivos, "similitud": round(sim, 2)})
    return res


def cronologia(hechos: list[dict], contrad: list[dict]) -> dict:
    """Solo hechos revisados por una persona. Los que no tienen fecha van aparte."""
    en_conflicto: dict[int, list[str]] = {}
    for c in contrad:
        a, b = c["hechos"]
        en_conflicto.setdefault(a, []).append(c["par"])
        en_conflicto.setdefault(b, []).append(c["par"])
    revisados = [h for h in hechos if h["estado"] in REVISADOS]
    con_fecha = sorted((h for h in revisados if h.get("fecha")), key=lambda h: (h["fecha"], h["id"]))
    return {"eventos": [{**h, "contradicciones": en_conflicto.get(h["id"], [])} for h in con_fecha],
            "sin_fecha": [{**h, "contradicciones": en_conflicto.get(h["id"], [])} for h in revisados if not h.get("fecha")]}


def sugerir_estado_punto(vinculos: list[dict], hechos_en_conflicto: set[int]) -> dict:
    """Sugerencia conservadora: nunca sugiere «respaldado» (eso implica juzgar la suficiencia)."""
    if not vinculos:
        return {"estado": "pendiente_evidencia", "motivo": "No tiene evidencia vinculada."}
    if any(v.get("hecho_id") in hechos_en_conflicto for v in vinculos):
        return {"estado": "contradictorio", "motivo": "Uno de los hechos vinculados tiene una posible contradicción."}
    return {"estado": "parcial", "motivo": "Tiene evidencia vinculada; la decisión de si basta corresponde al abogado."}
