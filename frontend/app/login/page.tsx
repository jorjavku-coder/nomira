"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import FormularioInformes from "@/components/FormularioInformes";
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
      router.replace("/");
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
        <Logo oscuro grande />
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
          <a href="#informes" className="btn-turquesa mt-8">Solicitar informes o suscripción</a>
        </div>
        <p className="relative text-xs text-white/40">Sus documentos permanecen privados dentro de su organización.</p>
      </section>

      <section className="flex items-center justify-center p-6">
        <form onSubmit={enviar} className="w-full max-w-sm space-y-4">
          <div className="lg:hidden"><Logo lema /></div>
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
          <p className="text-center text-sm text-slate-500">¿Aún no es cliente? <a href="#informes" className="font-semibold text-turquesa-700 hover:underline">Solicite informes o una suscripción</a></p>
        </form>
      </section>
    </div>

    <section id="informes" className="scroll-mt-6 border-t border-crema-300 bg-white px-6 py-16">
      <div className="mx-auto grid max-w-6xl items-start gap-10 lg:grid-cols-[1fr_1.15fr]">
        <div>
          <span className="rounded-full bg-turquesa-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-turquesa-700">Informes y suscripción</span>
          <h2 className="mt-4 text-3xl font-extrabold leading-tight text-marino">Deje de sumar quincenas a mano</h2>
          <p className="mt-3 text-slate-600">Suba los comprobantes y obtenga el desglose por quincena con solo las prestaciones de su catálogo. Cuéntenos de su operación y le decimos cómo empezar.</p>
          <ul className="mt-6 space-y-3 text-sm text-slate-700">
            {["Desglose por quincena de todo el expediente (72 quincenas o las que sean), listo en Excel y PDF.", "Su logotipo y su catálogo: cada despacho trabaja con su propia marca y sus reglas.", "Usuarios por rol y bitácora de cada corrección."].map((t) => (
              <li key={t} className="flex gap-2.5"><span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-turquesa" aria-hidden />{t}</li>
            ))}
          </ul>
        </div>
        <FormularioInformes />
      </div>
    </section>
    <footer className="bg-marino-700 px-6 py-6 text-center text-xs text-white/60">© {new Date().getFullYear()} Nomira · Cada prestación, en claro · Desarrollado por IMA</footer>
    </>
  );
}
