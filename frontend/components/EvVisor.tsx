"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Aviso, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const DPI = 130;
const LIMITE_MS = 45_000;  // nunca más de esto mostrando «Cargando…»
const AVISO_LENTO_MS = 6_000;

type Estado = { tipo: "cargando"; lento: boolean } | { tipo: "listo"; url: string; anchoPt: number; altoPt: number } | { tipo: "error"; mensaje: string };

/** Muestra la página de origen y resalta la zona del dato. Distingue el original (la imagen de la página,
 *  generada a partir del archivo que no se modifica) del texto que Nomira leyó (texto del PDF u OCR).
 *  Antes, si la imagen tardaba o fallaba, la vista se quedaba en «Cargando…» para siempre: ahora hay
 *  límite de tiempo, mensaje claro y «Reintentar». */
export default function EvVisor({ documento, pagina = 1, bbox, fragmento, titulo, onCerrar }: {
  documento: { id: number; nombre: string; paginas: number | null; estado?: string };
  pagina?: number | null; bbox?: number[] | null; fragmento?: string | null; titulo?: string; onCerrar: () => void;
}) {
  const [n, setN] = useState(pagina || 1);
  const [vista, setVista] = useState<"original" | "texto">("original");
  const [estado, setEstado] = useState<Estado>({ tipo: "cargando", lento: false });
  const [intento, setIntento] = useState(0);
  const [texto, setTexto] = useState<any>(null);
  const [total, setTotal] = useState(documento.paginas || 1);
  const contenedor = useRef<HTMLDivElement>(null);
  const reintentar = useCallback(() => setIntento((x) => x + 1), []);

  useEffect(() => {
    let vigente = true, url = "";
    const ctrl = new AbortController();
    setEstado({ tipo: "cargando", lento: false });
    const lento = setTimeout(() => vigente && setEstado((e) => (e.tipo === "cargando" ? { tipo: "cargando", lento: true } : e)), AVISO_LENTO_MS);
    const limite = setTimeout(() => ctrl.abort(), LIMITE_MS);
    api.blob(`/evidencia/documentos/${documento.id}/paginas/${n}/imagen?dpi=${DPI}`, { signal: ctrl.signal })
      .then(({ blob, encabezados }) => {
        if (!vigente) return;
        const p = Number(encabezados?.get("X-Paginas"));
        if (p > 0) setTotal(p);
        url = URL.createObjectURL(blob);
        const i = new Image();
        i.onload = () => vigente && setEstado({ tipo: "listo", url, anchoPt: (i.naturalWidth * 72) / DPI, altoPt: (i.naturalHeight * 72) / DPI });
        i.onerror = () => vigente && setEstado({ tipo: "error", mensaje: "La página llegó, pero el navegador no pudo mostrarla. Descargue el original." });
        i.src = url;
      })
      .catch((e: any) => {
        if (!vigente) return;
        setEstado({ tipo: "error", mensaje: e?.name === "AbortError"
          ? "El servidor tardó demasiado en preparar la página (puede estar despertando o leyendo documentos). Intente de nuevo en un momento."
          : e?.message || "No se pudo mostrar la página." });
      })
      .finally(() => { clearTimeout(lento); clearTimeout(limite); });
    return () => { vigente = false; ctrl.abort(); clearTimeout(lento); clearTimeout(limite); if (url) URL.revokeObjectURL(url); };
  }, [documento.id, n, intento]);

  useEffect(() => {
    if (vista !== "texto") return;
    setTexto(null);
    api.get(`/evidencia/documentos/${documento.id}/paginas/${n}/texto`).then(setTexto).catch((e) => setTexto({ error: e.message }));
  }, [vista, documento.id, n]);

  const resaltar = estado.tipo === "listo" && bbox && n === (pagina || 1);
  useEffect(() => {  // lleva la vista a la zona resaltada
    if (resaltar && contenedor.current) {
      const el = contenedor.current.querySelector("[data-resaltado]") as HTMLElement | null;
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [resaltar]);

  return (
    <Modal titulo={titulo || `${documento.nombre} — página ${n}`} onCerrar={onCerrar} ancho="max-w-5xl">
      <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
        <div>
          <div className="mb-2 flex gap-1" role="tablist" aria-label="Qué mostrar">
            {([["original", "Página original"], ["texto", "Texto leído por Nomira"]] as const).map(([k, t]) => (
              <button key={k} role="tab" aria-selected={vista === k} onClick={() => setVista(k)}
                className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${vista === k ? "bg-marino text-white" : "text-slate-600 hover:bg-crema"}`}>{t}</button>))}
          </div>
          <div ref={contenedor} className="max-h-[70vh] overflow-auto rounded-xl border border-crema-300 bg-slate-100">
            {vista === "original" ? (
              estado.tipo === "listo" ? (
                <div className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={estado.url} alt={`Página ${n} de ${documento.nombre}`} className="block w-full" />
                  {resaltar && (
                    <span data-resaltado className="pointer-events-none absolute rounded-sm border-2 border-turquesa bg-turquesa/20" aria-hidden
                      style={{ left: `${((bbox![0] - 3) / estado.anchoPt) * 100}%`, top: `${((bbox![1] - 3) / estado.altoPt) * 100}%`,
                        width: `${((bbox![2] - bbox![0] + 6) / estado.anchoPt) * 100}%`, height: `${((bbox![3] - bbox![1] + 6) / estado.altoPt) * 100}%` }} />
                  )}
                </div>
              ) : estado.tipo === "error" ? (
                <div className="space-y-3 p-6">
                  <Aviso>{estado.mensaje}</Aviso>
                  <button className="btn-primario" onClick={reintentar}>Reintentar</button>
                </div>
              ) : (
                <div className="p-6 text-sm text-slate-600" role="status" aria-live="polite">
                  <div className="mb-2 h-1.5 w-40 overflow-hidden rounded-full bg-crema-300"><div className="h-full w-1/2 animate-pulse rounded-full bg-turquesa" /></div>
                  Preparando la página {n}…
                  {estado.lento && <p className="mt-1 text-xs text-slate-500">Está tardando más de lo normal: el servidor puede estar despertando o leyendo documentos. Si no aparece, verá un mensaje y podrá reintentar.</p>}
                </div>
              )
            ) : (
              <div className="bg-white p-4 text-sm">
                {!texto ? <p className="text-slate-500">Cargando texto…</p> : texto.error ? <Aviso>{texto.error}</Aviso> : texto.texto == null ? (
                  <p className="text-slate-500">{texto.aviso}</p>
                ) : (
                  <>
                    <p className="mb-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">Esto es una <b>lectura</b> del documento, no el original. {texto.legibilidad}</p>
                    <Resaltado texto={texto.texto} fragmento={n === (pagina || 1) ? fragmento : null} />
                  </>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <button className="btn-sec" disabled={n <= 1} onClick={() => setN(n - 1)}>← Anterior</button>
            <span className="text-slate-600">Página {n} de {total}</span>
            <button className="btn-sec" disabled={n >= total} onClick={() => setN(n + 1)}>Siguiente →</button>
          </div>
          {pagina && n !== pagina && <button className="w-full text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => setN(pagina)}>Volver a la página citada ({pagina})</button>}
          {fragmento && (
            <div className="rounded-xl border border-turquesa bg-turquesa-50 p-3">
              <div className="etiqueta">Cita de origen{pagina ? ` (página ${pagina})` : ""}</div>
              <p className="whitespace-pre-wrap text-slate-800">«{fragmento}»</p>
            </div>
          )}
          {!bbox && fragmento && <p className="text-xs text-slate-500">No se conoce la zona exacta: se muestra la página citada. En «Texto leído» la cita aparece resaltada.</p>}
          <button className="btn-sec w-full" onClick={() => api.descargar(`/evidencia/documentos/${documento.id}/archivo`, documento.nombre).catch((e) => setEstado({ tipo: "error", mensaje: e.message }))}>
            Descargar el original</button>
          <p className="text-xs text-slate-500">El archivo original se conserva sin cambios. La vista de página es una imagen generada para revisarlo aquí.</p>
          {documento.estado === "recibido" && <Aviso tipo="alerta">Enviado por el cliente y aún no aceptado. Nomira no tiene antivirus: revise el archivo antes de abrirlo fuera de Nomira.</Aviso>}
        </div>
      </div>
    </Modal>
  );
}

function Resaltado({ texto, fragmento }: { texto: string; fragmento?: string | null }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => { ref.current?.scrollIntoView({ block: "center" }); }, [fragmento]);
  if (!fragmento) return <p className="whitespace-pre-wrap text-slate-800">{texto}</p>;
  // Coincidencia tolerante a espacios y saltos de línea
  const patron = fragmento.trim().split(/\s+/).slice(0, 40).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
  const m = new RegExp(patron).exec(texto);
  if (!m) return <p className="whitespace-pre-wrap text-slate-800">{texto}</p>;
  return (
    <p className="whitespace-pre-wrap text-slate-800">
      {texto.slice(0, m.index)}<mark ref={ref} className="rounded bg-turquesa/30 px-0.5">{m[0]}</mark>{texto.slice(m.index + m[0].length)}
    </p>
  );
}
