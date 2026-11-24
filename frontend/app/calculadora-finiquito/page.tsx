"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Avisos, Desglose, Resumen } from "@/components/liquidaciones";
import Logo from "@/components/Logo";
import { mxn } from "@/lib/api";

const CAUSAS = [["despido_injustificado", "Despido injustificado"], ["renuncia", "Renuncia voluntaria"], ["rescision_trabajador", "Rescisión por causa del patrón"],
  ["despido_justificado", "Despido justificado"], ["mutuo_acuerdo", "Mutuo acuerdo o fin de contrato"]];

/** Calculadora pública (sin sesión): no guarda nada. El cálculo lo hace el servidor con el mismo motor del módulo. */
export default function Calculadora() {
  const [f, setF] = useState({ fecha_ingreso: "", fecha_baja: "", causa: "despido_injustificado", salario_diario: "", zona: "general", fecha_calculo: "", veinte: "auto" });
  const [res, setRes] = useState<any>(null);
  const [error, setError] = useState("");
  const listo = !!(f.fecha_ingreso && f.fecha_baja && Number(f.salario_diario) > 0);
  const datos = useMemo(() => ({
    fecha_ingreso: f.fecha_ingreso, fecha_baja: f.fecha_baja, causa: f.causa, salario_diario: f.salario_diario, zona: f.zona,
    ...(f.fecha_calculo ? { fecha_calculo: f.fecha_calculo } : {}), incluir_20_dias: f.veinte === "auto" ? null : f.veinte === "si",
  }), [f]);
  useEffect(() => {
    if (!listo) { setRes(null); return; }
    const t = setTimeout(async () => {
      try {
        const r = await fetch("/api/publico/finiquito", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) });
        const j = await r.json();
        if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Revise los datos.");
        setRes(j); setError("");
      } catch (e: any) { setRes(null); setError(e.message); }
    }, 400);
    return () => clearTimeout(t);
  }, [datos, listo]);
  const pon = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const despido = f.causa === "despido_injustificado";
  return (
    <div className="min-h-screen bg-crema">
      <header className="border-b border-crema-300 bg-white/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-5 py-3">
          <Link href="/" aria-label="Nomira, inicio"><Logo /></Link>
          <Link href="/#informes" className="btn-turquesa">Solicitar informes</Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 py-10">
        <p className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Herramienta gratuita · Ley Federal del Trabajo</p>
        <h1 className="mt-2 font-marca text-3xl font-extrabold text-marino sm:text-4xl">Calculadora de finiquito y liquidación</h1>
        <p className="mt-2 max-w-3xl text-slate-600">Capture la fecha de ingreso, la fecha de baja y el salario diario. Verá cada concepto con su operación y su artículo. No guardamos lo que capture.</p>
        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
          <section className="tarjeta h-fit space-y-4 p-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block"><span className="etiqueta">Fecha de ingreso</span><input type="date" className="campo" value={f.fecha_ingreso} onChange={pon("fecha_ingreso")} /></label>
              <label className="block"><span className="etiqueta">Fecha de baja o despido</span><input type="date" className="campo" value={f.fecha_baja} onChange={pon("fecha_baja")} /></label>
              <label className="block"><span className="etiqueta">Salario diario</span><input inputMode="decimal" className="campo" placeholder="p. ej. 500" value={f.salario_diario} onChange={pon("salario_diario")} /></label>
              <label className="block"><span className="etiqueta">¿Cómo terminó la relación?</span><select className="campo" value={f.causa} onChange={pon("causa")}>
                {CAUSAS.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>
              <label className="block"><span className="etiqueta">Zona</span><select className="campo" value={f.zona} onChange={pon("zona")}>
                <option value="general">Resto del país</option><option value="frontera">Zona Libre de la Frontera Norte</option></select></label>
              {(despido || f.causa === "rescision_trabajador") && <label className="block"><span className="etiqueta">20 días por año</span><select className="campo" value={f.veinte} onChange={pon("veinte")}>
                <option value="auto">{despido ? "No incluir" : "Incluir"}</option><option value={despido ? "si" : "no"}>{despido ? "Incluir (negativa a reinstalar)" : "No incluir"}</option></select></label>}
              {despido && <label className="block"><span className="etiqueta">Calcular salarios caídos al</span><input type="date" className="campo" value={f.fecha_calculo} onChange={pon("fecha_calculo")} />
                <span className="mt-0.5 block text-xs text-slate-500">Vacío: hoy.</span></label>}
            </div>
            <div className="rounded-2xl bg-turquesa-50 p-4 text-sm text-marino">
              <p className="font-bold">¿Lleva casos laborales?</p>
              <p className="mt-1 text-slate-600">En Nomira guarda cada cálculo, lo liga al asunto y al cliente, agrega horas extra con la reforma de 40 horas, prepara la propuesta de convenio y la imprime con su logotipo.</p>
              <Link href="/#informes" className="mt-2 inline-block font-semibold text-turquesa-700 underline">Conozca Nomira para despachos →</Link>
            </div>
          </section>
          <aside className="lg:sticky lg:top-4 lg:self-start">
            <div className="tarjeta space-y-4 p-6" aria-live="polite">
              <div><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Total estimado</p>
                <p className="text-4xl font-black text-marino" data-prueba="total">{res ? mxn(res.total) : "—"}</p></div>
              {!listo && <p className="text-sm text-slate-500">Capture las fechas y el salario para ver el cálculo.</p>}
              {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
              {res && <><Resumen r={res} /><Desglose r={res} /><Avisos avisos={res.avisos} /></>}
              <p className="text-xs text-slate-500">Estimación informativa; no es asesoría jurídica. Consulte a su abogado.</p>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
