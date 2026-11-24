"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import Shell, { Icono, useSesion } from "@/components/Shell";
import { api } from "@/lib/api";
import { GRUPOS, SECCIONES } from "@/lib/modulos";

const PASOS: [string, string, string][] = [
  ["Pon el nombre y logo de tu despacho", "/organizacion", "Aparecen en el menú y en lo que exportes."],
  ["Invita a tu equipo", "/usuarios", "Cada quien con su usuario: administrador, analista o consulta."],
  ["Da de alta tu primer cliente", "/clientes", "Se captura una vez y se elige en cualquier módulo."],
  ["Registra un asunto y su próximo plazo", "/agenda", "La Agenda te avisa antes de que venza."],
  ["Hazle una pregunta al Asistente con tesis", "/asistente?tipo=investigar", "Responde citando solo tesis reales del Semanario."],
];

function saludo() {
  const h = new Date().getHours();
  return h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
}

/** Inicio: qué es cada parte de Nomira y por dónde empezar. Es lo primero que se ve al entrar. */
export default function Inicio() {
  const sesion = useSesion();
  const [activos, setActivos] = useState<string[] | null>(null);
  const [agenda, setAgenda] = useState<number | null>(null);
  const [pasosOcultos, setPasosOcultos] = useState(false);
  useEffect(() => {
    try { setPasosOcultos(localStorage.getItem("nomira:pasos-ocultos") === "1"); } catch { /* sin almacenamiento */ }
    api.get("/organizacion").then((o) => setActivos(Object.values(o.modulos as Record<string, any>).filter((x) => x.activo).map((x) => x.clave)))
      .catch(() => setActivos(leerActivos()));
  }, []);
  function leerActivos() { return sesion?.modulos ?? []; }
  const disponible = (req: string | null) => !req || (activos ?? []).includes(req);
  useEffect(() => { if ((activos ?? []).includes("agenda")) api.get("/agenda/contador").then((r) => setAgenda(r.total)).catch(() => {}); }, [activos]);
  const nombre = sesion?.usuario.nombre.split(" ")[0] ?? "";
  const ocultarPasos = () => { setPasosOcultos(true); try { localStorage.setItem("nomira:pasos-ocultos", "1"); } catch { /* nada */ } };
  const faltan = SECCIONES.filter((s) => !disponible(s.requiere));
  return (
    <Shell>
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Inicio</p>
      <h1 className="text-3xl font-extrabold text-marino">{saludo()}{nombre ? `, ${nombre}` : ""}</h1>
      <p className="mt-1 max-w-3xl text-slate-600">Nomira reúne en un solo lugar lo que tu despacho hace todos los días: plazos, clientes y cobranza, escritos con IA y la preparación de cada caso. Aquí ves para qué sirve cada parte y por dónde empezar.</p>
      {agenda !== null && agenda > 0 && <Link href="/agenda" className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-amber-300 bg-amber-50 px-5 py-4 text-amber-900 hover:bg-amber-100">
        <span><b>{agenda} {agenda === 1 ? "pendiente vencido o de hoy" : "pendientes vencidos o de hoy"}</b> en tu Agenda.</span><span className="font-semibold">Ver agenda →</span></Link>}

      {!pasosOcultos && <section className="tarjeta mt-5 p-5" aria-label="Primeros pasos">
        <div className="flex items-start justify-between gap-3"><div><h2 className="text-lg font-bold text-marino">Empieza en 5 pasos</h2>
          <p className="text-sm text-slate-500">Diez minutos para dejar tu despacho listo.</p></div>
          <button className="text-xs text-slate-500 underline" onClick={ocultarPasos}>Ya no mostrar</button></div>
        <ol className="mt-3 grid gap-2 md:grid-cols-5">{PASOS.map(([t, href, d], i) => (
          <li key={href}><Link href={href} className="block h-full rounded-xl border border-crema-300 bg-white p-3 transition hover:border-turquesa hover:shadow-sm">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-turquesa text-sm font-bold text-white">{i + 1}</span>
            <span className="mt-2 block text-sm font-semibold text-marino">{t}</span><span className="mt-1 block text-xs text-slate-500">{d}</span></Link></li>))}</ol>
      </section>}

      {GRUPOS.map((g) => {
        const secs = SECCIONES.filter((s) => s.grupo === g && disponible(s.requiere));
        if (!secs.length) return null;
        return (
          <section key={g} className="mt-7" aria-label={g}>
            <h2 className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">{g}</h2>
            <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{secs.map((s) => (
              <article key={s.clave} className="tarjeta flex flex-col p-5">
                <Link href={s.href} className="flex items-center gap-3 text-lg font-bold text-marino hover:underline">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-turquesa-50 text-turquesa-700"><Icono nombre={s.icono} /></span>{s.nombre}</Link>
                <p className="mt-2 text-sm text-slate-700">{s.para}</p>
                <p className="mt-2 text-xs text-slate-500"><b className="text-slate-600">Ejemplo:</b> {s.ejemplo}</p>
                <div className="mt-auto flex flex-wrap items-center gap-3 pt-4 text-sm">
                  <Link href={s.empezar[1]} className="btn-turquesa">{s.empezar[0]}</Link>
                  <Link href={`/ayuda/${s.ayuda}`} className="font-semibold text-turquesa-700 underline">¿Cómo se usa?</Link></div>
              </article>))}</div>
          </section>
        );
      })}

      {activos && faltan.length > 0 && <section className="mt-8" aria-label="Más para tu despacho">
        <h2 className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Más para tu despacho</h2>
        <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{faltan.map((s) => (
          <article key={s.clave} className="rounded-2xl border border-dashed border-crema-300 p-5">
            <p className="flex items-center gap-3 font-bold text-marino"><span className="text-slate-400"><Icono nombre={s.icono} /></span>{s.nombre}</p>
            <p className="mt-2 text-sm text-slate-600">{s.para}</p>
            <Link href={`/soporte?tema=${encodeURIComponent("Quiero activar " + s.nombre)}`} className="mt-3 inline-block text-sm font-semibold text-turquesa-700 underline">Quiero activarlo</Link>
          </article>))}</div>
      </section>}
      <p className="mt-8 text-sm text-slate-500">¿Dudas? Cada pantalla tiene un botón «¿Cómo se usa?» y en <Link href="/ayuda" className="font-semibold text-turquesa-700 underline">Ayuda y manuales</Link> están todas las guías.</p>
    </Shell>
  );
}
