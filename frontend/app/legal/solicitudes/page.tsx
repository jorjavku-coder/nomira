"use client";
import Link from "next/link";
import { useState } from "react";
import { MarcoLegal, legalPublico } from "@/components/legal";

const TIPOS: [string, string][] = [["acceso", "Acceso: saber qué datos míos tienen"], ["rectificacion", "Rectificación: corregir datos inexactos"],
  ["cancelacion", "Cancelación: que se eliminen mis datos"], ["oposicion", "Oposición: que dejen de usarlos para algún fin"],
  ["revocacion", "Revocar mi consentimiento"], ["limitacion", "Limitar el uso o la divulgación"]];
const RELACIONES: [string, string][] = [["usuario", "Uso Nomira en mi trabajo (usuario de un despacho)"], ["cliente_despacho", "Soy cliente de un despacho que usa Nomira"],
  ["prospecto", "Pedí informes a Nomira"], ["otro", "Otro"]];

/** Solicitud de derechos ARCO. Se registra con folio; la atiende una persona (nunca se da por resuelta sola). */
export default function SolicitudArco() {
  const [d, setD] = useState<any>({ tipo: "acceso", relacion: "usuario", despacho: "", nombre: "", email: "", descripcion: "", confirmo: false, sitio_web: "" });
  const [error, setError] = useState("");
  const [folio, setFolio] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const set = (k: string) => (e: any) => setD({ ...d, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    try { const r = await legalPublico("/arco", { method: "POST", body: JSON.stringify({ ...d, despacho: d.despacho || null }) }); setFolio(r.folio || "—"); }
    catch (x: any) { setError(x.message); }
    setEnviando(false);
  }
  return (
    <MarcoLegal>
      <Link href="/legal" className="text-sm font-semibold text-turquesa-700 hover:underline">← Centro legal</Link>
      <h1 className="mt-3 text-3xl font-extrabold text-marino">Solicitud sobre sus datos personales</h1>
      {folio ? (
        <div className="tarjeta mt-6 p-6">
          <p className="text-lg font-bold text-marino">Recibimos su solicitud</p>
          <p className="mt-1 text-slate-700">Folio: <b className="font-mono">{folio}</b>. Guárdelo para dar seguimiento.</p>
          <p className="mt-2 text-sm text-slate-600">Una persona la revisará y le responderá al correo que indicó. Es posible que le pidamos acreditar su identidad antes de dar respuesta. Recibirla no significa que ya esté resuelta.</p>
        </div>
      ) : (
        <form onSubmit={enviar} className="tarjeta mt-6 space-y-4 p-6">
          <label className="block"><span className="etiqueta">¿Qué desea solicitar?</span>
            <select className="campo" value={d.tipo} onChange={set("tipo")}>{TIPOS.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>
          <label className="block"><span className="etiqueta">Su relación con Nomira</span>
            <select className="campo" value={d.relacion} onChange={set("relacion")}>{RELACIONES.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>
          {(d.relacion === "cliente_despacho" || d.relacion === "usuario") && <label className="block"><span className="etiqueta">Nombre del despacho (si lo sabe)</span>
            <input className="campo" maxLength={200} value={d.despacho} onChange={set("despacho")} /></label>}
          {d.relacion === "cliente_despacho" && <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-900">El despacho es quien decide sobre sus datos. Le recomendamos dirigirse también a él; si nos escribe, le canalizaremos su solicitud.</p>}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block"><span className="etiqueta">Nombre completo</span><input className="campo" required minLength={3} maxLength={200} autoComplete="name" value={d.nombre} onChange={set("nombre")} /></label>
            <label className="block"><span className="etiqueta">Correo para responderle</span><input className="campo" required type="email" maxLength={254} autoComplete="email" value={d.email} onChange={set("email")} /></label>
          </div>
          <label className="block"><span className="etiqueta">Describa su solicitud</span>
            <textarea className="campo" required minLength={10} maxLength={4000} rows={5} value={d.descripcion} onChange={set("descripcion")}
              placeholder="Indique qué datos y qué necesita. No adjunte ni escriba aquí documentos de identidad: si hace falta, se los pediremos por un medio seguro." /></label>
          <div className="hidden" aria-hidden="true"><label>Sitio web<input tabIndex={-1} autoComplete="off" value={d.sitio_web} onChange={set("sitio_web")} /></label></div>
          <label className="flex items-start gap-2 text-sm text-slate-600"><input type="checkbox" className="mt-1 h-4 w-4 accent-turquesa" checked={d.confirmo} onChange={set("confirmo")} />
            <span>Confirmo que los datos son míos o que represento legalmente a su titular.</span></label>
          {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
          <button className="btn-turquesa" disabled={enviando || !d.confirmo}>{enviando ? "Enviando…" : "Enviar solicitud"}</button>
        </form>
      )}
    </MarcoLegal>
  );
}
