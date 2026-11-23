"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { cuando, dinero, Etapa, FormOportunidad, useCatalogosVentas, VentasShell } from "@/components/ventas";
import { Aviso } from "@/components/ui";
import { apiP, avisarContadores } from "@/lib/plataforma";

export default function Embudo() {
  const cat = useCatalogosVentas();
  const router = useRouter();
  const [r, setR] = useState<any>(null);
  const [t, setT] = useState<any>(null);
  const [filtro, setFiltro] = useState({ propietario_id: "", campana_id: "", q: "" });
  const [nueva, setNueva] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const cargar = useCallback(() => {
    const p = new URLSearchParams(Object.entries(filtro).filter(([, v]) => v) as any);
    apiP.get(`/ventas/tablero?${p}`).then(setT).catch((e) => setError(e.message));
    apiP.get("/ventas/resumen").then(setR).catch(() => {});
  }, [filtro]);
  useEffect(() => { const x = setTimeout(cargar, 200); return () => clearTimeout(x); }, [cargar]);
  async function mover(o: any, etapa: string) {
    setError("");
    if (etapa === "perdido") return router.push(`/plataforma/ventas/oportunidades/${o.id}?perder=1`);
    try { await apiP.post(`/ventas/oportunidades/${o.id}/etapa`, { etapa }); avisarContadores(); cargar(); } catch (e: any) { setError(e.message); }
  }
  async function importar() {
    try { const x = await apiP.post("/ventas/importar-solicitudes"); setOk(x.nuevas ? `Se agregaron ${x.nuevas} solicitud(es) del sitio.` : "No había solicitudes pendientes de agregar."); cargar(); }
    catch (e: any) { setError(e.message); }
  }
  return (
    <VentasShell acciones={<><button className="btn-sec" onClick={importar}>Traer solicitudes del sitio</button>
      {cat && <button className="btn-turquesa" onClick={() => setNueva(true)}>+ Nueva oportunidad</button>}</>}>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {r && <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Kpi titulo="En el embudo" valor={dinero(r.pipeline)} nota={`${r.abiertas} oportunidades abiertas (mensual)`} />
        <Kpi titulo="Pronóstico" valor={dinero(r.ponderado)} nota="Valor × probabilidad de cada etapa" />
        <Kpi titulo="Ganado este mes" valor={dinero(r.mrr_ganado_mes)} nota={`${r.ganadas_mes} cliente(s) nuevo(s)`} verde />
        <Kpi titulo="Conversión 90 días" valor={r.conversion_90 === null ? "—" : `${r.conversion_90}%`} nota="Ganadas ÷ cerradas" />
        <Link href="/plataforma/ventas/tareas"><Kpi titulo="Mis tareas" valor={`${r.tareas_vencidas} vencidas`} nota={`${r.tareas_hoy} para hoy · ${r.sin_contactar} sin contactar`} alerta={r.tareas_vencidas > 0} /></Link>
      </div>}
      <div className="mb-3 flex flex-wrap gap-2">
        <input className="campo max-w-xs" placeholder="Buscar despacho, persona o correo" value={filtro.q} onChange={(e) => setFiltro({ ...filtro, q: e.target.value })} aria-label="Buscar" />
        {cat && <select className="campo w-auto" value={filtro.propietario_id} onChange={(e) => setFiltro({ ...filtro, propietario_id: e.target.value })} aria-label="Responsable">
          <option value="">Todo el equipo</option><option value={cat.yo}>Solo las mías</option>{cat.equipo.filter((x: any) => x.id !== cat.yo).map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select>}
        {cat && <select className="campo w-auto" value={filtro.campana_id} onChange={(e) => setFiltro({ ...filtro, campana_id: e.target.value })} aria-label="Campaña">
          <option value="">Todas las campañas</option>{cat.campanas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select>}
      </div>
      {t && cat && <div className="flex gap-3 overflow-x-auto pb-4">{cat.etapas.map((e: any) => (
        <section key={e.clave} className={`w-72 shrink-0 rounded-2xl ${e.clave === "ganado" ? "bg-emerald-50" : e.clave === "perdido" ? "bg-slate-100" : "bg-crema/70"} p-2`} aria-label={e.nombre}>
          <header className="mb-2 flex items-baseline justify-between px-1">
            <h2 className="text-sm font-bold text-marino">{e.nombre} <span className="text-slate-400">({t.totales[e.clave].n})</span></h2>
            <span className="text-xs font-semibold text-slate-500">{dinero(t.totales[e.clave].valor)}</span></header>
          {["ganado", "perdido"].includes(e.clave) && <p className="mb-2 px-1 text-[11px] text-slate-500">Últimos 30 días</p>}
          <ul className="space-y-2">{t.columnas[e.clave].map((o: any) => (
            <li key={o.id} className="rounded-xl bg-white p-3 text-sm shadow-sm">
              <Link href={`/plataforma/ventas/oportunidades/${o.id}`} className="font-semibold text-marino hover:underline">{o.titulo}</Link>
              <p className="text-xs text-slate-600">{o.contacto?.nombre}{o.contacto?.despacho && o.contacto.despacho !== o.titulo ? ` · ${o.contacto.despacho}` : ""}</p>
              <p className="mt-1 flex justify-between text-xs"><b className="text-marino">{dinero(o.valor_mensual)}<span className="font-normal text-slate-400">/mes</span></b><span className="text-slate-500">{o.propietario || "Sin asignar"}</span></p>
              {o.proxima_tarea ? <p className={`mt-1 text-xs ${new Date(o.proxima_tarea) < new Date() ? "font-semibold text-red-700" : "text-slate-500"}`}>⏰ {cuando(o.proxima_tarea)}</p>
                : cat.abiertas.includes(o.etapa) && <p className="mt-1 text-xs text-amber-700">Sin siguiente paso</p>}
              {cat.abiertas.includes(o.etapa) && <select className="mt-2 w-full rounded-lg border border-crema-300 bg-crema/40 px-2 py-1 text-xs" value="" aria-label={`Mover ${o.titulo}`}
                onChange={(ev) => ev.target.value && mover(o, ev.target.value)}>
                <option value="">Mover a…</option>{cat.etapas.filter((x: any) => x.clave !== o.etapa).map((x: any) => <option key={x.clave} value={x.clave}>{x.nombre}</option>)}</select>}
              {o.etapa === "perdido" && o.motivo_texto && <p className="mt-1 text-xs text-slate-500">Motivo: {o.motivo_texto}</p>}
            </li>))}
            {!t.columnas[e.clave].length && <li className="px-1 py-3 text-center text-xs text-slate-400">—</li>}</ul>
        </section>))}</div>}
      {r?.por_vendedor?.length > 0 && <section className="tarjeta mt-2 overflow-hidden">
        <h2 className="border-b border-crema-300 px-4 py-3 font-semibold text-marino">Por persona del equipo</h2>
        <table className="w-full text-sm"><thead className="bg-crema/60 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-2">Responsable</th><th className="px-4 py-2 text-right">Abiertas</th><th className="px-4 py-2 text-right">En embudo</th><th className="px-4 py-2 text-right">Ganadas este mes</th></tr></thead>
          <tbody className="divide-y divide-crema-200">{r.por_vendedor.map((v: any) => <tr key={v.id ?? "x"}><td className="px-4 py-2">{v.nombre}</td><td className="px-4 py-2 text-right">{v.abiertas}</td><td className="px-4 py-2 text-right">{dinero(v.valor)}</td><td className="px-4 py-2 text-right">{v.ganadas_mes}</td></tr>)}</tbody></table>
      </section>}
      {nueva && cat && <FormOportunidad cat={cat} onCerrar={() => setNueva(false)} onListo={(o) => router.push(`/plataforma/ventas/oportunidades/${o.id}`)} />}
    </VentasShell>
  );
}

function Kpi({ titulo, valor, nota, alerta, verde }: { titulo: string; valor: string; nota: string; alerta?: boolean; verde?: boolean }) {
  return (
    <div className={`tarjeta h-full p-4 ${alerta ? "ring-2 ring-red-300" : ""}`}>
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{titulo}</p>
      <p className={`mt-1 text-xl font-extrabold ${alerta ? "text-red-700" : verde ? "text-emerald-700" : "text-marino"}`}>{valor}</p>
      <p className="text-xs text-slate-500">{nota}</p>
    </div>
  );
}
