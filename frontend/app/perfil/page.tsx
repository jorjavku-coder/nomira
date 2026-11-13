"use client";
import { useEffect, useRef, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Avatar, CampoContrasena, ReglasContrasena } from "@/components/ui";
import { actualizarSesion, api } from "@/lib/api";

const ROLES: Record<string, string> = { administrador: "Administrador", analista: "Analista", consulta: "Consulta" };

export default function Perfil() {
  const sesion = useSesion();
  const [nombre, setNombre] = useState("");
  const [msj, setMsj] = useState<{ tipo: "ok" | "error"; texto: string; zona: string } | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [c, setC] = useState({ actual: "", nueva: "", confirmar: "" });
  const [guardando, setGuardando] = useState("");
  const archivo = useRef<HTMLInputElement>(null);
  useEffect(() => { if (sesion) setNombre(sesion.usuario.nombre); }, [sesion?.usuario.nombre]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!sesion) return <Shell><p className="text-sm text-slate-500">Cargando…</p></Shell>;
  const u = sesion.usuario;
  const aviso = (zona: string) => msj?.zona === zona ? <Aviso tipo={msj.tipo}>{msj.texto}</Aviso> : null;

  async function foto(lista: FileList | null) {
    const a = lista?.[0];
    if (!a) return;
    setMsj(null); setSubiendo(true);
    try {
      const fd = new FormData();
      fd.append("archivo", a);
      actualizarSesion({ usuario: await api.subir("/auth/yo/foto", fd) });
      setMsj({ tipo: "ok", texto: "Foto actualizada.", zona: "foto" });
    } catch (e: any) { setMsj({ tipo: "error", texto: e.message, zona: "foto" }); }
    setSubiendo(false);
    if (archivo.current) archivo.current.value = "";
  }
  async function quitarFoto() {
    setMsj(null);
    try { actualizarSesion({ usuario: await api.borrar("/auth/yo/foto") }); setMsj({ tipo: "ok", texto: "Foto quitada.", zona: "foto" }); }
    catch (e: any) { setMsj({ tipo: "error", texto: e.message, zona: "foto" }); }
  }
  async function guardarNombre(e: React.FormEvent) {
    e.preventDefault(); setMsj(null); setGuardando("datos");
    try { actualizarSesion({ usuario: await api.patch("/auth/yo", { nombre }) }); setMsj({ tipo: "ok", texto: "Datos guardados.", zona: "datos" }); }
    catch (err: any) { setMsj({ tipo: "error", texto: err.message, zona: "datos" }); }
    setGuardando("");
  }
  async function cambiarContrasena(e: React.FormEvent) {
    e.preventDefault(); setMsj(null);
    if (c.nueva !== c.confirmar) return setMsj({ tipo: "error", texto: "Las contraseñas nuevas no coinciden.", zona: "clave" });
    setGuardando("clave");
    try {
      const r = await api.post("/auth/yo/contrasena", { actual: c.actual, nueva: c.nueva });
      actualizarSesion({ token: r.token, usuario: r.usuario });
      setC({ actual: "", nueva: "", confirmar: "" });
      setMsj({ tipo: "ok", texto: "Contraseña cambiada. Se cerraron sus sesiones en otros equipos.", zona: "clave" });
    } catch (err: any) { setMsj({ tipo: "error", texto: err.message, zona: "clave" }); }
    setGuardando("");
  }

  return (
    <Shell>
      <h1 className="text-3xl font-extrabold text-marino">Mi perfil</h1>
      <p className="mt-1 text-sm text-slate-500">Su foto, su nombre y su contraseña.</p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[20rem_1fr]">
        <section className="tarjeta flex flex-col items-center p-6 text-center">
          <Avatar nombre={u.nombre} foto={u.foto} tam={128} />
          <div className="mt-4 text-lg font-bold text-marino">{u.nombre}</div>
          <div className="text-sm text-slate-500">{u.email}</div>
          <span className="mt-2 rounded-full bg-marino-50 px-2.5 py-0.5 text-xs font-semibold text-marino">{ROLES[u.rol]}</span>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <input ref={archivo} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => foto(e.target.files)} />
            <button className="btn-turquesa" disabled={subiendo} onClick={() => archivo.current?.click()}>{subiendo ? "Subiendo…" : u.foto ? "Cambiar foto" : "Subir foto"}</button>
            {u.foto && <button className="btn-sec" onClick={quitarFoto}>Quitar</button>}
          </div>
          <p className="mt-2 text-xs text-slate-400">JPG, PNG o WEBP de hasta 5 MB. Se recorta en cuadrado.</p>
          <div className="mt-3 w-full">{aviso("foto")}</div>
        </section>

        <div className="space-y-6">
          <section className="tarjeta p-6">
            <h2 className="font-semibold text-marino">Datos personales</h2>
            <form onSubmit={guardarNombre} className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="block"><span className="etiqueta">Nombre</span>
                <input className="campo" required minLength={2} maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)} /></label>
              <label className="block"><span className="etiqueta">Correo</span>
                <input className="campo bg-crema text-slate-500" value={u.email} disabled title="El correo solo lo cambia un administrador" /></label>
              <div className="flex items-center gap-3 sm:col-span-2">
                <button className="btn-primario" disabled={guardando === "datos" || nombre.trim() === u.nombre}>{guardando === "datos" ? "Guardando…" : "Guardar cambios"}</button>
                <div className="flex-1">{aviso("datos")}</div>
              </div>
            </form>
          </section>

          <section className="tarjeta p-6">
            <h2 className="font-semibold text-marino">Cambiar contraseña</h2>
            <p className="mt-1 text-sm text-slate-500">Al cambiarla, se cierran sus sesiones abiertas en otros equipos.</p>
            <form onSubmit={cambiarContrasena} className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2 sm:max-w-sm"><CampoContrasena etiqueta="Contraseña actual" valor={c.actual} onCambio={(v) => setC({ ...c, actual: v })} /></div>
              <CampoContrasena etiqueta="Nueva contraseña" nueva valor={c.nueva} onCambio={(v) => setC({ ...c, nueva: v })} />
              <CampoContrasena etiqueta="Repita la nueva contraseña" nueva valor={c.confirmar} onCambio={(v) => setC({ ...c, confirmar: v })} />
              <div className="sm:col-span-2"><ReglasContrasena nueva={c.nueva} confirmar={c.confirmar} /></div>
              <div className="flex items-center gap-3 sm:col-span-2">
                <button className="btn-primario" disabled={guardando === "clave" || !c.actual || c.nueva.length < 10 || c.nueva !== c.confirmar}>
                  {guardando === "clave" ? "Cambiando…" : "Cambiar contraseña"}</button>
                <div className="flex-1">{aviso("clave")}</div>
              </div>
            </form>
          </section>
        </div>
      </div>
    </Shell>
  );
}
