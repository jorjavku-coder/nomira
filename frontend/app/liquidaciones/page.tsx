"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { CAUSA_CORTA } from "@/components/liquidaciones";
import { Aviso } from "@/components/ui";
import { api, fecha, mxn } from "@/lib/api";

export default function Liquidaciones() {
  const [r, setR] = useState<any>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const cargar = useCallback(() => api.get(`/liquidaciones?q=${encodeURIComponent(q)}`).then(setR).catch((e) => setError(e.message)), [q]);
  useEffect(() => { const t = setTimeout(cargar, 200); return () => clearTimeout(t); }, [cargar]);
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Ley Federal del Trabajo</p>
          <h1 className="text-3xl font-extrabold text-marino">Liquidaciones</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Finiquito, indemnización, prima de antigüedad, salarios caídos y horas extra, con la operación y el fundamento de cada concepto. Al día con la reforma de vacaciones 2023 y la de 40 horas.</p></div>
        <div className="flex items-center gap-2"><BotonAyuda modulo="liquidaciones" />
          <Link href="/liquidaciones/nuevo" className="btn-turquesa">+ Nuevo cálculo</Link></div>
      </div>
      <Aviso>{error}</Aviso>
      <input className="campo mb-3 max-w-sm" placeholder="Buscar por persona, patrón o título" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar cálculos" />
      {r && (r.calculos.length ? (
        <div className="tarjeta overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-crema-300 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="p-3">Persona trabajadora</th><th className="p-3">Causa</th><th className="p-3">Asunto / cliente</th>
              <th className="p-3 text-right">Total</th><th className="p-3 text-right">Propuesta</th><th className="p-3">Actualizado</th></tr></thead>
            <tbody>{r.calculos.map((c: any) => (
              <tr key={c.id} className="border-b border-crema-200 last:border-0 hover:bg-crema/50">
                <td className="p-3"><Link href={`/liquidaciones/${c.id}`} className="font-semibold text-marino hover:underline">{c.trabajador}</Link>
                  {c.patron && <p className="text-xs text-slate-500">vs. {c.patron}</p>}</td>
                <td className="p-3 text-slate-600">{CAUSA_CORTA[c.causa] || c.causa_nombre}</td>
                <td className="p-3 text-xs text-slate-600">{c.asunto ? <Link href={`/agenda/asuntos/${c.asunto.id}`} className="underline">{c.asunto.titulo}</Link> : null}
                  {c.cliente && <p>{c.cliente.nombre}</p>}{!c.asunto && !c.cliente && "—"}</td>
                <td className="p-3 text-right font-mono font-semibold text-marino">{mxn(c.total)}</td>
                <td className="p-3 text-right font-mono text-slate-600">{c.propuesta ? <>{mxn(c.propuesta)}<span className="block text-xs text-slate-400">{c.propuesta_pct} %</span></> : "—"}</td>
                <td className="p-3 text-xs text-slate-500">{fecha(c.actualizado_en)}</td>
              </tr>))}</tbody>
          </table>
        </div>
      ) : <div className="tarjeta p-10 text-center"><p className="font-semibold text-marino">{q ? "No hay cálculos con ese dato." : "Aún no hay cálculos guardados."}</p>
        {!q && <p className="mt-1 text-sm text-slate-500">Con «+ Nuevo cálculo» capture fechas, salario y causa; el resultado se ve al momento.</p>}</div>)}
    </Shell>
  );
}
