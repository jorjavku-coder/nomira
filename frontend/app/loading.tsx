import { LogoCargando } from "@/components/CargaNomira";

/** Mientras se abre una página: el logotipo de Nomira animado. */
export default function Cargando() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3" role="status" aria-live="polite">
      <LogoCargando className="h-16 w-16" />
      <p className="font-marca text-sm font-semibold text-marino">Cargando…</p>
    </div>
  );
}
