"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import { Avatar } from "@/components/ui";
import { Sesion, alCambiarSesion, api, guardarSesion, leerSesion } from "@/lib/api";

const ROLES: Record<string, string> = { administrador: "Administrador", analista: "Analista", consulta: "Consulta" };

const ICONOS: Record<string, React.ReactNode> = {
  expedientes: <path d="M4 6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />,
  catalogos: <><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z" /><path d="M9 9h6M9 13h6" /></>,
  empresa: <><path d="M4 20V7l8-3v16M12 9l8 2v9M3 20h18M8 9v.01M8 13v.01M8 17v.01M16 14v.01M16 17v.01" /></>,
  soporte: <><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /><path d="M8.5 10.5h7M8.5 13.5h4.5" /></>,
  usuarios: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.5a6.5 6.5 0 0 1 3.5 5.5" /></>,
  evidencia: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13l2 2 4-4" /></>,
  perfil: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
};
function Icono({ nombre }: { nombre: string }) {
  return <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONOS[nombre]}</svg>;
}

export function useSesion(): Sesion | null {
  const [s, setS] = useState<Sesion | null>(null);
  useEffect(() => {
    setS(leerSesion());
    return alCambiarSesion(() => setS(leerSesion()));
  }, []);
  return s;
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const ruta = usePathname();
  const [sesion, setSesion] = useState<Sesion | null>(null);
  useEffect(() => {
    const s = leerSesion();
    if (!s) router.replace("/login");
    else setSesion(s);
    return alCambiarSesion(() => setSesion(leerSesion()));
  }, [router]);
  const [marca, setMarca] = useState<{ nombre: string; logo: string | null } | null>(null);
  const [modulos, setModulos] = useState<string[] | null>(null);
  useEffect(() => {
    if (!sesion) return;
    let url = "";
    const cargar = () => api.get("/organizacion").then(async (o) => {
      let logo: string | null = null;
      if (o.tiene_logo) {
        try { url = URL.createObjectURL((await api.blob("/organizacion/logo")).blob); logo = url; } catch {}
      }
      setMarca({ nombre: o.nombre, logo });
      if (o.modulos) {
        const act = Object.values(o.modulos as Record<string, any>).filter((x) => x.activo).map((x) => x.clave);
        setModulos(act);
        // Se recuerda en la sesión para que la siguiente pantalla ya sepa qué módulos están activos.
        const s = leerSesion();
        if (s && JSON.stringify(s.modulos) !== JSON.stringify(act)) guardarSesion({ ...s, modulos: act });
      }
    }).catch(() => {});
    cargar();
    window.addEventListener("nomira:marca", cargar);
    window.addEventListener("nomira:modulos", cargar);
    return () => { window.removeEventListener("nomira:marca", cargar); window.removeEventListener("nomira:modulos", cargar); if (url) URL.revokeObjectURL(url); };
  }, [sesion]);
  // Módulos activos: los del inicio de sesión mientras llega la respuesta actualizada del servidor.
  const activos = modulos ?? sesion?.modulos ?? ["nomina"];
  const deNomina = ruta === "/app" || ruta.startsWith("/expedientes") || ruta.startsWith("/catalogos");
  const deEvidencia = ruta.startsWith("/evidencia");
  useEffect(() => {
    if (modulos && ruta === "/app" && !modulos.includes("nomina") && modulos.includes("evidencia")) router.replace("/evidencia");
  }, [modulos, ruta, router]);
  const [sinLeer, setSinLeer] = useState(0);
  useEffect(() => {
    if (!sesion) return;
    const cargar = () => api.get("/soporte/sin-leer").then((r) => setSinLeer(r.total)).catch(() => {});
    cargar();
    const t = setInterval(cargar, 120000);
    window.addEventListener("nomira:soporte", cargar);
    return () => { clearInterval(t); window.removeEventListener("nomira:soporte", cargar); };
  }, [sesion]);
  if (!sesion) return <div className="p-10 text-sm text-slate-500">Cargando…</div>;
  const inicio = activos.includes("nomina") ? "/app" : activos.includes("evidencia") ? "/evidencia" : "/perfil";
  const bloqueado = (deNomina && !activos.includes("nomina")) || (deEvidencia && !activos.includes("evidencia"));
  const enlaces = [
    ...(activos.includes("nomina") ? [
      { href: "/app", texto: "Expedientes", icono: "expedientes", activo: ruta === "/app" || ruta.startsWith("/expedientes") },
      { href: "/catalogos", texto: "Catálogos", icono: "catalogos", activo: ruta.startsWith("/catalogos") }] : []),
    ...(activos.includes("evidencia") ? [
      { href: "/evidencia", texto: "Evidencia", icono: "evidencia", activo: deEvidencia }] : []),
    ...(sesion.usuario.rol === "administrador" ? [
      { href: "/usuarios", texto: "Usuarios", icono: "usuarios", activo: ruta.startsWith("/usuarios") },
      { href: "/organizacion", texto: "Mi empresa", icono: "empresa", activo: ruta.startsWith("/organizacion") }] : []),
    { href: "/soporte", texto: "Soporte", icono: "soporte", activo: ruta.startsWith("/soporte"), n: sinLeer },
    { href: "/perfil", texto: "Mi perfil", icono: "perfil", activo: ruta.startsWith("/perfil") },
  ];
  const salir = () => { guardarSesion(null); router.replace("/login"); };
  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="z-40 flex flex-col bg-marino-700 text-white lg:fixed lg:inset-y-0 lg:left-0 lg:w-64">
        <div className="flex items-center justify-between px-5 pb-3 pt-5 lg:pb-6 lg:pt-7">
          <Link href={inicio} aria-label="Nomira, inicio"><Logo oscuro lema /></Link>
          <button className="rounded-lg border border-white/20 px-2.5 py-1 text-xs font-medium hover:bg-white/10 lg:hidden" onClick={salir}>Salir</button>
        </div>
        {marca && (
          <div className="mx-3 mb-3 hidden items-center gap-3 rounded-xl bg-white/[0.06] p-2.5 lg:flex">
            {marca.logo
              // eslint-disable-next-line @next/next/no-img-element
              ? <span className="flex h-11 w-16 shrink-0 items-center justify-center rounded-lg bg-white p-1"><img src={marca.logo} alt={`Logotipo de ${marca.nombre}`} className="max-h-full max-w-full object-contain" /></span>
              : <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-white/10 font-marca text-sm font-extrabold">{marca.nombre.slice(0, 2).toUpperCase()}</span>}
            <span className="min-w-0 text-sm font-semibold leading-tight" title={marca.nombre}><span className="line-clamp-2">{marca.nombre}</span></span>
          </div>
        )}
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:pb-0" aria-label="Principal">
          {enlaces.map((e) => (
            <Link key={e.href} href={e.href} aria-current={e.activo ? "page" : undefined}
              className={`relative flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2.5 text-sm font-medium transition ${e.activo ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5 hover:text-white"}`}>
              {e.activo && <span className="absolute -left-3 top-2 hidden h-6 w-1 rounded-r bg-turquesa-brillante lg:block" aria-hidden />}
              <span className={e.activo ? "text-turquesa-brillante" : ""}><Icono nombre={e.icono} /></span>
              <span className="flex-1">{e.texto}</span>
              {!!(e as any).n && <span className="rounded-full bg-turquesa-brillante px-1.5 text-[11px] font-bold text-marino-900" aria-label={`${(e as any).n} respuestas nuevas`}>{(e as any).n}</span>}
            </Link>
          ))}
        </nav>
        <div className="mt-auto hidden border-t border-white/10 p-4 lg:block">
          <Link href="/perfil" className="-m-2 flex items-center gap-3 rounded-xl p-2 transition hover:bg-white/5" title="Mi perfil">
            <Avatar nombre={sesion.usuario.nombre} foto={sesion.usuario.foto} tam={40} oscuro />
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-semibold">{sesion.usuario.nombre}</div>
              <div className="truncate text-xs text-white/60">{ROLES[sesion.usuario.rol]}</div>
            </div>
          </Link>
          <button className="mt-3 w-full rounded-xl border border-white/15 px-3 py-1.5 text-xs font-medium text-white/80 transition hover:bg-white/10 hover:text-white" onClick={salir}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="mx-auto min-h-[calc(100vh-4rem)] max-w-[88rem] px-4 py-6 sm:px-6 lg:px-10 lg:py-9">
        {bloqueado && modulos ? (
          <div className="tarjeta mx-auto mt-10 max-w-lg p-8 text-center">
            <h1 className="text-2xl font-extrabold text-marino">Módulo no activo</h1>
            <p className="mt-2 text-sm text-slate-600">Esta sección pertenece a un módulo que no está activo para su organización. Sus datos se conservan.
              {sesion.usuario.rol === "administrador" ? " Puede activarlo en «Mi empresa» si está contratado." : " Pida a un administrador que lo active."}</p>
            <Link href={inicio} className="btn-primario mt-5">Ir al inicio</Link>
          </div>
        ) : bloqueado ? <div className="p-10 text-sm text-slate-500">Cargando…</div> : children}
      </main>
      <footer className="border-t border-crema-300 px-4 py-4 text-center text-xs text-slate-500 lg:px-10">© {new Date().getFullYear()} Nomira · Desarrollado por IMA</footer>
    </div>
  );
}
