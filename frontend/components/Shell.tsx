"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import { Avatar } from "@/components/ui";
import { Sesion, alCambiarSesion, guardarSesion, leerSesion } from "@/lib/api";

const ROLES: Record<string, string> = { administrador: "Administrador", analista: "Analista", consulta: "Consulta" };

const ICONOS: Record<string, React.ReactNode> = {
  expedientes: <path d="M4 6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />,
  catalogos: <><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z" /><path d="M9 9h6M9 13h6" /></>,
  usuarios: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.5a6.5 6.5 0 0 1 3.5 5.5" /></>,
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
  if (!sesion) return <div className="p-10 text-sm text-slate-500">Cargando…</div>;
  const enlaces = [
    { href: "/", texto: "Expedientes", icono: "expedientes", activo: ruta === "/" || ruta.startsWith("/expedientes") },
    { href: "/catalogos", texto: "Catálogos", icono: "catalogos", activo: ruta.startsWith("/catalogos") },
    ...(sesion.usuario.rol === "administrador" ? [{ href: "/usuarios", texto: "Usuarios", icono: "usuarios", activo: ruta.startsWith("/usuarios") }] : []),
    { href: "/perfil", texto: "Mi perfil", icono: "perfil", activo: ruta.startsWith("/perfil") },
  ];
  const salir = () => { guardarSesion(null); router.replace("/login"); };
  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="z-40 flex flex-col bg-marino-700 text-white lg:fixed lg:inset-y-0 lg:left-0 lg:w-64">
        <div className="flex items-center justify-between px-5 pb-3 pt-5 lg:pb-6 lg:pt-7">
          <Link href="/" aria-label="Nomira, inicio"><Logo oscuro lema /></Link>
          <button className="rounded-lg border border-white/20 px-2.5 py-1 text-xs font-medium hover:bg-white/10 lg:hidden" onClick={salir}>Salir</button>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:pb-0" aria-label="Principal">
          {enlaces.map((e) => (
            <Link key={e.href} href={e.href} aria-current={e.activo ? "page" : undefined}
              className={`relative flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2.5 text-sm font-medium transition ${e.activo ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5 hover:text-white"}`}>
              {e.activo && <span className="absolute -left-3 top-2 hidden h-6 w-1 rounded-r bg-turquesa-brillante lg:block" aria-hidden />}
              <span className={e.activo ? "text-turquesa-brillante" : ""}><Icono nombre={e.icono} /></span>
              {e.texto}
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
          <div className="mt-2 truncate text-xs text-white/50" title={sesion.organizacion}>{sesion.organizacion}</div>
          <button className="mt-3 w-full rounded-xl border border-white/15 px-3 py-1.5 text-xs font-medium text-white/80 transition hover:bg-white/10 hover:text-white" onClick={salir}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="mx-auto max-w-[88rem] px-4 py-6 sm:px-6 lg:px-10 lg:py-9">{children}</main>
    </div>
  );
}
