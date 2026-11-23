/**
 * Manuales de usuario de Nomira, uno por módulo. Se muestran en /ayuda y desde el botón
 * «¿Cómo se usa?» de cada módulo. Las capturas están en /public/ayuda (datos de demostración ficticios).
 * Al cambiar una pantalla, actualice aquí el paso que la describe.
 */
export type Paso = { titulo: string; texto: string; imagen?: string; alt?: string };
export type Manual = {
  clave: string;
  modulo: string | null; // módulo que debe estar activo para verlo (null = todos)
  titulo: string;
  resumen: string;
  paraQue: string[];
  pasos: Paso[];
  consejos: string[];
  preguntas: { p: string; r: string }[];
};

export const MANUALES: Manual[] = [
  {
    clave: "primeros-pasos",
    modulo: null,
    titulo: "Primeros pasos",
    resumen: "Cómo está organizado Nomira, quién puede hacer qué y cómo proteger su cuenta.",
    paraQue: ["Ubicar cada módulo en el menú.", "Dar de alta a su equipo con el rol adecuado.", "Activar la verificación en dos pasos.", "Pedir ayuda a Nomira."],
    pasos: [
      { titulo: "Conozca el menú", imagen: "inicio-menu", alt: "Menú lateral agrupado en Nómina, Módulos y Mi despacho",
        texto: "El menú de la izquierda se divide en tres partes. Nómina reúne Expedientes y Catálogos. Módulos agrupa Agenda, Evidencia, AFORE, Leads y Academia (solo verá los que su despacho tiene contratados). Mi despacho tiene Usuarios, Mi empresa, Soporte y esta Ayuda. El número junto a Agenda indica cuántos pendientes vencieron o vencen hoy." },
      { titulo: "Invite a su equipo", imagen: "inicio-usuarios", alt: "Pantalla de Usuarios con el botón Nuevo usuario",
        texto: "En Usuarios → «+ Nuevo usuario» capture nombre, correo y rol. Administrador: todo, incluidos usuarios y ajustes. Analista: trabaja la información, pero no administra usuarios ni la empresa. Solo consulta: ve la información y marca como cumplido lo que le asignan. Abra «¿Qué puede hacer cada rol?» para ver el detalle." },
      { titulo: "Complete los datos de su empresa",
        texto: "En Mi empresa suba el logotipo y los datos del despacho. El logotipo aparece en el menú y en los diplomas de Academia." },
      { titulo: "Active la verificación en dos pasos", imagen: "inicio-perfil", alt: "Sección Verificación en dos pasos en Mi perfil",
        texto: "En Mi perfil → «Activar verificación en dos pasos». Escanee el código QR con una app de autenticación (Google Authenticator, Microsoft Authenticator…) y escriba el código de 6 dígitos. Guarde los 8 códigos de respaldo: le sirven si pierde el celular. Desde ahí también puede cerrar su sesión en los demás dispositivos." },
      { titulo: "Pida ayuda cuando la necesite",
        texto: "En Soporte escriba su duda o problema: el equipo de Nomira le responde ahí mismo y verá un número en el menú cuando haya respuesta. Cada módulo tiene el botón «¿Cómo se usa?» que abre su manual." },
    ],
    consejos: [
      "Cada persona con su propio usuario: no comparta cuentas.",
      "Si alguien deja el despacho, desactívelo en Usuarios: sus sesiones se cierran al instante.",
      "Al subir un archivo verá el logotipo de Nomira girando; al terminar aparece un aviso de éxito arriba.",
    ],
    preguntas: [
      { p: "Olvidé mi contraseña.", r: "Pida a un administrador de su despacho que le asigne una nueva desde Usuarios → Contraseña." },
      { p: "Perdí mi celular y mis códigos de respaldo.", r: "Un administrador puede quitarle la verificación en dos pasos desde Usuarios → «Quitar 2 pasos». Después actívela de nuevo." },
      { p: "No veo un módulo en el menú.", r: "Su despacho no lo tiene contratado. Escriba a Soporte para conocer los planes." },
    ],
  },
  {
    clave: "nomina",
    modulo: "nomina",
    titulo: "Nómina: expedientes y catálogos",
    resumen: "Sube los recibos de un trabajador, Nomira los lee y arma el desglose de prestaciones por quincena para que usted lo revise y valide.",
    paraQue: ["Calcular prestaciones a partir de recibos de nómina en PDF.", "Detectar quincenas faltantes, recibos duplicados o de otra persona.", "Exportar el resultado a Excel o PDF con su trazabilidad."],
    pasos: [
      { titulo: "Revise su catálogo de prestaciones", imagen: "nomina-catalogos", alt: "Pantalla de Catálogos de prestaciones",
        texto: "En Catálogos está la lista de claves que sí se suman (por ejemplo, 0101 Dietas). Solo se suman las percepciones cuya clave coincide con una clave activa del catálogo. Puede crear uno, leerlo desde un PDF («Leer catálogo desde PDF (OCR)») o capturarlo a mano. Un catálogo leído por OCR queda como borrador: revise las claves marcadas y actívelo." },
      { titulo: "Cree el expediente subiendo los recibos", imagen: "nomina-nuevo", alt: "Ventana Nuevo expediente con el botón Elegir PDF de recibos",
        texto: "En Expedientes → «+ Nuevo expediente» → «Elegir PDF de recibos». Nomira lee nombre, clave de servidor y periodos y llena el formulario por usted. Revise el periodo (debe iniciar el día 1 o 16 y terminar el 15 o fin de mes), elija la versión del catálogo y presione «Crear expediente»." },
      { titulo: "Lea el desglose por quincena", imagen: "nomina-desglose", alt: "Desglose por quincena del expediente",
        texto: "Cada tarjeta es una quincena con sus conceptos y su total. Las marcadas «Por revisar» tienen algo que confirmar; las rojas «Faltante» no tienen comprobante y no se les asigna importe. Arriba ve el total, cuántas quincenas tienen comprobante y cuántos pendientes hay." },
      { titulo: "Resuelva los pendientes", imagen: "nomina-revision", alt: "Pestaña Revisión con la lista de pendientes",
        texto: "En la pestaña Revisión aparece cada pendiente con su explicación (recibo duplicado, de otra persona, importe ilegible, clave que no está en el catálogo…). Presione «Revisar», decida y deje una nota. Cada decisión queda registrada en Trazabilidad." },
      { titulo: "Valide y exporte",
        texto: "Cuando no quedan pendientes, se activa «Validar resultado»: el resultado y la versión del catálogo quedan congelados. Use «Exportar Excel» o «Exportar PDF» para entregar el desglose. Si después necesita cambiar algo, «Reabrir» pide un motivo y queda en la bitácora." },
    ],
    consejos: [
      "Si el trabajador tiene varias plazas, el total se muestra por plaza. Use «Consolidar plazas» en Resultados si deben sumarse juntas.",
      "¿Faltan recibos? En Documentos use «Subir comprobantes PDF» y el desglose se recalcula solo.",
      "Si un concepto no se suma porque su clave no está en el catálogo, use «Agregar claves faltantes» en Catálogos: se crea una versión nueva que puede aplicar a los expedientes en revisión.",
    ],
    preguntas: [
      { p: "¿Por qué no puedo validar?", r: "Quedan pendientes por resolver. Debajo de los botones verá el aviso con el enlace a Revisión." },
      { p: "¿Por qué no puedo eliminar un catálogo?", r: "Porque lo usan expedientes: cada expediente guarda con qué catálogo se calculó. Al presionar «Eliminar catálogo» verá cuáles son." },
      { p: "Un PDF escaneado tarda en leerse.", r: "Es normal: cada página se lee como imagen (OCR). Verá «Leyendo…» mientras tanto." },
    ],
  },
  {
    clave: "evidencia",
    modulo: "evidencia",
    titulo: "Evidencia",
    resumen: "Organiza los documentos de un asunto, propone hechos y fechas con su fuente y señala diferencias entre fuentes para que usted decida.",
    paraQue: ["Tener en un solo lugar los documentos de un asunto.", "Construir la cronología y la matriz de hechos con su fuente.", "Detectar contradicciones entre lo que dicen distintas fuentes."],
    pasos: [
      { titulo: "Cree un asunto", imagen: "evidencia-lista", alt: "Lista de asuntos de Evidencia",
        texto: "En Evidencia → «+ Nuevo asunto» capture el nombre, el cliente, la materia y el responsable." },
      { titulo: "Suba los documentos",
        texto: "En la pestaña Documentos → «Subir documentos» (PDF o imágenes). Nomira los lee, sugiere de qué tipo son y propone hechos con la cita textual y la página de donde salen. Revise el aviso de lectura antes de aceptar." },
      { titulo: "Atienda «Requiere tu atención»", imagen: "evidencia-atencion", alt: "Pestaña Requiere tu atención con diferencias y hechos propuestos",
        texto: "Aquí se junta lo que necesita una decisión suya. En Posibles diferencias, compare las dos fuentes y elija «Son eventos distintos», «Diferencia aclarada», «Contradicción confirmada» o «No aplica». En Hechos propuestos, use «Confirmar», «Editar», «Descartar» o «No es relevante». En Documentos por clasificar, use «Clasificar»." },
      { titulo: "Consulte la cronología y la matriz", imagen: "evidencia-cronologia", alt: "Cronología del asunto",
        texto: "Cronología ordena los hechos confirmados por fecha. Matriz relaciona hechos con documentos. Buscar encuentra palabras en todos los documentos. Pendientes lista los documentos o datos que faltan." },
      { titulo: "Exporte",
        texto: "Use «Exportar PDF» o «Exportar Excel» para llevar la cronología y los hechos con sus fuentes." },
    ],
    consejos: [
      "Nomira propone; usted confirma. Un hecho propuesto no cuenta hasta que lo confirma.",
      "Cada hecho guarda el documento y la página de donde salió: use el enlace para verlo.",
      "Si un dato está mal leído, use «Corregir este dato»: la corrección queda en el Historial.",
    ],
    preguntas: [
      { p: "¿Nomira decide si un hecho es verdadero?", r: "No. Solo localiza, compara y organiza. La valoración jurídica es siempre del abogado." },
      { p: "Un documento salió con problemas de lectura.", r: "Aparece en «Documentos por clasificar o con problemas de lectura». Ábralo con «Ver» y clasifíquelo a mano." },
    ],
  },
  {
    clave: "afore",
    modulo: "afore",
    titulo: "AFORE",
    resumen: "Lleva los casos de AFORE y SAR: datos del titular, documentos, gestiones, plazos y comunicación con el cliente.",
    paraQue: ["Registrar casos de retiro, devoluciones, beneficiarios y aclaraciones.", "Saber qué documentos faltan y qué gestión espera respuesta.", "Mantener al cliente informado por portal o WhatsApp, con su aprobación."],
    pasos: [
      { titulo: "Empiece por el Resumen", imagen: "afore-resumen", alt: "Resumen de AFORE: qué requiere atención ahora",
        texto: "La pantalla «¿Qué requiere atención ahora?» junta los seguimientos vencidos o próximos, las gestiones sin respuesta, los clientes con documentos pendientes y los casos sin siguiente actividad. Use «Ver lista» en cada tarjeta." },
      { titulo: "Registre un caso nuevo", imagen: "afore-nuevo", alt: "Formulario Nuevo caso AFORE",
        texto: "Presione «+ Nuevo caso». Indique si el cliente es nuevo o ya registrado, quién se comunica, el titular de la cuenta, el problema y la siguiente actividad con su fecha. Si no tiene todos los datos, use «Guardar como borrador». Marque «Caso restringido» si solo deben verlo los administradores y el responsable." },
      { titulo: "Trabaje el caso por pestañas", imagen: "afore-caso", alt: "Detalle de un caso AFORE",
        texto: "Resumen: datos del caso y siguiente actividad. Checklist: documentos requeridos. Documentos: lo que entrega el cliente o la AFORE. Seguimiento: gestiones, folios y respuestas. ¿Expediente listo?: lo que falta para presentar. Portal y mensajes: comunicación con el cliente. Localizar AFORE y CURP: enlaces a los sitios oficiales." },
      { titulo: "Defina siempre la siguiente actividad",
        texto: "En Resumen → Siguiente actividad capture qué sigue, la fecha y quién la realiza. Así el caso no se queda en «sin siguiente actividad»." },
      { titulo: "Configure la comunicación",
        texto: "En Configuración puede conectar WhatsApp Business (API oficial de Meta) y decidir si los mensajes requieren aprobación de una persona antes de enviarse." },
    ],
    consejos: [
      "Los montos son datos que capturó el cliente o la AFORE: Nomira no los verifica ni proyecta resultados.",
      "En Catálogos y plantillas puede ajustar los documentos requeridos y los textos de mensajes de su despacho.",
    ],
    preguntas: [
      { p: "¿Nomira consulta la AFORE por mí?", r: "No. Abre los sitios oficiales (por ejemplo, AforeWeb) para que usted haga la consulta y registre el resultado." },
      { p: "¿El cliente ve todo el caso?", r: "No. Solo lo que usted marca como visible en el portal («Cliente lo ve»)." },
    ],
  },
  {
    clave: "leads",
    modulo: "leads",
    titulo: "Leads",
    resumen: "Recibe y da seguimiento a los prospectos que llegan por formulario, WhatsApp o anuncios, hasta que se vuelven clientes.",
    paraQue: ["Responder a tiempo a cada consulta.", "No perder el siguiente paso de cada prospecto.", "Saber qué campañas y fuentes traen clientes."],
    pasos: [
      { titulo: "Complete la configuración",
        texto: "En Configuración agregue el enlace del aviso de privacidad de su despacho (es obligatorio y Nomira se lo recuerda), sus materias o servicios y los motivos de «No contratado». Ahí mismo obtiene su formulario de contacto y puede conectar WhatsApp Business o los formularios de Facebook e Instagram." },
      { titulo: "Atienda la Bandeja", imagen: "leads-bandeja", alt: "Bandeja de Leads: a quién hay que atender",
        texto: "«¿A quién hay que atender?» ordena a los prospectos por urgencia: nuevos sin respuesta, consultas que esperan respuesta, citas próximas, seguimientos vencidos y prospectos sin próximo paso. Use «+ Agregar prospecto» para registrar a quien llamó o llegó a la oficina." },
      { titulo: "Trabaje cada prospecto",
        texto: "Dentro de un prospecto: «Definir el siguiente paso ahora», «Agendar consulta», «Enviar por WhatsApp» o «Enviar correo», y «Cambiar etapa». Cuando contrata, use «Completar alta» y, si aplica, abra el asunto en Evidencia o el caso en AFORE desde ahí." },
      { titulo: "Siga el embudo", imagen: "leads-seguimiento", alt: "Tablero de seguimiento por etapas",
        texto: "En Seguimiento ve a todos los prospectos por etapa (nuevo, contactado, consulta, propuesta, contratado…)." },
      { titulo: "Mida sus campañas", imagen: "leads-campanas", alt: "Campañas y fuentes",
        texto: "En Campañas y fuentes registre cada campaña: cada una tiene su enlace de formulario para saber de dónde llegó cada prospecto. En Resultados verá cuántos se contrataron por fuente." },
    ],
    consejos: [
      "Todo prospecto debe tener un próximo paso con fecha: así no se enfría.",
      "Nomira no publica anuncios ni envía mensajes masivos: solo recibe y organiza.",
    ],
    preguntas: [
      { p: "¿Cómo conecto mis anuncios de Facebook?", r: "En Configuración → «Anuncios de Facebook e Instagram» → «Conectar página». Necesita ser administrador de la página." },
      { p: "Un prospecto pidió que borremos sus datos.", r: "Dentro del prospecto use «Anonimizar»: se borran sus datos personales y se conservan solo las cifras." },
    ],
  },
  {
    clave: "academia",
    modulo: "academia",
    titulo: "Academia",
    resumen: "Capacitación del despacho: cursos de Nomira y cursos propios, con avance, cuestionarios, sesiones en vivo y diplomas.",
    paraQue: ["Capacitar a su equipo con cursos obligatorios o recomendados.", "Subir sus propios cursos (enlaces, videos, Excel o SCORM).", "Entregar diplomas verificables."],
    pasos: [
      { titulo: "Tome sus cursos", imagen: "academia-mi", alt: "Mi aprendizaje con cursos asignados",
        texto: "En Mi aprendizaje ve los cursos que le asignaron, lo que dejó a medias y lo que terminó. Presione «Iniciar curso» y avance lección por lección. Al terminar descargue su diploma o constancia." },
      { titulo: "Asigne cursos a su equipo",
        texto: "En Equipo, los administradores asignan cursos como obligatorios o recomendados, con fecha límite, y ven el avance de cada persona." },
      { titulo: "Cree o importe un curso propio", imagen: "academia-administrar", alt: "Administrar cursos",
        texto: "En Administrar → «Nuevo curso» o «Importar o pedir ayuda». Puede pegar enlaces de YouTube o Vimeo, llenar la plantilla de Excel, subir un paquete SCORM o pedir a Nomira que lo arme. Agregue lecciones, videos y cuestionarios, revise y publique. Su plan incluye 5 cursos propios." },
      { titulo: "Programe sesiones en vivo",
        texto: "En el editor del curso agregue una sesión en vivo con su fecha y el enlace de Zoom, Meet o Teams. Los participantes ven el botón para unirse 15 minutos antes y pueden agregarla a su calendario." },
    ],
    consejos: [
      "Los cursos de Nomira con costo se compran con tarjeta o por cotización desde la ficha del curso.",
      "Los enlaces de YouTube o Vimeo no ocupan espacio de su plan; los videos subidos sí.",
      "Cualquiera puede comprobar un diploma en nomirasoft.com/verificar con su folio.",
    ],
    preguntas: [
      { p: "No puedo crear más cursos.", r: "Llegó al límite de su plan. Archive un curso que ya no use o pida cursos adicionales a Nomira." },
      { p: "Ya no puedo subir videos.", r: "Se llenó el almacenamiento de su plan. Use enlaces de YouTube o Vimeo o contrate más espacio." },
    ],
  },
  {
    clave: "agenda",
    modulo: "agenda",
    titulo: "Agenda Jurídica",
    resumen: "Plazos, audiencias y actividades con responsables, cálculo asistido de días hábiles y avisos que escalan si algo se queda pendiente.",
    paraQue: ["Ver cada día lo vencido, lo de hoy y lo de la semana.", "Calcular plazos con el calendario de cada tribunal, con desglose.", "Que nadie se entere tarde de un vencimiento."],
    pasos: [
      { titulo: "Capture el calendario de su tribunal",
        texto: "En Días hábiles → «+ Nuevo calendario» capture los días inhábiles del tribunal (vacaciones, suspensiones) según su calendario oficial. Nomira ya incluye los días de descanso obligatorio del artículo 74 de la Ley Federal del Trabajo." },
      { titulo: "Revise su agenda de hoy", imagen: "agenda-hoy", alt: "Agenda de hoy",
        texto: "La vista Hoy muestra lo vencido sin cumplir, lo de hoy, los próximos 7 días, los plazos por validar y lo que no tiene responsable. Cambie entre «Todo el despacho» y «Solo lo mío». Marque «Cumplido» cuando termine." },
      { titulo: "Registre un plazo con cálculo asistido", imagen: "agenda-plazo", alt: "Formulario de plazo con desglose del cálculo",
        texto: "Presione «+ Plazo». Escriba qué hay que hacer, la fecha de notificación, los días, si son hábiles o naturales y cuándo surte efectos según la ley aplicable. Nomira muestra la fecha de vencimiento y el desglose de días contados y saltados. Si usted decide otra fecha, captúrela: queda anotada." },
      { titulo: "Valide el plazo",
        texto: "Todo plazo calculado queda «sin validar» hasta que un abogado revisa el desglose y presiona «Validar fecha». Si después cambia la fecha o el cálculo, hay que validarlo de nuevo." },
      { titulo: "Lleve sus asuntos y el calendario", imagen: "agenda-calendario", alt: "Calendario mensual",
        texto: "En Asuntos registre cada juicio con su tribunal, materia y actuaciones; al capturar una notificación, Nomira propone calcular el plazo. En Calendario ve el mes completo con los días inhábiles rayados." },
      { titulo: "Vigile sus expedientes en estrados (TRIJAEM)", imagen: "agenda-estrados", alt: "Pantalla de estrados digitales",
        texto: "Dentro del asunto pulse «Vigilar en estrados», escriba el número de expediente (por ejemplo 1234/2026), elija la sala y, si quiere, los números de sus promociones. Nomira revisa los estrados del TRIJAEM varias veces al día y avisa al responsable en cuanto se publica un acuerdo; en Agenda → Estrados lo ve con el enlace al acuerdo. Desde cada publicación puede pasarla al historial y calcular el plazo. También puede «Cotejar lista del día» pegando la lista o subiendo el PDF." },
    ],
    consejos: [
      "Los avisos llegan los días que configure (por omisión 5, 3, 1 y el mismo día). Si a mediodía del vencimiento sigue pendiente, avisa también a quien supervisa.",
      "En Avisos y ajustes puede generar un enlace privado para ver su agenda en Google Calendar u Outlook.",
      "Guarde en Días hábiles → «Plazos frecuentes del despacho» los plazos que usa seguido, con su fundamento.",
    ],
    preguntas: [
      { p: "¿Nomira decide el plazo?", r: "No. Ayuda a calcularlo con lo que usted captura. El abogado lo valida conforme a la ley y al calendario oficial del tribunal." },
      { p: "¿Nomira revisa los estrados solo?", r: "Sí, para el TRIJAEM: con el expediente y la sala, Nomira consulta sus estrados cada 3 horas en días hábiles. Si el tribunal no responde, lo verá marcado en el expediente y puede cotejar la lista del día. Confirme siempre en la consulta oficial." },
      { p: "No me llegan los correos de aviso.", r: "Revise en Avisos y ajustes que tenga activados los correos, y su carpeta de spam. Los avisos también se ven en la vista Hoy." },
    ],
  },
];

export const manual = (clave: string) => MANUALES.find((m) => m.clave === clave);
