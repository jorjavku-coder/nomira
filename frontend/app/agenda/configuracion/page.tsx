"use client";
import { useEffect, useState } from "react";
import { AgendaShell, useCatalogosAgenda } from "@/components/agenda";
import { Aviso } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

const lista = (v: string) => v.split(",").map((x) => parseInt(x.trim())).filter((x) => !isNaN(x));

export default function Configuracion() {
  const cat = useCatalogosAgenda();
  const [c, setC] = useState<any>(null);
  const [p, setP] = useState<any>(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState(""); const [ok, setOk] = useState("");
  useEffect(() => { api.get("/agenda/config").then((x) => setC({ ...x, ap: x.alertas_plazo.join(", "), aa: x.alertas_audiencia.join(", ") })).catch((e) => setError(e.message));
    api.get("/agenda/preferencias").then(setP).catch(() => {}); }, []);
  async function hacer(fn: () => Promise<any>, msg: string) { setError(""); setOk(""); try { const r = await fn(); setOk(msg); return r; } catch (e: any) { setError(e.message); } }
  return (
    <AgendaShell>
      <h1 className="mb-4 text-3xl font-extrabold text-marino">Avisos y ajustes</h1>
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>
      <div className="grid gap-5 lg:grid-cols-2">
        {p && <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Mis avisos</h2>
          <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" className="accent-turquesa" checked={p.resumen_diario} onChange={(e) => setP({ ...p, resumen_diario: e.target.checked })} />Recibir por correo el resumen diario de mi agenda</label>
          <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" className="accent-turquesa" checked={p.alertas_correo} onChange={(e) => setP({ ...p, alertas_correo: e.target.checked })} />Recibir por correo los avisos de vencimiento</label>
          <p className="mt-1 text-xs text-slate-500">Aunque desactive el correo, los avisos se siguen viendo en Nomira.</p>
          <button className="btn-sec mt-3" onClick={() => hacer(() => api.put("/agenda/preferencias", p).then(setP), "Preferencias guardadas.")}>Guardar</button>
          <h3 className="mt-6 font-semibold text-marino">Ver mi agenda en Google Calendar u Outlook</h3>
          <p className="mt-1 text-sm text-slate-600">Genere un enlace privado y agréguelo como «calendario desde URL». Incluye solo lo que a usted le toca.</p>
          <label className="mt-2 block"><span className="etiqueta">Qué se ve en el calendario externo</span><select className="campo max-w-sm" value={p.feed_detalle} onChange={(e) => setP({ ...p, feed_detalle: e.target.value })}>
            <option value="reservado">Reservado: tipo y número de expediente, sin nombres</option><option value="completo">Completo: títulos, asunto y tribunal</option></select></label>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn-turquesa" onClick={async () => { await api.put("/agenda/preferencias", p); const r = await hacer(() => api.post("/agenda/preferencias/feed"), "Enlace generado. Cópielo ahora: no se vuelve a mostrar."); if (r) { setP(r); setUrl(r.url); } }}>{p.feed_activo ? "Generar un enlace nuevo" : "Generar enlace"}</button>
            {p.feed_activo && <button className="btn-sec" onClick={async () => { const r = await hacer(() => api.borrar("/agenda/preferencias/feed"), "Enlace desactivado."); if (r) { setP(r); setUrl(""); } }}>Desactivar enlace</button>}
          </div>
          {p.feed_activo && !url && <p className="mt-2 text-xs text-slate-500">Hay un enlace activo desde {fechaHora(p.feed_creado_en)}. Generar uno nuevo desactiva el anterior.</p>}
          {url && <div className="mt-3 rounded-xl bg-crema/70 p-3"><input readOnly aria-label="Enlace privado" className="campo font-mono text-xs" value={url} onFocus={(e) => e.target.select()} />
            <p className="mt-1 text-xs text-amber-800">Quien tenga este enlace puede ver su agenda. No lo comparta.</p></div>}
        </section>}
        {c && cat && <section className="tarjeta p-5">
          <h2 className="font-semibold text-marino">Ajustes del despacho {!cat.es_admin && <span className="text-xs font-normal text-slate-500">(solo un administrador puede cambiarlos)</span>}</h2>
          <fieldset disabled={!cat.es_admin} className="mt-3 space-y-3">
            <label className="block"><span className="etiqueta">Avisos de plazos: días antes (0 = el mismo día)</span><input className="campo" value={c.ap} onChange={(e) => setC({ ...c, ap: e.target.value })} /></label>
            <label className="block"><span className="etiqueta">Avisos de audiencias: días antes</span><input className="campo" value={c.aa} onChange={(e) => setC({ ...c, aa: e.target.value })} /></label>
            <label className="block"><span className="etiqueta">Si algo vence sin cumplirse, avisar también a</span><select className="campo" value={c.escalar_a_id ?? ""} onChange={(e) => setC({ ...c, escalar_a_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Los administradores del despacho</option>{cat.usuarios.map((u: any) => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select></label>
            <label className="block"><span className="etiqueta">Calendario de días hábiles por omisión</span><select className="campo" value={c.calendario_id ?? ""} onChange={(e) => setC({ ...c, calendario_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Ninguno</option>{cat.calendarios.map((x: any) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></label>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" className="accent-turquesa" checked={c.resumen_diario} onChange={(e) => setC({ ...c, resumen_diario: e.target.checked })} />Enviar resumen diario a las</label>
              <select className="campo w-auto" aria-label="Hora del resumen" value={c.hora_resumen} onChange={(e) => setC({ ...c, hora_resumen: Number(e.target.value) })}>{[5, 6, 7, 8, 9, 10, 11].map((h) => <option key={h} value={h}>{h}:00</option>)}</select>
              <span className="text-slate-500">(hora del centro de México)</span>
            </div>
            <p className="rounded-xl bg-crema/70 p-3 text-xs text-slate-600"><b>Cómo escalan los avisos:</b> 1) los días configurados, al responsable y su apoyo; 2) el día del vencimiento, si sigue pendiente a mediodía, a quien supervisa; 3) si vence sin marcarse como cumplido, a ambos. Lo que no tiene responsable se avisa a quien supervisa desde el primer aviso.</p>
            {cat.es_admin && <button type="button" className="btn-turquesa" onClick={() => hacer(() => api.put("/agenda/config", { ...c, alertas_plazo: lista(c.ap), alertas_audiencia: lista(c.aa) }).then((x) => setC({ ...x, ap: x.alertas_plazo.join(", "), aa: x.alertas_audiencia.join(", ") })), "Ajustes guardados.")}>Guardar ajustes</button>}
          </fieldset>
        </section>}
      </div>
    </AgendaShell>
  );
}
