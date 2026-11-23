"use client";
import Link from "next/link";
import BotonAyuda from "@/components/BotonAyuda";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso } from "@/components/ui";
import { FormAsunto } from "@/components/EvFormAsunto";
import { api, fecha } from "@/lib/api";

export default function Evidencia() {
  const sesion = useSesion();
  const router = useRouter();
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [filtro, setFiltro] = useState("");
  const cargar = useCallback(() => api.get("/evidencia/asuntos").then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const editor = !!sesion && sesion.usuario.rol !== "consulta";
  const visibles = (lista || []).filter((a) => !filtro || [a.nombre, a.cliente, a.tipo_caso, a.identificador_interno]
    .some((v) => (v || "").toLowerCase().includes(filtro.toLowerCase())));
  const total = (k: string) => (lista || []).reduce((s, a) => s + (a[k] || 0), 0);
  const tarjetas = [
    { t: "Asuntos", v: lista?.length ?? "—" },
    { t: "Hechos por revisar", v: lista ? total("hechos_por_revisar") : "—", alerta: total("hechos_por_revisar") > 0 },
    { t: "Puntos sin evidencia", v: lista ? total("puntos_sin_evidencia") : "—" },
    { t: "Pendientes abiertos", v: lista ? total("pendientes_abiertos") : "—" },
  ];
  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3"><h1 className="text-3xl font-extrabold text-marino">Nomira Evidencia</h1><BotonAyuda modulo="evidencia" /></div>
          <p className="mt-1 text-sm text-slate-500">Documentos ordenados, hechos con fuente, cronología y matriz de evidencia por asunto.</p>
        </div>
        {editor && <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo asunto</button>}
      </div>
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {tarjetas.map((c) => (
          <div key={c.t} className={`tarjeta p-5 ${c.alerta ? "border-amber-300 bg-amber-50" : ""}`}>
            <div className="etiqueta">{c.t}</div>
            <div className="font-marca text-3xl font-extrabold text-marino">{c.v}</div>
          </div>
        ))}
      </div>
      <Aviso>{error}</Aviso>
      {lista && lista.length > 0 && (
        <input className="campo mb-4 max-w-sm" placeholder="Buscar por asunto, cliente, tipo o identificador" value={filtro}
          onChange={(e) => setFiltro(e.target.value)} aria-label="Buscar asuntos" />
      )}
      {lista === null && !error && <p className="text-sm text-slate-500">Cargando…</p>}
      {lista?.length === 0 && (
        <div className="tarjeta p-10 text-center">
          <h2 className="font-marca text-xl font-bold text-marino">Aún no hay asuntos</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">Cree un asunto, suba los documentos del cliente y Nomira propondrá hechos con su fuente para que usted los revise.</p>
          {editor && <button className="btn-turquesa mt-5" onClick={() => setNuevo(true)}>Crear el primer asunto</button>}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibles.map((a) => (
          <Link key={a.id} href={`/evidencia/${a.id}`} className="tarjeta flex flex-col p-5 transition hover:-translate-y-0.5 hover:border-turquesa">
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-marca text-lg font-bold leading-tight text-marino">{a.nombre}</h2>
              {a.tipo_caso && <span className="shrink-0 rounded-full bg-marino-50 px-2.5 py-0.5 text-xs font-semibold text-marino">{a.tipo_caso}</span>}
            </div>
            <p className="mt-1 text-sm text-slate-600">{[a.cliente, a.identificador_interno, a.jurisdiccion_texto || a.jurisdiccion].filter(Boolean).join(" · ") || "Sin datos adicionales"}</p>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
              <div className="rounded-lg bg-crema/70 p-2"><div className="font-marca text-lg font-extrabold text-marino">{a.documentos}</div>documentos</div>
              <div className={`rounded-lg p-2 ${a.hechos_por_revisar ? "bg-amber-50 text-amber-900" : "bg-crema/70"}`}><div className="font-marca text-lg font-extrabold">{a.hechos_por_revisar}</div>por revisar</div>
              <div className="rounded-lg bg-turquesa-50 p-2 text-turquesa-700"><div className="font-marca text-lg font-extrabold">{a.hechos_confirmados}</div>revisados</div>
            </div>
            <div className="mt-3 flex flex-wrap justify-between gap-2 text-xs text-slate-500">
              <span>{a.responsable ? `Responsable: ${a.responsable}` : "Sin responsable"}</span>
              <span>{a.documentos_recibidos > 0 && <b className="mr-1 text-violet-700">{a.documentos_recibidos} del cliente por aceptar ·</b>}{a.pendientes_abiertos ? <b className="text-amber-700">{a.pendientes_abiertos} pendiente(s)</b> : "Sin pendientes"} · {fecha(a.actualizado_en)}</span>
            </div>
          </Link>
        ))}
      </div>
      {nuevo && (
        <FormAsunto titulo="Nuevo asunto" onCerrar={() => setNuevo(false)}
          onGuardar={async (datos) => { const r = await api.post("/evidencia/asuntos", datos); router.push(`/evidencia/${r.id}`); }} />
      )}
    </Shell>
  );
}
