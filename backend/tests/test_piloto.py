"""Reinicio de la plataforma: borra despachos y datos de operación, conserva lo pedido; y crea la cuenta piloto."""
from app import models as m
from app.services import piloto
from app.services.tesis import base as tb

from .test_tesis import T1


def test_reiniciar_y_piloto(db, org, org2, plataforma, cliente):
    tb.guardar(db, [tb.desde_json(T1)], "json", "x.json")
    db.add(m.CmCupon(codigo="BLACKDAY2026", tipo="porcentaje", valor=20, usos=3))
    db.commit()
    admins = db.query(m.AdminPlataforma).count()
    r = piloto.reiniciar(db)
    assert r["antes"]["despachos"] >= 2 and r["despues"] == {"despachos": 0, "usuarios": 0, "clientes": 0, "expedientes": 0, "solicitudes_contacto": 0}
    assert db.query(m.AdminPlataforma).count() == admins  # el panel sigue entrando
    assert db.query(m.JTesis).count() == 1  # biblioteca de tesis
    c = db.query(m.CmCupon).one()
    assert c.codigo == "BLACKDAY2026" and c.usos == 0  # cupón conservado, sin usos de despachos borrados
    assert [a.accion for a in db.query(m.Auditoria)] == ["plataforma_reiniciada"]
    piloto.sembrar_piloto(db, "Demo2026#")
    o = db.query(m.Organizacion).one()
    assert o.nombre == piloto.PILOTO_DESPACHO and [u.email for u in db.query(m.Usuario)] == [piloto.PILOTO_EMAIL]
    assert db.query(m.CrCliente).count() >= 3 and db.query(m.BtVacante).count() == 1 and db.query(m.EvAsunto).count() >= 1
    tok = cliente.post("/api/auth/login", json={"email": piloto.PILOTO_EMAIL, "contrasena": "Demo2026#"})
    assert tok.status_code == 200, tok.text
