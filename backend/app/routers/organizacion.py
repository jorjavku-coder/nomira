"""Marca de la organización (cliente del SaaS): nombre y logotipo propios."""
import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, solo_admin, usuario_actual
from ..services import modulos

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
    return {**_datos(_org(db, u)), "modulos": modulos.estado(db, u.organizacion_id)}


class Activacion(BaseModel):
    activo: bool


@router.get("/modulos")
def ver_modulos(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return modulos.estado(db, u.organizacion_id)


@router.patch("/modulos/{modulo}")
def activar_modulo(modulo: str, d: Activacion, request: Request, u: m.Usuario = Depends(solo_admin),
                   db: Session = Depends(get_db)):
    """El administrador del despacho activa o desactiva un módulo contratado. Desactivar no borra datos."""
    antes = modulos.estado(db, u.organizacion_id).get(modulo, {}).get("activo")
    nuevo = modulos.fijar(db, u.organizacion_id, modulo, activo=d.activo)
    if antes != d.activo:
        auditar(db, u, "modulo_activado" if d.activo else "modulo_desactivado", "organizacion", u.organizacion_id,
                {"modulo": modulo}, request)
    db.commit()
    return nuevo


@router.get("/modulos/tienda")
def tienda(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Todos los módulos con su estado, precio mensual + IVA y la suscripción en línea, si la hay."""
    from ..services import modulos_compra as mc
    return {**mc.catalogo(db, _org(db, u)), "es_admin": u.rol == "administrador"}


@router.post("/modulos/{modulo}/contratar")
def contratar_modulo(modulo: str, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """En prueba: se enciende gratis hasta que termine la prueba. Si no: liga de pago de Stripe con cargo mensual automático;
    el módulo se enciende cuando Stripe confirma el pago."""
    from ..config import ajustes
    from ..services import modulos_compra as mc
    from ..services.comercial import base as cm
    from ..services.comercial import stripe as st

    if modulo not in modulos.MODULOS:
        raise HTTPException(404, "Módulo desconocido.")
    o = _org(db, u)
    if modulos.estado(db, o.id)[modulo]["contratado"]:
        nuevo = modulos.fijar(db, o.id, modulo, activo=True)
        db.commit()
        return {"activado": True, "modulo": nuevo}
    if mc.en_prueba(db, o):
        mc.activar_en_prueba(db, o, modulo)
        auditar(db, u, "modulo_activado_en_prueba", "organizacion", o.id, {"modulo": modulo}, request)
        db.commit()
        return {"activado": True, "en_prueba": True}
    p = mc.precio(db, modulo)
    if not p:
        raise HTTPException(409, "Este módulo no tiene precio publicado. Escríbanos a Soporte para contratarlo.")
    if not cm.stripe_estado()["conectado"]:
        raise HTTPException(409, "El pago en línea no está disponible por ahora. Escríbanos a Soporte y lo activamos.")
    if mc.vigente(db, o.id, modulo):
        raise HTTPException(409, "Ya tiene una suscripción a este módulo.")
    s = m.MdSuscripcion(organizacion_id=o.id, modulo=modulo, usuario_id=u.id, precio=p["precio"], iva=p["iva"], total=p["total"])
    db.add(s)
    db.flush()
    base_url = ajustes().url_publica.rstrip("/")
    try:
        sesion = st.crear_suscripcion(nombre=f"Nomira · {modulos.MODULOS[modulo]['nombre']} (mensual)", total_mensual=s.total, email=u.email,
                                      url_exito=f"{base_url}/organizacion?compra=procesando&modulo={modulo}",
                                      url_cancelar=f"{base_url}/organizacion?compra=cancelada",
                                      idempotencia=f"nomira-modulo-{s.id}", referencia=f"modulo-{modulo}-org-{o.id}",
                                      metadata={"tipo": "modulo", "suscripcion_id": str(s.id), "modulo": modulo, "organizacion_id": str(o.id)})
    except st.StripeError as e:
        db.rollback()
        raise HTTPException(502, str(e))
    s.stripe_sesion = sesion["id"]
    auditar(db, u, "modulo_compra_iniciada", "md_suscripcion", s.id, {"modulo": modulo}, request)
    db.commit()
    return {"url": sesion["url"]}


@router.post("/modulos/{modulo}/cancelar")
def cancelar_modulo(modulo: str, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Cancela la suscripción en línea: el módulo sigue hasta el fin del mes pagado y entonces se apaga (sin borrar datos)."""
    from ..services import modulos_compra as mc
    from ..services.comercial import stripe as st

    s = mc.vigente(db, u.organizacion_id, modulo)
    if not s or not s.stripe_suscripcion:
        raise HTTPException(404, "Este módulo no tiene una suscripción en línea. Para cambios de su plan, escríbanos a Soporte.")
    try:
        st.cancelar_al_final(s.stripe_suscripcion)
    except st.StripeError as e:
        raise HTTPException(502, str(e))
    s.estado = "cancelando"
    auditar(db, u, "modulo_cancelacion_solicitada", "md_suscripcion", s.id, {"modulo": modulo}, request)
    db.commit()
    return {"ok": True}


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
