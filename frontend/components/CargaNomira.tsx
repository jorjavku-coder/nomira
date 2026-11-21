"use client";
import { useEffect, useState } from "react";

/** Logotipo de Nomira girando dentro de un aro turquesa. */
export function LogoCargando({ tam = 112 }: { tam?: number }) {
  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: tam, height: tam }} aria-hidden>
      <svg viewBox="0 0 100 100" className="nm-aro absolute inset-0 h-full w-full">
        <circle cx="50" cy="50" r="46" fill="none" stroke="#C2EFEA" strokeWidth="5" />
        <circle cx="50" cy="50" r="46" fill="none" stroke="#01B2A6" strokeWidth="5" strokeLinecap="round" strokeDasharray="70 220" />
      </svg>
      <span className="flex items-center justify-center rounded-full bg-white shadow-flotante" style={{ width: tam * 0.74, height: tam * 0.74 }}>
        <svg viewBox="15 15 290 315" className="nm-girando" style={{ width: tam * 0.42, height: tam * 0.42 }} focusable="false">
          <path fill="#123048" d="M25 88V60q0-35 35-35h140q93 0 93 93v34l-75 68v-82q0-53-53-53H48q-14 0-23 3z" />
          <rect fill="#123048" x="28" y="117" width="162" height="38" rx="19" />
          <rect fill="#123048" x="28" y="184" width="162" height="38" rx="19" />
          <rect fill="#123048" x="28" y="253" width="100" height="38" rx="19" />
          <path fill="#01B2A6" d="M293 187v101q0 32-32 32h-65q-10 0-18-8l-30-30q-10-12 2-22t23 0l22 22z" />
        </svg>
      </span>
    </span>
  );
}

// ------------------------------------------------------------------ registro global de peticiones

type Tipo = "subida" | "entrada" | "guardado" | "lectura";
type Trabajo = { id: number; tipo: Tipo; texto: string; inicio: number; fin?: number };
type Aviso = { id: number; tipo: "ok" | "error"; texto: string; hasta: number };

const trabajos = new Map<number, Trabajo>();
let avisos: Aviso[] = [];
const oyentes = new Set<() => void>();
let siguiente = 1;
const avisar = () => oyentes.forEach((f) => f());

/** Muestra un aviso breve (p. ej. «Se cargó con éxito»). También lo pueden usar las páginas. */
export function notificar(texto: string, tipo: "ok" | "error" = "ok") {
  const a = { id: siguiente++, tipo, texto, hasta: Date.now() + (tipo === "ok" ? 4500 : 6500) };
  avisos = [...avisos.slice(-2), a];
  programar(a);
}

// Los avisos sobreviven a un cambio de página completo (p. ej. tras subir un archivo y abrir el resultado).
const LLAVE = "nomira:avisos";
function guardar() { try { sessionStorage.setItem(LLAVE, JSON.stringify(avisos)); } catch {} }
function programar(a: Aviso) {
  guardar();
  avisar();
  setTimeout(() => { avisos = avisos.filter((x) => x.id !== a.id); guardar(); avisar(); }, Math.max(0, a.hasta - Date.now()));
}
function recuperar() {
  try {
    const previos: Aviso[] = JSON.parse(sessionStorage.getItem(LLAVE) || "[]");
    avisos = previos.filter((a) => a.hasta > Date.now()).map((a) => ({ ...a, id: siguiente++ }));
    avisos.forEach(programar);
  } catch {}
}

// Peticiones que corren solas en segundo plano: no deben tapar la pantalla.
const SILENCIOSAS = [/\/contador$/, /\/sin-leer$/, /\/avisos\/leidos$/, /\/agenda\/calcular$/, /\/lecciones\/\d+\/scorm$/, /\/no-leidos/, /\/salud$/];
const ENTRADA = /^\/api\/(auth\/login|plataforma\/login)(\/codigo)?$/;
const ultimaLectura = new Map<string, number>();
const UMBRAL = { subida: 0, entrada: 0, guardado: 400, lectura: 500 };
const MINIMO = 900; // una vez visible, el logotipo se queda al menos esto (ms) para que se alcance a ver
const TEXTO: Record<Tipo, string> = { subida: "Subiendo archivo…", entrada: "Entrando…", guardado: "Guardando…", lectura: "Cargando…" };

function archivosDe(body: any): string[] {
  if (typeof FormData === "undefined" || !(body instanceof FormData)) return [];
  const n: string[] = [];
  body.forEach((v) => { if (typeof File !== "undefined" && v instanceof File) n.push(v.name); });
  return n;
}

function instalar() {
  const w = window as any;
  if (w.__nomiraCarga) return;
  w.__nomiraCarga = true;
  recuperar();
  const original = window.fetch.bind(window);
  window.fetch = async (entrada: RequestInfo | URL, init?: RequestInit) => {
    let url: URL;
    try { url = new URL(typeof entrada === "string" || entrada instanceof URL ? entrada.toString() : entrada.url, window.location.href); }
    catch { return original(entrada, init); }
    const ruta = url.pathname;
    if (url.origin !== window.location.origin || !ruta.startsWith("/api/") || SILENCIOSAS.some((r) => r.test(ruta))) return original(entrada, init);
    const metodo = (init?.method || (entrada instanceof Request ? entrada.method : "GET")).toUpperCase();
    const nombres = archivosDe(init?.body);
    let tipo: Tipo = ENTRADA.test(ruta) ? "entrada" : nombres.length ? "subida" : metodo === "GET" ? "lectura" : "guardado";
    if (tipo === "lectura") {  // la misma consulta repetida en poco tiempo = actualización automática: sin indicador
      const clave = ruta + url.search, antes = ultimaLectura.get(clave) || 0;
      ultimaLectura.set(clave, Date.now());
      if (Date.now() - antes < 120000) return original(entrada, init);
    }
    const t: Trabajo = { id: siguiente++, tipo, inicio: Date.now(),
      texto: tipo === "subida" ? (nombres.length > 1 ? `Subiendo ${nombres.length} archivos…` : `Subiendo «${nombres[0]}»…`) : TEXTO[tipo] };
    trabajos.set(t.id, t);
    setTimeout(avisar, UMBRAL[tipo] + 10);
    try {
      const r = await original(entrada, init);
      if (r.ok && tipo === "subida") {
        notificar(nombres.length > 1 ? `${nombres.length} archivos se cargaron con éxito.` : `«${nombres[0]}» se cargó con éxito.`);
      } else if (r.ok && tipo === "entrada") {
        r.clone().json().then((d) => { if (d?.token) notificar("Sesión iniciada. ¡Bienvenido!"); }).catch(() => {});
      } else if (!r.ok && tipo === "subida") {
        notificar("No se pudo cargar el archivo. Revise el mensaje en pantalla.", "error");
      }
      return r;
    } catch (e) {
      if (tipo !== "lectura") notificar("No hay conexión con Nomira. Revise su internet e intente de nuevo.", "error");
      throw e;
    } finally {
      const visible = Date.now() - t.inicio >= UMBRAL[t.tipo];
      const resta = visible ? MINIMO - (Date.now() - t.inicio - UMBRAL[t.tipo]) : 0;
      if (resta > 0 && t.tipo !== "lectura") { t.fin = Date.now(); setTimeout(() => { trabajos.delete(t.id); avisar(); }, resta); }
      else trabajos.delete(t.id);
      avisar();
    }
  };
}

/** Se monta una vez en el diseño raíz: vale para todos los módulos, el panel y las páginas públicas. */
export default function IndicadorCarga() {
  const [, setN] = useState(0);
  useEffect(() => {
    instalar();
    const f = () => setN((n) => n + 1);
    oyentes.add(f);
    return () => { oyentes.delete(f); };
  }, []);
  const ahora = Date.now();
  const vigentes = [...trabajos.values()].filter((t) => ahora - t.inicio >= UMBRAL[t.tipo]);
  const pantalla = vigentes.filter((t) => t.tipo !== "lectura");
  const principal = pantalla.find((t) => t.tipo === "subida") || pantalla.find((t) => t.tipo === "entrada") || pantalla[0];
  const leyendo = !principal && vigentes.some((t) => t.tipo === "lectura");
  return (
    <>
      {(principal || leyendo) && (
        <div className={`fixed inset-0 z-[100] flex flex-col items-center justify-center gap-4 p-6 ${principal ? "bg-marino-900/40 backdrop-blur-[2px]" : "pointer-events-none"}`}
          role="status" aria-live="polite" aria-busy="true">
          <div className="nm-aparecer flex flex-col items-center gap-3">
            <LogoCargando tam={principal ? 120 : 96} />
            <p className="rounded-full bg-white/95 px-4 py-1.5 text-center font-marca text-sm font-bold text-marino shadow-flotante">{principal ? principal.texto : "Cargando…"}</p>
            {principal?.tipo === "subida" && <p className="rounded-full bg-white/90 px-3 py-1 text-xs text-slate-600">No cierre esta ventana hasta que termine.</p>}
          </div>
        </div>
      )}
      <div className="pointer-events-none fixed inset-x-0 top-4 z-[110] flex flex-col items-center gap-2 px-4" aria-live="polite">
        {avisos.map((a) => (
          <div key={a.id} role={a.tipo === "error" ? "alert" : "status"}
            className={`nm-aparecer pointer-events-auto flex max-w-md items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold shadow-flotante ${a.tipo === "ok" ? "bg-marino text-white" : "bg-red-700 text-white"}`}>
            <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${a.tipo === "ok" ? "bg-turquesa-brillante text-marino-900" : "bg-white/20"}`} aria-hidden>
              {a.tipo === "ok" ? <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 10.5l4 4 8-9" /></svg> : "!"}
            </span>
            {a.texto}
          </div>
        ))}
      </div>
    </>
  );
}
