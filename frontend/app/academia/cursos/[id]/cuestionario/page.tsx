"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AcademiaShell } from "@/components/academia";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

export default function Cuestionario() {
  const { id } = useParams<{ id: string }>();
  const [q, setQ] = useState<any>(null);
  const [resp, setResp] = useState<Record<string, number>>({});
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const cargar = () => api.get(`/academia/cursos/${id}/cuestionario`).then(setQ).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { setR(await api.post(`/academia/cursos/${id}/cuestionario`, { respuestas: resp })); window.scrollTo({ top: 0, behavior: "smooth" }); } catch (x: any) { setError(x.message); }
  }
  if (!q) return <AcademiaShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</AcademiaShell>;
  const det: Record<number, any> = Object.fromEntries((r?.detalle || []).map((d: any) => [d.id, d]));
  return (
    <AcademiaShell>
      <div className="mx-auto max-w-3xl">
        <Link href={`/academia/cursos/${id}`} className="text-sm font-semibold text-turquesa-700 hover:underline">← {q.curso}</Link>
        <h1 className="mt-2 text-3xl font-extrabold text-marino">Cuestionario final</h1>
        <p className="mt-1 text-sm text-slate-500">{q.preguntas.length} preguntas{q.calificacion_minima ? ` · Calificación mínima para aprobar: ${q.calificacion_minima}` : ""}. Puede intentarlo las veces que necesite.</p>
        {!q.disponible && <div className="mt-3"><Aviso tipo="alerta">Complete todas las lecciones antes de responder el cuestionario.</Aviso></div>}
        {r && (
          <section className={`tarjeta mt-4 p-5 ${r.aprobado ? "border-emerald-300 bg-emerald-50" : "border-amber-300 bg-amber-50"}`}>
            <h2 className="text-xl font-bold text-marino">Obtuvo {r.calificacion} de 100 ({r.aciertos} de {r.total})</h2>
            <p className="text-sm">{r.aprobado ? (r.completado ? "¡Aprobado! Completó el curso." : "¡Aprobado!") : `Necesita ${r.minima} para aprobar. Revise las explicaciones e inténtelo de nuevo.`}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {r.completado && <button className="btn-turquesa" onClick={() => api.descargar(`/academia/constancias/${r.avance_id}`, "constancia.pdf")}>Descargar constancia</button>}
              {!r.aprobado && <button className="btn-sec" onClick={() => { setR(null); setResp({}); cargar(); }}>Intentar de nuevo</button>}
              <Link className="btn-sec" href="/academia">Mi aprendizaje</Link>
            </div>
          </section>)}
        <form className="mt-5 space-y-4" onSubmit={enviar}>
          {q.preguntas.map((p: any, n: number) => (
            <fieldset key={p.id} className="tarjeta p-5">
              <legend className="sr-only">Pregunta {n + 1}</legend>
              <p className="font-semibold text-marino">{n + 1}. {p.texto}</p>
              <div className="mt-2 space-y-2">
                {p.opciones.map((o: string, i: number) => {
                  const d = det[p.id];
                  const marca = d ? (i === d.correcta ? "border-emerald-400 bg-emerald-50" : i === d.respuesta ? "border-red-300 bg-red-50" : "border-crema-300") : resp[p.id] === i ? "border-turquesa bg-turquesa-50" : "border-crema-300";
                  return <label key={i} className={`flex cursor-pointer items-center gap-2 rounded-xl border p-3 text-sm ${marca}`}>
                    <input type="radio" name={`p${p.id}`} className="accent-turquesa" required disabled={!!r} checked={resp[p.id] === i} onChange={() => setResp({ ...resp, [p.id]: i })} />{o}</label>;
                })}
              </div>
              {det[p.id]?.explicacion && <p className="mt-2 text-xs text-slate-600">{det[p.id].explicacion}</p>}
            </fieldset>))}
          <Aviso>{error}</Aviso>
          {!r && <button className="btn-turquesa px-6 py-2.5 text-base" disabled={!q.disponible}>Enviar respuestas</button>}
        </form>
      </div>
    </AcademiaShell>
  );
}
