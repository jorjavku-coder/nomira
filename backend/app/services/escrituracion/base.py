"""Nomira Escrituración: plantillas de etapas y requisitos por acto, semáforo «listo para firmar», avance y avisos.

Las vigencias de los documentos son SUGERIDAS (varían por estado, municipio y criterio de cada notaría): el despacho
las ajusta en cada expediente. Nomira no decide si un documento es válido: lo valida una persona de la notaría."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import models as m
from .. import correo, envios
from ..plantillas_correo import _base, escape, fecha_larga

ACTOS = {
    "compraventa": "Compraventa de inmueble", "compraventa_credito": "Compraventa con crédito hipotecario", "donacion": "Donación de inmueble",
    "adjudicacion": "Adjudicación por herencia", "testamento": "Testamento", "poder": "Poder notarial", "sociedad": "Constitución de sociedad",
    "cancelacion_hipoteca": "Cancelación de hipoteca", "otro": "Otro acto",
}
ROLES = {"comprador": "Comprador(a)", "vendedor": "Vendedor(a)", "donante": "Donante", "donatario": "Donatario(a)", "adjudicatario": "Heredero(a) / adjudicatario(a)",
         "albacea": "Albacea", "testador": "Testador(a)", "poderdante": "Poderdante", "apoderado": "Apoderado(a)", "socio": "Socio(a)",
         "acreditante": "Banco / acreditante", "deudor": "Deudor(a)", "otro": "Otro"}
ROLES_POR_ACTO = {
    "compraventa": ["comprador", "vendedor"], "compraventa_credito": ["comprador", "vendedor", "acreditante"], "donacion": ["donante", "donatario"],
    "adjudicacion": ["adjudicatario", "albacea"], "testamento": ["testador"], "poder": ["poderdante", "apoderado"], "sociedad": ["socio"],
    "cancelacion_hipoteca": ["deudor", "acreditante"], "otro": ["otro"],
}
# Quién aporta los documentos del inmueble (los ve y puede subirlos desde su enlace)
APORTA_INMUEBLE = {"vendedor", "donante", "albacea", "deudor"}
INMUEBLE = {"compraventa", "compraventa_credito", "donacion", "adjudicacion", "cancelacion_hipoteca"}

_E_INMUEBLE = [("documentos", "Documentos recibidos"), ("avaluo", "Avalúo"), ("certificados", "Certificados y constancias de no adeudo"),
               ("proyecto", "Proyecto de escritura revisado"), ("firma", "Firma de la escritura"), ("impuestos", "Pago de impuestos y derechos"),
               ("registro", "Ingreso al Registro Público de la Propiedad"), ("inscripcion", "Inscripción en el Registro"),
               ("testimonio", "Testimonio listo para entrega"), ("entregado", "Testimonio entregado")]
ETAPAS = {
    "compraventa": _E_INMUEBLE,
    "compraventa_credito": _E_INMUEBLE[:3] + [("banco", "Instrucción y autorización del banco")] + _E_INMUEBLE[3:],
    "donacion": _E_INMUEBLE,
    "adjudicacion": [("documentos", "Documentos recibidos"), ("sucesion", "Trámite sucesorio concluido")] + _E_INMUEBLE[1:],
    "cancelacion_hipoteca": [("documentos", "Documentos recibidos"), ("carta", "Carta de instrucción del acreedor"), ("proyecto", "Proyecto de escritura revisado"),
                             ("firma", "Firma de la escritura"), ("registro", "Ingreso al Registro Público de la Propiedad"), ("inscripcion", "Inscripción en el Registro"),
                             ("testimonio", "Testimonio listo para entrega"), ("entregado", "Testimonio entregado")],
    "testamento": [("documentos", "Documentos recibidos"), ("proyecto", "Revisión del testamento"), ("firma", "Firma del testamento"),
                   ("aviso", "Aviso al Registro Nacional de Avisos de Testamento"), ("entregado", "Testimonio entregado")],
    "poder": [("documentos", "Documentos recibidos"), ("proyecto", "Proyecto revisado"), ("firma", "Firma"), ("testimonio", "Testimonio listo para entrega"),
              ("entregado", "Testimonio entregado")],
    "sociedad": [("documentos", "Documentos recibidos"), ("denominacion", "Autorización de uso de denominación"), ("proyecto", "Proyecto de estatutos revisado"),
                 ("firma", "Firma de la escritura constitutiva"), ("comercio", "Inscripción en el Registro Público de Comercio"),
                 ("posteriores", "Trámites posteriores (RFC y avisos)"), ("testimonio", "Testimonio listo para entrega"), ("entregado", "Testimonio entregado")],
    "otro": [("documentos", "Documentos recibidos"), ("proyecto", "Proyecto revisado"), ("firma", "Firma"), ("testimonio", "Testimonio listo para entrega"),
             ("entregado", "Testimonio entregado")],
}
# (clave, nombre, obligatorio, vigencia sugerida en días)
REQ_FISICA = [("identificacion", "Identificación oficial vigente (INE o pasaporte)", True, None), ("curp", "CURP", True, None),
              ("csf", "Constancia de situación fiscal", True, 90), ("domicilio", "Comprobante de domicilio", True, 90),
              ("nacimiento", "Acta de nacimiento", True, None)]
REQ_CASADO = ("matrimonio", "Acta de matrimonio", True, None)
REQ_MORAL = [("acta_constitutiva", "Acta constitutiva y sus reformas", True, None), ("poder_representante", "Poder del representante legal", True, None),
             ("identificacion_representante", "Identificación oficial del representante", True, None), ("csf", "Constancia de situación fiscal", True, 90),
             ("domicilio", "Comprobante de domicilio", True, 90)]
REQ_INMUEBLE = [("antecedente", "Escritura de propiedad (antecedente) inscrita", True, None), ("predial", "Boleta predial pagada del año", True, None),
                ("agua", "Constancia de no adeudo de agua", True, 30), ("libertad_gravamen", "Certificado de libertad de gravamen", True, 30),
                ("avaluo", "Avalúo", True, 180)]
REQ_OPERACION = {"compraventa_credito": [("carta_banco", "Carta de instrucción del banco", True, None)],
                 "cancelacion_hipoteca": [("carta_acreedor", "Carta de instrucción del acreedor", True, None)],
                 "adjudicacion": [("sucesion", "Documentos del trámite sucesorio", True, None)],
                 "sociedad": [("denominacion", "Autorización de uso de denominación", True, None)]}
ROLES_SIN_DOCS = {"acreditante"}  # el banco entrega carta, no expediente personal


def plantilla_requisitos(acto: str) -> list[tuple]:
    r = list(REQ_INMUEBLE) if acto in INMUEBLE and acto != "cancelacion_hipoteca" else []
    if acto == "cancelacion_hipoteca":
        r.append(REQ_INMUEBLE[0])
    return r + REQ_OPERACION.get(acto, [])


def requisitos_parte(p: m.EsParte) -> list[tuple]:
    if p.rol in ROLES_SIN_DOCS:
        return []
    base = list(REQ_MORAL if p.tipo == "moral" else REQ_FISICA)
    if p.tipo == "fisica" and p.casado:
        base.append(REQ_CASADO)
    return base


def agregar_requisitos(db: Session, exp_id: int, lista: list[tuple], parte_id: int | None = None) -> None:
    for clave, nombre, obligatorio, vig in lista:
        db.add(m.EsRequisito(expediente_id=exp_id, parte_id=parte_id, clave=clave, nombre=nombre, obligatorio=obligatorio, vigencia_dias=vig))


def crear_etapas(db: Session, e: m.EsExpediente) -> None:
    for i, (clave, nombre) in enumerate(ETAPAS.get(e.acto, ETAPAS["otro"]), start=1):
        db.add(m.EsHito(expediente_id=e.id, clave=clave, nombre=nombre, orden=i))


def siguiente_folio(db: Session, org: int, anio: int) -> str:
    db.execute(select(func.pg_advisory_xact_lock(920_000_000 + org)))
    pref = f"ESC-{anio}-"
    ult = db.scalar(select(func.max(m.EsExpediente.folio)).where(m.EsExpediente.organizacion_id == org, m.EsExpediente.folio.like(pref + "%")))
    n = int(ult.rsplit("-", 1)[1]) + 1 if ult else 1
    return f"{pref}{n:04d}"


def calcular_vence(r: m.EsRequisito) -> None:
    if r.expedido_en and r.vigencia_dias:
        r.vence_en = r.expedido_en + timedelta(days=r.vigencia_dias)


# ------------------------------------------------------------------ semáforo y avance

def semaforo(e: m.EsExpediente, requisitos: list[m.EsRequisito], partes: dict[int, m.EsParte], hoy: date) -> dict:
    """verde = todo validado y vigente para la fecha de firma · amarillo = falta validar o no hay cita · rojo = falta algo o vence."""
    ref = e.cita_firma.date() if e.cita_firma else hoy
    falta, vencidos, por_validar, por_vencer = [], [], [], []
    for r in requisitos:
        if not r.obligatorio or r.estado == "no_aplica":
            continue
        quien = partes[r.parte_id].nombre if r.parte_id and r.parte_id in partes else "Inmueble / operación"
        item = {"id": r.id, "nombre": r.nombre, "de": quien, "estado": r.estado, "vence_en": r.vence_en.isoformat() if r.vence_en else None}
        if r.estado in ("pendiente", "rechazado"):
            falta.append(item)
        elif r.vence_en and r.vence_en < ref:
            vencidos.append(item)
        else:
            if r.estado == "recibido":
                por_validar.append(item)
            if r.vence_en and r.vence_en <= ref + timedelta(days=7):
                por_vencer.append(item)
    if falta or vencidos:
        color, texto = "rojo", "No está listo para firmar"
    elif por_validar or not e.cita_firma:
        color, texto = "amarillo", "Casi listo" if por_validar else "Documentos completos · falta agendar la firma"
    else:
        color, texto = "verde", "Listo para firmar"
    total = sum(1 for r in requisitos if r.obligatorio and r.estado != "no_aplica")
    listos = sum(1 for r in requisitos if r.obligatorio and r.estado == "validado" and not (r.vence_en and r.vence_en < ref))
    return {"color": color, "texto": texto, "referencia": ref.isoformat(), "con_cita": bool(e.cita_firma), "faltan": falta, "vencidos": vencidos,
            "por_validar": por_validar, "por_vencer": por_vencer, "total": total, "validados": listos}


def avance(hitos: list[m.EsHito]) -> dict:
    vivos = [h for h in sorted(hitos, key=lambda h: h.orden) if h.estado != "no_aplica"]
    hechos = sum(1 for h in vivos if h.estado == "hecho")
    actual = next((h for h in vivos if h.estado != "hecho"), None)
    return {"porcentaje": round(100 * hechos / len(vivos)) if vivos else 0, "hechos": hechos, "total": len(vivos),
            "actual": actual.nombre if actual else "Concluido", "actual_clave": actual.clave if actual else None}


# ------------------------------------------------------------------ avisos por correo a quienes siguen el trámite

def avisar_avance(db: Session, e: m.EsExpediente, h: m.EsHito) -> int:
    """Correo a cada enlace vigente con correo y avisos activos. No incluye datos de la operación: solo la etapa."""
    if not correo.configurado():
        return 0
    org = db.get(m.Organizacion, e.organizacion_id)
    n = 0
    for a in db.scalars(select(m.EsAcceso).where(m.EsAcceso.expediente_id == e.id, m.EsAcceso.avisar.is_(True), m.EsAcceso.email.is_not(None),
                                                 m.EsAcceso.revocado_en.is_(None), m.EsAcceso.expira_en > m.ahora())):
        asunto = f"{org.nombre}: su trámite avanzó — {h.nombre}"
        nota = f'<p style="margin:0 0 16px;white-space:pre-line">{escape(h.nota_publica)}</p>' if h.nota_publica else ""
        html = _base(asunto, f"""<h1 style="margin:0 0 12px;font-size:22px;color:#123048">Hola, {escape(a.nombre.split()[0])}</h1>
<p>Su trámite <b>{escape(ACTOS.get(e.acto, e.acto))}</b> ({escape(e.folio)}) en <b>{escape(org.nombre)}</b> avanzó:</p>
<p style="font-size:18px;margin:0 0 12px">✅ <b>{escape(h.nombre)}</b>{f' · {escape(fecha_larga(h.fecha))}' if h.fecha else ''}</p>{nota}
<p style="font-size:13px;color:#64748b">Para ver todo el avance abra el enlace de seguimiento que le compartió la notaría (por seguridad no lo repetimos en este correo). Si tiene dudas, comuníquese con la notaría.</p>""",
                     pie=f"Recibe este correo porque {org.nombre} le dio seguimiento en línea a su trámite.")
        texto = f"Hola, {a.nombre}\n\nSu trámite {ACTOS.get(e.acto, e.acto)} ({e.folio}) en {org.nombre} avanzó: {h.nombre}.\n" + \
                (f"{h.nota_publica}\n" if h.nota_publica else "") + "\nConsulte el avance con el enlace que le compartió la notaría.\n"
        llave = "esc:" + hashlib.sha256(f"{a.id}:{h.id}:{h.estado}:{h.fecha}".encode()).hexdigest()[:40]
        r = envios.registrar_y_enviar(db, "escrituracion_avance", [a.email], asunto, html, texto, organizacion_id=e.organizacion_id, llave=llave)
        n += bool(r and r.estado == "enviado")
    return n


# ------------------------------------------------------------------ archivos

MAX_ARCHIVO = 15 * 1024 * 1024
FIRMAS = {b"%PDF": ("application/pdf", ".pdf"), b"\xff\xd8\xff": ("image/jpeg", ".jpg"), b"\x89PNG": ("image/png", ".png")}


def tipo_archivo(contenido: bytes) -> tuple[str, str] | None:
    for firma, t in FIRMAS.items():
        if contenido.startswith(firma):
            return t
    if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return ("image/webp", ".webp")
    return None


def guardar_archivo(org: int, exp_id: int, contenido: bytes) -> tuple[str, str]:
    import os
    import uuid
    from pathlib import Path

    from ...config import ajustes
    t = tipo_archivo(contenido)
    if not t:
        raise ValueError("tipo")
    rel = Path(str(org), "escrituracion", str(exp_id), f"{uuid.uuid4().hex}{t[1]}")
    destino = Path(ajustes().storage_dir, rel)
    destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destino.write_bytes(contenido)
    os.chmod(destino, 0o600)
    return str(rel), t[0]


def borrar_archivo(rel: str | None) -> None:
    if rel:
        from pathlib import Path

        from ...config import ajustes
        Path(ajustes().storage_dir, rel).unlink(missing_ok=True)
