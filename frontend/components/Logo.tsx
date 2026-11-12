/** Marca Nomira. Isotipo redibujado en vectorial a partir del logo proporcionado. */
export function Isotipo({ className = "h-8 w-8", oscuro = false }: { className?: string; oscuro?: boolean }) {
  const tinta = oscuro ? "#FFFFFF" : "#123048";
  const acento = oscuro ? "#01E9CD" : "#01B2A6";
  return (
    <svg viewBox="15 15 290 315" className={className} aria-hidden="true" focusable="false">
      <path fill={tinta} d="M25 88V60q0-35 35-35h140q93 0 93 93v34l-75 68v-82q0-53-53-53H48q-14 0-23 3z" />
      <rect fill={tinta} x="28" y="117" width="162" height="38" rx="19" />
      <rect fill={tinta} x="28" y="184" width="162" height="38" rx="19" />
      <rect fill={tinta} x="28" y="253" width="100" height="38" rx="19" />
      <path fill={acento} d="M293 187v101q0 32-32 32h-65q-10 0-18-8l-30-30q-10-12 2-22t23 0l22 22z" />
    </svg>
  );
}

export default function Logo({ oscuro = false, lema = false, grande = false }: { oscuro?: boolean; lema?: boolean; grande?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <Isotipo oscuro={oscuro} className={grande ? "h-12 w-12" : "h-8 w-8"} />
      <span className="flex flex-col leading-none">
        <span className={`font-marca font-extrabold tracking-tight ${grande ? "text-4xl" : "text-2xl"} ${oscuro ? "text-white" : "text-marino"}`}>nomira</span>
        {lema && <span className={`mt-1 font-marca ${grande ? "text-sm" : "text-[11px]"} ${oscuro ? "text-white/80" : "text-marino/80"}`}>Cada prestación, en claro</span>}
      </span>
    </span>
  );
}
