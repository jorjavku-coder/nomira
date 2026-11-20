"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { EnlacesLegales } from "@/components/legal";
import Logo from "@/components/Logo";
import { api, guardarSesion } from "@/lib/api";
import { Aviso } from "@/components/ui";

const PUNTOS = [
  ["Coincidencia exacta de claves", "Solo se suma lo que está en su catálogo autorizado."],
  ["Cada cifra con su origen", "Del total a la página del comprobante en un clic."],
  ["Nada se inventa", "Lo ilegible queda pendiente; lo faltante, señalado."],
];

export default function Login() {
  const router = useRouter();
  const [modo, setModo] = useState<"entrar" | "registro">("entrar");
  const [f, setF] = useState({ email: "", contrasena: "", nombre: "", organizacion: "" });
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [registro, setRegistro] = useState(false);
  useEffect(() => { api.get("/publico").then((p) => setRegistro(!!p.permitir_registro)).catch(() => {}); }, []);
  const cambiar = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      const s = modo === "entrar"
        ? await api.post("/auth/login", { email: f.email, contrasena: f.contrasena })
        : await api.post("/auth/registro", f);
      guardarSesion(s);
      router.replace("/app");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }

  return (
    <>
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-marino-700 p-14 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-turquesa/20 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-40 -left-24 h-[28rem] w-[28rem] rounded-full bg-turquesa-brillante/10 blur-3xl" aria-hidden />
        <Link href="/" aria-label="Ir al sitio de Nomira"><Logo oscuro grande /></Link>
        <div className="relative max-w-md">
          <h1 className="text-4xl font-extrabold leading-tight">Cada prestación,<br /><span className="text-turquesa-brillante">en claro.</span></h1>
          <p className="mt-4 text-white/70">Analice comprobantes de nómina y obtenga el desglose por quincena, con trazabilidad completa.</p>
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
          <Link href="/#informes" className="btn-turquesa mt-8">Solicitar informes o suscripción</Link>
        </div>
        <p className="relative text-xs text-white/40">Sus documentos permanecen privados dentro de su organización.</p>
      </section>

      <section className="flex items-center justify-center p-6">
        <form onSubmit={enviar} className="w-full max-w-sm space-y-4">
          <div className="lg:hidden"><Link href="/" aria-label="Ir al sitio de Nomira"><Logo lema /></Link></div>
          <div>
            <h2 className="text-2xl font-bold text-marino">{modo === "entrar" ? "Bienvenido de nuevo" : "Cree su organización"}</h2>
            <p className="mt-1 text-sm text-slate-500">{modo === "entrar" ? "Entre para continuar con sus expedientes." : "Usted será el primer administrador."}</p>
          </div>
          {modo === "registro" && (
            <>
              <label className="block"><span className="etiqueta">Organización</span>
                <input className="campo" required value={f.organizacion} onChange={cambiar("organizacion")} /></label>
              <label className="block"><span className="etiqueta">Su nombre</span>
                <input className="campo" required value={f.nombre} onChange={cambiar("nombre")} /></label>
            </>
          )}
          <label className="block"><span className="etiqueta">Correo electrónico</span>
            <input className="campo" type="email" required autoComplete="username" value={f.email} onChange={cambiar("email")} /></label>
          <label className="block"><span className="etiqueta">Contraseña{modo === "registro" && " (mínimo 10 caracteres)"}</span>
            <input className="campo" type="password" required minLength={modo === "registro" ? 10 : 1}
              autoComplete={modo === "entrar" ? "current-password" : "new-password"} value={f.contrasena} onChange={cambiar("contrasena")} /></label>
          <Aviso>{error}</Aviso>
          <button className="btn-primario w-full py-2.5" disabled={cargando}>
            {cargando ? "Un momento…" : modo === "entrar" ? "Entrar" : "Crear organización"}
          </button>
          {(registro || modo === "registro") && <button type="button" className="w-full text-center text-sm font-medium text-turquesa-700 hover:underline"
            onClick={() => { setModo(modo === "entrar" ? "registro" : "entrar"); setError(""); }}>
            {modo === "entrar" ? "Registrar una organización nueva" : "Ya tengo cuenta"}
          </button>}
          <p className="text-center text-sm text-slate-500">¿Aún no es cliente? <Link href="/#informes" className="font-semibold text-turquesa-700 hover:underline">Solicite informes o una suscripción</Link></p>
          <p className="text-center text-sm"><Link href="/" className="text-slate-500 hover:text-marino hover:underline">← Volver a nomirasoft.com</Link></p>
        </form>
      </section>
    </div>

    <footer className="space-y-2 bg-marino-700 px-6 py-6 text-center text-xs text-white/60">
      <EnlacesLegales claro />
      <p>© {new Date().getFullYear()} Nomira · Cada prestación, en claro · Desarrollado por IMA</p>
    </footer>
    </>
  );
}
