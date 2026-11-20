"use client";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import { fecha } from "@/lib/api";

/** Verificación pública de un diploma de Nomira Academia (a esta página lleva el código QR). */
export default function Verificar() {
  const [folio, setFolio] = useState("");
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  async function consultar(f: string) {
    const limpio = f.trim().toUpperCase();
    if (!limpio) return;
    setCargando(true); setError(""); setR(null);
    try {
      const x = await fetch(`/api/academia-publico/verificar/${encodeURIComponent(limpio)}`, { cache: "no-store" });
      const d = await x.json().catch(() => ({}));
      if (!x.ok) throw new Error(typeof d.detail === "string" ? d.detail : "No se pudo verificar.");
      setR(d);
    } catch (e: any) { setError(e.message); } finally { setCargando(false); }
  }
  useEffect(() => {
    const f = new URLSearchParams(window.location.search).get("folio") || "";
    setFolio(f);
    if (f) consultar(f);
  }, []);
  return (
    <main className="min-h-screen bg-crema">
      <header className="bg-marino-900 px-5 py-5"><div className="mx-auto max-w-2xl"><Logo oscuro /></div></header>
      <div className="h-1 bg-turquesa" />
      <div className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-3xl font-extrabold text-marino">Verificar un diploma</h1>
        <p className="mt-1 text-slate-600">Escriba el folio que aparece en el diploma o escanee su código QR.</p>
        <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); consultar(folio); }}>
          <input className="campo font-mono uppercase" aria-label="Folio" placeholder="NA-XXXX-XXXX" maxLength={20} value={folio} onChange={(e) => setFolio(e.target.value)} />
          <button className="btn-turquesa" disabled={cargando || !folio.trim()}>{cargando ? "Verificando…" : "Verificar"}</button>
        </form>
        {error && <p role="alert" className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</p>}
        {r?.valido && (
          <section className="tarjeta mt-6 border-2 border-emerald-300 p-6">
            <p className="flex items-center gap-2 text-lg font-bold text-emerald-800"><span aria-hidden className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500 text-white">✓</span>
              {r.tipo === "constancia" ? "Constancia auténtica" : "Diploma auténtico"}</p>
            <dl className="mt-4 grid grid-cols-[9rem_1fr] gap-y-2 text-sm">
              <dt className="text-slate-500">Otorgado a</dt><dd className="font-semibold text-marino">{r.participante}</dd>
              <dt className="text-slate-500">Curso</dt><dd>{r.curso}</dd>
              <dt className="text-slate-500">Emitido por</dt><dd>{r.organizacion}</dd>
              <dt className="text-slate-500">Fecha</dt><dd>{fecha(r.fecha)}</dd>
              {r.duracion_min && <><dt className="text-slate-500">Duración</dt><dd>{r.duracion_min >= 60 ? `${r.duracion_min / 60} h` : `${r.duracion_min} min`}</dd></>}
              <dt className="text-slate-500">Folio</dt><dd className="font-mono">{r.folio}</dd>
            </dl>
            <p className="mt-4 text-xs text-slate-500">Reconocimiento interno de capacitación emitido con Nomira Academia. No es una certificación oficial ni un aval institucional.</p>
          </section>)}
      </div>
    </main>
  );
}
