"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import { pedirPublico } from "@/components/empleos";
import { Aviso } from "@/components/ui";

/** Página donde el candidato contesta una prueba con su enlace personal. No muestra calificación: el resultado lo ve el despacho. */
export default function ContestarPrueba() {
  const { token } = useParams<{ token: string }>();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const [acepto, setAcepto] = useState(false);
  const [resp, setResp] = useState<(number | string | null)[]>([]);
  const [enviando, setEnviando] = useState(false);
  const [terminado, setTerminado] = useState(false);
  const [ahora, setAhora] = useState(Date.now());
  const clave = `nomira:prueba:${token}`;
  useEffect(() => { pedirPublico(`/prueba/${token}`).then(setD).catch((e) => setError(e.message)); }, [token]);
  useEffect(() => {  // respuestas guardadas en este navegador por si se cierra la pestaña
    try { const g = localStorage.getItem(clave); if (g) setResp(JSON.parse(g)); } catch { /* sin almacenamiento */ }
  }, [clave]);
  useEffect(() => { try { if (resp.length) localStorage.setItem(clave, JSON.stringify(resp)); } catch { /* sin almacenamiento */ } }, [resp, clave]);
  useEffect(() => { const t = setInterval(() => setAhora(Date.now()), 1000); return () => clearInterval(t); }, []);

  async function iniciar() {
    setError("");
    try { setD(await pedirPublico(`/prueba/${token}/iniciar`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ acepto }) })); }
    catch (e: any) { setError(e.message); }
  }
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEnviando(true);
    const n = d.prueba.preguntas.length;
    const respuestas = Array.from({ length: n }, (_, i) => resp[i] ?? null);
    try {
      await pedirPublico(`/prueba/${token}/responder`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ respuestas }) });
      try { localStorage.removeItem(clave); } catch { /* nada */ }
      setTerminado(true);
    } catch (er: any) { setError(er.message); } finally { setEnviando(false); }
  }
  const p = d?.prueba;
  const faltan = p?.preguntas ? p.preguntas.filter((_: any, i: number) => resp[i] === undefined || resp[i] === null || resp[i] === "").length : 0;
  const restante = p?.minutos && d?.iniciada_en ? Math.round((new Date(d.iniciada_en).getTime() + p.minutos * 60000 - ahora) / 1000) : null;
  const pon = (i: number, v: number | string) => { const x = [...resp]; x[i] = v; setResp(x); };
  return (
    <div className="min-h-screen bg-crema">
      <header className="border-b border-crema-300 bg-white/80"><div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-3"><Logo />
        {restante !== null && !terminado && <span className={`rounded-full px-3 py-1 text-sm font-semibold ${restante < 60 ? "bg-red-100 text-red-800" : "bg-crema text-marino"}`} aria-live="polite">
          {restante > 0 ? `Tiempo sugerido: ${Math.floor(restante / 60)}:${String(restante % 60).padStart(2, "0")}` : "Tiempo sugerido terminado"}</span>}</div></header>
      <main className="mx-auto max-w-3xl px-5 py-8">
        <Aviso>{error}</Aviso>
        {terminado && <div className="tarjeta p-6 text-center" role="status"><h1 className="text-2xl font-extrabold text-marino">¡Gracias! Terminaste la prueba</h1>
          <p className="mt-2 text-slate-600">{d.despacho} recibirá tus respuestas. Ya puedes cerrar esta página.</p></div>}
        {d && !terminado && d.estado === "terminada" && <div className="tarjeta p-6 text-center"><h1 className="text-xl font-bold text-marino">Ya contestaste esta prueba</h1></div>}
        {d && !terminado && (d.estado === "vencida" || d.estado === "cancelada") && <div className="tarjeta p-6 text-center">
          <h1 className="text-xl font-bold text-marino">Este enlace ya no está disponible</h1><p className="mt-2 text-slate-600">Si crees que es un error, escribe a {d.despacho}.</p></div>}

        {d && !terminado && d.estado === "enviada" && p && <div className="tarjeta space-y-4 p-6">
          <p className="text-sm text-slate-500">Hola {d.candidato}, {d.despacho} te invita a contestar:</p>
          <h1 className="text-2xl font-extrabold text-marino">{p.nombre}</h1>
          <p className="text-slate-700">{p.n} preguntas{p.minutos ? ` · unos ${p.minutos} minutos` : ""}. {p.instrucciones}</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
            <li>Busca un lugar tranquilo y contesta tú solo(a).</li><li>Puedes contestar desde tu celular. Si se cierra la página, tus respuestas se guardan en este navegador.</li>
            <li>Al terminar no verás calificación: el resultado lo revisa el despacho como un dato más de tu proceso.</li></ul>
          <label className="flex gap-2 text-sm text-slate-700"><input type="checkbox" className="mt-1" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} />
            <span>Acepto que {d.despacho} use mis respuestas solo para este proceso de selección.{d.correo_privacidad ? ` Puedo pedir que las borren escribiendo a ${d.correo_privacidad}.` : ""} Ver el <Link href="/legal/privacidad" target="_blank" className="underline">aviso de privacidad</Link>.</span></label>
          <button className="btn-turquesa" disabled={!acepto} onClick={iniciar}>Empezar</button>
        </div>}

        {d && !terminado && d.estado === "en_curso" && p?.preguntas && <form className="space-y-4" onSubmit={enviar}>
          <h1 className="text-2xl font-extrabold text-marino">{p.nombre}</h1>
          {p.instrucciones && <p className="text-slate-600">{p.instrucciones}</p>}
          <ol className="space-y-3">{p.preguntas.map((q: any, i: number) => (
            <li key={i} className="tarjeta p-4"><fieldset><legend className="font-semibold text-marino">{i + 1}. {q.texto}</legend>
              {q.opciones.length ? <div className={`mt-2 grid gap-2 ${p.tipo === "likert" ? "sm:grid-cols-5" : ""}`}>{q.opciones.map((o: string, j: number) => (
                <label key={j} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${resp[i] === j ? "border-turquesa bg-turquesa-50" : "border-crema-300 bg-white"}`}>
                  <input type="radio" name={`p${i}`} checked={resp[i] === j} onChange={() => pon(i, j)} />{o}</label>))}</div>
                : <textarea className="campo mt-2 min-h-24" aria-label={`Respuesta ${i + 1}`} value={(resp[i] as string) || ""} onChange={(e) => pon(i, e.target.value)} maxLength={4000} />}
            </fieldset></li>))}</ol>
          <div className="tarjeta sticky bottom-3 flex flex-wrap items-center justify-between gap-2 p-3">
            <span className="text-sm text-slate-600">{faltan ? `Te faltan ${faltan} pregunta${faltan === 1 ? "" : "s"}` : "Contestaste todo"}</span>
            <button className="btn-turquesa" disabled={enviando}>{enviando ? "Enviando…" : "Terminar y enviar"}</button></div>
        </form>}
      </main>
    </div>
  );
}
