"""Nomira Academia: independencia, cursos de Nomira y del despacho, publicación con revisión humana,
asignación a personas y equipos, avance guardado y retomado, actividades, cuestionario con
calificación mínima, constancia de participación, vigencia del contenido, historial al actualizar o
archivar, reporte y aislamiento entre organizaciones."""
from datetime import date, timedelta

import pytest

from app import models as m

from .test_evidencia import activar


@pytest.fixture
def ac(org, plataforma):
    activar(plataforma, org, "academia")
    return org


def curso(o, **kw):
    r = o.c.post("/api/academia/admin/cursos", headers=o.h, json={"titulo": "Atención de clientes ISSSTE", "materia": "ISSSTE",
                                                                  "roles": ["Abogados"], "duracion_min": 30, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def leccion(o, mid, **kw):
    r = o.c.post(f"/api/academia/admin/modulos/{mid}/lecciones", headers=o.h, json={"titulo": "Lección", "texto": "Contenido", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def armado(o, minima=None):
    """Curso con dos lecciones (una con actividad) y, si hay mínima, dos preguntas."""
    c = curso(o, calificacion_minima=minima)
    mid = c["modulos"][0]["id"]
    leccion(o, mid, titulo="Bienvenida", video_url="https://www.youtube.com/watch?v=abcdefghijk", transcripcion="Texto del video",
            recursos=[{"titulo": "Guía", "url": "https://ejemplo.test/guia"}])
    c = leccion(o, mid, titulo="Comprobación", actividad={"pregunta": "¿Quién evalúa el caso?", "opciones": ["El sistema", "El abogado"],
                                                          "correcta": 1, "explicacion": "Siempre el abogado."})
    if minima:
        for t in ("Pregunta 1", "Pregunta 2"):
            o.c.post(f"/api/academia/admin/cursos/{c['id']}/preguntas", headers=o.h, json={"texto": t, "opciones": ["A", "B"], "correcta": 0})
    r = o.c.post(f"/api/academia/admin/cursos/{c['id']}/publicar", headers=o.h, json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_modulo_independiente_y_cursos_de_nomira(org, plataforma):
    assert org.c.get("/api/academia/inicio", headers=org.h).status_code == 403
    activar(plataforma, org, "academia")
    org.c.patch("/api/organizacion/modulos/nomina", headers=org.h, json={"activo": False})
    r = org.c.get("/api/academia/inicio", headers=org.h).json()
    nomira = [c for c in r["disponibles"] if c["origen"] == "nomira"]
    assert len(nomira) >= 3 and all(c["instructor"] and c["actualizado_en"] and c["modalidad_texto"] and c["duracion_min"] for c in nomira)
    # los cursos de Nomira no se editan; se pueden duplicar para adaptarlos
    cid = nomira[0]["id"]
    assert org.c.patch(f"/api/academia/admin/cursos/{cid}", headers=org.h, json={"titulo": "Mío"}).status_code == 409
    copia = org.c.post(f"/api/academia/admin/cursos/{cid}/duplicar", headers=org.h).json()
    assert copia["origen"] == "despacho" and copia["estado"] == "borrador" and copia["modulos"][0]["lecciones"]


def test_flujo_completo_crear_asignar_avanzar_constancia(ac, db):
    analista = ac.usuario("analista", "abogada@org1.test")
    c = armado(ac, minima=50)
    # borrador no visible para participantes; publicado sí
    uid = next(u["id"] for u in ac.c.get("/api/academia/equipo", headers=ac.h).json()["usuarios"] if u["nombre"] == "Analista")
    r = ac.c.post("/api/academia/asignaciones", headers=ac.h, json={"curso_id": c["id"], "usuario_ids": [uid], "tipo": "obligatorio",
                                                                    "fecha_sugerida": (date.today() + timedelta(days=7)).isoformat()})
    assert r.json()["creadas"] == 1
    assert ac.c.post("/api/academia/asignaciones", headers=analista, json={"curso_id": c["id"], "usuario_ids": [uid]}).status_code == 403
    ini = ac.c.get("/api/academia/inicio", headers=analista).json()
    a = next(x for x in ini["asignados"] if x["id"] == c["id"])
    assert a["asignacion"]["tipo"] == "obligatorio" and a["progreso"]["estado"] == "sin_iniciar" and ini["resumen"]["obligatorios_pendientes"] == 1
    # iniciar y guardar avance automáticamente
    r = ac.c.post(f"/api/academia/cursos/{c['id']}/iniciar", headers=analista).json()
    l1 = ac.c.get(f"/api/academia/lecciones/{r['leccion_id']}", headers=analista).json()
    assert l1["video_embebido"].startswith("https://www.youtube-nocookie.com/embed/") and l1["transcripcion"] and l1["recursos"]
    ac.c.put(f"/api/academia/lecciones/{l1['id']}/avance", headers=analista, json={"posicion": 420})
    assert ac.c.get(f"/api/academia/lecciones/{l1['id']}", headers=analista).json()["posicion"] == 420
    x = ac.c.post(f"/api/academia/lecciones/{l1['id']}/completar", headers=analista).json()
    assert x["completado"] is False and x["siguiente_id"] == l1["siguiente_id"]
    # retomar: «continuar» lleva a donde se quedó
    ac.c.get(f"/api/academia/lecciones/{x['siguiente_id']}", headers=analista)
    ini = ac.c.get("/api/academia/inicio", headers=analista).json()
    assert ini["continuar"][0]["id"] == c["id"] and ini["continuar"][0]["progreso"]["porcentaje"] > 0
    assert ac.c.post(f"/api/academia/cursos/{c['id']}/iniciar", headers=analista).json()["leccion_id"] == x["siguiente_id"]
    # la actividad se responde antes de continuar
    l2 = x["siguiente_id"]
    assert ac.c.post(f"/api/academia/lecciones/{l2}/completar", headers=analista).status_code == 422
    r = ac.c.post(f"/api/academia/lecciones/{l2}/actividad", headers=analista, json={"respuesta": 0}).json()
    assert r["correcta"] is False and r["explicacion"] == "Siempre el abogado."
    x = ac.c.post(f"/api/academia/lecciones/{l2}/completar", headers=analista).json()
    assert x["ir_a_cuestionario"] is True and x["completado"] is False
    # cuestionario con calificación mínima
    q = ac.c.get(f"/api/academia/cursos/{c['id']}/cuestionario", headers=analista).json()
    assert "correcta" not in str(q["preguntas"])
    ids = [p["id"] for p in q["preguntas"]]
    r = ac.c.post(f"/api/academia/cursos/{c['id']}/cuestionario", headers=analista, json={"respuestas": {str(ids[0]): 1, str(ids[1]): 1}}).json()
    assert (r["calificacion"], r["aprobado"], r["completado"]) == (0, False, False)
    r = ac.c.post(f"/api/academia/cursos/{c['id']}/cuestionario", headers=analista, json={"respuestas": {str(ids[0]): 0, str(ids[1]): 1}}).json()
    assert (r["calificacion"], r["aprobado"], r["completado"]) == (50, True, True)
    # constancia de participación
    pdf = ac.c.get(f"/api/academia/constancias/{r['avance_id']}", headers=analista)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    ac.usuario("consulta", "otro@org1.test")
    otro = ac.c.post("/api/auth/login", json={"email": "otro@org1.test", "contrasena": "Contrasena-Segura-1"}).json()["token"]
    assert ac.c.get(f"/api/academia/constancias/{r['avance_id']}", headers={"Authorization": f"Bearer {otro}"}).status_code == 404
    assert ac.c.get(f"/api/academia/constancias/{r['avance_id']}", headers=ac.h).status_code == 200  # el administrador sí
    # el administrador consulta el avance y descarga el reporte
    eq = ac.c.get("/api/academia/equipo", headers=ac.h).json()
    fila = next(p for p in eq["personas"] if p["nombre"] == "Analista")
    assert fila["completados"] == 1 and fila["cursos"][str(c["id"])]["folio"].startswith("NA-")
    pc = next(x for x in eq["por_curso"] if x["id"] == c["id"])
    assert (pc["asignados"], pc["completados"]) == (1, 1)
    xl = ac.c.get("/api/academia/reportes/excel", headers=ac.h)
    assert xl.status_code == 200 and xl.headers["content-type"].startswith("application/vnd.openxml")
    assert db.query(m.Auditoria).filter_by(accion="ac_curso_completado").count() == 1


def test_actualizar_o_archivar_no_borra_historial(ac, db):
    c = armado(ac)
    r = ac.c.post(f"/api/academia/cursos/{c['id']}/iniciar", headers=ac.h).json()
    lid = r["leccion_id"]
    ac.c.post(f"/api/academia/lecciones/{lid}/completar", headers=ac.h)
    sig = ac.c.get(f"/api/academia/lecciones/{lid}", headers=ac.h).json()["siguiente_id"]
    ac.c.post(f"/api/academia/lecciones/{sig}/actividad", headers=ac.h, json={"respuesta": 1})
    x = ac.c.post(f"/api/academia/lecciones/{sig}/completar", headers=ac.h).json()
    assert x["completado"] is True  # sin calificación mínima: basta con las lecciones
    folio = db.query(m.AcAvance).one().constancia_folio
    v = c["version"]
    # agregar una lección nueva y archivar otra: la constancia y el avance se conservan
    c2 = leccion(ac, c["modulos"][0]["id"], titulo="Nueva lección")
    assert c2["version"] > v
    ac.c.delete(f"/api/academia/admin/lecciones/{lid}", headers=ac.h)
    d = ac.c.get(f"/api/academia/cursos/{c['id']}", headers=ac.h).json()
    assert d["progreso"]["estado"] == "completado" and d["constancia_folio"] == folio and d["completado_version_anterior"] is True
    ac.c.post(f"/api/academia/admin/cursos/{c['id']}/archivar", headers=ac.h)
    db.expire_all()
    av = db.query(m.AcAvance).one()
    assert av.constancia_folio == folio and av.curso_titulo == "Atención de clientes ISSSTE"
    assert ac.c.get(f"/api/academia/constancias/{av.id}", headers=ac.h).status_code == 200
    assert c["id"] not in [x["id"] for x in ac.c.get("/api/academia/cursos", headers=ac.h).json()["cursos"]]
    assert c["id"] in [x["id"] for x in ac.c.get("/api/academia/inicio", headers=ac.h).json()["completados"]]


def test_contenido_juridico_revision_humana_y_vigencia(ac, db):
    c = curso(ac, juridico=True, asistido_ia=True)
    leccion(ac, c["modulos"][0]["id"])
    r = ac.c.post(f"/api/academia/admin/cursos/{c['id']}/publicar", headers=ac.h, json={})
    assert r.status_code == 422 and "revisó" in r.json()["detail"]
    r = ac.c.post(f"/api/academia/admin/cursos/{c['id']}/publicar", headers=ac.h, json={"revisado": True}).json()
    assert r["revisado_por"] == "Admin 1" and r["estado"] == "publicado"
    # marcar para revisión: aviso visible, deja de recomendarse y no se puede asignar
    ac.c.patch(f"/api/academia/admin/cursos/{c['id']}", headers=ac.h, json={"requiere_revision": True, "nota_revision": "Cambió la ley"})
    det = ac.c.get(f"/api/academia/cursos/{c['id']}", headers=ac.h).json()
    assert det["aviso_vigencia"] == "Cambió la ley" and det["vigente"] is False
    assert c["id"] not in [x["id"] for x in ac.c.get("/api/academia/inicio", headers=ac.h).json()["disponibles"]]
    r = ac.c.post("/api/academia/asignaciones", headers=ac.h, json={"curso_id": c["id"], "usuario_ids": [ac.usuario_id]})
    assert r.status_code == 409
    # material jurídico sin actualizar en más de un año
    ac.c.patch(f"/api/academia/admin/cursos/{c['id']}", headers=ac.h, json={"requiere_revision": False})
    x = db.get(m.AcCurso, c["id"])
    x.contenido_actualizado_en = m.ahora() - timedelta(days=400)
    db.commit()
    assert "más de un año" in ac.c.get(f"/api/academia/cursos/{c['id']}", headers=ac.h).json()["aviso_vigencia"]
    # la calificación mínima exige preguntas
    c3 = curso(ac, titulo="Con mínima", calificacion_minima=80)
    leccion(ac, c3["modulos"][0]["id"])
    assert ac.c.post(f"/api/academia/admin/cursos/{c3['id']}/publicar", headers=ac.h, json={}).status_code == 422


def test_equipos_instructores_permisos_y_aislamiento(ac, org2, plataforma, db):
    analista = ac.usuario("analista", "instructora@org1.test")
    consulta = ac.usuario("consulta", "participante@org1.test")
    assert ac.c.post("/api/academia/admin/cursos", headers=analista, json={"titulo": "Mi curso", "materia": "AFORE"}).status_code == 403
    eq = ac.c.get("/api/academia/equipo", headers=ac.h).json()
    ids = {u["nombre"]: u["id"] for u in eq["usuarios"]}
    assert ac.c.put("/api/academia/instructores", headers=ac.h, json={"usuario_ids": [ids["Consulta"]]}).status_code == 422
    ac.c.put("/api/academia/instructores", headers=ac.h, json={"usuario_ids": [ids["Analista"]]})
    c = ac.c.post("/api/academia/admin/cursos", headers=analista, json={"titulo": "Proceso interno AFORE", "materia": "AFORE"}).json()
    lid = leccion(ac, c["modulos"][0]["id"], titulo="Paso 1", sesion_url="https://meet.ejemplo.test/abc")["modulos"][0]["lecciones"][0]["id"]
    assert ac.c.post(f"/api/academia/admin/cursos/{c['id']}/publicar", headers=analista, json={}).status_code == 200
    assert ac.c.get("/api/academia/equipo", headers=analista).status_code == 200
    assert ac.c.get("/api/academia/reportes/excel", headers=analista).status_code == 403
    # enlaces inseguros rechazados; no se simula una integración de video
    r = ac.c.patch(f"/api/academia/admin/lecciones/{lid}", headers=analista, json={"video_url": "javascript:alert(1)"})
    assert r.status_code == 422
    # equipo: la asignación llega a sus miembros, incluso a quien se agrega después
    e = ac.c.post("/api/academia/equipos", headers=ac.h, json={"nombre": "Litigio", "usuario_ids": [ids["Consulta"]]}).json()
    ac.c.post("/api/academia/asignaciones", headers=ac.h, json={"curso_id": c["id"], "equipo_ids": [e["id"]], "tipo": "recomendado"})
    assert [x["asignacion"]["tipo"] for x in ac.c.get("/api/academia/inicio", headers=consulta).json()["asignados"]] == ["recomendado"]
    ac.c.put(f"/api/academia/equipos/{e['id']}", headers=ac.h, json={"nombre": "Litigio", "usuario_ids": [ids["Consulta"], ids["Admin 1"]]})
    assert len(ac.c.get("/api/academia/inicio", headers=ac.h).json()["asignados"]) == 1
    # una asignación directa obligatoria gana a la recomendada del equipo
    ac.c.post("/api/academia/asignaciones", headers=ac.h, json={"curso_id": c["id"], "usuario_ids": [ids["Consulta"]], "tipo": "obligatorio"})
    assert ac.c.get("/api/academia/inicio", headers=consulta).json()["asignados"][0]["asignacion"]["tipo"] == "obligatorio"
    # retirar conserva el historial
    asig = ac.c.get("/api/academia/equipo", headers=ac.h).json()["asignaciones"]
    ac.c.delete(f"/api/academia/asignaciones/{asig[0]['id']}", headers=ac.h)
    assert any(a["retirada_en"] for a in ac.c.get("/api/academia/equipo", headers=ac.h).json()["asignaciones"])
    # sesiones en vivo: solo un enlace, sin simular una integración
    ac.c.post(f"/api/academia/admin/cursos/{c['id']}/sesiones", headers=ac.h, json={
        "titulo": "Sesión de dudas", "inicio": (m.ahora() + timedelta(days=2)).isoformat(), "enlace": "https://meet.ejemplo.test/xyz"})
    assert ac.c.get("/api/academia/inicio", headers=consulta).json()["sesiones"][0]["titulo"] == "Sesión de dudas"
    # aislamiento: otro despacho no ve cursos internos
    activar(plataforma, org2, "academia")
    assert org2.c.get(f"/api/academia/cursos/{c['id']}", headers=org2.h).status_code == 404
    assert c["id"] not in [x["id"] for x in org2.c.get("/api/academia/cursos", headers=org2.h).json()["cursos"]]
    assert org2.c.post(f"/api/academia/cursos/{c['id']}/iniciar", headers=org2.h).status_code == 404
    assert db.query(m.Auditoria).filter_by(accion="ac_curso_asignado").count() == 2


def test_material_descargable(ac):
    c = curso(ac)
    c = leccion(ac, c["modulos"][0]["id"], titulo="Con PDF")
    lid = c["modulos"][0]["lecciones"][0]["id"]
    r = ac.c.post(f"/api/academia/admin/lecciones/{lid}/archivo", headers=ac.h, files={"archivo": ("guia.pdf", b"%PDF-1.4 prueba", "application/pdf")})
    assert r.status_code == 200 and r.json()["modulos"][0]["lecciones"][0]["archivo"]["nombre"] == "guia.pdf"
    bad = ac.c.post(f"/api/academia/admin/lecciones/{lid}/archivo", headers=ac.h, files={"archivo": ("x.pdf", b"MZ ejecutable", "application/pdf")})
    assert bad.status_code == 415
    assert ac.c.get(f"/api/academia/lecciones/{lid}/archivo", headers=ac.h).content.startswith(b"%PDF")
