import { LogoCargando } from "@/components/CargaNomira";

/** Mientras se abre una página: el logotipo de Nomira animado. */
export default function Cargando() {
  return (
    <div className="fixed inset-0 z-[95] flex flex-col pointer-events-none items-center justify-center gap-3" role="status" aria-live="polite">
      <LogoCargando tam={104} />
      <p className="font-marca text-sm font-semibold text-marino">Cargando…</p>
    </div>
  );
}
