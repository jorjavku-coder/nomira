"""Plantillas de correo de Nomira (HTML compatible con Gmail/Outlook + versión de texto).

Reglas de HTML para correo: tablas para la maquetación, estilos en línea, ancho máximo de 600 px,
sin CSS externo ni JavaScript, y todo dato variable escapado con html.escape.
"""
from __future__ import annotations

from datetime import date
from html import escape
from urllib.parse import quote

from ..config import ajustes

MARINO, MARINO_900, TURQUESA, TURQUESA_700, CREMA, CREMA_300 = "#123048", "#0A1B2B", "#01B2A6", "#047A72", "#FCF9F4", "#E7E1D6"
FUENTE = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
TITULAR = "Montserrat,'Segoe UI',Helvetica,Arial,sans-serif"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def fecha_larga(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _url(ruta: str = "") -> str:
    return ajustes().url_publica.rstrip("/") + ruta


def _boton(texto: str, url: str) -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 8px">
  <tr><td align="center" bgcolor="{TURQUESA}" style="border-radius:12px">
    <a href="{escape(url)}" target="_blank" style="display:inline-block;padding:14px 28px;font-family:{FUENTE};font-size:16px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:12px">{escape(texto)}</a>
  </td></tr></table>"""


def _base(preencabezado: str, contenido: str) -> str:
    logo = _url("/correo/logo.png")
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><title>Nomira</title></head>
<body style="margin:0;padding:0;background:{CREMA};-webkit-text-size-adjust:100%">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{CREMA}">{escape(preencabezado)}&#8199;&#65279;&#847;&#8199;&#65279;&#847;&#8199;&#65279;&#847;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{CREMA}">
<tr><td align="center" style="padding:32px 12px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px">
    <tr><td style="background:{MARINO_900};border-radius:20px 20px 0 0;padding:28px 36px">
      <img src="{logo}" width="150" alt="nomira" style="display:block;border:0;width:150px;height:auto;color:#ffffff;font-family:{TITULAR};font-size:26px;font-weight:800">
    </td></tr>
    <tr><td style="height:4px;background:{TURQUESA};line-height:4px;font-size:0">&nbsp;</td></tr>
    <tr><td style="background:#ffffff;border-radius:0 0 20px 20px;padding:36px;font-family:{FUENTE};font-size:16px;line-height:1.6;color:#334155">
      {contenido}
    </td></tr>
    <tr><td style="padding:24px 36px;font-family:{FUENTE};font-size:12px;line-height:1.6;color:#64748b;text-align:center">
      Nomira · Cada prestación, en claro<br>
      <a href="{_url()}" style="color:{TURQUESA_700};text-decoration:none">{escape(_url().split('://')[-1])}</a>
      <br>Recibe este correo porque su organización tiene una cuenta en Nomira.
    </td></tr>
  </table>
</td></tr></table></body></html>"""


def bienvenida(nombre: str, organizacion: str, email: str, contrasena_temporal: str,
               fin_prueba: date | None = None) -> tuple[str, str, str]:
    """Correo con el acceso de un cliente nuevo. Devuelve (asunto, html, texto)."""
    asunto = f"Bienvenido a Nomira, {nombre.split()[0]}: aquí está su acceso"
    login = _url("/login")
    n, o, e, c = escape(nombre), escape(organizacion), escape(email), escape(contrasena_temporal)
    prueba_html = prueba_txt = ""
    if fin_prueba:
        prueba_html = f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px">
<tr><td style="background:#E0F2FE;border-radius:12px;padding:14px 18px;font-size:15px;color:#075985">
🎁 <b>Su prueba gratuita de 7 días está activa</b> hasta el <b>{fecha_larga(fin_prueba)}</b>.</td></tr></table>"""
        prueba_txt = f"Su prueba gratuita de 7 días está activa hasta el {fecha_larga(fin_prueba)}.\n\n"
    pasos = [("Cambie su contraseña", "En «Mi perfil», en cuanto entre por primera vez."),
             ("Cargue su catálogo", "En «Catálogos», desde el PDF de su catálogo de prestaciones."),
             ("Cree su primer expediente", "Suba los comprobantes en PDF y revise el desglose por quincena.")]
    filas = "".join(f"""<tr><td valign="top" style="padding:0 14px 14px 0;width:28px">
<div style="width:28px;height:28px;border-radius:14px;background:{MARINO};color:#fff;font-family:{TITULAR};font-weight:800;font-size:14px;line-height:28px;text-align:center">{i}</div></td>
<td valign="top" style="padding:0 0 14px;font-size:15px;color:#334155"><b style="color:{MARINO}">{t}</b><br>{d}</td></tr>"""
                    for i, (t, d) in enumerate(pasos, 1))
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:26px;line-height:1.25;color:{MARINO}">¡Bienvenido a Nomira, {n}!</h1>
<p style="margin:0 0 24px">Ya está lista la cuenta de <b style="color:{MARINO}">{o}</b>. Con Nomira obtiene el desglose de prestaciones por quincena a partir de los comprobantes de nómina, con cada cifra ligada a su origen.</p>
{prueba_html}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{CREMA};border:1px solid {CREMA_300};border-radius:16px">
<tr><td style="padding:22px 24px">
  <div style="font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{TURQUESA_700};margin-bottom:12px">Sus datos de acceso</div>
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="font-size:15px">
    <tr><td style="padding:4px 18px 4px 0;color:#64748b">Dirección</td><td style="padding:4px 0"><a href="{login}" style="color:{TURQUESA_700};font-weight:600">{escape(login.split('://')[-1])}</a></td></tr>
    <tr><td style="padding:4px 18px 4px 0;color:#64748b">Usuario</td><td style="padding:4px 0;font-weight:600;color:{MARINO}">{e}</td></tr>
    <tr><td style="padding:4px 18px 4px 0;color:#64748b">Contraseña temporal</td>
        <td style="padding:4px 0"><span style="display:inline-block;background:#ffffff;border:1px dashed {TURQUESA};border-radius:8px;padding:4px 10px;font-family:Consolas,'Courier New',monospace;font-size:16px;font-weight:700;color:{MARINO};letter-spacing:.02em">{c}</span></td></tr>
  </table>
</td></tr></table>
{_boton("Entrar a Nomira", login)}
<p style="margin:0 0 28px;font-size:13px;color:#64748b">Por seguridad, cambie la contraseña temporal la primera vez que entre. Nadie de Nomira se la pedirá nunca.</p>
<h2 style="margin:0 0 16px;font-family:{TITULAR};font-size:18px;color:{MARINO}">Primeros pasos</h2>
<table role="presentation" cellpadding="0" cellspacing="0" border="0">{filas}</table>
<p style="margin:12px 0 0;font-size:15px">¿Dudas? Escríbanos desde la sección <b>Soporte</b> dentro de Nomira o responda a este correo.</p>
<p style="margin:16px 0 0;font-size:15px">— El equipo de Nomira</p>"""
    texto = (f"¡Bienvenido a Nomira, {nombre}!\n\nYa está lista la cuenta de {organizacion}.\n\n{prueba_txt}"
             f"SUS DATOS DE ACCESO\nDirección: {login}\nUsuario: {email}\nContraseña temporal: {contrasena_temporal}\n\n"
             "Por seguridad, cambie la contraseña temporal la primera vez que entre (en «Mi perfil»).\n\n"
             "PRIMEROS PASOS\n" + "\n".join(f"{i}. {t}: {d}" for i, (t, d) in enumerate(pasos, 1)) +
             "\n\n¿Dudas? Escríbanos desde la sección Soporte dentro de Nomira o responda a este correo.\n\n— El equipo de Nomira\n")
    return asunto, _base(f"Su acceso a Nomira para {organizacion}", contenido), texto


def recordatorio_vencimiento(nombre: str, organizacion: str, plan: str, fin: date, dias: int,
                             monto: str | None = None) -> tuple[str, str, str]:
    """Aviso de que el plan vence pronto. `dias` = días que faltan (0 = vence hoy)."""
    cuando = "hoy" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"
    asunto = f"Su plan de Nomira vence {cuando} ({fin.day} de {MESES[fin.month - 1]})"
    n, o, p = escape(nombre.split()[0]), escape(organizacion), escape(plan.lower())
    wa = "".join(ch for ch in ajustes().whatsapp_contacto if ch.isdigit())
    contacto_url = (f"https://wa.me/{wa}?text=" + quote("Hola, quiero renovar mi plan de Nomira.")) if 10 <= len(wa) <= 15 else _url("/app")
    contacto_txt = "Escríbanos por WhatsApp" if 10 <= len(wa) <= 15 else "Entrar a Nomira"
    monto_html = f'<tr><td style="padding:4px 18px 4px 0;color:#64748b">Monto</td><td style="padding:4px 0;font-weight:600;color:{MARINO}">${escape(monto)} MXN</td></tr>' if monto else ""
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:24px;line-height:1.25;color:{MARINO}">Hola, {n}: su plan vence {cuando}</h1>
<p style="margin:0 0 24px">Le recordamos que el plan <b>{p}</b> de <b style="color:{MARINO}">{o}</b> termina el <b>{fecha_larga(fin)}</b>. Para seguir usando Nomira sin interrupciones, renuévelo antes de esa fecha.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:16px">
<tr><td style="padding:20px 24px">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="font-size:15px">
    <tr><td style="padding:4px 18px 4px 0;color:#64748b">Plan</td><td style="padding:4px 0;font-weight:600;color:{MARINO}">{escape(plan)}</td></tr>
    <tr><td style="padding:4px 18px 4px 0;color:#64748b">Vence</td><td style="padding:4px 0;font-weight:600;color:#B45309">{fecha_larga(fin)}</td></tr>
    {monto_html}
  </table>
</td></tr></table>
{_boton(contacto_txt, contacto_url)}
<p style="margin:0 0 0;font-size:14px;color:#64748b">Sus expedientes, catálogos y usuarios se conservan. Si ya realizó su pago, puede ignorar este mensaje o responder a este correo con su comprobante.</p>
<p style="margin:20px 0 0;font-size:15px">Gracias por confiar en Nomira.<br>— El equipo de Nomira</p>"""
    texto = (f"Hola, {nombre.split()[0]}:\n\nLe recordamos que el plan {plan.lower()} de {organizacion} termina el "
             f"{fecha_larga(fin)}. Para seguir usando Nomira sin interrupciones, renuévelo antes de esa fecha.\n\n"
             + (f"Monto: ${monto} MXN\n\n" if monto else "")
             + (f"Escríbanos por WhatsApp: https://wa.me/{wa}\n\n" if 10 <= len(wa) <= 15 else "")
             + "Si ya realizó su pago, puede ignorar este mensaje o responder con su comprobante.\n\n— El equipo de Nomira\n")
    return asunto, _base(f"El plan de {organizacion} vence el {fecha_larga(fin)}", contenido), texto
