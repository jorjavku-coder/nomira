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


PIE_CUENTA = "Recibe este correo porque su organización tiene una cuenta en Nomira."


def _base(preencabezado: str, contenido: str, pie: str = PIE_CUENTA) -> str:
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
      <br>{escape(pie)}
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
🎁 <b>Su prueba gratuita de 2 días está activa</b> hasta el <b>{fecha_larga(fin_prueba)}</b>.</td></tr></table>"""
        prueba_txt = f"Su prueba gratuita de 2 días está activa hasta el {fecha_larga(fin_prueba)}.\n\n"
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


def _lista(items: list[str]) -> str:
    filas = "".join(f'<tr><td style="padding:3px 10px 3px 0;color:{TURQUESA_700};vertical-align:top">•</td>'
                    f'<td style="padding:3px 0">{escape(i)}</td></tr>' for i in items)
    return f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="font-size:15px">{filas}</table>'


def solicitud_documentos(despacho: str, abogado: str, enlace: str, vence: date, mensaje: str | None,
                         documentos: list[str], requiere_codigo: bool) -> tuple[str, str, str]:
    """Al cliente del despacho: enlace para SUBIR documentos. No incluye datos del expediente."""
    asunto = f"{despacho} le solicita documentos"
    d, a = escape(despacho), escape(abogado)
    msj = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 20px">'
           f'<tr><td style="background:{CREMA};border-left:4px solid {TURQUESA};border-radius:8px;padding:14px 18px;'
           f'white-space:pre-line">{escape(mensaje)}</td></tr></table>') if mensaje else ""
    lista = (f'<p style="margin:0 0 8px;font-weight:700;color:{MARINO}">Documentos solicitados</p>'
             f'{_lista(documentos)}') if documentos else ""
    codigo = ("Al abrir el enlace le enviaremos un código de verificación a este mismo correo." if requiere_codigo else "")
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:24px;line-height:1.25;color:{MARINO}">Le solicitamos algunos documentos</h1>
<p style="margin:0 0 20px"><b>{a}</b>, de <b style="color:{MARINO}">{d}</b>, le pide que envíe documentos por este medio seguro.</p>
{msj}{lista}
{_boton("Enviar mis documentos", enlace)}
<p style="margin:0 0 6px;font-size:14px;color:#64748b">El enlace vence el <b>{fecha_larga(vence)}</b> y solo sirve para enviar archivos (PDF, JPG, PNG o WebP); no muestra ninguna información. {codigo}</p>
<p style="margin:16px 0 0;font-size:13px;color:#64748b">Si no esperaba este mensaje, ignórelo: nadie de {d} le pedirá contraseñas por correo.</p>"""
    texto = (f"{abogado}, de {despacho}, le pide que envíe documentos por un medio seguro.\n\n"
             + (f"{mensaje}\n\n" if mensaje else "")
             + ("Documentos solicitados:\n" + "\n".join(f"- {x}" for x in documentos) + "\n\n" if documentos else "")
             + f"Enviar documentos: {enlace}\n\nEl enlace vence el {fecha_larga(vence)} y solo sirve para enviar archivos. "
             + (codigo + "\n" if codigo else "\n")
             + f"\nSi no esperaba este mensaje, ignórelo.\n")
    return asunto, _base(f"{despacho} le pide documentos", contenido,
                         pie=f"Recibe este correo porque {despacho} le solicitó documentos por medio de Nomira."), texto


def codigo_verificacion(despacho: str, codigo: str, minutos: int, portal: bool = False) -> tuple[str, str, str]:
    asunto = f"Su código para {'entrar a su portal' if portal else 'enviar documentos'}: {codigo}"
    accion = "entrar al portal de" if portal else "enviar sus documentos a"
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:24px;line-height:1.25;color:{MARINO}">Su código de verificación</h1>
<p style="margin:0 0 20px">Escríbalo en la página para {accion} <b>{escape(despacho)}</b>.</p>
<p style="margin:0 0 20px;font-family:'Courier New',monospace;font-size:34px;font-weight:700;letter-spacing:8px;color:{MARINO}">{escape(codigo)}</p>
<p style="margin:0;font-size:14px;color:#64748b">Vence en {minutos} minutos. Si usted no lo pidió, ignore este correo.</p>"""
    texto = f"Su código para {accion} {despacho}: {codigo}\nVence en {minutos} minutos. Si usted no lo pidió, ignore este correo.\n"
    return asunto, _base(f"Código {codigo}", contenido, pie=f"Correo automático de Nomira para {despacho}."), texto


def documentos_recibidos(nombre: str, asunto_nombre: str, n: int, email_cliente: str, url: str) -> tuple[str, str, str]:
    """Al abogado: el cliente envió archivos; quedan pendientes de revisión."""
    asunto = f"Recibió {n} documento(s) del cliente — {asunto_nombre}"[:250]
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:24px;line-height:1.25;color:{MARINO}">Hola, {escape(nombre.split()[0])}: llegaron documentos</h1>
<p style="margin:0 0 16px"><b>{escape(email_cliente)}</b> envió <b>{n}</b> archivo(s) al asunto <b style="color:{MARINO}">{escape(asunto_nombre)}</b>.</p>
<p style="margin:0 0 4px">Quedaron como <b>«Recibido — pendiente de revisión»</b>: Nomira no los lee hasta que usted los acepte.</p>
{_boton("Revisar documentos", url)}"""
    texto = (f"{email_cliente} envió {n} archivo(s) al asunto {asunto_nombre}. Quedaron pendientes de revisión: "
             f"Nomira no los lee hasta que usted los acepte.\n\nRevisar: {url}\n")
    return asunto, _base(f"{n} documento(s) nuevos en {asunto_nombre}", contenido), texto


def codigo_cuenta(nombre: str, codigo: str, minutos: int, para: str) -> tuple[str, str, str]:
    """Código de 6 dígitos para confirmar el correo al registrarse («registro») o para cambiar la contraseña («recuperar»)."""
    registro = para == "registro"
    asunto = f"{'Confirme su correo' if registro else 'Restablezca su contraseña'} en Nomira: {codigo}"
    titulo = "Confirme su correo" if registro else "Restablezca su contraseña"
    motivo = ("Escríbalo en Nomira para crear su cuenta y empezar su prueba gratuita."
              if registro else "Escríbalo en Nomira para elegir una contraseña nueva.")
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:24px;line-height:1.25;color:{MARINO}">{titulo}</h1>
<p style="margin:0 0 20px">Hola {escape(nombre)}. {motivo}</p>
<p style="margin:0 0 20px;font-family:'Courier New',monospace;font-size:34px;font-weight:700;letter-spacing:8px;color:{MARINO}">{escape(codigo)}</p>
<p style="margin:0;font-size:14px;color:#64748b">Vence en {minutos} minutos. Si usted no lo pidió, ignore este correo: nadie podrá entrar sin el código.</p>"""
    texto = f"Hola {nombre}. {motivo}\nSu código: {codigo}\nVence en {minutos} minutos. Si usted no lo pidió, ignore este correo.\n"
    return asunto, _base(f"Código {codigo}", contenido, pie="Correo automático de Nomira."), texto


def bienvenida_prueba(nombre: str, organizacion: str, fin: date, modulos: list[str]) -> tuple[str, str, str]:
    asunto = f"Bienvenido a Nomira: su prueba gratuita termina el {fecha_larga(fin)}"
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:24px;line-height:1.25;color:{MARINO}">¡Bienvenido a Nomira, {escape(nombre)}!</h1>
<p style="margin:0 0 16px">La cuenta de <b>{escape(organizacion)}</b> está lista. Su prueba gratuita incluye:</p>
{_lista(modulos)}
<p style="margin:16px 0 0">Puede usarla hasta el <b>{fecha_larga(fin)}</b>. Al terminar, su información se conserva y puede contratar cuando quiera.</p>
{_boton("Entrar a Nomira", _url("/login"))}
<p style="margin:0;font-size:14px;color:#64748b">¿Dudas? Responda este correo y con gusto le ayudamos a configurar su primer caso.</p>"""
    texto = (f"¡Bienvenido a Nomira, {nombre}! La cuenta de {organizacion} está lista.\nMódulos de su prueba: {', '.join(modulos)}.\n"
             f"Su prueba gratuita termina el {fecha_larga(fin)}. Entre en {_url('/login')}\n")
    return asunto, _base("Su prueba gratuita de Nomira está lista", contenido), texto


def mensaje_de_cliente(nombre: str, cliente: str, motivo: str, url: str) -> tuple[str, str, str]:
    """Al abogado: un cliente escribió desde su portal. No incluye el texto del mensaje (se lee en Nomira)."""
    asunto = f"Mensaje nuevo de {cliente} — {motivo}"[:250]
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:24px;line-height:1.25;color:{MARINO}">Hola, {escape(nombre.split()[0])}: un cliente le escribió</h1>
<p style="margin:0 0 16px"><b>{escape(cliente)}</b> le envió un mensaje desde su portal: <b>{escape(motivo)}</b>.</p>
{_boton("Leer y responder", url)}"""
    texto = f"{cliente} le envió un mensaje desde su portal ({motivo}).\n\nLeer y responder: {url}\n"
    return asunto, _base(f"Mensaje nuevo de {cliente}", contenido), texto


def connect_aviso(despacho: str, nombre: str, asunto_nombre: str | None, titulo: str, parrafos: list[str], url: str,
                  accion: bool) -> tuple[str, str, str]:
    """Aviso al cliente de Nomira Connect. Solo dice QUÉ cambió; el detalle está en el portal seguro."""
    sobre = f" «{asunto_nombre}»" if asunto_nombre else ""
    asunto = f"{titulo}{sobre} — {despacho}"[:250]
    cuerpo = "".join(f'<p style="margin:0 0 10px">{escape(x)}</p>' for x in parrafos)
    alerta = (f'<p style="margin:0 0 14px;padding:10px 12px;border-radius:10px;background:#FEF3C7;color:#92400E;font-weight:600">'
              f'Necesitamos algo de usted para continuar.</p>') if accion else ""
    contenido = f"""
<h1 style="margin:0 0 8px;font-family:{TITULAR};font-size:24px;line-height:1.25;color:{MARINO}">Hola, {escape(nombre)}</h1>
<p style="margin:0 0 14px"><b>{escape(titulo)}</b>{escape(sobre)}.</p>
{alerta}{cuerpo}
{_boton("Ver el seguimiento completo", url)}
<p style="margin:12px 0 0;font-size:13px;color:#64748b">Es un enlace seguro y personal; al abrirlo le pediremos un código que llega a este correo. Vence en 14 días.</p>"""
    texto = (f"Hola, {nombre}.\n\n{titulo}{sobre}.\n" + ("Necesitamos algo de usted para continuar.\n" if accion else "")
             + "\n".join(parrafos) + f"\n\nConsulte el seguimiento completo en su portal seguro: {url}\n")
    return asunto, _base(titulo, contenido, pie=f"Aviso automático de {despacho} enviado con Nomira. Puede dejar de recibirlos desde su portal."), texto
