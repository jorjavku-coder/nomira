"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import Shell, { useSesion } from "@/components/Shell";
import { Aviso, Chip } from "@/components/ui";
import { api, fechaHora } from "@/lib/api";

const CLAVE = /^\d{4}$/;

function EtiquetaManual() {
  return <span className="ml-2 rounded-full bg-turquesa-50 px-2 py-0.5 text-[11px] font-semibold text-turquesa-700" title="No venía en el documento fuente: la agregó una persona">agregada a mano</span>;
}

function Fila({ e, editable, onCambio }: { e: any; editable: boolean; onCambio: (fn: () => Promise<any>) => void }) {
  const [clave, setClave] = useState(e.clave);
  const [desc, setDesc] = useState(e.descripcion);
  useEffect(() => { setClave(e.clave); setDesc(e.descripcion); }, [e.clave, e.descripcion]);
  const sucio = clave !== e.clave || desc !== e.descripcion;
  if (!editable) {
    return (<tr className={e.activo ? "" : "text-slate-400"}><td className="font-mono">{e.clave}</td>
      <td>{e.descripcion}{e.agregada_manual && <EtiquetaManual />}</td><td>{e.activo ? "Activa" : "Inactiva"}</td><td></td></tr>);
  }
  return (
    <tr className={e.requiere_revision ? "bg-amber-50" : ""}>
      <td><input className="campo w-24 font-mono" value={clave} onChange={(x) => setClave(x.target.value)} aria-label="Clave" /></td>
      <td><div className="flex items-center"><input className="campo" value={desc} onChange={(x) => setDesc(x.target.value)} aria-label="Descripción" />{e.agregada_manual && <EtiquetaManual />}</div>
        {e.requiere_revision && <div className="mt-1 text-xs text-amber-800">Revisar: {e.nota || "lectura dudosa"}{e.confianza !== null && ` · confianza OCR ${e.confianza}`}{e.pagina && ` · pág. ${e.pagina}`}</div>}</td>
      <td><label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={e.activo}
        onChange={(x) => onCambio(() => api.patch(`/catalogos/entradas/${e.id}`, { activo: x.target.checked }))} /> Activa</label></td>
      <td className="whitespace-nowrap text-right">
        {(sucio || e.requiere_revision) && <button className="btn-turquesa mr-1" onClick={() => onCambio(() => api.patch(`/catalogos/entradas/${e.id}`, { clave, descripcion: desc, revisada: true }))}>
          {sucio ? "Guardar" : "Marcar revisada"}</button>}
        <button className="btn-peligro" onClick={() => { if (confirm(`¿Eliminar la clave ${e.clave} de este borrador?`)) onCambio(() => api.borrar(`/catalogos/entradas/${e.id}`)); }}>Eliminar</button>
      </td>
    </tr>
  );
}

function TablaEntradas({ v, editable, onCambio, soloManual = false }: { v: any; editable: boolean; onCambio: (fn: () => Promise<any>) => void; soloManual?: boolean }) {
  const [filtro, setFiltro] = useState("");
  const [soloRevisar, setSoloRevisar] = useState(false);
  const entradas = v.entradas.filter((e: any) => (!soloManual || e.agregada_manual) && (!soloRevisar || e.requiere_revision) &&
    (!filtro || e.clave.includes(filtro) || e.descripcion.toLowerCase().includes(filtro.toLowerCase())));
  return (
    <>
      {!soloManual && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <input className="campo max-w-xs" placeholder="Buscar clave o descripción" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
          {v.estado === "borrador" && <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={soloRevisar} onChange={(e) => setSoloRevisar(e.target.checked)} /> Solo por revisar ({v.por_revisar})</label>}
          <span className="text-sm text-slate-500">{entradas.length} de {v.entradas_total} claves{v.agregadas_manual > 0 && ` · ${v.agregadas_manual} agregadas a mano`}</span>
        </div>
      )}
      <div className="tarjeta overflow-x-auto">
        <table className="tabla">
          <thead><tr><th>Clave</th><th>Descripción</th><th>Estado</th><th></th></tr></thead>
          <tbody>{entradas.map((e: any) => <Fila key={e.id} e={e} editable={editable} onCambio={onCambio} />)}</tbody>
        </table>
      </div>
    </>
  );
}

const PASOS = ["Revisar lo cargado", "Claves faltantes", "Activar"];

function Pasos({ paso, setPaso, v }: { paso: number; setPaso: (n: number) => void; v: any }) {
  return (
    <ol className="mb-5 grid gap-2 sm:grid-cols-3">
      {PASOS.map((t, i) => {
        const n = i + 1, actual = paso === n, hecho = paso > n;
        const sub = n === 1 ? (v.por_revisar > 0 ? `${v.por_revisar} por revisar` : `${v.entradas_total} claves`)
          : n === 2 ? (v.agregadas_manual > 0 ? `${v.agregadas_manual} agregadas` : "Opcional") : "Usar en los cálculos";
        return (
          <li key={t}>
            <button onClick={() => setPaso(n)} className={`flex w-full items-center gap-3 rounded-2xl border px-4 py-3 text-left transition ${actual ? "border-turquesa bg-white shadow-sm ring-2 ring-turquesa/20" : "border-crema-300 bg-white/60 hover:bg-white"}`}>
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${actual ? "bg-turquesa text-white" : hecho ? "bg-marino text-white" : "bg-crema-300 text-marino"}`}>{hecho ? "✓" : n}</span>
              <span className="min-w-0"><span className={`block text-sm font-semibold ${actual ? "text-marino" : "text-slate-600"}`}>{t}</span>
                <span className="block text-xs text-slate-500">{sub}</span></span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

type Renglon = { id: number; clave: string; descripcion: string };
let siguienteId = 1;
const renglon = (clave = "", descripcion = ""): Renglon => ({ id: siguienteId++, clave, descripcion });

/** Convierte texto pegado (de Excel, Word o escrito a mano) en renglones clave + descripción. */
function interpretarPegado(texto: string): Renglon[] {
  return texto.split(/\r?\n/).map((l) => l.trim()).filter(Boolean).map((l) => {
    const partes = l.includes("\t") ? l.split("\t") : l.match(/^(\S+)\s*[,;|-]?\s*(.*)$/)?.slice(1) || [l, ""];
    return renglon(partes[0].trim().replace(/^'/, ""), partes.slice(1).join(" ").trim());
  }).filter((r) => !/^clave$/i.test(r.clave));
}

function ClavesFaltantes({ v, onGuardado, onCambio }: { v: any; onGuardado: (v: any, mensaje: string) => void; onCambio: (fn: () => Promise<any>) => void }) {
  const [filas, setFilas] = useState<Renglon[]>([renglon(), renglon(), renglon()]);
  const [sugerencias, setSugerencias] = useState<any[] | null>(null);
  const [pegar, setPegar] = useState(false);
  const [texto, setTexto] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const existentes = useMemo(() => new Set(v.entradas.map((e: any) => e.clave)), [v.entradas]);

  const cargarSugerencias = useCallback(() => api.get(`/catalogos/versiones/${v.id}/sugerencias`).then(setSugerencias).catch(() => setSugerencias([])), [v.id]);
  useEffect(() => { cargarSugerencias(); }, [cargarSugerencias, v.entradas_total]);

  const llenas = filas.filter((f) => f.clave.trim() || f.descripcion.trim());
  const problema = (f: Renglon): string => {
    const c = f.clave.trim();
    if (!c && !f.descripcion.trim()) return "";
    if (!CLAVE.test(c)) return "La clave debe tener 4 dígitos";
    if (!f.descripcion.trim()) return "Falta la descripción";
    if (llenas.filter((x) => x.clave.trim() === c).length > 1) return "Repetida en la lista";
    return "";
  };
  const conProblema = llenas.filter((f) => problema(f));
  const yaEstan = llenas.filter((f) => existentes.has(f.clave.trim()) && !problema(f));
  const aGuardar = llenas.length - yaEstan.length;
  const enLista = new Set(llenas.map((f) => f.clave.trim()));

  const cambiar = (id: number, k: "clave" | "descripcion", valor: string) => setFilas((fs) => fs.map((f) => (f.id === id ? { ...f, [k]: valor } : f)));
  const agregarRenglones = (nuevos: Renglon[]) => setFilas((fs) => {
    const conDatos = fs.filter((f) => f.clave.trim() || f.descripcion.trim());
    return [...conDatos, ...nuevos, renglon()];
  });

  async function guardar() {
    setError(""); setGuardando(true);
    try {
      const r = await api.post(`/catalogos/versiones/${v.id}/entradas/lote`, {
        entradas: llenas.map((f) => ({ clave: f.clave.trim(), descripcion: f.descripcion.trim() })) });
      setFilas([renglon(), renglon(), renglon()]);
      const partes = [`Se agregaron ${r.agregadas.length} clave(s)`];
      if (r.omitidas.length) partes.push(`${r.omitidas.length} ya estaban en el catálogo (${r.omitidas.join(", ")})`);
      onGuardado(r, partes.join("; ") + ".");
    } catch (e: any) { setError(e.message); }
    setGuardando(false);
  }

  return (
    <div className="space-y-5">
      <div className="tarjeta p-5">
        <h2 className="text-lg font-bold text-marino">Agregue las claves que no vienen en el catálogo</h2>
        <p className="mt-1 text-sm text-slate-600">Este paso es <b>opcional</b>. Las percepciones cuya clave no esté en el catálogo se quedan fuera del cálculo.
          Escriba una clave por renglón, o pegue varias desde Excel (columna de clave y columna de descripción).</p>

        {sugerencias && sugerencias.length > 0 && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="font-semibold text-amber-900">Encontramos {sugerencias.length} clave(s) en sus recibos que no están en este catálogo</div>
                <div className="text-xs text-amber-800">Hoy se quedan fuera del cálculo. Revise que de verdad deban sumarse antes de agregarlas.</div>
              </div>
              <button className="btn-sec" onClick={() => agregarRenglones(sugerencias.filter((s) => !enLista.has(s.clave)).map((s) => renglon(s.clave, s.descripcion)))}>
                Pasar todas a la lista</button>
            </div>
            <ul className="mt-3 divide-y divide-amber-200/70">
              {sugerencias.map((s) => (
                <li key={s.clave} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                  <span className="w-14 font-mono font-bold text-marino">{s.clave}</span>
                  <span className="min-w-[10rem] flex-1">{s.descripcion || <i className="text-slate-500">sin descripción leída</i>}</span>
                  <span className="text-xs text-slate-500">{s.apariciones} {s.apariciones === 1 ? "vez" : "veces"} · {s.expedientes} {s.expedientes === 1 ? "expediente" : "expedientes"}</span>
                  {enLista.has(s.clave)
                    ? <span className="text-xs font-semibold text-emerald-700">✓ En la lista</span>
                    : <button className="text-xs font-semibold text-turquesa-700 hover:underline" onClick={() => agregarRenglones([renglon(s.clave, s.descripcion)])}>+ Agregar</button>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-5 overflow-x-auto">
          <table className="tabla">
            <thead><tr><th className="w-32">Clave</th><th>Descripción</th><th className="w-56"></th><th className="w-10"></th></tr></thead>
            <tbody>
              {filas.map((f, i) => {
                const p = problema(f), ya = !p && existentes.has(f.clave.trim());
                return (
                  <tr key={f.id}>
                    <td><input className={`campo font-mono ${p && f.clave ? "border-red-300" : ""}`} placeholder="0000" inputMode="numeric" maxLength={4}
                      value={f.clave} onChange={(e) => cambiar(f.id, "clave", e.target.value)} aria-label={`Clave del renglón ${i + 1}`}
                      onPaste={(e) => { const t = e.clipboardData.getData("text"); if (t.includes("\n")) { e.preventDefault(); agregarRenglones(interpretarPegado(t)); } }} /></td>
                    <td><input className="campo" placeholder="Descripción de la prestación" value={f.descripcion} maxLength={400}
                      onChange={(e) => cambiar(f.id, "descripcion", e.target.value)} aria-label={`Descripción del renglón ${i + 1}`}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (i === filas.length - 1) setFilas([...filas, renglon()]); } }} /></td>
                    <td className="text-xs">{p ? <span className="text-red-700">{p}</span> : ya ? <span className="text-slate-500">Ya está en el catálogo: se omitirá</span> : (f.clave && f.descripcion) ? <span className="text-emerald-700">✓ Lista</span> : null}</td>
                    <td><button className="rounded-lg p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label={`Quitar renglón ${i + 1}`}
                      onClick={() => setFilas(filas.length > 1 ? filas.filter((x) => x.id !== f.id) : [renglon()])}>✕</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="btn-sec" onClick={() => setFilas([...filas, renglon()])}>+ Agregar renglón</button>
          <button className="btn-sec" onClick={() => setPegar(!pegar)}>{pegar ? "Cerrar" : "Pegar varias claves"}</button>
        </div>
        {pegar && (
          <div className="mt-3 rounded-2xl bg-crema p-4">
            <label className="block"><span className="etiqueta">Pegue aquí: una clave por línea, seguida de su descripción</span>
              <textarea className="campo h-32 font-mono text-sm" value={texto} onChange={(e) => setTexto(e.target.value)}
                placeholder={"9876\tBONO ESPECIAL\n9877 AYUDA DE DESPENSA\n9878, PRIMA DE ANTIGÜEDAD"} /></label>
            <button className="btn-turquesa mt-2" disabled={!texto.trim()} onClick={() => { agregarRenglones(interpretarPegado(texto)); setTexto(""); setPegar(false); }}>
              Pasar {interpretarPegado(texto).length || ""} a la lista</button>
          </div>
        )}
        <div className="mt-4"><Aviso>{error}</Aviso></div>
        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-crema-300 pt-4">
          <button className="btn-primario" disabled={guardando || llenas.length === 0 || conProblema.length > 0} onClick={guardar}>
            {guardando ? "Guardando…" : `Guardar ${aGuardar > 0 ? aGuardar : ""} clave(s)`}</button>
          {conProblema.length > 0 && <span className="text-sm text-red-700">Corrija los {conProblema.length} renglón(es) marcados en rojo.</span>}
        </div>
      </div>

      {v.agregadas_manual > 0 && (
        <div>
          <h3 className="mb-2 font-semibold text-marino">Claves agregadas a mano en esta versión ({v.agregadas_manual})</h3>
          <TablaEntradas v={v} editable onCambio={onCambio} soloManual />
        </div>
      )}
    </div>
  );
}

export default function Version() {
  const { vid } = useParams<{ vid: string }>();
  const sesion = useSesion();
  const [v, setV] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [paso, setPaso] = useState(0);
  const [confirmo, setConfirmo] = useState(false);
  const [actualizar, setActualizar] = useState(true);
  const [activada, setActivada] = useState<any>(null);
  const [creando, setCreando] = useState(false);
  const cargar = useCallback(() => api.get(`/catalogos/versiones/${vid}`).then(setV).catch((e) => setError(e.message)), [vid]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    if (!v || paso) return;
    const pedido = Number(new URLSearchParams(window.location.search).get("paso"));
    setPaso(pedido >= 1 && pedido <= 3 ? pedido : 1);
  }, [v, paso]);
  const cambio = async (fn: () => Promise<any>) => {
    setError(""); setOk("");
    try { await fn(); await cargar(); } catch (e: any) { setError(e.message); }
  };
  const irA = (n: number) => { setPaso(n); setOk(""); setError(""); window.scrollTo({ top: 0, behavior: "smooth" }); };

  if (!v) return <Shell><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</Shell>;
  const admin = sesion?.usuario.rol === "administrador";
  const editable = v.estado === "borrador" && admin;

  async function nuevaConFaltantes() {
    setCreando(true); setError("");
    try {
      const n = await api.post(`/catalogos/${v.catalogo_id}/versiones`, { copiar_de_version_id: v.id, notas: `Copia de la versión ${v.numero} para agregar claves faltantes` });
      window.location.href = `/catalogos/${n.id}?paso=2`;
    } catch (e: any) { setError(e.message); setCreando(false); }
  }

  return (
    <Shell>
      <Link href="/catalogos" className="text-sm text-turquesa-700 hover:underline">← Catálogos</Link>
      <div className="mb-3 mt-1 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-extrabold text-marino">{v.catalogo} — versión {v.numero}</h1>
        <Chip estado={v.estado} />
      </div>
      {v.notas && <p className="mb-3 text-sm text-slate-600">{v.notas}</p>}
      <div className="mb-3 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      {!editable ? (
        <>
          {activada ? (
            <Aviso tipo="ok"><b>¡Versión activada!</b> Ya se usa para los expedientes nuevos
              {activada.expedientes_actualizados > 0 && <> y se actualizaron <b>{activada.expedientes_actualizados}</b> expediente(s) en revisión, que ya se recalcularon con las claves nuevas</>}.
              {" "}<Link href="/" className="font-semibold underline">Ir a los expedientes →</Link></Aviso>
          ) : v.estado === "borrador" ? (
            <Aviso tipo="alerta">Borrador pendiente de validación por un administrador.</Aviso>
          ) : (
            <Aviso tipo="info">Versión {v.estado === "activo" ? "activa" : "archivada"}, validada el {fechaHora(v.validado_en)}. No se modifica:
              para cambiarla se crea una versión nueva.</Aviso>
          )}
          {admin && v.estado === "activo" && !activada && (
            <div className="tarjeta my-4 flex flex-wrap items-center justify-between gap-3 p-4">
              <div><div className="font-semibold text-marino">¿Le faltan claves a este catálogo?</div>
                <div className="text-sm text-slate-600">Se crea una copia en borrador donde las agrega; al activarla, sustituye a esta.</div></div>
              <button className="btn-turquesa" disabled={creando} onClick={nuevaConFaltantes}>{creando ? "Creando copia…" : "Agregar claves faltantes"}</button>
            </div>
          )}
          <div className="mt-4"><TablaEntradas v={v} editable={false} onCambio={cambio} /></div>
        </>
      ) : (
        <>
          <Pasos paso={paso} setPaso={irA} v={v} />

          {paso === 1 && (
            <>
              <Aviso tipo="alerta">
                <b>Compare cada clave contra el documento fuente.</b> La lectura automática puede equivocarse: nada se corrige solo.
                {v.por_revisar > 0 && <> Hay <b>{v.por_revisar}</b> entrada(s) marcadas por revisar.</>}
              </Aviso>
              <div className="mt-4"><TablaEntradas v={v} editable onCambio={cambio} /></div>
              <div className="mt-4 flex justify-end"><button className="btn-primario" onClick={() => irA(2)}>Siguiente: claves faltantes →</button></div>
            </>
          )}

          {paso === 2 && (
            <>
              <ClavesFaltantes v={v} onCambio={cambio} onGuardado={(_, m) => { setOk(m); cargar(); }} />
              <div className="mt-5 flex flex-wrap justify-between gap-2">
                <button className="btn-sec" onClick={() => irA(1)}>← Revisar lo cargado</button>
                <button className="btn-primario" onClick={() => irA(3)}>{v.agregadas_manual > 0 ? "Siguiente: activar →" : "Omitir y continuar →"}</button>
              </div>
            </>
          )}

          {paso === 3 && (
            <div className="tarjeta max-w-3xl space-y-4 p-6">
              <h2 className="text-lg font-bold text-marino">Activar el catálogo</h2>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl bg-crema p-4"><div className="etiqueta">Claves en total</div><div className="font-marca text-2xl font-extrabold text-marino">{v.entradas_total}</div></div>
                <div className="rounded-2xl bg-crema p-4"><div className="etiqueta">Agregadas a mano</div><div className="font-marca text-2xl font-extrabold text-marino">{v.agregadas_manual}</div></div>
                <div className={`rounded-2xl p-4 ${v.por_revisar > 0 ? "bg-amber-50" : "bg-crema"}`}><div className="etiqueta">Por revisar</div>
                  <div className={`font-marca text-2xl font-extrabold ${v.por_revisar > 0 ? "text-amber-700" : "text-marino"}`}>{v.por_revisar}</div></div>
              </div>
              {v.por_revisar > 0 && <Aviso tipo="alerta">Primero resuelva las {v.por_revisar} claves por revisar en el <button className="font-semibold underline" onClick={() => irA(1)}>paso 1</button>.</Aviso>}
              <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} />
                <span>Confirmo que revisé las {v.entradas_total} claves contra el documento fuente{v.agregadas_manual > 0 && <> y que las {v.agregadas_manual} claves agregadas a mano son correctas</>}.</span></label>
              {v.expedientes_por_actualizar > 0 && (
                <label className="flex items-start gap-2 rounded-2xl border border-turquesa/30 bg-turquesa-50/60 p-3 text-sm">
                  <input type="checkbox" className="mt-1" checked={actualizar} onChange={(e) => setActualizar(e.target.checked)} />
                  <span><b>Usar este catálogo en los {v.expedientes_por_actualizar} expediente(s) que están en revisión</b>, para que se recalculen con las claves nuevas.
                    <span className="block text-xs text-slate-500">Los expedientes ya validados no cambian nunca.</span></span>
                </label>
              )}
              <p className="text-xs text-slate-500">Al activarla, esta versión ya no se puede modificar y sustituye a la versión activa para los expedientes nuevos.</p>
              <div className="flex flex-wrap justify-between gap-2">
                <button className="btn-sec" onClick={() => irA(2)}>← Claves faltantes</button>
                <button className="btn-primario" disabled={!confirmo || v.por_revisar > 0}
                  onClick={() => cambio(async () => {
                    const r = await api.post(`/catalogos/versiones/${v.id}/activar`, { confirmo_revision: true, actualizar_expedientes: actualizar && v.expedientes_por_actualizar > 0 });
                    setActivada(r);
                  })}>Activar catálogo</button>
              </div>
            </div>
          )}
        </>
      )}
    </Shell>
  );
}
