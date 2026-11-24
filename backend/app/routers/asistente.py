"""Nomira Asistente IA (módulo «asistente»): solicitudes de borrador, resumen o explicación, en segundo plano.

Leer: cualquier rol. Generar, editar y borrar: administrador y analista. Todo se filtra por organización."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, puede_editar, solo_admin, usuario_actual
from ..services.asistente import base as ab
from ..services.tesis import base as tb

router = APIRouter(prefix="/api/asistente", tags=["Nomira Asistente IA"])


def _sol(db: Session, sid: int, u: m.Usuario) -> m.AsSolicitud:
    s = db.get(m.AsSolicitud, sid)
    if not s or s.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return s


def _vista(db: Session, s: m.AsSolicitud, completo: bool = True) -> dict:
    a = db.get(m.AgAsunto, s.ag_asunto_id) if s.ag_asunto_id else None
    u = db.get(m.Usuario, s.usuario_id) if s.usuario_id else None
    x = {"id": s.id, "tipo": s.tipo, "tipo_texto": ab.TIPOS[s.tipo], "plantilla": s.plantilla, "plantilla_texto": ab.PLANTILLAS.get(s.plantilla or ""),
         "titulo": s.titulo, "estado": s.estado, "error": s.error, "editado": s.editado,
         "asunto": {"id": a.id, "titulo": a.titulo} if a else None, "por": u.nombre if u else None,
         "documentos": s.documentos or [], "creado_en": s.creado_en.isoformat(),
         "terminado_en": s.terminado_en.isoformat() if s.terminado_en else None}
    x.update({"con_tesis": s.con_tesis, "citas_eliminadas": s.citas_eliminadas or 0, "n_tesis": len(s.tesis_citadas or [])})
    if completo:
        tesis = [db.get(m.JTesis, r) for r in (s.tesis_citadas or [])]
        x.update({"instrucciones": s.instrucciones, "resultado": s.resultado, "tesis": [tb.a_dict(t, completo=False) for t in tesis if t]})
    return x


@router.get("/config")
def config(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    ok, motivo = ab.disponible()
    asuntos = db.scalars(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == u.organizacion_id, m.AgAsunto.estado == "activo")
                         .order_by(m.AgAsunto.titulo).limit(500))
    from ..services.comercial import base as cm

    return {"disponible": ok, "motivo": motivo, "cuota": ab.cuota(db, u.organizacion_id), "paquete": _paquete_precio(),
            "pago_en_linea": cm.stripe_estado()["conectado"], "es_admin": u.rol == "administrador",
            "tipos": [{"clave": k, "nombre": v} for k, v in ab.TIPOS.items()], "biblioteca_tesis": tb.total(db),
            "plantillas": [{"clave": k, "nombre": v} for k, v in ab.PLANTILLAS.items()],
            "asuntos": [{"id": a.id, "titulo": a.titulo, "numero": a.numero} for a in asuntos],
            "puede_editar": u.rol in ("administrador", "analista")}


def _paquete_precio() -> dict:
    sub = Decimal(ajustes().ia_paquete_precio).quantize(Decimal("0.01"))
    iva = (sub * Decimal("0.16")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"usos": ajustes().ia_paquete_usos, "subtotal": str(sub), "iva": str(iva), "total": str(sub + iva)}


@router.post("/paquetes")
def comprar_paquete(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Paquete extra de usos con el cobro en línea de Nomira. Los usos se suman solo cuando Stripe confirma el pago (webhook)."""
    from ..services.comercial import base as cm
    from ..services.comercial import stripe as st

    if not cm.stripe_estado()["conectado"]:
        raise HTTPException(409, "El pago en línea no está disponible por ahora. Escriba a soporte para comprar más usos.")
    p = _paquete_precio()
    compra = m.AsPaquete(organizacion_id=u.organizacion_id, usuario_id=u.id, usos=p["usos"], subtotal=Decimal(p["subtotal"]),
                         iva=Decimal(p["iva"]), total=Decimal(p["total"]))
    db.add(compra)
    db.flush()
    base_url = ajustes().url_publica.rstrip("/")
    try:
        sesion = st.crear_checkout(nombre=f"Nomira Asistente IA · {p['usos']} usos extra", total=compra.total, email=u.email,
                                   url_exito=f"{base_url}/asistente?paquete=procesando", url_cancelar=f"{base_url}/asistente?paquete=cancelado",
                                   idempotencia=f"nomira-ia-paquete-{compra.id}", referencia=f"ia-paquete-org-{u.organizacion_id}",
                                   metadata={"tipo": "ia_paquete", "paquete_id": str(compra.id), "organizacion_id": str(u.organizacion_id)})
    except st.StripeError as e:
        db.rollback()
        raise HTTPException(502, str(e))
    compra.stripe_sesion = sesion["id"]
    auditar(db, u, "ia_paquete_iniciado", "as_paquete", compra.id, {"usos": p["usos"], "total": p["total"]}, request)
    db.commit()
    return {"url": sesion["url"]}


@router.get("/solicitudes")
def listar(asunto: int | None = None, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    st = select(m.AsSolicitud).where(m.AsSolicitud.organizacion_id == u.organizacion_id)
    if asunto:
        st = st.where(m.AsSolicitud.ag_asunto_id == asunto)
    return {"solicitudes": [_vista(db, s, False) for s in db.scalars(st.order_by(m.AsSolicitud.creado_en.desc()).limit(100))]}


@router.post("/solicitudes", status_code=201)
async def crear(request: Request, tareas: BackgroundTasks, tipo: str = Form(...), plantilla: str | None = Form(None),
                instrucciones: str | None = Form(None), texto: str | None = Form(None), ag_asunto_id: int | None = Form(None),
                titulo: str | None = Form(None), con_tesis: bool = Form(False), archivos: list[UploadFile] = File(default=[]),
                u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    ok, motivo = ab.disponible()
    if not ok:
        raise HTTPException(503, motivo)
    if tipo not in ab.TIPOS:
        raise HTTPException(422, "Tipo de solicitud inválido.")
    if tipo == "borrador" and plantilla not in ab.PLANTILLAS:
        raise HTTPException(422, "Elija qué documento quiere redactar.")
    if tipo == "investigar" and not (instrucciones or "").strip():
        raise HTTPException(422, "Escriba qué quiere investigar: el problema jurídico y los hechos clave.")
    if (tipo == "investigar" or con_tesis) and not tb.total(db):
        raise HTTPException(409, "La biblioteca de tesis de Nomira todavía se está cargando. Intente más tarde.")
    db.scalar(select(m.Organizacion.id).where(m.Organizacion.id == u.organizacion_id).with_for_update())  # evita gastar el mismo uso dos veces
    q = ab.cuota(db, u.organizacion_id)
    if q["disponibles"] <= 0:
        p = _paquete_precio()
        raise HTTPException(429, f"Su despacho ya usó sus {q['incluidos']} usos incluidos de este mes. "
                                 f"Un administrador puede comprar {p['usos']} usos más por ${p['total']} (IVA incluido) en el Asistente IA, o esperar al próximo mes.")
    de_paquete = q["restantes_mes"] <= 0
    a = None
    if ag_asunto_id:
        a = db.get(m.AgAsunto, ag_asunto_id)
        if not a or a.organizacion_id != u.organizacion_id:
            raise HTTPException(422, "El asunto no existe.")
    if len(archivos) > 3:
        raise HTTPException(422, "Puede adjuntar hasta 3 archivos por solicitud.")
    documentos: list[tuple[str, str]] = []
    for f in archivos:
        contenido = await f.read(ab.MAX_ARCHIVO + 1)
        if len(contenido) > ab.MAX_ARCHIVO:
            raise HTTPException(413, f"«{f.filename}» pesa más de 15 MB.")
        try:
            t = ab.texto_de_archivo(f.filename or "", contenido)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception:
            raise HTTPException(422, f"No se pudo leer «{f.filename}».")
        if len(t.strip()) < 20:
            raise HTTPException(422, f"«{f.filename}» no tiene texto seleccionable (parece escaneado). Copie y pegue el texto en el recuadro.")
        documentos.append(((f.filename or "documento")[:120], t))
    if texto and texto.strip():
        documentos.append(("Texto pegado", texto.strip()))
    if tipo in ("resumen", "acuerdo") and not documentos:
        raise HTTPException(422, "Adjunte el documento o pegue el texto que quiere que el asistente lea.")
    if tipo == "borrador" and not (instrucciones or "").strip() and not documentos:
        raise HTTPException(422, "Cuéntele al asistente qué necesita: hechos, peticiones o el documento base.")
    total = sum(len(t) for _, t in documentos)
    if total > ab.MAX_CARACTERES:
        raise HTTPException(413, "Los documentos son demasiado largos para una sola solicitud. Divida el trabajo o adjunte solo las partes necesarias.")
    nombre = re.sub(r"\s+", " ", titulo or "").strip()[:200] or (ab.PLANTILLAS[plantilla] if tipo == "borrador" else ab.TIPOS[tipo]) + (f" · {a.titulo}" if a else "")
    s = m.AsSolicitud(organizacion_id=u.organizacion_id, usuario_id=u.id, ag_asunto_id=a.id if a else None, tipo=tipo,
                      plantilla=plantilla if tipo == "borrador" else None, titulo=nombre[:200], instrucciones=(instrucciones or "").strip()[:8000] or None,
                      documentos=[{"nombre": n, "caracteres": len(t)} for n, t in documentos], modelo=ajustes().ia_modelo_asistente,
                      de_paquete=de_paquete, con_tesis=tipo == "investigar" or (con_tesis and tipo == "borrador"))
    db.add(s)
    db.flush()
    # en la bitácora solo queda que se envió texto al proveedor de IA, nunca el contenido
    auditar(db, u, "ia_consulta_externa", "as_solicitud", s.id, {"tipo": tipo, "documentos": len(documentos), "caracteres": total,
                                                                  "modelo": ajustes().ia_modelo_asistente}, request)
    db.commit()
    tareas.add_task(ab.generar, s.id, documentos)
    return _vista(db, s)


@router.get("/solicitudes/{sid}")
def ver(sid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _vista(db, _sol(db, sid, u))


class EdicionIn(BaseModel):
    titulo: str | None = Field(None, max_length=200)
    resultado: str = Field(max_length=300_000)


@router.put("/solicitudes/{sid}")
def editar(sid: int, d: EdicionIn, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    s = _sol(db, sid, u)
    if s.estado != "listo":
        raise HTTPException(409, "Aún no hay texto para editar.")
    s.resultado, s.editado = d.resultado, True
    if d.titulo and d.titulo.strip():
        s.titulo = d.titulo.strip()[:200]
    db.commit()
    return _vista(db, s)


@router.delete("/solicitudes/{sid}")
def borrar(sid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    s = _sol(db, sid, u)
    auditar(db, u, "as_solicitud_borrada", "as_solicitud", s.id, None, request)
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.get("/solicitudes/{sid}/docx")
def descargar(sid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    s = _sol(db, sid, u)
    if s.estado != "listo" or not s.resultado:
        raise HTTPException(409, "Aún no hay texto para descargar.")
    nombre = re.sub(r"[^A-Za-z0-9_-]+", "-", s.titulo)[:60].strip("-") or "borrador"
    return Response(ab.docx(s.titulo, s.resultado), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}.docx"'})
