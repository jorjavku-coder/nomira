"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AforeShell, COLOR_CASO, Pastilla, mxnTexto, useCatalogos } from "@/components/afore";
import { Aviso } from "@/components/ui";
import { api, fecha } from "@/lib/api";

const FILTROS: Record<string, string> = { "": "Todos", abiertos: "Abiertos", esperando: "Esperando respuesta", docs_pendientes: "Con documentos pendientes",
  sin_siguiente: "Sin siguiente actividad", borradores: "Borradores" };

export default function Casos() {
  const cat = useCatalogos();
  const [f, setF] = useState<any>({ filtro: "", tipo: "", afore: "", responsable_id: "", estado: "", esperando_dias: "", q: "" });
  const [filas, setFilas] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [montos, setMontos] = useState(false);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("filtro")) setF((x: any) => ({ ...x, filtro: p.get("filtro") }));
  }, []);
  const consulta = () => new URLSearchParams(Object.entries(f).filter(([, v]) => v !== "") as [string, string][]).toString();
  const cargar = useCallback(() => {
    setFilas(null);
    api.get(`/afore/casos?${consulta()}`).then(setFilas).catch((e) => setError(e.message));
  }, [f]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const t = setTimeout(cargar, 250); return () => clearTimeout(t); }, [cargar]);
  const cambiar = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const val = (d: any) => d?.estado === "informado" ? mxnTexto(d.valor) : d?.estado ? cat?.estados_dato[d.estado] : "—";
  return (
    <AforeShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-extrabold text-marino">Casos AFORE</h1>
        <div className="flex gap-2">
          <button className="btn-sec" onClick={() => api.descargar(`/afore/reportes/excel?${consulta()}`, "casos-afore.xlsx").catch((e) => setError(e.message))}>Exportar reporte (Excel)</button>
          <Link href="/afore/casos/nuevo" className="btn-turquesa">+ Nuevo caso</Link>
        </div>
      </div>
      <div className="tarjeta mb-4 grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        <input className="campo" placeholder="Buscar cliente o referencia" value={f.q} onChange={cambiar("q")} aria-label="Buscar" />
        <select className="campo" value={f.filtro} onChange={cambiar("filtro")} aria-label="Vista">{Object.entries(FILTROS).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
        <select className="campo" value={f.tipo} onChange={cambiar("tipo")} aria-label="Tipo de problema"><option value="">Todos los problemas</option>
          {cat && Object.entries(cat.tipos).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select>
        <input className="campo" list="afores" placeholder="AFORE" value={f.afore} onChange={cambiar("afore")} aria-label="AFORE" />
        <datalist id="afores">{cat?.afores.map((x: string) => <option key={x} value={x} />)}</datalist>
        <select className="campo" value={f.responsable_id} onChange={cambiar("responsable_id")} aria-label="Responsable"><option value="">Todos los responsables</option>
          {cat?.responsables.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select>
        <select className="campo" value={f.estado} onChange={cambiar("estado")} aria-label="Estado"><option value="">Todos los estados</option>
          {cat && Object.entries(cat.estados_caso).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select>
        <select className="campo" value={f.esperando_dias} onChange={cambiar("esperando_dias")} aria-label="Tiempo esperando respuesta"><option value="">Cualquier espera</option>
          {[7, 15, 30, 60, 90].map((d) => <option key={d} value={d}>Esperando {d}+ días</option>)}</select>
      </div>
      <label className="mb-3 flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={montos} onChange={(e) => setMontos(e.target.checked)} />
        Mostrar montos (datos capturados, no verificados por Nomira)</label>
      <Aviso>{error}</Aviso>
      {!filas ? <p className="text-sm text-slate-500">Cargando…</p> : filas.length === 0 ? (
        <div className="tarjeta p-10 text-center text-sm text-slate-500">No hay casos con estos filtros.</div>
      ) : (
        <div className="tarjeta overflow-x-auto">
          <table className="tabla">
            <thead><tr><th>Cliente</th><th>Problema</th><th>AFORE</th><th>Estado</th><th>Responsable</th><th>Docs pendientes</th><th>Esperando</th><th>Siguiente actividad</th>
              {montos && <><th>Monto cliente*</th><th>Monto AFORE*</th><th>Entregado*</th></>}</tr></thead>
            <tbody>
              {filas.map((c) => (
                <tr key={c.id}>
                  <td><Link className="font-semibold text-marino hover:underline" href={`/afore/casos/${c.id}`}>{c.cliente}</Link>
                    {c.identificador_interno && <div className="text-xs text-slate-500">Ref. {c.identificador_interno}</div>}
                    {c.restringido && <div className="text-[11px] font-semibold text-red-700">Restringido</div>}</td>
                  <td className="max-w-[16rem] text-sm">{c.tipo_texto}</td>
                  <td>{c.afore || <span className="text-slate-400">—</span>}</td>
                  <td><Pastilla clase={COLOR_CASO[c.estado]}>{c.estado_texto}</Pastilla></td>
                  <td className="text-sm">{c.responsable || "—"}</td>
                  <td>{c.documentos_pendientes || "—"}</td>
                  <td>{c.dias_esperando != null ? `${c.dias_esperando} día(s)` : "—"}</td>
                  <td className="text-sm">{c.siguiente_actividad ? <>{c.siguiente_actividad}{c.siguiente_fecha && <div className="text-xs text-slate-500">{fecha(c.siguiente_fecha)}</div>}</> : <span className="text-amber-700">Sin definir</span>}</td>
                  {montos && <><td>{val(c.montos.monto_cliente)}</td><td>{val(c.montos.monto_afore)}</td><td>{val(c.montos.monto_entregado)}</td></>}
                </tr>))}
            </tbody>
          </table>
          {montos && <p className="px-4 py-2 text-xs text-slate-500">* Datos capturados por el despacho a partir de lo que informa el cliente o la AFORE. Nomira no los verifica ni proyecta resultados.</p>}
        </div>
      )}
    </AforeShell>
  );
}
