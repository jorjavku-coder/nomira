"""La lista de expedientes no debe hacer más consultas a la base por cada expediente."""
from contextlib import contextmanager

from sqlalchemy import event

from app.db import engine
from app.sinteticos import BASE, crear_pdf, recibo


@contextmanager
def contar_consultas():
    n = [0]

    def antes(*_):
        n[0] += 1
    event.listen(engine, "before_cursor_execute", antes)
    try:
        yield n
    finally:
        event.remove(engine, "before_cursor_execute", antes)


def _consultas_lista(org):
    with contar_consultas() as n:
        r = org.c.get("/api/expedientes", headers=org.h)
    assert r.status_code == 200
    return n[0], r.json()


def test_lista_de_expedientes_no_crece_con_n(org):
    pdf = crear_pdf([recibo("01-15 de Enero de 2025", BASE, num="1"), recibo("16-31 de Enero de 2025", BASE, num="2")])
    eid = org.expediente()
    org.subir(eid, pdf)
    pocas, lista1 = _consultas_lista(org)
    for _ in range(4):
        org.subir(org.expediente(), pdf)
    muchas, lista5 = _consultas_lista(org)
    assert len(lista5) == 5
    assert muchas == pocas, f"1 expediente: {pocas} consultas; 5 expedientes: {muchas}"
    # Mismo contenido que el detalle individual
    detalle = org.c.get(f"/api/expedientes/{eid}", headers=org.h).json()
    fila = next(e for e in lista5 if e["id"] == eid)
    assert fila == detalle


def test_detalle_sin_resumen_no_calcula(org):
    eid = org.expediente()
    with contar_consultas() as con:
        completo = org.c.get(f"/api/expedientes/{eid}", headers=org.h).json()
    with contar_consultas() as sin:
        ligero = org.c.get(f"/api/expedientes/{eid}?resumen=false", headers=org.h).json()
    assert "resumen" in completo and "resumen" not in ligero
    assert sin[0] < con[0]
    assert {k: v for k, v in completo.items() if k not in ("resumen", "total_expediente", "provisional")} == ligero


# ---------- archivos y salud ----------

def test_descarga_y_archivo_perdido(org, db):
    import os
    from app import models as m
    pdf = crear_pdf([recibo("01-15 de Enero de 2025", BASE, num="1")])
    did = org.subir(org.expediente(), pdf)[0]["documento_id"]
    r = org.c.get(f"/api/documentos/{did}/archivo", headers=org.h)
    assert r.status_code == 200 and r.content == pdf
    assert r.headers["cache-control"] == "private, no-store"
    assert 'filename="documento-' in r.headers["content-disposition"]
    os.unlink(db.get(m.Documento, did).ruta)  # p. ej. disco temporal tras reiniciar
    for ruta in (f"/api/documentos/{did}/archivo", f"/api/documentos/{did}/paginas/1/imagen"):
        r = org.c.get(ruta, headers=org.h)
        assert r.status_code == 410 and "ya no está disponible" in r.json()["detail"]


def test_salud_revisa_la_base(cliente, monkeypatch):
    assert cliente.get("/api/salud").json() == {"ok": True}
    from app import main

    class Caida:
        def connect(self):
            raise ConnectionError("sin base")
    monkeypatch.setattr(main, "engine", Caida())
    r = cliente.get("/api/salud")
    assert r.status_code == 503 and r.json()["ok"] is False
