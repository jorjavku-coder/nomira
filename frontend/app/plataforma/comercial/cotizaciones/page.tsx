"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ComercialShell, EstadoCot } from "@/components/comercial";
import { Aviso } from "@/components/ui";
import { fecha, fechaHora, mxn } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

const ESTADOS: Record<string, string> = { borrador: "Borrador", revision: "Lista para revisión", enviada: "Enviada", vista: "Vista por el cliente", aceptada: "Aceptada",
  pendiente_pago: "Pendiente de pago", pagada: "Pagada", vencida: "Vencida", cancelada: "Cancelada" };

export default function Cotizaciones() {
  const [q, setQ] = useState("");
  const [estado, setEstado] = useState("");
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { setEstado(new URLSearchParams(window.location.search).get("estado") || ""); }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      const p = new URLSearchParams();
      if (q.trim()) p.set("q", q.trim());
      if (estado) p.set("estado", estado);
      apiP.get(`/comercial/cotizaciones?${p}`).then(setLista).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [q, estado]);
  return (
    <ComercialShell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Cotizaciones</h1>
          <p className="mt-1 text-sm text-slate-500">Busque por folio, despacho, contacto o correo.</p></div>
        <Link href="/plataforma/comercial/cotizaciones/nueva" className="btn-turquesa">+ Nueva cotización</Link>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <input className="campo max-w-sm" placeholder="Buscar…" aria-label="Buscar cotizaciones" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="campo w-auto" aria-label="Filtrar por estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="">Todos los estados</option>{Object.entries(ESTADOS).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
      </div>
      <Aviso>{error}</Aviso>
      <div className="tarjeta overflow-x-auto">
        {lista && !lista.length ? <p className="p-6 text-sm text-slate-500">No hay cotizaciones con ese criterio.</p> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-crema-300 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="p-3">Folio</th><th>Despacho</th><th>Paquete</th><th className="text-right">Total</th><th className="pl-4">Estado</th><th>Vence</th><th>Actualizada</th></tr></thead>
            <tbody className="divide-y divide-crema-300">
              {lista?.map((c) => (
                <tr key={c.id} className="hover:bg-crema/60">
                  <td className="p-3"><Link className="font-semibold text-turquesa-700 hover:underline" href={`/plataforma/comercial/cotizaciones/${c.id}`}>{c.folio}</Link>
                    <span className="block text-xs text-slate-500">v{c.version}</span></td>
                  <td><span className="font-medium text-marino">{c.despacho}</span><span className="block text-xs text-slate-500">{c.contacto}</span></td>
                  <td>{c.paquete}</td><td className="text-right font-semibold">{mxn(c.total)}</td>
                  <td className="pl-4"><EstadoCot estado={c.estado} texto={c.estado_texto} /></td>
                  <td>{fecha(c.vence_en)}</td><td className="text-xs text-slate-500">{fechaHora(c.actualizado_en)}</td>
                </tr>))}
            </tbody>
          </table>)}
      </div>
    </ComercialShell>
  );
}
