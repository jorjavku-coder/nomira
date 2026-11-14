"use client";
import { useState } from "react";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

const VACIO = { tipo: "informes", nombre: "", empresa: "", email: "", telefono: "", expedientes_mes: "", mensaje: "", acepta_contacto: false, sitio_web: "" };

/** Formulario público de informes y suscripción (página de inicio). */
export default function FormularioInformes() {
  const [f, setF] = useState(VACIO);
  const [error, setError] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const cambiar = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setEnviando(true);
    try {
      await api.post("/solicitudes", { ...f, empresa: f.empresa || null, telefono: f.telefono || null, expedientes_mes: f.expedientes_mes || null, mensaje: f.mensaje || null });
      setEnviado(true); setF(VACIO);
    } catch (err: any) { setError(err.message); }
    setEnviando(false);
  }
  if (enviado) {
    return (
      <div className="tarjeta p-8 text-center" role="status">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-turquesa-50 text-turquesa-700">
          <svg viewBox="0 0 20 20" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 10.5l4 4 8-9" /></svg>
        </div>
        <h3 className="mt-3 font-marca text-xl font-extrabold text-marino">Recibimos su solicitud</h3>
        <p className="mt-1 text-sm text-slate-600">Nos pondremos en contacto con usted a la brevedad.</p>
        <button className="btn-sec mt-4" onClick={() => setEnviado(false)}>Enviar otra solicitud</button>
      </div>
    );
  }
  return (
    <form onSubmit={enviar} className="tarjeta space-y-4 p-6 sm:p-8">
      <fieldset>
        <legend className="etiqueta">¿Qué necesita?</legend>
        <div className="grid grid-cols-2 gap-2">
          {[["informes", "Quiero informes", "Conocer el sistema y resolver dudas"], ["suscripcion", "Quiero suscribirme", "Contratar Nomira para mi negocio"]].map(([v, t, d]) => (
            <label key={v} className={`cursor-pointer rounded-xl border-2 p-3 transition ${f.tipo === v ? "border-turquesa bg-turquesa-50" : "border-crema-300 bg-white hover:border-marino-300"}`}>
              <input type="radio" name="tipo" value={v} checked={f.tipo === v} onChange={cambiar("tipo")} className="sr-only" />
              <span className="block text-sm font-bold text-marino">{t}</span><span className="block text-xs text-slate-500">{d}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block"><span className="etiqueta">Nombre completo</span><input className="campo" required minLength={2} maxLength={200} autoComplete="name" value={f.nombre} onChange={cambiar("nombre")} /></label>
        <label className="block"><span className="etiqueta">Empresa o despacho</span><input className="campo" maxLength={200} autoComplete="organization" value={f.empresa} onChange={cambiar("empresa")} /></label>
        <label className="block"><span className="etiqueta">Correo electrónico</span><input className="campo" type="email" required maxLength={254} autoComplete="email" value={f.email} onChange={cambiar("email")} /></label>
        <label className="block"><span className="etiqueta">Teléfono (opcional)</span><input className="campo" type="tel" maxLength={25} autoComplete="tel" value={f.telefono} onChange={cambiar("telefono")} /></label>
      </div>
      <label className="block"><span className="etiqueta">Expedientes que analiza al mes (opcional)</span>
        <select className="campo" value={f.expedientes_mes} onChange={cambiar("expedientes_mes")}>
          <option value="">Seleccione…</option><option value="1-10">1 a 10</option><option value="11-50">11 a 50</option><option value="51-200">51 a 200</option><option value="200+">Más de 200</option>
        </select></label>
      <label className="block"><span className="etiqueta">Mensaje (opcional)</span><textarea className="campo" rows={3} maxLength={2000} value={f.mensaje} onChange={cambiar("mensaje")} /></label>
      {/* Campo trampa para bots: oculto a personas y lectores de pantalla */}
      <div className="hidden" aria-hidden="true"><label>Sitio web<input tabIndex={-1} autoComplete="off" value={f.sitio_web} onChange={cambiar("sitio_web")} /></label></div>
      <label className="flex items-start gap-2 text-sm text-slate-600"><input type="checkbox" className="mt-1" required checked={f.acepta_contacto} onChange={(e) => setF({ ...f, acepta_contacto: e.target.checked })} />
        <span>Acepto que se usen estos datos para contactarme sobre mi solicitud.</span></label>
      <Aviso>{error}</Aviso>
      <button className="btn-turquesa w-full py-2.5" disabled={enviando}>{enviando ? "Enviando…" : f.tipo === "suscripcion" ? "Solicitar suscripción" : "Solicitar informes"}</button>
    </form>
  );
}
