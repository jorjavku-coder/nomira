"""Datos de demostración de Nomira AFORE (100 % ficticios). Se crean una sola vez."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from .cifrado import cifrar
from .identificadores import pista_curp, pista_nss


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin:
        return False
    oid = admin.organizacion_id
    if db.scalar(select(m.OrganizacionModulo.id).where(m.OrganizacionModulo.organizacion_id == oid, m.OrganizacionModulo.modulo == "afore")):
        return False
    modulos.fijar(db, oid, "afore", contratado=True, activo=True)
    hoy = date.today()

    def cliente(nombre, tel, mail, curp, nss, **kw):
        c = m.AfCliente(organizacion_id=oid, nombre=nombre, telefono=tel, email=mail, curp_cifrado=cifrar(curp), curp_pista=pista_curp(curp),
                        nss_cifrado=cifrar(nss), nss_pista=pista_nss(nss), creado_por_id=admin.id, **kw)
        db.add(c)
        db.flush()
        return c

    rosa = cliente("Rosa Ficticia López", "525500000001", "rosa@ejemplo-ficticio.test", "HEGG560427MVZRRL04", "12345678903",
                   preferencia_contacto="correo")
    db.add(m.AfConsentimiento(organizacion_id=oid, cliente_id=rosa.id, canal="correo", alcance="Actualizaciones de su trámite", medio="escrito",
                              registrado_por_id=admin.id))
    pedro = cliente("Pedro Demo Ramírez", "525500000002", None, "BOXW310820HNERXN09", "12345678911", relacion="beneficiario",
                    titular_estado="vive", preferencia_contacto="whatsapp")
    c1 = m.AfCaso(organizacion_id=oid, cliente_id=rosa.id, estado="esperando", tipo_problema="inconformidad_retiro", responsable_id=admin.id,
                  datos={"afore": {"valor": "Coppel", "estado": "informado"}, "institucion": {"valor": "IMSS", "estado": "informado"},
                         "monto_cliente": {"valor": "85000.00", "estado": "informado"}, "monto_afore": {"valor": None, "estado": "pendiente"},
                         "monto_entregado": {"valor": "42000.00", "estado": "informado"}},
                  identificador_interno="AF-DEMO-01", siguiente_actividad="Llamar a la AFORE para dar seguimiento al folio",
                  siguiente_fecha=hoy + timedelta(days=2), siguiente_responsable_id=admin.id, portal_visible=True,
                  estado_publico="Presentamos su solicitud a la AFORE y esperamos su respuesta.",
                  siguiente_paso_publico="Envíenos su estado de cuenta bancario donde recibió el depósito.", publico_actualizado_en=m.ahora(),
                  creado_por_id=admin.id)
    c2 = m.AfCaso(organizacion_id=oid, cliente_id=pedro.id, titular_nombre="Juana Demo Ramírez", estado="abierto", tipo_problema="beneficiario_fallecimiento",
                  responsable_id=admin.id, datos={"afore": {"valor": None, "estado": "no_lo_se"}}, creado_por_id=admin.id)
    db.add_all([c1, c2])
    db.flush()
    from ...routers.afore import checklist_de
    for c in (c1, c2):
        for i, n in enumerate(checklist_de(db, oid, c.tipo_problema)):
            estado = "aceptado" if c is c1 and i < 2 else "solicitado" if c is c1 and i in (2, 6) else "no_solicitado"
            db.add(m.AfRequisito(organizacion_id=oid, caso_id=c.id, nombre=n, estado=estado, orden=i, actualizado_por_id=admin.id))
    db.add_all([
        m.AfActividad(organizacion_id=oid, caso_id=c1.id, tipo="solicitud_enviada", fecha=hoy - timedelta(days=18), institucion="Coppel", canal="Sucursal",
                      folio="REC-000123", resumen="Se presentó la reclamación por diferencia en el monto de retiro.", creado_por_id=admin.id),
        m.AfPlazo(organizacion_id=oid, caso_id=c1.id, tipo="informado_institucion", descripcion="Respuesta que la AFORE dijo dar", fecha=hoy + timedelta(days=5),
                  fuente="Dicho por personal de la sucursal", creado_por_id=admin.id, responsable_id=admin.id),
        m.AfMensaje(organizacion_id=oid, cliente_id=pedro.id, caso_id=c2.id, canal="whatsapp", plantilla="falta_documentacion", estado="borrador",
                    texto="Hola, Pedro. Para avanzar con tu trámite necesitamos algunos documentos. Consulta cuáles en tu portal seguro de Nomira: [enlace seguro al portal]",
                    motivo="El cliente no ha dado (o revocó) su consentimiento para recibir mensajes por whatsapp. WhatsApp no está conectado.",
                    origen="demo", telefono=pedro.telefono, creado_por_id=admin.id),
    ])
    db.commit()
    return True
