"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Avisos, Desglose, Resumen } from "@/components/liquidaciones";
import { Aviso } from "@/components/ui";
import { api, mxn } from "@/lib/api";

/** Hoja de cálculo para imprimir o guardar como PDF (para el expediente, el cliente o la audiencia de conciliación). */
export default function Imprimir() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<any>(null);
  const [logo, setLogo] = useState<string | null>(null);
  const [notas, setNotas] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get(`/liquidaciones/${id}`).then(async (x) => {
      setC(x);
      if (x.despacho.tiene_logo) try { setLogo(URL.createObjectURL((await api.blob("/organizacion/logo")).blob)); } catch {}
    }).catch((e) => setError(e.message));
  }, [id]);
  if (!c) return <div className="p-8"><Aviso>{error}</Aviso></div>;
  const r = c.resultado;
  const d = c.datos;
  const f = (iso?: string) => iso ? new Date(iso + "T12:00").toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" }) : "—";
  return (
    <div className="min-h-screen bg-crema/60 py-8 print:bg-white print:py-0">
      <div className="mx-auto mb-4 flex max-w-3xl flex-wrap items-center justify-between gap-2 px-4 print:hidden">
        <button onClick={() => history.back()} className="text-sm font-semibold text-turquesa-700">← Volver</button>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={notas} onChange={(e) => setNotas(e.target.checked)} /> Incluir propuesta y notas internas</label>
          <button className="btn-turquesa" onClick={() => window.print()}>Imprimir o guardar PDF</button></div>
      </div>
      <article className="mx-auto max-w-3xl rounded-2xl bg-white p-10 shadow-sm print:rounded-none print:p-0 print:shadow-none">
        <header className="flex items-start justify-between gap-6 border-b border-slate-200 pb-5">
          <div className="flex items-center gap-3">{logo && <img src={logo} alt="" className="h-12 w-auto" />}<p className="text-lg font-extrabold text-marino">{c.despacho.nombre}</p></div>
          <div className="text-right"><p className="text-xs uppercase tracking-widest text-slate-500">Cálculo de prestaciones (LFT)</p>
            <p className="text-sm text-slate-600">{new Date().toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" })}</p></div>
        </header>
        <section className="mt-5 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <p><span className="text-slate-500">Persona trabajadora:</span> <b className="text-marino">{c.trabajador}</b></p>
          {c.patron && <p><span className="text-slate-500">Patrón:</span> <b className="text-marino">{c.patron}</b></p>}
          {c.asunto && <p><span className="text-slate-500">Asunto:</span> {c.asunto.titulo}{c.asunto.numero ? ` (${c.asunto.numero})` : ""}</p>}
          <p><span className="text-slate-500">Causa:</span> {r.causa_nombre}</p>
          <p><span className="text-slate-500">Ingreso:</span> {f(d.fecha_ingreso)}</p>
          <p><span className="text-slate-500">Baja:</span> {f(d.fecha_baja)}</p>
        </section>
        <div className="mt-4 rounded-xl bg-crema/60 p-4"><Resumen r={r} /></div>
        <div className="mt-5"><Desglose r={r} /></div>
        <div className="mt-5 flex items-baseline justify-between border-t-2 border-marino pt-3">
          <span className="text-sm font-bold uppercase tracking-wider text-marino">Total estimado</span>
          <span className="text-3xl font-black text-marino">{mxn(r.total)}</span></div>
        {notas && (c.propuesta || c.autorizado || c.notas) && <section className="mt-4 rounded-xl border border-crema-300 p-4 text-sm">
          {c.propuesta && <p>Propuesta de convenio: <b>{mxn(c.propuesta)}</b> ({c.propuesta_pct} %)</p>}
          {c.autorizado && <p>Monto autorizado por el cliente: <b>{mxn(c.autorizado)}</b> ({c.autorizado_pct} %)</p>}
          {c.notas && <p className="mt-1 whitespace-pre-line text-slate-600">{c.notas}</p>}</section>}
        <div className="mt-5"><Avisos avisos={r.avisos} /></div>
      </article>
    </div>
  );
}
