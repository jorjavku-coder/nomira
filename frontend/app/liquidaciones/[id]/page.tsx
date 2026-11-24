"use client";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { ClienteBreve, SelectorCliente } from "@/components/clientes";
import { Avisos, Desglose, Resumen } from "@/components/liquidaciones";
import { Aviso, ConfirmarEliminar } from "@/components/ui";
import { api, mxn } from "@/lib/api";

type Extra = { desde: string; hasta: string; horas_semana: string };
type Otro = { concepto: string; importe: string };
const INICIAL = {
  fecha_ingreso: "", fecha_baja: "", causa: "despido_injustificado", salario_diario: "", fecha_calculo: "",
  salario_integrado: "", otras_prestaciones_diarias: "", zona: "general", salario_minimo: "",
  aguinaldo_dias: "15", prima_vacacional_pct: "25", dias_pendientes_pago: "", incluir_aguinaldo: true,
  vacaciones_anteriores_dias: "", vacaciones_tomadas_actual: "", incluir_20_dias: "auto", incluir_salarios_caidos: "auto", tipo_jornada: "diurna",
};
const OPCIONAL = ["fecha_calculo", "salario_integrado", "salario_minimo"];
const CERO_SI_VACIO = ["otras_prestaciones_diarias", "dias_pendientes_pago", "vacaciones_anteriores_dias", "vacaciones_tomadas_actual"];

function aDatos(f: typeof INICIAL, extras: Extra[], otros: Otro[]) {
  const d: any = { ...f };
  for (const k of OPCIONAL) if (!d[k]) delete d[k];
  for (const k of CERO_SI_VACIO) if (!d[k]) d[k] = "0";
  for (const k of ["incluir_20_dias", "incluir_salarios_caidos"]) d[k] = d[k] === "auto" ? null : d[k] === "si";
  d.horas_extra = extras.filter((x) => x.desde && x.hasta && Number(x.horas_semana) > 0);
  d.otros = otros.filter((x) => x.concepto.trim() && Number(x.importe) > 0);
  return d;
}

function deDatos(d: any): typeof INICIAL {
  const f: any = { ...INICIAL };
  for (const k of Object.keys(INICIAL)) if (d[k] !== undefined && d[k] !== null) f[k] = typeof d[k] === "boolean" && k !== "incluir_aguinaldo" ? (d[k] ? "si" : "no") : d[k];
  for (const k of CERO_SI_VACIO) if (f[k] === "0" || f[k] === "0.00") f[k] = "";
  return f;
}

function Campo({ e, children, ayuda }: { e: string; children: React.ReactNode; ayuda?: string }) {
  return <label className="block"><span className="etiqueta">{e}</span>{children}{ayuda && <span className="mt-0.5 block text-xs text-slate-500">{ayuda}</span>}</label>;
}

function Editor() {
  const { id } = useParams<{ id: string }>();
  const nuevo = id === "nuevo";
  const router = useRouter();
  const sp = useSearchParams();
  const [tablas, setTablas] = useState<any>(null);
  const [f, setF] = useState(INICIAL);
  const [extras, setExtras] = useState<Extra[]>([]);
  const [otros, setOtros] = useState<Otro[]>([]);
  const [persona, setPersona] = useState({ trabajador: "", patron: "", titulo: "", ag_asunto_id: "", propuesta: "", autorizado: "", notas: "" });
  const [cliente, setCliente] = useState<ClienteBreve | null>(null);
  const [res, setRes] = useState<any>(null);
  const [errCalc, setErrCalc] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargado, setCargado] = useState(nuevo);
  const [guardando, setGuardando] = useState(false);
  const [borrar, setBorrar] = useState(false);
  const [masSalario, setMasSalario] = useState(false);
  const puedeEditar = tablas?.puede_editar;

  useEffect(() => {
    api.get("/liquidaciones/tablas").then((t) => {
      setTablas(t);
      if (nuevo) {
        const a = sp.get("asunto");
        if (a) setPersona((p) => ({ ...p, ag_asunto_id: a }));
      }
    }).catch((e) => setError(e.message));
    if (!nuevo) api.get(`/liquidaciones/${id}`).then((c) => {
      setF(deDatos(c.datos));
      setExtras((c.datos.horas_extra || []).map((x: any) => ({ ...x, horas_semana: String(x.horas_semana) })));
      setOtros((c.datos.otros || []).map((x: any) => ({ ...x, importe: String(x.importe) })));
      setPersona({ trabajador: c.trabajador, patron: c.patron || "", titulo: c.titulo, ag_asunto_id: c.ag_asunto_id ? String(c.ag_asunto_id) : "",
        propuesta: c.propuesta || "", autorizado: c.autorizado || "", notas: c.notas || "" });
      setCliente(c.cliente);
      if (c.datos.salario_integrado || c.datos.salario_minimo || Number(c.datos.otras_prestaciones_diarias) > 0 || Number(c.datos.aguinaldo_dias ?? 15) !== 15 || Number(c.datos.prima_vacacional_pct ?? 25) !== 25) setMasSalario(true);
      setCargado(true);
    }).catch((e) => setError(e.message));
  }, [id, nuevo, sp]);

  const datos = useMemo(() => aDatos(f, extras, otros), [f, extras, otros]);
  const listo = !!(f.fecha_ingreso && f.fecha_baja && Number(f.salario_diario) > 0);
  useEffect(() => {
    if (!cargado || !listo) { setRes(null); return; }
    const t = setTimeout(() => api.post("/liquidaciones/calcular", datos).then((r) => { setRes(r); setErrCalc(""); }).catch((e) => { setRes(null); setErrCalc(e.message); }), 350);
    return () => clearTimeout(t);
  }, [datos, listo, cargado]);

  const pon = (k: keyof typeof INICIAL) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const pct = (v: string) => res && Number(v) > 0 && Number(res.total) > 0 ? `${((Number(v) * 100) / Number(res.total)).toFixed(1)} % del total` : "";
  const despido = f.causa === "despido_injustificado";
  const conIndemnizacion = despido || f.causa === "rescision_trabajador";

  async function guardar() {
    setError(""); setOk("");
    if (!persona.trabajador.trim()) { setError("Capture el nombre de la persona trabajadora."); return; }
    setGuardando(true);
    const cuerpo = { trabajador: persona.trabajador, patron: persona.patron || null, titulo: persona.titulo || null,
      ag_asunto_id: persona.ag_asunto_id ? Number(persona.ag_asunto_id) : null, cr_cliente_id: cliente?.id ?? null, datos,
      propuesta: persona.propuesta || null, autorizado: persona.autorizado || null, notas: persona.notas || null };
    try {
      const c = nuevo ? await api.post("/liquidaciones", cuerpo) : await api.put(`/liquidaciones/${id}`, cuerpo);
      setPersona((p) => ({ ...p, titulo: c.titulo }));
      if (nuevo) router.replace(`/liquidaciones/${c.id}`); else setOk("Cálculo guardado.");
    } catch (e: any) { setError(e.message); } finally { setGuardando(false); }
  }

  return (
    <Shell>
      <Link href="/liquidaciones" className="text-sm font-semibold text-turquesa-700">← Liquidaciones</Link>
      <div className="mb-4 mt-1 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-extrabold text-marino">{nuevo ? "Nuevo cálculo" : persona.titulo || "Cálculo"}</h1>
          <p className="text-sm text-slate-500">El resultado se actualiza mientras captura. Es una estimación: revise cada concepto con las constancias del caso.</p></div>
        <div className="flex flex-wrap items-center gap-2"><BotonAyuda modulo="liquidaciones" />
          {!nuevo && <><button className="btn-sec" onClick={() => api.descargar(`/liquidaciones/${id}/csv`, "liquidacion.csv")}>Excel (CSV)</button>
            <Link className="btn-sec" href={`/liquidaciones/${id}/imprimir`}>Imprimir o PDF</Link></>}
          {!nuevo && puedeEditar && <button className="btn-peligro" onClick={() => setBorrar(true)}>Eliminar</button>}
          {puedeEditar && <button className="btn-turquesa" disabled={guardando || !listo} onClick={guardar}>{guardando ? "Guardando…" : "Guardar cálculo"}</button>}</div>
      </div>
      <Aviso>{error}</Aviso>
      <Aviso tipo="ok">{ok}</Aviso>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="space-y-4">
          <section className="tarjeta space-y-3 p-5">
            <h2 className="font-bold text-marino">Persona y asunto</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <Campo e="Persona trabajadora *"><input className="campo" value={persona.trabajador} onChange={(e) => setPersona({ ...persona, trabajador: e.target.value })} /></Campo>
              <Campo e="Patrón o empresa"><input className="campo" value={persona.patron} onChange={(e) => setPersona({ ...persona, patron: e.target.value })} /></Campo>
              {tablas?.asuntos?.length > 0 && <Campo e="Asunto de la Agenda" ayuda="Suma este cálculo a la exposición económica del asunto.">
                <select className="campo" value={persona.ag_asunto_id} onChange={(e) => setPersona({ ...persona, ag_asunto_id: e.target.value })}>
                  <option value="">— Sin asunto —</option>{tablas.asuntos.map((a: any) => <option key={a.id} value={a.id}>{a.titulo}{a.numero ? ` (${a.numero})` : ""}</option>)}</select></Campo>}
              <SelectorCliente valor={cliente} onCambio={setCliente} etiqueta="Cliente del despacho" />
            </div>
          </section>

          <section className="tarjeta space-y-3 p-5">
            <h2 className="font-bold text-marino">Relación de trabajo</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              <Campo e="Fecha de ingreso *"><input type="date" className="campo" value={f.fecha_ingreso} onChange={pon("fecha_ingreso")} /></Campo>
              <Campo e="Fecha de baja o despido *"><input type="date" className="campo" value={f.fecha_baja} onChange={pon("fecha_baja")} /></Campo>
              <Campo e="Causa de terminación"><select className="campo" value={f.causa} onChange={pon("causa")}>
                {(tablas?.causas || []).map((c: any) => <option key={c.clave} value={c.clave}>{c.nombre}</option>)}</select></Campo>
              <Campo e="Salario diario *" ayuda="Cuota diaria (salario base)."><input inputMode="decimal" className="campo" value={f.salario_diario} onChange={pon("salario_diario")} placeholder="0.00" /></Campo>
              <Campo e="Zona del salario mínimo"><select className="campo" value={f.zona} onChange={pon("zona")}>
                <option value="general">General</option><option value="frontera">Zona Libre de la Frontera Norte</option></select></Campo>
              <Campo e="Jornada"><select className="campo" value={f.tipo_jornada} onChange={pon("tipo_jornada")}>
                <option value="diurna">Diurna (8 h)</option><option value="mixta">Mixta (7.5 h)</option><option value="nocturna">Nocturna (7 h)</option></select></Campo>
            </div>
            <button type="button" className="text-sm font-semibold text-turquesa-700 underline" onClick={() => setMasSalario(!masSalario)}>{masSalario ? "Ocultar" : "Ajustar"} salario integrado, aguinaldo y prima vacacional</button>
            {masSalario && <div className="grid gap-3 rounded-xl bg-crema/60 p-3 sm:grid-cols-3">
              <Campo e="Días de aguinaldo" ayuda="Mínimo de ley: 15."><input inputMode="decimal" className="campo" value={f.aguinaldo_dias} onChange={pon("aguinaldo_dias")} /></Campo>
              <Campo e="Prima vacacional (%)" ayuda="Mínimo de ley: 25 %."><input inputMode="decimal" className="campo" value={f.prima_vacacional_pct} onChange={pon("prima_vacacional_pct")} /></Campo>
              <Campo e="Otras prestaciones diarias" ayuda="Vales, fondo de ahorro, bonos fijos (art. 84)."><input inputMode="decimal" className="campo" value={f.otras_prestaciones_diarias} onChange={pon("otras_prestaciones_diarias")} placeholder="0.00" /></Campo>
              <Campo e="Salario diario integrado" ayuda={res ? `Calculado: ${mxn(res.salarios.integrado_calculado)}. Déjelo vacío para usarlo.` : "Déjelo vacío para calcularlo."}>
                <input inputMode="decimal" className="campo" value={f.salario_integrado} onChange={pon("salario_integrado")} /></Campo>
              <Campo e="Salario mínimo" ayuda="Vacío: el del año de la baja según la tabla."><input inputMode="decimal" className="campo" value={f.salario_minimo} onChange={pon("salario_minimo")} /></Campo>
            </div>}
          </section>

          <section className="tarjeta space-y-3 p-5">
            <h2 className="font-bold text-marino">Pendientes de pago</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              <Campo e="Días trabajados sin pagar"><input inputMode="decimal" className="campo" value={f.dias_pendientes_pago} onChange={pon("dias_pendientes_pago")} placeholder="0" /></Campo>
              <Campo e="Vacaciones ya disfrutadas este año" ayuda="Del año de servicio en curso."><input inputMode="decimal" className="campo" value={f.vacaciones_tomadas_actual} onChange={pon("vacaciones_tomadas_actual")} placeholder="0" /></Campo>
              <Campo e="Vacaciones de años anteriores sin disfrutar" ayuda="Días, si los hay."><input inputMode="decimal" className="campo" value={f.vacaciones_anteriores_dias} onChange={pon("vacaciones_anteriores_dias")} placeholder="0" /></Campo>
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.incluir_aguinaldo} onChange={(e) => setF({ ...f, incluir_aguinaldo: e.target.checked })} /> Incluir aguinaldo proporcional del año</label>
          </section>

          {conIndemnizacion && <section className="tarjeta space-y-3 p-5">
            <h2 className="font-bold text-marino">Indemnización</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              <Campo e="20 días por año" ayuda="Procede si el patrón se niega a reinstalar o en la rescisión (art. 50 y 52)."><select className="campo" value={String(f.incluir_20_dias)} onChange={pon("incluir_20_dias")}>
                <option value="auto">Según la causa</option><option value="si">Incluir</option><option value="no">No incluir</option></select></Campo>
              {despido && <><Campo e="Salarios caídos"><select className="campo" value={String(f.incluir_salarios_caidos)} onChange={pon("incluir_salarios_caidos")}>
                <option value="auto">Incluir</option><option value="no">No incluir</option></select></Campo>
                <Campo e="Calcular salarios caídos al" ayuda="Fecha estimada de pago o del laudo. Vacío: hoy."><input type="date" className="campo" value={f.fecha_calculo} onChange={pon("fecha_calculo")} /></Campo></>}
            </div>
          </section>}

          <section className="tarjeta space-y-3 p-5">
            <div className="flex items-center justify-between"><h2 className="font-bold text-marino">Horas extra</h2>
              <button type="button" className="text-sm font-semibold text-turquesa-700" onClick={() => setExtras([...extras, { desde: "", hasta: "", horas_semana: "" }])}>+ Agregar periodo</button></div>
            <p className="text-xs text-slate-500">Capture cuántas horas trabajaba a la semana en cada periodo. Se paga al doble hasta el tope de cada año (9 h; 10 en 2028, 11 en 2029, 12 desde 2030) y al triple lo que pase de ahí; la jornada legal baja de 48 a 40 h entre 2027 y 2030.</p>
            {extras.map((x, i) => (
              <div key={i} className="grid items-end gap-2 sm:grid-cols-[1fr_1fr_1fr_auto]">
                <Campo e="Desde"><input type="date" className="campo" value={x.desde} onChange={(e) => setExtras(extras.map((y, j) => j === i ? { ...y, desde: e.target.value } : y))} /></Campo>
                <Campo e="Hasta"><input type="date" className="campo" value={x.hasta} onChange={(e) => setExtras(extras.map((y, j) => j === i ? { ...y, hasta: e.target.value } : y))} /></Campo>
                <Campo e="Horas por semana"><input inputMode="decimal" className="campo" value={x.horas_semana} onChange={(e) => setExtras(extras.map((y, j) => j === i ? { ...y, horas_semana: e.target.value } : y))} placeholder="p. ej. 56" /></Campo>
                <button type="button" className="mb-2 text-xs font-semibold text-red-700 underline" onClick={() => setExtras(extras.filter((_, j) => j !== i))}>Quitar</button>
              </div>))}
          </section>

          <section className="tarjeta space-y-3 p-5">
            <div className="flex items-center justify-between"><h2 className="font-bold text-marino">Otros conceptos</h2>
              <button type="button" className="text-sm font-semibold text-turquesa-700" onClick={() => setOtros([...otros, { concepto: "", importe: "" }])}>+ Agregar concepto</button></div>
            <p className="text-xs text-slate-500">PTU, fondo de ahorro, bonos, comisiones u otro importe que ya tenga calculado.</p>
            {otros.map((x, i) => (
              <div key={i} className="grid items-end gap-2 sm:grid-cols-[2fr_1fr_auto]">
                <Campo e="Concepto"><input className="campo" value={x.concepto} onChange={(e) => setOtros(otros.map((y, j) => j === i ? { ...y, concepto: e.target.value } : y))} /></Campo>
                <Campo e="Importe"><input inputMode="decimal" className="campo" value={x.importe} onChange={(e) => setOtros(otros.map((y, j) => j === i ? { ...y, importe: e.target.value } : y))} /></Campo>
                <button type="button" className="mb-2 text-xs font-semibold text-red-700 underline" onClick={() => setOtros(otros.filter((_, j) => j !== i))}>Quitar</button>
              </div>))}
          </section>

          <section className="tarjeta space-y-3 p-5">
            <h2 className="font-bold text-marino">Propuesta de convenio</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <Campo e="Monto que se propone" ayuda={pct(persona.propuesta)}><input inputMode="decimal" className="campo" value={persona.propuesta} onChange={(e) => setPersona({ ...persona, propuesta: e.target.value })} /></Campo>
              <Campo e="Monto autorizado por el cliente" ayuda={pct(persona.autorizado) || "Límite que el cliente autorizó para negociar."}><input inputMode="decimal" className="campo" value={persona.autorizado} onChange={(e) => setPersona({ ...persona, autorizado: e.target.value })} /></Campo>
            </div>
            <Campo e="Notas internas"><textarea className="campo min-h-[70px]" value={persona.notas} onChange={(e) => setPersona({ ...persona, notas: e.target.value })} /></Campo>
            <Campo e="Título del cálculo" ayuda="Vacío: causa y nombre de la persona."><input className="campo" value={persona.titulo} onChange={(e) => setPersona({ ...persona, titulo: e.target.value })} /></Campo>
          </section>
        </div>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <div className="tarjeta space-y-4 p-5" aria-live="polite">
            <div><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Total estimado</p>
              <p className="text-4xl font-black text-marino" data-prueba="total">{res ? mxn(res.total) : "—"}</p>
              {res && <p className="text-xs text-slate-500">{res.causa_nombre}</p>}</div>
            {!listo && <p className="text-sm text-slate-500">Capture fecha de ingreso, fecha de baja y salario diario para ver el cálculo.</p>}
            <Aviso>{errCalc}</Aviso>
            {res && <><Resumen r={res} /><Desglose r={res} /><Avisos avisos={res.avisos} /></>}
          </div>
        </aside>
      </div>
      {borrar && <ConfirmarEliminar titulo="Eliminar cálculo" onCerrar={() => setBorrar(false)}
        onConfirmar={async () => { await api.borrar(`/liquidaciones/${id}`); router.replace("/liquidaciones"); }}>
        Se eliminará el cálculo de {persona.trabajador}. No se puede deshacer.</ConfirmarEliminar>}
    </Shell>
  );
}

export default function Pagina() {
  return <Suspense><Editor /></Suspense>;
}
