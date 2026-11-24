"""PJF (Lista de acuerdos): catálogo de órganos leído de la consulta oficial (sin reCAPTCHA), vigilancia federal,
revisión diaria asistida (una búsqueda por órgano) y cotejo restringido al órgano. Nunca hay consulta automática."""
import httpx
import pytest

from app.services.agenda import base, pjf

from .test_agenda import A, ag, asunto, buzon  # noqa: F401

PAGINA = """<form><input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="abc&amp;1" />
<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="xyz" />
<select name="FiltroOrgano$ddlOrgano" id="FiltroOrgano_ddlOrgano">
<option value="10">Juzgado Primero de Distrito en Materia Administrativa en la Ciudad de M&#233;xico</option>
<option value="555">Juzgado Primero de Distrito de Procesos Penales Federales (13/12/2001 - 31/08/2016)</option>
<option value="527">Juzgado Primero de Distrito en Materia de Trabajo en la Ciudad de México</option>
</select></form>"""

LISTA = """Órgano: Juzgado Primero de Distrito en Materia Administrativa en la Ciudad de México
Expediente 1234/2026 Amparo indirecto  Fecha de auto 23/11/2026
Se tiene por rendido el informe justificado de la autoridad responsable.
Expediente 77/2026 Amparo indirecto
Se admite la demanda."""


def test_catalogo_de_organos(monkeypatch):
    pjf._cache.clear()
    pedidos = []

    def responder(req: httpx.Request):
        pedidos.append(req)
        return httpx.Response(200, text=PAGINA)
    cli = httpx.Client(transport=httpx.MockTransport(responder))
    org = pjf.organos("1", cli)
    assert org == [{"id": "10", "nombre": "Juzgado Primero de Distrito en Materia Administrativa en la Ciudad de México"},
                   {"id": "527", "nombre": "Juzgado Primero de Distrito en Materia de Trabajo en la Ciudad de México"}]  # sin órganos cerrados
    cuerpo = pedidos[1].content.decode()
    assert "__EVENTTARGET=FiltroOrgano%24ddlCircuito" in cuerpo and "__VIEWSTATE=abc%261" in cuerpo
    assert "btnBuscar" not in cuerpo and "recaptcha" not in cuerpo.lower()  # nunca se envía la búsqueda
    assert pjf.organos("1", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))) == org  # caché
    with pytest.raises(pjf.SinCatalogo):
        pjf.organos("999")


def test_vigilancia_federal_y_revision_diaria(ag, buzon, monkeypatch):  # noqa: F811
    monkeypatch.setattr(pjf, "organos", lambda c, cliente=None: [{"id": "10", "nombre": "Juzgado Primero"}])
    assert ag.c.get(f"{A}/estrados/pjf/organos?circuito=1", headers=ag.h).json()["organos"][0]["id"] == "10"
    a1, a2, a3 = asunto(ag), asunto(ag), asunto(ag)
    org = "Juzgado Primero de Distrito en Materia Administrativa en la Ciudad de México"
    assert ag.c.put(f"{A}/asuntos/{a1['id']}/vigilancia", headers=ag.h, json={"fuente": "pjf", "expediente": "1234/2026", "sala": org}).status_code == 422  # falta circuito
    for a, exp in ((a1, "1234/2026"), (a2, "0077/2026")):
        r = ag.c.put(f"{A}/asuntos/{a['id']}/vigilancia", headers=ag.h, json={"fuente": "pjf", "circuito": "1", "id_sala": "10", "sala": org, "expediente": exp})
        assert r.status_code == 200, r.text
        assert r.json()["fuente"] == "pjf" and r.json()["circuito_texto"] == "Primer Circuito"
    # mismo número de expediente en OTRO juzgado: no debe confundirse
    ag.c.put(f"{A}/asuntos/{a3['id']}/vigilancia", headers=ag.h, json={"fuente": "pjf", "circuito": "1", "id_sala": "527", "sala": "Juzgado de Trabajo", "expediente": "1234/2026"})
    res = ag.c.get(f"{A}/estrados", headers=ag.h).json()
    grupos = {g["id_organo"]: g for g in res["revision_pjf"]}
    assert grupos["10"]["busqueda"] == "77/2026, 1234/2026" and grupos["527"]["busqueda"] == "1234/2026"
    vid = ag.c.get(f"{A}/asuntos/{a1['id']}", headers=ag.h).json()["vigilancia"]["id"]
    r = ag.c.post(f"{A}/vigilancias/{vid}/revisar", headers=ag.h)
    assert r.status_code == 409 and "reCAPTCHA" in r.text  # no hay consulta automática
    c = ag.c.post(f"{A}/estrados/cotejar", headers=ag.h, json={"fecha": base.hoy().isoformat(), "texto": LISTA, "fuente": "pjf", "id_organo": "10"}).json()
    assert c["revisados"] == 2 and c["encontrados"] == 2
    asuntos = {p["asunto_id"] for p in c["nuevas"]}
    assert asuntos == {a1["id"], a2["id"]}  # el de otro juzgado con el mismo número no se toca
    assert any("informe justificado" in p["descripcion"] for p in c["nuevas"])
    # cambiar de tribunal reutiliza la misma vigilancia
    r = ag.c.put(f"{A}/asuntos/{a3['id']}/vigilancia", headers=ag.h, json={"fuente": "trijaem", "id_sala": "1", "expediente": "1234/2026"}).json()
    assert r["fuente"] == "trijaem" and r["circuito"] is None
