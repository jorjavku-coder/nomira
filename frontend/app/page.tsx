"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Chip, Modal } from "@/components/ui";
import { api, fecha, mxn } from "@/lib/api";

function quincenasEntre(ini: string, fin: string): number | null {
  if (!ini || !fin) return null;
  const [a1, m1, d1] = ini.split("-").map(Number);
  const [a2, m2, d2] = fin.split("-").map(Number);
  const finMes = new Date(a2, m2, 0).getDate();
  if (![1, 16].includes(d1) || ![15, finMes].includes(d2)) return null;
  const n = (a2 * 12 + m2) * 2 + (d2 === 15 ? 1 : 2) - ((a1 * 12 + m1) * 2 + (d1 === 1 ? 1 : 2)) + 1;
  return n > 0 ? n : null;
}

function NuevoExpediente({ onCerrar, onCreado }: { onCerrar: () => void; onCreado: (id: number) => void }) {
  const [versiones, setVersiones] = useState<any[]>([]);
  const [f, setF] = useState({ trabajador_nombre: "", identificador_laboral: "", periodo_inicio: "", periodo_fin: "", quincenas_esperadas: "", catalogo_version_id: "" });
  const [error, setError] = useState("");
  useEffect(() => {
    api.get("/catalogos").then((cats: any[]) => {
      const activas = cats.flatMap((c) => c.versiones.filter((v: any) => v.estado === "activo"));
      setVersiones(activas);
      if (activas.length === 1) setF((x) => ({ ...x, catalogo_version_id: String(activas[0].id) }));
    }).catch((e) => setError(e.message));
  }, []);
  const calculadas = quincenasEntre(f.periodo_inicio, f.periodo_fin);
  const cambiar = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const r = await api.post("/expedientes", {
        ...f, identificador_laboral: f.identificador_laboral || null,
        quincenas_esperadas: f.quincenas_esperadas ? Number(f.quincenas_esperadas) : null,
        catalogo_version_id: Number(f.catalogo_version_id),
      });
      onCreado(r.id);
    } catch (err: any) {
      setError(err.message);
    }
  }
  return (
    <Modal titulo="Nuevo expediente" onCerrar={onCerrar}>
      <form onSubmit={enviar} className="space-y-3">
        <label className="block"><span className="etiqueta">Nombre del trabajador</span>
          <input className="campo" required minLength={2} value={f.trabajador_nombre} onChange={cambiar("trabajador_nombre")} /></label>
        <label className="block"><span className="etiqueta">Identificador laboral (opcional)</span>
          <input className="campo" value={f.identificador_laboral} onChange={cambiar("identificador_laboral")} placeholder="Clave de servidor" />
          <span className="mt-1 block text-xs text-slate-500">Si lo captura, los recibos se asignan por este identificador y no por el nombre.</span></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="etiqueta">Periodo: inicio</span>
            <input className="campo" type="date" required value={f.periodo_inicio} onChange={cambiar("periodo_inicio")} /></label>
          <label className="block"><span className="etiqueta">Periodo: fin</span>
            <input className="campo" type="date" required value={f.periodo_fin} onChange={cambiar("periodo_fin")} /></label>
        </div>
        <p className="text-xs text-slate-500">Debe iniciar el día 1 o 16 y terminar el día 15 o fin de mes.
          {calculadas !== null && <> El periodo contiene <b>{calculadas}</b> quincenas.</>}</p>
        <label className="block"><span className="etiqueta">Quincenas esperadas</span>
          <input className="campo" type="number" min={1} max={600} value={f.quincenas_esperadas} onChange={cambiar("quincenas_esperadas")}
            placeholder={calculadas !== null ? `${calculadas} (según el periodo)` : "p. ej. 72"} /></label>
        <label className="block"><span className="etiqueta">Catálogo de prestaciones (versión validada)</span>
          <select className="campo" required value={f.catalogo_version_id} onChange={cambiar("catalogo_version_id")}>
            <option value="">Seleccione…</option>
            {versiones.map((v) => <option key={v.id} value={v.id}>{v.catalogo} — versión {v.numero} ({v.entradas_total} claves)</option>)}
          </select>
          {versiones.length === 0 && <span className="mt-1 block text-xs text-amber-700">No hay catálogos validados. Un administrador debe activar uno en «Catálogos».</span>}</label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario">Crear expediente</button></div>
      </form>
    </Modal>
  );
}

export default function Expedientes() {
  const sesion = useSesion();
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const cargar = useCallback(() => api.get("/expedientes").then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const editor = sesion && sesion.usuario.rol !== "consulta";
  const conPendientes = (lista || []).filter((e) => e.estado !== "validado" && e.resumen.alertas_bloqueantes > 0);
  const tarjetas = [
    { t: "Expedientes", v: lista?.length ?? "—" },
    { t: "Con pendientes de revisión", v: lista ? conPendientes.length : "—", alerta: conPendientes.length > 0 },
    { t: "Listos para validar", v: lista ? lista.filter((e) => e.estado === "pendiente_revision" && e.resumen.alertas_bloqueantes === 0).length : "—" },
    { t: "Validados", v: lista ? lista.filter((e) => e.estado === "validado").length : "—" },
  ];
  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-extrabold text-marino">Expedientes</h1><p className="mt-1 text-sm text-slate-500">Sus expedientes y lo que falta por revisar en cada uno.</p></div>
        {editor && <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo expediente</button>}
      </div>
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {tarjetas.map((c) => (
          <div key={c.t} className={`tarjeta p-5 ${c.alerta ? "border-amber-300 bg-amber-50" : ""}`}>
            <div className="etiqueta">{c.t}</div>
            <div className="font-marca text-3xl font-extrabold text-marino">{c.v}</div>
          </div>
        ))}
      </div>
      <Aviso>{error}</Aviso>
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Expediente</th><th>Trabajador</th><th>Periodo</th><th>Estado</th><th>Pendientes</th><th>Quincenas</th><th className="num">Total autorizado</th></tr></thead>
          <tbody>
            {lista === null && <tr><td colSpan={7} className="text-slate-500">Cargando…</td></tr>}
            {lista?.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-slate-500">Aún no hay expedientes.{editor && " Cree el primero con «Nuevo expediente»."}</td></tr>}
            {lista?.map((e) => (
              <tr key={e.id} className="hover:bg-marino-50/50">
                <td><Link className="font-semibold text-marino underline-offset-2 hover:underline" href={`/expedientes/${e.id}`}>#{e.id}</Link></td>
                <td><Link href={`/expedientes/${e.id}`} className="hover:underline">{e.trabajador_nombre}</Link>
                  <div className="text-xs text-slate-500">{e.catalogo.nombre} · v{e.catalogo.version}</div></td>
                <td className="whitespace-nowrap">{fecha(e.periodo_inicio)} – {fecha(e.periodo_fin)}</td>
                <td><Chip estado={e.estado} /></td>
                <td>{e.estado === "validado" ? <span className="text-slate-400">—</span>
                  : e.resumen.alertas_bloqueantes > 0 ? <span className="font-semibold text-amber-700">{e.resumen.alertas_bloqueantes} por resolver</span>
                  : <span className="text-emerald-700">Sin pendientes</span>}</td>
                <td className="whitespace-nowrap">{e.resumen.quincenas_con_recibo}/{e.resumen.quincenas_esperadas}
                  {e.resumen.quincenas_faltantes > 0 && <span className="ml-1 text-xs text-red-700">({e.resumen.quincenas_faltantes} faltantes)</span>}</td>
                <td className="num">{e.total_expediente === null ? "Por plaza" : mxn(e.total_expediente)}
                  {e.provisional && <div className="font-sans text-xs text-amber-700">provisional</div>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {nuevo && <NuevoExpediente onCerrar={() => setNuevo(false)} onCreado={(id) => (window.location.href = `/expedientes/${id}`)} />}
    </Shell>
  );
}
