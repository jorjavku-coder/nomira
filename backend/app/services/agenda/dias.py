"""Cálculo ASISTIDO de plazos en días hábiles o naturales.

No es asesoría jurídica. El resultado depende de lo que el despacho capturó: la regla de cuándo surte
efectos la notificación, el tipo de días y el calendario del tribunal. Por eso:
- se guarda el DESGLOSE completo (qué días se contaron y cuáles se saltaron, y por qué);
- el plazo queda «sin validar» hasta que un abogado lo revisa y lo confirma.

Días de referencia que incluye Nomira: solo los de descanso obligatorio del artículo 74 de la Ley
Federal del Trabajo. Los periodos de vacaciones y los días que cada tribunal declara inhábiles los
captura el despacho desde el calendario oficial de ese tribunal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
SURTE_EFECTOS = {"mismo_dia": "El mismo día de la notificación",
                 "dia_habil_siguiente": "Al día hábil siguiente de la notificación"}
TIPOS_DIAS = {"habiles": "Días hábiles", "naturales": "Días naturales"}
MAX_DIAS = 400


def _n_lunes(anio: int, mes: int, n: int) -> date:
    d = date(anio, mes, 1)
    d += timedelta(days=(0 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def descanso_lft(anio: int) -> dict[date, str]:
    """Días de descanso obligatorio, art. 74 LFT (sin la jornada electoral, que se captura aparte)."""
    dias = {
        date(anio, 1, 1): "1 de enero (art. 74 LFT)",
        _n_lunes(anio, 2, 1): "Primer lunes de febrero, por el 5 de febrero (art. 74 LFT)",
        _n_lunes(anio, 3, 3): "Tercer lunes de marzo, por el 21 de marzo (art. 74 LFT)",
        date(anio, 5, 1): "1 de mayo (art. 74 LFT)",
        date(anio, 9, 16): "16 de septiembre (art. 74 LFT)",
        _n_lunes(anio, 11, 3): "Tercer lunes de noviembre, por el 20 de noviembre (art. 74 LFT)",
        date(anio, 12, 25): "25 de diciembre (art. 74 LFT)",
    }
    if anio >= 2024 and (anio - 2024) % 6 == 0:
        dias[date(anio, 10, 1)] = "1 de octubre, transmisión del Poder Ejecutivo Federal (art. 74 LFT)"
    return dias


@dataclass
class Calendario:
    """Reglas de un calendario ya resueltas (sin base de datos)."""
    nombre: str = "Sin calendario"
    semana_inhabil: tuple[int, ...] = (5, 6)
    lft: bool = True
    inhabiles: dict[date, str] = field(default_factory=dict)
    habilitados: dict[date, str] = field(default_factory=dict)

    def motivo_inhabil(self, d: date) -> str | None:
        """None si el día es hábil; si no, el motivo."""
        if d in self.habilitados:
            return None
        if d in self.inhabiles:
            return self.inhabiles[d]
        if self.lft:
            m = descanso_lft(d.year).get(d)
            if m:
                return m
        if d.weekday() in self.semana_inhabil:
            return DIAS_SEMANA[d.weekday()].capitalize()
        return None

    def habil(self, d: date) -> bool:
        return self.motivo_inhabil(d) is None

    def siguiente_habil(self, d: date, saltados: list | None = None) -> date:
        d = d + timedelta(days=1)
        for _ in range(MAX_DIAS):
            m = self.motivo_inhabil(d)
            if m is None:
                return d
            if saltados is not None:
                saltados.append({"fecha": d.isoformat(), "motivo": m})
            d += timedelta(days=1)
        raise ValueError("No se encontró un día hábil en el calendario.")


def calcular(cal: Calendario, notificacion: date, dias: int, tipo_dias: str, surte_efectos: str,
             recorrer_inhabil: bool = True) -> dict:
    """Plazo de `dias` contados a partir del día hábil siguiente a que surte efectos la notificación."""
    if tipo_dias not in TIPOS_DIAS:
        raise ValueError("Tipo de días inválido.")
    if surte_efectos not in SURTE_EFECTOS:
        raise ValueError("Indique cuándo surte efectos la notificación.")
    if not 1 <= dias <= MAX_DIAS:
        raise ValueError(f"Los días deben estar entre 1 y {MAX_DIAS}.")
    pasos, saltados = [], []
    pasos.append(f"Notificación: {notificacion.isoformat()} ({DIAS_SEMANA[notificacion.weekday()]}).")
    if surte_efectos == "mismo_dia":
        efectos = notificacion
    else:
        efectos = cal.siguiente_habil(notificacion, saltados)
    pasos.append(f"Surte efectos: {efectos.isoformat()} ({SURTE_EFECTOS[surte_efectos].lower()}).")
    inicio = cal.siguiente_habil(efectos, saltados)
    pasos.append(f"Primer día del plazo: {inicio.isoformat()} (día hábil siguiente a que surte efectos).")
    contados = []
    d = inicio
    if tipo_dias == "habiles":
        while True:
            m = cal.motivo_inhabil(d)
            if m is None:
                contados.append(d.isoformat())
                if len(contados) == dias:
                    break
            else:
                saltados.append({"fecha": d.isoformat(), "motivo": m})
            d += timedelta(days=1)
            if (d - inicio).days > MAX_DIAS * 3:
                raise ValueError("El calendario no tiene suficientes días hábiles.")
        vence = d
    else:
        contados = [(inicio + timedelta(days=i)).isoformat() for i in range(dias)]
        vence = inicio + timedelta(days=dias - 1)
        m = cal.motivo_inhabil(vence)
        if m and recorrer_inhabil:
            saltados.append({"fecha": vence.isoformat(), "motivo": m})
            original = vence
            vence = cal.siguiente_habil(vence, saltados)
            pasos.append(f"El día {dias} ({original.isoformat()}) es inhábil ({m}); se recorre al siguiente día hábil.")
    pasos.append(f"Se cuentan {dias} {TIPOS_DIAS[tipo_dias].lower()}: vence el {vence.isoformat()} ({DIAS_SEMANA[vence.weekday()]}).")
    vistos, unicos = set(), []
    for s in saltados:
        if s["fecha"] not in vistos:
            vistos.add(s["fecha"])
            unicos.append(s)
    return {"notificacion": notificacion.isoformat(), "surte_efectos": surte_efectos, "efectos": efectos.isoformat(),
            "inicio": inicio.isoformat(), "dias": dias, "tipo_dias": tipo_dias, "recorrer_inhabil": recorrer_inhabil,
            "vence": vence.isoformat(), "contados": contados, "saltados": unicos, "pasos": pasos, "calendario": cal.nombre,
            "aviso": "Cálculo asistido con el calendario capturado en Nomira. Debe validarlo un abogado conforme a la ley "
                     "aplicable y al calendario oficial del tribunal."}
