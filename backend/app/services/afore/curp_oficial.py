"""Adaptador OPCIONAL para una API oficial de CURP. Deshabilitado hasta que existan credenciales
(CURP_API_URL y CURP_API_KEY, solo en el servidor) Y la plataforma autorice a la organización.
Nunca se simula una consulta: sin configuración se responde «Validación oficial no configurada»."""
from __future__ import annotations

import httpx

from ...config import ajustes


class NoConfigurada(Exception):
    pass


def disponible(cfg) -> tuple[bool, str]:
    a = ajustes()
    if not (a.curp_api_url and a.curp_api_key):
        return False, "Validación oficial no configurada: faltan las credenciales del servicio oficial en el servidor."
    if not (cfg and cfg.curp_oficial_autorizado):
        return False, "Validación oficial no configurada: su organización aún no está autorizada para consultarla."
    return True, "Disponible"


def consultar(cfg, curp: str) -> dict:
    """Consulta la CURP en el servicio configurado. El contrato exacto depende del proveedor autorizado:
    se espera JSON con «estatus» y, opcionalmente, «coincide»."""
    ok, motivo = disponible(cfg)
    if not ok:
        raise NoConfigurada(motivo)
    a = ajustes()
    r = httpx.post(a.curp_api_url, json={"curp": curp}, headers={"Authorization": f"Bearer {a.curp_api_key}"}, timeout=20)
    r.raise_for_status()
    datos = r.json()
    return {"estatus": str(datos.get("estatus") or datos.get("status") or "sin dato")[:60]}
