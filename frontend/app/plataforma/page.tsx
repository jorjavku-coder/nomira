"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import ShellPlataforma, { Tarjeta } from "@/components/plataforma";
import { Aviso, Chip } from "@/components/ui";
import { fechaHora } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

export default function Resumen() {
  const [r, setR] = useState<any>(null);
  const [sol, setSol] = useState<any[]>([]);
  const [tick, setTick] = useState<any[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([apiP.get("/resumen"), apiP.get("/solicitudes"), apiP.get("/soporte")])
      .then(([a, b, c]) => { setR(a); setSol(b.filter((s: any) => s.estado === "nueva").slice(0, 5)); setTick(c.filter((t: any) => !t.leido_plataforma || t.estado === "abierto").slice(0, 5)); })
      .catch((e) => setError(e.message));
  }, []);
  return (
    <ShellPlataforma>
      <h1 className="text-3xl font-extrabold text-marino">Resumen</h1>
      <p className="mb-6 mt-1 text-sm text-slate-500">Lo que necesita su atención en Nomira.</p>
      <Aviso>{error}</Aviso>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Tarjeta etiqueta="Solicitudes nuevas" valor={r ? r.solicitudes_nuevas : "—"} nota="Prospectos sin atender" alerta={!!r?.solicitudes_nuevas} href="/plataforma/solicitudes" />
        <Tarjeta etiqueta="Mensajes sin leer" valor={r ? r.tickets_sin_leer : "—"} nota={r ? (r.tickets_abiertos === 1 ? "1 conversación abierta" : `${r.tickets_abiertos} conversaciones abiertas`) : ""} alerta={!!r?.tickets_sin_leer} href="/plataforma/soporte" />
        <Tarjeta etiqueta="Clientes activos" valor={r ? r.clientes_activos : "—"} nota={r?.clientes_suspendidos ? `${r.clientes_suspendidos} suspendido(s)` : "Ninguno suspendido"} href="/plataforma/clientes" />
        <Tarjeta etiqueta="Usuarios activos" valor={r ? r.usuarios_activos : "—"} nota="En todos los clientes" />
      </div>
      <div className="mt-8 grid gap-6 xl:grid-cols-2">
        <section className="tarjeta">
          <div className="flex items-center justify-between border-b border-crema-300 px-5 py-3"><h2 className="font-semibold text-marino">Solicitudes por atender</h2>
            <Link className="text-sm font-semibold text-turquesa-700 hover:underline" href="/plataforma/solicitudes">Ver todas →</Link></div>
          <ul className="divide-y divide-crema-300">
            {sol.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">Nada pendiente. 🎉</li>}
            {sol.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${s.tipo === "suscripcion" ? "bg-turquesa-100 text-turquesa-700" : "bg-marino-50 text-marino"}`}>{s.tipo === "suscripcion" ? "Suscripción" : "Informes"}</span>
                <span className="flex-1"><b className="text-marino">{s.nombre}</b>{s.empresa && <span className="text-slate-500"> · {s.empresa}</span>}</span>
                <span className="text-xs text-slate-500">{fechaHora(s.creado_en)}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="tarjeta">
          <div className="flex items-center justify-between border-b border-crema-300 px-5 py-3"><h2 className="font-semibold text-marino">Soporte</h2>
            <Link className="text-sm font-semibold text-turquesa-700 hover:underline" href="/plataforma/soporte">Ver todo →</Link></div>
          <ul className="divide-y divide-crema-300">
            {tick.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">Sin conversaciones abiertas.</li>}
            {tick.map((t) => (
              <li key={t.id}><Link href={`/plataforma/soporte?t=${t.id}`} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm hover:bg-crema/60">
                {!t.leido_plataforma && <span className="h-2 w-2 rounded-full bg-amber-500" aria-label="Sin leer" />}
                <span className="flex-1"><b className="text-marino">{t.asunto}</b><span className="text-slate-500"> · {t.organizacion}</span></span>
                <Chip estado={t.estado === "abierto" ? "pendiente" : "archivado"} texto={t.estado === "abierto" ? "Abierto" : "Cerrado"} />
              </Link></li>
            ))}
          </ul>
        </section>
      </div>
    </ShellPlataforma>
  );
}
