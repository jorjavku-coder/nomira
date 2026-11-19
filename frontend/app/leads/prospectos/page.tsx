"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AltaRapida, FilaProspecto, LeadsShell, useCatalogosLeads } from "@/components/leads";
import { Aviso } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

const VISTAS: Record<string, string> = {
  abiertos: "Abiertos", nuevos: "Nuevos (sin respuesta)", responder: "Esperan respuesta", citas: "Citas próximas", seguimientos: "Seguimientos de hoy o vencidos",
  sin_actividad: "Sin próximo paso o sin actividad", borradores: "Borradores", contratados: "Contratados", no_contratados: "No contratados", todos: "Todos",
  por_asignar: "Mensajes por asignar",
};

/** Lista de prospectos con filtros básicos: vista, etapa, responsable, materia y canal. */
export default function Prospectos() {
  const cat = useCatalogosLeads();
  const [f, setF] = useState<any>({ vista: "abiertos", etapa_id: "", responsable_id: "", materia: "", canal: "", campana_id: "", q: "" });
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [alta, setAlta] = useState(false);
  const [listo, setListo] = useState(false);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const v = p.get("vista");
    if (v && VISTAS[v]) setF((x: any) => ({ ...x, vista: v }));
    const c = p.get("campana");
    if (c) setF((x: any) => ({ ...x, campana_id: c, vista: v && VISTAS[v] ? v : "todos" }));
    setListo(true);
  }, []);
  const cargar = useCallback(() => {
    if (!listo || f.vista === "por_asignar") return;
    const cuerpo: any = { vista: f.vista };
    for (const k of ["etapa_id", "responsable_id", "campana_id"]) if (f[k]) cuerpo[k] = Number(f[k]);
    for (const k of ["materia", "canal", "q"]) if (f[k]) cuerpo[k] = f[k];
    setR(null);
    api.post("/leads/prospectos/consulta", cuerpo).then(setR).catch((e) => setError(e.message));
  }, [f, listo]);
  useEffect(() => { const t = setTimeout(cargar, 250); return () => clearTimeout(t); }, [cargar]);
  const cambiar = (k: string) => (e: any) => {
    setF({ ...f, [k]: e.target.value });
    if (k === "vista") history.replaceState(null, "", `/leads/prospectos?vista=${e.target.value}`);
  };
  return (
    <LeadsShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-extrabold text-marino">{VISTAS[f.vista]}</h1>
        <div className="flex flex-wrap gap-2">
          {cat?.puede_editar && f.vista !== "por_asignar" && <>
            <button className="btn-sec" onClick={() => api.descargar(`/leads/exportar?formato=xlsx&vista=${f.vista === "por_asignar" ? "todos" : f.vista}`, "prospectos.xlsx").catch((e) => setError(e.message))}>Descargar Excel</button>
            <button className="btn-sec" onClick={() => api.descargar(`/leads/exportar?formato=csv&vista=${f.vista}`, "prospectos.csv").catch((e) => setError(e.message))}>CSV</button>
          </>}
          {cat?.puede_editar && <button className="btn-turquesa" onClick={() => setAlta(true)}>+ Agregar prospecto</button>}
        </div>
      </div>
      {cat && (
        <div className="tarjeta mb-4 grid gap-2 p-3 sm:grid-cols-3 lg:grid-cols-7">
          <select className="campo" value={f.vista} onChange={cambiar("vista")} aria-label="Vista">
            {Object.entries(VISTAS).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
          {f.vista !== "por_asignar" && <>
            <select className="campo" value={f.etapa_id} onChange={cambiar("etapa_id")} aria-label="Etapa">
              <option value="">Todas las etapas</option>{cat.etapas.map((e: any) => <option key={e.id} value={e.id}>{e.nombre}</option>)}</select>
            <select className="campo" value={f.responsable_id} onChange={cambiar("responsable_id")} aria-label="Responsable">
              <option value="">Todos los responsables</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select>
            <select className="campo" value={f.materia} onChange={cambiar("materia")} aria-label="Materia">
              <option value="">Todas las materias</option>{cat.materias.map((x: string) => <option key={x}>{x}</option>)}</select>
            <select className="campo" value={f.canal} onChange={cambiar("canal")} aria-label="Canal">
              <option value="">Todos los canales</option>{Object.entries(cat.canales).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select>
            {f.campana_id && <button className="btn-sec" onClick={() => setF({ ...f, campana_id: "" })}>Campaña: {cat.campanas.find((c: any) => String(c.id) === String(f.campana_id))?.nombre || "—"} ✕</button>}
            <input className="campo" placeholder="Buscar nombre, teléfono o correo" value={f.q} onChange={cambiar("q")} aria-label="Buscar" />
          </>}
        </div>
      )}
      <Aviso>{error}</Aviso>
      {f.vista === "por_asignar" ? <PorAsignar /> : (
        <>
          {!r && !error && <p className="text-sm text-slate-500">Cargando…</p>}
          {r && <p className="mb-2 text-xs text-slate-500">{r.total} prospecto(s){r.total > r.filas.length ? ` (se muestran ${r.filas.length})` : ""}</p>}
          {r && (
            <div className="tarjeta divide-y divide-crema-200 overflow-hidden">
              {r.filas.length === 0 && (
                <div className="p-6 text-center text-sm text-slate-500">
                  No hay prospectos en esta lista.{" "}
                  {cat?.puede_editar && <button className="font-semibold text-turquesa-700 underline" onClick={() => setAlta(true)}>Agregar uno</button>}
                </div>)}
              {r.filas.map((x: any) => <FilaProspecto key={x.id} f={x} />)}
            </div>)}
        </>
      )}
      {alta && <AltaRapida onCerrar={() => setAlta(false)} />}
    </LeadsShell>
  );
}

/** Mensajes de WhatsApp que no se pudieron asociar con certeza a un prospecto. */
function PorAsignar() {
  const [xs, setXs] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busqueda, setBusqueda] = useState<Record<number, any[]>>({});
  const cargar = () => api.get("/leads/mensajes?bandeja=por_asignar").then(setXs).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  async function asignar(id: number, cuerpo: any) {
    setError(""); setOk("");
    try { await api.post(`/leads/mensajes/${id}/asignar`, cuerpo); setOk("Mensaje asignado."); cargar(); } catch (e: any) { setError(e.message); }
  }
  async function buscar(id: number, q: string) {
    if (q.trim().length < 2) return setBusqueda({ ...busqueda, [id]: [] });
    const r = await api.post("/leads/prospectos/consulta", { vista: "todos", q });
    setBusqueda({ ...busqueda, [id]: r.filas.slice(0, 6) });
  }
  return (
    <div className="space-y-3">
      <Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
      {!xs && <p className="text-sm text-slate-500">Cargando…</p>}
      {xs?.length === 0 && <p className="tarjeta p-6 text-center text-sm text-slate-500">No hay mensajes por asignar.</p>}
      {xs?.map((x) => (
        <div key={x.id} className="tarjeta p-4 text-sm">
          <p className="text-xs text-slate-500">WhatsApp · {x.telefono} · {fechaHora(x.creado_en)}</p>
          <p className="mt-1 whitespace-pre-line text-slate-800">{x.texto}</p>
          <p className="mt-2 text-xs text-slate-500">Hay más de un prospecto abierto con este número: elija a cuál pertenece o cree uno nuevo.</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input className="campo max-w-xs" placeholder="Buscar prospecto" onChange={(e) => buscar(x.id, e.target.value)} />
            <button className="btn-sec" onClick={() => asignar(x.id, { crear: true })}>Crear prospecto nuevo</button>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {(busqueda[x.id] || []).map((p) => <button key={p.id} className="btn-sec text-xs" onClick={() => asignar(x.id, { prospecto_id: p.id })}>Asignar a {p.nombre} ({p.etapa})</button>)}
          </div>
        </div>))}
      <p className="text-xs text-slate-500">¿Prefiere ver todos sus prospectos? <Link className="font-semibold text-turquesa-700 underline" href="/leads/prospectos?vista=abiertos">Volver a la lista</Link></p>
    </div>
  );
}
