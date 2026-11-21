"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AgendaShell, FormEvento, SITUACION, useCatalogosAgenda } from "@/components/agenda";
import { Aviso } from "@/components/ui";
import { api } from "@/lib/api";

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Calendario mensual: pendientes por día y días inhábiles del calendario judicial elegido. */
export default function Calendario() {
  const cat = useCatalogosAgenda();
  const hoy = new Date();
  const [mes, setMes] = useState(new Date(hoy.getFullYear(), hoy.getMonth(), 1));
  const [eventos, setEventos] = useState<any[]>([]);
  const [inhabiles, setInhabiles] = useState<Record<string, string>>({});
  const [semana, setSemana] = useState<number[]>([5, 6]);
  const [cal, setCal] = useState<string>("");
  const [mios, setMios] = useState(false);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState<string | null>(null);
  useEffect(() => { if (cat && !cal && cat.calendario_defecto) setCal(String(cat.calendario_defecto)); }, [cat, cal]);
  const celdas = useMemo(() => {
    const ini = new Date(mes); ini.setDate(1 - ((mes.getDay() + 6) % 7));
    return Array.from({ length: 42 }, (_, i) => { const d = new Date(ini); d.setDate(ini.getDate() + i); return d; });
  }, [mes]);
  const cargar = useCallback(() => {
    api.get(`/agenda/eventos?estado=todos&desde=${iso(celdas[0])}&hasta=${iso(celdas[41])}&solo_mios=${mios}`).then(setEventos).catch((e) => setError(e.message));
  }, [celdas, mios]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    if (!cal) { setInhabiles({}); return; }
    const anios = Array.from(new Set([celdas[0].getFullYear(), celdas[41].getFullYear()]));
    Promise.all(anios.map((a) => api.get(`/agenda/calendarios/${cal}/anio/${a}`))).then((rs) => {
      const m: Record<string, string> = {};
      const habilitados = new Set<string>();
      rs.forEach((r) => r.dias.forEach((d: any) => { if (d.tipo === "inhabil") m[d.fecha] = d.motivo; else habilitados.add(d.fecha); }));
      habilitados.forEach((f) => { m[f] = ""; });
      setInhabiles(m);
      setSemana(rs[0]?.calendario.dias_semana_inhabiles ?? [5, 6]);
    }).catch(() => setInhabiles({}));
  }, [cal, celdas]);
  const porDia = useMemo(() => { const m: Record<string, any[]> = {}; eventos.forEach((e) => (m[e.fecha] ||= []).push(e)); return m; }, [eventos]);
  return (
    <AgendaShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-2">
          <button className="btn-sec px-3" aria-label="Mes anterior" onClick={() => setMes(new Date(mes.getFullYear(), mes.getMonth() - 1, 1))}>‹</button>
          <h1 className="min-w-[13rem] text-center text-2xl font-extrabold text-marino">{MESES[mes.getMonth()]} {mes.getFullYear()}</h1>
          <button className="btn-sec px-3" aria-label="Mes siguiente" onClick={() => setMes(new Date(mes.getFullYear(), mes.getMonth() + 1, 1))}>›</button>
          <button className="btn-sec" onClick={() => setMes(new Date(hoy.getFullYear(), hoy.getMonth(), 1))}>Hoy</button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {cat && <select className="campo w-auto" aria-label="Calendario de días hábiles" value={cal} onChange={(e) => setCal(e.target.value)}>
            <option value="">Sin marcar días inhábiles</option>{cat.calendarios.map((c: any) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select>}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-turquesa" checked={mios} onChange={(e) => setMios(e.target.checked)} />Solo lo mío</label>
        </div>
      </div>
      <Aviso>{error}</Aviso>
      <div className="tarjeta overflow-hidden">
        <div className="grid grid-cols-7 border-b border-crema-300 bg-crema/60 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">
          {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((d) => <div key={d} className="py-2">{d}</div>)}</div>
        <div className="grid grid-cols-7">
          {celdas.map((d) => {
            const k = iso(d), fuera = d.getMonth() !== mes.getMonth(), inh = k in inhabiles ? inhabiles[k] : (cal ? semana : [5, 6]).includes((d.getDay() + 6) % 7) ? "Inhábil (día de la semana)" : "";
            const esHoy = k === iso(hoy);
            return (
              <div key={k} className={`min-h-[7.5rem] border-b border-r border-crema-200 p-1.5 ${fuera ? "bg-slate-50/60 text-slate-400" : ""} ${inh ? "bg-[repeating-linear-gradient(135deg,#f8f5ef,#f8f5ef_6px,#f1ece3_6px,#f1ece3_12px)]" : ""}`} title={inh || undefined}>
                <div className="flex items-center justify-between">
                  <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${esHoy ? "bg-turquesa text-white" : ""}`}>{d.getDate()}</span>
                  {cat?.puede_editar && !fuera && <button className="text-xs text-slate-400 hover:text-turquesa-700" aria-label={`Agregar el ${k}`} onClick={() => setNuevo(k)}>+</button>}
                </div>
                {inh && !fuera && <p className="truncate text-[10px] text-slate-500">{inh}</p>}
                <ul className="mt-1 space-y-0.5">{(porDia[k] || []).slice(0, 4).map((e) => <li key={e.id}>
                  <Link href={`/agenda/eventos/${e.id}`} className={`block truncate rounded px-1 py-0.5 text-[11px] font-medium ${SITUACION[e.situacion][1]} ${e.estado !== "pendiente" ? "line-through opacity-70" : ""}`}>
                    {e.hora ? `${e.hora} ` : ""}{e.titulo}</Link></li>)}
                  {(porDia[k] || []).length > 4 && <li className="text-[11px] text-slate-500">+{porDia[k].length - 4} más</li>}</ul>
              </div>);
          })}
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">Los días rayados son inhábiles según el calendario elegido (días capturados por su despacho y los de descanso obligatorio del art. 74 LFT).</p>
      {nuevo && <FormEvento inicial={{ tipo: "actividad", fecha: nuevo }} onCerrar={() => setNuevo(null)} onGuardado={() => { setNuevo(null); cargar(); }} />}
    </AgendaShell>
  );
}
