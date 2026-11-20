"use client";
import Link from "next/link";
import { Fragment, useEffect, useState } from "react";
import LogoMarca from "@/components/Logo";
import { Modal } from "@/components/ui";
import { api, fecha, guardarSesion } from "@/lib/api";

/** Centro Legal. Los textos vienen SOLO de las versiones publicadas en el panel de la plataforma
 *  (aprobadas por el responsable de Nomira y su abogado). Aquí no se escribe ni se resume ningún texto legal. */

export async function legalPublico(ruta: string, init?: RequestInit) {
  const r = await fetch(`/api/legal${ruta}`, { cache: "no-store", ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  let d: any = null;
  try { d = await r.json(); } catch {}
  if (!r.ok) throw new Error(typeof d?.detail === "string" ? d.detail : "No se pudo cargar. Intente de nuevo.");
  return d;
}

export const RUTA_DOC: Record<string, string> = {
  terminos: "/legal/terminos", privacidad: "/legal/privacidad", privacidad_simplificado: "/legal/privacidad_simplificado",
  cookies: "/legal/cookies", anexo_tratamiento: "/legal/anexo_tratamiento", subencargados: "/legal/subencargados",
  uso_aceptable: "/legal/uso_aceptable", anexo_ia: "/legal/anexo_ia",
};

export const NOMBRE_DOC: Record<string, string> = {
  terminos: "Términos y condiciones", privacidad: "Aviso de privacidad", privacidad_simplificado: "Aviso simplificado", cookies: "Cookies",
  anexo_tratamiento: "Anexo de tratamiento", subencargados: "Subencargados", uso_aceptable: "Uso aceptable", anexo_ia: "IA e integraciones",
};

/** Lector de Markdown sencillo y seguro (sin HTML): títulos, párrafos, listas, negritas y enlaces. */
function enLinea(t: string, k: string): React.ReactNode[] {
  const partes: React.ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|\[([^\]]+)\]\(((?:https?:\/\/|\/|mailto:)[^)\s]+)\)/g;
  let ultimo = 0, x: RegExpExecArray | null, i = 0;
  while ((x = re.exec(t))) {
    if (x.index > ultimo) partes.push(t.slice(ultimo, x.index));
    if (x[1]) partes.push(<b key={`${k}b${i++}`}>{x[1]}</b>);
    else partes.push(<a key={`${k}a${i++}`} href={x[3]} className="font-semibold text-turquesa-700 underline" {...(x[3].startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{x[2]}</a>);
    ultimo = re.lastIndex;
  }
  if (ultimo < t.length) partes.push(t.slice(ultimo));
  return partes;
}

export function TextoLegal({ texto }: { texto: string }) {
  const bloques: React.ReactNode[] = [];
  const lineas = texto.replace(/\r\n/g, "\n").split("\n");
  let parrafo: string[] = [], lista: { ord: boolean; items: string[] } | null = null, n = 0;
  const cerrar = () => {
    if (parrafo.length) { bloques.push(<p key={n++} className="my-3 leading-relaxed">{enLinea(parrafo.join(" "), `p${n}`)}</p>); parrafo = []; }
    if (lista) {
      const L = lista.ord ? "ol" : "ul";
      bloques.push(<L key={n++} className={`my-3 space-y-1 pl-6 ${lista.ord ? "list-decimal" : "list-disc"}`}>{lista.items.map((it, j) => <li key={j}>{enLinea(it, `l${n}-${j}`)}</li>)}</L>);
      lista = null;
    }
  };
  for (const l of lineas) {
    const s = l.trim();
    let h;
    if (!s) { cerrar(); continue; }
    if ((h = /^(#{1,4})\s+(.*)$/.exec(s))) {
      cerrar();
      const nivel = h[1].length;
      const cls = nivel === 1 ? "mt-8 text-2xl font-extrabold" : nivel === 2 ? "mt-7 text-xl font-bold" : "mt-5 text-lg font-bold";
      bloques.push(<p key={n++} role="heading" aria-level={Math.min(nivel + 1, 6)} className={`${cls} text-marino`}>{enLinea(h[2], `h${n}`)}</p>);
    } else if (/^(-{3,}|\*{3,})$/.test(s)) { cerrar(); bloques.push(<hr key={n++} className="my-6 border-crema-300" />); }
    else if ((h = /^[-*•]\s+(.*)$/.exec(s))) { if (parrafo.length || (lista && lista.ord)) cerrar(); lista = lista || { ord: false, items: [] }; lista.items.push(h[1]); }
    else if ((h = /^\d+[.)]\s+(.*)$/.exec(s))) { if (parrafo.length || (lista && !lista.ord)) cerrar(); lista = lista || { ord: true, items: [] }; lista.items.push(h[1]); }
    else { if (lista) cerrar(); parrafo.push(s); }
  }
  cerrar();
  return <div className="text-[15px] text-slate-800">{bloques.map((b, i) => <Fragment key={i}>{b}</Fragment>)}</div>;
}

/** Enlaces legales para pies de página (sitio, inicio de sesión y app). */
export function EnlacesLegales({ claro = false }: { claro?: boolean }) {
  const c = claro ? "text-white/60 hover:text-white" : "text-slate-500 hover:text-marino";
  return (
    <nav aria-label="Documentos legales" className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
      <Link className={c} href="/legal/terminos">Términos</Link>
      <Link className={c} href="/legal/privacidad">Aviso de privacidad</Link>
      <Link className={c} href="/legal/cookies">Cookies</Link>
      <Link className={c} href="/legal">Centro legal</Link>
    </nav>
  );
}

/** Aviso de privacidad simplificado junto a un formulario (art. 16 LFPDPPP). Si aún no está publicado,
 *  se dice con honestidad y se enlaza al Centro Legal. Devuelve el id de la versión mostrada. */
export function AvisoCorto({ onVersion }: { onVersion?: (id: number | null, marketing: boolean) => void }) {
  const [d, setD] = useState<any>(null);
  const [abierto, setAbierto] = useState(false);
  useEffect(() => {
    legalPublico("/documentos/privacidad_simplificado").then((x) => { setD(x); onVersion?.(x.version?.id ?? null, !!x.contacto?.marketing_habilitado); })
      .catch(() => setD({ version: null }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return null;
  if (!d.version) return (
    <p className="text-xs text-slate-500">Consulte cómo tratamos sus datos en el <Link className="font-semibold text-turquesa-700 underline" href="/legal" target="_blank">Centro legal</Link>.</p>
  );
  return (
    <div className="rounded-xl border border-crema-300 bg-crema/60 p-3 text-xs text-slate-600">
      <div className="flex items-center justify-between gap-2">
        <b className="text-marino">Aviso de privacidad simplificado</b>
        <button type="button" className="font-semibold text-turquesa-700 underline" onClick={() => setAbierto(!abierto)} aria-expanded={abierto}>{abierto ? "Ocultar" : "Leer"}</button>
      </div>
      {abierto && <div className="mt-2 max-h-56 overflow-y-auto pr-1 text-[13px]"><TextoLegal texto={d.version.contenido} /></div>}
      <p className="mt-1">Versión {d.version.version}. Aviso integral: <Link className="font-semibold text-turquesa-700 underline" href="/legal/privacidad" target="_blank">ver aquí</Link>.</p>
    </div>
  );
}

/** Pantalla de aceptación dentro de la app: aparece solo si hay una versión vigente que la persona
 *  aún no acepta (o una nueva que pide aceptarse otra vez). Casillas separadas y SIN marcar. */
export function AceptacionLegal() {
  const [p, setP] = useState<any>(null);
  const [marcas, setMarcas] = useState<Record<number, boolean>>({});
  const [marketing, setMarketing] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { api.get("/legal/pendientes").then(setP).catch(() => {}); }, []);
  if (!p || p.pendientes.length === 0) return null;
  const todas = p.pendientes.every((v: any) => marcas[v.id]);
  const preguntarMarketing = p.marketing.habilitado && !p.marketing.actual;
  async function continuar() {
    setError(""); setEnviando(true);
    try {
      const r = await api.post("/legal/aceptar", { version_ids: p.pendientes.map((v: any) => v.id), marketing: preguntarMarketing ? marketing : null, contexto: "inicio_sesion" });
      setP(r);
    } catch (e: any) { setError(e.message); setEnviando(false); }
  }
  return (
    <Modal titulo="Antes de continuar" onCerrar={() => {}} ancho="max-w-xl" sinCerrar>
      <div className="space-y-4 text-sm">
        <p className="text-slate-600">{p.pendientes.some((v: any) => v.requiere_aceptacion) ? "Actualizamos documentos que requieren su aceptación." : "Para usar Nomira, revise estos documentos."} Puede abrirlos en otra pestaña.</p>
        {p.pendientes.map((v: any) => (
          <label key={v.id} className="flex items-start gap-3 rounded-xl border border-crema-300 p-3">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={!!marcas[v.id]} onChange={(e) => setMarcas({ ...marcas, [v.id]: e.target.checked })} />
            <span>
              {v.evento === "aceptacion" ? "He leído y acepto los " : "He leído el "}
              <Link className="font-semibold text-turquesa-700 underline" href={`${RUTA_DOC[v.documento]}?version_id=${v.id}`} target="_blank">{v.documento_titulo}</Link>
              <span className="text-slate-500"> (versión {v.version}{v.vigente_desde ? `, vigente desde ${fecha(v.vigente_desde)}` : ""})</span>
              {v.resumen_cambios && <span className="mt-1 block text-xs text-slate-500">Cambios: {v.resumen_cambios}</span>}
            </span>
          </label>))}
        {preguntarMarketing && (
          <label className="flex items-start gap-3 rounded-xl border border-dashed border-crema-300 p-3">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} />
            <span>Opcional: acepto recibir información comercial de Nomira. <span className="text-slate-500">Puede cambiarlo cuando quiera en «Mi perfil».</span></span>
          </label>)}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button type="button" className="text-sm font-semibold text-slate-500 hover:underline" onClick={() => { guardarSesion(null); window.location.href = "/login"; }}>Ahora no, cerrar sesión</button>
          <button className="btn-turquesa" disabled={!todas || enviando} onClick={continuar}>{enviando ? "Guardando…" : "Continuar"}</button>
        </div>
      </div>
    </Modal>
  );
}

/** «Mi perfil»: documentos aceptados y consentimiento opcional. */
export function MisDocumentosLegales() {
  const [regs, setRegs] = useState<any[] | null>(null);
  const [p, setP] = useState<any>(null);
  const [error, setError] = useState("");
  const cargar = () => { api.get("/legal/mis-registros").then(setRegs).catch(() => setRegs([])); api.get("/legal/pendientes").then(setP).catch(() => {}); };
  useEffect(cargar, []);
  async function marketing(v: boolean) {
    setError("");
    try { setP(await api.post("/legal/aceptar", { version_ids: [], marketing: v, contexto: "perfil" })); cargar(); } catch (e: any) { setError(e.message); }
  }
  return (
    <section className="tarjeta p-6">
      <h2 className="font-semibold text-marino">Documentos legales</h2>
      <p className="mt-1 text-xs text-slate-500">Registro de lo que usted aceptó o confirmó haber leído. Consulte los textos en el <Link className="font-semibold text-turquesa-700 underline" href="/legal">Centro legal</Link>.</p>
      {regs && regs.length === 0 && <p className="mt-3 text-sm text-slate-400">Aún no hay registros.</p>}
      <ul className="mt-3 divide-y divide-crema-200 text-sm">
        {(regs || []).map((r) => (
          <li key={r.id} className="flex flex-wrap justify-between gap-2 py-2">
            <span>{r.evento_texto}: {r.version_id ? <Link className="text-turquesa-700 underline" href={`${RUTA_DOC[r.documento] || "/legal"}?version_id=${r.version_id}`}>{r.documento_titulo}{r.version ? ` v${r.version}` : ""}</Link> : r.documento_titulo}</span>
            <span className="text-xs text-slate-500">{new Date(r.creado_en).toLocaleString("es-MX")}</span>
          </li>))}
      </ul>
      {p?.marketing?.habilitado && (
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-turquesa" checked={p.marketing.actual} onChange={(e) => marketing(e.target.checked)} />
          Acepto recibir información comercial de Nomira (opcional)
        </label>)}
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
    </section>
  );
}

/** «Mi empresa»: anexo de tratamiento de datos del despacho. */
export function AnexoTratamiento() {
  const [r, setR] = useState<any>(null);
  const [marca, setMarca] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api.get("/legal/organizacion").then(setR).catch(() => {}); }, []);
  if (!r) return null;
  return (
    <section className="tarjeta mt-5 p-6">
      <h2 className="text-lg font-bold text-marino">Anexo de tratamiento de datos</h2>
      {!r.anexo ? (
        <p className="mt-1 text-sm text-slate-500">El anexo aún no está publicado. Cuando Nomira lo publique, podrá consultarlo y aceptarlo aquí.</p>
      ) : <>
        <p className="mt-1 text-sm text-slate-600">Condiciones con las que Nomira trata, por cuenta de su despacho, los datos de sus clientes. Versión vigente: <b>{r.anexo.version}</b>.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link className="btn-sec" href={`/legal/anexo_tratamiento?version_id=${r.anexo.id}`} target="_blank">Consultar o imprimir</Link>
        </div>
        {r.pendiente ? (r.puede_aceptar ? (
          <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm">
            <label className="flex items-start gap-2"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={marca} onChange={(e) => setMarca(e.target.checked)} />
              <span>Leí el anexo (versión {r.pendiente.version}) y lo acepto en nombre de mi despacho.</span></label>
            <button className="btn-turquesa mt-2" disabled={!marca} onClick={async () => { setError(""); try { setR(await api.post("/legal/organizacion/anexo", { version_id: r.pendiente.id })); } catch (e: any) { setError(e.message); } }}>Aceptar anexo</button>
          </div>) : <p className="mt-3 text-sm text-amber-800">Pendiente de aceptar por un administrador del despacho.</p>)
          : <p className="mt-3 text-sm text-emerald-700">Su despacho ya aceptó la versión vigente.</p>}
        {r.aceptaciones.length > 0 && <ul className="mt-3 text-xs text-slate-500">{r.aceptaciones.map((a: any, i: number) => <li key={i}>Versión {a.version} aceptada por {a.usuario || "—"} el {new Date(a.creado_en).toLocaleString("es-MX")}</li>)}</ul>}
        {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
      </>}
    </section>
  );
}

/** Marco de las páginas públicas del Centro Legal. */
export function MarcoLegal({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-crema">
      <header className="border-b border-crema-300 bg-white/80 backdrop-blur print:hidden">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3 px-5 py-3.5">
          <Link href="/" aria-label="Nomira, inicio"><LogoMarca /></Link>
          <nav className="flex gap-4 text-sm font-semibold"><Link className="text-slate-600 hover:text-marino" href="/legal">Centro legal</Link>
            <Link className="text-slate-600 hover:text-marino" href="/login">Iniciar sesión</Link></nav>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-5 py-10">{children}</main>
      <footer className="space-y-1.5 border-t border-crema-300 px-5 py-6 text-center text-xs text-slate-500 print:hidden">
        <EnlacesLegales />
        <p>© {new Date().getFullYear()} Nomira</p>
      </footer>
    </div>
  );
}
