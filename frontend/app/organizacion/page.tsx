"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

export default function MiEmpresa() {
  const sesion = useSesion();
  const [org, setOrg] = useState<any>(null);
  const [nombre, setNombre] = useState("");
  const [logo, setLogo] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const entrada = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async () => {
    try {
      const o = await api.get("/organizacion");
      setOrg(o); setNombre(o.nombre);
      setLogo(o.tiene_logo ? URL.createObjectURL((await api.blob("/organizacion/logo")).blob) : null);
    } catch (e: any) { setError(e.message); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  async function accion(fn: () => Promise<any>, mensaje: string) {
    setError(""); setOk(""); setOcupado(true);
    try { await fn(); setOk(mensaje); await cargar(); window.dispatchEvent(new Event("nomira:marca")); }
    catch (e: any) { setError(e.message); }
    setOcupado(false);
    if (entrada.current) entrada.current.value = "";
  }
  const subir = (a?: File) => {
    if (!a) return;
    const fd = new FormData(); fd.append("archivo", a);
    accion(() => api.subirPut("/organizacion/logo", fd), "Logotipo actualizado.");
  };
  if (sesion && sesion.usuario.rol !== "administrador") return <Shell><Aviso>Solo los administradores pueden cambiar la marca de la empresa.</Aviso></Shell>;
  return (
    <Shell>
      <h1 className="text-3xl font-extrabold text-marino">Mi empresa</h1>
      <p className="mb-6 mt-1 max-w-2xl text-sm text-slate-500">El nombre y el logotipo de su negocio aparecen en la barra lateral para todo su equipo y en los reportes de Excel y PDF que exporte.</p>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {org && (
        <div className="grid gap-5 lg:grid-cols-2">
          <section className="tarjeta p-6">
            <h2 className="text-lg font-bold text-marino">Logotipo</h2>
            <div className="mt-4 flex h-44 items-center justify-center rounded-xl border-2 border-dashed border-crema-300 bg-[linear-gradient(45deg,#f3eee5_25%,transparent_25%,transparent_75%,#f3eee5_75%),linear-gradient(45deg,#f3eee5_25%,#fff_25%,#fff_75%,#f3eee5_75%)] bg-[length:20px_20px] bg-[position:0_0,10px_10px] p-4"
              onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); if (!ocupado) subir(e.dataTransfer.files?.[0]); }}>
              {logo
                // eslint-disable-next-line @next/next/no-img-element
                ? <img src={logo} alt="Logotipo actual" className="max-h-full max-w-full object-contain" />
                : <span className="rounded-lg bg-white/80 px-3 py-1.5 text-sm text-slate-500">Sin logotipo. Arrastre una imagen aquí.</span>}
            </div>
            <input ref={entrada} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => subir(e.target.files?.[0])} />
            <div className="mt-4 flex flex-wrap gap-2">
              <button className="btn-turquesa" disabled={ocupado} onClick={() => entrada.current?.click()}>{ocupado ? "Subiendo…" : logo ? "Cambiar logotipo" : "Subir logotipo"}</button>
              {logo && <button className="btn-peligro" disabled={ocupado} onClick={() => { if (confirm("¿Quitar el logotipo de su empresa?")) accion(() => api.borrar("/organizacion/logo"), "Logotipo eliminado."); }}>Quitar</button>}
            </div>
            <p className="mt-3 text-xs text-slate-500">PNG, JPG o WebP, hasta 2 MB. Se recomienda fondo transparente y formato horizontal. No se aceptan archivos SVG.</p>
          </section>
          <section className="tarjeta p-6">
            <h2 className="text-lg font-bold text-marino">Nombre de la empresa</h2>
            <form className="mt-4 space-y-3" onSubmit={(e) => { e.preventDefault(); accion(() => api.patch("/organizacion", { nombre }), "Nombre actualizado."); }}>
              <label className="block"><span className="etiqueta">Nombre comercial o razón social</span>
                <input className="campo" required minLength={2} maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)} /></label>
              <button className="btn-primario" disabled={ocupado || nombre.trim() === org.nombre}>Guardar nombre</button>
            </form>
          </section>
        </div>
      )}
    </Shell>
  );
}
