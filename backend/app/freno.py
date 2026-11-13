"""Freno en memoria contra fuerza bruta en el acceso.

Dos contadores de intentos fallidos dentro de una ventana de tiempo:
- por IP + correo: frena a quien prueba contraseñas contra una cuenta;
- por IP: frena a quien prueba una contraseña contra muchas cuentas.

Deliberadamente NO hay un bloqueo por correo sin importar la IP: permitiría a cualquiera
dejar fuera a un usuario legítimo con unos cuantos intentos fallidos. Por eso es importante
que la IP sea la real (vea IP_CLIENTE_ENCABEZADO en config.py).

La memoria está acotada: las entradas vencidas se purgan y hay un tope de llaves.
Es por proceso; con varios procesos cada uno lleva su cuenta (suficiente para este MVP).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable


class Ventana:
    """Cuenta eventos por llave dentro de los últimos `segundos`."""

    def __init__(self, maximo: int, segundos: float, max_llaves: int = 10_000,
                 reloj: Callable[[], float] = time.monotonic):
        self.maximo, self.segundos, self.max_llaves, self.reloj = maximo, segundos, max_llaves, reloj
        self._eventos: dict[str, deque[float]] = {}
        self._candado = threading.Lock()

    def _vigentes(self, llave: str, ahora: float) -> deque[float] | None:
        cola = self._eventos.get(llave)
        if cola is None:
            return None
        while cola and ahora - cola[0] >= self.segundos:
            cola.popleft()
        if not cola:
            del self._eventos[llave]
            return None
        return cola

    def excedida(self, llave: str) -> bool:
        with self._candado:
            cola = self._vigentes(llave, self.reloj())
            return cola is not None and len(cola) >= self.maximo

    def registrar(self, llave: str) -> None:
        with self._candado:
            ahora = self.reloj()
            cola = self._vigentes(llave, ahora)
            if cola is None:
                if len(self._eventos) >= self.max_llaves:
                    self._purgar(ahora)
                cola = self._eventos[llave] = deque()
            cola.append(ahora)
            while len(cola) > self.maximo:  # no hace falta guardar más de `maximo` marcas por llave
                cola.popleft()

    def olvidar(self, llave: str) -> None:
        with self._candado:
            self._eventos.pop(llave, None)

    def _purgar(self, ahora: float) -> None:
        for llave in list(self._eventos):
            self._vigentes(llave, ahora)
        # Si aun así se rebasa el tope, se descartan las llaves con actividad más antigua.
        exceso = len(self._eventos) - self.max_llaves + 1
        if exceso > 0:
            for llave in sorted(self._eventos, key=lambda k: self._eventos[k][-1])[:exceso]:
                del self._eventos[llave]

    def __len__(self) -> int:
        return len(self._eventos)

    def clear(self) -> None:
        with self._candado:
            self._eventos.clear()


class FrenoAcceso:
    def __init__(self, por_cuenta: int = 8, por_ip: int = 40, segundos: float = 300,
                 segundos_ip: float = 900, reloj: Callable[[], float] = time.monotonic):
        self.cuenta = Ventana(por_cuenta, segundos, reloj=reloj)
        self.ip = Ventana(por_ip, segundos_ip, reloj=reloj)

    def bloqueado(self, ip: str, email: str) -> bool:
        return self.cuenta.excedida(f"{ip}|{email}") or self.ip.excedida(ip)

    def fallo(self, ip: str, email: str) -> None:
        self.cuenta.registrar(f"{ip}|{email}")
        self.ip.registrar(ip)

    def exito(self, ip: str, email: str) -> None:
        # Solo se perdona a la pareja IP+correo; los fallos de la IP contra otras cuentas siguen contando.
        self.cuenta.olvidar(f"{ip}|{email}")

    def clear(self) -> None:
        self.cuenta.clear()
        self.ip.clear()
