"""Catálogos de Nomira AFORE. Son ayudas de organización editables por el despacho: no son listas
definitivas de requisitos legales ni plazos."""
from __future__ import annotations

TIPOS_PROBLEMA = {
    "tramite_no_atendido": "Trámite no atendido o no concluido",
    "separacion_cuentas": "Separación de cuentas",
    "unificacion_cuentas": "Unificación de cuentas",
    "inconformidad_saldo": "Inconformidad con saldo o movimientos",
    "inconformidad_retiro": "Inconformidad con monto de retiro",
    "traspaso_no_reconocido": "Traspaso que el titular no reconoce",
    "correccion_datos": "Corrección de datos o expediente de identificación",
    "recursos_pension": "Entrega de recursos relacionada con pensión o negativa de pensión",
    "beneficiario_fallecimiento": "Reclamo de beneficiario por fallecimiento",
    "otro": "Otro",
}

ESTADOS_REQUISITO = {
    "no_solicitado": "No solicitado", "solicitado": "Solicitado al cliente", "recibido": "Recibido",
    "por_revisar": "Por revisar", "aceptado": "Aceptado por el despacho", "requiere_correccion": "Requiere corrección",
    "no_aplica": "No aplica",
}
# Lo que ve el cliente en su portal (lenguaje sencillo; «no solicitado» y «no aplica» no se le muestran)
ESTADOS_REQUISITO_CLIENTE = {"solicitado": "Falta enviarlo", "recibido": "Recibido, en revisión", "por_revisar": "Recibido, en revisión",
                             "aceptado": "Recibido y revisado", "requiere_correccion": "Hace falta corregirlo"}
ESTADOS_CASO = {"borrador": "Borrador", "abierto": "En atención", "esperando": "Esperando respuesta", "pausado": "En pausa",
                "cerrado": "Cerrado"}
RELACIONES = {"titular": "Titular de la cuenta", "pensionado": "Pensionado(a)", "beneficiario": "Beneficiario(a)",
              "representante": "Representante", "familiar": "Familiar"}
TITULAR = {"vive": "Vive", "fallecio": "Falleció", "no_se": "No se sabe"}
CONTACTO = {"whatsapp": "WhatsApp", "correo": "Correo", "telefono": "Llamada", "ninguno": "Sin preferencia"}
ESTADOS_DATO = {"informado": "Dato informado", "no_lo_se": "No lo sé", "pendiente": "Pendiente de confirmar", "no_aplica": "No aplica"}
INSTITUCIONES = ["IMSS", "ISSSTE", "PENSIONISSSTE", "INFONAVIT", "FOVISSSTE", "CONSAR", "CONDUSEF", "Otra"]
# Sugerencias para escribir (texto libre; la lista de AFORE cambia con el tiempo)
AFORES = ["Azteca", "Banamex", "Coppel", "Inbursa", "Invercap", "PensionISSSTE", "Principal", "Profuturo", "SURA", "XXI Banorte"]
CAMPOS_DATO = {
    "afore": "AFORE involucrada", "afore_anterior": "AFORE anterior", "afore_receptora": "AFORE receptora",
    "institucion": "Institución relacionada", "regimen": "Régimen o tipo de resolución",
    "monto_cliente": "Monto que el cliente dice reclamar", "monto_afore": "Monto reportado por la AFORE",
    "monto_entregado": "Monto entregado",
}
CAMPOS_MONTO = ("monto_cliente", "monto_afore", "monto_entregado")
TIPOS_ACTIVIDAD = {
    "solicitud_enviada": "Solicitud presentada", "respuesta_recibida": "Respuesta recibida", "acuse": "Acuse recibido",
    "queja": "Queja o reclamación", "llamada": "Llamada", "reunion": "Reunión con el cliente",
    "localizacion_afore": "Consulta de localización de AFORE", "nota": "Nota interna",
}
TIPOS_PLAZO = {
    "legal_confirmado": "Plazo legal confirmado por el abogado", "seguimiento_interno": "Fecha interna de seguimiento",
    "informado_institucion": "Tiempo de atención informado por la institución", "estimado": "Fecha estimada / por confirmar",
}

_BASE = ["Identificación oficial", "CURP", "NSS (si cotizó en el IMSS)", "Estado de cuenta AFORE reciente"]
CHECKLIST_DEFECTO = {
    "tramite_no_atendido": _BASE + ["Solicitud presentada a la AFORE (acuse)", "Folio del trámite", "Respuesta de la AFORE (si existe)"],
    "separacion_cuentas": _BASE + ["Estados de cuenta de cada cuenta", "Documentos que muestren los datos de cada persona", "Folio de la solicitud"],
    "unificacion_cuentas": _BASE + ["Estados de cuenta de las cuentas a unificar", "Constancias de semanas cotizadas", "Folio de la solicitud"],
    "inconformidad_saldo": _BASE + ["Estados de cuenta del periodo en cuestión", "Folio de queja o aclaración", "Respuesta de la AFORE"],
    "inconformidad_retiro": _BASE + ["Comprobante del retiro o depósito", "Resolución de pensión o negativa (si aplica)",
                                     "Estado de cuenta bancario donde se depositó", "Respuesta de la AFORE"],
    "traspaso_no_reconocido": _BASE + ["Constancia o aviso del traspaso", "Estado de cuenta de la AFORE anterior",
                                       "Estado de cuenta de la AFORE receptora", "Folio de reclamación"],
    "correccion_datos": _BASE + ["Acta de nacimiento", "Documento con el dato correcto", "Expediente de identificación (si se tiene)"],
    "recursos_pension": _BASE + ["Resolución de pensión o negativa", "Solicitudes presentadas a la AFORE", "Documentos bancarios (CLABE)",
                                 "Respuestas recibidas"],
    "beneficiario_fallecimiento": ["Identificación oficial de quien reclama", "CURP de quien reclama", "Acta de defunción del titular",
                                   "CURP y NSS del titular", "Documentos de parentesco o relación (actas)", "Resolución de pensión o negativa (si existe)",
                                   "Estado de cuenta AFORE del titular", "Documentos bancarios (CLABE)"],
    "otro": _BASE,
}

PLANTILLAS = {
    "solicitud_recibida": ("Confirmar que se recibió una solicitud",
                           "Hola, {nombre}. El despacho recibió tu solicitud y ya está en revisión. Te avisaremos por este medio cuando haya novedades."),
    "falta_documentacion": ("Avisar que falta documentación",
                            "Hola, {nombre}. Para avanzar con tu trámite necesitamos algunos documentos. Consulta cuáles en tu portal seguro de Nomira: {enlace}"),
    "documento_recibido": ("Confirmar recepción de un documento",
                           "Hola, {nombre}. Recibimos tu documento. El despacho lo revisará y te avisará si hace falta algo más."),
    "respuesta_registrada": ("Informar que se registró una respuesta o movimiento",
                             "Hola, {nombre}. El despacho registró un movimiento en tu trámite. Consulta los detalles en tu portal seguro de Nomira: {enlace}"),
    "actualizacion_portal": ("Avisar que hay una actualización en el portal",
                             "Hola, {nombre}. El despacho registró una actualización de tu trámite. Consulta los detalles en tu portal seguro de Nomira: {enlace}"),
    "recordatorio": ("Recordar una cita o seguimiento",
                     "Hola, {nombre}. Te recordamos que tienes un seguimiento pendiente con el despacho. Si tienes dudas, responde a este mensaje."),
}
