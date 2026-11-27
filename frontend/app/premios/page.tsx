"use client";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Aviso } from "@/components/ui";
import { api, leerSesion } from "@/lib/api";

const fecha = (d?: string | null) => d ? new Date(d.length === 10 ? d + "T12:00" : d).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" }) : "";
const COLORES = ["#0f2a44", "#0e9f9a", "#16426b", "#14b8a6", "#1e3a5f", "#0d9488", "#24507f", "#2dd4bf"];
const ESTADO_PREMIO: Record<string, [string, string]> = {
  pendiente: ["Se aplica al contratar", "bg-amber-100 text-amber-800"], aplicada: ["Aplicado", "bg-emerald-100 text-emerald-800"],
  disponible: ["Listo para usar", "bg-turquesa-50 text-turquesa-700"], usada: ["Usado", "bg-slate-100 text-slate-600"], vencida: ["Venció", "bg-slate-100 text-slate-500"],
};

/** Gana con Nomira: trivia jurídica del día, ruleta semanal, tienda de puntos, invitaciones y casos de la calculadora. */
export default function Premios() {
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const admin = leerSesion()?.usuario.rol === "administrador";
  const cargar = useCallback(() => api.get("/premios").then(setD).catch((e) => setError(e.message)), []);
  useEffect(() => { cargar(); }, [cargar]);
  const aviso = (t: string) => { setOk(t); setError(""); setTimeout(() => setOk(""), 5000); };
  return (
    <Shell>
      <div className="relative mb-6 overflow-hidden rounded-3xl bg-gradient-to-br from-marino-900 via-marino to-turquesa-700 p-6 text-white sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-turquesa-brillante/25 blur-3xl" aria-hidden />
        <div className="relative flex flex-wrap items-end justify-between gap-5">
          <div className="max-w-xl"><p className="text-xs font-bold uppercase tracking-[0.16em] text-turquesa-brillante">Gana con Nomira</p>
            <h1 className="mt-1 font-marca text-3xl font-extrabold">Juegue, invite y gane meses gratis</h1>
            <p className="mt-2 text-white/75">Conteste la trivia jurídica del día, gire la ruleta y cambie sus puntos por descuentos o meses de Nomira.</p></div>
          {d && <div className="rounded-2xl bg-white/10 px-5 py-3 text-right ring-1 ring-white/20">
            <span className="block text-[11px] font-bold uppercase tracking-wider text-turquesa-brillante">Puntos del despacho</span>
            <span className="font-marca text-4xl font-extrabold tabular-nums" data-prueba="puntos">{d.puntos.toLocaleString("es-MX")}</span></div>}
        </div>
      </div>
      <Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso>
      {d && <>
        {!d.ya_pago && <Aviso tipo="info">Puede jugar desde su prueba. Los meses que gane se guardan y se suman cuando contrate su primer plan.</Aviso>}
        <div className="grid gap-5 lg:grid-cols-2">
          {d.reglas.juegos && <Trivia d={d} onCambio={(t: number) => setD({ ...d, puntos: t })} />}
          {d.reglas.ruleta ? <Ruleta d={d} onPremio={(r: any) => { aviso(`¡Ganó ${r.premio.etiqueta}!`); cargar(); }} onError={setError} />
            : d.reglas.juegos && <div className="tarjeta flex flex-col items-center justify-center p-8 text-center"><p className="text-4xl" aria-hidden>🎡</p>
              <p className="mt-2 text-lg font-bold text-marino">La ruleta semanal llega pronto</p>
              <p className="mt-1 max-w-sm text-sm text-slate-500">Mientras tanto, junte puntos con la trivia y cámbielos en la tienda.</p></div>}
        </div>
        {d.reglas.juegos && <Tienda d={d} admin={admin} onCanje={(r: any) => { aviso(r.recompensa.tipo === "descuento" ? `Listo: su código es ${r.recompensa.cupon.codigo}.` : "¡Listo! Sus meses de regalo quedaron registrados."); cargar(); }} onError={setError} />}
        {d.reglas.referidos && <Invitar d={d} />}
        {d.reglas.casos && <Casos d={d} admin={admin} onGuardar={() => { aviso("Guardado."); cargar(); }} onError={setError} />}
        <MisPremios d={d} />
      </>}
    </Shell>
  );
}

function Trivia({ d, onCambio }: { d: any; onCambio: (t: number) => void }) {
  const [preguntas, setPreguntas] = useState<any[]>(d.trivia);
  const [error, setError] = useState("");
  const i = preguntas.findIndex((p) => !p.respuesta);
  const actual = i === -1 ? null : preguntas[i];
  const ultima = [...preguntas].reverse().find((p) => p.respuesta);
  const aciertos = preguntas.filter((p) => p.respuesta?.correcta).length;
  const responder = async (op: number) => {
    try {
      const r = await api.post(`/premios/trivia/${actual.id}`, { elegida: op });
      setPreguntas(preguntas.map((p) => p.id === actual.id ? { ...p, respuesta: { elegida: op, correcta: r.correcta, opcion_correcta: r.opcion_correcta, explicacion: r.explicacion, puntos: r.puntos } } : p));
      onCambio(r.puntos_total);
    } catch (e: any) { setError(e.message); }
  };
  return (
    <section className="tarjeta p-6" aria-labelledby="t-trivia">
      <div className="flex items-center justify-between gap-3"><h2 id="t-trivia" className="text-lg font-bold text-marino">🧠 Trivia del día</h2>
        <span className="text-xs font-semibold text-slate-500">{preguntas.filter((p) => p.respuesta).length} de {preguntas.length} · {d.reglas.puntos_por_acierto} puntos por acierto</span></div>
      <div className="mt-3 flex gap-1.5" aria-hidden>{preguntas.map((p) => <span key={p.id} className={`h-1.5 flex-1 rounded-full ${!p.respuesta ? "bg-crema-300" : p.respuesta.correcta ? "bg-emerald-500" : "bg-red-400"}`} />)}</div>
      <Aviso>{error}</Aviso>
      {ultima?.respuesta && (actual || i === -1) && <div className={`mt-4 rounded-xl p-3 text-sm ${ultima.respuesta.correcta ? "bg-emerald-50 text-emerald-900" : "bg-red-50 text-red-900"}`} role="status">
        <p className="font-bold">{ultima.respuesta.correcta ? `¡Correcto!${ultima.respuesta.puntos ? ` +${ultima.respuesta.puntos} puntos` : ""}` : `La respuesta era: ${ultima.opciones[ultima.respuesta.opcion_correcta]}`}</p>
        <p className="mt-0.5">{ultima.respuesta.explicacion}</p></div>}
      {actual ? <div className="mt-4">
        <p className="text-xs font-bold uppercase tracking-wider text-turquesa-700">{actual.materia}</p>
        <p className="mt-1 font-semibold text-marino">{actual.texto}</p>
        <div className="mt-3 grid gap-2">{actual.opciones.map((o: string, k: number) => (
          <button key={k} onClick={() => responder(k)} className="rounded-xl border border-crema-300 bg-white px-4 py-3 text-left text-sm font-medium text-slate-700 transition hover:border-turquesa hover:bg-turquesa-50">{o}</button>))}</div>
      </div> : <div className="mt-6 text-center"><p className="text-3xl" aria-hidden>{aciertos === preguntas.length && preguntas.length ? "🏆" : aciertos ? "✅" : "📚"}</p>
        <p className="mt-1 font-bold text-marino">{preguntas.length ? `Terminó la trivia de hoy: ${aciertos} de ${preguntas.length}` : "Ya contestó todas las preguntas disponibles"}</p>
        <p className="text-sm text-slate-500">Mañana hay preguntas nuevas.</p></div>}
    </section>
  );
}

function Ruleta({ d, onPremio, onError }: { d: any; onPremio: (r: any) => void; onError: (t: string) => void }) {
  const cas = d.ruleta.casillas;
  const [giro, setGiro] = useState(0);
  const [girando, setGirando] = useState(false);
  const [premio, setPremio] = useState<any>(null);
  const seg = 360 / Math.max(cas.length, 1);
  const girar = async () => {
    setGirando(true);
    try {
      const r = await api.post("/premios/ruleta");
      const k = Math.max(0, cas.findIndex((c: any) => c.id === r.premio.id));
      const destino = 360 * 6 + (360 - (k * seg + seg / 2));
      setGiro(giro - (giro % 360) + destino);
      setTimeout(() => { setGirando(false); setPremio(r.premio); onPremio(r); }, 4300);
    } catch (e: any) { setGirando(false); onError(e.message); }
  };
  const punto = (ang: number, r: number) => [100 + r * Math.sin((ang * Math.PI) / 180), 100 - r * Math.cos((ang * Math.PI) / 180)];
  const usada = d.ruleta.girada && !girando;
  return (
    <section className="tarjeta p-6" aria-labelledby="t-ruleta">
      <h2 id="t-ruleta" className="text-lg font-bold text-marino">🎡 Ruleta semanal</h2>
      <p className="text-xs font-semibold text-slate-500">Un giro por despacho cada semana · sin compra</p>
      <div className="mt-4 grid items-center gap-5 sm:grid-cols-[220px_1fr]">
        <div className="relative mx-auto h-[220px] w-[220px]">
          <div className="absolute left-1/2 top-[-6px] z-10 h-0 w-0 -translate-x-1/2 border-x-[11px] border-t-[18px] border-x-transparent border-t-amber-400 drop-shadow" aria-hidden />
          <svg viewBox="0 0 200 200" className="h-full w-full rounded-full shadow-lg" style={{ transform: `rotate(${giro}deg)`, transition: girando ? "transform 4.2s cubic-bezier(.17,.67,.2,1)" : "none" }} role="img" aria-label="Ruleta de premios">
            {cas.map((c: any, k: number) => {
              const [x1, y1] = punto(k * seg, 100), [x2, y2] = punto((k + 1) * seg, 100), [tx, ty] = punto(k * seg + seg / 2, 62);
              return <g key={c.id}><path d={`M100,100 L${x1},${y1} A100,100 0 ${seg > 180 ? 1 : 0} 1 ${x2},${y2} Z`} fill={c.tipo === "meses" ? "#f59e0b" : COLORES[k % COLORES.length]} stroke="#fff" strokeWidth="1" />
                <text x={tx} y={ty} fill="#fff" fontSize="8.5" fontWeight="700" textAnchor="middle" dominantBaseline="middle" transform={`rotate(${(k * seg + seg / 2) % 360 < 180 ? k * seg + seg / 2 - 90 : k * seg + seg / 2 + 90} ${tx} ${ty})`}>{c.etiqueta.replace(" de descuento", "").replace(" gratis", "")}</text></g>;
            })}
            <circle cx="100" cy="100" r="14" fill="#fff" /><circle cx="100" cy="100" r="7" fill="#0f2a44" />
          </svg>
        </div>
        <div>
          {premio ? <p className="rounded-xl bg-amber-50 p-3 text-center font-bold text-amber-900" role="status">🎉 Ganó: {premio.etiqueta}</p>
            : usada ? <p className="rounded-xl bg-crema p-3 text-sm text-slate-600">Su despacho ya giró esta semana ({d.ruleta.girada.etiqueta}). Vuelva el lunes.</p>
            : <button className="btn-turquesa w-full py-3 text-base" disabled={girando} onClick={girar}>{girando ? "Girando…" : "Girar la ruleta"}</button>}
          <details className="mt-3 text-sm" open><summary className="cursor-pointer font-semibold text-marino">Probabilidades reales</summary>
            <ul className="mt-1 space-y-0.5 text-slate-600">{cas.map((c: any) => <li key={c.id} className="flex justify-between gap-3"><span>{c.etiqueta}</span><span className="tabular-nums">{c.probabilidad}%</span></li>)}</ul>
            <p className="mt-1 text-xs text-slate-500">Las casillas se dibujan del mismo tamaño; lo que cuenta es esta tabla. {d.reglas.ruleta_permiso ? `Permiso ${d.reglas.ruleta_permiso}.` : ""}</p></details>
        </div>
      </div>
    </section>
  );
}

function Tienda({ d, admin, onCanje, onError }: { d: any; admin: boolean; onCanje: (r: any) => void; onError: (t: string) => void }) {
  const [ocupado, setOcupado] = useState(0);
  const [confirmar, setConfirmar] = useState(0);
  const canjear = async (p: any) => {
    if (confirmar !== p.id) { setConfirmar(p.id); return; }
    setOcupado(p.id); setConfirmar(0);
    try { onCanje(await api.post(`/premios/tienda/${p.id}`)); } catch (e: any) { onError(e.message); } finally { setOcupado(0); }
  };
  return (
    <section className="mt-6" aria-labelledby="t-tienda">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2"><h2 id="t-tienda" className="text-lg font-bold text-marino">🛍️ Tienda de puntos</h2>
        <p className="text-xs text-slate-500">{admin ? "Los meses se suman al final de su plan." : "Solo un administrador del despacho puede canjear."} Máximo {d.reglas.tope_meses_anual} meses de regalo por juegos al año.</p></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">{d.tienda.map((p: any) => {
        const falta = p.costo - d.puntos;
        return <div key={p.id} className={`tarjeta flex flex-col p-4 ${p.tipo === "meses" ? "ring-1 ring-amber-200" : ""}`}>
          <p className="text-2xl" aria-hidden>{p.tipo === "meses" ? "🗓️" : "🏷️"}</p>
          <p className="mt-1 font-marca text-lg font-extrabold text-marino">{p.etiqueta}</p>
          <p className="text-sm font-semibold text-turquesa-700">{p.costo.toLocaleString("es-MX")} puntos</p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-crema-300" aria-hidden><div className="h-full bg-turquesa" style={{ width: `${Math.min(100, (100 * d.puntos) / p.costo)}%` }} /></div>
          {falta > 0 ? <p className="mt-auto pt-3 text-xs text-slate-500">Le faltan {falta.toLocaleString("es-MX")}</p>
            : <button className="btn-turquesa mt-auto w-full text-sm" style={{ marginTop: "0.75rem" }} disabled={!admin || ocupado === p.id} onClick={() => canjear(p)}>{confirmar === p.id ? `Confirmar: −${p.costo.toLocaleString("es-MX")} puntos` : "Canjear"}</button>}
        </div>;
      })}</div>
    </section>
  );
}

function Invitar({ d }: { d: any }) {
  const [copiado, setCopiado] = useState(false);
  const inv = d.invitacion;
  const mensaje = `Te recomiendo Nomira para el despacho: agenda, cálculos laborales, tesis y portal para clientes. Pruébalo gratis con mi invitación: ${inv.enlace}`;
  const n = d.reglas.meses_referido;
  return (
    <section className="tarjeta mt-6 grid gap-5 p-6 lg:grid-cols-[1fr_1fr]" aria-labelledby="t-invitar">
      <div>
        <h2 id="t-invitar" className="text-lg font-bold text-marino">🤝 Invite a otro despacho y ganen los dos</h2>
        <p className="mt-1 text-sm text-slate-600">Cuando el despacho que invitó contrate su primer plan, <b>los dos reciben {n} {n === 1 ? "mes" : "meses"} gratis</b>. Sin límite de invitaciones (hasta {d.reglas.tope_referidos_anual} meses al año).</p>
        <div className="mt-4 flex items-center gap-2 rounded-xl border border-crema-300 bg-crema/50 p-2">
          <span className="min-w-0 flex-1 truncate px-2 font-mono text-sm text-marino" data-prueba="enlace-invitacion">{inv.enlace}</span>
          <button className="btn-sec text-sm" onClick={() => { navigator.clipboard.writeText(inv.enlace); setCopiado(true); setTimeout(() => setCopiado(false), 2000); }}>{copiado ? "¡Copiado!" : "Copiar"}</button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <a className="btn-turquesa text-sm" href={`https://wa.me/?text=${encodeURIComponent(mensaje)}`} target="_blank" rel="noopener noreferrer">Compartir por WhatsApp</a>
          <a className="btn-sec text-sm" href={`mailto:?subject=${encodeURIComponent("Te recomiendo Nomira")}&body=${encodeURIComponent(mensaje)}`}>Enviar por correo</a>
        </div>
        <p className="mt-2 text-xs text-slate-500">Su código: <b className="font-mono">{inv.codigo}</b></p>
      </div>
      <div>
        <p className="text-sm font-semibold text-marino">Despachos que invitó</p>
        {inv.referidos.length ? <ul className="mt-2 divide-y divide-crema-200">{inv.referidos.map((r: any, k: number) => (
          <li key={k} className="flex items-center justify-between gap-3 py-2 text-sm"><span><b className="text-marino">{r.despacho}</b><span className="block text-xs text-slate-500">desde el {fecha(r.desde)}</span></span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${r.estado === "premiado" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{r.estado === "premiado" ? "¡Ya ganaron!" : "En prueba"}</span></li>))}</ul>
          : <p className="mt-2 rounded-xl bg-crema/60 p-4 text-sm text-slate-500">Aún no invita a nadie. ¿Un colega, su antiguo despacho, su barra o colegio?</p>}
      </div>
    </section>
  );
}

function Casos({ d, admin, onGuardar, onError }: { d: any; admin: boolean; onGuardar: () => void; onError: (t: string) => void }) {
  const r = d.red;
  const [activo, setActivo] = useState(!!r.config?.activo);
  const [estados, setEstados] = useState<string[]>(r.config?.estados || []);
  const [tope, setTope] = useState(r.config?.tope_mensual ? String(r.config.tope_mensual) : "");
  const cumple = r.requisitos.plan && r.requisitos.prospectos;
  const guardar = async () => {
    try { await api.put("/premios/red", { activo, estados, tope_mensual: tope ? Number(tope) : null }); onGuardar(); } catch (e: any) { onError(e.message); }
  };
  return (
    <section className="tarjeta mt-6 p-6" aria-labelledby="t-casos">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl"><h2 id="t-casos" className="text-lg font-bold text-marino">📥 Nomira le manda clientes</h2>
          <p className="mt-1 text-sm text-slate-600">Cada día, trabajadores calculan su finiquito gratis en la calculadora pública de Nomira. Cuando alguien pide que un abogado revise su caso, se lo enviamos <b>por turnos</b> a un despacho de su estado, directo a sus Prospectos, con su autorización para contactarle.</p></div>
        <span className="rounded-full bg-turquesa-50 px-3 py-1 text-sm font-bold text-turquesa-700">{r.recibidos} {r.recibidos === 1 ? "caso recibido" : "casos recibidos"}</span>
      </div>
      {!cumple ? <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Para recibir casos necesita {[!r.requisitos.plan && "un plan pagado vigente", !r.requisitos.prospectos && "el módulo de Prospectos activo"].filter(Boolean).join(" y ")}.</p>
        : !admin ? <p className="mt-4 text-sm text-slate-500">{activo ? `Recibe casos de: ${estados.map((e) => r.estados[e]).join(", ")}.` : "Su despacho no está recibiendo casos."} Un administrador puede cambiarlo.</p>
        : <div className="mt-4 space-y-3">
          <label className="flex items-center gap-2 text-sm font-semibold text-marino"><input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} /> Quiero recibir casos laborales de la calculadora</label>
          {activo && <>
            <div><p className="etiqueta">Estados donde atiende</p>
              <div className="mt-1 flex flex-wrap gap-1.5">{Object.entries(r.estados).map(([k, t]) => (
                <button key={k} type="button" aria-pressed={estados.includes(k)} onClick={() => setEstados(estados.includes(k) ? estados.filter((x) => x !== k) : [...estados, k])}
                  className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${estados.includes(k) ? "border-marino bg-marino text-white" : "border-crema-300 bg-white text-slate-600"}`}>{t as string}</button>))}</div></div>
            <label className="block max-w-xs"><span className="etiqueta">Máximo de casos al mes (opcional)</span><input className="campo" inputMode="numeric" value={tope} onChange={(e) => setTope(e.target.value.replace(/\D/g, ""))} placeholder="Sin límite" /></label>
          </>}
          <button className="btn-turquesa" onClick={guardar}>Guardar</button>
        </div>}
    </section>
  );
}

function MisPremios({ d }: { d: any }) {
  if (!d.recompensas.length && !d.movimientos.length) return null;
  return (
    <section className="mt-6 grid gap-5 lg:grid-cols-2">
      <div className="tarjeta p-6"><h2 className="text-lg font-bold text-marino">🎁 Mis premios</h2>
        {d.recompensas.length ? <ul className="mt-2 divide-y divide-crema-200">{d.recompensas.map((r: any) => (
          <li key={r.id} className="py-2.5 text-sm"><div className="flex items-center justify-between gap-3"><b className="text-marino">{r.tipo === "meses" ? `${r.valor} ${r.valor === 1 ? "mes" : "meses"} gratis` : `${r.valor}% de descuento`}</b>
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTADO_PREMIO[r.estado]?.[1]}`}>{ESTADO_PREMIO[r.estado]?.[0] || r.estado}</span></div>
            <p className="text-xs text-slate-500">{r.descripcion} · {fecha(r.creado_en)}</p>
            {r.cupon && r.estado === "disponible" && <p className="mt-1 text-xs">Código <b className="font-mono text-marino">{r.cupon.codigo}</b> · úselo en su siguiente propuesta o renovación (vence el {fecha(r.cupon.vence_en)}).</p>}
            {r.periodo && <p className="mt-1 text-xs text-slate-600">Del {fecha(r.periodo.inicio)} al {fecha(r.periodo.fin)}.</p>}</li>))}</ul>
          : <p className="mt-2 text-sm text-slate-500">Aquí aparecerán sus descuentos y meses gratis.</p>}</div>
      {!!d.movimientos.length && <div className="tarjeta p-6"><h2 className="text-lg font-bold text-marino">Movimientos de puntos</h2>
        <ul className="mt-2 divide-y divide-crema-200">{d.movimientos.map((x: any, k: number) => (
          <li key={k} className="flex justify-between gap-3 py-2 text-sm"><span className="text-slate-600">{x.detalle}<span className="block text-xs text-slate-400">{fecha(x.dia)}</span></span>
            <b className={x.puntos >= 0 ? "text-emerald-700" : "text-red-700"}>{x.puntos > 0 ? "+" : ""}{x.puntos}</b></li>))}</ul></div>}
    </section>
  );
}
