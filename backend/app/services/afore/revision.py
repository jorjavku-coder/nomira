"""«¿Está listo el expediente?»: lista de lo que falta o hay que revisar. Usa lenguaje de revisión
(«Dato por confirmar», «Posible inconsistencia»). No concluye que un documento sea falso ni que
exista un derecho; no hay probabilidades de ganar."""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .catalogos import CAMPOS_DATO, ESTADOS_REQUISITO, TIPOS_ACTIVIDAD


def _plano(t: str | None) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(ch for ch in t if unicodedata.category(ch) != "Mn")))


def revisar(db: Session, caso: m.AfCaso, cliente: m.AfCliente, curp: str | None, nss: str | None) -> dict:
    reqs = db.scalars(select(m.AfRequisito).where(m.AfRequisito.caso_id == caso.id).order_by(m.AfRequisito.orden)).all()
    docs = db.scalars(select(m.AfDocumento).where(m.AfDocumento.caso_id == caso.id)).all()
    acts = db.scalars(select(m.AfActividad).where(m.AfActividad.caso_id == caso.id)).all()
    plazos = db.scalars(select(m.AfPlazo).where(m.AfPlazo.caso_id == caso.id, m.AfPlazo.completado_en.is_(None))).all()
    datos = caso.datos or {}

    faltan_datos = []
    if not (curp or nss):
        faltan_datos.append("CURP o NSS del titular (dato por confirmar).")
    for k, etiqueta in CAMPOS_DATO.items():
        d = datos.get(k) or {}
        if d.get("estado") in ("pendiente", "no_lo_se"):
            faltan_datos.append(f"{etiqueta}: {'pendiente de confirmar' if d['estado'] == 'pendiente' else 'el cliente no lo sabe'}.")
    if caso.tipo_problema == "beneficiario_fallecimiento" and cliente.titular_estado != "fallecio":
        faltan_datos.append("Situación del titular: el caso es por fallecimiento, pero el titular no está registrado como fallecido (dato por confirmar).")
    if not caso.responsable_id:
        faltan_datos.append("Responsable del despacho.")

    aplicables = [r for r in reqs if r.estado != "no_aplica"]
    faltan_docs = [f"{r.nombre} ({ESTADOS_REQUISITO[r.estado].lower()})" for r in aplicables if r.estado in ("no_solicitado", "solicitado", "requiere_correccion")]
    revisar_abogado = [f"Documento por revisar: {r.nombre}" for r in aplicables if r.estado in ("recibido", "por_revisar")]

    # Posibles inconsistencias: datos que una persona capturó de cada documento contra los del cliente
    inconsist = []
    nombre_ref = _plano(caso.titular_nombre or cliente.nombre)
    for d in docs:
        cap = d.datos_capturados or {}
        if cap.get("nombre") and _plano(cap["nombre"]) != nombre_ref:
            inconsist.append(f"Posible inconsistencia: el nombre en «{d.nombre_original}» («{cap['nombre']}») no coincide con el registrado.")
        if cap.get("curp") and curp and cap["curp"].upper().replace(" ", "") != curp:
            inconsist.append(f"Posible inconsistencia: la CURP capturada de «{d.nombre_original}» no coincide con la registrada.")
        if cap.get("nss") and nss and re.sub(r"\D", "", cap["nss"]) != nss:
            inconsist.append(f"Posible inconsistencia: el NSS capturado de «{d.nombre_original}» no coincide con el registrado.")
    fechas_nac = {(d.datos_capturados or {}).get("fecha_nacimiento") for d in docs} - {None, ""}
    if len(fechas_nac) > 1:
        inconsist.append("Posible inconsistencia: hay fechas de nacimiento distintas capturadas en los documentos.")

    folios = [f"{TIPOS_ACTIVIDAD.get(a.tipo, a.tipo)} del {a.fecha.strftime('%d/%m/%Y')} sin folio registrado." for a in acts
              if a.tipo in ("solicitud_enviada", "queja") and not a.folio]
    folios += [f"Respuesta del {a.fecha.strftime('%d/%m/%Y')} sin documento (acuse o respuesta) asociado." for a in acts
               if a.tipo == "respuesta_recibida" and not a.documento_id]
    revisar_abogado += [f"Fecha «{p.descripcion}» es estimada: confírmela o corríjala." for p in plazos if p.tipo == "estimado"]
    revisar_abogado += [f"{CAMPOS_DATO[k]}: dato informado, no verificado por Nomira." for k in ("monto_cliente", "monto_afore", "monto_entregado")
                        if (datos.get(k) or {}).get("estado") == "informado"]

    total = len(aplicables)
    recibidos = sum(1 for r in aplicables if r.estado in ("recibido", "por_revisar", "aceptado"))
    aceptados = sum(1 for r in aplicables if r.estado == "aceptado")
    return {"faltan_datos": faltan_datos, "faltan_documentos": faltan_docs, "inconsistencias": inconsist,
            "folios_pendientes": folios, "revision_abogado": revisar_abogado,
            "progreso": {"total": total, "recibidos": recibidos, "aceptados": aceptados,
                         "porcentaje_recibidos": round(100 * recibidos / total) if total else 0,
                         "explicacion": "Porcentaje de documentos del checklist (sin contar «No aplica») que ya se recibieron. "
                                        "Mide el avance en la integración del expediente, no la probabilidad de un resultado."},
            "listo_para_avanzar": not (faltan_datos or faltan_docs or inconsist or folios or revisar_abogado)}
