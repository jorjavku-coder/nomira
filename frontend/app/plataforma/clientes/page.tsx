"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import ShellPlataforma, { Credenciales } from "@/components/plataforma";
import { Aviso, Chip, Modal } from "@/components/ui";
import { fecha, fechaHora } from "@/lib/api";
import { apiP } from "@/lib/plataforma";

export default function Clientes() {
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [acceso, setAcceso] = useState<any>(null);
  const cargar = useCallback(() => apiP.get("/clientes").then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const visibles = useMemo(() => (lista || []).filter((c) => !buscar || c.nombre.toLowerCase().includes(buscar.toLowerCase())), [lista, buscar]);
  return (
    <ShellPlataforma>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-marino">Clientes</h1>
          <p className="mt-1 text-sm text-slate-500">Empresas con cuenta en Nomira. Aquí se ven sus cuentas y números, nunca el contenido de sus expedientes.</p>
        </div>
        <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo cliente</button>
      </div>
      <Aviso>{error}</Aviso>
      <div className="tarjeta mt-3 overflow-x-auto">
        <div className="border-b border-crema-300 p-3"><input className="campo sm:max-w-xs" placeholder="Buscar cliente…" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar cliente" /></div>
        <table className="tabla">
          <thead><tr><th>Cliente</th><th>Estado</th><th className="num">Usuarios</th><th className="num">Expedientes</th><th>Último acceso</th><th>Soporte</th><th>Alta</th></tr></thead>
          <tbody>
            {lista === null && <tr><td colSpan={7} className="text-slate-500">Cargando…</td></tr>}
            {lista && visibles.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-slate-500">Sin clientes.</td></tr>}
            {visibles.map((c) => (
              <tr key={c.id}>
                <td><Link className="font-semibold text-marino hover:underline" href={`/plataforma/clientes/${c.id}`}>{c.nombre}</Link><div className="text-xs text-slate-400">#{c.id}</div></td>
                <td><Chip estado={c.estado === "activa" ? "activo" : "error"} texto={c.estado === "activa" ? "Activa" : "Suspendida"} /></td>
                <td className="num">{c.usuarios_activos}<span className="text-slate-400"> / {c.usuarios}</span></td>
                <td className="num">{c.expedientes}</td>
                <td className="whitespace-nowrap">{c.ultimo_acceso ? fechaHora(c.ultimo_acceso) : <span className="text-slate-400">Nunca</span>}</td>
                <td>{c.tickets_abiertos > 0 ? <span className="font-semibold text-amber-700">{c.tickets_abiertos} abierto(s)</span> : <span className="text-slate-400">—</span>}</td>
                <td className="whitespace-nowrap">{fecha(c.creado_en)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {nuevo && <NuevoCliente onCerrar={() => setNuevo(false)} onListo={(r) => { setNuevo(false); setAcceso(r.acceso); cargar(); }} />}
      {acceso && <Credenciales acceso={acceso} titulo="Cliente creado: datos de acceso" onCerrar={() => setAcceso(null)} />}
    </ShellPlataforma>
  );
}

function NuevoCliente({ onCerrar, onListo }: { onCerrar: () => void; onListo: (r: any) => void }) {
  const [f, setF] = useState({ organizacion: "", admin_nombre: "", admin_email: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try { onListo(await apiP.post("/clientes", f)); } catch (err: any) { setError(err.message); setEnviando(false); }
  }
  return (
    <Modal titulo="Nuevo cliente" onCerrar={onCerrar} ancho="max-w-xl">
      <form className="space-y-4" onSubmit={enviar}>
        <label className="block"><span className="etiqueta">Nombre de la empresa</span>
          <input className="campo" required minLength={2} autoFocus value={f.organizacion} onChange={(e) => setF({ ...f, organizacion: e.target.value })} /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">Su administrador</span>
            <input className="campo" required minLength={2} value={f.admin_nombre} onChange={(e) => setF({ ...f, admin_nombre: e.target.value })} /></label>
          <label className="block"><span className="etiqueta">Correo del administrador</span>
            <input className="campo" type="email" required value={f.admin_email} onChange={(e) => setF({ ...f, admin_email: e.target.value })} /></label>
        </div>
        <p className="text-xs text-slate-500">Se genera una contraseña temporal; el administrador del cliente la cambia al entrar y da de alta a su propio equipo.</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={enviando}>{enviando ? "Creando…" : "Crear cliente"}</button></div>
      </form>
    </Modal>
  );
}
