"""Uso: python -m scripts.sembrar_demo [--restaurar]   (crea datos SINTÉTICOS de demostración)"""
import sys

from app.db import SessionLocal
from app.services.semilla import restaurar_archivos, sembrar_demo

if __name__ == "__main__":
    with SessionLocal() as db:
        r = sembrar_demo(db)
        if "--restaurar" in sys.argv:
            print("Archivos:", restaurar_archivos(db))
    if r["creado"]:
        print(f"Demo creada. Usuario: {r['email']}  Contraseña: {r['contrasena']}")
        print("También: analista@demo.local y consulta@demo.local (misma contraseña). Cámbielas.")
    else:
        print("La demo ya existía; no se modificó nada.")
