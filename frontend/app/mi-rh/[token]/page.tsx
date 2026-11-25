"use client";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import Logo from "@/components/Logo";
import { Chip, ESTADO_INC, fechaCorta } from "@/components/rh";
import { Aviso } from "@/components/ui";
import { mxn } from "@/lib/api";

/** Portal del empleado: entra con su enlace personal y su NIP. Pensado para el celular. */
export default function PortalEmpleado() {
  const { token } = useParams<{ token: string }>();
  const clave = `nomira:rh:${token.slice(0, 12)}`;
  const [acceso, setAcceso] = useState<any>(null);
  const [sesion, setSesion] = useState<string | null>(null);
  const [yo, setYo] = useState<any>(null);
  const [nip, setNip] = useState("");
  const [tab, setTab] = useState<"avisos" | "vacaciones" | "recibos" | "documentos">("avisos");
  const [error, setError] = useState(""); const [ok, setOk] = useState("");

  const pedir = useCallback(async (ruta: string, init: RequestInit = {}, ses = sesion) => {
    const r = await fetch(`/api/portal-rh${ruta}`, { ...init, headers: { ...(init.headers || {}), ...(ses ? { Authorization: `Bearer ${ses}` } : {}) } });
    if (r.status === 401 && ses) { try { sessionStorage.removeItem(clave); } catch { /* nada */ } setSesion(null); setYo(null); throw new Error("Su sesión terminó. Escriba su NIP otra vez."); }
    const ct = r.headers.get("content-type") || "";
    if (!r.ok) { const j = ct.includes("json") ? await r.json() : {}; throw new Error(typeof j.detail === "string" ? j.detail : "No se pudo completar."); }
    return ct.includes("json") ? r.json() : r.blob();
  }, [sesion, clave]);
  const cargar = useCallback((ses?: string) => pedir("/yo", {}, ses ?? sesion).then(setYo).catch((e) => setError(e.message)), [pedir, sesion]);

  useEffect(() => {
    pedir(`/acceso/${token}`, {}, null).then(setAcceso).catch((e) => setError(e.message));
    try { const s = sessionStorage.getItem(clave); if (s) { setSesion(s); cargar(s); } } catch { /* sin almacenamiento */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function entrar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      const r = await pedir(`/acceso/${token}/entrar`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nip }) }, null);
      setSesion(r.sesion); try { sessionStorage.setItem(clave, r.sesion); } catch { /* nada */ }
      setNip(""); await cargar(r.sesion);
    } catch (x: any) { setError(x.message); }
  }
  async function hacer(f: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { await f(); setOk(msg); await cargar(); } catch (x: any) { setError(x.message); }
  }
  async function bajar(ruta: string, nombre: string) {
    try { const b = await pedir(ruta); const a = document.createElement("a"); a.href = URL.createObjectURL(b as Blob); a.download = nombre; a.click(); } catch (x: any) { setError(x.message); }
  }
  const salir = () => { try { sessionStorage.removeItem(clave); } catch { /* nada */ } setSesion(null); setYo(null); };
  const pendientesLeer = yo ? yo.avisos.filter((a: any) => a.requiere_acuse && !a.leido).length : 0;

  return (
    <div className="min-h-screen bg-crema">
      <header className="border-b border-crema-300 bg-white/90"><div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3"><Logo />
        {yo && <button className="text-sm text-slate-600 underline" onClick={salir}>Salir</button>}</div></header>
      <main className="mx-auto max-w-2xl px-4 py-6">
        <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
        {!yo && acceso && <form className="tarjeta mt-4 space-y-4 p-6" onSubmit={entrar}>
          <p className="text-sm text-slate-500">{acceso.empresa}</p>
          <h1 className="text-2xl font-extrabold text-marino">Hola, {acceso.nombre}</h1>
          <p className="text-slate-600">Este es su portal de Recursos Humanos: avisos, vacaciones, recibos y documentos.</p>
          <label className="block"><span className="etiqueta">Su NIP de 6 dígitos</span>
            <input className="campo text-center font-mono text-2xl tracking-[0.5em]" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={nip}
              onChange={(e) => setNip(e.target.value.replace(/\D/g, ""))} required minLength={6} /></label>
          <button className="btn-turquesa w-full py-3">Entrar</button>
          <p className="text-xs text-slate-500">¿Olvidó su NIP? Pídale uno nuevo a Recursos Humanos.</p>
        </form>}

        {yo && <>
          <h1 className="text-2xl font-extrabold text-marino">Hola, {yo.nombre.split(" ")[0]}</h1>
          <p className="text-sm text-slate-500">{[yo.puesto, yo.empresa].filter(Boolean).join(" · ")}</p>
          <div className="mt-4 grid grid-cols-4 gap-1 rounded-2xl bg-white p-1 text-xs font-semibold sm:text-sm" role="tablist">
            {([["avisos", `Avisos${pendientesLeer ? ` (${pendientesLeer})` : ""}`], ["vacaciones", "Vacaciones"], ["recibos", "Recibos"], ["documentos", `Documentos${yo.faltantes.length ? ` (${yo.faltantes.length})` : ""}`]] as const).map(([k, t]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`rounded-xl px-2 py-2 ${tab === k ? "bg-marino text-white" : "text-marino"}`}>{t}</button>))}</div>

          {tab === "avisos" && <section className="mt-4 space-y-3" aria-label="Avisos">
            {!yo.avisos.length && <p className="tarjeta p-6 text-center text-slate-600">No hay avisos por ahora.</p>}
            {yo.avisos.map((a: any) => <article key={a.id} className={`tarjeta p-4 ${a.requiere_acuse && !a.leido ? "border-2 border-amber-300" : ""}`}>
              <p className="text-xs text-slate-500">{fechaCorta(a.fecha)}</p><h2 className="font-bold text-marino">{a.fijado ? "📌 " : ""}{a.titulo}</h2>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{a.cuerpo}</p>
              {a.requiere_acuse && (a.leido ? <p className="mt-2 text-xs font-semibold text-emerald-700">✓ Confirmó que lo leyó</p>
                : <button className="btn-turquesa mt-3" onClick={() => hacer(() => pedir(`/avisos/${a.id}/acuse`, { method: "POST" }), "Gracias, quedó registrado.")}>Enterado</button>)}
            </article>)}
          </section>}

          {tab === "vacaciones" && <Vacaciones yo={yo} pedir={pedir} hacer={hacer} />}

          {tab === "recibos" && <section className="tarjeta mt-4 p-4" aria-label="Recibos">
            {!yo.recibos.length ? <p className="text-center text-slate-600">Todavía no hay recibos publicados.</p>
              : <ul className="divide-y divide-crema-200">{yo.recibos.map((r: any) => <li key={r.id} className="flex items-center justify-between gap-2 py-3">
                <span className="text-sm">{fechaCorta(r.inicio)} al {fechaCorta(r.fin)}<span className="block text-xs text-slate-500">Pago {fechaCorta(r.fecha_pago)}</span></span>
                <span className="flex items-center gap-3"><b className="text-marino">{mxn(r.neto)}</b><button className="btn-sec text-sm" onClick={() => bajar(`/recibos/${r.id}/pdf`, `recibo-${r.fin}.pdf`)}>PDF</button></span></li>)}</ul>}
            <p className="mt-3 text-xs text-slate-500">Recibos de control interno. Si necesita su comprobante fiscal (CFDI), pídalo a Recursos Humanos.</p>
          </section>}

          {tab === "documentos" && <Documentos yo={yo} pedir={pedir} hacer={hacer} bajar={bajar} />}
          <p className="mt-6 text-center text-xs text-slate-400">Sus datos los administra {yo.empresa} con Nomira. Para corregirlos o pedir que se borren, hable con Recursos Humanos.</p>
        </>}
      </main>
    </div>
  );
}

function Vacaciones({ yo, pedir, hacer }: { yo: any; pedir: any; hacer: any }) {
  const v = yo.vacaciones;
  const [f, setF] = useState({ tipo: "vacaciones", desde: "", hasta: "", motivo: "" });
  const archivo = useRef<HTMLInputElement>(null);
  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const d = new FormData(); d.append("tipo", f.tipo); d.append("desde", f.desde); d.append("hasta", f.hasta || f.desde); if (f.motivo) d.append("motivo", f.motivo);
    const a = archivo.current?.files?.[0]; if (a) d.append("archivo", a);
    await hacer(() => pedir("/solicitudes", { method: "POST", body: d }), "Solicitud enviada a Recursos Humanos.");
    setF({ tipo: "vacaciones", desde: "", hasta: "", motivo: "" });
  }
  return <section className="mt-4 space-y-4" aria-label="Vacaciones y permisos">
    <div className="tarjeta p-5 text-center">{v.anios === 0
      ? <p className="text-slate-700">Al cumplir su primer año ({fechaCorta(v.proximo_aniversario)}) tendrá <b>{v.dias_proximo} días</b> de vacaciones.</p>
      : <><p className="text-5xl font-extrabold text-marino">{v.disponibles - v.pendientes_aprobar}</p><p className="text-slate-600">días de vacaciones disponibles</p>
        <p className="mt-1 text-xs text-slate-500">Le corresponden {v.derecho} este año · tomados {v.tomados}{v.pendientes_aprobar ? ` · por autorizar ${v.pendientes_aprobar}` : ""}</p></>}</div>
    <form className="tarjeta space-y-3 p-5" onSubmit={enviar}>
      <h2 className="font-bold text-marino">Pedir vacaciones o permiso</h2>
      <label className="block"><span className="etiqueta">¿Qué necesita?</span><select className="campo" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>
        {Object.entries(yo.tipos_solicitud).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
      <div className="grid grid-cols-2 gap-2">
        <label className="block"><span className="etiqueta">Desde</span><input className="campo" type="date" value={f.desde} onChange={(e) => setF({ ...f, desde: e.target.value })} required /></label>
        <label className="block"><span className="etiqueta">Hasta</span><input className="campo" type="date" value={f.hasta} min={f.desde} onChange={(e) => setF({ ...f, hasta: e.target.value })} /></label></div>
      <label className="block"><span className="etiqueta">Comentario (opcional)</span><input className="campo" value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} maxLength={500} /></label>
      {f.tipo === "incapacidad" && <label className="block"><span className="etiqueta">Foto o PDF de la incapacidad del IMSS</span><input ref={archivo} className="campo" type="file" accept=".pdf,.jpg,.jpeg,.png" capture="environment" required /></label>}
      <button className="btn-turquesa w-full py-3">Enviar solicitud</button>
    </form>
    {yo.solicitudes.length > 0 && <div className="tarjeta p-4"><h2 className="font-bold text-marino">Mis solicitudes</h2>
      <ul className="mt-1 divide-y divide-crema-200 text-sm">{yo.solicitudes.map((s: any) => <li key={s.id} className="flex items-center justify-between gap-2 py-2">
        <span>{s.tipo_texto} · {s.dias} día{s.dias === 1 ? "" : "s"}<span className="block text-xs text-slate-500">{fechaCorta(s.desde)}{s.hasta !== s.desde ? ` al ${fechaCorta(s.hasta)}` : ""}{s.comentario ? ` · RH: ${s.comentario}` : ""}</span></span>
        <span className="flex items-center gap-2"><Chip e={ESTADO_INC[s.estado]} />{s.estado === "pendiente" && s.origen === "portal" && <button className="text-xs text-slate-500 underline" onClick={() => hacer(() => pedir(`/solicitudes/${s.id}`, { method: "DELETE" }), "Solicitud cancelada.")}>Cancelar</button>}</span></li>)}</ul></div>}
  </section>;
}

function Documentos({ yo, pedir, hacer, bajar }: { yo: any; pedir: any; hacer: any; bajar: any }) {
  const [tipo, setTipo] = useState(yo.faltantes[0]?.tipo || "ine");
  const archivo = useRef<HTMLInputElement>(null);
  async function subir(e: React.FormEvent) {
    e.preventDefault(); const a = archivo.current?.files?.[0]; if (!a) return;
    const d = new FormData(); d.append("tipo", tipo); d.append("archivo", a);
    await hacer(() => pedir("/documentos", { method: "POST", body: d }), "Documento enviado. Recursos Humanos lo revisará.");
    if (archivo.current) archivo.current.value = "";
  }
  return <section className="mt-4 space-y-4" aria-label="Documentos">
    {yo.faltantes.length > 0 && <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"><b>Le faltan:</b> {yo.faltantes.map((x: any) => x.texto).join(", ")}.</div>}
    <form className="tarjeta space-y-3 p-5" onSubmit={subir}>
      <h2 className="font-bold text-marino">Subir un documento</h2>
      <label className="block"><span className="etiqueta">¿Cuál?</span><select className="campo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
        {Object.entries(yo.tipos_documento).filter(([k]) => !["contrato", "alta_imss"].includes(k)).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
      <label className="block"><span className="etiqueta">Foto o PDF</span><input ref={archivo} className="campo" type="file" accept=".pdf,.jpg,.jpeg,.png" capture="environment" required /></label>
      <button className="btn-turquesa w-full py-3">Enviar</button>
    </form>
    {yo.documentos.length > 0 && <div className="tarjeta p-4"><h2 className="font-bold text-marino">Mis documentos</h2>
      <ul className="mt-1 divide-y divide-crema-200 text-sm">{yo.documentos.map((d: any) => <li key={d.id} className="flex items-center justify-between gap-2 py-2">
        <span>{d.tipo_texto}{d.nota && <span className="block text-xs text-red-700">{d.nota}</span>}</span>
        <span className="flex items-center gap-2"><Chip e={d.estado === "aceptado" ? ["Aceptado", "bg-emerald-100 text-emerald-800"] : d.estado === "rechazado" ? ["Corregir", "bg-red-100 text-red-800"] : ["En revisión", "bg-amber-100 text-amber-800"]} />
          <button className="text-xs text-turquesa-700 underline" onClick={() => bajar(`/documentos/${d.id}`, d.nombre)}>Ver</button></span></li>)}</ul></div>}
  </section>;
}
