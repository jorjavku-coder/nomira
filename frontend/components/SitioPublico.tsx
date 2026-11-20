"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import FormularioInformes from "@/components/FormularioInformes";
import { EnlacesLegales } from "@/components/legal";
import Logo from "@/components/Logo";
import { api, leerSesion, mxn } from "@/lib/api";

const NAV = [["#modulos", "Módulos"], ["#clientes", "Portal del cliente"], ["#seguridad", "Seguridad"], ["#preguntas", "Preguntas"]];

const MODULOS = [
  { clave: "nomina", nombre: "Nómina y prestaciones", lema: "Del PDF al desglose por quincena",
    texto: "Lee comprobantes de nómina digitales o escaneados y suma solo las prestaciones de su catálogo autorizado, con cada cifra ligada a su página.",
    puntos: ["Lectura de PDF y OCR", "Catálogo con claves propias", "Excel y PDF con su logotipo", "Detecta faltantes y duplicados"],
    imagen: "/sitio/resultados.webp", alt: "Total por clave de prestación en Nomira (datos ficticios)." },
  { clave: "evidencia", nombre: "Nomira Evidencia", lema: "El expediente probatorio, ordenado",
    texto: "Organiza los documentos de un asunto, propone hechos con su cita y página, y le ayuda a encontrar diferencias entre fuentes. Usted valida y decide.",
    puntos: ["Hechos con cita, documento y página", "Fecha del documento ≠ fecha del evento", "Posibles diferencias lado a lado", "Matriz de evidencia y cronología", "Búsqueda dentro de los documentos"],
    imagen: "/sitio/evidencia.webp", alt: "Bandeja «Requiere tu atención» de Nomira Evidencia (datos ficticios)." },
  { clave: "afore", nombre: "Nomira AFORE", lema: "Casos AFORE y SAR sin perder el hilo",
    texto: "Alta guiada del caso, checklist por tipo de problema, folios, respuestas y seguimientos, y un portal donde el cliente ve sus avances y envía documentos.",
    puntos: ["Checklist editable por problema", "Folios, acuses y fechas con su naturaleza", "CURP y NSS cifrados y enmascarados", "Mensajes con aprobación del abogado", "WhatsApp oficial de Meta (opcional)"],
    imagen: "/sitio/afore.webp", alt: "Resumen «¿Qué requiere atención ahora?» de Nomira AFORE (datos ficticios)." },
  { clave: "leads", nombre: "Nomira Leads", lema: "Ningún prospecto sin respuesta",
    texto: "Una bandeja que le dice a quién atender hoy, un tablero de seguimiento y el próximo paso de cada prospecto. Sepa qué campañas de WhatsApp, correo y redes sociales le traen clientes.",
    puntos: ["Alta de prospectos en menos de un minuto", "Tablero con etapas a su medida", "Campañas por WhatsApp, correo y redes", "Formulario de contacto para anuncios", "Resultados y costo por cliente"],
    imagen: "/sitio/leads.webp", alt: "Bandeja «¿A quién hay que atender?» de Nomira Leads (datos ficticios)." },
  { clave: "academia", nombre: "Nomira Academia", lema: "Capacite a su equipo a su ritmo",
    texto: "Cursos breves y prácticos por materia: asígnelos a su equipo, vea quién avanza y quién terminó, y entregue constancias de participación al concluir.",
    puntos: ["Cursos propios y cursos de Nomira", "Video, lecturas, materiales y preguntas", "Avance guardado: retoma donde se quedó", "Asignación por persona o equipo", "Constancia de participación en PDF"],
    imagen: "/sitio/academia.webp", alt: "Pantalla «Mi aprendizaje» de Nomira Academia (datos ficticios)." },
];

const PASOS = [
  ["Cree el expediente", "Nombre del trabajador y periodo a revisar. Si sube primero los PDF, Nomira propone esos datos por usted."],
  ["Suba los comprobantes", "Los PDF de nómina tal como los tiene: digitales o escaneados. Nomira lee clave, concepto e importe de cada percepción."],
  ["Revise solo lo dudoso", "Lo ilegible, lo duplicado o lo que no cuadra queda señalado para que una persona decida. Nada se corrige solo."],
  ["Descargue el resultado", "Desglose por quincena y por clave, listo en Excel y PDF con el logotipo de su despacho."],
];

const BENEFICIOS = [
  ["Solo lo que está en su catálogo", "Se suman únicamente las percepciones cuya clave coincide exactamente con su catálogo autorizado. Las deducciones nunca se suman."],
  ["Cada cifra con su origen", "Del total a la quincena, y de ahí a la página del comprobante donde se leyó, en un clic."],
  ["Nada se inventa", "Si un importe no se lee, queda pendiente. Si falta una quincena, se señala como faltante; nunca se rellena."],
  ["Detecta lo que se escapa a mano", "Recibos repetidos, complementarios, de otro trabajador o fuera de periodo, y trabajadores con más de una plaza."],
  ["Su catálogo, a su medida", "Cárguelo desde el PDF oficial y agregue las claves que le falten. Cada cambio queda como una versión nueva."],
  ["Trabajo en equipo con bitácora", "Usuarios por rol (administrador, analista, consulta) y registro de cada corrección: quién, cuándo y por qué."],
];

const PREGUNTAS = [
  ["¿Qué documentos acepta?", "Comprobantes de nómina en PDF, tanto digitales como escaneados (en ese caso se leen con reconocimiento de texto). Puede subir uno o varios archivos por expediente."],
  ["¿Qué pasa si una clave no está en mi catálogo?", "Esa percepción queda fuera del total y se muestra en la lista de excluidos con el motivo. Si debe contar, la agrega a su catálogo y el expediente se recalcula."],
  ["¿Quién puede ver mis expedientes?", "Solo los usuarios de su organización. Ni otras empresas ni el equipo de Nomira tienen acceso a sus expedientes ni a sus documentos."],
  ["¿Tengo que instalar algo?", "No. Nomira funciona desde el navegador, en computadora o tableta."],
  ["¿Puedo corregir una lectura?", "Sí. Cada corrección pide un motivo y queda registrada; el comprobante original no se modifica."],
  ["¿Tengo que contratar todos los módulos?", "No. Cada módulo funciona por separado: contrate Nómina y prestaciones, Nomira Evidencia, Nomira AFORE, Nomira Leads, Nomira Academia o la combinación que necesite. Desactivar un módulo no borra su información."],
  ["¿Nomira decide si un hecho está probado o si el cliente tiene derecho?", "No. Nomira lee, organiza y señala lo que hay que revisar. La valoración jurídica, la estrategia y cualquier decisión las toma siempre el abogado."],
  ["¿Cómo envía documentos mi cliente?", "Usted le manda un enlace seguro que vence: lo abre en su celular, confirma un código que le llega a su correo y sube sus archivos. Solo puede enviar; no ve nada interno de su despacho."],
  ["¿Nomira manda mensajes de WhatsApp por su cuenta?", "Solo con la API oficial de WhatsApp Business de Meta conectada a su número, con el consentimiento del cliente y, por omisión, con la aprobación del abogado. Si algo falta, el mensaje queda como borrador."],
  ["¿Nomira Leads me consigue clientes?", "Nomira no publica anuncios ni promete clientes. Le ayuda a responder a tiempo a quien ya le contactó, a dar seguimiento ordenado y a medir qué campañas (WhatsApp, correo, redes sociales, su sitio web) le traen clientes."],
  ["¿La constancia de Nomira Academia es una certificación oficial?", "No. Es una constancia de participación interna que indica curso, participante, despacho y fecha. No sustituye certificaciones, acreditaciones ni avales de ninguna institución."],
  ["¿Cómo empiezo?", "Llene el formulario de informes o escríbanos. Le damos de alta, activamos los módulos que necesite y le acompañamos en su primer caso."],
];

const d = (ms: number) => ({ "--d": `${ms}ms` }) as React.CSSProperties;

const CINTA = ["Nómina y prestaciones", "Nomira Evidencia", "Nomira AFORE", "Nomira Leads", "Nomira Academia", "Portal del cliente",
  "WhatsApp oficial de Meta", "Bitácora completa", "Datos cifrados", "Excel y PDF con su logotipo", "Constancias de participación", "Campañas y resultados"];

/** Animaciones del sitio: aparición al desplazarse, encabezado compacto y barra de lectura. */
function useAnimaciones(raiz: React.RefObject<HTMLDivElement>) {
  const [desplazado, setDesplazado] = useState(false);
  const [progreso, setProgreso] = useState(0);
  useEffect(() => {
    const el = raiz.current;
    if (!el) return;
    el.classList.add("s-anim");
    const obs = new IntersectionObserver((xs) => xs.forEach((x) => {
      if (x.isIntersecting) { x.target.classList.add("s-visto"); obs.unobserve(x.target); }
    }), { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    el.querySelectorAll(".s-revelar, .s-revelar-lado").forEach((x) => obs.observe(x));
    let cuadro = 0;
    const alMover = () => {
      cancelAnimationFrame(cuadro);
      cuadro = requestAnimationFrame(() => {
        const alto = document.documentElement.scrollHeight - window.innerHeight;
        setDesplazado(window.scrollY > 12);
        setProgreso(alto > 0 ? Math.min(1, window.scrollY / alto) : 0);
      });
    };
    alMover();
    window.addEventListener("scroll", alMover, { passive: true });
    return () => { obs.disconnect(); window.removeEventListener("scroll", alMover); cancelAnimationFrame(cuadro); };
  }, [raiz]);
  return { desplazado, progreso };
}

/** Imagen de portada que se inclina un poco siguiendo el mouse (solo en escritorio). */
function Inclinable({ children }: { children: React.ReactNode }) {
  const reposo = "perspective(1400px) rotateX(0deg) rotateY(0deg)";
  const [t, setT] = useState(reposo);
  const mover = (e: React.MouseEvent<HTMLDivElement>) => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    setT(`perspective(1400px) rotateX(${(-y * 5).toFixed(2)}deg) rotateY(${(x * 7).toFixed(2)}deg)`);
  };
  return <div onMouseMove={mover} onMouseLeave={() => setT(reposo)} style={{ transform: t, transition: "transform .5s cubic-bezier(.2,.7,.2,1)" }}>{children}</div>;
}

const CLAVE_TEMA = "nomira_tema";
/** Se ejecuta antes de pintar la página para que quien eligió el modo oscuro no vea un destello claro. */
const SCRIPT_TEMA = `try{if(localStorage.getItem("${CLAVE_TEMA}")==="oscuro")document.documentElement.classList.add("s-tema-oscuro")}catch(e){}`;

/** Modo claro (predeterminado) u oscuro, recordado en este navegador. Solo afecta al sitio público. */
function useTema() {
  const [oscuro, setOscuro] = useState(false);
  useEffect(() => {
    setOscuro(document.documentElement.classList.contains("s-tema-oscuro"));
    return () => document.documentElement.classList.remove("s-tema-oscuro");  // al ir a «Iniciar sesión» el sistema sigue en claro
  }, []);
  const cambiar = () => {
    const nuevo = !oscuro;
    setOscuro(nuevo);
    document.documentElement.classList.toggle("s-tema-oscuro", nuevo);
    try { localStorage.setItem(CLAVE_TEMA, nuevo ? "oscuro" : "claro"); } catch {}
  };
  return { oscuro, cambiar };
}

/** Botón con sol (modo claro) y luna (modo oscuro). */
function BotonTema({ oscuro, onCambiar }: { oscuro: boolean; onCambiar: () => void }) {
  return (
    <button type="button" onClick={onCambiar} aria-pressed={oscuro} aria-label={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
      title={oscuro ? "Modo claro" : "Modo oscuro"}
      className={`relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border transition duration-300 hover:-translate-y-0.5 ${oscuro
        ? "border-white/15 bg-white/5 text-turquesa-brillante hover:border-turquesa-brillante/50" : "border-crema-300 bg-white text-amber-500 hover:border-amber-300"}`}>
      {/* Sol */}
      <svg viewBox="0 0 24 24" className={`absolute h-5 w-5 transition-all duration-500 ${oscuro ? "-translate-y-6 rotate-90 opacity-0" : "translate-y-0 rotate-0 opacity-100"}`}
        fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
        <circle cx="12" cy="12" r="4.2" fill="currentColor" />
        <path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4" />
      </svg>
      {/* Luna */}
      <svg viewBox="0 0 24 24" className={`absolute h-5 w-5 transition-all duration-500 ${oscuro ? "translate-y-0 rotate-0 opacity-100" : "translate-y-6 -rotate-90 opacity-0"}`}
        fill="currentColor" aria-hidden>
        <path d="M20.2 14.6A8.5 8.5 0 0 1 9.4 3.8a.6.6 0 0 0-.8-.7A9.5 9.5 0 1 0 20.9 15.4a.6.6 0 0 0-.7-.8z" />
        <circle cx="17.5" cy="5.5" r="1" /><circle cx="20.5" cy="9" r=".7" />
      </svg>
    </button>
  );
}

function Palomita({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return <svg viewBox="0 0 20 20" className={className} fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 10.5l4 4 8-9" /></svg>;
}

function BotonWhatsApp({ numero }: { numero: string }) {
  const texto = encodeURIComponent("Hola, me interesa conocer Nomira.");
  return (
    <a href={`https://wa.me/${numero}?text=${texto}`} target="_blank" rel="noopener noreferrer" aria-label="Escríbanos por WhatsApp"
      className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full bg-[#25D366] py-3 pl-3.5 pr-4 font-semibold text-white shadow-flotante transition hover:-translate-y-0.5 hover:bg-[#1ebe5b]">
      <svg viewBox="0 0 32 32" className="h-6 w-6" fill="currentColor" aria-hidden>
        <path d="M16.04 3C8.86 3 3.03 8.82 3.03 16c0 2.29.6 4.53 1.74 6.5L3 29l6.68-1.75A12.95 12.95 0 0 0 16.04 29C23.2 29 29 23.18 29 16S23.2 3 16.04 3zm0 23.64c-1.98 0-3.92-.53-5.62-1.54l-.4-.24-3.96 1.04 1.06-3.86-.26-.4A10.6 10.6 0 0 1 5.4 16c0-5.87 4.77-10.64 10.64-10.64 5.86 0 10.62 4.77 10.62 10.64 0 5.86-4.76 10.64-10.62 10.64zm5.83-7.96c-.32-.16-1.88-.93-2.17-1.03-.3-.11-.5-.16-.72.16-.21.32-.82 1.03-1 1.24-.19.21-.37.24-.69.08-.32-.16-1.35-.5-2.57-1.59-.95-.85-1.59-1.9-1.78-2.22-.19-.32-.02-.49.14-.65.14-.14.32-.37.48-.56.16-.18.21-.32.32-.53.1-.21.05-.4-.03-.56-.08-.16-.72-1.73-.98-2.37-.26-.62-.53-.54-.72-.55h-.61c-.21 0-.56.08-.85.4-.29.32-1.11 1.09-1.11 2.65 0 1.57 1.14 3.08 1.3 3.29.16.21 2.24 3.42 5.43 4.8.76.33 1.35.52 1.81.67.76.24 1.45.2 2-.12.61-.09 1.88-.77 2.14-1.51.27-.74.27-1.38.19-1.51-.08-.13-.29-.21-.61-.37z" />
      </svg>
      <span className="hidden sm:inline">Escríbanos</span>
    </a>
  );
}

export default function SitioPublico() {
  const [whatsapp, setWhatsapp] = useState<string | null>(null);
  const [desde, setDesde] = useState<string | null>(null);
  const [conSesion, setConSesion] = useState(false);
  const [menu, setMenu] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const { desplazado, progreso } = useAnimaciones(raiz);
  const { oscuro, cambiar } = useTema();
  useEffect(() => {
    setConSesion(!!leerSesion());
    api.get("/publico").then((p) => { setWhatsapp(p.whatsapp || null); setDesde(p.precio_desde || null); }).catch(() => {});
  }, []);
  const acceso = conSesion
    ? <Link href="/app" className="btn-turquesa">Ir a Nomira</Link>
    : <Link href="/login" className="btn-sec">Iniciar sesión</Link>;

  return (
    <div ref={raiz} className="s-sitio bg-crema text-slate-800">
      <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      {/* Encabezado */}
      <header className={`sticky top-0 z-40 border-b backdrop-blur-md transition-all duration-300 ${desplazado ? "border-crema-300/80 bg-crema/90 shadow-[0_8px_30px_-18px_rgba(10,27,43,.35)]" : "border-transparent bg-crema/40"}`}>
        <div className="absolute inset-x-0 bottom-0 h-0.5 origin-left bg-gradient-to-r from-turquesa to-turquesa-brillante" style={{ transform: `scaleX(${progreso})` }} aria-hidden />
        <div className={`mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 transition-all duration-300 ${desplazado ? "py-2.5" : "py-4"}`}>
          <Link href="/" aria-label="Nomira, inicio"><Logo oscuro={oscuro} /></Link>
          <nav className="hidden items-center gap-7 text-sm font-medium text-slate-600 md:flex" aria-label="Secciones">
            {NAV.map(([h, t]) => <a key={h} href={h} className="group relative transition hover:text-marino">{t}
              <span className="absolute -bottom-1 left-0 h-0.5 w-full origin-left scale-x-0 rounded-full bg-turquesa transition-transform duration-300 group-hover:scale-x-100" aria-hidden /></a>)}
          </nav>
          <div className="flex items-center gap-2">
            <BotonTema oscuro={oscuro} onCambiar={cambiar} />
            <a href="#informes" className="btn-primario hidden sm:inline-flex">Solicitar informes</a>
            {acceso}
            <button className="rounded-lg p-2 text-marino md:hidden" aria-label="Abrir menú" aria-expanded={menu} onClick={() => setMenu(!menu)}>
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden><path d={menu ? "M6 6l12 12M18 6L6 18" : "M4 7h16M4 12h16M4 17h16"} /></svg>
            </button>
          </div>
        </div>
        {menu && (
          <nav className="border-t border-crema-300 px-5 py-3 md:hidden" aria-label="Secciones">
            {[...NAV, ["#informes", "Solicitar informes"]].map(([h, t]) => <a key={h} href={h} onClick={() => setMenu(false)} className="block py-2 font-medium text-marino">{t}</a>)}
          </nav>
        )}
      </header>

      <main>
        {/* Portada */}
        <section className="relative overflow-hidden">
          <div className="s-cuadricula pointer-events-none absolute inset-0" aria-hidden />
          <div className="s-aurora pointer-events-none absolute -right-40 -top-40 h-[34rem] w-[34rem] rounded-full bg-turquesa/20 blur-3xl" aria-hidden />
          <div className="s-aurora pointer-events-none absolute -left-32 top-40 h-[26rem] w-[26rem] rounded-full bg-turquesa-brillante/10 blur-3xl" style={d(-6000)} aria-hidden />
          <div className="s-aurora pointer-events-none absolute bottom-0 right-1/3 h-72 w-72 rounded-full bg-marino/10 blur-3xl" style={d(-11000)} aria-hidden />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-14 lg:grid-cols-[1fr_1.1fr] lg:pt-20">
            <div className="relative">
              <span className="s-entrada inline-flex items-center gap-2 rounded-full border border-turquesa/20 bg-white/70 px-3 py-1 text-xs font-bold uppercase tracking-wider text-turquesa-700 backdrop-blur">
                <span className="s-pulso h-1.5 w-1.5 rounded-full bg-turquesa" aria-hidden />Software para despachos y áreas jurídicas</span>
              <h1 style={d(100)} className="s-entrada mt-5 font-marca text-4xl font-extrabold leading-[1.08] text-marino sm:text-5xl lg:text-[3.4rem]">
                Cada prestación,<br /><span className="s-degradado">en claro.</span></h1>
              <p style={d(200)} className="s-entrada mt-5 max-w-xl text-lg leading-relaxed text-slate-600">
                Nomira lee sus documentos, ordena la información y le muestra de dónde sale cada dato, para que usted dedique su tiempo a
                <b className="text-marino"> decidir</b>, no a copiar y pegar. Contrate solo los módulos que necesita.</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {MODULOS.map((m, i) => <a key={m.clave} href="#modulos" style={d(300 + i * 70)} className="s-entrada rounded-full border border-turquesa/40 bg-white/80 px-3 py-1 text-sm font-semibold text-marino backdrop-blur transition hover:-translate-y-0.5 hover:border-turquesa hover:shadow-suave">{m.nombre}</a>)}
              </div>
              <div style={d(650)} className="s-entrada mt-8 flex flex-wrap gap-3">
                <a href="#informes" className="btn-turquesa s-brillo px-5 py-3 text-base shadow-[0_12px_30px_-12px_rgba(1,178,166,.8)] hover:-translate-y-0.5">Solicitar informes →</a>
                <a href="#como-funciona" className="btn-sec px-5 py-3 text-base hover:-translate-y-0.5">Ver cómo funciona</a>
              </div>
              <ul style={d(800)} className="s-entrada mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
                {["Sin instalar nada", "Portal seguro para sus clientes", "Sus expedientes, privados"].map((t) => (
                  <li key={t} className="flex items-center gap-2"><span className="text-turquesa-700"><Palomita /></span>{t}</li>))}
              </ul>
            </div>
            <div style={d(350)} className="s-entrada relative">
              <div className="absolute -inset-3 rotate-1 rounded-[2rem] bg-gradient-to-br from-turquesa/15 via-transparent to-marino/10" aria-hidden />
              <Inclinable>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/sitio/visor.webp" width={1600} height={1034} alt="Nomira muestra el comprobante original junto a lo que leyó: cada percepción con su clave, importe y si se incluye o queda pendiente."
                  className="relative w-full rounded-3xl border border-crema-300 bg-white shadow-flotante" />
              </Inclinable>
              <div aria-hidden className="pointer-events-none absolute -left-6 top-8 hidden sm:block">
                <div className="s-flotar flex items-center gap-2 rounded-2xl border border-crema-300 bg-white/90 px-3 py-2 text-xs font-semibold text-marino shadow-flotante backdrop-blur">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><Palomita /></span>Cifra ligada a su página</div>
              </div>
              <div aria-hidden className="pointer-events-none absolute -right-4 top-1/2 hidden sm:block">
                <div style={d(-2000)} className="s-flotar flex items-center gap-2 rounded-2xl border border-crema-300 bg-white/90 px-3 py-2 text-xs font-semibold text-marino shadow-flotante backdrop-blur">
                  <span className="s-pulso h-2 w-2 rounded-full bg-turquesa" />Nuevo prospecto · WhatsApp</div>
              </div>
              <div aria-hidden className="pointer-events-none absolute left-10 top-[74%] hidden sm:block">
                <div style={d(-4000)} className="s-flotar flex items-center gap-2 rounded-2xl bg-marino px-3 py-2 text-xs font-semibold text-white shadow-flotante">
                  <span className="text-turquesa-brillante">★</span>Constancia emitida</div>
              </div>
              <p className="relative mt-8 text-center text-xs text-slate-500">Datos ficticios de demostración.</p>
            </div>

          </div>
        </section>

        {/* Cinta de módulos y funciones */}
        <div className="s-cinta-marco relative overflow-hidden border-y border-crema-300 bg-white/70 py-4" aria-hidden>
          <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-white to-transparent" />
          <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-white to-transparent" />
          <div className="s-cinta flex w-max gap-10 whitespace-nowrap">
            {[...CINTA, ...CINTA].map((t, i) => (
              <span key={i} className="flex items-center gap-10 font-marca text-sm font-bold uppercase tracking-wider text-marino/70">{t}<span className="h-1.5 w-1.5 rounded-full bg-turquesa" /></span>))}
          </div>
        </div>

        {/* El problema */}
        <section className="relative overflow-hidden bg-marino-700 text-white">
          <div className="s-aurora pointer-events-none absolute -right-20 -top-24 h-80 w-80 rounded-full bg-turquesa-brillante/15 blur-3xl" aria-hidden />
          <div className="relative mx-auto grid max-w-6xl gap-10 px-5 py-16 md:grid-cols-[1fr_1.4fr] md:items-center">
            <h2 className="s-revelar-lado font-marca text-3xl font-extrabold leading-tight">El trabajo repetitivo<br /><span className="text-turquesa-brillante">no debería tomar días.</span></h2>
            <p style={d(150)} className="s-revelar text-lg leading-relaxed text-white/75">
              Sumar quincenas a mano, buscar una fecha entre decenas de documentos, perseguir al cliente por un acta o recordar en qué va
              cada folio con la AFORE, dar seguimiento a cada prospecto o capacitar al equipo. Nomira hace la lectura, el orden y el seguimiento, y le deja a usted lo que de verdad requiere criterio.</p>
          </div>
        </section>

        {/* Módulos */}
        <section id="modulos" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-5 pt-20">
            <div className="s-revelar max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Módulos</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Cinco módulos, una sola plataforma</h2>
              <p className="mt-3 text-slate-600">Cada uno funciona por separado y comparte los mismos usuarios, la bitácora y la seguridad de su despacho.</p>
            </div>
            <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-6">
              {MODULOS.map((m, i) => (
                <article key={m.clave} style={d((i % 3) * 120)} className={`s-revelar s-tarjeta tarjeta group flex flex-col overflow-hidden lg:col-span-2 ${i === 3 ? "lg:col-start-2" : ""}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <div className="overflow-hidden border-b border-crema-300"><img src={m.imagen} alt={m.alt} loading="lazy" className="aspect-[16/10] w-full bg-crema object-cover object-left-top" /></div>
                  <div className="flex flex-1 flex-col p-6">
                    <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">{m.lema}</span>
                    <h3 className="mt-1 font-marca text-xl font-extrabold text-marino transition group-hover:text-turquesa-700">{m.nombre}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-slate-600">{m.texto}</p>
                    <ul className="mt-4 space-y-1.5 text-sm">
                      {m.puntos.map((p) => <li key={p} className="flex gap-2"><span className="mt-0.5 text-turquesa-700"><Palomita /></span>{p}</li>)}
                    </ul>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Cómo funciona */}
        <section id="como-funciona" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-5 py-20">
            <div className="s-revelar max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Cómo funciona</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Nómina y prestaciones: de los PDF al desglose en cuatro pasos</h2>
            </div>
            <ol className="s-revelar relative mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <span className="s-trazo absolute left-6 right-6 top-11 hidden h-0.5 rounded-full bg-gradient-to-r from-turquesa via-turquesa-brillante to-marino lg:block" aria-hidden />
              {PASOS.map(([t, dd], i) => (
                <li key={t} style={d(i * 130)} className="s-revelar s-tarjeta tarjeta relative p-6">
                  <span className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-marino font-marca text-lg font-extrabold text-white">{i + 1}</span>
                  <h3 className="mt-4 text-lg font-bold text-marino">{t}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{dd}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Beneficios */}
        <section id="beneficios" className="scroll-mt-20 border-y border-crema-300 bg-white">
          <div className="mx-auto grid max-w-6xl gap-12 px-5 py-20 lg:grid-cols-[1.25fr_1fr] lg:items-start">
            <div className="s-revelar">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Nómina y prestaciones · Beneficios</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Un resultado que puede defender</h2>
              <p className="mt-3 max-w-xl text-slate-600">Nomira no adivina: aplica reglas claras y le muestra de dónde sale cada número.</p>
              <ul className="mt-8 grid gap-6 sm:grid-cols-2">
                {BENEFICIOS.map(([t, dd], i) => (
                  <li key={t} style={d((i % 2) * 120)} className="s-revelar flex gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-turquesa-50 text-turquesa-700"><Palomita /></span>
                    <span><span className="block font-bold text-marino">{t}</span><span className="mt-1 block text-sm leading-relaxed text-slate-600">{dd}</span></span>
                  </li>
                ))}
              </ul>
            </div>
            <figure style={d(200)} className="s-revelar lg:sticky lg:top-24">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/sitio/resultados.webp" width={1099} height={1076} loading="lazy" alt="Tabla de Nomira con el total por clave de prestación: clave, concepto del catálogo, veces que aparece y total."
                className="w-full rounded-3xl border border-crema-300 shadow-flotante" />
              <figcaption className="mt-3 text-center text-xs text-slate-500">Total por clave de prestación (datos ficticios).</figcaption>
            </figure>
          </div>
        </section>

        {/* Portal del cliente */}
        <section id="clientes" className="scroll-mt-20">
          <div className="mx-auto grid max-w-6xl gap-12 px-5 py-20 lg:grid-cols-[1fr_1fr] lg:items-center">
            <div className="s-revelar-lado">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Su cliente, conectado</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Menos llamadas de «¿cómo va mi asunto?»</h2>
              <p className="mt-3 text-slate-600">Su cliente recibe un enlace seguro desde su celular: ve solo lo que usted decide compartir, sabe qué documentos faltan y los envía en un minuto.</p>
              <ul className="mt-6 space-y-4">
                {[["Solicitud de documentos con enlace seguro", "Vence, se puede cancelar y pide un código que llega al correo del cliente. Solo sirve para enviar archivos."],
                  ["Usted revisa antes que nada", "Lo que llega queda «pendiente de revisión»: no se lee ni se agrega al expediente hasta que usted lo acepta."],
                  ["Avisos con su aprobación", "Correos de bienvenida, recordatorios y avisos de novedades. En AFORE, también WhatsApp oficial, siempre con consentimiento del cliente."],
                  ["Sin datos sensibles en los mensajes", "Los avisos solo dicen que hay novedades: los detalles se consultan en el portal seguro."]].map(([t, d]) => (
                  <li key={t} className="flex gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-turquesa-50 text-turquesa-700"><Palomita /></span>
                    <span><span className="block font-bold text-marino">{t}</span><span className="mt-1 block text-sm leading-relaxed text-slate-600">{d}</span></span>
                  </li>))}
              </ul>
            </div>
            <figure style={d(200)} className="s-revelar relative mx-auto w-full max-w-sm">
              <div className="s-aurora pointer-events-none absolute -inset-10 -z-10 rounded-full bg-turquesa/20 blur-3xl" aria-hidden />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/sitio/portal.webp" alt="Página del cliente en el celular para enviar sus documentos de forma segura (datos ficticios)." loading="lazy"
                className="s-flotar w-full rounded-[2rem] border-8 border-marino-900 shadow-flotante" />
              <figcaption className="mt-3 text-center text-xs text-slate-500">Lo que ve su cliente en el celular (datos ficticios).</figcaption>
            </figure>
          </div>
        </section>

        {/* Para quién */}
        <section>
          <div className="mx-auto max-w-6xl px-5 py-16">
            <h2 className="s-revelar text-center font-marca text-2xl font-extrabold text-marino">Pensado para quien trabaja con documentos y plazos</h2>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[["Despachos laborales", "Integre prestaciones con el respaldo de cada comprobante y arme el expediente probatorio."],
                ["Familiar, civil y mercantil", "Ordene documentos, hechos y fechas de cada asunto, y detecte versiones distintas entre fuentes."],
                ["Seguridad social y AFORE", "Lleve cada caso AFORE/SAR con su checklist, folios, respuestas y seguimientos al día."],
                ["Despachos que quieren crecer", "Atienda cada consulta a tiempo y sepa qué campañas le traen clientes, sin depender de la memoria de nadie."],
                ["Equipos en formación", "Capacite a abogados y personal de apoyo con cursos breves, y compruebe quién ya los terminó."],
                ["Recursos humanos y áreas jurídicas", "Verifique pagos de varios periodos con trazabilidad completa, lista para un expediente."]].map(([t, dd], i) => (
                <div key={t} style={d((i % 3) * 110)} className="s-revelar s-tarjeta rounded-3xl border border-crema-300 bg-white/60 p-6">
                  <h3 className="font-bold text-marino">{t}</h3><p className="mt-2 text-sm leading-relaxed text-slate-600">{dd}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Seguridad */}
        <section id="seguridad" className="relative scroll-mt-20 overflow-hidden bg-marino-900 text-white">
          <div className="s-aurora pointer-events-none absolute -left-24 top-10 h-96 w-96 rounded-full bg-turquesa/15 blur-3xl" aria-hidden />
          <div className="relative mx-auto max-w-6xl px-5 py-20">
            <div className="s-revelar max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-brillante">Seguridad y privacidad</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold sm:text-4xl">Sus expedientes son solo suyos</h2>
              <p className="mt-3 text-white/70">Sus documentos contienen datos personales y secreto profesional. Nomira está construido para tratarlos con ese cuidado.</p>
            </div>
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[["Separado por organización", "Cada despacho ve únicamente sus propios expedientes, casos, documentos y clientes."],
                ["Ni nosotros los vemos", "El equipo de Nomira administra cuentas, pero no tiene acceso a sus expedientes ni a sus documentos."],
                ["Accesos protegidos", "Conexión cifrada (HTTPS), contraseñas protegidas, bloqueo ante intentos repetidos y documentos restringidos por usuario."],
                ["Datos sensibles cifrados", "CURP, NSS y credenciales se guardan cifrados y se muestran enmascarados; verlos completos queda registrado."],
                ["Enlaces que vencen", "Los enlaces para sus clientes caducan, se pueden cancelar, piden código y no contienen información del caso."],
                ["Todo queda registrado", "Bitácora de quién creó, editó, validó, envió o descargó cada cosa y cuándo."]].map(([t, dd], i) => (
                <div key={t} style={d((i % 3) * 110)} className="s-revelar s-oscura rounded-3xl border border-white/10 bg-white/[0.04] p-6">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-turquesa-brillante/15 text-turquesa-brillante">
                    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 3l7 3v5c0 4.4-3 8.2-7 9.5-4-1.3-7-5.1-7-9.5V6z" /><path d="M9.5 12l1.8 1.8 3.5-3.6" /></svg>
                  </span>
                  <h3 className="mt-4 font-bold">{t}</h3><p className="mt-2 text-sm leading-relaxed text-white/65">{dd}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Preguntas */}
        <section id="preguntas" className="scroll-mt-20">
          <div className="mx-auto max-w-3xl px-5 py-20">
            <h2 className="s-revelar text-center font-marca text-3xl font-extrabold text-marino sm:text-4xl">Preguntas frecuentes</h2>
            <div className="mt-10 space-y-3">
              {PREGUNTAS.map(([p, r], i) => (
                <details key={p} style={d(Math.min(i, 6) * 60)} className="s-revelar group tarjeta px-5 py-4 transition hover:border-turquesa/40 open:border-turquesa/40 open:shadow-sm">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-marino">
                    {p}<span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-turquesa-50 text-xl text-turquesa-700 transition duration-300 group-open:rotate-45 group-open:bg-turquesa group-open:text-white" aria-hidden>+</span></summary>
                  <p className="mt-3 text-sm leading-relaxed text-slate-600">{r}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Informes */}
        <section id="informes" className="scroll-mt-20 border-t border-crema-300 bg-white">
          <div className="mx-auto grid max-w-6xl items-start gap-10 px-5 py-20 lg:grid-cols-[1fr_1.15fr]">
            <div className="s-revelar-lado">
              <span className="rounded-full bg-turquesa-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-turquesa-700">Informes y suscripción</span>
              <h2 className="mt-4 font-marca text-3xl font-extrabold leading-tight text-marino sm:text-4xl">Hablemos de su operación</h2>
              <p className="mt-3 text-slate-600">Cuéntenos qué módulos le interesan, cuántos asuntos lleva y cómo trabaja hoy. Le respondemos para explicarle cómo empezar.</p>
              {desde && <p className="mt-4 inline-flex items-center gap-2 rounded-xl border border-turquesa/40 bg-turquesa-50 px-4 py-2 text-sm text-marino">
                <b>Paquetes desde {mxn(desde).replace(/\.00$/, "")} MXN + IVA</b><span className="text-slate-600">· le enviamos una cotización a la medida</span></p>}
              {whatsapp && (
                <a href={`https://wa.me/${whatsapp}?text=${encodeURIComponent("Hola, me interesa conocer Nomira.")}`} target="_blank" rel="noopener noreferrer"
                  className="mt-6 inline-flex items-center gap-2 rounded-xl border border-[#25D366]/40 bg-[#25D366]/10 px-4 py-2.5 text-sm font-semibold text-[#128C4B] transition hover:bg-[#25D366]/20">
                  ¿Prefiere WhatsApp? Escríbanos directo →</a>
              )}
              <p className="mt-6 text-sm text-slate-500">¿Ya es cliente? <Link href="/login" className="font-semibold text-turquesa-700 hover:underline">Inicie sesión aquí</Link>.</p>
            </div>
            <div style={d(150)} className="s-revelar"><FormularioInformes /></div>
          </div>
        </section>
      </main>

      <footer className="bg-marino-900 text-white/60">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-sm">
          <div className="flex items-center gap-3"><Logo oscuro /><span className="hidden text-white/40 sm:inline">Cada prestación, en claro</span></div>
          <nav className="flex flex-wrap gap-5" aria-label="Pie de página">
            <a href="#modulos" className="hover:text-white">Módulos</a>
            <a href="#como-funciona" className="hover:text-white">Cómo funciona</a>
            <a href="#informes" className="hover:text-white">Informes</a>
            <Link href="/login" className="hover:text-white">Iniciar sesión</Link>
          </nav>
          <div className="w-full text-xs sm:w-auto"><EnlacesLegales claro /></div>
          <p className="w-full text-xs text-white/40 sm:w-auto">© {new Date().getFullYear()} Nomira · Desarrollado por IMA</p>
        </div>
      </footer>
      {whatsapp && <BotonWhatsApp numero={whatsapp} />}
    </div>
  );
}
