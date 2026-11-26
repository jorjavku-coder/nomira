"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import FormularioInformes from "@/components/FormularioInformes";
import { EnlacesLegales } from "@/components/legal";
import Logo from "@/components/Logo";
import { api, leerSesion, mxn } from "@/lib/api";

const NAV = [["#modulos", "Módulos"], ["#connect", "Connect"], ["#jurisprudencia", "Jurisprudencia"], ["#empezar", "Cómo empezar"], ["/calculadora-finiquito", "Calculadora"], ["#preguntas", "Preguntas"]];

/** Cuadrícula «bento»: cada módulo con su captura real (datos ficticios). `ancho` = columnas de 6 en escritorio. */
const BENTO = [
  { clave: "agenda", nombre: "Agenda Jurídica", lema: "Ningún plazo se le pasa", ancho: 4,
    texto: "Plazos y audiencias con días hábiles del tribunal, responsables y avisos. Revisa los estrados por usted.",
    puntos: ["Días hábiles", "Estrados TRIJAEM", "Expedientes PJF"], imagen: "/sitio/app-agenda.webp", ruta: "agenda",
    alt: "Agenda de hoy en Nomira: vencidos, audiencias y plazos por validar (datos ficticios)." },
  { clave: "celular", nombre: "En su celular", lema: "Donde esté", ancho: 2, celular: true,
    texto: "Lo de hoy, sus pendientes y sus cobros, también desde el teléfono.",
    puntos: ["Sin instalar nada"], imagen: "/sitio/app-cel.webp", ruta: "",
    alt: "Inicio de Nomira en un celular con los pendientes del día (datos ficticios)." },
  { clave: "clientes", nombre: "Clientes y cobranza", lema: "Incluido en todos los planes", ancho: 3,
    texto: "Cada cliente capturado una vez, con su saldo, sus pagos y sus recibos.",
    puntos: ["Saldos y vencidos", "Recibos", "Ligas de pago"], imagen: "/sitio/clientes.webp", ruta: "clientes",
    alt: "Directorio de clientes con saldo, vencido y próximo pago (datos ficticios)." },
  { clave: "rh", nombre: "Recursos humanos", lema: "Su equipo, en orden", ancho: 3,
    texto: "Expedientes del personal, vacaciones según la LFT, avisos con acuse y portal del empleado.",
    puntos: ["Vacaciones LFT", "Avisos con acuse", "Portal del empleado"], imagen: "/sitio/rh.webp", ruta: "rh",
    alt: "Lista de empleados con antigüedad y expediente en Nomira (datos ficticios)." },
  { clave: "nomina", nombre: "Nómina y liquidaciones", lema: "Del PDF al desglose", ancho: 2,
    texto: "Lee comprobantes y calcula finiquitos y liquidaciones de la LFT.",
    puntos: ["Cifra ligada a su página", "Operación y artículo"], imagen: "/sitio/liquidaciones.webp", ruta: "liquidaciones",
    alt: "Calculadora de liquidación de Nomira con el desglose por concepto (datos ficticios)." },
  { clave: "evidencia", nombre: "Nomira Evidencia", lema: "El expediente probatorio", ancho: 2,
    texto: "Propone hechos con su cita y página. Usted valida y decide.",
    puntos: ["Hechos con fuente", "Cronología"], imagen: "/sitio/evidencia.webp", ruta: "evidencia",
    alt: "Bandeja «Requiere tu atención» de Nomira Evidencia (datos ficticios)." },
  { clave: "escrituracion", nombre: "Escrituración", lema: "Para notarías", ancho: 2,
    texto: "Semáforo de «listo para firmar» y avance visible para cliente, inmobiliaria y banco.",
    puntos: ["Vigencias", "Semáforo"], imagen: "/sitio/escrituracion.webp", ruta: "escrituracion",
    alt: "Lista de expedientes de escrituración con semáforo (datos ficticios)." },
  { clave: "afore", nombre: "Nomira AFORE", lema: "Casos AFORE y SAR", ancho: 2,
    texto: "Checklist por problema, folios, seguimientos y portal para el cliente.",
    puntos: ["Checklist", "CURP y NSS cifrados"], imagen: "/sitio/afore.webp", ruta: "afore",
    alt: "Resumen «¿Qué requiere atención ahora?» de Nomira AFORE (datos ficticios)." },
  { clave: "leads", nombre: "Nomira Leads", lema: "Ningún prospecto sin respuesta", ancho: 2,
    texto: "A quién atender hoy y qué campañas le traen clientes.",
    puntos: ["Tablero", "Costo por cliente"], imagen: "/sitio/leads.webp", ruta: "leads",
    alt: "Bandeja «¿A quién hay que atender?» de Nomira Leads (datos ficticios)." },
  { clave: "academia", nombre: "Nomira Academia", lema: "Capacite a su equipo", ancho: 2,
    texto: "Cursos breves, avance por persona y constancias de participación.",
    puntos: ["Cursos", "Constancias"], imagen: "/sitio/academia.webp", ruta: "academia",
    alt: "Pantalla «Mi aprendizaje» de Nomira Academia (datos ficticios)." },
];
const ANCHO: Record<number, string> = { 2: "lg:col-span-2", 3: "lg:col-span-3", 4: "lg:col-span-4" };

const CIFRAS = [["10", "módulos para elegir"], ["2 días", "de prueba, sin tarjeta"], ["0", "programas que instalar"], ["Diaria", "revisión de estrados"]];

const INCLUIDO = [
  ["Clientes y cobranza", "Directorio, saldos, pagos y recibos."],
  ["Asistente IA", "Borradores y resúmenes; 30 usos al mes."],
  ["Buscador de tesis", "Jurisprudencia del SJF con filtros."],
  ["Bolsa de trabajo", "Publique vacantes y reciba CVs gratis."],
];

const PASOS = [
  ["Cree su cuenta", "Elija hasta 3 módulos y úselos 2 días gratis. Sin tarjeta."],
  ["Pruébelo con un caso real", "Suba sus documentos y vea el resultado. Si quiere, le acompañamos en el primero."],
  ["Quédese solo con lo que use", "Encienda o apague módulos desde su perfil y pague mes a mes. Su información se conserva."],
];

const PREGUNTAS = [
  ["¿Mis clientes pueden ver cómo va su asunto?", "Sí, con Nomira Connect: usted publica las etapas de cada asunto y su cliente las consulta desde el celular, sin app ni cuenta. También le puede escribir por ahí. Usted decide qué se comparte; las notas internas nunca se muestran."],
  ["¿Tengo que instalar algo?", "No. Nomira funciona desde el navegador, en computadora o tableta."],
  ["¿Tengo que contratar todos los módulos?", "No. Cada módulo funciona por separado y usted elige la combinación. Clientes y cobranza, el Asistente IA y el buscador de tesis vienen incluidos. Apagar un módulo no borra su información."],
  ["¿La inteligencia artificial inventa tesis?", "No. Solo puede citar tesis de la biblioteca de Nomira, copiada de fuentes oficiales de la SCJN. Si escribe una que no puede verificar, Nomira la elimina y se lo avisa."],
  ["¿Quién puede ver mis expedientes?", "Solo los usuarios de su despacho. Ni otras empresas ni el equipo de Nomira tienen acceso a sus expedientes ni a sus documentos."],
  ["¿Nomira decide si mi cliente tiene derecho?", "No. Nomira lee, organiza y señala lo que hay que revisar. La valoración jurídica y las decisiones son siempre del abogado."],
  ["¿Sirve para notarías?", "Sí, con el módulo de Escrituración. No sustituye el protocolo electrónico, la firma notarial, el timbrado ni los avisos a la UIF."],
  ["¿Puedo cobrar y facturar a mis clientes?", "Sí, con sus propias cuentas de Stripe y Facturapi: ligas de pago por WhatsApp y facturas CFDI 4.0. El dinero llega directo a su cuenta."],
  ["¿Qué pasa al terminar la prueba?", "Su información se conserva. Para seguir, contrate desde su perfil los módulos que necesite o pida ayuda a un asesor."],
];

const d = (ms: number) => ({ "--d": `${ms}ms` }) as React.CSSProperties;

/** Animaciones del sitio: aparición al desplazarse, encabezado compacto y barra de lectura. */
function useAnimaciones(raiz: React.RefObject<HTMLDivElement | null>) {
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

/** Marco de navegador para las capturas. */
function Ventana({ src, alt, ruta, prioridad = false, className = "" }: { src: string; alt: string; ruta: string; prioridad?: boolean; className?: string }) {
  return (
    <div className={`s-ventana overflow-hidden rounded-2xl border border-crema-300 bg-white shadow-flotante ${className}`}>
      <div className="flex items-center gap-1.5 border-b border-crema-300 bg-slate-100 px-3 py-2" aria-hidden>
        <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28C840]" />
        <span className="ml-3 hidden truncate rounded-md bg-white px-3 py-0.5 text-[11px] text-slate-500 sm:block">nomirasoft.com/{ruta}</span>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} loading={prioridad ? "eager" : "lazy"} className="block w-full object-cover object-left-top" />
    </div>
  );
}

/** Marco de celular. */
function Celular({ src, alt, className = "" }: { src: string; alt: string; className?: string }) {
  return (
    <div className={`overflow-hidden rounded-[2rem] border-[7px] border-marino-900 bg-marino-900 shadow-flotante ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} loading="lazy" className="block w-full rounded-[1.5rem]" />
    </div>
  );
}

/** Luz que sigue al mouse dentro de una tarjeta. */
const foco = (e: React.MouseEvent<HTMLElement>) => {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
};

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
  const [prueba, setPrueba] = useState(false);
  const [conSesion, setConSesion] = useState(false);
  const [menu, setMenu] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const { desplazado, progreso } = useAnimaciones(raiz);
  const { oscuro, cambiar } = useTema();
  useEffect(() => {
    setConSesion(!!leerSesion());
    api.get("/publico").then((p) => { setWhatsapp(p.whatsapp || null); setDesde(p.precio_desde || null); setPrueba(!!p.permitir_registro); }).catch(() => {});
  }, []);
  const acceso = conSesion
    ? <Link href="/inicio" className="btn-turquesa">Ir a Nomira</Link>
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
            {NAV.map(([h, t]) => <a key={h} href={h} className={`group relative whitespace-nowrap transition hover:text-marino ${h.startsWith("/") ? "font-semibold text-turquesa-700" : ""}`}>{t}
              <span className="absolute -bottom-1 left-0 h-0.5 w-full origin-left scale-x-0 rounded-full bg-turquesa transition-transform duration-300 group-hover:scale-x-100" aria-hidden /></a>)}
          </nav>
          <div className="flex items-center gap-2">
            <BotonTema oscuro={oscuro} onCambiar={cambiar} />
            {prueba && !conSesion ? <Link href="/login?registro=1" className="btn-primario hidden sm:inline-flex">Pruebe 2 días gratis</Link>
              : <a href="#informes" className="btn-primario hidden sm:inline-flex">Solicitar informes</a>}
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
          <div className="s-malla pointer-events-none absolute inset-0" aria-hidden />
          <div className="s-cuadricula s-cuadricula-fade pointer-events-none absolute inset-0" aria-hidden />
          <div className="s-aurora pointer-events-none absolute -right-40 -top-40 h-[34rem] w-[34rem] rounded-full bg-turquesa/20 blur-3xl" aria-hidden />
          <div className="s-aurora pointer-events-none absolute -left-32 top-40 h-[26rem] w-[26rem] rounded-full bg-turquesa-brillante/10 blur-3xl" style={d(-6000)} aria-hidden />
          <div className="relative mx-auto max-w-6xl px-5 pb-10 pt-14 text-center lg:pt-20">
            <span className="s-entrada inline-flex items-center gap-2 rounded-full border border-turquesa/25 bg-white/70 py-1 pl-1 pr-3 text-xs font-semibold text-marino shadow-sm backdrop-blur">
              <span className="rounded-full bg-marino px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">Nuevo</span>
              Active módulos desde su perfil y pague mes a mes</span>
            <h1 style={d(100)} className="s-entrada mx-auto mt-6 max-w-4xl font-marca text-[2.6rem] font-extrabold leading-[1.02] tracking-tight text-marino sm:text-6xl lg:text-7xl">
              Todo su despacho,<br className="hidden sm:block" /> <span className="s-degradado">en claro.</span></h1>
            <p style={d(200)} className="s-entrada mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-600 sm:text-xl">
              Plazos, liquidaciones, jurisprudencia, clientes y cobranza en un solo lugar. Nomira hace el trabajo repetitivo;
              <b className="text-marino"> usted decide</b>.</p>
            <div style={d(320)} className="s-entrada mt-8 flex flex-wrap justify-center gap-3">
              {prueba ? <>
                <Link href="/login?registro=1" className="btn-turquesa s-brillo px-6 py-3.5 text-base shadow-[0_12px_30px_-12px_rgba(1,178,166,.8)] hover:-translate-y-0.5">Pruebe 2 días gratis →</Link>
                <a href="#modulos" className="btn-sec px-6 py-3.5 text-base hover:-translate-y-0.5">Ver los módulos</a></>
                : <><a href="#informes" className="btn-turquesa s-brillo px-6 py-3.5 text-base shadow-[0_12px_30px_-12px_rgba(1,178,166,.8)] hover:-translate-y-0.5">Solicitar informes →</a>
                <a href="#modulos" className="btn-sec px-6 py-3.5 text-base hover:-translate-y-0.5">Ver los módulos</a></>}
            </div>
            <ul style={d(420)} className="s-entrada mt-6 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-slate-600">
              {[prueba ? "2 días gratis, sin tarjeta" : "Sin instalar nada", "Portal seguro para sus clientes", "Sus expedientes, privados"].map((t) => (
                <li key={t} className="flex items-center gap-2"><span className="text-turquesa-700"><Palomita /></span>{t}</li>))}
            </ul>

            {/* Producto: navegador + celular + avisos flotantes */}
            <div className="relative mx-auto mt-14 max-w-5xl">
              <div className="pointer-events-none absolute inset-x-10 -bottom-6 top-10 rounded-[3rem] bg-gradient-to-r from-turquesa/30 via-turquesa-brillante/20 to-marino/20 blur-3xl" aria-hidden />
              <div style={d(450)} className="s-levantar relative">
                <Inclinable>
                  <Ventana src="/sitio/app-inicio.webp" ruta="inicio" prioridad className="s-borde-luz text-left"
                    alt="Inicio de Nomira: pendientes de hoy, por cobrar, prospectos y accesos rápidos (datos ficticios)." />
                </Inclinable>
              </div>
              <div style={d(900)} className="s-entrada absolute -bottom-10 -right-2 hidden w-40 sm:block lg:-right-10 lg:w-48">
                <div className="s-flotar" style={d(-1500)}><Celular src="/sitio/app-cel.webp" alt="Nomira en el celular (datos ficticios)." /></div>
              </div>
              <div aria-hidden className="pointer-events-none absolute -left-4 top-44 hidden md:block lg:-left-12">
                <div className="s-flotar flex items-center gap-2 rounded-2xl border border-crema-300 bg-white/90 px-3 py-2 text-xs font-semibold text-marino shadow-flotante backdrop-blur">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><Palomita /></span>Plazo validado</div>
              </div>
              <div aria-hidden className="pointer-events-none absolute -left-8 bottom-24 hidden md:block lg:-left-16">
                <div style={d(-2500)} className="s-flotar flex items-center gap-2 rounded-2xl bg-marino px-3 py-2 text-xs font-semibold text-white shadow-flotante">
                  <span className="s-pulso h-2 w-2 rounded-full bg-turquesa-brillante" />Nueva publicación en estrados</div>
              </div>
              <div aria-hidden className="pointer-events-none absolute -top-5 right-24 hidden md:block">
                <div style={d(-4000)} className="s-flotar flex items-center gap-2 rounded-2xl border border-crema-300 bg-white/90 px-3 py-2 text-xs font-semibold text-marino shadow-flotante backdrop-blur">
                  <span className="text-base" aria-hidden>💳</span>Pago recibido · $3,500</div>
              </div>
            </div>
            <p className="relative mt-16 text-xs text-slate-500">Capturas reales de Nomira con datos ficticios de demostración.</p>
          </div>

          {/* Cifras */}
          <div className="relative mx-auto max-w-5xl px-5 pb-16">
            <dl className="grid grid-cols-2 divide-crema-300 overflow-hidden rounded-3xl border border-crema-300 bg-white/70 backdrop-blur md:grid-cols-4 md:divide-x">
              {CIFRAS.map(([n, t], i) => (
                <div key={t} style={d(i * 100)} className="s-revelar px-6 py-5 text-center">
                  <dt className="sr-only">{t}</dt>
                  <dd className="font-marca text-3xl font-extrabold text-marino">{n}</dd>
                  <dd className="mt-1 text-sm text-slate-600">{t}</dd>
                </div>))}
            </dl>
          </div>
        </section>

        {/* El problema */}
        <section className="relative overflow-hidden bg-marino-700 text-white">
          <div className="s-aurora pointer-events-none absolute -right-20 -top-24 h-80 w-80 rounded-full bg-turquesa-brillante/15 blur-3xl" aria-hidden />
          <div className="relative mx-auto grid max-w-6xl gap-6 px-5 py-12 md:grid-cols-[1fr_1.4fr] md:items-center">
            <h2 className="s-revelar-lado font-marca text-3xl font-extrabold leading-tight">El trabajo repetitivo<br /><span className="text-turquesa-brillante">no debería tomar días.</span></h2>
            <p style={d(150)} className="s-revelar text-lg leading-relaxed text-white/75">
              Sumar quincenas, buscar fechas entre documentos o perseguir al cliente por un acta. Nomira se encarga de eso y le deja lo que requiere su criterio.</p>
          </div>
        </section>

        {/* Jurisprudencia: buscador con filtros + IA que no inventa */}
        <section id="jurisprudencia" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-5 pt-20">
            <div className="s-revelar max-w-3xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Jurisprudencia</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Así busca jurisprudencia hoy. <span className="text-turquesa-700">Así la busca un despacho con Nomira.</span></h2>
              <p className="mt-3 text-slate-600">Encuentre la tesis exacta con filtros y pida a la IA que le explique cuál aplica, citando solo tesis reales del Semanario Judicial de la Federación.</p>
            </div>
            <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_1.25fr] lg:items-start">
              <div className="s-revelar-lado rounded-3xl border border-crema-300 bg-white/70 p-6">
                <p className="text-sm font-bold uppercase tracking-wide text-slate-500">Búsqueda tradicional</p>
                <ul className="mt-4 space-y-3 text-slate-600">
                  {["Cientos de resultados que hay que abrir uno por uno.", "Copiar a mano rubro, clave y registro digital.",
                    "La IA genérica «cita» tesis que no existen."].map((t) => (
                    <li key={t} className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full bg-red-50 text-sm font-bold text-red-600" aria-hidden>✕</span>{t}</li>))}
                </ul>
              </div>
              <div style={d(150)} className="s-revelar rounded-3xl bg-marino p-6 text-white shadow-[0_30px_60px_-30px_rgba(11,37,69,.6)]">
                <p className="text-sm font-bold uppercase tracking-wide text-turquesa-brillante">Con Nomira</p>
                <div className="mt-4 rounded-2xl bg-white p-4 text-marino" aria-label="Ejemplo de búsqueda de tesis en Nomira">
                  <div className="flex gap-2"><div className="flex-1 rounded-lg border border-crema-300 px-3 py-2 text-sm text-slate-500">suspensión clausura establecimiento</div>
                    <span className="rounded-lg bg-turquesa px-3 py-2 text-sm font-bold text-marino-900">Buscar</span></div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-semibold">
                    {["Jurisprudencia", "Materia: Común", "Órgano: Segunda Sala", "Desde 2021"].map((t) => <span key={t} className="rounded-full bg-turquesa-50 px-2.5 py-1 text-turquesa-700">{t}</span>)}</div>
                  <div className="mt-3 rounded-xl border border-crema-300 p-3">
                    <div className="flex flex-wrap items-center gap-1.5 text-[11px]"><span className="rounded-full bg-marino px-2 py-0.5 font-semibold text-white">Jurisprudencia</span>
                      <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-800">✓ Verificada</span><span className="text-slate-500">Registro digital · clave · época</span></div>
                    <p className="mt-1.5 text-sm font-bold">Rubro oficial de la tesis</p>
                    <p className="text-xs text-slate-500">Texto completo · Ficha PDF · Liga al Semanario · Copiar cita</p>
                  </div>
                </div>
                <ul className="mt-5 space-y-3 text-white/85">
                  {["Filtros por tipo, materia, órgano, año y época.",
                    "La IA cita solo tesis verificadas. Si no puede comprobar una, la borra y se lo avisa.",
                    "Texto, ficha PDF, liga oficial y la cita lista para pegar."].map((t) => (
                    <li key={t} className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full bg-turquesa text-sm font-bold text-white" aria-hidden>✓</span>{t}</li>))}
                </ul>
                <Link href="/login?registro=1" className="btn-turquesa mt-6 inline-flex px-5 py-3">Pruébelo 2 días gratis →</Link>
              </div>
            </div>
          </div>
        </section>

        {/* Módulos */}
        <section id="modulos" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-5 pt-20">
            <div className="s-revelar max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Módulos</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-5xl">Un módulo para cada parte de su trabajo</h2>
              <p className="mt-3 text-slate-600">Contrate solo los que necesita. Todos comparten usuarios, clientes y seguridad.</p>
            </div>
            <div className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-6">
              {BENTO.map((m, i) => (
                <article key={m.clave} onMouseMove={foco} style={d((i % 3) * 110)}
                  className={`s-revelar s-tarjeta s-foco tarjeta group flex flex-col overflow-hidden ${ANCHO[m.ancho]} ${m.celular ? "bg-gradient-to-b from-turquesa/15 to-transparent" : ""}`}>
                  <div className={`relative overflow-hidden ${m.celular ? "flex justify-center px-10 pt-6" : "px-5 pt-5"} ${m.ancho >= 3 ? "h-64 sm:h-72" : "h-52"}`}>
                    {m.celular
                      ? <Celular src={m.imagen} alt={m.alt} className="w-52 translate-y-2" />
                      : <Ventana src={m.imagen} alt={m.alt} ruta={m.ruta} />}
                    <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-white to-transparent" aria-hidden />
                  </div>
                  <div className="flex flex-1 flex-col p-6 pt-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">{m.lema}</span>
                    <h3 className="mt-1 font-marca text-xl font-extrabold text-marino transition group-hover:text-turquesa-700">{m.nombre}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{m.texto}</p>
                    <div className="mt-auto flex flex-wrap gap-1.5 pt-4">
                      {m.puntos.map((p) => <span key={p} className="rounded-full border border-turquesa/25 bg-turquesa-50 px-2.5 py-0.5 text-xs font-semibold text-turquesa-700">{p}</span>)}
                    </div>
                  </div>
                </article>
              ))}
            </div>
            <div className="s-revelar mt-6 rounded-3xl border border-turquesa/30 bg-gradient-to-br from-turquesa-50 to-white p-6 md:p-8">
              <span className="rounded-full bg-turquesa px-3 py-1 text-xs font-bold uppercase tracking-wider text-marino-900">Incluido en todos los planes</span>
              <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {INCLUIDO.map(([t, dd]) => (
                  <li key={t} className="flex gap-2"><span className="mt-0.5 text-turquesa-700"><Palomita /></span>
                    <span><span className="block font-bold text-marino">{t}</span><span className="block text-sm text-slate-600">{dd}</span></span></li>))}
              </ul>
              <p className="mt-5 text-sm text-slate-600">Además, módulo opcional de <b className="text-marino">Pruebas psicométricas</b> para sus vacantes.</p>
            </div>
          </div>
        </section>

        {/* Nomira Connect */}
        <section id="connect" className="relative scroll-mt-20 overflow-hidden bg-marino-900 text-white">
          <div className="s-aurora pointer-events-none absolute -left-24 top-10 h-96 w-96 rounded-full bg-turquesa/20 blur-3xl" aria-hidden />
          <div className="s-aurora pointer-events-none absolute -right-24 bottom-0 h-96 w-96 rounded-full bg-turquesa-brillante/10 blur-3xl" style={d(-5000)} aria-hidden />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 py-20 lg:grid-cols-[1.05fr_1fr]">
            <div>
              <span className="s-revelar inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-turquesa-brillante">
                <span className="rounded-full bg-turquesa px-2 py-0.5 text-[10px] text-marino-900">Nuevo</span>Nomira Connect</span>
              <h2 style={d(80)} className="s-revelar mt-4 font-marca text-3xl font-extrabold leading-tight sm:text-5xl">Que tus clientes sigan su expediente, <span className="text-turquesa-brillante">no a su abogado.</span></h2>
              <p style={d(160)} className="s-revelar mt-4 text-lg leading-relaxed text-white/75">
                Comparta el avance de cada asunto por etapas, como el rastreo de un pedido. Su cliente lo consulta desde el celular las 24 horas y le escribe por un solo canal.</p>
              <div style={d(240)} className="s-revelar mt-8 grid gap-4 sm:grid-cols-2">
                {[["Para su despacho", ["Menos llamadas de «¿cómo va lo mío?»", "Mensajes ordenados por cliente y motivo", "Notas internas que el cliente nunca ve"]],
                  ["Para su cliente", ["Ve en qué etapa va, en palabras sencillas", "Sabe qué documentos o acciones faltan", "Sin app ni cuenta: letra grande y alto contraste"]]].map(([t, l]) => (
                  <div key={t as string} className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
                    <p className="text-sm font-bold text-turquesa-brillante">{t as string}</p>
                    <ul className="mt-3 space-y-2">{(l as string[]).map((x) => <li key={x} className="flex gap-2 text-sm text-white/80"><span className="mt-0.5 text-turquesa-brillante"><Palomita /></span>{x}</li>)}</ul>
                  </div>))}
              </div>
              <p className="mt-4 text-xs text-white/50">Sin porcentajes ni fechas inventadas: el abogado decide qué se comparte y cuándo.</p>
              <div className="mt-6 flex flex-wrap gap-3">
                <a href="#informes" className="btn-turquesa s-brillo px-5 py-3 text-base">Solicitar una demostración →</a>
                <a href="#informes" className="rounded-xl border border-white/25 px-5 py-3 text-base font-semibold text-white transition hover:bg-white/10">Pedir información</a></div>
            </div>
            <div className="relative mx-auto flex w-full max-w-md justify-center">
              <div className="pointer-events-none absolute inset-10 rounded-full bg-turquesa/25 blur-3xl" aria-hidden />
              <div style={d(150)} className="s-revelar relative z-10 w-52 -rotate-3 sm:w-60"><div className="s-flotar"><Celular src="/sitio/connect-inicio.webp" alt="Portal del cliente: su asunto en la etapa «Desahogo de pruebas» y su próxima audiencia (datos ficticios)." /></div></div>
              <div style={d(300)} className="s-revelar relative -ml-10 mt-16 w-52 rotate-3 sm:w-60"><div className="s-flotar" style={d(-2000)}><Celular src="/sitio/connect-etapas.webp" alt="Línea de tiempo de etapas: completadas en verde y la etapa actual en turquesa (datos ficticios)." /></div></div>
              <div aria-hidden className="pointer-events-none absolute -left-2 top-6 z-20 hidden sm:block">
                <div className="s-flotar flex items-center gap-2 rounded-2xl bg-white px-3 py-2 text-xs font-semibold text-marino shadow-flotante">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><Palomita /></span>Demanda admitida</div></div>
              <div aria-hidden className="pointer-events-none absolute -right-2 bottom-16 z-20 hidden sm:block">
                <div style={d(-3000)} className="s-flotar flex items-center gap-2 rounded-2xl bg-turquesa px-3 py-2 text-xs font-semibold text-marino-900 shadow-flotante">💬 Nuevo mensaje de su abogado</div></div>
            </div>
          </div>
        </section>

        {/* Por qué Nomira */}
        <section id="por-que" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-5 pt-20">
            <div className="s-revelar max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Por qué Nomira</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Más que un control de expedientes</h2>
              <p className="mt-3 text-slate-600">La mayoría de los sistemas para despachos guardan información. Nomira además hace el trabajo pesado y mantiene informado a su cliente.</p>
            </div>
            <div className="s-revelar tarjeta mt-8 overflow-x-auto">
              <table className="w-full min-w-[36rem] text-sm">
                <thead><tr className="border-b border-crema-300 text-left">
                  <th className="p-4 font-semibold text-slate-500">Lo que necesita su despacho</th>
                  <th className="p-4 text-center font-semibold text-slate-500">Control de expedientes tradicional</th>
                  <th className="p-4 text-center font-marca font-extrabold text-marino">Nomira</th></tr></thead>
                <tbody>{([
                  ["Expedientes, agenda y audiencias", true, true],
                  ["Cobranza de honorarios con recibos", true, true],
                  ["Su cliente ve el avance y sube documentos desde el celular", false, true],
                  ["Revisión automática de estrados digitales", false, true],
                  ["Liquidación LFT con operación y artículo", false, true],
                  ["IA que cita solo tesis verificadas", false, true],
                  ["Contrata solo lo que usa", false, true],
                ] as [string, boolean, boolean][]).map(([t, a, b]) => (
                  <tr key={t} className="border-b border-crema-200 last:border-0">
                    <td className="p-4 font-medium text-slate-700">{t}</td>
                    <td className="p-4 text-center">{a ? <span className="inline-flex text-slate-400"><Palomita className="h-4 w-4" /></span> : <span className="text-slate-400" aria-label="No">—</span>}</td>
                    <td className="p-4 text-center">{b && <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-turquesa text-marino-900"><Palomita className="h-4 w-4" /></span>}</td>
                  </tr>))}</tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-slate-500">Comparación general con sistemas que solo llevan expedientes, agenda y cobranza.</p>

            <div className="s-revelar mt-10 grid items-center gap-6 overflow-hidden rounded-3xl bg-marino p-8 text-white md:grid-cols-[1.4fr_1fr]">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-turquesa-brillante">Herramienta gratuita</span>
                <h3 className="mt-2 font-marca text-2xl font-extrabold sm:text-3xl">Calcule un finiquito o una liquidación ahora</h3>
                <p className="mt-2 text-white/75">Con fechas y salario ve el desglose al instante, con el artículo de cada concepto. Sin registrarse.</p>
              </div>
              <div className="flex md:justify-end"><Link href="/calculadora-finiquito" className="btn-turquesa s-brillo px-5 py-3 text-base">Abrir la calculadora →</Link></div>
            </div>
          </div>
        </section>

        {/* Cómo empezar */}
        <section id="empezar" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-5 py-20">
            <div className="s-revelar max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Cómo empezar</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">En tres pasos, sin compromiso</h2>
            </div>
            <ol className="s-revelar relative mt-10 grid gap-5 md:grid-cols-3">
              <span className="s-trazo absolute left-6 right-6 top-11 hidden h-0.5 rounded-full bg-gradient-to-r from-turquesa via-turquesa-brillante to-marino md:block" aria-hidden />
              {PASOS.map(([t, dd], i) => (
                <li key={t} style={d(i * 130)} className="s-revelar s-tarjeta tarjeta relative p-6">
                  <span className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-marino font-marca text-lg font-extrabold text-white">{i + 1}</span>
                  <h3 className="mt-4 text-lg font-bold text-marino">{t}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{dd}</p>
                </li>
              ))}
            </ol>
            <div className="s-revelar mt-8 flex flex-wrap items-center gap-4">
              {prueba ? <Link href="/login?registro=1" className="btn-turquesa s-brillo px-5 py-3 text-base">Pruebe 2 días gratis →</Link>
                : <a href="#informes" className="btn-turquesa s-brillo px-5 py-3 text-base">Solicitar informes →</a>}
              {desde && <span className="text-sm text-slate-600">Paquetes desde <b className="text-marino">{mxn(desde).replace(/\.00$/, "")} MXN + IVA</b></span>}
            </div>
          </div>
        </section>

        {/* Portal del cliente */}
        <section id="clientes" className="scroll-mt-20">
          <div className="mx-auto grid max-w-6xl gap-12 px-5 py-20 lg:grid-cols-[1fr_1fr] lg:items-center">
            <div className="s-revelar-lado">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Su cliente, conectado</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Menos llamadas de «¿cómo va mi asunto?»</h2>
              <p className="mt-3 text-slate-600">Su cliente ve en su celular solo lo que usted comparte, sabe qué documentos faltan y los envía en un minuto.</p>
              <ul className="mt-6 space-y-4">
                {[["Enlace seguro que vence", "Pide un código al correo del cliente y solo sirve para enviar archivos."],
                  ["Usted revisa antes que nada", "Lo que llega queda pendiente hasta que usted lo acepta."],
                  ["Sin datos sensibles en los mensajes", "Los avisos solo dicen que hay novedades; el detalle está en el portal."]].map(([t, d]) => (
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

        {/* Seguridad */}
        <section id="seguridad" className="relative scroll-mt-20 overflow-hidden bg-marino-900 text-white">
          <div className="s-aurora pointer-events-none absolute -left-24 top-10 h-96 w-96 rounded-full bg-turquesa/15 blur-3xl" aria-hidden />
          <div className="relative mx-auto max-w-6xl px-5 py-20">
            <div className="s-revelar max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-brillante">Seguridad y privacidad</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold sm:text-4xl">Sus expedientes son solo suyos</h2>
              <p className="mt-3 text-white/70">Datos personales y secreto profesional, tratados con ese cuidado.</p>
            </div>
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[["Separado por organización", "Cada despacho ve únicamente sus propios expedientes, casos, documentos y clientes."],
                ["Ni nosotros los vemos", "El equipo de Nomira administra cuentas, pero no tiene acceso a sus expedientes ni a sus documentos."],
                ["Accesos protegidos", "Conexión cifrada (HTTPS), contraseñas protegidas y bloqueo ante intentos repetidos."],
                ["Datos sensibles cifrados", "CURP, NSS y credenciales se guardan cifrados y se muestran enmascarados; verlos completos queda registrado."],
                ["Enlaces que vencen", "Los enlaces para sus clientes caducan, se pueden cancelar, piden código y no contienen información del caso."],
                ["Todo queda registrado", "Bitácora de quién hizo qué y cuándo."]].map(([t, dd], i) => (
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
            <a href="#empezar" className="hover:text-white">Cómo empezar</a>
            <a href="#seguridad" className="hover:text-white">Seguridad</a>
            <a href="#informes" className="hover:text-white">Informes</a>
            <Link href="/empleos" className="hover:text-white">Empleos</Link>
            <Link href="/calculadora-finiquito" className="hover:text-white">Calculadora de finiquito</Link>
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
