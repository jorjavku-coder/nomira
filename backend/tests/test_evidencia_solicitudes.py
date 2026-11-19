"""Evidencia: datos atómicos, fecha del documento ≠ fecha del evento, posibles contradicciones solo
del mismo dato (demo ficticia del divorcio de Laura) y solicitud segura de documentos al cliente."""
import re
import shutil
from datetime import timedelta

import pytest

from app import models as m
from app.config import ajustes
from app.services import correo
from app.services.evidencia import demo, solicitudes as sol

from .test_evidencia import CONTRATO, activar, asunto, panel, subir

DIV = demo.documentos_divorcio()
ENTREVISTA, CONVENIO, CONVERSACION = (DIV["entrevista_inicial_ficticia.pdf"], DIV["borrador_convenio_ficticio.pdf"],
                                      DIV["conversacion_simulada_ficticia.png"])
requiere_ocr = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract no está instalado")


@pytest.fixture
def ev(org, plataforma):
    activar(plataforma, org, "evidencia")
    return org


@pytest.fixture
def buzon(monkeypatch):
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto: enviados.append(
        {"para": dest, "asunto": asunto, "html": html, "texto": texto}))
    monkeypatch.setattr(ajustes(), "url_publica", "https://nomirasoft.com")
    return enviados


# ---------- extracción atómica y contradicciones (demo de Laura) ----------

@requiere_ocr
def test_demo_laura_distingue_fechas_y_solo_compara_el_mismo_dato(ev):
    aid = asunto(ev, nombre="Divorcio de Laura")
    subir(ev, aid, ("entrevista.pdf", ENTREVISTA), ("convenio.pdf", CONVENIO), ("conversacion.png", CONVERSACION))
    p = panel(ev, aid)
    doc = {d["nombre"]: d["id"] for d in p["documentos"]}
    hs = p["hechos"]
    de = lambda n: [h for h in hs if h["documento_id"] == doc[n]]  # noqa: E731

    # Separación: 10 de enero (entrevista) y 12 de enero (convenio y conversación), como fecha del EVENTO
    sep = {(h["documento_id"], h["fecha"]) for h in hs if h["tema"] == "separacion"}
    assert sep == {(doc["entrevista.pdf"], "2026-01-10"), (doc["convenio.pdf"], "2026-01-12"),
                   (doc["conversacion.png"], "2026-01-12")}
    # Las tres las afirma una persona: la clienta (entrevista), las partes (borrador) y Laura (mensajes)
    assert {h["tipo_dato"] for h in hs if h["tema"] == "separacion"} == {"fecha_mencionada"}
    atrib = {h["documento_id"]: h["atribucion"] for h in hs if h["tema"] == "separacion"}
    assert atrib[doc["entrevista.pdf"]] == "La cliente indica" and atrib[doc["conversacion.png"]] == "Laura escribe"
    assert atrib[doc["convenio.pdf"]].startswith("El borrador propone")
    # El 12 de febrero es la fecha del borrador, no un evento; texto original y normalizado por separado
    borrador = next(h for h in de("convenio.pdf") if h["fecha"] == "2026-02-12")
    assert (borrador["tipo_dato"], borrador["valor_original"], borrador["valor"]) == \
        ("fecha_documento", "12 de febrero de 2026", "12 feb 2026")
    # Lugar, fecha del borrador y estado del documento: tres propuestas distintas, no una
    tipos = {h["tipo_dato"]: h for h in de("convenio.pdf")}
    assert tipos["lugar"]["valor"] == "Toluca, Estado de México" and "2026" not in tipos["lugar"]["descripcion"]
    assert "borrador" in tipos["administrativo"]["valor"] and "Toluca" not in tipos["administrativo"]["descripcion"]
    assert "Toluca" not in borrador["descripcion"] and "Estado del documento" not in borrador["descripcion"]
    # La nota editorial y los títulos no son hechos del caso
    assert not any("nota" in h["descripcion"].lower() or "no equivale" in h["descripcion"] for h in hs)
    assert not any(h["descripcion"].isupper() for h in hs)
    # Cada propuesta tiene documento, página y fragmento; la conversación (OCR) trae confianza
    assert all(h["documento_id"] and h["pagina"] and h["fragmento"] for h in hs)
    assert all("OCR" in h["calidad"]["lectura"] for h in de("conversacion.png"))
    assert all("confianza" not in h for h in hs)  # sin porcentajes que parezcan certeza
    assert next(h for h in de("entrevista.pdf") if h["tipo_dato"] == "persona")["valor"] == "Laura Ficticia Ramírez"

    # Posibles contradicciones: solo la fecha de separación, entrevista contra cada otra fuente
    entrevista_sep = next(h for h in de("entrevista.pdf") if h["tema"] == "separacion")
    pares = {tuple(sorted(c["hechos"])) for c in p["contradicciones"]}
    otras = [h["id"] for h in hs if h["tema"] == "separacion" and h["id"] != entrevista_sep["id"]]
    assert pares == {tuple(sorted((entrevista_sep["id"], o))) for o in otras}
    assert all(c["tema"] == "separacion" and c["estado"] == "pendiente" and c["difieren"] == ["fecha"]
               for c in p["contradicciones"])
    assert all("10 ene 2026" in c["explicacion"] and "12 ene 2026" in c["explicacion"] for c in p["contradicciones"])
    assert not any(borrador["id"] in c["hechos"] for c in p["contradicciones"])
    assert p["resumen"]["diferencias_pendientes"] == 2  # nunca «0» si hay diferencias sin resolver

    # La persona decide; ningún hecho cambia ni se elige versión, y queda en el historial del asunto
    c1, c2 = p["contradicciones"]
    url = f"/api/evidencia/asuntos/{aid}/diferencias"
    assert ev.c.post(url, headers=ev.h, json={"par": c1["par"], "decision": "contradiccion", "nota": "Pedir aclaración"}).status_code == 200
    assert ev.c.post(url, headers=ev.h, json={"par": c2["par"], "decision": "eventos_distintos"}).status_code == 200
    assert ev.c.post(url, headers=ev.h, json={"par": c2["par"], "decision": "inventada"}).status_code == 422
    p2 = panel(ev, aid)
    dec = {c["par"]: (c["estado"], c["decision_texto"], c["decision"]["por_nombre"]) for c in p2["contradicciones"]}
    assert dec == {c1["par"]: ("resuelta", "Contradicción confirmada", "Admin 1"), c2["par"]: ("resuelta", "Son eventos distintos", "Admin 1")}
    assert p2["resumen"]["diferencias_pendientes"] == 0 and p2["resumen"]["contradicciones"] == 1
    assert {h["id"]: h["estado"] for h in p2["hechos"]} == {h["id"]: h["estado"] for h in hs}
    assert ev.c.post(url, headers=ev.h, json={"par": c2["par"], "decision": None}).status_code == 200
    assert panel(ev, aid)["resumen"]["diferencias_pendientes"] == 1
    hist = ev.c.get(f"/api/evidencia/asuntos/{aid}/historial", headers=ev.h).json()
    assert [x["accion"] for x in hist[:3]] == ["Reabrió una posible diferencia", "Decidió sobre una posible diferencia",
                                               "Decidió sobre una posible diferencia"]
    assert hist[2]["detalle"]["decision"] == "contradiccion" and hist[2]["usuario"] == "Admin 1"
    # Una pareja ajena al asunto no se acepta
    assert ev.c.post(url, headers=ev.h, json={"par": "999998-999999", "decision": "no_aplica"}).status_code == 404

    # Validar la extracción ≠ probar el hecho: etiquetas y fecha del documento fuera de la cronología
    r = ev.c.post(f"/api/evidencia/hechos/{borrador['id']}/confirmar", headers=ev.h).json()
    assert (r["estado"], r["estado_texto"]) == ("confirmado", "Confirmado por una persona")
    ev.c.post(f"/api/evidencia/hechos/{entrevista_sep['id']}/confirmar", headers=ev.h)
    eventos = panel(ev, aid)["cronologia"]["eventos"]
    assert [e["id"] for e in eventos] == [entrevista_sep["id"]] and eventos[0]["contradicciones"]


def test_historial_registra_quien_hizo_cada_cambio(ev):
    aid = asunto(ev)
    subir(ev, aid, ("contrato.pdf", CONTRATO))
    h = next(x for x in panel(ev, aid)["hechos"] if x["tipo_dato"] == "fecha_evento")
    ev.c.post(f"/api/evidencia/hechos/{h['id']}/validar", headers=ev.h)
    r = ev.c.patch(f"/api/evidencia/hechos/{h['id']}", headers=ev.h, json={"fecha": "2020-01-16"}).json()
    assert (r["estado"], r["estado_texto"], r["valor"]) == ("editado", "Editado por una persona", "16 ene 2020")
    hist = ev.c.get(f"/api/evidencia/hechos/{h['id']}/historial", headers=ev.h).json()
    assert [x["accion"] for x in hist] == ["Propuesto automáticamente por Nomira", "Confirmado por una persona", "Editado por una persona"]
    assert hist[1]["usuario"] == "Admin 1"
    assert hist[2]["detalle"]["antes"] == {"fecha": "2020-01-15"} and hist[2]["detalle"]["despues"] == {"fecha": "2020-01-16"}


# ---------- solicitud de documentos al cliente ----------

def _crear(ev, aid, buzon, **kw):
    datos = {"email": "laura@cliente.test", "mensaje": "Hola Laura, necesitamos estos documentos.",
             "documentos": ["Acta de matrimonio", "Actas de nacimiento"], **kw}
    r = ev.c.post(f"/api/evidencia/asuntos/{aid}/solicitudes", headers=ev.h, json=datos)
    assert r.status_code == 201, r.text
    r = r.json()
    token = r["enlace"].split("#", 1)[1]
    return r, token


def _codigo(buzon) -> str:
    return re.search(r"\b(\d{6})\b", buzon[-1]["asunto"])[1]


def test_flujo_completo_de_solicitud(ev, buzon, cliente, db):
    aid = asunto(ev, nombre="Asunto confidencial de Laura")
    subir(ev, aid, ("contrato.pdf", CONTRATO))  # documento previo del despacho: el cliente no debe verlo
    r, token = _crear(ev, aid, buzon)
    assert r["enlace"] == f"https://nomirasoft.com/subir#{token}" and r["correo"]["enviado"]
    s = r["solicitud"]
    assert (s["estado"], s["email"], s["archivos_recibidos"], s["requiere_codigo"]) == ("activa", "laura@cliente.test", 0, True)
    assert s["creado_por"] == "Admin 1" and s["expira_en"] and "token" not in s and "token_hash" not in s
    # Correo al cliente: el enlace, lo que se pide; nada del expediente
    (c,) = buzon
    assert c["para"] == ["laura@cliente.test"] and token in c["html"] and "Acta de matrimonio" in c["html"]
    assert "Asunto confidencial" not in c["html"] + c["texto"] + c["asunto"] and "contrato.pdf" not in c["html"]
    # En la base solo queda la huella del token, nunca el token
    fila = db.query(m.EvSolicitud).one()
    assert fila.token_hash == sol.huella(token) and token not in str(fila.__dict__)
    assert not any(token in str(a.detalle) for a in db.query(m.Auditoria))
    assert not any(token in (x.destinatarios + x.asunto) for x in db.query(m.CorreoEnviado))

    H = {"X-Enlace": token}
    info = cliente.post("/api/subida/estado", headers=H).json()
    assert info["despacho"] == "Org 1" and info["documentos"] == ["Acta de matrimonio", "Actas de nacimiento"]
    assert info["email"] == "l•••a@c•••e.test" and info["requiere_codigo"] and not info["verificado"]
    texto_info = str(info)
    assert "contrato" not in texto_info and "Asunto confidencial" not in texto_info and "hechos" not in texto_info
    # Sin código no puede subir
    f = [("archivos", ("acta.pdf", CONTRATO[:0] + ENTREVISTA, "application/pdf"))]
    assert cliente.post("/api/subida/archivos", headers=H, files=f).status_code == 401
    # Código de un solo uso enviado al correo destinatario
    assert cliente.post("/api/subida/codigo", headers=H).status_code == 200
    codigo = _codigo(buzon)
    assert buzon[-1]["para"] == ["laura@cliente.test"]
    assert cliente.post("/api/subida/codigo", headers=H).status_code == 429  # espera de un minuto
    assert cliente.post("/api/subida/verificar", headers=H, json={"codigo": "000000" if codigo != "000000" else "111111"}).status_code == 422
    sesion = cliente.post("/api/subida/verificar", headers=H, json={"codigo": codigo}).json()["sesion"]
    assert cliente.post("/api/subida/verificar", headers=H, json={"codigo": codigo}).status_code == 409  # ya se usó
    # La sesión de carga no sirve en el panel de clientes ni en el de la plataforma
    assert cliente.get("/api/evidencia/asuntos", headers={"Authorization": f"Bearer {sesion}"}).status_code == 401
    assert cliente.get("/api/plataforma/clientes", headers={"Authorization": f"Bearer {sesion}"}).status_code == 401
    HS = {**H, "X-Sesion": sesion}
    assert cliente.post("/api/subida/estado", headers=HS).json()["verificado"]
    r = cliente.post("/api/subida/archivos", headers=HS, data={"solicitado_como": ["Acta de matrimonio", "Otra cosa"]}, files=[
        ("archivos", ("acta.pdf", ENTREVISTA, "application/pdf")),
        ("archivos", ("foto.jpg", CONVERSACION, "image/jpeg")),       # PNG con extensión .jpg: no coincide
        ("archivos", ("virus.exe", b"MZ\x90\x00" * 100, "application/octet-stream")),
        ("archivos", ("falso.pdf", b"esto no es un pdf", "application/pdf")),
        ("archivos", ("copia.pdf", CONTRATO, "application/pdf")),   # ya existía en el asunto: no se duplica ni se revela
    ])
    assert r.status_code == 201, r.text
    res = {x["nombre"]: x for x in r.json()["resultados"]}
    assert res["acta.pdf"]["aceptado"] and res["copia.pdf"]["aceptado"]
    assert not res["foto.jpg"]["aceptado"] and "extensión" in res["foto.jpg"]["motivo"]
    assert not res["virus.exe"]["aceptado"] and not res["falso.pdf"]["aceptado"]
    assert "contrato" not in str(r.json())
    # Llegó como «recibido»: sin leer, sin hechos; el abogado recibe un aviso
    docs = {d["nombre"]: d for d in panel(ev, aid)["documentos"]}
    acta = docs["acta.pdf"]
    assert (acta["estado"], acta["origen"], acta["hechos"], acta["paginas"]) == ("recibido", "cliente", 0, None)
    assert db.query(m.EvHecho).filter_by(documento_id=acta["id"]).count() == 0
    assert db.query(m.EvPagina).filter_by(documento_id=acta["id"]).count() == 0
    aviso = buzon[-1]
    assert aviso["para"] == ["admin1@org1.test"] and "Asunto confidencial de Laura" in aviso["asunto"]
    assert acta["solicitado_como"] == "Acta de matrimonio"
    info = cliente.post("/api/subida/estado", headers=HS).json()
    assert info["estado_documentos"] == [{"documento": "Acta de matrimonio", "enviados": 1}, {"documento": "Actas de nacimiento", "enviados": 0}]
    assert [x["nombre"] for x in info["mis_envios"]] == ["acta.pdf"] and "pendiente de revisión" in info["mis_envios"][0]["estado"]
    assert cliente.post("/api/subida/estado", headers=H).json()["mis_envios"] == []  # sin verificar no se listan
    p = panel(ev, aid)
    assert p["resumen"]["documentos_recibidos"] == 1 and p["solicitudes"][0]["archivos_recibidos"] == 1
    assert p["solicitudes"][0]["utilizada"] and p["solicitudes"][0]["ultima_carga_en"]
    doc = db.get(m.EvDocumento, acta["id"])
    assert (doc.organizacion_id, doc.asunto_id, doc.nombre_original, doc.subido_por_id) == (ev.org_id, aid, "acta.pdf", None)
    # No se relee ni se procesa hasta aceptarlo
    assert ev.c.post(f"/api/evidencia/documentos/{acta['id']}/reprocesar", headers=ev.h).status_code == 409
    assert ev.c.post(f"/api/evidencia/documentos/{acta['id']}/aceptar", headers=ev.h).status_code == 200
    acta = next(d for d in panel(ev, aid)["documentos"] if d["id"] == acta["id"])
    assert acta["estado"] == "leido" and acta["aceptado_por"] == "Admin 1" and acta["hechos"] > 0
    assert all(h["estado"] == "por_revisar" for h in panel(ev, aid)["hechos"] if h["documento_id"] == acta["id"])
    # Revocar: el enlace deja de funcionar de inmediato
    sid = p["solicitudes"][0]["id"]
    assert ev.c.post(f"/api/evidencia/solicitudes/{sid}/revocar", headers=ev.h).json()["estado"] == "revocada"
    assert cliente.post("/api/subida/estado", headers=H).status_code == 410
    assert cliente.post("/api/subida/archivos", headers=HS, files=f).status_code == 410
    acciones = {a.accion for a in db.query(m.Auditoria)}
    assert {"ev_solicitud_creada", "ev_solicitud_abierta", "ev_solicitud_codigo_enviado", "ev_solicitud_verificada",
            "ev_documento_recibido_cliente", "ev_documento_aceptado", "ev_solicitud_revocada"} <= acciones


def test_enlace_vence_tiene_limites_y_no_sirve_para_otro_asunto(ev, org2, plataforma, buzon, cliente, db):
    aid = asunto(ev)
    _, token = _crear(ev, aid, buzon, requiere_codigo=False, max_archivos=2, dias=1)
    H = {"X-Enlace": token}
    assert cliente.post("/api/subida/estado", headers=H).json()["verificado"]  # sin código, por decisión del abogado
    r = cliente.post("/api/subida/archivos", headers=H, files=[
        ("archivos", (n, d, "application/pdf")) for n, d in (("a.pdf", ENTREVISTA), ("b.pdf", CONVENIO), ("c.pdf", CONTRATO))])
    res = r.json()["resultados"]
    assert [x["aceptado"] for x in res] == [True, True, False] and "máximo" in res[2]["motivo"]
    assert cliente.post("/api/subida/estado", headers=H).json()["estado"] == "completa"
    # Los documentos quedan solo en ESE asunto de ESA organización
    assert {d.asunto_id for d in db.query(m.EvDocumento)} == {aid}
    # Token inexistente o alterado
    assert cliente.post("/api/subida/estado", headers={"X-Enlace": token[:-2] + "xx"}).status_code == 404
    assert cliente.post("/api/subida/estado").status_code == 404
    # Vencido
    s = db.query(m.EvSolicitud).one()
    s.expira_en = m.ahora() - timedelta(minutes=1)
    db.commit()
    assert cliente.post("/api/subida/estado", headers=H).status_code == 410
    assert panel(ev, aid)["solicitudes"][0]["estado"] == "vencida"
    # Validaciones de la solicitud
    for malo in ({"email": "no-es-correo"}, {"email": "a@b.test", "dias": 400}):
        assert ev.c.post(f"/api/evidencia/asuntos/{aid}/solicitudes", headers=ev.h, json=malo).status_code == 422
    # Otra organización no puede revocar ni ver la solicitud; consulta no puede crear
    activar(plataforma, org2, "evidencia")
    assert org2.c.post(f"/api/evidencia/solicitudes/{s.id}/revocar", headers=org2.h).status_code == 404
    assert org2.c.post(f"/api/evidencia/asuntos/{aid}/solicitudes", headers=org2.h, json={"email": "x@y.test"}).status_code == 404


def test_freno_y_codigo_con_intentos_limitados(ev, buzon, cliente, db):
    aid = asunto(ev)
    _, token = _crear(ev, aid, buzon)
    H = {"X-Enlace": token}
    cliente.post("/api/subida/codigo", headers=H)
    codigo = _codigo(buzon)
    malo = "000000" if codigo != "000000" else "111111"
    for _ in range(sol.CODIGO_INTENTOS):
        assert cliente.post("/api/subida/verificar", headers=H, json={"codigo": malo}).status_code == 422
    # Agotó los intentos: ni el código correcto sirve ya
    assert cliente.post("/api/subida/verificar", headers=H, json={"codigo": codigo}).status_code == 409
    # Muchos enlaces inválidos desde la misma IP: se frena
    for _ in range(30):
        cliente.post("/api/subida/estado", headers={"X-Enlace": "x" * 43})
    assert cliente.post("/api/subida/estado", headers=H).status_code == 429


def test_enlace_inutil_si_se_desactiva_el_modulo_o_se_suspende(ev, plataforma, buzon, cliente, db):
    aid = asunto(ev)
    _, token = _crear(ev, aid, buzon, requiere_codigo=False)
    activar(plataforma, ev, "evidencia", contratado=False)
    assert cliente.post("/api/subida/estado", headers={"X-Enlace": token}).status_code == 410
    activar(plataforma, ev, "evidencia")
    o = db.get(m.Organizacion, ev.org_id)
    o.estado = "suspendida"
    db.commit()
    assert cliente.post("/api/subida/estado", headers={"X-Enlace": token}).status_code == 410


def test_correo_en_modo_prueba_no_sale(monkeypatch, tmp_path):
    """Fuera de producción, aunque haya proveedor real configurado, los correos se guardan localmente."""
    import httpx
    a = ajustes()
    for k, v in {"entorno": "desarrollo", "correo_proveedor": "resend", "resend_api_key": "re_x", "correo_envio_real": False,
                 "storage_dir": str(tmp_path)}.items():
        monkeypatch.setattr(a, k, v)
    monkeypatch.setattr(httpx, "post", lambda *x, **k: (_ for _ in ()).throw(AssertionError("no debe salir")))
    correo.enviar(["x@y.test"], "Hola", "<p>hola</p>", "hola")
    assert len(list((tmp_path / "correos_prueba").glob("*.json"))) == 1


def test_la_plataforma_no_ve_correos_de_los_despachos_a_sus_clientes(ev, plataforma, buzon):
    aid = asunto(ev)
    _crear(ev, aid, buzon)
    hist = plataforma.c.get("/api/plataforma/correos", headers=plataforma.h).json()["historial"]
    assert not any("laura@cliente.test" in h["destinatarios"] for h in hist)


def test_demo_divorcio_se_siembra_una_vez(db):
    from app.services.semilla import sembrar_demo
    sembrar_demo(db)
    assert demo.sembrar_divorcio(db) is False  # sin Evidencia activo no hace nada
    demo.sembrar(db)
    assert demo.sembrar_divorcio(db) is True and demo.sembrar_divorcio(db) is False
    a = db.query(m.EvAsunto).filter_by(identificador_interno="DEMO-002").one()
    assert db.query(m.EvDocumento).filter_by(asunto_id=a.id).count() == 3
    assert db.query(m.EvHecho).filter_by(asunto_id=a.id, estado="confirmado").count() == 0
