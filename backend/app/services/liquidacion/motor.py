"""Calculadora de finiquito y liquidación conforme a la Ley Federal del Trabajo (apartado A).

Funciones puras: sin base de datos ni E/S, todo en Decimal (nunca float) y cada concepto redondeado a centavos.
El resultado es una ESTIMACIÓN para preparar demandas, contestaciones y convenios: cada concepto lleva su
fundamento y la operación que lo produjo para que el abogado la revise. Importes brutos, antes de ISR.

Tablas que cambian con el tiempo (aquí, en un solo lugar):
- Salarios mínimos por año (zona general y Zona Libre de la Frontera Norte), DOF.
- Vacaciones: tabla anterior y la de la reforma «vacaciones dignas» (vigente desde el 1 de enero de 2023).
- Jornada máxima semanal y horas extra dobles por año: reforma a la LFT publicada en el DOF el 1 de mayo de 2026
  (48 h hasta 2026; 46 en 2027; 44 en 2028; 42 en 2029; 40 desde 2030; dobles 9/9/10/11/12).
- Salarios caídos: reforma del 30 de noviembre de 2012 (tope de 12 meses + 2 % mensual sobre 15 meses).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CERO = Decimal("0")
CENT = Decimal("0.01")
D365 = Decimal("365")

CAUSAS = {
    "renuncia": "Renuncia voluntaria",
    "mutuo_acuerdo": "Terminación por mutuo acuerdo o fin de contrato",
    "despido_justificado": "Despido justificado (art. 47)",
    "despido_injustificado": "Despido injustificado (art. 48)",
    "rescision_trabajador": "Rescisión por causa del patrón (art. 51)",
    "fallecimiento": "Fallecimiento del trabajador",
}
JORNADAS = {"diurna": Decimal("8"), "mixta": Decimal("7.5"), "nocturna": Decimal("7")}
TOPE_SEMANAL_TIPO = {"diurna": None, "mixta": 45, "nocturna": 42}

# Salario mínimo diario: (zona general, Zona Libre de la Frontera Norte). Antes de 2019 había una sola área.
SALARIOS_MINIMOS: dict[int, tuple[str, str]] = {
    2017: ("80.04", "80.04"),
    2018: ("88.36", "88.36"),
    2019: ("102.68", "176.72"),
    2020: ("123.22", "185.56"),
    2021: ("141.70", "213.39"),
    2022: ("172.87", "260.34"),
    2023: ("207.44", "312.41"),
    2024: ("248.93", "374.89"),
    2025: ("278.80", "419.88"),
    2026: ("315.04", "440.87"),
}
# Año -> (jornada máxima semanal, horas extra pagadas al doble por semana). Antes de 2027: 48 y 9.
JORNADA_POR_ANIO: dict[int, tuple[int, int]] = {2027: (46, 9), 2028: (44, 10), 2029: (42, 11), 2030: (40, 12)}
REFORMA_VACACIONES = date(2023, 1, 1)
REFORMA_SALARIOS_CAIDOS = date(2012, 12, 1)


def r2(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def txt(v: Decimal | None) -> str | None:
    return None if v is None else str(r2(v))


def num(v: Decimal, n: int = 4) -> str:
    """Número para mostrar en la fórmula, sin ceros de sobra."""
    s = f"{v.quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP):f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def pesos(v: Decimal) -> str:
    return f"${r2(v):,.2f}"


def jornada_legal(anio: int) -> tuple[int, int]:
    if anio <= 2026:
        return 48, 9
    return JORNADA_POR_ANIO.get(anio, (40, 12))


def salario_minimo(anio: int, zona: str) -> tuple[Decimal | None, int | None]:
    """Devuelve (salario mínimo, año usado). Si el año aún no está en la tabla usa el más reciente."""
    if anio in SALARIOS_MINIMOS:
        g, f = SALARIOS_MINIMOS[anio]
        return Decimal(f if zona == "frontera" else g), anio
    if anio > max(SALARIOS_MINIMOS):
        ult = max(SALARIOS_MINIMOS)
        g, f = SALARIOS_MINIMOS[ult]
        return Decimal(f if zona == "frontera" else g), ult
    return None, None


def dias_vacaciones(anio_servicio: int, al: date) -> int:
    """Días de vacaciones del año de servicio n (n >= 1), con la tabla vigente en la fecha «al»."""
    n = max(1, anio_servicio)
    if al >= REFORMA_VACACIONES:  # art. 76 reformado: 12, 14, 16, 18, 20 y +2 cada 5 años
        return 10 + 2 * n if n <= 5 else 20 + 2 * ((n - 5 + 4) // 5)
    return 4 + 2 * n if n <= 4 else 12 + 2 * (n // 5)  # tabla anterior: 6, 8, 10, 12, 14 y +2 cada 5 años


def _aniversario(ingreso: date, anios: int) -> date:
    try:
        return ingreso.replace(year=ingreso.year + anios)
    except ValueError:  # 29 de febrero
        return date(ingreso.year + anios, 3, 1)


def anios_completos(ingreso: date, al: date) -> int:
    n = al.year - ingreso.year
    if _aniversario(ingreso, n) > al:
        n -= 1
    return max(0, n)


@dataclass
class PeriodoExtra:
    desde: date
    hasta: date
    horas_semana: Decimal  # horas trabajadas por semana en ese periodo


@dataclass
class OtroConcepto:
    concepto: str
    importe: Decimal


@dataclass
class Datos:
    fecha_ingreso: date
    fecha_baja: date
    causa: str
    salario_diario: Decimal
    fecha_calculo: date | None = None  # hasta dónde corren los salarios caídos
    salario_integrado: Decimal | None = None  # si se captura, manda sobre el calculado
    otras_prestaciones_diarias: Decimal = CERO  # p. ej. vales, fondo de ahorro: integran el salario (art. 84)
    zona: str = "general"  # general | frontera
    salario_minimo: Decimal | None = None  # si se captura, manda sobre la tabla
    aguinaldo_dias: Decimal = Decimal("15")
    prima_vacacional_pct: Decimal = Decimal("25")
    dias_pendientes_pago: Decimal = CERO
    incluir_aguinaldo: bool = True
    vacaciones_anteriores_dias: Decimal = CERO
    vacaciones_tomadas_actual: Decimal = CERO
    incluir_20_dias: bool | None = None  # None = según la causa
    incluir_salarios_caidos: bool | None = None
    tipo_jornada: str = "diurna"
    horas_extra: list[PeriodoExtra] = field(default_factory=list)
    otros: list[OtroConcepto] = field(default_factory=list)


class ErrorDatos(ValueError):
    pass


def _c(clave: str, concepto: str, importe: Decimal, operacion: str, fundamento: str) -> dict:
    return {"clave": clave, "concepto": concepto, "importe": txt(importe), "operacion": operacion, "fundamento": fundamento}


def calcular(d: Datos, hoy: date) -> dict:
    if d.fecha_baja < d.fecha_ingreso:
        raise ErrorDatos("La fecha de baja no puede ser anterior a la de ingreso.")
    if d.salario_diario <= 0:
        raise ErrorDatos("Capture el salario diario.")
    if d.causa not in CAUSAS:
        raise ErrorDatos("Causa de terminación no válida.")
    if d.tipo_jornada not in JORNADAS:
        raise ErrorDatos("Tipo de jornada no válido.")
    avisos: list[str] = []
    sd = d.salario_diario
    calc_al = d.fecha_calculo or hoy

    # ---- antigüedad
    # Años completos (por aniversario) más la fracción del año en curso, contando el día de la baja.
    dias_ant = (d.fecha_baja - d.fecha_ingreso).days + 1
    completos = anios_completos(d.fecha_ingreso, d.fecha_baja)
    ult_aniv = _aniversario(d.fecha_ingreso, completos)
    dias_aniv = min(365, (d.fecha_baja - ult_aniv).days + 1)
    anios = Decimal(completos) + Decimal(dias_aniv) / D365

    # ---- salario integrado (art. 84 y 89)
    vac_actual = dias_vacaciones(completos + 1, d.fecha_baja)
    pv = d.prima_vacacional_pct / Decimal(100)
    factor = Decimal(1) + (d.aguinaldo_dias + Decimal(vac_actual) * pv) / D365
    sdi_calc = r2(sd * factor + d.otras_prestaciones_diarias)
    sdi = r2(d.salario_integrado) if d.salario_integrado and d.salario_integrado > 0 else sdi_calc

    # ---- salario mínimo y tope de la prima de antigüedad (art. 162, 485 y 486)
    if d.salario_minimo and d.salario_minimo > 0:
        sm, sm_anio = d.salario_minimo, None
    else:
        sm, sm_anio = salario_minimo(d.fecha_baja.year, d.zona)
        if sm_anio and sm_anio != d.fecha_baja.year:
            avisos.append(f"Aún no está en la tabla el salario mínimo de {d.fecha_baja.year}; se usó el de {sm_anio}. Puede capturarlo a mano.")
        if sm is None:
            avisos.append("No hay salario mínimo en la tabla para el año de la baja: captúrelo para calcular el tope de la prima de antigüedad.")

    secciones: list[dict] = []

    # ---- finiquito: lo que se debe siempre, sea cual sea la causa
    fin: list[dict] = []
    if d.dias_pendientes_pago > 0:
        fin.append(_c("salarios_devengados", "Salarios devengados no pagados", r2(d.dias_pendientes_pago * sd),
                      f"{num(d.dias_pendientes_pago)} días × {pesos(sd)}", "Art. 82, 88 y 89 LFT"))
    if d.incluir_aguinaldo:
        inicio_anio = max(d.fecha_ingreso, date(d.fecha_baja.year, 1, 1))
        dias_anio = (d.fecha_baja - inicio_anio).days + 1
        ag = r2(d.aguinaldo_dias * Decimal(dias_anio) / D365 * sd)
        fin.append(_c("aguinaldo", "Aguinaldo proporcional", ag,
                      f"{num(d.aguinaldo_dias)} días × {dias_anio}/365 días trabajados en {d.fecha_baja.year} × {pesos(sd)}", "Art. 87 LFT"))
    prop = Decimal(vac_actual) * Decimal(dias_aniv) / D365
    vac_dias = max(CERO, prop - d.vacaciones_tomadas_actual) + d.vacaciones_anteriores_dias
    if vac_dias > 0:
        tabla = "tabla vigente desde 2023" if d.fecha_baja >= REFORMA_VACACIONES else "tabla anterior a 2023"
        partes = [f"{vac_actual} días del año {completos + 1} de servicio × {dias_aniv}/365 ({tabla})"]
        if d.vacaciones_tomadas_actual > 0:
            partes.append(f"− {num(d.vacaciones_tomadas_actual)} ya disfrutados")
        if d.vacaciones_anteriores_dias > 0:
            partes.append(f"+ {num(d.vacaciones_anteriores_dias)} pendientes de periodos anteriores")
        vac = r2(vac_dias * sd)
        fin.append(_c("vacaciones", "Vacaciones", vac, f"{' '.join(partes)} = {num(vac_dias, 2)} días × {pesos(sd)}", "Art. 76, 79 LFT"))
        fin.append(_c("prima_vacacional", "Prima vacacional", r2(vac * pv), f"{pesos(vac)} × {num(d.prima_vacacional_pct)} %", "Art. 80 LFT"))
    secciones.append({"clave": "finiquito", "titulo": "Finiquito", "conceptos": fin})

    # ---- prima de antigüedad
    ind: list[dict] = []
    voluntaria = d.causa in ("renuncia", "mutuo_acuerdo")
    if voluntaria and anios < 15:
        avisos.append("La prima de antigüedad no procede: en la separación voluntaria se paga solo con 15 años o más de servicio (art. 162, fr. III).")
    elif sm is not None:
        tope = r2(sm * 2)
        base = min(sdi, tope)
        nota = "tope: 2 salarios mínimos" if base == tope and sdi > tope else "salario integrado (no rebasa el tope)"
        ind.append(_c("prima_antiguedad", "Prima de antigüedad", r2(Decimal(12) * anios * base),
                      f"12 días × {num(anios)} años × {pesos(base)} ({nota}; mínimo {pesos(sm)})", "Art. 162, 485 y 486 LFT"))

    # ---- indemnizaciones
    con_indemnizacion = d.causa in ("despido_injustificado", "rescision_trabajador")
    if con_indemnizacion:
        ind.append(_c("tres_meses", "Indemnización constitucional (3 meses)", r2(Decimal(90) * sdi),
                      f"90 días × {pesos(sdi)} (salario integrado)", "Art. 123 A fr. XXII Constitución; art. 48, 50 fr. III y 52 LFT"))
        veinte = d.incluir_20_dias if d.incluir_20_dias is not None else d.causa == "rescision_trabajador"
        if veinte:
            ind.append(_c("veinte_dias", "20 días por año de servicio", r2(Decimal(20) * anios * sdi),
                          f"20 días × {num(anios)} años × {pesos(sdi)}", "Art. 50 fr. II, 49 y 52 LFT"))
        elif d.causa == "despido_injustificado":
            avisos.append("No se incluyeron los 20 días por año: proceden cuando el patrón se niega a reinstalar (art. 49 y 50). Actívelos si aplica.")
    elif d.incluir_20_dias:
        avisos.append("Los 20 días por año solo se calculan en despido injustificado o rescisión por causa del patrón.")
    if ind:
        secciones.append({"clave": "indemnizacion", "titulo": "Indemnización y prima de antigüedad", "conceptos": ind})

    # ---- salarios caídos (vencidos)
    caidos = d.incluir_salarios_caidos if d.incluir_salarios_caidos is not None else d.causa == "despido_injustificado"
    if caidos and d.causa != "despido_injustificado":
        avisos.append("Los salarios caídos solo se calculan en despido injustificado.")
        caidos = False
    if caidos:
        dias_c = max(0, (calc_al - d.fecha_baja).days)
        sc: list[dict] = []
        if dias_c == 0:
            avisos.append("Salarios caídos en cero: la fecha de cálculo no es posterior al despido.")
        elif d.fecha_baja < REFORMA_SALARIOS_CAIDOS:
            sc.append(_c("salarios_caidos", "Salarios caídos (sin tope, despido anterior a la reforma de 2012)", r2(Decimal(dias_c) * sdi),
                         f"{dias_c} días del {d.fecha_baja:%d/%m/%Y} al {calc_al:%d/%m/%Y} × {pesos(sdi)}", "Art. 48 LFT (texto anterior al 1/12/2012)"))
            avisos.append("Despido anterior al 1 de diciembre de 2012: verifique la fecha de presentación de la demanda; se aplicó el régimen anterior.")
        else:
            topados = min(dias_c, 365)
            sc.append(_c("salarios_caidos", "Salarios caídos (máximo 12 meses)", r2(Decimal(topados) * sdi),
                         f"{topados} días del {d.fecha_baja:%d/%m/%Y} al {calc_al:%d/%m/%Y}{' (tope de 12 meses)' if dias_c > 365 else ''} × {pesos(sdi)}",
                         "Art. 48 LFT"))
            if dias_c > 365:
                meses = r2(Decimal(dias_c - 365) / Decimal(30))
                base15 = r2(sdi * 30 * 15)
                sc.append(_c("intereses", "Intereses del 2 % mensual (después de 12 meses)", r2(base15 * Decimal("0.02") * meses),
                             f"{pesos(base15)} (15 meses de salario) × 2 % × {num(meses, 2)} meses", "Art. 48, tercer párrafo LFT"))
        if sc:
            secciones.append({"clave": "salarios_caidos", "titulo": "Salarios caídos", "conceptos": sc})

    # ---- horas extra
    if d.horas_extra:
        valor_hora = sd / JORNADAS[d.tipo_jornada]
        he: list[dict] = []
        hace_un_anio = _aniversario(d.fecha_baja, -1)
        prescritas = False
        for i, p in enumerate(d.horas_extra, 1):
            if p.hasta < p.desde:
                raise ErrorDatos(f"Horas extra, periodo {i}: la fecha final es anterior a la inicial.")
            if p.desde < hace_un_anio:
                prescritas = True
            for anio in range(p.desde.year, p.hasta.year + 1):
                a = max(p.desde, date(anio, 1, 1))
                b = min(p.hasta, date(anio, 12, 31))
                jornada, dobles_max = jornada_legal(anio)
                tope_tipo = TOPE_SEMANAL_TIPO[d.tipo_jornada]
                if tope_tipo:
                    jornada = min(jornada, tope_tipo)
                extra = max(CERO, p.horas_semana - Decimal(jornada))
                if extra == 0:
                    continue
                dobles = min(extra, Decimal(dobles_max))
                triples = extra - dobles
                semanas = Decimal((b - a).days + 1) / Decimal(7)
                imp = r2(semanas * valor_hora * (2 * dobles + 3 * triples))
                op = (f"{num(semanas, 2)} semanas × ({num(dobles, 2)} h × 2 + {num(triples, 2)} h × 3) × {pesos(valor_hora)} la hora"
                      f" — jornada legal {jornada} h/sem en {anio}, {num(p.horas_semana, 2)} h trabajadas")
                he.append(_c(f"horas_extra_{i}_{anio}", f"Horas extra del {a:%d/%m/%Y} al {b:%d/%m/%Y}", imp, op, "Art. 61, 66, 67 y 68 LFT (reforma DOF 1/5/2026)"))
        if prescritas:
            avisos.append("Hay horas extra de más de un año antes de la baja: pueden estar prescritas (art. 516 LFT).")
        if he:
            secciones.append({"clave": "horas_extra", "titulo": "Horas extra", "conceptos": he})
        else:
            avisos.append("Las horas capturadas no rebasan la jornada legal: no hay horas extra que pagar.")

    # ---- otros conceptos capturados por el abogado
    if d.otros:
        secciones.append({"clave": "otros", "titulo": "Otros conceptos", "conceptos": [
            _c(f"otro_{i}", o.concepto, r2(o.importe), "Capturado por el despacho", "—") for i, o in enumerate(d.otros, 1) if o.importe]})

    total = CERO
    for s in secciones:
        s["subtotal"] = txt(sum((Decimal(c["importe"]) for c in s["conceptos"]), CERO))
        total += Decimal(s["subtotal"])
    secciones = [s for s in secciones if s["conceptos"]]
    avisos.append("Estimación con importes brutos, antes de ISR. Revise cada concepto con las constancias del caso.")
    return {
        "causa": d.causa, "causa_nombre": CAUSAS[d.causa],
        "antiguedad": {"dias": dias_ant, "anios": num(anios), "anios_completos": completos, "dias_ultimo_anio": dias_aniv},
        "salarios": {"diario": txt(sd), "integrado": txt(sdi), "integrado_calculado": txt(sdi_calc), "factor": num(factor, 4),
                     "vacaciones_dias_anio": vac_actual, "minimo": txt(sm), "minimo_anio": sm_anio, "zona": d.zona,
                     "tope_prima": txt(sm * 2) if sm is not None else None},
        "fecha_calculo": calc_al.isoformat(),
        "secciones": secciones, "total": txt(total), "avisos": avisos,
    }


def tablas() -> dict:
    anios = sorted(set(range(2026, 2031)))
    return {
        "causas": [{"clave": k, "nombre": v} for k, v in CAUSAS.items()],
        "salarios_minimos": [{"anio": a, "general": g, "frontera": f} for a, (g, f) in sorted(SALARIOS_MINIMOS.items())],
        "jornadas": [{"anio": a, "semanal": jornada_legal(a)[0], "dobles": jornada_legal(a)[1]} for a in anios],
        "tipos_jornada": [{"clave": k, "horas": str(v)} for k, v in JORNADAS.items()],
    }
