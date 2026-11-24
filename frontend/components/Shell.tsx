"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Fragment, useEffect, useState } from "react";
import { AceptacionLegal, EnlacesLegales } from "@/components/legal";
import Logo from "@/components/Logo";
import { Avatar } from "@/components/ui";
import { Sesion, alCambiarSesion, api, guardarSesion, leerSesion } from "@/lib/api";

const ROLES: Record<string, string> = { administrador: "Administrador", analista: "Analista", consulta: "Consulta" };

const ICONOS: Record<string, React.ReactNode> = {
  bolsa: <><rect x="3.5" y="7" width="17" height="12.5" rx="2" /><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3.5 12.5h17" /></>,
  clientes: <><circle cx="9" cy="8" r="3.2" /><path d="M3.5 19a5.5 5.5 0 0 1 11 0M15.5 5.3a3 3 0 0 1 0 5.4M17 14a5 5 0 0 1 3.5 5" /></>,
  expedientes: <path d="M4 6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />,
  catalogos: <><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z" /><path d="M9 9h6M9 13h6" /></>,
  empresa: <><path d="M4 20V7l8-3v16M12 9l8 2v9M3 20h18M8 9v.01M8 13v.01M8 17v.01M16 14v.01M16 17v.01" /></>,
  ayuda: <><circle cx="12" cy="12" r="9" /><path d="M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.6M12 17h.01" /></>,
  soporte: <><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /><path d="M8.5 10.5h7M8.5 13.5h4.5" /></>,
  usuarios: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.5a6.5 6.5 0 0 1 3.5 5.5" /></>,
  evidencia: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13l2 2 4-4" /></>,
  perfil: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  afore: <><path d="M12 3l8 4v2H4V7z" /><path d="M6 10v7M10 10v7M14 10v7M18 10v7M3 20h18" /></>,
  leads: <><path d="M3 5h18l-7 8v5l-4 2v-7z" /></>,
  academia: <><path d="M2 9l10-5 10 5-10 5z" /><path d="M6 11v5c3 2 9 2 12 0v-5M22 9v6" /></>,
  asistente: <><path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z" /><path d="M18.5 14.5l.8 1.9 1.9.8-1.9.8-.8 1.9-.8-1.9-1.9-.8 1.9-.8zM5 16l.6 1.4L7 18l-1.4.6L5 20l-.6-1.4L3 18l1.4-.6z" /></>,
  liquidaciones: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8 7h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15v3M8 18h4" /></>,
  escrituracion: <><path d="M6 3h9l4 4v14H6z" /><path d="M15 3v4h4M9 12h7M9 16h4" /><circle cx="17" cy="18" r="2.2" /></>,
  agenda: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4M8 14h3M8 17h6" /></>,
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
  const deNomina = ruta === "/app" || ruta.startsWith("/expedientes") || ruta.startsWith("/catalogos") || ruta.startsWith("/liquidaciones");
  const deEvidencia = ruta.startsWith("/evidencia");
  const deAfore = ruta.startsWith("/afore");
  const deLeads = ruta.startsWith("/leads");
  const deAcademia = ruta.startsWith("/academia");
  const deAgenda = ruta.startsWith("/agenda");
  const deEscrituracion = ruta.startsWith("/escrituracion");
  const deAsistente = ruta.startsWith("/asistente");
  useEffect(() => {
    if (modulos && ruta === "/app" && !modulos.includes("nomina")) {
      if (modulos.includes("evidencia")) router.replace("/evidencia");
      else if (modulos.includes("afore")) router.replace("/afore");
      else if (modulos.includes("leads")) router.replace("/leads");
      else if (modulos.includes("agenda")) router.replace("/agenda");
      else if (modulos.includes("escrituracion")) router.replace("/escrituracion");
      else if (modulos.includes("academia")) router.replace("/academia");
    }
  }, [modulos, ruta, router]);
  const [prueba, setPrueba] = useState<any>(null);
  useEffect(() => {
    if (!sesion) return;
    const cargar = () => api.get("/auth/prueba").then((r) => setPrueba(r.prueba)).catch(() => {});
    const terminada = () => setPrueba((p: any) => ({ ...(p || {}), bloqueada: true, estado: "vencida" }));
    cargar();
    window.addEventListener("nomira:prueba-terminada", terminada);
    return () => window.removeEventListener("nomira:prueba-terminada", terminada);
  }, [sesion]);
  const [sinLeer, setSinLeer] = useState(0);
  const [agendaN, setAgendaN] = useState(0);
  const conAgenda = (modulos ?? sesion?.modulos ?? []).includes("agenda");
  useEffect(() => {
    if (!sesion || !conAgenda) return;
    const cargar = () => api.get("/agenda/contador").then((r) => setAgendaN(r.total)).catch(() => {});
    cargar();
    const t = setInterval(cargar, 300000);
    window.addEventListener("nomira:agenda", cargar);
    return () => { clearInterval(t); window.removeEventListener("nomira:agenda", cargar); };
  }, [sesion, conAgenda]);
  useEffect(() => {
    if (!sesion) return;
    const cargar = () => api.get("/soporte/sin-leer").then((r) => setSinLeer(r.total)).catch(() => {});
    cargar();
    const t = setInterval(cargar, 120000);
    window.addEventListener("nomira:soporte", cargar);
    return () => { clearInterval(t); window.removeEventListener("nomira:soporte", cargar); };
  }, [sesion]);
  if (!sesion) return <div className="p-10 text-sm text-slate-500">Cargando…</div>;
  const bloqueoPrueba = prueba?.bloqueada && !ruta.startsWith("/soporte");
  const inicio = activos.includes("nomina") ? "/app" : activos.includes("evidencia") ? "/evidencia" : activos.includes("afore") ? "/afore"
    : activos.includes("leads") ? "/leads" : activos.includes("agenda") ? "/agenda" : activos.includes("escrituracion") ? "/escrituracion"
    : activos.includes("academia") ? "/academia" : "/asistente";
  const bloqueado = (deNomina && !activos.includes("nomina")) || (deEvidencia && !activos.includes("evidencia")) || (deAfore && !activos.includes("afore"))
    || (deLeads && !activos.includes("leads")) || (deAcademia && !activos.includes("academia")) || (deAgenda && !activos.includes("agenda"))
    || (deEscrituracion && !activos.includes("escrituracion"));
  const enlaces = [
    { grupo: "Clientes", href: "/clientes", texto: "Clientes y cobranza", icono: "clientes", activo: ruta.startsWith("/clientes") },
    { grupo: "Clientes", href: "/bolsa", texto: "Bolsa de trabajo", icono: "bolsa", activo: ruta.startsWith("/bolsa") },  // gratis para todos
    ...(activos.includes("nomina") ? [
      { grupo: "Nómina", href: "/app", texto: "Expedientes", icono: "expedientes", activo: ruta === "/app" || ruta.startsWith("/expedientes") },
      { grupo: "Nómina", href: "/liquidaciones", texto: "Liquidaciones", icono: "liquidaciones", activo: ruta.startsWith("/liquidaciones") },
      { grupo: "Nómina", href: "/catalogos", texto: "Catálogos", icono: "catalogos", activo: ruta.startsWith("/catalogos") }] : []),
    ...(activos.includes("escrituracion") ? [
      { grupo: "Módulos", href: "/escrituracion", texto: "Escrituración", icono: "escrituracion", activo: deEscrituracion }] : []),
    { grupo: "Módulos", href: "/asistente", texto: "Asistente IA", icono: "asistente", activo: deAsistente },  // incluido en todos los planes
    ...(activos.includes("agenda") ? [
      { grupo: "Módulos", href: "/agenda", texto: "Agenda", icono: "agenda", activo: deAgenda, n: agendaN }] : []),
    ...(activos.includes("evidencia") ? [
      { grupo: "Módulos", href: "/evidencia", texto: "Evidencia", icono: "evidencia", activo: deEvidencia }] : []),
    ...(activos.includes("afore") ? [
      { grupo: "Módulos", href: "/afore", texto: "AFORE", icono: "afore", activo: deAfore }] : []),
    ...(activos.includes("leads") ? [
      { grupo: "Módulos", href: "/leads", texto: "Leads", icono: "leads", activo: deLeads }] : []),
    ...(activos.includes("academia") ? [
      { grupo: "Módulos", href: "/academia", texto: "Academia", icono: "academia", activo: deAcademia }] : []),
    ...(sesion.usuario.rol === "administrador" ? [
      { grupo: "Mi despacho", href: "/usuarios", texto: "Usuarios", icono: "usuarios", activo: ruta.startsWith("/usuarios") },
      { grupo: "Mi despacho", href: "/organizacion", texto: "Mi empresa", icono: "empresa", activo: ruta.startsWith("/organizacion") }] : []),
    { grupo: "Mi despacho", href: "/soporte", texto: "Soporte", icono: "soporte", activo: ruta.startsWith("/soporte"), n: sinLeer },
    { grupo: "Mi despacho", href: "/ayuda", texto: "Ayuda y manuales", icono: "ayuda", activo: ruta.startsWith("/ayuda") },
    { grupo: "Mi despacho", href: "/perfil", texto: "Mi perfil", icono: "perfil", activo: ruta.startsWith("/perfil") },
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
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:gap-0.5 lg:overflow-y-auto lg:pb-0" aria-label="Principal">
          {enlaces.map((e, i) => (<Fragment key={e.href}>
            {(i === 0 || enlaces[i - 1].grupo !== e.grupo) && <p className={`hidden px-3 pb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-white/40 lg:block ${i ? "pt-4" : "pt-1"}`}>{e.grupo}</p>}
            <Link href={e.href} aria-current={e.activo ? "page" : undefined}
              className={`relative flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2.5 text-sm font-medium transition lg:py-2 ${e.activo ? "bg-white/10 text-white" : "text-white/65 hover:bg-white/5 hover:text-white"}`}>
              {e.activo && <span className="absolute -left-3 top-2 hidden h-6 w-1 rounded-r bg-turquesa-brillante lg:block" aria-hidden />}
              <span className={e.activo ? "text-turquesa-brillante" : ""}><Icono nombre={e.icono} /></span>
              <span className="flex-1">{e.texto}</span>
              {!!(e as any).n && <span className="rounded-full bg-turquesa-brillante px-1.5 text-[11px] font-bold text-marino-900" aria-label={`${(e as any).n} ${e.href === "/agenda" ? "pendientes vencidos o de hoy" : "respuestas nuevas"}`}>{(e as any).n}</span>}
            </Link>
          </Fragment>))}
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
        <Bienvenida ruta={ruta} />
        {prueba && !prueba.bloqueada && prueba.estado === "prueba" && <AvisoPrueba prueba={prueba} />}
        {bloqueoPrueba ? <PruebaTerminada prueba={prueba} onSalir={salir} /> : bloqueado && modulos ? (
          <div className="tarjeta mx-auto mt-10 max-w-lg p-8 text-center">
            <h1 className="text-2xl font-extrabold text-marino">Módulo no activo</h1>
            <p className="mt-2 text-sm text-slate-600">Esta sección pertenece a un módulo que no está activo para su organización. Sus datos se conservan.
              {sesion.usuario.rol === "administrador" ? " Puede activarlo en «Mi empresa» si está contratado." : " Pida a un administrador que lo active."}</p>
            <Link href={inicio} className="btn-primario mt-5">Ir al inicio</Link>
          </div>
        ) : bloqueado ? <div className="p-10 text-sm text-slate-500">Cargando…</div> : children}
      </main>
      <footer className="space-y-1.5 border-t border-crema-300 px-4 py-4 text-center text-xs text-slate-500 lg:px-10">
        <EnlacesLegales />
        <p>© {new Date().getFullYear()} Nomira · Desarrollado por IMA</p>
      </footer>
      <AceptacionLegal />
    </div>
  );
}


/** Aviso de bienvenida para quien entra por primera vez en este navegador: lleva a los manuales. */
function Bienvenida({ ruta }: { ruta: string }) {
  const [ver, setVer] = useState(false);
  useEffect(() => { try { setVer(!localStorage.getItem("nomira:bienvenida") && !ruta.startsWith("/ayuda")); } catch {} }, [ruta]);
  const cerrar = () => { try { localStorage.setItem("nomira:bienvenida", "1"); } catch {} setVer(false); };
  if (!ver) return null;
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3 rounded-2xl border border-turquesa/30 bg-turquesa-50 px-4 py-3 text-sm text-marino" role="region" aria-label="Bienvenida">
      <span className="text-xl" aria-hidden>👋</span>
      <p className="min-w-0 flex-1"><b>¿Primera vez en Nomira?</b> Cada módulo tiene un manual paso a paso con capturas. Empiece por «Primeros pasos».</p>
      <Link href="/ayuda/primeros-pasos" onClick={cerrar} className="btn-turquesa py-1.5 text-sm">Ver la guía</Link>
      <button className="rounded-lg px-2 py-1 text-slate-500 hover:bg-white" onClick={cerrar} aria-label="Cerrar aviso de bienvenida">✕</button>
    </div>
  );
}


/** Franja con los días que le quedan a la prueba gratuita (solo cuentas registradas en línea). */
function AvisoPrueba({ prueba }: { prueba: any }) {
  const [pedido, setPedido] = useState("");
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-turquesa/40 bg-turquesa-50 px-4 py-3 text-sm">
      <p className="text-marino"><b>Prueba gratuita:</b> {prueba.dias_restantes === 1 ? "hoy es su último día" : `le quedan ${prueba.dias_restantes} días`}.
        <span className="text-slate-600"> Al terminar, su información se conserva.</span></p>
      {pedido ? <span className="font-semibold text-turquesa-700">{pedido}</span>
        : <button className="btn-turquesa" onClick={async () => { try { setPedido((await api.post("/auth/prueba/contratar", {})).mensaje); } catch (e: any) { setPedido(e.message); } }}>Quiero contratar</button>}
    </div>
  );
}

/** Pantalla cuando terminó la prueba: sin borrar nada, invita a contratar. */
function PruebaTerminada({ prueba, onSalir }: { prueba: any; onSalir: () => void }) {
  const [msg, setMsg] = useState("");
  const [texto, setTexto] = useState("");
  const [ocupado, setOcupado] = useState(false);
  return (
    <div className="tarjeta mx-auto mt-10 max-w-xl p-8 text-center">
      <p className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Su prueba gratuita terminó</p>
      <h1 className="mt-2 text-2xl font-extrabold text-marino">Gracias por probar Nomira</h1>
      <p className="mt-2 text-sm text-slate-600">Todo lo que capturó está guardado. Contrate un plan y siga exactamente donde se quedó.</p>
      {msg ? <p role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{msg}</p> : <>
        <textarea className="campo mt-5 text-left" rows={3} maxLength={1000} placeholder="¿Algo que debamos saber? (opcional): módulos, número de usuarios, dudas…" value={texto} onChange={(e) => setTexto(e.target.value)} />
        <button className="btn-turquesa mt-3 w-full py-2.5" disabled={ocupado} onClick={async () => {
          setOcupado(true);
          try { setMsg((await api.post("/auth/prueba/contratar", { mensaje: texto || null })).mensaje); } catch (e: any) { setMsg(e.message); } finally { setOcupado(false); }
        }}>Quiero contratar</button></>}
      <div className="mt-4 flex justify-center gap-4 text-sm"><Link href="/soporte" className="font-semibold text-turquesa-700 hover:underline">Escribir a soporte</Link>
        <button className="text-slate-500 hover:underline" onClick={onSalir}>Cerrar sesión</button></div>
    </div>
  );
}
