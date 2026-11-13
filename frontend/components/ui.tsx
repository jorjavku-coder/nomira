"use client";
import { useState } from "react";
import { ESTADOS } from "@/lib/api";

export function Chip({ estado, texto }: { estado: string; texto?: string }) {
  const e = ESTADOS[estado] || { texto: estado, clase: "bg-slate-100 text-slate-700" };
  return <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${e.clase}`}><span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" aria-hidden />{texto || e.texto}</span>;
}

export function Aviso({ tipo = "error", children }: { tipo?: "error" | "ok" | "info" | "alerta"; children: React.ReactNode }) {
  if (!children) return null;
  const clase = {
    error: "border-red-200 bg-red-50 text-red-800",
    ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-marino-100 bg-marino-50 text-marino",
    alerta: "border-amber-200 bg-amber-50 text-amber-900",
  }[tipo];
  return <div role={tipo === "error" ? "alert" : "status"} className={`rounded-xl border px-3.5 py-2.5 text-sm ${clase}`}>{children}</div>;
}

export function Modal({ titulo, onCerrar, children, ancho = "max-w-lg" }: { titulo: string; onCerrar: () => void; children: React.ReactNode; ancho?: string }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-marino-900/55 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={titulo}>
      <div className={`tarjeta mt-8 w-full shadow-flotante ${ancho}`}>
        <div className="flex items-center justify-between border-b border-crema-300 px-5 py-3.5">
          <h2 className="font-semibold text-marino">{titulo}</h2>
          <button onClick={onCerrar} className="btn-sec" aria-label="Cerrar">Cerrar</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

/** Foto de perfil o, si no hay, las iniciales sobre un círculo de color estable por nombre. */
export function Avatar({ nombre, foto, tam = 36, oscuro = false }: { nombre: string; foto?: string | null; tam?: number; oscuro?: boolean }) {
  const iniciales = nombre.split(/\s+/).filter(Boolean).map((p) => p[0]).slice(0, 2).join("").toUpperCase() || "?";
  const tonos = ["bg-turquesa-50 text-turquesa-700", "bg-marino-50 text-marino", "bg-amber-50 text-amber-800", "bg-emerald-50 text-emerald-800", "bg-rose-50 text-rose-700"];
  const tono = oscuro ? "bg-turquesa-brillante/15 text-turquesa-brillante" : tonos[[...nombre].reduce((a, c) => a + c.charCodeAt(0), 0) % tonos.length];
  const estilo = { width: tam, height: tam, fontSize: Math.max(10, tam * 0.36) };
  // eslint-disable-next-line @next/next/no-img-element
  if (foto) return <img src={foto} alt={`Foto de ${nombre}`} style={estilo} className="shrink-0 rounded-full object-cover ring-2 ring-white/70" />;
  return <span style={estilo} className={`flex shrink-0 items-center justify-center rounded-full font-bold ${tono}`} aria-hidden>{iniciales}</span>;
}

/** Campo de contraseña con botón para mostrarla. */
export function CampoContrasena({ etiqueta, valor, onCambio, nueva = false, autoFocus = false }: {
  etiqueta: string; valor: string; onCambio: (v: string) => void; nueva?: boolean; autoFocus?: boolean;
}) {
  const [ver, setVer] = useState(false);
  return (
    <label className="block"><span className="etiqueta">{etiqueta}</span>
      <div className="relative">
        <input className="campo pr-20" type={ver ? "text" : "password"} required minLength={nueva ? 10 : 1} autoFocus={autoFocus}
          autoComplete={nueva ? "new-password" : "current-password"} value={valor} onChange={(e) => onCambio(e.target.value)} />
        <button type="button" onClick={() => setVer(!ver)} className="absolute inset-y-0 right-2 my-auto h-7 rounded-lg px-2 text-xs font-semibold text-turquesa-700 hover:bg-turquesa-50">
          {ver ? "Ocultar" : "Mostrar"}</button>
      </div>
    </label>
  );
}

/** Indicador sencillo: largo mínimo, coincidencia con la confirmación. */
export function ReglasContrasena({ nueva, confirmar }: { nueva: string; confirmar: string }) {
  const reglas = [
    { ok: nueva.length >= 10, t: "Al menos 10 caracteres" },
    { ok: /[a-zA-Z]/.test(nueva) && /\d/.test(nueva), t: "Letras y números (recomendado)" },
    { ok: !!nueva && nueva === confirmar, t: "Las dos contraseñas coinciden" },
  ];
  return (
    <ul className="space-y-1 text-xs">
      {reglas.map((r) => (
        <li key={r.t} className={`flex items-center gap-1.5 ${r.ok ? "text-emerald-700" : "text-slate-500"}`}>
          <span aria-hidden>{r.ok ? "✓" : "○"}</span>{r.t}
        </li>
      ))}
    </ul>
  );
}

/** Confirmación para acciones que no se pueden deshacer. */
export function ConfirmarEliminar({ titulo, children, boton = "Eliminar", onConfirmar, onCerrar }: {
  titulo: string; children: React.ReactNode; boton?: string; onConfirmar: () => Promise<any>; onCerrar: () => void;
}) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  async function confirmar() {
    setEnviando(true); setError("");
    try { await onConfirmar(); onCerrar(); } catch (e: any) { setError(e.message); setEnviando(false); }
  }
  return (
    <Modal titulo={titulo} onCerrar={onCerrar}>
      <div className="space-y-4">
        <div className="flex gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-50 text-lg text-red-600" aria-hidden>!</span>
          <div className="text-sm text-slate-700">{children}</div>
        </div>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2">
          <button className="btn-sec" onClick={onCerrar} disabled={enviando}>Cancelar</button>
          <button className="btn bg-red-600 text-white hover:bg-red-700 disabled:opacity-60" onClick={confirmar} disabled={enviando}>{enviando ? "Eliminando…" : boton}</button>
        </div>
      </div>
    </Modal>
  );
}
