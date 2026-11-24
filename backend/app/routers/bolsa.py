"""Bolsa de trabajo del despacho: vacantes, candidatos y pruebas (las pruebas requieren el módulo «psicometria»)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, condecimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, puede_editar, solo_admin, usuario_actual
from ..services import correo, envios, modulos
from ..services.bolsa import base as bt, pruebas as pb

router = APIRouter(prefix="/api/bolsa", tags=["Bolsa de trabajo"])


def _premium(db: Session, u: m.Usuario) -> bool:
    return modulos.estado(db, u.organizacion_id)["psicometria"]["activo"]


def _exigir_premium(db: Session, u: m.Usuario) -> None:
    if not _premium(db, u):
        raise HTTPException(402, "Las pruebas psicométricas son parte del módulo «Pruebas psicométricas». Contrátelo para enviarlas.")


@router.get("/config")
def config(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    org = db.get(m.Organizacion, u.organizacion_id)
    p = bt.perfil(db, org)
    db.commit()
    return {"perfil": _perfil_dict(p), "premium": _premium(db, u), "es_admin": u.rol == "administrador", "puede_editar": u.rol in ("administrador", "analista"),
            "areas": bt.AREAS, "puestos": bt.PUESTOS, "jornadas": bt.JORNADAS, "modalidades": bt.MODALIDADES, "estados_mx": bt.ESTADOS_MX,
            "etapas": bt.ETAPAS, "experiencia": bt.EXPERIENCIA, "url_publica": ajustes().url_publica.rstrip("/")}


def _perfil_dict(p: m.BtPerfil) -> dict:
    return {"codigo": p.codigo, "nombre_publico": p.nombre_publico, "descripcion": p.descripcion, "ciudad": p.ciudad, "sitio_web": p.sitio_web,
            "correo_privacidad": p.correo_privacidad, "url": f"{ajustes().url_publica.rstrip('/')}/empleos/despacho/{p.codigo}"}


class PerfilIn(BaseModel):
    nombre_publico: str = Field(min_length=2, max_length=200)
    descripcion: str | None = Field(None, max_length=3000)
    ciudad: str | None = Field(None, max_length=120)
    sitio_web: str | None = Field(None, max_length=200, pattern=r"^(https?://[^\s]+)?$")
    correo_privacidad: str | None = Field(None, max_length=254, pattern=r"^([^@\s]+@[^@\s]+\.[^@\s]+)?$")


@router.put("/perfil")
def guardar_perfil(d: PerfilIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    p = bt.perfil(db, db.get(m.Organizacion, u.organizacion_id))
    p.nombre_publico, p.descripcion, p.ciudad = d.nombre_publico.strip(), bt.txt(d.descripcion, 3000), bt.txt(d.ciudad, 120)
    p.sitio_web, p.correo_privacidad = bt.txt(d.sitio_web, 200), bt.txt(d.correo_privacidad, 254)
    p.actualizado_en = datetime.now(timezone.utc)
    auditar(db, u, "bolsa_perfil", "bt_perfil", p.id, None, request)
    db.commit()
    return _perfil_dict(p)


# ------------------------------------------------------------------ vacantes

def _vacante(db: Session, vid: int, u: m.Usuario) -> m.BtVacante:
    v = db.get(m.BtVacante, vid)
    if not v or v.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Vacante no encontrada.")
    return v


def vacante_dict(v: m.BtVacante, privada: bool = False) -> dict:
    x = {"codigo": v.codigo, "titulo": v.titulo, "area": v.area, "area_texto": bt.AREAS.get(v.area, v.area), "puesto": v.puesto,
         "puesto_texto": bt.PUESTOS.get(v.puesto, v.puesto), "jornada": v.jornada, "jornada_texto": bt.JORNADAS.get(v.jornada, v.jornada),
         "modalidad": v.modalidad, "modalidad_texto": bt.MODALIDADES.get(v.modalidad, v.modalidad), "estado_republica": v.estado_republica,
         "ciudad": v.ciudad, "descripcion": v.descripcion, "requisitos": v.requisitos, "ofrecemos": v.ofrecemos,
         "sueldo_min": str(v.sueldo_min) if v.sueldo_min is not None and (privada or v.mostrar_sueldo) else None,
         "sueldo_max": str(v.sueldo_max) if v.sueldo_max is not None and (privada or v.mostrar_sueldo) else None,
         "publicada_en": v.publicada_en.isoformat() if v.publicada_en else None}
    if privada:
        x.update({"id": v.id, "estado": v.estado, "en_portal": v.en_portal, "mostrar_sueldo": v.mostrar_sueldo, "pruebas": v.pruebas or [],
                  "creado_en": v.creado_en.isoformat(), "cerrada_en": v.cerrada_en.isoformat() if v.cerrada_en else None,
                  "url": bt.enlace_vacante(v)})
    return x


class VacanteIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=200)
    area: str
    puesto: str
    jornada: str
    modalidad: str
    estado_republica: str | None = None
    ciudad: str | None = Field(None, max_length=120)
    sueldo_min: condecimal(ge=0, max_digits=12, decimal_places=2) | None = None
    sueldo_max: condecimal(ge=0, max_digits=12, decimal_places=2) | None = None
    mostrar_sueldo: bool = True
    descripcion: str = Field(min_length=20, max_length=8000)
    requisitos: str | None = Field(None, max_length=5000)
    ofrecemos: str | None = Field(None, max_length=5000)
    en_portal: bool = True
    pruebas: list[str] = Field(default_factory=list, max_length=8)


def _validar(db: Session, d: VacanteIn, org_id: int) -> None:
    for campo, cat in (("area", bt.AREAS), ("puesto", bt.PUESTOS), ("jornada", bt.JORNADAS), ("modalidad", bt.MODALIDADES)):
        if getattr(d, campo) not in cat:
            raise HTTPException(422, f"Valor no válido en «{campo}».")
    if d.estado_republica and d.estado_republica not in bt.ESTADOS_MX:
        raise HTTPException(422, "Estado no válido.")
    if d.modalidad != "remoto" and not d.estado_republica:
        raise HTTPException(422, "Indique en qué estado es la vacante.")
    if d.sueldo_min is not None and d.sueldo_max is not None and d.sueldo_max < d.sueldo_min:
        raise HTTPException(422, "El sueldo máximo no puede ser menor que el mínimo.")
    for p in d.pruebas:
        if not bt.prueba_def(db, org_id, p):
            raise HTTPException(422, "Una de las pruebas sugeridas no existe.")
    malos = bt.avisos_discriminacion(d.titulo, d.descripcion, d.requisitos)
    if malos:
        raise HTTPException(422, "Quite requisitos que pueden ser discriminatorios (" + ", ".join(f"«{x}»" for x in malos)
                            + "). Describa conocimientos, experiencia y habilidades del puesto.")


def _aplicar(v: m.BtVacante, d: VacanteIn) -> None:
    v.titulo, v.area, v.puesto, v.jornada, v.modalidad = d.titulo.strip(), d.area, d.puesto, d.jornada, d.modalidad
    v.estado_republica, v.ciudad = d.estado_republica, bt.txt(d.ciudad, 120)
    v.sueldo_min, v.sueldo_max, v.mostrar_sueldo = d.sueldo_min, d.sueldo_max, d.mostrar_sueldo
    v.descripcion, v.requisitos, v.ofrecemos = d.descripcion.strip(), bt.txt(d.requisitos, 5000), bt.txt(d.ofrecemos, 5000)
    v.en_portal, v.pruebas = d.en_portal, list(dict.fromkeys(d.pruebas))


@router.get("/vacantes")
def vacantes(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    vs = db.scalars(select(m.BtVacante).where(m.BtVacante.organizacion_id == u.organizacion_id).order_by(m.BtVacante.creado_en.desc())).all()
    cuentas = dict(db.execute(select(m.BtCandidato.vacante_id, func.count()).where(m.BtCandidato.organizacion_id == u.organizacion_id)
                              .group_by(m.BtCandidato.vacante_id)).all())
    nuevos = dict(db.execute(select(m.BtCandidato.vacante_id, func.count()).where(m.BtCandidato.organizacion_id == u.organizacion_id,
                                                                                 m.BtCandidato.etapa == "nuevo").group_by(m.BtCandidato.vacante_id)).all())
    return {"vacantes": [{**vacante_dict(v, True), "candidatos": cuentas.get(v.id, 0), "nuevos": nuevos.get(v.id, 0)} for v in vs]}


@router.post("/vacantes", status_code=201)
def crear_vacante(d: VacanteIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    _validar(db, d, u.organizacion_id)
    bt.perfil(db, db.get(m.Organizacion, u.organizacion_id))
    v = m.BtVacante(organizacion_id=u.organizacion_id, codigo=bt.codigo(), creado_por_id=u.id)
    _aplicar(v, d)
    db.add(v)
    db.flush()
    auditar(db, u, "bolsa_vacante", "bt_vacante", v.id, {"accion": "crear"}, request)
    db.commit()
    return vacante_dict(v, True)


@router.get("/vacantes/{vid}")
def ver_vacante(vid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    v = _vacante(db, vid, u)
    cs = db.scalars(select(m.BtCandidato).where(m.BtCandidato.vacante_id == v.id).order_by(m.BtCandidato.creado_en.desc())).all()
    apl = {}
    for a in db.scalars(select(m.BtAplicacion).where(m.BtAplicacion.candidato_id.in_([c.id for c in cs]))) if cs else []:
        apl.setdefault(a.candidato_id, []).append(_resumen_aplicacion(a))
    return {"vacante": vacante_dict(v, True), "candidatos": [{**_candidato_dict(c), "pruebas": apl.get(c.id, [])} for c in cs]}


@router.put("/vacantes/{vid}")
def editar_vacante(vid: int, d: VacanteIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    v = _vacante(db, vid, u)
    _validar(db, d, u.organizacion_id)
    _aplicar(v, d)
    auditar(db, u, "bolsa_vacante", "bt_vacante", v.id, {"accion": "editar"}, request)
    db.commit()
    return vacante_dict(v, True)


class EstadoIn(BaseModel):
    estado: str


@router.post("/vacantes/{vid}/estado")
def estado_vacante(vid: int, d: EstadoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    v = _vacante(db, vid, u)
    if d.estado not in ("publicada", "pausada", "cerrada"):
        raise HTTPException(422, "Estado no válido.")
    if d.estado == "publicada":
        if v.estado == "cerrada":
            raise HTTPException(409, "La vacante está cerrada. Cree una nueva para volver a publicar.")
        v.publicada_en = v.publicada_en or datetime.now(timezone.utc)
    if d.estado == "cerrada":
        v.cerrada_en = datetime.now(timezone.utc)
    v.estado = d.estado
    auditar(db, u, "bolsa_vacante", "bt_vacante", v.id, {"accion": d.estado}, request)
    db.commit()
    return vacante_dict(v, True)


@router.delete("/vacantes/{vid}")
def borrar_vacante(vid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    v = _vacante(db, vid, u)
    for c in db.scalars(select(m.BtCandidato).where(m.BtCandidato.vacante_id == v.id)):
        bt.borrar_cv(c.cv_archivo)
    db.delete(v)
    auditar(db, u, "bolsa_vacante", "bt_vacante", vid, {"accion": "borrar"}, request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ candidatos

def _candidato(db: Session, cid: int, u: m.Usuario) -> m.BtCandidato:
    c = db.get(m.BtCandidato, cid)
    if not c or c.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Candidato no encontrado.")
    return c


def _candidato_dict(c: m.BtCandidato) -> dict:
    return {"id": c.id, "vacante_id": c.vacante_id, "nombre": c.nombre, "email": c.email, "telefono": c.telefono, "ciudad": c.ciudad, "cedula": c.cedula,
            "experiencia": c.experiencia, "experiencia_texto": bt.EXPERIENCIA.get(c.experiencia or "", None), "mensaje": c.mensaje,
            "cv": bool(c.cv_archivo), "cv_nombre": c.cv_nombre, "etapa": c.etapa, "etapa_texto": bt.ETAPAS[c.etapa], "calificacion": c.calificacion,
            "notas": c.notas, "creado_en": c.creado_en.isoformat()}


def _resumen_aplicacion(a: m.BtAplicacion) -> dict:
    vencida = a.estado in ("enviada", "en_curso") and a.vence_en < datetime.now(timezone.utc)
    r = a.resultado or {}
    return {"id": a.id, "prueba": a.prueba, "nombre": a.nombre_prueba, "estado": "vencida" if vencida else a.estado,
            "enviada_en": a.creado_en.isoformat(), "terminada_en": a.terminada_en.isoformat() if a.terminada_en else None,
            "vence_en": a.vence_en.isoformat(), "porcentaje": r.get("porcentaje"), "tipo_resultado": r.get("tipo")}


@router.get("/candidatos/{cid}")
def ver_candidato(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _candidato(db, cid, u)
    apl = db.scalars(select(m.BtAplicacion).where(m.BtAplicacion.candidato_id == c.id).order_by(m.BtAplicacion.creado_en.desc())).all()
    return {**_candidato_dict(c), "pruebas": [_resumen_aplicacion(a) for a in apl]}


class CandidatoIn(BaseModel):
    etapa: str | None = None
    calificacion: int | None = Field(None, ge=0, le=5)
    notas: str | None = Field(None, max_length=8000)


@router.put("/candidatos/{cid}")
def editar_candidato(cid: int, d: CandidatoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _candidato(db, cid, u)
    if d.etapa is not None:
        if d.etapa not in bt.ETAPAS:
            raise HTTPException(422, "Etapa no válida.")
        c.etapa = d.etapa
    if d.calificacion is not None:
        c.calificacion = d.calificacion or None
    if d.notas is not None:
        c.notas = bt.txt(d.notas, 8000)
    c.actualizado_en = datetime.now(timezone.utc)
    auditar(db, u, "bolsa_candidato", "bt_candidato", c.id, {"etapa": c.etapa}, request)  # sin notas ni datos personales
    db.commit()
    return _candidato_dict(c)


@router.delete("/candidatos/{cid}")
def borrar_candidato(cid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Para atender una solicitud de cancelación (derechos ARCO) o depurar: borra datos, CV y pruebas."""
    c = _candidato(db, cid, u)
    bt.borrar_cv(c.cv_archivo)
    db.delete(c)
    auditar(db, u, "bolsa_candidato_borrado", "bt_candidato", cid, None, request)
    db.commit()
    return {"ok": True}


@router.get("/candidatos/{cid}/cv")
def cv(cid: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _candidato(db, cid, u)
    if not c.cv_archivo:
        raise HTTPException(404, "El candidato no envió CV.")
    ruta = Path(ajustes().storage_dir, c.cv_archivo)
    if not ruta.exists():
        raise HTTPException(404, "No se encontró el archivo.")
    mime = "application/pdf" if ruta.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(ruta, media_type=mime, filename=c.cv_nombre or f"cv{ruta.suffix}", content_disposition_type="inline")


# ------------------------------------------------------------------ pruebas (premium)

@router.get("/pruebas")
def catalogo_pruebas(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    propias = db.scalars(select(m.BtPruebaPropia).where(m.BtPruebaPropia.organizacion_id == u.organizacion_id).order_by(m.BtPruebaPropia.nombre)).all()
    return {"premium": _premium(db, u), "nomira": pb.catalogo(), "revision_juridica": pb.REVISION_JURIDICA,
            "propias": [{"clave": f"propia:{p.id}", "id": p.id, "nombre": p.nombre, "categoria": "Pruebas del despacho", "minutos": p.minutos,
                         "preguntas": len(p.preguntas), "activa": p.activa, "instrucciones": p.instrucciones} for p in propias]}


@router.get("/pruebas/ver/{clave}")
def ver_prueba(clave: str, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Vista previa para el despacho, con las respuestas correctas."""
    p = bt.prueba_def(db, u.organizacion_id, clave)
    if not p:
        raise HTTPException(404, "Prueba no encontrada.")
    preguntas = [{"texto": q["texto"], "opciones": q.get("opciones") or (pb.LIKERT if p["tipo"] == "likert" else []), "correcta": q.get("correcta")}
                 for q in p["preguntas"]]
    return {"clave": clave, "nombre": p["nombre"], "tipo": p["tipo"], "minutos": p.get("minutos"), "instrucciones": p.get("instrucciones"),
            "descripcion": p.get("descripcion"), "preguntas": preguntas}


class PreguntaIn(BaseModel):
    texto: str = Field(min_length=3, max_length=2000)
    opciones: list[str] = Field(default_factory=list, max_length=6)
    correcta: int | None = None


class PruebaPropiaIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=150)
    instrucciones: str | None = Field(None, max_length=3000)
    minutos: int | None = Field(None, ge=1, le=180)
    preguntas: list[PreguntaIn] = Field(min_length=1, max_length=80)
    activa: bool = True


def _preguntas(d: PruebaPropiaIn) -> list[dict]:
    r = []
    for i, q in enumerate(d.preguntas, 1):
        ops = [o.strip()[:500] for o in q.opciones if o.strip()]
        if ops and len(ops) < 2:
            raise HTTPException(422, f"La pregunta {i} necesita al menos 2 opciones (o ninguna, si es abierta).")
        if ops and (q.correcta is None or not 0 <= q.correcta < len(ops)):
            raise HTTPException(422, f"Marque la respuesta correcta de la pregunta {i}.")
        r.append({"texto": q.texto.strip(), "opciones": ops, "correcta": q.correcta if ops else None})
    return r


@router.post("/pruebas/propias", status_code=201)
def crear_propia(d: PruebaPropiaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    _exigir_premium(db, u)
    p = m.BtPruebaPropia(organizacion_id=u.organizacion_id, nombre=d.nombre.strip(), instrucciones=bt.txt(d.instrucciones, 3000), minutos=d.minutos,
                         preguntas=_preguntas(d), activa=d.activa)
    db.add(p)
    db.flush()
    auditar(db, u, "bolsa_prueba_propia", "bt_prueba_propia", p.id, {"accion": "crear"}, request)
    db.commit()
    return {"clave": f"propia:{p.id}", "id": p.id}


@router.post("/pruebas/copiar/{clave}", status_code=201)
def copiar(clave: str, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Copia una prueba de opción múltiple de Nomira a las pruebas del despacho para ajustarla."""
    _exigir_premium(db, u)
    p = pb.PRUEBAS.get(clave)
    if not p or p["tipo"] != "opcion":
        raise HTTPException(422, "Solo se pueden copiar pruebas de opción múltiple.")
    x = m.BtPruebaPropia(organizacion_id=u.organizacion_id, nombre=f"{p['nombre']} (copia)"[:150], instrucciones=p.get("instrucciones"),
                         minutos=p.get("minutos"), preguntas=[dict(q) for q in p["preguntas"]])
    db.add(x)
    db.flush()
    auditar(db, u, "bolsa_prueba_propia", "bt_prueba_propia", x.id, {"accion": "copiar", "de": clave}, request)
    db.commit()
    return {"clave": f"propia:{x.id}", "id": x.id}


def _propia(db: Session, pid: int, u: m.Usuario) -> m.BtPruebaPropia:
    p = db.get(m.BtPruebaPropia, pid)
    if not p or p.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Prueba no encontrada.")
    return p


@router.put("/pruebas/propias/{pid}")
def editar_propia(pid: int, d: PruebaPropiaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    _exigir_premium(db, u)
    p = _propia(db, pid, u)
    p.nombre, p.instrucciones, p.minutos, p.preguntas, p.activa = d.nombre.strip(), bt.txt(d.instrucciones, 3000), d.minutos, _preguntas(d), d.activa
    p.actualizado_en = datetime.now(timezone.utc)
    auditar(db, u, "bolsa_prueba_propia", "bt_prueba_propia", p.id, {"accion": "editar"}, request)
    db.commit()
    return {"ok": True}


@router.delete("/pruebas/propias/{pid}")
def borrar_propia(pid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _propia(db, pid, u)
    usada = db.scalar(select(m.BtAplicacion.id).where(m.BtAplicacion.prueba == f"propia:{p.id}").limit(1))
    if usada:  # los resultados guardados dependen de sus preguntas: se desactiva en lugar de borrar
        p.activa = False
    else:
        db.delete(p)
    auditar(db, u, "bolsa_prueba_propia", "bt_prueba_propia", pid, {"accion": "desactivar" if usada else "borrar"}, request)
    db.commit()
    return {"ok": True, "desactivada": bool(usada)}


class EnviarIn(BaseModel):
    pruebas: list[str] = Field(min_length=1, max_length=8)
    por_correo: bool = False


@router.post("/candidatos/{cid}/pruebas", status_code=201)
def enviar_pruebas(cid: int, d: EnviarIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    _exigir_premium(db, u)
    c = _candidato(db, cid, u)
    defs = []
    for clave in dict.fromkeys(d.pruebas):
        p = bt.prueba_def(db, u.organizacion_id, clave)
        if not p or p.get("activa") is False:
            raise HTTPException(422, "Una de las pruebas no existe o está desactivada.")
        defs.append((clave, p))
    enlaces = []
    for clave, p in defs:
        a, token = bt.nueva_aplicacion(db, c, clave, p["nombre"], u.id)
        enlaces.append({"id": a.id, "nombre": p["nombre"], "url": bt.enlace_prueba(token)})
    auditar(db, u, "bolsa_pruebas_enviadas", "bt_candidato", c.id, {"pruebas": [k for k, _ in defs]}, request)
    db.commit()
    enviado = False
    if d.por_correo and correo.configurado():
        despacho = bt.perfil(db, db.get(m.Organizacion, u.organizacion_id)).nombre_publico
        lineas = "".join(f'<li><a href="{e["url"]}">{e["nombre"]}</a></li>' for e in enlaces)
        html = (f"<p>Hola {c.nombre}:</p><p>{despacho} te invita a contestar estas pruebas como parte de tu postulación. "
                f"Cada enlace es personal y vence en {bt.DIAS_PRUEBA} días.</p><ul>{lineas}</ul><p>Busca un lugar tranquilo antes de empezar.</p>")
        texto = f"Hola {c.nombre}:\n{despacho} te invita a contestar estas pruebas (vencen en {bt.DIAS_PRUEBA} días):\n" + \
            "\n".join(f"- {e['nombre']}: {e['url']}" for e in enlaces)
        r = envios.registrar_y_enviar(db, "bolsa_pruebas", [c.email], f"{despacho}: pruebas para tu postulación", html, texto,
                                      organizacion_id=u.organizacion_id)
        enviado = bool(r and r.estado == "enviado")
    return {"enlaces": enlaces, "correo_enviado": enviado, "correo_disponible": correo.configurado()}


@router.get("/aplicaciones/{aid}")
def ver_aplicacion(aid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    a = db.get(m.BtAplicacion, aid)
    if not a or a.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrada.")
    return {**_resumen_aplicacion(a), "resultado": a.resultado, "iniciada_en": a.iniciada_en.isoformat() if a.iniciada_en else None,
            "consentimiento_en": a.consentimiento_en.isoformat() if a.consentimiento_en else None}


@router.post("/aplicaciones/{aid}/cancelar")
def cancelar_aplicacion(aid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = db.get(m.BtAplicacion, aid)
    if not a or a.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrada.")
    if a.estado == "terminada":
        raise HTTPException(409, "La prueba ya fue contestada.")
    a.estado = "cancelada"
    auditar(db, u, "bolsa_prueba_cancelada", "bt_candidato", a.candidato_id, {"aplicacion": a.id}, request)
    db.commit()
    return _resumen_aplicacion(a)
