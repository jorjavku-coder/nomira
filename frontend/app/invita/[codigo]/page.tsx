"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";

const VENTAJAS = [
  ["📅", "Agenda con días hábiles", "Plazos y audiencias contando días hábiles."],
  ["🧮", "Cálculos laborales", "Finiquitos y liquidaciones con su operación y su artículo."],
  ["📚", "Tesis y jurisprudencia", "Busque tesis del Semanario Judicial de la Federación."],
  ["💬", "Portal para sus clientes", "Que sigan su asunto sin llamarle a cada rato."],
];

/** Invitación de un despacho a otro: guarda el código en este navegador y lleva al registro con prueba gratis. */
export default function Invitacion() {
  const { codigo } = useParams<{ codigo: string }>();
  const router = useRouter();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    fetch(`/api/invitacion/${encodeURIComponent(codigo)}`).then(async (r) => {
      if (!r.ok) throw new Error();
      const j = await r.json();
      setD(j);
      try { localStorage.setItem("nomira_invitacion", JSON.stringify({ ...j, guardada: Date.now() })); } catch { /* sin almacenamiento */ }
    }).catch(() => setError(true));
  }, [codigo]);
  return (
    <div className="min-h-screen bg-crema">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4"><Link href="/" aria-label="Nomira, inicio"><Logo /></Link>
        <Link href="/login" className="text-sm font-semibold text-marino hover:underline">Iniciar sesión</Link></header>
      <main className="mx-auto max-w-5xl px-5 pb-16 pt-6">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-marino-900 via-marino to-turquesa-700 p-8 text-white sm:p-12">
          <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-turquesa-brillante/25 blur-3xl" aria-hidden />
          {error ? <div className="relative"><h1 className="font-marca text-3xl font-extrabold">Esta invitación ya no está vigente</h1>
            <p className="mt-2 text-white/75">Puede probar Nomira gratis de todos modos.</p>
            <Link href="/login?registro=1" className="btn-turquesa mt-6 inline-block px-6 py-3">Probar 2 días gratis</Link></div>
          : <div className="relative max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-turquesa-brillante">Invitación</p>
            <h1 className="mt-2 font-marca text-3xl font-extrabold sm:text-4xl">{d ? <>{d.despacho} le invita a usar Nomira</> : "Cargando su invitación…"}</h1>
            <p className="mt-3 text-lg text-white/80">El software para despachos jurídicos en México. Pruébelo 2 días gratis, sin tarjeta.</p>
            {d && <p className="mt-4 inline-block rounded-2xl bg-white/10 px-4 py-2 text-sm ring-1 ring-white/20">🎁 Al contratar su primer plan, <b>usted y {d.despacho} reciben {d.meses} {d.meses === 1 ? "mes" : "meses"} gratis</b>.</p>}
            <div className="mt-7"><button className="btn-turquesa px-6 py-3 text-base" disabled={!d} onClick={() => router.push("/login?registro=1")}>Crear mi cuenta gratis</button></div>
          </div>}
        </div>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{VENTAJAS.map(([i, t, x]) => (
          <div key={t} className="tarjeta p-5"><p className="text-2xl" aria-hidden>{i}</p><p className="mt-2 font-bold text-marino">{t}</p><p className="mt-1 text-sm text-slate-600">{x}</p></div>))}</div>
      </main>
    </div>
  );
}
