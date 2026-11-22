"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { MANUALES } from "@/lib/ayuda";

/** Centro de ayuda: un manual por módulo contratado, con búsqueda. */
export default function Ayuda() {
  const sesion = useSesion();
  const [q, setQ] = useState("");
  const activos: string[] = sesion?.modulos ?? [];
  const lista = MANUALES.filter((m) => !m.modulo || activos.includes(m.modulo));
  const resultados = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (t.length < 3) return [];
    const r: { m: string; titulo: string; texto: string; ancla: string }[] = [];
    for (const m of lista) {
      m.pasos.forEach((p, i) => { if ((p.titulo + " " + p.texto).toLowerCase().includes(t)) r.push({ m: m.clave, titulo: `${m.titulo} · ${p.titulo}`, texto: p.texto, ancla: `paso-${i + 1}` }); });
      m.preguntas.forEach((p, i) => { if ((p.p + " " + p.r).toLowerCase().includes(t)) r.push({ m: m.clave, titulo: `${m.titulo} · ${p.p}`, texto: p.r, ancla: `pregunta-${i + 1}` }); });
    }
    return r.slice(0, 12);
  }, [q, lista]);
  return (
    <Shell>
      <h1 className="text-3xl font-extrabold text-marino">Ayuda y manuales</h1>
      <p className="mt-1 text-sm text-slate-500">Un manual paso a paso por cada módulo de su despacho, con capturas de pantalla.</p>
      <input className="campo mt-5 max-w-xl" placeholder="Buscar en los manuales, p. ej. «validar», «catálogo», «WhatsApp»…" aria-label="Buscar en los manuales" value={q} onChange={(e) => setQ(e.target.value)} />
      {q.trim().length >= 3 && <section className="tarjeta mt-3 max-w-3xl divide-y divide-crema-200">
        {resultados.length ? resultados.map((r, i) => (
          <Link key={i} href={`/ayuda/${r.m}#${r.ancla}`} className="block px-4 py-3 hover:bg-crema/40">
            <p className="font-semibold text-marino">{r.titulo}</p><p className="line-clamp-2 text-sm text-slate-600">{r.texto}</p></Link>))
          : <p className="px-4 py-3 text-sm text-slate-500">Sin resultados. Pruebe con otra palabra o escriba a <Link className="font-semibold text-turquesa-700 underline" href="/soporte">Soporte</Link>.</p>}
      </section>}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {lista.map((m) => (
          <Link key={m.clave} href={`/ayuda/${m.clave}`} className="tarjeta group flex flex-col p-5 transition hover:-translate-y-0.5 hover:shadow-flotante">
            <span className="text-xs font-semibold uppercase tracking-wider text-turquesa-700">{m.clave === "primeros-pasos" ? "Empiece aquí" : "Manual del módulo"}</span>
            <h2 className="mt-1 text-lg font-bold text-marino">{m.titulo}</h2>
            <p className="mt-1 flex-1 text-sm text-slate-600">{m.resumen}</p>
            <span className="mt-3 text-sm font-semibold text-turquesa-700 group-hover:underline">{m.pasos.length} pasos · Leer →</span>
          </Link>))}
      </div>
      <p className="mt-8 text-sm text-slate-500">¿No encuentra lo que busca? Escríbanos en <Link className="font-semibold text-turquesa-700 underline" href="/soporte">Soporte</Link>.</p>
    </Shell>
  );
}
