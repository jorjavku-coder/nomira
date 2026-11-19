"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Logo from "@/components/Logo";

/** Portal del cliente (Nomira AFORE). Muestra SOLO lo que el despacho decidió compartir. El enlace llega
 *  como /portal#token: el fragmento no viaja al servidor; se quita de la barra y se manda en un encabezado. */
const CLAVE = "nomira_portal", CLAVE_SESION = "nomira_portal_sesion";
const fechaLarga = (iso: string) => new Date(iso).toLocaleString("es-MX", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });

async function llamar(ruta: string, token: string, init: RequestInit = {}) {
  const h = new Headers(init.headers);
  h.set("X-Enlace", token);
  const s = sessionStorage.getItem(CLAVE_SESION);
  if (s) h.set("X-Sesion", s);
  if (init.body && !(init.body instanceof FormData)) h.set("Content-Type", "application/json");
  const r = await fetch(`/api/portal-afore${ruta}`, { ...init, headers: h, cache: "no-store" });
  let d: any = null;
  try { d = await r.json(); } catch {}
  if (!r.ok) throw Object.assign(new Error(typeof d?.detail === "string" ? d.detail : "No se pudo completar. Intente de nuevo."), { estado: r.status });
  return d;
}

export default function Portal() {
  const [token, setToken] = useState<string | null>(null);
  const [info, setInfo] = useState<any>(null);
  const [fatal, setFatal] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [codigoEnviado, setCodigoEnviado] = useState<any>(null);
  const [codigo, setCodigo] = useState("");
  useEffect(() => {
    const h = window.location.hash.slice(1);
    if (h) {
      if (sessionStorage.getItem(CLAVE) !== h) sessionStorage.removeItem(CLAVE_SESION);
      sessionStorage.setItem(CLAVE, h);
      history.replaceState(null, "", window.location.pathname);
    }
    const t = sessionStorage.getItem(CLAVE);
    if (!t) setFatal("Abra esta página desde el enlace que le envió su despacho.");
    setToken(t);
  }, []);
  const cargar = useCallback(async () => {
    if (!token) return;
    try { setInfo(await llamar("/estado", token, { method: "POST" })); } catch (e: any) { setFatal(e.message); }
  }, [token]);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(fn: () => Promise<any>, msj = "") {
    setError(""); setOk("");
    try { const r = await fn(); if (msj) setOk(msj); await cargar(); return r; } catch (e: any) { setError(e.message); if (e.estado === 401) { sessionStorage.removeItem(CLAVE_SESION); cargar(); } }
  }
  return (
    <main className="min-h-screen bg-crema">
      <header className="bg-marino-900 px-6 py-5"><div className="mx-auto max-w-2xl"><Logo oscuro /></div></header>
      <div className="h-1 bg-turquesa" />
      <div className="mx-auto max-w-2xl space-y-5 px-4 py-8">
        {fatal ? (
          <section className="tarjeta p-8 text-center"><h1 className="text-2xl font-extrabold text-marino">No es posible abrir su portal</h1><p className="mt-2 text-slate-600">{fatal}</p></section>
        ) : !info ? <p className="text-center text-slate-500" role="status">Cargando…</p> : (
          <>
            <section className="tarjeta p-6">
              <p className="text-sm font-semibold text-turquesa-700">{info.despacho}</p>
              <h1 className="mt-1 text-2xl font-extrabold text-marino">Hola, {info.nombre}</h1>
              <p className="mt-1 text-slate-600">Aquí puede ver cómo va su trámite, qué documentos faltan y enviarlos de forma segura.</p>
            </section>
            {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}
            {ok && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{ok}</div>}
            {!info.verificado ? (
              <section className="tarjeta p-6">
                <h2 className="text-lg font-bold text-marino">Confirme que es usted</h2>
                <p className="mt-1 text-sm text-slate-600">Le enviaremos un código de 6 dígitos a <b>{info.email}</b>.</p>
                {!codigoEnviado ? <button className="btn-primario mt-4" onClick={async () => { setError(""); try { setCodigoEnviado(await llamar("/codigo", token!, { method: "POST" })); } catch (e: any) { setError(e.message); } }}>Enviarme el código</button> : (
                  <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={async (e) => { e.preventDefault(); setError("");
                    try { const r = await llamar("/verificar", token!, { method: "POST", body: JSON.stringify({ codigo }) }); sessionStorage.setItem(CLAVE_SESION, r.sesion); setCodigo(""); cargar(); } catch (err: any) { setError(err.message); } }}>
                    <label className="block"><span className="etiqueta">Código</span><input className="campo w-44 text-center font-mono text-2xl tracking-[0.4em]" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required autoFocus value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} /></label>
                    <button className="btn-primario">Entrar</button>
                  </form>)}
              </section>
            ) : (
              <>
                {info.casos.length === 0 && <section className="tarjeta p-6 text-slate-600">Su despacho todavía no ha publicado información de su trámite. Vuelva a consultar más tarde.</section>}
                {info.casos.map((c: any) => <Caso key={c.id} c={c} token={token!} hacer={hacer} />)}
                <Preferencias info={info} token={token!} hacer={hacer} />
              </>
            )}
            <p className="text-center text-xs text-slate-400">Enlace válido hasta el {fechaLarga(info.expira_en)}. Nadie del despacho le pedirá contraseñas por este medio.</p>
          </>
        )}
      </div>
    </main>
  );
}

function Caso({ c, token, hacer }: any) {
  return (
    <section className="tarjeta space-y-4 p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Su trámite</p>
        <h2 className="text-xl font-bold text-marino">{c.tramite}</h2>
      </div>
      <div className="rounded-xl bg-crema/70 p-4">
        <p className="text-sm text-slate-500">Cómo va</p>
        <p className="text-lg font-semibold text-marino">{c.estado || "El despacho está revisando su caso."}</p>
        {c.siguiente_paso && <p className="mt-2 text-slate-700"><b>Siguiente paso:</b> {c.siguiente_paso}</p>}
        {c.actualizado_en && <p className="mt-1 text-xs text-slate-500">Última actualización: {fechaLarga(c.actualizado_en)}</p>}
      </div>
      {c.documentos_pedidos.length > 0 && (
        <div>
          <h3 className="font-bold text-marino">Documentos que le pedimos</h3>
          <ul className="mt-2 space-y-2">{c.documentos_pedidos.map((r: any) => <Pedido key={r.id} r={r} token={token} hacer={hacer} />)}</ul>
        </div>
      )}
      {c.documentos.length > 0 && (
        <div>
          <h3 className="font-bold text-marino">Documentos</h3>
          <ul className="mt-2 divide-y divide-crema-300 text-sm">{c.documentos.map((d: any, i: number) => (
            <li key={i} className="py-2"><b>{d.nombre}</b>
              <div className="text-xs text-slate-500">{d.enviado_por_usted ? `Usted lo envió el ${fechaLarga(d.fecha)}` : `Compartido por el despacho el ${fechaLarga(d.fecha)}`}
                {d.enviado_por_usted && (d.recepcion_confirmada_en ? <span className="text-emerald-700"> · ✓ El despacho confirmó la recepción el {fechaLarga(d.recepcion_confirmada_en)}</span> : " · El despacho aún no confirma la recepción")}</div></li>))}</ul>
        </div>
      )}
    </section>
  );
}

function Pedido({ r, token, hacer }: any) {
  const entrada = useRef<HTMLInputElement>(null);
  const [enviando, setEnviando] = useState(false);
  return (
    <li className={`rounded-xl p-3 ring-1 ${r.pendiente ? "bg-amber-50 ring-amber-200" : "bg-white ring-crema-300"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-marino">{r.nombre}</span>
        <span className={`text-sm font-semibold ${r.pendiente ? "text-amber-800" : "text-emerald-700"}`}>{r.estado}</span>
      </div>
      {r.indicacion && <p className="mt-1 text-sm text-slate-600">{r.indicacion}</p>}
      <input ref={entrada} type="file" className="hidden" accept="application/pdf,.pdf,image/png,image/jpeg,image/webp" onChange={async (e) => {
        const f = e.target.files?.[0]; if (!f) return;
        setEnviando(true);
        const fd = new FormData(); fd.append("archivo", f); fd.append("requisito_id", String(r.id));
        await hacer(() => llamar("/documentos", token, { method: "POST", body: fd }), `Recibimos «${f.name}». El despacho confirmará su recepción.`);
        setEnviando(false); if (entrada.current) entrada.current.value = "";
      }} />
      <button className="btn-turquesa mt-2 w-full sm:w-auto" disabled={enviando} onClick={() => entrada.current?.click()}>{enviando ? "Enviando…" : r.pendiente ? "Enviar documento" : "Enviar otro archivo"}</button>
      <p className="mt-1 text-xs text-slate-500">PDF o fotografía (JPG, PNG). Puede tomar la foto con su celular.</p>
    </li>
  );
}

function Preferencias({ info, token, hacer }: any) {
  const p = info.preferencias;
  const cambiar = (body: any, msj: string) => hacer(() => llamar("/preferencias", token, { method: "POST", body: JSON.stringify(body) }), msj);
  return (
    <section className="tarjeta space-y-3 p-6">
      <h2 className="font-bold text-marino">Cómo quiere recibir avisos</h2>
      <p className="text-sm text-slate-600">Los avisos solo le indican que hay novedades; los detalles siempre los verá aquí. Puede cambiar esto cuando quiera.</p>
      {(["whatsapp", "correo"] as const).map((k) => {
        const disponible = k === "whatsapp" ? p.tiene_telefono : p.tiene_correo;
        return (
          <label key={k} className="flex items-center justify-between gap-3 rounded-xl bg-crema/60 p-3">
            <span><b>{k === "whatsapp" ? "WhatsApp" : "Correo electrónico"}</b>{!disponible && <span className="block text-xs text-slate-500">El despacho no tiene registrado su {k === "whatsapp" ? "teléfono" : "correo"}.</span>}</span>
            <input type="checkbox" className="h-5 w-5 accent-turquesa" disabled={!disponible} checked={p.consentimientos[k]}
              onChange={(e) => cambiar({ [k]: e.target.checked }, e.target.checked ? "Listo: recibirá avisos por este medio." : "Listo: ya no recibirá avisos por este medio.")} />
          </label>);
      })}
    </section>
  );
}
