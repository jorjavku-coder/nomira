"use client";
import { useCallback, useEffect, useState } from "react";
import { ConfigDosPasos } from "@/components/DosPasos";
import ShellPlataforma, { Credenciales, useSesionP } from "@/components/plataforma";
import { Aviso, Avatar, CampoContrasena, Chip, Modal } from "@/components/ui";
import { fechaHora } from "@/lib/api";
import { apiP, esSuperadmin, guardarSesionP, leerSesionP } from "@/lib/plataforma";

const ROLES: Record<string, string> = { superadministrador: "Superadministrador", soporte: "Soporte", ejecutivo_comercial: "Ejecutivo comercial" };

export default function Admins() {
  const sesion = useSesionP();
  const [lista, setLista] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [acceso, setAcceso] = useState<any>(null);
  const [c, setC] = useState({ actual: "", nueva: "", confirmar: "" });
  const [msjClave, setMsjClave] = useState<{ tipo: "ok" | "error"; t: string } | null>(null);
  const cargar = useCallback(() => apiP.get("/admins").then(setLista).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  async function cambiarClave(e: React.FormEvent) {
    e.preventDefault(); setMsjClave(null);
    if (c.nueva !== c.confirmar) return setMsjClave({ tipo: "error", t: "Las contraseñas nuevas no coinciden." });
    try {
      const r = await apiP.post("/yo/contrasena", { actual: c.actual, nueva: c.nueva });
      const s = leerSesionP();
      if (s) guardarSesionP({ ...s, token: r.token, admin: r.admin });
      setC({ actual: "", nueva: "", confirmar: "" });
      setMsjClave({ tipo: "ok", t: "Contraseña cambiada. Sus otras sesiones se cerraron." });
    } catch (err: any) { setMsjClave({ tipo: "error", t: err.message }); }
  }
  return (
    <ShellPlataforma>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-marino">Administradores</h1>
          <p className="mt-1 text-sm text-slate-500">Personas que pueden entrar a este panel. No pertenecen a ningún cliente.</p>
        </div>
        <button className="btn-turquesa" onClick={() => setNuevo(true)}>+ Nuevo administrador</button>
      </div>
      <div className="mb-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="tarjeta">
        <ul className="divide-y divide-crema-300">
          {lista?.map((a) => {
            const yo = a.id === sesion?.admin.id;
            return (
              <li key={a.id} className="flex flex-wrap items-center gap-4 p-4">
                <div className={a.activo ? "" : "opacity-50 grayscale"}><Avatar nombre={a.nombre} tam={40} /></div>
                <div className="min-w-[12rem] flex-1">
                  <div className="flex items-center gap-2"><span className="font-semibold text-marino">{a.nombre}</span>
                    {yo && <span className="rounded-full bg-turquesa-50 px-2 py-0.5 text-[11px] font-semibold text-turquesa-700">Usted</span>}
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${a.rol === "superadministrador" ? "bg-amber-100 text-amber-800" : "bg-crema-200 text-marino"}`}>{ROLES[a.rol] || a.rol}</span>
                    {!a.activo && <Chip estado="archivado" texto="Desactivado" />}
                    {a.dos_pasos ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">2 pasos</span>
                      : <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">Sin 2 pasos</span>}</div>
                  <div className="text-sm text-slate-500">{a.email} · último acceso: {a.ultimo_acceso ? fechaHora(a.ultimo_acceso) : "nunca"}</div>
                </div>
                {!yo && esSuperadmin(sesion) && <select aria-label={`Rol de ${a.nombre}`} className="campo w-auto" value={a.rol} onChange={async (e) => {
                  setError(""); setOk("");
                  try { await apiP.patch(`/admins/${a.id}`, { rol: e.target.value }); setOk(`${a.nombre} ahora es ${ROLES[e.target.value]}. Deberá volver a iniciar sesión.`); cargar(); }
                  catch (err: any) { setError(err.message); }
                }}>{Object.entries(ROLES).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>}
                {!yo && a.dos_pasos && esSuperadmin(sesion) && <button className="btn-sec" onClick={async () => {
                  if (!window.confirm(`¿Quitar la verificación en dos pasos de ${a.nombre}? Se cerrarán sus sesiones.`)) return;
                  setError(""); setOk("");
                  try { await apiP.post(`/admins/${a.id}/dos-pasos/quitar`); setOk(`Se quitó la verificación en dos pasos de ${a.nombre}.`); cargar(); }
                  catch (e: any) { setError(e.message); }
                }}>Quitar 2 pasos</button>}
                {!yo && <button className="btn-sec" onClick={async () => {
                  setError(""); setOk("");
                  try { await apiP.patch(`/admins/${a.id}`, { activo: !a.activo }); setOk(a.activo ? `${a.nombre} ya no puede entrar al panel.` : `${a.nombre} puede entrar de nuevo.`); cargar(); }
                  catch (e: any) { setError(e.message); }
                }}>{a.activo ? "Desactivar" : "Reactivar"}</button>}
              </li>
            );
          })}
        </ul>
      </div>

      <section className="tarjeta mt-6 max-w-2xl p-6">
        <h2 className="font-semibold text-marino">Mi contraseña</h2>
        <p className="mt-1 text-sm text-slate-500">Mínimo 12 caracteres. Al cambiarla se cierran sus otras sesiones.</p>
        <form onSubmit={cambiarClave} className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2 sm:max-w-sm"><CampoContrasena etiqueta="Contraseña actual" valor={c.actual} onCambio={(v) => setC({ ...c, actual: v })} /></div>
          <CampoContrasena etiqueta="Nueva contraseña" nueva valor={c.nueva} onCambio={(v) => setC({ ...c, nueva: v })} />
          <CampoContrasena etiqueta="Repítala" nueva valor={c.confirmar} onCambio={(v) => setC({ ...c, confirmar: v })} />
          <div className="flex items-center gap-3 sm:col-span-2">
            <button className="btn-primario" disabled={!c.actual || c.nueva.length < 12 || c.nueva !== c.confirmar}>Cambiar contraseña</button>
            {msjClave && <div className="flex-1"><Aviso tipo={msjClave.tipo}>{msjClave.t}</Aviso></div>}
          </div>
        </form>
      </section>
      {nuevo && <NuevoAdmin onCerrar={() => setNuevo(false)} onListo={(r) => { setNuevo(false); setAcceso(r.acceso); cargar(); }} />}
      {acceso && <Credenciales acceso={acceso} titulo="Administrador creado: datos de acceso" onCerrar={() => setAcceso(null)} />}
      <div className="mt-6 max-w-2xl"><ConfigDosPasos api={apiP} ruta="/yo" onCerrarSesiones={async () => { const r = await apiP.post("/yo/cerrar-sesiones"); const x = leerSesionP(); if (x) guardarSesionP({ ...x, token: r.token, admin: r.admin }); }} /></div>
    </ShellPlataforma>
  );
}

function NuevoAdmin({ onCerrar, onListo }: { onCerrar: () => void; onListo: (r: any) => void }) {
  const [f, setF] = useState({ nombre: "", email: "", rol: "soporte" });
  const sesion = useSesionP();
  const [error, setError] = useState("");
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { onListo(await apiP.post("/admins", f)); } catch (err: any) { setError(err.message); }
  }
  return (
    <Modal titulo="Nuevo administrador de la plataforma" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={enviar}>
        <label className="block"><span className="etiqueta">Nombre</span><input className="campo" required minLength={2} autoFocus value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Correo</span><input className="campo" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
        {esSuperadmin(sesion) && <label className="block"><span className="etiqueta">Rol</span>
          <select className="campo" value={f.rol} onChange={(e) => setF({ ...f, rol: e.target.value })}>{Object.entries(ROLES).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>}
        <p className="text-xs text-slate-500">Soporte: solicitudes, clientes, suscripciones, correos, soporte y legal. Ejecutivo comercial: solo Ventas (CRM), solicitudes, cotizaciones y cupones (hasta el descuento máximo autorizado). Superadministrador: todo, incluidos el módulo Comercial y los roles. Nadie en este panel puede ver expedientes.</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Crear</button></div>
      </form>
    </Modal>
  );
}
