"""Reglas de Nomira Academia: permisos, vigencia del contenido y cálculo del avance."""
from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m

MODALIDADES = {"autodirigido": "Autodirigido", "en_vivo": "En vivo", "combinado": "Combinado"}
ESTADOS = {"borrador": "Borrador", "publicado": "Publicado", "archivado": "Archivado"}
TIPOS_ASIGNACION = {"obligatorio": "Obligatorio", "recomendado": "Recomendado"}
DIAS_VIGENCIA_JURIDICA = 365
_LETRAS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def es_instructor(db: Session, u: m.Usuario) -> bool:
    if u.rol == "administrador":
        return True
    return bool(db.scalar(select(m.AcInstructor.id).where(m.AcInstructor.organizacion_id == u.organizacion_id,
                                                         m.AcInstructor.usuario_id == u.id)))


def puede_editar(db: Session, u: m.Usuario, c: m.AcCurso) -> bool:
    """Los cursos de Nomira son de solo lectura (se pueden duplicar). Los del despacho los editan
    administradores e instructores."""
    return c.organizacion_id == u.organizacion_id and es_instructor(db, u)


def aviso_vigencia(c: m.AcCurso) -> str | None:
    if c.requiere_revision:
        return c.nota_revision or "El administrador indicó que este material debe revisarse: puede estar desactualizado."
    if c.juridico and m.ahora() - c.contenido_actualizado_en > timedelta(days=DIAS_VIGENCIA_JURIDICA):
        return "Este material jurídico no se ha actualizado en más de un año: confirme que siga vigente antes de aplicarlo."
    return None


def vigente(c: m.AcCurso) -> bool:
    return aviso_vigencia(c) is None


def lecciones(db: Session, curso_id: int) -> list[m.AcLeccion]:
    """Lecciones activas en orden de módulo y lección."""
    mods = {x.id: x for x in db.scalars(select(m.AcModulo).where(m.AcModulo.curso_id == curso_id, m.AcModulo.archivado_en.is_(None)))}
    ls = [x for x in db.scalars(select(m.AcLeccion).where(m.AcLeccion.curso_id == curso_id, m.AcLeccion.archivado_en.is_(None)))
          if x.modulo_id in mods]
    return sorted(ls, key=lambda x: (mods[x.modulo_id].orden, mods[x.modulo_id].id, x.orden, x.id))


def preguntas(db: Session, curso_id: int) -> list[m.AcPregunta]:
    return db.scalars(select(m.AcPregunta).where(m.AcPregunta.curso_id == curso_id, m.AcPregunta.archivado_en.is_(None))
                      .order_by(m.AcPregunta.orden, m.AcPregunta.id)).all()


def avance_de(db: Session, u: m.Usuario, curso_id: int) -> m.AcAvance | None:
    return db.scalar(select(m.AcAvance).where(m.AcAvance.usuario_id == u.id, m.AcAvance.curso_id == curso_id))


def progreso(db: Session, c: m.AcCurso, a: m.AcAvance | None) -> dict:
    ls = lecciones(db, c.id)
    hechas = set()
    if a:
        hechas = {x.leccion_id for x in db.scalars(select(m.AcAvanceLeccion).where(m.AcAvanceLeccion.avance_id == a.id,
                                                                                  m.AcAvanceLeccion.completada_en.is_not(None)))}
    n_hechas = sum(1 for x in ls if x.id in hechas)
    pregs = preguntas(db, c.id)
    requiere_cuestionario = c.calificacion_minima is not None and bool(pregs)
    aprobado = bool(a and a.calificacion is not None and c.calificacion_minima is not None and a.calificacion >= c.calificacion_minima)
    pasos = len(ls) + (1 if requiere_cuestionario else 0)
    hechos = n_hechas + (1 if requiere_cuestionario and aprobado else 0)
    if a and a.completado_en:
        estado, texto = "completado", "Completado"
    elif a:
        estado, texto = "en_curso", f"Va en {hechos} de {pasos} pasos" if pasos else "Iniciado"
    else:
        estado, texto = "sin_iniciar", "Sin iniciar"
    siguiente = next((x.id for x in ls if x.id not in hechas), None)
    return {"estado": estado, "texto": texto, "lecciones": len(ls), "lecciones_hechas": n_hechas, "porcentaje": 100 if estado == "completado" else
            (round(100 * hechos / pasos) if pasos else 0), "requiere_cuestionario": requiere_cuestionario, "cuestionario_aprobado": aprobado,
            "calificacion": a.calificacion if a else None, "hechas": sorted(hechas), "siguiente_leccion_id": siguiente,
            "lecciones_listas": bool(ls) and n_hechas == len(ls)}


def folio() -> str:
    return "NA-" + "".join(secrets.choice(_LETRAS) for _ in range(4)) + "-" + "".join(secrets.choice(_LETRAS) for _ in range(4))


def revisar_completo(db: Session, c: m.AcCurso, a: m.AcAvance) -> bool:
    """Marca el curso como completado si ya se cumplieron sus requisitos. Devuelve True si se completó ahora."""
    if a.completado_en:
        return False
    p = progreso(db, c, a)
    if not p["lecciones_listas"] or (p["requiere_cuestionario"] and not p["cuestionario_aprobado"]):
        return False
    a.completado_en = m.ahora()
    a.curso_titulo, a.curso_version, a.curso_duracion_min = c.titulo, c.version, c.duracion_min
    f = folio()
    while db.scalar(select(m.AcAvance.id).where(m.AcAvance.constancia_folio == f)):
        f = folio()
    a.constancia_folio = f
    return True


def asignaciones_de(db: Session, u: m.Usuario) -> dict[int, m.AcAsignacion]:
    """Asignaciones vigentes de la persona (directas o por equipo). Si hay varias de un curso, gana la
    obligatoria y, entre iguales, la de fecha sugerida más próxima."""
    equipos = list(db.scalars(select(m.AcEquipoMiembro.equipo_id).where(m.AcEquipoMiembro.usuario_id == u.id)))
    q = select(m.AcAsignacion).where(m.AcAsignacion.organizacion_id == u.organizacion_id, m.AcAsignacion.retirada_en.is_(None))
    xs = [x for x in db.scalars(q) if x.usuario_id == u.id or (x.equipo_id and x.equipo_id in equipos)]
    res: dict[int, m.AcAsignacion] = {}
    for x in xs:
        act = res.get(x.curso_id)
        clave = lambda a: (a.tipo != "obligatorio", a.fecha_sugerida or m.date.max)  # noqa: E731
        if act is None or clave(x) < clave(act):
            res[x.curso_id] = x
    return res


def miembros(db: Session, equipo_id: int) -> list[int]:
    return list(db.scalars(select(m.AcEquipoMiembro.usuario_id).where(m.AcEquipoMiembro.equipo_id == equipo_id)))


def tocar(c: m.AcCurso) -> None:
    """Registra un cambio de contenido: nueva versión y fecha de actualización visible."""
    c.version = (c.version or 1) + 1
    c.contenido_actualizado_en = m.ahora()
