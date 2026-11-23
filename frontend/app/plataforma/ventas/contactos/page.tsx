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
  function exportar() {
    const filas = [["Nombre", "Despacho", "Cargo", "Correo", "Teléfono", "Ciudad", "Origen", "Campaña", "Responsable", "No contactar"],
      ...(lista || []).map((c) => [c.nombre, c.despacho, c.cargo, c.email, c.telefono, c.ciudad, c.origen_texto, c.campana, c.propietario, c.no_contactar ? "Sí" : ""])];
    const csv = "﻿" + filas.map((f) => f.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); a.download = "contactos-nomira.csv"; a.click();
  }
  return (
    <VentasShell acciones={<><button className="btn-sec" onClick={exportar} disabled={!lista?.length}>Exportar CSV</button>{cat && <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo contacto</button>}</>}>
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
          {!lista.length && <tr><td colSpan={5} className="p-8 text-center text-slate-500">{q ? "Sin resultados." : "Aún no hay contactos. Las solicitudes del sitio llegan aquí solas."}</td></tr>}</tbody></table></div>}
      {nuevo && cat && <FormContacto cat={cat} onCerrar={() => setNuevo(false)} onListo={(c) => router.push(`/plataforma/ventas/contactos/${c.id}`)} />}
    </VentasShell>
  );
}
