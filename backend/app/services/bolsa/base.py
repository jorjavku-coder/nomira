"""Bolsa de trabajo: vacantes del despacho, página pública por despacho, portal de Nomira y candidatos.

Reglas:
- Publicar vacantes y recibir candidatos es gratis para todos los despachos. Enviar pruebas requiere el módulo
  de pago «psicometria».
- No se piden edad, sexo, estado civil, foto ni otros datos que puedan usarse para discriminar.
- El despacho es responsable de los datos de sus candidatos; Nomira los trata por su cuenta y no los comparte
  con otros despachos.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ...config import ajustes
from . import pruebas as pb

AREAS = {"laboral": "Laboral", "civil": "Civil y mercantil", "familiar": "Familiar", "penal": "Penal", "amparo": "Amparo y constitucional",
         "administrativo": "Administrativo y fiscal", "corporativo": "Corporativo", "notarial": "Notarial", "seguridad_social": "Seguridad social",
         "general": "Varias materias", "administracion": "Administración del despacho"}
PUESTOS = {"abogado": "Abogado(a)", "abogado_sr": "Abogado(a) senior", "asociado": "Asociado(a)", "pasante": "Pasante", "becario": "Becario(a) / prácticas",
           "asistente": "Asistente legal", "gestor": "Gestor(a)", "recepcion": "Recepción", "contador": "Contabilidad", "otro": "Otro"}
JORNADAS = {"completa": "Tiempo completo", "medio": "Medio tiempo", "proyecto": "Por proyecto", "practicas": "Prácticas profesionales"}
MODALIDADES = {"presencial": "Presencial", "hibrido": "Híbrido", "remoto": "Remoto"}
EXPERIENCIA = {"0": "Sin experiencia", "1": "Menos de 1 año", "1-3": "1 a 3 años", "3-5": "3 a 5 años", "5-10": "5 a 10 años", "10+": "Más de 10 años"}
ETAPAS = {"nuevo": "Nuevo", "revision": "En revisión", "entrevista": "Entrevista", "oferta": "Oferta", "contratado": "Contratado", "descartado": "Descartado"}
ESTADOS_MX = ["Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua", "Ciudad de México", "Coahuila", "Colima",
              "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca",
              "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán",
              "Zacatecas"]
MAX_CV = 5 * 1024 * 1024
DIAS_PRUEBA = 7
# Palabras que suelen anunciar requisitos discriminatorios (Ley Federal para Prevenir y Eliminar la Discriminación).
_DISCRIMINATORIO = re.compile(r"\b(edad (m[aá]xima|entre)|de \d{2} a \d{2} a[nñ]os|menores? de \d{2} a[nñ]os|buena presentaci[oó]n|sexo|soltero|soltera|"
                              r"estado civil|sin hijos|no embarazada|religi[oó]n|complexi[oó]n|estatura|tez)\b", re.I)


def codigo() -> str:
    return secrets.token_urlsafe(8).replace("-", "x").replace("_", "y")[:10]


def huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def txt(v: str | None, n: int) -> str | None:
    v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", (v or "")).strip()
    return v[:n] or None


def avisos_discriminacion(*textos: str | None) -> list[str]:
    encontrados = {x.group(0).lower() for t in textos if t for x in _DISCRIMINATORIO.finditer(t)}
    return sorted(encontrados)


def perfil(db: Session, org: m.Organizacion) -> m.BtPerfil:
    p = db.scalar(select(m.BtPerfil).where(m.BtPerfil.organizacion_id == org.id))
    if p is None:
        p = m.BtPerfil(organizacion_id=org.id, codigo=codigo(), nombre_publico=org.nombre[:200])
        db.add(p)
        db.flush()
    return p


def org_visible(db: Session, org_id: int) -> bool:
    """Las vacantes de un despacho suspendido o con la prueba gratis vencida no se muestran al público."""
    from ..registro import estado_prueba

    o = db.get(m.Organizacion, org_id)
    if not o or o.estado != "activa":
        return False
    p = estado_prueba(db, o)
    return not (p and p["bloqueada"])


def guardar_cv(org_id: int, vacante_id: int, nombre: str, contenido: bytes) -> tuple[str, str]:
    """Valida por contenido (PDF o Word) y guarda. Devuelve (ruta relativa, nombre limpio)."""
    if contenido.startswith(b"%PDF"):
        ext = ".pdf"
    elif contenido.startswith(b"PK") and b"word/" in contenido[:4000]:
        ext = ".docx"
    else:
        raise ValueError("Suba su CV en PDF o Word (.docx).")
    rel = Path(str(org_id), "bolsa", str(vacante_id), f"{uuid.uuid4().hex}{ext}")
    destino = Path(ajustes().storage_dir, rel)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    limpio = re.sub(r"[^\w.\- ]+", "", Path(nombre or "cv").stem)[:80] or "cv"
    return str(rel), f"{limpio}{ext}"


def borrar_cv(rel: str | None) -> None:
    if rel:
        Path(ajustes().storage_dir, rel).unlink(missing_ok=True)


def prueba_def(db: Session, org_id: int, clave: str) -> dict | None:
    """Definición de una prueba de Nomira o de una propia del despacho."""
    if clave in pb.PRUEBAS:
        return pb.PRUEBAS[clave]
    x = re.fullmatch(r"propia:(\d+)", clave or "")
    if not x:
        return None
    p = db.get(m.BtPruebaPropia, int(x.group(1)))
    if not p or p.organizacion_id != org_id:
        return None
    return {"nombre": p.nombre, "tipo": "opcion", "minutos": p.minutos, "instrucciones": p.instrucciones, "preguntas": p.preguntas,
            "categoria": "Pruebas del despacho", "activa": p.activa}


def nueva_aplicacion(db: Session, c: m.BtCandidato, clave: str, nombre: str, usuario_id: int) -> tuple[m.BtAplicacion, str]:
    token = secrets.token_urlsafe(24)
    a = m.BtAplicacion(organizacion_id=c.organizacion_id, candidato_id=c.id, prueba=clave, nombre_prueba=nombre[:150], token_hash=huella(token),
                       vence_en=datetime.now(timezone.utc) + timedelta(days=DIAS_PRUEBA), enviada_por_id=usuario_id)
    db.add(a)
    db.flush()
    return a, token


def enlace_prueba(token: str) -> str:
    return f"{ajustes().url_publica.rstrip('/')}/prueba/{token}"


def enlace_vacante(v: m.BtVacante) -> str:
    return f"{ajustes().url_publica.rstrip('/')}/empleos/{v.codigo}"
