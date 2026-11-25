"""Deja Nomira en ceros y crea la cuenta piloto. NO SE PUEDE DESHACER.

Uso (en Render > nomira-demo > Shell):
    cd /app/backend && python -m scripts.reiniciar_plataforma --confirmo-borrar-todo

Borra todos los despachos con sus usuarios, clientes, expedientes, documentos y archivos, más las solicitudes de
contacto, el CRM de ventas, pagos, tickets, solicitudes ARCO, evidencias de aceptación, correos enviados y la bitácora.
Conserva: administradores del panel, textos legales, precios, paquetes, cupones y ejecutivos, tesis, cursos de Nomira
y días inhábiles. Después crea demo@nomirasoft.com con la contraseña de PILOTO_CONTRASENA (o la pide en pantalla).
"""
import getpass
import sys

from app.config import ajustes
from app.db import SessionLocal
from app.services.piloto import PILOTO_EMAIL, conteo, reiniciar, sembrar_piloto

if __name__ == "__main__":
    if "--confirmo-borrar-todo" not in sys.argv:
        print(__doc__)
        sys.exit(1)
    with SessionLocal() as db:
        c = conteo(db)
    print(f"Base: {ajustes().entorno}. Se borrarán {c['despachos']} despachos, {c['usuarios']} usuarios, {c['clientes']} clientes, "
          f"{c['expedientes']} expedientes y {c['solicitudes_contacto']} solicitudes de contacto, con todos sus archivos.")
    if input('Para continuar escriba exactamente BORRAR TODO: ').strip() != "BORRAR TODO":
        print("Cancelado. No se borró nada.")
        sys.exit(1)
    contrasena = ajustes().piloto_contrasena or getpass.getpass(f"Contraseña para {PILOTO_EMAIL} (no se muestra): ")
    with SessionLocal() as db:
        r = reiniciar(db)
        print("Listo. Antes:", r["antes"], "· Después:", r["despues"])
        sembrar_piloto(db, contrasena)
    print(f"Cuenta piloto creada: {PILOTO_EMAIL}. Entre en https://nomirasoft.com/login")
