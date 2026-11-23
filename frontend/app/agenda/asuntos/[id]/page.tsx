"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AgendaShell, diaLargo, Etq, FilaEvento, FormAsunto, FormEvento, useCatalogosAgenda } from "@/components/agenda";
import { VigilanciaAsunto } from "@/components/estrados";
import { Aviso } from "@/components/ui";
import { api, fecha } from "@/lib/api";

const ESTADO: Record<string, string> = { activo: "bg-emerald-100 text-emerald-800", concluido: "bg-slate-200 text-slate-700", archivado: "bg-slate-200 text-slate-500" };

export default function Asunto() {
  const { id } = useParams<{ id: string }>();
  const cat = useCatalogosAgenda();
  const [a, setA] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [editar, setEditar] = useState(false);
  const [nuevo, setNuevo] = useState<any>(null);
  const [act, setAct] = useState({ fecha: "", tipo: "notificacion", descripcion: "", notificada_en: "" });
  const cargar = useCallback(() => api.get(`/agenda/asuntos/${id}`).then(setA).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(fn: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { const r = await fn(); if (r?.id) setA(r); setOk(msg); return r; } catch (e: any) { setError(e.message); }
  }
  if (!a) return <AgendaShell><Aviso>{error}</Aviso></AgendaShell>;
  const pend = a.eventos.filter((e: any) => e.estado === "pendiente"), cerr = a.eventos.filter((e: any) => e.estado !== "pendiente");
  return (
    <AgendaShell>
      <Link href="/agenda/asuntos" className="text-sm font-semibold text-turquesa-700">← Asuntos</Link>
      <div className="mb-4 mt-2 flex flex-wrap items-start justify-between gap-3">
        <div><div className="flex items-center gap-2"><h1 className="text-3xl font-extrabold text-marino">{a.titulo}</h1><Etq clase={ESTADO[a.estado]}>{a.estado}</Etq></div>
          <p className="mt-1 text-sm text-slate-600">{a.numero && <span className="font-mono">{a.numero} · </span>}{a.materia_texto} · {a.tribunal || "Tribunal sin capturar"}
            {a.entidad ? ` · ${a.entidad}` : " · Federal"}{a.responsable ? ` · Responsable: ${a.responsable}` : ""}</p>
          {a.cr_cliente_id && <p className="text-sm"><Link href={`/clientes/${a.cr_cliente_id}`} className="font-semibold text-turquesa-700 hover:underline">👤 {a.cliente}</Link></p>}
          <p className="text-xs text-slate-500">Días hábiles: {a.calendario || "sin calendario del tribunal (solo fines de semana y art. 74 LFT)"}</p></div>
        {cat?.puede_editar && <div className="flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => setEditar(true)}>Editar</button>
          {a.estado === "activo" ? <button className="btn-sec" onClick={() => hacer(() => api.post(`/agenda/asuntos/${a.id}/estado`, { estado: "concluido" }), "Asunto concluido.")}>Concluir</button>
            : <button className="btn-sec" onClick={() => hacer(() => api.post(`/agenda/asuntos/${a.id}/estado`, { estado: "activo" }), "Asunto reactivado.")}>Reactivar</button>}
          {a.estado === "activo" && <button className="btn-turquesa" onClick={() => setNuevo({ tipo: "plazo" })}>+ Plazo o audiencia</button>}
        </div>}
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="grid gap-5 lg:grid-cols-[1fr_24rem]">
        <div className="space-y-5">
          <section className="tarjeta overflow-hidden"><h2 className="border-b border-crema-300 px-4 py-3 font-semibold text-marino">Pendientes ({pend.length})</h2>
            {pend.length ? <ul className="divide-y divide-crema-200">{pend.map((e: any) => <FilaEvento key={e.id} e={e} onCambio={cargar} mostrarAsunto={false} />)}</ul>
              : <p className="p-4 text-sm text-slate-500">Sin pendientes.</p>}</section>
          {cerr.length > 0 && <details className="tarjeta overflow-hidden"><summary className="cursor-pointer px-4 py-3 font-semibold text-marino">Cumplidos y cancelados ({cerr.length})</summary>
            <ul className="divide-y divide-crema-200">{cerr.map((e: any) => <FilaEvento key={e.id} e={e} onCambio={cargar} mostrarAsunto={false} />)}</ul></details>}
          {a.notas && <section className="tarjeta p-4 text-sm"><h2 className="mb-1 font-semibold text-marino">Notas</h2><p className="whitespace-pre-line text-slate-700">{a.notas}</p></section>}
        </div>
        <div className="space-y-5">
        <VigilanciaAsunto asunto={a} puedeEditar={!!cat?.puede_editar} onCambio={cargar} />
        <section className="tarjeta p-4">
          <h2 className="font-semibold text-marino">Actuaciones</h2>
          {cat?.puede_editar && a.estado === "activo" && <form className="mt-3 space-y-2 rounded-xl bg-crema/60 p-3" onSubmit={async (ev) => {
            ev.preventDefault();
            const r = await hacer(() => api.post(`/agenda/asuntos/${a.id}/actuaciones`, { ...act, notificada_en: act.notificada_en || null }), "Actuación registrada.");
            if (r) { const n = act.notificada_en; setAct({ fecha: "", tipo: "notificacion", descripcion: "", notificada_en: "" });
              if (n) setNuevo({ tipo: "plazo", actuacion_id: r.actuacion_id, calculo: { notificacion: n } }); }
          }}>
            <div className="grid grid-cols-2 gap-2">
              <label><span className="etiqueta">Fecha</span><input className="campo" type="date" required value={act.fecha} onChange={(e) => setAct({ ...act, fecha: e.target.value })} /></label>
              <label><span className="etiqueta">Tipo</span><select className="campo" value={act.tipo} onChange={(e) => setAct({ ...act, tipo: e.target.value })}>{cat && Object.entries(cat.tipos_actuacion).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
            </div>
            <label className="block"><span className="etiqueta">Qué se acordó o sucedió</span><textarea className="campo" rows={2} required minLength={3} value={act.descripcion} onChange={(e) => setAct({ ...act, descripcion: e.target.value })} /></label>
            <label className="block"><span className="etiqueta">Fecha en que se notificó al despacho (opcional)</span><input className="campo" type="date" value={act.notificada_en} onChange={(e) => setAct({ ...act, notificada_en: e.target.value })} /></label>
            <p className="text-xs text-slate-500">Si captura la notificación, le proponemos calcular el plazo que corre a partir de ella.</p>
            <button className="btn-sec w-full">Registrar actuación</button>
          </form>}
          <ol className="mt-3 space-y-3 border-l-2 border-crema-300 pl-4">{a.actuaciones.map((x: any) => (
            <li key={x.id} className="relative text-sm"><span className="absolute -left-[1.4rem] top-1 h-2.5 w-2.5 rounded-full bg-turquesa" />
              <p className="text-xs text-slate-500">{diaLargo(x.fecha)} · {x.tipo_texto}{x.por ? ` · ${x.por}` : ""}</p>
              <p className="text-slate-800">{x.descripcion}</p>
              {x.notificada_en && <p className="text-xs text-slate-600">Notificada el {fecha(x.notificada_en)}
                {cat?.puede_editar && a.estado === "activo" && <button className="ml-2 font-semibold text-turquesa-700 underline" onClick={() => setNuevo({ tipo: "plazo", actuacion_id: x.id, calculo: { notificacion: x.notificada_en } })}>Calcular plazo</button>}</p>}
            </li>))}
            {!a.actuaciones.length && <li className="text-sm text-slate-500">Sin actuaciones registradas.</li>}</ol>
        </section>
        </div>
      </div>
      {editar && <FormAsunto inicial={a} onCerrar={() => setEditar(false)} onGuardado={(x) => { setA(x); setEditar(false); setOk("Asunto actualizado."); }} />}
      {nuevo && <FormEvento inicial={nuevo} asuntoFijo={a} onCerrar={() => setNuevo(null)} onGuardado={() => { setNuevo(null); setOk("Agregado a la agenda."); cargar(); }} />}
    </AgendaShell>
  );
}
