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
    if a.entorno == "produccion" and (a.jwt_secreto == SECRETO_INSEGURO or len(a.jwt_secreto) < 32):
        raise RuntimeError("JWT_SECRETO debe definirse (32+ caracteres) en producción.")
    return a
