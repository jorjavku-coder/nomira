"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { COLOR_ETAPA, Copiar, Etiqueta, LeadsShell, ProximoPaso, enDias, tel, useCatalogosLeads } from "@/components/leads";
import { Aviso, ConfirmarEliminar, Modal } from "@/components/ui";
import { api, fecha, fechaHora } from "@/lib/api";

export default function Prospecto() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const cat = useCatalogosLeads();
  const [p, setP] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [modal, setModal] = useState<string | null>(null);
  const cargar = useCallback(() => api.get(`/leads/prospectos/${id}`).then(setP).catch((e) => setError(e.message)), [id]);
  useEffect(() => {
    cargar();
    if (new URLSearchParams(window.location.search).get("nuevo")) setOk("Prospecto registrado.");
  }, [cargar]);
  /** Ejecuta una acción; si responde con el prospecto actualizado, lo muestra. */
  async function accion(fn: () => Promise<any>, exito: string) {
    setError(""); setOk("");
    try {
      const r = await fn();
      if (r && r.id && r.historial) setP(r); else await cargar();
      setOk(exito);
      return r || true;
    } catch (e: any) {
      setError(e.detalle?.faltantes ? `${e.message} ${e.detalle.faltantes.join(" ")}` : e.message);
      return null;
    }
  }
  if (!p || !cat) return <LeadsShell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</LeadsShell>;
  const editor = cat.puede_editar && !p.anonimizado;
  const abierta = p.etapa_tipo === "abierta";
  return (
    <LeadsShell>
      <Link href="/leads/prospectos" className="text-sm font-semibold text-turquesa-700 hover:underline">← Prospectos</Link>
      <div className="mb-4 mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-marino">{p.nombre}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <Etiqueta clase={COLOR_ETAPA[p.etapa_tipo]}>{p.etapa}</Etiqueta>
            {p.borrador && <Etiqueta clase="bg-amber-100 text-amber-800">Borrador</Etiqueta>}
            <span>{p.canal_texto}{p.campana ? ` · ${p.campana}` : ""}</span>
            {p.materia && <span>· {p.materia}</span>}
            <span>· Registrado {fecha(p.creado_en)}</span>
          </div>
        </div>
        {editor && (
          <div className="flex flex-wrap gap-2">
            {abierta && <button className="btn-turquesa" onClick={() => setModal("consulta")}>Agendar consulta</button>}
            <button className="btn-sec" onClick={() => setModal("nota")}>Registrar seguimiento</button>
            <button className="btn-sec" onClick={() => setModal("etapa")}>Cambiar etapa</button>
            {abierta && <button className="btn-primario" onClick={() => setModal("contratar")}>Registrar contratación</button>}
          </div>)}
      </div>
      <div className="space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      {p.anonimizado && <Aviso tipo="info">Este prospecto fue anonimizado: sus datos personales se eliminaron y solo se conserva la información estadística.</Aviso>}
      {p.borrador && editor && <div className="mt-3"><Aviso tipo="alerta">Este registro es un borrador. Complete el nombre, un teléfono o correo y el próximo paso, y luego pulse <button className="font-semibold underline" onClick={() => accion(() => api.patch(`/leads/prospectos/${id}`, { borrador: false }), "Alta completada.")}>Completar alta</button>.</Aviso></div>}
      {p.etapa_tipo === "ganada" && (
        <section className="tarjeta mt-4 border-emerald-300 bg-emerald-50/50 p-4 text-sm">
          <b className="text-emerald-800">Cliente contratado</b> el {fecha(p.contratado_en)} · {p.servicio_contratado}
          {p.asunto_titulo && <> · Asunto: <b>{p.asunto_titulo}</b>{p.asunto_referencia ? ` (${p.asunto_referencia})` : ""}</>}
          {p.ev_asunto_id && <> · <Link className="font-semibold text-turquesa-700 underline" href={`/evidencia/${p.ev_asunto_id}`}>Abrir en Evidencia</Link></>}
          {p.af_caso_id && <> · <Link className="font-semibold text-turquesa-700 underline" href={`/afore/casos/${p.af_caso_id}`}>Abrir caso AFORE</Link></>}
        </section>)}
      {p.etapa_tipo === "perdida" && (
        <section className="tarjeta mt-4 p-4 text-sm text-slate-700"><b>No contratado</b> · Motivo: {p.motivo_perdida}{p.motivo_nota ? ` — ${p.motivo_nota}` : ""}</section>)}

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Pasos p={p} cat={cat} editor={editor && abierta} accion={accion} />
          <Conversacion p={p} cat={cat} editor={editor} accion={accion} />
          <section className="tarjeta p-5">
            <h2 className="mb-3 font-semibold text-marino">Historial</h2>
            <ol className="space-y-3 border-l-2 border-crema-300 pl-4 text-sm">
              {p.historial.map((h: any) => (
                <li key={h.id}><p className="text-xs text-slate-500">{fechaHora(h.creado_en)}{h.usuario ? ` · ${h.usuario}` : ""}</p>
                  <p className="whitespace-pre-line text-slate-800">{h.texto || <i className="text-slate-400">({h.tipo})</i>}</p></li>))}
            </ol>
          </section>
        </div>
        <div className="space-y-5">
          <Datos p={p} cat={cat} editor={editor} accion={accion} />
          <Consentimientos p={p} cat={cat} editor={editor} accion={accion} />
          <section className="tarjeta p-5 text-sm">
            <h2 className="mb-2 font-semibold text-marino">Origen</h2>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              <dt className="text-slate-500">Canal</dt><dd>{p.canal_texto}</dd>
              <dt className="text-slate-500">Campaña</dt><dd>{p.campana || "—"}</dd>
              <dt className="text-slate-500">Entrada</dt><dd>{{ manual: "Captura manual", formulario: "Formulario de contacto", whatsapp: "Mensaje de WhatsApp", meta: "Anuncio de Facebook o Instagram", integracion: "Otro sistema" }[p.entrada as string] || p.entrada}</dd>
              {p.origen_detalle?.utm && <><dt className="text-slate-500">Parámetros</dt><dd className="break-all text-xs">{Object.entries(p.origen_detalle.utm).map(([k, v]) => `${k}=${v}`).join(" · ")}</dd></>}
              {p.origen_detalle?.anuncio && <><dt className="text-slate-500">Anuncio</dt><dd className="text-xs">{Object.values(p.origen_detalle.anuncio).join(" · ")}</dd></>}
            </dl>
          </section>
          {cat.es_admin && (
            <section className="tarjeta p-5 text-sm">
              <h2 className="mb-2 font-semibold text-marino">Datos personales</h2>
              <p className="text-xs text-slate-500">Si la persona lo solicita o ya no es necesario conservar sus datos.</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {!p.anonimizado && <button className="btn-sec" onClick={() => setModal("anonimizar")}>Anonimizar</button>}
                <button className="btn-peligro" onClick={() => setModal("eliminar")}>Eliminar</button>
              </div>
            </section>)}
        </div>
      </div>

      {modal === "nota" && <ModalNota id={id} onCerrar={() => setModal(null)} accion={accion} />}
      {modal === "consulta" && <ModalAccion id={id} cat={cat} tipo="consulta" onCerrar={() => setModal(null)} accion={accion} />}
      {modal === "etapa" && <ModalEtapa p={p} cat={cat} onCerrar={() => setModal(null)} accion={accion} />}
      {modal === "contratar" && <ModalContratar p={p} cat={cat} onCerrar={() => setModal(null)} accion={accion} router={router} />}
      {modal === "anonimizar" && <ConfirmarEliminar titulo="Anonimizar prospecto" boton="Anonimizar" onCerrar={() => setModal(null)}
        onConfirmar={async () => { await api.post(`/leads/prospectos/${id}/anonimizar`); await cargar(); }}>
        Se borran su nombre, teléfono, correo, descripción, notas y mensajes. Se conservan canal, campaña, etapa y fechas para los reportes. No se puede deshacer.</ConfirmarEliminar>}
      {modal === "eliminar" && <ConfirmarEliminar titulo="Eliminar prospecto" onCerrar={() => setModal(null)}
        onConfirmar={async () => { await api.borrar(`/leads/prospectos/${id}`); router.replace("/leads/prospectos"); }}>
        Se elimina el prospecto con todo su historial y deja de contar en los reportes. No se puede deshacer.</ConfirmarEliminar>}
    </LeadsShell>
  );
}

function Pasos({ p, cat, editor, accion }: any) {
  const [nuevo, setNuevo] = useState(false);
  const [cerrando, setCerrando] = useState<any>(null);
  return (
    <section className="tarjeta p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-semibold text-marino">Próximo paso</h2>
        {editor && <button className="btn-sec text-xs" onClick={() => setNuevo(true)}>+ Agregar paso</button>}
      </div>
      {p.pendientes.length === 0 && (
        <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">{p.etapa_tipo === "abierta" ? "Este prospecto no tiene próximo paso. Defina uno para que no se quede sin seguimiento." : "Prospecto cerrado: no tiene pasos pendientes."}</p>)}
      <ul className="space-y-2">
        {p.pendientes.map((a: any) => (
          <li key={a.id} className={`rounded-xl border p-3 text-sm ${a.vencida ? "border-red-200 bg-red-50/50" : "border-crema-300"}`}>
            <ProximoPaso p={a} />
            <p className="text-xs text-slate-500">Responsable: {a.responsable || "—"}{a.recordatorio ? " · con recordatorio en la bandeja" : ""}</p>
            {editor && <div className="mt-2 flex flex-wrap gap-2">
              <button className="btn-turquesa px-3 py-1 text-xs" onClick={() => setCerrando(a)}>Marcar como hecho</button>
              <button className="btn-sec px-3 py-1 text-xs" onClick={() => accion(() => api.post(`/leads/acciones/${a.id}/cancelar`), "Paso cancelado.")}>Cancelar</button>
            </div>}
          </li>))}
      </ul>
      {p.acciones.length > 0 && (
        <details className="mt-3 text-sm"><summary className="cursor-pointer text-xs font-semibold text-slate-500">Pasos anteriores ({p.acciones.length})</summary>
          <ul className="mt-2 space-y-1 text-xs text-slate-600">
            {p.acciones.map((a: any) => <li key={a.id}>{a.cancelada ? "✕" : "✓"} {a.tipo_texto} · {fecha(a.fecha)}{a.resultado ? ` — ${a.resultado}` : ""}{a.completada_por ? ` (${a.completada_por})` : ""}</li>)}
          </ul></details>)}
      {nuevo && <ModalAccion id={p.id} cat={cat} onCerrar={() => setNuevo(false)} accion={accion} />}
      {cerrando && <ModalHecho a={cerrando} cat={cat} onCerrar={() => setCerrando(null)} accion={accion} />}
    </section>
  );
}

function CamposPaso({ v, set, cat, tipoFijo }: any) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {!tipoFijo && <label><span className="etiqueta">Qué</span>
        <select className="campo" value={v.tipo} onChange={(e) => set({ ...v, tipo: e.target.value })}>
          {Object.entries(cat.tipos_accion).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>}
      <label><span className="etiqueta">Fecha</span><input className="campo" type="date" required value={v.fecha} onChange={(e) => set({ ...v, fecha: e.target.value })} /></label>
      <label><span className="etiqueta">Hora (opcional)</span><input className="campo" type="time" value={v.hora} onChange={(e) => set({ ...v, hora: e.target.value })} /></label>
      <label><span className="etiqueta">Responsable</span>
        <select className="campo" value={v.responsable_id} onChange={(e) => set({ ...v, responsable_id: e.target.value })}>
          <option value="">El responsable del prospecto</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
      <label className="sm:col-span-2"><span className="etiqueta">Detalle</span><input className="campo" maxLength={300} value={v.descripcion} onChange={(e) => set({ ...v, descripcion: e.target.value })} /></label>
      <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={v.recordatorio} onChange={(e) => set({ ...v, recordatorio: e.target.checked })} />
        Recordármelo en la bandeja (no envía nada al prospecto)</label>
    </div>
  );
}
const pasoVacio = (tipo = "llamada", dias = 1) => ({ tipo, fecha: enDias(dias), hora: "", responsable_id: "", descripcion: "", recordatorio: true });
const cuerpoPaso = (v: any) => ({ tipo: v.tipo, fecha: v.fecha, hora: v.hora || null, descripcion: v.descripcion || null,
  responsable_id: v.responsable_id ? Number(v.responsable_id) : null, recordatorio: v.recordatorio });

function ModalAccion({ id, cat, tipo, onCerrar, accion }: any) {
  const [v, setV] = useState<any>(pasoVacio(tipo || "llamada", tipo === "consulta" ? 2 : 1));
  return (
    <Modal titulo={tipo === "consulta" ? "Agendar consulta" : "Agregar próximo paso"} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); if (await accion(() => api.post(`/leads/prospectos/${id}/acciones`, cuerpoPaso(v)), tipo === "consulta" ? "Consulta agendada." : "Paso agregado.")) onCerrar(); }}>
        <CamposPaso v={v} set={setV} cat={cat} tipoFijo={tipo === "consulta"} />
        {tipo === "consulta" && <p className="text-xs text-slate-500">Si quiere, cambie también la etapa a «Consulta agendada».</p>}
        <div className="flex justify-end"><button className="btn-turquesa">{tipo === "consulta" ? "Agendar consulta" : "Guardar paso"}</button></div>
      </form>
    </Modal>
  );
}

function ModalHecho({ a, cat, onCerrar, accion }: any) {
  const [resultado, setResultado] = useState("");
  const [sig, setSig] = useState(true);
  const [v, setV] = useState<any>(pasoVacio("seguimiento", 2));
  return (
    <Modal titulo={`Hecho: ${a.tipo_texto}`} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        if (await accion(() => api.post(`/leads/acciones/${a.id}/completar`, { resultado: resultado || null, siguiente: sig ? cuerpoPaso(v) : null }), "Paso registrado.")) onCerrar();
      }}>
        <label className="block"><span className="etiqueta">¿Qué resultó?</span>
          <textarea className="campo" rows={2} maxLength={500} value={resultado} onChange={(e) => setResultado(e.target.value)} placeholder="Ej. Le interesa, pide cita el jueves" /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-turquesa" checked={sig} onChange={(e) => setSig(e.target.checked)} />Definir el siguiente paso ahora</label>
        {sig && <CamposPaso v={v} set={setV} cat={cat} />}
        <div className="flex justify-end"><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

function ModalNota({ id, onCerrar, accion }: any) {
  const [t, setT] = useState("");
  return (
    <Modal titulo="Registrar seguimiento" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); if (await accion(() => api.post(`/leads/prospectos/${id}/notas`, { texto: t }), "Seguimiento registrado.")) onCerrar(); }}>
        <textarea className="campo" rows={4} required maxLength={4000} autoFocus value={t} onChange={(e) => setT(e.target.value)} placeholder="Qué pasó: llamada, mensaje, acuerdo…" />
        <div className="flex justify-end"><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

function ModalEtapa({ p, cat, onCerrar, accion }: any) {
  const opciones = cat.etapas.filter((e: any) => e.tipo !== "ganada");
  const [etapa, setEtapa] = useState(String(p.etapa_tipo === "ganada" ? opciones[0].id : p.etapa_id));
  const [nota, setNota] = useState("");
  const [motivo, setMotivo] = useState("");
  const [motivoNota, setMotivoNota] = useState("");
  const perdida = cat.etapas.find((e: any) => String(e.id) === etapa)?.tipo === "perdida";
  return (
    <Modal titulo="Cambiar etapa" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        if (await accion(() => api.post(`/leads/prospectos/${p.id}/etapa`, { etapa_id: Number(etapa), nota: nota || null, motivo: motivo || null, motivo_nota: motivoNota || null }), "Etapa actualizada.")) onCerrar();
      }}>
        <div className="flex flex-wrap gap-2">
          {opciones.map((e: any) => (
            <label key={e.id} className={`cursor-pointer rounded-xl border px-3 py-2 text-sm ${String(e.id) === etapa ? "border-turquesa bg-turquesa-50 font-semibold text-marino" : "border-crema-300"}`}>
              <input type="radio" className="sr-only" name="etapa" value={e.id} checked={String(e.id) === etapa} onChange={() => setEtapa(String(e.id))} />{e.nombre}</label>))}
        </div>
        {perdida && <>
          <label className="block"><span className="etiqueta">Motivo</span>
            <select className="campo" required value={motivo} onChange={(e) => setMotivo(e.target.value)}>
              <option value="">Elija un motivo</option>{cat.motivos.map((x: string) => <option key={x}>{x}</option>)}</select></label>
          <input className="campo" maxLength={500} placeholder="Detalle del motivo (opcional)" value={motivoNota} onChange={(e) => setMotivoNota(e.target.value)} />
        </>}
        <input className="campo" maxLength={500} placeholder="Nota breve (opcional)" value={nota} onChange={(e) => setNota(e.target.value)} />
        <p className="text-xs text-slate-500">Para «Contratado» use «Registrar contratación».</p>
        <div className="flex justify-end"><button className="btn-turquesa">Guardar</button></div>
      </form>
    </Modal>
  );
}

function ModalContratar({ p, cat, onCerrar, accion, router }: any) {
  const [d, setD] = useState<any>({ servicio: p.materia || "", asunto_titulo: "", referencia: "", nota: "", crear_en: "" });
  const mods: string[] = cat.modulos || [];
  return (
    <Modal titulo="Registrar contratación" onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        const r = await accion(() => api.post(`/leads/prospectos/${p.id}/contratar`, { ...d, crear_en: d.crear_en || null, asunto_titulo: d.asunto_titulo || null,
          referencia: d.referencia || null, nota: d.nota || null }), "Contratación registrada.");
        if (r) { onCerrar(); if (r.destino) router.push(r.destino); }
      }}>
        <p className="text-sm text-slate-600">Se usan los datos que ya tiene el prospecto: no hay que capturarlos de nuevo.</p>
        <label className="block"><span className="etiqueta">Servicio contratado</span><input className="campo" required minLength={2} value={d.servicio} onChange={(e) => setD({ ...d, servicio: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Nombre del asunto (opcional)</span><input className="campo" placeholder={`${d.servicio || "Servicio"} — ${p.nombre}`} value={d.asunto_titulo} onChange={(e) => setD({ ...d, asunto_titulo: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Referencia interna (opcional)</span><input className="campo" maxLength={80} value={d.referencia} onChange={(e) => setD({ ...d, referencia: e.target.value })} /></label>
        {(mods.includes("evidencia") || mods.includes("afore")) && (
          <fieldset className="rounded-xl border border-crema-300 p-3 text-sm">
            <legend className="etiqueta px-1">Abrir también el asunto en</legend>
            <label className="mr-4"><input type="radio" className="mr-1" checked={!d.crear_en} onChange={() => setD({ ...d, crear_en: "" })} />Solo registrar aquí</label>
            {mods.includes("evidencia") && <label className="mr-4"><input type="radio" className="mr-1" checked={d.crear_en === "evidencia"} onChange={() => setD({ ...d, crear_en: "evidencia" })} />Nomira Evidencia</label>}
            {mods.includes("afore") && <label><input type="radio" className="mr-1" checked={d.crear_en === "afore"} onChange={() => setD({ ...d, crear_en: "afore" })} />Nomira AFORE (borrador)</label>}
          </fieldset>)}
        <textarea className="campo" rows={2} maxLength={1000} placeholder="Nota (opcional)" value={d.nota} onChange={(e) => setD({ ...d, nota: e.target.value })} />
        <div className="flex justify-end"><button className="btn-primario">Registrar contratación</button></div>
      </form>
    </Modal>
  );
}

function Conversacion({ p, cat, editor, accion }: any) {
  const [canal, setCanal] = useState<"whatsapp" | "correo">(p.telefono ? "whatsapp" : "correo");
  const [texto, setTexto] = useState("");
  const wa = p.whatsapp;
  const enlace = p.telefono && wa.enlace_directo ? `https://wa.me/${String(p.telefono).replace(/\D/g, "")}?text=${encodeURIComponent(texto)}` : null;
  const enviar = (modo: string) => accion(() => api.post(`/leads/prospectos/${p.id}/mensajes`, { canal, texto, modo }),
    modo === "manual" ? "Respuesta registrada." : "Mensaje enviado.").then((r: any) => { if (r) setTexto(""); });
  return (
    <section className="tarjeta p-5">
      <h2 className="mb-1 font-semibold text-marino">Conversación</h2>
      <p className="mb-3 text-xs text-slate-500">Cada mensaje lo revisa y envía una persona. Nomira no responde solo ni da asesoría.</p>
      <div className="max-h-80 space-y-2 overflow-y-auto">
        {p.mensajes.length === 0 && <p className="text-sm text-slate-400">Sin mensajes todavía.</p>}
        {p.mensajes.map((x: any) => (
          <div key={x.id} className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${x.direccion === "entrante" ? "bg-crema-200" : "ml-auto bg-turquesa-50"}`}>
            <p className="whitespace-pre-line">{x.texto}</p>
            <p className="mt-1 text-[11px] text-slate-500">{x.canal === "whatsapp" ? "WhatsApp" : "Correo"} · {fechaHora(x.creado_en)} · {x.estado_texto}{x.creado_por ? ` · ${x.creado_por}` : ""}</p>
            {x.error && <p className="text-[11px] text-red-700">{x.error}</p>}
          </div>))}
      </div>
      {editor && (
        <div className="mt-3 space-y-2 border-t border-crema-300 pt-3">
          <div className="flex gap-2 text-sm">
            {(["whatsapp", "correo"] as const).map((c) => (
              <button key={c} type="button" onClick={() => setCanal(c)} className={`rounded-full px-3 py-1 font-semibold ${canal === c ? "bg-marino text-white" : "bg-crema-200 text-marino"}`}>{c === "whatsapp" ? "WhatsApp" : "Correo"}</button>))}
          </div>
          {!p.consiente[canal] && <p className="text-xs text-amber-800">Sin consentimiento registrado para {canal === "whatsapp" ? "WhatsApp" : "correo"}: regístrelo antes de escribirle (sección Consentimientos).</p>}
          <textarea className="campo" rows={3} maxLength={4000} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Escriba la respuesta" />
          <div className="flex flex-wrap gap-2">
            {canal === "whatsapp" && <>
              {wa.conectado && wa.ventana_abierta && <button className="btn-turquesa" disabled={!texto.trim()} onClick={() => enviar("enviar")}>Enviar por WhatsApp</button>}
              {wa.conectado && !wa.ventana_abierta && wa.plantilla && <button className="btn-turquesa" onClick={() => enviar("plantilla")}>Enviar plantilla «{wa.plantilla}»</button>}
              {enlace && <a className="btn-sec" href={enlace} target="_blank" rel="noopener noreferrer">Abrir en WhatsApp</a>}
            </>}
            {canal === "correo" && p.email && p.correo_configurado && <button className="btn-turquesa" disabled={!texto.trim()} onClick={() => enviar("enviar")}>Enviar correo</button>}
            {texto.trim() && <Copiar texto={texto} etiqueta="Copiar texto" />}
            <button className="btn-sec" disabled={!texto.trim()} onClick={() => enviar("manual")}>Ya lo envié (registrar)</button>
          </div>
          {canal === "whatsapp" && !wa.conectado && <p className="text-xs text-slate-500">WhatsApp Business Platform no está conectado: use «Abrir en WhatsApp» y luego «Ya lo envié» para dejarlo registrado.</p>}
          {canal === "whatsapp" && wa.conectado && !wa.ventana_abierta && <p className="text-xs text-slate-500">Pasaron más de 24 h desde su último mensaje: WhatsApp solo permite escribirle con una plantilla aprobada por Meta.</p>}
        </div>)}
    </section>
  );
}

function Datos({ p, cat, editor, accion }: any) {
  const [ed, setEd] = useState(false);
  const [d, setD] = useState<any>({});
  const abrir = () => { setD({ nombre: p.nombre, telefono: p.telefono || "", email: p.email || "", ciudad: p.ciudad || "", materia: p.materia || "", descripcion: p.descripcion || "",
    canal: p.canal, campana_id: p.campana_id ? String(p.campana_id) : "", preferencia_contacto: p.preferencia_contacto, responsable_id: p.responsable_id ? String(p.responsable_id) : "" }); setEd(true); };
  if (ed) return (
    <section className="tarjeta p-5">
      <h2 className="mb-3 font-semibold text-marino">Datos</h2>
      <form className="grid gap-2" onSubmit={async (e) => {
        e.preventDefault();
        const r = await accion(() => api.patch(`/leads/prospectos/${p.id}`, { ...d, campana_id: d.campana_id ? Number(d.campana_id) : null, responsable_id: d.responsable_id ? Number(d.responsable_id) : null }), "Datos guardados.");
        if (r) setEd(false);
      }}>
        {[["nombre", "Nombre"], ["telefono", "Teléfono"], ["email", "Correo"], ["ciudad", "Ciudad"]].map(([k, t]) => (
          <label key={k}><span className="etiqueta">{t}</span><input className="campo" value={d[k]} onChange={(e) => setD({ ...d, [k]: e.target.value })} /></label>))}
        <label><span className="etiqueta">Materia</span><input className="campo" list="ld-m2" value={d.materia} onChange={(e) => setD({ ...d, materia: e.target.value })} />
          <datalist id="ld-m2">{cat.materias.map((x: string) => <option key={x} value={x} />)}</datalist></label>
        <label><span className="etiqueta">Qué necesita</span><textarea className="campo" rows={3} value={d.descripcion} onChange={(e) => setD({ ...d, descripcion: e.target.value })} /></label>
        <label><span className="etiqueta">Canal</span><select className="campo" value={d.canal} onChange={(e) => setD({ ...d, canal: e.target.value })}>
          {Object.entries(cat.canales).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label><span className="etiqueta">Campaña</span><select className="campo" value={d.campana_id} onChange={(e) => setD({ ...d, campana_id: e.target.value })}>
          <option value="">Ninguna</option>{cat.campanas.map((c: any) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></label>
        <label><span className="etiqueta">Responsable</span><select className="campo" value={d.responsable_id} onChange={(e) => setD({ ...d, responsable_id: e.target.value })}>
          <option value="">Sin asignar</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
        <label><span className="etiqueta">Prefiere contacto por</span><select className="campo" value={d.preferencia_contacto} onChange={(e) => setD({ ...d, preferencia_contacto: e.target.value })}>
          {Object.entries(cat.preferencias).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select></label>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={() => setEd(false)}>Cancelar</button><button className="btn-turquesa">Guardar</button></div>
      </form>
    </section>
  );
  return (
    <section className="tarjeta p-5 text-sm">
      <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold text-marino">Datos</h2>{editor && <button className="btn-sec text-xs" onClick={abrir}>Editar</button>}</div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-slate-500">Teléfono</dt><dd>{tel(p.telefono)}</dd>
        <dt className="text-slate-500">Correo</dt><dd className="break-all">{p.email || "—"}</dd>
        <dt className="text-slate-500">Ciudad</dt><dd>{p.ciudad || "—"}</dd>
        <dt className="text-slate-500">Lo atiende</dt><dd>{p.responsable || "Sin asignar"}</dd>
        <dt className="text-slate-500">Prefiere</dt><dd>{cat.preferencias[p.preferencia_contacto]}</dd>
      </dl>
      {p.descripcion && <p className="mt-3 whitespace-pre-line rounded-xl bg-crema/60 p-3 text-slate-700">{p.descripcion}</p>}
      {!cat.ve_datos && <p className="mt-2 text-xs text-slate-500">Su rol ve los datos de contacto enmascarados.</p>}
    </section>
  );
}

function Consentimientos({ p, cat, editor, accion }: any) {
  const [canal, setCanal] = useState("whatsapp");
  const [medio, setMedio] = useState("verbal");
  return (
    <section className="tarjeta p-5 text-sm">
      <h2 className="mb-2 font-semibold text-marino">Consentimientos</h2>
      <ul className="space-y-1.5">
        {p.consentimientos.length === 0 && <li className="text-slate-400">Sin consentimientos registrados.</li>}
        {p.consentimientos.map((c: any) => (
          <li key={c.id} className="flex flex-wrap items-center justify-between gap-2">
            <span><b>{c.canal_texto}</b> · {c.medio_texto} · {fecha(c.otorgado_en)}{c.revocado_en ? <span className="text-red-700"> · revocado {fecha(c.revocado_en)}</span> : ""}</span>
            {editor && !c.revocado_en && <button className="text-xs font-semibold text-red-700 hover:underline" onClick={() => accion(() => api.post(`/leads/consentimientos/${c.id}/revocar`, { medio: "verbal" }), "Consentimiento revocado.")}>Revocar</button>}
          </li>))}
      </ul>
      {editor && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-crema-300 pt-3">
          <select className="campo w-auto" value={canal} onChange={(e) => setCanal(e.target.value)} aria-label="Canal">
            {Object.entries(cat.canales_consentimiento).map(([k, t]: any) => <option key={k} value={k}>{t}</option>)}</select>
          <select className="campo w-auto" value={medio} onChange={(e) => setMedio(e.target.value)} aria-label="Cómo lo autorizó">
            {["verbal", "escrito", "mensaje"].map((k) => <option key={k} value={k}>{cat.medios_consentimiento[k]}</option>)}</select>
          <button className="btn-sec" onClick={() => accion(() => api.post(`/leads/prospectos/${p.id}/consentimientos`, { canal, medio }), "Consentimiento registrado.")}>Registrar</button>
        </div>)}
    </section>
  );
}

