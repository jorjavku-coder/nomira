"use client";
import { useEffect, useMemo, useState } from "react";
import Shell from "@/components/Shell";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const ICONO: Record<string, string> = { salud: "🩺", oficina: "🖇️", tecnologia: "💻", capacitacion: "🎓", finanzas: "📊", autos: "🚗",
  viajes: "✈️", restaurantes: "🍽️", bienestar: "🧘", otros: "🎁" };
const fecha = (d?: string | null) => d ? new Date(d + "T12:00").toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" }) : "";

/** Club Nomira: beneficios de empresas aliadas para los despachos que usan Nomira, y la credencial digital. */
export default function Club() {
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const [cat, setCat] = useState("todas");
  const [q, setQ] = useState("");
  const [abierto, setAbierto] = useState<any>(null);
  const [credencial, setCredencial] = useState(false);
  useEffect(() => { api.get("/club").then(setD).catch((e) => setError(e.message)); }, []);
  const lista = useMemo(() => (d?.beneficios || []).filter((b: any) => (cat === "todas" || b.categoria === cat)
    && (!q.trim() || `${b.titulo} ${b.resumen} ${b.aliado.nombre} ${b.descripcion || ""}`.toLowerCase().includes(q.trim().toLowerCase()))), [d, cat, q]);
  const usadas = useMemo(() => new Set((d?.beneficios || []).map((b: any) => b.categoria)), [d]);
  const abrir = async (b: any) => { setAbierto(b); api.post(`/club/beneficios/${b.id}/uso`, { tipo: "vista" }).catch(() => {}); };
  return (
    <Shell>
      <div className="relative mb-6 overflow-hidden rounded-3xl bg-gradient-to-br from-marino-900 via-marino to-marino-700 p-6 text-white sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-turquesa/25 blur-3xl" aria-hidden />
        <div className="relative flex flex-wrap items-end justify-between gap-5">
          <div className="max-w-xl"><p className="text-xs font-bold uppercase tracking-[0.16em] text-turquesa-brillante">Club Nomira</p>
            <h1 className="mt-1 font-marca text-3xl font-extrabold">Beneficios para su despacho</h1>
            <p className="mt-2 text-white/75">Descuentos y promociones de empresas aliadas, solo por usar Nomira. Sin costo extra.</p></div>
          {d && <button onClick={() => setCredencial(true)} className="rounded-2xl bg-white/10 px-4 py-3 text-left ring-1 ring-white/20 transition hover:bg-white/15">
            <span className="block text-[11px] font-bold uppercase tracking-wider text-turquesa-brillante">Mi credencial</span>
            <span className="font-mono text-lg font-bold">{d.credencial.codigo}</span>
            <span className={`ml-2 rounded-full px-2 py-0.5 text-[11px] font-bold ${d.credencial.vigente ? "bg-emerald-400/20 text-emerald-200" : "bg-white/15 text-white/70"}`}>{d.credencial.vigente ? "Vigente" : "Sin plan vigente"}</span></button>}
        </div>
      </div>
      <Aviso>{error}</Aviso>
      {d && !d.credencial.vigente && <Aviso tipo="alerta">Puede ver los beneficios, pero para canjearlos necesita un plan vigente de Nomira.</Aviso>}
      {d && <>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <input className="campo max-w-xs" placeholder="Buscar beneficio o empresa" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar" />
          {[["todas", "Todas"], ...Object.entries(d.categorias).filter(([k]) => usadas.has(k))].map(([k, t]) => (
            <button key={k as string} onClick={() => setCat(k as string)} className={`rounded-full border px-3 py-1.5 text-sm font-semibold ${cat === k ? "border-marino bg-marino text-white" : "border-crema-300 bg-white text-slate-600"}`}>
              {k !== "todas" && <span className="mr-1" aria-hidden>{ICONO[k as string]}</span>}{t as string}</button>))}
        </div>
        {!d.beneficios.length ? (
          <div className="tarjeta p-10 text-center"><p className="text-4xl" aria-hidden>🎁</p><p className="mt-2 text-lg font-bold text-marino">Muy pronto, los primeros beneficios</p>
            <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">Estamos sumando empresas aliadas para su despacho. Le avisaremos cuando estén disponibles.</p></div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{lista.map((b: any) => (
            <button key={b.id} onClick={() => abrir(b)} className="tarjeta group flex flex-col overflow-hidden text-left transition hover:-translate-y-0.5 hover:shadow-lg">
              <div className="flex items-center gap-3 border-b border-crema-300 p-4">
                <Logo b={b} />
                <div className="min-w-0"><p className="truncate font-bold text-marino">{b.aliado.nombre}</p><p className="truncate text-xs text-slate-500">{b.aliado.giro || b.categoria_texto}</p></div>
                {b.destacado && <span className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-800">Destacado</span>}
              </div>
              <div className="flex flex-1 flex-col p-4">
                <p className="font-marca text-2xl font-extrabold text-turquesa-700">{b.resumen}</p>
                <p className="mt-1 font-semibold text-marino">{b.titulo}</p>
                <p className="mt-auto pt-3 text-xs text-slate-500">{b.cobertura ? b.cobertura.join(", ") : "Todo México"}{b.vigente_hasta && ` · hasta el ${fecha(b.vigente_hasta)}`}</p>
              </div>
            </button>))}
            {!lista.length && <p className="text-sm text-slate-500">Nada con ese filtro.</p>}
          </div>)}
        <p className="mt-6 text-xs text-slate-500">Las promociones las ofrecen y respetan directamente las empresas aliadas, con sus propias condiciones. Nomira no comparte sus datos con ellas: solo les informa cuántos despachos usaron cada beneficio.</p>
      </>}
      {abierto && <Detalle b={abierto} vigente={d.credencial.vigente} onCerrar={() => setAbierto(null)} onCredencial={() => { setAbierto(null); setCredencial(true); }} />}
      {credencial && d && <Modal titulo="Mi credencial del Club Nomira" onCerrar={() => setCredencial(false)}><Credencial c={d.credencial} /></Modal>}
    </Shell>
  );
}

function Logo({ b, grande = false }: { b: any; grande?: boolean }) {
  const t = grande ? "h-16 w-16 text-2xl" : "h-11 w-11 text-lg";
  /* eslint-disable-next-line @next/next/no-img-element */
  return b.aliado.logo ? <img src={`/api/club-publico/logos/${b.aliado.id}`} alt="" className={`${t} shrink-0 rounded-xl bg-white object-contain p-1 ring-1 ring-crema-300`} />
    : <span className={`${t} flex shrink-0 items-center justify-center rounded-xl bg-turquesa-50`} aria-hidden>{ICONO[b.categoria] || "🎁"}</span>;
}

function Detalle({ b, vigente, onCerrar, onCredencial }: { b: any; vigente: boolean; onCerrar: () => void; onCredencial: () => void }) {
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [copiado, setCopiado] = useState(false);
  const canjear = async () => {
    try { const r = await api.post(`/club/beneficios/${b.id}/uso`, { tipo: "canje" }); setC(r); }
    catch (e: any) { setError(e.message); }
  };
  return (
    <Modal titulo={b.titulo} onCerrar={onCerrar} ancho="max-w-lg">
      <div className="flex items-center gap-3"><Logo b={b} grande /><div><p className="font-bold text-marino">{b.aliado.nombre}</p>
        {b.aliado.sitio && <a href={b.aliado.sitio} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-turquesa-700">{b.aliado.sitio.replace(/^https:\/\//, "")}</a>}</div></div>
      <p className="mt-4 font-marca text-3xl font-extrabold text-turquesa-700">{b.resumen}</p>
      {b.descripcion && <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{b.descripcion}</p>}
      <dl className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-crema/60 p-3 text-sm">
        <div><dt className="text-xs text-slate-500">Cómo se canjea</dt><dd className="font-semibold text-marino">{b.canje_texto}</dd></div>
        <div><dt className="text-xs text-slate-500">Dónde</dt><dd className="font-semibold text-marino">{b.cobertura ? b.cobertura.join(", ") : "Todo México"}</dd></div>
        {b.vigente_hasta && <div><dt className="text-xs text-slate-500">Vigente hasta</dt><dd className="font-semibold text-marino">{fecha(b.vigente_hasta)}</dd></div>}
      </dl>
      {b.condiciones && <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold text-marino">Condiciones</summary><p className="mt-1 whitespace-pre-wrap text-slate-600">{b.condiciones}</p></details>}
      <Aviso>{error}</Aviso>
      {!vigente ? <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">Para canjear necesita un plan vigente de Nomira.</p>
        : b.canje === "credencial" ? <button className="btn-turquesa mt-4 w-full py-3" onClick={async () => { await canjear(); onCredencial(); }}>Mostrar mi credencial</button>
        : !c ? <button className="btn-turquesa mt-4 w-full py-3" onClick={canjear}>{b.canje === "codigo" ? "Ver mi código" : "Ir al sitio del aliado"}</button>
        : c.canje === "codigo" ? <div className="mt-4 rounded-2xl border-2 border-dashed border-turquesa p-4 text-center">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Su código</p>
            <p className="mt-1 font-mono text-3xl font-extrabold tracking-widest text-marino">{c.codigo}</p>
            <button className="btn-sec mt-3 text-sm" onClick={() => { navigator.clipboard.writeText(c.codigo); setCopiado(true); setTimeout(() => setCopiado(false), 2000); }}>{copiado ? "¡Copiado!" : "Copiar código"}</button>
            {c.enlace && <a href={c.enlace} target="_blank" rel="noopener noreferrer" className="btn-turquesa ml-2 mt-3 text-sm">Ir al sitio</a>}</div>
        : <a href={c.enlace} target="_blank" rel="noopener noreferrer" className="btn-turquesa mt-4 block w-full py-3 text-center">Abrir el sitio del aliado</a>}
    </Modal>
  );
}

function Credencial({ c }: { c: any }) {
  return (
    <div>
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-marino-900 via-marino to-turquesa-700 p-6 text-white shadow-xl">
        <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-turquesa-brillante/30 blur-2xl" aria-hidden />
        <div className="relative flex items-center justify-between"><span className="font-marca text-xl font-extrabold">nomira</span>
          <span className="rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider">Club Nomira</span></div>
        <p className="relative mt-8 text-xs uppercase tracking-wider text-white/60">Miembro</p>
        <p className="relative text-xl font-bold">{c.nombre}</p>
        <p className="relative text-sm text-white/75">{c.despacho}</p>
        <div className="relative mt-6 flex items-end justify-between">
          <span className="font-mono text-2xl font-extrabold tracking-widest">{c.codigo}</span>
          <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${c.vigente ? "bg-emerald-400 text-marino-900" : "bg-white/20"}`}>{c.vigente ? "● Vigente" : "Sin plan vigente"}</span>
        </div>
      </div>
      <p className="mt-4 text-sm text-slate-600">Muéstrela en el comercio. Para comprobarla, pueden abrir <b className="break-all text-marino">{c.verificar.replace(/^https?:\/\//, "")}</b>, que solo muestra su nombre, su despacho y si está vigente.</p>
    </div>
  );
}
