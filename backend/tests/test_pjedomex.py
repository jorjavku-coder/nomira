"""Calendario oficial del Poder Judicial del Estado de México (datos abiertos) y accesos a sus sistemas."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import models as m
from app.services.agenda import pjedomex

from .test_agenda import A, ag  # noqa: F401  (fixture)

DATOS = json.loads((Path(__file__).parent / "datos" / "pjedomex_calendario_2026.json").read_text(encoding="utf-8"))


@pytest.fixture
def tribunal(monkeypatch):
    """Simula el archivo público del PJEdomex: 2026 publicado, 2027 todavía no (404)."""
    archivos = {2026: DATOS}
    monkeypatch.setattr(pjedomex, "descargar", lambda anio: archivos.get(anio))
    monkeypatch.setattr(pjedomex, "_anios", lambda hoy=None: [2026, 2027])
    return archivos


def test_lectura_del_calendario_oficial():
    d = pjedomex.dias_inhabiles(DATOS)
    assert d[date(2026, 5, 1)] == "Día del Trabajo"
    assert date(2026, 5, 8) not in d  # Día de las Madres: festivo, pero no inhábil
    assert date(2026, 7, 13) not in d  # Día del Abogado: festivo, se trabaja
    assert d[date(2026, 7, 20)] == "Primer periodo vacacional (verano 2026)"
    assert d[date(2027, 1, 6)] == "Segundo periodo vacacional (invierno 2026)"  # el periodo cruza de año
    assert date(2027, 1, 7) not in d


def test_conectar_calcular_y_respetar_lo_capturado(ag, tribunal, db):  # noqa: F811
    info = ag.c.get(f"{A}/pjedomex", headers=ag.h).json()
    assert info["calendario"] is None and any(x["clave"] == "tribunal" and "tribunalelectronico.pjedomex.gob.mx" in x["url"] for x in info["accesos"])
    r = ag.c.post(f"{A}/pjedomex/calendario", headers=ag.h, json={"predeterminado": True})
    assert r.status_code == 200, r.text
    x = r.json()
    cal = x["calendario"]
    assert x["es_predeterminado"] and cal["oficial"] == "pjedomex" and cal["entidad"] == "Estado de México" and cal["sincronizado_en"]
    assert x["resultado"]["anios"] == [2026] and x["resultado"]["nuevos"] > 30
    # el plazo usa los días oficiales: notificado el viernes 30-oct-2026, 3 días hábiles; 2 y 16 de nov son inhábiles
    c = ag.c.post(f"{A}/calcular", headers=ag.h, json={"notificacion": "2026-10-30", "dias": 3, "tipo_dias": "habiles",
                                                       "surte_efectos": "dia_habil_siguiente"}).json()
    assert c.get("calendario_id") == cal["id"], c
    assert date(2026, 11, 2).isoformat() in json.dumps(c)  # aparece como día saltado
    # un día que el despacho captura a mano no se toca al sincronizar
    ag.c.post(f"{A}/calendarios/{cal['id']}/dias", headers=ag.h, json={"desde": "2026-10-12", "motivo": "Circular 45/2026 del juzgado"})
    # el tribunal quita un día y publica 2027
    nuevo = json.loads(json.dumps(DATOS))
    nuevo["dias_especiales"] = [d for d in nuevo["dias_especiales"] if d["fecha"] != "2026-12-12"]
    tribunal[2026] = nuevo
    tribunal[2027] = {"dias_especiales": [{"fecha": "2027-05-01", "tipo": "inhabil", "titulo": "Día del Trabajo"}], "periodos": []}
    calm = db.get(m.AgCalendario, cal["id"])
    calm.sincronizado_en = datetime.now(timezone.utc) - timedelta(days=2)
    db.commit()
    r = pjedomex.sincronizar_si_toca(db)
    assert r["calendarios"] == 1 and r["quitados"] == 1
    assert pjedomex.sincronizar_si_toca(db)["calendarios"] == 0  # ya no toca hasta mañana
    dias = {d.fecha: d for d in db.query(m.AgDia).filter_by(calendario_id=cal["id"])}
    assert date(2026, 12, 12) not in dias and date(2027, 5, 1) in dias
    assert dias[date(2026, 10, 12)].origen is None and dias[date(2026, 10, 12)].motivo == "Circular 45/2026 del juzgado"


def test_si_el_tribunal_no_responde(ag, monkeypatch, db):  # noqa: F811
    def falla(anio):
        raise pjedomex.SinDatos("No hubo conexión con el PJEdomex (ConnectTimeout).")
    monkeypatch.setattr(pjedomex, "descargar", falla)
    x = ag.c.post(f"{A}/pjedomex/calendario", headers=ag.h, json={}).json()
    assert "No hubo conexión" in x["resultado"]["error"] and "No hubo conexión" in x["calendario"]["sincronizacion_error"]
    assert not x["es_predeterminado"]
