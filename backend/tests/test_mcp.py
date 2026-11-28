"""Conector MCP público: protocolo (initialize, tools/list, tools/call, notificaciones, lotes) y herramientas de consulta."""
from app import models as m
from app.db import SessionLocal

U = "/api/mcp"


def rpc(cliente, metodo, params=None, id_=1):
    r = cliente.post(U, json={"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params or {}})
    assert r.status_code == 200, r.text
    return r.json()


def llamar(cliente, nombre, args):
    return rpc(cliente, "tools/call", {"name": nombre, "arguments": args})["result"]


def test_protocolo(cliente):
    r = rpc(cliente, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "prueba", "version": "1"}})
    assert r["result"]["protocolVersion"] == "2025-06-18" and "tools" in r["result"]["capabilities"]
    assert rpc(cliente, "initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"] == "2025-06-18"
    assert cliente.post(U, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    nombres = [t["name"] for t in rpc(cliente, "tools/list")["result"]["tools"]]
    assert nombres == ["buscar_tesis", "ver_tesis", "calcular_finiquito", "calcular_plazo"]
    assert rpc(cliente, "nada/aqui")["error"]["code"] == -32601
    assert rpc(cliente, "tools/call", {"name": "borrar_todo"})["error"]["code"] == -32602
    lote = cliente.post(U, json=[{"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"jsonrpc": "2.0", "method": "notifications/initialized"}]).json()
    assert lote == [{"jsonrpc": "2.0", "id": 1, "result": {}}]
    assert cliente.post(U, content=b"{no json").status_code == 400
    assert cliente.get(U).status_code == 405


def test_tesis(cliente):
    with SessionLocal() as db:
        db.add(m.JTesis(registro=2099001, rubro="LITISCONSORCIO PASIVO NECESARIO. SU ANÁLISIS ES DE OFICIO.", clave="1a./J. 99/2099",
                        tipo="jurisprudencia", epoca="Undécima Época", instancia="Primera Sala", materias="Civil", anio=2024,
                        texto="El litisconsorcio pasivo necesario debe analizarse de oficio por el juzgador.", origen="prueba"))
        db.commit()
    r = llamar(cliente, "buscar_tesis", {"consulta": "litisconsorcio pasivo"})
    assert not r["isError"] and "2099001" in r["content"][0]["text"] and r["structuredContent"]["resultados"][0]["registro"] == 2099001
    assert "sjf2.scjn.gob.mx" in r["content"][0]["text"]
    v = llamar(cliente, "ver_tesis", {"registro": 2099001})
    assert "de oficio por el juzgador" in v["content"][0]["text"]
    assert llamar(cliente, "ver_tesis", {"registro": 1})["isError"] is True
    vacio = llamar(cliente, "buscar_tesis", {"consulta": "zzzqqqxxx"})
    assert not vacio["isError"] and "No encontré" in vacio["content"][0]["text"]


def test_finiquito_y_plazo(cliente):
    r = llamar(cliente, "calcular_finiquito", {"fecha_ingreso": "2020-01-01", "fecha_baja": "2025-06-01", "causa": "despido_injustificado",
                                               "salario_diario": 500})
    t = r["content"][0]["text"]
    assert not r["isError"] and "TOTAL: $" in t and "Art. 87 LFT" in t and "Indemnización constitucional" in t
    assert llamar(cliente, "calcular_finiquito", {"fecha_ingreso": "2020-01-01", "causa": "renuncia", "salario_diario": 500})["isError"]
    p = llamar(cliente, "calcular_plazo", {"fecha_notificacion": "2026-11-13", "dias": 15, "inhabiles": ["2026-11-26"]})
    sc = p["structuredContent"]
    assert not p["isError"] and sc["vence"] > "2026-11-13"
    assert any("art. 74" in s["motivo"] for s in sc["saltados"])  # 16 de noviembre de 2026: tercer lunes
    assert any(s["fecha"] == "2026-11-26" for s in sc["saltados"])
    assert llamar(cliente, "calcular_plazo", {"fecha_notificacion": "ayer", "dias": 5})["isError"]
