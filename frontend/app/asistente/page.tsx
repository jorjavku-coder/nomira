"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { LeerTesis, TarjetaTesis } from "@/components/tesis";
import { Aviso, ConfirmarEliminar } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

const ICONO_TIPO: Record<string, string> = { investigar: "🔎", borrador: "✍️", resumen: "📄", acuerdo: "⚖️" };

function SinUsos({ cfg, onError }: { cfg: any; onError: (m: string) => void }) {
  const [yendo, setYendo] = useState(false);
  async function comprar() {
    setYendo(true);
    try { const r = await api.post("/asistente/paquetes", {}); window.location.href = r.url; }
    catch (e: any) { onError(e.message); setYendo(false); }
  }
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="status">
      <p className="font-semibold">Ya usaste los {cfg.cuota.incluidos} usos {cfg.cuota.en_prueba ? "de tu prueba gratis" : "incluidos de este mes"}.</p>
      <p className="mt-1">Se renuevan el día 1 del próximo mes. Si necesitas más ahora, compra un paquete de <b>{cfg.paquete.usos} usos por ${cfg.paquete.subtotal} + IVA</b> (${cfg.paquete.total} en total). No caducan.</p>
      {cfg.es_admin
        ? cfg.pago_en_linea
          ? <button className="btn-turquesa mt-3" onClick={comprar} disabled={yendo}>{yendo ? "Abriendo pago…" : `Comprar ${cfg.paquete.usos} usos`}</button>
          : <p className="mt-2 text-xs">El pago en línea no está disponible por ahora; escribe a soporte para comprar más usos.</p>
        : <p className="mt-2 text-xs">Pide a un administrador de tu despacho que compre el paquete.</p>}
    </div>
  );
}

function Asistente() {
  const sp = useSearchParams();
  const [cfg, setCfg] = useState<any>(null);
  const [lista, setLista] = useState<any[]>([]);
  const [actual, setActual] = useState<any>(null);
  const [f, setF] = useState({ tipo: sp.get("tipo") || "borrador", plantilla: "promocion", ag_asunto_id: sp.get("asunto") || "", instrucciones: "", texto: sp.get("texto") || "", con_tesis: true });
  const [leer, setLeer] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [texto, setTexto] = useState("");
  const [borrar, setBorrar] = useState<any>(null);
  const archivos = useRef<HTMLInputElement>(null);

  const cargarLista = useCallback(() => api.get("/asistente/solicitudes").then((r) => setLista(r.solicitudes)).catch(() => {}), []);
  useEffect(() => { api.get("/asistente/config").then(setCfg).catch((e) => setError(e.message)); cargarLista(); }, [cargarLista]);
  const abrir = useCallback((id: number) => api.get(`/asistente/solicitudes/${id}`).then((s) => { setActual(s); setTexto(s.resultado || ""); }).catch((e) => setError(e.message)), []);
  useEffect(() => {  // mientras genera, se consulta cada 2 segundos
    if (actual?.estado !== "generando") return;
    const t = setInterval(() => api.get(`/asistente/solicitudes/${actual.id}`).then((s) => {
      if (s.estado !== "generando") { setActual(s); setTexto(s.resultado || ""); cargarLista(); }
    }).catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [actual, cargarLista]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setOk(""); setEnviando(true);
    const d = new FormData();
    d.append("tipo", f.tipo);
    if (f.tipo === "borrador") d.append("plantilla", f.plantilla);
    if (f.ag_asunto_id) d.append("ag_asunto_id", f.ag_asunto_id);
    if (f.instrucciones.trim()) d.append("instrucciones", f.instrucciones);
    if (f.texto.trim()) d.append("texto", f.texto);
    if (f.tipo === "borrador" && f.con_tesis && cfg?.biblioteca_tesis) d.append("con_tesis", "true");
    for (const a of Array.from(archivos.current?.files || [])) d.append("archivos", a);
    try {
      const s = await api.subir("/asistente/solicitudes", d);
      setActual(s); setTexto(""); cargarLista();
      if (archivos.current) archivos.current.value = "";
    } catch (err: any) { setError(err.message); } finally { setEnviando(false); }
  }
  async function guardar() {
    try { const s = await api.put(`/asistente/solicitudes/${actual.id}`, { resultado: texto }); setActual(s); setOk("Cambios guardados."); cargarLista(); }
    catch (e: any) { setError(e.message); }
  }

  const puede = cfg?.puede_editar && cfg?.disponible;
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Inteligencia artificial</p>
          <h1 className="text-3xl font-extrabold text-marino">Asistente IA</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Investigue con tesis reales del Semanario Judicial de la Federación, redacte escritos, resuma documentos y entienda acuerdos. <b className="text-marino">La IA que no inventa:</b> solo cita tesis que Nomira verificó, cada una con su liga oficial.</p></div>
        <div className="flex items-center gap-2"><BotonAyuda modulo="asistente" />
          {cfg && <span className="rounded-full bg-crema px-3 py-1 text-xs text-slate-600" title="Los usos incluidos se renuevan cada mes; los de paquetes extra no caducan.">
            Te quedan {cfg.cuota.restantes_mes} de {cfg.cuota.incluidos} usos {cfg.cuota.en_prueba ? "de tu prueba gratis" : "este mes"}{cfg.cuota.extra ? ` + ${cfg.cuota.extra} extra` : ""}</span>}</div>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
        {cfg && !cfg.disponible && <Aviso tipo="alerta">{cfg.motivo}</Aviso>}
        {sp.get("paquete") === "procesando" && <Aviso tipo="ok">Gracias por tu compra. Los usos extra se suman en cuanto Stripe confirme el pago (normalmente en menos de un minuto).</Aviso>}
        {cfg && cfg.disponible && cfg.cuota.disponibles <= 0 && <SinUsos cfg={cfg} onError={setError} />}</div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-5">
          {cfg?.puede_editar && <form onSubmit={enviar} className="tarjeta space-y-3 p-5">
            <div className="flex flex-wrap gap-2" role="tablist">{cfg.tipos.map((t: any) => (
              <button key={t.clave} type="button" role="tab" aria-selected={f.tipo === t.clave} onClick={() => setF({ ...f, tipo: t.clave })}
                className={`rounded-xl px-3 py-2 text-sm font-semibold ${f.tipo === t.clave ? "bg-marino text-white" : "bg-crema text-slate-600 hover:text-marino"}`}>{ICONO_TIPO[t.clave]} {t.nombre}</button>))}</div>
            <div className="grid gap-3 sm:grid-cols-2">
              {f.tipo === "borrador" && <label><span className="etiqueta">Documento a redactar</span>
                <select className="campo" value={f.plantilla} onChange={(e) => setF({ ...f, plantilla: e.target.value })}>
                  {cfg.plantillas.map((p: any) => <option key={p.clave} value={p.clave}>{p.nombre}</option>)}</select></label>}
              <label><span className="etiqueta">Asunto de la Agenda (opcional)</span>
                <select className="campo" value={f.ag_asunto_id} onChange={(e) => setF({ ...f, ag_asunto_id: e.target.value })}>
                  <option value="">— Sin asunto —</option>{cfg.asuntos.map((a: any) => <option key={a.id} value={a.id}>{a.titulo}{a.numero ? ` (${a.numero})` : ""}</option>)}</select>
                <span className="mt-0.5 block text-xs text-slate-500">Toma número, tribunal, cliente y últimas actuaciones.</span></label>
            </div>
            {f.tipo === "investigar" && <p className="rounded-xl bg-turquesa-50 px-3 py-2 text-sm text-marino">Plantee el problema jurídico. Nomira busca en su biblioteca de {Number(cfg.biblioteca_tesis).toLocaleString("es-MX")} tesis del Semanario y la IA responde citando <b>solo</b> las que encontró; cualquier cita que no pueda verificar se elimina.</p>}
            <label className="block"><span className="etiqueta">{f.tipo === "borrador" ? "¿Qué necesita? Hechos, peticiones, tono…" : f.tipo === "investigar" ? "¿Qué quiere investigar?" : "Indicaciones (opcional)"}</span>
              <textarea className="campo" rows={4} maxLength={8000} value={f.instrucciones} onChange={(e) => setF({ ...f, instrucciones: e.target.value })}
                placeholder={f.tipo === "investigar" ? "Ej. ¿Procede la suspensión en amparo indirecto contra la clausura de un restaurante por falta de licencia de funcionamiento?" : f.tipo === "borrador" ? "Ej. Desahogar la prevención del acuerdo de 20 de noviembre aclarando el acto reclamado y la autoridad responsable." : "Ej. Enfócate en los plazos y en lo que pide la contraparte."} /></label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block"><span className="etiqueta">Documentos (PDF, Word o texto; hasta 3)</span>
                <input ref={archivos} className="campo" type="file" multiple accept=".pdf,.docx,.txt,application/pdf" /></label>
              <label className="block"><span className="etiqueta">…o pegue el texto</span>
                <textarea className="campo font-mono text-xs" rows={3} value={f.texto} onChange={(e) => setF({ ...f, texto: e.target.value })} placeholder="Texto del acuerdo, la demanda, el contrato…" /></label>
            </div>
            {f.tipo === "borrador" && <label className="flex items-start gap-2 text-sm text-slate-700">
              <input type="checkbox" className="mt-1" checked={f.con_tesis && !!cfg.biblioteca_tesis} disabled={!cfg.biblioteca_tesis} onChange={(e) => setF({ ...f, con_tesis: e.target.checked })} />
              <span>Fundamentar con tesis del Semanario Judicial de la Federación <span className="block text-xs text-slate-500">{cfg.biblioteca_tesis ? "Solo cita tesis verificadas de la biblioteca de Nomira, con su registro digital." : "La biblioteca de tesis todavía se está cargando."}</span></span></label>}
            <p className="text-xs text-slate-500">El texto se envía a Anthropic, el proveedor de IA de Nomira, solo para generar la respuesta. Los archivos no se guardan; el resultado sí, para que lo edite.</p>
            <div className="flex justify-end"><button className="btn-turquesa" disabled={!puede || enviando}>{enviando ? "Enviando…" : "Generar con IA"}</button></div>
          </form>}

          {actual && <section className="tarjeta p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div><p className="text-xs text-slate-500">{actual.tipo_texto}{actual.asunto ? ` · ${actual.asunto.titulo}` : ""}</p>
                <h2 className="text-lg font-bold text-marino">{actual.titulo}</h2></div>
              {actual.estado === "listo" && <div className="flex flex-wrap gap-2">
                <button className="btn-sec" onClick={() => { navigator.clipboard?.writeText(texto); setOk("Texto copiado."); }}>Copiar</button>
                <button className="btn-sec" onClick={() => api.descargar(`/asistente/solicitudes/${actual.id}/docx`, "borrador.docx")}>Descargar Word</button>
                {cfg?.puede_editar && <button className="btn-turquesa" disabled={texto === actual.resultado} onClick={guardar}>Guardar cambios</button>}</div>}
            </div>
            {actual.estado === "generando" && <div className="mt-6 flex items-center gap-3 text-sm text-slate-600" role="status">
              <span className="h-5 w-5 animate-spin rounded-full border-2 border-turquesa border-t-transparent" aria-hidden />El asistente está trabajando. Un escrito largo puede tardar uno o dos minutos.</div>}
            {actual.estado === "error" && <Aviso>{actual.error}</Aviso>}
            {actual.estado === "listo" && <>
              <p className="mt-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-900">Borrador generado con IA: revise hechos, fundamentos y datos marcados [COMPLETAR] antes de usarlo.</p>
              {actual.citas_eliminadas > 0 && <p className="mt-2 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-800" role="status">Nomira quitó {actual.citas_eliminadas === 1 ? "1 cita" : `${actual.citas_eliminadas} citas`} de tesis que no pudo verificar (aparecen como [CITA ELIMINADA]). No las agregue sin revisarlas en el Semanario.</p>}
              <textarea className="campo mt-3 min-h-[28rem] font-serif text-[15px] leading-relaxed" value={texto} onChange={(e) => setTexto(e.target.value)} readOnly={!cfg?.puede_editar} aria-label="Texto generado" />
              {actual.con_tesis && <div className="mt-4"><h3 className="font-semibold text-marino">Tesis citadas ({actual.tesis.length})</h3>
                {actual.tesis.length ? <ul className="mt-2 space-y-2">{actual.tesis.map((t: any) => <TarjetaTesis key={t.registro} t={t} verificada onLeer={() => setLeer(t.registro)} />)}</ul>
                  : <p className="mt-1 text-sm text-slate-500">La respuesta no cita tesis de la biblioteca.</p>}</div>}</>}
          </section>}
        </div>

        <aside className="tarjeta h-fit overflow-hidden">
          <h2 className="border-b border-crema-300 px-4 py-3 font-semibold text-marino">Historial</h2>
          {lista.length ? <ul className="max-h-[40rem] divide-y divide-crema-200 overflow-y-auto">{lista.map((s) => (
            <li key={s.id} className={`flex items-start justify-between gap-2 px-4 py-3 text-sm ${actual?.id === s.id ? "bg-turquesa-50" : ""}`}>
              <button className="min-w-0 text-left" onClick={() => abrir(s.id)}>
                <span className="block truncate font-semibold text-marino">{ICONO_TIPO[s.tipo]} {s.titulo}</span>
                <span className="block text-xs text-slate-500">{fechaHora(s.creado_en)} · {s.estado === "listo" ? (s.editado ? "editado" : "listo") : s.estado === "error" ? "con error" : "generando…"}</span></button>
              {cfg?.puede_editar && <button className="text-xs text-red-700 underline" onClick={() => setBorrar(s)}>Borrar</button>}
            </li>))}</ul>
            : <p className="p-4 text-sm text-slate-500">Aquí aparecerán sus borradores y resúmenes.</p>}
          <p className="border-t border-crema-300 px-4 py-3 text-xs text-slate-500">También puede abrirlo desde un asunto de la <Link href="/agenda/asuntos" className="underline">Agenda</Link> o desde una publicación de estrados.</p>
        </aside>
      </div>
      {leer && <LeerTesis registro={leer} onCerrar={() => setLeer(null)} />}
      {borrar && <ConfirmarEliminar titulo="Borrar del historial" onCerrar={() => setBorrar(null)}
        onConfirmar={async () => { await api.borrar(`/asistente/solicitudes/${borrar.id}`); if (actual?.id === borrar.id) setActual(null); cargarLista(); }}>
        Se borrará «{borrar.titulo}». No se puede deshacer.</ConfirmarEliminar>}
    </Shell>
  );
}

export default function Pagina() {
  return <Suspense><Asistente /></Suspense>;
}
