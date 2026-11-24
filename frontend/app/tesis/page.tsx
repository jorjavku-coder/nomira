"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { LeerTesis, TarjetaTesis } from "@/components/tesis";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

const EPOCAS = ["Duodécima Época", "Undécima Época", "Décima Época"];

export default function Tesis() {
  const [f, setF] = useState({ q: "", tipo: "", epoca: "" });
  const [pagina, setPagina] = useState(1);
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [leer, setLeer] = useState<number | null>(null);
  const [buscando, setBuscando] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => {
      setBuscando(true);
      const q = new URLSearchParams({ ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)), pagina: String(pagina) });
      api.get(`/tesis?${q}`).then((x) => { setR(x); setError(""); }).catch((e) => setError(e.message)).finally(() => setBuscando(false));
    }, 300);
    return () => clearTimeout(t);
  }, [f, pagina]);
  const pon = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setPagina(1); setF({ ...f, [k]: e.target.value }); };
  const paginas = r ? Math.min(50, Math.ceil(r.total / 20)) : 1;
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Semanario Judicial de la Federación</p>
          <h1 className="text-3xl font-extrabold text-marino">Buscador de tesis</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Tesis y jurisprudencia oficiales con su registro digital y liga al Semanario. ¿Quiere que la IA le explique cuáles aplican? Use <Link href="/asistente?tipo=investigar" className="font-semibold text-turquesa-700 underline">Investigar con tesis</Link>.</p></div>
        <BotonAyuda modulo="tesis" />
      </div>
      <form className="grid gap-2 sm:grid-cols-[1fr_auto_auto]" role="search" onSubmit={(e) => e.preventDefault()}>
        <input className="campo" aria-label="Buscar tesis" placeholder="Palabras del rubro o del texto, o un registro digital (ej. 2031967)" value={f.q} onChange={pon("q")} />
        <select className="campo" aria-label="Tipo" value={f.tipo} onChange={pon("tipo")}><option value="">Jurisprudencia y aisladas</option><option value="jurisprudencia">Solo jurisprudencia</option><option value="aislada">Solo aisladas</option></select>
        <select className="campo" aria-label="Época" value={f.epoca} onChange={pon("epoca")}><option value="">Todas las épocas</option>{EPOCAS.map((x) => <option key={x}>{x}</option>)}</select>
      </form>
      <div className="mt-3"><Aviso>{error}</Aviso></div>
      {r && <p className="mt-3 text-sm text-slate-500" aria-live="polite">{buscando ? "Buscando…" : f.q ? `${r.total.toLocaleString("es-MX")} resultado${r.total === 1 ? "" : "s"}` : "Escriba para buscar"} · Biblioteca: {Number(r.en_biblioteca).toLocaleString("es-MX")} tesis</p>}
      {r && !r.en_biblioteca && <Aviso tipo="info">La biblioteca de tesis todavía se está cargando desde las fuentes oficiales de la SCJN. Vuelva más tarde.</Aviso>}
      <ul className="mt-3 space-y-2">{r?.resultados.map((t: any) => <TarjetaTesis key={t.registro} t={t} onLeer={() => setLeer(t.registro)} />)}</ul>
      {r && f.q && !r.total && r.en_biblioteca > 0 && <p className="tarjeta mt-2 p-6 text-center text-slate-600">Sin resultados. Pruebe con menos palabras o sinónimos.</p>}
      {paginas > 1 && <div className="mt-5 flex justify-center gap-2">
        <button className="btn-sec" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</button>
        <span className="self-center text-sm text-slate-600">Página {pagina} de {paginas}</span>
        <button className="btn-sec" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>Siguiente</button></div>}
      <p className="mt-6 text-xs text-slate-500">Nomira guarda una copia del registro oficial para buscar rápido. La versión que vale es la del Semanario Judicial de la Federación: ábrala con «Ver en el Semanario» antes de citar.</p>
      {leer && <LeerTesis registro={leer} onCerrar={() => setLeer(null)} />}
    </Shell>
  );
}
