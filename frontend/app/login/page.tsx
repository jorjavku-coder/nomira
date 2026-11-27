"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { EnlacesLegales } from "@/components/legal";
import Logo from "@/components/Logo";
import { PasoCodigo } from "@/components/DosPasos";
import { api, guardarSesion } from "@/lib/api";
import { Aviso } from "@/components/ui";

const PUNTOS = [
  ["2 días gratis, sin tarjeta", "Elija hasta 3 módulos y empiece hoy mismo."],
  ["Sus datos, solo suyos", "Cada despacho ve únicamente su información; ni Nomira la ve."],
  ["Todo en un lugar", "Liquidaciones, agenda, clientes, cobranza, evidencia y más."],
];
const ERRORES_GOOGLE: Record<string, string> = {
  cancelado: "Se canceló el acceso con Google.",
  vencido: "El acceso con Google tardó demasiado. Intente de nuevo.",
  google: "Google no pudo confirmar su cuenta. Intente de nuevo.",
  otra_cuenta: "Ese correo ya está vinculado a otra cuenta de Google. Entre con su contraseña.",
  inactivo: "Su usuario está desactivado. Pida ayuda al administrador de su despacho.",
  sin_cuenta: "Esa cuenta de Google no tiene acceso a Nomira. Solicite informes para darle de alta.",
};

type Modo = "entrar" | "registro" | "codigo" | "google" | "recuperar" | "dos_pasos";

function IconoGoogle() {
  return <svg viewBox="0 0 48 48" className="h-5 w-5" aria-hidden><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" /><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" /><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" /><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" /></svg>;
}

function BotonGoogle({ modo, texto }: { modo: "entrar" | "registro"; texto: string }) {
  return (
    <a href={`/api/auth/google/inicio?modo=${modo}`} className="flex w-full items-center justify-center gap-3 rounded-xl border border-crema-300 bg-white px-4 py-2.5 text-sm font-semibold text-marino shadow-sm transition hover:border-marino-300 hover:bg-marino-50">
      <IconoGoogle />{texto}</a>
  );
}

function Separador() {
  return <div className="flex items-center gap-3 text-xs uppercase tracking-wider text-slate-400"><span className="h-px flex-1 bg-crema-300" />o con su correo<span className="h-px flex-1 bg-crema-300" /></div>;
}

/** Selección de hasta 3 módulos para la prueba gratuita. */
function ElegirModulos({ lista, max, valor, onCambio }: { lista: any[]; max: number; valor: string[]; onCambio: (v: string[]) => void }) {
  return (
    <fieldset>
      <legend className="etiqueta">Elija hasta {max} módulos para su prueba ({valor.length}/{max})</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {lista.map((m) => {
          const sel = valor.includes(m.clave);
          const lleno = !sel && valor.length >= max;
          return (
            <label key={m.clave} className={`flex cursor-pointer gap-2 rounded-xl border p-2.5 text-sm transition ${sel ? "border-turquesa bg-turquesa-50" : lleno ? "cursor-not-allowed border-crema-300 opacity-50" : "border-crema-300 hover:border-turquesa/60"}`}>
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={sel} disabled={lleno} aria-label={m.nombre}
                onChange={() => onCambio(sel ? valor.filter((x) => x !== m.clave) : [...valor, m.clave])} />
              <span><span className="block font-semibold text-marino">{m.nombre}</span><span className="block text-xs leading-snug text-slate-500">{m.descripcion}</span></span>
            </label>);
        })}
      </div>
    </fieldset>
  );
}

function Acepto({ valor, onCambio }: { valor: boolean; onCambio: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-2 text-xs text-slate-600"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={valor} onChange={(e) => onCambio(e.target.checked)} />
      <span>Acepto los <Link className="font-semibold text-turquesa-700 underline" href="/legal/terminos" target="_blank">Términos y condiciones</Link> y el{" "}
        <Link className="font-semibold text-turquesa-700 underline" href="/legal/privacidad" target="_blank">Aviso de privacidad</Link>.</span></label>
  );
}

export default function Login() {
  const router = useRouter();
  const [modo, setModo] = useState<Modo>("entrar");
  const [f, setF] = useState({ email: "", contrasena: "", nombre: "", organizacion: "", telefono: "" });
  const [mods, setMods] = useState<string[]>([]);
  const [acepto, setAcepto] = useState(false);
  const [aceptaWa, setAceptaWa] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(false);
  const [pub, setPub] = useState<any>(null);
  const [reto, setReto] = useState<string | null>(null);
  const [codigo, setCodigo] = useState("");
  const [nueva, setNueva] = useState("");
  const [tokenGoogle, setTokenGoogle] = useState<{ token: string; email: string; nombre: string } | null>(null);
  const registro = !!pub?.permitir_registro;
  const [invitacion, setInvitacion] = useState<{ codigo: string; despacho: string; meses: number } | null>(null);

  useEffect(() => {
    api.get("/publico").then(setPub).catch(() => {});
    const q = new URLSearchParams(window.location.search);
    if (q.get("registro")) setModo("registro");
    try {  // invitación de otro despacho (nomirasoft.com/invita/CODIGO), vigente 30 días
      const inv = JSON.parse(localStorage.getItem("nomira_invitacion") || "null");
      if (inv?.codigo && Date.now() - (inv.guardada || 0) < 30 * 864e5) setInvitacion(inv);
    } catch { /* sin almacenamiento: sin invitación */ }
    const h = window.location.hash.slice(1);
    if (!h) return;
    history.replaceState(null, "", window.location.pathname);
    const [clave, valor] = [h.slice(0, h.indexOf("=")), decodeURIComponent(h.slice(h.indexOf("=") + 1))];
    if (clave === "google_error") setError(ERRORES_GOOGLE[valor] || "No se pudo entrar con Google.");
    if (clave === "google") {
      setCargando(true);
      api.post("/auth/google/canjear", { pase: valor }).then(listo).catch((e) => setError(e.message)).finally(() => setCargando(false));
    }
    if (clave === "registro_google") {
      try {
        const d = JSON.parse(atob(valor.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
        setTokenGoogle({ token: valor, email: d.email, nombre: d.nombre });
        setF((x) => ({ ...x, nombre: d.nombre }));
        setModo("google");
      } catch { setError("No se pudo leer la cuenta de Google. Intente de nuevo."); }
    }
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const cambiar = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const ir = (m: Modo) => { setModo(m); setError(""); setOk(""); setCodigo(""); };
  function listo(s: any) {
    if (s.requiere_codigo) { setReto(s.reto); setModo("dos_pasos"); return; }
    guardarSesion(s);
    router.replace("/inicio");
  }
  async function hacer(fn: () => Promise<any>) {
    setError(""); setOk(""); setCargando(true);
    try { return await fn(); } catch (e: any) { setError(e.message); } finally { setCargando(false); }
  }

  const entrar = (e: React.FormEvent) => { e.preventDefault(); hacer(async () => { listo(await api.post("/auth/login", { email: f.email, contrasena: f.contrasena })); setF({ ...f, contrasena: "" }); }); };
  const registrar = (e: React.FormEvent) => {
    e.preventDefault();
    hacer(async () => {
      const r = await api.post("/auth/registro", { ...f, telefono: f.telefono || null, modulos: mods, acepto, acepta_whatsapp: aceptaWa && !!f.telefono, invitacion: invitacion?.codigo || null });
      setReto(r.reto); setModo("codigo"); setOk(`Le enviamos un código de 6 dígitos a ${r.email}. Revise también su carpeta de spam.`);
    });
  };
  const verificar = (e: React.FormEvent) => { e.preventDefault(); hacer(async () => listo(await api.post("/auth/registro/verificar", { reto, codigo }))); };
  const reenviar = () => hacer(async () => { const r = await api.post("/auth/registro/reenviar", { reto }); setReto(r.reto); setOk("Le enviamos un código nuevo."); });
  const registrarGoogle = (e: React.FormEvent) => {
    e.preventDefault();
    hacer(async () => listo(await api.post("/auth/registro/google", { token: tokenGoogle!.token, organizacion: f.organizacion, nombre: f.nombre, telefono: f.telefono || null, modulos: mods, acepto, acepta_whatsapp: aceptaWa && !!f.telefono, invitacion: invitacion?.codigo || null })));
  };
  const pedirRecuperar = (e: React.FormEvent) => {
    e.preventDefault();
    hacer(async () => { const r = await api.post("/auth/recuperar", { email: f.email }); setReto(r.reto); setOk(r.mensaje); });
  };
  const cambiarContrasena = (e: React.FormEvent) => {
    e.preventDefault();
    hacer(async () => { const r = await api.post("/auth/recuperar/cambiar", { reto, codigo, nueva }); setReto(null); setNueva(""); setCodigo(""); setModo("entrar"); setOk(r.mensaje); });
  };
  const enviarDosPasos = (c: string) => hacer(async () => {
    try { listo(await api.post("/auth/login/codigo", { reto, codigo: c })); }
    catch (err: any) { if (/caduc/i.test(err.message)) { setReto(null); setModo("entrar"); } throw err; }
  });

  const pestañas = registro && (modo === "entrar" || modo === "registro") && (
    <div className="flex rounded-xl bg-crema p-1" role="tablist">
      {([["entrar", "Iniciar sesión"], ["registro", "Crear cuenta · 2 días gratis"]] as [Modo, string][]).map(([m, t]) => (
        <button key={m} type="button" role="tab" aria-selected={modo === m} onClick={() => ir(m)}
          className={`flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition ${modo === m ? "bg-white text-marino shadow-sm" : "text-slate-500 hover:text-marino"}`}>{t}</button>))}
    </div>);
  const campoCodigo = (
    <label className="block"><span className="etiqueta">Código de 6 dígitos</span>
      <input className="campo text-center font-mono text-2xl tracking-[0.4em]" required autoFocus autoComplete="one-time-code" inputMode="numeric" maxLength={6}
        placeholder="000000" value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} /></label>);
  const avisos = <><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></>;

  return (
    <>
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.1fr]">
      <section className="relative hidden overflow-hidden bg-marino-700 p-14 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-turquesa/20 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-40 -left-24 h-[28rem] w-[28rem] rounded-full bg-turquesa-brillante/10 blur-3xl" aria-hidden />
        <Link href="/" aria-label="Ir al sitio de Nomira"><Logo oscuro grande /></Link>
        <div className="relative max-w-md">
          <h1 className="text-4xl font-extrabold leading-tight">El software para su despacho,<br /><span className="text-turquesa-brillante">en claro.</span></h1>
          <p className="mt-4 text-white/70">Liquidaciones, agenda con estrados, clientes y cobranza, portal para sus clientes y más. Contrate solo lo que usa.</p>
          <ul className="mt-8 space-y-4">
            {PUNTOS.map(([t, d]) => (
              <li key={t} className="flex gap-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-turquesa-brillante/15 text-turquesa-brillante">
                  <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 10.5l4 4 8-9" /></svg>
                </span>
                <span><span className="block font-semibold">{t}</span><span className="text-sm text-white/65">{d}</span></span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-white/40">Conexión cifrada · Bitácora de cada acción · Verificación en dos pasos opcional</p>
      </section>

      <section className="flex items-start justify-center p-6 sm:items-center">
        <div className="w-full max-w-md space-y-5 py-6">
          <div className="lg:hidden"><Link href="/" aria-label="Ir al sitio de Nomira"><Logo lema /></Link></div>
          {pestañas}

          {modo === "dos_pasos" && reto && <PasoCodigo onEnviar={enviarDosPasos} onCancelar={() => { setReto(null); ir("entrar"); }} error={error} cargando={cargando} />}

          {modo === "entrar" && <form onSubmit={entrar} className="space-y-4">
            <div><h2 className="text-2xl font-bold text-marino">Bienvenido de nuevo</h2>
              <p className="mt-1 text-sm text-slate-500">Entre para continuar con su trabajo.</p></div>
            {pub?.google && <><BotonGoogle modo="entrar" texto="Continuar con Google" /><Separador /></>}
            <label className="block"><span className="etiqueta">Correo electrónico</span>
              <input className="campo" type="email" required autoComplete="username" value={f.email} onChange={cambiar("email")} /></label>
            <div><div className="flex items-center justify-between"><label htmlFor="contrasena" className="etiqueta">Contraseña</label>
              <button type="button" className="mb-1.5 text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => ir("recuperar")}>¿Olvidó su contraseña?</button></div>
              <input id="contrasena" className="campo" type="password" required autoComplete="current-password" value={f.contrasena} onChange={cambiar("contrasena")} /></div>
            {avisos}
            <button className="btn-primario w-full py-2.5" disabled={cargando}>{cargando ? "Un momento…" : "Entrar"}</button>
            {!registro && <p className="text-center text-sm text-slate-500">¿Aún no es cliente? <Link href="/#informes" className="font-semibold text-turquesa-700 hover:underline">Solicite informes</Link></p>}
          </form>}

          {modo === "registro" && <form onSubmit={registrar} className="space-y-4">
            <div><h2 className="text-2xl font-bold text-marino">Pruebe Nomira 2 días gratis</h2>
              <p className="mt-1 text-sm text-slate-500">Sin tarjeta. Usted será el administrador de su despacho.</p></div>
            {invitacion && <p className="rounded-xl bg-turquesa-50 p-3 text-sm text-marino" data-prueba="invitacion">🤝 Le invitó <b>{invitacion.despacho}</b>. Cuando contrate su primer plan, los dos reciben {invitacion.meses} {invitacion.meses === 1 ? "mes" : "meses"} gratis.</p>}
            {pub?.google && <><BotonGoogle modo="registro" texto="Registrarse con Google" /><Separador /></>}
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block sm:col-span-2"><span className="etiqueta">Despacho o notaría</span><input className="campo" required minLength={2} value={f.organizacion} onChange={cambiar("organizacion")} /></label>
              <label className="block"><span className="etiqueta">Su nombre</span><input className="campo" required minLength={2} autoComplete="name" value={f.nombre} onChange={cambiar("nombre")} /></label>
              <label className="block"><span className="etiqueta">Teléfono (opcional)</span><input className="campo" type="tel" autoComplete="tel" value={f.telefono} onChange={cambiar("telefono")} /></label>
              <label className="block"><span className="etiqueta">Correo electrónico</span><input className="campo" type="email" required autoComplete="email" value={f.email} onChange={cambiar("email")} /></label>
              <label className="block"><span className="etiqueta">Contraseña (mínimo 10)</span><input className="campo" type="password" required minLength={10} autoComplete="new-password" value={f.contrasena} onChange={cambiar("contrasena")} /></label>
            </div>
            {pub && <ElegirModulos lista={pub.modulos_prueba} max={pub.max_modulos_prueba} valor={mods} onCambio={setMods} />}
            {f.telefono.trim() && <label className="flex items-start gap-2 text-sm text-slate-600"><input type="checkbox" className="mt-1" checked={aceptaWa} onChange={(e) => setAceptaWa(e.target.checked)} />
              <span>Acepto recibir por WhatsApp avisos de mi cuenta (bienvenida y vencimiento). Puedo darme de baja escribiendo «BAJA».</span></label>}
            <Acepto valor={acepto} onCambio={setAcepto} />
            {avisos}
            <button className="btn-turquesa w-full py-2.5" disabled={cargando || !mods.length || !acepto}>{cargando ? "Un momento…" : "Crear mi cuenta gratis"}</button>
            <p className="text-center text-xs text-slate-500">Le enviaremos un código a su correo para confirmarlo.</p>
          </form>}

          {modo === "codigo" && <form onSubmit={verificar} className="space-y-4">
            <div><h2 className="text-2xl font-bold text-marino">Confirme su correo</h2>
              <p className="mt-1 text-sm text-slate-500">Escriba el código que le enviamos a <b>{f.email}</b>.</p></div>
            {campoCodigo}
            {avisos}
            <button className="btn-turquesa w-full py-2.5" disabled={cargando || codigo.length !== 6}>{cargando ? "Creando su cuenta…" : "Confirmar y empezar"}</button>
            <div className="flex justify-between text-sm"><button type="button" className="font-semibold text-turquesa-700 hover:underline" onClick={reenviar} disabled={cargando}>Reenviar código</button>
              <button type="button" className="text-slate-500 hover:underline" onClick={() => ir("registro")}>Corregir datos</button></div>
          </form>}

          {modo === "google" && tokenGoogle && <form onSubmit={registrarGoogle} className="space-y-4">
            <div><h2 className="text-2xl font-bold text-marino">Un paso más</h2>
              <p className="mt-1 text-sm text-slate-500">Entrará con su cuenta de Google <b>{tokenGoogle.email}</b>. Díganos de su despacho para crear su prueba gratuita de 2 días.</p></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block sm:col-span-2"><span className="etiqueta">Despacho o notaría</span><input className="campo" required minLength={2} autoFocus value={f.organizacion} onChange={cambiar("organizacion")} /></label>
              <label className="block"><span className="etiqueta">Su nombre</span><input className="campo" required minLength={2} value={f.nombre} onChange={cambiar("nombre")} /></label>
              <label className="block"><span className="etiqueta">Teléfono (opcional)</span><input className="campo" type="tel" value={f.telefono} onChange={cambiar("telefono")} /></label>
            </div>
            {pub && <ElegirModulos lista={pub.modulos_prueba} max={pub.max_modulos_prueba} valor={mods} onCambio={setMods} />}
            {f.telefono.trim() && <label className="flex items-start gap-2 text-sm text-slate-600"><input type="checkbox" className="mt-1" checked={aceptaWa} onChange={(e) => setAceptaWa(e.target.checked)} />
              <span>Acepto recibir por WhatsApp avisos de mi cuenta (bienvenida y vencimiento). Puedo darme de baja escribiendo «BAJA».</span></label>}
            <Acepto valor={acepto} onCambio={setAcepto} />
            {avisos}
            <button className="btn-turquesa w-full py-2.5" disabled={cargando || !mods.length || !acepto}>{cargando ? "Creando su cuenta…" : "Empezar mi prueba gratis"}</button>
            <button type="button" className="w-full text-center text-sm text-slate-500 hover:underline" onClick={() => { setTokenGoogle(null); ir("entrar"); }}>Cancelar</button>
          </form>}

          {modo === "recuperar" && (!reto ? <form onSubmit={pedirRecuperar} className="space-y-4">
            <div><h2 className="text-2xl font-bold text-marino">Recuperar contraseña</h2>
              <p className="mt-1 text-sm text-slate-500">Le enviaremos un código a su correo para elegir una contraseña nueva.</p></div>
            <label className="block"><span className="etiqueta">Correo electrónico</span><input className="campo" type="email" required autoComplete="username" value={f.email} onChange={cambiar("email")} /></label>
            {avisos}
            <button className="btn-primario w-full py-2.5" disabled={cargando}>{cargando ? "Un momento…" : "Enviarme un código"}</button>
            <button type="button" className="w-full text-center text-sm text-slate-500 hover:underline" onClick={() => ir("entrar")}>← Volver a iniciar sesión</button>
          </form> : <form onSubmit={cambiarContrasena} className="space-y-4">
            <div><h2 className="text-2xl font-bold text-marino">Elija una contraseña nueva</h2></div>
            {campoCodigo}
            <label className="block"><span className="etiqueta">Contraseña nueva (mínimo 10)</span><input className="campo" type="password" required minLength={10} autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} /></label>
            {avisos}
            <button className="btn-primario w-full py-2.5" disabled={cargando || codigo.length !== 6}>{cargando ? "Un momento…" : "Guardar contraseña"}</button>
            <button type="button" className="w-full text-center text-sm text-slate-500 hover:underline" onClick={() => { setReto(null); ir("entrar"); }}>← Volver a iniciar sesión</button>
          </form>)}

          <p className="text-center text-sm"><Link href="/" className="text-slate-500 hover:text-marino hover:underline">← Volver a nomirasoft.com</Link></p>
        </div>
      </section>
    </div>

    <footer className="space-y-2 bg-marino-700 px-6 py-6 text-center text-xs text-white/60">
      <EnlacesLegales claro />
      <p>© {new Date().getFullYear()} Nomira · Desarrollado por IMA</p>
    </footer>
    </>
  );
}
