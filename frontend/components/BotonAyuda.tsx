import Link from "next/link";

/** Acceso directo al manual del módulo, visible en el encabezado de cada módulo. */
export default function BotonAyuda({ modulo, className = "" }: { modulo: string; className?: string }) {
  return (
    <Link href={`/ayuda/${modulo}`} className={`inline-flex items-center gap-1.5 rounded-full border border-turquesa/40 bg-turquesa-50 px-3 py-1 text-xs font-semibold text-turquesa-700 transition hover:bg-turquesa-100 ${className}`}>
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" aria-hidden>
        <circle cx="12" cy="12" r="9" /><path d="M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.6M12 17h.01" />
      </svg>
      ¿Cómo se usa?
    </Link>
  );
}
