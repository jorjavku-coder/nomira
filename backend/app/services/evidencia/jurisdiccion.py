"""Catálogo de jurisdicción para asuntos en México. Los campos son opcionales: no todos aplican."""
from __future__ import annotations

from .lectura import normalizar

AMBITOS = {"federal": "Federal", "local": "Local"}
ENTIDADES = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua", "Ciudad de México",
    "Coahuila", "Colima", "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán",
    "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa",
    "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
]
_SINONIMOS = {"cdmx": "Ciudad de México", "df": "Ciudad de México", "distrito federal": "Ciudad de México",
              "edomex": "Estado de México", "mexico": "Estado de México", "edo. de mexico": "Estado de México",
              "coahuila de zaragoza": "Coahuila", "michoacan de ocampo": "Michoacán", "veracruz de ignacio de la llave": "Veracruz"}
_POR_NOMBRE = {normalizar(e): e for e in ENTIDADES} | _SINONIMOS


def entidad_de(texto: str | None) -> str | None:
    """Solo si el texto ES una entidad (no se adivina a partir de frases más largas)."""
    if not texto:
        return None
    return _POR_NOMBRE.get(normalizar(texto).strip(" .,"))


def texto(a) -> str | None:
    """Jurisdicción para mostrar: los campos nuevos y, si no los hay, lo que se capturó antes."""
    partes = [AMBITOS.get(a.ambito or "", None), a.entidad_federativa, a.municipio_distrito, a.organo]
    partes = [p for p in partes if p]
    if a.expediente_judicial:
        partes.append(f"Exp. {a.expediente_judicial}")
    return " · ".join(partes) or a.jurisdiccion
