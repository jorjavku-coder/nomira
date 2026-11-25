"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { fechaCorta } from "@/components/rh";
import { Aviso, ConfirmarEliminar, Modal } from "@/components/ui";
import { api, mxn } from "@/lib/api";

export default function Periodo() {
  const { id } = useParams<{ id: string }>();
  const [p, setP] = useState<any>(null);
  const [cfg, setCfg] = useState<any>(null);
  const [editar, setEditar] = useState<any>(null);
  const [borrar, setBorrar] = useState(false);
  const [error, setError] = useState(""); const [ok, setOk] = useState("");
  const cargar = useCallback(() => api.get(`/rh/periodos/${id}`).then(setP).catch((x) => setError(x.message)), [id]);
  useEffect(() => { cargar(); api.get("/rh/resumen").then(setCfg).catch(() => {}); }, [cargar]);
  async function hacer(f: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { await f(); setOk(msg); await cargar(); } catch (x: any) { setError(x.message); }
  }
  if (!p || !cfg) return <Shell><Aviso>{error}</Aviso></Shell>;
  const borrador = p.estado === "borrador";
  const suma = (l: any[]) => l.reduce((a, x) => a + Number(x.importe), 0);
  return (
    <Shell>
      <Link href="/rh?tab=nomina" className="text-sm font-semibold text-turquesa-700">← Nómina</Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Nómina del {fechaCorta(p.inicio)} al {fechaCorta(p.fin)}</h1>
          <p className="text-sm text-slate-600">{p.empresa} · Pago el {fechaCorta(p.fecha_pago)} · {p.empleados} empleados · Total neto <b>{mxn(p.total)}</b></p></div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => api.descargar(`/rh/periodos/${id}/excel`, "nomina.xlsx")}>Descargar Excel</button>
          {cfg.puede_editar && borrador && <button className="btn-turquesa" onClick={() => hacer(() => api.post(`/rh/periodos/${id}/cerrar`, {}), "Periodo cerrado: los empleados ya ven su recibo en su portal.")}>Cerrar y publicar recibos</button>}
          {cfg.es_admin && !borrador && <button className="btn-sec" onClick={() => hacer(() => api.post(`/rh/periodos/${id}/reabrir`, {}), "Periodo reabierto.")}>Reabrir</button>}
          {cfg.puede_editar && borrador && <button className="btn-sec" onClick={() => setBorrar(true)}>Borrar</button>}</div>
      </div>
      <div className="my-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
        {borrador && <Aviso tipo="info">Borrador: revise cada recibo y agregue bonos o retenciones (ISR, IMSS) con los datos de su contador. Al cerrar, cada empleado lo verá en su portal.</Aviso>}</div>
      <section className="tarjeta overflow-x-auto" aria-label="Recibos">
        <table className="w-full text-sm"><thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
          <th className="px-4 py-2">Empleado</th><th className="px-4 py-2">Días</th><th className="px-4 py-2">Percepciones</th><th className="px-4 py-2">Deducciones</th><th className="px-4 py-2">Neto</th><th className="px-4 py-2"><span className="sr-only">Acciones</span></th></tr></thead>
          <tbody className="divide-y divide-crema-200">{p.recibos.map((r: any) => (
            <tr key={r.id}><td className="px-4 py-3"><Link href={`/rh/empleados/${r.empleado_id}`} className="font-semibold text-marino hover:underline">{r.empleado}</Link>
              <span className="block text-xs text-slate-500">{r.puesto || ""} · {mxn(r.salario_diario)} diario</span></td>
              <td className="px-4 py-3">{r.dias_pagados}{r.faltas ? <span className="block text-xs text-amber-700">{r.faltas} falta(s)</span> : null}</td>
              <td className="px-4 py-3">{mxn(suma(r.percepciones).toFixed(2))}<span className="block text-xs text-slate-500">{r.percepciones.map((x: any) => x.concepto).join(", ")}</span></td>
              <td className="px-4 py-3">{mxn(suma(r.deducciones).toFixed(2))}{r.deducciones.length > 0 && <span className="block text-xs text-slate-500">{r.deducciones.map((x: any) => x.concepto).join(", ")}</span>}</td>
              <td className="px-4 py-3 font-bold text-marino">{mxn(r.neto)}{r.visto && <span className="block text-xs font-normal text-emerald-700">✓ Lo descargó</span>}</td>
              <td className="px-4 py-3 text-right text-xs"><span className="flex justify-end gap-3">
                {cfg.puede_editar && borrador && <button className="font-semibold text-turquesa-700 underline" onClick={() => setEditar(r)}>Ajustar</button>}
                <button className="text-slate-600 underline" onClick={() => api.descargar(`/rh/recibos/${r.id}/pdf`, "recibo.pdf")}>PDF</button></span></td></tr>))}</tbody></table>
      </section>
      <p className="mt-3 text-xs text-slate-500">Nómina de control interno: no calcula impuestos ni timbra el CFDI de nómina. Para el timbrado, envíe el Excel a su contador o a su sistema de nómina.</p>
      {editar && <Ajustar r={editar} onCerrar={() => setEditar(null)} onListo={() => { setEditar(null); setOk("Recibo actualizado."); cargar(); }} />}
      {borrar && <ConfirmarEliminar titulo="Borrar periodo" onCerrar={() => setBorrar(false)} onConfirmar={() => api.borrar(`/rh/periodos/${id}`).then(() => { window.location.href = "/rh?tab=nomina"; })}>
        Se borran el periodo y sus recibos en borrador.</ConfirmarEliminar>}
    </Shell>
  );
}

type L = { concepto: string; importe: string };
function Ajustar({ r, onCerrar, onListo }: { r: any; onCerrar: () => void; onListo: () => void }) {
  const [per, setPer] = useState<L[]>(r.percepciones.map((x: any) => ({ ...x })));
  const [ded, setDed] = useState<L[]>(r.deducciones.map((x: any) => ({ ...x })));
  const [error, setError] = useState("");
  const total = (l: L[]) => l.reduce((a, x) => a + (Number(x.importe) || 0), 0);
  const lista = (titulo: string, l: L[], set: (x: L[]) => void, ej: string) => (
    <fieldset><legend className="text-xs font-bold uppercase tracking-wide text-slate-500">{titulo}</legend>
      {l.map((x, i) => <div key={i} className="mt-1 flex gap-2">
        <input className="campo" aria-label={`${titulo} ${i + 1}: concepto`} value={x.concepto} onChange={(e) => set(l.map((y, j) => j === i ? { ...y, concepto: e.target.value } : y))} required />
        <input className="campo w-36" aria-label={`${titulo} ${i + 1}: importe`} inputMode="decimal" value={x.importe} onChange={(e) => set(l.map((y, j) => j === i ? { ...y, importe: e.target.value } : y))} required />
        <button type="button" className="text-slate-500" aria-label="Quitar" onClick={() => set(l.filter((_, j) => j !== i))}>✕</button></div>)}
      <button type="button" className="mt-1 text-xs font-semibold text-turquesa-700 underline" onClick={() => set([...l, { concepto: "", importe: "" }])}>+ Agregar ({ej})</button></fieldset>);
  return <Modal titulo={`Recibo de ${r.empleado}`} onCerrar={onCerrar} ancho="max-w-2xl">
    <form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); setError(""); try { await api.put(`/rh/recibos/${r.id}`, { percepciones: per, deducciones: ded }); onListo(); } catch (x: any) { setError(x.message); } }}>
      {lista("Percepciones", per, setPer, "bono, horas extra, comisión")}
      {lista("Deducciones", ded, setDed, "ISR retenido, IMSS, préstamo")}
      <p className="text-right text-lg font-bold text-marino">Neto: {mxn((total(per) - total(ded)).toFixed(2))}</p>
      <Aviso>{error}</Aviso><div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
    </form></Modal>;
}
