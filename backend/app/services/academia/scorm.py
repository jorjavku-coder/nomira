"""Reproductor SCORM: el paquete se sirve en un iframe AISLADO (sandbox, origen opaco) para que su
JavaScript no pueda leer la sesión de Nomira. En cada página HTML se inyecta una API SCORM (1.2 y
2004) que guarda los datos en memoria y los envía a Nomira por postMessage; la página de Nomira,
que sí tiene la sesión, los guarda en el servidor."""
from __future__ import annotations

import json

ESTADOS_COMPLETOS = {"completed", "passed"}

_SHIM = """<script>(function(){
var D=__DATOS__,E="0",V=__VERSION__;
function enviar(fin){try{parent.postMessage({nomiraScorm:1,datos:D,fin:!!fin},"*")}catch(e){}}
function g(k){var v=D[k];return v===undefined||v===null?"":String(v)}
function s(k,v){D[k]=String(v);E="0";return "true"}
var api12={LMSInitialize:function(){E="0";return "true"},LMSFinish:function(){enviar(1);return "true"},
LMSGetValue:function(k){return g(k)},LMSSetValue:function(k,v){return s(k,v)},LMSCommit:function(){enviar(0);return "true"},
LMSGetLastError:function(){return E},LMSGetErrorString:function(){return ""},LMSGetDiagnostic:function(){return ""}};
var api04={Initialize:function(){E="0";return "true"},Terminate:function(){enviar(1);return "true"},
GetValue:function(k){return g(k)},SetValue:function(k,v){return s(k,v)},Commit:function(){enviar(0);return "true"},
GetLastError:function(){return E},GetErrorString:function(){return ""},GetDiagnostic:function(){return ""}};
window.API=api12;window.API_1484_11=api04;
setInterval(function(){enviar(0)},30000);
window.addEventListener("pagehide",function(){enviar(0)});
})();</script>"""


def datos_iniciales(guardados: dict | None, nombre: str, usuario_id: int, version: str) -> dict:
    d = dict(guardados or {})
    if version == "1.2":
        d.setdefault("cmi.core.student_id", str(usuario_id))
        d.setdefault("cmi.core.student_name", nombre)
        d.setdefault("cmi.core.lesson_status", "not attempted")
        d["cmi.core.entry"] = "resume" if d.get("cmi.core.lesson_location") or d.get("cmi.suspend_data") else "ab-initio"
    else:
        d.setdefault("cmi.learner_id", str(usuario_id))
        d.setdefault("cmi.learner_name", nombre)
        d.setdefault("cmi.completion_status", "unknown")
        d["cmi.entry"] = "resume" if d.get("cmi.location") or d.get("cmi.suspend_data") else "ab-initio"
    return d


def inyectar(html: bytes, datos: dict, version: str) -> bytes:
    js = _SHIM.replace("__DATOS__", json.dumps(datos).replace("</", "<\\/")).replace("__VERSION__", json.dumps(version)).encode()
    bajo = html.lower()
    i = bajo.find(b"<head")
    if i >= 0:
        j = bajo.find(b">", i)
        return html[: j + 1] + js + html[j + 1:]
    return js + html


def resumen(datos: dict, version: str) -> dict:
    """Estado legible de lo que guardó el paquete."""
    if version == "1.2":
        estado = (datos.get("cmi.core.lesson_status") or "").lower()
        puntos = datos.get("cmi.core.score.raw")
        completo = estado in ESTADOS_COMPLETOS
    else:
        estado = (datos.get("cmi.success_status") if datos.get("cmi.success_status") not in (None, "", "unknown") else
                  datos.get("cmi.completion_status") or "").lower()
        puntos = datos.get("cmi.score.raw") or (str(round(float(datos["cmi.score.scaled"]) * 100)) if datos.get("cmi.score.scaled") else None)
        completo = (datos.get("cmi.completion_status") or "").lower() == "completed" or (datos.get("cmi.success_status") or "").lower() == "passed"
    try:
        calif = round(float(puntos)) if puntos not in (None, "") else None
    except ValueError:
        calif = None
    return {"estado": estado or "sin iniciar", "completo": completo, "calificacion": calif}


def limpiar(datos: dict) -> dict:
    """Solo claves cmi.* razonables (el paquete es contenido de terceros)."""
    res = {}
    for k, v in list(datos.items())[:500]:
        if isinstance(k, str) and k.startswith("cmi.") and len(k) <= 255:
            res[k] = str(v)[:65536] if v is not None else ""
    return res
