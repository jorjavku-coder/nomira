"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Avatar, CampoContrasena, Chip, ConfirmarEliminar, Modal, ReglasContrasena } from "@/components/ui";
import { actualizarSesion, api, fechaHora, type Usuario } from "@/lib/api";

const ROLES: [string, string, string][] = [
  ["administrador", "Administrador", "Usuarios, catálogos y expedientes"],
  ["analista", "Analista", "Opera y valida expedientes"],
  ["consulta", "Consulta", "Solo lectura y descargas"],
];
const NOMBRE_ROL = Object.fromEntries(ROLES.map(([v, t]) => [v, t]));
const PLURAL: Record<string, string> = { administrador: "Administradores", analista: "Analistas", consulta: "Solo consulta" };
const COLOR_ROL: Record<string, string> = {
  administrador: "bg-marino text-white", analista: "bg-turquesa-50 text-turquesa-700", consulta: "bg-slate-100 text-slate-700",
};

/** Contraseña aleatoria fácil de dictar (sin caracteres ambiguos). */
function sugerirContrasena(): string {
  const letras = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";
  const v = new Uint32Array(14);
  crypto.getRandomValues(v);
  const s = Array.from(v, (n) => letras[n % letras.length]).join("");
  return `${s.slice(0, 5)}-${s.slice(5, 10)}-${s.slice(10)}`;
}

type Dialogo = { tipo: "nuevo" } | { tipo: "editar" | "contrasena" | "eliminar"; u: Usuario };

export default function Usuarios() {
  const sesion = useSesion();
  const [usuarios, setUsuarios] = useState<Usuario[] | null>(null);
  const [auditoria, setAuditoria] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [buscar, setBuscar] = useState("");
  const [dialogo, setDialogo] = useState<Dialogo | null>(null);
  const [verAuditoria, setVerAuditoria] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const [us, au] = await Promise.all([api.get("/usuarios"), api.get("/auditoria?limite=100")]);
      setUsuarios(us); setAuditoria(au);
    } catch (e: any) { setError(e.message); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  async function accion(fn: () => Promise<any>, mensaje: string) {
    setError(""); setOk("");
    try {
      const r = await fn();
      if (r?.id && r.id === sesion?.usuario.id) actualizarSesion({ usuario: r });
      setOk(mensaje); await cargar();
    } catch (e: any) { setError(e.message); }
  }
  const lista = useMemo(() => {
    const q = buscar.trim().toLowerCase();
    return (usuarios || []).filter((u) => !q || u.nombre.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));
  }, [usuarios, buscar]);

  if (sesion && sesion.usuario.rol !== "administrador") return <Shell><Aviso>Solo los administradores pueden ver esta sección.</Aviso></Shell>;
  const conteo = (rol: string) => (usuarios || []).filter((u) => u.rol === rol && u.activo).length;

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-marino">Usuarios</h1>
          <p className="mt-1 text-sm text-slate-500">Quién puede entrar a su organización y qué puede hacer.</p>
        </div>
        <button className="btn-turquesa" onClick={() => setDialogo({ tipo: "nuevo" })}>+ Nuevo usuario</button>
      </div>

      <div className="mb-5 grid gap-2 sm:max-w-xl sm:grid-cols-3 sm:gap-3">
        {ROLES.map(([v]) => (
          <div key={v} className="tarjeta flex items-center justify-between px-4 py-2.5 sm:block sm:py-3">
            <div className="etiqueta !mb-0 sm:!mb-1.5">{PLURAL[v]} activos</div>
            <div className="font-marca text-xl font-extrabold text-marino sm:text-2xl">{usuarios ? conteo(v) : "—"}</div></div>
        ))}
      </div>

      <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      <div className="tarjeta mt-3">
        <div className="border-b border-crema-300 p-3">
          <input className="campo sm:max-w-xs" placeholder="Buscar por nombre o correo…" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar usuarios" />
        </div>
        <ul className="divide-y divide-crema-300">
          {usuarios === null && <li className="p-5 text-sm text-slate-500">Cargando…</li>}
          {usuarios && lista.length === 0 && <li className="p-5 text-sm text-slate-500">Ningún usuario coincide con la búsqueda.</li>}
          {lista.map((u) => {
            const yo = u.id === sesion?.usuario.id;
            return (
              <li key={u.id} className={`flex flex-wrap items-center gap-4 p-4 ${u.activo ? "" : "bg-slate-50/70"}`}>
                <div className={u.activo ? "" : "opacity-50 grayscale"}><Avatar nombre={u.nombre} foto={u.foto} tam={44} /></div>
                <div className="min-w-[12rem] flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-marino">{u.nombre}</span>
                    {yo && <span className="rounded-full bg-turquesa-50 px-2 py-0.5 text-[11px] font-semibold text-turquesa-700">Usted</span>}
                    {!u.activo && <Chip estado="archivado" texto="Desactivado" />}
                  </div>
                  <div className="text-sm text-slate-500">{u.email}</div>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${COLOR_ROL[u.rol]}`}>{NOMBRE_ROL[u.rol]}</span>
                <div className="flex flex-wrap gap-1.5">
                  <button className="btn-sec" onClick={() => setDialogo({ tipo: "editar", u })}>Editar</button>
                  <button className="btn-sec" onClick={() => setDialogo({ tipo: "contrasena", u })}>Contraseña</button>
                  {!yo && <button className="btn-sec" onClick={() => accion(() => api.patch(`/usuarios/${u.id}`, { activo: !u.activo }), u.activo ? `${u.nombre} ya no puede entrar.` : `${u.nombre} puede entrar de nuevo.`)}>
                    {u.activo ? "Desactivar" : "Reactivar"}</button>}
                  {!yo && <button className="btn-peligro" onClick={() => setDialogo({ tipo: "eliminar", u })}>Eliminar</button>}
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      <button className="mt-8 text-sm font-semibold text-turquesa-700 hover:underline" onClick={() => setVerAuditoria(!verAuditoria)}>
        {verAuditoria ? "▾ Ocultar" : "▸ Ver"} registro de auditoría (últimos 100)</button>
      {verAuditoria && (
        <div className="tarjeta mt-2 max-h-96 overflow-auto">
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Elemento</th><th>IP</th><th>Detalle</th></tr></thead>
            <tbody>
              {auditoria.map((a) => (
                <tr key={a.id}><td className="whitespace-nowrap">{fechaHora(a.fecha)}</td><td>{a.usuario || "—"}</td>
                  <td className="font-mono text-xs">{a.accion}</td><td>{a.entidad ? `${a.entidad} #${a.entidad_id}` : "—"}</td>
                  <td className="font-mono text-xs">{a.ip || "—"}</td>
                  <td className="font-mono text-xs text-slate-500">{a.detalle ? JSON.stringify(a.detalle) : ""}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dialogo?.tipo === "nuevo" && <NuevoUsuario onCerrar={() => setDialogo(null)} onListo={(n) => { setDialogo(null); setOk(`Usuario ${n} creado.`); cargar(); }} />}
      {dialogo?.tipo === "editar" && <EditarUsuario u={dialogo.u} yo={dialogo.u.id === sesion?.usuario.id}
        onCerrar={() => setDialogo(null)} onListo={(r, m) => { if (r.id === sesion?.usuario.id) actualizarSesion({ usuario: r }); setOk(m); cargar(); }} />}
      {dialogo?.tipo === "contrasena" && <ContrasenaUsuario u={dialogo.u} yo={dialogo.u.id === sesion?.usuario.id}
        onCerrar={() => setDialogo(null)} onListo={(m) => { setDialogo(null); setOk(m); cargar(); }} />}
      {dialogo?.tipo === "eliminar" && (
        <ConfirmarEliminar titulo="Eliminar usuario" boton="Sí, eliminar" onCerrar={() => setDialogo(null)}
          onConfirmar={async () => { await api.borrar(`/usuarios/${dialogo.u.id}`); setOk(`${dialogo.u.nombre} fue eliminado.`); await cargar(); }}>
          <p>¿Eliminar a <b>{dialogo.u.nombre}</b> ({dialogo.u.email})?</p>
          <p className="mt-2">Ya no podrá entrar y dejará de aparecer aquí. Sus correcciones y validaciones anteriores se conservan en el historial. Si solo quiere quitarle el acceso por un tiempo, use «Desactivar».</p>
        </ConfirmarEliminar>
      )}
    </Shell>
  );
}

function SelectorRol({ valor, onCambio }: { valor: string; onCambio: (v: string) => void }) {
  return (
    <fieldset><legend className="etiqueta">Rol</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {ROLES.map(([v, t, d]) => (
          <label key={v} className={`cursor-pointer rounded-xl border p-3 text-sm transition ${valor === v ? "border-turquesa bg-turquesa-50 ring-2 ring-turquesa/20" : "border-crema-300 hover:border-marino-300"}`}>
            <input type="radio" name="rol" className="sr-only" checked={valor === v} onChange={() => onCambio(v)} />
            <div className="font-semibold text-marino">{t}</div><div className="text-xs text-slate-500">{d}</div>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function NuevoUsuario({ onCerrar, onListo }: { onCerrar: () => void; onListo: (nombre: string) => void }) {
  const [f, setF] = useState({ nombre: "", email: "", contrasena: "", rol: "analista" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try { await api.post("/usuarios", f); onListo(f.nombre); } catch (err: any) { setError(err.message); setEnviando(false); }
  }
  return (
    <Modal titulo="Nuevo usuario" onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-4" onSubmit={enviar}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">Nombre completo</span><input className="campo" required minLength={2} autoFocus value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></label>
          <label className="block"><span className="etiqueta">Correo</span><input className="campo" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
        </div>
        <SelectorRol valor={f.rol} onCambio={(rol) => setF({ ...f, rol })} />
        <div>
          <CampoContrasena etiqueta="Contraseña inicial" nueva valor={f.contrasena} onCambio={(v) => setF({ ...f, contrasena: v })} />
          <div className="mt-1.5 flex items-center justify-between gap-2 text-xs">
            <span className={f.contrasena.length >= 10 ? "text-emerald-700" : "text-slate-500"}>{f.contrasena.length >= 10 ? "✓" : "○"} Al menos 10 caracteres</span>
            <button type="button" className="font-semibold text-turquesa-700 hover:underline" onClick={() => setF({ ...f, contrasena: sugerirContrasena() })}>Generar una segura</button>
          </div>
          <p className="mt-1 text-xs text-slate-500">Compártala con la persona por un medio seguro; podrá cambiarla en «Mi perfil».</p>
        </div>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={enviando}>{enviando ? "Creando…" : "Crear usuario"}</button></div>
      </form>
    </Modal>
  );
}

function EditarUsuario({ u, yo, onCerrar, onListo }: { u: Usuario; yo: boolean; onCerrar: () => void; onListo: (u: Usuario, mensaje: string) => void }) {
  const [nombre, setNombre] = useState(u.nombre);
  const [rol, setRol] = useState(u.rol);
  const [foto, setFoto] = useState(u.foto);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const archivo = useRef<HTMLInputElement>(null);
  async function subirFoto(lista: FileList | null) {
    if (!lista?.[0]) return;
    setError("");
    try {
      const fd = new FormData(); fd.append("archivo", lista[0]);
      const r = await api.subir(`/usuarios/${u.id}/foto`, fd);
      setFoto(r.foto); onListo(r, "Foto actualizada.");
    } catch (e: any) { setError(e.message); }
    if (archivo.current) archivo.current.value = "";
  }
  async function quitarFoto() {
    setError("");
    try { const r = await api.borrar(`/usuarios/${u.id}/foto`); setFoto(null); onListo(r, "Foto quitada."); } catch (e: any) { setError(e.message); }
  }
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    const cambios: any = {};
    if (nombre.trim() !== u.nombre) cambios.nombre = nombre.trim();
    if (rol !== u.rol) cambios.rol = rol;
    try {
      const r = Object.keys(cambios).length ? await api.patch(`/usuarios/${u.id}`, cambios) : u;
      onListo(r, "Cambios guardados."); onCerrar();
    } catch (err: any) { setError(err.message); setEnviando(false); }
  }
  return (
    <Modal titulo={`Editar a ${u.nombre}`} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-5" onSubmit={guardar}>
        <div className="flex items-center gap-4">
          <Avatar nombre={nombre || u.nombre} foto={foto} tam={72} />
          <div className="flex flex-wrap gap-2">
            <input ref={archivo} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => subirFoto(e.target.files)} />
            <button type="button" className="btn-sec" onClick={() => archivo.current?.click()}>{foto ? "Cambiar foto" : "Subir foto"}</button>
            {foto && <button type="button" className="btn-sec" onClick={quitarFoto}>Quitar foto</button>}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">Nombre completo</span><input className="campo" required minLength={2} value={nombre} onChange={(e) => setNombre(e.target.value)} /></label>
          <label className="block"><span className="etiqueta">Correo</span><input className="campo bg-crema text-slate-500" value={u.email} disabled /></label>
        </div>
        <SelectorRol valor={rol} onCambio={setRol} />
        {yo && rol !== "administrador" && <Aviso tipo="alerta">Dejará de ser administrador y perderá acceso a esta pantalla.</Aviso>}
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={enviando}>{enviando ? "Guardando…" : "Guardar"}</button></div>
      </form>
    </Modal>
  );
}

function ContrasenaUsuario({ u, yo, onCerrar, onListo }: { u: Usuario; yo: boolean; onCerrar: () => void; onListo: (mensaje: string) => void }) {
  const [nueva, setNueva] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  if (yo) return (
    <Modal titulo="Cambiar su contraseña" onCerrar={onCerrar}>
      <p className="text-sm text-slate-700">Para cambiar <b>su propia</b> contraseña, vaya a <a className="font-semibold text-turquesa-700 underline" href="/perfil">Mi perfil</a>; ahí se le pide la actual por seguridad.</p>
    </Modal>
  );
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    if (nueva !== confirmar) return setError("Las contraseñas no coinciden.");
    setEnviando(true);
    try { await api.patch(`/usuarios/${u.id}`, { contrasena: nueva }); onListo(`Contraseña de ${u.nombre} cambiada. Sus sesiones abiertas se cerraron.`); }
    catch (err: any) { setError(err.message); setEnviando(false); }
  }
  return (
    <Modal titulo={`Nueva contraseña para ${u.nombre}`} onCerrar={onCerrar}>
      <form className="space-y-4" onSubmit={enviar}>
        <div className="flex items-center gap-3 rounded-xl bg-crema p-3"><Avatar nombre={u.nombre} foto={u.foto} tam={36} />
          <div className="text-sm"><div className="font-semibold text-marino">{u.nombre}</div><div className="text-slate-500">{u.email}</div></div></div>
        <CampoContrasena etiqueta="Nueva contraseña" nueva autoFocus valor={nueva} onCambio={setNueva} />
        <CampoContrasena etiqueta="Repítala" nueva valor={confirmar} onCambio={setConfirmar} />
        <div className="flex items-start justify-between gap-3">
          <ReglasContrasena nueva={nueva} confirmar={confirmar} />
          <button type="button" className="whitespace-nowrap text-xs font-semibold text-turquesa-700 hover:underline"
            onClick={() => { const s = sugerirContrasena(); setNueva(s); setConfirmar(s); }}>Generar una segura</button>
        </div>
        <p className="text-xs text-slate-500">Se cerrarán las sesiones que {u.nombre} tenga abiertas. Comparta la nueva contraseña por un medio seguro.</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={enviando || nueva.length < 10 || nueva !== confirmar}>{enviando ? "Guardando…" : "Cambiar contraseña"}</button></div>
      </form>
    </Modal>
  );
}
