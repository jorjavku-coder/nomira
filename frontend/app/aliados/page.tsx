"use client";
import Link from "next/link";
import { useState } from "react";
import Logo from "@/components/Logo";

const PASOS = [
  ["Cuéntenos su propuesta", "Un descuento, un precio especial o un regalo para despachos y abogados."],
  ["La publicamos en el Club", "Aparece con su logo dentro de Nomira, donde los despachos trabajan todos los días."],
  ["Reciba a sus nuevos clientes", "Con un código, un enlace o la credencial digital del miembro. Le compartimos cuántos despachos la usaron."],
];
const POR_QUE = [
  ["Público profesional", "Despachos de abogados y notarías que ya pagan por herramientas para su trabajo."],
  ["Sin intermediarios", "El miembro le compra directamente a usted, con sus propias condiciones."],
  ["Métricas claras", "Vistas y canjes de su promoción, sin datos personales de nadie."],
];

/** Página pública para empresas que quieren ofrecer beneficios a los despachos del Club Nomira. */
export default function Aliados() {
  const [f, setF] = useState({ empresa: "", giro: "", nombre: "", email: "", telefono: "", propuesta: "", acepta_contacto: false, sitio_web: "" });
  const [estado, setEstado] = useState<"" | "enviando" | "listo">("");
  const [error, setError] = useState("");
  const enviar = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setEstado("enviando");
    try {
      const r = await fetch("/api/club-publico/aliados", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(f) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Revise los datos.");
      setEstado("listo");
    } catch (x: any) { setError(x.message); setEstado(""); }
  };
  const c = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="min-h-screen bg-crema">
      <header className="border-b border-crema-300 bg-white/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-5 py-3">
          <Link href="/" aria-label="Nomira, inicio"><Logo /></Link>
          <a href="#postular" className="btn-turquesa">Quiero ser aliado</a>
        </div>
      </header>
      <main>
        <section className="relative overflow-hidden bg-marino-900 text-white">
          <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-turquesa/25 blur-3xl" aria-hidden />
          <div className="relative mx-auto max-w-6xl px-5 py-16 sm:py-20">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-turquesa-brillante">Aliados del Club Nomira</p>
            <h1 className="mt-3 max-w-3xl font-marca text-4xl font-extrabold leading-tight sm:text-5xl">Lleve su marca a los despachos de abogados de México.</h1>
            <p className="mt-4 max-w-2xl text-lg text-white/75">El Club Nomira reúne beneficios para los despachos que usan Nomira. Ofrezca una promoción y llegue a abogados y notarías donde trabajan todos los días.</p>
            <a href="#postular" className="btn-turquesa mt-8 inline-block px-6 py-3 text-base">Quiero ser aliado →</a>
          </div>
        </section>
        <section className="mx-auto grid max-w-6xl gap-4 px-5 py-14 md:grid-cols-3">
          {POR_QUE.map(([t, d]) => <div key={t} className="tarjeta p-6"><h2 className="font-marca text-lg font-extrabold text-marino">{t}</h2><p className="mt-1 text-sm text-slate-600">{d}</p></div>)}
        </section>
        <section className="mx-auto max-w-6xl px-5 pb-14">
          <h2 className="font-marca text-2xl font-extrabold text-marino">Cómo funciona</h2>
          <ol className="mt-5 grid gap-4 md:grid-cols-3">{PASOS.map(([t, d], i) => (
            <li key={t} className="tarjeta p-6"><span className="flex h-9 w-9 items-center justify-center rounded-full bg-marino font-bold text-white">{i + 1}</span>
              <h3 className="mt-3 font-bold text-marino">{t}</h3><p className="mt-1 text-sm text-slate-600">{d}</p></li>))}</ol>
          <p className="mt-4 text-sm text-slate-500">Ideal para: seguros y salud, papelería y equipo de oficina, tecnología y software, capacitación, autos, viajes, restaurantes y bienestar.</p>
        </section>
        <section id="postular" className="scroll-mt-20 bg-white">
          <div className="mx-auto max-w-2xl px-5 py-14">
            <h2 className="font-marca text-2xl font-extrabold text-marino">Postule a su empresa</h2>
            <p className="mt-1 text-sm text-slate-600">Le contactamos para conocer su propuesta. Sin costo para postularse.</p>
            {estado === "listo" ? <p className="mt-6 rounded-2xl bg-emerald-50 p-5 text-emerald-800" role="status">✓ Recibimos su solicitud. Le contactaremos pronto.</p> : (
              <form onSubmit={enviar} className="mt-6 grid gap-3 sm:grid-cols-2">
                <label className="sm:col-span-2"><span className="etiqueta">Empresa</span><input className="campo" required minLength={2} value={f.empresa} onChange={c("empresa")} /></label>
                <label><span className="etiqueta">Giro</span><input className="campo" value={f.giro} onChange={c("giro")} placeholder="Ej. Seguros, papelería" /></label>
                <label><span className="etiqueta">Su nombre</span><input className="campo" required minLength={2} value={f.nombre} onChange={c("nombre")} /></label>
                <label><span className="etiqueta">Correo</span><input className="campo" type="email" required value={f.email} onChange={c("email")} /></label>
                <label><span className="etiqueta">Teléfono (opcional)</span><input className="campo" value={f.telefono} onChange={c("telefono")} /></label>
                <label className="sm:col-span-2"><span className="etiqueta">¿Qué le gustaría ofrecer?</span><textarea className="campo" rows={3} value={f.propuesta} onChange={c("propuesta")} placeholder="Ej. 15% de descuento en seguros de gastos médicos para despachos" /></label>
                <input type="text" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden value={f.sitio_web} onChange={c("sitio_web")} />
                <label className="flex items-start gap-2 text-sm text-slate-600 sm:col-span-2"><input type="checkbox" className="mt-1" checked={f.acepta_contacto} onChange={(e) => setF({ ...f, acepta_contacto: e.target.checked })} required />
                  <span>Acepto que Nomira me contacte para atender esta solicitud. Consulte el <Link href="/legal/privacidad" className="font-semibold text-turquesa-700 underline">aviso de privacidad</Link>.</span></label>
                {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 sm:col-span-2" role="alert">{error}</p>}
                <button className="btn-turquesa py-3 sm:col-span-2" disabled={estado === "enviando"}>{estado === "enviando" ? "Enviando…" : "Enviar solicitud"}</button>
              </form>)}
          </div>
        </section>
      </main>
      <footer className="py-8 text-center text-xs text-slate-500"><Link href="/" className="hover:text-marino">← Volver a Nomira</Link></footer>
    </div>
  );
}
