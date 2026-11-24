"""Solo para e2e local: conecta llaves de PRUEBA ficticias y crea una liga y una factura de ejemplo en la demo."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from app.services.clientes import base as cb, cobro as cob

with SessionLocal() as db:
    org = db.scalar(select(m.Usuario).where(m.Usuario.email == "admin@demo.local")).organizacion_id
    c = cob.config(db, org)
    cob.guardar_llaves(c, "rk_test_" + "e2e" * 8, "sk_test_" + "e2e" * 8)
    c.clave_producto = "80121600"
    cli = db.scalars(select(m.CrCliente).where(m.CrCliente.organizacion_id == org).order_by(m.CrCliente.nombre)).first()
    db.add(m.CrLigaPago(organizacion_id=org, cliente_id=cli.id, concepto="Anticipo de honorarios", monto=Decimal("2500"), stripe_sesion="cs_test_e2e",
                        url="https://checkout.stripe.com/c/pay/cs_test_e2e", expira_en=datetime.now(timezone.utc) + timedelta(hours=20)))
    p = db.scalars(select(m.CrPago).where(m.CrPago.cliente_id == cli.id)).first()
    if p is None:
        p = m.CrPago(organizacion_id=org, cliente_id=cli.id, folio=cb.siguiente_folio(db, org), monto=Decimal("1160"), fecha=datetime.now().date(), metodo="transferencia")
        db.add(p)
        db.flush()
    db.add(m.CrFactura(organizacion_id=org, cliente_id=cli.id, pago_id=p.id, facturapi_id="inv_e2e", uuid="00000000-E2E0-0000-0000-000000000000",
                       serie_folio="A1", subtotal=Decimal("1000"), total=Decimal("1160"), uso="G03", forma_pago="03", prueba=True))
    db.commit()
    print(cli.nombre)
