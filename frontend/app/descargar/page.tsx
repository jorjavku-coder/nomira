"use client";
import Link from "next/link";
import Logo from "@/components/Logo";
import { BotonInstalar } from "@/components/AppInstalable";

const PUNTOS = [
  ["📅", "Su agenda a la mano", "Plazos y audiencias del día con un toque."],
  ["👥", "Clientes y cobranza", "Lo que le deben y lo que sigue con cada cliente."],
  ["💬", "Connect", "Responda a sus clientes y actualice sus asuntos desde el celular."],
  ["🧮", "Cálculos laborales", "Finiquitos y liquidaciones en plena audiencia."],
];

/** Página pública para instalar Nomira como app (Android, iPhone y computadora), sin tiendas. */
export default function Descargar() {
  return (
    <div className="min-h-screen bg-crema">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4"><Link href="/" aria-label="Nomira, inicio"><Logo /></Link>
        <Link href="/login" className="text-sm font-semibold text-marino hover:underline">Iniciar sesión</Link></header>
      <main className="mx-auto max-w-5xl px-5 pb-16 pt-4">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-marino-900 via-marino to-turquesa-700 p-8 text-white sm:p-12">
          <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-turquesa-brillante/25 blur-3xl" aria-hidden />
          <div className="relative flex flex-wrap items-center gap-8">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/app/icono-512.png" alt="Ícono de la app de Nomira" className="h-28 w-28 rounded-[28px] shadow-2xl" />
            <div className="max-w-xl">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-turquesa-brillante">Android · iPhone · computadora</p>
              <h1 className="mt-2 font-marca text-3xl font-extrabold sm:text-4xl">Nomira en su celular</h1>
              <p className="mt-3 text-lg text-white/80">Instálela en segundos, sin tienda de aplicaciones y casi sin ocupar espacio. Se abre con su ícono, en pantalla completa y siempre en su versión más nueva.</p>
              <div className="mt-6 flex flex-wrap items-center gap-3"><BotonInstalar oscuro className="btn-turquesa px-6 py-3 text-base" />
                <Link href="/login?registro=1" className="rounded-xl border border-white/25 px-5 py-3 font-semibold text-white transition hover:bg-white/10">Crear cuenta gratis</Link></div>
              <p className="mt-3 text-xs text-white/60">En iPhone se instala desde Safari. Necesita una cuenta de Nomira para entrar.</p>
            </div>
          </div>
        </div>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{PUNTOS.map(([i, t, x]) => (
          <div key={t} className="tarjeta p-5"><p className="text-2xl" aria-hidden>{i}</p><p className="mt-2 font-bold text-marino">{t}</p><p className="mt-1 text-sm text-slate-600">{x}</p></div>))}</div>
      </main>
    </div>
  );
}
