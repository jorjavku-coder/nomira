"use client";
import { useEffect, useState } from "react";
import { ComercialShell, useCatalogoCM } from "@/components/comercial";
import { Aviso, Modal } from "@/components/ui";
import { fechaHora, mxn } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

const ESTADO: Record<string, string> = { activo: "bg-emerald-100 text-emerald-800", inactivo: "bg-amber-100 text-amber-800", archivado: "bg-slate-200 text-slate-600" };
const CAMPO: Record<string, string> = { precio_mensual: "Precio mensual", modulos_incluidos: "Módulos incluidos", usuarios: "Usuarios", almacenamiento_gb: "Almacenamiento (GB)",
  estado: "Estado", activo: "Activo", unidad_gb: "GB por bloque", nombre: "Nombre", descripcion: "Descripción", ciclo: "Ciclo", iva_pct: "IVA %", orden: "Orden" };

export default function Paquetes() {
  const [cat, err, recargar] = useCatalogoCM();
  const [hist, setHist] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [edit, setEdit] = useState<any>(null);
  const [precios, setPrecios] = useState<Record<number, any>>({});
  const [alm, setAlm] = useState<any>(null);
  const cargarHist = () => { apiP.get("/comercial/historial-precios").then(setHist).catch(() => {}); apiP.get("/comercial/almacenamiento").then(setAlm).catch(() => {}); };
  useEffect(() => { cargarHist(); }, []);
  useEffect(() => { if (cat) setPrecios(Object.fromEntries(cat.precios.map((p: any) => [p.id, { ...p }]))); }, [cat]);
  async function hacer(fn: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { await fn(); setOk(msg); recargar(); cargarHist(); return true; } catch (e: any) { setError(e.message); return false; }
  }
  return (
    <ComercialShell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Paquetes y precios</h1>
          <p className="mt-1 text-sm text-slate-500">Precios antes de IVA. Cambiarlos no altera cotizaciones ya enviadas ni condiciones de clientes existentes.</p></div>
        <button className="btn-turquesa" onClick={() => setEdit({ nombre: "", descripcion: "", precio_mensual: "", modulos_incluidos: 1, usuarios: 5, almacenamiento_gb: 20, ciclo: "mensual", iva_pct: null, orden: 9 })}>+ Nuevo paquete</button>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{err || error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {cat && <>
        <div className="grid gap-4 md:grid-cols-3">
          {cat.paquetes.map((p: any) => (
            <article key={p.id} className={`tarjeta p-5 ${p.estado === "archivado" ? "opacity-60" : ""}`}>
              <div className="flex items-center justify-between"><h2 className="text-lg font-bold text-marino">{p.nombre}</h2>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${ESTADO[p.estado]}`}>{p.estado}</span></div>
              <div className="mt-1 text-2xl font-extrabold text-marino">{mxn(p.precio_mensual)} <span className="text-xs font-medium text-slate-500">/mes + IVA</span></div>
              <ul className="mt-2 text-sm text-slate-600"><li>{p.modulos_incluidos} módulo(s) incluidos</li><li>{p.usuarios} usuarios internos</li><li>{p.almacenamiento_gb} GB{(() => { const c = alm?.paquetes.find((x: any) => x.id === p.id); return c ? <span className="block text-xs text-slate-500">te cuestan {mxn(c.costo_mxn)}/mes en Render ({c.pct_del_precio}% del precio)</span> : null; })()}</li>
                <li>IVA {p.iva_pct ? `${Number(p.iva_pct)}% (propio)` : `${Number(cat.config.iva_pct)}% (general)`}</li></ul>
              <div className="mt-3 flex flex-wrap gap-2">
                {p.estado !== "archivado" && <button className="btn-sec py-1 text-xs" onClick={() => setEdit(p)}>Editar</button>}
                {p.estado !== "activo" && <button className="btn-sec py-1 text-xs" onClick={() => hacer(() => apiP.post(`/comercial/paquetes/${p.id}/estado`, { estado: "activo" }), `${p.nombre} activado.`)}>Activar</button>}
                {p.estado === "activo" && <button className="btn-sec py-1 text-xs" onClick={() => hacer(() => apiP.post(`/comercial/paquetes/${p.id}/estado`, { estado: "inactivo" }), `${p.nombre} desactivado.`)}>Desactivar</button>}
                {p.estado !== "archivado" && <button className="btn-sec py-1 text-xs" onClick={() => hacer(() => apiP.post(`/comercial/paquetes/${p.id}/estado`, { estado: "archivado" }), `${p.nombre} archivado.`)}>Archivar</button>}
              </div>
            </article>))}
        </div>
        <section className="tarjeta mt-6 p-5">
          <h2 className="font-semibold text-marino">Precios de adicionales (al mes, antes de IVA)</h2>
          <div className="mt-3 divide-y divide-crema-300">
            {cat.precios.map((p: any) => {
              const v = precios[p.id] || p;
              const cambio = v.precio_mensual !== p.precio_mensual || v.activo !== p.activo || v.unidad_gb !== p.unidad_gb;
              return (
                <div key={p.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                  <span className="min-w-[14rem] flex-1 font-medium text-marino">{p.nombre}</span>
                  <label className="flex items-center gap-1">$<input className="campo w-28 py-1" inputMode="decimal" aria-label={`Precio de ${p.nombre}`} value={v.precio_mensual}
                    onChange={(e) => setPrecios({ ...precios, [p.id]: { ...v, precio_mensual: e.target.value } })} /></label>
                  {p.clave === "almacenamiento" && <label className="flex items-center gap-1">por <input className="campo w-20 py-1" type="number" min={1} aria-label="GB por bloque" value={v.unidad_gb || ""}
                    onChange={(e) => setPrecios({ ...precios, [p.id]: { ...v, unidad_gb: Number(e.target.value) || null } })} /> GB</label>}
                  <label className="flex items-center gap-1"><input type="checkbox" className="accent-turquesa" checked={v.activo} onChange={(e) => setPrecios({ ...precios, [p.id]: { ...v, activo: e.target.checked } })} />Activo</label>
                  <button className="btn-sec py-1 text-xs" disabled={!cambio} onClick={() => hacer(() => apiP.patch(`/comercial/precios/${p.id}`, { precio_mensual: v.precio_mensual, activo: v.activo, unidad_gb: v.unidad_gb }), `${p.nombre}: guardado.`)}>Guardar</button>
                </div>);
            })}
          </div>
        </section>
        {alm && <Almacenamiento alm={alm} hacer={hacer} onCambio={setAlm} />}
        <section className="tarjeta mt-6 p-5">
          <h2 className="font-semibold text-marino">Historial de cambios de precios</h2>
          {!hist.length ? <p className="mt-2 text-sm text-slate-500">Sin cambios registrados.</p> : (
            <div className="mt-2 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase tracking-wider text-slate-500"><th className="py-2">Fecha</th><th>Concepto</th><th>Campo</th><th>Antes</th><th>Después</th><th>Por</th></tr></thead>
              <tbody className="divide-y divide-crema-300">{hist.map((h) => <tr key={h.id}><td className="py-1.5 text-xs">{fechaHora(h.fecha)}</td><td>{h.nombre}</td><td>{CAMPO[h.campo] || h.campo}</td><td>{h.antes ?? "—"}</td><td className="font-semibold">{h.despues ?? "—"}</td><td>{h.por || "—"}</td></tr>)}</tbody></table></div>)}
        </section>
      </>}
      {edit && <EditarPaquete p={edit} onCerrar={() => setEdit(null)} onGuardar={async (d) => {
        if (await hacer(() => edit.id ? apiP.patch(`/comercial/paquetes/${edit.id}`, d) : apiP.post("/comercial/paquetes", d), edit.id ? "Paquete actualizado." : "Paquete creado (inactivo hasta que lo active).")) setEdit(null);
      }} />}
    </ComercialShell>
  );
}

function EditarPaquete({ p, onCerrar, onGuardar }: { p: any; onCerrar: () => void; onGuardar: (d: any) => void }) {
  const [f, setF] = useState({ ...p, iva_pct: p.iva_pct ?? "" });
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return <Modal titulo={p.id ? `Editar ${p.nombre}` : "Nuevo paquete"} onCerrar={onCerrar} ancho="max-w-xl">
    <div className="grid gap-3 sm:grid-cols-2">
      <label><span className="etiqueta">Nombre</span><input className="campo" value={f.nombre} onChange={set("nombre")} /></label>
      <label><span className="etiqueta">Precio mensual (antes de IVA)</span><input className="campo" inputMode="decimal" value={f.precio_mensual} onChange={set("precio_mensual")} /></label>
      <label><span className="etiqueta">Módulos incluidos</span><input className="campo" type="number" min={1} max={5} value={f.modulos_incluidos} onChange={set("modulos_incluidos")} /></label>
      <label><span className="etiqueta">Usuarios internos</span><input className="campo" type="number" min={1} value={f.usuarios} onChange={set("usuarios")} /></label>
      <label><span className="etiqueta">Almacenamiento (GB)</span><input className="campo" type="number" min={1} value={f.almacenamiento_gb} onChange={set("almacenamiento_gb")} /></label>
      <label><span className="etiqueta">Ciclo de cobro base</span><select className="campo" value={f.ciclo} onChange={set("ciclo")}><option value="mensual">Mensual</option><option value="semestral">Semestral</option><option value="anual">Anual</option></select></label>
      <label><span className="etiqueta">IVA propio % (vacío = general)</span><input className="campo" inputMode="decimal" value={f.iva_pct} onChange={set("iva_pct")} /></label>
      <label><span className="etiqueta">Orden</span><input className="campo" type="number" value={f.orden} onChange={set("orden")} /></label>
      <label className="sm:col-span-2"><span className="etiqueta">Descripción (opcional)</span><input className="campo" maxLength={500} value={f.descripcion || ""} onChange={set("descripcion")} /></label>
    </div>
    <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
      <button className="btn-turquesa" onClick={() => onGuardar({ nombre: f.nombre, descripcion: f.descripcion || null, precio_mensual: f.precio_mensual, modulos_incluidos: Number(f.modulos_incluidos),
        usuarios: Number(f.usuarios), almacenamiento_gb: Number(f.almacenamiento_gb), ciclo: f.ciclo, iva_pct: f.iva_pct === "" ? null : f.iva_pct, orden: Number(f.orden) || 0 })}>Guardar</button></div>
  </Modal>;
}

/** Lo que cuesta el disco en Render y cómo se traslada al precio del almacenamiento adicional. */
function Almacenamiento({ alm, hacer, onCambio }: { alm: any; hacer: (fn: () => Promise<any>, msg: string) => Promise<boolean>; onCambio: (x: any) => void }) {
  const [f, setF] = useState({ ...alm.config });
  useEffect(() => setF({ ...alm.config }), [alm]);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const b = alm.bloque, d = alm.disco;
  const distinto = b.precio_actual !== null && Number(b.precio_actual) !== Number(b.precio_sugerido);
  return (
    <section className="tarjeta mt-6 p-5">
      <h2 className="font-semibold text-marino">Almacenamiento: lo que te cobra Render y lo que paga tu cliente</h2>
      <p className="mt-1 text-sm text-slate-500">Render cobra el disco por GB al mes, en dólares, aunque no esté lleno. Aquí calculas el precio del bloque de almacenamiento para que ese costo lo pague el cliente.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label><span className="etiqueta">Costo de Render por GB al mes (USD)</span><input className="campo" inputMode="decimal" value={f.costo_gb_usd} onChange={set("costo_gb_usd")} /></label>
        <label><span className="etiqueta">Tipo de cambio (MXN por dólar)</span><input className="campo" inputMode="decimal" value={f.tipo_cambio} onChange={set("tipo_cambio")} /></label>
        <label><span className="etiqueta">Margen sobre el costo (%)</span><input className="campo" inputMode="decimal" value={f.margen_almacenamiento_pct} onChange={set("margen_almacenamiento_pct")} /></label>
        <label><span className="etiqueta">Tamaño de tu disco en Render (GB)</span><input className="campo" type="number" min={1} value={f.disco_gb} onChange={set("disco_gb")} /></label>
      </div>
      <p className="mt-1 text-xs text-slate-500">El margen cubre el espacio libre que pagas aunque no se use, las descargas de videos, la comisión de Stripe y la variación del dólar.</p>
      <button className="btn-sec mt-2" onClick={async () => { let x: any; if (await hacer(async () => { x = await apiP.put("/comercial/almacenamiento", { ...f, disco_gb: Number(f.disco_gb) }); }, "Costos de almacenamiento guardados.")) onCambio(x); }}>Guardar y recalcular</button>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl bg-crema/60 p-4 text-sm">
          <p>1 GB te cuesta <b>{mxn(alm.costo_gb_mxn)}</b> al mes.</p>
          <p>Un bloque de {b.gb} GB te cuesta <b>{mxn(b.costo_mxn)}</b> al mes.</p>
          <p className="mt-2 text-base">Precio sugerido del bloque: <b className="text-marino">{mxn(b.precio_sugerido)}</b> + IVA</p>
          {b.precio_actual !== null && <p className="text-slate-600">Hoy lo cobras en {mxn(b.precio_actual)} (margen de {b.margen_actual_pct}%).</p>}
          {distinto && b.id && <button className="btn-turquesa mt-2" onClick={() => hacer(() => apiP.patch(`/comercial/precios/${b.id}`, { precio_mensual: b.precio_sugerido, activo: true, unidad_gb: b.gb }), "Precio del bloque actualizado.")}>Usar {mxn(b.precio_sugerido)}</button>}
        </div>
        <div className={`rounded-xl p-4 text-sm ${d.ampliar ? "bg-amber-50 text-amber-900" : "bg-emerald-50 text-emerald-900"}`}>
          <p>Tu disco: <b>{d.disco_gb} GB</b> ({mxn(d.costo_disco_mxn)} al mes, {d.costo_disco_usd} USD).</p>
          <p>Espacio que ya vendiste a tus clientes: <b>{d.contratado_gb} GB</b>. En uso real: <b>{d.usado_gb} GB</b>.</p>
          {d.ampliar ? <p className="mt-2 font-semibold">Amplía tu disco en Render a {d.recomendado_gb} GB (unos {d.costo_recomendado_usd} USD al mes). En Render: tu servicio → Disks → cambia el tamaño. Se puede agrandar, pero no achicar.</p>
            : <p className="mt-2">Tu disco alcanza para lo que has vendido.</p>}
        </div>
      </div>

      {d.organizaciones.length > 0 && <div className="mt-4 overflow-x-auto"><table className="w-full text-sm">
        <thead><tr className="text-left text-xs uppercase tracking-wider text-slate-500"><th className="py-2">Despacho</th><th>Contratado</th><th>En uso</th><th>%</th></tr></thead>
        <tbody className="divide-y divide-crema-300">{d.organizaciones.map((o: any) => <tr key={o.id}>
          <td className="py-1.5">{o.nombre}</td><td>{o.contratado_gb ? `${o.contratado_gb} GB` : <span className="text-slate-400">Sin plan asignado</span>}</td>
          <td>{o.usado_mb >= 1024 ? `${(o.usado_mb / 1024).toFixed(1)} GB` : `${o.usado_mb} MB`}</td>
          <td className={o.pct >= 90 ? "font-semibold text-red-700" : ""}>{o.pct ?? "—"}{o.pct !== null && "%"}</td></tr>)}</tbody></table>
        <p className="mt-1 text-xs text-slate-500">Solo se mide el tamaño de los archivos; nunca su contenido. Cuando un despacho llega a su límite, Academia ya no le deja subir videos ni SCORM hasta que contrate más espacio; sus expedientes y evidencia no se bloquean.</p></div>}
    </section>
  );
}
