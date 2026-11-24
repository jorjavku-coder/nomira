"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { Barra, fechaHoraCorta, NuevoExpediente, Semaforo, SEMAFORO, useCatalogosEsc } from "@/components/escrituracion";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

export default function Escrituracion() {
  const cat = useCatalogosEsc();
  const router = useRouter();
  const [r, setR] = useState<any>(null);
  const [estado, setEstado] = useState("abierto");
  const [q, setQ] = useState("");
  const [color, setColor] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [error, setError] = useState("");
  const cargar = useCallback(() => api.get(`/escrituracion/expedientes?estado=${estado}&q=${encodeURIComponent(q)}`).then(setR).catch((e) => setError(e.message)), [estado, q]);
  useEffect(() => { const t = setTimeout(cargar, 200); return () => clearTimeout(t); }, [cargar]);
  const lista = (r?.expedientes || []).filter((e: any) => !color || e.semaforo.color === color);
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Nomira para notarías</p>
          <h1 className="text-3xl font-extrabold text-marino">Escrituración</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Cada operación con sus etapas, documentos y vigencias. Sus clientes, la inmobiliaria y el banco ven el avance con un enlace, sin llamar a la notaría.</p></div>
        <div className="flex items-center gap-2"><BotonAyuda modulo="escrituracion" />
          {r?.puede_editar && cat && <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo expediente</button>}</div>
      </div>
      <Aviso>{error}</Aviso>
      {r && estado === "abierto" && <div className="mb-5 grid gap-3 sm:grid-cols-3">{(["rojo", "amarillo", "verde"] as const).map((c) => (
        <button key={c} onClick={() => setColor(color === c ? "" : c)} className={`tarjeta flex items-center gap-3 p-4 text-left ${color === c ? "ring-2 ring-turquesa" : ""}`}>
          <span className={`h-4 w-4 rounded-full ${SEMAFORO[c].punto}`} aria-hidden />
          <span><span className="block text-2xl font-extrabold text-marino">{r.totales[c]}</span>
            <span className="text-xs text-slate-500">{c === "rojo" ? "No listos para firmar" : c === "amarillo" ? "Casi listos" : "Listos para firmar"}</span></span></button>))}</div>}
      <div className="mb-3 flex flex-wrap gap-2">
        <div className="flex rounded-xl bg-crema p-1">{[["abierto", "En trámite"], ["concluido", "Concluidos"], ["cancelado", "Cancelados"]].map(([v, t]) =>
          <button key={v} onClick={() => { setEstado(v); setColor(""); }} className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${estado === v ? "bg-white text-marino shadow-sm" : "text-slate-500"}`}>{t}</button>)}</div>
        <input className="campo max-w-sm" placeholder="Buscar por folio, inmueble, escritura o persona" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar expedientes" />
      </div>
      {r && (lista.length ? <ul className="grid gap-3 lg:grid-cols-2">{lista.map((e: any) => (
        <li key={e.id}><button onClick={() => router.push(`/escrituracion/${e.id}`)} className={`tarjeta block w-full p-4 text-left hover:shadow-md ${e.semaforo.color === "rojo" ? "border-l-4 border-l-red-400" : e.semaforo.color === "verde" ? "border-l-4 border-l-emerald-400" : "border-l-4 border-l-amber-300"}`}>
          <div className="flex items-start justify-between gap-2">
            <div><p className="text-xs font-mono text-slate-400">{e.folio} · {e.acto_texto}</p><p className="font-bold text-marino">{e.titulo}</p>
              <p className="text-xs text-slate-600">{e.partes.map((p: any) => `${p.rol_texto}: ${p.nombre}`).join(" · ") || "Sin partes"}</p></div>
            {e.del_cliente > 0 && <span className="whitespace-nowrap rounded-full bg-turquesa px-2 py-0.5 text-xs font-semibold text-white">{e.del_cliente} doc. del cliente</span>}
          </div>
          <div className="mt-3 flex items-center gap-3"><Barra pct={e.avance.porcentaje} /><span className="whitespace-nowrap text-xs text-slate-500">{e.avance.porcentaje}%</span></div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="text-slate-600">Etapa: <b>{e.avance.actual}</b></span><Semaforo s={e.semaforo} chico /></div>
          {e.cita_firma && <p className="mt-1 text-xs text-slate-600">✍️ Firma: {fechaHoraCorta(e.cita_firma)}</p>}
        </button></li>))}</ul>
        : <div className="tarjeta p-10 text-center"><p className="font-semibold text-marino">{q || color ? "No hay expedientes con ese filtro." : "Aún no hay expedientes."}</p>
          {!q && !color && r.puede_editar && <p className="mt-1 text-sm text-slate-500">Cree el primero con «+ Nuevo expediente». Puede tomar a las partes de su directorio de <Link href="/clientes" className="font-semibold text-turquesa-700 underline">Clientes</Link>.</p>}</div>)}
      {nuevo && cat && <NuevoExpediente cat={cat} onCerrar={() => setNuevo(false)} onListo={(e) => router.push(`/escrituracion/${e.id}`)} />}
    </Shell>
  );
}
