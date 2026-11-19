"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import ShellPlataforma, { Credenciales, EstadoSuscripcion, RegistrarPeriodo, Tarjeta } from "@/components/plataforma";
import { Aviso, Avatar, Chip, Modal } from "@/components/ui";
import { fecha, fechaHora, mxn } from "@/lib/api";
import { apiP, avisarContadores } from "@/lib/plataforma";

const ROLES: Record<string, string> = { administrador: "Administrador", analista: "Analista", consulta: "Consulta" };

export default function Cliente() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [acceso, setAcceso] = useState<{ a: any; t: string } | null>(null);
  const [dialogo, setDialogo] = useState<"suspender" | "eliminar" | "usuario" | "mensaje" | "nombre" | null>(null);
  const cargar = useCallback(() => apiP.get(`/clientes/${id}`).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  async function accion(fn: () => Promise<any>, mensaje: string) {
    setError(""); setOk("");
    try { const r = await fn(); setOk(mensaje); await cargar(); return r; } catch (e: any) { setError(e.message); }
  }
  if (!c) return <ShellPlataforma><Aviso>{error}</Aviso>{!error && <p className="text-sm text-slate-500">Cargando…</p>}</ShellPlataforma>;
  const activa = c.estado === "activa";
  return (
    <ShellPlataforma>
      <Link href="/plataforma/clientes" className="text-sm text-turquesa-700 hover:underline">← Clientes</Link>
      <div className="mb-2 mt-1 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-extrabold text-marino">{c.nombre}</h1>
        <Chip estado={activa ? "activo" : "error"} texto={activa ? "Activa" : "Suspendida"} />
        <button className="text-sm font-semibold text-turquesa-700 hover:underline" onClick={() => setDialogo("nombre")}>Cambiar nombre</button>
      </div>
      <p className="mb-5 text-sm text-slate-500">Cliente #{c.id} · alta el {fecha(c.creado_en)}</p>
      {!activa && <div className="mb-4"><Aviso tipo="alerta"><b>Cuenta suspendida.</b> Nadie de esta empresa puede entrar.{c.motivo_suspension && <> Motivo: {c.motivo_suspension}</>}</Aviso></div>}
      <div className="mb-4 space-y-2"><Aviso>{error}</Aviso><Aviso tipo="ok">{ok}</Aviso></div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Tarjeta etiqueta="Usuarios activos" valor={c.usuarios_activos} nota={`${c.usuarios} en total`} />
        <Tarjeta etiqueta="Expedientes" valor={c.expedientes} nota="Solo el número: el contenido es privado del cliente" />
        <Tarjeta etiqueta="Último acceso" valor={<span className="text-xl">{c.ultimo_acceso ? fecha(c.ultimo_acceso) : "Nunca"}</span>} />
        <Tarjeta etiqueta="Soporte abierto" valor={c.tickets_abiertos} alerta={c.tickets_abiertos > 0} href="/plataforma/soporte" />
      </div>

      <Suscripcion c={c} onCambio={(m) => { setOk(m); setError(""); avisarContadores(); cargar(); }} onError={setError} />

      {c.modulos && (
        <section className="tarjeta mt-6 p-5">
          <h2 className="font-semibold text-marino">Módulos contratados</h2>
          <p className="mt-1 text-sm text-slate-500">Lo que marque aquí queda disponible y activo para el cliente; su administrador puede desactivarlo en «Mi empresa». Retirar un módulo lo oculta pero no borra sus datos.</p>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {Object.values(c.modulos as Record<string, any>).map((md) => (
              <label key={md.clave} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 ${md.contratado ? "border-turquesa bg-turquesa-50/60" : "border-crema-300"}`}>
                <input type="checkbox" className="mt-1 h-4 w-4 accent-turquesa" checked={md.contratado}
                  onChange={(e) => {
                    const contratado = e.target.checked;
                    if (!contratado && !confirm(`¿Retirar «${md.nombre}» a ${c.nombre}? Dejarán de verlo; sus datos se conservan.`)) return;
                    accion(() => apiP.patch(`/clientes/${c.id}/modulos/${md.clave}`, { contratado }), contratado ? "Módulo contratado." : "Módulo retirado.");
                  }} />
                <span>
                  <span className="block font-semibold text-marino">{md.nombre}</span>
                  <span className="block text-xs text-slate-600">{md.descripcion}</span>
                  <span className="mt-1 block text-xs font-semibold text-slate-500">{md.contratado ? (md.activo ? "Contratado · activo" : "Contratado · desactivado por el cliente") : "No contratado"}</span>
                </span>
              </label>
            ))}
          </div>
          {c.modulos.afore?.contratado && (
            <label className="mt-3 flex items-start gap-2 rounded-xl border border-crema-300 p-3 text-sm">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-turquesa" checked={!!c.curp_oficial_autorizado}
                onChange={(e) => accion(() => apiP.patch(`/clientes/${c.id}/curp-oficial`, { autorizado: e.target.checked }),
                  e.target.checked ? "Consulta oficial de CURP autorizada para este cliente." : "Consulta oficial de CURP retirada.")} />
              <span><b className="text-marino">Nomira AFORE: autorizar consulta oficial de CURP</b>
                <span className="block text-xs text-slate-500">Márquelo solo si el despacho acreditó su autorización. Además se requieren las credenciales del servicio oficial en el servidor (CURP_API_URL y CURP_API_KEY); sin ellas sigue «no configurada».</span></span>
            </label>
          )}
        </section>
      )}

      <section className="tarjeta mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-crema-300 px-5 py-3">
          <h2 className="font-semibold text-marino">Usuarios del cliente</h2>
          <div className="flex gap-2">
            <button className="btn-sec" onClick={() => setDialogo("mensaje")}>Enviar mensaje</button>
            <button className="btn-turquesa" onClick={() => setDialogo("usuario")}>+ Agregar usuario</button>
          </div>
        </div>
        <ul className="divide-y divide-crema-300">
          {c.usuarios_detalle.length === 0 && <li className="p-5 text-sm text-slate-500">Sin usuarios.</li>}
          {c.usuarios_detalle.map((u: any) => (
            <li key={u.id} className={`flex flex-wrap items-center gap-4 p-4 ${u.activo ? "" : "bg-slate-50/70"}`}>
              <div className={u.activo ? "" : "opacity-50 grayscale"}><Avatar nombre={u.nombre} tam={40} /></div>
              <div className="min-w-[12rem] flex-1">
                <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-marino">{u.nombre}</span>
                  <span className="rounded-full bg-marino-50 px-2 py-0.5 text-[11px] font-semibold text-marino">{ROLES[u.rol]}</span>
                  {!u.activo && <Chip estado="archivado" texto="Desactivado" />}</div>
                <div className="text-sm text-slate-500">{u.email} · último acceso: {u.ultimo_acceso ? fechaHora(u.ultimo_acceso) : "nunca"}</div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button className="btn-sec" title="Genera una contraseña temporal y cierra sus sesiones"
                  onClick={async () => { if (!confirm(`¿Generar una contraseña temporal nueva para ${u.nombre}? La actual dejará de servir.`)) return;
                    const r = await accion(() => apiP.post(`/clientes/${c.id}/usuarios/${u.id}/restablecer`), `Contraseña de ${u.nombre} restablecida.`);
                    if (r) setAcceso({ a: r.acceso, t: "Contraseña restablecida" }); }}>Restablecer contraseña</button>
                <button className="btn-sec" title="Quita el bloqueo por muchos intentos fallidos"
                  onClick={() => accion(async () => { const r = await apiP.post(`/clientes/${c.id}/usuarios/${u.id}/desbloquear`);
                    if (!r.estaba_bloqueado) throw new Error(`${u.nombre} no estaba bloqueado.`); }, `${u.nombre} ya puede volver a intentar entrar.`)}>Desbloquear</button>
                <button className="btn-sec" onClick={() => accion(() => apiP.patch(`/clientes/${c.id}/usuarios/${u.id}`, { activo: !u.activo }),
                  u.activo ? `${u.nombre} desactivado.` : `${u.nombre} reactivado.`)}>{u.activo ? "Desactivar" : "Reactivar"}</button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-6 rounded-2xl border border-red-200 bg-red-50/40 p-5">
        <h2 className="font-semibold text-red-800">Zona delicada</h2>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-b border-red-100 pb-3">
          <div className="text-sm text-slate-700"><b>{activa ? "Suspender la cuenta" : "Reactivar la cuenta"}</b><br />
            <span className="text-slate-500">{activa ? "Nadie de la empresa podrá entrar; sus datos se conservan." : "Sus usuarios podrán volver a entrar."}</span></div>
          {activa
            ? <button className="btn-sec" onClick={() => setDialogo("suspender")}>Suspender</button>
            : <button className="btn-turquesa" onClick={() => accion(() => apiP.patch(`/clientes/${c.id}`, { estado: "activa" }), "Cuenta reactivada.")}>Reactivar</button>}
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-700"><b>Eliminar la cuenta</b><br />
            <span className="text-slate-500">Borra la empresa con todos sus usuarios, expedientes, PDF y catálogos. No se puede deshacer.</span></div>
          <button className="btn-peligro" onClick={() => setDialogo("eliminar")}>Eliminar cliente</button>
        </div>
      </section>

      {dialogo === "nombre" && <CambiarNombre c={c} onCerrar={() => setDialogo(null)} onGuardar={async (n) => { await accion(() => apiP.patch(`/clientes/${c.id}`, { nombre: n }), "Nombre actualizado."); setDialogo(null); }} />}
      {dialogo === "suspender" && <Suspender c={c} onCerrar={() => setDialogo(null)} onSuspender={async (m) => { await accion(() => apiP.patch(`/clientes/${c.id}`, { estado: "suspendida", motivo: m }), "Cuenta suspendida: sus sesiones se cerraron."); setDialogo(null); }} />}
      {dialogo === "eliminar" && <Eliminar c={c} onCerrar={() => setDialogo(null)} onEliminado={() => router.replace("/plataforma/clientes")} />}
      {dialogo === "usuario" && <AgregarUsuario c={c} onCerrar={() => setDialogo(null)} onListo={(r) => { setDialogo(null); setAcceso({ a: r.acceso, t: "Usuario creado: datos de acceso" }); cargar(); }} />}
      {dialogo === "mensaje" && <NuevoMensaje c={c} onCerrar={() => setDialogo(null)} onListo={(t) => router.push(`/plataforma/soporte?t=${t.id}`)} />}
      {acceso && <Credenciales acceso={acceso.a} titulo={acceso.t} onCerrar={() => setAcceso(null)} />}
    </ShellPlataforma>
  );
}

function CambiarNombre({ c, onCerrar, onGuardar }: { c: any; onCerrar: () => void; onGuardar: (n: string) => void }) {
  const [n, setN] = useState(c.nombre);
  return (
    <Modal titulo="Cambiar nombre del cliente" onCerrar={onCerrar}>
      <input className="campo" value={n} minLength={2} onChange={(e) => setN(e.target.value)} autoFocus />
      <div className="mt-3 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
        <button className="btn-primario" disabled={n.trim().length < 2} onClick={() => onGuardar(n.trim())}>Guardar</button></div>
    </Modal>
  );
}

function Suspender({ c, onCerrar, onSuspender }: { c: any; onCerrar: () => void; onSuspender: (m: string) => void }) {
  const [m, setM] = useState("");
  return (
    <Modal titulo={`Suspender a ${c.nombre}`} onCerrar={onCerrar}>
      <p className="text-sm text-slate-700">Se cerrarán al instante las sesiones de sus {c.usuarios_activos} usuario(s) y no podrán entrar hasta que reactive la cuenta. Sus datos no se borran.</p>
      <label className="mt-3 block"><span className="etiqueta">Motivo (opcional, interno)</span>
        <input className="campo" maxLength={300} value={m} onChange={(e) => setM(e.target.value)} placeholder="Ej. Falta de pago" /></label>
      <div className="mt-4 flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar}>Cancelar</button>
        <button className="btn bg-amber-600 text-white hover:bg-amber-700" onClick={() => onSuspender(m)}>Suspender cuenta</button></div>
    </Modal>
  );
}

function Eliminar({ c, onCerrar, onEliminado }: { c: any; onCerrar: () => void; onEliminado: () => void }) {
  const [n, setN] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  async function eliminar() {
    setError(""); setEnviando(true);
    try { await apiP.post(`/clientes/${c.id}/eliminar`, { confirmar_nombre: n }); onEliminado(); }
    catch (e: any) { setError(e.message); setEnviando(false); }
  }
  return (
    <Modal titulo="Eliminar cliente" onCerrar={onCerrar}>
      <div className="space-y-3 text-sm text-slate-700">
        <p>Se borrará <b>{c.nombre}</b> con sus <b>{c.usuarios} usuario(s)</b>, sus <b>{c.expedientes} expediente(s)</b>, los PDF, catálogos y mensajes de soporte.</p>
        <p className="font-semibold text-red-700">No se puede deshacer. Considere suspender la cuenta en su lugar.</p>
        <label className="block"><span className="etiqueta">Para confirmar, escriba el nombre exacto: {c.nombre}</span>
          <input className="campo" value={n} onChange={(e) => setN(e.target.value)} autoFocus /></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button className="btn-sec" onClick={onCerrar} disabled={enviando}>Cancelar</button>
          <button className="btn bg-red-600 text-white hover:bg-red-700 disabled:opacity-50" disabled={n.trim() !== c.nombre || enviando} onClick={eliminar}>
            {enviando ? "Eliminando…" : "Eliminar para siempre"}</button></div>
      </div>
    </Modal>
  );
}

function AgregarUsuario({ c, onCerrar, onListo }: { c: any; onCerrar: () => void; onListo: (r: any) => void }) {
  const [f, setF] = useState({ nombre: "", email: "", rol: "administrador" });
  const [error, setError] = useState("");
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { onListo(await apiP.post(`/clientes/${c.id}/usuarios`, f)); } catch (err: any) { setError(err.message); }
  }
  return (
    <Modal titulo={`Agregar usuario a ${c.nombre}`} onCerrar={onCerrar}>
      <form className="space-y-3" onSubmit={enviar}>
        <p className="text-sm text-slate-600">Útil si el cliente perdió el acceso de todos sus administradores. Normalmente cada cliente da de alta a su propio equipo.</p>
        <label className="block"><span className="etiqueta">Nombre</span><input className="campo" required minLength={2} autoFocus value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Correo</span><input className="campo" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Rol</span>
          <select className="campo" value={f.rol} onChange={(e) => setF({ ...f, rol: e.target.value })}>
            {Object.entries(ROLES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Crear usuario</button></div>
      </form>
    </Modal>
  );
}

function NuevoMensaje({ c, onCerrar, onListo }: { c: any; onCerrar: () => void; onListo: (t: any) => void }) {
  const [f, setF] = useState({ asunto: "", texto: "" });
  const [error, setError] = useState("");
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { onListo(await apiP.post("/soporte", { organizacion_id: c.id, ...f })); } catch (err: any) { setError(err.message); }
  }
  return (
    <Modal titulo={`Mensaje para ${c.nombre}`} onCerrar={onCerrar} ancho="max-w-xl">
      <form className="space-y-3" onSubmit={enviar}>
        <label className="block"><span className="etiqueta">Asunto</span><input className="campo" required minLength={2} maxLength={200} autoFocus value={f.asunto} onChange={(e) => setF({ ...f, asunto: e.target.value })} /></label>
        <label className="block"><span className="etiqueta">Mensaje</span><textarea className="campo h-36" required maxLength={5000} value={f.texto} onChange={(e) => setF({ ...f, texto: e.target.value })} /></label>
        <p className="text-xs text-slate-500">Lo verá cualquier usuario del cliente en su sección «Soporte».</p>
        <Aviso>{error}</Aviso>
        <div className="flex justify-end gap-2"><button type="button" className="btn-sec" onClick={onCerrar}>Cancelar</button><button className="btn-primario">Enviar</button></div>
      </form>
    </Modal>
  );
}

function Suscripcion({ c, onCambio, onError }: { c: any; onCambio: (m: string) => void; onError: (m: string) => void }) {
  const [s, setS] = useState<any>(null);
  const [registrar, setRegistrar] = useState(false);
  const cargar = useCallback(() => apiP.get(`/clientes/${c.id}/suscripcion`).then(setS).catch((e) => onError(e.message)), [c.id, onError]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (s && window.location.hash === "#suscripcion") document.getElementById("suscripcion")?.scrollIntoView({ block: "start" }); }, [s]);
  const accion = async (fn: () => Promise<any>, m: string) => { try { setS(await fn()); onCambio(m); } catch (e: any) { onError(e.message); } };
  if (!s) return null;
  const aviso: Record<string, string> = {
    prueba: "border-sky-200 bg-sky-50/60", activa: "border-emerald-200 bg-emerald-50/50", por_vencer: "border-amber-300 bg-amber-50",
    vencida: "border-red-200 bg-red-50/60", programada: "border-crema-300 bg-white", sin_plan: "border-crema-300 bg-white",
  };
  return (
    <section id="suscripcion" className={`mt-6 scroll-mt-6 rounded-3xl border p-5 ${aviso[s.estado]}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="etiqueta">Suscripción</div>
          <div className="mt-1 flex flex-wrap items-center gap-2"><EstadoSuscripcion s={s} />
            {s.pagos_pendientes > 0 && <span className="text-sm font-semibold text-amber-700">· {s.pagos_pendientes} pago(s) pendiente(s){s.monto_pendiente && Number(s.monto_pendiente) > 0 ? ` (${mxn(s.monto_pendiente)})` : ""}</span>}</div>
          {s.inicio && <p className="mt-2 text-sm text-slate-600">{s.estado === "vencida" ? "Su último periodo" : "Periodo"}: <b>{s.plan_nombre}</b>, del {fecha(s.inicio)} al {fecha(s.fin)}.</p>}
          {s.siguiente && <p className="text-sm text-emerald-700">✓ Renovación registrada: {s.siguiente.plan_nombre} desde el {fecha(s.siguiente.inicio)}.</p>}
          {s.recordatorios?.[0] && <p className={`text-sm ${s.recordatorios[0].estado === "enviado" ? "text-slate-600" : "text-red-700"}`}>
            ✉️ {s.recordatorios[0].estado === "enviado" ? `Recordatorio de vencimiento enviado el ${fechaHora(s.recordatorios[0].fecha)} a ${s.recordatorios[0].destinatarios}.`
              : `No se pudo enviar el recordatorio (${fechaHora(s.recordatorios[0].fecha)}): ${s.recordatorios[0].error}`}</p>}
          {s.estado === "vencida" && c.estado === "activa" && <p className="mt-1 text-xs text-slate-500">La cuenta sigue abierta. Si no renueva, puede suspenderla en la zona delicada.</p>}
        </div>
        <button className="btn-turquesa" onClick={() => setRegistrar(true)}>{["sin_plan", "vencida"].includes(s.estado) ? "Registrar venta" : "Renovar / agregar periodo"}</button>
      </div>
      {s.periodos.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-2xl border border-crema-300 bg-white">
          <table className="tabla">
            <thead><tr><th>Plan</th><th>Inicio</th><th>Vence</th><th className="num">Monto</th><th>Pago</th><th>Nota</th><th></th></tr></thead>
            <tbody>
              {s.periodos.map((p: any) => (
                <tr key={p.id} className={p.situacion === "vigente" ? "bg-turquesa-50/40" : ""}>
                  <td className="whitespace-nowrap font-semibold text-marino">{p.plan_nombre}
                    <div className="text-[11px] font-normal text-slate-500">{p.situacion === "vigente" ? "Vigente" : p.situacion === "futuro" ? "Próximo" : "Terminado"}</div></td>
                  <td className="whitespace-nowrap">{fecha(p.inicio)}</td>
                  <td className="whitespace-nowrap">{fecha(p.fin)}</td>
                  <td className="num">{p.monto !== null ? mxn(p.monto) : <span className="text-slate-400">—</span>}</td>
                  <td className="whitespace-nowrap">{p.plan === "prueba" ? <span className="text-xs text-slate-400">Gratis</span>
                    : p.pagado ? <span className="text-xs font-semibold text-emerald-700">✓ Pagado {fecha(p.pagado_en)}</span>
                    : <button className="text-xs font-semibold text-amber-700 hover:underline" onClick={() => accion(() => apiP.patch(`/periodos/${p.id}`, { pagado: true }), "Pago registrado.")}>Pendiente · marcar pagado</button>}</td>
                  <td className="max-w-[16rem] truncate text-sm text-slate-600" title={p.nota || ""}>{p.nota || ""}</td>
                  <td className="whitespace-nowrap text-right">
                    {p.pagado && <button className="mr-2 text-xs text-slate-500 hover:underline" onClick={() => accion(() => apiP.patch(`/periodos/${p.id}`, { pagado: false }), "Pago desmarcado.")}>Desmarcar pago</button>}
                    <button className="text-xs text-red-600 hover:underline" onClick={() => { if (confirm(`¿Borrar el periodo ${p.plan_nombre.toLowerCase()} del ${fecha(p.inicio)} al ${fecha(p.fin)}? Úselo solo para corregir un error de captura.`)) accion(() => apiP.borrar(`/periodos/${p.id}`), "Periodo borrado."); }}>Borrar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {registrar && <RegistrarPeriodo cliente={c} s={s} onCerrar={() => setRegistrar(false)} onListo={(nuevo) => { setS(nuevo); setRegistrar(false); onCambio("Periodo registrado."); }} />}
    </section>
  );
}
