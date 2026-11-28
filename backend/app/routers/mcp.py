"""Conector de Nomira para Claude y otros asistentes compatibles con MCP (Model Context Protocol).

Servidor MCP público y sin sesión (transporte «Streamable HTTP», respuestas JSON) en POST /api/mcp
(y nomirasoft.com/mcp). Fase 1: solo herramientas de consulta que no tocan datos de ningún despacho:
- buscar_tesis / ver_tesis: biblioteca de tesis del Semanario Judicial de la Federación de Nomira.
- calcular_finiquito: el mismo motor de la calculadora de liquidaciones (LFT), con operación y fundamento.
- calcular_plazo: días hábiles con el calendario base (fines de semana y art. 74 LFT) más los inhábiles que se indiquen.
Nada de lo que se consulta se guarda; solo se cuentan llamadas por herramienta (sin contenido) en el registro.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..freno import Ventana
from ..services.agenda import dias as plazos
from ..services.agenda.base import hoy
from ..services.liquidacion import motor
from ..services.tesis import base as tb
from .liquidaciones import DatosIn, _motor

router = APIRouter(tags=["Conector MCP"])
log = logging.getLogger("quincena.mcp")
_llamadas_ip = Ventana(120, 600)

VERSIONES = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCCIONES = (
    "Nomira es software para despachos jurídicos en México. Estas herramientas consultan su biblioteca de tesis del "
    "Semanario Judicial de la Federación (SJF), calculan finiquitos y liquidaciones con la Ley Federal del Trabajo y cuentan "
    "plazos en días hábiles. Al citar una tesis, indique su registro digital, su rubro y su enlace oficial al SJF. La biblioteca "
    "de Nomira puede no estar completa: si no encuentra una tesis, dígalo y sugiera consultar el SJF. Los cálculos son "
    "asistidos y deben revisarse por un abogado. Más herramientas para despachos en https://nomirasoft.com.")

SOLO_LECTURA = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
HERRAMIENTAS = [
    {"name": "buscar_tesis", "title": "Buscar tesis del SJF",
     "description": "Busca tesis aisladas y jurisprudencias del Semanario Judicial de la Federación en la biblioteca de Nomira, por palabras "
                    "o por registro digital. Devuelve registro, rubro, clave, tipo, época, instancia, materias, año, un extracto y el enlace oficial.",
     "inputSchema": {"type": "object", "properties": {
         "consulta": {"type": "string", "description": "Palabras clave (p. ej. «litisconsorcio pasivo necesario») o un registro digital."},
         "tipo": {"type": "string", "enum": ["jurisprudencia", "aislada"], "description": "Solo jurisprudencia o solo tesis aisladas."},
         "materia": {"type": "string", "description": "Materia, p. ej. Civil, Laboral, Penal, Administrativa, Constitucional, Común."},
         "anio_desde": {"type": "integer"}, "anio_hasta": {"type": "integer"},
         "limite": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5}},
         "required": ["consulta"]}, "annotations": SOLO_LECTURA},
    {"name": "ver_tesis", "title": "Ver tesis completa",
     "description": "Texto completo de una tesis del SJF por su registro digital, con precedentes y enlace oficial.",
     "inputSchema": {"type": "object", "properties": {"registro": {"type": "integer", "description": "Registro digital de la tesis."}},
                     "required": ["registro"]}, "annotations": SOLO_LECTURA},
    {"name": "calcular_finiquito", "title": "Calcular finiquito o liquidación (LFT)",
     "description": "Calcula finiquito y, según la causa, indemnización, prima de antigüedad y salarios caídos conforme a la Ley Federal "
                    "del Trabajo, con la operación y el fundamento de cada concepto. Montos en pesos mexicanos.",
     "inputSchema": {"type": "object", "properties": {
         "fecha_ingreso": {"type": "string", "format": "date", "description": "AAAA-MM-DD"},
         "fecha_baja": {"type": "string", "format": "date", "description": "AAAA-MM-DD"},
         "causa": {"type": "string", "enum": list(motor.CAUSAS), "description": "; ".join(f"{k}: {v}" for k, v in motor.CAUSAS.items())},
         "salario_diario": {"type": "number", "exclusiveMinimum": 0},
         "salario_integrado": {"type": "number", "description": "Opcional; si no se da, se calcula con las prestaciones mínimas de ley."},
         "aguinaldo_dias": {"type": "number", "minimum": 15, "default": 15},
         "prima_vacacional_pct": {"type": "number", "minimum": 25, "default": 25},
         "dias_pendientes_pago": {"type": "number", "minimum": 0, "default": 0, "description": "Días trabajados no pagados."},
         "vacaciones_tomadas_actual": {"type": "number", "minimum": 0, "default": 0, "description": "Días de vacaciones ya disfrutados en el año en curso."},
         "zona": {"type": "string", "enum": ["general", "frontera"], "default": "general"}},
         "required": ["fecha_ingreso", "fecha_baja", "causa", "salario_diario"]}, "annotations": SOLO_LECTURA},
    {"name": "calcular_plazo", "title": "Calcular plazo en días hábiles",
     "description": "Cuenta un plazo a partir de una notificación: cuándo surte efectos, primer día y vencimiento, con los días que se "
                    "saltaron y por qué. Calendario base: sábados, domingos y descansos del art. 74 LFT; agregue los días que el "
                    "tribunal declaró inhábiles en «inhabiles».",
     "inputSchema": {"type": "object", "properties": {
         "fecha_notificacion": {"type": "string", "format": "date", "description": "AAAA-MM-DD"},
         "dias": {"type": "integer", "minimum": 1, "maximum": plazos.MAX_DIAS},
         "tipo_dias": {"type": "string", "enum": list(plazos.TIPOS_DIAS), "default": "habiles"},
         "surte_efectos": {"type": "string", "enum": list(plazos.SURTE_EFECTOS), "default": "dia_habil_siguiente",
                           "description": "; ".join(f"{k}: {v}" for k, v in plazos.SURTE_EFECTOS.items())},
         "inhabiles": {"type": "array", "items": {"type": "string", "format": "date"}, "maxItems": 120,
                       "description": "Días inhábiles adicionales del tribunal (vacaciones, suspensiones), AAAA-MM-DD."}},
         "required": ["fecha_notificacion", "dias"]}, "annotations": SOLO_LECTURA},
]


class ErrorHerramienta(Exception):
    """Error que se le explica al asistente (isError: true), no un error del protocolo."""


def _pesos(v) -> str:
    return f"${Decimal(str(v)):,.2f}"


def _buscar_tesis(db: Session, a: dict) -> tuple[str, dict]:
    consulta = str(a.get("consulta") or "").strip()
    if not consulta:
        raise ErrorHerramienta("Indique qué buscar.")
    limite = max(1, min(int(a.get("limite") or 5), 10))
    filas, n = tb.buscar(db, consulta, a.get("tipo"), None, None, limite=limite, cualquiera=True, materia=a.get("materia"),
                         anio_desde=a.get("anio_desde"), anio_hasta=a.get("anio_hasta"))
    res = [tb.a_dict(t, completo=False) for t in filas]
    if not res:
        return (f"No encontré tesis para «{consulta}» en la biblioteca de Nomira ({tb.total(db):,} tesis). Puede no estar completa: "
                "consulte también https://sjf2.scjn.gob.mx.", {"resultados": [], "total": 0})
    lineas = [f"{len(res)} de {n} tesis para «{consulta}» (biblioteca de Nomira):"]
    for t in res:
        lineas.append(f"\n— Registro digital {t['registro']} · {t['tipo'] or 'tesis'} · {t['clave'] or 's/clave'} · {t['instancia'] or ''} · "
                      f"{t['epoca'] or ''} · {t['anio'] or ''}\n  {t['rubro']}\n  Extracto: {t['extracto']}…\n  {t['enlace']}")
    return "\n".join(lineas), {"resultados": res, "total": n}


def _ver_tesis(db: Session, a: dict) -> tuple[str, dict]:
    try:
        registro = int(a.get("registro"))
    except (TypeError, ValueError):
        raise ErrorHerramienta("Indique el registro digital (número).")
    t = db.get(m.JTesis, registro)
    if not t:
        raise ErrorHerramienta(f"La tesis {registro} no está en la biblioteca de Nomira. Consúltela en https://sjf2.scjn.gob.mx.")
    d = tb.a_dict(t)
    texto = (f"Registro digital {d['registro']} · {d['tipo'] or ''} · {d['clave'] or ''}\n{d['instancia'] or ''} · {d['epoca'] or ''} · "
             f"Materia(s): {d['materias'] or ''}\n\n{d['rubro']}\n\n{d['texto'] or ''}\n\n{d['precedentes'] or ''}\n\nFuente: {d['fuente'] or 'SJF'} · {d['enlace']}")
    return texto, {k: v for k, v in d.items() if k not in ("huella_oficial", "origen")}


def _finiquito(db: Session, a: dict) -> tuple[str, dict]:
    campos = ("fecha_ingreso", "fecha_baja", "causa", "salario_diario", "salario_integrado", "aguinaldo_dias", "prima_vacacional_pct",
              "dias_pendientes_pago", "vacaciones_tomadas_actual", "zona")
    try:
        datos = DatosIn(**{k: a[k] for k in campos if a.get(k) is not None})
        r = motor.calcular(_motor(datos), hoy())
    except ValidationError as e:
        raise ErrorHerramienta("Datos inválidos: " + "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:5]))
    except ValueError as e:
        raise ErrorHerramienta(str(e))
    ant = r["antiguedad"]
    lineas = [f"{r['causa_nombre']} · antigüedad {ant['anios_completos']} años y {ant['dias_ultimo_anio']} días · salario diario "
              f"{_pesos(r['salarios']['diario'])}, integrado {_pesos(r['salarios']['integrado'])}"]
    for s in r["secciones"]:
        lineas.append(f"\n{s['titulo']}:")
        for c in s["conceptos"]:
            lineas.append(f"• {c['concepto']}: {_pesos(c['importe'])} = {c['operacion']} ({c['fundamento']})")
        lineas.append(f"  Subtotal: {_pesos(s['subtotal'])}")
    lineas.append(f"\nTOTAL: {_pesos(r['total'])}")
    for x in r.get("avisos") or []:
        lineas.append(f"Nota: {x}")
    lineas.append("\nCálculo asistido de Nomira (calculadora gratuita: https://nomirasoft.com/calculadora-finiquito). Revíselo un abogado; "
                  "no incluye impuestos ni cuotas.")
    return "\n".join(lineas), json.loads(json.dumps(r, default=str))


def _plazo(db: Session, a: dict) -> tuple[str, dict]:
    try:
        notif = date.fromisoformat(str(a.get("fecha_notificacion")))
        inhabiles = {date.fromisoformat(str(x)): "Inhábil indicado por el usuario" for x in (a.get("inhabiles") or [])[:120]}
        dias = int(a.get("dias"))
    except (TypeError, ValueError):
        raise ErrorHerramienta("Fechas en formato AAAA-MM-DD y días como número entero.")
    cal = plazos.Calendario(nombre="Base: sábados, domingos y art. 74 LFT" + (" + inhábiles indicados" if inhabiles else ""), inhabiles=inhabiles)
    try:
        r = plazos.calcular(cal, notif, dias, a.get("tipo_dias") or "habiles", a.get("surte_efectos") or "dia_habil_siguiente")
    except ValueError as e:
        raise ErrorHerramienta(str(e))
    saltados = "; ".join(f"{s['fecha']} ({s['motivo']})" for s in r["saltados"][:40]) or "ninguno"
    texto = ("\n".join(r["pasos"]) + f"\nDías inhábiles saltados: {saltados}\nCalendario: {r['calendario']}.\n"
             "Importante: no incluye vacaciones ni días que el tribunal declare inhábiles salvo los que se indicaron; "
             "verifique el calendario oficial del órgano. " + r["aviso"])
    return texto, r


EJECUTAR = {"buscar_tesis": _buscar_tesis, "ver_tesis": _ver_tesis, "calcular_finiquito": _finiquito, "calcular_plazo": _plazo}


def _resp(id_, resultado=None, error=None) -> dict:
    d = {"jsonrpc": "2.0", "id": id_}
    if error:
        d["error"] = error
    else:
        d["result"] = resultado
    return d


def _atender(db: Session, msg: dict) -> dict | None:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _resp(msg.get("id") if isinstance(msg, dict) else None, error={"code": -32600, "message": "Solicitud inválida."})
    metodo, id_, p = msg["method"], msg.get("id"), msg.get("params") or {}
    if id_ is None:  # notificación (p. ej. notifications/initialized): sin respuesta
        return None
    if metodo == "initialize":
        pedida = p.get("protocolVersion")
        return _resp(id_, {"protocolVersion": pedida if pedida in VERSIONES else VERSIONES[0],
                           "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "nomira", "title": "Nomira — derecho mexicano", "version": "1.0.0"},
                           "instructions": INSTRUCCIONES})
    if metodo == "ping":
        return _resp(id_, {})
    if metodo == "tools/list":
        return _resp(id_, {"tools": HERRAMIENTAS})
    if metodo == "tools/call":
        nombre = p.get("name")
        f = EJECUTAR.get(nombre)
        if not f:
            return _resp(id_, error={"code": -32602, "message": f"Herramienta desconocida: {nombre}"})
        args = p.get("arguments") or {}
        if not isinstance(args, dict):
            return _resp(id_, error={"code": -32602, "message": "Los argumentos deben ser un objeto."})
        log.info("mcp herramienta=%s", nombre)  # sin argumentos: no se registra lo que se consulta
        try:
            texto, datos = f(db, args)
            return _resp(id_, {"content": [{"type": "text", "text": texto}], "structuredContent": datos, "isError": False})
        except ErrorHerramienta as e:
            return _resp(id_, {"content": [{"type": "text", "text": str(e)}], "isError": True})
    if metodo in ("resources/list", "prompts/list"):
        return _resp(id_, {"resources": []} if metodo == "resources/list" else {"prompts": []})
    return _resp(id_, error={"code": -32601, "message": f"Método no disponible: {metodo}"})


@router.post("/api/mcp")
async def mcp(request: Request, db: Session = Depends(get_db)):
    ip = ip_cliente(request) or "?"
    if _llamadas_ip.excedida(ip):
        return JSONResponse(_resp(None, error={"code": -32000, "message": "Demasiadas solicitudes. Espere unos minutos."}), status_code=429)
    _llamadas_ip.registrar(ip)
    try:
        cuerpo = json.loads(await request.body() or b"null")
    except ValueError:
        return JSONResponse(_resp(None, error={"code": -32700, "message": "JSON inválido."}), status_code=400)
    if isinstance(cuerpo, list):
        if not cuerpo or len(cuerpo) > 20:
            return JSONResponse(_resp(None, error={"code": -32600, "message": "Lote vacío o demasiado grande."}), status_code=400)
        salidas = [r for r in (_atender(db, x) for x in cuerpo) if r is not None]
        db.rollback()
        return JSONResponse(salidas) if salidas else Response(status_code=202)
    salida = _atender(db, cuerpo)
    db.rollback()  # solo lectura
    return JSONResponse(salida) if salida is not None else Response(status_code=202)


@router.get("/api/mcp")
def mcp_get():
    """Este servidor no abre flujos SSE: todo va por POST con respuestas JSON."""
    return Response(status_code=405, headers={"Allow": "POST"})


@router.delete("/api/mcp")
def mcp_delete():
    return Response(status_code=405, headers={"Allow": "POST"})
