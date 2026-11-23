"use client";
import { useCallback, useEffect, useState } from "react";
import { dinero, useCatalogosVentas, VentasShell } from "@/components/ventas";
import { Aviso, Modal } from "@/components/ui";
import { apiP } from "@/lib/plataforma";

const ESTADO: Record<string, string> = { activa: "bg-emerald-100 text-emerald-800", pausada: "bg-amber-100 text-amber-800", terminada: "bg-slate-200 text-slate-600" };

export default function Campanas() {
  const cat = useCatalogosVentas();
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [editar, setEditar] = useState<any>(null);
  const cargar = useCallback(() => apiP.get("/ventas/campanas").then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  return (
    <VentasShell acciones={<button className="btn-turquesa" onClick={() => setEditar({})}>+ Nueva campaña</button>}>
      <p className="mb-4 max-w-3xl text-sm text-slate-600">Registre cada campaña con su presupuesto y asígnela a los contactos u oportunidades que traiga. Aquí ve cuántos prospectos generó, cuántos se volvieron clientes, cuánto ingreso mensual trajo y cuánto le costó cada uno.</p>
      <Aviso>{error}</Aviso>
      {lista && <div className="tarjeta overflow-x-auto"><table className="w-full text-sm">
        <thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
          <th className="px-4 py-2">Campaña</th><th className="px-4 py-2 text-right">Presupuesto</th><th className="px-4 py-2 text-right">Prospectos</th><th className="px-4 py-2 text-right">Abiertas</th>
          <th className="px-4 py-2 text-right">Ganadas</th><th className="px-4 py-2 text-right">Conversión</th><th className="px-4 py-2 text-right">Ingreso mensual</th><th className="px-4 py-2 text-right">Costo por prospecto</th><th className="px-4 py-2 text-right">Costo por cliente</th></tr></thead>
        <tbody className="divide-y divide-crema-200">{lista.map((c) => (
          <tr key={c.id} className="cursor-pointer hover:bg-crema/50" onClick={() => setEditar(c)}>
            <td className="px-4 py-2"><p className="font-semibold text-marino">{c.nombre}</p><p className="text-xs text-slate-500">{c.canal_texto} <span className={`ml-1 rounded-full px-2 ${ESTADO[c.estado]}`}>{c.estado}</span>{c.utm_campaign && <span className="ml-1 font-mono">utm: {c.utm_campaign}</span>}</p></td>
            <td className="px-4 py-2 text-right">{dinero(c.presupuesto)}</td><td className="px-4 py-2 text-right">{c.leads}</td><td className="px-4 py-2 text-right">{c.abiertas}</td>
            <td className="px-4 py-2 text-right font-semibold text-emerald-700">{c.ganadas}</td><td className="px-4 py-2 text-right">{c.conversion === null ? "—" : `${c.conversion}%`}</td>
            <td className="px-4 py-2 text-right font-semibold">{dinero(c.mrr_ganado)}</td><td className="px-4 py-2 text-right">{dinero(c.costo_por_lead)}</td><td className="px-4 py-2 text-right">{dinero(c.costo_por_cliente)}</td>
          </tr>))}
          {!lista.length && <tr><td colSpan={9} className="p-8 text-center text-slate-500">Aún no hay campañas.</td></tr>}</tbody></table></div>}
      {editar && cat && <FormCampana c={editar} cat={cat} onCerrar={() => setEditar(null)} onListo={() => { setEditar(null); cargar(); }} />}
    </VentasShell>
  );
}

function FormCampana({ c, cat, onCerrar, onListo }: { c: any; cat: any; onCerrar: () => void; onListo: () => void }) {
  const [f, setF] = useState<any>({ nombre: c.nombre || "", canal: c.canal || "facebook", estado: c.estado || "activa", inicio: c.inicio || "", fin: c.fin || "", presupuesto: c.presupuesto || "", utm_campaign: c.utm_campaign || "", notas: c.notas || "" });
  const [error, setError] = useState("");
  const k = (x: string) => ({ value: f[x] ?? "", onChange: (e: any) => setF({ ...f, [x]: e.target.value }) });
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    const cuerpo = { ...f, inicio: f.inicio || null, fin: f.fin || null, presupuesto: f.presupuesto || null, utm_campaign: f.utm_campaign || null, notas: f.notas || null };
    try { c.id ? await apiP.put(`/ventas/campanas/${c.id}`, cuerpo) : await apiP.post("/ventas/campanas", cuerpo); onListo(); } catch (x: any) { setError(x.message); }
  }
  async function borrar() { try { await apiP.borrar(`/ventas/campanas/${c.id}`); onListo(); } catch (x: any) { setError(x.message); } }
  return (
    <Modal titulo={c.id ? "Editar campaña" : "Nueva campaña"} onCerrar={onCerrar} ancho="max-w-xl">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={guardar}>
        <label className="sm:col-span-2"><span className="etiqueta">Nombre</span><input className="campo" required minLength={2} placeholder="Ej. Facebook · despachos laborales · noviembre" {...k("nombre")} /></label>
        <label><span className="etiqueta">Canal</span><select className="campo" {...k("canal")}>{Object.entries(cat.canales).map(([a, b]) => <option key={a} value={a}>{b as string}</option>)}</select></label>
        <label><span className="etiqueta">Estado</span><select className="campo" {...k("estado")}><option value="activa">Activa</option><option value="pausada">Pausada</option><option value="terminada">Terminada</option></select></label>
        <label><span className="etiqueta">Inicio</span><input className="campo" type="date" {...k("inicio")} /></label>
        <label><span className="etiqueta">Fin</span><input className="campo" type="date" {...k("fin")} /></label>
        <label><span className="etiqueta">Presupuesto total (MXN)</span><input className="campo" inputMode="decimal" value={f.presupuesto} onChange={(e) => setF({ ...f, presupuesto: e.target.value.replace(/[^\d.]/g, "") })} /></label>
        <label><span className="etiqueta">utm_campaign (opcional)</span><input className="campo font-mono" {...k("utm_campaign")} /></label>
        <label className="sm:col-span-2"><span className="etiqueta">Notas</span><textarea className="campo" rows={2} {...k("notas")} /></label>
        <div className="sm:col-span-2"><Aviso>{error}</Aviso></div>
        <div className="flex justify-between gap-2 sm:col-span-2">{c.id && cat.es_super ? <button type="button" className="btn-sec text-red-700" onClick={borrar}>Borrar</button> : <span />}
          <span className="flex gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></span></div>
      </form>
    </Modal>
  );
}
