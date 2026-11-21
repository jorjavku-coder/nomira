"use client";
import { useCallback, useEffect, useState } from "react";
import { AgendaShell, diaLargo, recargarCatalogosAgenda, useCatalogosAgenda } from "@/components/agenda";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

/** Calendarios judiciales (días inhábiles por tribunal) y plazos frecuentes que define el despacho. */
export default function Calendarios() {
  const cat = useCatalogosAgenda();
  const [lista, setLista] = useState<any[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [edit, setEdit] = useState<any>(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => api.get("/agenda/calendarios").then((x) => { setLista(x); if (!sel && x.length) setSel(x[0].id); }).catch((e) => setError(e.message)), [sel]);
  useEffect(() => { cargar(); }, [cargar]);
  return (
    <AgendaShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Días hábiles</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-500">Capture el calendario oficial de cada tribunal: vacaciones, suspensiones y días que se habiliten. Nomira incluye como referencia los días de descanso obligatorio del artículo 74 de la Ley Federal del Trabajo; los demás días los define cada tribunal y los captura su despacho.</p></div>
        {cat?.puede_editar && <button className="btn-turquesa" onClick={() => setEdit({ nombre: "", jurisdiccion: "federal", entidad: "", descripcion: "", fuente: "", dias_semana_inhabiles: [5, 6], incluir_descanso_lft: true, activo: true })}>+ Nuevo calendario</button>}
      </div>
      <Aviso>{error}</Aviso>
      <div className="grid gap-5 lg:grid-cols-[18rem_1fr]">
        <ul className="tarjeta h-fit divide-y divide-crema-200">{lista.map((c) => (
          <li key={c.id}><button className={`w-full px-4 py-3 text-left text-sm ${sel === c.id ? "bg-turquesa-50" : "hover:bg-crema/40"}`} onClick={() => setSel(c.id)}>
            <b className="text-marino">{c.nombre}</b>{!c.activo && <span className="ml-1 text-xs text-slate-400">(inactivo)</span>}
            <span className="block text-xs text-slate-500">{c.jurisdiccion === "estatal" ? c.entidad : "Federal"} · {c.dias_capturados} día(s) capturados</span></button></li>))}
          {!lista.length && <li className="p-4 text-sm text-slate-500">Aún no hay calendarios. Sin calendario, los plazos solo saltan fines de semana y los días del art. 74 LFT.</li>}</ul>
        {sel && <DetalleCalendario id={sel} onEditar={(c) => setEdit(c)} puede={cat?.puede_editar} />}
      </div>
      <Plantillas />
      {edit && <EditarCalendario c={edit} onCerrar={() => setEdit(null)} onGuardado={(c) => { setEdit(null); setSel(c.id); cargar(); recargarCatalogosAgenda(); }} />}
    </AgendaShell>
  );
}

function DetalleCalendario({ id, onEditar, puede }: { id: number; onEditar: (c: any) => void; puede: boolean }) {
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [r, setR] = useState<any>(null);
  const [f, setF] = useState({ desde: "", hasta: "", motivo: "", tipo: "inhabil" });
  const [error, setError] = useState(""); const [ok, setOk] = useState("");
  const cargar = useCallback(() => api.get(`/agenda/calendarios/${id}/anio/${anio}`).then(setR).catch((e) => setError(e.message)), [id, anio]);
  useEffect(() => { cargar(); }, [cargar]);
  if (!r) return null;
  const c = r.calendario;
  return (
    <section className="tarjeta p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><h2 className="text-lg font-bold text-marino">{c.nombre}</h2>
          <p className="text-sm text-slate-600">Inhábiles cada semana: {c.dias_semana_inhabiles.map((d: number) => SEMANA[d]).join(", ") || "ninguno"} · {c.incluir_descanso_lft ? "incluye art. 74 LFT" : "sin art. 74 LFT"}</p>
          {c.fuente && <p className="text-xs text-slate-500">Fuente: {c.fuente}</p>}</div>
        <div className="flex items-center gap-2">
          <button className="btn-sec px-3" aria-label="Año anterior" onClick={() => setAnio(anio - 1)}>‹</button><b>{anio}</b><button className="btn-sec px-3" aria-label="Año siguiente" onClick={() => setAnio(anio + 1)}>›</button>
          {puede && <button className="btn-sec" onClick={() => onEditar(c)}>Editar</button>}
        </div>
      </div>
      {puede && <form className="mt-4 grid gap-2 rounded-xl bg-crema/60 p-3 sm:grid-cols-[auto_auto_1fr_auto_auto]" onSubmit={async (e) => {
        e.preventDefault(); setError(""); setOk("");
        try { const x = await api.post(`/agenda/calendarios/${id}/dias`, { ...f, hasta: f.hasta || null }); setOk(`${x.agregados} día(s) guardados.`); setF({ desde: "", hasta: "", motivo: "", tipo: "inhabil" }); if (Number(f.desde.slice(0, 4)) === anio) setR(x); else cargar(); }
        catch (x: any) { setError(x.message); }
      }}>
        <label><span className="etiqueta">Desde</span><input className="campo" type="date" required value={f.desde} onChange={(e) => setF({ ...f, desde: e.target.value })} /></label>
        <label><span className="etiqueta">Hasta (periodo)</span><input className="campo" type="date" value={f.hasta} onChange={(e) => setF({ ...f, hasta: e.target.value })} /></label>
        <label><span className="etiqueta">Motivo</span><input className="campo" required minLength={3} placeholder="Ej. Primer periodo vacacional" value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} /></label>
        <label><span className="etiqueta">Tipo</span><select className="campo" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}><option value="inhabil">Inhábil</option><option value="habil">Hábil (habilitado)</option></select></label>
        <button className="btn-turquesa self-end">Agregar</button>
      </form>}
      <div className="mt-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <ul className="mt-3 divide-y divide-crema-200 text-sm">{r.dias.map((d: any) => (
        <li key={d.fecha} className="flex items-center justify-between gap-2 py-1.5">
          <span><span className={`mr-2 inline-block w-20 text-xs font-semibold ${d.tipo === "habil" ? "text-emerald-700" : "text-slate-500"}`}>{d.tipo === "habil" ? "HABILITADO" : d.origen === "lft" ? "ART. 74 LFT" : "INHÁBIL"}</span>
            {diaLargo(d.fecha)} — {d.motivo}</span>
          {puede && d.id && <button className="text-xs font-semibold text-red-700 hover:underline" onClick={() => api.borrar(`/agenda/calendarios/${id}/dias/${d.id}`).then(setR).catch((x) => setError(x.message))}>Quitar</button>}
        </li>))}
        {!r.dias.length && <li className="py-2 text-slate-500">Sin días inhábiles capturados para {anio}.</li>}</ul>
    </section>
  );
}

function EditarCalendario({ c, onCerrar, onGuardado }: { c: any; onCerrar: () => void; onGuardado: (c: any) => void }) {
  const cat = useCatalogosAgenda();
  const [f, setF] = useState({ ...c, entidad: c.entidad || "", descripcion: c.descripcion || "", fuente: c.fuente || "" });
  const [error, setError] = useState("");
  return (
    <Modal titulo={c.id ? "Editar calendario" : "Nuevo calendario"} onCerrar={onCerrar} ancho="max-w-xl">
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault(); setError("");
        const cuerpo = { ...f, entidad: f.entidad || null, descripcion: f.descripcion || null, fuente: f.fuente || null };
        try { onGuardado(c.id ? await api.patch(`/agenda/calendarios/${c.id}`, cuerpo) : await api.post("/agenda/calendarios", cuerpo)); } catch (x: any) { setError(x.message); }
      }}>
        <label className="block"><span className="etiqueta">Nombre</span><input className="campo" required minLength={3} value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} placeholder="Ej. Poder Judicial de la Federación 2026" /></label>
        <div className="grid grid-cols-2 gap-3">
          <label><span className="etiqueta">Jurisdicción</span><select className="campo" value={f.jurisdiccion} onChange={(e) => setF({ ...f, jurisdiccion: e.target.value })}>{cat && Object.entries(cat.jurisdicciones).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
          {f.jurisdiccion === "estatal" && <label><span className="etiqueta">Entidad</span><select className="campo" required value={f.entidad} onChange={(e) => setF({ ...f, entidad: e.target.value })}><option value="">Elija…</option>{cat?.entidades.map((x: string) => <option key={x}>{x}</option>)}</select></label>}
        </div>
        <label className="block"><span className="etiqueta">Fuente (acuerdo o circular oficial)</span><input className="campo" value={f.fuente} onChange={(e) => setF({ ...f, fuente: e.target.value })} /></label>
        <div><span className="etiqueta">Días de la semana inhábiles</span><div className="flex flex-wrap gap-3 text-sm">{SEMANA.map((d, i) => <label key={d} className="flex items-center gap-1.5">
          <input type="checkbox" className="accent-turquesa" checked={f.dias_semana_inhabiles.includes(i)} onChange={() => setF({ ...f, dias_semana_inhabiles: f.dias_semana_inhabiles.includes(i) ? f.dias_semana_inhabiles.filter((x: number) => x !== i) : [...f.dias_semana_inhabiles, i] })} />{d}</label>)}</div></div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-turquesa" checked={f.incluir_descanso_lft} onChange={(e) => setF({ ...f, incluir_descanso_lft: e.target.checked })} />Incluir los días de descanso obligatorio del art. 74 LFT</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-turquesa" checked={f.activo} onChange={(e) => setF({ ...f, activo: e.target.checked })} />Activo</label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

function Plantillas() {
  const cat = useCatalogosAgenda();
  const [lista, setLista] = useState<any[]>([]);
  const [edit, setEdit] = useState<any>(null);
  const [error, setError] = useState("");
  const cargar = () => api.get("/agenda/plantillas").then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  return (
    <section className="tarjeta mt-6 p-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div><h2 className="text-lg font-bold text-marino">Plazos frecuentes del despacho</h2>
          <p className="text-sm text-slate-500">Guarde los plazos que usan seguido con su fundamento, para no capturarlos cada vez. Nomira no precarga plazos legales: los define y revisa su despacho.</p></div>
        {cat?.puede_editar && <button className="btn-sec" onClick={() => setEdit({ nombre: "", materia: "", dias: "", tipo_dias: "habiles", surte_efectos: "", fundamento: "", activo: true })}>+ Plazo frecuente</button>}
      </div>
      <Aviso>{error}</Aviso>
      <ul className="mt-3 divide-y divide-crema-200 text-sm">{lista.map((p) => (
        <li key={p.id} className={`flex flex-wrap items-center justify-between gap-2 py-2 ${p.activo ? "" : "opacity-50"}`}>
          <span><b className="text-marino">{p.nombre}</b> · {p.dias} {p.tipo_dias === "habiles" ? "días hábiles" : "días naturales"} · {cat?.surte_efectos[p.surte_efectos]?.toLowerCase()}
            {p.fundamento && <span className="block text-xs text-slate-500">Fundamento: {p.fundamento}</span>}</span>
          {cat?.puede_editar && <button className="btn-sec py-1 text-xs" onClick={() => setEdit(p)}>Editar</button>}
        </li>))}
        {!lista.length && <li className="py-2 text-slate-500">Sin plazos frecuentes.</li>}</ul>
      {edit && cat && <Modal titulo={edit.id ? "Editar plazo frecuente" : "Nuevo plazo frecuente"} onCerrar={() => setEdit(null)}>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={async (e) => {
          e.preventDefault(); setError("");
          const cuerpo = { ...edit, dias: Number(edit.dias), materia: edit.materia || null, fundamento: edit.fundamento || null };
          try { edit.id ? await api.patch(`/agenda/plantillas/${edit.id}`, cuerpo) : await api.post("/agenda/plantillas", cuerpo); setEdit(null); cargar(); recargarCatalogosAgenda(); } catch (x: any) { setError(x.message); }
        }}>
          <label className="sm:col-span-2"><span className="etiqueta">Nombre</span><input className="campo" required minLength={3} value={edit.nombre} onChange={(e) => setEdit({ ...edit, nombre: e.target.value })} placeholder="Ej. Contestación de demanda (materia civil, CDMX)" /></label>
          <label><span className="etiqueta">Días</span><input className="campo" type="number" min={1} required value={edit.dias} onChange={(e) => setEdit({ ...edit, dias: e.target.value })} /></label>
          <label><span className="etiqueta">Tipo de días</span><select className="campo" value={edit.tipo_dias} onChange={(e) => setEdit({ ...edit, tipo_dias: e.target.value })}>{Object.entries(cat.tipos_dias).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
          <label><span className="etiqueta">Surte efectos</span><select className="campo" required value={edit.surte_efectos} onChange={(e) => setEdit({ ...edit, surte_efectos: e.target.value })}><option value="">Elija…</option>{Object.entries(cat.surte_efectos).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
          <label><span className="etiqueta">Materia</span><select className="campo" value={edit.materia || ""} onChange={(e) => setEdit({ ...edit, materia: e.target.value })}><option value="">Cualquiera</option>{Object.entries(cat.materias).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
          <label className="sm:col-span-2"><span className="etiqueta">Fundamento (artículo y ley)</span><input className="campo" value={edit.fundamento || ""} onChange={(e) => setEdit({ ...edit, fundamento: e.target.value })} /></label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-turquesa" checked={edit.activo} onChange={(e) => setEdit({ ...edit, activo: e.target.checked })} />Activo</label>
          <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" className="btn-sec" onClick={() => setEdit(null)}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
        </form></Modal>}
    </section>
  );
}
