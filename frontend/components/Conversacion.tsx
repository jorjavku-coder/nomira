"use client";
import { useEffect, useRef, useState } from "react";
import { Aviso, Chip } from "@/components/ui";
import { fechaHora } from "@/lib/api";

/** Hilo de soporte. `lado` = quién está mirando: sus mensajes van a la derecha. */
export default function Conversacion({ t, lado, onEnviar, onEstado }: {
  t: any; lado: "cliente" | "plataforma"; onEnviar: (texto: string) => Promise<void>; onEstado?: (estado: "abierto" | "cerrado") => Promise<void>;
}) {
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const fin = useRef<HTMLDivElement>(null);
  useEffect(() => { fin.current?.scrollIntoView({ block: "nearest" }); }, [t.conversacion.length]);
  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!texto.trim()) return;
    setEnviando(true); setError("");
    try { await onEnviar(texto.trim()); setTexto(""); } catch (err: any) { setError(err.message); }
    setEnviando(false);
  }
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 px-5 py-3">
        <div className="min-w-0">
          <h2 className="truncate font-semibold text-marino">{t.asunto}</h2>
          <div className="text-xs text-slate-500">{t.organizacion ? `${t.organizacion} · ` : ""}abierta el {fechaHora(t.creado_en)}</div>
        </div>
        <div className="flex items-center gap-2">
          <Chip estado={t.estado === "abierto" ? "pendiente" : "archivado"} texto={t.estado === "abierto" ? "Abierta" : "Resuelta"} />
          {onEstado && (t.estado === "abierto"
            ? <button className="btn-sec" onClick={() => onEstado("cerrado")}>Marcar resuelta</button>
            : lado === "plataforma" && <button className="btn-sec" onClick={() => onEstado("abierto")}>Reabrir</button>)}
        </div>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto bg-crema/40 px-5 py-4" style={{ maxHeight: "60vh" }}>
        {t.conversacion.map((x: any) => {
          const mio = x.autor_tipo === lado;
          return (
            <div key={x.id} className={`flex ${mio ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm shadow-sm ${mio ? "rounded-br-md bg-marino text-white" : x.autor_tipo === "plataforma" ? "rounded-bl-md bg-amber-50 text-slate-800 ring-1 ring-amber-200" : "rounded-bl-md bg-white text-slate-800 ring-1 ring-crema-300"}`}>
                <div className={`mb-0.5 text-[11px] font-semibold ${mio ? "text-white/70" : "text-slate-500"}`}>{x.autor_nombre} · {fechaHora(x.creado_en)}</div>
                <div className="whitespace-pre-wrap">{x.texto}</div>
              </div>
            </div>
          );
        })}
        <div ref={fin} />
      </div>
      <form onSubmit={enviar} className="border-t border-crema-300 p-4">
        {t.estado === "cerrado" && <p className="mb-2 text-xs text-slate-500">Esta conversación está resuelta; si escribe, se vuelve a abrir.</p>}
        <textarea className="campo h-24" maxLength={5000} placeholder="Escriba su mensaje…" value={texto} onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) enviar(e as any); }} aria-label="Mensaje" />
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-xs text-slate-400">Ctrl + Enter para enviar</span>
          <button className="btn-primario" disabled={enviando || !texto.trim()}>{enviando ? "Enviando…" : "Enviar"}</button>
        </div>
        <div className="mt-2"><Aviso>{error}</Aviso></div>
      </form>
    </div>
  );
}
