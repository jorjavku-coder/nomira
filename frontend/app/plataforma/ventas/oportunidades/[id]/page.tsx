"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EstadoCot } from "@/components/comercial";
import { cuando, dinero, Etapa, FormActividad, Historial, useCatalogosVentas, VentasShell } from "@/components/ventas";
import { Aviso, Modal } from "@/components/ui";
import { apiP, avisarContadores } from "@/lib/plataforma";

export default function Oportunidad() {
  const { id } = useParams<{ id: string }>();
  const cat = useCatalogosVentas();
  const [o, setO] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [dialogo, setDialogo] = useState<"" | "actividad" | "tarea" | "editar" | "perder" | "ganar">("");
  const cargar = useCallback(() => apiP.get(`/ventas/oportunidades/${id}`).then(setO).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (new URLSearchParams(window.location.search).get("perder") === "1") setDialogo("perder"); }, []);
  async function etapa(e: string, extra: any = {}) {
    setError(""); setOk("");
    try { setO(await apiP.post(`/ventas/oportunidades/${id}/etapa`, { etapa: e, ...extra })); avisarContadores(); setDialogo(""); setOk("Etapa actualizada."); }
    catch (x: any) { setError(x.message); }
  }
  if (!o || !cat) return <VentasShell><Aviso>{error}</Aviso></VentasShell>;
  const abierta = cat.abiertas.includes(o.etapa);
  const ct = o.contacto_completo;
  return (
    <VentasShell>
      <Link href="/plataforma/ventas" className="text-sm font-semibold text-turquesa-700">← Embudo</Link>
      <div className="mb-4 mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2"><h2 className="text-2xl font-extrabold text-marino">{o.titulo}</h2><Etapa etapa={o.etapa} texto={o.etapa_texto} /></div>
          <p className="mt-1 text-sm text-slate-600">{dinero(o.valor_mensual)}/mes · probabilidad {o.probabilidad}% · {o.propietario || "Sin responsable"}
            {o.cierre_estimado && ` · cierre estimado ${new Date(o.cierre_estimado + "T12:00").toLocaleDateString("es-MX")}`}</p>
          <p className="text-xs text-slate-500">Origen: {o.origen_texto}{o.campana ? ` · Campaña: ${o.campana}` : ""} · creada {cuando(o.creado_en)}</p>
          {o.etapa === "perdido" && <p className="mt-1 text-sm text-slate-600">Perdida: <b>{o.motivo_texto}</b>{o.nota_cierre ? ` — ${o.nota_cierre}` : ""}</p>}
          {o.organizacion && <p className="mt-1 text-sm">Ya es cliente: <Link className="font-semibold text-turquesa-700 underline" href={`/plataforma/clientes/${o.organizacion.id}`}>{o.organizacion.nombre}</Link></p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => setDialogo("editar")}>Editar</button>
          {abierta ? <><button className="btn-sec" onClick={() => setDialogo("perder")}>Marcar perdida</button><button className="btn-turquesa" onClick={() => setDialogo("ganar")}>¡Ganada!</button></>
            : <button className="btn-sec" onClick={() => etapa("negociacion")}>Reabrir</button>}
        </div>
      </div>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {abierta && <ol className="mb-5 flex overflow-x-auto rounded-2xl border border-crema-300 bg-white text-xs font-semibold" aria-label="Etapas">
        {cat.etapas.filter((e: any) => cat.abiertas.includes(e.clave)).map((e: any) => {
          const i = cat.abiertas.indexOf(e.clave), act = cat.abiertas.indexOf(o.etapa);
          return <li key={e.clave} className="flex-1"><button onClick={() => e.clave !== o.etapa && etapa(e.clave)}
            className={`w-full whitespace-nowrap px-3 py-2.5 ${i < act ? "bg-turquesa-50 text-turquesa-700" : i === act ? "bg-turquesa text-white" : "text-slate-500 hover:bg-crema"}`}>{e.nombre}</button></li>;
        })}</ol>}
      <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
        <div className="space-y-5">
          <section className="tarjeta p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold text-marino">Actividad y siguientes pasos</h3>
              <div className="flex gap-2"><button className="btn-sec text-sm" onClick={() => setDialogo("actividad")}>+ Registrar</button><button className="btn-turquesa text-sm" onClick={() => setDialogo("tarea")}>+ Tarea</button></div></div>
            <Historial actividades={o.actividades} onCambio={() => { cargar(); avisarContadores(); }} />
          </section>
        </div>
        <div className="space-y-5">
          <section className="tarjeta p-4 text-sm">
            <div className="mb-2 flex items-center justify-between"><h3 className="font-semibold text-marino">Contacto</h3><Link href={`/plataforma/ventas/contactos/${ct.id}`} className="text-xs font-semibold text-turquesa-700 underline">Ver ficha</Link></div>
            <p className="font-semibold">{ct.nombre}</p><p className="text-slate-600">{[ct.cargo, ct.despacho].filter(Boolean).join(" · ")}</p>
            {ct.email && <a className="block text-turquesa-700 underline" href={`mailto:${ct.email}`}>{ct.email}</a>}
            {ct.telefono && <p>{ct.telefono} {!ct.no_contactar && <a className="ml-2 text-xs font-semibold text-emerald-700 underline" target="_blank" rel="noopener noreferrer" href={`https://wa.me/${ct.telefono.replace(/\D/g, "").replace(/^(\d{10})$/, "52$1")}`}>WhatsApp</a>}</p>}
            {ct.no_contactar && <p className="mt-1 rounded bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">Pidió no ser contactado</p>}
            {(ct.ciudad || ct.abogados || ct.especialidad) && <p className="mt-1 text-xs text-slate-500">{[ct.ciudad, ct.abogados && `${ct.abogados} abogados`, ct.especialidad].filter(Boolean).join(" · ")}</p>}
          </section>
          <section className="tarjeta p-4 text-sm">
            <div className="mb-2 flex items-center justify-between"><h3 className="font-semibold text-marino">Cotizaciones</h3>
              <Link href={`/plataforma/comercial/cotizaciones/nueva?oportunidad=${o.id}`} className="text-xs font-semibold text-turquesa-700 underline">+ Cotizar</Link></div>
            {o.cotizaciones.length ? <ul className="divide-y divide-crema-200">{o.cotizaciones.map((c: any) => (
              <li key={c.id} className="flex items-center justify-between gap-2 py-2"><Link href={c.ruta} className="font-semibold text-marino hover:underline">{c.folio}</Link>
                <span className="text-xs">{c.paquete} · {dinero(c.total)}</span><EstadoCot estado={c.estado} texto={c.estado_texto} /></li>))}</ul>
              : <p className="text-slate-500">Aún sin cotización. Al enviarla, la oportunidad pasa a «Propuesta enviada»; al pagarse, a «Ganado».</p>}
          </section>
          {(o.paquete_interes || o.modulos_interes.length > 0) && <section className="tarjeta p-4 text-sm"><h3 className="mb-1 font-semibold text-marino">Interés</h3>
            <p>{o.paquete_interes}</p>{o.modulos_interes.length > 0 && <p className="text-slate-600">{o.modulos_interes.join(", ")}</p>}</section>}
        </div>
      </div>
      {(dialogo === "actividad" || dialogo === "tarea") && <FormActividad cat={cat} oportunidadId={o.id} tarea={dialogo === "tarea"} onCerrar={() => setDialogo("")} onListo={() => { setDialogo(""); cargar(); avisarContadores(); }} />}
      {dialogo === "editar" && <Editar o={o} cat={cat} onCerrar={() => setDialogo("")} onListo={(x) => { setO(x); setDialogo(""); setOk("Guardado."); }} />}
      {dialogo === "perder" && <Perder cat={cat} onCerrar={() => setDialogo("")} onGuardar={(motivo, nota) => etapa("perdido", { motivo, nota })} />}
      {dialogo === "ganar" && <Modal titulo="¡Oportunidad ganada!" onCerrar={() => setDialogo("")}>
        <p className="text-sm text-slate-600">Se cierra como ganada y se completan sus tareas pendientes. Si el despacho pagó una cotización, esto pasa solo. Para darle acceso, conviértalo desde la cotización pagada (superadministrador) o desde Solicitudes.</p>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={() => setDialogo("")}>Cancelar</button><button className="btn-turquesa" onClick={() => etapa("ganado")}>Marcar ganada</button></div>
      </Modal>}
    </VentasShell>
  );
}

function Perder({ cat, onCerrar, onGuardar }: { cat: any; onCerrar: () => void; onGuardar: (m: string, n: string | null) => void }) {
  const [motivo, setMotivo] = useState("");
  const [nota, setNota] = useState("");
  return (
    <Modal titulo="¿Por qué se perdió?" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onGuardar(motivo, nota || null); }}>
        <div className="grid gap-2 sm:grid-cols-2">{Object.entries(cat.motivos).map(([k, v]) => <label key={k} className={`flex cursor-pointer items-center gap-2 rounded-xl border p-2 text-sm ${motivo === k ? "border-turquesa bg-turquesa-50" : "border-crema-300"}`}>
          <input type="radio" name="motivo" checked={motivo === k} onChange={() => setMotivo(k)} /> {v as string}</label>)}</div>
        <label className="block"><span className="etiqueta">Nota (opcional)</span><input className="campo" value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Ej. Volver a buscar en enero" /></label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa" disabled={!motivo}>Marcar perdida</button></div>
      </form>
    </Modal>
  );
}

function Editar({ o, cat, onCerrar, onListo }: { o: any; cat: any; onCerrar: () => void; onListo: (x: any) => void }) {
  const [f, setF] = useState<any>({ titulo: o.titulo, valor_mensual: o.valor_mensual || "", paquete_interes: o.paquete_interes || "", cierre_estimado: o.cierre_estimado || "",
    propietario_id: o.propietario_id ? String(o.propietario_id) : "", campana_id: o.campana_id ? String(o.campana_id) : "", modulos: (o.modulos_interes || []).join(", ") });
  const [error, setError] = useState("");
  const c = (k: string) => ({ value: f[k] ?? "", onChange: (e: any) => setF({ ...f, [k]: e.target.value }) });
  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      onListo(await apiP.put(`/ventas/oportunidades/${o.id}`, { titulo: f.titulo, valor_mensual: f.valor_mensual || null, paquete_interes: f.paquete_interes || null,
        cierre_estimado: f.cierre_estimado || null, propietario_id: f.propietario_id ? Number(f.propietario_id) : null, campana_id: f.campana_id ? Number(f.campana_id) : null,
        modulos_interes: f.modulos.split(",").map((x: string) => x.trim()).filter(Boolean) }));
    } catch (x: any) { setError(x.message); }
  }
  return (
    <Modal titulo="Editar oportunidad" onCerrar={onCerrar} ancho="max-w-xl">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={guardar}>
        <label className="sm:col-span-2"><span className="etiqueta">Nombre</span><input className="campo" required minLength={2} {...c("titulo")} /></label>
        <label><span className="etiqueta">Valor mensual (sin IVA)</span><input className="campo" inputMode="decimal" value={f.valor_mensual} onChange={(e) => setF({ ...f, valor_mensual: e.target.value.replace(/[^\d.]/g, "") })} /></label>
        <label><span className="etiqueta">Cierre estimado</span><input className="campo" type="date" {...c("cierre_estimado")} /></label>
        <label><span className="etiqueta">Paquete de interés</span><select className="campo" {...c("paquete_interes")}><option value="">Sin definir</option>{cat.paquetes.map((p: string) => <option key={p}>{p}</option>)}</select></label>
        <label><span className="etiqueta">Responsable</span><select className="campo" {...c("propietario_id")}><option value="">Sin asignar</option>{cat.equipo.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
        <label><span className="etiqueta">Campaña</span><select className="campo" {...c("campana_id")}><option value="">Ninguna</option>{cat.campanas.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
        <label><span className="etiqueta">Módulos de interés</span><input className="campo" placeholder="Agenda, AFORE…" {...c("modulos")} /></label>
        <div className="sm:col-span-2"><Aviso>{error}</Aviso></div>
        <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}
