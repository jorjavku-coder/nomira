"""CURP y NSS: revisión LOCAL de formato y dígito verificador. No es una consulta oficial: una CURP
con formato válido puede no existir o no corresponder a la persona."""
from __future__ import annotations

import re

_RE_CURP = re.compile(r"^[A-Z][AEIOUX][A-Z]{2}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[HMX]"
                      r"(AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)"
                      r"[B-DF-HJ-NP-TV-Z]{3}[0-9A-Z]\d$")
_DICC = "0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"


def limpiar(v: str | None) -> str:
    return re.sub(r"[\s-]", "", (v or "")).upper()


def revisar_curp(curp: str) -> dict:
    """{"valida_formato", "detalle"}: estructura (18 caracteres, fecha, sexo, entidad) y dígito verificador."""
    c = limpiar(curp)
    if len(c) != 18:
        return {"valida_formato": False, "detalle": f"La CURP debe tener 18 caracteres (tiene {len(c)})."}
    if not _RE_CURP.match(c):
        return {"valida_formato": False, "detalle": "La estructura no corresponde a una CURP (letras, fecha, sexo o entidad)."}
    suma = sum(_DICC.index(ch) * (18 - i) for i, ch in enumerate(c[:17]))
    digito = (10 - suma % 10) % 10
    if int(c[17]) != digito:
        return {"valida_formato": False, "detalle": "El dígito verificador no coincide: puede haber un error de captura."}
    return {"valida_formato": True, "detalle": "Formato y dígito verificador correctos (revisión local, no es una consulta oficial)."}


def revisar_nss(nss: str) -> dict:
    """NSS del IMSS: 11 dígitos; el último se calcula con el algoritmo de Luhn."""
    n = re.sub(r"\D", "", nss or "")
    if len(n) != 11:
        return {"valida_formato": False, "detalle": f"El NSS debe tener 11 dígitos (tiene {len(n)})."}
    suma = 0
    for i, ch in enumerate(n[:10]):
        d = int(ch) * (2 if i % 2 else 1)
        suma += d - 9 if d > 9 else d
    if (10 - suma % 10) % 10 != int(n[10]):
        return {"valida_formato": False, "detalle": "El dígito verificador no coincide: puede haber un error de captura."}
    return {"valida_formato": True, "detalle": "Formato y dígito verificador correctos (revisión local)."}


def pista_curp(c: str) -> str:
    c = limpiar(c)
    return f"{c[:4]}…{c[-2:]}" if len(c) >= 6 else "…"


def pista_nss(n: str) -> str:
    n = re.sub(r"\D", "", n or "")
    return f"…{n[-4:]}" if len(n) >= 4 else "…"


def telefono(v: str | None) -> str | None:
    """Solo dígitos con lada de país. 10 dígitos mexicanos → 52 + número."""
    d = re.sub(r"\D", "", v or "")
    if not d:
        return None
    if len(d) == 10:
        d = "52" + d
    return d if 11 <= len(d) <= 15 else None


def enmascarar_telefono(t: str | None) -> str | None:
    return f"•••• {t[-4:]}" if t else None
