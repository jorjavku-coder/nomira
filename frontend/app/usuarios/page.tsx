"use client";
import { useCallback, useEffect, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Chip, Modal } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

const ROLES = [["administrador", "Administrador — usuarios, catálogos y expedientes"], ["analista", "Analista — opera y valida expedientes"], ["consulta", "Consulta — solo lectura y descargas"]];

export default function Usuarios() {
  const sesion = useSesion();
  const [usuarios, setUsuarios] = useState<any[]>([]);
  const [auditoria, setAuditoria] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [f, setF] = useState({ nombre: "", email: "", contrasena: "", rol: "analista" });
  const cargar = useCallback(async () => {
    try {
      setUsuarios(await api.get("/usuarios"));
      setAuditoria(await api.get("/auditoria?limite=100"));
    } catch (e: any) { setError(e.message); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  async function accion(fn: () => Promise<any>) {
    setError("");
    try { await fn(); await cargar(); } catch (e: any) { setError(e.message); }
  }
  if (sesion && sesion.usuario.rol !== "administrador") return <Shell><Aviso>Solo los administradores pueden ver esta sección.</Aviso></Shell>;
  return (
    <Shell>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-marino">Usuarios</h1>
        <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo usuario</button>
      </div>
      <Aviso>{error}</Aviso>
      <div className="tarjeta mt-3 overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Estado</th><th></th></tr></thead>
          <tbody>
            {usuarios.map((u) => (
              <tr key={u.id}>
                <td>{u.nombre}</td><td>{u.email}</td>
                <td><select className="campo w-auto" value={u.rol} aria-label={`Rol de ${u.nombre}`}
                  onChange={(e) => accion(() => api.patch(`/usuarios/${u.id}`, { rol: e.target.value }))}>
                  {ROLES.map(([v]) => <option key={v} value={v}>{v[0].toUpperCase() + v.slice(1)}</option>)}</select></td>
                <td><Chip estado={u.activo ? "activo" : "archivado"} texto={u.activo ? "Activo" : "Desactivado"} /></td>
                <td className="text-right"><button className="btn-sec" onClick={() => accion(() => api.patch(`/usuarios/${u.id}`, { activo: !u.activo }))}>
                  {u.activo ? "Desactivar" : "Reactivar"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2 className="mb-2 mt-8 text-lg font-semibold text-marino">Registro de auditoría (últimos 100)</h2>
      <div className="tarjeta max-h-96 overflow-auto">
        <table className="tabla">
          <thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Elemento</th><th>Detalle</th></tr></thead>
          <tbody>
            {auditoria.map((a) => (
              <tr key={a.id}><td className="whitespace-nowrap">{fechaHora(a.fecha)}</td><td>{a.usuario || "—"}</td>
                <td className="font-mono text-xs">{a.accion}</td><td>{a.entidad ? `${a.entidad} #${a.entidad_id}` : "—"}</td>
                <td className="font-mono text-xs text-slate-500">{a.detalle ? JSON.stringify(a.detalle) : ""}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {nuevo && (
        <Modal titulo="Nuevo usuario" onCerrar={() => setNuevo(false)}>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); accion(async () => { await api.post("/usuarios", f); setNuevo(false); setF({ nombre: "", email: "", contrasena: "", rol: "analista" }); }); }}>
            <label className="block"><span className="etiqueta">Nombre</span><input className="campo" required value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></label>
            <label className="block"><span className="etiqueta">Correo</span><input className="campo" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
            <label className="block"><span className="etiqueta">Contraseña inicial (mínimo 10)</span><input className="campo" type="password" required minLength={10} autoComplete="new-password" value={f.contrasena} onChange={(e) => setF({ ...f, contrasena: e.target.value })} /></label>
            <label className="block"><span className="etiqueta">Rol</span><select className="campo" value={f.rol} onChange={(e) => setF({ ...f, rol: e.target.value })}>
              {ROLES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
            <Aviso>{error}</Aviso>
            <div className="flex justify-end"><button className="btn-primario">Crear usuario</button></div>
          </form>
        </Modal>
      )}
    </Shell>
  );
}
