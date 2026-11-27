"use client";
import { useEffect, useState } from "react";

/** Registra el service worker (solo en producción) para que Nomira se pueda instalar como app. */
export function RegistrarApp() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }, []);
  return null;
}

type Plataforma = "instalada" | "android" | "ios" | "ios_otro" | "escritorio" | null;

function detectar(): Plataforma {
  if (typeof window === "undefined") return null;
  if (window.matchMedia("(display-mode: standalone)").matches || (navigator as any).standalone) return "instalada";
  const ua = navigator.userAgent;
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  if (ios) return /CriOS|FxiOS|EdgiOS/.test(ua) ? "ios_otro" : "ios";
  return /Android/.test(ua) ? "android" : "escritorio";
}

/** Botón «Instalar la app»: en Android/Chrome abre el instalador del sistema; en iPhone explica los 2 pasos. */
export function BotonInstalar({ className = "", texto = "Instalar la app de Nomira", oscuro = false }: { className?: string; texto?: string; oscuro?: boolean }) {
  const [evento, setEvento] = useState<any>(null);
  const [plat, setPlat] = useState<Plataforma>(null);
  const [ayuda, setAyuda] = useState(false);
  const [listo, setListo] = useState(false);
  useEffect(() => {
    setPlat(detectar());
    const f = (e: Event) => { e.preventDefault(); setEvento(e); };
    const g = () => setListo(true);
    window.addEventListener("beforeinstallprompt", f);
    window.addEventListener("appinstalled", g);
    return () => { window.removeEventListener("beforeinstallprompt", f); window.removeEventListener("appinstalled", g); };
  }, []);
  if (!plat || plat === "instalada" || listo) return listo ? <p className={`text-sm font-semibold ${oscuro ? "text-emerald-300" : "text-emerald-700"}`}>✓ Nomira quedó instalada</p> : null;
  const instalar = async () => {
    if (evento) { evento.prompt(); const r = await evento.userChoice; if (r?.outcome === "accepted") setListo(true); setEvento(null); return; }
    setAyuda(true);
  };
  return (
    <>
      <button type="button" onClick={instalar} className={className}>{texto}</button>
      {ayuda && <div className="fixed inset-0 z-[60] flex items-end justify-center bg-marino-900/60 p-4 backdrop-blur-sm sm:items-center" role="dialog" aria-modal="true" aria-label="Cómo instalar Nomira" onClick={() => setAyuda(false)}>
        <div className="w-full max-w-sm rounded-3xl bg-white p-6 text-marino shadow-2xl" onClick={(e) => e.stopPropagation()}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/app/icono-192.png" alt="" className="h-14 w-14 rounded-2xl" />
          <p className="mt-3 text-lg font-bold">Instale Nomira en su {plat === "escritorio" ? "computadora" : "celular"}</p>
          {plat === "ios" ? <ol className="mt-3 space-y-2 text-sm text-slate-700">
              <li><b>1.</b> Toque el botón <b>Compartir</b> <span aria-hidden>⬆️</span> abajo en Safari.</li>
              <li><b>2.</b> Elija <b>«Agregar a pantalla de inicio»</b> y luego <b>Agregar</b>.</li>
              <li><b>3.</b> Abra Nomira desde su nuevo ícono.</li></ol>
            : plat === "ios_otro" ? <p className="mt-3 text-sm text-slate-700">En iPhone la app se instala desde <b>Safari</b>. Abra <b>nomirasoft.com</b> en Safari y toque <b>Compartir → «Agregar a pantalla de inicio»</b>.</p>
            : plat === "android" ? <ol className="mt-3 space-y-2 text-sm text-slate-700">
              <li><b>1.</b> Toque el menú <b>⋮</b> arriba a la derecha de Chrome.</li>
              <li><b>2.</b> Elija <b>«Instalar app»</b> o <b>«Agregar a la pantalla principal»</b>.</li></ol>
            : <ol className="mt-3 space-y-2 text-sm text-slate-700">
              <li><b>1.</b> En Chrome o Edge, busque el ícono de <b>instalar</b> <span aria-hidden>⊕</span> a la derecha de la barra de direcciones.</li>
              <li><b>2.</b> Haga clic en <b>Instalar</b>. También puede abrir nomirasoft.com en su celular.</li></ol>}
          <button className="btn-turquesa mt-5 w-full" onClick={() => setAyuda(false)}>Entendido</button>
        </div></div>}
    </>
  );
}
