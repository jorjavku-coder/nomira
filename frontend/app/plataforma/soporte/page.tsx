"use client";
import { useCallback, useEffect, useState } from "react";
import Conversacion from "@/components/Conversacion";
import ShellPlataforma from "@/components/plataforma";
import { Aviso } from "@/components/ui";
import { fechaHora } from "@/lib/api";
import { apiP, avisarContadores } from "@/lib/plataforma";

export default function SoportePlataforma() {
  const [lista, setLista] = useState<any[] | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [t, setT] = useState<any>(null);
  const [filtro, setFiltro] = useState<"abierto" | "cerrado" | "todas">("abierto");
  const [error, setError] = useState("");
  const cargar = useCallback(() => apiP.get("/soporte").then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => {
    cargar();
    const q = Number(new URLSearchParams(window.location.search).get("t"));
    if (q) setSel(q);
    const i = setInterval(cargar, 30000);
    return () => clearInterval(i);
  }, [cargar]);
  useEffect(() => {
    if (!sel) return;
    apiP.get(`/soporte/${sel}`).then((x) => { setT(x); avisarContadores(); cargar(); }).catch((e) => setError(e.message));
    window.history.replaceState(null, "", `/plataforma/soporte?t=${sel}`);
  }, [sel, cargar]);
  const visibles = (lista || []).filter((x) => filtro === "todas" || x.estado === filtro);
  const despues = (x: any) => { setT(x); cargar(); };
  return (
    <ShellPlataforma>
      <h1 className="text-3xl font-extrabold text-marino">Soporte</h1>
      <p className="mb-5 mt-1 text-sm text-slate-500">Mensajes de sus clientes. Ellos escriben desde la sección «Soporte» de su cuenta.</p>
      <Aviso>{error}</Aviso>
      <div className="mt-3 grid gap-4 lg:grid-cols-[22rem_1fr]">
        <section className="tarjeta overflow-hidden">
          <div className="flex gap-1 border-b border-crema-300 p-2" role="tablist">
            {([["abierto", "Abiertas"], ["cerrado", "Resueltas"], ["todas", "Todas"]] as const).map(([v, txt]) => (
              <button key={v} role="tab" aria-selected={filtro === v} onClick={() => setFiltro(v)}
                className={`flex-1 rounded-lg px-2 py-1.5 text-sm font-semibold ${filtro === v ? "bg-marino text-white" : "text-slate-600 hover:bg-crema"}`}>{txt}</button>
            ))}
          </div>
          <ul className="max-h-[70vh] divide-y divide-crema-300 overflow-y-auto">
            {lista === null && <li className="p-4 text-sm text-slate-500">Cargando…</li>}
            {lista && visibles.length === 0 && <li className="p-6 text-center text-sm text-slate-500">Sin conversaciones.</li>}
            {visibles.map((x) => (
              <li key={x.id}>
                <button onClick={() => setSel(x.id)} className={`block w-full px-4 py-3 text-left transition ${sel === x.id ? "bg-turquesa-50" : "hover:bg-crema/60"}`}>
                  <div className="flex items-center gap-2">
                    {!x.leido_plataforma && <span className="h-2 w-2 shrink-0 rounded-full bg-amber-500" aria-label="Sin leer" />}
                    <span className={`truncate text-sm ${x.leido_plataforma ? "font-medium text-slate-700" : "font-bold text-marino"}`}>{x.asunto}</span>
                  </div>
                  <div className="mt-0.5 truncate text-xs text-slate-500">{x.organizacion} · {fechaHora(x.actualizado_en)}</div>
                  {x.ultimo && <div className="mt-1 line-clamp-1 text-xs text-slate-400">{x.ultimo.autor_tipo === "plataforma" ? "Usted: " : ""}{x.ultimo.texto}</div>}
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="tarjeta overflow-hidden">
          {t ? (
            <Conversacion t={t} lado="plataforma"
              onEnviar={async (texto) => despues(await apiP.post(`/soporte/${t.id}/mensajes`, { texto }))}
              onEstado={async (estado) => despues(await apiP.patch(`/soporte/${t.id}`, { estado }))} />
          ) : <div className="flex h-full min-h-[20rem] items-center justify-center p-8 text-sm text-slate-500">Elija una conversación de la lista.</div>}
        </section>
      </div>
    </ShellPlataforma>
  );
}
