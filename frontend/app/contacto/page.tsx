"use client";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";

/** Formulario público de contacto de un despacho (Nomira Leads). El enlace llega como /contacto#token:
 *  el fragmento no viaja al servidor; aquí se lee y se manda en un encabezado. Los datos van en el
 *  cuerpo, nunca en la URL. No es asesoría jurídica: solo registra la solicitud. */
const CLAVE = "nomira_contacto";
const UTM = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];

async function llamar(ruta: string, token: string, cuerpo?: unknown) {
  const r = await fetch(`/api/leads-publico${ruta}`, { method: "POST", headers: { "X-Enlace": token, "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo ?? {}), cache: "no-store" });
  let d: any = null;
  try { d = await r.json(); } catch {}
  if (!r.ok) throw new Error(typeof d?.detail === "string" ? d.detail : Array.isArray(d?.detail) ? "Revise los datos del formulario." : "No se pudo enviar. Intente de nuevo.");
  return d;
}

export default function Contacto() {
  const [token, setToken] = useState<string | null>(null);
  const [utm, setUtm] = useState<Record<string, string>>({});
  const [info, setInfo] = useState<any>(null);
  const [fatal, setFatal] = useState("");
  const [error, setError] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [d, setD] = useState<any>({ nombre: "", telefono: "", email: "", ciudad: "", materia: "", descripcion: "", preferencia: "whatsapp", acepta: false, sitio_web: "" });

  useEffect(() => {
    const h = window.location.hash.slice(1);
    const q = new URLSearchParams(window.location.search);
    const u: Record<string, string> = {};
    UTM.forEach((k) => { const v = q.get(k); if (v) u[k] = v.slice(0, 120); });
    setUtm(u);
    if (h) { sessionStorage.setItem(CLAVE, h); history.replaceState(null, "", window.location.pathname); }
    const t = sessionStorage.getItem(CLAVE);
    if (!t) { setFatal("Este enlace no está completo. Pida al despacho su enlace de contacto."); return; }
    setToken(t);
    llamar("/formulario/info", t).then(setInfo).catch((e) => setFatal(e.message));
  }, []);

  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    if (!d.telefono.trim() && !d.email.trim()) { setError("Escriba un teléfono o un correo para que puedan responderle."); return; }
    setEnviando(true);
    try { await llamar("/formulario", token!, { ...d, telefono: d.telefono || null, email: d.email || null, ciudad: d.ciudad || null, materia: d.materia || null,
      descripcion: d.descripcion || null, utm: Object.keys(utm).length ? utm : null }); setEnviado(true); }
    catch (x: any) { setError(x.message); }
    setEnviando(false);
  }
  const set = (k: string) => (e: any) => setD({ ...d, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <main className="min-h-screen bg-crema px-4 py-8">
      <div className="mx-auto max-w-lg">
        <div className="tarjeta p-6 sm:p-8">
          {fatal ? <p role="alert" className="text-sm text-red-800">{fatal}</p> : !info ? <p className="text-sm text-slate-500">Cargando…</p> : enviado ? (
            <div className="text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-2xl text-emerald-700" aria-hidden>✓</div>
              <h1 className="text-2xl font-extrabold text-marino">Recibimos su solicitud</h1>
              <p className="mt-2 text-sm text-slate-600">{info.despacho} le contactará por el medio que indicó. Puede cerrar esta página.</p>
            </div>
          ) : (
            <form onSubmit={enviar} className="space-y-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-turquesa-700">{info.despacho}</p>
                <h1 className="text-2xl font-extrabold text-marino">Solicite que le contactemos</h1>
                <p className="mt-1 text-sm text-slate-600">Déjenos sus datos y una breve descripción. Un integrante del despacho le responderá.</p>
              </div>
              <label className="block"><span className="etiqueta">Nombre</span><input className="campo" required minLength={2} maxLength={200} autoComplete="name" value={d.nombre} onChange={set("nombre")} /></label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block"><span className="etiqueta">Teléfono o WhatsApp</span><input className="campo" inputMode="tel" autoComplete="tel" maxLength={30} value={d.telefono} onChange={set("telefono")} /></label>
                <label className="block"><span className="etiqueta">Correo</span><input className="campo" type="email" autoComplete="email" maxLength={254} value={d.email} onChange={set("email")} /></label>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block"><span className="etiqueta">Tema</span>
                  <select className="campo" value={d.materia} onChange={set("materia")}><option value="">Elija una opción</option>{info.materias.map((x: string) => <option key={x}>{x}</option>)}</select></label>
                <label className="block"><span className="etiqueta">Ciudad (opcional)</span><input className="campo" maxLength={120} autoComplete="address-level2" value={d.ciudad} onChange={set("ciudad")} /></label>
              </div>
              <label className="block"><span className="etiqueta">¿En qué le podemos ayudar? (breve)</span>
                <textarea className="campo" rows={3} maxLength={2000} value={d.descripcion} onChange={set("descripcion")} placeholder="No incluya contraseñas, números de cuenta ni documentos." /></label>
              <label className="block"><span className="etiqueta">Prefiero que me contacten por</span>
                <select className="campo" value={d.preferencia} onChange={set("preferencia")}>{Object.entries(info.preferencias).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
              <label className="absolute -left-[9999px]" aria-hidden="true">Sitio web<input tabIndex={-1} autoComplete="off" value={d.sitio_web} onChange={set("sitio_web")} /></label>
              <label className="flex items-start gap-2 rounded-xl border border-turquesa/40 bg-turquesa-50/50 p-3 text-sm">
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" required checked={d.acepta} onChange={set("acepta")} />
                <span>Autorizo a <b>{info.despacho}</b> a contactarme por los medios que indiqué para atender esta solicitud. Puedo retirar esta autorización en cualquier momento.</span>
              </label>
              {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
              <button className="btn-turquesa w-full py-3 text-base" disabled={enviando}>{enviando ? "Enviando…" : "Enviar solicitud"}</button>
              <p className="text-center text-xs text-slate-500">Enviar este formulario no constituye asesoría jurídica ni una relación profesional.</p>
            </form>
          )}
        </div>
        <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-500">Formulario seguro de <Logo /></div>
      </div>
    </main>
  );
}
