"use client";

const LLAVE = "qc_sesion";

export type Usuario = { id: number; nombre: string; email: string; rol: string; activo?: boolean; foto?: string | null };
export type Sesion = { token: string; usuario: Usuario; organizacion: string };
const EVENTO = "nomira-sesion";

export function leerSesion(): Sesion | null {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(sessionStorage.getItem(LLAVE) || "null");
  } catch {
    return null;
  }
}
export function guardarSesion(s: Sesion | null) {
  if (s) sessionStorage.setItem(LLAVE, JSON.stringify(s));
  else sessionStorage.removeItem(LLAVE);
  if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENTO));
}
/** Actualiza los datos del usuario (nombre, foto) y, si se da, el token; avisa al menú lateral. */
export function actualizarSesion(cambios: { usuario?: Usuario; token?: string }) {
  const s = leerSesion();
  if (!s) return;
  guardarSesion({ ...s, ...(cambios.token ? { token: cambios.token } : {}), usuario: { ...s.usuario, ...(cambios.usuario || {}) } });
}
export function alCambiarSesion(fn: () => void): () => void {
  window.addEventListener(EVENTO, fn);
  return () => window.removeEventListener(EVENTO, fn);
}

export class ErrorApi extends Error {
  constructor(public estado: number, mensaje: string, public detalle?: any) {
    super(mensaje);
  }
}

function mensajeDe(detalle: any, estado: number): string {
  if (typeof detalle === "string") return detalle;
  if (detalle?.mensaje) return detalle.mensaje;
  if (Array.isArray(detalle)) return detalle.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  return `Error ${estado}`;
}

async function pedir(ruta: string, init: RequestInit = {}): Promise<Response> {
  const s = leerSesion();
  if (!s && !ruta.startsWith("/auth/")) {
    if (typeof window !== "undefined" && window.location.pathname !== "/login") window.location.href = "/login";
    throw new ErrorApi(401, "Inicie sesión para continuar.");
  }
  const headers = new Headers(init.headers);
  if (s) headers.set("Authorization", `Bearer ${s.token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const r = await fetch(`/api${ruta}`, { ...init, headers, cache: "no-store" });
  if (r.status === 401 && !ruta.startsWith("/auth/login")) {
    guardarSesion(null);
    if (typeof window !== "undefined" && window.location.pathname !== "/login") window.location.href = "/login";
  }
  if (!r.ok) {
    let detalle: any = null;
    try {
      detalle = (await r.json()).detail;
    } catch {}
    throw new ErrorApi(r.status, mensajeDe(detalle, r.status), detalle);
  }
  return r;
}

export const api = {
  get: async <T = any>(ruta: string): Promise<T> => (await pedir(ruta)).json(),
  post: async <T = any>(ruta: string, cuerpo?: unknown): Promise<T> =>
    (await pedir(ruta, { method: "POST", body: JSON.stringify(cuerpo ?? {}) })).json(),
  patch: async <T = any>(ruta: string, cuerpo: unknown): Promise<T> =>
    (await pedir(ruta, { method: "PATCH", body: JSON.stringify(cuerpo) })).json(),
  borrar: async <T = any>(ruta: string): Promise<T> => (await pedir(ruta, { method: "DELETE" })).json(),
  subir: async <T = any>(ruta: string, datos: FormData): Promise<T> => (await pedir(ruta, { method: "POST", body: datos })).json(),
  blob: async (ruta: string): Promise<{ blob: Blob; nombre: string | null }> => {
    const r = await pedir(ruta);
    const cd = r.headers.get("Content-Disposition") || "";
    return { blob: await r.blob(), nombre: /filename="([^"]+)"/.exec(cd)?.[1] ?? null };
  },
  descargar: async (ruta: string, respaldo: string) => {
    const { blob, nombre } = await api.blob(ruta);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = nombre || respaldo;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  },
};

/** Importes: llegan como texto decimal exacto; aquí solo se les da formato (sin aritmética). */
export function mxn(v: string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const neg = v.startsWith("-");
  const [ent, dec = "00"] = v.replace("-", "").split(".");
  return `${neg ? "-" : ""}$${ent.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${dec.padEnd(2, "0")}`;
}

export function fecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

export function fechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  const f = new Date(iso);
  return f.toLocaleString("es-MX", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export const ESTADOS: Record<string, { texto: string; clase: string }> = {
  nuevo: { texto: "Nuevo", clase: "bg-slate-100 text-slate-700" },
  procesando: { texto: "Procesando", clase: "bg-blue-100 text-blue-800" },
  pendiente_revision: { texto: "Pendiente de revisión", clase: "bg-amber-100 text-amber-800" },
  validado: { texto: "Validado", clase: "bg-emerald-100 text-emerald-800" },
  error: { texto: "Error", clase: "bg-red-100 text-red-800" },
  borrador: { texto: "Borrador", clase: "bg-amber-100 text-amber-800" },
  activo: { texto: "Activo", clase: "bg-emerald-100 text-emerald-800" },
  archivado: { texto: "Archivado", clase: "bg-slate-100 text-slate-600" },
  pendiente: { texto: "Pendiente", clase: "bg-amber-100 text-amber-800" },
  procesado: { texto: "Procesado", clase: "bg-emerald-100 text-emerald-800" },
  con_prestaciones: { texto: "Con prestaciones", clase: "bg-emerald-100 text-emerald-800" },
  cero: { texto: "$0.00 autorizado", clase: "bg-slate-200 text-slate-700" },
  faltante: { texto: "Faltante", clase: "bg-red-100 text-red-800" },
};
