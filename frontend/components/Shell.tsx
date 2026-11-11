"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Sesion, guardarSesion, leerSesion } from "@/lib/api";

const ROLES: Record<string, string> = { administrador: "Administrador", analista: "Analista", consulta: "Consulta" };

export function useSesion(): Sesion | null {
  const [s, setS] = useState<Sesion | null>(null);
  useEffect(() => setS(leerSesion()), []);
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
  }, [router]);
  if (!sesion) return <div className="p-10 text-sm text-slate-500">Cargando…</div>;
  const enlaces = [
    { href: "/", texto: "Expedientes", activo: ruta === "/" || ruta.startsWith("/expedientes") },
    { href: "/catalogos", texto: "Catálogos", activo: ruta.startsWith("/catalogos") },
    ...(sesion.usuario.rol === "administrador" ? [{ href: "/usuarios", texto: "Usuarios", activo: ruta.startsWith("/usuarios") }] : []),
  ];
  return (
    <div className="min-h-screen">
      <header className="bg-marino text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3">
          <Link href="/" className="flex items-center gap-2 text-lg font-bold tracking-tight">
            <span className="inline-block h-6 w-6 rounded bg-turquesa" aria-hidden />
            Quincena Clara
          </Link>
          <nav className="flex gap-1" aria-label="Principal">
            {enlaces.map((e) => (
              <Link key={e.href} href={e.href} aria-current={e.activo ? "page" : undefined}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${e.activo ? "bg-white/15" : "text-white/80 hover:bg-white/10"}`}>
                {e.texto}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <div className="text-right leading-tight">
              <div className="font-medium">{sesion.usuario.nombre} · {ROLES[sesion.usuario.rol]}</div>
              <div className="text-xs text-white/70">{sesion.organizacion}</div>
            </div>
            <button className="rounded-md border border-white/30 px-2 py-1 text-xs hover:bg-white/10"
              onClick={() => { guardarSesion(null); router.replace("/login"); }}>
              Salir
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
