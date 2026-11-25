"""Inicio: solo muestra números de los módulos activos, lo de hoy y el avance de los primeros pasos."""
from datetime import timedelta

from app.services.agenda import base

from .test_evidencia import activar


def test_inicio_solo_lo_activo_y_lo_de_hoy(org, org2, plataforma):
    r = org.c.get("/api/inicio", headers=org.h).json()
    assert [n["clave"] for n in r["numeros"]] == [] and r["hoy"] == [] and r["aviso"] is None
    assert r["pasos"] == {"despacho": False, "equipo": False, "cliente": False, "agenda": False, "asistente": False}
    activar(plataforma, org, "agenda")
    activar(plataforma, org, "rh")
    hoy = base.hoy()
    org.c.post("/api/agenda/eventos", headers=org.h, json={"tipo": "actividad", "titulo": "Revisar acuerdo", "fecha": hoy.isoformat()})
    org.c.post("/api/agenda/eventos", headers=org.h, json={"tipo": "actividad", "titulo": "Llamar al perito", "fecha": (hoy - timedelta(days=1)).isoformat()})
    org.c.post("/api/agenda/eventos", headers=org.h, json={"tipo": "actividad", "titulo": "Dentro de un mes", "fecha": (hoy + timedelta(days=30)).isoformat()})
    r = org.c.get("/api/inicio", headers=org.h).json()
    assert [n["clave"] for n in r["numeros"]] == ["agenda", "rh"]
    assert r["numeros"][0]["valor"] == "1" and r["aviso"]["texto"] == "2 pendientes vencidos o de hoy"
    assert [x["titulo"] for x in r["hoy"]] == ["Llamar al perito", "Revisar acuerdo"] and r["hoy"][0]["situacion"] == "vencido"
    assert r["pasos"]["agenda"] is True
    # otro despacho no ve nada de esto
    r2 = org2.c.get("/api/inicio", headers=org2.h).json()
    assert r2["hoy"] == [] and r2["aviso"] is None
