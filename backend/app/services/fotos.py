"""Fotos de perfil: se validan, se enderezan, se recortan en cuadrado y se reducen.

Nunca se guarda el archivo original (puede traer ubicación GPS y otros metadatos EXIF):
se vuelve a codificar como JPEG limpio de 256×256.
"""
from __future__ import annotations

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELES = 40_000_000  # protección contra «bombas» de descompresión
LADO = 256
FORMATOS = {"JPEG", "PNG", "WEBP", "GIF", "MPO"}  # MPO = JPEG de algunos celulares


class FotoInvalida(ValueError):
    pass


def procesar(datos: bytes) -> bytes:
    if len(datos) > MAX_BYTES:
        raise FotoInvalida("La foto excede 5 MB.")
    try:
        with Image.open(io.BytesIO(datos)) as im:
            if im.format not in FORMATOS:
                raise FotoInvalida("Use una imagen JPG, PNG o WEBP.")
            if im.width * im.height > MAX_PIXELES:
                raise FotoInvalida("La imagen es demasiado grande.")
            im = ImageOps.exif_transpose(im)  # fotos de celular giradas
            if im.mode in ("RGBA", "LA", "P"):
                fondo = Image.new("RGB", im.size, (255, 255, 255))
                im = im.convert("RGBA")
                fondo.paste(im, mask=im.split()[-1])
                im = fondo
            im = ImageOps.fit(im.convert("RGB"), (LADO, LADO), Image.Resampling.LANCZOS)
            salida = io.BytesIO()
            im.save(salida, "JPEG", quality=85, optimize=True)  # sin EXIF
            return salida.getvalue()
    except FotoInvalida:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise FotoInvalida("El archivo no es una imagen válida.")


def data_url(foto: bytes | None) -> str | None:
    return None if not foto else "data:image/jpeg;base64," + base64.b64encode(foto).decode()
