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


FECHAS = ("fecha_evento", "fecha_mencionada", "fecha_indeterminada")  # nunca la fecha de un documento
DECISIONES = {"eventos_distintos": "Son eventos distintos", "aclarada": "Diferencia aclarada",
              "contradiccion": "Contradicción confirmada", "no_aplica": "No aplica"}


def _mismo_dato(a: dict, b: dict, umbral: float) -> tuple[bool, float]:
    """¿Describen el mismo evento o dato? Con tema en ambos, deben coincidir; si falta en alguno,
    se exige que el texto sea muy parecido."""
    ta, tb = a.get("tema"), b.get("tema")
    if ta and tb:
        return ta == tb, 1.0 if ta == tb else 0.0
    sim = similitud(a["descripcion"], b["descripcion"])
    return sim >= umbral, sim


def _nombre(v: str | None) -> str:
    return " ".join(re.findall(r"[a-zñ]+", normalizar(v or "")))


def _explicar(a: dict, b: dict, motivos: list[str], tema_txt: str | None) -> str:
    sobre = f"de «{tema_txt.lower()}»" if tema_txt else "de algo muy parecido (las frases casi coinciden)"
    partes = []
    if "fecha" in motivos:
        partes.append(f"Las dos fuentes hablan {sobre} y dan fechas distintas: {a.get('valor') or a['fecha']} y {b.get('valor') or b['fecha']}.")
    if "importe" in motivos:
        partes.append(f"Las dos fuentes hablan {sobre} y dan cantidades distintas: ${a['importe']} y ${b['importe']}.")
    if "nombre" in motivos:
        partes.append(f"Las dos fuentes nombran de forma distinta a quien aparece como «{tema_txt}»: {a.get('valor')} y {b.get('valor')}.")
    return " ".join(partes) + " Puede tratarse de eventos distintos, de un error o de una contradicción: decídalo usted."


def contradicciones(hechos: list[dict], descartadas: set[str] | None = None, decisiones: dict | None = None,
                    etiquetas_tema: dict | None = None, umbral: float = 0.5) -> list[dict]:
    """«Posibles diferencias por revisar»: pares de propuestas o hechos (no descartados) de documentos
    distintos que parecen describir el MISMO dato con valores diferentes (fechas de eventos, cantidades
    o nombres de una misma persona). Nunca compara la fecha de un documento con la del evento que
    describe. No decide cuál versión es correcta ni cambia ningún hecho. `descartadas` son decisiones
    antiguas («marcar como revisada»), que equivalen a «No aplica»."""
    descartadas, decisiones, etiquetas_tema = descartadas or set(), decisiones or {}, etiquetas_tema or {}
    candidatos = [h for h in hechos if h["estado"] != "descartado" and h.get("documento_id")
                  and h.get("tipo_dato", "fecha_evento") in FECHAS + ("importe", "persona")]
    res = []
    for a, b in combinations(sorted(candidatos, key=lambda h: h["id"]), 2):
        if a["documento_id"] == b["documento_id"]:
            continue
        par = f"{a['id']}-{b['id']}"
        ta, tb = a.get("tipo_dato", "fecha_evento"), b.get("tipo_dato", "fecha_evento")
        motivos = []
        if ta == tb == "persona":
            na, nb = _nombre(a.get("valor")), _nombre(b.get("valor"))
            if a.get("tema") and a.get("tema") == b.get("tema") and na and nb and na != nb and na not in nb and nb not in na:
                motivos.append("nombre")
            mismo, sim = bool(motivos), 1.0
        else:
            if ta in FECHAS and tb in FECHAS and a.get("fecha") and b.get("fecha") and a["fecha"] != b["fecha"]:
                motivos.append("fecha")
            if a.get("importe") is not None and b.get("importe") is not None and a["importe"] != b["importe"]:
                motivos.append("importe")
            if not motivos:
                continue
            mismo, sim = _mismo_dato(a, b, umbral)
        if not (motivos and mismo):
            continue
        tema = a.get("tema") or b.get("tema")
        tema_txt = etiquetas_tema.get(tema) or (tema.split(":", 1)[1].capitalize() if tema and tema.startswith("rol:") else None)
        decision = decisiones.get(par) or ({"decision": "no_aplica", "por": None, "en": None, "nota": None} if par in descartadas else None)
        res.append({"par": par, "hechos": [a["id"], b["id"]], "difieren": motivos, "similitud": round(sim, 2), "tema": tema,
                    "tema_texto": tema_txt, "explicacion": _explicar(a, b, motivos, tema_txt),
                    "decision": decision, "decision_texto": DECISIONES.get(decision["decision"]) if decision else None,
                    "estado": "pendiente" if not decision else "resuelta",
                    "contradiccion": bool(decision and decision["decision"] == "contradiccion")})
    return res


def cronologia(hechos: list[dict], contrad: list[dict]) -> dict:
    """Solo hechos validados por una persona. La fecha de un documento no es un evento del caso, y
    lugares, personas y datos administrativos no forman parte de la línea de tiempo."""
    en_conflicto: dict[int, list[str]] = {}
    for c in contrad:
        if c.get("estado") == "resuelta" and not c.get("contradiccion"):
            continue  # la persona decidió que no es una contradicción
        a, b = c["hechos"]
        en_conflicto.setdefault(a, []).append(c["par"])
        en_conflicto.setdefault(b, []).append(c["par"])
    revisados = [h for h in hechos if h["estado"] in REVISADOS]
    eventos = [h for h in revisados if h.get("fecha") and h.get("tipo_dato", "fecha_evento") in FECHAS + ("importe", "otro")]
    con_fecha = sorted(eventos, key=lambda h: (h["fecha"], h["id"]))
    sin_fecha = [h for h in revisados if not h.get("fecha") and h.get("tipo_dato", "otro") in ("importe", "otro")]
    return {"eventos": [{**h, "contradicciones": en_conflicto.get(h["id"], [])} for h in con_fecha],
            "sin_fecha": [{**h, "contradicciones": en_conflicto.get(h["id"], [])} for h in sin_fecha]}


def sugerir_estado_punto(vinculos: list[dict], hechos_en_conflicto: set[int]) -> dict:
    """Sugerencia conservadora: NUNCA sugiere «respaldado» (eso implica juzgar la suficiencia), y un
    archivo vinculado no basta para que un punto parezca acreditado."""
    if not vinculos:
        return {"estado": "pendiente_evidencia", "motivo": "No tiene evidencia vinculada."}
    if any(v.get("relacion") == "contradice" for v in vinculos):
        return {"estado": "contradictorio", "motivo": "Usted marcó al menos una fuente como «contradice»."}
    if any(v.get("hecho_id") in hechos_en_conflicto for v in vinculos):
        return {"estado": "contradictorio", "motivo": "Uno de los hechos vinculados tiene una posible diferencia sin resolver o confirmada."}
    sin = sum(1 for v in vinculos if v.get("relacion", "sin_evaluar") == "sin_evaluar")
    if sin:
        return {"estado": "parcial", "motivo": f"{sin} fuente(s) vinculada(s) sin evaluar. Indique si apoyan, contradicen o no bastan."}
    return {"estado": "parcial", "motivo": "Decidir si la evidencia basta corresponde al abogado; Nomira no lo evalúa."}
