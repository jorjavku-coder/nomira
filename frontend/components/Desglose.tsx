"use client";
import { useMemo, useState } from "react";
import { mxn } from "@/lib/api";

type Filtro = "todas" | "pendientes" | "faltantes";

/** Desglose por quincena con el mismo formato de la hoja de cálculo que se llenaba a mano. */
export default function Desglose({ res, validado, onAbrir }: { res: any; validado: boolean; onAbrir: (quincena: string) => void }) {
  const [filtro, setFiltro] = useState<Filtro>("todas");
  const cuenta = useMemo(() => ({
    todas: res.quincenas.length,
    pendientes: res.quincenas.filter((q: any) => q.provisional || q.estado === "pendiente").length,
    faltantes: res.quincenas.filter((q: any) => q.estado === "faltante").length,
  }), [res]);
  const visibles = res.quincenas.filter((q: any) => filtro === "todas" || (filtro === "faltantes" ? q.estado === "faltante" : q.provisional || q.estado === "pendiente"));
  const porAnio: Record<string, any[]> = {};
  for (const q of visibles) (porAnio[q.inicio.slice(0, 4)] ||= []).push(q);
  const varias = res.plazas.length > 1;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5" role="group" aria-label="Filtrar quincenas">
          {([["todas", "Todas"], ["pendientes", "Con pendientes"], ["faltantes", "Faltantes"]] as [Filtro, string][]).map(([k, t]) => (
            <button key={k} onClick={() => setFiltro(k)} aria-pressed={filtro === k}
              className={`rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${filtro === k ? "bg-marino text-white" : "border border-crema-300 bg-white text-marino hover:bg-marino-50"}`}>
              {t} <span className={filtro === k ? "text-white/70" : "text-slate-400"}>{cuenta[k]}</span>
            </button>
          ))}
        </div>
        <p className="text-sm text-slate-500">Solo se suman las prestaciones del catálogo «{res.catalogo.nombre}» v{res.catalogo.version}.</p>
      </div>

      {visibles.length === 0 && <div className="tarjeta p-8 text-center text-slate-500">No hay quincenas en este filtro.</div>}

      {Object.entries(porAnio).map(([anio, qs]) => (
        <section key={anio}>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wider text-slate-400">{anio}</h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {qs.map((q: any) => {
              const faltante = q.estado === "faltante";
              const pendiente = q.estado === "pendiente" || q.provisional;
              const bloques = res.consolidado || q.plazas.length <= 1
                ? [{ plaza: null, conceptos: q.plazas.flatMap((p: any) => p.conceptos), total: q.total }]
                : q.plazas.map((p: any) => ({ plaza: p.plaza, conceptos: p.conceptos, total: p.total }));
              return (
                <button key={q.quincena} onClick={() => onAbrir(q.quincena)} title="Ver detalle y comprobante"
                  className={`tarjeta flex flex-col p-4 text-left transition hover:-translate-y-0.5 hover:border-turquesa hover:shadow-flotante/30 ${faltante ? "border-red-200 bg-red-50/60" : pendiente && !validado ? "border-amber-300" : ""}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-marca text-base font-extrabold text-marino">Quincena {q.numero}</div>
                      <div className="text-xs text-slate-500">{q.periodo_texto}</div>
                    </div>
                    <span className="flex shrink-0 flex-col items-end gap-1">
                      {faltante && <span className="rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-bold text-red-800">Faltante</span>}
                      {!faltante && pendiente && !validado && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-800">Por revisar</span>}
                      {q.ia === "coincide" && <span className="rounded-full bg-turquesa-50 px-2 py-0.5 text-[11px] font-bold text-turquesa-700" title="La segunda lectura con IA coincide">IA ✓</span>}
                      {q.ia === "discrepancia" && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-800" title="La IA leyó algo distinto">IA ≠</span>}
                    </span>
                  </div>
                  {faltante ? (
                    <p className="mt-3 text-sm text-red-800">Sin comprobante. No se le asigna importe.</p>
                  ) : (
                    bloques.map((b: any) => (
                      <div key={b.plaza || "u"} className="mt-3">
                        {b.plaza && <div className="mb-1 font-mono text-[11px] text-slate-500">Plaza {b.plaza}</div>}
                        <dl className="space-y-1 text-sm">
                          {b.conceptos.map((c: any) => (
                            <div key={c.fila_id} className="flex items-baseline justify-between gap-3">
                              <dt className="min-w-0 truncate text-slate-700" title={`${c.clave} · ${c.concepto_catalogo}`}>
                                <span className="lowercase first-letter:uppercase inline-block">{c.concepto_catalogo}</span>
                              </dt>
                              <dd className={`shrink-0 tabular-nums ${c.negativo ? "text-red-700" : ""}`}>{mxn(c.importe)}</dd>
                            </div>
                          ))}
                          {b.conceptos.length === 0 && <div className="text-slate-500">{q.estado === "pendiente" ? "Recibo pendiente de revisión." : "Ninguna prestación autorizada."}</div>}
                        </dl>
                        <div className="mt-2 flex items-baseline justify-between border-t border-crema-300 pt-2 font-bold text-marino">
                          <span>TOTAL{varias && b.plaza ? "" : ""}</span>
                          <span className="tabular-nums">{q.estado === "pendiente" ? "—" : mxn(b.total)}</span>
                        </div>
                      </div>
                    ))
                  )}
                </button>
              );
            })}
          </div>
        </section>
      ))}

      <div className="tarjeta flex flex-wrap items-center justify-between gap-3 bg-marino-700 p-5 text-white">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-white/60">Total de {res.resumen.quincenas_con_recibo} quincena(s) con comprobante{!validado && " · provisional"}</div>
          {!res.consolidado && <div className="mt-1 text-sm text-white/70">{res.plazas.map((p: any) => `Plaza ${p.plaza}: ${mxn(p.total)}`).join(" · ")}</div>}
        </div>
        <div className="font-marca text-3xl font-extrabold text-turquesa-brillante">{res.consolidado ? mxn(res.total_expediente) : "Por plaza"}</div>
      </div>
    </div>
  );
}
