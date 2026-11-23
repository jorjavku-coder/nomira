"""Alta de clientes sin capturar: lectura de la Constancia de Situación Fiscal (PDF del SAT) e importación de Excel/CSV.

La lectura siempre devuelve una PROPUESTA: el usuario la revisa y la guarda. Nada se guarda solo."""
from __future__ import annotations

import csv
import io
import re
import unicodedata

from openpyxl import Workbook, load_workbook

RFC_LIBRE = re.compile(r"\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b")
CURP_LIBRE = re.compile(r"\b([A-Z][AEIOUX][A-Z]{2}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d)\b")
CP = re.compile(r"\b(\d{5})\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _plano(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip().lower()


def texto_pdf(contenido: bytes, paginas: int = 5) -> str:
    import pymupdf
    with pymupdf.open(stream=contenido, filetype="pdf") as doc:
        return "\n".join(doc[i].get_text() for i in range(min(len(doc), paginas)))


def _valor(lineas: list[str], *etiquetas: str) -> str | None:
    """Busca «Etiqueta: valor» en la misma línea o, si va vacío, en la línea siguiente."""
    planas = [_plano(x) for x in lineas]
    for et in etiquetas:
        e = _plano(et).rstrip(":")
        for i, p in enumerate(planas):
            if p.startswith(e + ":") or p == e:
                resto = lineas[i].split(":", 1)[1].strip() if ":" in lineas[i] else ""
                if resto:
                    return resto
                for sig in lineas[i + 1:i + 3]:
                    s = sig.strip()
                    if ":" in s:  # la siguiente ya es otra etiqueta: este dato viene vacío
                        break
                    if s:
                        return s
    return None


def leer_constancia(texto: str) -> dict:
    """Datos de la Constancia de Situación Fiscal / Cédula de Identificación Fiscal del SAT."""
    lineas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    plano = _plano(texto)
    es_csf = "situacion fiscal" in plano or "identificacion fiscal" in plano or "servicio de administracion tributaria" in plano
    rfc = _valor(lineas, "RFC")
    rfc = (RFC_LIBRE.search(rfc.upper()) or RFC_LIBRE.search(texto.upper())) if rfc else RFC_LIBRE.search(texto.upper())
    rfc = rfc.group(1) if rfc else None
    curp = CURP_LIBRE.search(texto.upper())
    razon = _valor(lineas, "Denominación/Razón Social", "Denominación o Razón Social", "Razón Social")
    regimen_capital = _valor(lineas, "Régimen Capital")
    nombres, ap1, ap2 = _valor(lineas, "Nombre (s)", "Nombre(s)"), _valor(lineas, "Primer Apellido"), _valor(lineas, "Segundo Apellido")
    moral = bool(razon) or (rfc is not None and len(rfc) == 12)
    if moral:
        nombre = " ".join(x for x in (razon, regimen_capital) if x) or None
    else:
        nombre = " ".join(x for x in (nombres, ap1, ap2) if x) or None
    via = " ".join(x for x in (_valor(lineas, "Tipo de Vialidad"), _valor(lineas, "Nombre de Vialidad")) if x)
    ext, inte = _valor(lineas, "Número Exterior"), _valor(lineas, "Número Interior")
    partes = [via + (f" {ext}" if ext else "") + (f" int. {inte}" if inte else "")] if via else []
    for et in ("Nombre de la Colonia", "Nombre de la Localidad", "Nombre del Municipio o Demarcación Territorial", "Nombre de la Entidad Federativa"):
        v = _valor(lineas, et)
        if v and v not in partes:
            partes.append(v)
    cp = _valor(lineas, "Código Postal")
    cp = CP.search(cp).group(1) if cp and CP.search(cp) else None
    regimen = None
    for i, ln in enumerate(lineas):
        p = _plano(ln)
        if p.startswith("regimen") and not p.startswith("regimen capital") and "fecha" not in p and ":" not in ln and len(p) > 12:
            regimen = ln
            break
        if p in ("regimenes:", "regimenes") or p.startswith("regimenes"):
            for sig in lineas[i + 1:i + 6]:
                ps = _plano(sig)
                if ps.startswith("regimen") and "fecha" not in ps and len(ps) > 12:
                    regimen = re.sub(r"\s*\d{2}/\d{2}/\d{4}.*$", "", sig).strip()
                    break
            if regimen:
                break
    correo = _valor(lineas, "Correo Electrónico")
    correo = EMAIL.search(correo).group(0).lower() if correo and EMAIL.search(correo) else None
    datos = {"tipo": "moral" if moral else "fisica", "nombre": nombre, "rfc": rfc, "curp": curp.group(1) if curp and not moral else None,
             "domicilio": ", ".join(p for p in partes if p) or None, "codigo_postal": cp, "regimen_fiscal": regimen, "email": correo}
    encontrados = [k for k, v in datos.items() if v and k != "tipo"]
    return {"es_constancia": es_csf, "datos": datos, "encontrados": encontrados}


# ------------------------------------------------------------------ Excel / CSV

COLUMNAS = {
    "nombre": ("nombre", "nombre completo", "razon social", "cliente", "denominacion"),
    "tipo": ("tipo", "tipo de persona", "persona"),
    "rfc": ("rfc",),
    "curp": ("curp",),
    "email": ("email", "correo", "correo electronico", "e-mail"),
    "telefono": ("telefono", "celular", "tel", "whatsapp"),
    "domicilio": ("domicilio", "direccion"),
    "codigo_postal": ("cp", "codigo postal", "c.p."),
    "regimen_fiscal": ("regimen", "regimen fiscal"),
    "contacto": ("contacto", "persona de contacto"),
    "notas": ("notas", "observaciones", "comentarios"),
}


def plantilla() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    ws.append(["Nombre o razón social", "Tipo (física/moral)", "RFC", "CURP", "Correo", "Teléfono", "Domicilio", "CP", "Régimen fiscal", "Contacto", "Notas"])
    ws.append(["Juana Ejemplo Pérez", "física", "", "", "juana@ejemplo.com", "5512345678", "Calle 1, Col. Centro, Toluca", "50000", "", "", "Ejemplo: borre esta fila"])
    for col, ancho in zip("ABCDEFGHIJK", (34, 16, 16, 22, 28, 16, 40, 8, 30, 24, 30)):
        ws.column_dimensions[col].width = ancho
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def _filas_archivo(nombre: str, contenido: bytes) -> list[list]:
    if nombre.lower().endswith((".csv", ".txt")):
        texto = contenido.decode("utf-8-sig", errors="replace")
        try:
            dialecto = csv.Sniffer().sniff(texto[:2000], delimiters=",;\t")
        except csv.Error:
            dialecto = csv.excel
        return [r for r in csv.reader(io.StringIO(texto), dialecto)]
    wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True)]


def leer_tabla(nombre: str, contenido: bytes, max_filas: int = 2000) -> tuple[list[dict], list[str]]:
    filas = [r for r in _filas_archivo(nombre, contenido) if any(str(c or "").strip() for c in r)]
    if not filas:
        return [], ["El archivo está vacío."]
    enc = [_plano(str(c or "")).rstrip(":") for c in filas[0]]
    mapa = {}
    for campo, alias in COLUMNAS.items():
        for i, e in enumerate(enc):
            if e in alias or any(e.startswith(a) for a in alias if len(a) > 3):
                mapa.setdefault(campo, i)
                break
    if "nombre" not in mapa:
        return [], ["No encontramos la columna «Nombre». Use la plantilla de Nomira."]
    r = []
    for fila in filas[1:max_filas + 1]:
        d = {}
        for campo, i in mapa.items():
            v = fila[i] if i < len(fila) else None
            v = "" if v is None else str(v).strip()
            if campo in ("telefono", "codigo_postal") and v.endswith(".0"):
                v = v[:-2]
            if campo == "codigo_postal" and v.isdigit() and len(v) == 4:  # Excel quita el cero inicial
                v = "0" + v
            d[campo] = v
        if d.get("nombre"):
            t = _plano(d.get("tipo", ""))
            d["tipo"] = "moral" if t.startswith("moral") or t == "m" else "fisica"
            r.append(d)
    avisos = [f"Se leyeron solo las primeras {max_filas} filas."] if len(filas) - 1 > max_filas else []
    return r, avisos
