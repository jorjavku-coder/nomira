"use client";
import { ESTADOS } from "@/lib/api";

export function Chip({ estado, texto }: { estado: string; texto?: string }) {
  const e = ESTADOS[estado] || { texto: estado, clase: "bg-slate-100 text-slate-700" };
  return <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${e.clase}`}>{texto || e.texto}</span>;
}

export function Aviso({ tipo = "error", children }: { tipo?: "error" | "ok" | "info" | "alerta"; children: React.ReactNode }) {
  if (!children) return null;
  const clase = {
    error: "border-red-200 bg-red-50 text-red-800",
    ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-marino-100 bg-marino-50 text-marino",
    alerta: "border-amber-200 bg-amber-50 text-amber-900",
  }[tipo];
  return <div role={tipo === "error" ? "alert" : "status"} className={`rounded-md border px-3 py-2 text-sm ${clase}`}>{children}</div>;
}

export function Modal({ titulo, onCerrar, children, ancho = "max-w-lg" }: { titulo: string; onCerrar: () => void; children: React.ReactNode; ancho?: string }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4" role="dialog" aria-modal="true" aria-label={titulo}>
      <div className={`tarjeta mt-8 w-full ${ancho}`}>
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <h2 className="font-semibold text-marino">{titulo}</h2>
          <button onClick={onCerrar} className="btn-sec" aria-label="Cerrar">Cerrar</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
