"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import BotonAyuda from "@/components/BotonAyuda";
import Shell from "@/components/Shell";
import { Chip, ESTADO_INC, FormAviso, FormEmpleado, FormEmpresa, FormPeriodo, fechaCorta } from "@/components/rh";
import { Aviso, ConfirmarEliminar, Modal } from "@/components/ui";
import { api, mxn } from "@/lib/api";

type Pestana = "empleados" | "solicitudes" | "avisos" | "nomina" | "empresas";

function RH() {
  const sp = useSearchParams();
  const [cfg, setCfg] = useState<any>(null);
  const [tab, setTab] = useState<Pestana>((sp.get("tab") as Pestana) || "empleados");
  const [empresa, setEmpresa] = useState("");
  const [estado, setEstado] = useState("activo");
  const [emps, setEmps] = useState<any[] | null>(null);
  const [sols, setSols] = useState<any[]>([]);
  const [avisos, setAvisos] = useState<any[]>([]);
  const [periodos, setPeriodos] = useState<any[]>([]);
  const [clientes, setClientes] = useState<any[]>([]);
  const [dlg, setDlg] = useState<any>(null);
  const [error, setError] = useState(""); const [ok, setOk] = useState("");
  const cargar = useCallback(() => {
    api.get("/rh/resumen").then(setCfg).catch((e) => setError(e.message));
    api.get(`/rh/empleados?estado=${estado}${empresa ? `&empresa=${empresa}` : ""}`).then((r) => setEmps(r.empleados)).catch(() => {});
    api.get("/rh/incidencias?estado=pendiente").then((r) => setSols(r.incidencias)).catch(() => {});
    api.get("/rh/avisos").then((r) => setAvisos(r.avisos)).catch(() => {});
    api.get("/rh/periodos").then((r) => setPeriodos(r.periodos)).catch(() => {});
  }, [estado, empresa]);
  useEffect(() => { cargar(); }, [cargar]);
  async function hacer(f: () => Promise<any>, msg: string) {
    setError(""); setOk("");
    try { await f(); setOk(msg); cargar(); } catch (e: any) { setError(e.message); }
  }
  if (!cfg) return <Shell><Aviso>{error}</Aviso></Shell>;
  const TABS: [Pestana, string, number?][] = [["empleados", "Empleados", cfg.activos], ["solicitudes", "Solicitudes", cfg.solicitudes], ["avisos", "Avisos"],
    ["nomina", "Nómina"], ["empresas", "Empresas"]];
  return (
    <Shell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-turquesa-700">Recursos humanos</p>
          <h1 className="text-3xl font-extrabold text-marino">Personal y nómina</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-500">Lleve el personal de su despacho y el de las empresas a las que les da servicio: expedientes con documentos, vacaciones, faltas, avisos con acuse de lectura y nómina de control. Cada empleado tiene su propio portal en el celular.</p></div>
        <div className="flex flex-wrap items-center gap-2"><BotonAyuda modulo="rh" />
          {cfg.puede_editar && <button className="btn-turquesa" onClick={() => setDlg({ t: "empleado" })}>+ Alta de empleado</button>}</div>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
        {cfg.documentos_por_revisar > 0 && <Aviso tipo="info">Hay {cfg.documentos_por_revisar} documento(s) que subieron los empleados desde su portal esperando revisión. Ábralos desde la ficha de cada empleado.</Aviso>}</div>
      <div className="mb-4 flex flex-wrap gap-2" role="tablist">{TABS.map(([k, t, n]) => (
        <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
          className={`rounded-full px-4 py-2 text-sm font-semibold ${tab === k ? "bg-marino text-white" : "bg-crema text-marino hover:bg-crema-300"}`}>
          {t}{n ? <span className={`ml-2 rounded-full px-1.5 text-xs ${k === "solicitudes" ? "bg-amber-400 text-marino" : "bg-white/20"}`}>{n}</span> : null}</button>))}</div>

      {tab === "empleados" && <section className="tarjeta overflow-hidden" aria-label="Empleados">
        <div className="flex flex-wrap gap-2 border-b border-crema-300 p-3">
          <select className="campo w-auto py-1.5 text-sm" aria-label="Empresa" value={empresa} onChange={(e) => setEmpresa(e.target.value)}>
            <option value="">Todas las empresas</option>{cfg.empresas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select>
          <select className="campo w-auto py-1.5 text-sm" aria-label="Estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="activo">Activos</option><option value="baja">Dados de baja</option><option value="">Todos</option></select></div>
        {emps && !emps.length ? <div className="p-8 text-center"><p className="font-semibold text-marino">Todavía no hay empleados aquí</p>
          <p className="mt-1 text-sm text-slate-600">Dé de alta a su equipo; si lleva la nómina de un cliente, primero agréguelo en la pestaña «Empresas».</p></div>
          : <table className="w-full text-sm"><thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
            <th className="px-4 py-2">Nombre</th><th className="px-4 py-2">Empresa</th><th className="px-4 py-2">Antigüedad</th><th className="px-4 py-2">Expediente</th><th className="px-4 py-2">Portal</th></tr></thead>
            <tbody className="divide-y divide-crema-200">{emps?.map((e) => (
              <tr key={e.id}><td className="px-4 py-3"><Link href={`/rh/empleados/${e.id}`} className="font-semibold text-marino hover:underline">{e.nombre}</Link>
                <span className="block text-xs text-slate-500">{e.puesto || "—"}</span></td>
                <td className="px-4 py-3 text-slate-600">{e.empresa}</td>
                <td className="px-4 py-3 text-slate-600">{e.antiguedad ? `${e.antiguedad} año${e.antiguedad === 1 ? "" : "s"}` : "Menos de 1 año"}</td>
                <td className="px-4 py-3"><span className={e.documentos_completos >= e.documentos_requeridos ? "text-emerald-700" : "text-amber-700"}>
                  {e.documentos_completos} de {e.documentos_requeridos} documentos</span></td>
                <td className="px-4 py-3 text-xs">{e.portal ? <span className="text-emerald-700">✓ {e.portal_ultimo_acceso ? `entró ${fechaCorta(e.portal_ultimo_acceso)}` : "con acceso"}</span> : <span className="text-slate-400">Sin acceso</span>}</td></tr>))}</tbody></table>}
      </section>}

      {tab === "solicitudes" && <section className="tarjeta overflow-hidden" aria-label="Solicitudes por autorizar">
        {!sols.length ? <p className="p-8 text-center text-sm text-slate-600">No hay solicitudes por autorizar. Cuando un empleado pida vacaciones, un permiso o avise de una incapacidad desde su portal, aparecerá aquí.</p>
          : <ul className="divide-y divide-crema-200">{sols.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
              <span><Link href={`/rh/empleados/${s.empleado_id}`} className="font-semibold text-marino hover:underline">{s.empleado}</Link> · <b>{s.tipo_texto}</b> · {s.dias} día{s.dias === 1 ? "" : "s"}
                <span className="block text-xs text-slate-500">Del {fechaCorta(s.desde)} al {fechaCorta(s.hasta)}{s.motivo ? ` · «${s.motivo}»` : ""}</span>
                {s.archivo && <button className="text-xs font-semibold text-turquesa-700 underline" onClick={() => api.descargar(`/rh/incidencias/${s.id}/archivo`, "incapacidad")}>Ver archivo</button>}</span>
              {cfg.puede_editar && <span className="flex gap-2"><button className="btn-turquesa" onClick={() => hacer(() => api.post(`/rh/incidencias/${s.id}/resolver`, { aprobar: true }), "Autorizada.")}>Autorizar</button>
                <button className="btn-sec" onClick={() => setDlg({ t: "rechazar", s })}>Rechazar</button></span>}
            </li>))}</ul>}
      </section>}

      {tab === "avisos" && <section className="space-y-3" aria-label="Avisos al personal">
        {cfg.puede_editar && <button className="btn-turquesa" onClick={() => setDlg({ t: "aviso" })}>+ Nuevo aviso</button>}
        {!avisos.length && <p className="tarjeta p-8 text-center text-sm text-slate-600">Publique avisos para todo el personal o solo para una empresa: días inhábiles, pagos, juntas, cambios de horario. Si pide acuse, verá quién ya lo leyó.</p>}
        {avisos.map((a) => (
          <article key={a.id} className="tarjeta p-4">
            <div className="flex flex-wrap items-start justify-between gap-2"><h2 className="font-semibold text-marino">{a.fijado ? "📌 " : ""}{a.titulo}</h2>
              <span className="text-xs text-slate-500">{fechaCorta(a.creado_en)} · {a.empresa_id ? cfg.empresas.find((x: any) => x.id === a.empresa_id)?.nombre : "Todo el personal"}</span></div>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{a.cuerpo}</p>
            <div className="mt-2 flex flex-wrap gap-3 text-xs">
              {a.requiere_acuse && <button className="font-semibold text-turquesa-700 underline" onClick={() => setDlg({ t: "acuses", a })}>Leído por {a.leidos} de {a.destinatarios}</button>}
              {cfg.puede_editar && <><button className="text-slate-600 underline" onClick={() => setDlg({ t: "aviso", a })}>Editar</button>
                <button className="text-slate-500 underline" onClick={() => setDlg({ t: "borrar_aviso", a })}>Borrar</button></>}</div>
          </article>))}
      </section>}

      {tab === "nomina" && <section className="space-y-3" aria-label="Nómina">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="max-w-3xl text-sm text-slate-600">Nómina de control: sueldo por días pagados, faltas, prima vacacional y los conceptos que usted capture. No calcula ISR ni IMSS ni timbra CFDI: exporte a Excel para su contador.</p>
          {cfg.puede_editar && <button className="btn-turquesa" onClick={() => setDlg({ t: "periodo" })}>+ Nuevo periodo</button>}</div>
        <div className="tarjeta overflow-hidden">{!periodos.length ? <p className="p-8 text-center text-sm text-slate-600">Todavía no hay periodos de nómina.</p>
          : <table className="w-full text-sm"><thead className="bg-crema/60 text-left text-xs uppercase tracking-wide text-slate-500"><tr>
            <th className="px-4 py-2">Periodo</th><th className="px-4 py-2">Empresa</th><th className="px-4 py-2">Empleados</th><th className="px-4 py-2">Total neto</th><th className="px-4 py-2">Estado</th></tr></thead>
            <tbody className="divide-y divide-crema-200">{periodos.map((p) => (
              <tr key={p.id}><td className="px-4 py-3"><Link href={`/rh/nomina/${p.id}`} className="font-semibold text-marino hover:underline">{fechaCorta(p.inicio)} al {fechaCorta(p.fin)}</Link></td>
                <td className="px-4 py-3 text-slate-600">{p.empresa}</td><td className="px-4 py-3">{p.empleados}</td><td className="px-4 py-3">{mxn(p.total)}</td>
                <td className="px-4 py-3"><Chip e={p.estado === "cerrado" ? ["Cerrado: lo ven los empleados", "bg-emerald-100 text-emerald-800"] : ["Borrador", "bg-amber-100 text-amber-800"]} /></td></tr>))}</tbody></table>}</div>
      </section>}

      {tab === "empresas" && <section className="space-y-3" aria-label="Empresas">
        <div className="flex flex-wrap items-center justify-between gap-2"><p className="max-w-3xl text-sm text-slate-600">La primera es su despacho. Agregue las empresas de sus clientes a las que les lleva Recursos Humanos: cada una con sus empleados, avisos y nómina.</p>
          {cfg.puede_editar && <button className="btn-turquesa" onClick={() => { api.get("/clientes").then((r) => setClientes(r.clientes || [])).catch(() => {}); setDlg({ t: "empresa" }); }}>+ Agregar empresa cliente</button>}</div>
        <div className="grid gap-3 md:grid-cols-2">{cfg.empresas.map((x: any) => (
          <article key={x.id} className="tarjeta p-4"><p className="font-semibold text-marino">{x.nombre}{x.propia && <span className="ml-2 rounded-full bg-turquesa-50 px-2 py-0.5 text-xs text-turquesa-700">Su despacho</span>}</p>
            <p className="text-xs text-slate-500">{[x.rfc && `RFC ${x.rfc}`, x.registro_patronal && `Reg. patronal ${x.registro_patronal}`, cfg.periodicidades[x.periodicidad]].filter(Boolean).join(" · ")}</p>
            <p className="mt-1 text-sm">{x.empleados} empleado{x.empleados === 1 ? "" : "s"} activo{x.empleados === 1 ? "" : "s"}</p>
            {cfg.puede_editar && <button className="mt-2 text-xs font-semibold text-turquesa-700 underline" onClick={() => { api.get("/clientes").then((r) => setClientes(r.clientes || [])).catch(() => {}); setDlg({ t: "empresa", x }); }}>Editar</button>}
          </article>))}</div>
      </section>}

      {dlg?.t === "empleado" && <FormEmpleado cfg={cfg} empresa={empresa ? Number(empresa) : undefined} onCerrar={() => setDlg(null)} onListo={(e) => { window.location.href = `/rh/empleados/${e.id}`; }} />}
      {dlg?.t === "empresa" && <FormEmpresa cfg={cfg} empresa={dlg.x} clientes={clientes} onCerrar={() => setDlg(null)} onListo={() => { setDlg(null); setOk("Empresa guardada."); cargar(); }} />}
      {dlg?.t === "aviso" && <FormAviso cfg={cfg} aviso={dlg.a} onCerrar={() => setDlg(null)} onListo={() => { setDlg(null); setOk("Aviso publicado: lo verán en su portal."); cargar(); }} />}
      {dlg?.t === "periodo" && <FormPeriodo cfg={cfg} onCerrar={() => setDlg(null)} onListo={(p) => { window.location.href = `/rh/nomina/${p.id}`; }} />}
      {dlg?.t === "borrar_aviso" && <ConfirmarEliminar titulo="Borrar aviso" onCerrar={() => setDlg(null)} onConfirmar={() => api.borrar(`/rh/avisos/${dlg.a.id}`).then(cargar)}>¿Borrar «{dlg.a.titulo}»? Deja de verse en los portales.</ConfirmarEliminar>}
      {dlg?.t === "rechazar" && <Rechazar s={dlg.s} onCerrar={() => setDlg(null)} onListo={() => { setDlg(null); setOk("Solicitud rechazada; el empleado verá el motivo."); cargar(); }} />}
      {dlg?.t === "acuses" && <Acuses a={dlg.a} onCerrar={() => setDlg(null)} />}
    </Shell>
  );
}

function Rechazar({ s, onCerrar, onListo }: { s: any; onCerrar: () => void; onListo: () => void }) {
  const [c, setC] = useState(""); const [error, setError] = useState("");
  return <Modal titulo={`Rechazar: ${s.tipo_texto} de ${s.empleado}`} onCerrar={onCerrar}>
    <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { await api.post(`/rh/incidencias/${s.id}/resolver`, { aprobar: false, comentario: c }); onListo(); } catch (x: any) { setError(x.message); } }}>
      <label className="block"><span className="etiqueta">Motivo (lo verá el empleado)</span><input className="campo" value={c} onChange={(e) => setC(e.target.value)} required maxLength={500} /></label>
      <Aviso>{error}</Aviso><div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Rechazar</button></div>
    </form></Modal>;
}

function Acuses({ a, onCerrar }: { a: any; onCerrar: () => void }) {
  const [p, setP] = useState<any[] | null>(null);
  useEffect(() => { api.get(`/rh/avisos/${a.id}/acuses`).then((r) => setP(r.personas)).catch(() => setP([])); }, [a.id]);
  return <Modal titulo={`¿Quién leyó «${a.titulo}»?`} onCerrar={onCerrar}>
    <ul className="divide-y divide-crema-200 text-sm">{p?.map((x) => <li key={x.id} className="flex justify-between gap-2 py-2"><span>{x.nombre}</span>
      {x.leido_en ? <span className="text-emerald-700">✓ {fechaCorta(x.leido_en)}</span> : <span className="text-slate-400">{x.portal ? "Sin leer" : "Sin acceso al portal"}</span>}</li>)}</ul>
  </Modal>;
}

export default function Pagina() { return <Suspense><RH /></Suspense>; }
