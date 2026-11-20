"""Sesiones en vivo: Nomira no crea reuniones; reconoce el enlace que pega el despacho (Zoom, Google
Meet, Microsoft Teams, Webex) y ofrece el archivo de calendario (.ics) y el enlace de Google Calendar."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

PLATAFORMAS = [
    ("zoom", "Zoom", re.compile(r"^https://([\w-]+\.)?zoom\.(us|com)/")),
    ("meet", "Google Meet", re.compile(r"^https://meet\.google\.com/")),
    ("teams", "Microsoft Teams", re.compile(r"^https://teams\.(microsoft|live)\.com/")),
    ("webex", "Webex", re.compile(r"^https://([\w-]+\.)?webex\.com/")),
]
MINUTOS_ANTES = 15


def plataforma(url: str | None) -> dict | None:
    if not url:
        return None
    for clave, nombre, rx in PLATAFORMAS:
        if rx.match(url):
            return {"clave": clave, "nombre": nombre}
    return {"clave": "otra", "nombre": "Enlace de la sesión"}


def ventana(inicio: datetime, duracion_min: int, ahora: datetime | None = None) -> dict:
    ahora = ahora or datetime.now(timezone.utc)
    abre = inicio - timedelta(minutes=MINUTOS_ANTES)
    cierra = inicio + timedelta(minutes=duracion_min)
    return {"abre_en": abre.isoformat(), "cierra_en": cierra.isoformat(), "unirse_activo": abre <= ahora <= cierra,
            "terminada": ahora > cierra}


def _ics_texto(t: str) -> str:
    return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _utc(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ics(*, uid: str, titulo: str, curso: str, inicio: datetime, duracion_min: int, enlace: str | None, notas: str | None,
        organizacion: str) -> str:
    fin = inicio + timedelta(minutes=duracion_min)
    desc = "\n".join(x for x in (f"Curso: {curso}", f"Unirse: {enlace}" if enlace else None, notas) if x)
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Nomira//Academia//ES", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
              f"UID:{uid}", f"DTSTAMP:{_utc(datetime.now(timezone.utc))}", f"DTSTART:{_utc(inicio)}", f"DTEND:{_utc(fin)}",
              f"SUMMARY:{_ics_texto(titulo)}", f"DESCRIPTION:{_ics_texto(desc)}", f"ORGANIZER;CN={_ics_texto(organizacion)}:mailto:no-responder@nomirasoft.com"]
    if enlace:
        lineas += [f"LOCATION:{_ics_texto(enlace)}", f"URL:{enlace}"]
    lineas += ["BEGIN:VALARM", "TRIGGER:-PT15M", "ACTION:DISPLAY", "DESCRIPTION:La sesión empieza en 15 minutos", "END:VALARM",
               "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lineas) + "\r\n"


def google_calendar(*, titulo: str, curso: str, inicio: datetime, duracion_min: int, enlace: str | None) -> str:
    fin = inicio + timedelta(minutes=duracion_min)
    detalles = f"Curso: {curso}" + (f"\nUnirse: {enlace}" if enlace else "")
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote(titulo)}&dates={_utc(inicio)}/{_utc(fin)}&details={quote(detalles)}" + (f"&location={quote(enlace)}" if enlace else ""))
