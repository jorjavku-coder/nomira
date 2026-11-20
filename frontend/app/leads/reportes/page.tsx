"use client";
import { useEffect, useState } from "react";
import { LeadsShell } from "@/components/leads";
import { Aviso } from "@/components/ui";
import { api, mxn } from "@/lib/api";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v}%`);
const horas = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v < 1 ? "menos de 1 h" : v < 48 ? `${v} h` : `${Math.round(v / 24)} días`);

/** Resultados sencillos: de dónde llegan, cuántos se atienden y cuántos contratan. */
export default function Reportes() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const q = new URLSearchParams(Object.entries({ desde, hasta }).filter(([, v]) => v) as [string, string][]).toString();
    api.get(`/leads/reportes?${q}`).then(setR).catch((e) => setError(e.message));
  }, [desde, hasta]);
  const Tabla = ({ filas, primera, extra }: any) => (
    <div className="tarjeta overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr><th className="px-4 py-2">{primera}</th><th className="px-3 py-2 text-right">Prospectos</th><th className="px-3 py-2 text-right">Consultas agendadas</th>
            <th className="px-3 py-2 text-right">Consultas realizadas</th><th className="px-3 py-2 text-right">Contratados</th><th className="px-3 py-2 text-right">Conversión</th>
            <th className="px-3 py-2 text-right">1.ª respuesta</th>{extra && <><th className="px-3 py-2 text-right">Inversión</th><th className="px-3 py-2 text-right">Costo por cliente</th></>}</tr>
        </thead>
        <tbody className="divide-y divide-crema-200">
          {filas.length === 0 && <tr><td colSpan={9} className="px-4 py-4 text-center text-slate-400">Sin datos en este periodo.</td></tr>}
          {filas.map((f: any, i: number) => (
            <tr key={i}><td className="px-4 py-2 font-semibold text-marino">{f.canal_texto || f.nombre}</td><td className="px-3 py-2 text-right">{f.recibidos}</td>
              <td className="px-3 py-2 text-right">{f.consultas_agendadas}</td><td className="px-3 py-2 text-right">{f.consultas_realizadas}</td>
              <td className="px-3 py-2 text-right font-semibold">{f.contratados}</td><td className="px-3 py-2 text-right">{pct(f.conversion)}</td>
              <td className="px-3 py-2 text-right">{horas(f.primera_respuesta_horas)}</td>
              {extra && <><td className="px-3 py-2 text-right">{f.inversion ? mxn(f.inversion) : "—"}</td><td className="px-3 py-2 text-right">{f.costo_por_cliente ? mxn(f.costo_por_cliente) : "—"}</td></>}</tr>))}
        </tbody>
      </table>
    </div>
  );
  return (
    <LeadsShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Resultados</h1>
          <p className="text-sm text-slate-500">Prospectos registrados en el periodo, según su canal y campaña de origen.</p></div>
        <div className="flex flex-wrap items-end gap-2 text-sm">
          <label><span className="etiqueta">Desde</span><input className="campo" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
          <label><span className="etiqueta">Hasta</span><input className="campo" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
        </div>
      </div>
      <Aviso>{error}</Aviso>
      {!r && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {r && (
        <div className="space-y-6">
          {r.aviso_origen && <Aviso tipo="alerta">{r.aviso_origen}</Aviso>}
          <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {[["Prospectos", r.total.recibidos], ["Consultas realizadas", r.total.consultas_realizadas], ["Contratados", r.total.contratados],
              ["Conversión", pct(r.total.conversion)], ["Primera respuesta (promedio)", horas(r.total.primera_respuesta_horas)]].map(([t, v]) => (
              <div key={t as string} className="tarjeta p-4"><p className="text-xs uppercase tracking-wide text-slate-500">{t}</p><p className="mt-1 text-2xl font-extrabold text-marino">{v}</p></div>))}
          </section>
          <section><h2 className="mb-2 font-semibold text-marino">Por canal</h2><Tabla filas={r.por_canal} primera="Canal" /></section>
          <section><h2 className="mb-2 font-semibold text-marino">Por campaña</h2><Tabla filas={r.por_campana} primera="Campaña" extra />
            <p className="mt-1 text-xs text-slate-500">El costo por cliente solo aparece si registró la inversión de la campaña.</p></section>
          <section className="tarjeta p-5">
            <h2 className="mb-2 font-semibold text-marino">Motivos por los que no se contrató</h2>
            {r.motivos_perdida.length === 0 ? <p className="text-sm text-slate-400">Sin registros.</p> : (
              <ul className="space-y-1.5 text-sm">{r.motivos_perdida.map((x: any) => {
                const max = r.motivos_perdida[0].total;
                return <li key={x.motivo} className="flex items-center gap-3"><span className="w-48 shrink-0 truncate">{x.motivo}</span>
                  <span className="h-2.5 rounded-full bg-turquesa/70" style={{ width: `${Math.max(6, (x.total / max) * 60)}%` }} aria-hidden /><b>{x.total}</b></li>;
              })}</ul>)}
          </section>
          {r.sin_origen > 0 && <p className="text-xs text-slate-500">{r.sin_origen} prospecto(s) sin canal ni campaña identificados («Otro»).</p>}
          <p className="text-xs text-slate-500">Estos números reflejan lo registrado en Nomira por su equipo y por las fuentes conectadas. Nomira no genera clientes por sí sola.</p>
        </div>)}
    </LeadsShell>
  );
}
