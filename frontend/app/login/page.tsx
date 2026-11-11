"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, guardarSesion } from "@/lib/api";
import { Aviso } from "@/components/ui";

export default function Login() {
  const router = useRouter();
  const [modo, setModo] = useState<"entrar" | "registro">("entrar");
  const [f, setF] = useState({ email: "", contrasena: "", nombre: "", organizacion: "" });
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
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
      router.replace("/");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-marino p-4">
      <form onSubmit={enviar} className="tarjeta w-full max-w-sm space-y-4 p-6">
        <div>
          <div className="flex items-center gap-2 text-xl font-bold text-marino">
            <span className="inline-block h-6 w-6 rounded bg-turquesa" aria-hidden /> Quincena Clara
          </div>
          <p className="mt-1 text-sm text-slate-500">Prestaciones por quincena, con trazabilidad.</p>
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
        <button className="btn-primario w-full" disabled={cargando}>
          {cargando ? "Un momento…" : modo === "entrar" ? "Entrar" : "Crear organización"}
        </button>
        <button type="button" className="w-full text-center text-sm text-turquesa-700 hover:underline"
          onClick={() => { setModo(modo === "entrar" ? "registro" : "entrar"); setError(""); }}>
          {modo === "entrar" ? "Registrar una organización nueva" : "Ya tengo cuenta"}
        </button>
      </form>
    </div>
  );
}
