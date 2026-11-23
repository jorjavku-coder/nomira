"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import Shell from "@/components/Shell";
import { Modal } from "@/components/ui";
import { manual, MANUALES } from "@/lib/ayuda";

/** Manual de un módulo: para qué sirve, pasos con captura, consejos y preguntas frecuentes. */
export default function ManualModulo() {
  const { modulo } = useParams<{ modulo: string }>();
  const m = manual(modulo);
  const [zoom, setZoom] = useState<{ src: string; alt: string } | null>(null);
  if (!m) return <Shell><p className="text-slate-600">No encontramos ese manual. <Link className="font-semibold text-turquesa-700 underline" href="/ayuda">Ver todos</Link></p></Shell>;
  const i = MANUALES.indexOf(m);
  return (
    <Shell>
      <Link href="/ayuda" className="text-sm font-semibold text-turquesa-700">← Ayuda y manuales</Link>
      <article className="mx-auto max-w-4xl">
        <h1 className="mt-2 text-3xl font-extrabold text-marino">{m.titulo}</h1>
        <p className="mt-2 text-lg text-slate-700">{m.resumen}</p>
        <section className="mt-5 rounded-2xl bg-turquesa-50 p-5">
          <h2 className="font-semibold text-marino">Para qué le sirve</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-700">{m.paraQue.map((x) => <li key={x}>{x}</li>)}</ul>
        </section>
        <nav className="mt-6 flex flex-wrap gap-2 text-sm" aria-label="Pasos">
          {m.pasos.map((p, n) => <a key={n} href={`#paso-${n + 1}`} className="rounded-full border border-crema-300 bg-white px-3 py-1 text-slate-700 hover:border-turquesa">{n + 1}. {p.titulo}</a>)}
        </nav>
        <ol className="mt-6 space-y-8">
          {m.pasos.map((p, n) => (
            <li key={n} id={`paso-${n + 1}`} className="scroll-mt-6">
              <div className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-marino font-marca text-sm font-bold text-white">{n + 1}</span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-xl font-bold text-marino">{p.titulo}</h2>
                  <p className="mt-1 leading-relaxed text-slate-700">{p.texto}</p>
                  {p.imagen && <button type="button" className="mt-3 block w-full overflow-hidden rounded-xl border border-crema-300 shadow-sm transition hover:shadow-flotante" onClick={() => setZoom({ src: `/ayuda/${p.imagen}.webp`, alt: p.alt || p.titulo })} aria-label={`Ampliar captura: ${p.alt || p.titulo}`}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={`/ayuda/${p.imagen}.webp`} alt={p.alt || p.titulo} loading="lazy" className="w-full" />
                  </button>}
                </div>
              </div>
            </li>))}
        </ol>
        {m.consejos.length > 0 && <section className="mt-10 rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <h2 className="font-semibold text-amber-900">Consejos</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-800">{m.consejos.map((x) => <li key={x}>{x}</li>)}</ul>
        </section>}
        {m.preguntas.length > 0 && <section className="mt-8">
          <h2 className="text-xl font-bold text-marino">Preguntas frecuentes</h2>
          <div className="mt-3 divide-y divide-crema-200 rounded-2xl border border-crema-300 bg-white">
            {m.preguntas.map((x, n) => <details key={n} id={`pregunta-${n + 1}`} className="group px-5 py-3">
              <summary className="cursor-pointer font-semibold text-marino">{x.p}</summary><p className="mt-2 text-slate-700">{x.r}</p></details>)}
          </div>
        </section>}
        <div className="mt-10 flex flex-wrap justify-between gap-3 border-t border-crema-300 pt-5 text-sm">
          {i > 0 ? <Link className="font-semibold text-turquesa-700" href={`/ayuda/${MANUALES[i - 1].clave}`}>← {MANUALES[i - 1].titulo}</Link> : <span />}
          <Link className="font-semibold text-slate-600" href="/soporte">¿Le quedó una duda? Escríbanos</Link>
          {i < MANUALES.length - 1 ? <Link className="font-semibold text-turquesa-700" href={`/ayuda/${MANUALES[i + 1].clave}`}>{MANUALES[i + 1].titulo} →</Link> : <span />}
        </div>
      </article>
      {zoom && <Modal titulo={zoom.alt} onCerrar={() => setZoom(null)} ancho="max-w-6xl">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={zoom.src} alt={zoom.alt} className="w-full rounded-lg" />
      </Modal>}
    </Shell>
  );
}
