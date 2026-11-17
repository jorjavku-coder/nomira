"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import { Avatar, Modal } from "@/components/ui";
import { SesionP, alCambiarSesionP, apiP, guardarSesionP, leerSesionP } from "@/lib/plataforma";

const ICONOS: Record<string, React.ReactNode> = {
  resumen: <><path d="M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 7h6V4h-6z" /></>,
  solicitudes: <><path d="M4 6h16v12H4z" /><path d="M4 7l8 6 8-6" /></>,
  clientes: <><path d="M4 20V7l8-3v16M12 9l8 2v9M3 20h18" /></>,
  soporte: <><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /><path d="M8.5 10.5h7M8.5 13.5h4.5" /></>,
  admins: <><path d="M12 3l7 3v5c0 4.4-3 8.2-7 9.5-4-1.3-7-5.1-7-9.5V6z" /><path d="M9.5 12l1.8 1.8 3.5-3.6" /></>,
};
function Icono({ nombre }: { nombre: string }) {
  return <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONOS[nombre]}</svg>;
}

export function useSesionP(): SesionP | null {
  const [s, setS] = useState<SesionP | null>(null);
  useEffect(() => { setS(leerSesionP()); return alCambiarSesionP(() => setS(leerSesionP())); }, []);
  return s;
}

export default function ShellPlataforma({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const ruta = usePathname();
  const [sesion, setSesion] = useState<SesionP | null>(null);
  const [cont, setCont] = useState<any>(null);
  useEffect(() => {
    const s = leerSesionP();
    if (!s) router.replace("/plataforma/login");
    else setSesion(s);
    return alCambiarSesionP(() => setSesion(leerSesionP()));
  }, [router]);
  useEffect(() => {
    if (!sesion) return;
    const cargar = () => apiP.get("/resumen").then(setCont).catch(() => {});
    cargar();
    const t = setInterval(cargar, 60000);
    window.addEventListener("nomira-plataforma-contadores", cargar);
    return () => { clearInterval(t); window.removeEventListener("nomira-plataforma-contadores", cargar); };
  }, [sesion]);
  if (!sesion) return <div className="p-10 text-sm text-slate-500">Cargando…</div>;
  const enlaces = [
    { href: "/plataforma", texto: "Resumen", icono: "resumen", activo: ruta === "/plataforma" },
    { href: "/plataforma/solicitudes", texto: "Solicitudes", icono: "solicitudes", activo: ruta.startsWith("/plataforma/solicitudes"), n: cont?.solicitudes_nuevas },
    { href: "/plataforma/clientes", texto: "Clientes", icono: "clientes", activo: ruta.startsWith("/plataforma/clientes") },
    { href: "/plataforma/soporte", texto: "Soporte", icono: "soporte", activo: ruta.startsWith("/plataforma/soporte"), n: cont?.tickets_sin_leer },
    { href: "/plataforma/admins", texto: "Administradores", icono: "admins", activo: ruta.startsWith("/plataforma/admins") },
  ];
  const salir = () => { guardarSesionP(null); router.replace("/plataforma/login"); };
  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="z-40 flex flex-col bg-marino-900 text-white lg:fixed lg:inset-y-0 lg:left-0 lg:w-64">
        <div className="flex items-center justify-between px-5 pb-2 pt-5 lg:pt-7">
          <Link href="/plataforma" aria-label="Panel de la plataforma"><Logo oscuro /></Link>
          <button className="rounded-lg border border-white/20 px-2.5 py-1 text-xs font-medium hover:bg-white/10 lg:hidden" onClick={salir}>Salir</button>
        </div>
        <div className="mx-5 mb-4 inline-flex w-fit items-center gap-1.5 rounded-full bg-amber-400/15 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-amber-300">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-300" aria-hidden />Panel de la plataforma</div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:pb-0" aria-label="Panel">
          {enlaces.map((e) => (
            <Link key={e.href} href={e.href} aria-current={e.activo ? "page" : undefined}
              className={`relative flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2.5 text-sm font-medium transition ${e.activo ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5 hover:text-white"}`}>
              {e.activo && <span className="absolute -left-3 top-2 hidden h-6 w-1 rounded-r bg-amber-300 lg:block" aria-hidden />}
              <span className={e.activo ? "text-amber-300" : ""}><Icono nombre={e.icono} /></span>
              <span className="flex-1">{e.texto}</span>
              {!!e.n && <span className="rounded-full bg-amber-400 px-1.5 text-[11px] font-bold text-marino-900" aria-label={`${e.n} pendientes`}>{e.n}</span>}
            </Link>
          ))}
        </nav>
        <div className="mx-3 mt-4 hidden rounded-xl border border-white/10 p-3 text-[11px] leading-snug text-white/55 lg:block">
          🔒 Desde este panel no se pueden ver expedientes, recibos ni documentos de los clientes: solo sus cuentas.
        </div>
        <div className="mt-auto hidden border-t border-white/10 p-4 lg:block">
          <div className="flex items-center gap-3">
            <Avatar nombre={sesion.admin.nombre} tam={40} oscuro />
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-semibold">{sesion.admin.nombre}</div>
              <div className="truncate text-xs text-white/60">{sesion.admin.email}</div>
            </div>
          </div>
          <button className="mt-3 w-full rounded-xl border border-white/15 px-3 py-1.5 text-xs font-medium text-white/80 transition hover:bg-white/10 hover:text-white" onClick={salir}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="mx-auto min-h-[calc(100vh-4rem)] max-w-[88rem] px-4 py-6 sm:px-6 lg:px-10 lg:py-9">{children}</main>
      <footer className="border-t border-crema-300 px-4 py-4 text-center text-xs text-slate-500 lg:px-10">Nomira · Panel de la plataforma</footer>
    </div>
  );
}

/** Muestra una contraseña temporal UNA sola vez, con un mensaje listo para enviar. */
export function Credenciales({ acceso, titulo, onCerrar }: { acceso: { email: string; nombre: string; contrasena_temporal: string }; titulo: string; onCerrar: () => void }) {
  const [copiado, setCopiado] = useState("");
  const url = typeof window !== "undefined" ? `${window.location.origin}/login` : "/login";
  const mensaje = `Hola ${acceso.nombre}:\n\nEste es tu acceso a Nomira.\nDirección: ${url}\nCorreo: ${acceso.email}\nContraseña temporal: ${acceso.contrasena_temporal}\n\nAl entrar, cámbiala en «Mi perfil».`;
  const copiar = async (texto: string, que: string) => { try { await navigator.clipboard.writeText(texto); setCopiado(que); } catch { setCopiado(""); } };
  return (
    <Modal titulo={titulo} onCerrar={onCerrar} ancho="max-w-xl">
      <div className="space-y-4">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <b>Copie estos datos ahora:</b> por seguridad la contraseña no se vuelve a mostrar. Si se pierde, genere otra.</div>
        <dl className="grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
          <dt className="text-slate-500">Persona</dt><dd className="font-semibold text-marino">{acceso.nombre}</dd>
          <dt className="text-slate-500">Correo</dt><dd className="font-mono">{acceso.email}</dd>
          <dt className="text-slate-500">Contraseña</dt>
          <dd className="flex items-center gap-2"><code className="rounded-lg bg-crema px-2 py-1 font-mono text-base font-bold text-marino">{acceso.contrasena_temporal}</code>
            <button className="text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => copiar(acceso.contrasena_temporal, "clave")}>{copiado === "clave" ? "✓ Copiada" : "Copiar"}</button></dd>
        </dl>
        <div>
          <div className="etiqueta">Mensaje listo para enviar</div>
          <pre className="whitespace-pre-wrap rounded-2xl bg-crema p-3 font-sans text-sm text-slate-700">{mensaje}</pre>
          <div className="mt-2 flex gap-2">
            <button className="btn-turquesa" onClick={() => copiar(mensaje, "mensaje")}>{copiado === "mensaje" ? "✓ Mensaje copiado" : "Copiar mensaje"}</button>
            <a className="btn-sec" href={`mailto:${acceso.email}?subject=${encodeURIComponent("Tu acceso a Nomira")}&body=${encodeURIComponent(mensaje)}`}>Abrir en el correo</a>
          </div>
        </div>
        <div className="flex justify-end"><button className="btn-primario" onClick={onCerrar}>Listo</button></div>
      </div>
    </Modal>
  );
}

export function Tarjeta({ etiqueta, valor, nota, alerta = false, href }: { etiqueta: string; valor: React.ReactNode; nota?: string; alerta?: boolean; href?: string }) {
  const cuerpo = (
    <div className={`tarjeta h-full p-5 transition ${href ? "hover:-translate-y-0.5 hover:shadow-md" : ""} ${alerta ? "ring-2 ring-amber-300" : ""}`}>
      <div className="etiqueta">{etiqueta}</div>
      <div className={`font-marca text-3xl font-extrabold ${alerta ? "text-amber-700" : "text-marino"}`}>{valor}</div>
      {nota && <div className="mt-1 text-xs text-slate-500">{nota}</div>}
    </div>
  );
  return href ? <Link href={href}>{cuerpo}</Link> : cuerpo;
}
