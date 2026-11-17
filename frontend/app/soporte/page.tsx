"use client";
import { useCallback, useEffect, useState } from "react";
import Conversacion from "@/components/Conversacion";
import Shell from "@/components/Shell";
import { Aviso, Modal } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

export default function Soporte() {
  const [lista, setLista] = useState<any[] | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [t, setT] = useState<any>(null);
  const [nuevo, setNuevo] = useState(false);
  const [error, setError] = useState("");
  const cargar = useCallback(() => api.get("/soporte").then(setLista).catch((e) => setError(e.message)), []);
  const avisar = () => window.dispatchEvent(new Event("nomira:soporte"));
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    if (!sel) return;
    api.get(`/soporte/${sel}`).then((x) => { setT(x); avisar(); cargar(); }).catch((e) => setError(e.message));
  }, [sel, cargar]);
  const despues = (x: any) => { setT(x); cargar(); };
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-marino">Soporte</h1>
          <p className="mt-1 text-sm text-slate-500">¿Dudas o algún problema? Escríbale al equipo de Nomira. Las respuestas llegan aquí.</p>
        </div>
        <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nueva consulta</button>
      </div>
      <Aviso>{error}</Aviso>
      <div className="mt-3 grid gap-4 lg:grid-cols-[20rem_1fr]">
        <section className="tarjeta overflow-hidden">
          <ul className="max-h-[70vh] divide-y divide-crema-300 overflow-y-auto">
            {lista === null && <li className="p-4 text-sm text-slate-500">Cargando…</li>}
            {lista?.length === 0 && <li className="p-6 text-center text-sm text-slate-500">Aún no tiene consultas.</li>}
            {lista?.map((x) => (
              <li key={x.id}>
                <button onClick={() => setSel(x.id)} className={`block w-full px-4 py-3 text-left transition ${sel === x.id ? "bg-turquesa-50" : "hover:bg-crema/60"}`}>
                  <div className="flex items-center gap-2">
                    {!x.leido_cliente && <span className="h-2 w-2 shrink-0 rounded-full bg-turquesa" aria-label="Respuesta nueva" />}
                    <span className={`truncate text-sm ${x.leido_cliente ? "font-medium text-slate-700" : "font-bold text-marino"}`}>{x.asunto}</span>
                  </div>
                  <div className="mt-0.5 text-xs text-slate-500">{x.estado === "abierto" ? "Abierta" : "Resuelta"} · {fechaHora(x.actualizado_en)}</div>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="tarjeta overflow-hidden">
          {t ? (
            <Conversacion t={t} lado="cliente"
              onEnviar={async (texto) => despues(await api.post(`/soporte/${t.id}/mensajes`, { texto }))}
              onEstado={async () => despues(await api.patch(`/soporte/${t.id}`, {}))} />
          ) : <div className="flex h-full min-h-[16rem] items-center justify-center p-8 text-center text-sm text-slate-500">
            {lista?.length ? "Elija una consulta de la lista." : "Cuando escriba una consulta, aquí verá la conversación con el equipo de Nomira."}</div>}
        </section>
      </div>
      {nuevo && <NuevaConsulta onCerrar={() => setNuevo(false)} onListo={(x) => { setNuevo(false); cargar(); setSel(x.id); setT(x); }} />}
    </Shell>
  );
}

function NuevaConsulta({ onCerrar, onListo }: { onCerrar: () => void; onListo: (t: any) => void }) {
  const [f, setF] = useState({ asunto: "", texto: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try { onListo(await api.post("/soporte", f)); } catch (err: any) { setError(err.message); setEnviando(false); }
  }
  return (
    <Modal titulo="Nueva consulta a soporte" onCerrar={onCerrar} ancho="max-w-xl">
      <form className="space-y-3" onSubmit={enviar}>
        <label className="block"><span className="etiqueta">Asunto</span>
          <input className="campo" required minLength={2} maxLength={200} autoFocus placeholder="Ej. No puedo subir un PDF" value={f.asunto} onChange={(e) => setF({ ...f, asunto: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Cuéntenos qué pasa</span>
          <textarea className="campo h-40" required maxLength={5000} value={f.texto} onChange={(e) => setF({ ...f, texto: e.target.value })} /></label>
        <Aviso tipo="info">El equipo de Nomira <b>no tiene acceso a sus expedientes</b>. Si hace falta, describa el problema sin incluir datos personales de los trabajadores.</Aviso>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={enviando}>{enviando ? "Enviando…" : "Enviar consulta"}</button></div>
      </form>
    </Modal>
  );
}
