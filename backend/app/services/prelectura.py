"""Prelectura: lee uno o varios PDF SIN guardarlos y propone los datos del expediente
(trabajador, identificador laboral y periodo). Es solo una propuesta que la persona confirma."""
from __future__ import annotations

from collections import Counter
from datetime import date

from ..config import ajustes
from .calculo import clave_q, etiqueta, limites, quincena_de, quincenas_esperadas
from .extraccion import abrir_pdf, extraer_pagina
from .lector_recibos import clasificar_pagina, leer_recibo


def rango_quincenal(periodos: list[tuple[date, date]]) -> tuple[date, date] | None:
    """Del primer día de la quincena más antigua al último de la más reciente."""
    qs = sorted(q for q in (quincena_de(i, f) for i, f in periodos) if q)
    return (limites(qs[0])[0], limites(qs[-1])[1]) if qs else None


def analizar(archivos: list[tuple[str, str]]) -> dict:
    """archivos: [(nombre, ruta)]. No persiste nada."""
    recibos, por_archivo, avisos = [], [], []
    for nombre, ruta in archivos:
        info = {"nombre": nombre, "paginas": 0, "recibos": 0, "informativas": 0, "sin_clasificar": 0, "ocr": 0}
        with abrir_pdf(ruta) as pdf:
            if pdf.page_count > ajustes().max_paginas_pdf:
                raise ValueError(f"«{nombre}» excede {ajustes().max_paginas_pdf} páginas.")
            info["paginas"] = pdf.page_count
            for n, pagina in enumerate(pdf, start=1):
                pe = extraer_pagina(pagina, n)
                info["ocr"] += pe.metodo == "ocr"
                tipo = clasificar_pagina(pe)
                r = leer_recibo(pe) if tipo == "recibo" else None
                if r:
                    info["recibos"] += 1
                    recibos.append(r)
                elif tipo == "informativa":
                    info["informativas"] += 1
                else:
                    info["sin_clasificar"] += 1
        por_archivo.append(info)

    # Agrupa por trabajador: la clave de servidor manda; si no se leyó, el nombre.
    grupos: dict[str, list] = {}
    for r in recibos:
        grupos.setdefault(r.clave_servidor or (r.trabajador_nombre or "").strip().upper() or "?", []).append(r)
    trabajadores = []
    for llave, rs in grupos.items():
        nombres = Counter(r.trabajador_nombre for r in rs if r.trabajador_nombre)
        claves = Counter(r.clave_servidor for r in rs if r.clave_servidor)
        rango = rango_quincenal([(r.periodo_inicio, r.periodo_fin) for r in rs if r.periodo_inicio])
        qs = {quincena_de(r.periodo_inicio, r.periodo_fin) for r in rs} - {None}
        esperadas = quincenas_esperadas(*rango) if rango else []
        trabajadores.append({
            "identificado": llave != "?",
            "nombre": nombres.most_common(1)[0][0] if nombres else None,
            "identificador_laboral": claves.most_common(1)[0][0] if claves else None,
            "plazas": sorted({r.plaza for r in rs if r.plaza}),
            "recibos": len(rs),
            "recibos_sin_periodo": sum(1 for r in rs if not quincena_de(r.periodo_inicio, r.periodo_fin)),
            "periodo_inicio": rango[0].isoformat() if rango else None,
            "periodo_fin": rango[1].isoformat() if rango else None,
            "quincenas_en_periodo": len(esperadas),
            "quincenas_con_recibo": len(qs),
            "quincenas_sin_recibo": [{"quincena": clave_q(q), "etiqueta": etiqueta(q)} for q in esperadas if q not in qs],
        })
    trabajadores.sort(key=lambda t: (-t["identificado"], -t["recibos"]))

    if not recibos:
        avisos.append("No se detectó ningún recibo en los archivos. Capture los datos a mano.")
    identificados = [t for t in trabajadores if t["identificado"]]
    if len(identificados) > 1:
        avisos.append(f"Los archivos contienen recibos de {len(identificados)} trabajadores. Se propone el que tiene "
                      "más recibos; los demás no se sumarán en este expediente.")
    if any(not t["identificado"] for t in trabajadores):
        n = sum(t["recibos"] for t in trabajadores if not t["identificado"])
        avisos.append(f"En {n} recibo(s) no se pudo leer el trabajador; quedarán pendientes de revisión.")
    sugerido = identificados[0] if identificados else None
    if sugerido:
        if sugerido["recibos_sin_periodo"]:
            avisos.append(f"{sugerido['recibos_sin_periodo']} recibo(s) sin periodo legible: no se usaron para "
                          "proponer las fechas.")
        if sugerido["quincenas_sin_recibo"]:
            avisos.append(f"Dentro del periodo detectado hay {len(sugerido['quincenas_sin_recibo'])} quincena(s) sin "
                          "recibo; se reportarán como faltantes.")
        if not sugerido["periodo_inicio"]:
            avisos.append("No se pudo leer ningún periodo de pago. Capture las fechas a mano.")
    return {"archivos": por_archivo, "trabajadores": trabajadores, "sugerencia": sugerido, "avisos": avisos,
            "total_recibos": len(recibos)}
