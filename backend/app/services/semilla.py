"""Datos de demostración (sintéticos) y carga del catálogo de referencia."""
from __future__ import annotations

import csv
import hashlib
import os
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..security import hash_contrasena
from ..sinteticos import BASE, CASO_ACEPTACION, crear_pdf, recibo
from .procesamiento import procesar_documento

RUTA_REFERENCIA = Path(os.environ.get(
    "CATALOGO_REFERENCIA", Path(__file__).resolve().parents[3] / "datos" / "catalogo" / "prestaciones_referencia.csv"))


def leer_referencia() -> list[tuple[str, str]]:
    with open(RUTA_REFERENCIA, newline="", encoding="utf-8") as f:
        return [(r["clave"], r["descripcion"]) for r in csv.DictReader(f)]  # claves como texto


def crear_catalogo_referencia(db: Session, org_id: int, usuario_id: int | None,
                              nombre="Prestaciones (transcripción de referencia)") -> m.CatalogoVersion:
    cat = m.Catalogo(organizacion_id=org_id, nombre=nombre)
    db.add(cat)
    db.flush()
    v = m.CatalogoVersion(
        catalogo_id=cat.id, organizacion_id=org_id, numero=1, estado="activo", origen="manual",
        archivo_nombre="prestaciones_referencia.csv", creado_por_id=usuario_id, validado_por_id=usuario_id,
        validado_en=m.ahora(), notas="Transcripción de referencia incluida en el repositorio. Verifíquela contra "
                                     "su documento fuente antes de usarla en expedientes reales.")
    for clave, desc in leer_referencia():
        v.entradas.append(m.CatalogoEntrada(clave=clave, descripcion=desc))
    db.add(v)
    db.flush()
    return v


def guardar_documento(db: Session, exp: m.Expediente, nombre: str, datos: bytes, usuario_id: int | None) -> m.Documento:
    sha = hashlib.sha256(datos).hexdigest()
    carpeta = Path(ajustes().storage_dir) / str(exp.organizacion_id) / str(exp.id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{sha}.pdf"
    ruta.write_bytes(datos)
    d = m.Documento(organizacion_id=exp.organizacion_id, expediente_id=exp.id, nombre_original=nombre, sha256=sha,
                    tamano_bytes=len(datos), ruta=str(ruta), subido_por_id=usuario_id)
    db.add(d)
    db.commit()
    procesar_documento(db, d.id)
    return d


Q = {1: "01-15", 2: "16-{fin}"}
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
         "Noviembre", "Diciembre"]
FIN = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def periodo(anio: int, mes: int, mitad: int) -> str:
    dias = "01-15" if mitad == 1 else f"16-{FIN[mes] + (1 if mes == 2 and anio % 4 == 0 else 0)}"
    return f"{dias} de {MESES[mes - 1]} de {anio}"


def pdfs_demo() -> dict[str, bytes]:
    """Los tres PDF sintéticos de la demo (bytes reproducibles salvo, quizá, el escaneado)."""
    limpio = [recibo(periodo(2025, mes, q), BASE + ([("0108", "CARRERA MAGISTERIAL", "700.00"),
                                                    ("0109", "DESARROLLO PROFESIONAL", "1000.00")] if q == 2 else []),
                     num=f"{1000 + mes * 2 + q:07d}") for mes in (7, 8, 9) for q in (1, 2)]
    incidencias = [
        recibo(periodo(2025, 1, 1), CASO_ACEPTACION, num="2000001"),
        recibo(periodo(2025, 1, 2), BASE + [("1104", "RETR COMPENSACION", "350.00")], num="2000002"),
        # febrero Q1: solo claves fuera de catálogo => quincena en $0.00 (no es faltante)
        recibo(periodo(2025, 2, 1), [("0136", "FORTALECIMIENTO AL SALARIO DOC", "1591.85"),
                                     ("0302", "PRIMA POR AÑOS DE SERVICIO DE", "459.00")], num="2000003"),
        # febrero Q2: fila sin importe y un importe negativo
        recibo(periodo(2025, 2, 2), BASE + [("0512", "DESPENSA", None), ("0607", "BONO DE PRODUCTIVIDAD", "-120.00")],
               num="2000004", total_percepciones="11173.75"),
        recibo(periodo(2025, 3, 1), BASE, num="2000005"),
        recibo(periodo(2025, 3, 1), BASE, num="2000005"),  # duplicado exacto
        recibo(periodo(2025, 3, 2), BASE, num="2000006"),
        recibo(periodo(2025, 3, 2), [("0609", "DESPENSA EXTRAORDINARIA", "1200.00")], num="2000007"),  # complementario
        # abril Q1: FALTANTE (no hay recibo). abril Q2: recibo de otra persona ficticia
        recibo(periodo(2025, 4, 2), BASE, num="2000008", nombre="OTRA PERSONA FICTICIA", clave_servidor="900000999"),
    ]
    plaza2 = [recibo(periodo(2025, 1, 1), [("0102", "SUELDO BASE", "3100.00")], num="3000001", plaza="990000000000002")]
    return {"sintetico_jul-sep_2025.pdf": crear_pdf(limpio),
            "sintetico_con_incidencias.pdf": crear_pdf(incidencias),
            "sintetico_escaneado_segunda_plaza.pdf": crear_pdf(plaza2, informativas=False, escaneado=True)}


def sembrar_demo(db: Session, email="admin@demo.local", contrasena="Demo-Quincena-2025") -> dict:
    """Crea una organización de demostración con usuarios, catálogo y dos expedientes sintéticos."""
    if db.scalar(select(m.Usuario.id).where(m.Usuario.email == email)):
        return {"creado": False}
    org = m.Organizacion(nombre="Despacho Demostración (datos sintéticos)")
    db.add(org)
    db.flush()
    admin = m.Usuario(organizacion_id=org.id, email=email, nombre="Admin Demo",
                      hash_contrasena=hash_contrasena(contrasena), rol="administrador")
    db.add_all([admin,
                m.Usuario(organizacion_id=org.id, email="analista@demo.local", nombre="Analista Demo",
                          hash_contrasena=hash_contrasena(contrasena), rol="analista"),
                m.Usuario(organizacion_id=org.id, email="consulta@demo.local", nombre="Consulta Demo",
                          hash_contrasena=hash_contrasena(contrasena), rol="consulta")])
    db.flush()
    v = crear_catalogo_referencia(db, org.id, admin.id)

    def expediente(ini, fin, n):
        e = m.Expediente(organizacion_id=org.id, trabajador_nombre="EJEMPLO SINTETICO MARIA FERNANDA",
                         identificador_laboral="900000001", periodo_inicio=ini, periodo_fin=fin,
                         quincenas_esperadas=n, catalogo_version_id=v.id, creado_por_id=admin.id)
        db.add(e)
        db.commit()
        return e

    pdfs = pdfs_demo()
    limpio = expediente(date(2025, 7, 1), date(2025, 9, 30), 6)  # listo para validar
    guardar_documento(db, limpio, "sintetico_jul-sep_2025.pdf", pdfs["sintetico_jul-sep_2025.pdf"], admin.id)
    inc = expediente(date(2025, 1, 1), date(2025, 4, 30), 8)  # con incidencias para practicar la revisión
    for nombre in ("sintetico_con_incidencias.pdf", "sintetico_escaneado_segunda_plaza.pdf"):
        guardar_documento(db, inc, nombre, pdfs[nombre], admin.id)
    db.add(m.Auditoria(organizacion_id=org.id, usuario_id=admin.id, usuario_email=admin.email, accion="demo_sembrada"))
    db.commit()
    return {"creado": True, "email": email, "contrasena": contrasena}


def restaurar_archivos(db: Session) -> dict:
    """Para alojamientos con disco temporal: tras un reinicio los PDF desaparecen. Los de la demo
    (sintéticos) se regeneran si su huella coincide; los demás se marcan en error, sin inventar nada."""
    demo = {hashlib.sha256(datos).hexdigest(): datos for datos in pdfs_demo().values()}
    restaurados = perdidos = 0
    for d in db.scalars(select(m.Documento)):
        if Path(d.ruta).exists():
            continue
        if d.sha256 in demo:
            Path(d.ruta).parent.mkdir(parents=True, exist_ok=True)
            Path(d.ruta).write_bytes(demo[d.sha256])
            restaurados += 1
        elif d.estado != "error":
            d.estado = "error"
            d.error = "El archivo original ya no está disponible (almacenamiento temporal del servicio de demostración)."
            perdidos += 1
    db.commit()
    return {"restaurados": restaurados, "perdidos": perdidos}
