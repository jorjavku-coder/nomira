import Link from "next/link";

export const metadata = { title: "Pago · Nomira" };

export default async function Pago({ searchParams }: { searchParams: Promise<{ resultado?: string }> }) {
  const { resultado } = await searchParams;
  const ok = resultado === "ok";
  return (
    <main className="flex min-h-screen items-center justify-center bg-crema p-6">
      <div className="tarjeta max-w-md p-8 text-center">
        <h1 className="text-2xl font-extrabold text-marino">{ok ? "¡Gracias! Recibimos tu pago" : "El pago no se completó"}</h1>
        <p className="mt-3 text-slate-600">{ok
          ? "Tu despacho verá el pago registrado en unos minutos. El comprobante de Stripe llega a tu correo si lo diste al pagar."
          : "No se hizo ningún cargo. Puedes volver a abrir la liga que te mandó tu despacho para intentarlo de nuevo."}</p>
        <p className="mt-6 text-xs text-slate-400">Pago procesado por Stripe. <Link href="/" className="underline">Nomira</Link></p>
      </div>
    </main>
  );
}
