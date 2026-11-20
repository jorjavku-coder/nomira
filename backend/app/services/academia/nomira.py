"""Cursos que ofrece Nomira a todos los despachos con Academia activa. Son prácticos y operativos
(no contienen criterios jurídicos). Los despachos no los editan, pero pueden duplicarlos para
adaptarlos. Se crean una sola vez (por su clave) y se actualizan aquí con una nueva versión."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models as m

P = lambda pregunta, opciones, correcta, explicacion: {"pregunta": pregunta, "opciones": opciones, "correcta": correcta, "explicacion": explicacion}  # noqa: E731

CURSOS = [
    {
        "clave": "nomira-atencion-inicial", "titulo": "Atención inicial de clientes", "materia": "Atención a clientes",
        "roles": ["Recepción", "Asistentes", "Abogados"], "duracion_min": 25, "calificacion_minima": 70,
        "descripcion": "Cómo recibir una primera consulta con orden y empatía: qué preguntar, qué registrar, qué no prometer y cómo "
                       "acordar el siguiente paso.",
        "modulos": [
            ("Antes de la primera conversación", [
                ("Prepárese en dos minutos", "Antes de devolver una llamada o un mensaje, revise lo que ya se sabe: nombre, cómo llegó al "
                 "despacho y qué escribió. Tenga a la mano la agenda de los abogados para proponer una cita.\n\n"
                 "• Salude por su nombre y preséntese con el nombre del despacho.\n• Pregunte si es buen momento para hablar.\n"
                 "• Si no puede atender en ese momento, acuerde una hora concreta para llamar.",
                 P("¿Qué conviene hacer si la persona no puede hablar en ese momento?",
                   ["Insistir para no perder el contacto", "Acordar una hora concreta para llamar", "Enviarle por escrito la estrategia del caso"], 1,
                   "Acordar una hora concreta respeta su tiempo y deja un próximo paso claro.")),
            ]),
            ("Durante la consulta inicial", [
                ("Escuchar y registrar", "Deje que la persona cuente su situación sin interrumpir. Después, confirme los datos básicos: cómo "
                 "contactarle, qué necesita, si hay fechas importantes que ya conoce y qué documentos tiene.\n\n"
                 "Registre los hechos tal como la persona los cuenta, sin calificarlos. Si algo no está claro, anótelo como pendiente "
                 "de confirmar.", None),
                ("Lo que no se promete", "En una primera conversación no se garantizan resultados, montos ni tiempos. La evaluación del "
                 "caso la hace el abogado responsable después de revisar la información y los documentos.\n\n"
                 "Puede explicar con claridad el proceso del despacho: quién atenderá, cuándo será la consulta y qué conviene llevar.",
                 P("Una persona pregunta: «¿Seguro que voy a ganar?». ¿Qué responde quien la atiende por primera vez?",
                   ["Sí, para animarla", "Que el abogado evaluará su caso en la consulta y le explicará sus opciones",
                    "Un porcentaje aproximado de éxito"], 1,
                   "Nadie del equipo debe prometer resultados: la evaluación corresponde al abogado responsable.")),
            ]),
            ("Después de la conversación", [
                ("Siguiente paso y seguimiento", "Toda consulta debe terminar con un siguiente paso acordado: una cita, el envío de "
                 "documentos o una llamada de seguimiento, con responsable y fecha.\n\n"
                 "Confirme por el medio que la persona prefiera (y que haya autorizado) y registre en el sistema lo que se acordó.",
                 P("¿Qué debe quedar registrado al terminar una consulta inicial?",
                   ["Solo el nombre de la persona", "El siguiente paso, su responsable y su fecha", "Nada, si la persona no contrató"], 1,
                   "Un siguiente paso con responsable y fecha evita que la persona quede sin respuesta.")),
            ]),
        ],
        "preguntas": [
            ("Al iniciar una llamada con un prospecto, lo primero es…", ["Hablar de honorarios", "Saludar, presentarse y preguntar si es buen momento",
                                                                        "Pedir todos sus documentos"], 1, "Un inicio claro y respetuoso facilita la conversación."),
            ("Si un dato de la persona no está claro, conviene…", ["Suponer lo más probable", "Anotarlo como pendiente de confirmar", "Omitirlo"], 1,
             "Registrar lo que falta evita errores y permite confirmarlo después."),
            ("¿Quién evalúa el caso y sus posibilidades?", ["Quien contesta el teléfono", "El abogado responsable", "El sistema"], 1,
             "La evaluación jurídica corresponde siempre al abogado."),
        ],
    },
    {
        "clave": "nomira-confidencialidad", "titulo": "Manejo de información confidencial en el despacho", "materia": "Confidencialidad",
        "roles": ["Todo el equipo"], "duracion_min": 20, "calificacion_minima": 80,
        "descripcion": "Hábitos prácticos para proteger los datos de los clientes en el día a día: documentos, mensajes, contraseñas y qué "
                       "hacer si algo sale mal. No sustituye el aviso de privacidad ni las políticas de su despacho.",
        "modulos": [
            ("Hábitos diarios", [
                ("Documentos y pantallas", "• No deje expedientes ni documentos de clientes a la vista en escritorios o salas.\n"
                 "• Bloquee su computadora cuando se levante.\n• Imprima solo lo necesario y recójalo de inmediato.\n"
                 "• Use los sistemas del despacho para guardar documentos, no carpetas personales.", None),
                ("Mensajes y correos", "Antes de enviar, confirme el destinatario. No reenvíe documentos de clientes a cuentas personales ni "
                 "los comparta por grupos de mensajería.\n\nSi necesita pedir un documento a un cliente, use el medio seguro que defina el "
                 "despacho (por ejemplo, un enlace de carga) en lugar de pedirle fotos por chat.",
                 P("Un cliente ofrece mandar su identificación por un grupo de WhatsApp. ¿Qué conviene hacer?",
                   ["Aceptar para ahorrar tiempo", "Pedirle que use el medio seguro del despacho", "Pedirle que la publique en la nube"], 1,
                   "Los documentos deben llegar por el medio seguro que defina el despacho.")),
            ]),
            ("Contraseñas e incidentes", [
                ("Contraseñas", "Use contraseñas largas y distintas para cada sistema. No las comparta ni las anote a la vista. Si sospecha "
                 "que alguien conoce su contraseña, cámbiela de inmediato.", None),
                ("Si algo sale mal", "Si envió información a quien no debía, perdió un documento o un equipo, avise de inmediato a la persona "
                 "responsable en su despacho. Avisar rápido permite reducir el daño; ocultarlo lo empeora.",
                 P("Enviaste por error un documento de un cliente a otra persona. ¿Qué haces?",
                   ["Esperar a ver si alguien se da cuenta", "Avisar de inmediato a la persona responsable del despacho", "Borrar tu copia y olvidarlo"], 1,
                   "Avisar de inmediato es lo correcto: permite actuar a tiempo.")),
            ]),
        ],
        "preguntas": [
            ("¿Qué hacer al levantarte de tu lugar?", ["Dejar la sesión abierta", "Bloquear la computadora", "Apagar el monitor"], 1,
             "Bloquear evita que otra persona vea o use tu sesión."),
            ("¿Dónde se guardan los documentos de clientes?", ["En carpetas personales", "En los sistemas del despacho", "En el correo personal"], 1,
             "Los sistemas del despacho controlan quién accede."),
            ("Si sospechas que alguien conoce tu contraseña…", ["La cambias de inmediato", "Esperas al siguiente mes", "La compartes con tu jefe"], 0,
             "Cambiarla de inmediato corta el acceso no autorizado."),
        ],
    },
    {
        "clave": "nomira-seguimiento", "titulo": "Seguimiento ordenado de asuntos", "materia": "Procesos internos",
        "roles": ["Abogados", "Asistentes"], "duracion_min": 15, "calificacion_minima": None,
        "descripcion": "Cómo mantener cada asunto con un siguiente paso claro, registrar lo que pasa y distinguir un seguimiento interno "
                       "de una fecha que confirma el abogado.",
        "modulos": [
            ("Orden en el día a día", [
                ("Siempre un siguiente paso", "Cada asunto abierto debe tener una próxima actividad con responsable y fecha. Si no la tiene, "
                 "es fácil que se quede detenido sin que nadie lo note.\n\nAl terminar cualquier gestión, registre qué pasó y defina lo "
                 "que sigue.", None),
                ("Fechas: no todas son iguales", "Distinga entre un seguimiento interno (por ejemplo, «llamar al cliente el jueves») y una "
                 "fecha que el abogado confirmó como relevante para el asunto. Las segundas solo las define el abogado responsable.",
                 P("¿Quién confirma una fecha relevante para el asunto?", ["Cualquier persona del equipo", "El abogado responsable", "El cliente"], 1,
                   "Las fechas relevantes del asunto las confirma el abogado responsable.")),
                ("Registrar sin interpretar", "Al anotar una llamada o un documento, escriba lo que ocurrió y quién lo dijo. Si es una "
                 "interpretación o una duda, márquela como tal. Así cualquier persona del equipo puede retomar el asunto.", None),
            ]),
        ],
        "preguntas": [],
    },
]


def asegurar(db: Session) -> None:
    """Crea los cursos de Nomira que falten. Seguro aunque varios procesos lo ejecuten a la vez."""
    existentes = set(db.scalars(select(m.AcCurso.clave).where(m.AcCurso.organizacion_id.is_(None))))
    for c in CURSOS:
        if c["clave"] in existentes:
            continue
        try:
            with db.begin_nested():
                curso = m.AcCurso(organizacion_id=None, clave=c["clave"], titulo=c["titulo"], materia=c["materia"], roles=c["roles"],
                                  instructor="Equipo Nomira", institucion=None, descripcion=c["descripcion"], duracion_min=c["duracion_min"],
                                  modalidad="autodirigido", estado="publicado", juridico=False, calificacion_minima=c["calificacion_minima"],
                                  publicado_en=m.ahora(), version=1)
                db.add(curso)
                db.flush()
                for i, (titulo, lecciones) in enumerate(c["modulos"]):
                    mod = m.AcModulo(curso_id=curso.id, titulo=titulo, orden=i)
                    db.add(mod)
                    db.flush()
                    for j, (lt, texto, act) in enumerate(lecciones):
                        db.add(m.AcLeccion(curso_id=curso.id, modulo_id=mod.id, titulo=lt, orden=j, texto=texto, actividad=act, duracion_min=5))
                for k, (texto, opciones, correcta, expl) in enumerate(c["preguntas"]):
                    db.add(m.AcPregunta(curso_id=curso.id, texto=texto, opciones=opciones, correcta=correcta, explicacion=expl, orden=k))
                db.flush()
        except IntegrityError:
            pass
    db.commit()
