"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import ShellPlataforma from "@/components/plataforma";
import { Aviso } from "@/components/ui";
import { fechaHora } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

const ESTADO: Record<string, [string, string]> = {
  pendiente: ["Por empezar", "bg-slate-100 text-slate-700"], descargando: ["Descargando", "bg-amber-100 text-amber-800"],
  al_dia: ["Al día", "bg-emerald-100 text-emerald-800"], bloqueada: ["Bloqueada por la SCJN", "bg-red-100 text-red-800"],
  error: ["Con error", "bg-red-100 text-red-800"], apagada: ["Apagada", "bg-slate-100 text-slate-600"],
};
const ORIGEN: Record<string, string> = { repositorio: "Repositorio de datos abiertos", pdf_semanal: "PDF semanal", json: "Archivos JSON", csv: "CSV del Repositorio" };

/** Biblioteca de tesis del SJF: la usan el buscador de tesis y el Asistente IA de todos los despachos. */
export default function TesisPanel() {
  const [e, setE] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const archivo = useRef<HTMLInputElement>(null);
  const cargar = useCallback(() => apiP.get("/tesis").then(setE).catch((x) => setError(x.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  async function subir(ev: React.FormEvent) {
    ev.preventDefault(); setError(""); setOk("");
    const a = archivo.current?.files?.[0];
    if (!a) return;
    const d = new FormData(); d.append("archivo", a);
    setSubiendo(true);
    try { const r = await apiP.subir("/tesis/importar", d); setOk(`Se cargaron ${r.importadas} tesis.`); setE(r); if (archivo.current) archivo.current.value = ""; }
    catch (x: any) { setError(x.message); } finally { setSubiendo(false); }
  }
  return (
    <ShellPlataforma>
      <h1 className="text-3xl font-extrabold text-marino">Tesis del Semanario (SJF)</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-500">Biblioteca común que usan el buscador de tesis y el Asistente IA de todos los despachos. La IA solo puede citar tesis que estén aquí.</p>
      <div className="my-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {e && <div className="grid gap-5 lg:grid-cols-2">
        <section className="tarjeta p-5" aria-label="Estado">
          <p className="text-4xl font-extrabold text-marino">{Number(e.total).toLocaleString("es-MX")}</p><p className="text-sm text-slate-500">tesis en la biblioteca</p>
          <ul className="mt-2 text-sm text-slate-600">{Object.entries(e.por_origen).map(([k, n]) => <li key={k}>{ORIGEN[k] || k}: {Number(n).toLocaleString("es-MX")}</li>)}</ul>
          <h2 className="mt-4 font-semibold text-marino">Sincronización automática</h2>
          <p className="mt-1"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${(ESTADO[e.estado] || ESTADO.pendiente)[1]}`}>{(ESTADO[e.estado] || ESTADO.pendiente)[0]}</span></p>
          {e.mensaje && <p className="mt-2 text-sm text-slate-700">{e.mensaje}</p>}
          <dl className="mt-2 grid grid-cols-2 gap-1 text-sm">
            <dt className="text-slate-500">En la SCJN</dt><dd>{e.total_remoto ? Number(e.total_remoto).toLocaleString("es-MX") : "—"}</dd>
            <dt className="text-slate-500">Por descargar</dt><dd>{Number(e.pendientes).toLocaleString("es-MX")}</dd>
            <dt className="text-slate-500">Épocas antiguas omitidas</dt><dd>{Number(e.omitidas).toLocaleString("es-MX")}</dd>
            <dt className="text-slate-500">Última corrida</dt><dd>{e.ultima_corrida ? fechaHora(e.ultima_corrida) : "—"}</dd>
            {e.proximo_intento && <><dt className="text-slate-500">Próximo intento</dt><dd>{fechaHora(e.proximo_intento)}</dd></>}</dl>
          <p className="mt-2 text-xs text-slate-500">Descarga una tesis por segundo (hasta 500 por hora), de la más nueva a la más vieja, desde la {e.epoca_minima === 10 ? "Décima" : `${e.epoca_minima}.ª`} Época. Si la SCJN muestra una verificación anti-robots, Nomira se detiene y no intenta saltarla.</p>
          {e.sincronizar && <button className="btn-sec mt-3" onClick={async () => { setError(""); try { await apiP.post("/tesis/sincronizar", {}); setOk("Se pidió una tanda. Actualice en un par de minutos."); } catch (x: any) { setError(x.message); } }}>Sincronizar ahora</button>}
        </section>
        <section className="tarjeta p-5" aria-label="Cargar archivos oficiales">
          <h2 className="font-semibold text-marino">Cargar archivos oficiales</h2>
          <p className="mt-1 text-sm text-slate-600">Úselo si la sincronización está bloqueada o para tener al día lo de esta semana:</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
            <li>Cada viernes la SCJN publica el PDF <b>«Tesis publicación semanal»</b> en scjn.gob.mx (lo anuncia en sus redes como #SJFSemanal). Descárguelo con su navegador.</li>
            <li>O, en el <a className="font-semibold text-turquesa-700 underline" href="https://bicentenario.scjn.gob.mx/repositorio-scjn/sjf" target="_blank" rel="noopener noreferrer">Repositorio de la SCJN</a>, filtre por fecha de publicación y presione «Descargar» (hasta 100 tesis por archivo): suba el ZIP tal cual.</li>
            <li>Súbalo aquí. Nomira separa cada tesis por su «Registro digital» y actualiza las que ya existían.</li>
          </ol>
          <form className="mt-3 space-y-2" onSubmit={subir}>
            <input ref={archivo} className="campo" type="file" accept=".pdf,.json,.jsonl,.csv,.zip,application/pdf,application/json,text/csv,application/zip" aria-label="Archivo de tesis" required />
            <button className="btn-turquesa" disabled={subiendo}>{subiendo ? "Leyendo…" : "Cargar tesis"}</button>
          </form>
          {e.ejemplos && <ul className="mt-3 space-y-1 text-xs text-slate-600">{e.ejemplos.map((x: any) => <li key={x.registro}><b>{x.registro}</b> · {x.rubro}</li>)}</ul>}
        </section>
      </div>}
    </ShellPlataforma>
  );
}
