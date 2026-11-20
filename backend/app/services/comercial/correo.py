"""Correo de la cotización (HTML con la marca de Nomira + texto)."""
from __future__ import annotations

from datetime import datetime
from html import escape

from ..plantillas_correo import FUENTE, MARINO, TURQUESA_700, _base, _boton
from .pdf import fecha_larga, pesos

MENSAJE_INICIAL = ("Gracias por su interés en Nomira. Le compartimos la propuesta que preparamos para su despacho, "
                   "con los módulos y capacidades que conversamos.")


def asunto(plantilla: str | None, folio: str, nombre_comercial: str, despacho: str) -> str:
    base = (plantilla or "Cotización {folio} · {nombre_comercial}").strip()
    try:
        texto = base.format(folio=folio, nombre_comercial=nombre_comercial, despacho=despacho)
    except (KeyError, IndexError, ValueError):
        texto = base
    if folio not in texto:  # el folio siempre va en el asunto
        texto = f"{texto} ({folio})"
    return texto[:200]


def armar(*, folio: str, contacto: str, despacho: str, mensaje: str | None, calculo: dict, vence_en: datetime, url: str | None,
          nomira: dict, asunto_plantilla: str | None, con_pdf: bool) -> tuple[str, str, str]:
    nombre = nomira.get("nombre_comercial") or "Nomira"
    a = asunto(asunto_plantilla, folio, nombre, despacho)
    msg = (mensaje or MENSAJE_INICIAL).strip()
    paq, per = calculo["paquete"], calculo["periodicidad"]
    modulos = ", ".join(x["nombre"] for x in calculo["modulos"])
    vence = fecha_larga(vence_en, hora=True)
    filas = [("Paquete", f"{paq['nombre']} · cobro {per['nombre'].lower()}"), ("Módulos", modulos),
             ("Usuarios internos", str(calculo["usuarios"]["total"])), ("Almacenamiento", f"{calculo['almacenamiento']['total_gb']} GB"),
             ("Total con IVA", f"{pesos(calculo['total'])} MXN"), ("Vigencia", f"Hasta el {vence}")]
    tabla = "".join(f"""<tr><td style="padding:8px 0;border-bottom:1px solid #E7E1D6;color:#64748b;font-size:14px;width:40%">{escape(k)}</td>
<td style="padding:8px 0;border-bottom:1px solid #E7E1D6;color:{MARINO};font-size:14px;font-weight:600">{escape(v)}</td></tr>""" for k, v in filas)
    contacto_v = " · ".join(x for x in (nomira.get("correo_ventas"), nomira.get("telefono")) if x)
    html = _base(f"Su cotización {folio} vence el {vence}.", f"""
<p style="margin:0 0 6px;font-family:{FUENTE};font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{TURQUESA_700}">Cotización {escape(folio)}</p>
<p style="margin:0 0 16px">Hola {escape(contacto)}:</p>
<p style="margin:0 0 16px">{escape(msg).replace(chr(10), '<br>')}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 4px;font-family:{FUENTE}">{tabla}</table>
{_boton("Ver mi propuesta", url) if url else ""}
<p style="margin:16px 0 0;font-size:14px;color:#64748b">{"Adjuntamos también la cotización en PDF. " if con_pdf else ""}Desde la propuesta puede aceptarla o pedirnos ajustes.</p>
{f'<p style="margin:16px 0 0;font-size:14px;color:#64748b">Contacto comercial: {escape(contacto_v)}</p>' if contacto_v else ""}
""", pie=f"Recibe este correo porque pidió información a {nombre}.")
    texto = "\n".join([f"Hola {contacto}:", "", msg, "", f"Cotización {folio}"] + [f"- {k}: {v}" for k, v in filas]
                      + ([f"", f"Ver mi propuesta: {url}"] if url else []) + (["", "Adjuntamos la cotización en PDF."] if con_pdf else [])
                      + (["", f"Contacto comercial: {contacto_v}"] if contacto_v else []))
    return a, html, texto
