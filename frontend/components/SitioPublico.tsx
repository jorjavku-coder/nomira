"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import FormularioInformes from "@/components/FormularioInformes";
import Logo from "@/components/Logo";
import { api, leerSesion } from "@/lib/api";

const NAV = [["#como-funciona", "Cómo funciona"], ["#beneficios", "Beneficios"], ["#seguridad", "Seguridad"], ["#preguntas", "Preguntas"]];

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
  ["¿Cómo empiezo?", "Llene el formulario de informes o escríbanos. Le damos de alta y le explicamos cómo cargar su catálogo y su primer expediente."],
];

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
  const [conSesion, setConSesion] = useState(false);
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    setConSesion(!!leerSesion());
    api.get("/publico").then((p) => setWhatsapp(p.whatsapp || null)).catch(() => {});
  }, []);
  const acceso = conSesion
    ? <Link href="/app" className="btn-turquesa">Ir a mis expedientes</Link>
    : <Link href="/login" className="btn-sec">Iniciar sesión</Link>;

  return (
    <div className="bg-crema text-slate-800">
      {/* Encabezado */}
      <header className="sticky top-0 z-40 border-b border-crema-300/70 bg-crema/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3.5">
          <Link href="/" aria-label="Nomira, inicio"><Logo /></Link>
          <nav className="hidden items-center gap-7 text-sm font-medium text-slate-600 md:flex" aria-label="Secciones">
            {NAV.map(([h, t]) => <a key={h} href={h} className="transition hover:text-marino">{t}</a>)}
          </nav>
          <div className="flex items-center gap-2">
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
          <div className="pointer-events-none absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-turquesa/15 blur-3xl" aria-hidden />
          <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-14 lg:grid-cols-[1fr_1.1fr] lg:pt-20">
            <div className="relative">
              <span className="inline-flex items-center gap-2 rounded-full bg-turquesa-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-turquesa-700">
                <span className="h-1.5 w-1.5 rounded-full bg-turquesa" aria-hidden />Análisis de comprobantes de nómina</span>
              <h1 className="mt-5 font-marca text-4xl font-extrabold leading-[1.08] text-marino sm:text-5xl lg:text-[3.4rem]">
                Cada prestación,<br /><span className="text-turquesa">en claro.</span></h1>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-slate-600">
                Nomira lee los comprobantes de nómina en PDF, suma solo las prestaciones de su catálogo autorizado y le entrega el
                <b className="text-marino"> desglose por quincena</b>, con cada cifra ligada a la página de donde salió.</p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href="#informes" className="btn-turquesa px-5 py-3 text-base">Solicitar informes</a>
                <a href="#como-funciona" className="btn-sec px-5 py-3 text-base">Ver cómo funciona</a>
              </div>
              <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
                {["Sin instalar nada", "Excel y PDF con su logotipo", "Sus expedientes, privados"].map((t) => (
                  <li key={t} className="flex items-center gap-2"><span className="text-turquesa-700"><Palomita /></span>{t}</li>))}
              </ul>
            </div>
            <div className="relative">
              <div className="absolute -inset-3 rotate-1 rounded-[2rem] bg-marino/5" aria-hidden />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/sitio/visor.webp" width={1600} height={1034} alt="Nomira muestra el comprobante original junto a lo que leyó: cada percepción con su clave, importe y si se incluye o queda pendiente."
                className="relative w-full rounded-3xl border border-crema-300 bg-white shadow-flotante" />
              <p className="relative mt-3 text-center text-xs text-slate-500">Datos ficticios de demostración.</p>
            </div>
          </div>
        </section>

        {/* El problema */}
        <section className="bg-marino-700 text-white">
          <div className="mx-auto grid max-w-6xl gap-10 px-5 py-16 md:grid-cols-[1fr_1.4fr] md:items-center">
            <h2 className="font-marca text-3xl font-extrabold leading-tight">Sumar quincenas a mano<br /><span className="text-turquesa-brillante">no debería tomar días.</span></h2>
            <p className="text-lg leading-relaxed text-white/75">
              Un expediente puede traer decenas de comprobantes, cada uno con varias percepciones. Copiar claves e importes a una hoja de
              cálculo es lento y basta un renglón equivocado para que el total no cuadre. Nomira hace la lectura y la suma, y le deja a usted
              lo que de verdad requiere criterio.</p>
          </div>
        </section>

        {/* Cómo funciona */}
        <section id="como-funciona" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-5 py-20">
            <div className="max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Cómo funciona</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">De los PDF al desglose en cuatro pasos</h2>
            </div>
            <ol className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {PASOS.map(([t, d], i) => (
                <li key={t} className="tarjeta relative p-6">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-marino font-marca text-lg font-extrabold text-white">{i + 1}</span>
                  <h3 className="mt-4 text-lg font-bold text-marino">{t}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{d}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Beneficios */}
        <section id="beneficios" className="scroll-mt-20 border-y border-crema-300 bg-white">
          <div className="mx-auto grid max-w-6xl gap-12 px-5 py-20 lg:grid-cols-[1.25fr_1fr] lg:items-start">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Beneficios</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Un resultado que puede defender</h2>
              <p className="mt-3 max-w-xl text-slate-600">Nomira no adivina: aplica reglas claras y le muestra de dónde sale cada número.</p>
              <ul className="mt-8 grid gap-6 sm:grid-cols-2">
                {BENEFICIOS.map(([t, d]) => (
                  <li key={t} className="flex gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-turquesa-50 text-turquesa-700"><Palomita /></span>
                    <span><span className="block font-bold text-marino">{t}</span><span className="mt-1 block text-sm leading-relaxed text-slate-600">{d}</span></span>
                  </li>
                ))}
              </ul>
            </div>
            <figure className="lg:sticky lg:top-24">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/sitio/resultados.webp" width={1099} height={1076} loading="lazy" alt="Tabla de Nomira con el total por clave de prestación: clave, concepto del catálogo, veces que aparece y total."
                className="w-full rounded-3xl border border-crema-300 shadow-flotante" />
              <figcaption className="mt-3 text-center text-xs text-slate-500">Total por clave de prestación (datos ficticios).</figcaption>
            </figure>
          </div>
        </section>

        {/* Para quién */}
        <section>
          <div className="mx-auto max-w-6xl px-5 py-16">
            <h2 className="text-center font-marca text-2xl font-extrabold text-marino">Pensado para quien revisa nóminas con detalle</h2>
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              {[["Despachos laborales", "Integre el monto de las prestaciones de cada trabajador con el respaldo de sus comprobantes."],
                ["Recursos humanos", "Verifique pagos de varios periodos y detecte quincenas faltantes o recibos repetidos."],
                ["Áreas jurídicas y contables", "Obtenga un desglose con trazabilidad completa, listo para integrarse a un expediente."]].map(([t, d]) => (
                <div key={t} className="rounded-3xl border border-crema-300 bg-white/60 p-6">
                  <h3 className="font-bold text-marino">{t}</h3><p className="mt-2 text-sm leading-relaxed text-slate-600">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Seguridad */}
        <section id="seguridad" className="scroll-mt-20 bg-marino-900 text-white">
          <div className="mx-auto max-w-6xl px-5 py-20">
            <div className="max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-turquesa-brillante">Seguridad y privacidad</span>
              <h2 className="mt-2 font-marca text-3xl font-extrabold sm:text-4xl">Sus expedientes son solo suyos</h2>
              <p className="mt-3 text-white/70">Los comprobantes de nómina contienen datos personales. Nomira está construido para tratarlos con ese cuidado.</p>
            </div>
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {[["Separado por organización", "Cada empresa ve únicamente sus propios expedientes, documentos y catálogos."],
                ["Ni nosotros los vemos", "El equipo de Nomira administra cuentas, pero no tiene acceso a sus expedientes ni a sus PDF."],
                ["Accesos protegidos", "Conexión cifrada (HTTPS), contraseñas protegidas y bloqueo ante intentos repetidos."],
                ["Todo queda registrado", "Bitácora de accesos, correcciones y validaciones para saber quién hizo qué y cuándo."]].map(([t, d]) => (
                <div key={t} className="rounded-3xl border border-white/10 bg-white/[0.04] p-6">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-turquesa-brillante/15 text-turquesa-brillante">
                    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 3l7 3v5c0 4.4-3 8.2-7 9.5-4-1.3-7-5.1-7-9.5V6z" /><path d="M9.5 12l1.8 1.8 3.5-3.6" /></svg>
                  </span>
                  <h3 className="mt-4 font-bold">{t}</h3><p className="mt-2 text-sm leading-relaxed text-white/65">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Preguntas */}
        <section id="preguntas" className="scroll-mt-20">
          <div className="mx-auto max-w-3xl px-5 py-20">
            <h2 className="text-center font-marca text-3xl font-extrabold text-marino sm:text-4xl">Preguntas frecuentes</h2>
            <div className="mt-10 space-y-3">
              {PREGUNTAS.map(([p, r]) => (
                <details key={p} className="group tarjeta px-5 py-4 open:shadow-sm">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-marino">
                    {p}<span className="text-xl text-turquesa-700 transition group-open:rotate-45" aria-hidden>+</span></summary>
                  <p className="mt-3 text-sm leading-relaxed text-slate-600">{r}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Informes */}
        <section id="informes" className="scroll-mt-20 border-t border-crema-300 bg-white">
          <div className="mx-auto grid max-w-6xl items-start gap-10 px-5 py-20 lg:grid-cols-[1fr_1.15fr]">
            <div>
              <span className="rounded-full bg-turquesa-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-turquesa-700">Informes y suscripción</span>
              <h2 className="mt-4 font-marca text-3xl font-extrabold leading-tight text-marino sm:text-4xl">Hablemos de su operación</h2>
              <p className="mt-3 text-slate-600">Cuéntenos cuántos expedientes revisa y cómo trabaja hoy. Le respondemos para explicarle cómo empezar.</p>
              {whatsapp && (
                <a href={`https://wa.me/${whatsapp}?text=${encodeURIComponent("Hola, me interesa conocer Nomira.")}`} target="_blank" rel="noopener noreferrer"
                  className="mt-6 inline-flex items-center gap-2 rounded-xl border border-[#25D366]/40 bg-[#25D366]/10 px-4 py-2.5 text-sm font-semibold text-[#128C4B] transition hover:bg-[#25D366]/20">
                  ¿Prefiere WhatsApp? Escríbanos directo →</a>
              )}
              <p className="mt-6 text-sm text-slate-500">¿Ya es cliente? <Link href="/login" className="font-semibold text-turquesa-700 hover:underline">Inicie sesión aquí</Link>.</p>
            </div>
            <FormularioInformes />
          </div>
        </section>
      </main>

      <footer className="bg-marino-900 text-white/60">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-sm">
          <div className="flex items-center gap-3"><Logo oscuro /><span className="hidden text-white/40 sm:inline">Cada prestación, en claro</span></div>
          <nav className="flex flex-wrap gap-5" aria-label="Pie de página">
            <a href="#como-funciona" className="hover:text-white">Cómo funciona</a>
            <a href="#informes" className="hover:text-white">Informes</a>
            <Link href="/login" className="hover:text-white">Iniciar sesión</Link>
          </nav>
          <p className="w-full text-xs text-white/40 sm:w-auto">© {new Date().getFullYear()} Nomira · Desarrollado por IMA</p>
        </div>
      </footer>
      {whatsapp && <BotonWhatsApp numero={whatsapp} />}
    </div>
  );
}
