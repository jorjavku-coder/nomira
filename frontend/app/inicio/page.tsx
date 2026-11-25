"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import Shell, { Icono, useSesion } from "@/components/Shell";
import { api } from "@/lib/api";
import { SECCIONES } from "@/lib/modulos";

const PASOS: { clave: string; texto: string; href: string }[] = [
  { clave: "despacho", texto: "Pon el logo de tu despacho", href: "/organizacion" },
  { clave: "equipo", texto: "Invita a tu equipo", href: "/usuarios" },
  { clave: "cliente", texto: "Da de alta tu primer cliente", href: "/clientes" },
  { clave: "agenda", texto: "Registra tu próximo plazo", href: "/agenda" },
  { clave: "asistente", texto: "Pregúntale al Asistente IA", href: "/asistente?tipo=investigar" },
];

type Resumen = {
  modulos: string[]; aviso: { texto: string; href: string } | null;
  numeros: { clave: string; etiqueta: string; valor: string; href: string }[];
  hoy: { id: number; titulo: string; fecha: string; hora: string | null; situacion: string; asunto: string | null; href: string }[];
  pasos: Record<string, boolean>;
};

function saludo() {
  const h = new Date().getHours();
  return h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
}

function cuando(x: Resumen["hoy"][number]) {
  if (x.situacion === "vencido") return <span className="font-semibold text-red-700">Vencido</span>;
  if (x.situacion === "hoy") return <span className="font-semibold text-marino">{x.hora ? x.hora.slice(0, 5) : "Hoy"}</span>;
  return <span className="text-slate-600">{new Date(x.fecha + "T12:00:00").toLocaleDateString("es-MX", { weekday: "long" })}</span>;
}

/** Inicio: qué tengo que hacer hoy, en una sola pantalla. Las explicaciones de cada módulo viven en «¿Cómo se usa?» y en Ayuda. */
export default function Inicio() {
  const sesion = useSesion();
  const [r, setR] = useState<Resumen | null>(null);
  const [error, setError] = useState("");
  const [pasosOcultos, setPasosOcultos] = useState(true);
  useEffect(() => {
    try { setPasosOcultos(localStorage.getItem("nomira:pasos-ocultos") === "1"); } catch { setPasosOcultos(false); }
    api.get("/inicio").then(setR).catch((e) => setError(e.message));
  }, []);
  const nombre = sesion?.usuario.nombre.split(" ")[0] ?? "";
  const activos = r?.modulos ?? sesion?.modulos ?? [];
  const mios = SECCIONES.filter((s) => !s.requiere || activos.includes(s.requiere));
  const hechos = r ? PASOS.filter((p) => r.pasos[p.clave]).length : 0;
  const siguiente = r ? PASOS.find((p) => !r.pasos[p.clave]) : undefined;
  const ocultarPasos = () => { setPasosOcultos(true); try { localStorage.setItem("nomira:pasos-ocultos", "1"); } catch { /* nada */ } };
  const accesos: [string, string, string][] = [
    ...(activos.includes("agenda") ? [["Plazo o audiencia", "/agenda", "agenda"] as [string, string, string]] : []),
    ["Nuevo cliente", "/clientes", "clientes"],
    ["Preguntar a la IA", "/asistente", "asistente"],
    ["Buscar una tesis", "/tesis", "tesis"],
  ];
  const hoyTxt = new Date().toLocaleDateString("es-MX", { weekday: "long", day: "numeric", month: "long" });
  const hoy = hoyTxt.charAt(0).toUpperCase() + hoyTxt.slice(1);

  return (
    <Shell>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-3xl font-extrabold text-marino">{saludo()}{nombre ? `, ${nombre}` : ""}</h1>
        <p className="text-sm text-slate-500">{hoy}</p>
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

      {r?.aviso && <Link href={r.aviso.href} className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-amber-300 bg-amber-50 px-5 py-3 text-amber-900 hover:bg-amber-100">
        <b>{r.aviso.texto}</b><span className="font-semibold">Ver agenda →</span></Link>}

      {r && !pasosOcultos && siguiente && <div className="mt-4 flex flex-wrap items-center gap-3 rounded-2xl border border-turquesa/30 bg-turquesa-50 px-4 py-2.5 text-sm text-marino" aria-label="Primeros pasos">
        <span className="font-semibold">Primeros pasos: {hechos} de {PASOS.length}</span>
        <span className="h-1.5 w-24 overflow-hidden rounded-full bg-white" aria-hidden><span className="block h-full bg-turquesa" style={{ width: `${(hechos / PASOS.length) * 100}%` }} /></span>
        <Link href={siguiente.href} className="font-semibold text-turquesa-700 underline">Siguiente: {siguiente.texto}</Link>
        <button className="ml-auto text-xs text-slate-500 underline" onClick={ocultarPasos}>Ya no mostrar</button>
      </div>}

      {r && r.numeros.length > 0 && <div className={`mt-5 grid gap-3 sm:grid-cols-2 ${r.numeros.length >= 4 ? "lg:grid-cols-4" : r.numeros.length === 3 ? "lg:grid-cols-3" : ""}`}>
        {r.numeros.map((n) => (
          <Link key={n.clave} href={n.href} className="tarjeta p-4 transition hover:border-turquesa hover:shadow-sm">
            <span className="block text-sm text-slate-500">{n.etiqueta}</span>
            <span className="mt-1 block text-3xl font-extrabold text-marino">{n.valor}</span></Link>))}
      </div>}

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        {activos.includes("agenda") ? <section className="tarjeta p-5" aria-label="Lo de hoy">
          <h2 className="font-bold text-marino">Lo de hoy</h2>
          {r && r.hoy.length > 0 ? <ul className="mt-2 divide-y divide-crema-200">{r.hoy.map((x) => (
            <li key={x.id}><Link href={x.href} className="flex items-center justify-between gap-3 py-2.5 text-sm hover:bg-crema/40">
              <span className="min-w-0"><span className="mr-2 inline-block w-20 capitalize">{cuando(x)}</span><span className="text-slate-800">{x.titulo}</span></span>
              {x.asunto && <span className="truncate text-xs text-slate-500">{x.asunto}</span>}</Link></li>))}</ul>
            : <p className="mt-2 text-sm text-slate-500">{r ? "Nada pendiente para esta semana." : "Cargando…"}</p>}
          <Link href="/agenda" className="mt-2 inline-block text-sm font-semibold text-turquesa-700 underline">Ver toda la agenda</Link>
        </section> : <section className="tarjeta p-5"><h2 className="font-bold text-marino">Tu despacho</h2>
          <p className="mt-1 text-sm text-slate-600">Empieza por lo que más usas: abajo están tus módulos y aquí a un lado lo más rápido.</p></section>}
        <section aria-label="Accesos rápidos">
          <h2 className="font-bold text-marino">Accesos rápidos</h2>
          <div className="mt-2 grid gap-2">{accesos.map(([t, href, ic]) => (
            <Link key={href} href={href} className="flex items-center gap-3 rounded-xl border border-crema-300 bg-white px-4 py-3 text-sm font-semibold text-marino transition hover:border-turquesa">
              <span className="text-turquesa-700"><Icono nombre={ic} /></span>{t}</Link>))}</div>
        </section>
      </div>

      <section className="mt-6" aria-label="Mis módulos">
        <div className="flex items-baseline justify-between"><h2 className="font-bold text-marino">Mis módulos</h2>
          {sesion?.usuario.rol === "administrador" && <Link href="/organizacion" className="text-sm font-semibold text-turquesa-700 underline">Agregar módulos</Link>}</div>
        <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">{mios.map((s) => (
          <Link key={s.clave} href={s.href} title={s.para} className="flex flex-col items-center gap-1.5 rounded-xl border border-crema-300 bg-white px-2 py-3 text-center text-xs font-semibold text-marino transition hover:border-turquesa">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-turquesa-50 text-turquesa-700"><Icono nombre={s.icono} /></span>{s.nombre}</Link>))}</div>
      </section>
      <p className="mt-6 text-sm text-slate-500">¿Para qué sirve cada módulo? Cada pantalla tiene su botón «¿Cómo se usa?» y en <Link href="/ayuda" className="font-semibold text-turquesa-700 underline">Ayuda y manuales</Link> están todas las guías.</p>
    </Shell>
  );
}
