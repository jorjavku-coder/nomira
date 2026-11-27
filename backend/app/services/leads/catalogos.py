"""Catálogos de Nomira Leads. Lenguaje sencillo: el despacho puede ajustar etapas, materias y motivos."""

CANALES = {
    "whatsapp": "WhatsApp", "correo": "Correo electrónico", "facebook": "Facebook", "instagram": "Instagram",
    "tiktok": "TikTok", "google": "Google (búsqueda o anuncios)", "linkedin": "LinkedIn", "sitio_web": "Sitio web",
    "referido": "Recomendación o referido", "llamada": "Llamada telefónica", "visita": "Visita a la oficina",
    "evento": "Evento o plática", "nomira": "Nomira (calculadora de finiquito)", "otro": "Otro",
}
# Canales que funcionan como campañas en redes sociales (para agrupar en reportes)
REDES = ("facebook", "instagram", "tiktok", "linkedin")

ETAPAS_DEFECTO = [
    ("nuevo", "Nuevo", "abierta"), ("contactado", "Contactado", "abierta"), ("consulta_agendada", "Consulta agendada", "abierta"),
    ("consulta_realizada", "Consulta realizada", "abierta"), ("propuesta_enviada", "Propuesta enviada", "abierta"),
    ("contratado", "Contratado", "ganada"), ("no_contratado", "No contratado", "perdida"),
]

MOTIVOS_DEFECTO = ["No respondió", "No asistió a la consulta", "Fuera de especialidad", "Precio", "Contrató otro despacho",
                   "Ya no lo necesita", "Datos de contacto incorrectos", "Otro"]

MATERIAS_DEFECTO = ["Laboral", "Familiar", "Civil", "Mercantil", "Penal", "Administrativo", "Fiscal", "Seguridad social (IMSS, ISSSTE)",
                    "AFORE y retiro", "Amparo", "Migratorio", "Otro"]

TIPOS_ACCION = {"llamada": "Llamar", "mensaje": "Enviar mensaje", "consulta": "Consulta", "propuesta": "Enviar propuesta",
                "seguimiento": "Dar seguimiento"}

PREFERENCIAS = {"whatsapp": "WhatsApp", "llamada": "Llamada", "correo": "Correo", "ninguno": "No desea ser contactado"}
CANALES_CONSENTIMIENTO = {"whatsapp": "WhatsApp", "correo": "Correo", "llamada": "Llamada telefónica"}
MEDIOS_CONSENTIMIENTO = {"verbal": "De palabra (en llamada o en persona)", "escrito": "Por escrito", "formulario_web": "Formulario web de Nomira",
                         "formulario_meta": "Formulario de anuncio de Meta", "mensaje": "Por mensaje", "integracion": "Otro sistema (integración)"}

ESTADOS_MENSAJE = {"enviado": "Enviado", "entregado": "Entregado", "leido": "Leído", "fallido": "Falló", "recibido": "Recibido",
                   "por_asignar": "Por asignar", "manual": "Registrado (enviado fuera de Nomira)"}

FINALIDAD = "Responder su consulta y dar seguimiento a su solicitud de servicios jurídicos"
