"""API de Nomira Academia. Todas las rutas exigen el módulo activo (vea main.py) y se filtran por
organización: los cursos internos nunca son públicos ni visibles para otro despacho. Roles:
participante (todos), instructor (crea y edita cursos del despacho y ve su avance) y administrador
(además asigna, administra equipos e instructores y descarga reportes). Actualizar o archivar un
curso nunca borra el avance ni las constancias de quienes ya lo tomaron."""
from __future__ import annotations

import hashlib
import io
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, solo_admin, usuario_actual
from ..services.academia import base, constancia, nomira

router = APIRouter(prefix="/api/academia", tags=["Nomira Academia"])
PRIVADO = {"Cache-Control": "no-store"}
MAX_ARCHIVO = 25 * 1024 * 1024
FORMATOS = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "png": "image/png", "jpg": "image/jpeg",
            "txt": "text/plain; charset=utf-8"}


# ---------- utilidades y permisos ----------

def _txt(v: str | None, n: int) -> str | None:
    v = (v or "").strip()
    return v[:n] or None


def _url(v: str | None) -> str | None:
    v = (v or "").strip()
    if not v:
        return None
    if not re.match(r"^https://[^\s]+$", v) or len(v) > 500:
        raise HTTPException(422, "Los enlaces deben empezar con https:// (video, sesión o recurso).")
    return v


def _nombres(db: Session, org: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org)).all())


def _instructor(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)) -> m.Usuario:
    if not base.es_instructor(db, u):
        raise HTTPException(403, "Solo administradores e instructores pueden crear o editar cursos.")
    return u


def _visible(db: Session, u: m.Usuario, c: m.AcCurso) -> bool:
    if c.organizacion_id not in (None, u.organizacion_id):
        return False
    if c.estado == "publicado":
        return True
    if c.organizacion_id == u.organizacion_id and base.es_instructor(db, u):
        return True
    # un curso archivado sigue visible para quien lo empezó o lo tiene asignado (historial)
    return c.estado == "archivado" and (base.avance_de(db, u, c.id) is not None or c.id in base.asignaciones_de(db, u))


def _curso(db: Session, cid: int, u: m.Usuario) -> m.AcCurso:
    c = db.get(m.AcCurso, cid)
    if not c or not _visible(db, u, c):
        raise HTTPException(404, "No encontrado.")
    return c


def _editable(db: Session, cid: int, u: m.Usuario) -> m.AcCurso:
    c = db.get(m.AcCurso, cid)
    if not c or c.organizacion_id not in (None, u.organizacion_id):
        raise HTTPException(404, "No encontrado.")
    if c.organizacion_id is None:
        raise HTTPException(409, "Los cursos de Nomira no se editan: use «Duplicar para adaptar».")
    if not base.puede_editar(db, u, c):
        raise HTTPException(403, "Solo administradores e instructores pueden editar cursos.")
    return c


def _leccion(db: Session, lid: int, u: m.Usuario, editar: bool = False) -> tuple[m.AcLeccion, m.AcCurso]:
    x = db.get(m.AcLeccion, lid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    c = _editable(db, x.curso_id, u) if editar else _curso(db, x.curso_id, u)
    return x, c


def _aud(db, u, accion, entidad, eid, request=None, **detalle):
    auditar(db, u, accion, entidad, eid, detalle or None, request)


def _usuario_org(db: Session, uid: int, u: m.Usuario) -> m.Usuario:
    x = db.get(m.Usuario, uid)
    if not x or x.organizacion_id != u.organizacion_id or x.eliminado_en:
        raise HTTPException(422, "La persona debe ser un usuario de su organización.")
    return x


# ---------- representaciones ----------

def curso_tarjeta(c: m.AcCurso, db: Session, u: m.Usuario, asignacion: m.AcAsignacion | None = None,
                  avance: m.AcAvance | None | bool = False) -> dict:
    a = base.avance_de(db, u, c.id) if avance is False else avance
    p = base.progreso(db, c, a)
    return {"id": c.id, "titulo": c.titulo, "materia": c.materia, "roles": c.roles or [], "instructor": c.instructor, "institucion": c.institucion,
            "descripcion": c.descripcion, "duracion_min": c.duracion_min, "modalidad": c.modalidad,
            "modalidad_texto": base.MODALIDADES.get(c.modalidad, c.modalidad), "estado": c.estado, "origen": "nomira" if c.organizacion_id is None else "despacho",
            "juridico": c.juridico, "actualizado_en": c.contenido_actualizado_en.isoformat(), "creado_en": c.creado_en.isoformat(),
            "aviso_vigencia": base.aviso_vigencia(c), "vigente": base.vigente(c), "version": c.version,
            "asignacion": {"id": asignacion.id, "tipo": asignacion.tipo, "tipo_texto": base.TIPOS_ASIGNACION[asignacion.tipo],
                           "fecha_sugerida": asignacion.fecha_sugerida.isoformat() if asignacion.fecha_sugerida else None,
                           "vencida": bool(asignacion.fecha_sugerida and asignacion.fecha_sugerida < date.today() and p["estado"] != "completado")}
            if asignacion else None,
            "progreso": {k: p[k] for k in ("estado", "texto", "porcentaje", "lecciones", "lecciones_hechas", "siguiente_leccion_id")},
            "avance_id": a.id if a else None, "completado_en": a.completado_en.isoformat() if a and a.completado_en else None,
            "ultima_leccion_id": a.ultima_leccion_id if a else None, "ultima_actividad_en": a.ultima_actividad_en.isoformat() if a else None}


def _cursos_visibles(db: Session, u: m.Usuario) -> list[m.AcCurso]:
    nomira.asegurar(db)
    xs = db.scalars(select(m.AcCurso).where((m.AcCurso.organizacion_id.is_(None)) | (m.AcCurso.organizacion_id == u.organizacion_id))
                    .order_by(m.AcCurso.titulo)).all()
    return [c for c in xs if c.estado == "publicado"]


def sesion_dict(s: m.AcSesion, curso: m.AcCurso | None = None) -> dict:
    return {"id": s.id, "curso_id": s.curso_id, "curso": curso.titulo if curso else None, "titulo": s.titulo, "inicio": s.inicio.isoformat(),
            "duracion_min": s.duracion_min, "enlace": s.enlace, "grabacion_url": s.grabacion_url, "notas": s.notas, "cancelada": s.cancelada}


# ---------- mi aprendizaje ----------

@router.get("/yo")
def permisos(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return {"es_instructor": base.es_instructor(db, u), "es_admin": u.rol == "administrador"}


@router.get("/inicio")
def inicio(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    publicados = {c.id: c for c in _cursos_visibles(db, u)}
    asig = base.asignaciones_de(db, u)
    avances = {a.curso_id: a for a in db.scalars(select(m.AcAvance).where(m.AcAvance.usuario_id == u.id))}
    todos = {**publicados, **{c.id: c for c in db.scalars(select(m.AcCurso).where(m.AcCurso.id.in_(set(asig) | set(avances))))
                               if c.organizacion_id in (None, u.organizacion_id)}}
    tarjeta = lambda c: curso_tarjeta(c, db, u, asig.get(c.id), avances.get(c.id))  # noqa: E731
    continuar = sorted((tarjeta(todos[cid]) for cid, a in avances.items() if not a.completado_en and cid in todos and todos[cid].estado != "borrador"),
                       key=lambda t: t["ultima_actividad_en"] or "", reverse=True)
    asignados = [tarjeta(todos[cid]) for cid in asig if cid in todos and todos[cid].estado == "publicado"]
    asignados.sort(key=lambda t: (t["progreso"]["estado"] == "completado", t["asignacion"]["tipo"] != "obligatorio",
                                  t["asignacion"]["fecha_sugerida"] or "9999"))
    disponibles = [tarjeta(c) for c in publicados.values() if c.id not in asig and c.id not in avances and base.vigente(c)]
    completados = sorted((tarjeta(todos[cid]) for cid, a in avances.items() if a.completado_en and cid in todos),
                         key=lambda t: t["completado_en"], reverse=True)
    ids = set(asig) | set(avances)
    sesiones = db.scalars(select(m.AcSesion).where(m.AcSesion.organizacion_id == u.organizacion_id, m.AcSesion.cancelada.is_(False),
                                                   m.AcSesion.inicio >= m.ahora() - timedelta(hours=2)).order_by(m.AcSesion.inicio).limit(20)).all()
    sesiones = [sesion_dict(s, todos.get(s.curso_id) or db.get(m.AcCurso, s.curso_id)) | {"mio": s.curso_id in ids} for s in sesiones
                if (s.curso_id in todos and todos[s.curso_id].estado == "publicado")]
    obligatorios = [t for t in asignados if t["asignacion"]["tipo"] == "obligatorio"]
    db.commit()
    return {"continuar": continuar[:6], "asignados": asignados, "disponibles": disponibles, "completados": completados, "sesiones": sesiones[:6],
            "resumen": {"asignados": len(asignados), "completados": len(completados),
                        "obligatorios_pendientes": sum(1 for t in obligatorios if t["progreso"]["estado"] != "completado")},
            "es_instructor": base.es_instructor(db, u), "es_admin": u.rol == "administrador"}


@router.get("/cursos")
def catalogo(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    asig = base.asignaciones_de(db, u)
    cs = _cursos_visibles(db, u)
    db.commit()
    return {"cursos": [curso_tarjeta(c, db, u, asig.get(c.id)) for c in cs], "materias": sorted({c.materia for c in cs})}


@router.get("/cursos/{cid}")
def ver_curso(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _curso(db, cid, u)
    a = base.avance_de(db, u, c.id)
    p = base.progreso(db, c, a)
    hechas = set(p["hechas"])
    nombres = _nombres(db, u.organizacion_id)
    mods = db.scalars(select(m.AcModulo).where(m.AcModulo.curso_id == c.id, m.AcModulo.archivado_en.is_(None)).order_by(m.AcModulo.orden, m.AcModulo.id)).all()
    ls = base.lecciones(db, c.id)
    pregs = base.preguntas(db, c.id)
    sesiones = db.scalars(select(m.AcSesion).where(m.AcSesion.curso_id == c.id, m.AcSesion.organizacion_id == u.organizacion_id)
                          .order_by(m.AcSesion.inicio)).all()
    d = curso_tarjeta(c, db, u, base.asignaciones_de(db, u).get(c.id), a)
    d.update({
        "modulos": [{"id": mo.id, "titulo": mo.titulo, "lecciones": [
            {"id": x.id, "titulo": x.titulo, "duracion_min": x.duracion_min, "completada": x.id in hechas,
             "tiene": [k for k, v in (("video", x.video_url), ("sesion", x.sesion_url), ("documento", x.archivo_ruta), ("texto", x.texto),
                                      ("actividad", x.actividad), ("recursos", x.recursos)) if v]}
            for x in ls if x.modulo_id == mo.id]} for mo in mods],
        "cuestionario": {"preguntas": len(pregs), "calificacion_minima": c.calificacion_minima, "requerido": p["requiere_cuestionario"],
                         "aprobado": p["cuestionario_aprobado"], "calificacion": p["calificacion"], "disponible": p["lecciones_listas"]},
        "sesiones": [sesion_dict(s) for s in sesiones if not s.cancelada],
        "revisado_por": nombres.get(c.revisado_por_id), "revisado_en": c.revisado_en.isoformat() if c.revisado_en else None,
        "publicado_en": c.publicado_en.isoformat() if c.publicado_en else None, "asistido_ia": c.asistido_ia,
        "puede_editar": base.puede_editar(db, u, c), "constancia": bool(a and a.constancia_folio),
        "constancia_folio": a.constancia_folio if a else None,
        "completado_version_anterior": bool(a and a.completado_en and a.curso_version and a.curso_version < c.version)})
    db.commit()
    return d


@router.post("/cursos/{cid}/iniciar")
def iniciar(cid: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _curso(db, cid, u)
    if c.estado != "publicado":
        raise HTTPException(409, "Este curso no está publicado.")
    a = base.avance_de(db, u, c.id)
    if a is None:
        a = m.AcAvance(organizacion_id=u.organizacion_id, usuario_id=u.id, curso_id=c.id)
        db.add(a)
        db.flush()
        _aud(db, u, "ac_curso_iniciado", "ac_curso", c.id, request)
    p = base.progreso(db, c, a)
    destino = a.ultima_leccion_id if a.ultima_leccion_id and a.ultima_leccion_id not in p["hechas"] else p["siguiente_leccion_id"]
    ls = base.lecciones(db, c.id)
    if destino not in {x.id for x in ls}:
        destino = p["siguiente_leccion_id"] or (ls[0].id if ls else None)
    db.commit()
    return {"avance_id": a.id, "leccion_id": destino, "cuestionario": destino is None and p["requiere_cuestionario"] and not p["cuestionario_aprobado"]}


def _avance(db, u, c, crear: bool = True) -> m.AcAvance:
    a = base.avance_de(db, u, c.id)
    if a is None:
        if not crear or c.estado != "publicado":
            raise HTTPException(409, "Inicie el curso primero.")
        a = m.AcAvance(organizacion_id=u.organizacion_id, usuario_id=u.id, curso_id=c.id)
        db.add(a)
        db.flush()
    return a


def _al(db, a: m.AcAvance, lid: int) -> m.AcAvanceLeccion:
    x = db.scalar(select(m.AcAvanceLeccion).where(m.AcAvanceLeccion.avance_id == a.id, m.AcAvanceLeccion.leccion_id == lid))
    if x is None:
        x = m.AcAvanceLeccion(avance_id=a.id, leccion_id=lid, posicion=0)
        db.add(x)
        db.flush()
    return x


@router.get("/lecciones/{lid}")
def ver_leccion(lid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    x, c = _leccion(db, lid, u)
    if x.archivado_en:
        raise HTTPException(410, "Esta lección ya no forma parte del curso.")
    vista_previa = c.estado != "publicado"
    a = None if vista_previa else _avance(db, u, c)
    al = None
    if a:
        a.ultima_leccion_id, a.ultima_actividad_en = x.id, m.ahora()  # «continuar donde se quedó»
        al = _al(db, a, x.id)
    ls = base.lecciones(db, c.id)
    ids = [y.id for y in ls]
    i = ids.index(x.id) if x.id in ids else -1
    mod = db.get(m.AcModulo, x.modulo_id)
    p = base.progreso(db, c, a)
    act = x.actividad
    respondida = al is not None and al.respuesta is not None
    d = {"id": x.id, "curso_id": c.id, "curso": c.titulo, "modulo": mod.titulo if mod else None, "titulo": x.titulo, "texto": x.texto,
         "video_url": x.video_url, "video_embebido": _embebido(x.video_url), "sesion_url": x.sesion_url, "transcripcion": x.transcripcion,
         "recursos": x.recursos or [], "duracion_min": x.duracion_min,
         "archivo": {"nombre": x.archivo_nombre, "formato": x.archivo_formato, "tamano": x.archivo_tamano} if x.archivo_ruta else None,
         "actividad": {"pregunta": act["pregunta"], "opciones": act["opciones"],
                       **({"respuesta": al.respuesta, "correcta": al.correcta, "respuesta_correcta": act["correcta"], "explicacion": act.get("explicacion")}
                          if respondida else {})} if act else None,
         "completada": bool(al and al.completada_en), "posicion": al.posicion if al else 0,
         "anterior_id": ids[i - 1] if i > 0 else None, "siguiente_id": ids[i + 1] if 0 <= i < len(ids) - 1 else None,
         "numero": i + 1, "total": len(ids), "progreso": {k: p[k] for k in ("porcentaje", "texto", "requiere_cuestionario", "cuestionario_aprobado")},
         "vista_previa": vista_previa, "aviso_vigencia": base.aviso_vigencia(c), "actualizado_en": x.actualizado_en.isoformat()}
    db.commit()
    return d


def _embebido(url: str | None) -> str | None:
    """Solo YouTube y Vimeo se muestran dentro de Nomira; cualquier otro video se abre en su sitio."""
    if not url:
        return None
    y = re.match(r"^https://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{6,20})", url)
    if y:
        return f"https://www.youtube-nocookie.com/embed/{y.group(1)}"
    v = re.match(r"^https://(?:www\.)?vimeo\.com/(\d+)", url)
    if v:
        return f"https://player.vimeo.com/video/{v.group(1)}"
    return None


class Posicion(BaseModel):
    posicion: int = Field(ge=0, le=10_000_000)


@router.put("/lecciones/{lid}/avance")
def guardar_posicion(lid: int, d: Posicion, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Guardado automático de dónde se quedó dentro de la lección."""
    x, c = _leccion(db, lid, u)
    if c.estado != "publicado":
        return {"ok": True}
    a = _avance(db, u, c)
    al = _al(db, a, x.id)
    al.posicion = d.posicion
    a.ultima_leccion_id, a.ultima_actividad_en = x.id, m.ahora()
    db.commit()
    return {"ok": True}


class Respuesta(BaseModel):
    respuesta: int = Field(ge=0, le=20)


@router.post("/lecciones/{lid}/actividad")
def responder_actividad(lid: int, d: Respuesta, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    x, c = _leccion(db, lid, u)
    if not x.actividad:
        raise HTTPException(404, "Esta lección no tiene actividad.")
    if d.respuesta >= len(x.actividad["opciones"]):
        raise HTTPException(422, "Opción inválida.")
    correcta = d.respuesta == x.actividad["correcta"]
    if c.estado == "publicado":
        al = _al(db, _avance(db, u, c), x.id)
        al.respuesta, al.correcta = d.respuesta, correcta
        db.commit()
    return {"correcta": correcta, "respuesta_correcta": x.actividad["correcta"], "explicacion": x.actividad.get("explicacion")}


@router.post("/lecciones/{lid}/completar")
def completar_leccion(lid: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    x, c = _leccion(db, lid, u)
    if c.estado != "publicado":
        raise HTTPException(409, "Vista previa: el avance solo se guarda en cursos publicados.")
    a = _avance(db, u, c)
    al = _al(db, a, x.id)
    if x.actividad and al.respuesta is None:
        raise HTTPException(422, "Responda la pregunta de comprobación antes de continuar.")
    al.completada_en = al.completada_en or m.ahora()
    a.ultima_actividad_en = m.ahora()
    db.flush()
    completo = base.revisar_completo(db, c, a)
    if completo:
        _aud(db, u, "ac_curso_completado", "ac_curso", c.id, request, folio=a.constancia_folio, version=c.version)
    p = base.progreso(db, c, a)
    db.commit()
    return {"completado": bool(a.completado_en), "recien_completado": completo, "siguiente_id": p["siguiente_leccion_id"],
            "ir_a_cuestionario": p["lecciones_listas"] and p["requiere_cuestionario"] and not p["cuestionario_aprobado"],
            "progreso": {k: p[k] for k in ("porcentaje", "texto")}, "avance_id": a.id}


@router.get("/lecciones/{lid}/archivo")
def descargar_material(lid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    x, _ = _leccion(db, lid, u)
    if not x.archivo_ruta or not os.path.exists(x.archivo_ruta):
        raise HTTPException(404, "El material no está disponible.")
    nombre = re.sub(r'[^\w.\- ]', "_", x.archivo_nombre or f"material.{x.archivo_formato}")
    return Response(Path(x.archivo_ruta).read_bytes(), media_type=FORMATOS.get(x.archivo_formato or "", "application/octet-stream"),
                    headers={**PRIVADO, "Content-Disposition": f'attachment; filename="{nombre}"', "Access-Control-Expose-Headers": "Content-Disposition"})


@router.get("/cursos/{cid}/cuestionario")
def ver_cuestionario(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _curso(db, cid, u)
    pregs = base.preguntas(db, c.id)
    a = base.avance_de(db, u, c.id)
    intentos = db.scalars(select(m.AcIntento).where(m.AcIntento.avance_id == a.id).order_by(m.AcIntento.id.desc())).all() if a else []
    return {"curso": c.titulo, "curso_id": c.id, "calificacion_minima": c.calificacion_minima,
            "preguntas": [{"id": p.id, "texto": p.texto, "opciones": p.opciones} for p in pregs],
            "intentos": [{"calificacion": i.calificacion, "aprobado": i.aprobado, "creado_en": i.creado_en.isoformat()} for i in intentos],
            "disponible": base.progreso(db, c, a)["lecciones_listas"]}


class Respuestas(BaseModel):
    respuestas: dict[str, int]


@router.post("/cursos/{cid}/cuestionario")
def contestar(cid: int, d: Respuestas, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _curso(db, cid, u)
    if c.estado != "publicado":
        raise HTTPException(409, "Este curso no está publicado.")
    pregs = base.preguntas(db, c.id)
    if not pregs:
        raise HTTPException(404, "Este curso no tiene cuestionario.")
    a = _avance(db, u, c)
    if not base.progreso(db, c, a)["lecciones_listas"]:
        raise HTTPException(409, "Complete todas las lecciones antes del cuestionario.")
    faltan = [p.id for p in pregs if str(p.id) not in d.respuestas]
    if faltan:
        raise HTTPException(422, "Responda todas las preguntas.")
    detalle = [{"id": p.id, "respuesta": d.respuestas[str(p.id)], "correcta": p.correcta, "acierto": d.respuestas[str(p.id)] == p.correcta,
                "explicacion": p.explicacion} for p in pregs]
    aciertos = sum(1 for x in detalle if x["acierto"])
    cal = round(100 * aciertos / len(pregs))
    aprobado = c.calificacion_minima is None or cal >= c.calificacion_minima
    db.add(m.AcIntento(avance_id=a.id, respuestas={str(x["id"]): x["respuesta"] for x in detalle}, aciertos=aciertos, total=len(pregs),
                       calificacion=cal, aprobado=aprobado))
    if a.calificacion is None or cal > a.calificacion:
        a.calificacion = cal
    a.ultima_actividad_en = m.ahora()
    db.flush()
    completo = base.revisar_completo(db, c, a)
    if completo:
        _aud(db, u, "ac_curso_completado", "ac_curso", c.id, request, folio=a.constancia_folio, version=c.version)
    db.commit()
    return {"calificacion": cal, "aciertos": aciertos, "total": len(pregs), "aprobado": aprobado, "minima": c.calificacion_minima,
            "detalle": detalle, "completado": bool(a.completado_en), "avance_id": a.id}


@router.get("/constancias/{aid}")
def constancia_pdf(aid: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    a = db.get(m.AcAvance, aid)
    if not a or a.organizacion_id != u.organizacion_id or (a.usuario_id != u.id and u.rol != "administrador"):
        raise HTTPException(404, "No encontrado.")
    if not a.completado_en or not a.constancia_folio:
        raise HTTPException(409, "La constancia se emite al completar el curso.")
    persona, org, c = db.get(m.Usuario, a.usuario_id), db.get(m.Organizacion, a.organizacion_id), db.get(m.AcCurso, a.curso_id)
    datos = constancia.pdf(participante=persona.nombre, curso=a.curso_titulo or c.titulo, organizacion=org.nombre, fecha=a.completado_en,
                           folio=a.constancia_folio, duracion_min=a.curso_duracion_min, instructor=c.instructor,
                           calificacion=a.calificacion if c.calificacion_minima is not None else None)
    _aud(db, u, "ac_constancia_descargada", "ac_avance", a.id, request, folio=a.constancia_folio)
    db.commit()
    return Response(datos, media_type="application/pdf", headers={**PRIVADO, "Content-Disposition": f'attachment; filename="constancia-{a.constancia_folio}.pdf"',
                                                                  "Access-Control-Expose-Headers": "Content-Disposition"})


# ---------- administrar cursos ----------

@router.get("/admin/cursos")
def admin_cursos(u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    nomira.asegurar(db)
    nombres = _nombres(db, u.organizacion_id)
    xs = db.scalars(select(m.AcCurso).where((m.AcCurso.organizacion_id == u.organizacion_id) | (m.AcCurso.organizacion_id.is_(None)))
                    .order_by(m.AcCurso.organizacion_id.is_(None), m.AcCurso.estado, m.AcCurso.titulo)).all()
    res = []
    for c in xs:
        avs = db.scalars(select(m.AcAvance).where(m.AcAvance.curso_id == c.id, m.AcAvance.organizacion_id == u.organizacion_id)).all()
        asig = db.query(m.AcAsignacion).filter(m.AcAsignacion.curso_id == c.id, m.AcAsignacion.organizacion_id == u.organizacion_id,
                                               m.AcAsignacion.retirada_en.is_(None)).count()
        res.append({**{k: v for k, v in curso_tarjeta(c, db, u).items() if k not in ("progreso", "asignacion")},
                    "estado_texto": base.ESTADOS.get(c.estado, c.estado), "lecciones": len(base.lecciones(db, c.id)),
                    "iniciados": len(avs), "completados": sum(1 for a in avs if a.completado_en), "asignaciones": asig,
                    "creado_por": nombres.get(c.creado_por_id), "editable": base.puede_editar(db, u, c)})
    return {"cursos": res, "es_admin": u.rol == "administrador"}


class CursoIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=200)
    materia: str = Field(min_length=2, max_length=120)
    roles: list[str] = []
    instructor: str | None = Field(None, max_length=200)
    institucion: str | None = Field(None, max_length=200)
    descripcion: str | None = Field(None, max_length=3000)
    duracion_min: int | None = Field(None, ge=1, le=10000)
    modalidad: str = "autodirigido"
    juridico: bool = False
    asistido_ia: bool = False
    calificacion_minima: int | None = Field(None, ge=1, le=100)


@router.post("/admin/cursos", status_code=201)
def crear_curso(d: CursoIn, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    if d.modalidad not in base.MODALIDADES:
        raise HTTPException(422, "Modalidad inválida.")
    c = m.AcCurso(organizacion_id=u.organizacion_id, titulo=d.titulo.strip(), materia=d.materia.strip(), roles=[r.strip()[:60] for r in d.roles if r.strip()][:10],
                  instructor=_txt(d.instructor, 200) or u.nombre, institucion=_txt(d.institucion, 200), descripcion=_txt(d.descripcion, 3000),
                  duracion_min=d.duracion_min, modalidad=d.modalidad, estado="borrador", juridico=d.juridico, asistido_ia=d.asistido_ia,
                  calificacion_minima=d.calificacion_minima, creado_por_id=u.id, version=1)
    db.add(c)
    db.flush()
    mod = m.AcModulo(curso_id=c.id, titulo="Módulo 1", orden=0)
    db.add(mod)
    _aud(db, u, "ac_curso_creado", "ac_curso", c.id, request)
    db.commit()
    return admin_curso(c.id, u, db)


@router.get("/admin/cursos/{cid}")
def admin_curso(cid: int, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    c = db.get(m.AcCurso, cid)
    if not c or c.organizacion_id not in (None, u.organizacion_id):
        raise HTTPException(404, "No encontrado.")
    nombres = _nombres(db, u.organizacion_id)
    mods = db.scalars(select(m.AcModulo).where(m.AcModulo.curso_id == c.id, m.AcModulo.archivado_en.is_(None)).order_by(m.AcModulo.orden, m.AcModulo.id)).all()
    ls = base.lecciones(db, c.id)
    sesiones = db.scalars(select(m.AcSesion).where(m.AcSesion.curso_id == c.id, m.AcSesion.organizacion_id == u.organizacion_id).order_by(m.AcSesion.inicio)).all()
    return {**{k: v for k, v in curso_tarjeta(c, db, u).items() if k not in ("progreso", "asignacion")},
            "estado_texto": base.ESTADOS.get(c.estado, c.estado), "asistido_ia": c.asistido_ia, "requiere_revision": c.requiere_revision,
            "nota_revision": c.nota_revision, "calificacion_minima": c.calificacion_minima, "editable": base.puede_editar(db, u, c),
            "revisado_por": nombres.get(c.revisado_por_id), "revisado_en": c.revisado_en.isoformat() if c.revisado_en else None,
            "publicado_por": nombres.get(c.publicado_por_id), "publicado_en": c.publicado_en.isoformat() if c.publicado_en else None,
            "creado_por": nombres.get(c.creado_por_id),
            "modulos": [{"id": mo.id, "titulo": mo.titulo, "orden": mo.orden,
                         "lecciones": [leccion_admin(x) for x in ls if x.modulo_id == mo.id]} for mo in mods],
            "preguntas": [{"id": p.id, "texto": p.texto, "opciones": p.opciones, "correcta": p.correcta, "explicacion": p.explicacion}
                          for p in base.preguntas(db, c.id)],
            "sesiones": [sesion_dict(s) for s in sesiones]}


def leccion_admin(x: m.AcLeccion) -> dict:
    return {"id": x.id, "modulo_id": x.modulo_id, "titulo": x.titulo, "orden": x.orden, "texto": x.texto, "video_url": x.video_url,
            "sesion_url": x.sesion_url, "transcripcion": x.transcripcion, "recursos": x.recursos or [], "actividad": x.actividad,
            "duracion_min": x.duracion_min, "archivo": {"nombre": x.archivo_nombre, "formato": x.archivo_formato, "tamano": x.archivo_tamano}
            if x.archivo_ruta else None}


class CursoCambio(BaseModel):
    titulo: str | None = Field(None, min_length=3, max_length=200)
    materia: str | None = Field(None, min_length=2, max_length=120)
    roles: list[str] | None = None
    instructor: str | None = Field(None, max_length=200)
    institucion: str | None = Field(None, max_length=200)
    descripcion: str | None = Field(None, max_length=3000)
    duracion_min: int | None = Field(None, ge=1, le=10000)
    modalidad: str | None = None
    juridico: bool | None = None
    asistido_ia: bool | None = None
    calificacion_minima: int | None = Field(None, ge=1, le=100)
    requiere_revision: bool | None = None
    nota_revision: str | None = Field(None, max_length=500)


@router.patch("/admin/cursos/{cid}")
def cambiar_curso(cid: int, d: CursoCambio, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    c = _editable(db, cid, u)
    datos = d.model_dump(exclude_unset=True)
    if "modalidad" in datos and datos["modalidad"] not in base.MODALIDADES:
        raise HTTPException(422, "Modalidad inválida.")
    contenido = {"titulo", "materia", "descripcion", "calificacion_minima", "duracion_min", "modalidad", "instructor", "institucion"}
    for k, v in datos.items():
        if k == "roles":
            v = [r.strip()[:60] for r in (v or []) if r.strip()][:10]
        elif isinstance(v, str):
            v = v.strip() or None
            if k in ("titulo", "materia") and not v:
                continue
        setattr(c, k, v)
    if datos.get("requiere_revision") is False:
        c.nota_revision = None
        c.revisado_por_id, c.revisado_en = u.id, m.ahora()
    if contenido & set(datos):
        base.tocar(c)
    _aud(db, u, "ac_curso_actualizado", "ac_curso", c.id, request, campos=sorted(datos), version=c.version)
    db.commit()
    return admin_curso(c.id, u, db)


class Publicar(BaseModel):
    revisado: bool = False


@router.post("/admin/cursos/{cid}/publicar")
def publicar(cid: int, d: Publicar, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    """Solo una persona autorizada (administrador o instructor) publica. Si el curso es jurídico o se
    preparó con ayuda de IA, debe confirmar que revisó el contenido: nada se publica como validado solo."""
    c = _editable(db, cid, u)
    if not base.lecciones(db, c.id):
        raise HTTPException(422, "Agregue al menos una lección antes de publicar.")
    if (c.juridico or c.asistido_ia) and not d.revisado:
        raise HTTPException(422, "Confirme que una persona autorizada revisó el contenido antes de publicarlo.")
    if c.calificacion_minima is not None and not base.preguntas(db, c.id):
        raise HTTPException(422, "El curso pide una calificación mínima: agregue preguntas al cuestionario o quite la calificación mínima.")
    if d.revisado:
        c.revisado_por_id, c.revisado_en = u.id, m.ahora()
    c.estado, c.publicado_por_id, c.publicado_en, c.archivado_en = "publicado", u.id, m.ahora(), None
    _aud(db, u, "ac_curso_publicado", "ac_curso", c.id, request, version=c.version, revisado=d.revisado)
    db.commit()
    return admin_curso(c.id, u, db)


def duplicar(cid: int, request: Request, u: m.Usuario, db: Session):
    c = db.get(m.AcCurso, cid)
    if not c or c.organizacion_id not in (None, u.organizacion_id):
        raise HTTPException(404, "No encontrado.")
    n = m.AcCurso(organizacion_id=u.organizacion_id, titulo=(f"{c.titulo} (copia)")[:200], materia=c.materia, roles=c.roles,
                  instructor=c.instructor, institucion=c.institucion, descripcion=c.descripcion, duracion_min=c.duracion_min, modalidad=c.modalidad,
                  estado="borrador", juridico=c.juridico, asistido_ia=c.asistido_ia, calificacion_minima=c.calificacion_minima, creado_por_id=u.id, version=1)
    db.add(n)
    db.flush()
    for mo in db.scalars(select(m.AcModulo).where(m.AcModulo.curso_id == c.id, m.AcModulo.archivado_en.is_(None)).order_by(m.AcModulo.orden, m.AcModulo.id)):
        nm = m.AcModulo(curso_id=n.id, titulo=mo.titulo, orden=mo.orden)
        db.add(nm)
        db.flush()
        for x in base.lecciones(db, c.id):
            if x.modulo_id == mo.id:
                db.add(m.AcLeccion(curso_id=n.id, modulo_id=nm.id, titulo=x.titulo, orden=x.orden, texto=x.texto, video_url=x.video_url,
                                   sesion_url=x.sesion_url, transcripcion=x.transcripcion, recursos=x.recursos, actividad=x.actividad,
                                   archivo_ruta=x.archivo_ruta, archivo_nombre=x.archivo_nombre, archivo_formato=x.archivo_formato,
                                   archivo_tamano=x.archivo_tamano, duracion_min=x.duracion_min))
    for p in base.preguntas(db, c.id):
        db.add(m.AcPregunta(curso_id=n.id, texto=p.texto, opciones=p.opciones, correcta=p.correcta, explicacion=p.explicacion, orden=p.orden))
    _aud(db, u, "ac_curso_duplicado", "ac_curso", n.id, request, origen=c.id)
    db.commit()
    return admin_curso(n.id, u, db)


class ModuloIn(BaseModel):
    titulo: str = Field(min_length=2, max_length=200)


@router.post("/admin/cursos/{cid}/modulos", status_code=201)
def crear_modulo(cid: int, d: ModuloIn, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    c = _editable(db, cid, u)
    orden = max((x.orden for x in db.scalars(select(m.AcModulo).where(m.AcModulo.curso_id == c.id))), default=-1) + 1
    db.add(m.AcModulo(curso_id=c.id, titulo=d.titulo.strip(), orden=orden))
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="modulo_creado")
    db.commit()
    return admin_curso(c.id, u, db)


class ModuloCambio(BaseModel):
    titulo: str | None = Field(None, min_length=2, max_length=200)
    mover: str | None = None  # arriba | abajo


def _mover(xs: list, x, direccion: str):
    i = xs.index(x)
    j = i - 1 if direccion == "arriba" else i + 1
    if 0 <= j < len(xs):
        xs[i], xs[j] = xs[j], xs[i]
    for k, y in enumerate(xs):
        y.orden = k


@router.patch("/admin/modulos/{mid}")
def cambiar_modulo(mid: int, d: ModuloCambio, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    mo = db.get(m.AcModulo, mid)
    if not mo:
        raise HTTPException(404, "No encontrado.")
    c = _editable(db, mo.curso_id, u)
    if d.titulo:
        mo.titulo = d.titulo.strip()
    if d.mover in ("arriba", "abajo"):
        xs = db.scalars(select(m.AcModulo).where(m.AcModulo.curso_id == c.id, m.AcModulo.archivado_en.is_(None)).order_by(m.AcModulo.orden, m.AcModulo.id)).all()
        _mover(list(xs), mo, d.mover)
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="modulo_editado")
    db.commit()
    return admin_curso(c.id, u, db)


@router.delete("/admin/modulos/{mid}")
def archivar_modulo(mid: int, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    mo = db.get(m.AcModulo, mid)
    if not mo:
        raise HTTPException(404, "No encontrado.")
    c = _editable(db, mo.curso_id, u)
    mo.archivado_en = m.ahora()  # se archiva: el avance de quien ya tomó sus lecciones se conserva
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="modulo_archivado")
    db.commit()
    return admin_curso(c.id, u, db)


class Recurso(BaseModel):
    titulo: str = Field(min_length=1, max_length=150)
    url: str = Field(min_length=8, max_length=500)


class Actividad(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)
    opciones: list[str] = Field(min_length=2, max_length=6)
    correcta: int = Field(ge=0, le=5)
    explicacion: str | None = Field(None, max_length=500)


class LeccionIn(BaseModel):
    titulo: str | None = Field(None, min_length=2, max_length=200)
    texto: str | None = Field(None, max_length=20000)
    video_url: str | None = Field(None, max_length=500)
    sesion_url: str | None = Field(None, max_length=500)
    transcripcion: str | None = Field(None, max_length=50000)
    recursos: list[Recurso] | None = None
    actividad: Actividad | None = None
    quitar_actividad: bool = False
    duracion_min: int | None = Field(None, ge=1, le=600)
    mover: str | None = None
    modulo_id: int | None = None


def _aplicar_leccion(x: m.AcLeccion, d: LeccionIn):
    datos = d.model_dump(exclude_unset=True)
    if d.titulo:
        x.titulo = d.titulo.strip()
    for k in ("texto", "transcripcion"):
        if k in datos:
            setattr(x, k, _txt(datos[k], 50000))
    for k in ("video_url", "sesion_url"):
        if k in datos:
            setattr(x, k, _url(datos[k]))
    if "recursos" in datos:
        x.recursos = [{"titulo": r.titulo.strip(), "url": _url(r.url)} for r in (d.recursos or [])][:20] or None
    if "duracion_min" in datos:
        x.duracion_min = d.duracion_min
    if d.actividad:
        ops = [o.strip()[:200] for o in d.actividad.opciones if o.strip()]
        if len(ops) < 2 or d.actividad.correcta >= len(ops):
            raise HTTPException(422, "La actividad necesita al menos dos opciones y una respuesta correcta.")
        x.actividad = {"pregunta": d.actividad.pregunta.strip(), "opciones": ops, "correcta": d.actividad.correcta,
                       "explicacion": _txt(d.actividad.explicacion, 500)}
    elif d.quitar_actividad:
        x.actividad = None


@router.post("/admin/modulos/{mid}/lecciones", status_code=201)
def crear_leccion(mid: int, d: LeccionIn, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    mo = db.get(m.AcModulo, mid)
    if not mo or mo.archivado_en:
        raise HTTPException(404, "No encontrado.")
    c = _editable(db, mo.curso_id, u)
    if not d.titulo:
        raise HTTPException(422, "Escriba el título de la lección.")
    orden = max((x.orden for x in db.scalars(select(m.AcLeccion).where(m.AcLeccion.modulo_id == mo.id))), default=-1) + 1
    x = m.AcLeccion(curso_id=c.id, modulo_id=mo.id, titulo=d.titulo.strip(), orden=orden)
    _aplicar_leccion(x, d)
    db.add(x)
    base.tocar(c)
    db.flush()
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="leccion_creada", leccion_id=x.id)
    db.commit()
    return admin_curso(c.id, u, db)


@router.patch("/admin/lecciones/{lid}")
def cambiar_leccion(lid: int, d: LeccionIn, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    x, c = _leccion(db, lid, u, editar=True)
    _aplicar_leccion(x, d)
    if d.modulo_id and d.modulo_id != x.modulo_id:
        mo = db.get(m.AcModulo, d.modulo_id)
        if not mo or mo.curso_id != c.id or mo.archivado_en:
            raise HTTPException(422, "Módulo inválido.")
        x.modulo_id = mo.id
        x.orden = max((y.orden for y in db.scalars(select(m.AcLeccion).where(m.AcLeccion.modulo_id == mo.id))), default=-1) + 1
    if d.mover in ("arriba", "abajo"):
        xs = db.scalars(select(m.AcLeccion).where(m.AcLeccion.modulo_id == x.modulo_id, m.AcLeccion.archivado_en.is_(None))
                        .order_by(m.AcLeccion.orden, m.AcLeccion.id)).all()
        _mover(list(xs), x, d.mover)
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="leccion_editada", leccion_id=x.id)
    db.commit()
    return admin_curso(c.id, u, db)


@router.delete("/admin/lecciones/{lid}")
def archivar_leccion(lid: int, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    x, c = _leccion(db, lid, u, editar=True)
    x.archivado_en = m.ahora()
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="leccion_archivada", leccion_id=x.id)
    db.commit()
    return admin_curso(c.id, u, db)


@router.post("/admin/lecciones/{lid}/archivo")
def subir_material(lid: int, request: Request, archivo: UploadFile = File(...), u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    x, c = _leccion(db, lid, u, editar=True)
    datos = archivo.file.read(MAX_ARCHIVO + 1)
    if len(datos) > MAX_ARCHIVO:
        raise HTTPException(413, "El archivo supera 25 MB.")
    ext = (archivo.filename or "").rsplit(".", 1)[-1].lower()
    ext = "jpg" if ext == "jpeg" else ext
    firmas = {"pdf": b"%PDF", "png": b"\x89PNG", "jpg": b"\xff\xd8\xff", "docx": b"PK", "xlsx": b"PK", "pptx": b"PK"}
    if ext not in FORMATOS or (ext in firmas and not datos.startswith(firmas[ext])):
        raise HTTPException(415, "Formatos permitidos: PDF, Word, Excel, PowerPoint, imagen (PNG o JPG) o texto.")
    sha = hashlib.sha256(datos).hexdigest()
    carpeta = Path(ajustes().storage_dir) / str(u.organizacion_id) / "academia" / str(c.id)
    carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
    ruta = carpeta / f"{sha}.{ext}"
    ruta.write_bytes(datos)
    os.chmod(ruta, 0o600)
    x.archivo_ruta, x.archivo_nombre, x.archivo_formato, x.archivo_tamano = str(ruta), os.path.basename(archivo.filename or f"material.{ext}")[:300], ext, len(datos)
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="material_cargado", leccion_id=x.id, sha256=sha)
    db.commit()
    return admin_curso(c.id, u, db)


@router.delete("/admin/lecciones/{lid}/archivo")
def quitar_material(lid: int, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    x, c = _leccion(db, lid, u, editar=True)
    x.archivo_ruta = x.archivo_nombre = x.archivo_formato = x.archivo_tamano = None  # el archivo se conserva (puede usarlo una copia)
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="material_quitado", leccion_id=x.id)
    db.commit()
    return admin_curso(c.id, u, db)


class PreguntaIn(BaseModel):
    texto: str = Field(min_length=3, max_length=500)
    opciones: list[str] = Field(min_length=2, max_length=6)
    correcta: int = Field(ge=0, le=5)
    explicacion: str | None = Field(None, max_length=500)


def _opciones(d: PreguntaIn) -> list[str]:
    ops = [o.strip()[:200] for o in d.opciones if o.strip()]
    if len(ops) < 2 or d.correcta >= len(ops):
        raise HTTPException(422, "La pregunta necesita al menos dos opciones y una respuesta correcta.")
    return ops


@router.post("/admin/cursos/{cid}/preguntas", status_code=201)
def crear_pregunta(cid: int, d: PreguntaIn, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    c = _editable(db, cid, u)
    orden = len(base.preguntas(db, c.id))
    db.add(m.AcPregunta(curso_id=c.id, texto=d.texto.strip(), opciones=_opciones(d), correcta=d.correcta, explicacion=_txt(d.explicacion, 500), orden=orden))
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="pregunta_creada")
    db.commit()
    return admin_curso(c.id, u, db)


@router.patch("/admin/preguntas/{pid}")
def cambiar_pregunta(pid: int, d: PreguntaIn, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    p = db.get(m.AcPregunta, pid)
    if not p or p.archivado_en:
        raise HTTPException(404, "No encontrado.")
    c = _editable(db, p.curso_id, u)
    p.texto, p.opciones, p.correcta, p.explicacion = d.texto.strip(), _opciones(d), d.correcta, _txt(d.explicacion, 500)
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="pregunta_editada")
    db.commit()
    return admin_curso(c.id, u, db)


@router.delete("/admin/preguntas/{pid}")
def quitar_pregunta(pid: int, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    p = db.get(m.AcPregunta, pid)
    if not p:
        raise HTTPException(404, "No encontrado.")
    c = _editable(db, p.curso_id, u)
    p.archivado_en = m.ahora()
    base.tocar(c)
    _aud(db, u, "ac_contenido_cambiado", "ac_curso", c.id, request, cambio="pregunta_archivada")
    db.commit()
    return admin_curso(c.id, u, db)


class SesionIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=200)
    inicio: datetime
    duracion_min: int = Field(60, ge=10, le=600)
    enlace: str | None = Field(None, max_length=500)
    grabacion_url: str | None = Field(None, max_length=500)
    notas: str | None = Field(None, max_length=500)
    cancelada: bool = False


@router.post("/admin/cursos/{cid}/sesiones", status_code=201)
def crear_sesion(cid: int, d: SesionIn, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    c = db.get(m.AcCurso, cid)
    if not c or c.organizacion_id not in (None, u.organizacion_id):
        raise HTTPException(404, "No encontrado.")
    s = m.AcSesion(organizacion_id=u.organizacion_id, curso_id=c.id, titulo=d.titulo.strip(), inicio=d.inicio, duracion_min=d.duracion_min,
                   enlace=_url(d.enlace), grabacion_url=_url(d.grabacion_url), notas=_txt(d.notas, 500), creado_por_id=u.id)
    db.add(s)
    db.flush()
    _aud(db, u, "ac_sesion_creada", "ac_sesion", s.id, request, curso_id=c.id)
    db.commit()
    return admin_curso(c.id, u, db)


@router.patch("/admin/sesiones/{sid}")
def cambiar_sesion(sid: int, d: SesionIn, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    s = db.get(m.AcSesion, sid)
    if not s or s.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    s.titulo, s.inicio, s.duracion_min, s.enlace = d.titulo.strip(), d.inicio, d.duracion_min, _url(d.enlace)
    s.grabacion_url, s.notas, s.cancelada = _url(d.grabacion_url), _txt(d.notas, 500), d.cancelada
    _aud(db, u, "ac_sesion_actualizada", "ac_sesion", s.id, request, cancelada=s.cancelada)
    db.commit()
    return admin_curso(s.curso_id, u, db)


# ---------- equipo: avance, asignaciones, equipos e instructores ----------

def _personas(db: Session, u: m.Usuario) -> list[m.Usuario]:
    return db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == u.organizacion_id, m.Usuario.eliminado_en.is_(None))
                      .order_by(m.Usuario.nombre)).all()


def _cursos_equipo(db: Session, u: m.Usuario) -> list[m.AcCurso]:
    """Administradores: todos los cursos. Instructores: solo los que crearon (y los de Nomira que asignaron)."""
    xs = db.scalars(select(m.AcCurso).where((m.AcCurso.organizacion_id == u.organizacion_id) | (m.AcCurso.organizacion_id.is_(None)))).all()
    if u.rol == "administrador":
        return xs
    mios = set(db.scalars(select(m.AcAsignacion.curso_id).where(m.AcAsignacion.asignado_por_id == u.id)))
    return [c for c in xs if c.creado_por_id == u.id or c.id in mios]


def _matriz(db: Session, u: m.Usuario) -> tuple[list[m.Usuario], list[m.AcCurso], dict, dict]:
    personas = _personas(db, u)
    cursos = {c.id: c for c in _cursos_equipo(db, u)}
    avs = {(a.usuario_id, a.curso_id): a for a in db.scalars(select(m.AcAvance).where(m.AcAvance.organizacion_id == u.organizacion_id))
           if a.curso_id in cursos}
    asig = {}
    for p in personas:
        for cid, x in base.asignaciones_de(db, p).items():
            if cid in cursos:
                asig[(p.id, cid)] = x
    usados = {cid for (_, cid) in avs} | {cid for (_, cid) in asig}
    return personas, [c for c in cursos.values() if c.id in usados or (c.organizacion_id == u.organizacion_id and c.estado == "publicado")], avs, asig


def _celda(db, c, a, x) -> dict:
    p = base.progreso(db, c, a)
    vencida = bool(x and x.fecha_sugerida and x.fecha_sugerida < date.today() and p["estado"] != "completado")
    return {"estado": p["estado"], "texto": p["texto"], "porcentaje": p["porcentaje"], "calificacion": a.calificacion if a else None,
            "completado_en": a.completado_en.isoformat() if a and a.completado_en else None, "avance_id": a.id if a else None,
            "folio": a.constancia_folio if a else None, "asignacion": {"id": x.id, "tipo": x.tipo, "por_equipo": x.equipo_id is not None,
                                                                          "fecha_sugerida": x.fecha_sugerida.isoformat() if x.fecha_sugerida else None,
                                                                          "vencida": vencida} if x else None}


@router.get("/equipo")
def equipo(u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    personas, cursos, avs, asig = _matriz(db, u)
    equipos = db.scalars(select(m.AcEquipo).where(m.AcEquipo.organizacion_id == u.organizacion_id).order_by(m.AcEquipo.nombre)).all()
    miembros = {e.id: base.miembros(db, e.id) for e in equipos}
    por_persona = []
    for p in personas:
        celdas = {c.id: _celda(db, c, avs.get((p.id, c.id)), asig.get((p.id, c.id))) for c in cursos
                  if (p.id, c.id) in avs or (p.id, c.id) in asig}
        por_persona.append({"id": p.id, "nombre": p.nombre, "activo": p.activo, "equipos": [e.nombre for e in equipos if p.id in miembros[e.id]],
                            "cursos": celdas, "asignados": sum(1 for x in celdas.values() if x["asignacion"]),
                            "completados": sum(1 for x in celdas.values() if x["estado"] == "completado"),
                            "atrasados": sum(1 for x in celdas.values() if x["asignacion"] and x["asignacion"]["vencida"])})
    por_curso = []
    for c in cursos:
        filas = [x for x in por_persona if c.id in x["cursos"]]
        asignados = [x for x in filas if x["cursos"][c.id]["asignacion"]]
        por_curso.append({"id": c.id, "titulo": c.titulo, "materia": c.materia, "estado": c.estado, "origen": "nomira" if c.organizacion_id is None else "despacho",
                          "aviso_vigencia": base.aviso_vigencia(c), "asignados": len(asignados),
                          "iniciados": sum(1 for x in filas if x["cursos"][c.id]["estado"] != "sin_iniciar"),
                          "completados": sum(1 for x in filas if x["cursos"][c.id]["estado"] == "completado"),
                          "atrasados": sum(1 for x in asignados if x["cursos"][c.id]["asignacion"]["vencida"])})
    por_equipo = []
    for e in equipos:
        filas = [x for x in por_persona if x["id"] in miembros[e.id]]
        tot = sum(x["asignados"] for x in filas)
        hechos = sum(1 for x in filas for cc in x["cursos"].values() if cc["asignacion"] and cc["estado"] == "completado")
        por_equipo.append({"id": e.id, "nombre": e.nombre, "descripcion": e.descripcion, "miembros": [{"id": x["id"], "nombre": x["nombre"]} for x in filas],
                           "asignaciones": tot, "completadas": hechos, "porcentaje": round(100 * hechos / tot) if tot else None})
    instructores = set(db.scalars(select(m.AcInstructor.usuario_id).where(m.AcInstructor.organizacion_id == u.organizacion_id)))
    asignaciones = db.scalars(select(m.AcAsignacion).where(m.AcAsignacion.organizacion_id == u.organizacion_id).order_by(m.AcAsignacion.creado_en.desc()).limit(300)).all()
    nombres = _nombres(db, u.organizacion_id)
    titulos = {c.id: c.titulo for c in db.scalars(select(m.AcCurso).where(m.AcCurso.id.in_({x.curso_id for x in asignaciones})))}
    eq = {e.id: e.nombre for e in equipos}
    return {"personas": por_persona, "cursos": [{"id": c.id, "titulo": c.titulo} for c in cursos], "por_curso": por_curso, "equipos": por_equipo,
            "instructores": sorted(instructores), "usuarios": [{"id": p.id, "nombre": p.nombre, "rol": p.rol, "activo": p.activo} for p in personas],
            "asignaciones": [{"id": x.id, "curso_id": x.curso_id, "curso": titulos.get(x.curso_id), "persona": nombres.get(x.usuario_id),
                              "equipo": eq.get(x.equipo_id), "tipo": x.tipo, "fecha_sugerida": x.fecha_sugerida.isoformat() if x.fecha_sugerida else None,
                              "asignado_por": nombres.get(x.asignado_por_id), "creado_en": x.creado_en.isoformat(),
                              "retirada_en": x.retirada_en.isoformat() if x.retirada_en else None, "retirada_por": nombres.get(x.retirada_por_id)}
                             for x in asignaciones],
            "es_admin": u.rol == "administrador"}


class AsignarIn(BaseModel):
    curso_id: int
    usuario_ids: list[int] = []
    equipo_ids: list[int] = []
    tipo: str = "obligatorio"
    fecha_sugerida: date | None = None


@router.post("/asignaciones", status_code=201)
def asignar(d: AsignarIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    c = db.get(m.AcCurso, d.curso_id)
    if not c or c.organizacion_id not in (None, u.organizacion_id):
        raise HTTPException(404, "No encontrado.")
    if c.estado != "publicado":
        raise HTTPException(409, "Solo se pueden asignar cursos publicados.")
    if not base.vigente(c):
        raise HTTPException(409, "Este curso está marcado para revisión o puede estar desactualizado: revíselo o actualícelo antes de asignarlo.")
    if d.tipo not in base.TIPOS_ASIGNACION:
        raise HTTPException(422, "Tipo inválido.")
    if not d.usuario_ids and not d.equipo_ids:
        raise HTTPException(422, "Elija al menos una persona o un equipo.")
    creadas = 0
    for uid in dict.fromkeys(d.usuario_ids):
        _usuario_org(db, uid, u)
        if db.scalar(select(m.AcAsignacion.id).where(m.AcAsignacion.curso_id == c.id, m.AcAsignacion.usuario_id == uid, m.AcAsignacion.retirada_en.is_(None))):
            continue
        db.add(m.AcAsignacion(organizacion_id=u.organizacion_id, curso_id=c.id, usuario_id=uid, tipo=d.tipo, fecha_sugerida=d.fecha_sugerida, asignado_por_id=u.id))
        creadas += 1
    for eid in dict.fromkeys(d.equipo_ids):
        e = db.get(m.AcEquipo, eid)
        if not e or e.organizacion_id != u.organizacion_id:
            raise HTTPException(422, "Equipo inválido.")
        if db.scalar(select(m.AcAsignacion.id).where(m.AcAsignacion.curso_id == c.id, m.AcAsignacion.equipo_id == eid, m.AcAsignacion.retirada_en.is_(None))):
            continue
        db.add(m.AcAsignacion(organizacion_id=u.organizacion_id, curso_id=c.id, equipo_id=eid, tipo=d.tipo, fecha_sugerida=d.fecha_sugerida, asignado_por_id=u.id))
        creadas += 1
    _aud(db, u, "ac_curso_asignado", "ac_curso", c.id, request, personas=d.usuario_ids, equipos=d.equipo_ids, tipo=d.tipo,
         fecha=d.fecha_sugerida.isoformat() if d.fecha_sugerida else None)
    db.commit()
    return {"creadas": creadas}


@router.delete("/asignaciones/{aid}")
def retirar(aid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    x = db.get(m.AcAsignacion, aid)
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    if x.retirada_en:
        raise HTTPException(409, "Ya estaba retirada.")
    x.retirada_en, x.retirada_por_id = m.ahora(), u.id  # el avance de la persona se conserva
    _aud(db, u, "ac_asignacion_retirada", "ac_asignacion", x.id, request, curso_id=x.curso_id)
    db.commit()
    return {"ok": True}


class EquipoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    descripcion: str | None = Field(None, max_length=300)
    usuario_ids: list[int] = []


def _miembros(db, e: m.AcEquipo, ids: list[int], u: m.Usuario):
    for x in db.scalars(select(m.AcEquipoMiembro).where(m.AcEquipoMiembro.equipo_id == e.id)):
        db.delete(x)
    db.flush()
    for uid in dict.fromkeys(ids):
        _usuario_org(db, uid, u)
        db.add(m.AcEquipoMiembro(equipo_id=e.id, usuario_id=uid))


@router.post("/equipos", status_code=201)
def crear_equipo(d: EquipoIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    e = m.AcEquipo(organizacion_id=u.organizacion_id, nombre=d.nombre.strip(), descripcion=_txt(d.descripcion, 300))
    db.add(e)
    db.flush()
    _miembros(db, e, d.usuario_ids, u)
    _aud(db, u, "ac_equipo_creado", "ac_equipo", e.id, request, miembros=d.usuario_ids)
    db.commit()
    return {"id": e.id}


@router.put("/equipos/{eid}")
def cambiar_equipo(eid: int, d: EquipoIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    e = db.get(m.AcEquipo, eid)
    if not e or e.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    e.nombre, e.descripcion = d.nombre.strip(), _txt(d.descripcion, 300)
    _miembros(db, e, d.usuario_ids, u)
    _aud(db, u, "ac_equipo_actualizado", "ac_equipo", e.id, request, miembros=d.usuario_ids)
    db.commit()
    return {"id": e.id}


@router.delete("/equipos/{eid}")
def borrar_equipo(eid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    e = db.get(m.AcEquipo, eid)
    if not e or e.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    for x in db.scalars(select(m.AcAsignacion).where(m.AcAsignacion.equipo_id == e.id, m.AcAsignacion.retirada_en.is_(None))):
        x.retirada_en, x.retirada_por_id = m.ahora(), u.id
    db.flush()
    # las asignaciones retiradas conservan el historial con el nombre del equipo en la auditoría
    _aud(db, u, "ac_equipo_eliminado", "ac_equipo", e.id, request, nombre=e.nombre)
    for x in db.scalars(select(m.AcAsignacion).where(m.AcAsignacion.equipo_id == e.id)):
        x.equipo_id = None
    db.delete(e)
    db.commit()
    return {"ok": True}


class Instructores(BaseModel):
    usuario_ids: list[int]


@router.put("/instructores")
def fijar_instructores(d: Instructores, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    for x in db.scalars(select(m.AcInstructor).where(m.AcInstructor.organizacion_id == u.organizacion_id)):
        db.delete(x)
    db.flush()
    for uid in dict.fromkeys(d.usuario_ids):
        x = _usuario_org(db, uid, u)
        if x.rol == "consulta":
            raise HTTPException(422, f"{x.nombre} tiene rol «consulta»: no puede ser instructor.")
        db.add(m.AcInstructor(organizacion_id=u.organizacion_id, usuario_id=uid))
    _aud(db, u, "ac_instructores_actualizados", None, None, request, usuarios=d.usuario_ids)
    db.commit()
    return {"ok": True}


@router.get("/reportes/excel")
def reporte(request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    personas, cursos, avs, asig = _matriz(db, u)
    equipos = db.scalars(select(m.AcEquipo).where(m.AcEquipo.organizacion_id == u.organizacion_id)).all()
    mie = {e.id: set(base.miembros(db, e.id)) for e in equipos}
    wb = Workbook()
    ws = wb.active
    ws.title = "Finalización"
    cab = ["Persona", "Equipo(s)", "Curso", "Materia", "Asignación", "Fecha sugerida", "Estado", "Avance (%)", "Calificación", "Completado el",
           "Folio de constancia", "Versión del curso al completarlo"]
    ws.append(cab)
    for c_ in ws[1]:
        c_.font = Font(bold=True)
    for p in personas:
        for c in cursos:
            a, x = avs.get((p.id, c.id)), asig.get((p.id, c.id))
            if not a and not x:
                continue
            cel = _celda(db, c, a, x)
            ws.append([p.nombre, ", ".join(e.nombre for e in equipos if p.id in mie[e.id]), a.curso_titulo if a and a.curso_titulo else c.titulo,
                       c.materia, base.TIPOS_ASIGNACION.get(x.tipo) if x else "Por iniciativa propia",
                       x.fecha_sugerida.isoformat() if x and x.fecha_sugerida else None, cel["texto"], cel["porcentaje"], cel["calificacion"],
                       a.completado_en.date().isoformat() if a and a.completado_en else None, a.constancia_folio if a else None,
                       a.curso_version if a and a.completado_en else None])
    _aud(db, u, "ac_reporte_exportado", None, None, request)
    db.commit()
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={**PRIVADO, "Content-Disposition": 'attachment; filename="academia-finalizacion.xlsx"', "Access-Control-Expose-Headers": "Content-Disposition"})


# Declarada al final: «/admin/cursos/{cid}/{accion}» no debe capturar modulos, preguntas ni sesiones.
@router.post("/admin/cursos/{cid}/{accion}")
def estado_curso(cid: int, accion: str, request: Request, u: m.Usuario = Depends(_instructor), db: Session = Depends(get_db)):
    if accion == "duplicar":
        return duplicar(cid, request, u, db)
    c = _editable(db, cid, u)
    if accion == "archivar":
        c.estado, c.archivado_en = "archivado", m.ahora()
    elif accion == "despublicar":
        c.estado = "borrador"
    elif accion == "restaurar":
        c.estado, c.archivado_en = "borrador", None
    else:
        raise HTTPException(404, "Acción desconocida.")
    _aud(db, u, f"ac_curso_{accion}", "ac_curso", c.id, request)
    db.commit()
    return admin_curso(c.id, u, db)
