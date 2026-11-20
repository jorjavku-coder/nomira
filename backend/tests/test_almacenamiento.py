"""Almacenamiento: costo del disco de Render pasado al precio del cliente y espacio de Academia
medido contra el almacenamiento contratado en Comercial."""
from app.services import almacenamiento as almacen

from .test_academia import curso, leccion
from .test_evidencia import activar

R = "/api/plataforma/comercial"
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20000  # ~20 KB


def test_costo_del_proveedor_y_precio_sugerido(plataforma):
    r = plataforma.c.get(f"{R}/almacenamiento", headers=plataforma.h)
    assert r.status_code == 200, r.text
    x = r.json()
    assert x["config"] == {"costo_gb_usd": "0.25", "tipo_cambio": "19.00", "margen_almacenamiento_pct": "150", "disco_gb": 5}
    # 0.25 USD × 19 = 4.75 MXN por GB; bloque de 25 GB = 118.75; +150 % = 296.88 → 299
    assert x["costo_gb_mxn"] == "4.75" and x["bloque"]["costo_mxn"] == "118.75" and x["bloque"]["precio_sugerido"] == "299"
    assert x["bloque"]["precio_actual"] == "299.00"
    basico = next(p for p in x["paquetes"] if p["nombre"] == "Básico")
    assert basico["gb"] == 10 and basico["costo_mxn"] == "47.50"
    assert x["disco"]["disco_gb"] == 5 and x["disco"]["contratado_gb"] == 0
    r = plataforma.c.put(f"{R}/almacenamiento", headers=plataforma.h,
                         json={"costo_gb_usd": "0.25", "tipo_cambio": "20", "margen_almacenamiento_pct": "100", "disco_gb": 10})
    assert r.status_code == 200 and r.json()["bloque"]["precio_sugerido"] == "259"  # 25 × 5 × 2 = 250 → 259
    assert plataforma.c.put(f"{R}/almacenamiento", headers=plataforma.h,
                            json={"costo_gb_usd": "0", "tipo_cambio": "20", "margen_almacenamiento_pct": "100", "disco_gb": 10}).status_code == 422


def test_precio_redondo():
    from decimal import Decimal as D
    assert almacen.precio_redondo(D("296.875")) == 299 and almacen.precio_redondo(D("250")) == 259 and almacen.precio_redondo(D("299")) == 299


def _asignar(plataforma, org, bloques=0):
    cat = plataforma.c.get(f"{R}/catalogo", headers=plataforma.h).json()
    basico = next(x for x in cat["paquetes"] if x["clave"] == "basico")
    e = {"paquete_id": basico["id"], "modulos": ["academia"], "bloques_extra": bloques}
    cot = plataforma.c.post(f"{R}/cotizaciones", headers=plataforma.h, json={"contacto": "Ana", "despacho": "Org", "email": "a@org.test", "entrada": e}).json()
    plataforma.c.post(f"{R}/cotizaciones/{cot['id']}/enviar", headers=plataforma.h, json={"confirmacion": "Enviar cotización", "manual": True})
    r = plataforma.c.post(f"{R}/cotizaciones/{cot['id']}/convertir", headers=plataforma.h,
                          json={"organizacion_id": org.org_id, "promocional": True, "motivo": "Piloto aprobado", "confirmo": True})
    assert r.status_code == 200, r.text


def test_academia_usa_el_almacenamiento_contratado(org, plataforma, monkeypatch):
    activar(plataforma, org, "academia")
    e = org.c.get("/api/academia/admin/cursos", headers=org.h).json()["espacio"]
    assert e["alcance"] == "academia" and e["cuota_mb"] == 2048  # sin plan: espacio general de Academia
    _asignar(plataforma, org)
    e = org.c.get("/api/academia/admin/cursos", headers=org.h).json()["espacio"]
    assert e["alcance"] == "despacho" and e["cuota_mb"] == 10 * 1024  # Básico: 10 GB para todo el despacho
    import shutil
    shutil.rmtree(almacen.carpeta(org.org_id), ignore_errors=True)  # archivos que dejaron otras pruebas
    monkeypatch.setattr(almacen, "GB", 10 * 1024)  # 10 «GB» = 100 KB para probar el límite
    c = curso(org, titulo="Con video")
    c = leccion(org, c["modulos"][0]["id"], titulo="Clase")
    lid = c["modulos"][0]["lecciones"][0]["id"]
    assert org.c.post(f"/api/academia/admin/lecciones/{lid}/video", headers=org.h, files={"archivo": ("a.mp4", MP4, "video/mp4")}).status_code == 200
    r = org.c.post(f"/api/academia/admin/lecciones/{lid}/video", headers=org.h, files={"archivo": ("b.mp4", MP4 * 8, "video/mp4")})
    assert r.status_code == 413 and "almacenamiento adicional" in r.json()["detail"]
    # el archivo rechazado no se queda en disco
    assert almacen.uso_bytes(org.org_id, fresco=True) < 2 * len(MP4)
    # la vista de Nomira ve el uso por despacho (solo tamaños)
    d = plataforma.c.get(f"{R}/almacenamiento", headers=plataforma.h).json()["disco"]
    fila = next(o for o in d["organizaciones"] if o["id"] == org.org_id)
    assert fila["contratado_gb"] == 10 and fila["usado_mb"] >= 0 and d["contratado_gb"] >= 10 and d["ampliar"] is True
