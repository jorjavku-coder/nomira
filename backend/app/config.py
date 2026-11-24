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
    # Entrar y registrarse con Google (OAuth 2.0, «ID de cliente» de tipo «Aplicación web» en Google Cloud).
    # URI de redirección autorizada: <URL_PUBLICA>/api/auth/google/callback. Vacíos: no se muestra el botón.
    google_client_id: str = ""
    google_client_secret: str = ""
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
    # --- Nomira AFORE ---
    afore_clave_cifrado: str = ""  # clave para cifrar CURP, NSS y tokens (vacío: se deriva de JWT_SECRETO)
    # WhatsApp Business Platform (Cloud API oficial de Meta): datos de la APP de Meta de la plataforma.
    # El número y el token de cada despacho se guardan cifrados en su configuración.
    whatsapp_verify_token: str = ""  # para validar la suscripción del webhook
    whatsapp_app_secret: str = ""  # para validar la firma X-Hub-Signature-256 de cada webhook
    whatsapp_api_version: str = "v21.0"
    # API oficial de CURP (opcional, deshabilitada sin credenciales y sin autorización por organización)
    curp_api_url: str = ""
    curp_api_key: str = ""
    # Stripe Checkout para cotizaciones (módulo Comercial).
    # STRIPE_MODO=prueba (por defecto): solo llaves de prueba (sk_test_/rk_test_), sin dinero real.
    # STRIPE_MODO=real: solo llaves reales (rk_live_ recomendada, o sk_live_) y cobros REALES.
    # Si la llave no corresponde al modo, Stripe queda desconectado: nunca se cobra por error.
    stripe_modo: str = "prueba"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Cuentas de demostración (admin/analista/consulta@demo.local). Su contraseña de ejemplo está en el
    # repositorio: en producción se reemplaza por DEMO_CONTRASENA (12+ caracteres) o, si falta, se desactivan.
    demo_contrasena: str = ""
    plataforma_admin_email: str = ""
    plataforma_admin_contrasena: str = ""

    # Lectura
    clave_regex: str = r"^\d{4}$"
    ocr_idioma: str = "spa"
    # Estrados digitales del TRIJAEM: revisión automática de los expedientes vigilados (false = solo cotejo manual).
    trijaem_estrados_activo: bool = True
    ocr_dpi: int = 300
    # Catálogos (tablas de claves): a 200 se leyó MEJOR que a 300 en el catálogo de referencia
    # (124/124 claves y 114 descripciones exactas contra 123 y 109), en ~25 % menos tiempo y ~1/3 menos memoria.
    ocr_dpi_catalogo: int = 200
    ocr_min_caracteres: int = 40  # menos texto nativo que esto => OCR
    ocr_confianza_minima: int = 70  # por debajo, la fila queda pendiente

    # IA opcional (apagada por defecto; nunca decide claves ni sumas)
    # La clave se toma de ANTHROPIC_API_KEY (variable de entorno estándar del SDK).
    ia_habilitada: bool = False
    ia_modelo: str = "claude-opus-5-5"
    piloto_contrasena: str = ""  # cuenta demo@nomirasoft.com (despacho piloto). Vacía: no se crea.
    tesis_sincronizar: bool = True  # Repositorio de datos abiertos de la SCJN; se detiene sola si la SCJN la bloquea
    tesis_repositorio_url: str = "https://bicentenario.scjn.gob.mx/repositorio-scjn/api/v1"
    tesis_por_tanda: int = 500  # tesis por hora como máximo (una por segundo)
    tesis_epoca_minima: int = 10  # Décima Época en adelante
    ia_modelo_asistente: str = "claude-sonnet-5-5"  # Asistente IA: más económico para poder incluirlo en todos los planes
    ia_usos_incluidos: int = 30  # Asistente IA: usos al mes incluidos en cualquier plan
    ia_usos_prueba: int = 10  # durante la prueba gratis de 7 días
    ia_paquete_usos: int = 100  # paquete extra (no caduca)
    ia_paquete_precio: str = "149"  # MXN antes de IVA  # Asistente IA: solicitudes por organización al mes (control de costo)


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
