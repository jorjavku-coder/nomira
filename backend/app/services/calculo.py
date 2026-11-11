"""Motor de cálculo: funciones puras, sin base de datos ni E/S.

Regla principal: solo se suma una fila de PERCEPCIONES cuya clave coincide EXACTAMENTE
(comparación de texto, con ceros iniciales) con una clave ACTIVA del catálogo elegido.
Nunca se autoriza por parecido de nombre, y nunca se usa float.
"""
from __future__ import annotations

import calendar
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

CERO = Decimal("0.00")
POLITICA_RETROACTIVOS = (
    "Los conceptos retroactivos conservan su clave original y se asignan a la quincena en que "
    "se pagaron. No se redistribuyen a periodos anteriores ni se equiparan con otras claves.")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


@dataclass
class FilaCalc:
    id: int
    tipo: str  # percepcion | deduccion
    orden: int
    clave: str | None
    concepto: str | None
    importe: Decimal | None
    confianza: int | None = None
    corregida: bool = False
    confirmada: bool = False


@dataclass
class ReciboCalc:
    id: int
    documento_id: int
    documento_nombre: str
    pagina: int
    num_recibo: str | None
    trabajador_nombre: str | None
    clave_servidor: str | None
    plaza: str | None
    periodo_inicio: date | None
    periodo_fin: date | None
    total_percepciones: Decimal | None = None
    total_deducciones: Decimal | None = None
    decision: str | None = None  # incluir | excluir
    filas: list[FilaCalc] = field(default_factory=list)


@dataclass
class ParametrosExpediente:
    trabajador_nombre: str
    identificador_laboral: str | None
    periodo_inicio: date
    periodo_fin: date
    quincenas_esperadas: int
    decision_plazas: str | None = None  # consolidar | separar
    clave_regex: str = r"^\d{4}$"
    confianza_minima: int = 70


# ---------- utilidades ----------

def dinero(v: Decimal | None) -> str | None:
    """Decimal -> texto con 2 decimales (serialización exacta para JSON)."""
    return None if v is None else str(v.quantize(Decimal("0.01")))


def _norm_nombre(s: str | None) -> tuple[str, ...]:
    s = unicodedata.normalize("NFD", (s or "").upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return tuple(sorted(re.findall(r"[A-ZÑ]+", s)))


def _solo_digitos(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def fin_de_mes(anio: int, mes: int) -> int:
    return calendar.monthrange(anio, mes)[1]


def quincena_de(inicio: date | None, fin: date | None) -> tuple[int, int, int] | None:
    """(año, mes, mitad) si el periodo es exactamente una quincena natural; si no, None."""
    if not inicio or not fin or (inicio.year, inicio.month) != (fin.year, fin.month):
        return None
    if inicio.day == 1 and fin.day == 15:
        return inicio.year, inicio.month, 1
    if inicio.day == 16 and fin.day == fin_de_mes(fin.year, fin.month):
        return inicio.year, inicio.month, 2
    return None


def limites(q: tuple[int, int, int]) -> tuple[date, date]:
    a, m, mitad = q
    return (date(a, m, 1), date(a, m, 15)) if mitad == 1 else (date(a, m, 16), date(a, m, fin_de_mes(a, m)))


def etiqueta(q: tuple[int, int, int]) -> str:
    return f"{'1.ª' if q[2] == 1 else '2.ª'} quincena de {MESES[q[1] - 1]} de {q[0]}"


def clave_q(q: tuple[int, int, int]) -> str:
    return f"{q[0]:04d}-{q[1]:02d}-Q{q[2]}"


def quincenas_esperadas(inicio: date, fin: date) -> list[tuple[int, int, int]]:
    """Quincenas naturales contenidas por completo en [inicio, fin]."""
    res = []
    a, m = inicio.year, inicio.month
    while date(a, m, 1) <= fin:
        for mitad in (1, 2):
            i, f = limites((a, m, mitad))
            if i >= inicio and f <= fin:
                res.append((a, m, mitad))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return res


def periodo_alineado(inicio: date, fin: date) -> bool:
    return inicio.day in (1, 16) and fin.day in (15, fin_de_mes(fin.year, fin.month)) and inicio <= fin


def es_retroactivo(clave: str) -> bool:
    """Indicador (primer dígito) 1 = retroactiva, 3 = periodos fiscales anteriores, según la
    página explicativa de los propios comprobantes. Solo informa; no altera la suma."""
    return len(clave) == 4 and clave[0] in "13"


def huella_recibo(r: ReciboCalc) -> str:
    """Huella del contenido (no del número de recibo, que puede repetirse)."""
    partes = [f"{f.tipo}|{f.clave}|{dinero(f.importe)}" for f in sorted(r.filas, key=lambda f: (f.tipo, f.orden))]
    partes.append(f"T|{dinero(r.total_percepciones)}|{dinero(r.total_deducciones)}")
    return hashlib.sha256("\n".join(partes).encode()).hexdigest()


def mismo_trabajador(p: ParametrosExpediente, r: ReciboCalc) -> bool | None:
    """True/False, o None si el recibo no permite identificar al trabajador."""
    if p.identificador_laboral and _solo_digitos(p.identificador_laboral):
        if not r.clave_servidor:
            return None
        return _solo_digitos(r.clave_servidor) == _solo_digitos(p.identificador_laboral)
    if not r.trabajador_nombre:
        return None
    return _norm_nombre(r.trabajador_nombre) == _norm_nombre(p.trabajador_nombre)


# ---------- cálculo ----------

def calcular(p: ParametrosExpediente, recibos: list[ReciboCalc],
             catalogo: dict[str, tuple[str, bool]]) -> dict:
    """catalogo: clave -> (descripción, activo). Devuelve un dict serializable a JSON."""
    re_clave = re.compile(p.clave_regex)
    alertas: list[dict] = []

    def alerta(tipo, mensaje, bloqueante=True, **ref):
        alertas.append({"tipo": tipo, "mensaje": mensaje, "bloqueante": bloqueante, **ref})

    esperadas = quincenas_esperadas(p.periodo_inicio, p.periodo_fin)
    esperadas_set = set(esperadas)
    if len(esperadas) != p.quincenas_esperadas:
        alerta("quincenas_esperadas",
               f"El expediente espera {p.quincenas_esperadas} quincenas, pero el periodo de análisis "
               f"contiene {len(esperadas)}.", bloqueante=False)

    recibos = sorted(recibos, key=lambda r: (r.documento_id, r.pagina))
    info_recibo: dict[int, dict] = {}
    candidatos: list[ReciboCalc] = []

    # 1) Elegibilidad de cada recibo
    for r in recibos:
        q = quincena_de(r.periodo_inicio, r.periodo_fin)
        ref = {"recibo_id": r.id, "documento_id": r.documento_id, "pagina": r.pagina,
               "quincena": clave_q(q) if q else None}
        info = {"estado": "incluido", "motivo": None, "quincena": ref["quincena"], "huella": huella_recibo(r)}
        info_recibo[r.id] = info
        if r.decision == "excluir":
            info.update(estado="excluido", motivo="Excluido por decisión del revisor")
            continue
        mt = mismo_trabajador(p, r)
        if mt is False and r.decision != "incluir":
            info.update(estado="excluido", motivo="El recibo corresponde a otro trabajador")
            alerta("otro_trabajador", "Recibo de un trabajador distinto al del expediente: no se suma. "
                   "Confirme la exclusión.", **ref)
            continue
        if mt is None and r.decision != "incluir":
            info.update(estado="pendiente", motivo="No se pudo identificar al trabajador en el recibo")
            alerta("trabajador_ilegible", "No se pudo leer el trabajador del recibo. Revise el original y "
                   "decida si se incluye.", **ref)
            continue
        if q is None:
            info.update(estado="pendiente", motivo="Periodo de pago ilegible o no quincenal")
            alerta("periodo_invalido", "El periodo de pago no se leyó o no corresponde a una quincena "
                   "natural. Corrija el periodo o excluya el recibo.", **ref)
            continue
        if q not in esperadas_set:
            info.update(estado="excluido", motivo="Fuera del periodo de análisis")
            alerta("fuera_de_periodo", f"Recibo de la {etiqueta(q)}, fuera del periodo de análisis: no se suma.",
                   bloqueante=False, **ref)
            continue
        candidatos.append(r)

    # 2) Duplicados vs. complementarios: misma plaza y mismo periodo
    grupos: dict[tuple, list[ReciboCalc]] = {}
    for r in candidatos:
        grupos.setdefault((r.plaza or "", r.periodo_inicio, r.periodo_fin), []).append(r)
    incluidos_r: list[ReciboCalc] = []
    for grupo in grupos.values():
        base = grupo[0]
        incluidos_r.append(base)
        for r in grupo[1:]:
            info = info_recibo[r.id]
            ref = {"recibo_id": r.id, "documento_id": r.documento_id, "pagina": r.pagina,
                   "quincena": info["quincena"], "recibo_relacionado_id": base.id}
            identico = info["huella"] == info_recibo[base.id]["huella"]
            if r.decision == "incluir":
                incluidos_r.append(r)
                continue
            if identico:
                info.update(estado="pendiente", motivo="Posible duplicado (mismo trabajador, plaza, periodo y contenido)")
                alerta("posible_duplicado", "Posible recibo duplicado: mismo periodo, plaza y contenido que otro "
                       "recibo. No se suma hasta que decida incluirlo o excluirlo.", **ref)
            else:
                incluidos_r.append(r)
                info["motivo"] = "Recibo complementario del mismo periodo (pendiente de confirmar)"
                alerta("complementario", "Hay más de un recibo para la misma plaza y periodo con contenido "
                       "distinto (posible complementario). Se suma, pero debe confirmarlo.", **ref)

    # Aviso informativo: número de recibo repetido en periodos distintos
    por_num: dict[str, set] = {}
    for r in candidatos:
        if r.num_recibo:
            por_num.setdefault(r.num_recibo, set()).add((r.periodo_inicio, r.periodo_fin))
    for num, periodos in por_num.items():
        if len(periodos) > 1:
            alerta("num_recibo_repetido", f"El número de recibo {num} aparece en {len(periodos)} periodos "
                   "distintos. Se tratan como recibos diferentes (el número no identifica al recibo).",
                   bloqueante=False)

    # 3) Clasificación de filas
    incluidos, excluidos, pendientes = [], [], []
    ids_incluidos = {r.id for r in incluidos_r}
    for r in recibos:
        info = info_recibo[r.id]
        q_txt = info["quincena"]
        suma_perc = CERO
        legible = True
        for f in r.filas:
            if f.tipo != "percepcion":
                continue  # las deducciones jamás se evalúan ni se suman
            base = {"fila_id": f.id, "recibo_id": r.id, "documento_id": r.documento_id,
                    "documento": r.documento_nombre, "pagina": r.pagina, "quincena": q_txt,
                    "plaza": r.plaza, "clave": f.clave, "concepto_original": f.concepto,
                    "importe": dinero(f.importe), "corregida": f.corregida}
            if f.importe is None:
                legible = False
            else:
                suma_perc += f.importe
            if r.id not in ids_incluidos:
                if info["estado"] == "pendiente":
                    pendientes.append({**base, "motivo": info["motivo"]})
                else:
                    excluidos.append({**base, "motivo": info["motivo"]})
                continue
            motivo = None
            if not f.clave or not re_clave.match(f.clave):
                motivo = "Clave ilegible o con formato inesperado"
            elif f.importe is None:
                motivo = "Importe faltante o ilegible"
            elif (f.confianza is not None and f.confianza < p.confianza_minima
                  and not (f.corregida or f.confirmada)):
                motivo = f"Lectura OCR dudosa (confianza {f.confianza})"
            elif f.importe < 0 and not f.confirmada:
                motivo = "Importe negativo: confirme que es correcto"
            if motivo:
                pendientes.append({**base, "motivo": motivo})
                alerta("fila_pendiente", f"Fila pendiente (clave {f.clave or '¿?'}): {motivo}.",
                       fila_id=f.id, recibo_id=r.id, documento_id=r.documento_id, pagina=r.pagina, quincena=q_txt)
                continue
            entrada = catalogo.get(f.clave)  # coincidencia exacta de texto
            if entrada is None:
                excluidos.append({**base, "motivo": "La clave no está en el catálogo autorizado"})
            elif not entrada[1]:
                excluidos.append({**base, "motivo": "Clave inactiva en el catálogo"})
            else:
                incluidos.append({**base, "concepto_catalogo": entrada[0],
                                  "retroactivo": es_retroactivo(f.clave), "negativo": f.importe < 0})
        if (r.id in ids_incluidos and legible and r.total_percepciones is not None
                and suma_perc != r.total_percepciones and r.decision != "incluir"):
            alerta("descuadre", f"La suma de percepciones leídas ({dinero(suma_perc)}) no coincide con el "
                   f"«Total de percepciones» del recibo ({dinero(r.total_percepciones)}). Revise la lectura.",
                   recibo_id=r.id, documento_id=r.documento_id, pagina=r.pagina, quincena=q_txt)

    # 4) Plazas
    plazas = sorted({r.plaza or "(sin plaza)" for r in incluidos_r})
    if len(plazas) > 1 and p.decision_plazas not in ("consolidar", "separar"):
        alerta("plazas", f"Se detectaron {len(plazas)} plazas. Decida si se consolidan o se reportan por separado.")
    consolidar = len(plazas) <= 1 or p.decision_plazas == "consolidar"

    # 5) Desglose por quincena
    con_recibo: dict[tuple, list[ReciboCalc]] = {}
    for r in incluidos_r:
        con_recibo.setdefault(quincena_de(r.periodo_inicio, r.periodo_fin), []).append(r)
    q_pendiente = {x["quincena"] for x in pendientes if x["quincena"]}
    q_pendiente |= {a["quincena"] for a in alertas if a["bloqueante"] and a.get("quincena")}
    quincenas, faltantes = [], []
    total_exp = CERO
    for n, q in enumerate(esperadas, start=1):
        ini, fin = limites(q)
        cq = clave_q(q)
        filas_q = [x for x in incluidos if x["quincena"] == cq]
        por_plaza = []
        for pz in sorted({x["plaza"] or "(sin plaza)" for x in filas_q}):
            conceptos = [x for x in filas_q if (x["plaza"] or "(sin plaza)") == pz]
            por_plaza.append({"plaza": pz, "conceptos": conceptos,
                              "total": dinero(sum((Decimal(x["importe"]) for x in conceptos), CERO))})
        total = sum((Decimal(x["importe"]) for x in filas_q), CERO)
        total_exp += total
        if q not in con_recibo:
            estado = "pendiente" if cq in q_pendiente else "faltante"
        else:
            estado = "con_prestaciones" if filas_q else "cero"
        if estado == "faltante":
            faltantes.append({"quincena": cq, "etiqueta": etiqueta(q), "inicio": ini.isoformat(), "fin": fin.isoformat()})
        quincenas.append({
            "numero": n, "quincena": cq, "etiqueta": etiqueta(q), "inicio": ini.isoformat(),
            "fin": fin.isoformat(), "estado": estado, "provisional": cq in q_pendiente,
            "recibos": [r.id for r in con_recibo.get(q, [])], "plazas": por_plaza, "total": dinero(total)})
    if faltantes:
        alerta("quincenas_faltantes", f"Faltan comprobantes de {len(faltantes)} quincena(s). No se les asigna "
               "importe alguno.", bloqueante=False)

    # 6) Acumulados
    por_clave: dict[str, dict] = {}
    for x in incluidos:
        d = por_clave.setdefault(x["clave"], {"clave": x["clave"], "concepto_catalogo": x["concepto_catalogo"],
                                              "retroactivo": x["retroactivo"], "apariciones": 0, "_t": CERO})
        d["apariciones"] += 1
        d["_t"] += Decimal(x["importe"])
    acumulado = [{**{k: v for k, v in d.items() if k != "_t"}, "total": dinero(d["_t"])}
                 for d in sorted(por_clave.values(), key=lambda d: d["clave"])]
    por_plaza_tot = [{"plaza": pz, "total": dinero(sum(
        (Decimal(x["importe"]) for x in incluidos if (x["plaza"] or "(sin plaza)") == pz), CERO))} for pz in plazas]

    bloqueantes = [a for a in alertas if a["bloqueante"]]
    return {
        "quincenas": quincenas,
        "incluidos": incluidos,
        "excluidos": excluidos,
        "pendientes": pendientes,
        "acumulado_por_clave": acumulado,
        "plazas": por_plaza_tot,
        "consolidado": consolidar,
        # Con plazas separadas no se presenta un total único del expediente.
        "total_expediente": dinero(total_exp) if consolidar else None,
        "faltantes": faltantes,
        "alertas": alertas,
        "recibos": {str(k): {"estado": v["estado"], "motivo": v["motivo"], "quincena": v["quincena"]}
                    for k, v in info_recibo.items()},
        "resumen": {
            "quincenas_esperadas": p.quincenas_esperadas,
            "quincenas_en_periodo": len(esperadas),
            "quincenas_con_recibo": len(con_recibo),
            "quincenas_faltantes": len(faltantes),
            "quincenas_en_cero": sum(1 for q in quincenas if q["estado"] == "cero"),
            "filas_incluidas": len(incluidos), "filas_excluidas": len(excluidos),
            "filas_pendientes": len(pendientes), "alertas_bloqueantes": len(bloqueantes),
            "recibos": len(recibos),
        },
        "provisional": bool(bloqueantes),
        "politica_retroactivos": POLITICA_RETROACTIVOS,
    }
