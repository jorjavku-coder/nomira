"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { EditorEtapas, ESTADO_ETAPA, fechaCorta, fechaHora, LineaTiempo } from "@/components/connect";
import { Aviso, ConfirmarEliminar, Modal } from "@/components/ui";
import { api } from "@/lib/api";

const ACCIONES: [string, string][] = [["actual", "Es la etapa actual"], ["completada", "Completada"], ["atencion", "Requiere al cliente"],
  ["incidencia", "Incidencia"], ["suspendida", "Suspendida"], ["pendiente", "Próxima"], ["omitida", "No aplica"]];

/** Seguimiento de un asunto: mover etapas, notas públicas e internas, publicación, enlace y mensaje para el cliente. */
export default function Seguimiento() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [s, setS] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [sel, setSel] = useState<any>(null);
  const [notas, setNotas] = useState({ publica: "", interna: "", avisar: true });
  const [editarEtapas, setEditarEtapas] = useState<any[] | null>(null);
  const [borrar, setBorrar] = useState(false);
  const [mov, setMov] = useState({ fecha: new Date().toISOString().slice(0, 10), texto: "" });
  const [msg, setMsg] = useState({ mensaje: "", accion: "" });
  const cargar = useCallback(() => api.get(`/connect/seguimientos/${id}`).then((x) => {
    setS(x); setMsg({ mensaje: x.mensaje || "", accion: x.accion_cliente || "" });
  }).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  const elegir = (e: any) => { setSel(e); setNotas({ publica: e.nota || "", interna: e.nota_interna || "", avisar: true }); };
  const hecho = (x: any, t: string) => { setS(x); setOk(t); setError(""); setTimeout(() => setOk(""), 3500); };
  const accion = async (estado: string) => {
    try {
      const x = await api.post(`/connect/seguimientos/${id}/etapa`, { etapa_id: sel.id, estado, nota_publica: notas.publica, nota_interna: notas.interna, avisar: notas.avisar });
      hecho(x, "Seguimiento actualizado."); setSel(x.etapas.find((e: any) => e.id === sel.id));
    } catch (e: any) { setError(e.message); }
  };
  const ajustar = async (cambios: any, t = "Guardado.") => { try { hecho(await api.put(`/connect/seguimientos/${id}`, cambios), t); } catch (e: any) { setError(e.message); } };
  if (!s) return <Shell><Aviso>{error}</Aviso><p className="text-sm text-slate-500">{error ? "" : "Cargando…"}</p></Shell>;
  return (
    <Shell>
      <Link href="/connect" className="text-sm font-semibold text-turquesa-700">← Nomira Connect</Link>
      <div className="mb-4 mt-2 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-extrabold text-marino">{s.asunto}</h1>
          <p className="text-sm text-slate-500">{[s.numero, s.cliente?.nombre || "Sin cliente vinculado", s.abogado && `Responsable: ${s.abogado}`, s.plantilla].filter(Boolean).join(" · ")}</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-3 py-1 text-xs font-bold ${s.visible_cliente ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{s.visible_cliente ? "● Publicado: su cliente lo ve" : "Borrador: su cliente aún no lo ve"}</span>
          <button className={s.visible_cliente ? "btn-sec" : "btn-turquesa"} onClick={() => ajustar({ visible_cliente: !s.visible_cliente }, s.visible_cliente ? "Ya no se muestra al cliente." : "Publicado: su cliente ya lo puede ver.")}>
            {s.visible_cliente ? "Ocultar al cliente" : "Publicar al cliente"}</button></div>
      </div>
      <Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
      {!s.cliente && <VincularCliente onElegir={(cid) => ajustar({ cliente_id: cid }, "Cliente vinculado.")} />}
      <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
        <div className="space-y-5">
          <section className="tarjeta p-5">
            <div className="mb-4 flex items-center justify-between"><h2 className="font-bold text-marino">Etapas</h2>
              <button className="btn-sec text-xs" onClick={() => setEditarEtapas(s.etapas.map((e: any) => ({ id: e.id, nombre: e.nombre, explicacion: e.explicacion || "", opcional: e.opcional })))}>Personalizar etapas</button></div>
            <p className="mb-4 text-xs text-slate-500">Toque una etapa para moverla. Lo que marque se refleja en el portal del cliente{s.visible_cliente ? "" : " cuando lo publique"}.</p>
            <LineaTiempo etapas={s.etapas} onElegir={elegir} elegida={sel?.id} />
          </section>
          <section className="tarjeta p-5"><h2 className="mb-3 font-bold text-marino">Historial</h2>
            <ul className="space-y-2">{s.historial.map((h: any, i: number) => (
              <li key={i} className="flex gap-3 text-sm"><span className="w-28 shrink-0 text-xs text-slate-400">{fechaHora(h.fecha)}</span>
                <span className="min-w-0"><b className="text-marino">{h.titulo}</b>{h.detalle && <span className="block text-slate-600">{h.detalle}</span>}
                  <span className="text-[11px] text-slate-400">{h.por && `${h.por} · `}{h.visible ? "Visible para el cliente" : "Solo el despacho"}</span></span></li>))}</ul>
          </section>
        </div>
        <div className="space-y-5">
          {sel && <section className="tarjeta border-turquesa/40 p-5 ring-2 ring-turquesa/20">
            <div className="flex items-start justify-between gap-2"><div><p className="text-xs font-bold uppercase tracking-wider text-turquesa-700">Etapa seleccionada</p>
              <h2 className="text-lg font-bold text-marino">{sel.nombre}</h2>
              <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${ESTADO_ETAPA[sel.estado].chip}`}>{ESTADO_ETAPA[sel.estado].texto}</span></div>
              <button className="text-slate-400" onClick={() => setSel(null)} aria-label="Cerrar">✕</button></div>
            <label className="mt-3 block"><span className="etiqueta">Nota para el cliente (la verá)</span>
              <textarea className="campo" rows={2} maxLength={500} value={notas.publica} onChange={(e) => setNotas({ ...notas, publica: e.target.value })} placeholder="Ej. Presentamos su demanda; ahora esperamos que el tribunal la admita." /></label>
            <label className="mt-3 block"><span className="etiqueta">🔒 Nota interna (solo su despacho, nunca la ve el cliente)</span>
              <textarea className="campo bg-amber-50/40" rows={2} maxLength={1000} value={notas.interna} onChange={(e) => setNotas({ ...notas, interna: e.target.value })} /></label>
            <label className="mt-2 flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={notas.avisar} onChange={(e) => setNotas({ ...notas, avisar: e.target.checked })} /> Registrar el cambio en el historial que ve el cliente</label>
            <div className="mt-3 flex flex-wrap gap-2">{ACCIONES.map(([v, t]) => (
              <button key={v} onClick={() => accion(v)} className={v === "actual" ? "btn-turquesa text-sm" : `rounded-xl border px-3 py-1.5 text-xs font-semibold ${ESTADO_ETAPA[v].chip}`}>{t}</button>))}</div>
          </section>}
          <section className="tarjeta p-5"><h2 className="mb-1 font-bold text-marino">Para su cliente</h2>
            <label className="mt-2 block"><span className="etiqueta">Mensaje de su abogado</span>
              <textarea className="campo" rows={2} maxLength={1000} value={msg.mensaje} onChange={(e) => setMsg({ ...msg, mensaje: e.target.value })} placeholder="Ej. Todo va en orden. Le avisaremos en cuanto haya una novedad." /></label>
            <label className="mt-2 block"><span className="etiqueta">Lo que necesitamos de usted</span>
              <textarea className="campo" rows={2} maxLength={500} value={msg.accion} onChange={(e) => setMsg({ ...msg, accion: e.target.value })} placeholder="Ej. Traer su credencial del INE original el lunes. Si no hay nada, déjelo vacío." /></label>
            <button className="btn-sec mt-2 text-sm" onClick={() => ajustar({ mensaje_publico: msg.mensaje, accion_cliente: msg.accion })}>Guardar</button>
          </section>
          <section className="tarjeta p-5"><h2 className="font-bold text-marino">Movimientos y revisión</h2>
            <p className="mt-1 text-xs text-slate-500">El cliente ve por separado la <b>fecha del último movimiento judicial</b> y la <b>fecha en que su despacho revisó</b> el expediente.</p>
            <div className="mt-3 rounded-xl bg-crema/60 p-3 text-sm">
              <p><b className="text-marino">Último movimiento:</b> {s.ultimo_movimiento_fecha ? `${fechaCorta(s.ultimo_movimiento_fecha)} — ${s.ultimo_movimiento_texto}` : "Sin registrar"}</p>
              <p className="mt-1"><b className="text-marino">Última revisión:</b> {s.ultima_revision ? `${fechaHora(s.ultima_revision)}${s.ultima_revision_por ? ` por ${s.ultima_revision_por}` : ""}` : "Sin registrar"}</p></div>
            <button className="btn-sec mt-3 w-full text-sm" onClick={async () => { try { hecho(await api.post(`/connect/seguimientos/${id}/revisado`, {}), "Revisión registrada."); } catch (e: any) { setError(e.message); } }}>✓ Revisé el expediente hoy</button>
            <div className="mt-3 grid grid-cols-[130px_1fr] gap-2">
              <input type="date" className="campo" value={mov.fecha} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setMov({ ...mov, fecha: e.target.value })} aria-label="Fecha del movimiento" />
              <input className="campo" value={mov.texto} maxLength={500} onChange={(e) => setMov({ ...mov, texto: e.target.value })} placeholder="Qué pasó, en palabras sencillas" /></div>
            <button className="btn-sec mt-2 w-full text-sm" disabled={mov.texto.trim().length < 3}
              onClick={async () => { try { hecho(await api.post(`/connect/seguimientos/${id}/movimiento`, mov), "Movimiento registrado."); setMov({ ...mov, texto: "" }); } catch (e: any) { setError(e.message); } }}>Registrar movimiento</button>
          </section>
          {s.cliente && <Enlaces cliente={s.cliente} />}
          <section className="tarjeta p-5"><h2 className="mb-2 font-bold text-marino">Qué ve el cliente</h2>
            {[["mostrar_audiencias", "Próximas audiencias de este asunto (de la Agenda)"], ["mostrar_pagos", "Sus pagos pendientes (de Clientes y cobranza)"]].map(([k, t]) => (
              <label key={k} className="flex items-center gap-2 py-1 text-sm text-slate-700"><input type="checkbox" checked={!!s[k]} onChange={(e) => ajustar({ [k]: e.target.checked })} /> {t}</label>))}
            <p className="mt-2 text-xs text-slate-500">Nunca ve: notas internas, notas del asunto en la Agenda, documentos no compartidos ni otros asuntos.</p>
            <div className="mt-4 flex flex-wrap gap-2 border-t border-crema-300 pt-3">
              {s.estado !== "activo" && <button className="btn-sec text-xs" onClick={() => ajustar({ estado: "activo" })}>Reactivar</button>}
              {s.estado === "activo" && <button className="btn-sec text-xs" onClick={() => ajustar({ estado: "suspendido" })}>Suspender temporalmente</button>}
              {s.estado !== "cerrado" && <button className="btn-sec text-xs" onClick={() => ajustar({ estado: "cerrado" })}>Marcar como concluido</button>}
              <button className="ml-auto text-xs font-semibold text-red-600" onClick={() => setBorrar(true)}>Eliminar seguimiento</button></div>
          </section>
        </div>
      </div>
      {editarEtapas && <Modal titulo="Etapas de este asunto" onCerrar={() => setEditarEtapas(null)} ancho="max-w-2xl">
        <p className="mb-3 text-sm text-slate-500">Los cambios aplican solo a este asunto: la plantilla y los demás asuntos no cambian. Las etapas que ya tienen avance lo conservan.</p>
        <EditorEtapas etapas={editarEtapas} setEtapas={setEditarEtapas} />
        <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={() => setEditarEtapas(null)}>Cancelar</button>
          <button className="btn-turquesa" onClick={async () => { try { hecho(await api.put(`/connect/seguimientos/${id}/etapas`, { etapas: editarEtapas }), "Etapas guardadas."); setEditarEtapas(null); setSel(null); } catch (e: any) { setError(e.message); } }}>Guardar etapas</button></div>
      </Modal>}
      {borrar && <ConfirmarEliminar titulo="¿Eliminar este seguimiento?" onCerrar={() => setBorrar(false)}
        onConfirmar={async () => { await api.borrar(`/connect/seguimientos/${id}`); router.push("/connect"); }}>
        Se borran sus etapas e historial y el cliente deja de verlo. El asunto de la Agenda no se borra.</ConfirmarEliminar>}
    </Shell>
  );
}

function VincularCliente({ onElegir }: { onElegir: (id: number) => void }) {
  const [clientes, setClientes] = useState<any[]>([]);
  const [cid, setCid] = useState("");
  useEffect(() => { api.get("/clientes").then((x) => setClientes(x.clientes || [])).catch(() => {}); }, []);
  return (
    <div className="mb-4 flex flex-wrap items-end gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-4">
      <label className="min-w-[240px] flex-1"><span className="etiqueta">Para publicarlo, ¿de qué cliente es este asunto?</span>
        <select className="campo" value={cid} onChange={(e) => setCid(e.target.value)}>
          <option value="">— Elegir de su directorio —</option>{clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></label>
      <button className="btn-turquesa" disabled={!cid} onClick={() => onElegir(Number(cid))}>Vincular cliente</button>
      <Link href="/clientes" className="text-sm font-semibold text-turquesa-700 underline">Dar de alta un cliente</Link>
    </div>);
}

function Enlaces({ cliente }: { cliente: any }) {
  const [e, setE] = useState<any>(null);
  const [nuevo, setNuevo] = useState<any>(null);
  const [copiado, setCopiado] = useState(false);
  const cargar = useCallback(() => api.get(`/connect/clientes/${cliente.id}/enlaces`).then(setE).catch(() => {}), [cliente.id]);
  useEffect(() => { cargar(); }, [cargar]);
  const crear = async () => { setNuevo(await api.post(`/connect/clientes/${cliente.id}/enlaces`, { dias: 30 })); cargar(); };
  const texto = nuevo ? `Hola, ${cliente.nombre.split(" ")[0]}. Aquí puede ver en qué va su asunto y escribirnos: ${nuevo.url}` : "";
  const vigentes = (e?.enlaces || []).filter((x: any) => x.estado === "activo");
  return (
    <section className="tarjeta p-5"><h2 className="font-bold text-marino">Portal de {cliente.nombre.split(" ")[0]}</h2>
      <p className="mt-1 text-xs text-slate-500">Un solo enlace para todos sus asuntos publicados. {cliente.email ? "Al abrirlo le pedimos un código que llega a su correo." : "⚠ El cliente no tiene correo: el enlace no pedirá código. Agréguele correo en Clientes para mayor seguridad."}</p>
      {nuevo ? <div className="mt-3 rounded-xl bg-turquesa-50 p-3">
        <p className="break-all text-xs text-marino">{nuevo.url}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="btn-sec text-xs" onClick={() => { navigator.clipboard.writeText(texto); setCopiado(true); setTimeout(() => setCopiado(false), 2000); }}>{copiado ? "¡Copiado!" : "Copiar mensaje"}</button>
          <a className="btn-sec text-xs" target="_blank" rel="noreferrer" href={`https://wa.me/?text=${encodeURIComponent(texto)}`}>Enviar por mi WhatsApp</a></div>
        <p className="mt-2 text-[11px] text-slate-500">Por seguridad este enlace solo se muestra ahora. Vence en 30 días.</p></div>
        : <button className="btn-turquesa mt-3 w-full text-sm" onClick={crear}>{vigentes.length ? "Crear un enlace nuevo" : "Crear enlace para el cliente"}</button>}
      {e?.enlaces.length > 0 && <ul className="mt-3 space-y-1 text-xs">{e.enlaces.slice(0, 5).map((x: any) => (
        <li key={x.id} className="flex items-center justify-between gap-2"><span className="text-slate-600">…{x.pista} · {x.estado === "activo" ? `vence ${fechaCorta(x.expira_en)}` : x.estado} · {x.visitas} visita(s)</span>
          {x.estado === "activo" && <button className="font-semibold text-red-600" onClick={() => api.post(`/connect/enlaces/${x.id}/revocar`, {}).then(cargar)}>Desactivar</button>}</li>))}</ul>}
    </section>
  );
}
