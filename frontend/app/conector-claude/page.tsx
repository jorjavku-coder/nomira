"use client";
import Link from "next/link";
import { useState } from "react";
import Logo from "@/components/Logo";

const URL_MCP = "https://nomirasoft.com/mcp";
const HERRAMIENTAS = [
  ["📚", "Tesis del Semanario Judicial", "Busca jurisprudencias y tesis aisladas por tema o registro digital, con su rubro, texto y enlace oficial."],
  ["🧮", "Finiquitos y liquidaciones", "Calcula con la Ley Federal del Trabajo cada concepto, con su operación y su artículo."],
  ["📅", "Plazos en días hábiles", "Cuenta un plazo desde la notificación, saltando fines de semana, el art. 74 LFT y los inhábiles que usted indique."],
];
const EJEMPLOS = [
  "Busca en Nomira jurisprudencia sobre litisconsorcio pasivo necesario y explícamela con sus registros.",
  "Con Nomira, calcula el finiquito por despido injustificado: entró el 1/3/2019, salió el 15/10/2025, salario diario $650.",
  "Me notificaron el 13 de noviembre de 2026; con Nomira, ¿cuándo vence un plazo de 15 días hábiles?",
];

/** Instrucciones públicas para agregar el conector MCP de Nomira a Claude. */
export default function ConectorClaude() {
  const [copiado, setCopiado] = useState(false);
  return (
    <div className="min-h-screen bg-crema">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4"><Link href="/" aria-label="Nomira, inicio"><Logo /></Link>
        <Link href="/precios" className="text-sm font-semibold text-marino hover:underline">Precios</Link></header>
      <main className="mx-auto max-w-5xl px-5 pb-16 pt-4">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-marino-900 via-marino to-turquesa-700 p-8 text-white sm:p-12">
          <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-turquesa-brillante/25 blur-3xl" aria-hidden />
          <div className="relative max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-turquesa-brillante">Gratis · conector MCP</p>
            <h1 className="mt-2 font-marca text-3xl font-extrabold sm:text-4xl">Nomira dentro de Claude</h1>
            <p className="mt-3 text-lg text-white/80">Pida a Claude que busque tesis, calcule finiquitos o cuente plazos, y él consulta a Nomira con fundamento y enlace oficial.</p>
            <div className="mt-6 flex flex-wrap items-center gap-2 rounded-2xl bg-white/10 p-2 ring-1 ring-white/20">
              <code className="min-w-0 flex-1 truncate px-3 font-mono text-base" data-prueba="url-mcp">{URL_MCP}</code>
              <button className="btn-turquesa" onClick={() => { navigator.clipboard.writeText(URL_MCP); setCopiado(true); setTimeout(() => setCopiado(false), 2000); }}>{copiado ? "¡Copiado!" : "Copiar dirección"}</button>
            </div>
          </div>
        </div>

        <section className="mt-8 grid gap-4 sm:grid-cols-3" aria-label="Herramientas">{HERRAMIENTAS.map(([i, t, x]) => (
          <div key={t} className="tarjeta p-5"><p className="text-2xl" aria-hidden>{i}</p><p className="mt-2 font-bold text-marino">{t}</p><p className="mt-1 text-sm text-slate-600">{x}</p></div>))}</section>

        <section className="tarjeta mt-8 p-6 sm:p-8" aria-labelledby="t-pasos">
          <h2 id="t-pasos" className="text-xl font-bold text-marino">Agréguelo en 3 pasos</h2>
          <ol className="mt-4 space-y-4 text-slate-700">
            <li><b className="text-marino">1. Abra los conectores de Claude.</b> En claude.ai o en la app de escritorio, vaya a <b>Personalizar → Conectores</b> (Customize → Connectors).</li>
            <li><b className="text-marino">2. Agregue un conector personalizado.</b> Elija <b>«Agregar conector personalizado»</b> (Add custom connector), escriba de nombre <b>Nomira</b> y pegue la dirección <code className="rounded bg-crema px-1.5 py-0.5 font-mono text-sm">{URL_MCP}</code>.</li>
            <li><b className="text-marino">3. Úselo.</b> No pide usuario ni contraseña. En un chat nuevo, pídale a Claude que use Nomira.</li>
          </ol>
          <p className="mt-4 rounded-xl bg-crema/70 p-3 text-sm text-slate-600">En planes Team o Enterprise, un administrador lo agrega primero en <b>Configuración de la organización → Conectores</b>; después cada persona lo activa. En el plan gratuito de Claude se puede tener un conector personalizado.</p>
        </section>

        <section className="mt-8" aria-labelledby="t-ej"><h2 id="t-ej" className="text-xl font-bold text-marino">Pruebe con estas preguntas</h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-3">{EJEMPLOS.map((e) => <li key={e} className="tarjeta p-4 text-sm text-slate-700">«{e}»</li>)}</ul></section>

        <section className="mt-8 grid gap-5 sm:grid-cols-2">
          <div className="tarjeta p-6"><h2 className="font-bold text-marino">Privacidad</h2>
            <p className="mt-1 text-sm text-slate-600">El conector solo consulta información pública (tesis, ley y calendario). No ve expedientes ni datos de ningún despacho, y no guardamos lo que pregunta.</p></div>
          <div className="tarjeta p-6"><h2 className="font-bold text-marino">¿Lleva un despacho?</h2>
            <p className="mt-1 text-sm text-slate-600">Agenda, clientes y cobranza, portal para sus clientes y mucho más en Nomira.</p>
            <div className="mt-3 flex flex-wrap gap-2"><Link href="/login?registro=1" className="btn-turquesa text-sm">Probar 2 días gratis</Link><Link href="/precios" className="btn-sec text-sm">Ver precios</Link></div></div>
        </section>
        <p className="mt-6 text-xs text-slate-500">Los cálculos son asistidos y deben revisarse por un abogado. Claude es una marca de Anthropic; Nomira no está afiliada a Anthropic.</p>
      </main>
    </div>
  );
}
