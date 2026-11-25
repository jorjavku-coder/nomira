"use client";
import { useEffect, useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

export function EtiquetaTipo({ tipo }: { tipo?: string | null }) {
  if (!tipo) return null;
  return tipo === "jurisprudencia"
    ? <span className="rounded-full bg-marino px-2 py-0.5 text-[11px] font-semibold text-white">Jurisprudencia</span>
    : <span className="rounded-full bg-crema-300 px-2 py-0.5 text-[11px] font-semibold text-marino">Tesis aislada</span>;
}

export function cita(t: any) {
  return `«${t.rubro}» ${[t.instancia, t.epoca, t.clave && `Tesis: ${t.clave}`].filter(Boolean).join(", ")}. Registro digital: ${t.registro}.`;
}

export function TarjetaTesis({ t, onLeer, verificada = false }: { t: any; onLeer: () => void; verificada?: boolean }) {
  const [ok, setOk] = useState("");
  return (
    <li className="rounded-xl border border-crema-300 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <EtiquetaTipo tipo={t.tipo} /><span>Registro digital {t.registro}</span>{t.clave && <span>· {t.clave}</span>}
        {verificada && <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-800">✓ Verificada en la biblioteca</span>}
      </div>
      <button className="mt-1 text-left font-semibold text-marino hover:underline" onClick={onLeer}>{t.rubro}</button>
      <p className="text-xs text-slate-500">{[t.instancia, t.epoca, t.materias, t.anio && `Publicada en ${t.anio}`].filter(Boolean).join(" · ")}</p>
      {t.extracto && <p className="mt-1 line-clamp-2 text-sm text-slate-600">{t.extracto}</p>}
      <div className="mt-2 flex flex-wrap gap-3 text-xs font-semibold">
        <button className="text-turquesa-700 underline" onClick={onLeer}>Leer completa</button>
        <a className="text-turquesa-700 underline" href={t.enlace} target="_blank" rel="noopener noreferrer">Ver en el Semanario (oficial)</a>
        <button className="text-turquesa-700 underline" onClick={() => api.descargar(`/tesis/${t.registro}/pdf`, `tesis-${t.registro}.pdf`)}>Ficha PDF</button>
        <button className="text-slate-600 underline" onClick={async () => { try { await navigator.clipboard.writeText(cita(t)); setOk("Cita copiada"); } catch { setOk(""); } }}>Copiar cita</button>
        {ok && <span className="text-emerald-700" role="status">{ok}</span>}
      </div>
    </li>
  );
}

export function LeerTesis({ registro, onCerrar }: { registro: number; onCerrar: () => void }) {
  const [t, setT] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get(`/tesis/${registro}`).then(setT).catch((e) => setError(e.message)); }, [registro]);
  return (
    <Modal titulo={`Registro digital ${registro}`} onCerrar={onCerrar} ancho="max-w-3xl">
      <Aviso>{error}</Aviso>
      {t && <article className="space-y-3 text-sm">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500"><EtiquetaTipo tipo={t.tipo} />
          {[t.instancia, t.epoca, t.materias && `Materia(s): ${t.materias}`, t.clave && `Tesis: ${t.clave}`].filter(Boolean).join(" · ")}</div>
        <h2 className="text-base font-bold text-marino">{t.rubro}</h2>
        <div className="whitespace-pre-wrap leading-relaxed text-slate-800">{t.texto}</div>
        {t.precedentes && <div className="whitespace-pre-wrap text-xs text-slate-600">{t.precedentes}</div>}
        {t.publicada && <p className="text-xs text-slate-500">{t.publicada}</p>}
        <div className="flex flex-wrap gap-2 border-t border-crema-300 pt-3">
          <a className="btn-turquesa" href={t.enlace} target="_blank" rel="noopener noreferrer">Ver en el Semanario Judicial de la Federación</a>
          <button className="btn-sec" onClick={() => api.descargar(`/tesis/${t.registro}/pdf`, `tesis-${t.registro}.pdf`)}>Descargar ficha PDF</button>
        </div>
        <p className="text-xs text-slate-500">Texto copiado de {t.origen === "repositorio" ? "el Repositorio de datos abiertos de la SCJN" : "una publicación oficial de la SCJN"}.
          {t.huella_oficial ? ` Huella SHA-256 oficial: ${t.huella_oficial}.` : ""} Antes de citarla, confirme su vigencia en el Semanario.</p>
      </article>}
    </Modal>
  );
}
