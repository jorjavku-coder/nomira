/** Qué es cada parte de Nomira, en palabras de abogado. Lo usan Inicio y el menú para que todo diga lo mismo.
 *  ``requiere``: clave del módulo contratado (null = incluido en todos los planes). */
export type Seccion = {
  clave: string; nombre: string; href: string; icono: string; grupo: string; requiere: string | null;
  para: string; ejemplo: string; empezar: [string, string]; ayuda: string;
};

export const GRUPOS = ["Día a día", "Casos y trámites", "Crecer el despacho"];

export const SECCIONES: Seccion[] = [
  { clave: "agenda", nombre: "Agenda", href: "/agenda", icono: "agenda", grupo: "Día a día", requiere: "agenda",
    para: "Que no se te pase ningún plazo ni audiencia: qué vence hoy, quién es responsable y qué publicaron los tribunales.",
    ejemplo: "Capturas un acuerdo con plazo de 15 días hábiles y Nomira calcula la fecha y te avisa antes.",
    empezar: ["Registrar un plazo", "/agenda"], ayuda: "agenda" },
  { clave: "clientes", nombre: "Clientes y cobranza", href: "/clientes", icono: "clientes", grupo: "Día a día", requiere: null,
    para: "Todos tus clientes en un solo lugar: datos, documentos, honorarios, pagos y quién te debe.",
    ejemplo: "Registras unos honorarios a pagos y ves quién está vencido; mandas el recordatorio o una liga de pago.",
    empezar: ["Dar de alta un cliente", "/clientes"], ayuda: "clientes" },
  { clave: "asistente", nombre: "Asistente IA", href: "/asistente", icono: "asistente", grupo: "Día a día", requiere: null,
    para: "Borradores de escritos, resúmenes de documentos y respuestas con tesis reales del Semanario. No inventa citas.",
    ejemplo: "Pegas un acuerdo y te explica qué ordena y qué plazo corre; o le pides una contestación de demanda.",
    empezar: ["Investigar con tesis", "/asistente?tipo=investigar"], ayuda: "asistente" },
  { clave: "tesis", nombre: "Tesis (SJF)", href: "/tesis", icono: "tesis", grupo: "Día a día", requiere: null,
    para: "Buscador de tesis y jurisprudencia oficiales, con su registro digital, ficha PDF y liga al Semanario.",
    ejemplo: "Buscas «suspensión clausura» y copias la cita lista para tu escrito.",
    empezar: ["Buscar una tesis", "/tesis"], ayuda: "tesis" },
  { clave: "evidencia", nombre: "Evidencia", href: "/evidencia", icono: "evidencia", grupo: "Casos y trámites", requiere: "evidencia",
    para: "Prepara la prueba de un juicio: sube los documentos, ubica cada hecho con su página y ve qué punto no tiene prueba.",
    ejemplo: "Subes contrato, recibos y correos; Nomira arma la cronología y te muestra qué falta probar.",
    empezar: ["Crear un asunto", "/evidencia"], ayuda: "evidencia" },
  { clave: "liquidaciones", nombre: "Liquidaciones LFT", href: "/liquidaciones", icono: "liquidaciones", grupo: "Casos y trámites", requiere: "nomina",
    para: "Calcula finiquitos e indemnizaciones con la Ley Federal del Trabajo, con la operación y el fundamento de cada concepto.",
    ejemplo: "Despido injustificado de 4 años: indemnización, 20 días, prima de antigüedad, vacaciones y propuesta de convenio.",
    empezar: ["Hacer un cálculo", "/liquidaciones"], ayuda: "liquidaciones" },
  { clave: "nomina", nombre: "Revisión de nómina", href: "/app", icono: "expedientes", grupo: "Casos y trámites", requiere: "nomina",
    para: "Lee los recibos de nómina en PDF de un trabajador y desglosa sus prestaciones quincena por quincena.",
    ejemplo: "Subes 3 años de recibos y obtienes el total por prestación y las quincenas que faltan.",
    empezar: ["Nuevo expediente de nómina", "/app"], ayuda: "nomina" },
  { clave: "escrituracion", nombre: "Escrituración", href: "/escrituracion", icono: "escrituracion", grupo: "Casos y trámites", requiere: "escrituracion",
    para: "Para notarías: cada escritura con sus etapas, documentos y vigencias, y un enlace para que el cliente vea el avance.",
    ejemplo: "Una compraventa muestra en rojo el certificado que falta y en verde cuando ya está lista para firmar.",
    empezar: ["Abrir una escritura", "/escrituracion"], ayuda: "escrituracion" },
  { clave: "afore", nombre: "AFORE", href: "/afore", icono: "afore", grupo: "Casos y trámites", requiere: "afore",
    para: "Trámites de AFORE y del SAR: documentos del cliente, folios, seguimientos y un portal para que el cliente suba papeles.",
    ejemplo: "Un retiro por desempleo: checklist de requisitos, folio de la AFORE y recordatorio de seguimiento.",
    empezar: ["Abrir un caso AFORE", "/afore"], ayuda: "afore" },
  { clave: "leads", nombre: "Prospectos", href: "/leads", icono: "leads", grupo: "Crecer el despacho", requiere: "leads",
    para: "Las personas que preguntan por tus servicios: a quién contestar, citas, seguimientos y de dónde llegan tus clientes.",
    ejemplo: "Llega un mensaje de Facebook; lo registras, agendas la consulta y ves si se convirtió en cliente.",
    empezar: ["Agregar un prospecto", "/leads"], ayuda: "leads" },
  { clave: "bolsa", nombre: "Bolsa de trabajo", href: "/bolsa", icono: "bolsa", grupo: "Crecer el despacho", requiere: null,
    para: "Publica vacantes gratis, recibe CVs y, con la versión premium, aplica pruebas psicométricas en línea.",
    ejemplo: "Publicas «Pasante de amparo», compartes el enlace y comparas a los candidatos por etapa.",
    empezar: ["Publicar una vacante", "/bolsa"], ayuda: "bolsa" },
  { clave: "academia", nombre: "Academia", href: "/academia", icono: "academia", grupo: "Crecer el despacho", requiere: "academia",
    para: "Capacita a tu equipo con cursos cortos, cuestionarios y constancias; sabes quién ya terminó.",
    ejemplo: "Asignas «Atención inicial de clientes» a los pasantes nuevos con fecha límite.",
    empezar: ["Ver cursos", "/academia"], ayuda: "academia" },
];
