"""Genera un PDF de recibos SINTÉTICOS para probar la carga.
Uso: python -m scripts.generar_pdf_ejemplo [ruta_salida.pdf]"""
import sys

from app.services.semilla import periodo
from app.sinteticos import BASE, CASO_ACEPTACION, crear_pdf, recibo

if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "recibos_sinteticos.pdf"
    extra = [("0108", "CARRERA MAGISTERIAL", "700.00"), ("1633", "RETR INCENTIVO POR CONVENIO MA", "1937.00")]
    recs = [recibo(periodo(2025, 12, 1), CASO_ACEPTACION, num="5000001", nombre="DEMO FICTICIO JORGE ALBERTO",
                   clave_servidor="900000555", plaza="990000000000555")]
    quincenas = [(2025, 12, 2), (2026, 1, 1), (2026, 1, 2), (2026, 2, 1), (2026, 2, 2), (2026, 3, 1)]
    for n, (anio, mes, mitad) in enumerate(quincenas, start=2):
        recs.append(recibo(periodo(anio, mes, mitad), BASE + (extra if mitad == 2 else []), num=f"{5000000 + n}",
                           nombre="DEMO FICTICIO JORGE ALBERTO", clave_servidor="900000555", plaza="990000000000555"))
    with open(ruta, "wb") as f:
        f.write(crear_pdf(recs))
    print(f"{ruta}: {len(recs)} recibos sintéticos")
