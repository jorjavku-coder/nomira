"""Importar cursos a Academia: enlaces de video, plantilla de Excel y paquetes SCORM.

Todo lo importado queda como BORRADOR: el despacho lo revisa antes de publicarlo.
"""
from __future__ import annotations

import io
import re
import shutil
import stat
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

import httpx
from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

# ------------------------------------------------------------------ enlaces de video

_YT = re.compile(r"^https://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/)|youtu\.be/)([\w-]{6,20})")
_VIMEO = re.compile(r"^https://(?:www\.)?vimeo\.com/(\d+)")


def plataforma_video(url: str) -> str | None:
    if _YT.match(url):
        return "youtube"
    if _VIMEO.match(url):
        return "vimeo"
    if re.match(r"^https://(?:www\.)?loom\.com/share/", url):
        return "loom"
    if re.match(r"^https://drive\.google\.com/", url):
        return "drive"
    return None


def titulo_oembed(url: str) -> str | None:
    """Título público del video (YouTube y Vimeo publican oEmbed sin llave). Si falla, None."""
    p = plataforma_video(url)
    fuente = {"youtube": "https://www.youtube.com/oembed", "vimeo": "https://vimeo.com/api/oembed.json"}.get(p or "")
    if not fuente:
        return None
    try:
        r = httpx.get(fuente, params={"url": url, "format": "json"}, timeout=4)
        if r.status_code == 200:
            t = (r.json().get("title") or "").strip()
            return t[:200] or None
    except (httpx.HTTPError, ValueError):
        return None
    return None


def limpiar_enlaces(texto_o_lista) -> list[str]:
    crudos = texto_o_lista if isinstance(texto_o_lista, list) else re.split(r"[\s,]+", texto_o_lista or "")
    res = []
    for x in crudos:
        x = (x or "").strip()
        if not x:
            continue
        if not re.match(r"^https://\S+$", x) or len(x) > 500:
            raise HTTPException(422, f"Enlace inválido (debe empezar con https://): {x[:80]}")
        if "list=" in x and not _YT.match(x):
            raise HTTPException(422, "Las listas de reproducción de YouTube no se pueden leer sin una llave de Google: pegue el enlace de cada video.")
        if x not in res:
            res.append(x)
    if not res:
        raise HTTPException(422, "Pegue al menos un enlace.")
    if len(res) > 100:
        raise HTTPException(422, "Máximo 100 enlaces por importación.")
    return res


# ------------------------------------------------------------------ plantilla de Excel

HOJA_CURSO = ["Título del curso", "Materia", "Descripción", "Instructor", "Duración (min)", "Calificación mínima (opcional)"]
HOJA_LECCIONES = ["Módulo", "Lección", "Enlace de video (opcional)", "Texto (opcional)", "Duración (min)", "Recurso: título (opcional)",
                  "Recurso: enlace (opcional)"]
HOJA_PREGUNTAS = ["Pregunta", "Opción A", "Opción B", "Opción C (opcional)", "Opción D (opcional)", "Respuesta correcta (A-D)",
                  "Explicación (opcional)"]


def plantilla() -> bytes:
    wb = Workbook()
    titulo = Font(bold=True, color="FFFFFF")
    relleno = PatternFill("solid", fgColor="123048")
    for i, (nombre, cols, ejemplo) in enumerate((
        ("Curso", HOJA_CURSO, ["Atención a clientes", "Habilidades", "Cómo dar seguimiento a una consulta", "Lic. Ejemplo", 45, 70]),
        ("Lecciones", HOJA_LECCIONES, ["Bienvenida", "Presentación del curso", "https://www.youtube.com/watch?v=XXXXXXXXXXX",
                                       "Qué aprenderá en este curso.", 5, "Guía en PDF", "https://ejemplo.com/guia.pdf"]),
        ("Preguntas", HOJA_PREGUNTAS, ["¿Qué se registra en la primera consulta?", "Solo el nombre", "Los datos y hechos tal como los cuenta",
                                       "Una opinión sobre el caso", "", "B", "Se registran los hechos sin calificarlos."]),
    )):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = nombre
        ws.append(cols)
        ws.append(ejemplo)
        for c in ws[1]:
            c.font, c.fill = titulo, relleno
        for col, ancho in zip("ABCDEFG", (34, 28, 44, 34, 16, 26, 34)):
            ws.column_dimensions[col].width = ancho
        if nombre == "Preguntas":
            dv = DataValidation(type="list", formula1='"A,B,C,D"', allow_blank=False)
            ws.add_data_validation(dv)
            dv.add("F2:F200")
    ws = wb.create_sheet("Instrucciones")
    for linea in ("Llene una fila por lección en «Lecciones» (el módulo agrupa lecciones con el mismo nombre).",
                  "La fila 2 de cada hoja es un ejemplo: reemplácela o bórrela.",
                  "Los enlaces deben empezar con https:// (YouTube y Vimeo se ven dentro de Nomira).",
                  "Las preguntas forman el cuestionario final; si pone calificación mínima, se exige aprobarlo.",
                  "El curso se importa como BORRADOR: revíselo antes de publicarlo."):
        ws.append([linea])
    ws.column_dimensions["A"].width = 110
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _celda(v) -> str:
    return "" if v is None else str(v).strip()


def _entero(v, campo: str, fila: int, minimo: int, maximo: int) -> int | None:
    t = _celda(v)
    if not t:
        return None
    try:
        n = int(float(t))
    except ValueError:
        raise HTTPException(422, f"{campo} (fila {fila}): debe ser un número.")
    if not minimo <= n <= maximo:
        raise HTTPException(422, f"{campo} (fila {fila}): fuera de rango.")
    return n


def _url_ok(v: str, donde: str) -> str | None:
    if not v:
        return None
    if not re.match(r"^https://\S+$", v) or len(v) > 500:
        raise HTTPException(422, f"{donde}: el enlace debe empezar con https://.")
    return v


def leer_excel(datos: bytes) -> dict:
    """Devuelve {curso, lecciones, preguntas} validados, o lanza 422 con la fila del problema."""
    try:
        wb = load_workbook(io.BytesIO(datos), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(422, "No se pudo leer el archivo. Use la plantilla de Nomira en formato .xlsx.")
    if not {"Curso", "Lecciones"} <= set(wb.sheetnames):
        raise HTTPException(422, "El archivo no tiene las hojas «Curso» y «Lecciones» de la plantilla.")
    filas = list(wb["Curso"].iter_rows(min_row=2, max_row=2, values_only=True))
    if not filas or not _celda(filas[0][0]):
        raise HTTPException(422, "Hoja «Curso»: escriba el título en la fila 2.")
    f = list(filas[0]) + [None] * 6
    curso = {"titulo": _celda(f[0])[:200], "materia": (_celda(f[1]) or "General")[:120], "descripcion": _celda(f[2])[:3000] or None,
             "instructor": _celda(f[3])[:200] or None, "duracion_min": _entero(f[4], "Duración", 2, 1, 10000),
             "calificacion_minima": _entero(f[5], "Calificación mínima", 2, 1, 100)}
    if len(curso["titulo"]) < 3:
        raise HTTPException(422, "Hoja «Curso»: el título debe tener al menos 3 caracteres.")
    lecciones = []
    for i, r in enumerate(wb["Lecciones"].iter_rows(min_row=2, values_only=True), start=2):
        r = list(r) + [None] * 7
        if not any(_celda(x) for x in r[:7]):
            continue
        titulo = _celda(r[1])
        if not titulo:
            raise HTTPException(422, f"Hoja «Lecciones», fila {i}: falta el nombre de la lección.")
        rec_t, rec_u = _celda(r[5]), _url_ok(_celda(r[6]), f"Hoja «Lecciones», fila {i}")
        lecciones.append({"modulo": (_celda(r[0]) or "Módulo 1")[:200], "titulo": titulo[:200],
                          "video_url": _url_ok(_celda(r[2]), f"Hoja «Lecciones», fila {i}"), "texto": _celda(r[3])[:50000] or None,
                          "duracion_min": _entero(r[4], "Duración", i, 1, 10000),
                          "recursos": [{"titulo": (rec_t or "Recurso")[:200], "url": rec_u}] if rec_u else None})
        if len(lecciones) > 300:
            raise HTTPException(422, "Máximo 300 lecciones por importación.")
    if not lecciones:
        raise HTTPException(422, "Hoja «Lecciones»: agregue al menos una lección.")
    preguntas = []
    if "Preguntas" in wb.sheetnames:
        for i, r in enumerate(wb["Preguntas"].iter_rows(min_row=2, values_only=True), start=2):
            r = list(r) + [None] * 7
            if not any(_celda(x) for x in r[:7]):
                continue
            ops = [_celda(x)[:200] for x in r[1:5]]
            letra = _celda(r[5]).upper()[:1]
            idx = "ABCD".find(letra) if letra else -1
            presentes = [o for o in ops if o]
            if not _celda(r[0]) or len(presentes) < 2 or idx < 0 or not ops[idx]:
                raise HTTPException(422, f"Hoja «Preguntas», fila {i}: escriba la pregunta, al menos dos opciones y la letra de la correcta.")
            correcta = presentes.index(ops[idx])
            preguntas.append({"texto": _celda(r[0])[:500], "opciones": presentes, "correcta": correcta, "explicacion": _celda(r[6])[:500] or None})
    if curso["calificacion_minima"] is not None and not preguntas:
        raise HTTPException(422, "Puso calificación mínima pero no hay preguntas en la hoja «Preguntas».")
    return {"curso": curso, "lecciones": lecciones, "preguntas": preguntas}


# ------------------------------------------------------------------ SCORM

MAX_ARCHIVOS_SCORM = 5000


def _ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def leer_manifest(z: zipfile.ZipFile) -> dict:
    """Lee imsmanifest.xml: título, versión (1.2 o 2004) y las SCO con su página de inicio."""
    nombres = {n.lower(): n for n in z.namelist()}
    if "imsmanifest.xml" not in nombres:
        raise HTTPException(422, "No es un paquete SCORM: falta imsmanifest.xml en la raíz del ZIP.")
    try:
        raiz = ET.fromstring(z.read(nombres["imsmanifest.xml"]))
    except ET.ParseError:
        raise HTTPException(422, "El imsmanifest.xml del paquete está dañado.")
    texto = ET.tostring(raiz, encoding="unicode")
    version = "2004" if ("2004" in texto or "adlcp_v1p3" in texto or "imsss" in texto) else "1.2"
    for el in raiz.iter():
        if _ns(el.tag) == "schemaversion" and el.text:
            version = "1.2" if "1.2" in el.text else "2004"
    recursos = {}
    for el in raiz.iter():
        if _ns(el.tag) == "resource":
            tipo = next((v for k, v in el.attrib.items() if _ns(k).lower() == "scormtype"), "sco")
            href = el.attrib.get("href")
            base = next((v for k, v in el.attrib.items() if _ns(k) == "base"), "")
            if href:
                recursos[el.attrib.get("identifier")] = {"href": (base or "") + href, "sco": tipo.lower() == "sco"}
    titulo, items = None, []
    for org in raiz.iter():
        if _ns(org.tag) != "organization":
            continue
        for hijo in org:
            if _ns(hijo.tag) == "title" and hijo.text and not titulo:
                titulo = hijo.text.strip()

        def recorrer(nodo, ruta):
            for it in nodo:
                if _ns(it.tag) != "item":
                    continue
                t = next((h.text.strip() for h in it if _ns(h.tag) == "title" and h.text), "Lección")
                ref = it.attrib.get("identifierref")
                if ref and ref in recursos:
                    items.append({"titulo": t[:200], "href": recursos[ref]["href"], "modulo": ruta or None})
                recorrer(it, t if not ref else ruta)
        recorrer(org, None)
        break
    if not items and recursos:
        r = next(iter(recursos.values()))
        items = [{"titulo": titulo or "Contenido SCORM", "href": r["href"], "modulo": None}]
    if not items:
        raise HTTPException(422, "El paquete SCORM no indica ninguna página de inicio.")
    return {"titulo": (titulo or items[0]["titulo"])[:200], "version": version, "items": items[:200]}


def extraer_scorm(fuente: bytes | Path, destino_base: Path, maximo_bytes: int) -> dict:
    """Valida y extrae el ZIP (ruta en disco o bytes) en una carpeta nueva. Rechaza rutas peligrosas,
    enlaces simbólicos y paquetes que se descomprimen por encima del máximo."""
    try:
        z = zipfile.ZipFile(fuente if isinstance(fuente, Path) else io.BytesIO(fuente))
    except zipfile.BadZipFile:
        raise HTTPException(422, "El archivo no es un ZIP válido.")
    infos = z.infolist()
    if len(infos) > MAX_ARCHIVOS_SCORM:
        raise HTTPException(422, "El paquete tiene demasiados archivos.")
    total = 0
    for i in infos:
        p = PurePosixPath(i.filename.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts or i.filename.startswith(("/", "\\")):
            raise HTTPException(422, "El paquete contiene rutas no permitidas.")
        if stat.S_ISLNK(i.external_attr >> 16):
            raise HTTPException(422, "El paquete contiene enlaces simbólicos, que no se permiten.")
        total += i.file_size
    if total > maximo_bytes:
        raise HTTPException(413, f"El paquete descomprimido supera {maximo_bytes // 1048576} MB.")
    man = leer_manifest(z)
    carpeta = destino_base / uuid.uuid4().hex
    carpeta.mkdir(parents=True, exist_ok=False, mode=0o700)
    try:
        for i in infos:
            if i.is_dir():
                continue
            rel = PurePosixPath(i.filename.replace("\\", "/"))
            ruta = (carpeta / Path(*rel.parts)).resolve()
            if carpeta.resolve() not in ruta.parents:
                raise HTTPException(422, "El paquete contiene rutas no permitidas.")
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as fuente, open(ruta, "wb") as f:
                shutil.copyfileobj(fuente, f, 1024 * 1024)
    except Exception:
        shutil.rmtree(carpeta, ignore_errors=True)
        raise
    for it in man["items"]:
        inicio = it["href"].split("?")[0].split("#")[0]
        if not (carpeta / inicio).is_file():
            shutil.rmtree(carpeta, ignore_errors=True)
            raise HTTPException(422, f"El paquete no incluye su página de inicio ({inicio[:80]}).")
    return {**man, "carpeta": str(carpeta), "tamano": total}
