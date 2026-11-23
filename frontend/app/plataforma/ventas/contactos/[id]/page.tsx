"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Calificar, Descartar, dinero, Etapa, FormActividad, FormContacto, FormOportunidad, Historial, useCatalogosVentas, VentasShell } from "@/components/ventas";
import { Aviso, ConfirmarEliminar } from "@/components/ui";
import { apiP } from "@/lib/plataforma";

export default function Contacto() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const cat = useCatalogosVentas();
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [dialogo, setDialogo] = useState<"" | "editar" | "oportunidad" | "actividad" | "tarea" | "borrar" | "calificar" | "descartar">("");
  const cargar = useCallback(() => apiP.get(`/ventas/contactos/${id}`).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  if (!c || !cat) return <VentasShell><Aviso>{error}</Aviso></VentasShell>;
  return (
    <VentasShell>
      {c.fase === "sql" ? <Link href="/plataforma/ventas/contactos" className="text-sm font-semibold text-turquesa-700">← Contactos (SQL)</Link>
        : <Link href="/plataforma/ventas/leads" className="text-sm font-semibold text-turquesa-700">← Leads (MQL)</Link>}
      <div className="mb-4 mt-2 flex flex-wrap items-start justify-between gap-3">
        <div><div className="flex items-center gap-2"><h2 className="text-2xl font-extrabold text-marino">{c.nombre}</h2>
            <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${c.fase === "sql" ? "bg-emerald-100 text-emerald-800" : c.fase === "mql" ? "bg-sky-100 text-sky-800" : "bg-slate-200 text-slate-600"}`}>
              {c.fase === "sql" ? "SQL · contacto" : c.fase === "mql" ? "MQL · lead" : `Descartado: ${c.motivo_descarte_texto}`}</span></div>
          {c.fase === "sql" && c.calificado_en && <p className="text-xs text-emerald-700">Calificado {new Date(c.calificado_en).toLocaleDateString("es-MX")} · {c.calificacion_texto}</p>}
          <p className="text-sm text-slate-600">{[c.cargo, c.despacho, c.ciudad].filter(Boolean).join(" · ")}</p>
          <p className="text-sm">{c.email && <a className="text-turquesa-700 underline" href={`mailto:${c.email}`}>{c.email}</a>}{c.telefono && ` · ${c.telefono}`}</p>
          <p className="text-xs text-slate-500">{c.origen_texto}{c.campana ? ` · ${c.campana}` : ""} · Responsable: {c.propietario || "sin asignar"}</p>
          {c.organizacion && <p className="mt-1 text-sm">Cliente de Nomira: <Link className="font-semibold text-turquesa-700 underline" href={`/plataforma/clientes/${c.organizacion.id}`}>{c.organizacion.nombre}</Link></p>}
          {c.no_contactar && <p className="mt-1 inline-block rounded bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">Pidió no ser contactado</p>}</div>
        <div className="flex flex-wrap gap-2"><button className="btn-sec" onClick={() => setDialogo("editar")}>Editar</button>
          {cat.es_super && <button className="btn-sec text-red-700" onClick={() => setDialogo("borrar")}>Borrar</button>}
          {c.fase === "sql" ? <button className="btn-turquesa" onClick={() => setDialogo("oportunidad")}>+ Oportunidad</button>
            : c.fase === "mql" ? <><button className="btn-sec" onClick={() => setDialogo("descartar")}>Descartar</button><button className="btn-turquesa" onClick={() => setDialogo("calificar")}>Pasar a SQL</button></>
            : <button className="btn-sec" onClick={async () => { try { setC(await apiP.post(`/ventas/leads/${c.id}/reactivar`)); } catch (e: any) { setError(e.message); } }}>Reactivar lead</button>}</div>
      </div>
      <Aviso>{error}</Aviso>
      <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
        <section className="tarjeta p-4">
          <div className="mb-3 flex items-center justify-between"><h3 className="font-semibold text-marino">Historial</h3>
            <div className="flex gap-2"><button className="btn-sec text-sm" onClick={() => setDialogo("actividad")}>{c.fase === "sql" ? "+ Registrar" : "+ Intento o actividad"}</button><button className="btn-turquesa text-sm" onClick={() => setDialogo("tarea")}>+ Tarea</button></div></div>
          <Historial actividades={c.actividades} onCambio={cargar} />
        </section>
        <div className="space-y-5">
          <section className="tarjeta p-4 text-sm"><h3 className="mb-2 font-semibold text-marino">Oportunidades</h3>
            {c.oportunidades.length ? <ul className="divide-y divide-crema-200">{c.oportunidades.map((o: any) => (
              <li key={o.id} className="py-2"><Link href={`/plataforma/ventas/oportunidades/${o.id}`} className="font-semibold text-marino hover:underline">{o.titulo}</Link>
                <p className="flex items-center gap-2 text-xs"><Etapa etapa={o.etapa} texto={o.etapa_texto} /> {dinero(o.valor_mensual)}/mes</p></li>))}</ul>
              : <p className="text-slate-500">Sin oportunidades.</p>}</section>
          {(c.notas || c.etiquetas.length > 0 || c.abogados || c.especialidad) && <section className="tarjeta p-4 text-sm"><h3 className="mb-1 font-semibold text-marino">Notas</h3>
            {(c.abogados || c.especialidad) && <p className="text-slate-600">{[c.abogados && `${c.abogados} abogados`, c.especialidad].filter(Boolean).join(" · ")}</p>}
            {c.notas && <p className="whitespace-pre-line">{c.notas}</p>}
            {c.etiquetas.map((e: string) => <span key={e} className="mr-1 rounded-full bg-crema px-2 py-0.5 text-xs">{e}</span>)}</section>}
        </div>
      </div>
      {dialogo === "editar" && <FormContacto cat={cat} contacto={c} onCerrar={() => setDialogo("")} onListo={(x) => { setC(x); setDialogo(""); }} />}
      {dialogo === "oportunidad" && <FormOportunidad cat={cat} contacto={c} onCerrar={() => setDialogo("")} onListo={(o) => router.push(`/plataforma/ventas/oportunidades/${o.id}`)} />}
      {(dialogo === "actividad" || dialogo === "tarea") && <FormActividad cat={cat} contactoId={c.id} esLead={c.fase !== "sql"} tarea={dialogo === "tarea"} onCerrar={() => setDialogo("")} onListo={() => { setDialogo(""); cargar(); }} />}
      {dialogo === "calificar" && <Calificar cat={cat} lead={c} onCerrar={() => setDialogo("")} onListo={(r) => router.push(`/plataforma/ventas/oportunidades/${r.oportunidad_id}`)} />}
      {dialogo === "descartar" && <Descartar cat={cat} lead={c} onCerrar={() => setDialogo("")} onListo={() => { setDialogo(""); cargar(); }} />}
      {dialogo === "borrar" && <ConfirmarEliminar titulo={`Borrar a ${c.nombre}`} onCerrar={() => setDialogo("")}
        onConfirmar={async () => { try { await apiP.borrar(`/ventas/contactos/${c.id}`); router.push(c.fase === "sql" ? "/plataforma/ventas/contactos" : "/plataforma/ventas/leads"); } catch (e: any) { setError(e.message); setDialogo(""); } }}>
        Se borran el contacto, sus oportunidades y su historial (por ejemplo, si pidió que borremos sus datos). Las cotizaciones se conservan.</ConfirmarEliminar>}
    </VentasShell>
  );
}
