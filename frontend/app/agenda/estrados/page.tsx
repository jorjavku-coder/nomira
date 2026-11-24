"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AgendaShell } from "@/components/agenda";
import { EstadoVigilancia, FilaPublicacion } from "@/components/estrados";
import { Aviso, Modal } from "@/components/ui";
import { api, hoyLocal } from "@/lib/api";

/** Estrados digitales: expedientes vigilados, publicaciones encontradas y cotejo de la lista del día. */
export default function Estrados() {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cotejo, setCotejo] = useState(false);
  const [soloNuevas, setSoloNuevas] = useState(false);
  const cargar = useCallback(() => api.get(`/agenda/estrados?solo_sin_ver=${soloNuevas}`).then((x) => { setR(x); window.dispatchEvent(new Event("nomira:agenda")); })
    .catch((e) => setError(e.message)), [soloNuevas]);
  useEffect(() => { cargar(); }, [cargar]);
  async function revisar(v: any) {
    setError(""); setOk("");
    try { const x = await api.post(`/agenda/vigilancias/${v.id}/revisar`); setOk(x.nuevas ? `${x.nuevas} publicación(es) nueva(s).` : "Revisado: sin publicaciones nuevas."); cargar(); }
    catch (e: any) { setError(e.message); }
  }
  const activas = r?.vigilancias.filter((v: any) => v.activa).length ?? 0;
  return (
    <AgendaShell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Estrados digitales</h1>
          <p className="mt-1 text-sm text-slate-500">Avisos cuando se publica algo de sus expedientes · TRIJAEM (Estado de México) y Lista de acuerdos del Poder Judicial de la Federación</p></div>
        {r?.puede_editar && <button className="btn-turquesa" onClick={() => setCotejo(true)}>Cotejar lista del día</button>}
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {r && <>
        <div className={`mb-5 rounded-2xl border p-4 text-sm ${r.automatica ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
          {r.automatica
            ? <p><b>Revisión automática activa.</b> Nomira consulta los estrados del TRIJAEM para cada expediente vigilado cada {r.revisar_cada_horas} horas, de lunes a viernes de {r.horario[0]}:00 a {r.horario[1]}:00, y le avisa aquí y por correo cuando se publica un acuerdo. También puede cotejar la lista del día cuando quiera.</p>
            : <p><b>Revisión automática apagada.</b> Use <b>«Cotejar lista del día»</b>: pegue la lista o suba el PDF de estrados y Nomira encuentra al instante todos los expedientes que su despacho vigila y avisa a cada responsable.</p>}
          <p className="mt-1 text-xs opacity-80">{r.fuentes[0]?.efectos} Nomira no sustituye la consulta oficial: la fecha en que surte efectos es una estimación que el abogado debe confirmar. <a className="underline" href={r.fuentes[0]?.consulta} target="_blank" rel="noopener noreferrer">Abrir estrados del TRIJAEM ↗</a></p>
        </div>
        {r.revision_pjf?.length > 0 && <RevisionPJF grupos={r.revision_pjf} consulta={r.fuentes.find((x: any) => x.clave === "pjf")?.consulta}
          puedeEditar={r.puede_editar} onListo={(x) => { setOk(x); cargar(); }} />}
        <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
          <section className="tarjeta overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 px-4 py-3">
              <h2 className="font-semibold text-marino">Publicaciones {r.sin_ver ? <span className="ml-1 rounded-full bg-turquesa px-2 py-0.5 text-xs text-white">{r.sin_ver} nuevas</span> : null}</h2>
              <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={soloNuevas} onChange={(e) => setSoloNuevas(e.target.checked)} /> Solo las nuevas que me tocan</label>
            </div>
            {r.publicaciones.length ? <ul className="divide-y divide-crema-200">{r.publicaciones.map((p: any) => <FilaPublicacion key={p.id} p={p} puedeEditar={r.puede_editar} onCambio={cargar} />)}</ul>
              : <p className="p-6 text-center text-sm text-slate-500">{soloNuevas ? "No tiene publicaciones nuevas por revisar." : "Aún no hay publicaciones registradas."}</p>}
          </section>
          <section className="tarjeta overflow-hidden">
            <h2 className="border-b border-crema-300 px-4 py-3 font-semibold text-marino">Expedientes vigilados ({activas})</h2>
            {r.vigilancias.length ? <ul className="divide-y divide-crema-200">{r.vigilancias.map((v: any) => (
              <li key={v.id} className="p-4 text-sm">
                <Link href={`/agenda/asuntos/${v.asunto_id}`} className="font-semibold text-marino hover:underline">{v.asunto}</Link>
                <p className="font-mono text-xs text-slate-600">Exp. {v.expediente}{v.sala ? ` · ${v.sala}` : ""}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2"><EstadoVigilancia v={v} automatica={r.automatica} />
                  {v.sin_ver > 0 && <span className="text-xs font-semibold text-turquesa-700">{v.sin_ver} nueva(s)</span>}</div>
                {r.automatica && v.ultimo_error && <p className="mt-1 text-xs text-amber-700">{v.ultimo_error}</p>}
                {r.automatica && r.puede_editar && v.activa && <button className="mt-1 text-xs font-semibold text-turquesa-700 underline" onClick={() => revisar(v)}>Revisar ahora</button>}
              </li>))}</ul>
              : <div className="p-4 text-sm text-slate-600"><p>Todavía no vigila ningún expediente.</p>
                <p className="mt-1">Abra un asunto en <Link href="/agenda/asuntos" className="font-semibold text-turquesa-700 underline">Asuntos</Link> y pulse <b>«Vigilar en estrados»</b>.</p></div>}
          </section>
        </div>
      </>}
      {cotejo && <Cotejo onCerrar={() => setCotejo(false)} onListo={(x) => { setCotejo(false); setOk(x); cargar(); }} />}
    </AgendaShell>
  );
}

function Cotejo({ onCerrar, onListo }: { onCerrar: () => void; onListo: (msg: string) => void }) {
  const [f, setF] = useState({ fecha: hoyLocal(), sala: "", texto: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const pdf = useRef<HTMLInputElement>(null);
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try {
      const archivo = pdf.current?.files?.[0];
      let r;
      if (archivo) {
        const d = new FormData(); d.append("archivo", archivo); d.append("fecha", f.fecha); if (f.sala) d.append("sala", f.sala);
        r = await api.subir("/agenda/estrados/cotejar-pdf", d);
      } else {
        if (f.texto.trim().length < 5) throw new Error("Pegue el texto de la lista o elija el PDF.");
        r = await api.post("/agenda/estrados/cotejar", { ...f, sala: f.sala || null });
      }
      onListo(r.nuevas.length ? `Se encontraron ${r.nuevas.length} publicación(es) nueva(s) de sus expedientes. Ya avisamos a los responsables.`
        : r.ya_registradas ? "Sus expedientes de esa lista ya estaban registrados." : `Se revisaron ${r.revisados} expediente(s) vigilados: ninguno aparece en esta lista.`);
    } catch (e: any) { setError(e.message); } finally { setEnviando(false); }
  }
  return (
    <Modal titulo="Cotejar lista del día" onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-3" onSubmit={enviar}>
        <p className="text-sm text-slate-600">Abra los estrados del TRIJAEM, copie la lista de acuerdos (o descargue el PDF) y tráigala aquí. Nomira busca los números de expediente que su despacho vigila.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label><span className="etiqueta">Fecha de publicación</span><input className="campo" type="date" required max={hoyLocal()} value={f.fecha} onChange={(e) => setF({ ...f, fecha: e.target.value })} /></label>
          <label><span className="etiqueta">Sala de esta lista (opcional)</span><input className="campo" placeholder="Ej. Primera Sala Regional" value={f.sala} onChange={(e) => setF({ ...f, sala: e.target.value })} /></label>
        </div>
        <label className="block"><span className="etiqueta">Pegue aquí el texto de la lista</span>
          <textarea className="campo font-mono text-xs" rows={9} placeholder={"1. JA-1234/2026  ACTOR: …\n   Se tiene por presentada la promoción…"} value={f.texto} onChange={(e) => setF({ ...f, texto: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">…o suba el PDF de la lista</span><input ref={pdf} className="campo" type="file" accept="application/pdf" /></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-turquesa" disabled={enviando}>{enviando ? "Buscando…" : "Buscar mis expedientes"}</button></div>
      </form>
    </Modal>
  );
}

/** Revisión diaria asistida del PJF: una búsqueda por órgano en la consulta oficial (que pide «No soy un robot»). */
function RevisionPJF({ grupos, consulta, puedeEditar, onListo }: { grupos: any[]; consulta: string; puedeEditar: boolean; onListo: (msg: string) => void }) {
  const [abierto, setAbierto] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [fechaP, setFechaP] = useState(hoyLocal());
  const [copiado, setCopiado] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const clave = (g: any) => g.id_organo || g.organo;
  async function cotejar(g: any) {
    setError(""); setEnviando(true);
    try {
      const x = await api.post("/agenda/estrados/cotejar", { fecha: fechaP, texto, fuente: "pjf", id_organo: g.id_organo || null, sala: g.id_organo ? null : g.organo });
      setTexto(""); setAbierto(null);
      onListo(x.nuevas.length ? `${g.organo}: ${x.nuevas.length} acuerdo(s) nuevo(s) de sus expedientes. Ya avisamos a los responsables.`
        : x.ya_registradas ? `${g.organo}: esos acuerdos ya estaban registrados.` : `${g.organo}: ninguno de sus expedientes aparece en ese resultado.`);
    } catch (e: any) { setError(e.message); } finally { setEnviando(false); }
  }
  return (
    <section className="tarjeta mb-5 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><h2 className="font-semibold text-marino">Revisión diaria del PJF</h2>
          <p className="max-w-3xl text-xs text-slate-500">La Lista de acuerdos federal pide «No soy un robot», por eso no se revisa sola. Por cada juzgado: copie los expedientes, búsquelos todos a la vez en la consulta oficial y pegue aquí el resultado.</p></div>
        <a href={consulta} target="_blank" rel="noopener noreferrer" className="btn-sec">Abrir Lista de acuerdos del PJF ↗</a>
      </div>
      <ul className="mt-3 divide-y divide-crema-200">{grupos.map((g) => (
        <li key={clave(g)} className="py-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><p className="font-semibold text-marino">{g.organo}</p><p className="text-xs text-slate-500">{g.circuito} · {g.expedientes.length} expediente(s)</p></div>
            <div className="flex flex-wrap items-center gap-2">
              <code className="rounded-lg bg-crema px-2 py-1 font-mono text-xs">{g.busqueda}</code>
              <button className="text-xs font-semibold text-turquesa-700 underline" onClick={() => { navigator.clipboard?.writeText(g.busqueda); setCopiado(clave(g)); }}>
                {copiado === clave(g) ? "✓ Copiados" : "Copiar expedientes"}</button>
              {puedeEditar && <button className="text-xs font-semibold text-turquesa-700 underline" onClick={() => { setAbierto(abierto === clave(g) ? null : clave(g)); setTexto(""); setError(""); }}>Pegar resultado</button>}
            </div>
          </div>
          {abierto === clave(g) && <div className="mt-2 space-y-2 rounded-xl bg-crema/60 p-3">
            <ol className="list-decimal space-y-0.5 pl-5 text-xs text-slate-600">
              <li>En la consulta oficial elija «Por Órgano Jurisdiccional»: {g.circuito} → <b>{g.organo}</b>, y la fecha.</li>
              <li>En «Número de expediente» pegue: <span className="font-mono">{g.busqueda}</span></li>
              <li>Marque «No soy un robot», busque y copie todo el resultado.</li></ol>
            <div className="grid gap-2 sm:grid-cols-[12rem_1fr]">
              <label><span className="etiqueta">Fecha de la lista</span><input className="campo" type="date" max={hoyLocal()} value={fechaP} onChange={(e) => setFechaP(e.target.value)} /></label>
              <label><span className="etiqueta">Resultado de la consulta</span><textarea className="campo font-mono text-xs" rows={5} value={texto} onChange={(e) => setTexto(e.target.value)} /></label>
            </div>
            <Aviso>{error}</Aviso>
            <div className="flex justify-end"><button className="btn-turquesa" disabled={enviando || texto.trim().length < 5} onClick={() => cotejar(g)}>{enviando ? "Buscando…" : "Buscar mis expedientes"}</button></div>
          </div>}
        </li>))}</ul>
    </section>
  );
}
