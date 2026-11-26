"use client";
import { useState } from "react";
/** Nomira Connect: piezas compartidas entre el panel del despacho y el portal del cliente. */

/** Colores del seguimiento (los mismos en el panel y en el portal). */
export const ESTADO_ETAPA: Record<string, { texto: string; punto: string; chip: string; linea: string }> = {
  completada: { texto: "Completada", punto: "bg-emerald-500 text-white", chip: "bg-emerald-50 text-emerald-800 border-emerald-200", linea: "bg-emerald-400" },
  actual: { texto: "Etapa actual", punto: "bg-turquesa text-marino-900 ring-4 ring-turquesa/25", chip: "bg-turquesa-50 text-turquesa-700 border-turquesa/40", linea: "bg-slate-200" },
  pendiente: { texto: "Próxima", punto: "bg-slate-200 text-slate-500", chip: "bg-slate-50 text-slate-500 border-slate-200", linea: "bg-slate-200" },
  atencion: { texto: "Requiere su atención", punto: "bg-amber-400 text-marino-900 ring-4 ring-amber-200", chip: "bg-amber-50 text-amber-800 border-amber-200", linea: "bg-slate-200" },
  incidencia: { texto: "Incidencia", punto: "bg-red-500 text-white ring-4 ring-red-100", chip: "bg-red-50 text-red-700 border-red-200", linea: "bg-slate-200" },
  suspendida: { texto: "Suspendida temporalmente", punto: "bg-violet-500 text-white ring-4 ring-violet-100", chip: "bg-violet-50 text-violet-800 border-violet-200", linea: "bg-slate-200" },
  omitida: { texto: "No aplica", punto: "bg-slate-100 text-slate-300", chip: "bg-slate-50 text-slate-400 border-slate-200", linea: "bg-slate-200" },
};

export const fechaCorta = (iso?: string | null) =>
  iso ? new Date(iso.length === 10 ? iso + "T12:00" : iso).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" }) : "";
export const fechaLarga = (iso?: string | null) =>
  iso ? new Date(iso.length === 10 ? iso + "T12:00" : iso).toLocaleDateString("es-MX", { weekday: "long", day: "numeric", month: "long" }) : "";
export const fechaHora = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString("es-MX", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

function Icono({ estado, n }: { estado: string; n: number }) {
  if (estado === "completada") return <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="3"><path d="m5 12 5 5 9-10" /></svg>;
  if (estado === "atencion") return <span className="text-sm font-black">!</span>;
  if (estado === "incidencia") return <span className="text-sm font-black">×</span>;
  if (estado === "suspendida") return <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>;
  return <span className="text-xs font-bold">{n}</span>;
}

/** Línea de tiempo vertical estilo «rastreo de pedido». `grande` = modo accesible (letra más grande). */
export function LineaTiempo({ etapas, grande = false, onElegir, elegida }: {
  etapas: any[]; grande?: boolean; onElegir?: (e: any) => void; elegida?: number | null;
}) {
  return (
    <ol className="relative">
      {etapas.map((e, i) => {
        const est = ESTADO_ETAPA[e.estado] || ESTADO_ETAPA.pendiente;
        const ultima = i === etapas.length - 1;
        const siguienteHecha = etapas[i + 1] && ["completada", "actual", "atencion", "incidencia", "suspendida"].includes(etapas[i + 1].estado);
        const destacada = ["actual", "atencion", "incidencia", "suspendida"].includes(e.estado);
        const Contenido = (
          <>
            <div className="relative flex flex-col items-center">
              <span className={`relative z-10 flex ${grande ? "h-10 w-10" : "h-8 w-8"} shrink-0 items-center justify-center rounded-full transition ${est.punto}`}>
                <Icono estado={e.estado} n={i + 1} />
                {e.estado === "actual" && <span className="absolute inset-0 animate-ping rounded-full bg-turquesa/40" aria-hidden />}
              </span>
              {!ultima && <span className={`mt-1 w-0.5 flex-1 rounded-full ${e.estado === "completada" && siguienteHecha ? "bg-emerald-400" : "bg-slate-200"}`} aria-hidden />}
            </div>
            <div className={`min-w-0 flex-1 ${ultima ? "" : "pb-6"}`}>
              <div className={`rounded-2xl ${destacada ? `border p-4 ${est.chip}` : "pt-1"}`}>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className={`font-bold ${grande ? "text-lg" : "text-[15px]"} ${e.estado === "pendiente" || e.estado === "omitida" ? "text-slate-500" : "text-marino"}`}>{e.nombre}</span>
                  {destacada && <span className={`rounded-full border px-2 py-0.5 text-[11px] font-bold ${est.chip}`}>{est.texto}</span>}
                  {e.opcional && e.estado === "pendiente" && <span className="text-[11px] text-slate-400">si aplica</span>}
                </div>
                {e.fecha && !["pendiente", "omitida"].includes(e.estado) && <p className={`${grande ? "text-sm" : "text-xs"} mt-0.5 text-slate-500`}>{e.estado === "completada" ? "Completada el " : "Desde el "}{fechaCorta(e.fecha)}</p>}
                {(destacada || grande) && e.explicacion && <p className={`${grande ? "text-base" : "text-sm"} mt-1.5 leading-relaxed text-slate-600`}>{e.explicacion}</p>}
                {e.nota && <p className={`${grande ? "text-base" : "text-sm"} mt-2 rounded-xl bg-white/80 p-2.5 text-marino`}>💬 {e.nota}</p>}
              </div>
            </div>
          </>
        );
        return (
          <li key={e.id ?? i} className="flex gap-3">
            {onElegir ? (
              <button type="button" onClick={() => onElegir(e)} className={`flex w-full gap-3 rounded-2xl text-left transition hover:bg-crema/60 ${elegida === e.id ? "bg-crema/80 ring-2 ring-turquesa/50" : ""}`}>{Contenido}</button>
            ) : Contenido}
          </li>
        );
      })}
    </ol>
  );
}

/** Editor de etapas: reordenar (arrastrando o con flechas), agregar, quitar, explicación y «si aplica». */
export function EditorEtapas({ etapas, setEtapas }: { etapas: any[]; setEtapas: (e: any[]) => void }) {
  const [arrastra, setArrastra] = useState<number | null>(null);
  const mover = (i: number, d: number) => { const j = i + d; if (j < 0 || j >= etapas.length) return; const n = [...etapas]; [n[i], n[j]] = [n[j], n[i]]; setEtapas(n); };
  const cambiar = (i: number, k: string, v: any) => setEtapas(etapas.map((e, x) => x === i ? { ...e, [k]: v } : e));
  return (
    <div className="space-y-2">
      {etapas.map((e, i) => (
        <div key={e.id ?? `n${i}`} draggable onDragStart={() => setArrastra(i)} onDragOver={(ev) => ev.preventDefault()}
          onDrop={() => { if (arrastra === null || arrastra === i) return; const n = [...etapas]; const [x] = n.splice(arrastra, 1); n.splice(i, 0, x); setEtapas(n); setArrastra(null); }}
          className={`rounded-xl border bg-white p-3 ${arrastra === i ? "border-turquesa opacity-60" : "border-crema-300"}`}>
          <div className="flex items-center gap-2">
            <span className="cursor-grab select-none text-slate-400" title="Arrastre para reordenar" aria-hidden>⋮⋮</span>
            <span className="w-6 text-center text-xs font-bold text-slate-400">{i + 1}</span>
            <input className="campo flex-1 py-1.5" value={e.nombre} placeholder="Nombre de la etapa" onChange={(x) => cambiar(i, "nombre", x.target.value)} aria-label={`Etapa ${i + 1}`} />
            <button type="button" className="px-1 text-slate-500 hover:text-marino" onClick={() => mover(i, -1)} aria-label="Subir">↑</button>
            <button type="button" className="px-1 text-slate-500 hover:text-marino" onClick={() => mover(i, 1)} aria-label="Bajar">↓</button>
            <button type="button" className="px-1 text-red-500 hover:text-red-700" onClick={() => setEtapas(etapas.filter((_, x) => x !== i))} aria-label="Quitar etapa">✕</button>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 pl-10">
            <input className="campo flex-1 py-1 text-xs" value={e.explicacion || ""} placeholder="Explicación para el cliente, en palabras sencillas" onChange={(x) => cambiar(i, "explicacion", x.target.value)} />
            <label className="flex items-center gap-1 text-xs text-slate-600"><input type="checkbox" checked={!!e.opcional} onChange={(x) => cambiar(i, "opcional", x.target.checked)} /> Si aplica</label>
          </div>
        </div>))}
      <button type="button" className="btn-sec w-full text-sm" onClick={() => setEtapas([...etapas, { nombre: "", explicacion: "", opcional: false }])}>+ Agregar etapa</button>
    </div>
  );
}

