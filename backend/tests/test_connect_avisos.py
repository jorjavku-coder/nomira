"""Nomira Connect (fase 2): avisos automáticos, actualizaciones preventivas y preferencias del cliente.

Cubre: una actualización autorizada genera su aviso; un mismo evento no genera avisos duplicados; varios cambios
seguidos salen como uno; la nota interna nunca viaja; WhatsApp solo con todo configurado y consentimiento (si no,
queda «omitido» con el motivo, sin simular el envío); la preventiva no afirma una revisión que no existe;
reintentos de envíos fallidos; recordatorio de audiencia sin duplicados; aislamiento entre despachos."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select, update

from app import models as m
from app.db import SessionLocal
from app.services import correo
from app.services.afore import whatsapp
from app.services.connect import avisos as av

from .test_agenda import buzon  # noqa: F401
from .test_connect import C, P, SECRETO, cliente_dir, enlace, entrar, seguimiento
from .test_evidencia import activar


@pytest.fixture
def cn(org, plataforma, monkeypatch):
    activar(plataforma, org, "connect")
    monkeypatch.setattr(av, "HORA_INICIO", 0)  # en pruebas no hay «horario nocturno»
    monkeypatch.setattr(av, "HORA_FIN", 24)
    monkeypatch.setattr(av, "DEMORA_ETAPA", timedelta(0))
    return org


def ciclo():
    with SessionLocal() as db:
        av.generar(db)
        return av.enviar_pendientes(db)


def avisos(**f):
    with SessionLocal() as db:
        q = select(m.CnAviso)
        for k, v in f.items():
            q = q.where(getattr(m.CnAviso, k) == v)
        return [(x.tipo, x.canal, x.estado, x.motivo) for x in db.scalars(q.order_by(m.CnAviso.id))]


def publicado(o, **kw):
    cid = cliente_dir(o)
    s = seguimiento(o, cid, **kw)
    o.c.put(f"{C}/seguimientos/{s['id']}", headers=o.h, json={"visible_cliente": True})
    return cid, s


def mover(o, s, nombre, estado="actual", **kw):
    e = next(x for x in s["etapas"] if x["nombre"] == nombre)
    r = o.c.post(f"{C}/seguimientos/{s['id']}/etapa", headers=o.h, json={"etapa_id": e["id"], "estado": estado, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_cambio_de_etapa_genera_un_aviso_sin_duplicados(cn, buzon):
    cid, s = publicado(cn)
    mover(cn, s, "Presentación de la demanda", nota_publica="NOTA-PUBLICA-DETALLE", nota_interna=SECRETO)
    assert avisos() == [("etapa", "correo", "pendiente", None)]
    antes = len(buzon)
    assert ciclo()["enviado"] == 1
    correo_cliente = buzon[-1]
    assert len(buzon) == antes + 1 and correo_cliente["para"] == ["maria@cliente.test"]
    t = correo_cliente["texto"]
    assert "Nueva etapa: Presentación de la demanda" in t and "Etapa anterior: Recepción del asunto" in t
    assert "no necesita realizar ninguna acción" in t and "/mi-asunto#" in t
    assert SECRETO not in t and "NOTA-PUBLICA-DETALLE" not in t  # solo QUÉ cambió; el detalle, en el portal
    assert ciclo()["enviado"] == 0 and len(buzon) == antes + 1  # repetir la vuelta no duplica
    # el enlace del aviso funciona y no aparece en la lista de enlaces que crea el despacho
    with SessionLocal() as db:
        assert db.scalar(select(m.CnAcceso).where(m.CnAcceso.origen == "aviso"))
    assert cn.c.get(f"{C}/clientes/{cid}/enlaces", headers=cn.h).json()["enlaces"] == []


def test_varios_cambios_seguidos_salen_como_uno(cn, buzon):
    cid, s = publicado(cn)
    mover(cn, s, "Integración de documentación")
    mover(cn, s, "Análisis de prestaciones")
    assert [x[2] for x in avisos(tipo="etapa")] == ["omitido", "pendiente"]
    ciclo()
    assert sum("Análisis de prestaciones" in c["texto"] for c in buzon) == 1
    assert not any("Nueva etapa: Integración" in c["texto"] for c in buzon)


def test_sin_publicar_o_con_avisos_apagados_no_avisa(cn, buzon):
    cid = cliente_dir(cn)
    s = seguimiento(cn, cid)
    mover(cn, s, "Admisión")  # borrador
    assert avisos() == []
    cn.c.put(f"{C}/seguimientos/{s['id']}", headers=cn.h, json={"visible_cliente": True, "avisos": False})
    mover(cn, s, "Desahogo de pruebas")
    assert avisos() == []
    cn.c.put(f"{C}/seguimientos/{s['id']}", headers=cn.h, json={"avisos": True})
    cn.c.put(f"{C}/avisos/config", headers=cn.h, json={"avisos_activos": False})
    mover(cn, s, "En espera de resolución")
    assert avisos() == []


def test_el_cliente_apaga_el_correo_desde_su_portal(cn, buzon):
    cid, s = publicado(cn)
    h = entrar(cn, enlace(cn, cid), buzon)
    e = cn.c.post(f"{P}/estado", headers=h).json()
    assert e["preferencias"]["correo"] is True and e["preferencias"]["whatsapp"] is False
    assert cn.c.post(f"{P}/preferencias", headers=h, json={"correo": False}).json()["correo"] is False
    mover(cn, s, "Admisión")
    ciclo()
    assert avisos(tipo="etapa")[0][2:] == ("omitido", "El cliente pidió no recibir avisos por correo.")


def test_whatsapp_solo_con_todo_listo_y_consentimiento(cn, buzon, monkeypatch):
    enviados = []
    monkeypatch.setattr(whatsapp, "enviar_plantilla", lambda cfg, tel, nombre, idioma, params: enviados.append((tel, nombre, idioma, params)) or "wamid.PRUEBA")
    cid, s = publicado(cn)
    cn.c.put(f"{C}/avisos/config", headers=cn.h, json={"canal_whatsapp": True, "canal_correo": False})
    mover(cn, s, "Admisión")
    ciclo()
    t, canal, estado, motivo = avisos(tipo="etapa")[-1]
    assert canal == "whatsapp" and estado == "omitido" and "pendiente de configurar" in motivo and not enviados
    # el despacho conecta su número y su plantilla aprobada; falta el consentimiento del cliente
    cfg = cn.c.put(f"{C}/avisos/whatsapp", headers=cn.h, json={"phone_number_id": "1234567890", "numero": "+52 55 0000 0000", "token": "T" * 40}).json()
    assert cfg["whatsapp"]["conectado"] is True and "T" * 40 not in str(cfg)
    cfg = cn.c.put(f"{C}/avisos/config", headers=cn.h, json={"wa_plantilla": "nomira_actualizacion", "wa_aprobada": True}).json()
    assert cfg["whatsapp"]["listo"] is True
    mover(cn, s, "Desahogo de pruebas")
    ciclo()
    assert avisos(tipo="etapa")[-1][2:] == ("omitido", "El cliente no ha aceptado recibir avisos por WhatsApp.") and not enviados
    # el cliente acepta desde su portal
    h = entrar(cn, enlace(cn, cid), buzon)
    assert cn.c.post(f"{P}/preferencias", headers=h, json={"whatsapp": True}).json()["whatsapp"] is True
    with SessionLocal() as db:
        p = db.scalar(select(m.CnPreferencia))
        assert p.whatsapp_medio == "portal" and p.whatsapp_consentido_en
    mover(cn, s, "En espera de resolución")
    ciclo()
    assert avisos(tipo="etapa")[-1][2] == "enviado"
    tel, nombre, idioma, params = enviados[-1]
    assert tel == "525512345678" and nombre == "nomira_actualizacion" and idioma == "es_MX"
    assert params[0] == "María" and params[1] == "Pensión ISSEMYM de María" and "En espera de resolución" in params[2] and "/mi-asunto#" in params[3]


def test_preventiva_no_inventa_revision(cn, buzon):
    cid, s = publicado(cn)
    with SessionLocal() as db:
        db.execute(update(m.CnSeguimiento).values(publico_actualizado_en=m.ahora() - timedelta(days=20), creado_en=m.ahora() - timedelta(days=30)))
        db.commit()
    ciclo()
    prev = [c for c in buzon if "Le compartimos una actualización" in c["asunto"]]
    assert len(prev) == 1
    t = prev[0]["texto"]
    assert "no tenemos registrados nuevos movimientos" in t and "Recepción del asunto" in t
    assert "revisión" not in t  # no hay revisión registrada: no se menciona
    ciclo()
    assert len([c for c in buzon if "Le compartimos una actualización" in c["asunto"]]) == 1  # no se repite
    # con revisión registrada y 0 días de espera para este asunto: se apaga
    cn.c.put(f"{C}/seguimientos/{s['id']}", headers=cn.h, json={"preventiva_dias": 0})
    with SessionLocal() as db:
        db.execute(update(m.CnSeguimiento).values(ultima_preventiva_en=m.ahora() - timedelta(days=40), publico_actualizado_en=m.ahora() - timedelta(days=40)))
        db.commit()
    ciclo()
    assert len([c for c in buzon if "Le compartimos una actualización" in c["asunto"]]) == 1


def test_preventiva_con_revision_registrada(cn, buzon):
    cid, s = publicado(cn)
    cn.c.post(f"{C}/seguimientos/{s['id']}/revisado", headers=cn.h)
    with SessionLocal() as db:
        db.execute(update(m.CnSeguimiento).values(publico_actualizado_en=m.ahora() - timedelta(days=16), ultima_revision_en=m.ahora() - timedelta(days=16),
                                                  creado_en=m.ahora() - timedelta(days=30)))
        db.commit()
    ciclo()
    t = next(c for c in buzon if "Le compartimos una actualización" in c["asunto"])["texto"]
    assert "registró la última revisión de su expediente" in t


def test_recordatorio_de_audiencia_una_sola_vez(cn, buzon):
    cid, s = publicado(cn)
    with SessionLocal() as db:
        db.add(m.AgEvento(organizacion_id=cn.org_id, asunto_id=s["asunto_id"], tipo="audiencia", titulo="Audiencia de pruebas",
                          fecha=date.today() + timedelta(days=2), hora="10:00", estado="pendiente"))
        db.commit()
    ciclo()
    ciclo()
    assert len([c for c in buzon if "Recordatorio de audiencia" in c["asunto"]]) == 1


def test_reintentos_y_reintentar_manual(cn, buzon, monkeypatch):
    cid, s = publicado(cn)

    def falla(*a, **k):
        raise correo.CorreoError("proveedor caído")
    monkeypatch.setattr(correo, "enviar", falla)
    mover(cn, s, "Admisión")
    for _ in range(len(av.ESPERAS) + 1):
        ciclo()
        with SessionLocal() as db:  # adelanta el reloj hasta el siguiente intento
            db.execute(update(m.CnAviso).where(m.CnAviso.estado == "pendiente").values(programado_en=m.ahora() - timedelta(minutes=1)))
            db.commit()
    x = cn.c.get(f"{C}/avisos", headers=cn.h).json()["avisos"][0]
    assert x["estado"] == "error" and x["intentos"] == len(av.ESPERAS) + 1 and "proveedor" in x["motivo"]
    monkeypatch.undo()
    monkeypatch.setattr(av, "HORA_INICIO", 0)
    monkeypatch.setattr(av, "HORA_FIN", 24)
    monkeypatch.setattr(correo, "configurado", lambda: True)
    enviados = []
    monkeypatch.setattr(correo, "enviar", lambda dest, asunto, html, texto, **kw: enviados.append(asunto))
    assert cn.c.post(f"{C}/avisos/{x['id']}/reintentar", headers=cn.h).json()["estado"] == "pendiente"
    ciclo()
    assert enviados and avisos(tipo="etapa")[0][2] == "enviado"


def test_respuesta_del_despacho_avisa_al_cliente(cn, buzon):
    cid, s = publicado(cn)
    cn.c.post(f"{C}/mensajes/{cid}", headers=cn.h, json={"texto": "TEXTO-PRIVADO-DE-LA-RESPUESTA"})
    ciclo()
    c = next(x for x in buzon if "Tiene un mensaje nuevo" in x["asunto"])
    assert "TEXTO-PRIVADO-DE-LA-RESPUESTA" not in c["texto"]


def test_aislamiento_de_avisos(cn, org2, plataforma, buzon):
    cid, s = publicado(cn)
    mover(cn, s, "Admisión")
    activar(plataforma, org2, "connect")
    assert org2.c.get(f"{C}/avisos", headers=org2.h).json()["avisos"] == []
    aid = cn.c.get(f"{C}/avisos", headers=cn.h).json()["avisos"][0]["id"]
    assert org2.c.post(f"{C}/avisos/{aid}/reintentar", headers=org2.h).status_code == 404
    assert org2.c.put(f"{C}/clientes/{cid}/preferencias", headers=org2.h, json={"whatsapp": True}).status_code == 404
    # solo el administrador cambia la configuración
    h = cn.usuario("analista", "analista@org1.test")
    assert cn.c.put(f"{C}/avisos/config", headers=h, json={"canal_correo": False}).status_code == 403
