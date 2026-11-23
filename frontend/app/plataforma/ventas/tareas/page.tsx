"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CompletarTarea, cuando, useCatalogosVentas, VentasShell } from "@/components/ventas";
import { Aviso } from "@/components/ui";
import { apiP, avisarContadores } from "@/lib/plataforma";

export default function Tareas() {
  const cat = useCatalogosVentas();
  const [quien, setQuien] = useState("yo");
  const [estado, setEstado] = useState("pendientes");
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [cerrar, setCerrar] = useState<any>(null);
  const cargar = useCallback(() => apiP.get(`/ventas/actividades?asignado=${quien}&estado=${estado}`).then(setLista).catch((e) => setError(e.message)), [quien, estado]);
  useEffect(() => { cargar(); }, [cargar]);
  const grupos: [string, (t: any) => boolean][] = estado === "pendientes" ? [
    ["Vencidas", (t) => t.vencida], ["Hoy", (t) => !t.vencida && new Date(t.vence_en).toDateString() === new Date().toDateString()],
    ["Próximas", (t) => !t.vencida && new Date(t.vence_en).toDateString() !== new Date().toDateString()]] : [["Hechas", () => true]];
  return (
    <VentasShell>
      <div className="mb-4 flex flex-wrap gap-2">
        <select className="campo w-auto" value={quien} onChange={(e) => setQuien(e.target.value)} aria-label="De quién">
          <option value="yo">Mías y sin asignar</option><option value="todas">Todo el equipo</option>
          {cat?.equipo.filter((x: any) => x.id !== cat.yo).map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select>
        <select className="campo w-auto" value={estado} onChange={(e) => setEstado(e.target.value)} aria-label="Estado"><option value="pendientes">Pendientes</option><option value="hechas">Hechas</option></select>
      </div>
      <Aviso>{error}</Aviso>
      {lista && !lista.length && <div className="tarjeta p-8 text-center text-sm text-slate-500">{estado === "pendientes" ? "¡Al día! No hay tareas pendientes." : "Aún no hay tareas hechas."}</div>}
      {lista && grupos.map(([titulo, f]) => {
        const xs = lista.filter(f);
        return xs.length > 0 && <section key={titulo} className="mb-5">
          <h2 className={`mb-2 text-sm font-bold uppercase tracking-wide ${titulo === "Vencidas" ? "text-red-700" : "text-slate-500"}`}>{titulo} ({xs.length})</h2>
          <ul className="tarjeta divide-y divide-crema-200">{xs.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center justify-between gap-3 p-3 text-sm">
              <div><p className="font-semibold text-marino">{t.tipo_texto}: {t.titulo}</p>
                <p className="text-slate-600">{t.oportunidad_id ? <Link className="hover:underline" href={`/plataforma/ventas/oportunidades/${t.oportunidad_id}`}>{t.oportunidad}</Link>
                  : <Link className="hover:underline" href={`/plataforma/ventas/contactos/${t.contacto_id}`}>{t.contacto}</Link>} · {t.contacto}{t.telefono ? ` · ${t.telefono}` : ""}</p>
                <p className={`text-xs ${t.vencida ? "font-semibold text-red-700" : "text-slate-500"}`}>{estado === "pendientes" ? cuando(t.vence_en) : `Hecha ${cuando(t.completada_en)}${t.resultado ? ` · ${t.resultado}` : ""}`}{t.asignado ? ` · ${t.asignado}` : ""}</p></div>
              {estado === "pendientes" && <button className="btn-sec text-sm" onClick={() => setCerrar(t)}>✓ Hecho</button>}
            </li>))}</ul></section>;
      })}
      {cerrar && <CompletarTarea tarea={cerrar} onCerrar={() => setCerrar(null)} onListo={() => { setCerrar(null); cargar(); avisarContadores(); }} />}
    </VentasShell>
  );
}
