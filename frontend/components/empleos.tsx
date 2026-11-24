import Link from "next/link";
import Logo from "@/components/Logo";
import { mxn } from "@/lib/api";

export async function pedirPublico(ruta: string, init: RequestInit = {}) {
  const r = await fetch(`/api${ruta}`, init);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "No se pudo completar. Intenta de nuevo.");
  return j;
}

export function CabeceraEmpleos() {
  return (
    <header className="border-b border-crema-300 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-3">
        <Link href="/" aria-label="Nomira, inicio"><Logo /></Link>
        <nav className="flex items-center gap-4 text-sm font-semibold"><Link href="/empleos" className="text-marino hover:underline">Bolsa de trabajo</Link>
          <Link href="/login?registro=1" className="btn-turquesa">Publica vacantes gratis</Link></nav>
      </div>
    </header>
  );
}

export function PieEmpleos() {
  return (
    <footer className="mt-12 border-t border-crema-300 py-6 text-center text-xs text-slate-500">
      Bolsa de trabajo jurídica de <Link href="/" className="underline">Nomira</Link> · <Link href="/legal/privacidad" className="underline">Aviso de privacidad</Link> ·{" "}
      <Link href="/legal/terminos" className="underline">Términos</Link>
    </footer>
  );
}

export function sueldoPublico(v: any) {
  if (!v.sueldo_min && !v.sueldo_max) return null;
  if (v.sueldo_min && v.sueldo_max) return `${mxn(v.sueldo_min)} – ${mxn(v.sueldo_max)} mensuales`;
  return v.sueldo_min ? `Desde ${mxn(v.sueldo_min)} mensuales` : `Hasta ${mxn(v.sueldo_max)} mensuales`;
}

export function TarjetaVacante({ v, despacho = true }: { v: any; despacho?: boolean }) {
  const s = sueldoPublico(v);
  return (
    <Link href={`/empleos/${v.codigo}`} className="tarjeta block p-4 transition hover:-translate-y-0.5 hover:shadow-flotante">
      <h2 className="font-semibold text-marino">{v.titulo}</h2>
      {despacho && v.despacho && <p className="text-sm text-slate-600">{v.despacho.nombre}</p>}
      <p className="mt-1 text-xs text-slate-500">{v.area_texto} · {v.jornada_texto} · {v.modalidad_texto}{v.estado_republica ? ` · ${v.ciudad ? v.ciudad + ", " : ""}${v.estado_republica}` : ""}</p>
      {s && <p className="mt-2 text-sm font-semibold text-turquesa-700">{s}</p>}
    </Link>
  );
}
