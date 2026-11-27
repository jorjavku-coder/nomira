"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

/** «Quiero que un abogado revise mi caso» en la calculadora pública. Primero pregunta el estado: si ahí no hay un
 *  despacho de la red disponible, ni siquiera se piden datos. Con autorización expresa, el caso va a UN despacho. */
export default function QuieroAbogado({ calculo }: { calculo: any | null }) {
  const [abierto, setAbierto] = useState(false);
  const [estados, setEstados] = useState<Record<string, string>>({});
  const [estado, setEstado] = useState("");
  const [disponible, setDisponible] = useState<boolean | null>(null);
  const [f, setF] = useState({ nombre: "", telefono: "", email: "", mensaje: "", sitio_web: "" });
  const [acepta, setAcepta] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [listo, setListo] = useState<string | null>(null);
  const [activo, setActivo] = useState(false);
  useEffect(() => {  // Nomira puede apagar este servicio desde su panel
    fetch("/api/publico/abogados?estado=-").then((r) => r.json()).then((j) => { setEstados(j.estados || {}); setActivo(!!j.activo); }).catch(() => {});
  }, []);
  useEffect(() => {
    setDisponible(null);
    if (!estado) return;
    fetch(`/api/publico/abogados?estado=${estado}`).then((r) => r.json()).then((j) => setDisponible(!!j.disponible)).catch(() => setDisponible(false));
  }, [estado]);
  const pon = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const enviar = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setEnviando(true);
    try {
      const r = await fetch("/api/publico/quiero-abogado", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...f, estado, acepta, telefono: f.telefono || null, email: f.email || null, mensaje: f.mensaje || null, calculo }) });
      const j = await r.json();
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Revise los datos.");
      setListo(j.despacho || "un despacho de su estado");
    } catch (err: any) { setError(err.message); } finally { setEnviando(false); }
  };
  if (!activo) return null;
  if (listo) return (
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900" role="status">
      <p className="text-lg font-bold">¡Listo! Su caso llegó a {listo}.</p>
      <p className="mt-1 text-sm">Le contactarán por el medio que nos dejó. La consulta y los honorarios los acuerda directamente con el despacho.</p>
    </div>);
  if (!abierto) return (
    <div className="rounded-2xl bg-marino p-5 text-white">
      <p className="text-lg font-bold">¿Quiere que un abogado revise su caso?</p>
      <p className="mt-1 text-sm text-white/75">Le ponemos en contacto con un despacho laboral de su estado que usa Nomira. Pedirlo no tiene costo.</p>
      <button className="btn-turquesa mt-3" onClick={() => setAbierto(true)}>Quiero contactar a un abogado</button>
    </div>);
  return (
    <form onSubmit={enviar} className="space-y-3 rounded-2xl border border-crema-300 bg-white p-5" aria-labelledby="t-abogado">
      <p id="t-abogado" className="text-lg font-bold text-marino">Contactar a un abogado</p>
      <label className="block"><span className="etiqueta">¿En qué estado está?</span>
        <select className="campo" value={estado} onChange={(e) => setEstado(e.target.value)} required>
          <option value="">Elija su estado</option>{Object.entries(estados).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>
      {estado && disponible === false && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Por ahora no hay un despacho de Nomira disponible en su estado. No le pediremos sus datos. Puede acudir gratis a la Procuraduría de la Defensa del Trabajo.</p>}
      {estado && disponible && <>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block sm:col-span-2"><span className="etiqueta">Su nombre</span><input className="campo" required minLength={2} autoComplete="name" value={f.nombre} onChange={pon("nombre")} /></label>
          <label className="block"><span className="etiqueta">WhatsApp o teléfono</span><input className="campo" type="tel" autoComplete="tel" value={f.telefono} onChange={pon("telefono")} /></label>
          <label className="block"><span className="etiqueta">Correo (opcional)</span><input className="campo" type="email" autoComplete="email" value={f.email} onChange={pon("email")} /></label>
          <label className="block sm:col-span-2"><span className="etiqueta">Cuéntenos brevemente (opcional)</span><textarea className="campo" rows={3} maxLength={1000} value={f.mensaje} onChange={pon("mensaje")} placeholder="p. ej. me despidieron sin darme nada por escrito" /></label>
          <input className="hidden" tabIndex={-1} autoComplete="off" aria-hidden value={f.sitio_web} onChange={pon("sitio_web")} name="sitio_web" />
        </div>
        <label className="flex items-start gap-2 text-sm text-slate-600"><input type="checkbox" className="mt-1" checked={acepta} onChange={(e) => setAcepta(e.target.checked)} required />
          <span>Autorizo que Nomira envíe estos datos y mi cálculo a <b>un</b> despacho de mi estado para que me contacte. Leí el <Link href="/legal/privacidad" target="_blank" className="font-semibold text-turquesa-700 underline">aviso de privacidad</Link>.</span></label>
        {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
        <button className="btn-turquesa w-full py-3" disabled={enviando || !acepta || (!f.telefono && !f.email)}>{enviando ? "Enviando…" : "Enviar mi caso"}</button>
      </>}
      <button type="button" className="text-sm text-slate-500 hover:underline" onClick={() => setAbierto(false)}>Cancelar</button>
    </form>);
}
