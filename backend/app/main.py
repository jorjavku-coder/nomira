import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import ajustes
from .db import SessionLocal, engine
from .routers import (academia, academia_medios, afore, agenda, agenda_estrados, agenda_feed, clientes, afore_publico, auth, catalogos, comercial, comercial_publico, documentos, evidencia,
                      evidencia_publica, expedientes, ia, leads, leads_publico, legal, organizacion, plataforma, plataforma_academia, plataforma_legal,
                      soporte, solicitudes)
from .services.evidencia.procesamiento import recuperar_interrumpidos as recuperar_evidencia
from .services.academia import nomira as cursos_nomira
from .services.agenda import avisos as agenda_avisos, estrados as agenda_estrados_srv
from .services.modulos import requiere_modulo
from .services import correo
from .services.envios import ejecutar_recordatorios
from .services.plataforma import asegurar_admin_inicial
from .services.semilla import proteger_demo
from .services.procesamiento import recuperar_interrumpidos

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo(app: FastAPI):
    try:
        recuperar_interrumpidos()
    except Exception:  # la base puede no estar migrada todavía
        logging.getLogger("quincena").warning("No se pudo revisar documentos interrumpidos.")
    try:
        recuperar_evidencia()
    except Exception:
        logging.getLogger("quincena").warning("No se pudo revisar documentos de evidencia interrumpidos.")
    try:
        with SessionLocal() as db:
            cursos_nomira.asegurar(db)
    except Exception:
        logging.getLogger("quincena").warning("No se pudieron revisar los cursos de Nomira Academia.")
    try:
        with SessionLocal() as db:
            asegurar_admin_inicial(db)
            r = proteger_demo(db)
            if r != "sin_cambios":
                logging.getLogger("nomira").warning("Cuentas de demostración: %s.", r)
    except Exception:
        logging.getLogger("quincena").warning("No se pudo revisar el administrador de la plataforma.")
    tarea = asyncio.create_task(_revisar_recordatorios())
    tarea_agenda = asyncio.create_task(_revisar_agenda())
    yield
    for t in (tarea, tarea_agenda):
        t.cancel()
        with suppress(asyncio.CancelledError):
            await t


def _una_revision() -> None:
    with SessionLocal() as db:
        for r in ejecutar_recordatorios(db):
            logging.getLogger("nomira.correos").info("Recordatorio %s: %s (%s)", r["estado"], r["cliente"], r["detalle"])


async def _revisar_recordatorios(espera_inicial: float = 120, cada: float = 3600) -> None:
    """Cada hora revisa qué recordatorios de vencimiento faltan por enviar. Es seguro aunque haya
    varios procesos: cada aviso tiene una llave única en la base. Si el servicio estuvo dormido,
    los avisos atrasados salen en la siguiente revisión."""
    await asyncio.sleep(espera_inicial)
    while True:
        if correo.configurado() and ajustes().recordatorio_dias > 0:
            try:
                await asyncio.to_thread(_una_revision)
            except Exception:
                logging.getLogger("nomira.correos").exception("Falló la revisión de recordatorios.")
        await asyncio.sleep(cada)


def _una_revision_agenda() -> None:
    with SessionLocal() as db:
        r = agenda_avisos.ejecutar(db)
        if any(r.values()):
            logging.getLogger("nomira.agenda").info("Agenda: %s avisos, %s correos, %s resúmenes", r["avisos"], r["correos"], r["resumenes"])
    with SessionLocal() as db:  # estrados digitales: solo si la consulta automática está configurada
        r = agenda_estrados_srv.ejecutar(db)
        if r["revisadas"]:
            logging.getLogger("nomira.estrados").info("Estrados: %s revisados, %s publicaciones nuevas, %s correos", r["revisadas"], r["nuevas"], r["correos"])


async def _revisar_agenda(espera_inicial: float = 90, cada: float = 900) -> None:
    """Cada 15 minutos genera los avisos escalonados de plazos y audiencias, y el resumen diario.
    Cada aviso tiene llave única: repetir la revisión no duplica nada."""
    await asyncio.sleep(espera_inicial)
    while True:
        try:
            await asyncio.to_thread(_una_revision_agenda)
        except Exception:
            logging.getLogger("nomira.agenda").exception("Falló la revisión de la agenda.")
        await asyncio.sleep(cada)


app = FastAPI(title="Nomira", version="0.1.0", lifespan=ciclo)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in ajustes().cors_origenes.split(",") if o.strip()],
                   allow_methods=["*"], allow_headers=["Authorization", "Content-Type", "X-Enlace", "X-Sesion"])
for r in (auth.router, organizacion.router, solicitudes.router, plataforma.router, soporte.router):
    app.include_router(r)
# Cada módulo protege sus rutas en el backend: si no está activo para la organización, responde 403.
for r in (catalogos.router, documentos.router, expedientes.router, ia.router):
    app.include_router(r, dependencies=[Depends(requiere_modulo("nomina"))])
app.include_router(evidencia.router, dependencies=[Depends(requiere_modulo("evidencia"))])
# Carga pública de documentos del cliente: sin sesión; valida el enlace, la organización y el módulo.
app.include_router(evidencia_publica.router)
app.include_router(afore.router, dependencies=[Depends(requiere_modulo("afore"))])
# Portal del cliente y webhook de WhatsApp: sin sesión de usuario (validan su enlace o la firma de Meta).
app.include_router(afore_publico.router)
app.include_router(leads.router, dependencies=[Depends(requiere_modulo("leads"))])
# Formulario de contacto, entrada de otros sistemas y anuncios de Meta: validan su enlace, clave o firma.
app.include_router(leads_publico.router)
app.include_router(academia.router, dependencies=[Depends(requiere_modulo("academia"))])
app.include_router(clientes.router)  # Clientes del despacho: incluido en todos los planes
app.include_router(agenda.router, dependencies=[Depends(requiere_modulo("agenda"))])
app.include_router(agenda_estrados.router, dependencies=[Depends(requiere_modulo("agenda"))])
app.include_router(agenda_feed.router)  # calendario privado por persona (lo valida su enlace)
app.include_router(academia_medios.router)  # URL firmadas (video/SCORM) y verificación pública de diplomas
# Centro Legal: documentos publicados (públicos), solicitudes ARCO y aceptación; y su administración en el panel
app.include_router(legal.router)
app.include_router(plataforma_legal.router)
app.include_router(comercial.router)  # solo superadministrador (dependencia en el propio router)
app.include_router(plataforma_academia.router)  # solo superadministrador (dependencia en el propio router)
app.include_router(comercial_publico.router)


@app.get("/api/salud")
def salud():
    """Lo usa la plataforma para saber si reiniciar el servicio: comprueba también la base."""
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        logging.getLogger("quincena").warning("Salud: la base de datos no responde.")
        return JSONResponse({"ok": False, "base_de_datos": False}, status_code=503)
    return {"ok": True}
