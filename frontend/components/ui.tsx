"use client";
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
