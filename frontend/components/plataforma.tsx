"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import { Aviso, Avatar, Modal } from "@/components/ui";
import { SesionP, alCambiarSesionP, apiP, guardarSesionP, leerSesionP } from "@/lib/plataforma";

const ICONOS: Record<string, React.ReactNode> = {
  resumen: <><path d="M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 7h6V4h-6z" /></>,
  solicitudes: <><path d="M4 6h16v12H4z" /><path d="M4 7l8 6 8-6" /></>,
  clientes: <><path d="M4 20V7l8-3v16M12 9l8 2v9M3 20h18" /></>,
  suscripciones: <><rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4M8 14h3" /></>,
  soporte: <><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /><path d="M8.5 10.5h7M8.5 13.5h4.5" /></>,
  correos: <><path d="M4 6h16v12H4z" /><path d="M4 7l8 6 8-6" /><circle cx="19" cy="6" r="2.5" fill="currentColor" stroke="none" /></>,
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
    { href: "/plataforma/suscripciones", texto: "Suscripciones", icono: "suscripciones", activo: ruta.startsWith("/plataforma/suscripciones"), n: cont ? cont.por_vencer + cont.vencidas : 0 },
    { href: "/plataforma/correos", texto: "Correos", icono: "correos", activo: ruta.startsWith("/plataforma/correos") },
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
export function Credenciales({ acceso, titulo, onCerrar, correo }: {
  acceso: { email: string; nombre: string; contrasena_temporal: string }; titulo: string; onCerrar: () => void;
  correo?: { enviado: boolean; destinatario: string; error: string | null } | null;
}) {
  const [copiado, setCopiado] = useState("");
  const url = typeof window !== "undefined" ? `${window.location.origin}/login` : "/login";
  const mensaje = `Hola ${acceso.nombre}:\n\nEste es tu acceso a Nomira.\nDirección: ${url}\nCorreo: ${acceso.email}\nContraseña temporal: ${acceso.contrasena_temporal}\n\nAl entrar, cámbiala en «Mi perfil».`;
  const copiar = async (texto: string, que: string) => { try { await navigator.clipboard.writeText(texto); setCopiado(que); } catch { setCopiado(""); } };
  return (
    <Modal titulo={titulo} onCerrar={onCerrar} ancho="max-w-xl">
      <div className="space-y-4">
        {correo?.enviado && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
          ✉️ <b>Le enviamos su correo de bienvenida</b> con estos datos a <b>{correo.destinatario}</b>.</div>}
        {correo && !correo.enviado && <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <b>No se pudo enviar el correo de bienvenida.</b> {correo.error} Copie los datos y envíelos usted.</div>}
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <b>{correo?.enviado ? "Por si acaso, copie estos datos:" : "Copie estos datos ahora:"}</b> por seguridad la contraseña no se vuelve a mostrar. Si se pierde, genere otra.</div>
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

/** Situación de venta de un cliente, en una etiqueta de color. */
export function EstadoSuscripcion({ s, compacto = false }: { s: any; compacto?: boolean }) {
  if (!s) return null;
  const f = (iso: string) => { const [a, m, d] = iso.split("-"); return `${d}/${m}/${compacto ? a.slice(2) : a}`; };
  const dias = (n: number) => (n === 1 ? "1 día" : `${n} días`);
  const v: Record<string, [string, string]> = {
    prueba: ["bg-sky-50 text-sky-800 ring-sky-200", `En prueba · ${s.dias_restantes === 1 ? "último día" : `quedan ${dias(s.dias_restantes)}`}`],
    activa: ["bg-emerald-50 text-emerald-800 ring-emerald-200", `${s.plan_nombre} · vence ${s.fin ? f(s.fin) : ""}`],
    por_vencer: ["bg-amber-50 text-amber-800 ring-amber-300", `${s.plan_nombre} · ${s.dias_restantes === 1 ? "vence hoy" : `vence en ${dias(s.dias_restantes)}`}`],
    vencida: ["bg-red-50 text-red-700 ring-red-200", `Vencida hace ${dias(s.dias_vencida)}`],
    programada: ["bg-slate-100 text-slate-700 ring-slate-200", `${s.plan_nombre} · inicia ${s.inicio ? f(s.inicio) : ""}`],
    sin_plan: ["bg-slate-100 text-slate-500 ring-slate-200", "Sin plan"],
  };
  const [clase, texto] = v[s.estado] || v.sin_plan;
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${clase}`}>{texto}</span>;
}

const NOMBRES_PLAN: Record<string, string> = { prueba: "Prueba gratuita", mensual: "Mensual", semestral: "Semestral", anual: "Anual" };
const DURACION: Record<string, string> = { prueba: "7 días", mensual: "1 mes", semestral: "6 meses", anual: "12 meses" };

function sumarMeses(iso: string, meses: number): Date {
  const [a, m, d] = iso.split("-").map(Number);
  const total = m - 1 + meses, anio = a + Math.floor(total / 12), mes = total % 12;
  const ultimo = new Date(anio, mes + 1, 0).getDate();
  return new Date(anio, mes, Math.min(d, ultimo));
}
/** Misma regla que el servidor: fin inclusivo. */
export function finDePlan(plan: string, inicio: string): string {
  if (!inicio) return "";
  const meses = { prueba: 0, mensual: 1, semestral: 6, anual: 12 }[plan] ?? 1;
  const [a, m, d] = inicio.split("-").map(Number);
  const f = meses === 0 ? new Date(a, m - 1, d + 6) : (() => { const x = sumarMeses(inicio, meses); x.setDate(x.getDate() - 1); return x; })();
  return `${String(f.getDate()).padStart(2, "0")}/${String(f.getMonth() + 1).padStart(2, "0")}/${f.getFullYear()}`;
}

/** Registrar una venta, renovación o prueba para un cliente. */
export function RegistrarPeriodo({ cliente, s, onCerrar, onListo }: { cliente: { id: number; nombre: string }; s: any; onCerrar: () => void; onListo: (s: any) => void }) {
  const [f, setF] = useState({ plan: s?.tuvo_prueba ? "mensual" : "prueba", inicio: s?.sugerido_inicio || "", monto: "", pagado: false, nota: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try {
      onListo(await apiP.post(`/clientes/${cliente.id}/periodos`, { plan: f.plan, inicio: f.inicio, monto: f.monto ? f.monto : null, pagado: f.pagado, nota: f.nota || null }));
    } catch (err: any) { setError(err.message); setEnviando(false); }
  }
  const prueba = f.plan === "prueba";
  return (
    <Modal titulo={`Registrar periodo · ${cliente.nombre}`} onCerrar={onCerrar} ancho="max-w-2xl">
      <form className="space-y-4" onSubmit={enviar}>
        <fieldset><legend className="etiqueta">Plan</legend>
          <div className="grid gap-2 sm:grid-cols-4">
            {Object.keys(NOMBRES_PLAN).map((p) => {
              const bloqueado = p === "prueba" && s?.tuvo_prueba;
              return (
                <label key={p} className={`rounded-xl border p-3 text-sm transition ${bloqueado ? "cursor-not-allowed opacity-45" : "cursor-pointer"} ${f.plan === p ? "border-turquesa bg-turquesa-50 ring-2 ring-turquesa/20" : "border-crema-300 hover:border-marino-300"}`}
                  title={bloqueado ? "Este cliente ya tuvo su prueba gratuita" : ""}>
                  <input type="radio" name="plan" className="sr-only" disabled={bloqueado} checked={f.plan === p} onChange={() => setF({ ...f, plan: p, pagado: p === "prueba" ? false : f.pagado })} />
                  <div className="font-semibold text-marino">{NOMBRES_PLAN[p]}</div><div className="text-xs text-slate-500">{DURACION[p]}</div>
                </label>
              );
            })}
          </div>
        </fieldset>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block"><span className="etiqueta">Fecha de inicio</span>
            <input className="campo" type="date" required value={f.inicio} onChange={(e) => setF({ ...f, inicio: e.target.value })} /></label>
          <div><span className="etiqueta">Vence (último día incluido)</span>
            <div className="campo flex items-center bg-crema font-semibold text-marino">{finDePlan(f.plan, f.inicio) || "—"}</div></div>
          {!prueba && <>
            <label className="block"><span className="etiqueta">Monto (MXN, opcional)</span>
              <input className="campo" type="number" min="0" step="0.01" inputMode="decimal" placeholder="0.00" value={f.monto} onChange={(e) => setF({ ...f, monto: e.target.value })} /></label>
            <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={f.pagado} onChange={(e) => setF({ ...f, pagado: e.target.checked })} /> Ya está pagado</label>
          </>}
        </div>
        <label className="block"><span className="etiqueta">Nota (opcional)</span>
          <input className="campo" maxLength={500} placeholder="Ej. Factura A-123, transferencia, descuento por pronto pago…" value={f.nota} onChange={(e) => setF({ ...f, nota: e.target.value })} /></label>
        {s?.sugerido_inicio && f.inicio === s.sugerido_inicio && s.estado !== "sin_plan" && s.estado !== "vencida" &&
          <p className="text-xs text-slate-500">La fecha sugerida es el día siguiente a que termina su periodo actual, para que no queden días sin cubrir ni encimados.</p>}
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button>
          <button className="btn-primario" disabled={enviando || !f.inicio}>{enviando ? "Guardando…" : "Registrar"}</button></div>
      </form>
    </Modal>
  );
}

/** Periodo con el que arranca un cliente nuevo (desde hoy). */
export function PlanInicial({ valor, onCambio }: { valor: string | null; onCambio: (v: string | null) => void }) {
  const hoy = new Date();
  const iso = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}-${String(hoy.getDate()).padStart(2, "0")}`;
  return (
    <label className="block"><span className="etiqueta">Empieza con</span>
      <select className="campo" value={valor ?? ""} onChange={(e) => onCambio(e.target.value || null)}>
        <option value="prueba">Prueba gratuita de 7 días (vence {finDePlan("prueba", iso)})</option>
        <option value="mensual">Plan mensual desde hoy (vence {finDePlan("mensual", iso)})</option>
        <option value="semestral">Plan semestral desde hoy (vence {finDePlan("semestral", iso)})</option>
        <option value="anual">Plan anual desde hoy (vence {finDePlan("anual", iso)})</option>
        <option value="">Sin plan por ahora</option>
      </select>
      <span className="mt-1 block text-xs text-slate-500">El monto y el pago se registran después en su sección «Suscripción».</span>
    </label>
  );
}

/** Casilla para enviar (o no) el correo de bienvenida con el acceso. */
export function EnviarBienvenida({ valor, onCambio }: { valor: boolean; onCambio: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-2 rounded-xl border border-turquesa/30 bg-turquesa-50/60 p-3 text-sm">
      <input type="checkbox" className="mt-0.5" checked={valor} onChange={(e) => onCambio(e.target.checked)} />
      <span><b className="text-marino">Enviarle un correo de bienvenida</b> con el enlace, su usuario y su contraseña temporal.</span>
    </label>
  );
}

const MODULOS_ALTA = [
  ["nomina", "Nómina y prestaciones", "Desglose de prestaciones por quincena."],
  ["evidencia", "Nomira Evidencia", "Expediente probatorio con hechos, cronología y matriz."],
  ["afore", "Nomira AFORE", "Casos AFORE/SAR, portal del cliente y mensajes con aprobación."],
];

/** Módulos que el cliente contrata desde el alta (al menos uno). */
export function ModulosIniciales({ valor, onCambio }: { valor: string[]; onCambio: (v: string[]) => void }) {
  return (
    <fieldset>
      <legend className="etiqueta">Módulos contratados</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {MODULOS_ALTA.map(([clave, nombre, desc]) => {
          const marcado = valor.includes(clave);
          return (
            <label key={clave} className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 text-sm ${marcado ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={marcado}
                onChange={(e) => onCambio(e.target.checked ? [...valor, clave] : valor.filter((x) => x !== clave))} />
              <span><span className="block font-semibold text-marino">{nombre}</span><span className="block text-xs text-slate-500">{desc}</span></span>
            </label>
          );
        })}
      </div>
      {valor.length === 0 && <p className="mt-1 text-xs text-red-700">Elija al menos un módulo.</p>}
    </fieldset>
  );
}
