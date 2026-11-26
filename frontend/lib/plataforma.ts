"use client";
/** Cliente del panel de la plataforma. Sesión aparte de la de los clientes (otra llave y otro
 * token): una no sirve para la otra, ni en el navegador ni en el servidor. */
import { ErrorApi } from "@/lib/api";

const LLAVE = "nomira_plataforma";
const EVENTO = "nomira-plataforma-sesion";

export type AdminP = { id: number; nombre: string; email: string; activo: boolean; ultimo_acceso: string | null; rol?: string };
export const esSuperadmin = (s: SesionP | null) => s?.admin.rol === "superadministrador";
export const esEjecutivo = (s: SesionP | null) => s?.admin.rol === "ejecutivo_comercial";
export type SesionP = { token: string; admin: AdminP };

export function leerSesionP(): SesionP | null {
  if (typeof window === "undefined") return null;
  try { return JSON.parse(sessionStorage.getItem(LLAVE) || "null"); } catch { return null; }
}
export function guardarSesionP(s: SesionP | null) {
  if (s) sessionStorage.setItem(LLAVE, JSON.stringify(s));
  else sessionStorage.removeItem(LLAVE);
  window.dispatchEvent(new Event(EVENTO));
}
export function alCambiarSesionP(fn: () => void): () => void {
  window.addEventListener(EVENTO, fn);
  return () => window.removeEventListener(EVENTO, fn);
}
/** Avisa al menú que cambió algo que muestra contadores (solicitudes, mensajes). */
export const avisarContadores = () => window.dispatchEvent(new Event("nomira-plataforma-contadores"));

async function pedir(ruta: string, init: RequestInit = {}): Promise<Response> {
  const s = leerSesionP();
  const login = ruta === "/login";
  if (!s && !login) {
    if (window.location.pathname !== "/plataforma/login") window.location.href = "/plataforma/login";
    throw new ErrorApi(401, "Inicie sesión para continuar.");
  }
  const headers = new Headers(init.headers);
  if (s && !login) headers.set("Authorization", `Bearer ${s.token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const r = await fetch(`/api/plataforma${ruta}`, { ...init, headers, cache: "no-store" });
  if (r.status === 401 && !login) {
    guardarSesionP(null);
    if (window.location.pathname !== "/plataforma/login") window.location.href = "/plataforma/login";
  }
  if (!r.ok) {
    let detalle: any = null;
    try { detalle = (await r.json()).detail; } catch {}
    throw new ErrorApi(r.status, typeof detalle === "string" ? detalle : Array.isArray(detalle) ? detalle.map((d: any) => d.msg).join("; ") : `Error ${r.status}`, detalle);
  }
  return r;
}

export const apiP = {
  get: async <T = any>(ruta: string): Promise<T> => (await pedir(ruta)).json(),
  post: async <T = any>(ruta: string, cuerpo?: unknown): Promise<T> =>
    (await pedir(ruta, { method: "POST", body: JSON.stringify(cuerpo ?? {}) })).json(),
  patch: async <T = any>(ruta: string, cuerpo: unknown): Promise<T> =>
    (await pedir(ruta, { method: "PATCH", body: JSON.stringify(cuerpo) })).json(),
  put: async <T = any>(ruta: string, cuerpo: unknown): Promise<T> =>
    (await pedir(ruta, { method: "PUT", body: JSON.stringify(cuerpo) })).json(),
  borrar: async <T = any>(ruta: string): Promise<T> => (await pedir(ruta, { method: "DELETE" })).json(),
  /** Subida de archivos (multipart). */
  subir: async <T = any>(ruta: string, datos: FormData): Promise<T> => (await pedir(ruta, { method: "POST", body: datos })).json(),
  subirPut: async <T = any>(ruta: string, datos: FormData): Promise<T> => (await pedir(ruta, { method: "PUT", body: datos })).json(),
  texto: async (ruta: string): Promise<string> => (await pedir(ruta)).text(),
  /** Descarga binaria (PDF): devuelve un Blob. */
  blob: async (ruta: string): Promise<Blob> => (await pedir(ruta)).blob(),
};
