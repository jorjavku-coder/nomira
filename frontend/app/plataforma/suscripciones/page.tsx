"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import ShellPlataforma, { EstadoSuscripcion, RegistrarPeriodo, Tarjeta } from "@/components/plataforma";
import { Aviso } from "@/components/ui";
import { fecha, mxn } from "@/lib/api";
import { apiP, avisarContadores } from "@/lib/plataforma";

const FILTROS: [string, string, (x: any) => boolean][] = [
  ["atencion", "Requieren atención", (x) => ["por_vencer", "vencida", "sin_plan"].includes(x.estado) || x.pagos_pendientes > 0],
  ["prueba", "En prueba", (x) => x.estado === "prueba"],
  ["activa", "Activas", (x) => ["activa", "por_vencer", "programada"].includes(x.estado)],
  ["todas", "Todas", () => true],
];
// Lo urgente primero
const ORDEN: Record<string, number> = { vencida: 0, por_vencer: 1, prueba: 2, sin_plan: 3, programada: 4, activa: 5 };

export default function Suscripciones() {
  const [lista, setLista] = useState<any[] | null>(null);
  const [r, setR] = useState<any>(null);
  const [filtro, setFiltro] = useState("atencion");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [registrar, setRegistrar] = useState<any>(null);
  const cargar = useCallback(() => Promise.all([apiP.get("/suscripciones"), apiP.get("/resumen")])
    .then(([l, res]) => { setLista(l); setR(res); }).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const visibles = useMemo(() => {
    const fn = FILTROS.find(([v]) => v === filtro)![2];
    return (lista || []).filter(fn).sort((a, b) => (ORDEN[a.estado] - ORDEN[b.estado]) || (a.fin || "").localeCompare(b.fin || ""));
  }, [lista, filtro]);
  const cuenta = (v: string) => (lista || []).filter(FILTROS.find(([x]) => x === v)![2]).length;

  return (
    <ShellPlataforma>
      <h1 className="text-3xl font-extrabold text-marino">Suscripciones</h1>
      <p className="mb-5 mt-1 text-sm text-slate-500">Periodos de venta de cada cliente: prueba gratuita de 2 días, mensual, semestral o anual.</p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Tarjeta etiqueta="En prueba" valor={r ? r.en_prueba : "—"} nota="2 días gratis" />
        <Tarjeta etiqueta="Por vencer" valor={r ? r.por_vencer : "—"} nota="7 días o menos, sin renovar" alerta={!!r?.por_vencer} />
        <Tarjeta etiqueta="Vencidas" valor={r ? r.vencidas : "—"} alerta={!!r?.vencidas} />
        <Tarjeta etiqueta="Sin plan" valor={r ? r.sin_plan : "—"} />
        <Tarjeta etiqueta="Pagos pendientes" valor={r ? r.pagos_pendientes : "—"} alerta={!!r?.pagos_pendientes} />
      </div>
      <div className="mb-3 mt-6 flex flex-wrap gap-2" role="tablist">
        {FILTROS.map(([v, t]) => (
          <button key={v} role="tab" aria-selected={filtro === v} onClick={() => setFiltro(v)}
            className={`rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${filtro === v ? "bg-marino text-white" : "bg-white text-slate-600 ring-1 ring-crema-300 hover:bg-crema"}`}>{t} ({lista ? cuenta(v) : "…"})</button>
        ))}
      </div>
      <div className="mb-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Cliente</th><th>Situación</th><th>Periodo actual</th><th>Pago</th><th className="num">Total cobrado</th><th></th></tr></thead>
          <tbody>
            {lista === null && <tr><td colSpan={6} className="text-slate-500">Cargando…</td></tr>}
            {lista && visibles.length === 0 && <tr><td colSpan={6} className="py-8 text-center text-slate-500">{filtro === "atencion" ? "Todo en orden. 🎉" : "Sin clientes en esta vista."}</td></tr>}
            {visibles.map((x) => (
              <tr key={x.id}>
                <td><Link className="font-semibold text-marino hover:underline" href={`/plataforma/clientes/${x.id}#suscripcion`}>{x.nombre}</Link>
                  {x.estado_cuenta !== "activa" && <div className="text-xs font-semibold text-red-700">Cuenta suspendida</div>}</td>
                <td><EstadoSuscripcion s={x} />{x.siguiente && <div className="mt-1 text-xs text-emerald-700">Renovación: {x.siguiente.plan_nombre} desde {fecha(x.siguiente.inicio)}</div>}</td>
                <td className="whitespace-nowrap text-sm">{x.inicio ? `${fecha(x.inicio)} – ${fecha(x.fin)}` : "—"}</td>
                <td>{x.pagos_pendientes > 0
                  ? <span className="text-sm font-semibold text-amber-700">{x.pagos_pendientes} pendiente(s){x.monto_pendiente && Number(x.monto_pendiente) > 0 ? ` · ${mxn(x.monto_pendiente)}` : ""}</span>
                  : <span className="text-sm text-slate-400">Al corriente</span>}</td>
                <td className="num">{mxn(x.total_cobrado)}</td>
                <td className="text-right"><button className="btn-sec whitespace-nowrap" onClick={() => setRegistrar(x)}>
                  {["sin_plan", "vencida"].includes(x.estado) ? "Registrar venta" : "Renovar"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {registrar && <RegistrarPeriodo cliente={registrar} s={registrar} onCerrar={() => setRegistrar(null)}
        onListo={() => { setOk(`Periodo registrado para ${registrar.nombre}.`); setRegistrar(null); avisarContadores(); cargar(); }} />}
    </ShellPlataforma>
  );
}
