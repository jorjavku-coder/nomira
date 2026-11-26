"""Uso: python -m scripts.sembrar_demo [--restaurar]   (crea datos SINTÉTICOS de demostración)"""
import sys

from app.config import ajustes
from app.db import SessionLocal
from app.services.academia import demo as academia_demo
from app.services.afore import demo as afore_demo
from app.services.agenda import demo as agenda_demo
from app.services.bolsa import demo as bolsa_demo
from app.services.rh import demo as rh_demo
from app.services.connect import demo as connect_demo
from app.services.escrituracion import demo as escrituracion_demo
from app.services.liquidacion import demo as liquidacion_demo
from app.services.clientes import demo as clientes_demo
from app.services.evidencia import demo as evidencia_demo
from app.services.leads import demo as leads_demo
from app.services.semilla import proteger_demo, restaurar_archivos, sembrar_demo

if __name__ == "__main__":
    if ajustes().entorno == "produccion":
        # En producción solo existe el despacho piloto (demo@nomirasoft.com); la demo de desarrollo nunca se crea.
        from app.services.piloto import PILOTO_EMAIL, sembrar_piloto

        with SessionLocal() as db:
            if not ajustes().piloto_contrasena:
                print("Sin PILOTO_CONTRASENA: no se crea la cuenta piloto.")
            else:
                r = sembrar_piloto(db, ajustes().piloto_contrasena)
                print("Cuenta piloto creada:" if r["creado"] else "La cuenta piloto ya existía:", PILOTO_EMAIL)
            if "--restaurar" in sys.argv:
                print("Archivos:", restaurar_archivos(db), "· Evidencia:", evidencia_demo.restaurar_archivos(db))
            proteger_demo(db)
        sys.exit(0)
    with SessionLocal() as db:
        r = sembrar_demo(db)
        ev = evidencia_demo.sembrar(db)  # una sola vez por organización de demostración
        evidencia_demo.sembrar_divorcio(db)
        afore_demo.sembrar(db)  # Nomira AFORE: dos casos ficticios
        leads_demo.sembrar(db)  # Nomira Leads: prospectos y campañas ficticios
        academia_demo.sembrar(db)  # Nomira Academia: un curso interno y asignaciones de ejemplo
        agenda_demo.sembrar(db)  # Nomira Agenda: calendario, dos asuntos, plazos y una audiencia ficticios
        agenda_demo.sembrar_estrados(db)  # un expediente ficticio vigilado en estrados del TRIJAEM
        escrituracion_demo.sembrar(db)  # Escrituración: una compraventa y un testamento ficticios
        liquidacion_demo.sembrar(db)  # Liquidaciones LFT: dos cálculos ligados al asunto laboral
        clientes_demo.sembrar(db)  # Clientes y cobranza: tres clientes ficticios con honorarios y pagos
        rh_demo.sembrar(db)  # Recursos humanos: equipo del despacho y una empresa cliente
        connect_demo.sembrar(db)  # Nomira Connect: el juicio laboral publicado en el portal del cliente
        bolsa_demo.sembrar(db)  # Bolsa de trabajo: una vacante (no va al portal público), dos candidatos y una prueba
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
