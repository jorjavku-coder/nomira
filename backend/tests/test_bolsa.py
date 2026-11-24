"""Bolsa de trabajo: vacantes (gratis), filtro de requisitos discriminatorios, portal y página por despacho, postulación con CV,
aislamiento, pruebas premium con enlace secreto, calificación (opción múltiple y cinco factores), pruebas propias y borrado ARCO."""
from datetime import datetime, timedelta, timezone

import pymupdf

from app import models as m
from app.services.bolsa import pruebas as pb

from .test_evidencia import activar

B = "/api/bolsa"
E = "/api/empleos"


def pdf():
    d = pymupdf.open()
    d.new_page().insert_text((50, 72), "Curriculum")
    return d.tobytes()


VAC = {"titulo": "Abogado(a) laboralista", "area": "laboral", "puesto": "abogado", "jornada": "completa", "modalidad": "hibrido",
       "estado_republica": "Ciudad de México", "ciudad": "Benito Juárez", "sueldo_min": "18000", "sueldo_max": "25000", "mostrar_sueldo": True,
       "descripcion": "Llevar juicios laborales de la parte trabajadora ante tribunales y centros de conciliación.",
       "requisitos": "Cédula profesional. 2 años de experiencia en litigio laboral.", "ofrecemos": "Prestaciones de ley y capacitación."}


def publicar(o, **kw):
    r = o.c.post(f"{B}/vacantes", headers=o.h, json={**VAC, **kw})
    assert r.status_code == 201, r.text
    v = r.json()
    assert o.c.post(f"{B}/vacantes/{v['id']}/estado", headers=o.h, json={"estado": "publicada"}).json()["estado"] == "publicada"
    return v


def postular(cliente, codigo, **kw):
    datos = {"nombre": "Ana López Ruiz", "email": "ana@candidata.test", "telefono": "5512345678", "experiencia": "1-3", "acepto": "true",
             "cedula": "12345678", **kw}
    return cliente.post(f"{E}/vacante/{codigo}/postular", data=datos, files={"cv": ("cv ana.pdf", pdf(), "application/pdf")})


def test_vacante_portal_y_postulacion(org, org2, cliente, db):
    r = org.c.post(f"{B}/vacantes", headers=org.h, json={**VAC, "requisitos": "Edad entre 25 y 35 años, buena presentación"})
    assert r.status_code == 422 and "discriminatorios" in r.json()["detail"]
    v = org.c.post(f"{B}/vacantes", headers=org.h, json=VAC).json()
    assert v["estado"] == "borrador"
    assert cliente.get(f"{E}/vacante/{v['codigo']}").status_code == 404  # borrador: no es pública
    org.c.post(f"{B}/vacantes/{v['id']}/estado", headers=org.h, json={"estado": "publicada"})
    oculta = publicar(org, titulo="Pasante de amparo", area="amparo", puesto="pasante", en_portal=False, mostrar_sueldo=False)
    portal = cliente.get(E).json()
    assert [x["codigo"] for x in portal["vacantes"]] == [v["codigo"]]  # la que no va al portal no aparece
    assert portal["vacantes"][0]["despacho"]["nombre"] and "id" not in portal["vacantes"][0]
    assert cliente.get(E, params={"texto": "laborales"}).json()["total"] == 1 and cliente.get(E, params={"area": "civil"}).json()["total"] == 0
    cfg = org.c.get(f"{B}/config", headers=org.h).json()
    pagina = cliente.get(f"{E}/despacho/{cfg['perfil']['codigo']}").json()
    assert {x["codigo"] for x in pagina["vacantes"]} == {v["codigo"], oculta["codigo"]}  # su página muestra todas
    assert next(x for x in pagina["vacantes"] if x["codigo"] == oculta["codigo"])["sueldo_min"] is None
    # postular
    assert postular(cliente, v["codigo"], acepto="false").status_code == 422
    r = postular(cliente, v["codigo"])
    assert r.status_code == 201 and r.json() == {"ok": True}
    assert postular(cliente, v["codigo"], email="ANA@candidata.test").json().get("repetida")  # no se duplica
    assert postular(cliente, v["codigo"], email="robot@x.test", sitio_web="spam").status_code == 201  # campo trampa
    malo = cliente.post(f"{E}/vacante/{v['codigo']}/postular", data={"nombre": "Luis", "email": "luis@x.test", "acepto": "true"},
                        files={"cv": ("cv.exe", b"MZ\x90\x00", "application/octet-stream")})
    assert malo.status_code == 422
    det = org.c.get(f"{B}/vacantes/{v['id']}", headers=org.h).json()
    assert [c["nombre"] for c in det["candidatos"]] == ["Ana López Ruiz"]
    cid = det["candidatos"][0]["id"]
    assert org.c.get(f"{B}/candidatos/{cid}/cv", headers=org.h).content.startswith(b"%PDF")
    assert org2.c.get(f"{B}/candidatos/{cid}", headers=org2.h).status_code == 404  # aislamiento
    assert org2.c.get(f"{B}/vacantes/{v['id']}", headers=org2.h).status_code == 404
    e = org.c.put(f"{B}/candidatos/{cid}", headers=org.h, json={"etapa": "entrevista", "calificacion": 4, "notas": "Buen perfil"}).json()
    assert e["etapa"] == "entrevista" and e["calificacion"] == 4
    aud = db.query(m.Auditoria).filter_by(accion="bolsa_candidato").one()
    assert "Buen perfil" not in str(aud.detalle)
    # cerrada: deja de recibir
    org.c.post(f"{B}/vacantes/{v['id']}/estado", headers=org.h, json={"estado": "cerrada"})
    assert postular(cliente, v["codigo"], email="otra@x.test").status_code == 409
    assert cliente.get(E).json()["total"] == 0


def test_despacho_suspendido_no_se_muestra(org, cliente, db):
    v = publicar(org)
    db.get(m.Organizacion, org.org_id).estado = "suspendida"
    db.commit()
    assert cliente.get(E).json()["total"] == 0 and cliente.get(f"{E}/vacante/{v['codigo']}").status_code == 404


def _enlace(o, cid, pruebas):
    r = o.c.post(f"{B}/candidatos/{cid}/pruebas", headers=o.h, json={"pruebas": pruebas})
    assert r.status_code == 201, r.text
    return [x["url"].rsplit("/", 1)[-1] for x in r.json()["enlaces"]], r.json()["enlaces"]


def test_pruebas_premium(org, plataforma, cliente, db):
    v = publicar(org)
    postular(cliente, v["codigo"])
    cid = org.c.get(f"{B}/vacantes/{v['id']}", headers=org.h).json()["candidatos"][0]["id"]
    cat = org.c.get(f"{B}/pruebas", headers=org.h).json()
    assert cat["premium"] is False and {p["clave"] for p in cat["nomira"]} >= {"big5", "numerico", "verbal", "atencion", "laboral", "amparo", "civil"}
    assert org.c.post(f"{B}/candidatos/{cid}/pruebas", headers=org.h, json={"pruebas": ["numerico"]}).status_code == 402  # sin módulo
    activar(plataforma, org, "psicometria")
    (t_num, t_big), enlaces = _enlace(org, cid, ["numerico", "big5"])
    # el candidato no ve respuestas antes de iniciar ni las correctas nunca
    info = cliente.get(f"/api/prueba/{t_num}").json()
    assert info["estado"] == "enviada" and "preguntas" not in info["prueba"] and info["prueba"]["n"] == 12
    assert cliente.post(f"/api/prueba/{t_num}/iniciar", json={"acepto": False}).status_code == 422
    inicio = cliente.post(f"/api/prueba/{t_num}/iniciar", json={"acepto": True}).json()
    assert "correcta" not in str(inicio["prueba"]["preguntas"])
    correctas = [q["correcta"] for q in pb.NUMERICO]
    respuestas = correctas[:9] + [(c + 1) % 4 for c in correctas[9:]]  # 9 de 12
    assert cliente.post(f"/api/prueba/{t_num}/responder", json={"respuestas": respuestas}).json() == {"ok": True}
    assert cliente.post(f"/api/prueba/{t_num}/responder", json={"respuestas": respuestas}).status_code == 409  # una sola vez
    r = org.c.get(f"{B}/aplicaciones/{enlaces[0]['id']}", headers=org.h).json()
    assert r["estado"] == "terminada" and r["resultado"]["aciertos"] == 9 and r["resultado"]["porcentaje"] == 75
    # cinco factores: todo «muy de acuerdo» da 50 % en cada factor (mitad directos, mitad inversos no siempre): solo validamos estructura y rango
    cliente.post(f"/api/prueba/{t_big}/iniciar", json={"acepto": True})
    cliente.post(f"/api/prueba/{t_big}/responder", json={"respuestas": [4] * 50})
    perfil = org.c.get(f"{B}/aplicaciones/{enlaces[1]['id']}", headers=org.h).json()["resultado"]
    assert perfil["tipo"] == "perfil" and len(perfil["factores"]) == 5 and all(0 <= f["porcentaje"] <= 100 for f in perfil["factores"])
    assert cliente.get("/api/prueba/token-falso").status_code == 404
    # vencida
    (t3,), _ = _enlace(org, cid, ["verbal"])
    a = db.query(m.BtAplicacion).filter_by(prueba="verbal").one()
    a.vence_en = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert cliente.get(f"/api/prueba/{t3}").json()["estado"] == "vencida"
    assert cliente.post(f"/api/prueba/{t3}/iniciar", json={"acepto": True}).status_code == 409
    # borrar candidato (ARCO): se van datos, CV y pruebas
    assert org.c.delete(f"{B}/candidatos/{cid}", headers=org.h).json() == {"ok": True}
    assert db.query(m.BtAplicacion).count() == 0 and cliente.get(f"/api/prueba/{t_num}").status_code == 404


def test_calificacion_cinco_factores():
    # respuestas que maximizan cada factor: 4 en directos, 0 en inversos
    resp = [4 if signo > 0 else 0 for _, _, signo in pb._BIG5]
    r = pb.calificar(pb.PRUEBAS["big5"], resp)
    assert all(f["porcentaje"] == 100 and f["nivel"] == "alto" for f in r["factores"])
    r = pb.calificar(pb.PRUEBAS["big5"], [2] * 50)
    assert all(f["porcentaje"] == 50 and f["nivel"] == "medio" for f in r["factores"])
    assert sum(1 for _, f, _ in pb._BIG5 if f == "C") == 10 and len(pb._BIG5) == 50
    for p in pb.PRUEBAS.values():  # toda pregunta de opción múltiple tiene una correcta válida
        for q in p["preguntas"]:
            if p["tipo"] == "opcion":
                assert 0 <= q["correcta"] < len(q["opciones"])


def test_pruebas_propias(org, org2, plataforma, cliente):
    activar(plataforma, org, "psicometria")
    cuerpo = {"nombre": "Examen de redacción", "minutos": 20, "preguntas": [
        {"texto": "¿Qué artículo de la LFT regula las vacaciones?", "opciones": ["76", "123"], "correcta": 0},
        {"texto": "Redacte un párrafo de un escrito inicial."}]}
    assert org.c.post(f"{B}/pruebas/propias", headers=org.h, json={**cuerpo, "preguntas": [{"texto": "Sin correcta", "opciones": ["a", "b"]}]}).status_code == 422
    p = org.c.post(f"{B}/pruebas/propias", headers=org.h, json=cuerpo).json()
    copia = org.c.post(f"{B}/pruebas/copiar/laboral", headers=org.h).json()
    assert org.c.get(f"{B}/pruebas/ver/{copia['clave']}", headers=org.h).json()["preguntas"][0]["correcta"] == pb.LABORAL[0]["correcta"]
    assert org2.c.get(f"{B}/pruebas/ver/{p['clave']}", headers=org2.h).status_code == 404
    v = publicar(org)
    postular(cliente, v["codigo"])
    cid = org.c.get(f"{B}/vacantes/{v['id']}", headers=org.h).json()["candidatos"][0]["id"]
    (t,), enl = _enlace(org, cid, [p["clave"]])
    cliente.post(f"/api/prueba/{t}/iniciar", json={"acepto": True})
    cliente.post(f"/api/prueba/{t}/responder", json={"respuestas": [0, "Comparece ante este H. Tribunal…"]})
    r = org.c.get(f"{B}/aplicaciones/{enl[0]['id']}", headers=org.h).json()["resultado"]
    assert r["aciertos"] == 1 and r["total"] == 1 and r["abiertas"][0]["respuesta"].startswith("Comparece")
    # usada: borrar la desactiva para conservar los resultados
    assert org.c.delete(f"{B}/pruebas/propias/{p['id']}", headers=org.h).json()["desactivada"] is True
