"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Logo from "@/components/Logo";
import { PasoCodigo } from "@/components/DosPasos";
import { Aviso } from "@/components/ui";
import { apiP, guardarSesionP } from "@/lib/plataforma";

export default function LoginPlataforma() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [reto, setReto] = useState<string | null>(null);
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try {
      const r = await apiP.post("/login", { email, contrasena });
      if (r.requiere_codigo) { setReto(r.reto); setContrasena(""); setEnviando(false); return; }
      guardarSesionP(r);
      router.replace("/plataforma");
    } catch (err: any) { setError(err.message); setEnviando(false); }
  }
  async function enviarCodigo(codigo: string) {
    setError(""); setEnviando(true);
    try { guardarSesionP(await apiP.post("/login/codigo", { reto, codigo })); router.replace("/plataforma"); }
    catch (err: any) { setError(err.message); setEnviando(false); if (/caduc/i.test(err.message)) setReto(null); }
  }
  if (reto) return (
    <main className="flex min-h-screen items-center justify-center bg-marino-900 p-6">
      <div className="w-full max-w-sm rounded-3xl bg-white p-8 shadow-flotante"><PasoCodigo onEnviar={enviarCodigo} onCancelar={() => { setReto(null); setError(""); }} error={error} cargando={enviando} /></div>
    </main>);
  return (
    <main className="flex min-h-screen items-center justify-center bg-marino-900 p-6">
      <form onSubmit={enviar} className="w-full max-w-sm space-y-5 rounded-3xl bg-white p-8 shadow-flotante">
        <div>
          <Logo />
          <div className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-amber-800">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden />Panel de la plataforma</div>
          <h1 className="mt-3 text-2xl font-extrabold text-marino">Acceso para administrar Nomira</h1>
          <p className="mt-1 text-sm text-slate-500">Solo para quien opera la plataforma. Las cuentas de los clientes entran por <a className="font-semibold text-turquesa-700 hover:underline" href="/login">el acceso normal</a>.</p>
        </div>
        <label className="block"><span className="etiqueta">Correo</span>
          <input className="campo" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="block"><span className="etiqueta">Contraseña</span>
          <input className="campo" type="password" required autoComplete="current-password" value={contrasena} onChange={(e) => setContrasena(e.target.value)} /></label>
        <Aviso>{error}</Aviso>
        <button type="submit" className="btn-primario w-full" disabled={enviando}>{enviando ? "Entrando…" : "Entrar al panel"}</button>
      </form>
    </main>
  );
}
