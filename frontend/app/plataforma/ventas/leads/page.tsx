"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Calificar, cuando, Descartar, FormActividad, useCatalogosVentas, VentasShell } from "@/components/ventas";
import { Aviso, Modal } from "@/components/ui";
import { apiP, avisarContadores } from "@/lib/plataforma";

/** Leads (MQL): prospectos que el equipo busca o carga. Pasan a Contactos (SQL) con una llamada efectiva o respuesta por correo. */
export default function Leads() {
  const cat = useCatalogosVentas();
  const router = useRouter();
  const [estado, setEstado] = useState("mql");
  const [filtro, setFiltro] = useState({ q: "", propietario_id: "", campana_id: "" });
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [dialogo, setDialogo] = useState<{ tipo: "nuevo" | "importar" | "intento" | "calificar" | "descartar"; lead?: any } | null>(null);
  const cargar = useCallback(() => {
    const p = new URLSearchParams({ estado, ...Object.fromEntries(Object.entries(filtro).filter(([, v]) => v)) });
    apiP.get(`/ventas/leads?${p}`).then(setLista).catch((e) => setError(e.message));
  }, [estado, filtro]);
  useEffect(() => { const t = setTimeout(cargar, 200); return () => clearTimeout(t); }, [cargar]);
  async function descargar(ruta: string, nombre: string) {
    try { const b = await apiP.blob(ruta); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = nombre; a.click(); } catch (e: any) { setError(e.message); }
  }
  async function traerSitio() {
    try { const x = await apiP.post("/ventas/importar-solicitudes"); setOk(x.nuevas ? `Se agregaron ${x.nuevas} solicitud(es) del sitio.` : "No había solicitudes del sitio pendientes."); cargar(); }
    catch (e: any) { setError(e.message); }
  }
  const listo = (msg: string) => { setDialogo(null); setOk(msg); cargar(); avisarContadores(); };
  return (
    <VentasShell acciones={<>
      <button className="btn-sec" onClick={() => descargar(`/ventas/leads/exportar?estado=${estado}`, estado === "mql" ? "leads-mql-nomira.xlsx" : "leads-descartados-nomira.xlsx")}>Exportar Excel</button>
      <button className="btn-sec" onClick={() => setDialogo({ tipo: "importar" })}>Importar Excel</button>
      <button className="btn-turquesa" onClick={() => setDialogo({ tipo: "nuevo" })}>+ Nuevo lead</button></>}>
      <div className="mb-4 rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
        <b>Leads (MQL)</b>: prospectos que buscó el equipo, que cargó de Excel o que llegaron por el sitio. Registre cada intento (llamada sin respuesta, correo enviado).
        Cuando haya una <b>llamada efectiva</b> o <b>aceptación / respuesta por correo</b>, pulse <b>«Pasar a SQL»</b>: se vuelve contacto y entra al embudo.
        <button className="ml-2 font-semibold underline" onClick={traerSitio}>Traer solicitudes del sitio</button>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="mb-3 flex flex-wrap gap-2">
        <div className="flex rounded-xl bg-crema p-1">{[["mql", "Por trabajar"], ["descartado", "Descartados"]].map(([v, t]) =>
          <button key={v} onClick={() => setEstado(v)} className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${estado === v ? "bg-white text-marino shadow-sm" : "text-slate-500"}`}>{t}</button>)}</div>
        <input className="campo max-w-xs" placeholder="Buscar nombre, despacho, correo, ciudad…" value={filtro.q} onChange={(e) => setFiltro({ ...filtro, q: e.target.value })} aria-label="Buscar leads" />
        {cat && <select className="campo w-auto" value={filtro.propietario_id} onChange={(e) => setFiltro({ ...filtro, propietario_id: e.target.value })} aria-label="Ejecutivo">
          <option value="">Todo el equipo</option><option value={cat.yo}>Solo los míos</option>{cat.equipo.filter((x: any) => x.id !== cat.yo).map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select>}
        {cat && <select className="campo w-auto" value={filtro.campana_id} onChange={(e) => setFiltro({ ...filtro, campana_id: e.target.value })} aria-label="Campaña">
          <option value="">Todas las campañas</option>{cat.campanas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select>}
        {lista && <span className="self-center text-sm text-slate-500">{lista.length} lead(s)</span>}
      </div>
      {lista && <div className="tarjeta overflow-x-auto"><table className="w-full text-sm">
        <thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
          <th className="px-4 py-2">Lead</th><th className="px-4 py-2">Datos</th><th className="px-4 py-2">Origen</th><th className="px-4 py-2">Intentos</th><th className="px-4 py-2">Ejecutivo</th><th className="px-4 py-2 text-right">Acciones</th></tr></thead>
        <tbody className="divide-y divide-crema-200">{lista.map((l) => (
          <tr key={l.id} className="hover:bg-crema/40">
            <td className="px-4 py-2"><Link href={`/plataforma/ventas/contactos/${l.id}`} className="font-semibold text-marino hover:underline">{l.nombre}</Link>
              <p className="text-xs text-slate-500">{[l.cargo, l.despacho].filter(Boolean).join(" · ")}{l.no_contactar && <span className="ml-1 rounded-full bg-red-100 px-2 text-red-700">No contactar</span>}</p></td>
            <td className="px-4 py-2 text-slate-600">{l.email || "—"}<p className="text-xs">{[l.telefono, l.ciudad, l.abogados && `${l.abogados} abog.`, l.especialidad].filter(Boolean).join(" · ")}</p></td>
            <td className="px-4 py-2 text-xs text-slate-600">{l.origen_texto}{l.campana && <p>{l.campana}</p>}</td>
            <td className="px-4 py-2 text-xs">{l.intentos ? <><b>{l.intentos}</b> · último {cuando(l.ultimo_intento)}</> : <span className="font-semibold text-amber-700">Sin intentos</span>}
              {l.tarea && <p className={new Date(l.tarea) < new Date() ? "font-semibold text-red-700" : "text-slate-500"}>⏰ {cuando(l.tarea)}</p>}
              {estado === "descartado" && <p className="text-slate-500">{l.motivo_descarte_texto}</p>}</td>
            <td className="px-4 py-2 text-xs text-slate-600">{l.propietario || "Sin asignar"}</td>
            <td className="whitespace-nowrap px-4 py-2 text-right">{estado === "mql" ? <span className="inline-flex gap-1">
              <button className="btn-sec px-2 py-1 text-xs" onClick={() => setDialogo({ tipo: "intento", lead: l })}>+ Intento</button>
              <button className="btn-turquesa px-2 py-1 text-xs" onClick={() => setDialogo({ tipo: "calificar", lead: l })}>Pasar a SQL</button>
              <button className="px-2 py-1 text-xs text-slate-500 underline" onClick={() => setDialogo({ tipo: "descartar", lead: l })}>Descartar</button></span>
              : <button className="btn-sec px-2 py-1 text-xs" onClick={async () => { await apiP.post(`/ventas/leads/${l.id}/reactivar`); listo("Lead reactivado."); }}>Reactivar</button>}</td>
          </tr>))}
          {!lista.length && <tr><td colSpan={6} className="p-8 text-center text-slate-500">{estado === "mql" ? "No hay leads por trabajar. Cárguelos a mano o importe un Excel." : "No hay leads descartados."}</td></tr>}</tbody></table></div>}
      {dialogo?.tipo === "nuevo" && cat && <NuevoLead cat={cat} onCerrar={() => setDialogo(null)} onListo={() => listo("Lead agregado.")} />}
      {dialogo?.tipo === "importar" && cat && <Importar cat={cat} onCerrar={() => setDialogo(null)} onListo={(n) => listo(`Se cargaron ${n} lead(s).`)} />}
      {dialogo?.tipo === "intento" && cat && <FormActividad cat={cat} contactoId={dialogo.lead.id} esLead onCerrar={() => setDialogo(null)}
        onListo={() => listo("Actividad registrada.")} />}
      {dialogo?.tipo === "calificar" && cat && <Calificar cat={cat} lead={dialogo.lead} onCerrar={() => setDialogo(null)} onListo={(r) => router.push(`/plataforma/ventas/oportunidades/${r.oportunidad_id}`)} />}
      {dialogo?.tipo === "descartar" && cat && <Descartar cat={cat} lead={dialogo.lead} onCerrar={() => setDialogo(null)} onListo={() => listo("Lead descartado.")} />}
    </VentasShell>
  );
}

function NuevoLead({ cat, onCerrar, onListo }: { cat: any; onCerrar: () => void; onListo: () => void }) {
  const [f, setF] = useState<any>({ nombre: "", despacho: "", cargo: "", email: "", telefono: "", ciudad: "", abogados: "", especialidad: "", origen: "prospeccion", campana_id: "", notas: "" });
  const [error, setError] = useState("");
  const [dup, setDup] = useState("");
  const c = (k: string) => ({ value: f[k] ?? "", onChange: (e: any) => setF({ ...f, [k]: e.target.value }) });
  async function guardar(e: React.FormEvent | null, forzar = false) {
    e?.preventDefault(); setError(""); setDup("");
    const n = (v: string) => v || null;
    try {
      await apiP.post(`/ventas/leads${forzar ? "?permitir_duplicado=true" : ""}`, { ...f, despacho: n(f.despacho), cargo: n(f.cargo), email: n(f.email), telefono: n(f.telefono),
        ciudad: n(f.ciudad), especialidad: n(f.especialidad), notas: n(f.notas), abogados: f.abogados ? Number(f.abogados) : null, campana_id: f.campana_id ? Number(f.campana_id) : null });
      onListo();
    } catch (x: any) { if (/Ya existe/.test(x.message)) setDup(x.message); else setError(x.message); }
  }
  return (
    <Modal titulo="Nuevo lead (MQL)" onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => guardar(e)}>
        <label><span className="etiqueta">Nombre</span><input className="campo" required minLength={2} {...c("nombre")} /></label>
        <label><span className="etiqueta">Despacho</span><input className="campo" {...c("despacho")} /></label>
        <label><span className="etiqueta">Correo</span><input className="campo" type="email" {...c("email")} /></label>
        <label><span className="etiqueta">Teléfono</span><input className="campo" {...c("telefono")} /></label>
        <label><span className="etiqueta">Cargo</span><input className="campo" {...c("cargo")} /></label>
        <label><span className="etiqueta">Ciudad</span><input className="campo" {...c("ciudad")} /></label>
        <label><span className="etiqueta">Abogados</span><input className="campo" type="number" min={1} {...c("abogados")} /></label>
        <label><span className="etiqueta">Especialidad</span><input className="campo" {...c("especialidad")} /></label>
        <label><span className="etiqueta">¿De dónde salió?</span><select className="campo" {...c("origen")}>{Object.entries(cat.origenes).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
        <label><span className="etiqueta">Campaña</span><select className="campo" {...c("campana_id")}><option value="">Ninguna</option>{cat.campanas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
        <label className="sm:col-span-2"><span className="etiqueta">Notas</span><input className="campo" {...c("notas")} /></label>
        <div className="sm:col-span-2"><Aviso>{error}</Aviso>{dup && <Aviso tipo="alerta">{dup} <button type="button" className="font-semibold underline" onClick={() => guardar(null, true)}>Es otra persona: agregar</button></Aviso>}</div>
        <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Agregar lead</button></div>
      </form>
    </Modal>
  );
}

function Importar({ cat, onCerrar, onListo }: { cat: any; onCerrar: () => void; onListo: (n: number) => void }) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [opc, setOpc] = useState({ propietario_id: String(cat.yo), campana_id: "", origen: "prospeccion" });
  const [vista, setVista] = useState<any>(null);
  const [error, setError] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  async function enviar(confirmar: boolean, a = archivo) {
    if (!a) return;
    setError("");
    const d = new FormData(); d.append("archivo", a); d.append("confirmar", String(confirmar)); d.append("origen", opc.origen);
    if (opc.propietario_id) d.append("propietario_id", opc.propietario_id);
    if (opc.campana_id) d.append("campana_id", opc.campana_id);
    try { const r = await apiP.subir("/ventas/leads/importar", d); if (confirmar) onListo(r.nuevos); else setVista(r); } catch (e: any) { setError(e.message); }
  }
  async function plantilla() { const b = await apiP.blob("/ventas/leads/plantilla"); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "plantilla-leads-nomira.xlsx"; a.click(); }
  const COLOR: Record<string, string> = { nuevo: "text-emerald-700", repetido: "text-slate-500", error: "text-red-700" };
  return (
    <Modal titulo="Importar leads de Excel" onCerrar={onCerrar} ancho="max-w-2xl">
      <div className="space-y-3 text-sm">
        <p className="text-slate-600">Excel (.xlsx) o CSV con columnas como Nombre, Despacho, Correo, Teléfono, Ciudad, Estado, Abogados, Especialidad y Notas. Los repetidos (mismo correo o teléfono) se omiten. <button className="font-semibold text-turquesa-700 underline" onClick={plantilla}>Descargar plantilla</button></p>
        <div className="grid gap-3 sm:grid-cols-3">
          <label><span className="etiqueta">Asignar a</span><select className="campo" value={opc.propietario_id} onChange={(e) => setOpc({ ...opc, propietario_id: e.target.value })}>{cat.equipo.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Campaña</span><select className="campo" value={opc.campana_id} onChange={(e) => setOpc({ ...opc, campana_id: e.target.value })}><option value="">Ninguna</option>{cat.campanas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
          <label><span className="etiqueta">Origen</span><select className="campo" value={opc.origen} onChange={(e) => setOpc({ ...opc, origen: e.target.value })}>{Object.entries(cat.origenes).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}</select></label>
        </div>
        <input ref={ref} className="campo" type="file" accept=".xlsx,.csv" aria-label="Archivo de leads" onChange={(e) => { const a = e.target.files?.[0] || null; setArchivo(a); setVista(null); if (a) enviar(false, a); }} />
        <Aviso>{error}</Aviso>
        {vista && <>
          <p><b className="text-emerald-700">{vista.nuevos} nuevos</b> · {vista.repetidos} repetidos · <span className={vista.errores ? "text-red-700" : ""}>{vista.errores} con errores</span></p>
          <div className="max-h-64 overflow-auto rounded-xl border border-crema-300"><table className="w-full text-xs"><tbody className="divide-y divide-crema-200">
            {vista.filas.map((f: any) => <tr key={f.fila}><td className="px-2 py-1 text-slate-400">Fila {f.fila}</td><td className="px-2 py-1 font-semibold">{f.nombre}</td><td className="px-2 py-1">{f.email}</td>
              <td className={`px-2 py-1 ${COLOR[f.estado]}`}>{f.estado === "nuevo" ? "Se cargará" : f.motivo}</td></tr>)}</tbody></table></div></>}
        <div className="flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={!vista?.nuevos} onClick={() => enviar(true)}>Cargar {vista?.nuevos || ""} lead(s)</button></div>
      </div>
    </Modal>
  );
}
