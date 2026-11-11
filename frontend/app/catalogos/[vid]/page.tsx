"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Chip } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

function Fila({ e, editable, onCambio }: { e: any; editable: boolean; onCambio: (fn: () => Promise<any>) => void }) {
  const [clave, setClave] = useState(e.clave);
  const [desc, setDesc] = useState(e.descripcion);
  useEffect(() => { setClave(e.clave); setDesc(e.descripcion); }, [e.clave, e.descripcion]);
  const sucio = clave !== e.clave || desc !== e.descripcion;
  if (!editable) {
    return (<tr className={e.activo ? "" : "text-slate-400"}><td className="font-mono">{e.clave}</td><td>{e.descripcion}</td>
      <td>{e.activo ? "Activa" : "Inactiva"}</td><td></td></tr>);
  }
  return (
    <tr className={e.requiere_revision ? "bg-amber-50" : ""}>
      <td><input className="campo w-24 font-mono" value={clave} onChange={(x) => setClave(x.target.value)} aria-label="Clave" /></td>
      <td><input className="campo" value={desc} onChange={(x) => setDesc(x.target.value)} aria-label="Descripción" />
        {e.requiere_revision && <div className="mt-1 text-xs text-amber-800">Revisar: {e.nota || "lectura dudosa"}{e.confianza !== null && ` · confianza OCR ${e.confianza}`}{e.pagina && ` · pág. ${e.pagina}`}</div>}</td>
      <td><label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={e.activo}
        onChange={(x) => onCambio(() => api.patch(`/catalogos/entradas/${e.id}`, { activo: x.target.checked }))} /> Activa</label></td>
      <td className="whitespace-nowrap text-right">
        {(sucio || e.requiere_revision) && <button className="btn-turquesa mr-1" onClick={() => onCambio(() => api.patch(`/catalogos/entradas/${e.id}`, { clave, descripcion: desc, revisada: true }))}>
          {sucio ? "Guardar" : "Marcar revisada"}</button>}
        <button className="btn-peligro" onClick={() => { if (confirm(`¿Eliminar la clave ${e.clave} de este borrador?`)) onCambio(() => api.borrar(`/catalogos/entradas/${e.id}`)); }}>Eliminar</button>
      </td>
    </tr>
  );
}

export default function Version() {
  const { vid } = useParams<{ vid: string }>();
  const sesion = useSesion();
  const [v, setV] = useState<any>(null);
  const [error, setError] = useState("");
  const [filtro, setFiltro] = useState("");
  const [soloRevisar, setSoloRevisar] = useState(false);
  const [nueva, setNueva] = useState({ clave: "", descripcion: "" });
  const [confirmo, setConfirmo] = useState(false);
  const cargar = useCallback(() => api.get(`/catalogos/versiones/${vid}`).then(setV).catch((e) => setError(e.message)), [vid]);
  useEffect(() => { cargar(); }, [cargar]);
  const cambio = async (fn: () => Promise<any>) => {
    setError("");
    try { setV(await fn()); } catch (e: any) { setError(e.message); }
  };
  if (!v) return <Shell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</Shell>;
  const editable = v.estado === "borrador" && sesion?.usuario.rol === "administrador";
  const entradas = v.entradas.filter((e: any) => (!soloRevisar || e.requiere_revision) &&
    (!filtro || e.clave.includes(filtro) || e.descripcion.toLowerCase().includes(filtro.toLowerCase())));
  return (
    <Shell>
      <Link href="/catalogos" className="text-sm text-turquesa-700 hover:underline">← Catálogos</Link>
      <div className="mb-3 mt-1 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-marino">{v.catalogo} — versión {v.numero}</h1>
        <Chip estado={v.estado} />
      </div>
      {v.estado === "borrador" ? (
        <Aviso tipo="alerta">
          <b>Borrador pendiente de validación humana.</b> Compare cada clave contra el documento fuente. El OCR puede equivocarse:
          nada se corrige ni se completa automáticamente. {v.por_revisar > 0 && <>Hay <b>{v.por_revisar}</b> entrada(s) marcadas por revisar.</>}
        </Aviso>
      ) : (
        <Aviso tipo="info">Versión {v.estado === "activo" ? "activa" : "archivada"}, validada el {fechaHora(v.validado_en)}. Es inmutable:
          para cambiar el catálogo cree una versión nueva desde «Catálogos».</Aviso>
      )}
      {v.notas && <p className="mt-2 text-sm text-slate-600">{v.notas}</p>}
      <div className="my-3"><Aviso>{error}</Aviso></div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <input className="campo max-w-xs" placeholder="Buscar clave o descripción" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
        {v.estado === "borrador" && <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={soloRevisar} onChange={(e) => setSoloRevisar(e.target.checked)} /> Solo por revisar ({v.por_revisar})</label>}
        <span className="text-sm text-slate-500">{entradas.length} de {v.entradas_total} claves</span>
      </div>
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Clave</th><th>Descripción</th><th>Estado</th><th></th></tr></thead>
          <tbody>{entradas.map((e: any) => <Fila key={e.id} e={e} editable={editable} onCambio={cambio} />)}</tbody>
        </table>
      </div>
      {editable && (
        <>
          <form className="tarjeta mt-4 flex flex-wrap items-end gap-3 p-4" onSubmit={(e) => { e.preventDefault(); cambio(() => api.post(`/catalogos/versiones/${v.id}/entradas`, nueva)).then(() => setNueva({ clave: "", descripcion: "" })); }}>
            <label className="block"><span className="etiqueta">Agregar clave</span>
              <input className="campo w-28 font-mono" required pattern="\d{4}" title="4 dígitos" value={nueva.clave} onChange={(e) => setNueva({ ...nueva, clave: e.target.value })} placeholder="0000" /></label>
            <label className="block grow"><span className="etiqueta">Descripción</span>
              <input className="campo" required value={nueva.descripcion} onChange={(e) => setNueva({ ...nueva, descripcion: e.target.value })} /></label>
            <button className="btn-sec">Agregar</button>
          </form>
          <div className="tarjeta mt-4 space-y-3 p-4">
            <h2 className="font-semibold text-marino">Validar y activar</h2>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} />
              <span>Confirmo que revisé las {v.entradas_total} claves contra el documento fuente. Al activar, esta versión queda inmutable y sustituye a la versión activa para expedientes nuevos (los existentes no cambian).</span></label>
            <button className="btn-primario" disabled={!confirmo || v.por_revisar > 0}
              onClick={() => cambio(() => api.post(`/catalogos/versiones/${v.id}/activar`, { confirmo_revision: true }))}>Activar versión</button>
            {v.por_revisar > 0 && <p className="text-xs text-amber-800">Resuelva primero las {v.por_revisar} entradas por revisar.</p>}
          </div>
        </>
      )}
    </Shell>
  );
}
