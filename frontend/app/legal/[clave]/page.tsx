"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { MarcoLegal, NOMBRE_DOC, RUTA_DOC, TextoLegal, legalPublico } from "@/components/legal";
import { fecha } from "@/lib/api";

/** Documento legal: muestra la versión vigente (o la elegida del historial) tal como fue aprobada. */
export default function DocumentoLegal() {
  const { clave } = useParams<{ clave: string }>();
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [versionId, setVersionId] = useState<string | null | undefined>(undefined);
  useEffect(() => { setVersionId(new URLSearchParams(window.location.search).get("version_id")); }, []);
  useEffect(() => {
    if (versionId === undefined) return;
    setR(null); setError("");
    legalPublico(`/documentos/${encodeURIComponent(clave)}${versionId ? `?version_id=${encodeURIComponent(versionId)}` : ""}`).then(setR).catch((e) => setError(e.message));
  }, [clave, versionId]);
  const ver = (id: number | null) => { setVersionId(id ? String(id) : null); history.replaceState(null, "", id ? `?version_id=${id}` : window.location.pathname); };
  const v = r?.version;
  return (
    <MarcoLegal>
      <Link href="/legal" className="text-sm font-semibold text-turquesa-700 hover:underline print:hidden">← Centro legal</Link>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      {!r && !error && <p className="mt-6 text-sm text-slate-500">Cargando…</p>}
      {r && <>
        <h1 className="mt-3 text-3xl font-extrabold text-marino">{v?.titulo || r.titulo}</h1>
        {!v ? (
          <div className="tarjeta mt-6 p-6 text-slate-700">
            <p className="font-semibold text-marino">Documento en preparación</p>
            <p className="mt-1 text-sm">Se publicará aquí cuando haya sido revisado y aprobado. {r.descripcion}</p>
            <p className="mt-3 text-sm">Si tiene dudas sobre sus datos personales, puede <Link className="font-semibold text-turquesa-700 underline" href="/legal/solicitudes">enviarnos una solicitud</Link>.</p>
          </div>
        ) : <>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
            <span>Versión <b>{v.version}</b></span>
            <span>Vigente desde {fecha(v.vigente_desde || v.publicado_en)}</span>
            {!v.es_vigente && <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">Versión anterior (no vigente)</span>}
            <button className="text-sm font-semibold text-turquesa-700 underline print:hidden" onClick={() => window.print()}>Imprimir o guardar como PDF</button>
          </div>
          {!v.es_vigente && <p className="mt-2 text-sm print:hidden"><button className="font-semibold text-turquesa-700 underline" onClick={() => ver(null)}>Ver la versión vigente</button></p>}
          <article className="tarjeta mt-6 p-6 sm:p-8 print:border-0 print:shadow-none"><TextoLegal texto={v.contenido} /></article>
          <p className="mt-2 break-all text-[11px] text-slate-400">Huella del texto (SHA-256): {v.sha256}</p>
        </>}
        {r.historial.length > 0 && (
          <section className="mt-8 print:hidden">
            <h2 className="font-bold text-marino">Historial de versiones</h2>
            <ul className="mt-2 divide-y divide-crema-300 text-sm">
              {r.historial.map((h: any) => (
                <li key={h.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span><b>Versión {h.version}</b> · publicada el {fecha(h.publicado_en)}{h.estado === "retirada" ? " · retirada" : ""}{h.resumen_cambios ? ` — ${h.resumen_cambios}` : ""}</span>
                  {v?.id === h.id ? <span className="text-xs text-slate-500">Mostrando</span> : <button className="text-sm font-semibold text-turquesa-700 underline" onClick={() => ver(h.id)}>Ver</button>}
                </li>))}
            </ul>
          </section>)}
        <p className="mt-8 text-xs text-slate-500 print:hidden">Otros documentos: {Object.entries(RUTA_DOC).filter(([k]) => k !== clave).map(([k, h], i) => <span key={k}>{i ? " · " : ""}<Link className="underline" href={h}>{NOMBRE_DOC[k]}</Link></span>)}</p>
      </>}
    </MarcoLegal>
  );
}
