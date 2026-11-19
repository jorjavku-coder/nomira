"""Evidencia: visor de fuente, relectura sin duplicar, «no relevante», matriz con relación de cada
fuente, búsqueda, duplicados/versiones, visibilidad de documentos y jurisdicción por campos."""
import os
from pathlib import Path

import pytest

from app import models as m
from app.config import ajustes
from app.services.evidencia import demo
from app.services.evidencia.procesamiento import procesar

from .test_evidencia import AVISO, CONTRATO, activar, asunto, panel, subir
from .test_evidencia_solicitudes import CONVENIO, ENTREVISTA


@pytest.fixture
def ev(org, plataforma):
    activar(plataforma, org, "evidencia")
    return org


def test_visor_pagina_texto_y_errores_claros(ev, db):
    aid = asunto(ev)
    subir(ev, aid, ("contrato.pdf", CONTRATO))
    did = panel(ev, aid)["documentos"][0]["id"]
    r = ev.c.get(f"/api/evidencia/documentos/{did}/paginas/1/imagen", headers=ev.h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    cache = list((Path(ajustes().storage_dir) / "cache" / "evidencia").glob(f"{did}-*-1-110.png"))
    assert len(cache) == 1  # la segunda vez no se vuelve a dibujar
    assert ev.c.get(f"/api/evidencia/documentos/{did}/paginas/1/imagen", headers=ev.h).content == r.content
    # El original no cambia
    d = db.get(m.EvDocumento, did)
    assert Path(d.ruta).read_bytes() == CONTRATO
    # Texto leído, separado del original y descrito en palabras (sin porcentajes)
    t = ev.c.get(f"/api/evidencia/documentos/{did}/paginas/1/texto", headers=ev.h).json()
    assert "relación de trabajo inicia" in t["texto"] and t["metodo"] == "texto" and "PDF" in t["legibilidad"]
    # Página inexistente y original perdido: mensajes claros, nunca una espera infinita
    r = ev.c.get(f"/api/evidencia/documentos/{did}/paginas/9/imagen", headers=ev.h)
    assert r.status_code == 404 and "página 9" in r.json()["detail"]
    for f in cache:
        f.unlink()
    os.unlink(d.ruta)
    r = ev.c.get(f"/api/evidencia/documentos/{did}/paginas/1/imagen", headers=ev.h)
    assert r.status_code == 410 and "no está disponible" in r.json()["detail"]


def test_relectura_conserva_lo_humano_no_duplica_e_informa(ev, db):
    aid = asunto(ev)
    subir(ev, aid, ("contrato.pdf", CONTRATO))
    p = panel(ev, aid)
    did = p["documentos"][0]["id"]
    assert p["documentos"][0]["resumen_lectura"]["nuevas"] == len(p["hechos"]) and not p["documentos"][0]["resumen_lectura"]["relectura"]
    inicio = next(h for h in p["hechos"] if h["tema"] == "inicio_relacion")
    salario = next(h for h in p["hechos"] if h["tema"] == "salario")
    lugar = next(h for h in p["hechos"] if h["tipo_dato"] == "lugar")
    ev.c.post(f"/api/evidencia/hechos/{inicio['id']}/confirmar", headers=ev.h)
    ev.c.patch(f"/api/evidencia/hechos/{salario['id']}", headers=ev.h, json={"descripcion": "Salario mensual pactado"})
    r = ev.c.post(f"/api/evidencia/hechos/{lugar['id']}/no_relevante", headers=ev.h).json()
    assert (r["estado"], r["motivo_descarte"]) == ("descartado", "no_relevante") and "no relevante" in r["estado_texto"]
    procesar(db, did)  # «Volver a leer»
    p2 = panel(ev, aid)
    assert len(p2["hechos"]) == len(p["hechos"])  # nada duplicado
    por_id = {h["id"]: h for h in p2["hechos"]}
    assert por_id[inicio["id"]]["estado"] == "confirmado" and por_id[salario["id"]]["descripcion"] == "Salario mensual pactado"
    assert por_id[lugar["id"]]["estado"] == "descartado"  # lo descartado tampoco reaparece
    rl = p2["documentos"][0]["resumen_lectura"]
    assert rl["relectura"] and rl["nuevas"] == 0 and rl["ya_revisadas"] == 3 and rl["conservadas"] == 3
    # Reabrir quita el motivo
    assert ev.c.post(f"/api/evidencia/hechos/{lugar['id']}/reabrir", headers=ev.h).json()["motivo_descarte"] is None


def test_matriz_relacion_de_cada_fuente_decidida_por_el_abogado(ev, db):
    aid = asunto(ev)
    subir(ev, aid, ("contrato.pdf", CONTRATO), ("aviso.pdf", AVISO))
    hs = panel(ev, aid)["hechos"]
    a = next(h for h in hs if h["tema"] == "inicio_relacion")
    b = next(h for h in hs if h["tema"] == "terminacion_relacion")
    for h in (a, b):
        ev.c.post(f"/api/evidencia/hechos/{h['id']}/confirmar", headers=ev.h)
    pid = ev.c.post(f"/api/evidencia/asuntos/{aid}/puntos", headers=ev.h, json={"descripcion": "Relación de trabajo"}).json()["id"]
    pt = ev.c.post(f"/api/evidencia/puntos/{pid}/vinculos", headers=ev.h, json={"hecho_id": a["id"], "relacion": "apoya"}).json()
    assert pt["vinculos"][0]["relacion_texto"] == "Apoya" and pt["vinculos"][0]["relacion_por"] == "Admin 1"
    pt = ev.c.post(f"/api/evidencia/puntos/{pid}/vinculos", headers=ev.h, json={"hecho_id": b["id"]}).json()
    assert pt["vinculos"][1]["relacion"] == "sin_evaluar"
    # Un archivo vinculado no hace que el punto parezca respaldado
    assert (pt["estado"], pt["sugerencia"]["estado"]) == ("pendiente_evidencia", "parcial") and "sin evaluar" in pt["sugerencia"]["motivo"]
    vid = pt["vinculos"][1]["id"]
    pt = ev.c.patch(f"/api/evidencia/vinculos/{vid}", headers=ev.h, json={"relacion": "contradice"}).json()
    assert pt["sugerencia"]["estado"] == "contradictorio" and pt["estado"] == "pendiente_evidencia"
    assert ev.c.patch(f"/api/evidencia/vinculos/{vid}", headers=ev.h, json={"relacion": "probado"}).status_code == 422
    hist = ev.c.get(f"/api/evidencia/asuntos/{aid}/historial", headers=ev.h).json()
    assert hist[0]["accion"] == "Evaluó una fuente de la matriz" and hist[0]["detalle"]["relacion"] == "contradice"


def test_busqueda_duplicados_y_versiones(ev, db):
    aid = asunto(ev)
    # Misma información con otro archivo (otra «versión»): un PDF casi igual
    otro = demo._pdf("CONTRATO INDIVIDUAL DE TRABAJO POR TIEMPO INDETERMINADO", [
        "En la Ciudad de México, el 15 de enero de 2020, celebran el presente contrato por una parte EMPRESA "
        "FICTICIA DEMO, S.A. de C.V., representada por el Lic. Roberto Ejemplo Pérez, y por la otra el C. Juan Demo "
        "Ficticio, a quien se denominará el trabajador.",
        "PRIMERA. La relación de trabajo inicia el 15 de enero de 2020 y será por tiempo indeterminado.",
        "SEGUNDA. El trabajador desempeñará el puesto de analista administrativo en el domicilio de la empresa.",
        "TERCERA. El salario mensual será de $19,000.00 M.N., pagadero por quincenas vencidas.",
        "CUARTA. La jornada será de lunes a viernes, de 9:00 a 18:00 horas, con una hora para tomar alimentos.",
    ])
    subir(ev, aid, ("contrato.pdf", CONTRATO), ("contrato_v2.pdf", otro), ("convenio.pdf", CONVENIO))
    docs = {d["nombre"]: d for d in panel(ev, aid)["documentos"]}
    rel = docs["contrato.pdf"]["relacionados"]
    assert [(r["nombre"], r["tipo"], r["es_mas_reciente"]) for r in rel] == [("contrato_v2.pdf", "duplicado", True)] or \
        [(r["nombre"], r["tipo"]) for r in rel] == [("contrato_v2.pdf", "version")]
    assert docs["convenio.pdf"]["relacionados"] == []
    c = ev.c.get(f"/api/evidencia/documentos/{docs['contrato.pdf']['id']}/comparar/{docs['contrato_v2.pdf']['id']}", headers=ev.h).json()
    cambios = [x for x in c["lineas"] if x["tipo"] != "igual"]
    assert c["cambios"] >= 2 and any("18,500.00" in x["texto"] and x["tipo"] == "solo_a" for x in cambios)
    assert any("19,000.00" in x["texto"] and x["tipo"] == "solo_b" for x in cambios) and c["mas_reciente_id"] == docs["contrato_v2.pdf"]["id"]
    assert len({Path(d.ruta).read_bytes() for d in db.query(m.EvDocumento)}) == 3  # ambos originales intactos
    # Búsqueda sin acentos ni mayúsculas; indica documento, página y fragmento
    r = ev.c.get(f"/api/evidencia/asuntos/{aid}/buscar", headers=ev.h, params={"q": "pension ALIMENTICIA"}).json()
    assert [(x["documento"], x["pagina"]) for x in r["resultados"]] == [("convenio.pdf", 1)]
    assert r["resultados"][0]["coincidencia"].lower() == "pensión alimenticia" and r["resultados"][0]["antes"]
    assert ev.c.get(f"/api/evidencia/asuntos/{aid}/buscar", headers=ev.h, params={"q": "x"}).status_code == 422


def test_visibilidad_restringida_se_respeta_en_servidor(ev, db):
    aid = asunto(ev)
    subir(ev, aid, ("entrevista.pdf", ENTREVISTA), ("contrato.pdf", CONTRATO))
    docs = {d["nombre"]: d for d in panel(ev, aid)["documentos"]}
    did = docs["entrevista.pdf"]["id"]
    r = ev.c.patch(f"/api/evidencia/documentos/{did}/visibilidad", headers=ev.h, json={"visibilidad": "restringido"})
    assert r.status_code == 200 and r.json()["visibilidad_texto"] == "Restringido"
    assert ev.c.patch(f"/api/evidencia/documentos/{did}/visibilidad", headers=ev.h, json={"visibilidad": "secreto"}).status_code == 422
    ha = ev.usuario("analista", "ana@org1.test")
    p = ev.c.get(f"/api/evidencia/asuntos/{aid}", headers=ha).json()
    assert [d["nombre"] for d in p["documentos"]] == ["contrato.pdf"] and p["resumen"]["documentos_restringidos_ocultos"] == 1
    assert not any(h["documento_id"] == did for h in p["hechos"])
    for ruta in (f"/documentos/{did}/archivo", f"/documentos/{did}/paginas/1/imagen", f"/documentos/{did}/paginas/1/texto"):
        assert ev.c.get("/api/evidencia" + ruta, headers=ha).status_code == 404
    r = ev.c.get(f"/api/evidencia/asuntos/{aid}/buscar", headers=ha, params={"q": "separación"}).json()
    assert r["resultados"] == []
    pdf = ev.c.get(f"/api/evidencia/asuntos/{aid}/exportar/excel", headers=ha)
    import io

    from openpyxl import load_workbook
    celdas = [str(c.value) for ws in load_workbook(io.BytesIO(pdf.content)) for fila in ws.iter_rows() for c in fila]
    assert pdf.status_code == 200 and not any("entrevista.pdf" in c for c in celdas) and any("contrato.pdf" in c for c in celdas)
    # El administrador sí lo ve
    assert len(panel(ev, aid)["documentos"]) == 2


def test_jurisdiccion_por_campos_sin_perder_lo_anterior(ev, db):
    aid = asunto(ev, jurisdiccion="Toluca, Edo. Méx.")
    r = ev.c.patch(f"/api/evidencia/asuntos/{aid}", headers=ev.h, json={
        "ambito": "local", "entidad_federativa": "Estado de México", "municipio_distrito": "Distrito judicial de Toluca",
        "organo": "Juzgado Tercero Familiar", "expediente_judicial": "123/2026"}).json()
    assert r["jurisdiccion"] == "Toluca, Edo. Méx."  # lo capturado antes se conserva
    assert r["jurisdiccion_texto"] == "Local · Estado de México · Distrito judicial de Toluca · Juzgado Tercero Familiar · Exp. 123/2026"
    assert r["identificador_interno"] is None  # el expediente judicial va aparte del identificador del despacho
    for malo in ({"ambito": "estatal"}, {"entidad_federativa": "Texas"}):
        assert ev.c.patch(f"/api/evidencia/asuntos/{aid}", headers=ev.h, json=malo).status_code == 422
    r = ev.c.patch(f"/api/evidencia/asuntos/{aid}", headers=ev.h, json={"ambito": "federal", "entidad_federativa": None}).json()
    assert (r["ambito"], r["entidad_federativa"]) == ("federal", None)
    assert len(panel(ev, aid)["catalogos"]["entidades"]) == 32
