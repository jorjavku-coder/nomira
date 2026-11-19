"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AforeShell, TarjetaMensaje } from "@/components/afore";
import { useSesion } from "@/components/Shell";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const BANDEJAS: Record<string, string> = { pendientes: "Por atender", por_aprobar: "Esperan aprobación", borradores: "Borradores", errores: "Con error",
  por_asignar: "Recibidos por asignar", recibidos: "Recibidos", enviados: "Enviados", todos: "Todos" };

export default function MensajesAfore() {
  const sesion = useSesion();
  const editor = !!sesion && sesion.usuario.rol !== "consulta";
  const [bandeja, setBandeja] = useState("pendientes");
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [asignar, setAsignar] = useState<any>(null);
  useEffect(() => { const b = new URLSearchParams(window.location.search).get("bandeja"); if (b && BANDEJAS[b]) setBandeja(b); }, []);
  const cargar = useCallback(() => api.get(`/afore/mensajes?bandeja=${bandeja}`).then(setR).catch((e) => setError(e.message)), [bandeja]);
  useEffect(() => { setR(null); cargar(); }, [cargar]);
  async function accion(fn: () => Promise<any>, mensaje = "") {
    setError(""); setOk("");
    try { const x = await fn(); if (mensaje) setOk(mensaje); await cargar(); return x ?? true; } catch (e: any) { setError(e.message); }
  }
  const esAdmin = sesion?.usuario.rol === "administrador";
  return (
    <AforeShell>
      <h1 className="text-3xl font-extrabold text-marino">Mensajes</h1>
      <p className="mt-1 text-sm text-slate-500">Toda comunicación automática empieza «Esperando aprobación»: nada sale sin que un administrador o el abogado responsable lo apruebe (salvo plantillas que el despacho marque como automáticas). Si falta algo, el mensaje queda como borrador con el motivo.</p>
      {r && !r.whatsapp_conectado && <div className="mt-3"><Aviso tipo="alerta">WhatsApp no está conectado: los mensajes por WhatsApp quedarán como borradores. <Link className="font-semibold underline" href="/afore/configuracion">Ver configuración</Link></Aviso></div>}
      <div className="my-4 flex flex-wrap gap-1.5">
        {Object.entries(BANDEJAS).map(([k, t]) => <button key={k} onClick={() => setBandeja(k)} aria-pressed={bandeja === k}
          className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ${bandeja === k ? "bg-marino text-white" : "border border-crema-300 bg-white text-marino hover:bg-marino-50"}`}>{t}</button>)}
      </div>
      <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {!r ? <p className="text-sm text-slate-500">Cargando…</p> : r.mensajes.length === 0 ? <div className="tarjeta p-10 text-center text-sm text-slate-500">No hay mensajes en esta bandeja.</div> : (
        <div className="space-y-3">{r.mensajes.map((x: any) => (
          <div key={x.id}>
            <TarjetaMensaje x={x} puedeAprobar={esAdmin} editor={editor} accion={accion} />
            <div className="mt-1 flex gap-3 px-1 text-xs">
              {x.caso_id && <Link className="font-semibold text-turquesa-700 hover:underline" href={`/afore/casos/${x.caso_id}`}>Abrir caso →</Link>}
              {editor && x.estado === "por_asignar" && <button className="font-semibold text-violet-800 hover:underline" onClick={() => setAsignar(x)}>Asignar a un cliente y caso</button>}
              {!esAdmin && x.estado === "esperando_aprobacion" && x.caso_id && <span className="text-slate-500">Si usted es el abogado responsable, apruébelo desde el caso.</span>}
            </div>
          </div>))}</div>
      )}
      {asignar && <Asignar x={asignar} onCerrar={() => setAsignar(null)} accion={accion} />}
    </AforeShell>
  );
}

function Asignar({ x, onCerrar, accion }: any) {
  const [clientes, setClientes] = useState<any[]>([]);
  const [cliente, setCliente] = useState("");
  const [casos, setCasos] = useState<any[]>([]);
  const [caso, setCaso] = useState("");
  useEffect(() => { api.get("/afore/clientes").then(setClientes); }, []);
  useEffect(() => { setCaso(""); if (cliente) api.get(`/afore/clientes/${cliente}`).then((c) => setCasos(c.casos)); }, [cliente]);
  return (
    <Modal titulo="Asignar mensaje recibido" onCerrar={onCerrar}>
      <p className="mb-3 rounded-lg bg-crema/70 p-3 text-sm">«{x.texto}» <span className="block text-xs text-slate-500">De: {x.telefono}</span></p>
      <p className="mb-3 text-xs text-slate-500">Asignarlo no cambia el estado del caso.</p>
      <select className="campo mb-2" value={cliente} onChange={(e) => setCliente(e.target.value)}><option value="">Elija el cliente…</option>{clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select>
      <select className="campo" value={caso} onChange={(e) => setCaso(e.target.value)} disabled={!cliente}><option value="">Sin caso específico</option>{casos.map((c) => <option key={c.id} value={c.id}>{c.tipo_texto}</option>)}</select>
      <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
        <button className="btn-primario" disabled={!cliente} onClick={async () => { const r = await accion(() => api.post(`/afore/mensajes/${x.id}/asignar`, { cliente_id: Number(cliente), caso_id: caso ? Number(caso) : null }), "Mensaje asignado."); if (r) onCerrar(); }}>Asignar</button></div>
    </Modal>
  );
}
