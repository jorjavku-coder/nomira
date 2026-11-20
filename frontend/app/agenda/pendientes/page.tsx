"use client";
import { useCallback, useEffect, useState } from "react";
import { AgendaShell, FilaEvento, FormEvento, useCatalogosAgenda } from "@/components/agenda";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

/** Todos los pendientes con filtros y exportación. */
export default function Pendientes() {
  const cat = useCatalogosAgenda();
  const [f, setF] = useState({ estado: "pendiente", tipo: "", responsable_id: "", desde: "", hasta: "", por_validar: false });
  const [filas, setFilas] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const cargar = useCallback(() => {
    const q = new URLSearchParams(Object.entries(f).filter(([, v]) => v !== "" && v !== false).map(([k, v]) => [k, String(v)]));
    api.get(`/agenda/eventos?${q}`).then(setFilas).catch((e) => setError(e.message));
  }, [f]);
  useEffect(() => { cargar(); }, [cargar]);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <AgendaShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-3xl font-extrabold text-marino">Todos los pendientes</h1>
        <div className="flex gap-2">
          <button className="btn-sec" onClick={() => api.descargar(`/agenda/exportar.csv${f.desde || f.hasta ? `?${new URLSearchParams({ ...(f.desde ? { desde: f.desde } : {}), ...(f.hasta ? { hasta: f.hasta } : {}) })}` : ""}`, "agenda.csv").catch((e) => setError(e.message))}>Exportar a Excel (CSV)</button>
          {cat?.puede_editar && <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo</button>}
        </div>
      </div>
      {cat && <div className="tarjeta mb-4 grid gap-3 p-4 sm:grid-cols-3 lg:grid-cols-6">
        <label><span className="etiqueta">Estado</span><select className="campo" value={f.estado} onChange={set("estado")}><option value="pendiente">Pendientes</option><option value="cumplido">Cumplidos</option><option value="cancelado">Cancelados</option><option value="todos">Todos</option></select></label>
        <label><span className="etiqueta">Tipo</span><select className="campo" value={f.tipo} onChange={set("tipo")}><option value="">Todos</option>{Object.entries(cat.tipos_evento).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label><span className="etiqueta">Responsable</span><select className="campo" value={f.responsable_id} onChange={set("responsable_id")}><option value="">Todos</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
        <label><span className="etiqueta">Desde</span><input className="campo" type="date" value={f.desde} onChange={set("desde")} /></label>
        <label><span className="etiqueta">Hasta</span><input className="campo" type="date" value={f.hasta} onChange={set("hasta")} /></label>
        <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" className="accent-turquesa" checked={f.por_validar} onChange={set("por_validar")} />Solo cálculos por validar</label>
      </div>}
      <Aviso>{error}</Aviso>
      {filas && <section className="tarjeta overflow-hidden">{filas.length ? <ul className="divide-y divide-crema-200">{filas.map((e) => <FilaEvento key={e.id} e={e} onCambio={cargar} />)}</ul>
        : <p className="p-4 text-sm text-slate-500">No hay resultados con esos filtros.</p>}</section>}
      {nuevo && <FormEvento onCerrar={() => setNuevo(false)} onGuardado={() => { setNuevo(false); cargar(); }} />}
    </AgendaShell>
  );
}
