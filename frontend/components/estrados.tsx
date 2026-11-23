"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { diaLargo, Etq } from "@/components/agenda";
import { Aviso } from "@/components/ui";
import { api, fecha } from "@/lib/api";

const ESTADO: Record<string, [string, string]> = {
  pendiente: ["Aún no revisado", "bg-slate-100 text-slate-600"], ok: ["Revisión automática al día", "bg-emerald-100 text-emerald-800"],
  error: ["El tribunal no respondió", "bg-amber-100 text-amber-800"], sin_conexion: ["Solo cotejo manual", "bg-slate-100 text-slate-600"],
};

export function EstadoVigilancia({ v, automatica }: { v: any; automatica: boolean }) {
  if (!v.activa) return <Etq clase="bg-slate-100 text-slate-500">En pausa</Etq>;
  const [t, c] = automatica ? ESTADO[v.ultimo_estado] || ESTADO.pendiente : ESTADO.sin_conexion;
  return <Etq clase={c}>{t}</Etq>;
}

/** Tarjeta dentro del asunto: activar o cambiar la vigilancia en estrados. */
export function VigilanciaAsunto({ asunto, puedeEditar, onCambio }: { asunto: any; puedeEditar: boolean; onCambio: () => void }) {
  const v = asunto.vigilancia;
  const [abierto, setAbierto] = useState(false);
  const [f, setF] = useState({ expediente: v?.expediente || asunto.numero || "", sala: v?.sala || (/sala/i.test(asunto.tribunal || "") ? asunto.tribunal : "") });
  const [error, setError] = useState("");
  async function guardar(activa = true) {
    setError("");
    try { await api.put(`/agenda/asuntos/${asunto.id}/vigilancia`, { ...f, sala: f.sala || null, activa }); setAbierto(false); onCambio(); }
    catch (e: any) { setError(e.message); }
  }
  async function quitar() {
    setError("");
    try { await api.borrar(`/agenda/vigilancias/${v.id}`); onCambio(); } catch (e: any) { setError(e.message); }
  }
  return (
    <section className="tarjeta p-4">
      <div className="flex items-start justify-between gap-2">
        <div><h2 className="font-semibold text-marino">Estrados digitales</h2>
          <p className="text-xs text-slate-500">TRIJAEM · Tribunal de Justicia Administrativa del Estado de México</p></div>
        {v && <Etq clase={v.activa ? "bg-turquesa-100 text-turquesa-700" : "bg-slate-100 text-slate-500"}>{v.activa ? "Vigilando" : "En pausa"}</Etq>}
      </div>
      <Aviso>{error}</Aviso>
      {v && !abierto && <div className="mt-2 text-sm text-slate-700">
        <p>Expediente <span className="font-mono font-semibold">{v.expediente}</span>{v.sala ? ` · ${v.sala}` : ""}</p>
        <p className="text-xs text-slate-500">{v.publicaciones} publicación(es) encontradas{v.sin_ver ? ` · ${v.sin_ver} sin revisar` : ""}</p>
        <div className="mt-2 flex flex-wrap gap-2 text-sm">
          <Link href="/agenda/estrados" className="font-semibold text-turquesa-700 underline">Ver publicaciones</Link>
          {puedeEditar && <>
            <button className="font-semibold text-turquesa-700 underline" onClick={() => setAbierto(true)}>Cambiar</button>
            <button className="font-semibold text-slate-500 underline" onClick={() => guardar(!v.activa)}>{v.activa ? "Pausar" : "Reanudar"}</button>
            <button className="font-semibold text-red-700 underline" onClick={quitar}>Dejar de vigilar</button></>}
        </div></div>}
      {!v && !abierto && <div className="mt-2 text-sm text-slate-600">
        <p>Reciba un aviso cuando se publique un acuerdo o notificación de este expediente en los estrados del tribunal.</p>
        {puedeEditar && asunto.estado === "activo" && <button className="btn-sec mt-2 w-full" onClick={() => setAbierto(true)}>Vigilar en estrados</button>}</div>}
      {abierto && <form className="mt-3 space-y-2 rounded-xl bg-crema/60 p-3" onSubmit={(e) => { e.preventDefault(); guardar(true); }}>
        <label className="block"><span className="etiqueta">Número de expediente como lo publica el tribunal</span>
          <input className="campo font-mono" required placeholder="Ej. 1234/2026" value={f.expediente} onChange={(e) => setF({ ...f, expediente: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Sala o sección (recomendado)</span>
          <input className="campo" placeholder="Ej. Primera Sala Regional" value={f.sala} onChange={(e) => setF({ ...f, sala: e.target.value })} /></label>
        <p className="text-xs text-slate-500">Cada sala numera sus juicios por separado; con la sala evitamos confundir su expediente con otro del mismo número.</p>
        <div className="flex gap-2"><button className="btn-turquesa flex-1">Guardar</button><button type="button" className="btn-sec" onClick={() => setAbierto(false)}>Cancelar</button></div>
      </form>}
    </section>
  );
}

/** Una publicación encontrada en estrados, con lo que el abogado puede hacer con ella. */
export function FilaPublicacion({ p, puedeEditar, onCambio }: { p: any; puedeEditar: boolean; onCambio: () => void }) {
  const router = useRouter();
  const [error, setError] = useState("");
  async function vista() { try { await api.post(`/agenda/publicaciones/${p.id}/vista`); onCambio(); } catch (e: any) { setError(e.message); } }
  async function historial() {
    try { const r = await api.post(`/agenda/publicaciones/${p.id}/actuacion`); router.push(`/agenda/asuntos/${r.asunto_id}`); } catch (e: any) { setError(e.message); }
  }
  return (
    <li className={`p-4 ${p.vista ? "" : "bg-turquesa-50/60"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        {!p.vista && <Etq clase="bg-turquesa text-white">Nueva</Etq>}
        <span className="font-semibold text-marino">{p.asunto}</span><span className="font-mono">Exp. {p.expediente}</span>
        {p.sala && <span>· {p.sala}</span>}<span>· {p.origen === "automatica" ? "encontrada por Nomira" : "registrada por el despacho"}</span>
      </div>
      <p className="mt-1 text-sm text-slate-800">{p.descripcion}</p>
      <p className="mt-1 text-xs text-slate-600">Publicado el <b>{diaLargo(p.fecha_publicacion)}</b> · surtiría efectos el <b>{diaLargo(p.surte_efectos)}</b> <span className="text-slate-400">(estimado, confírmelo)</span></p>
      <Aviso>{error}</Aviso>
      <div className="mt-2 flex flex-wrap gap-3 text-sm">
        {p.actuacion_id ? <Link href={`/agenda/asuntos/${p.asunto_id}`} className="font-semibold text-emerald-700 underline">✓ En el historial del asunto · calcular plazo</Link>
          : puedeEditar && <button className="font-semibold text-turquesa-700 underline" onClick={historial}>Pasar al historial y calcular plazo</button>}
        {!p.vista && <button className="font-semibold text-slate-600 underline" onClick={vista}>Marcar como revisada</button>}
        {p.enlace && <a href={p.enlace} target="_blank" rel="noopener noreferrer" className="font-semibold text-slate-600 underline">Ver documento</a>}
        <a href={p.consulta_oficial} target="_blank" rel="noopener noreferrer" className="font-semibold text-slate-600 underline">Consulta oficial ↗</a>
      </div>
    </li>
  );
}
