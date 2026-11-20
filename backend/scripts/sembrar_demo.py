"""Uso: python -m scripts.sembrar_demo [--restaurar]   (crea datos SINTÉTICOS de demostración)"""
import sys

from app.db import SessionLocal
from app.services.academia import demo as academia_demo
from app.services.afore import demo as afore_demo
from app.services.agenda import demo as agenda_demo
from app.services.evidencia import demo as evidencia_demo
from app.services.leads import demo as leads_demo
from app.services.semilla import restaurar_archivos, sembrar_demo

if __name__ == "__main__":
    with SessionLocal() as db:
        r = sembrar_demo(db)
        ev = evidencia_demo.sembrar(db)  # una sola vez por organización de demostración
        evidencia_demo.sembrar_divorcio(db)
        afore_demo.sembrar(db)  # Nomira AFORE: dos casos ficticios
        leads_demo.sembrar(db)  # Nomira Leads: prospectos y campañas ficticios
        academia_demo.sembrar(db)  # Nomira Academia: un curso interno y asignaciones de ejemplo
        agenda_demo.sembrar(db)  # Nomira Agenda: calendario, dos asuntos, plazos y una audiencia ficticios
        if "--restaurar" in sys.argv:
            print("Archivos:", restaurar_archivos(db), "· Evidencia:", evidencia_demo.restaurar_archivos(db))
    if r["creado"]:
        print(f"Demo creada. Usuario: {r['email']}  Contraseña: {r['contrasena']}")
        print("También: analista@demo.local y consulta@demo.local (misma contraseña). Cámbielas.")
    else:
        print("La demo ya existía; no se modificó nada.")
    if ev:
        print("Nomira Evidencia activado en la demo con un asunto de ejemplo.")
