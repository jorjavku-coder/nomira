"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AgendaShell, FormEvento, ListaEventos, useCatalogosAgenda } from "@/components/agenda";
import { Aviso } from "@/components/ui";
import { api, fecha } from "@/lib/api";

/** Vista diaria: lo vencido, lo de hoy, lo de la semana y lo que falta validar. */
export default function Hoy() {
  const cat = useCatalogosAgenda();
  const [mios, setMios] = useState(false);
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState<string | null>(null);
  const cargar = useCallback(() => api.get(`/agenda/hoy?solo_mios=${mios}`).then((x) => { setR(x); window.dispatchEvent(new Event("nomira:agenda")); }).catch((e) => setError(e.message)), [mios]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (r?.avisos?.length) api.post("/agenda/avisos/leidos").catch(() => {}); }, [r]);
  const tarjetas = r ? [["Vencidos sin cumplir", r.vencidos.length, "text-red-700"], ["Hoy", r.hoy.length, "text-amber-700"],
    ["Próximos 7 días", r.proximos.length, "text-marino"], ["Plazos por validar", r.por_validar.length, "text-violet-700"]] : [];
  return (
    <AgendaShell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Agenda de hoy</h1>
          <p className="mt-1 text-sm text-slate-500">{r ? fecha(r.fecha) : ""} · {r ? `${r.cumplidos_hoy} cumplido(s) hoy` : ""}</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-full border border-crema-300 p-0.5 text-sm" role="group" aria-label="Qué ver">
            <button className={`rounded-full px-3 py-1 ${!mios ? "bg-marino text-white" : "text-slate-600"}`} onClick={() => setMios(false)}>Todo el despacho</button>
            <button className={`rounded-full px-3 py-1 ${mios ? "bg-marino text-white" : "text-slate-600"}`} onClick={() => setMios(true)}>Solo lo mío</button>
          </div>
          {cat?.puede_editar && <>
            <button className="btn-sec" onClick={() => setNuevo("audiencia")}>+ Audiencia</button>
            <button className="btn-turquesa" onClick={() => setNuevo("plazo")}>+ Plazo</button></>}
        </div>
      </div>
      <Aviso>{error}</Aviso>
      {r && <>
        {r.estrados_sin_ver > 0 && <Link href="/agenda/estrados" className="mb-4 flex items-center justify-between gap-3 rounded-2xl border-2 border-turquesa bg-turquesa-50 p-4 text-marino">
          <span><b>📜 {r.estrados_sin_ver} publicación(es) nueva(s) en estrados</b> de expedientes que vigila. Revíselas para no perder el plazo.</span>
          <span className="whitespace-nowrap font-semibold text-turquesa-700">Ver →</span></Link>}
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {tarjetas.map(([t, n, c]: any) => <div key={t} className="tarjeta p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t}</p>
            <p className={`mt-1 text-3xl font-extrabold ${n ? c : "text-slate-300"}`}>{n}</p></div>)}
        </div>
        <div className="grid gap-5 xl:grid-cols-2">
          <div className="space-y-5">
            {r.vencidos.length > 0 && <ListaEventos titulo="Vencidos sin marcar como cumplidos" tono="border-2 border-red-200" eventos={r.vencidos} vacio="" onCambio={cargar} />}
            <ListaEventos titulo="Hoy" eventos={r.hoy} vacio="Nada vence hoy." onCambio={cargar} />
            <ListaEventos titulo="Próximos 7 días" eventos={r.proximos} vacio="Sin pendientes esta semana." onCambio={cargar} />
          </div>
          <div className="space-y-5">
            <ListaEventos titulo="Plazos por validar" eventos={r.por_validar} vacio="Todos los plazos están validados." onCambio={cargar} />
            {r.sin_responsable.length > 0 && <ListaEventos titulo="Sin responsable" eventos={r.sin_responsable} vacio="" onCambio={cargar} />}
          </div>
        </div>
      </>}
      {nuevo && <FormEvento inicial={{ tipo: nuevo }} onCerrar={() => setNuevo(null)} onGuardado={() => { setNuevo(null); cargar(); }} />}
    </AgendaShell>
  );
}
