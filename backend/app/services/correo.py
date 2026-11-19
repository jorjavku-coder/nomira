"""Envío de correos: Resend (API por HTTPS) o SMTP. Configuración en config.py (CORREO_*)."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

import httpx

from ..config import ajustes


class CorreoError(Exception):
    """Mensaje pensado para mostrarse tal cual en el panel."""


def configurado() -> bool:
    a = ajustes()
    if a.correo_proveedor == "prueba":
        return True
    if a.correo_proveedor == "resend":
        return bool(a.resend_api_key)
    if a.correo_proveedor == "smtp":
        return bool(a.smtp_host and a.smtp_usuario and a.smtp_contrasena)
    return False


def descripcion() -> dict:
    """Para el panel: qué se usa, sin revelar claves."""
    a = ajustes()
    return {"configurado": configurado(), "proveedor": a.correo_proveedor or None,
            "remitente": a.correo_remitente, "servidor": a.smtp_host if a.correo_proveedor == "smtp" else None,
            "recordatorio_dias": a.recordatorio_dias, "url_publica": a.url_publica}


def enviar(destinatarios: list[str], asunto: str, html: str, texto: str) -> None:
    """Envía o lanza CorreoError. No reintenta: quien llama decide."""
    if not destinatarios:
        raise CorreoError("No hay destinatarios.")
    if not configurado():
        raise CorreoError("El envío de correos no está configurado (CORREO_PROVEEDOR).")
    a = ajustes()
    if modo_prueba():
        _prueba(destinatarios, asunto, html, texto)
    elif a.correo_proveedor == "resend":
        _resend(destinatarios, asunto, html, texto)
    else:
        _smtp(destinatarios, asunto, html, texto)


def modo_prueba() -> bool:
    """Fuera de producción nunca sale un correo real, salvo que se pida con CORREO_ENVIO_REAL=true."""
    a = ajustes()
    return a.correo_proveedor == "prueba" or (a.entorno != "produccion" and not a.correo_envio_real)


def _prueba(destinatarios: list[str], asunto: str, html: str, texto: str) -> None:
    """Modo de prueba: el correo se guarda en STORAGE_DIR/correos_prueba en vez de enviarse."""
    import json
    import time
    from pathlib import Path

    carpeta = Path(ajustes().storage_dir) / "correos_prueba"
    carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
    base = carpeta / f"{time.time():.6f}"
    base.with_suffix(".html").write_text(html, encoding="utf-8")
    base.with_suffix(".txt").write_text(texto, encoding="utf-8")
    base.with_suffix(".json").write_text(json.dumps({"para": destinatarios, "asunto": asunto}, ensure_ascii=False), encoding="utf-8")


def _resend(destinatarios: list[str], asunto: str, html: str, texto: str) -> None:
    a = ajustes()
    cuerpo = {"from": a.correo_remitente, "to": destinatarios, "subject": asunto, "html": html, "text": texto}
    if a.correo_responder_a:
        cuerpo["reply_to"] = a.correo_responder_a
    try:
        r = httpx.post("https://api.resend.com/emails", json=cuerpo, timeout=20,
                       headers={"Authorization": f"Bearer {a.resend_api_key}"})
    except httpx.HTTPError as e:
        raise CorreoError(f"No se pudo conectar con Resend ({type(e).__name__}).") from e
    if r.status_code >= 300:
        try:
            detalle = r.json().get("message") or r.text
        except ValueError:
            detalle = r.text
        raise CorreoError(f"Resend rechazó el envío ({r.status_code}): {detalle[:300]}")


def _smtp(destinatarios: list[str], asunto: str, html: str, texto: str) -> None:
    a = ajustes()
    m = EmailMessage()
    nombre, direccion = parseaddr(a.correo_remitente)
    m["From"] = formataddr((nombre, direccion or a.smtp_usuario))
    m["To"] = ", ".join(destinatarios)
    m["Subject"] = asunto
    m["Message-ID"] = make_msgid(domain=(direccion or a.smtp_usuario).split("@")[-1])
    if a.correo_responder_a:
        m["Reply-To"] = a.correo_responder_a
    m.set_content(texto)
    m.add_alternative(html, subtype="html")
    contexto = ssl.create_default_context()
    try:
        if a.smtp_puerto == 465:
            with smtplib.SMTP_SSL(a.smtp_host, a.smtp_puerto, timeout=20, context=contexto) as s:
                s.login(a.smtp_usuario, a.smtp_contrasena)
                s.send_message(m)
        else:
            with smtplib.SMTP(a.smtp_host, a.smtp_puerto, timeout=20) as s:
                s.starttls(context=contexto)
                s.login(a.smtp_usuario, a.smtp_contrasena)
                s.send_message(m)
    except smtplib.SMTPAuthenticationError as e:
        raise CorreoError("El servidor de correo rechazó el usuario o la contraseña (SMTP_USUARIO / SMTP_CONTRASENA).") from e
    except (TimeoutError, OSError) as e:
        if isinstance(e, smtplib.SMTPException):
            raise CorreoError(f"El servidor de correo rechazó el mensaje: {e}") from e
        raise CorreoError(f"No se pudo conectar a {a.smtp_host}:{a.smtp_puerto}. Si Nomira está en el plan "
                          "gratuito de Render, ese plan bloquea los puertos de correo: use Resend o un plan de pago.") from e
