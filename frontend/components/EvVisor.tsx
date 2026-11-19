"use client";
import { useEffect, useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const DPI = 130;

/** Muestra el documento original en la página de origen y resalta la zona del hecho, si se conoce. */
export default function EvVisor({ documento, pagina = 1, bbox, fragmento, titulo, onCerrar }: {
  documento: { id: number; nombre: string; paginas: number | null };
  pagina?: number | null; bbox?: number[] | null; fragmento?: string | null; titulo?: string; onCerrar: () => void;
}) {
  const [n, setN] = useState(pagina || 1);
  const [img, setImg] = useState<{ url: string; anchoPt: number; altoPt: number } | null>(null);
  const [error, setError] = useState("");
  const total = documento.paginas || 1;
  useEffect(() => {
    let url = "";
    setImg(null); setError("");
    api.blob(`/evidencia/documentos/${documento.id}/paginas/${n}/imagen?dpi=${DPI}`).then(({ blob }) => {
      url = URL.createObjectURL(blob);
      const i = new Image();
      i.onload = () => setImg({ url, anchoPt: (i.naturalWidth * 72) / DPI, altoPt: (i.naturalHeight * 72) / DPI });
      i.src = url;
    }).catch((e) => setError(e.message));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [documento.id, n]);
  const resaltar = bbox && n === (pagina || 1);
  return (
    <Modal titulo={titulo || `${documento.nombre} — página ${n}`} onCerrar={onCerrar} ancho="max-w-5xl">
      <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
        <div className="max-h-[75vh] overflow-auto rounded-xl border border-crema-300 bg-slate-100">
          <Aviso>{error}</Aviso>
          {img ? (
            <div className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img.url} alt={`Página ${n} de ${documento.nombre}`} className="block w-full" />
              {resaltar && (
                <span className="pointer-events-none absolute rounded-sm border-2 border-turquesa bg-turquesa/20" aria-hidden
                  style={{ left: `${((bbox![0] - 3) / img.anchoPt) * 100}%`, top: `${((bbox![1] - 3) / img.altoPt) * 100}%`,
                    width: `${((bbox![2] - bbox![0] + 6) / img.anchoPt) * 100}%`, height: `${((bbox![3] - bbox![1] + 6) / img.altoPt) * 100}%` }} />
              )}
            </div>
          ) : !error && <p className="p-6 text-sm text-slate-500">Cargando página…</p>}
        </div>
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <button className="btn-sec" disabled={n <= 1} onClick={() => setN(n - 1)}>← Anterior</button>
            <span className="text-slate-600">Página {n} de {total}</span>
            <button className="btn-sec" disabled={n >= total} onClick={() => setN(n + 1)}>Siguiente →</button>
          </div>
          {fragmento && (
            <div className="rounded-xl border border-turquesa bg-turquesa-50 p-3">
              <div className="etiqueta">Texto de origen{pagina ? ` (página ${pagina})` : ""}</div>
              <p className="whitespace-pre-wrap text-slate-800">{fragmento}</p>
            </div>
          )}
          {!bbox && fragmento && <p className="text-xs text-slate-500">La zona exacta no está disponible para este hecho; se muestra la página indicada.</p>}
          <button className="btn-sec w-full" onClick={() => api.descargar(`/evidencia/documentos/${documento.id}/archivo`, documento.nombre).catch((e) => setError(e.message))}>
            Descargar el original</button>
        </div>
      </div>
    </Modal>
  );
}
