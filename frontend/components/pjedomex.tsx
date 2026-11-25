"use client";
import { useEffect, useState } from "react";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

/** Accesos a los sistemas del Poder Judicial del Estado de México y su calendario oficial.
 *  Los sistemas se abren en la página oficial con la cuenta del abogado: Nomira no guarda contraseñas. */

type Acceso = { clave: string; nombre: string; url: string; para: string; cuenta: string };
type Info = { accesos: Acceso[]; calendario: any | null; es_predeterminado: boolean };

let cache: Info | null = null;
function useInfo(): [Info | null, (x: Info) => void] {
  const [info, setInfo] = useState<Info | null>(cache);
  useEffect(() => { api.get("/agenda/pjedomex").then((x: Info) => { cache = x; setInfo(x); }).catch(() => {}); }, []);
  return [info, (x) => { cache = x; setInfo(x); }];
}

function Copiar({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button type="button" className="flex w-full items-center justify-between rounded-lg border border-crema-300 bg-white px-3 py-2 text-left text-sm hover:bg-crema/40"
      onClick={async () => { try { await navigator.clipboard.writeText(valor); setOk(true); setTimeout(() => setOk(false), 1500); } catch { /* sin permiso */ } }}>
      <span><span className="block text-xs text-slate-500">{etiqueta}</span><b className="font-mono text-marino">{valor}</b></span>
      <span className="text-xs font-semibold text-turquesa-700">{ok ? "¡Copiado!" : "Copiar"}</span>
    </button>
  );
}

/** Tribunales del Edomex que NO son del Poder Judicial (tienen sus propios sistemas). */
const OTRO_TRIBUNAL = /trijaem|justicia administrativa|conciliaci[oó]n y arbitraje|\bteca\b|electoral|centro de conciliaci/i;

/** Tarjeta en la ficha de un asunto del Estado de México ante el Poder Judicial (juzgados civiles, familiares, mercantiles, penales). */
export function AccesosPjedomex({ asunto }: { asunto: any }) {
  const [info] = useInfo();
  if (asunto.entidad !== "Estado de México" || asunto.jurisdiccion !== "estatal" || OTRO_TRIBUNAL.test(asunto.tribunal || "") || !info) return null;
  const [num, anio] = (asunto.numero || "").split("/").map((x: string) => x.trim());
  const principales = info.accesos.filter((a) => ["tribunal", "acuerdos", "boletin", "correo"].includes(a.clave));
  return (
    <section className="tarjeta p-4 text-sm">
      <h2 className="font-semibold text-marino">Poder Judicial del Estado de México</h2>
      <p className="mt-1 text-xs text-slate-500">Se abre la página oficial en otra pestaña y usted entra con su cuenta. Nomira no guarda sus contraseñas: su navegador puede recordarlas.</p>
      {(asunto.tribunal || num) && <div className="mt-3 space-y-2">
        <p className="etiqueta">Datos para la búsqueda</p>
        {asunto.tribunal && <Copiar etiqueta="Juzgado" valor={asunto.tribunal} />}
        {num && <Copiar etiqueta="Número de expediente" valor={num} />}
        {anio && <Copiar etiqueta="Año" valor={anio} />}
      </div>}
      <div className="mt-3 grid gap-2">{principales.map((a) => (
        <a key={a.clave} href={a.url} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-crema-300 px-3 py-2 hover:border-turquesa hover:bg-turquesa-50">
          <span className="flex items-center justify-between"><b className="text-marino">{a.nombre}</b><span aria-hidden className="text-turquesa-700">↗</span></span>
          <span className="block text-xs text-slate-500">{a.para} · {a.cuenta}</span></a>))}</div>
      <a href="#actuaciones" className="btn-turquesa mt-3 block text-center">Registrar lo que vi</a>
      <p className="mt-2 text-xs text-slate-500">Anote el acuerdo o la fecha de audiencia: queda en el historial del asunto y Nomira le recuerda los plazos.</p>
      {!info.calendario && <p className="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">Para que los plazos respeten los días inhábiles oficiales, conecte el calendario del PJEdomex en <a className="font-semibold underline" href="/agenda/calendarios">Días hábiles</a>.</p>}
    </section>
  );
}

/** Tarjeta en «Días hábiles» para conectar el calendario oficial. */
export function CalendarioPjedomex({ puede, onListo }: { puede: boolean; onListo: (calId: number) => void }) {
  const [info, setInfo] = useInfo();
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  if (!info) return null;
  const c = info.calendario;
  const conectar = async (predeterminado: boolean) => {
    setCargando(true); setError("");
    try {
      const x = await api.post("/agenda/pjedomex/calendario", { predeterminado });
      setInfo(x);
      if (x.resultado?.error) setError(x.resultado.error);
      if (x.calendario) onListo(x.calendario.id);
    } catch (e: any) { setError(e.message); } finally { setCargando(false); }
  };
  return (
    <section className="tarjeta mb-5 flex flex-wrap items-center justify-between gap-3 border-l-4 border-turquesa p-4 text-sm">
      <div className="max-w-3xl">
        <h2 className="font-semibold text-marino">Calendario oficial del Poder Judicial del Estado de México</h2>
        {c ? <p className="text-slate-600">Conectado · {c.dias_capturados} días inhábiles · se actualiza solo una vez al día
            {c.sincronizado_en && <> (última revisión: {new Date(c.sincronizado_en).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" })})</>}
            {info.es_predeterminado && " · es el calendario predeterminado del despacho"}</p>
          : <p className="text-slate-600">Nomira trae del sitio oficial los días inhábiles y los periodos vacacionales, y los mantiene al día. Los días que usted capture a mano no se tocan.</p>}
        {c?.sincronizacion_error && <p className="mt-1 text-xs text-amber-700">Último aviso: {c.sincronizacion_error}</p>}
        <Aviso>{error}</Aviso>
      </div>
      {puede && <div className="flex flex-wrap gap-2">
        {!info.es_predeterminado && <button className="btn-sec" disabled={cargando} onClick={() => conectar(true)}>{c ? "Usar como predeterminado" : "Conectar y usar como predeterminado"}</button>}
        <button className="btn-turquesa" disabled={cargando} onClick={() => conectar(false)}>{cargando ? "Consultando…" : c ? "Actualizar ahora" : "Conectar"}</button>
      </div>}
    </section>
  );
}
