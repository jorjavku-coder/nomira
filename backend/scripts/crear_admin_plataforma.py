"""Crea (o restablece) un administrador del panel de la plataforma (/plataforma).

Uso:  python -m scripts.crear_admin_plataforma correo@ejemplo.com "Nombre Apellido"
La contraseña se pide por teclado (no queda en el historial de la terminal).
Si el correo ya existe, se le asigna la nueva contraseña y se reactiva.
"""
import getpass
import sys

from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from app.security import hash_contrasena


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    email = sys.argv[1].strip().lower()
    nombre = sys.argv[2] if len(sys.argv) > 2 else "Administrador de Nomira"
    contrasena = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if len(contrasena) < 12 or contrasena != getpass.getpass("Repítala: "):
        sys.exit("La contraseña es muy corta o no coincide.")
    with SessionLocal() as db:
        a = db.scalar(select(m.AdminPlataforma).where(m.AdminPlataforma.email == email))
        if a:
            a.hash_contrasena, a.activo = hash_contrasena(contrasena), True
            a.sesion_version += 1
            print(f"Se restableció la contraseña de {email}.")
        else:
            db.add(m.AdminPlataforma(email=email, nombre=nombre, hash_contrasena=hash_contrasena(contrasena)))
            print(f"Se creó el administrador de la plataforma {email}.")
        db.commit()


if __name__ == "__main__":
    main()
