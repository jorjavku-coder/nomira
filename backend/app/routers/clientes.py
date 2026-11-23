"""Clientes del despacho (mini CRM incluido en todos los planes): directorio, ficha con todo lo del cliente en los
módulos, documentos, alta desde constancia fiscal o Excel, honorarios, pagos, recibos y recordatorios.

Leer: cualquier rol. Capturar y cobrar: administrador y analista. Borrar: administrador.
Todo se filtra por organización."""
from __future__ import annotations

import hashlib
import mimetypes
import uuid
from datetime import date
from decimal import Decimal
from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, condecimal
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, puede_editar, solo_admin, usuario_actual
from ..services import almacenamiento as almacen, correo, envios, modulos
from ..services.agenda.base import hoy
from ..services.clientes import base as cb, lectura
from ..services.plantillas_correo import _base, fecha_larga

router = APIRouter(prefix="/api/clientes", tags=["Clientes del despacho"])
MAX_DOC = 15 * 1024 * 1024
MAX_TABLA = 5 * 1024 * 1024
PERMITIDOS = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
Monto = condecimal(gt=0, max_digits=12, decimal_places=2)


def _cliente(db: Session, cid: int, u: m.Usuario) -> m.CrCliente:
    return cb.de_org(db, cid, u.organizacion_id)


def _nombres(db: Session, org: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org)).all())


def _dict(c: m.CrCliente, nombres: dict, cta: cb.Cuenta | None = None) -> dict:
    return {"id": c.id, "tipo": c.tipo, "nombre": c.nombre, "rfc": c.rfc, "curp_pista": c.curp_pista, "email": c.email, "telefono": c.telefono,
            "domicilio": c.domicilio, "codigo_postal": c.codigo_postal, "regimen_fiscal": c.regimen_fiscal, "contacto": c.contacto,
            "notas": c.notas, "etiquetas": c.etiquetas or [], "responsable_id": c.responsable_id, "responsable": nombres.get(c.responsable_id),
            "estado": c.estado, "origen": c.origen, "creado_en": c.creado_en.isoformat(),
            "cuenta": (cta or cb.Cuenta()).resumen()}


# ------------------------------------------------------------------ directorio

@router.get("")
def lista(q: str | None = None, estado: str = "activo", filtro: str | None = None, responsable_id: int | None = None,
          u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    s = select(m.CrCliente).where(m.CrCliente.organizacion_id == u.organizacion_id)
    if estado != "todos":
        s = s.where(m.CrCliente.estado == estado)
    if responsable_id:
        s = s.where(m.CrCliente.responsable_id == responsable_id)
    if q and q.strip():
        t = f"%{q.strip()[:80]}%"
        s = s.where(or_(m.CrCliente.nombre.ilike(t), m.CrCliente.rfc.ilike(t), m.CrCliente.email.ilike(t), m.CrCliente.telefono.ilike(t),
                        m.CrCliente.contacto.ilike(t)))
    cuentas = cb.cuentas_org(db, u.organizacion_id, hoy())
    nombres = _nombres(db, u.organizacion_id)
    filas = [_dict(c, nombres, cuentas.get(c.id)) for c in db.scalars(s.order_by(m.CrCliente.nombre).limit(2000))]
    if filtro == "con_saldo":
        filas = [f for f in filas if Decimal(f["cuenta"]["saldo"]) > 0]
    elif filtro == "vencidos":
        filas = [f for f in filas if Decimal(f["cuenta"]["vencido"]) > 0]
    tot = {"clientes": db.scalar(select(m.CrCliente.id).where(m.CrCliente.organizacion_id == u.organizacion_id).limit(1)) is not None,
           "por_cobrar": str(sum((max(c.saldo, cb.CERO) for c in cuentas.values()), cb.CERO)),
           "vencido": str(sum((c.vencido for c in cuentas.values()), cb.CERO))}
    inicio = hoy().replace(day=1)
    tot["cobrado_mes"] = str(sum((p.monto for p in db.scalars(select(m.CrPago).where(
        m.CrPago.organizacion_id == u.organizacion_id, m.CrPago.cancelado_en.is_(None), m.CrPago.fecha >= inicio))), cb.CERO))
    return {"clientes": filas, "totales": tot, "puede_editar": u.rol in ("administrador", "analista"),
            "sugerencias": len(cb.sugerencias(db, u.organizacion_id)) if u.rol in ("administrador", "analista") else 0}


@router.get("/buscar")
def buscar(q: str = "", u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Para el selector de cliente de los módulos."""
    s = select(m.CrCliente).where(m.CrCliente.organizacion_id == u.organizacion_id, m.CrCliente.estado == "activo")
    if q.strip():
        t = f"%{q.strip()[:80]}%"
        s = s.where(or_(m.CrCliente.nombre.ilike(t), m.CrCliente.rfc.ilike(t), m.CrCliente.email.ilike(t)))
    return [{"id": c.id, "nombre": c.nombre, "rfc": c.rfc, "email": c.email, "telefono": c.telefono, "tipo": c.tipo}
            for c in db.scalars(s.order_by(m.CrCliente.nombre).limit(20))]


class ClienteIn(BaseModel):
    tipo: str = "fisica"
    nombre: str = Field(min_length=2, max_length=250)
    rfc: str | None = Field(None, max_length=20)
    curp: str | None = Field(None, max_length=20)  # vacío al editar = se conserva la guardada
    borrar_curp: bool = False
    email: str | None = Field(None, max_length=254)
    telefono: str | None = Field(None, max_length=30)
    domicilio: str | None = Field(None, max_length=500)
    codigo_postal: str | None = Field(None, max_length=10)
    regimen_fiscal: str | None = Field(None, max_length=200)
    contacto: str | None = Field(None, max_length=200)
    notas: str | None = Field(None, max_length=5000)
    etiquetas: list[str] = Field(default_factory=list, max_length=20)
    responsable_id: int | None = None
    origen: str = "manual"


def _aplicar(db: Session, c: m.CrCliente, d: ClienteIn, u: m.Usuario) -> None:
    if d.tipo not in ("fisica", "moral"):
        raise HTTPException(422, "Tipo de persona no válido.")
    email = cb.txt(d.email, 254)
    if email and not lectura.EMAIL.fullmatch(email):
        raise HTTPException(422, "Revise el correo electrónico.")
    cp = cb.txt(d.codigo_postal, 10)
    if cp and not (cp.isdigit() and len(cp) == 5):
        raise HTTPException(422, "El código postal debe tener 5 dígitos.")
    if d.responsable_id:
        r = db.get(m.Usuario, d.responsable_id)
        if not r or r.organizacion_id != u.organizacion_id:
            raise HTTPException(422, "Responsable no válido.")
    c.tipo, c.nombre, c.rfc = d.tipo, cb.txt(d.nombre, 250), cb.limpiar_rfc(d.rfc)
    c.email, c.telefono = email.lower() if email else None, cb.txt(d.telefono, 20)
    c.domicilio, c.codigo_postal, c.regimen_fiscal = cb.txt(d.domicilio, 500), cp, cb.txt(d.regimen_fiscal, 200)
    c.contacto, c.notas = cb.txt(d.contacto, 200), (d.notas or "").strip()[:5000] or None
    c.etiquetas = list(dict.fromkeys(t.strip()[:40] for t in d.etiquetas if t and t.strip()))[:20]
    c.responsable_id = d.responsable_id
    if d.borrar_curp:
        cb.fijar_curp(c, None)
    elif d.curp and d.curp.strip():
        cb.fijar_curp(c, d.curp)
    if c.tipo == "moral" and c.curp_cifrado:
        cb.fijar_curp(c, None)


def _duplicado(db: Session, org: int, c: m.CrCliente) -> m.CrCliente | None:
    s = select(m.CrCliente).where(m.CrCliente.organizacion_id == org, m.CrCliente.id != (c.id or 0))
    if c.rfc:
        x = db.scalar(s.where(m.CrCliente.rfc == c.rfc).limit(1))
        if x:
            return x
    k = cb.plano(c.nombre)
    return next((x for x in db.scalars(s) if cb.plano(x.nombre) == k), None)


@router.post("", status_code=201)
def crear(d: ClienteIn, request: Request, permitir_duplicado: bool = False, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = m.CrCliente(organizacion_id=u.organizacion_id, creado_por_id=u.id, responsable_id=u.id,
                    origen=d.origen if d.origen in ("manual", "constancia") else "manual")
    _aplicar(db, c, d, u)
    c.responsable_id = d.responsable_id or u.id
    dup = _duplicado(db, u.organizacion_id, c)
    if dup and not permitir_duplicado:
        raise HTTPException(409, f"Ya existe «{dup.nombre}» con {'ese RFC' if c.rfc and dup.rfc == c.rfc else 'ese nombre'}. "
                                 f"Ábralo desde Clientes o confirme que es otra persona.")
    db.add(c)
    db.flush()
    auditar(db, u, "cliente_creado", "cr_cliente", c.id, {"origen": c.origen}, request)
    db.commit()
    return ver(c.id, u, db)


@router.get("/{cid}")
def ver(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    nombres = _nombres(db, u.organizacion_id)
    cargos = list(db.scalars(select(m.CrCargo).where(m.CrCargo.cliente_id == c.id)))
    pagos = list(db.scalars(select(m.CrPago).where(m.CrPago.cliente_id == c.id).order_by(m.CrPago.fecha.desc(), m.CrPago.id.desc())))
    cta = cb.cuenta(cargos, pagos, hoy())
    docs = db.scalars(select(m.CrDocumento).where(m.CrDocumento.cliente_id == c.id).order_by(m.CrDocumento.id.desc())).all()
    conceptos = {x.id: x.concepto for x in cargos}
    activos = modulos.activos(db, u.organizacion_id)
    return {**_dict(c, nombres, cta), "cargos": cta.cargos,
            "pagos": [_pago_dict(p, nombres, conceptos) for p in pagos],
            "documentos": [{"id": x.id, "tipo": x.tipo, "tipo_texto": cb.TIPOS_DOC.get(x.tipo, x.tipo), "nombre": x.nombre, "tamano": x.tamano,
                            "mime": x.mime, "subido_por": nombres.get(x.subido_por_id), "creado_en": x.creado_en.isoformat()} for x in docs],
            "vinculos": cb.vinculos(db, c), "modulos": [k for k in cb.VINCULOS if cb.VINCULOS[k][0] in activos],
            "puede_editar": u.rol in ("administrador", "analista"), "es_admin": u.rol == "administrador",
            "correo_disponible": correo.configurado(), "tipos_documento": cb.TIPOS_DOC, "metodos": cb.METODOS}


@router.put("/{cid}")
def editar(cid: int, d: ClienteIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    _aplicar(db, c, d, u)
    for modulo, (mod, modelo, campo, *_r) in cb.VINCULOS.items():  # el nombre en Evidencia se mantiene al día
        if modulo == "evidencia" and mod in modulos.activos(db, u.organizacion_id):
            for x in db.scalars(select(modelo).where(modelo.cr_cliente_id == c.id)):
                x.cliente = c.nombre[:200]
    auditar(db, u, "cliente_editado", "cr_cliente", c.id, None, request)
    db.commit()
    return ver(c.id, u, db)


class EstadoIn(BaseModel):
    estado: str


@router.put("/{cid}/estado")
def cambiar_estado(cid: int, d: EstadoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    if d.estado not in ("activo", "inactivo"):
        raise HTTPException(422, "Estado no válido.")
    c.estado = d.estado
    auditar(db, u, "cliente_estado", "cr_cliente", c.id, {"estado": d.estado}, request)
    db.commit()
    return ver(c.id, u, db)


@router.delete("/{cid}")
def eliminar(cid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Solo si no tiene pagos registrados ni nada ligado en los módulos; si no, se marca como inactivo."""
    c = _cliente(db, cid, u)
    if db.scalar(select(m.CrPago.id).where(m.CrPago.cliente_id == c.id).limit(1)):
        raise HTTPException(409, "Este cliente tiene pagos registrados: no se puede borrar. Márquelo como inactivo.")
    if cb.vinculos(db, c):
        raise HTTPException(409, "Este cliente está ligado a asuntos o expedientes de los módulos. Desligue primero o márquelo como inactivo.")
    for x in db.scalars(select(m.CrDocumento).where(m.CrDocumento.cliente_id == c.id)):
        Path(ajustes().storage_dir, x.archivo).unlink(missing_ok=True)
    db.delete(c)
    auditar(db, u, "cliente_eliminado", "cr_cliente", cid, None, request)
    db.commit()
    almacen.olvidar(u.organizacion_id)
    return {"ok": True}


# ------------------------------------------------------------------ alta sin capturar

@router.post("/leer-constancia")
async def leer_constancia(archivo: UploadFile = File(...), u: m.Usuario = Depends(puede_editar)):
    """Lee la Constancia de Situación Fiscal y PROPONE los datos; no guarda nada."""
    contenido = await archivo.read(MAX_DOC + 1)
    if len(contenido) > MAX_DOC:
        raise HTTPException(413, "El PDF pesa más de 15 MB.")
    if not contenido.startswith(b"%PDF"):
        raise HTTPException(422, "Suba la constancia en PDF, tal como la descarga del SAT.")
    try:
        texto = lectura.texto_pdf(contenido)
    except Exception:
        raise HTTPException(422, "No se pudo leer el PDF.")
    if len(texto.strip()) < 30:
        raise HTTPException(422, "El PDF no tiene texto (parece escaneado). Descárguelo de nuevo del SAT o capture los datos a mano.")
    r = lectura.leer_constancia(texto)
    if not r["encontrados"]:
        raise HTTPException(422, "No encontramos datos fiscales en este PDF. Revise que sea la Constancia de Situación Fiscal.")
    return r


@router.get("/importar/plantilla")
def plantilla(u: m.Usuario = Depends(usuario_actual)):
    return Response(lectura.plantilla(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-clientes-nomira.xlsx"'})


@router.post("/importar")
async def importar(request: Request, archivo: UploadFile = File(...), confirmar: bool = Form(False),
                   u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Primero muestra qué se va a crear (confirmar=false); luego lo crea. Los repetidos se omiten."""
    contenido = await archivo.read(MAX_TABLA + 1)
    if len(contenido) > MAX_TABLA:
        raise HTTPException(413, "El archivo pesa más de 5 MB.")
    try:
        filas, avisos = lectura.leer_tabla(archivo.filename or "clientes.xlsx", contenido)
    except Exception:
        raise HTTPException(422, "No se pudo leer el archivo. Use Excel (.xlsx) o CSV.")
    if not filas and avisos:
        raise HTTPException(422, avisos[0])
    vistos_rfc = {r for (r,) in db.execute(select(m.CrCliente.rfc).where(m.CrCliente.organizacion_id == u.organizacion_id, m.CrCliente.rfc.is_not(None)))}
    vistos_nombre = {cb.plano(n) for (n,) in db.execute(select(m.CrCliente.nombre).where(m.CrCliente.organizacion_id == u.organizacion_id))}
    resultado = []
    for i, f in enumerate(filas, start=2):
        item = {"fila": i, "nombre": f.get("nombre"), "rfc": f.get("rfc") or None, "email": f.get("email") or None, "estado": "nuevo", "motivo": None}
        try:
            d = ClienteIn(**{k: (v or None) for k, v in f.items() if k in ClienteIn.model_fields}, origen="manual")
            c = m.CrCliente(organizacion_id=u.organizacion_id, creado_por_id=u.id, origen="excel")
            _aplicar(db, c, d, u)
        except HTTPException as e:
            item.update(estado="error", motivo=e.detail)
        except Exception:
            item.update(estado="error", motivo="Datos incompletos o con formato no válido.")
        else:
            if (c.rfc and c.rfc in vistos_rfc) or cb.plano(c.nombre) in vistos_nombre:
                item.update(estado="repetido", motivo="Ya existe en Clientes (mismo RFC o nombre).")
            else:
                vistos_nombre.add(cb.plano(c.nombre))
                if c.rfc:
                    vistos_rfc.add(c.rfc)
                if confirmar:
                    c.responsable_id = u.id
                    db.add(c)
        resultado.append(item)
    nuevos = sum(1 for r in resultado if r["estado"] == "nuevo")
    if confirmar:
        auditar(db, u, "clientes_importados", "cr_cliente", None, {"nuevos": nuevos}, request)
        db.commit()
    return {"filas": resultado, "nuevos": nuevos, "repetidos": sum(1 for r in resultado if r["estado"] == "repetido"),
            "errores": sum(1 for r in resultado if r["estado"] == "error"), "avisos": avisos, "guardado": confirmar}


# ------------------------------------------------------------------ unir lo que ya está en los módulos

@router.get("/sugerencias/modulos")
def ver_sugerencias(u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    return cb.sugerencias(db, u.organizacion_id)


class Union(BaseModel):
    nombre: str = Field(min_length=2, max_length=250)
    items: list[dict] = Field(min_length=1, max_length=200)
    cliente_id: int | None = None  # None = crear el cliente
    email: str | None = None
    telefono: str | None = None


@router.post("/sugerencias/unir")
def unir(d: Union, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, d.cliente_id, u) if d.cliente_id else None
    if c is None:
        c = m.CrCliente(organizacion_id=u.organizacion_id, nombre=d.nombre.strip()[:250], email=cb.txt(d.email, 254),
                        telefono=cb.txt(d.telefono, 20), origen="modulos", creado_por_id=u.id, responsable_id=u.id)
        db.add(c)
        db.flush()
    for it in d.items:
        cb.vincular(db, u.organizacion_id, str(it.get("modulo")), int(it.get("id") or 0), c)
    auditar(db, u, "clientes_unidos", "cr_cliente", c.id, {"ligados": len(d.items)}, request)
    db.commit()
    return {"cliente_id": c.id}


class VinculoIn(BaseModel):
    modulo: str
    id: int
    cliente_id: int | None = None


@router.put("/vinculos/modulo")
def vincular(d: VinculoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, d.cliente_id, u) if d.cliente_id else None
    cb.vincular(db, u.organizacion_id, d.modulo, d.id, c)
    auditar(db, u, "cliente_vinculo", "cr_cliente", c.id if c else None, {"modulo": d.modulo, "id": d.id}, request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ documentos

@router.post("/{cid}/documentos", status_code=201)
async def subir_documento(cid: int, request: Request, archivo: UploadFile = File(...), tipo: str = Form("otro"), nombre: str | None = Form(None),
                          u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    if tipo not in cb.TIPOS_DOC:
        raise HTTPException(422, "Tipo de documento no válido.")
    contenido = await archivo.read(MAX_DOC + 1)
    if len(contenido) > MAX_DOC:
        raise HTTPException(413, "El archivo pesa más de 15 MB.")
    mime = archivo.content_type or mimetypes.guess_type(archivo.filename or "")[0] or ""
    firmas = {b"%PDF": "application/pdf", b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png"}
    real = next((v for k, v in firmas.items() if contenido.startswith(k)), "image/webp" if contenido[8:12] == b"WEBP" else None)
    if real not in PERMITIDOS or (mime and mime not in PERMITIDOS):
        raise HTTPException(422, "Suba PDF, JPG, PNG o WebP.")
    gb = almacen.contratado_gb(db, u.organizacion_id)
    if gb and almacen.uso_bytes(u.organizacion_id, fresco=True) + len(contenido) > gb * almacen.GB:
        raise HTTPException(413, "Ya no hay espacio en el almacenamiento de su plan. Contrate almacenamiento adicional con Nomira.")
    ext = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[real]
    rel = Path(str(u.organizacion_id), "clientes", str(c.id), f"{uuid.uuid4().hex}{ext}")
    destino = Path(ajustes().storage_dir, rel)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    nombre = cb.txt(nombre, 200) or cb.txt(archivo.filename, 200) or cb.TIPOS_DOC[tipo]
    x = m.CrDocumento(organizacion_id=u.organizacion_id, cliente_id=c.id, tipo=tipo, nombre=nombre, archivo=str(rel), tamano=len(contenido),
                      mime=real, sha256=hashlib.sha256(contenido).hexdigest(), subido_por_id=u.id)
    db.add(x)
    db.flush()
    auditar(db, u, "cliente_documento", "cr_cliente", c.id, {"tipo": tipo}, request)
    db.commit()
    almacen.olvidar(u.organizacion_id)
    return {"id": x.id}


def _documento(db: Session, did: int, u: m.Usuario) -> m.CrDocumento:
    x = db.get(m.CrDocumento, did)
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return x


@router.get("/documentos/{did}/archivo")
def descargar_documento(did: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    x = _documento(db, did, u)
    ruta = Path(ajustes().storage_dir, x.archivo)
    if not ruta.exists():
        raise HTTPException(404, "El archivo ya no está disponible.")
    auditar(db, u, "cliente_documento_visto", "cr_cliente", x.cliente_id, {"documento_id": x.id}, request)
    db.commit()
    ext = ruta.suffix
    nombre = x.nombre if x.nombre.lower().endswith(ext) else f"{x.nombre}{ext}"
    return FileResponse(ruta, media_type=x.mime, filename=nombre, content_disposition_type="inline",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/documentos/{did}")
def borrar_documento(did: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _documento(db, did, u)
    Path(ajustes().storage_dir, x.archivo).unlink(missing_ok=True)
    cid = x.cliente_id
    db.delete(x)
    auditar(db, u, "cliente_documento_borrado", "cr_cliente", cid, None, request)
    db.commit()
    almacen.olvidar(u.organizacion_id)
    return {"ok": True}


# ------------------------------------------------------------------ honorarios y pagos

class CargoIn(BaseModel):
    concepto: str = Field(min_length=2, max_length=250)
    monto: Monto
    fecha: date | None = None
    vence: date
    repetir_meses: int = Field(1, ge=1, le=36)  # 1 = pago único; >1 = mensualidades (iguala o parcialidades)
    relacionado: dict | None = None  # {"modulo": "agenda", "id": 3}


@router.post("/{cid}/cargos", status_code=201)
def crear_cargo(cid: int, d: CargoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    rel = None
    if d.relacionado and d.relacionado.get("modulo"):
        mod = str(d.relacionado["modulo"])
        item = next((v for v in cb.vinculos(db, c) if v["modulo"] == mod and v["id"] == int(d.relacionado.get("id") or 0)), None)
        if not item:
            raise HTTPException(422, "Ese asunto no está ligado a este cliente.")
        rel = {"modulo": mod, "id": item["id"], "titulo": item["titulo"], "ruta": item["ruta"]}
    grupo = uuid.uuid4().hex if d.repetir_meses > 1 else None
    hecho = d.fecha or hoy()
    for i in range(d.repetir_meses):
        sufijo = f" ({i + 1}/{d.repetir_meses})" if d.repetir_meses > 1 else ""
        db.add(m.CrCargo(organizacion_id=u.organizacion_id, cliente_id=c.id, concepto=(d.concepto.strip() + sufijo)[:250], monto=d.monto,
                         fecha=hecho, vence=cb.sumar_meses(d.vence, i), relacionado=rel, grupo=grupo, creado_por_id=u.id))
    auditar(db, u, "cliente_cargo", "cr_cliente", c.id, {"meses": d.repetir_meses}, request)
    db.commit()
    return ver(c.id, u, db)


class CancelarIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)


@router.post("/cargos/{gid}/cancelar")
def cancelar_cargo(gid: int, d: CancelarIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = db.get(m.CrCargo, gid)
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    if x.cancelado_en is None:
        x.cancelado_en, x.motivo_cancelacion = m.ahora(), d.motivo.strip()
        for p in db.scalars(select(m.CrPago).where(m.CrPago.cargo_id == x.id)):  # lo pagado a ese cargo queda a cuenta
            p.cargo_id = None
        auditar(db, u, "cliente_cargo_cancelado", "cr_cliente", x.cliente_id, None, request)
        db.commit()
    return ver(x.cliente_id, u, db)


def _pago_dict(p: m.CrPago, nombres: dict, conceptos: dict) -> dict:
    return {"id": p.id, "folio": p.folio, "monto": str(p.monto), "fecha": p.fecha.isoformat(), "metodo": p.metodo,
            "metodo_texto": cb.METODOS.get(p.metodo, p.metodo), "referencia": p.referencia, "nota": p.nota, "cargo_id": p.cargo_id,
            "concepto": conceptos.get(p.cargo_id) or "A cuenta", "cancelado": p.cancelado_en is not None,
            "motivo_cancelacion": p.motivo_cancelacion, "registrado_por": nombres.get(p.registrado_por_id)}


class PagoIn(BaseModel):
    monto: Monto
    fecha: date
    metodo: str = "transferencia"
    referencia: str | None = Field(None, max_length=120)
    nota: str | None = Field(None, max_length=500)
    cargo_id: int | None = None


@router.post("/{cid}/pagos", status_code=201)
def registrar_pago(cid: int, d: PagoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    if d.metodo not in cb.METODOS:
        raise HTTPException(422, "Forma de pago no válida.")
    if d.fecha > hoy():
        raise HTTPException(422, "La fecha del pago no puede ser futura.")
    if d.cargo_id:
        g = db.get(m.CrCargo, d.cargo_id)
        if not g or g.cliente_id != c.id or g.cancelado_en:
            raise HTTPException(422, "Ese cargo no es de este cliente.")
    p = m.CrPago(organizacion_id=u.organizacion_id, cliente_id=c.id, cargo_id=d.cargo_id, folio=cb.siguiente_folio(db, u.organizacion_id),
                 monto=d.monto, fecha=d.fecha, metodo=d.metodo, referencia=cb.txt(d.referencia, 120), nota=cb.txt(d.nota, 500), registrado_por_id=u.id)
    db.add(p)
    db.flush()
    auditar(db, u, "cliente_pago", "cr_cliente", c.id, {"folio": p.folio}, request)
    db.commit()
    return {**ver(c.id, u, db), "pago_id": p.id}


@router.post("/pagos/{pid}/cancelar")
def cancelar_pago(pid: int, d: CancelarIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    p = db.get(m.CrPago, pid)
    if not p or p.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    if p.cancelado_en is None:
        p.cancelado_en, p.motivo_cancelacion = m.ahora(), d.motivo.strip()
        auditar(db, u, "cliente_pago_cancelado", "cr_cliente", p.cliente_id, {"folio": p.folio}, request)
        db.commit()
    return ver(p.cliente_id, u, db)


@router.get("/pagos/{pid}/recibo")
def recibo(pid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    p = db.get(m.CrPago, pid)
    if not p or p.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    c = db.get(m.CrCliente, p.cliente_id)
    org = db.get(m.Organizacion, u.organizacion_id)
    cargos = list(db.scalars(select(m.CrCargo).where(m.CrCargo.cliente_id == c.id)))
    pagos = list(db.scalars(select(m.CrPago).where(m.CrPago.cliente_id == c.id)))
    g = db.get(m.CrCargo, p.cargo_id) if p.cargo_id else None
    return {"folio": p.folio, "fecha": p.fecha.isoformat(), "monto": str(p.monto), "monto_letra": cb.importe_con_letra(p.monto),
            "metodo": cb.METODOS.get(p.metodo, p.metodo), "referencia": p.referencia, "nota": p.nota, "concepto": g.concepto if g else "Pago a cuenta de honorarios",
            "cancelado": p.cancelado_en is not None, "motivo_cancelacion": p.motivo_cancelacion,
            "cliente": {"nombre": c.nombre, "rfc": c.rfc, "domicilio": c.domicilio},
            "despacho": {"nombre": org.nombre, "tiene_logo": org.logo_actualizado is not None,
                         "logo_version": org.logo_actualizado.isoformat() if org.logo_actualizado else None},
            "saldo_despues": cb.cuenta(cargos, pagos, hoy()).resumen()["saldo"],
            "recibio": _nombres(db, u.organizacion_id).get(p.registrado_por_id)}


# ------------------------------------------------------------------ recordatorio de pago al cliente

def _dinero(v) -> str:
    return f"${Decimal(v):,.2f}"


def correo_recordatorio(despacho: str, c: m.CrCliente, cta: cb.Cuenta, mensaje: str | None) -> tuple[str, str, str]:
    pend = [x for x in cta.cargos if x["estado"] in ("vencido", "pendiente", "parcial")]
    asunto = f"{despacho}: recordatorio de pago"
    filas = "".join(f'<tr><td style="padding:6px 8px;border-bottom:1px solid #eee">{escape(x["concepto"])}</td>'
                    f'<td style="padding:6px 8px;border-bottom:1px solid #eee">{escape(fecha_larga(date.fromisoformat(x["vence"])))}</td>'
                    f'<td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:right"><b>{_dinero(x["pendiente"])}</b></td></tr>' for x in pend)
    msj = f'<p style="white-space:pre-line">{escape(mensaje)}</p>' if mensaje else ""
    html = _base(asunto, f"""<h1 style="margin:0 0 12px;font-size:22px;color:#123048">Estimado(a) {escape(c.nombre)}</h1>
<p>Le compartimos el resumen de su cuenta con <b>{escape(despacho)}</b>:</p>{msj}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;margin:8px 0 16px">
<tr><th align="left" style="padding:6px 8px">Concepto</th><th align="left" style="padding:6px 8px">Vence</th><th align="right" style="padding:6px 8px">Pendiente</th></tr>{filas}</table>
<p style="font-size:16px">Saldo pendiente: <b>{_dinero(max(cta.saldo, cb.CERO))}</b>{f' · vencido: <b style="color:#b91c1c">{_dinero(cta.vencido)}</b>' if cta.vencido else ''}</p>
<p style="font-size:13px;color:#64748b">Si ya realizó su pago, por favor ignore este mensaje o responda con su comprobante. Este correo no solicita datos bancarios ni contraseñas.</p>""",
                 pie=f"Recibe este correo porque es cliente de {despacho}.")
    texto = (f"Estimado(a) {c.nombre}\n\nResumen de su cuenta con {despacho}:\n" + (f"{mensaje}\n" if mensaje else "")
             + "\n".join(f"- {x['concepto']}: vence {fecha_larga(date.fromisoformat(x['vence']))}, pendiente {_dinero(x['pendiente'])}" for x in pend)
             + f"\n\nSaldo pendiente: {_dinero(max(cta.saldo, cb.CERO))}\n\nSi ya realizó su pago, ignore este mensaje.\n")
    return asunto, html, texto


class RecordatorioIn(BaseModel):
    mensaje: str | None = Field(None, max_length=1000)
    enviar: bool = False  # false = vista previa


@router.post("/{cid}/recordatorio")
def recordatorio(cid: int, d: RecordatorioIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    cta = cb.cuenta(list(db.scalars(select(m.CrCargo).where(m.CrCargo.cliente_id == c.id))),
                    list(db.scalars(select(m.CrPago).where(m.CrPago.cliente_id == c.id))), hoy())
    if cta.saldo <= 0:
        raise HTTPException(409, "Este cliente no tiene saldo pendiente.")
    org = db.get(m.Organizacion, u.organizacion_id)
    asunto, html, texto = correo_recordatorio(org.nombre, c, cta, (d.mensaje or "").strip() or None)
    if not d.enviar:
        return {"para": c.email, "asunto": asunto, "texto": texto, "puede_enviar": bool(c.email and correo.configurado())}
    if not c.email:
        raise HTTPException(409, "El cliente no tiene correo registrado.")
    if not correo.configurado():
        raise HTTPException(409, "El envío de correos aún no está configurado en Nomira.")
    r = envios.registrar_y_enviar(db, "cliente_recordatorio_pago", [c.email], asunto, html, texto, organizacion_id=u.organizacion_id)
    auditar(db, u, "cliente_recordatorio", "cr_cliente", c.id, {"estado": r.estado if r else None}, request)
    db.commit()
    if not r or r.estado != "enviado":
        raise HTTPException(502, "No se pudo enviar el correo. Intente más tarde.")
    return {"ok": True, "para": c.email}
