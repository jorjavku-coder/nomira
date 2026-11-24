"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CabeceraEmpleos, PieEmpleos, pedirPublico, sueldoPublico } from "@/components/empleos";
import { Aviso } from "@/components/ui";

const fecha = (s: string) => new Date(s).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" });

export default function VacantePublica() {
  const { codigo } = useParams<{ codigo: string }>();
  const [v, setV] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { pedirPublico(`/empleos/vacante/${codigo}`).then(setV).catch((e) => setError(e.message)); }, [codigo]);
  return (
    <>
      <CabeceraEmpleos />
      <main className="mx-auto max-w-5xl px-5 py-8">
        <Link href="/empleos" className="text-sm font-semibold text-turquesa-700">← Todas las vacantes</Link>
        <div className="mt-3"><Aviso>{error}</Aviso></div>
        {v && <div className="mt-3 grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <article>
            <h1 className="font-marca text-3xl font-extrabold text-marino">{v.titulo}</h1>
            {v.despacho && <p className="mt-1 text-slate-700"><Link href={`/empleos/despacho/${v.despacho.codigo}`} className="font-semibold hover:underline">{v.despacho.nombre}</Link></p>}
            <ul className="mt-3 flex flex-wrap gap-2 text-xs">{[v.puesto_texto, v.area_texto, v.jornada_texto, v.modalidad_texto,
              v.estado_republica && `${v.ciudad ? v.ciudad + ", " : ""}${v.estado_republica}`].filter(Boolean).map((t: string) =>
              <li key={t} className="rounded-full bg-white px-3 py-1 text-slate-700 ring-1 ring-crema-300">{t}</li>)}</ul>
            {sueldoPublico(v) && <p className="mt-3 text-lg font-semibold text-turquesa-700">{sueldoPublico(v)}</p>}
            {v.publicada_en && <p className="mt-1 text-xs text-slate-500">Publicada el {fecha(v.publicada_en)}</p>}
            <h2 className="mt-6 text-lg font-bold text-marino">Lo que harás</h2><p className="mt-1 whitespace-pre-wrap text-slate-700">{v.descripcion}</p>
            {v.requisitos && <><h2 className="mt-5 text-lg font-bold text-marino">Requisitos</h2><p className="mt-1 whitespace-pre-wrap text-slate-700">{v.requisitos}</p></>}
            {v.ofrecemos && <><h2 className="mt-5 text-lg font-bold text-marino">Ofrecemos</h2><p className="mt-1 whitespace-pre-wrap text-slate-700">{v.ofrecemos}</p></>}
          </article>
          <aside>{v.recibe ? <Postular v={v} codigo={codigo} /> : <p className="tarjeta p-5 text-slate-600">Esta vacante ya no recibe postulaciones.</p>}</aside>
        </div>}
      </main>
      <PieEmpleos />
    </>
  );
}

function Postular({ v, codigo }: { v: any; codigo: string }) {
  const [f, setF] = useState({ nombre: "", email: "", telefono: "", ciudad: "", cedula: "", experiencia: "", mensaje: "", sitio_web: "" });
  const [acepto, setAcepto] = useState(false);
  const [estado, setEstado] = useState<"" | "enviando" | "listo" | "repetida">("");
  const [error, setError] = useState("");
  const cv = useRef<HTMLInputElement>(null);
  const pon = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  async function enviar(e: React.FormEvent) {
    e.preventDefault(); setError(""); setEstado("enviando");
    const d = new FormData();
    Object.entries(f).forEach(([k, x]) => x && d.append(k, x));
    d.append("acepto", String(acepto));
    const archivo = cv.current?.files?.[0];
    if (archivo) d.append("cv", archivo);
    try { const r = await pedirPublico(`/empleos/vacante/${codigo}/postular`, { method: "POST", body: d }); setEstado(r.repetida ? "repetida" : "listo"); }
    catch (er: any) { setError(er.message); setEstado(""); }
  }
  if (estado === "listo" || estado === "repetida") return (
    <div className="tarjeta p-5" role="status"><h2 className="text-xl font-extrabold text-marino">{estado === "listo" ? "¡Listo, ya te postulaste!" : "Ya te habías postulado"}</h2>
      <p className="mt-2 text-slate-600">{v.despacho?.nombre || "El despacho"} revisará tu información. Si avanzas, te contactarán por correo o teléfono; a veces te mandarán un enlace para contestar pruebas en línea.</p></div>);
  return (
    <form className="tarjeta space-y-3 p-5" onSubmit={enviar} aria-label="Postularme">
      <h2 className="text-xl font-extrabold text-marino">Postularme</h2>
      <label className="block"><span className="etiqueta">Nombre completo</span><input className="campo" value={f.nombre} onChange={pon("nombre")} required minLength={3} maxLength={200} autoComplete="name" /></label>
      <label className="block"><span className="etiqueta">Correo</span><input className="campo" type="email" value={f.email} onChange={pon("email")} required autoComplete="email" /></label>
      <label className="block"><span className="etiqueta">Teléfono (WhatsApp)</span><input className="campo" type="tel" value={f.telefono} onChange={pon("telefono")} maxLength={30} autoComplete="tel" /></label>
      <label className="block"><span className="etiqueta">Ciudad donde vives</span><input className="campo" value={f.ciudad} onChange={pon("ciudad")} maxLength={120} /></label>
      <div className="grid grid-cols-2 gap-2">
        <label className="block"><span className="etiqueta">Experiencia</span><select className="campo" value={f.experiencia} onChange={pon("experiencia")}><option value="">—</option>
          {Object.entries(v.experiencia).map(([k, t]) => <option key={k} value={k}>{t as string}</option>)}</select></label>
        <label className="block"><span className="etiqueta">Cédula (opcional)</span><input className="campo" inputMode="numeric" value={f.cedula} onChange={(e) => setF({ ...f, cedula: e.target.value.replace(/\D/g, "").slice(0, 8) })} /></label></div>
      <label className="block"><span className="etiqueta">CV en PDF o Word (máx. 5 MB)</span><input ref={cv} className="campo" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" /></label>
      <label className="block"><span className="etiqueta">¿Por qué te interesa? (opcional)</span><textarea className="campo min-h-20" value={f.mensaje} onChange={pon("mensaje")} maxLength={4000} /></label>
      <div aria-hidden className="absolute -left-[9999px]"><label>Sitio web<input tabIndex={-1} autoComplete="off" value={f.sitio_web} onChange={pon("sitio_web")} /></label></div>
      <label className="flex gap-2 text-xs text-slate-600"><input type="checkbox" className="mt-0.5" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} required />
        <span>Acepto que {v.despacho?.nombre || "el despacho"} use mis datos y mi CV solo para este proceso de selección. Nomira los guarda por cuenta del despacho y no los comparte con otros.
          {v.correo_privacidad ? <> Para consultarlos o pedir que se borren escribe a {v.correo_privacidad}.</> : null} Consulta el <Link href="/legal/privacidad" className="underline" target="_blank">aviso de privacidad</Link>.</span></label>
      <Aviso>{error}</Aviso>
      <button className="btn-turquesa w-full" disabled={estado === "enviando"}>{estado === "enviando" ? "Enviando…" : "Enviar postulación"}</button>
    </form>
  );
}
