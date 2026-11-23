"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { FormContacto, useCatalogosVentas, VentasShell } from "@/components/ventas";
import { Aviso } from "@/components/ui";
import { apiP } from "@/lib/plataforma";

export default function Contactos() {
  const cat = useCatalogosVentas();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const cargar = useCallback(() => apiP.get(`/ventas/contactos?q=${encodeURIComponent(q)}`).then(setLista).catch((e) => setError(e.message)), [q]);
  useEffect(() => { const t = setTimeout(cargar, 200); return () => clearTimeout(t); }, [cargar]);
  async function exportar() {
    try { const b = await apiP.blob("/ventas/leads/exportar?estado=sql"); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "contactos-sql-nomira.xlsx"; a.click(); }
    catch (e: any) { setError(e.message); }
  }
  return (
    <VentasShell acciones={<><button className="btn-sec" onClick={exportar} disabled={!lista?.length}>Exportar Excel</button>{cat && <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo contacto</button>}</>}>
      <p className="mb-3 max-w-3xl text-sm text-slate-600"><b>Contactos (SQL)</b>: personas con las que ya hubo una llamada efectiva o que aceptaron/respondieron por correo. Cada uno tiene su oportunidad en el embudo. Los prospectos sin contacto real están en <a className="font-semibold text-turquesa-700 underline" href="/plataforma/ventas/leads">Leads (MQL)</a>.</p>
      <input className="campo mb-4 max-w-sm" placeholder="Buscar por nombre, despacho, correo, teléfono o ciudad" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar contactos" />
      <Aviso>{error}</Aviso>
      {lista && <div className="tarjeta overflow-x-auto"><table className="w-full text-sm">
        <thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-2">Contacto</th><th className="px-4 py-2">Datos</th><th className="px-4 py-2">Origen</th><th className="px-4 py-2">Responsable</th><th className="px-4 py-2 text-right">Abiertas</th></tr></thead>
        <tbody className="divide-y divide-crema-200">{lista.map((c) => (
          <tr key={c.id} className="cursor-pointer hover:bg-crema/50" onClick={() => router.push(`/plataforma/ventas/contactos/${c.id}`)}>
            <td className="px-4 py-2"><Link href={`/plataforma/ventas/contactos/${c.id}`} className="font-semibold text-marino hover:underline">{c.nombre}</Link>
              <p className="text-xs text-slate-500">{c.despacho}{c.es_cliente && <span className="ml-1 rounded-full bg-emerald-100 px-2 text-emerald-800">Cliente</span>}{c.no_contactar && <span className="ml-1 rounded-full bg-red-100 px-2 text-red-700">No contactar</span>}</p></td>
            <td className="px-4 py-2 text-slate-600">{c.email}<p className="text-xs">{[c.telefono, c.ciudad].filter(Boolean).join(" · ")}</p></td>
            <td className="px-4 py-2 text-slate-600">{c.origen_texto}{c.campana && <p className="text-xs">{c.campana}</p>}</td>
            <td className="px-4 py-2 text-slate-600">{c.propietario || "—"}</td>
            <td className="px-4 py-2 text-right font-semibold">{c.oportunidades_abiertas || "—"}</td>
          </tr>))}
          {!lista.length && <tr><td colSpan={5} className="p-8 text-center text-slate-500">{q ? "Sin resultados." : "Aún no hay contactos SQL. Califique sus leads para que aparezcan aquí."}</td></tr>}</tbody></table></div>}
      {nuevo && cat && <FormContacto cat={cat} onCerrar={() => setNuevo(false)} onListo={(c) => router.push(`/plataforma/ventas/contactos/${c.id}`)} />}
    </VentasShell>
  );
}
