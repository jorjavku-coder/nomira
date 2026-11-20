"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { COLOR_ESTADO, ComercialShell } from "@/components/comercial";
import { Aviso } from "@/components/ui";
import { fecha, mxn } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

const ESTADOS_ASIG: Record<string, string> = { activa: "Activa", impago: "Impago (en revisión)", vencida: "Vencida", cancelada: "Cancelada" };

export default function ResumenComercial() {
  const hoy = new Date();
  const ini = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}-01`;
  const fin = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}-${String(hoy.getDate()).padStart(2, "0")}`;
  const [p, setP] = useState({ desde: ini, hasta: fin });
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const cargar = useCallback(() => apiP.get(`/comercial/resumen?desde=${p.desde}&hasta=${p.hasta}`).then(setR).catch((e) => setError(e.message)), [p]);
  useEffect(() => { cargar(); }, [cargar]);
  const visibles = ["borrador", "revision", "enviada", "vista", "aceptada", "pendiente_pago", "pagada", "vencida", "cancelada"];
  return (
    <ComercialShell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-marino">Resumen comercial</h1>
          <p className="mt-1 text-sm text-slate-500">Cifras reales de las cotizaciones registradas en Nomira. Si no hay datos, no se muestran importes.</p>
        </div>
        <Link href="/plataforma/comercial/cotizaciones/nueva" className="btn-turquesa">+ Nueva cotización</Link>
      </div>
      <Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
      {r && <>
        {r.total_cotizaciones === 0
          ? <div className="tarjeta p-8 text-center"><p className="font-semibold text-marino">Aún no hay cotizaciones.</p>
              <p className="mt-1 text-sm text-slate-500">Cree la primera para empezar a ver el resumen.</p></div>
          : <>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {visibles.map((k) => {
                const e = r.estados.find((x: any) => x.clave === k);
                return (
                  <Link key={k} href={`/plataforma/comercial/cotizaciones?estado=${k}`} className="tarjeta p-4 transition hover:-translate-y-0.5">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${COLOR_ESTADO[k]}`}>{e.nombre}</span>
                    <div className="mt-2 text-3xl font-extrabold text-marino">{e.n}</div>
                  </Link>);
              })}
              <div className="tarjeta p-4"><span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">Próximas a vencer (3 días)</span>
                <div className="mt-2 text-3xl font-extrabold text-marino">{r.proximas_a_vencer}</div></div>
              <div className="tarjeta p-4"><span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-semibold text-sky-800">Ajustes pedidos por clientes</span>
                <div className="mt-2 text-3xl font-extrabold text-marino">{r.ajustes_pendientes}</div></div>
            </div>
            <section className="tarjeta mt-6 p-5">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <h2 className="font-semibold text-marino">Importes del periodo (con IVA)</h2>
                <div className="flex gap-2">
                  <label><span className="etiqueta">Desde</span><input type="date" className="campo" value={p.desde} onChange={(e) => setP({ ...p, desde: e.target.value })} /></label>
                  <label><span className="etiqueta">Hasta</span><input type="date" className="campo" value={p.hasta} onChange={(e) => setP({ ...p, hasta: e.target.value })} /></label>
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {[["cotizado", "Cotizado (versiones enviadas)"], ["aceptado", "Aceptado por clientes"], ["cobrado", "Cobrado (pagos confirmados)"]].map(([k, t]) => (
                  <div key={k} className="rounded-2xl bg-crema p-4">
                    <div className="etiqueta">{t}</div>
                    {r.importes[k].n ? <><div className="text-2xl font-extrabold text-marino">{mxn(r.importes[k].monto)}</div>
                      <div className="text-xs text-slate-500">{r.importes[k].n} registro(s)</div></>
                      : <div className="text-sm text-slate-500">Sin datos en el periodo</div>}
                  </div>))}
              </div>
            </section>
          </>}
        <section className="tarjeta mt-6 p-5">
          <h2 className="font-semibold text-marino">Paquetes asignados a despachos</h2>
          <p className="text-sm text-slate-500">Cambiar el estado comercial nunca borra ni oculta expedientes o documentos del despacho.</p>
          {!r.asignaciones.length ? <p className="mt-3 text-sm text-slate-500">Todavía no hay asignaciones.</p> : (
            <div className="mt-3 overflow-x-auto"><table className="w-full text-sm">
              <thead><tr className="text-left text-xs uppercase tracking-wider text-slate-500"><th className="py-2">Despacho</th><th>Paquete</th><th>Capacidad</th><th>Inicio</th><th>Renovación</th><th>Origen</th><th>Estado</th></tr></thead>
              <tbody className="divide-y divide-crema-300">{r.asignaciones.map((a: any) => (
                <tr key={a.id}>
                  <td className="py-2 font-semibold text-marino"><Link className="hover:underline" href={`/plataforma/clientes/${a.organizacion_id}`}>{a.organizacion}</Link></td>
                  <td>{a.paquete} · {mxn(a.monto)}</td><td>{a.usuarios} usuarios · {a.almacenamiento_gb} GB</td>
                  <td>{fecha(a.inicio)}</td><td>{fecha(a.renovacion)}</td><td>{a.origen === "promocional" ? "Promocional" : "Pago"}</td>
                  <td><select aria-label={`Estado de ${a.organizacion}`} className="campo w-auto py-1" value={a.estado} onChange={async (e) => {
                    setError(""); setOk("");
                    try { await apiP.patch(`/comercial/asignaciones/${a.id}`, { estado: e.target.value }); setOk("Estado actualizado. Los datos del despacho no se tocaron."); cargar(); }
                    catch (x: any) { setError(x.message); }
                  }}>{Object.entries(ESTADOS_ASIG).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></td>
                </tr>))}</tbody>
            </table></div>)}
        </section>
      </>}
    </ComercialShell>
  );
}
