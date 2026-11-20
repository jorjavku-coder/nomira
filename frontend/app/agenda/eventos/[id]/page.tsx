"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AgendaShell, Desglose, diaLargo, Etq, faltanTexto, FormEvento, SITUACION, useCatalogosAgenda } from "@/components/agenda";
import { Aviso, Modal } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

export default function Evento() {
  const { id } = useParams<{ id: string }>();
  const cat = useCatalogosAgenda();
  const [e, setE] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [editar, setEditar] = useState(false);
  const [cierre, setCierre] = useState<"cumplir" | "cancelar" | null>(null);
  const [nota, setNota] = useState("");
  const cargar = useCallback(() => api.get(`/agenda/eventos/${id}`).then(setE).catch((x) => setError(x.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(ruta: string, cuerpo: any, msg: string) {
    setError(""); setOk("");
    try { setE(await api.post(`/agenda/eventos/${id}/${ruta}`, cuerpo)); setOk(msg); window.dispatchEvent(new Event("nomira:agenda")); return true; } catch (x: any) { setError(x.message); return false; }
  }
  if (!e) return <AgendaShell><Aviso>{error}</Aviso></AgendaShell>;
  const editor = cat?.puede_editar, mio = e.responsable_id === cat?.yo;
  return (
    <AgendaShell>
      <Link href={e.asunto ? `/agenda/asuntos/${e.asunto.id}` : "/agenda"} className="text-sm font-semibold text-turquesa-700">← {e.asunto ? e.asunto.titulo : "Agenda"}</Link>
      <div className="mb-4 mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2"><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{e.tipo_texto}</span>
            <Etq clase={SITUACION[e.situacion][1]}>{faltanTexto(e)}</Etq>
            {e.tipo === "plazo" && e.estado === "pendiente" && (e.validado ? <Etq clase="bg-emerald-100 text-emerald-800">Validado por {e.validado_por}</Etq> : <Etq clase="bg-violet-100 text-violet-800">Sin validar</Etq>)}</div>
          <h1 className="mt-1 text-3xl font-extrabold text-marino">{e.titulo}</h1>
          <p className="mt-1 text-slate-700">{diaLargo(e.fecha)}{e.hora ? ` · ${e.hora} h` : ""}{e.duracion_min ? ` · ${e.duracion_min} min` : ""}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => api.descargar(`/agenda/eventos/${e.id}/calendario.ics`, "agenda.ics").catch((x) => setError(x.message))}>Agregar a mi calendario</button>
          {e.estado === "pendiente" ? <>
            {editor && <button className="btn-sec" onClick={() => setEditar(true)}>Editar</button>}
            {editor && e.tipo === "plazo" && !e.validado && <button className="btn-sec" onClick={() => hacer("validar", {}, "Plazo validado. Queda registrado con su nombre.")}>Validar fecha</button>}
            {editor && <button className="btn-sec" onClick={() => { setNota(""); setCierre("cancelar"); }}>Cancelar</button>}
            {(editor || mio) && <button className="btn-turquesa" onClick={() => { setNota(""); setCierre("cumplir"); }}>Marcar como cumplido</button>}
          </> : editor && <button className="btn-sec" onClick={() => hacer("reabrir", {}, "Pendiente reabierto.")}>Reabrir</button>}
        </div>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
        {e.conflictos?.length > 0 && <Aviso tipo="alerta">El responsable tiene otra audiencia ese día: {e.conflictos.join("; ")}.</Aviso>}</div>
      <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-5">
          {e.calculo && <section><h2 className="mb-2 font-semibold text-marino">Cómo se calculó</h2><Desglose r={e.calculo} />
            {!e.validado && e.estado === "pendiente" && <p className="mt-2 text-sm text-violet-900">Revise el desglose contra la ley aplicable y el calendario oficial del tribunal. Al validar, queda registrado quién lo revisó; si después cambia la fecha o el cálculo, habrá que validarlo de nuevo.</p>}</section>}
          {e.tipo === "plazo" && !e.calculo && <Aviso tipo="info">Fecha capturada directamente (sin cálculo asistido).</Aviso>}
          {e.descripcion && <section className="tarjeta p-4"><h2 className="mb-1 font-semibold text-marino">Notas</h2><p className="whitespace-pre-line text-sm text-slate-700">{e.descripcion}</p></section>}
          {e.estado !== "pendiente" && <section className="tarjeta p-4 text-sm"><p><b>{e.estado === "cumplido" ? "Cumplido" : "Cancelado"}</b> por {e.cumplido_por} el {fechaHora(e.cumplido_en)}.</p>{e.nota_cierre && <p className="mt-1 text-slate-700">{e.nota_cierre}</p>}</section>}
        </div>
        <aside className="tarjeta space-y-2 p-4 text-sm">
          {e.asunto && <p><span className="text-slate-500">Asunto:</span> <Link className="font-semibold text-marino hover:underline" href={`/agenda/asuntos/${e.asunto.id}`}>{e.asunto.titulo}</Link>{e.asunto.numero ? ` · ${e.asunto.numero}` : ""}</p>}
          {e.asunto?.tribunal && <p><span className="text-slate-500">Tribunal:</span> {e.asunto.tribunal}</p>}
          <p><span className="text-slate-500">Responsable:</span> {e.responsable || <b className="text-red-700">Sin asignar</b>}</p>
          {e.apoyo.length > 0 && <p><span className="text-slate-500">Apoyo:</span> {e.apoyo.join(", ")}</p>}
          <p><span className="text-slate-500">Prioridad:</span> {cat?.prioridades[e.prioridad]}</p>
          {e.lugar && <p><span className="text-slate-500">Lugar:</span> {e.lugar}</p>}
          {e.enlace && <p><a className="btn-turquesa w-full" href={e.enlace} target="_blank" rel="noopener noreferrer">Unirse{e.plataforma ? ` por ${e.plataforma.nombre}` : ""}</a></p>}
          <p><span className="text-slate-500">Avisos:</span> {e.alertas.length ? e.alertas.map((d: number) => d === 0 ? "el mismo día" : `${d} día(s) antes`).join(", ") : "sin avisos anticipados"}</p>
        </aside>
      </div>
      {editar && <FormEvento inicial={e} asuntoFijo={e.asunto ? { id: e.asunto.id, titulo: e.asunto.titulo, numero: e.asunto.numero } : undefined}
        onCerrar={() => setEditar(false)} onGuardado={(x) => { setE(x); setEditar(false); setOk(x.calculo && !x.validado ? "Guardado. La fecha quedó sin validar." : "Guardado."); }} />}
      {cierre && <Modal titulo={cierre === "cumplir" ? "Marcar como cumplido" : "Cancelar pendiente"} onCerrar={() => setCierre(null)}>
        <label className="block"><span className="etiqueta">{cierre === "cumplir" ? "Nota (opcional): qué se presentó o cómo se cumplió" : "¿Por qué se cancela?"}</span>
          <textarea className="campo" rows={3} value={nota} onChange={(x) => setNota(x.target.value)} /></label>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={() => setCierre(null)}>Volver</button>
          <button className="btn-turquesa" disabled={cierre === "cancelar" && nota.trim().length < 5}
            onClick={async () => { if (await hacer(cierre, { nota: nota || null }, cierre === "cumplir" ? "Marcado como cumplido." : "Pendiente cancelado.")) setCierre(null); }}>Confirmar</button></div>
      </Modal>}
    </AgendaShell>
  );
}
