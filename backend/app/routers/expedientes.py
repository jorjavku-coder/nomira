from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, obtener, puede_editar, usuario_actual
from ..services import exportar
from ..services.calculo import periodo_alineado, quincenas_esperadas
from ..services.procesamiento import invalidar_validacion, recalcular_estado
from ..services.resultados import calcular_expediente, resultado_completo, trazabilidad
from .documentos import PRIVADO, expediente_editable

router = APIRouter(prefix="/api", tags=["expedientes y revisión"])


class ExpedienteNuevo(BaseModel):
    trabajador_nombre: str = Field(min_length=2, max_length=200)
    identificador_laboral: str | None = Field(None, max_length=40)
    periodo_inicio: date
    periodo_fin: date
    quincenas_esperadas: int | None = Field(None, ge=1, le=600)
    catalogo_version_id: int


class ExpedienteCambio(BaseModel):
    trabajador_nombre: str | None = Field(None, min_length=2, max_length=200)
    identificador_laboral: str | None = Field(None, max_length=40)
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    quincenas_esperadas: int | None = Field(None, ge=1, le=600)
    catalogo_version_id: int | None = None
    decision_plazas: str | None = None


class Motivo(BaseModel):
    motivo: str = Field(min_length=3, max_length=1000)


class CorreccionFila(Motivo):
    clave: str | None = Field(None, max_length=40)
    concepto: str | None = Field(None, max_length=300)
    importe: str | None = Field(None, max_length=30)  # texto decimal; nunca float


class FilaManual(Motivo):
    tipo: str = "percepcion"
    clave: str = Field(min_length=1, max_length=40)
    concepto: str | None = Field(None, max_length=300)
    importe: str = Field(max_length=30)


class CorreccionRecibo(Motivo):
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    plaza: str | None = Field(None, max_length=60)
    num_recibo: str | None = Field(None, max_length=40)
    trabajador_nombre: str | None = Field(None, max_length=200)
    clave_servidor: str | None = Field(None, max_length=40)


class Decision(Motivo):
    decision: str | None  # incluir | excluir | None (revertir)


class Validacion(BaseModel):
    acepta_faltantes: bool = False
    notas: str | None = Field(None, max_length=2000)


def _importe(txt: str) -> Decimal:
    t = txt.strip().replace("$", "").replace(",", "").replace(" ", "")
    try:
        v = Decimal(t)
    except InvalidOperation:
        raise HTTPException(422, "Importe inválido. Use el formato 1234.56")
    if not v.is_finite() or v.as_tuple().exponent < -2 or abs(v) >= Decimal("1e12"):
        raise HTTPException(422, "El importe admite como máximo 2 decimales.")
    return v.quantize(Decimal("0.01"))


def _version_activa(db: Session, vid: int, u: m.Usuario) -> m.CatalogoVersion:
    v = obtener(db, m.CatalogoVersion, vid, u)
    if v.estado != "activo":
        raise HTTPException(409, "Solo puede seleccionarse una versión de catálogo validada y activa.")
    return v


def _periodo(ini: date, fin: date):
    if not periodo_alineado(ini, fin):
        raise HTTPException(422, "El periodo debe iniciar el día 1 o 16 y terminar el día 15 o fin de mes.")


def _exp(db: Session, e: m.Expediente, con_resumen=True) -> dict:
    v = e.catalogo_version
    d = {"id": e.id, "trabajador_nombre": e.trabajador_nombre, "identificador_laboral": e.identificador_laboral,
         "periodo_inicio": e.periodo_inicio.isoformat(), "periodo_fin": e.periodo_fin.isoformat(),
         "quincenas_esperadas": e.quincenas_esperadas, "estado": e.estado, "decision_plazas": e.decision_plazas,
         "catalogo": {"version_id": v.id, "nombre": v.catalogo.nombre, "version": v.numero, "estado": v.estado},
         "documentos": len(e.documentos), "creado_en": e.creado_en.isoformat(),
         "actualizado_en": e.actualizado_en.isoformat(),
         "validado_en": e.validado_en.isoformat() if e.validado_en else None}
    if con_resumen:
        res = calcular_expediente(db, e)
        d["resumen"] = res["resumen"]
        d["total_expediente"] = res["total_expediente"]
        d["provisional"] = res["provisional"]
    return d


def _recibo_editable(db: Session, rid: int, u: m.Usuario) -> tuple[m.Recibo, m.Expediente]:
    r = obtener(db, m.Recibo, rid, u)
    return r, expediente_editable(db, r.expediente_id, u)


def _ref(r: m.Recibo, f: m.Fila | None = None) -> dict:
    ref = {"documento": r.documento.nombre_original, "documento_id": r.documento_id, "pagina": r.pagina_numero}
    if f is not None:
        ref.update(tipo=f.tipo, clave_leida=f.clave_leida, importe_leido=f.importe_leido_texto)
    return ref


def _registrar(db, u, exp, r, f, entidad, campo, antes, despues, motivo):
    db.add(m.Correccion(
        organizacion_id=u.organizacion_id, expediente_id=exp.id, recibo_id=r.id, fila_id=f.id if f else None,
        entidad=entidad, campo=campo, valor_anterior=None if antes is None else str(antes),
        valor_nuevo=None if despues is None else str(despues), motivo=motivo, usuario_id=u.id,
        usuario_email=u.email, referencia=_ref(r, f)))


# ---------- expedientes ----------

@router.get("/expedientes")
def listar(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    exps = db.scalars(select(m.Expediente).where(m.Expediente.organizacion_id == u.organizacion_id)
                      .order_by(m.Expediente.actualizado_en.desc()))
    return [_exp(db, e) for e in exps]


@router.post("/expedientes", status_code=201)
def crear(d: ExpedienteNuevo, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    _periodo(d.periodo_inicio, d.periodo_fin)
    v = _version_activa(db, d.catalogo_version_id, u)
    n = len(quincenas_esperadas(d.periodo_inicio, d.periodo_fin))
    e = m.Expediente(organizacion_id=u.organizacion_id, trabajador_nombre=d.trabajador_nombre.strip(),
                     identificador_laboral=(d.identificador_laboral or "").strip() or None,
                     periodo_inicio=d.periodo_inicio, periodo_fin=d.periodo_fin,
                     quincenas_esperadas=d.quincenas_esperadas or n, catalogo_version_id=v.id, creado_por_id=u.id)
    db.add(e)
    db.flush()
    auditar(db, u, "expediente_creado", "expediente", e.id, {"catalogo_version_id": v.id}, request)
    db.commit()
    return _exp(db, e)


@router.get("/expedientes/{eid}")
def ver(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _exp(db, obtener(db, m.Expediente, eid, u))


@router.patch("/expedientes/{eid}")
def cambiar(eid: int, d: ExpedienteCambio, request: Request, u: m.Usuario = Depends(puede_editar),
            db: Session = Depends(get_db)):
    e = expediente_editable(db, eid, u)
    datos = d.model_dump(exclude_unset=True)
    cambios = {}
    if "catalogo_version_id" in datos and datos["catalogo_version_id"] != e.catalogo_version_id:
        v = _version_activa(db, datos["catalogo_version_id"], u)
        cambios["catalogo_version_id"] = [e.catalogo_version_id, v.id]
        e.catalogo_version_id = v.id
    if "decision_plazas" in datos:
        if datos["decision_plazas"] not in (None, "consolidar", "separar"):
            raise HTTPException(422, "decision_plazas debe ser «consolidar» o «separar».")
        cambios["decision_plazas"] = [e.decision_plazas, datos["decision_plazas"]]
        e.decision_plazas = datos["decision_plazas"]
    ini, fin = datos.get("periodo_inicio") or e.periodo_inicio, datos.get("periodo_fin") or e.periodo_fin
    if (ini, fin) != (e.periodo_inicio, e.periodo_fin):
        _periodo(ini, fin)
        cambios["periodo"] = [f"{e.periodo_inicio}/{e.periodo_fin}", f"{ini}/{fin}"]
        e.periodo_inicio, e.periodo_fin = ini, fin
    for campo in ("trabajador_nombre", "identificador_laboral", "quincenas_esperadas"):
        if campo in datos and datos[campo] != getattr(e, campo):
            if campo != "identificador_laboral" and datos[campo] is None:
                continue
            cambios[campo] = True
            setattr(e, campo, datos[campo] or None)
    auditar(db, u, "expediente_modificado", "expediente", e.id, cambios, request)
    db.commit()
    db.refresh(e)
    return _exp(db, e)


@router.get("/expedientes/{eid}/resultado")
def resultado(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return resultado_completo(db, obtener(db, m.Expediente, eid, u))


@router.get("/expedientes/{eid}/recibos")
def recibos(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    e = obtener(db, m.Expediente, eid, u)
    rs = db.scalars(select(m.Recibo).where(m.Recibo.expediente_id == e.id)
                    .order_by(m.Recibo.periodo_inicio.nulls_last(), m.Recibo.documento_id, m.Recibo.pagina_numero))
    return [_recibo(r) for r in rs]


def _recibo(r: m.Recibo) -> dict:
    return {
        "id": r.id, "documento_id": r.documento_id, "documento": r.documento.nombre_original,
        "pagina": r.pagina_numero, "num_recibo": r.num_recibo, "trabajador_nombre": r.trabajador_nombre,
        "clave_servidor": r.clave_servidor, "plaza": r.plaza, "periodo_texto": r.periodo_texto,
        "periodo_inicio": r.periodo_inicio.isoformat() if r.periodo_inicio else None,
        "periodo_fin": r.periodo_fin.isoformat() if r.periodo_fin else None,
        "total_percepciones": None if r.total_percepciones is None else str(r.total_percepciones),
        "total_deducciones": None if r.total_deducciones is None else str(r.total_deducciones),
        "total_neto": None if r.total_neto is None else str(r.total_neto),
        "decision": r.decision, "decision_motivo": r.decision_motivo,
        "filas": [{"id": f.id, "tipo": f.tipo, "orden": f.orden, "origen": f.origen, "clave": f.clave,
                   "concepto": f.concepto, "importe": None if f.importe is None else str(f.importe),
                   "clave_leida": f.clave_leida, "concepto_leido": f.concepto_leido,
                   "importe_leido_texto": f.importe_leido_texto, "confianza": f.confianza, "bbox": f.bbox,
                   "corregida": f.corregida, "confirmada": f.confirmada} for f in r.filas]}


@router.get("/recibos/{rid}")
def ver_recibo(rid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _recibo(obtener(db, m.Recibo, rid, u))


# ---------- revisión ----------

@router.post("/filas/{fid}/corregir")
def corregir_fila(fid: int, d: CorreccionFila, request: Request, u: m.Usuario = Depends(puede_editar),
                  db: Session = Depends(get_db)):
    """Corrige la LECTURA de una fila. No toca el catálogo: si la clave corregida no está
    autorizada, la fila simplemente queda excluida."""
    f = db.get(m.Fila, fid)
    if not f:
        raise HTTPException(404, "No encontrado.")
    r, exp = _recibo_editable(db, f.recibo_id, u)
    datos = d.model_dump(exclude_unset=True)
    hubo = False
    if "clave" in datos and datos["clave"] is not None and datos["clave"].strip() != (f.clave or ""):
        _registrar(db, u, exp, r, f, "fila", "clave", f.clave, datos["clave"].strip(), d.motivo)
        f.clave, hubo = datos["clave"].strip(), True
    if "concepto" in datos and (datos["concepto"] or None) != f.concepto:
        _registrar(db, u, exp, r, f, "fila", "concepto", f.concepto, datos["concepto"] or None, d.motivo)
        f.concepto, hubo = datos["concepto"] or None, True
    if "importe" in datos and datos["importe"] is not None:
        nuevo = _importe(datos["importe"])
        if nuevo != f.importe:
            _registrar(db, u, exp, r, f, "fila", "importe", f.importe, nuevo, d.motivo)
            f.importe, hubo = nuevo, True
    if not hubo:
        raise HTTPException(422, "No hay cambios que registrar.")
    f.corregida = True
    f.confirmada = False
    auditar(db, u, "fila_corregida", "fila", f.id, {"expediente_id": exp.id}, request)
    db.commit()
    return _recibo(r)


@router.post("/filas/{fid}/confirmar")
def confirmar_fila(fid: int, d: Motivo, request: Request, u: m.Usuario = Depends(puede_editar),
                   db: Session = Depends(get_db)):
    """Confirma, tras ver el original, una lectura dudosa o un importe negativo."""
    f = db.get(m.Fila, fid)
    if not f:
        raise HTTPException(404, "No encontrado.")
    r, exp = _recibo_editable(db, f.recibo_id, u)
    if f.importe is None or not f.clave:
        raise HTTPException(409, "No puede confirmarse una fila sin clave o sin importe: corríjala.")
    _registrar(db, u, exp, r, f, "fila", "confirmacion", "sin confirmar", "confirmada", d.motivo)
    f.confirmada = True
    auditar(db, u, "fila_confirmada", "fila", f.id, {"expediente_id": exp.id}, request)
    db.commit()
    return _recibo(r)


@router.post("/recibos/{rid}/filas", status_code=201)
def agregar_fila(rid: int, d: FilaManual, request: Request, u: m.Usuario = Depends(puede_editar),
                 db: Session = Depends(get_db)):
    r, exp = _recibo_editable(db, rid, u)
    if d.tipo not in ("percepcion", "deduccion"):
        raise HTTPException(422, "Tipo inválido.")
    orden = (db.scalar(select(func.max(m.Fila.orden)).where(m.Fila.recibo_id == r.id, m.Fila.tipo == d.tipo)) or 0) + 1
    f = m.Fila(recibo_id=r.id, tipo=d.tipo, orden=orden, origen="manual", clave=d.clave.strip(),
               concepto=d.concepto or None, importe=_importe(d.importe), corregida=True)
    db.add(f)
    db.flush()
    _registrar(db, u, exp, r, f, "fila", "fila_agregada", None, f"{f.clave} · {f.importe}", d.motivo)
    auditar(db, u, "fila_agregada", "fila", f.id, {"expediente_id": exp.id}, request)
    db.commit()
    db.refresh(r)
    return _recibo(r)


@router.post("/recibos/{rid}/corregir")
def corregir_recibo(rid: int, d: CorreccionRecibo, request: Request, u: m.Usuario = Depends(puede_editar),
                    db: Session = Depends(get_db)):
    r, exp = _recibo_editable(db, rid, u)
    datos = d.model_dump(exclude_unset=True, exclude={"motivo"})
    hubo = False
    for campo, valor in datos.items():
        if valor is None or valor == getattr(r, campo):
            continue
        if isinstance(valor, str):
            valor = valor.strip()
        _registrar(db, u, exp, r, None, "recibo", campo, getattr(r, campo), valor, d.motivo)
        setattr(r, campo, valor)
        hubo = True
    if not hubo:
        raise HTTPException(422, "No hay cambios que registrar.")
    if r.periodo_inicio and r.periodo_fin and r.periodo_fin < r.periodo_inicio:
        raise HTTPException(422, "El periodo final es anterior al inicial.")
    auditar(db, u, "recibo_corregido", "recibo", r.id, {"expediente_id": exp.id, "campos": list(datos)}, request)
    db.commit()
    return _recibo(r)


@router.post("/recibos/{rid}/decision")
def decidir(rid: int, d: Decision, request: Request, u: m.Usuario = Depends(puede_editar),
            db: Session = Depends(get_db)):
    """Resuelve duplicados, complementarios, descuadres o recibos de otro trabajador."""
    r, exp = _recibo_editable(db, rid, u)
    if d.decision not in (None, "incluir", "excluir"):
        raise HTTPException(422, "Decisión inválida.")
    _registrar(db, u, exp, r, None, "recibo", "decision", r.decision, d.decision, d.motivo)
    r.decision, r.decision_motivo = d.decision, d.motivo
    r.decision_por_id, r.decision_en = u.id, m.ahora()
    auditar(db, u, "recibo_decision", "recibo", r.id, {"expediente_id": exp.id, "decision": d.decision}, request)
    db.commit()
    return _recibo(r)


@router.get("/expedientes/{eid}/correcciones")
def correcciones(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return trazabilidad(db, obtener(db, m.Expediente, eid, u))


# ---------- validación ----------

@router.post("/expedientes/{eid}/validar")
def validar(eid: int, d: Validacion, request: Request, u: m.Usuario = Depends(puede_editar),
            db: Session = Depends(get_db)):
    e = expediente_editable(db, eid, u)
    res = resultado_completo(db, e)
    bloqueos = [a for a in res["alertas"] if a["bloqueante"]]
    if bloqueos:
        raise HTTPException(409, {"mensaje": f"No puede validarse: hay {len(bloqueos)} pendiente(s) por resolver.",
                                  "pendientes": bloqueos[:50]})
    if res["faltantes"] and not d.acepta_faltantes:
        raise HTTPException(409, {"mensaje": f"Hay {len(res['faltantes'])} quincena(s) sin comprobante. Para validar "
                                             "debe reconocerlo de forma explícita; no se les asignará importe.",
                                  "faltantes": res["faltantes"]})
    ahora = m.ahora()
    res["provisional"] = False
    res["puede_validarse"] = False
    res["estado_validacion"] = {"validado": True, "por": u.email, "fecha": ahora.isoformat(), "notas": d.notas,
                                "faltantes_reconocidas": len(res["faltantes"])}
    e.resultado_validado = res  # instantánea congelada: cambios posteriores no la alteran
    e.estado, e.validado_por_id, e.validado_en, e.notas_validacion = "validado", u.id, ahora, d.notas
    auditar(db, u, "expediente_validado", "expediente", e.id,
            {"total": res["total_expediente"], "catalogo_version_id": e.catalogo_version_id,
             "faltantes": len(res["faltantes"])}, request)
    db.commit()
    return res


@router.post("/expedientes/{eid}/reabrir")
def reabrir(eid: int, d: Motivo, request: Request, u: m.Usuario = Depends(puede_editar),
            db: Session = Depends(get_db)):
    e = obtener(db, m.Expediente, eid, u)
    if not invalidar_validacion(e):
        raise HTTPException(409, "El expediente no está validado.")
    recalcular_estado(db, e)
    auditar(db, u, "expediente_reabierto", "expediente", e.id, {"motivo": d.motivo}, request)
    db.commit()
    return _exp(db, e)


# ---------- exportación ----------

def _exportar(eid, formato, request, u, db):
    e = obtener(db, m.Expediente, eid, u)
    res = resultado_completo(db, e)
    auditar(db, u, f"exportacion_{formato}", "expediente", e.id, {"validado": res["estado_validacion"]["validado"]}, request)
    db.commit()
    sufijo = "validado" if res["estado_validacion"]["validado"] else "PROVISIONAL"
    if formato == "excel":
        cuerpo, tipo, ext = (exportar.generar_excel(res),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx")
    else:
        cuerpo, tipo, ext = exportar.generar_pdf(res), "application/pdf", "pdf"
    return Response(cuerpo, media_type=tipo, headers={
        **PRIVADO, "Content-Disposition": f'attachment; filename="expediente-{e.id}-{sufijo}.{ext}"',
        "Access-Control-Expose-Headers": "Content-Disposition"})


@router.get("/expedientes/{eid}/exportar/excel")
def exportar_excel(eid: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _exportar(eid, "excel", request, u, db)


@router.get("/expedientes/{eid}/exportar/pdf")
def exportar_pdf(eid: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _exportar(eid, "pdf", request, u, db)
