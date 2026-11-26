"""Plantillas de fábrica de Nomira Connect, por especialidad.

Son una GUÍA editable: no representan procedimientos obligatorios. Cada despacho las duplica y adapta, y
cada asunto puede tener sus propias etapas sin tocar la plantilla. Las explicaciones son para el cliente:
lenguaje sencillo, sin plazos ni promesas de resultado.
"""
from __future__ import annotations

E = lambda nombre, explicacion, opcional=False: {"nombre": nombre, "explicacion": explicacion, "opcional": opcional}

RECEPCION = E("Recepción del asunto", "Recibimos su caso y lo registramos en el despacho.")
DOCS = E("Integración de documentación", "Reunimos los documentos necesarios. Si falta alguno, se lo pediremos por aquí.")
PRESENTACION = E("Presentación de la demanda", "Entregamos la demanda al tribunal o a la autoridad.")
ADMISION = E("Admisión", "El tribunal revisa la demanda y decide si la acepta para darle trámite.")
PRUEBAS = E("Desahogo de pruebas", "Se presentan y revisan las pruebas de cada parte. Puede incluir audiencias.")
ESPERA = E("En espera de resolución", "El tribunal estudia el asunto para resolver. En esta etapa es normal que pase tiempo sin movimientos.")
CUMPLIMIENTO = E("Cumplimiento", "Damos seguimiento a que se cumpla lo que se resolvió.")
CIERRE = E("Cierre del asunto", "El asunto concluyó. Le entregamos un resumen y sus documentos.")

BASE: dict[str, dict] = {
    "pensiones": {"nombre": "Pensiones y seguridad social", "nota": "IMSS, ISSSTE, ISSEMYM, AFORE y organismos estatales", "etapas": [
        RECEPCION, DOCS,
        E("Análisis de prestaciones", "Revisamos sus semanas, salarios y prestaciones para saber qué le corresponde."),
        E("Cálculo de diferencias económicas", "Calculamos las cantidades que podrían reclamarse."),
        E("Preparación de la demanda", "Redactamos la demanda con la información y pruebas reunidas."),
        PRESENTACION, ADMISION, PRUEBAS, ESPERA,
        E("Notificación de la resolución", "El tribunal da a conocer su decisión. Le explicaremos qué significa."),
        E("Cumplimiento de la resolución", "Seguimos que la institución cumpla lo que ordenó el tribunal."),
        E("Pago o recuperación económica", "La institución realiza el pago o ajuste que corresponda.", True),
        CIERRE]},
    "laboral": {"nombre": "Derecho laboral", "etapas": [
        RECEPCION, E("Análisis documental", "Revisamos sus documentos laborales: contrato, recibos, constancias."),
        E("Conciliación", "Se busca un acuerdo con la otra parte ante el Centro de Conciliación.", True),
        E("Preparación de la demanda", "Redactamos la demanda laboral."), PRESENTACION,
        E("Audiencias", "Se celebran las audiencias del juicio. Le avisaremos si necesita asistir."),
        PRUEBAS, E("Sentencia", "El tribunal dicta su decisión."), CUMPLIMIENTO, CIERRE]},
    "familiar": {"nombre": "Derecho familiar", "etapas": [
        E("Consulta inicial", "Conversamos sobre su situación y definimos cómo proceder."), DOCS, PRESENTACION, ADMISION,
        E("Notificación", "Se avisa formalmente a la otra parte del juicio."),
        E("Audiencias", "Se celebran las audiencias. Le avisaremos si necesita asistir."),
        E("Resolución", "El juzgado dicta su decisión."), CUMPLIMIENTO, CIERRE]},
    "amparo": {"nombre": "Amparo", "etapas": [
        E("Análisis del acto reclamado", "Estudiamos el acto de autoridad que le afecta."),
        E("Preparación de la demanda", "Redactamos la demanda de amparo."), PRESENTACION, ADMISION,
        E("Suspensión", "El juzgado decide si detiene provisionalmente el acto mientras se resuelve.", True),
        E("Audiencias", "Se celebra la audiencia del juicio de amparo."), E("Sentencia", "El juzgado dicta su decisión."),
        E("Recursos o cumplimiento", "Se revisa la sentencia o se sigue su cumplimiento."), CIERRE]},
    "notarial": {"nombre": "Notarías", "etapas": [
        E("Recepción de la solicitud", "Recibimos su solicitud de trámite."), DOCS,
        E("Validación jurídica", "Revisamos que los documentos y la operación estén en orden."),
        E("Elaboración del instrumento", "Preparamos la escritura o el instrumento."),
        E("Revisión", "Usted y las partes revisan el proyecto."), E("Firma", "Se firma ante el notario."),
        E("Inscripción", "Se inscribe en el registro que corresponda."),
        E("Entrega de documentación", "Le entregamos su testimonio y documentos.")]},
    "corporativo": {"nombre": "Derecho corporativo", "etapas": [
        E("Recepción de la solicitud", "Recibimos su solicitud."), E("Análisis", "Estudiamos lo que necesita su empresa."),
        E("Elaboración documental", "Preparamos los contratos, actas o documentos."), E("Revisión", "Revisamos los documentos con usted."),
        E("Autorización", "Usted aprueba la versión final."), E("Firma", "Se firman los documentos."),
        E("Entrega", "Le entregamos los documentos firmados.")]},
    "civil": {"nombre": "Derecho civil", "etapas": [
        RECEPCION, DOCS, E("Preparación de la demanda", "Redactamos la demanda."), PRESENTACION, ADMISION,
        E("Emplazamiento", "Se notifica a la otra parte para que conteste."), PRUEBAS,
        E("Alegatos", "Las partes presentan sus argumentos finales.", True), E("Sentencia", "El juzgado dicta su decisión."),
        E("Ejecución", "Se sigue que se cumpla la sentencia.", True), CIERRE]},
    "mercantil": {"nombre": "Derecho mercantil", "etapas": [
        RECEPCION, DOCS, E("Requerimiento de pago", "Se pide formalmente el pago a la otra parte.", True),
        E("Preparación de la demanda", "Redactamos la demanda."), PRESENTACION, ADMISION,
        E("Emplazamiento", "Se notifica a la otra parte para que conteste."), PRUEBAS, E("Sentencia", "El juzgado dicta su decisión."),
        E("Ejecución y cobro", "Se gestiona el cobro de lo que ordenó el juzgado.", True), CIERRE]},
    "fiscal": {"nombre": "Derecho fiscal", "etapas": [
        RECEPCION, DOCS, E("Análisis del crédito o acto", "Revisamos el acto de la autoridad fiscal."),
        E("Recurso administrativo", "Se presenta un recurso ante la propia autoridad.", True),
        E("Demanda de nulidad", "Se presenta la demanda ante el tribunal."), ADMISION, ESPERA,
        E("Sentencia", "El tribunal dicta su decisión."), CUMPLIMIENTO, CIERRE]},
    "administrativo": {"nombre": "Derecho administrativo", "etapas": [
        RECEPCION, DOCS, E("Análisis del acto", "Revisamos el acto de la autoridad."),
        E("Escrito o recurso", "Presentamos el escrito o recurso ante la autoridad o el tribunal."), ADMISION,
        PRUEBAS, ESPERA, E("Resolución", "La autoridad o el tribunal resuelve."), CUMPLIMIENTO, CIERRE]},
    "penal": {"nombre": "Derecho penal", "etapas": [
        RECEPCION, E("Investigación", "Etapa ante el Ministerio Público. Le mantendremos al tanto de lo que pueda compartirse."),
        E("Audiencia inicial", "Primera audiencia ante el juez."),
        E("Etapa intermedia", "Se definen las pruebas que se presentarán en el juicio.", True),
        E("Juicio oral", "Se presentan las pruebas ante el tribunal.", True),
        E("Sentencia", "El tribunal dicta su decisión.", True),
        E("Soluciones alternas", "Acuerdo reparatorio o suspensión condicional, si procede.", True), CIERRE]},
    "migratorio": {"nombre": "Derecho migratorio", "etapas": [
        RECEPCION, DOCS, E("Preparación de la solicitud", "Preparamos su solicitud migratoria."),
        E("Presentación ante la autoridad", "Entregamos la solicitud ante la autoridad migratoria."),
        E("Requerimientos", "La autoridad puede pedir información adicional; se la pediremos por aquí.", True),
        E("Resolución", "La autoridad resuelve su trámite."), E("Entrega de documento", "Recibe su documento migratorio."), CIERRE]},
    "inmobiliario": {"nombre": "Derecho inmobiliario", "etapas": [
        RECEPCION, DOCS, E("Revisión del inmueble", "Revisamos certificados, gravámenes y situación del inmueble."),
        E("Elaboración de contrato", "Preparamos el contrato."), E("Revisión y firma", "Revisamos el contrato con usted y se firma."),
        E("Escrituración o registro", "Se formaliza o inscribe la operación.", True), E("Entrega", "Le entregamos sus documentos."), CIERRE]},
    "propiedad_intelectual": {"nombre": "Propiedad intelectual", "etapas": [
        RECEPCION, E("Búsqueda de anterioridades", "Revisamos si existen registros parecidos."),
        E("Preparación de la solicitud", "Preparamos la solicitud de registro."), E("Presentación ante el IMPI", "Presentamos la solicitud."),
        E("Examen de forma y fondo", "El IMPI revisa la solicitud."),
        E("Respuesta a requerimientos", "Si el IMPI pide algo, lo atendemos.", True),
        E("Resolución", "El IMPI resuelve."), E("Entrega del título", "Le entregamos su título o registro."), CIERRE]},
}

ESPECIALIDADES = {k: v["nombre"] for k, v in BASE.items()}

ESTADOS = {
    "pendiente": "Próxima", "actual": "Etapa actual", "completada": "Completada", "atencion": "Requiere su atención",
    "incidencia": "Incidencia", "suspendida": "Suspendida temporalmente", "omitida": "No aplica",
}


def limpiar_etapas(etapas: list[dict]) -> list[dict]:
    """Normaliza una lista de etapas que viene del editor."""
    out = []
    for e in etapas[:40]:
        n = str(e.get("nombre") or "").strip()[:120]
        if n:
            out.append({"nombre": n, "explicacion": (str(e.get("explicacion") or "").strip()[:500] or None),
                        "opcional": bool(e.get("opcional"))})
    return out
