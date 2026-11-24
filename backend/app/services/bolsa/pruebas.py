"""Pruebas de Nomira para candidatos.

- Personalidad: los 50 marcadores de cinco factores del International Personality Item Pool (IPIP, Goldberg 1992),
  de dominio público (ipip.ori.org). Traducción al español de Nomira. No es un instrumento clínico ni tiene baremo
  mexicano: el resultado es un perfil para comparar candidatos y orientar la entrevista.
- Razonamiento numérico, verbal y atención al detalle: reactivos propios de Nomira.
- Conocimientos jurídicos (laboral, amparo, civil): reactivos propios de Nomira sobre reglas estables de la ley,
  revisados a la fecha que indica cada prueba. El despacho puede copiarlas a sus pruebas propias para ajustarlas.

Ninguna prueba decide por sí sola: el resultado es un dato más para la persona que entrevista.
"""
from __future__ import annotations

LIKERT = ["Muy en desacuerdo", "En desacuerdo", "Ni de acuerdo ni en desacuerdo", "De acuerdo", "Muy de acuerdo"]

# (texto, factor, +1 directo / -1 inverso). Orden original del IPIP de 50 reactivos.
_BIG5 = [
    ("Soy el alma de la fiesta.", "E", 1), ("Me preocupan poco los demás.", "A", -1), ("Siempre estoy preparado.", "C", 1),
    ("Me estreso con facilidad.", "N", -1), ("Tengo un vocabulario amplio.", "O", 1), ("No hablo mucho.", "E", -1),
    ("Me interesa la gente.", "A", 1), ("Dejo mis cosas tiradas.", "C", -1), ("Estoy relajado la mayor parte del tiempo.", "N", 1),
    ("Me cuesta entender ideas abstractas.", "O", -1), ("Me siento cómodo con otras personas.", "E", 1), ("Insulto a la gente.", "A", -1),
    ("Pongo atención a los detalles.", "C", 1), ("Me preocupo por las cosas.", "N", -1), ("Tengo una imaginación muy viva.", "O", 1),
    ("Me mantengo en segundo plano.", "E", -1), ("Comparto los sentimientos de los demás.", "A", 1), ("Hago un desorden de las cosas.", "C", -1),
    ("Rara vez me siento triste.", "N", 1), ("No me interesan las ideas abstractas.", "O", -1), ("Inicio las conversaciones.", "E", 1),
    ("No me interesan los problemas de otras personas.", "A", -1), ("Hago mis pendientes de inmediato.", "C", 1),
    ("Me altero con facilidad.", "N", -1), ("Tengo ideas excelentes.", "O", 1), ("Tengo poco que decir.", "E", -1),
    ("Tengo un corazón blando.", "A", 1), ("Con frecuencia olvido regresar las cosas a su lugar.", "C", -1), ("Me molesto con facilidad.", "N", -1),
    ("No tengo buena imaginación.", "O", -1), ("En las reuniones hablo con muchas personas distintas.", "E", 1),
    ("En realidad no me interesan los demás.", "A", -1), ("Me gusta el orden.", "C", 1), ("Cambio mucho de humor.", "N", -1),
    ("Entiendo las cosas rápido.", "O", 1), ("No me gusta llamar la atención.", "E", -1), ("Me doy tiempo para los demás.", "A", 1),
    ("Evado mis obligaciones.", "C", -1), ("Tengo cambios de ánimo frecuentes.", "N", -1), ("Uso palabras difíciles.", "O", 1),
    ("No me molesta ser el centro de atención.", "E", 1), ("Siento las emociones de los demás.", "A", 1), ("Sigo un horario.", "C", 1),
    ("Me irrito con facilidad.", "N", -1), ("Dedico tiempo a reflexionar sobre las cosas.", "O", 1), ("Soy callado con los desconocidos.", "E", -1),
    ("Hago que la gente se sienta a gusto.", "A", 1), ("Soy exigente en mi trabajo.", "C", 1), ("Con frecuencia me siento triste.", "N", -1),
    ("Estoy lleno de ideas.", "O", 1),
]
FACTORES = {
    "E": ("Extroversión", "Qué tanto busca el trato con otras personas y se siente cómodo hablando en grupo.",
          "Prefiere el trabajo individual y tranquilo.", "Busca el contacto con la gente; cómodo al frente de reuniones."),
    "A": ("Amabilidad", "Cooperación, empatía y trato cordial.", "Directo y competitivo; puede priorizar la tarea sobre el trato.",
          "Cooperativo y empático; cuida la relación con clientes y equipo."),
    "C": ("Responsabilidad", "Orden, cumplimiento de pendientes y atención al detalle.", "Más flexible y espontáneo; conviene acompañar plazos y orden.",
          "Ordenado y cumplido; sigue plazos y cuida los detalles."),
    "N": ("Estabilidad emocional", "Calma ante la presión y manejo del estrés.", "Le afecta más la presión; conviene revisar cómo maneja cargas y urgencias.",
          "Se mantiene tranquilo bajo presión."),
    "O": ("Apertura intelectual", "Curiosidad, imaginación e interés por ideas nuevas.", "Prefiere lo práctico y probado.",
          "Curioso y creativo; disfruta analizar ideas complejas."),
}


def _opcion(texto: str, opciones: list[str], correcta: int) -> dict:
    return {"texto": texto, "opciones": opciones, "correcta": correcta}


NUMERICO = [
    _opcion("Un despacho cobra $18,000 de honorarios y el cliente paga 40 % de anticipo. ¿Cuánto queda pendiente?", ["$7,200", "$10,800", "$11,200", "$12,000"], 1),
    _opcion("Si 3 pasantes revisan 45 expedientes en 5 días, ¿cuántos expedientes revisa en promedio cada pasante por día?", ["3", "5", "9", "15"], 0),
    _opcion("¿Qué número sigue? 2, 6, 18, 54, …", ["72", "108", "162", "216"], 2),
    _opcion("Un monto de $5,000 más IVA de 16 %, ¿cuánto da en total?", ["$5,016", "$5,160", "$5,800", "$6,600"], 2),
    _opcion("¿Qué número sigue? 3, 5, 9, 17, 33, …", ["49", "64", "65", "66"], 2),
    _opcion("Si el salario diario es de $400, ¿cuánto suman 15 días de salario?", ["$4,000", "$5,600", "$6,000", "$6,400"], 2),
    _opcion("Un precio bajó de $2,000 a $1,500. ¿En qué porcentaje bajó?", ["20 %", "25 %", "30 %", "33 %"], 1),
    _opcion("Si 4 copias cuestan $10, ¿cuánto cuestan 26 copias?", ["$60.00", "$62.50", "$65.00", "$104.00"], 2),
    _opcion("¿Cuál es el promedio de 7, 9, 10 y 6?", ["7.5", "8", "8.5", "9"], 1),
    _opcion("Una audiencia empieza a las 9:40 y dura 2 horas 35 minutos. ¿A qué hora termina?", ["11:15", "12:05", "12:15", "12:25"], 2),
    _opcion("¿Qué número sigue? 100, 95, 85, 70, 50, …", ["20", "25", "30", "35"], 1),
    _opcion("Un plazo de 15 días hábiles, con semanas de 5 días hábiles y sin días inhábiles adicionales, ¿cuántas semanas completas abarca?", ["2", "3", "4", "5"], 1),
]

VERBAL = [
    _opcion("¿Qué significa «diligente»?", ["Cuidadoso y activo", "Lento", "Descuidado", "Indeciso"], 0),
    _opcion("¿Cuál es lo contrario de «efímero»?", ["Pasajero", "Breve", "Duradero", "Frágil"], 2),
    _opcion("Juez es a sentencia como legislador es a…", ["Tribunal", "Ley", "Demanda", "Abogado"], 1),
    _opcion("Plazo es a días como distancia es a…", ["Velocidad", "Kilómetros", "Camino", "Reloj"], 1),
    _opcion("¿Qué palabra no pertenece al grupo?", ["Demanda", "Contestación", "Reconvención", "Vacaciones"], 3),
    _opcion("Todos los socios del despacho son abogados. Laura no es abogada. Por lo tanto…", ["Laura es socia", "Laura no es socia", "Laura es pasante", "No se puede concluir nada"], 1),
    _opcion("Ningún expediente cerrado tiene plazos pendientes. El expediente 12 tiene plazos pendientes. Por lo tanto…",
            ["El expediente 12 está cerrado", "El expediente 12 no está cerrado", "El expediente 12 vence hoy", "No se puede concluir nada"], 1),
    _opcion("¿Cuál está bien escrita?", ["Precripción", "Prescripción", "Prescrisión", "Prescipción"], 1),
    _opcion("¿Qué significa «ratificar»?", ["Anular", "Confirmar", "Revisar", "Retrasar"], 1),
    _opcion("En un juicio, ¿qué ocurre primero?", ["La sentencia", "El emplazamiento", "La presentación de la demanda", "La contestación"], 2),
    _opcion("«El cliente debe entregar sus documentos a más tardar el viernes; si no lo hace, la audiencia del lunes se reprogramará.» "
            "El cliente los entregó el jueves. Según el texto…", ["La audiencia se reprograma", "La audiencia sigue el lunes", "La audiencia se cancela", "El texto no dice nada al respecto"], 1),
    _opcion("¿Cuál es lo contrario de «explícito»?", ["Claro", "Tácito", "Expreso", "Evidente"], 1),
]

_IG, _DIF = "Son iguales", "Son diferentes"
ATENCION = [
    _opcion("Compare: «Exp. 1452/2025-III» y «Exp. 1452/2025-III»", [_IG, _DIF], 0),
    _opcion("Compare: «RFC GOMJ800101AB3» y «RFC GOMJ800101A83»", [_IG, _DIF], 1),
    _opcion("Compare: «Juzgado Tercero de lo Civil» y «Juzgado Tercero de lo Civil»", [_IG, _DIF], 0),
    _opcion("Compare: «$12,450.80» y «$12,450.08»", [_IG, _DIF], 1),
    _opcion("Compare: «CURP PEXJ900215HDFRRN09» y «CURP PEXJ900215HDFRRN09»", [_IG, _DIF], 0),
    _opcion("¿Cuántas veces aparece la letra «a» en «Sala Superior»?", ["1", "2", "3", "4"], 1),
    _opcion("¿Cuál número es distinto? 48213 · 48213 · 48231 · 48213", ["El primero", "El segundo", "El tercero", "El cuarto"], 2),
    _opcion("Compare: «Av. Insurgentes Sur 1605, piso 9» y «Av. Insurgentes Sur 1650, piso 9»", [_IG, _DIF], 1),
    _opcion("¿Cuántas veces aparece el número 7 en «7177 0707»?", ["3", "4", "5", "6"], 2),
    _opcion("Compare: «Folio A-00392-B» y «Folio A-00392-B»", [_IG, _DIF], 0),
]

LABORAL = [
    _opcion("Conforme a la Ley Federal del Trabajo vigente, ¿cuántos días de vacaciones corresponden al cumplir el primer año de servicio?", ["6", "10", "12", "15"], 2),
    _opcion("¿Cuál es la prima vacacional mínima?", ["15 %", "25 %", "30 %", "50 %"], 1),
    _opcion("El aguinaldo mínimo es de…", ["15 días de salario, pagado antes del 20 de diciembre", "30 días de salario, pagado antes del 31 de diciembre",
                                         "15 días de salario, pagado antes del 31 de diciembre", "10 días de salario, pagado en enero"], 0),
    _opcion("La indemnización constitucional por despido injustificado equivale a…", ["1 mes de salario", "3 meses de salario", "6 meses de salario", "20 días de salario"], 1),
    _opcion("La prima de antigüedad es de…", ["12 días de salario por año de servicio", "15 días por año", "20 días por año", "30 días por año"], 0),
    _opcion("En la mayoría de los conflictos individuales, antes de demandar se debe acudir a…",
            ["La Junta de Conciliación y Arbitraje", "El Centro de Conciliación", "La Procuraduría Federal del Consumidor", "Un Tribunal Colegiado"], 1),
    _opcion("¿En qué plazo prescriben las acciones de los trabajadores separados del trabajo?", ["1 mes", "2 meses", "1 año", "2 años"], 1),
    _opcion("¿Cuál es el plazo general de prescripción de las acciones de trabajo?", ["2 meses", "6 meses", "1 año", "5 años"], 2),
    _opcion("¿Cuál es la duración máxima de la jornada diurna por día?", ["6 horas", "7 horas", "8 horas", "9 horas"], 2),
    _opcion("¿Qué porcentaje de las utilidades se reparte entre los trabajadores (PTU)?", ["5 %", "10 %", "15 %", "20 %"], 1),
]

AMPARO = [
    _opcion("¿Cuál es el plazo general para presentar la demanda de amparo?", ["10 días", "15 días", "30 días", "90 días"], 1),
    _opcion("¿Cuál es el plazo para reclamar en amparo una norma general autoaplicativa a partir de su entrada en vigor?", ["15 días", "30 días", "60 días", "90 días"], 1),
    _opcion("¿Quién conoce en primera instancia del amparo indirecto?", ["Un Tribunal Colegiado de Circuito", "Un Juez de Distrito", "La Suprema Corte", "El Tribunal de Disciplina Judicial"], 1),
    _opcion("El amparo directo procede contra…", ["Sentencias definitivas, laudos y resoluciones que ponen fin al juicio", "Cualquier acuerdo de trámite",
                                                 "Leyes recién publicadas", "Actos de particulares sin autoridad"], 0),
    _opcion("¿Qué órgano resuelve el amparo directo?", ["Un Juez de Distrito", "Un Tribunal Colegiado de Circuito", "Un Juez de primera instancia local", "La Sala del tribunal que dictó la sentencia"], 1),
    _opcion("¿Cómo se llama la parte que promueve el juicio de amparo?", ["Tercero interesado", "Autoridad responsable", "Persona quejosa", "Ministerio Público"], 2),
]

CIVIL = [
    _opcion("¿A qué edad se alcanza la mayoría de edad y con ella la capacidad de ejercicio?", ["16 años", "18 años", "21 años", "25 años"], 1),
    _opcion("Según el Código Civil Federal, ¿qué elementos son necesarios para que exista un contrato?", ["Consentimiento y objeto", "Forma y testigos",
                                                                                                        "Precio y plazo", "Firma ante notario"], 0),
    _opcion("¿Cuáles son vicios del consentimiento?", ["Error, dolo y violencia", "Mora, culpa y caso fortuito", "Plazo, condición y modo", "Novación, compensación y confusión"], 0),
    _opcion("La compraventa es perfecta y obligatoria cuando las partes se ponen de acuerdo en…", ["La cosa y el precio", "La fecha de entrega", "La forma de pago",
                                                                                                   "La firma ante notario"], 0),
    _opcion("En el Código Civil Federal, ¿en cuánto tiempo prescribe, como regla general, una obligación (prescripción negativa)?", ["2 años", "5 años", "10 años", "20 años"], 2),
    _opcion("El testamento ológrafo es el que…", ["Se otorga ante notario", "Escribe de su puño y letra el testador", "Se hace en caso de guerra", "Se hace a bordo de un barco"], 1),
    _opcion("Si una obligación es solidaria entre varios deudores, el acreedor…", ["Solo puede cobrar a cada uno su parte", "Puede exigir el total a cualquiera de ellos",
                                                                                  "Debe demandar a todos juntos", "Pierde el derecho si uno no paga"], 1),
    _opcion("¿Qué es una persona moral?", ["Un ente con personalidad jurídica propia, como una sociedad o asociación", "Una persona con buena reputación",
                                           "Una persona menor de edad", "Un servidor público"], 0),
]

REVISION_JURIDICA = "noviembre de 2026"

PRUEBAS: dict[str, dict] = {
    "big5": {"nombre": "Personalidad (cinco factores)", "categoria": "Personalidad", "tipo": "likert", "minutos": 15,
             "descripcion": "50 afirmaciones del IPIP (dominio público) sobre extroversión, amabilidad, responsabilidad, estabilidad emocional y apertura.",
             "instrucciones": "Lea cada afirmación y elija qué tanto lo describe hoy, no como le gustaría ser. No hay respuestas buenas ni malas.",
             "preguntas": [{"texto": t} for t, _, _ in _BIG5]},
    "numerico": {"nombre": "Razonamiento numérico", "categoria": "Razonamiento y atención", "tipo": "opcion", "minutos": 15,
                 "descripcion": "12 problemas de porcentajes, proporciones, series y tiempos.", "preguntas": NUMERICO,
                 "instrucciones": "Elija una respuesta por pregunta. Puede usar papel y lápiz; no use calculadora."},
    "verbal": {"nombre": "Razonamiento verbal", "categoria": "Razonamiento y atención", "tipo": "opcion", "minutos": 12,
               "descripcion": "12 reactivos de vocabulario, analogías, lógica y comprensión de lectura.", "preguntas": VERBAL,
               "instrucciones": "Elija la respuesta que mejor complete o responda cada pregunta."},
    "atencion": {"nombre": "Atención al detalle", "categoria": "Razonamiento y atención", "tipo": "opcion", "minutos": 6,
                 "descripcion": "10 comparaciones de folios, montos, RFC y direcciones.", "preguntas": ATENCION,
                 "instrucciones": "Revise con cuidado y responda lo más rápido que pueda sin equivocarse."},
    "laboral": {"nombre": "Conocimientos: derecho laboral", "categoria": "Conocimientos jurídicos", "tipo": "opcion", "minutos": 12,
                "descripcion": f"10 preguntas de la Ley Federal del Trabajo (revisadas a {REVISION_JURIDICA}).", "preguntas": LABORAL,
                "instrucciones": "Responda sin consultar la ley."},
    "amparo": {"nombre": "Conocimientos: amparo", "categoria": "Conocimientos jurídicos", "tipo": "opcion", "minutos": 8,
               "descripcion": f"6 preguntas de la Ley de Amparo (revisadas a {REVISION_JURIDICA}).", "preguntas": AMPARO,
               "instrucciones": "Responda sin consultar la ley."},
    "civil": {"nombre": "Conocimientos: derecho civil", "categoria": "Conocimientos jurídicos", "tipo": "opcion", "minutos": 10,
              "descripcion": f"8 preguntas de derecho civil federal (revisadas a {REVISION_JURIDICA}).", "preguntas": CIVIL,
              "instrucciones": "Responda sin consultar la ley."},
}


def catalogo() -> list[dict]:
    return [{"clave": k, "nombre": v["nombre"], "categoria": v["categoria"], "descripcion": v["descripcion"], "minutos": v["minutos"],
             "preguntas": len(v["preguntas"]), "tipo": v["tipo"]} for k, v in PRUEBAS.items()]


def para_candidato(p: dict) -> dict:
    """Lo que ve el candidato: sin respuestas correctas."""
    preguntas = [{"texto": q["texto"], "opciones": q.get("opciones") or LIKERT} for q in p["preguntas"]]
    return {"nombre": p["nombre"], "instrucciones": p.get("instrucciones"), "minutos": p.get("minutos"), "tipo": p.get("tipo", "opcion"), "preguntas": preguntas}


def calificar(p: dict, respuestas: list) -> dict:
    """Respuestas: lista con el índice elegido (o texto libre en preguntas abiertas de pruebas propias)."""
    if p.get("tipo") == "likert":
        suma = {f: 0 for f in FACTORES}
        n = {f: 0 for f in FACTORES}
        for (_, f, signo), r in zip(_BIG5, respuestas):
            if isinstance(r, int) and 0 <= r <= 4:
                v = r + 1 if signo > 0 else 5 - r
                suma[f] += v
                n[f] += 1
        factores = []
        for f, (nombre, que, bajo, alto) in FACTORES.items():
            pct = round((suma[f] - n[f]) / (4 * n[f]) * 100) if n[f] else None
            nivel = None if pct is None else "alto" if pct >= 65 else "bajo" if pct <= 35 else "medio"
            factores.append({"clave": f, "nombre": nombre, "que_mide": que, "porcentaje": pct, "nivel": nivel,
                             "lectura": alto if nivel == "alto" else bajo if nivel == "bajo" else "En un punto intermedio." if nivel else None})
        return {"tipo": "perfil", "factores": factores, "contestadas": sum(n.values()), "total": len(_BIG5)}
    aciertos = calificables = 0
    abiertas = []
    detalle = []
    for i, q in enumerate(p["preguntas"]):
        r = respuestas[i] if i < len(respuestas) else None
        if q.get("correcta") is None or not q.get("opciones"):
            abiertas.append({"pregunta": q["texto"], "respuesta": str(r)[:4000] if r not in (None, "") else None})
            continue
        calificables += 1
        ok = isinstance(r, int) and r == q["correcta"]
        aciertos += ok
        detalle.append({"pregunta": q["texto"], "elegida": q["opciones"][r] if isinstance(r, int) and 0 <= r < len(q["opciones"]) else None,
                        "correcta": q["opciones"][q["correcta"]], "acierto": ok})
    return {"tipo": "aciertos", "aciertos": aciertos, "total": calificables,
            "porcentaje": round(aciertos / calificables * 100) if calificables else None, "detalle": detalle, "abiertas": abiertas}
