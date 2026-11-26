"use client";
import { useCallback, useEffect, useState } from "react";
import ShellPlataforma from "@/components/plataforma";
import { Aviso, Modal } from "@/components/ui";
import { apiP } from "@/lib/plataforma";

const EST_ALIADO: Record<string, [string, string]> = { prospecto: ["Prospecto", "bg-slate-100 text-slate-700"], activo: ["Activo", "bg-emerald-100 text-emerald-800"], pausado: ["Pausado", "bg-amber-100 text-amber-800"] };
const EST_BENEF: Record<string, [string, string]> = { borrador: ["Borrador", "bg-slate-100 text-slate-700"], publicado: ["Publicado", "bg-emerald-100 text-emerald-800"], pausado: ["Pausado", "bg-amber-100 text-amber-800"] };
const EST_SOL: Record<string, string> = { nueva: "Nueva", en_contacto: "En contacto", aliado: "Ya es aliado", descartada: "Descartada" };
const Chip = ({ e, m }: { e: string; m: Record<string, [string, string]> }) => <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${m[e]?.[1]}`}>{m[e]?.[0] || e}</span>;

/** Club Nomira en el panel: empresas aliadas, sus beneficios, métricas (solo conteos) y postulaciones del sitio. */
export default function ClubPanel() {
  const [d, setD] = useState<any>(null);
  const [tab, setTab] = useState<"beneficios" | "aliados" | "solicitudes">("beneficios");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [aliado, setAliado] = useState<any>(null);
  const [benef, setBenef] = useState<any>(null);
  const [dias, setDias] = useState(90);
  const cargar = useCallback(() => apiP.get(`/club?dias=${dias}`).then(setD).catch((e) => setError(e.message)), [dias]);
  useEffect(() => { cargar(); }, [cargar]);
  const hecho = (t: string) => { setOk(t); setError(""); setTimeout(() => setOk(""), 3000); cargar(); };
  const nombreAliado = (id: number) => d?.aliados.find((a: any) => a.id === id)?.nombre || "—";
  return (
    <ShellPlataforma>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-extrabold text-marino">Club Nomira</h1>
          <p className="text-sm text-slate-500">Beneficios de empresas aliadas para los despachos. A los aliados solo se les comparten conteos, nunca datos personales.</p></div>
        <div className="flex gap-2"><button className="btn-sec" onClick={() => setAliado({ estado: "prospecto" })}>+ Aliado</button>
          <button className="btn-turquesa" disabled={!d?.aliados.length} onClick={() => setBenef({ categoria: "salud", canje: "codigo", estado: "borrador", aliado_id: d?.aliados[0]?.id })}>+ Beneficio</button></div>
      </div>
      <Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
      {d && <div className="mb-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[["Aliados activos", d.cifras.aliados_activos], ["Beneficios visibles", d.cifras.publicados], [`Vistas (${d.dias} días)`, d.cifras.vistas],
          [`Canjes (${d.dias} días)`, d.cifras.canjes], ["Postulaciones nuevas", d.cifras.solicitudes_nuevas], ["Credenciales emitidas", d.cifras.credenciales]].map(([t, n]) => (
          <div key={t as string} className="tarjeta p-4"><p className="text-2xl font-extrabold text-marino">{n as number}</p><p className="text-xs text-slate-500">{t}</p></div>))}
      </div>}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-xl bg-crema p-1 text-sm">{([["beneficios", "Beneficios"], ["aliados", "Aliados"], ["solicitudes", `Postulaciones${d?.cifras.solicitudes_nuevas ? ` (${d.cifras.solicitudes_nuevas})` : ""}`]] as const).map(([v, t]) => (
          <button key={v} onClick={() => setTab(v)} className={`rounded-lg px-3 py-2 font-semibold ${tab === v ? "bg-white text-marino shadow-sm" : "text-slate-500"}`}>{t}</button>))}</div>
        {tab === "beneficios" && <select className="campo ml-auto w-auto text-sm" value={dias} onChange={(e) => setDias(Number(e.target.value))} aria-label="Periodo de métricas">
          {[30, 90, 365].map((x) => <option key={x} value={x}>Métricas de {x} días</option>)}</select>}
      </div>

      {d && tab === "beneficios" && (d.beneficios.length ? (
        <div className="tarjeta overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="border-b border-crema-300 text-left text-xs text-slate-500"><th className="p-3">Beneficio</th><th className="p-3">Aliado</th><th className="p-3">Estado</th><th className="p-3 text-right">Vistas</th><th className="p-3 text-right">Canjes</th><th className="p-3 text-right">Despachos</th><th /></tr></thead>
          <tbody>{d.beneficios.map((b: any) => (
            <tr key={b.id} className="border-b border-crema-200 last:border-0">
              <td className="p-3"><b className="text-marino">{b.resumen}</b> · {b.titulo}{b.destacado && " ★"}<span className="block text-xs text-slate-500">{d.categorias[b.categoria]}{!b.en_fechas && " · fuera de vigencia"}</span></td>
              <td className="p-3 text-slate-600">{nombreAliado(b.aliado_id)}</td><td className="p-3"><Chip e={b.estado} m={EST_BENEF} /></td>
              <td className="p-3 text-right tabular-nums">{b.metricas.vistas}</td><td className="p-3 text-right tabular-nums">{b.metricas.canjes}</td><td className="p-3 text-right tabular-nums">{b.metricas.despachos}</td>
              <td className="p-3 text-right"><button className="text-xs font-semibold text-turquesa-700" onClick={() => setBenef(b)}>Editar</button></td></tr>))}</tbody></table></div>
      ) : <Vacio t="Aún no hay beneficios" d={d.aliados.length ? "Cree el primero con «+ Beneficio»." : "Primero dé de alta un aliado con «+ Aliado»."} />)}

      {d && tab === "aliados" && (d.aliados.length ? (
        <div className="grid gap-3 md:grid-cols-2">{d.aliados.map((a: any) => (
          <div key={a.id} className="tarjeta flex items-start gap-3 p-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {a.logo && a.estado === "activo" ? <img src={`/api/club-publico/logos/${a.id}`} alt="" className="h-12 w-12 rounded-lg object-contain ring-1 ring-crema-300" />
              : <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-crema text-lg font-bold text-marino">{a.nombre[0]}</span>}
            <div className="min-w-0 flex-1"><p className="font-bold text-marino">{a.nombre} <Chip e={a.estado} m={EST_ALIADO} /></p>
              <p className="text-xs text-slate-500">{[a.giro, a.contacto_nombre, a.contacto_email, a.contacto_telefono].filter(Boolean).join(" · ")}</p>
              <p className="text-xs text-slate-500">{a.beneficios} beneficio(s)</p></div>
            <button className="text-xs font-semibold text-turquesa-700" onClick={() => setAliado(a)}>Editar</button></div>))}</div>
      ) : <Vacio t="Aún no hay aliados" d="Dé de alta la primera empresa con «+ Aliado», o conviértala desde una postulación." />)}

      {d && tab === "solicitudes" && (d.solicitudes.length ? (
        <div className="space-y-3">{d.solicitudes.map((s: any) => (
          <div key={s.id} className="tarjeta p-4"><div className="flex flex-wrap items-start justify-between gap-2">
            <div><p className="font-bold text-marino">{s.empresa}{s.giro && <span className="font-normal text-slate-500"> · {s.giro}</span>}</p>
              <p className="text-sm text-slate-600">{s.nombre} · <a className="text-turquesa-700" href={`mailto:${s.email}`}>{s.email}</a>{s.telefono && ` · ${s.telefono}`}</p>
              {s.propuesta && <p className="mt-1 text-sm text-slate-700">«{s.propuesta}»</p>}
              <p className="text-xs text-slate-400">{new Date(s.creado_en).toLocaleString("es-MX")}</p></div>
            <div className="flex items-center gap-2">
              <select className="campo w-auto text-sm" value={s.estado} onChange={(e) => apiP.patch(`/club/solicitudes/${s.id}`, { estado: e.target.value }).then(() => hecho("Postulación actualizada."))} aria-label="Estado">
                {Object.entries(EST_SOL).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
              {s.estado !== "aliado" && <button className="btn-sec text-xs" onClick={() => setAliado({ nombre: s.empresa, giro: s.giro, contacto_nombre: s.nombre, contacto_email: s.email, contacto_telefono: s.telefono, estado: "prospecto", solicitud_id: s.id })}>Convertir en aliado</button>}</div>
          </div></div>))}</div>
      ) : <Vacio t="Sin postulaciones" d="Las empresas se postulan desde nomirasoft.com/aliados." />)}

      {aliado && <EditorAliado a={aliado} onCerrar={() => setAliado(null)} onListo={(t) => { setAliado(null); hecho(t); }} />}
      {benef && d && <EditorBeneficio b={benef} d={d} onCerrar={() => setBenef(null)} onListo={(t) => { setBenef(null); setTab("beneficios"); hecho(t); }} />}
    </ShellPlataforma>
  );
}

const Vacio = ({ t, d }: { t: string; d: string }) => <div className="tarjeta p-10 text-center"><p className="font-bold text-marino">{t}</p><p className="mt-1 text-sm text-slate-500">{d}</p></div>;

function EditorAliado({ a, onCerrar, onListo }: { a: any; onCerrar: () => void; onListo: (t: string) => void }) {
  const [f, setF] = useState<any>({ nombre: "", giro: "", sitio: "", contacto_nombre: "", contacto_email: "", contacto_telefono: "", notas: "", ...a });
  const [logo, setLogo] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [borrar, setBorrar] = useState(false);
  const c = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const guardar = async () => {
    try {
      const cuerpo = { nombre: f.nombre, giro: f.giro, sitio: f.sitio, contacto_nombre: f.contacto_nombre, contacto_email: f.contacto_email,
        contacto_telefono: f.contacto_telefono, estado: f.estado, notas: f.notas, solicitud_id: f.solicitud_id };
      const r = a.id ? await apiP.put(`/club/aliados/${a.id}`, cuerpo) : await apiP.post("/club/aliados", cuerpo);
      if (logo) { const fd = new FormData(); fd.append("archivo", logo); await apiP.subirPut(`/club/aliados/${r.id}/logo`, fd); }
      onListo(a.id ? "Aliado actualizado." : "Aliado creado.");
    } catch (e: any) { setError(e.message); }
  };
  return (
    <Modal titulo={a.id ? "Editar aliado" : "Nuevo aliado"} onCerrar={onCerrar} ancho="max-w-xl">
      <Aviso>{error}</Aviso>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="sm:col-span-2"><span className="etiqueta">Empresa</span><input className="campo" value={f.nombre} onChange={c("nombre")} /></label>
        <label><span className="etiqueta">Giro</span><input className="campo" value={f.giro || ""} onChange={c("giro")} /></label>
        <label><span className="etiqueta">Sitio web</span><input className="campo" value={f.sitio || ""} onChange={c("sitio")} placeholder="https://" /></label>
        <label><span className="etiqueta">Contacto</span><input className="campo" value={f.contacto_nombre || ""} onChange={c("contacto_nombre")} /></label>
        <label><span className="etiqueta">Correo del contacto</span><input className="campo" value={f.contacto_email || ""} onChange={c("contacto_email")} /></label>
        <label><span className="etiqueta">Teléfono</span><input className="campo" value={f.contacto_telefono || ""} onChange={c("contacto_telefono")} /></label>
        <label><span className="etiqueta">Estado</span><select className="campo" aria-label="Estado del aliado" value={f.estado} onChange={c("estado")}>{Object.entries(EST_ALIADO).map(([k, [t]]) => <option key={k} value={k}>{t}</option>)}</select>
          <span className="mt-1 block text-[11px] text-slate-500">Solo los aliados «Activos» muestran sus beneficios.</span></label>
        <label className="sm:col-span-2"><span className="etiqueta">Logotipo (PNG, JPG o WebP)</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setLogo(e.target.files?.[0] || null)} className="text-sm" /></label>
        <label className="sm:col-span-2"><span className="etiqueta">Notas internas (convenio, comisiones…)</span><textarea className="campo" rows={3} value={f.notas || ""} onChange={c("notas")} /></label>
      </div>
      <div className="mt-4 flex items-center gap-2">
        {a.id && (borrar ? <button className="text-xs font-semibold text-red-600" onClick={() => apiP.borrar(`/club/aliados/${a.id}`).then(() => onListo("Aliado eliminado."))}>Confirmar: borrar aliado y sus beneficios</button>
          : <button className="text-xs font-semibold text-red-600" onClick={() => setBorrar(true)}>Eliminar</button>)}
        <button className="btn-sec ml-auto" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa" disabled={!f.nombre?.trim()} onClick={guardar}>Guardar</button></div>
    </Modal>
  );
}

function EditorBeneficio({ b, d, onCerrar, onListo }: { b: any; d: any; onCerrar: () => void; onListo: (t: string) => void }) {
  const [f, setF] = useState<any>({ titulo: "", resumen: "", descripcion: "", codigo: "", enlace: "", condiciones: "", vigente_desde: "", vigente_hasta: "", destacado: false, cobertura: null, ...b });
  const [error, setError] = useState("");
  const [borrar, setBorrar] = useState(false);
  const c = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const guardar = async () => {
    try {
      const cuerpo = { aliado_id: Number(f.aliado_id), titulo: f.titulo, resumen: f.resumen, descripcion: f.descripcion, categoria: f.categoria, canje: f.canje,
        codigo: f.codigo, enlace: f.enlace, condiciones: f.condiciones, cobertura: f.cobertura, vigente_desde: f.vigente_desde || null,
        vigente_hasta: f.vigente_hasta || null, destacado: !!f.destacado, estado: f.estado };
      if (b.id) await apiP.put(`/club/beneficios/${b.id}`, cuerpo); else await apiP.post("/club/beneficios", cuerpo);
      onListo(b.id ? "Beneficio actualizado." : "Beneficio creado.");
    } catch (e: any) { setError(e.message); }
  };
  const aliadoActivo = d.aliados.find((a: any) => a.id === Number(f.aliado_id))?.estado === "activo";
  return (
    <Modal titulo={b.id ? "Editar beneficio" : "Nuevo beneficio"} onCerrar={onCerrar} ancho="max-w-2xl">
      <Aviso>{error}</Aviso>
      <div className="grid gap-3 sm:grid-cols-2">
        <label><span className="etiqueta">Aliado</span><select className="campo" value={f.aliado_id} onChange={c("aliado_id")}>{d.aliados.map((a: any) => <option key={a.id} value={a.id}>{a.nombre}</option>)}</select></label>
        <label><span className="etiqueta">Categoría</span><select className="campo" value={f.categoria} onChange={c("categoria")}>{Object.entries(d.categorias).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
        <label><span className="etiqueta">Beneficio en corto</span><input className="campo" maxLength={80} value={f.resumen} onChange={c("resumen")} placeholder="20% de descuento" /></label>
        <label><span className="etiqueta">Título</span><input className="campo" maxLength={150} value={f.titulo} onChange={c("titulo")} placeholder="Seguro de gastos médicos para despachos" /></label>
        <label className="sm:col-span-2"><span className="etiqueta">Descripción</span><textarea className="campo" rows={3} value={f.descripcion || ""} onChange={c("descripcion")} /></label>
        <label><span className="etiqueta">Cómo se canjea</span><select className="campo" aria-label="Cómo se canjea" value={f.canje} onChange={c("canje")}>{Object.entries(d.canjes).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
        {f.canje === "codigo" && <label><span className="etiqueta">Código</span><input className="campo font-mono" value={f.codigo || ""} onChange={c("codigo")} /></label>}
        <label className={f.canje === "codigo" ? "sm:col-span-2" : ""}><span className="etiqueta">Enlace {f.canje === "enlace" ? "" : "(opcional)"}</span><input className="campo" value={f.enlace || ""} onChange={c("enlace")} placeholder="https://" /></label>
        <label><span className="etiqueta">Vigente desde</span><input type="date" className="campo" value={f.vigente_desde || ""} onChange={c("vigente_desde")} /></label>
        <label><span className="etiqueta">Vigente hasta</span><input type="date" className="campo" value={f.vigente_hasta || ""} onChange={c("vigente_hasta")} /></label>
        <label className="sm:col-span-2"><span className="etiqueta">Dónde aplica</span>
          <select className="campo" aria-label="Entidades donde aplica" multiple size={4} value={f.cobertura || []} onChange={(e) => { const v = Array.from(e.target.selectedOptions).map((o) => o.value); setF({ ...f, cobertura: v.length ? v : null }); }}>
            {d.entidades.map((x: string) => <option key={x} value={x}>{x}</option>)}</select>
          <span className="mt-1 block text-[11px] text-slate-500">Sin selección = todo México. Ctrl/Cmd para elegir varios.</span></label>
        <label className="sm:col-span-2"><span className="etiqueta">Condiciones</span><textarea className="campo" rows={2} value={f.condiciones || ""} onChange={c("condiciones")} /></label>
        <label><span className="etiqueta">Estado</span><select className="campo" aria-label="Estado del beneficio" value={f.estado} onChange={c("estado")}>{Object.entries(EST_BENEF).map(([k, [t]]) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={!!f.destacado} onChange={(e) => setF({ ...f, destacado: e.target.checked })} /> Destacado (aparece primero)</label>
      </div>
      {f.estado === "publicado" && !aliadoActivo && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">El aliado no está «Activo»: este beneficio no se verá hasta que lo active.</p>}
      <div className="mt-4 flex items-center gap-2">
        {b.id && (borrar ? <button className="text-xs font-semibold text-red-600" onClick={() => apiP.borrar(`/club/beneficios/${b.id}`).then(() => onListo("Beneficio eliminado."))}>Confirmar: borrar</button>
          : <button className="text-xs font-semibold text-red-600" onClick={() => setBorrar(true)}>Eliminar</button>)}
        <button className="btn-sec ml-auto" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa" disabled={!f.titulo?.trim() || !f.resumen?.trim()} onClick={guardar}>Guardar</button></div>
    </Modal>
  );
}
