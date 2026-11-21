"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AgendaShell, Etq, faltanTexto, FormAsunto, SITUACION, useCatalogosAgenda } from "@/components/agenda";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

export default function Asuntos() {
  const cat = useCatalogosAgenda();
  const router = useRouter();
  const [estado, setEstado] = useState("activo");
  const [q, setQ] = useState("");
  const [filas, setFilas] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const cargar = useCallback(() => api.get(`/agenda/asuntos?estado=${estado}&q=${encodeURIComponent(q)}`).then(setFilas).catch((e) => setError(e.message)), [estado, q]);
  useEffect(() => { const t = setTimeout(cargar, 250); return () => clearTimeout(t); }, [cargar]);
  return (
    <AgendaShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Asuntos</h1><p className="mt-1 text-sm text-slate-500">Juicios y procedimientos con su tribunal, materia, actuaciones y pendientes.</p></div>
        {cat?.puede_editar && <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo asunto</button>}
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <input className="campo max-w-sm" placeholder="Buscar por nombre, número o tribunal" aria-label="Buscar" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="campo w-auto" aria-label="Estado" value={estado} onChange={(e) => setEstado(e.target.value)}><option value="activo">Activos</option><option value="concluido">Concluidos</option><option value="archivado">Archivados</option><option value="todos">Todos</option></select>
      </div>
      <Aviso>{error}</Aviso>
      {filas && (filas.length ? <div className="tarjeta divide-y divide-crema-200">{filas.map((a) => (
        <Link key={a.id} href={`/agenda/asuntos/${a.id}`} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 hover:bg-crema/40">
          <div><p className="font-semibold text-marino">{a.titulo} {a.numero && <span className="font-mono text-sm text-slate-500">· {a.numero}</span>}</p>
            <p className="text-sm text-slate-600">{a.materia_texto} · {a.tribunal || "Tribunal sin capturar"}{a.entidad ? ` · ${a.entidad}` : ""}{a.responsable ? ` · ${a.responsable}` : ""}</p></div>
          <div className="text-right text-sm">
            {a.vencidos > 0 && <Etq clase="bg-red-100 text-red-800">{a.vencidos} vencido(s)</Etq>}
            {a.proximo ? <p className="mt-1 text-slate-600">Siguiente: {a.proximo.titulo} · <span className={SITUACION[a.proximo.situacion][1] + " rounded px-1"}>{faltanTexto(a.proximo)}</span></p>
              : <p className="text-slate-400">Sin pendientes</p>}
          </div>
        </Link>))}</div> : <div className="tarjeta p-6 text-center text-sm text-slate-500">Aún no hay asuntos. Registre el primero para llevar sus plazos y audiencias.</div>)}
      {nuevo && <FormAsunto onCerrar={() => setNuevo(false)} onGuardado={(a) => router.push(`/agenda/asuntos/${a.id}`)} />}
    </AgendaShell>
  );
}
