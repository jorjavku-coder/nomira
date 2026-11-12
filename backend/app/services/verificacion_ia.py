"""Verificación opcional con IA: una segunda lectura independiente de cada recibo que se COMPARA con
la lectura del sistema. La IA no modifica importes, no decide claves autorizadas y no suma: solo
señala diferencias para que una persona las revise contra el original."""
from __future__ import annotations

import logging
from collections import Counter
from decimal import Decimal

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from ..config import ajustes
from ..db import SessionLocal
from . import ia_adaptador
from .calculo import dinero

log = logging.getLogger("quincena.ia")


def huella_filas(filas) -> str:
    """Identifica el estado de las percepciones al verificar (si luego se corrigen, la verificación caduca)."""
    return "|".join(sorted(f"{f.clave}={dinero(f.importe)}" for f in filas if f.tipo == "percepcion"))


def comparar(filas_sistema: list[tuple[str | None, Decimal | None]], lectura: ia_adaptador.LecturaIA | None,
             total_sistema: Decimal | None = None) -> tuple[str, list[str]]:
    """Devuelve (estado, diferencias). estado: coincide | discrepancia | no_legible."""
    if lectura is None or not lectura.legible:
        return "no_legible", ["La IA no pudo leer el recibo con certeza."]
    sistema = Counter((c or "¿?", dinero(i) or "ilegible") for c, i in filas_sistema)
    ia = Counter((f.clave, f.importe or "ilegible") for f in lectura.percepciones)
    difs = []
    for (clave, imp), n in sorted((sistema - ia).items()):
        otros = [i for (c, i) in ia if c == clave and (c, i) not in sistema]
        if otros:
            difs.append(f"Clave {clave}: el sistema leyó {imp} y la IA leyó {otros[0]}.")
        else:
            difs.append(f"Clave {clave} ({imp}): la IA no la encontró en el recibo.")
    claves_con_dif = {d.split()[1].rstrip(":") for d in difs}
    for (clave, imp), n in sorted((ia - sistema).items()):
        if clave not in claves_con_dif:
            difs.append(f"Clave {clave} ({imp}): la IA la ve en el recibo y el sistema no la leyó.")
    if lectura.total_percepciones and total_sistema is not None and Decimal(lectura.total_percepciones) != total_sistema:
        difs.append(f"Total de percepciones: el sistema leyó {dinero(total_sistema)} y la IA leyó {lectura.total_percepciones}.")
    return ("discrepancia" if difs else "coincide"), difs


def verificar_expediente(db: Session, expediente_id: int, cliente=None) -> dict:
    exp = db.get(m.Expediente, expediente_id)
    recibos = db.scalars(select(m.Recibo).where(m.Recibo.expediente_id == expediente_id)
                         .options(selectinload(m.Recibo.filas), selectinload(m.Recibo.documento))
                         .order_by(m.Recibo.documento_id, m.Recibo.pagina_numero)).all()
    avance = {"estado": "en_curso", "total": len(recibos), "hechos": 0, "modelo": ajustes().ia_modelo,
              "inicio": m.ahora().isoformat(), "error": None}
    exp.verificacion_ia = dict(avance)
    db.commit()
    fallos_seguidos = 0
    try:
        cliente = cliente or ia_adaptador.crear_cliente()
        for r in recibos:
            actual = huella_filas(r.filas)
            previa = r.verificacion_ia or {}
            if previa.get("huella") == actual and previa.get("estado") in ("coincide", "discrepancia"):
                avance["hechos"] += 1  # ya verificado y sin cambios: no se vuelve a enviar
                continue
            try:
                with pymupdf.open(r.documento.ruta) as pdf:
                    png = pdf[r.pagina_numero - 1].get_pixmap(dpi=130).tobytes("png")
                lectura = ia_adaptador.leer_recibo_imagen(png, cliente)
                estado, difs = comparar([(f.clave, f.importe) for f in r.filas if f.tipo == "percepcion"],
                                        lectura, r.total_percepciones)
                fallos_seguidos = 0
            except Exception as e:
                estado, difs = "error", [f"No se pudo consultar a la IA ({type(e).__name__})."]
                fallos_seguidos += 1
                log.warning("Verificación IA falló en recibo %s: %s", r.id, type(e).__name__)
            r.verificacion_ia = {"estado": estado, "diferencias": difs, "huella": actual,
                                 "modelo": ajustes().ia_modelo, "fecha": m.ahora().isoformat()}
            avance["hechos"] += 1
            exp.verificacion_ia = dict(avance)
            db.commit()
            if fallos_seguidos >= 3:
                raise RuntimeError("La IA falló en 3 recibos seguidos; se detuvo la verificación. "
                                   "Revise la clave de API y el modelo configurados.")
        avance["estado"] = "terminada"
    except Exception as e:
        avance["estado"] = "error"
        avance["error"] = str(e)[:300] if isinstance(e, RuntimeError) else f"No se pudo iniciar la IA ({type(e).__name__})."
    avance["fin"] = m.ahora().isoformat()
    exp.verificacion_ia = dict(avance)
    db.commit()
    return avance


def verificar_en_segundo_plano(expediente_id: int) -> None:
    with SessionLocal() as db:
        verificar_expediente(db, expediente_id)


def resumen(recibos: list[m.Recibo], exp: m.Expediente) -> tuple[dict, dict, list[dict]]:
    """(resumen del expediente, estado por recibo, alertas) para integrarlo al resultado."""
    por_recibo, alertas = {}, []
    cuenta = Counter()
    for r in recibos:
        v = r.verificacion_ia
        if not v:
            estado = "sin_verificar"
        elif v.get("huella") != huella_filas(r.filas):
            estado = "desactualizada"  # la lectura cambió después de verificar
        else:
            estado = v["estado"]
        cuenta[estado] += 1
        por_recibo[r.id] = {"estado": estado, "diferencias": (v or {}).get("diferencias", []) if estado != "desactualizada" else [],
                            "fecha": (v or {}).get("fecha")}
        if estado in ("discrepancia", "no_legible") and r.decision is None:
            alertas.append({"tipo": "verificacion_ia", "bloqueante": True, "recibo_id": r.id,
                            "documento_id": r.documento_id, "pagina": r.pagina_numero,
                            "mensaje": "La verificación con IA no coincide con la lectura del sistema: "
                                       + " ".join(v["diferencias"][:3]) + " Revise el original y corrija o confirme el recibo."})
    return ({"habilitada": ajustes().ia_habilitada, "avance": exp.verificacion_ia, "recibos": dict(cuenta)},
            por_recibo, alertas)
