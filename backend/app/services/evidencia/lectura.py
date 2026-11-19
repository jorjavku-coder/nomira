"""Lectura de documentos de Evidencia: PDF o imagen → páginas con texto (nativo u OCR) →
clasificación sugerida y hechos propuestos con su fuente (documento, página, fragmento y zona).

Todo lo que produce este módulo es una PROPUESTA: los hechos quedan «por revisar» y la
clasificación como «sugerida» hasta que una persona los confirme. Nada se inventa: un hecho solo
se propone a partir de una frase que existe en el documento.
"""
from __future__ import annotations

import io
import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

import pymupdf

from ...config import ajustes
from ..extraccion import PaginaExtraida, Palabra, agrupar_lineas, extraer_pagina

MESES = {m: i + 1 for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                          "septiembre", "octubre", "noviembre", "diciembre"])}
MESES["setiembre"] = 9
_RE_FECHA_LARGA = re.compile(r"\b(\d{1,2}|primero)\s+de\s+(" + "|".join(MESES) + r")\s+(?:de|del)\s+(?:a[nñ]o\s+)?(\d{4})\b")
_RE_FECHA_NUM = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_RE_FECHA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_RE_IMPORTE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?|\b(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})\s*(?:pesos|m\.?\s?n\.?|mxn)\b")
_TITULOS = r"(?:C\.|Sr\.|Sra\.|Srita\.|Lic\.|Licda\.|Ing\.|Dr\.|Dra\.|Mtro\.|Mtra\.|Arq\.|Contador|el señor|la señora|ciudadano|ciudadana)"
_RE_PERSONA = re.compile(_TITULOS + r"\s+((?:[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+)(?:\s+(?:de|del|la|los|las|y)?\s*[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,4})")

# Tipo sugerido: primera coincidencia en orden de prioridad (texto normalizado, sin acentos).
TIPOS = [
    ("Recibo de nómina", ["comprobante de percepciones", "recibo de nomina", "percepciones y deducciones"]),
    ("Factura / CFDI", ["comprobante fiscal digital", "cfdi", "factura"]),
    ("Convenio", ["convenio"]),
    ("Entrevista", ["entrevista"]),
    ("Conversación / mensajes", ["conversacion", "mensajes de whatsapp", "chat"]),
    ("Contrato", ["contrato"]),
    ("Finiquito / liquidación", ["finiquito", "liquidacion"]),
    ("Aviso de terminación", ["aviso de rescision", "aviso de terminacion", "terminacion de la relacion"]),
    ("Renuncia", ["renuncia"]),
    ("Demanda", ["demanda", "escrito inicial"]),
    ("Resolución / sentencia", ["sentencia", "laudo", "resolucion"]),
    ("Acta", ["acta"]),
    ("Estado de cuenta", ["estado de cuenta"]),
    ("Constancia", ["constancia"]),
    ("Identificación", ["credencial para votar", "instituto nacional electoral", "pasaporte"]),
    ("Oficio", ["oficio"]),
    ("Correo o mensaje", ["asunto:", "de:", "para:", "enviado:", "remitente"]),
]
TIPOS_DISPONIBLES = [t for t, _ in TIPOS] + ["Comprobante de pago", "Fotografía", "Otro"]
MAX_HECHOS_POR_DOCUMENTO = 200
# No terminan una oración: «Lic.», «C.», «S.A.», «M.N.», «C.V.», «No.», viñetas «1.»
_RE_ABREVIATURA = re.compile(r"(?:[A-ZÁÉÍÓÚ][a-záéíóú]{0,4}\.|(?:[A-ZÁÉÍÓÚa-z]\.){1,4}|\d{1,2}\.)")


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# ---------- apertura del archivo ----------

def detectar_formato(datos: bytes) -> str | None:
    if datos.startswith(b"%PDF-"):
        return "pdf"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if datos.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp"
    return None


def abrir(ruta: str, formato: str) -> pymupdf.Document:
    """Abre el original SIN modificarlo. Las imágenes se pasan a PNG en memoria para leerlas."""
    if formato == "pdf":
        doc = pymupdf.open(ruta)
        if not doc.is_pdf or doc.needs_pass:
            raise ValueError("El PDF no se puede abrir (dañado o protegido con contraseña).")
        return doc
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 60_000_000
    with Image.open(ruta) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    return pymupdf.open(stream=buf.getvalue(), filetype="png")


# ---------- hechos propuestos ----------

TIPOS_DATO = {"fecha_evento": "Fecha del evento", "fecha_mencionada": "Fecha mencionada por una persona",
              "fecha_indeterminada": "Fecha (tipo no determinado)", "fecha_documento": "Fecha del documento",
              "importe": "Importe", "persona": "Persona", "lugar": "Lugar", "administrativo": "Dato administrativo",
              "otro": "Otro"}
TIPOS_FECHA_DE_HECHO = ("fecha_evento", "fecha_mencionada", "fecha_indeterminada")
_VERBOS_DECIR = (r"refieren?|indican?|senalan?|manifiestan?|declaran?|afirman?|dicen?|mencionan?|narran?|comentan?|"
                 r"reconocen?|expresan?|sostienen?|relatan?|aseguran?|agregan?|precisan?|aclaran?")
# «La cliente refiere…», «Las partes manifiestan…» (sobre el texto sin acentos, en minúsculas)
_RE_SUJETO = re.compile(r"^((?:la|el|las|los)\s+[a-zn]+(?:\s+(?!que\b)[a-zn]+){0,3}?)\s+(" + _VERBOS_DECIR + r")\b")
_RE_SIN_SUJETO = re.compile(r"^(" + _VERBOS_DECIR + r")\s+que\b")
# «Laura: …» o «Laura (15/01 09:12): …» en conversaciones
_RE_HABLANTE = re.compile(r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)\s*(?:\([^)]{0,40}\))?:\s")
_NO_HABLANTE = {"estimado", "estimada", "hola", "querido", "querida", "atentamente", "saludos", "asunto", "de", "para",
                "fecha", "cc", "nota", "lugar", "cliente", "nombre", "estado", "folio", "expediente", "referencia", "importante"}
_RE_TEXTO_LEGAL = re.compile(r"\b(diario oficial|articulos?\s+\d|fraccion\s+[ivxl]+|ley federal|codigo (civil|penal|nacional))")
_RE_PIE = re.compile(r"^(pagina|pag\.?|hoja)\s+\d+(\s+de\s+\d+)?$")
# Tema del evento: sirve para comparar solo datos que describen LO MISMO (p. ej. la fecha de separación
# contra otra fecha de separación). Raíces sin acentos, al inicio de palabra; gana la primera que coincide.
TEMAS = [
    ("separacion", "Separación", ["separa"]),
    ("matrimonio", "Matrimonio", ["matrimonio", "contrajeron", "contrajo", "se casaron"]),
    ("nacimiento", "Nacimiento", ["nacio", "nacimiento"]),
    ("terminacion_relacion", "Terminación de la relación de trabajo", ["termin", "ultimo dia", "despid", "rescision", "renuncia"]),
    ("inicio_relacion", "Inicio de la relación de trabajo", ["inici", "ingres", "comenz"]),
    ("salario", "Salario", ["salario", "sueldo"]),
    ("pension", "Pensión alimenticia", ["pension"]),
    ("pago", "Pago", ["recibi", "pago", "pague", "deposit", "finiquito"]),
]
ETIQUETA_TEMA = {k: t for k, t, _ in TEMAS}
_RE_TEMAS = [(k, re.compile(r"\b(?:" + "|".join(re.escape(r) for r in raices) + ")")) for k, _, raices in TEMAS]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# «Toluca, Estado de México, a 12 de febrero de 2026»: lugar y fecha en que se hizo el documento.
_RE_LUGAR_FECHA = re.compile(r"^\s*([A-ZÁÉÍÓÚÑ][^\d:;]{2,80}?),?\s+a\s+(?:los\s+)?(?:\d{1,2}|primero)\s+(?:d[ií]as\s+del\s+mes\s+)?de\s", re.I)
_RE_EN_LUGAR = re.compile(r"^\s*En\s+(?:la\s+|el\s+)?([A-ZÁÉÍÓÚÑ][^,;:]{2,60}?),\s")
# Etiqueta «Algo: valor» al inicio de la oración.
_RE_ETIQUETA = re.compile(r"^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ ]{1,40}?)\s*:\s*(.+?)\s*\.?\s*$", re.S)
_ETQ_FECHA_DOC = re.compile(r"^(fecha|fecha (del|de la|de) (documento|entrevista|conversacion|reunion|sesion|elaboracion|emision|firma|creacion|carga|borrador|escrito|oficio|correo|mensaje)|elaborado|emitido|firmado)$")
_ETQ_LUGAR = re.compile(r"^(lugar|lugar y fecha|domicilio|ciudad)$")
_ETQ_PERSONA = re.compile(r"^(nombre|cliente|entrevistad[oa]|solicitante|conyuge|trabajador|trabajadora|parte actora|parte demandada|promovente|demandado|demandada|actor|actora)$")
_ETQ_ADMIN = re.compile(r"^(estado del documento|estado|estatus|folio|expediente|numero de expediente|no\. de expediente|version|referencia|juzgado|asunto|tipo de documento|clave)$")
_RE_DOC_PROPIO = re.compile(r"\b(?:el|este|la|esta)\s+presente\s+(?:contrato|convenio|documento|escrito|acta|instrumento)|\b(?:este|esta)\s+(?:contrato|convenio|documento|escrito|acta|borrador)\b")
_RE_DOC_ACCION = re.compile(r"\b(celebra|firma|suscrib|elabor|emit|otorga|redact|expid)")
# Texto que NO es un hecho del caso: notas editoriales, instrucciones, avisos del sistema.
_NO_HECHO_INICIO = ("nota", "aclaracion", "instruccion", "observacion del sistema", "importante:", "advertencia",
                    "documento ficticio", "este documento es ficticio", "aviso:", "leyenda")


@dataclass
class HechoPropuesto:
    descripcion: str
    pagina: int
    fragmento: str
    bbox: list[float]
    confianza: int | None
    tipo_dato: str = "otro"
    tema: str | None = None
    atribucion: str | None = None
    calidad: str = "buena"
    motivo_calidad: str | None = None
    valor_original: str | None = None
    valor: str | None = None
    fecha: date | None = None
    fecha_texto: str | None = None
    importe: Decimal | None = None
    personas: list[str] = field(default_factory=list)
    dato: str | None = None


def fecha_corta(d: date) -> str:
    return f"{d.day} {MESES_CORTOS[d.month - 1]} {d.year}"


def buscar_fechas_pos(texto: str) -> list[tuple[int, int, date, str]]:
    """(inicio, fin, fecha, texto original) de cada fecha válida, en orden de aparición."""
    t = normalizar(texto)  # misma longitud que el original: solo quita acentos y pasa a minúsculas
    hallazgos = []
    for m_ in _RE_FECHA_LARGA.finditer(t):
        dia = 1 if m_[1] == "primero" else int(m_[1])
        hallazgos.append((m_.start(), m_.end(), (dia, MESES[m_[2]], int(m_[3]))))
    for m_ in _RE_FECHA_NUM.finditer(t):  # formato mexicano: día/mes/año
        hallazgos.append((m_.start(), m_.end(), (int(m_[1]), int(m_[2]), int(m_[3]))))
    for m_ in _RE_FECHA_ISO.finditer(t):
        hallazgos.append((m_.start(), m_.end(), (int(m_[3]), int(m_[2]), int(m_[1]))))
    res = []
    for a, b, (d, mes, anio) in sorted(hallazgos):
        if not 1900 <= anio <= 2100 or (res and a < res[-1][1]):
            continue
        try:
            res.append((a, b, date(anio, mes, d), texto[a:b]))
        except ValueError:
            continue  # 31/02/2024 y similares: no se inventa una fecha parecida
    return res


def buscar_fechas(texto: str) -> list[tuple[date, str]]:
    """Fechas válidas en el texto, en orden de aparición, con el texto tal como aparece."""
    return [(f, crudo) for _, _, f, crudo in buscar_fechas_pos(texto)]


def buscar_importe(texto: str) -> Decimal | None:
    x = buscar_importe_pos(texto)
    return x[0] if x else None


def buscar_importe_pos(texto: str) -> tuple[Decimal, str] | None:
    m_ = _RE_IMPORTE.search(texto.lower())
    if not m_:
        return None
    entero, dec = (m_[1], m_[2]) if m_[1] else (m_[3], m_[4])
    try:
        return Decimal(entero.replace(",", "") + "." + (dec or "00")), texto[m_.start():m_.end()].strip()
    except InvalidOperation:
        return None


def buscar_personas(texto: str) -> list[str]:
    vistas = []
    for m_ in _RE_PERSONA.finditer(texto):
        nombre = re.sub(r"\s+", " ", m_[1]).strip(" ,.;")
        if nombre and nombre not in vistas:
            vistas.append(nombre)
    return vistas[:6]


def tema_de(texto: str) -> str | None:
    t = normalizar(texto)
    for clave, rx in _RE_TEMAS:
        if rx.search(t):
            return clave
    return None


def no_es_hecho(texto: str) -> bool:
    """Notas editoriales, instrucciones o texto sobre el propio sistema: nunca son hechos del caso."""
    t = normalizar(texto).strip(" -–—*•")
    if t.startswith(_NO_HECHO_INICIO) or "nomira" in t or _RE_PIE.match(t) or "derechos reservados" in t:
        return True
    if "fecha del documento" in t and any(x in t for x in ("no equivale", "no corresponde", "no es la fecha", "distinta")):
        return True
    return "no equivale a la fecha" in t


def _es_encabezado(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    return len(letras) >= 6 and sum(c.isupper() for c in letras) / len(letras) > 0.85 and len(texto.split()) <= 14


def _parrafos(pe: PaginaExtraida) -> list[list[Palabra]]:
    """Agrupa líneas cercanas en párrafos (el texto de un hecho suele ocupar varias líneas)."""
    lineas = agrupar_lineas(pe.palabras)
    if not lineas:
        return []
    alto = statistics.median(p.alto for p in pe.palabras) or 8.0
    parrafos, actual, fondo = [], [], None
    for ln in lineas:
        tope = min(p.y0 for p in ln)
        if actual and fondo is not None and tope - fondo > alto * 0.9:
            parrafos.append(actual)
            actual = []
        actual.extend(ln)
        fondo = max(p.y1 for p in ln)
    if actual:
        parrafos.append(actual)
    return parrafos


def _oraciones(parrafo: list[Palabra]) -> list[list[Palabra]]:
    res, actual = [], []
    for p in parrafo:
        actual.append(p)
        if re.search(r"[.;]$", p.texto) and not _RE_ABREVIATURA.fullmatch(p.texto.strip("(),")):
            res.append(actual)
            actual = []
    if actual:
        res.append(actual)
    return res


class _Oracion:
    """Texto de una oración con la posición de cada palabra, para ubicar la zona de cada dato."""

    def __init__(self, palabras: list[Palabra]):
        self.palabras, self.rangos, partes, pos = palabras, [], [], 0
        for p in palabras:
            t = p.texto.strip()
            if partes:
                pos += 1
            self.rangos.append((pos, pos + len(t)))
            partes.append(t)
            pos += len(t)
        self.texto = " ".join(partes)

    def zona(self, a: int = 0, b: int | None = None) -> tuple[list[float], int | None]:
        b = len(self.texto) if b is None else b
        ps = [p for p, (x, y) in zip(self.palabras, self.rangos) if x < b and y > a] or self.palabras
        confs = [p.conf for p in ps if p.conf is not None]
        caja = [round(v, 1) for v in (min(p.x0 for p in ps), min(p.y0 for p in ps), max(p.x1 for p in ps), max(p.y1 for p in ps))]
        return caja, (min(confs) if confs else None)


def atribucion_de(texto: str, ultimo_sujeto: str | None) -> tuple[str | None, str | None, bool]:
    """(atribución, nuevo último sujeto, ¿la afirma una persona?). Solo con señales explícitas del texto."""
    t = normalizar(texto)
    m_ = _RE_SUJETO.match(t)
    if m_:
        sujeto = texto[:m_.end(1)].strip()
        return f"{sujeto} {texto[m_.start(2):m_.end(2)]}", sujeto, True
    m_ = _RE_SIN_SUJETO.match(t)
    if m_ and ultimo_sujeto:
        return f"{ultimo_sujeto} {texto[m_.start(1):m_.end(1)].lower()}", ultimo_sujeto, True
    m_ = _RE_HABLANTE.match(texto)
    if m_ and normalizar(m_[1].split()[0]) not in _NO_HABLANTE:
        return f"{m_[1]} escribe", ultimo_sujeto, True
    return None, ultimo_sujeto, False


def calidad_de(descripcion: str, tipo: str, conf: int | None) -> tuple[str, str | None]:
    """Calidad de la EXTRACCIÓN (no del hecho): ¿se entiende la frase y se leyó bien?"""
    t = normalizar(descripcion)
    letras = sum(c.isalpha() for c in descripcion) / max(len(descripcion), 1)
    if conf is not None and conf < 70:
        return "baja", "El texto se leyó con dificultad (OCR poco legible): compárelo con el original."
    if tipo in TIPOS_FECHA_DE_HECHO + ("importe",) and len(descripcion.split()) < 5:
        return "baja", "La frase es muy corta o está fragmentada; puede faltar contexto."
    if tipo in TIPOS_FECHA_DE_HECHO + ("importe",) and letras < 0.55:
        return "baja", "La frase tiene muchos números o símbolos; puede ser una tabla o un encabezado."
    if _RE_TEXTO_LEGAL.search(t):
        return "baja", "Parece una referencia legal genérica, no un hecho del asunto."
    if tipo == "fecha_indeterminada":
        return "revisar", "No se pudo determinar a qué evento corresponde la fecha."
    if conf is not None and conf < 85:
        return "revisar", "Leído con OCR de legibilidad media: compárelo con el original."
    return "buena", None


def _limpiar_clausula(t: str) -> str:
    t = re.sub(r"^[\s,;:]*(?:y\s+(?:que\s+)?|e\s+|así como\s+)?", "", t.strip())
    return t[:1].upper() + t[1:] if t else t


def proponer_hechos(pe: PaginaExtraida) -> list[HechoPropuesto]:
    """Propuestas ATÓMICAS: un dato por propuesta (fecha del evento, fecha del documento, importe,
    persona, lugar o dato administrativo), siempre con su fragmento de origen."""
    hechos: list[HechoPropuesto] = []
    vistas: set[tuple] = set()
    ultimo_sujeto: str | None = None

    def agregar(o: _Oracion, a: int, b: int | None, **kw):
        clave = (kw.get("tipo_dato"), normalizar(kw.get("descripcion", "")), kw.get("fecha"), kw.get("importe"))
        if clave in vistas:
            return
        vistas.add(clave)
        caja, conf = o.zona(a, b)
        nivel, motivo = calidad_de(kw.get("descripcion", ""), kw.get("tipo_dato", "otro"), conf)
        hechos.append(HechoPropuesto(pagina=pe.numero, fragmento=o.texto[:1500], bbox=caja, confianza=conf,
                                     calidad=nivel, motivo_calidad=motivo, **kw))

    for parrafo in _parrafos(pe):
        for palabras in _oraciones(parrafo):
            o = _Oracion(palabras)
            texto = re.sub(r"\s+", " ", o.texto).strip()
            if len(texto) < 6 or no_es_hecho(texto):
                continue
            fechas = buscar_fechas_pos(texto)
            m_et = _RE_ETIQUETA.match(texto)
            etiqueta = normalizar(m_et[1]).strip() if m_et else ""
            valor_et = m_et[2].strip(" .") if m_et else ""

            # 1) Datos etiquetados: «Estado del documento: borrador», «Cliente: …», «Fecha: 02/07/2025»
            if m_et and _ETQ_FECHA_DOC.match(etiqueta) and fechas:
                _, _, f, crudo = fechas[0]
                agregar(o, 0, None, tipo_dato="fecha_documento", descripcion=f"{m_et[1].strip()}: {crudo}",
                        fecha=f, fecha_texto=crudo, valor_original=crudo, valor=fecha_corta(f))
                continue
            if m_et and _ETQ_LUGAR.match(etiqueta) and not fechas:
                agregar(o, 0, None, tipo_dato="lugar", descripcion=f"Lugar: {valor_et}", valor_original=valor_et, valor=valor_et)
                continue
            if m_et and _ETQ_PERSONA.match(etiqueta) and not fechas:
                agregar(o, 0, None, tipo_dato="persona", descripcion=f"{m_et[1].strip()}: {valor_et}", valor_original=valor_et,
                        valor=valor_et, personas=[valor_et], tema="rol:" + etiqueta)
                continue
            if m_et and _ETQ_ADMIN.match(etiqueta) and not fechas and len(valor_et) <= 200:
                agregar(o, 0, None, tipo_dato="administrativo", descripcion=f"{m_et[1].strip()}: {valor_et}",
                        valor_original=valor_et, valor=valor_et, dato=f"{m_et[1].strip()}: {valor_et}")
                continue

            # 2) Encabezados sin fecha (títulos, etiquetas sueltas): no son hechos
            if _es_encabezado(texto) and not fechas:
                continue

            # 3) Lugar y fecha del propio documento: «Toluca, Estado de México, a 12 de febrero de 2026.»
            m_lf = _RE_LUGAR_FECHA.match(texto)
            if m_lf and fechas and fechas[0][0] <= m_lf.end() + 25:
                lugar = m_lf[1].strip(" ,")
                agregar(o, 0, len(lugar), tipo_dato="lugar", descripcion=f"Lugar del documento: {lugar}", valor_original=lugar, valor=lugar)
                a, b, f, crudo = fechas[0]
                agregar(o, a, b, tipo_dato="fecha_documento", descripcion=f"Fecha del documento: {crudo}", fecha=f,
                        fecha_texto=crudo, valor_original=crudo, valor=fecha_corta(f))
                fechas = fechas[1:]
                if not fechas:
                    continue
            m_en = _RE_EN_LUGAR.match(texto)
            if m_en and fechas:
                lugar = m_en[1].strip()
                agregar(o, 0, m_en.end(), tipo_dato="lugar", descripcion=f"Lugar: {lugar}", valor_original=lugar, valor=lugar)

            personas = buscar_personas(texto)
            imp = buscar_importe_pos(texto)
            atrib, ultimo_sujeto, de_persona = atribucion_de(texto, ultimo_sujeto)
            t_norm = normalizar(texto)
            es_doc = bool(_RE_DOC_PROPIO.search(t_norm) and _RE_DOC_ACCION.search(t_norm)) or _es_encabezado(texto)

            # 4) Fechas: cada una es su propio dato, con la parte de la oración que le corresponde
            inicio = 0
            for i, (a, b, f, crudo) in enumerate(fechas):
                fin = len(texto) if i == len(fechas) - 1 else b
                clausula = _limpiar_clausula(texto[inicio:fin]) if len(fechas) > 1 else texto
                inicio = b
                if es_doc and i == 0:
                    agregar(o, a, b, tipo_dato="fecha_documento", descripcion=f"Fecha del documento: {crudo}", fecha=f,
                            fecha_texto=crudo, valor_original=crudo, valor=fecha_corta(f), personas=personas)
                    continue
                imp_c = buscar_importe_pos(clausula)
                tema = tema_de(clausula)
                tipo = "fecha_mencionada" if de_persona else "fecha_evento" if tema else "fecha_indeterminada"
                agregar(o, a, b, tipo_dato=tipo, descripcion=clausula[:600], fecha=f, fecha_texto=crudo,
                        valor_original=crudo, valor=fecha_corta(f), tema=tema, atribucion=atrib,
                        importe=imp_c[0] if imp_c else None, personas=buscar_personas(clausula) or personas)
            # 5) Importe sin fecha del evento en la misma oración
            if imp and not any(h.importe == imp[0] and h.fragmento == o.texto[:1500] for h in hechos):
                agregar(o, 0, None, tipo_dato="importe", descripcion=texto[:600], importe=imp[0], valor_original=imp[1],
                        valor=f"${imp[0]:,.2f}", tema=tema_de(texto), personas=personas, atribucion=atrib)
    return hechos


def sugerir_tipo(texto: str) -> str | None:
    t = normalizar(texto[:6000])
    if "asunto:" in t and ("de:" in t or "para:" in t):  # encabezado de correo
        return "Correo o mensaje"
    for tipo, claves in TIPOS:
        if any(c in t for c in claves):
            return tipo
    return None


def atribucion_documento(tipo: str | None, borrador: bool) -> str:
    """De dónde proviene lo que dice un documento cuando el texto no nombra a quien lo afirma."""
    if borrador:
        return "El borrador propone"
    return {"Contrato": "El contrato establece", "Convenio": "El convenio establece", "Entrevista": "Registrado en la entrevista",
            "Aviso de terminación": "El aviso indica", "Correo o mensaje": "El correo indica",
            "Conversación / mensajes": "La conversación indica", "Finiquito / liquidación": "El recibo indica",
            "Recibo de nómina": "El recibo indica", "Demanda": "La demanda afirma", "Acta": "El acta registra",
            "Resolución / sentencia": "La resolución indica"}.get(tipo or "", "El documento indica")


@dataclass
class Lectura:
    paginas: list[PaginaExtraida]
    hechos: list[HechoPropuesto]
    tipo_sugerido: str | None
    fecha_sugerida: date | None
    paginas_dudosas: list[int]


def leer(ruta: str, formato: str) -> Lectura:
    minimo = ajustes().ocr_confianza_minima
    paginas, hechos, dudosas = [], [], []
    with abrir(ruta, formato) as doc:
        if doc.page_count > ajustes().max_paginas_pdf:
            raise ValueError(f"El documento excede {ajustes().max_paginas_pdf} páginas.")
        for n, pagina in enumerate(doc, start=1):
            pe = extraer_pagina(pagina, n)
            paginas.append(pe)
            texto = pe.texto.strip()
            if len(texto) < 20 or (pe.metodo == "ocr" and (pe.confianza or 0) < minimo):
                dudosas.append(n)
            hechos.extend(proponer_hechos(pe))
    texto_inicio = "\n".join(p.texto for p in paginas[:2])
    tipo_doc = sugerir_tipo(texto_inicio)
    general = atribucion_documento(tipo_doc, "borrador" in normalizar(texto_inicio))
    for h in hechos:  # «El borrador propone (Las partes manifiestan)»: quién lo dice y en qué documento
        if h.tipo_dato in ("fecha_documento", "lugar", "administrativo", "persona"):
            continue
        if general.startswith("El borrador") and h.atribucion:
            h.atribucion = f"{general} ({h.atribucion[:1].lower() + h.atribucion[1:]})"
        elif not h.atribucion:
            h.atribucion = general
    propia = next((h.fecha for h in hechos if h.tipo_dato == "fecha_documento" and h.pagina <= 2), None)
    fechas = buscar_fechas(paginas[0].texto) if paginas and not propia else []
    return Lectura(paginas, hechos[:MAX_HECHOS_POR_DOCUMENTO], tipo_doc,
                   propia or (fechas[0][0] if fechas else None), dudosas)
