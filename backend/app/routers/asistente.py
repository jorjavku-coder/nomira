"""Nomira Asistente IA (módulo «asistente»): solicitudes de borrador, resumen o explicación, en segundo plano.

Leer: cualquier rol. Generar, editar y borrar: administrador y analista. Todo se filtra por organización."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, puede_editar, usuario_actual
from ..services.asistente import base as ab

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
    if completo:
        x.update({"instrucciones": s.instrucciones, "resultado": s.resultado})
    return x


@router.get("/config")
def config(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    ok, motivo = ab.disponible()
    asuntos = db.scalars(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == u.organizacion_id, m.AgAsunto.estado == "activo")
                         .order_by(m.AgAsunto.titulo).limit(500))
    return {"disponible": ok, "motivo": motivo, "limite": ajustes().ia_limite_mensual, "usados_mes": ab.usados_mes(db, u.organizacion_id),
            "tipos": [{"clave": k, "nombre": v} for k, v in ab.TIPOS.items()],
            "plantillas": [{"clave": k, "nombre": v} for k, v in ab.PLANTILLAS.items()],
            "asuntos": [{"id": a.id, "titulo": a.titulo, "numero": a.numero} for a in asuntos],
            "puede_editar": u.rol in ("administrador", "analista")}


@router.get("/solicitudes")
def listar(asunto: int | None = None, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    st = select(m.AsSolicitud).where(m.AsSolicitud.organizacion_id == u.organizacion_id)
    if asunto:
        st = st.where(m.AsSolicitud.ag_asunto_id == asunto)
    return {"solicitudes": [_vista(db, s, False) for s in db.scalars(st.order_by(m.AsSolicitud.creado_en.desc()).limit(100))]}


@router.post("/solicitudes", status_code=201)
async def crear(request: Request, tareas: BackgroundTasks, tipo: str = Form(...), plantilla: str | None = Form(None),
                instrucciones: str | None = Form(None), texto: str | None = Form(None), ag_asunto_id: int | None = Form(None),
                titulo: str | None = Form(None), archivos: list[UploadFile] = File(default=[]),
                u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    ok, motivo = ab.disponible()
    if not ok:
        raise HTTPException(503, motivo)
    if tipo not in ab.TIPOS:
        raise HTTPException(422, "Tipo de solicitud inválido.")
    if tipo == "borrador" and plantilla not in ab.PLANTILLAS:
        raise HTTPException(422, "Elija qué documento quiere redactar.")
    if ab.usados_mes(db, u.organizacion_id) >= ajustes().ia_limite_mensual:
        raise HTTPException(429, f"Su despacho llegó al límite de {ajustes().ia_limite_mensual} solicitudes del mes. Escriba a soporte si necesita más.")
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
                      documentos=[{"nombre": n, "caracteres": len(t)} for n, t in documentos], modelo=ajustes().ia_modelo)
    db.add(s)
    db.flush()
    # en la bitácora solo queda que se envió texto al proveedor de IA, nunca el contenido
    auditar(db, u, "ia_consulta_externa", "as_solicitud", s.id, {"tipo": tipo, "documentos": len(documentos), "caracteres": total,
                                                                  "modelo": ajustes().ia_modelo}, request)
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
