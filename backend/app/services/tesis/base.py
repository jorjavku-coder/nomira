"""Biblioteca de tesis del Semanario Judicial de la Federación (SJF).

Fuentes oficiales, en este orden de preferencia:
1. Repositorio de datos abiertos de la SCJN (API JSON). Ver ``repositorio.py``.
2. Archivos que una persona descarga de la SCJN con su navegador y sube en el panel de Nomira:
   - el PDF semanal «Tesis publicación semanal» que publica la SCJN, o
   - archivos JSON (o un ZIP con varios) del Repositorio.

Cada tesis guarda su registro digital: con él se arma la liga oficial al SJF, que es la fuente que el abogado debe consultar.
"""
from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ... import models as m

SJF = "https://sjf2.scjn.gob.mx/detalle/tesis/{registro}"
MAX_IMPORTACION = 60 * 1024 * 1024
_SIN_ACENTO = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuAEIOUU")


def enlace(registro: int) -> str:
    return SJF.format(registro=int(registro))


def plano(t: str) -> str:
    return (t or "").translate(_SIN_ACENTO).lower()


def _limpio(v, n: int | None = None) -> str | None:
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        v = ", ".join(str(x) for x in v if x)
    v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v)).strip()
    return (v[:n] if n else v) or None


MATERIAS = ["Constitucional", "Común", "Administrativa", "Civil", "Penal", "Laboral", "Familiar"]
INSTANCIAS = {"pleno": ("Pleno de la Suprema Corte", "Pleno"), "primera": ("Primera Sala", "Primera Sala"), "segunda": ("Segunda Sala", "Segunda Sala"),
              "regionales": ("Plenos Regionales", "Plenos Regionales"), "circuito": ("Plenos de Circuito", "Plenos de Circuito"),
              "colegiados": ("Tribunales Colegiados", "Colegiados")}


def anio_de(publicada: str | None, clave: str | None) -> int | None:
    """Año de publicación: de la nota («Esta tesis se publicó el … de 2026») o, si no, del número de la tesis («1a./J. 10/2024»)."""
    for texto, rx in ((publicada, r"\b(19[0-9]{2}|20[0-9]{2})\b"), (clave, r"/\s*(19[0-9]{2}|20[0-9]{2})\b")):
        x = re.search(rx, texto or "")
        if x:
            return int(x.group(1))
    return None


def tipo_normal(v: str | None) -> str | None:
    t = plano(v or "")
    if "juris" in t:
        return "jurisprudencia"
    if "aislada" in t:
        return "aislada"
    return None


# ------------------------------------------------------------------ JSON del Repositorio (nombres de campo tolerantes)

_CLAVES = {
    "registro": ("registrodigital", "registro", "ius", "numregistro", "idtesis", "id"),
    "rubro": ("rubro", "rubrotitulosubtitulo", "titulo", "title"),
    "texto": ("texto", "contenido", "text", "cuerpo"),
    "precedentes": ("precedentes", "precedente"),
    "clave": ("tesis", "clavetesis", "numeroidentificacion", "numerodeidentificacion", "identificacion"),
    "tipo": ("tipotesis", "tipo", "tipodetesis"),
    "epoca": ("epoca", "época"),
    "instancia": ("instancia",),
    "organo": ("organojuris", "organo", "órgano", "organojurisdiccional"),
    "materias": ("materias", "materia"),
    "fuente": ("fuente", "localizacion"),
    "publicada": ("notapublicacion", "notadepublicacion", "fechapublicacion", "publicacion"),
    "huella_oficial": ("sha256", "hash", "huella", "certificado", "certificadodigital"),
}


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def _buscar(obj: dict, nombres: tuple[str, ...]):
    idx = {re.sub(r"[^a-z0-9]", "", _sin_acentos(str(k).lower())): v for k, v in obj.items()}
    for n in nombres:
        if n in idx and idx[n] not in (None, "", []):
            return idx[n]
    return None


def _materias(v):
    """«[Penal, Común]» (CSV del Repositorio) o ["Penal","Común"] (JSON) → «Penal, Común»."""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, str):
        return v.strip().strip("[]").replace('"', "")
    return v


def desde_json(obj: dict) -> dict | None:
    """Convierte un objeto JSON del Repositorio (o equivalente) a los campos de la biblioteca. None si no es una tesis."""
    if not isinstance(obj, dict):
        return None
    for envoltura in ("tesis", "data", "documento"):  # algunas respuestas vienen envueltas
        if isinstance(obj.get(envoltura), dict):
            obj = obj[envoltura]
    reg = _buscar(obj, _CLAVES["registro"])
    try:
        reg = int(str(reg).strip())
    except (TypeError, ValueError):
        return None
    d = {k: _buscar(obj, v) for k, v in _CLAVES.items() if k != "registro"}
    if not d["rubro"] or not d["texto"]:
        return None
    return {"registro": reg, "rubro": _limpio(d["rubro"]), "texto": _limpio(d["texto"]), "precedentes": _limpio(d["precedentes"]),
            "clave": _limpio(d["clave"], 120), "tipo": tipo_normal(_limpio(d["tipo"])), "epoca": _limpio(d["epoca"], 30),
            "instancia": _limpio(d["instancia"], 200), "organo": _limpio(d["organo"], 300), "materias": _limpio(_materias(d["materias"]), 200),
            "fuente": _limpio(d["fuente"], 300), "publicada": _limpio(d["publicada"], 200), "huella_oficial": _limpio(d["huella_oficial"], 128)}


# ------------------------------------------------------------------ PDF semanal de la SCJN

_PIE = re.compile(r"^\s*(Pág\.\s*\d+\s*de\s*\d+.*|Fecha de impresión.*|Semanario Judicial de la Federación\s*)$", re.I)
_MARCA = re.compile(r"(?m)^\s*Registro digital:\s*(\d{5,8})\s*$")
_META = {
    "instancia": re.compile(r"^\s*Instancia:\s*(.+)$", re.I),
    "materias": re.compile(r"^\s*Materias?\s*\(s\)\s*:\s*(.+)$", re.I),
    "clave": re.compile(r"^\s*Tesis:\s*(.+)$", re.I),
    "tipo": re.compile(r"^\s*Tipo:\s*(.+)$", re.I),
    "fuente": re.compile(r"^\s*Fuente:\s*(.+)$", re.I),
    "epoca": re.compile(r"^\s*((?:Primera|Segunda|Tercera|Cuarta|Quinta|Sexta|Séptima|Octava|Novena|Décima|Undécima|Duodécima)\s+Época)\s*$", re.I),
}


def _es_mayusculas(linea: str) -> bool:
    letras = [c for c in linea if c.isalpha()]
    return len(letras) >= 3 and sum(c.isupper() for c in letras) / len(letras) > 0.9


def desde_pdf(contenido: bytes) -> list[dict]:
    """Separa el PDF semanal de tesis de la SCJN en tesis, usando cada «Registro digital: N» como inicio."""
    import pymupdf

    with pymupdf.open(stream=contenido, filetype="pdf") as doc:
        lineas = [ln for p in doc for ln in p.get_text().splitlines()]
    texto = "\n".join(ln for ln in lineas if not _PIE.match(ln))
    marcas = list(_MARCA.finditer(texto))
    tesis = []
    for i, mk in enumerate(marcas):
        bloque = texto[mk.end(): marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)]
        meta: dict = {}
        resto = []
        for ln in bloque.splitlines():
            for k, rx in _META.items():
                x = rx.match(ln)
                if x and k not in meta:
                    meta[k] = x.group(1).strip()
                    break
            else:
                if ln.strip() and ln.strip() not in ("Tesis", "TESIS"):  # encabezado de cada ficha en el PDF semanal
                    resto.append(ln.strip())
        rubro = []
        while resto and _es_mayusculas(resto[0]):
            rubro.append(resto.pop(0))
        cuerpo = "\n".join(resto)
        cuerpo = re.sub(r"(?<![.:;])\n(?=[a-záéíóúñ(])", " ", cuerpo)  # une renglones cortados por el PDF
        publicada = re.search(r"Esta tesis se publicó[^\n]*", cuerpo)
        if not rubro or len(cuerpo) < 50:
            continue
        tesis.append({"registro": int(mk.group(1)), "rubro": " ".join(rubro), "texto": cuerpo.strip(), "precedentes": None,
                      "clave": _limpio(meta.get("clave"), 120), "tipo": tipo_normal(meta.get("tipo")), "epoca": _limpio(meta.get("epoca"), 30),
                      "instancia": _limpio(meta.get("instancia"), 200), "organo": None, "materias": _limpio(meta.get("materias"), 200),
                      "fuente": _limpio(meta.get("fuente"), 300), "publicada": _limpio(publicada.group(0), 200) if publicada else None,
                      "huella_oficial": None})
    return tesis


# ------------------------------------------------------------------ guardar e importar

def guardar(db: Session, datos: list[dict], origen: str, ref: str | None) -> int:
    """Inserta o actualiza por registro digital. Devuelve cuántas se guardaron."""
    n = 0
    ahora = datetime.now(timezone.utc)
    for d in datos:
        fila = {**d, "anio": anio_de(d.get("publicada"), d.get("clave")), "origen": origen, "origen_ref": (ref or "")[:300] or None, "actualizado_en": ahora}
        q = insert(m.JTesis).values(**fila)
        db.execute(q.on_conflict_do_update(index_elements=[m.JTesis.registro], set_={k: q.excluded[k] for k in fila if k != "registro"}))
        n += 1
    return n


class ArchivoNoValido(Exception):
    pass


def leer_archivo(nombre: str, contenido: bytes) -> tuple[list[dict], str]:
    """Devuelve (tesis, origen). Acepta PDF semanal, JSON (objeto, lista o una tesis por renglón) o ZIP con varios."""
    if len(contenido) > MAX_IMPORTACION:
        raise ArchivoNoValido("El archivo pesa más de 60 MB. Divídalo.")
    if contenido.startswith(b"%PDF"):
        return desde_pdf(contenido), "pdf_semanal"
    if contenido.startswith(b"PK"):
        todas: list[dict] = []
        hubo_csv = False
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            for info in z.infolist()[:5000]:
                if info.is_dir() or info.file_size > MAX_IMPORTACION:
                    continue
                datos = z.read(info)
                nombre_arch = info.filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
                if nombre_arch.endswith(".csv"):
                    todas += _csv(datos)
                    hubo_csv = True
                elif nombre_arch.endswith((".json", ".jsonl", ".txt")) or datos[:1] in (b"{", b"["):
                    todas += _json(datos)
                elif datos.startswith(b"%PDF") and "acuse" not in nombre_arch:  # el acuse firmado de la descarga no trae tesis
                    todas += desde_pdf(datos)
        return todas, "csv" if hubo_csv else "json"
    if nombre.lower().endswith(".csv") or contenido.lstrip(b"\xef\xbb\xbf")[:16].lower().startswith(b"registro digital"):
        return _csv(contenido), "csv"
    return _json(contenido), "json"


def _csv(datos: bytes) -> list[dict]:
    """CSV que exporta el Repositorio de la SCJN («Descargar» en bicentenario.scjn.gob.mx/repositorio-scjn/sjf)."""
    import csv

    csv.field_size_limit(10_000_000)
    t = datos.decode("utf-8-sig", errors="replace")
    filas = csv.DictReader(io.StringIO(t))
    return [x for x in (desde_json(dict(f)) for f in filas) if x]


def _json(datos: bytes) -> list[dict]:
    t = datos.decode("utf-8-sig", errors="replace").strip()
    objetos: list = []
    try:
        j = json.loads(t)
        if isinstance(j, dict):
            for k in ("tesis", "data", "resultados", "items", "documentos"):
                if isinstance(j.get(k), list):
                    j = j[k]
                    break
        objetos = j if isinstance(j, list) else [j]
    except json.JSONDecodeError:
        for ln in t.splitlines():  # una tesis por renglón
            try:
                objetos.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return [x for x in (desde_json(o) for o in objetos) if x]


# ------------------------------------------------------------------ búsqueda

def total(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(m.JTesis)) or 0


def buscar(db: Session, consulta: str, tipo: str | None = None, epoca: str | None = None, instancia: str | None = None,
           limite: int = 20, desde: int = 0, cualquiera: bool = False, materia: str | None = None, anio_desde: int | None = None,
           anio_hasta: int | None = None) -> tuple[list[m.JTesis], int]:
    """Búsqueda de texto completo. Con ``cualquiera`` basta que aparezca alguna palabra (para la IA); si no, todas.
    Un número de 6 o 7 dígitos se toma como registro digital. Sin palabras pero con filtros, lista lo más reciente."""
    q = (consulta or "").strip()[:300]
    filtros = []
    if instancia in INSTANCIAS:
        instancia = INSTANCIAS[instancia][1]
    if materia:
        filtros.append(func.translate(func.lower(m.JTesis.materias), "áéíóú", "aeiou").contains(plano(materia[:40])))
    if anio_desde:
        filtros.append(m.JTesis.anio >= anio_desde)
    if anio_hasta:
        filtros.append(m.JTesis.anio <= anio_hasta)
    if tipo in ("jurisprudencia", "aislada"):
        filtros.append(m.JTesis.tipo == tipo)
    if epoca:
        filtros.append(m.JTesis.epoca.ilike(f"{epoca[:30]}%"))
    if instancia:
        filtros.append(m.JTesis.instancia.ilike(f"%{instancia[:60]}%"))
    if re.fullmatch(r"\d{5,8}", q):
        t = db.get(m.JTesis, int(q))
        return ([t] if t else []), (1 if t else 0)
    palabras = [w for w in re.findall(r"[a-zñ0-9]+", plano(q)) if len(w) > 2]
    if not palabras:
        if not filtros:
            return [], 0
        base = select(m.JTesis).where(*filtros)
        n = db.scalar(select(func.count()).select_from(base.subquery())) or 0
        return list(db.scalars(base.order_by(m.JTesis.registro.desc()).offset(desde).limit(limite)).all()), n
    tsq = func.to_tsquery("spanish", (" | " if cualquiera else " & ").join(palabras))
    base = select(m.JTesis).where(m.JTesis.buscable.op("@@")(tsq), *filtros)
    n = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    # más relevante primero; empata a favor de jurisprudencia y de lo más reciente (registro mayor)
    rango = func.ts_rank_cd(m.JTesis.buscable, tsq) * text("(CASE WHEN j_tesis.tipo = 'jurisprudencia' THEN 1.3 ELSE 1.0 END)")
    filas = db.scalars(base.order_by(rango.desc(), m.JTesis.registro.desc()).offset(desde).limit(limite)).all()
    return list(filas), n


def a_dict(t: m.JTesis, completo: bool = True) -> dict:
    d = {"registro": t.registro, "rubro": t.rubro, "clave": t.clave, "tipo": t.tipo, "epoca": t.epoca, "instancia": t.instancia, "organo": t.organo,
         "materias": t.materias, "anio": t.anio, "enlace": enlace(t.registro)}
    if completo:
        d.update({"texto": t.texto, "precedentes": t.precedentes, "fuente": t.fuente, "publicada": t.publicada, "huella_oficial": t.huella_oficial,
                  "origen": t.origen, "actualizado_en": t.actualizado_en.isoformat()})
    else:
        d["extracto"] = (t.texto or "")[:320]
    return d


def ficha_pdf(t: m.JTesis) -> bytes:
    """Ficha en PDF con el texto del registro oficial, su liga al SJF y su origen. No sustituye al documento del SJF."""
    from html import escape as e

    import pymupdf

    meta = " · ".join(x for x in (t.instancia, t.epoca, t.materias and f"Materia(s): {t.materias}", t.clave and f"Tesis: {t.clave}",
                                   t.tipo and f"Tipo: {t.tipo.capitalize()}") if x)
    parrafos = "".join(f"<p>{e(p)}</p>" for p in (t.texto or "").split("\n") if p.strip())
    prec = "".join(f"<p class='chico'>{e(p)}</p>" for p in (t.precedentes or "").split("\n") if p.strip())
    html = (f"<p class='chico'>Registro digital: <b>{t.registro}</b></p><p class='chico'>{e(meta)}</p>"
            f"<h1>{e(t.rubro)}</h1>{parrafos}{prec}"
            + (f"<p class='chico'>{e(t.publicada)}</p>" if t.publicada else "")
            + f"<hr/><p class='chico'>Consulte la versión oficial en el Semanario Judicial de la Federación: {e(enlace(t.registro))}<br/>"
            f"Copia generada por Nomira a partir de {'el Repositorio de datos abiertos de la SCJN' if t.origen == 'repositorio' else 'una publicación oficial de la SCJN'}"
            + (f". Huella SHA-256 oficial: {e(t.huella_oficial)}" if t.huella_oficial else "") + ".</p>")
    css = ("body{font-family:sans-serif;font-size:10.5pt;line-height:1.45} h1{font-size:12pt;margin:10px 0} p{margin:0 0 7px 0;text-align:justify}"
           " .chico{font-size:8.5pt;color:#475569}")
    historia = pymupdf.Story(html=html, user_css=css)
    salida = io.BytesIO()
    escritor = pymupdf.DocumentWriter(salida)
    caja = pymupdf.paper_rect("letter") + (60, 60, -60, -60)
    mas = True
    while mas:
        dispositivo = escritor.begin_page(pymupdf.paper_rect("letter"))
        mas, _ = historia.place(caja)
        historia.draw(dispositivo)
        escritor.end_page()
    escritor.close()
    return salida.getvalue()
