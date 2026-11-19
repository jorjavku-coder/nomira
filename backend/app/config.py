"""Configuración por variables de entorno. Ningún secreto vive en el código."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETO_INSEGURO = "cambia-este-secreto"


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    entorno: str = "desarrollo"  # desarrollo | produccion
    database_url: str = "postgresql+psycopg://qc:qc@localhost:5432/quincena"
    jwt_secreto: str = SECRETO_INSEGURO
    jwt_minutos: int = 480
    storage_dir: str = "./almacen"
    max_mb_archivo: int = 40
    max_paginas_pdf: int = 400
    cors_origenes: str = "http://localhost:3000"
    permitir_registro: bool = True
    zona_horaria: str = "America/Mexico_City"
    # Encabezado con la IP real del cliente, SOLO si lo pone un proxy de confianza que impide
    # falsificarlo (p. ej. «True-Client-IP» en Render, que lo fija Cloudflare). Vacío = IP de la conexión.
    # No use X-Forwarded-For: Next.js lo reenvía tal como lo manda el navegador.
    ip_cliente_encabezado: str = ""
    # Correos (separados por coma) de quienes operan la plataforma: ven las solicitudes de
    # informes y suscripción. No es un rol de organización.
    # Primer administrador del panel de la plataforma (/plataforma). Si no existe al arrancar, se
    # crea con estos datos; después la contraseña se cambia desde el panel y estos valores se ignoran.
    # Número de WhatsApp del botón del sitio público, con lada de país (p. ej. 5215512345678).
    # Vacío: no se muestra el botón.
    whatsapp_contacto: str = ""
    # Dirección pública para los enlaces de los correos (sin «/» al final).
    url_publica: str = "http://localhost:3000"
    # Envío de correos. CORREO_PROVEEDOR: «resend» (API por HTTPS; funciona en el plan gratuito de
    # Render), «smtp» (p. ej. el correo de su hosting; Render solo lo permite en planes de pago) o
    # vacío (no se envía nada; el panel lo indica).
    correo_proveedor: str = ""
    correo_remitente: str = "Nomira <hola@nomirasoft.com>"
    correo_responder_a: str = ""
    resend_api_key: str = ""
    # Fuera de producción los correos se guardan en STORAGE_DIR/correos_prueba (no se envían) salvo esto:
    correo_envio_real: bool = False
    smtp_host: str = ""
    smtp_puerto: int = 465  # 465 = SSL; 587 = STARTTLS
    smtp_usuario: str = ""
    smtp_contrasena: str = ""
    # Recordatorio a los administradores del cliente cuando faltan estos días (o menos) para que
    # venza su plan de pago sin renovación registrada. 0 = desactivado.
    recordatorio_dias: int = 7
    plataforma_admin_email: str = ""
    plataforma_admin_contrasena: str = ""

    # Lectura
    clave_regex: str = r"^\d{4}$"
    ocr_idioma: str = "spa"
    ocr_dpi: int = 300
    ocr_min_caracteres: int = 40  # menos texto nativo que esto => OCR
    ocr_confianza_minima: int = 70  # por debajo, la fila queda pendiente

    # IA opcional (apagada por defecto; nunca decide claves ni sumas)
    # La clave se toma de ANTHROPIC_API_KEY (variable de entorno estándar del SDK).
    ia_habilitada: bool = False
    ia_modelo: str = "claude-opus-5-5"


@lru_cache
def ajustes() -> Ajustes:
    a = Ajustes()
    # Las plataformas de alojamiento suelen entregar «postgres://…»; se adapta al controlador usado.
    for prefijo in ("postgres://", "postgresql://"):
        if a.database_url.startswith(prefijo):
            a.database_url = "postgresql+psycopg://" + a.database_url[len(prefijo):]
    if a.entorno == "produccion" and (a.jwt_secreto == SECRETO_INSEGURO or len(a.jwt_secreto) < 32):
        raise RuntimeError("JWT_SECRETO debe definirse (32+ caracteres) en producción.")
    return a
