"""Biblioteca de tesis: lectura de JSON del Repositorio y del PDF semanal de la SCJN, búsqueda sin acentos, ficha PDF,
carga desde el panel (solo plataforma) y sincronización cortés que se detiene si la SCJN bloquea."""
import json

import httpx
import pymupdf
import pytest

from app import models as m
from app.config import ajustes
from app.services.tesis import base as tb, repositorio as rp

T1 = {"registroDigital": 2031967, "rubro": "PRESCRIPCIÓN DE LA ACCIÓN DE NULIDAD. CÓMPUTO DEL PLAZO.", "texto": "Hechos: Se analizó el plazo de prescripción "
      "de la acción de nulidad de un contrato. Criterio jurídico: el plazo corre desde que el acto es conocido por la persona afectada.",
      "precedentes": "Contradicción de criterios 1/2026.", "tesis": "P./J. 42/2026 (12a.)", "tipoTesis": "Jurisprudencia", "epoca": "Duodécima Época",
      "instancia": "Pleno", "materias": ["Civil"], "sha256": "ab" * 32}
T2 = {"registroDigital": 2030000, "rubro": "SUSPENSIÓN EN EL AMPARO. PROCEDE CONTRA LA CLAUSURA.", "texto": "La suspensión procede contra la clausura de "
      "un establecimiento cuando se satisfacen los requisitos del artículo 128 de la Ley de Amparo y no se afecta el interés social.",
      "tesis": "I.1o.A. 5 A (11a.)", "tipoTesis": "Aislada", "epoca": "Undécima Época", "instancia": "Tribunales Colegiados de Circuito"}


def pdf_semanal() -> bytes:
    d = pymupdf.open()
    p = d.new_page()
    renglones = ["Tesis", "Registro digital: 2032328", "Instancia: Primera Sala", "Duodécima Época", "Materia(s): Común",
                 "Tesis: 1a./J. 99/2026 (12a.)", "Tipo: Jurisprudencia", "IMPEDIMENTO POR AMISTAD ESTRECHA. PARA ANALIZAR DICHA CAUSA ES",
                 "FUNDAMENTAL LO MANIFESTADO POR LA PERSONA JUZGADORA EN SU INFORME.", "Hechos: Una persona promovió un impedimento",
                 "por amistad estrecha y el órgano lo declaró infundado.", "Esta tesis se publicó el viernes 26 de junio de 2026 a las 10:30 horas.",
                 "Pág. 2 de 100 Fecha de impresión 26/06/2026", "Tesis", "Registro digital: 2032344",
                 "PROVIDENCIAS PRECAUTORIAS EN EL JUICIO ORAL MERCANTIL. PROCEDE EL AMPARO INDIRECTO.",
                 "Contra las determinaciones que concedan o nieguen providencias precautorias procede el amparo indirecto, con",
                 "número de registro digital: 2029969, y así se resolvió."]
    y = 50
    for r in renglones:
        p.insert_text((40, y), r, fontsize=8)
        y += 12
    return d.tobytes()


def test_lectura_json_y_pdf():
    t = tb.desde_json(T1)
    assert t["registro"] == 2031967 and t["tipo"] == "jurisprudencia" and t["materias"] == "Civil" and t["huella_oficial"] == "ab" * 32
    assert tb.desde_json({"registro": "x", "rubro": "A"}) is None
    datos, origen = tb.leer_archivo("x.json", json.dumps({"data": [T1, T2]}).encode())
    assert origen == "json" and {d["registro"] for d in datos} == {2031967, 2030000}
    filas, origen = tb.leer_archivo("semanal.pdf", pdf_semanal())
    assert origen == "pdf_semanal" and [f["registro"] for f in filas] == [2032328, 2032344]
    assert filas[0]["rubro"].startswith("IMPEDIMENTO POR AMISTAD ESTRECHA") and filas[0]["rubro"].endswith("INFORME.")
    assert filas[0]["clave"] == "1a./J. 99/2026 (12a.)" and filas[0]["tipo"] == "jurisprudencia" and filas[0]["epoca"] == "Duodécima Época"
    assert not filas[0]["texto"].rstrip().endswith("Tesis")
    assert "Pág." not in filas[0]["texto"] and filas[0]["publicada"].startswith("Esta tesis se publicó")
    assert "2029969" in filas[1]["texto"]  # una cita dentro del texto no parte la tesis


def test_busqueda_y_ficha(db, org):
    tb.guardar(db, [tb.desde_json(T1), tb.desde_json(T2)], "json", "prueba.json")
    db.commit()
    filas, n = tb.buscar(db, "prescripcion accion nulidad")
    assert n == 1 and filas[0].registro == 2031967
    assert tb.buscar(db, "clausura amparo")[0][0].registro == 2030000
    assert tb.buscar(db, "clausura nulidad")[1] == 0 and tb.buscar(db, "clausura nulidad", cualquiera=True)[1] == 2
    assert tb.buscar(db, "2030000")[0][0].registro == 2030000
    r = org.c.get("/api/tesis", headers=org.h, params={"q": "suspensión", "tipo": "aislada"}).json()
    assert r["total"] == 1 and r["resultados"][0]["enlace"] == "https://sjf2.scjn.gob.mx/detalle/tesis/2030000" and "texto" not in r["resultados"][0]
    assert org.c.get("/api/tesis/2031967", headers=org.h).json()["clave"] == "P./J. 42/2026 (12a.)"
    assert org.c.get("/api/tesis/1", headers=org.h).status_code == 404
    pdf = org.c.get("/api/tesis/2031967/pdf", headers=org.h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    with pymupdf.open(stream=pdf.content, filetype="pdf") as d:
        texto = "".join(p.get_text() for p in d)
    assert "2031967" in texto and "sjf2.scjn.gob.mx/detalle/tesis/2031967" in texto
    assert org.c.get("/api/tesis", params={"q": "x"}).status_code == 401


def test_importar_desde_panel(plataforma, org):
    r = plataforma.c.post("/api/plataforma/tesis/importar", headers=plataforma.h, files={"archivo": ("semanal.pdf", pdf_semanal(), "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["importadas"] == 2 and r.json()["por_origen"] == {"pdf_semanal": 2}
    assert plataforma.c.post("/api/plataforma/tesis/importar", headers=plataforma.h, files={"archivo": ("x.txt", b"hola", "text/plain")}).status_code == 422
    assert org.c.post("/api/plataforma/tesis/importar", headers=org.h, files={"archivo": ("s.pdf", pdf_semanal(), "application/pdf")}).status_code == 401


class Remoto:
    def __init__(self, bloquear=False):
        self.llamadas = []
        self.bloquear = bloquear
        self.tesis = {2031967: T1, 2030000: T2, 170000: {**T2, "registroDigital": 170000, "epoca": "Novena Época"}}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.llamadas.append(str(req.url))
        if self.bloquear:
            return httpx.Response(200, headers={"content-type": "text/html"}, text="<html><script src='/_Incapsula_Resource'></script></html>")
        ruta = req.url.path.rsplit("/api/v1/", 1)[1]
        if ruta == "tesis/count":
            return httpx.Response(200, json=len(self.tesis))
        if ruta == "tesis/ids":
            return httpx.Response(200, json=list(self.tesis) if req.url.params["page"] == "0" else [])
        return httpx.Response(200, json=self.tesis[int(ruta.split("/")[1])])


@pytest.fixture
def sincronizar(monkeypatch):
    monkeypatch.setattr(ajustes(), "tesis_sincronizar", True)


def test_sincronizacion(db, sincronizar):
    remoto = Remoto()
    e = rp.correr(db, cliente=httpx.Client(transport=httpx.MockTransport(remoto)), pausa=0)
    assert e.estado == "al_dia" and e.descargadas == 2 and e.omitidas == 1 and e.total_remoto == 3
    assert {t.registro for t in db.query(m.JTesis)} == {2031967, 2030000}  # la de Novena Época no se guarda
    assert db.get(m.JTesis, 2031967).origen == "repositorio"
    # siguiente corrida: ya está al día, no vuelve a listar
    n = len(remoto.llamadas)
    rp.correr(db, cliente=httpx.Client(transport=httpx.MockTransport(remoto)), pausa=0)
    assert len(remoto.llamadas) == n


def test_bloqueo_se_detiene(db, sincronizar):
    remoto = Remoto(bloquear=True)
    e = rp.correr(db, cliente=httpx.Client(transport=httpx.MockTransport(remoto)), pausa=0)
    assert e.estado == "bloqueada" and "no" not in (e.mensaje or "")[:0] and len(remoto.llamadas) == 1  # una sola solicitud y se detiene
    assert e.proximo_intento is not None
    rp.correr(db, cliente=httpx.Client(transport=httpx.MockTransport(remoto)), pausa=0)
    assert len(remoto.llamadas) == 1  # respeta la espera de 24 horas


def test_apagada(db, monkeypatch):
    monkeypatch.setattr(ajustes(), "tesis_sincronizar", False)
    assert rp.correr(db, pausa=0).estado == "apagada"


def test_filtros_materia_organo_anio(db, org):
    t2 = {**T2, "materias": "Común, Administrativa", "notaPublicacion": "Esta tesis se publicó el viernes 10 de enero de 2025"}
    tb.guardar(db, [tb.desde_json(T1), tb.desde_json(t2)], "json", "x.json")
    db.commit()
    assert db.get(m.JTesis, 2031967).anio == 2026 and db.get(m.JTesis, 2030000).anio == 2025  # de la clave y de la nota
    assert [t.registro for t in tb.buscar(db, "", materia="civil")[0]] == [2031967]
    assert [t.registro for t in tb.buscar(db, "", materia="Administrativa")[0]] == [2030000]
    assert [t.registro for t in tb.buscar(db, "", instancia="colegiados")[0]] == [2030000]
    assert [t.registro for t in tb.buscar(db, "", instancia="pleno")[0]] == [2031967]
    assert [t.registro for t in tb.buscar(db, "", anio_desde=2026)[0]] == [2031967]
    assert tb.buscar(db, "")[1] == 0  # sin palabras ni filtros no lista todo
    r = org.c.get("/api/tesis", headers=org.h, params={"tipo": "jurisprudencia", "materia": "Civil", "instancia": "pleno", "anio_desde": 2026}).json()
    assert r["total"] == 1 and r["resultados"][0]["anio"] == 2026 and r["anios"] == [2025, 2026] and "Laboral" in r["materias"]
