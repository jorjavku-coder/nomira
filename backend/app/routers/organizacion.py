"""Marca de la organización (cliente del SaaS): nombre y logotipo propios."""
import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, solo_admin, usuario_actual

router = APIRouter(prefix="/api/organizacion", tags=["organización"])
MAX_BYTES = 2 * 1024 * 1024
MAX_LADO = 600  # px del lado mayor tras normalizar
FORMATOS = {"PNG", "JPEG", "WEBP"}


def normalizar_logo(datos: bytes) -> bytes:
    """Valida que sea una imagen ráster real y la vuelve a codificar como PNG.
    Recodificar descarta metadatos y cualquier contenido incrustado; por eso no se admite SVG."""
    from PIL import Image

    if len(datos) > MAX_BYTES:
        raise HTTPException(413, "El logotipo no debe pesar más de 2 MB.")
    try:
        Image.MAX_IMAGE_PIXELS = 40_000_000
        with Image.open(io.BytesIO(datos)) as prueba:
            if prueba.format not in FORMATOS:
                raise HTTPException(415, "Use una imagen PNG, JPG o WebP.")
            prueba.verify()
        with Image.open(io.BytesIO(datos)) as img:
            img = img.convert("RGBA")
            if min(img.size) < 32:
                raise HTTPException(422, "La imagen es demasiado pequeña (mínimo 32 px por lado).")
            img.thumbnail((MAX_LADO, MAX_LADO))
            salida = io.BytesIO()
            img.save(salida, format="PNG", optimize=True)
            return salida.getvalue()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(415, "El archivo no es una imagen válida. Use PNG, JPG o WebP.")


def _org(db: Session, u: m.Usuario) -> m.Organizacion:
    return db.get(m.Organizacion, u.organizacion_id)


def _datos(o: m.Organizacion) -> dict:
    return {"id": o.id, "nombre": o.nombre, "tiene_logo": o.logo_actualizado is not None,
            "logo_version": o.logo_actualizado.isoformat() if o.logo_actualizado else None}


class Nombre(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)


@router.get("")
def ver(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _datos(_org(db, u))


@router.patch("")
def renombrar(d: Nombre, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    o = _org(db, u)
    o.nombre = d.nombre.strip()
    auditar(db, u, "organizacion_renombrada", "organizacion", o.id, request=request)
    db.commit()
    return _datos(o)


@router.get("/logo")
def logo(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Solo entrega el logotipo de la organización del propio usuario."""
    o = _org(db, u)
    if not o.logo:
        raise HTTPException(404, "La organización no tiene logotipo.")
    return Response(o.logo, media_type="image/png",
                    headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})


@router.put("/logo")
def subir_logo(request: Request, archivo: UploadFile = File(...), u: m.Usuario = Depends(solo_admin),
               db: Session = Depends(get_db)):
    png = normalizar_logo(archivo.file.read(MAX_BYTES + 1))
    o = _org(db, u)
    o.logo, o.logo_actualizado = png, m.ahora()
    auditar(db, u, "organizacion_logo_actualizado", "organizacion", o.id, {"bytes": len(png)}, request)
    db.commit()
    return _datos(o)


@router.delete("/logo")
def quitar_logo(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    o = _org(db, u)
    o.logo, o.logo_actualizado = None, None
    auditar(db, u, "organizacion_logo_eliminado", "organizacion", o.id, request=request)
    db.commit()
    return _datos(o)
