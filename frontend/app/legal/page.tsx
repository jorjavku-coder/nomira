"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { MarcoLegal, RUTA_DOC, legalPublico } from "@/components/legal";
import { fecha } from "@/lib/api";

export default function CentroLegal() {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { legalPublico("/documentos").then(setR).catch((e) => setError(e.message)); }, []);
  return (
    <MarcoLegal>
      <h1 className="text-3xl font-extrabold text-marino sm:text-4xl">Centro legal</h1>
      <p className="mt-2 text-slate-600">Documentos que rigen el uso de Nomira y el tratamiento de datos personales, con su historial de versiones.</p>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      {!r && !error && <p className="mt-6 text-sm text-slate-500">Cargando…</p>}
      {r && <>
        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {r.documentos.map((d: any) => (
            <li key={d.clave}>
              <Link href={RUTA_DOC[d.clave]} className="tarjeta block h-full p-5 transition hover:-translate-y-0.5 hover:border-turquesa/40">
                <h2 className="font-bold text-marino">{d.titulo}</h2>
                <p className="mt-1 text-sm text-slate-600">{d.descripcion}</p>
                <p className="mt-3 text-xs font-semibold">{d.vigente
                  ? <span className="text-emerald-700">Versión {d.vigente.version} · vigente desde {fecha(d.vigente.vigente_desde || d.vigente.publicado_en)}</span>
                  : <span className="text-amber-700">En preparación</span>}</p>
              </Link>
            </li>))}
        </ul>
        <section className="tarjeta mt-8 p-6">
          <h2 className="text-lg font-bold text-marino">Sus datos personales: contacto y derechos ARCO</h2>
          <p className="mt-2 text-sm text-slate-600">Puede solicitar el acceso, la rectificación, la cancelación u oposición al tratamiento de sus datos, revocar su consentimiento o limitar su uso.</p>
          <ul className="mt-3 space-y-1 text-sm">
            {r.contacto.responsable_datos && <li>Responsable de atender solicitudes: <b>{r.contacto.responsable_datos}</b></li>}
            {r.contacto.correo_privacidad ? <li>Correo de privacidad: <a className="font-semibold text-turquesa-700 underline" href={`mailto:${r.contacto.correo_privacidad}`}>{r.contacto.correo_privacidad}</a></li>
              : <li className="text-slate-500">El correo de privacidad se publicará aquí. Mientras tanto, use el formulario.</li>}
          </ul>
          <Link href="/legal/solicitudes" className="btn-turquesa mt-4">Enviar una solicitud</Link>
          <p className="mt-3 text-xs text-slate-500">Si usted es cliente de un despacho que usa Nomira, el despacho es quien decide sobre sus datos: le conviene dirigirse primero a él. Si nos escribe, canalizaremos su solicitud.</p>
        </section>
      </>}
    </MarcoLegal>
  );
}
