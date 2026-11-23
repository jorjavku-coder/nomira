"""Uso: python -m scripts.sembrar_demo [--restaurar]   (crea datos SINTÉTICOS de demostración)"""
import sys

from app.config import ajustes
from app.db import SessionLocal
from app.services.academia import demo as academia_demo
from app.services.afore import demo as afore_demo
from app.services.agenda import demo as agenda_demo
from app.services.clientes import demo as clientes_demo
from app.services.evidencia import demo as evidencia_demo
from app.services.leads import demo as leads_demo
from app.services.semilla import proteger_demo, restaurar_archivos, sembrar_demo

if __name__ == "__main__":
    with SessionLocal() as db:
        r = sembrar_demo(db)
        ev = evidencia_demo.sembrar(db)  # una sola vez por organización de demostración
        evidencia_demo.sembrar_divorcio(db)
        afore_demo.sembrar(db)  # Nomira AFORE: dos casos ficticios
        leads_demo.sembrar(db)  # Nomira Leads: prospectos y campañas ficticios
        academia_demo.sembrar(db)  # Nomira Academia: un curso interno y asignaciones de ejemplo
        agenda_demo.sembrar(db)  # Nomira Agenda: calendario, dos asuntos, plazos y una audiencia ficticios
        agenda_demo.sembrar_estrados(db)  # un expediente ficticio vigilado en estrados del TRIJAEM
        clientes_demo.sembrar(db)  # Clientes y cobranza: tres clientes ficticios con honorarios y pagos
        proteger_demo(db)  # en producción: nunca con la contraseña publicada en el README
        if "--restaurar" in sys.argv:
            print("Archivos:", restaurar_archivos(db), "· Evidencia:", evidencia_demo.restaurar_archivos(db))
    if r["creado"]:
        print(f"Demo creada. Usuario: {r['email']}" + ("" if ajustes().entorno == "produccion" else f"  Contraseña: {r['contrasena']}"))
        print("También: analista@demo.local y consulta@demo.local (misma contraseña). Cámbielas.")
    else:
        print("La demo ya existía; no se modificó nada.")
    if ev:
        print("Nomira Evidencia activado en la demo con un asunto de ejemplo.")
