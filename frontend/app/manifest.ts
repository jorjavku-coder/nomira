import type { MetadataRoute } from "next";

/** Nomira como app instalable (Android, iPhone, computadora): ícono, pantalla completa y accesos directos. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/inicio",
    name: "Nomira — software para despachos jurídicos",
    short_name: "Nomira",
    description: "Agenda, clientes, cálculos laborales, tesis y portal para sus clientes, desde su celular.",
    lang: "es-MX",
    start_url: "/inicio?origen=app",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0F263C",
    theme_color: "#0F263C",
    categories: ["business", "productivity"],
    icons: [
      { src: "/app/icono-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/app/icono-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/app/icono-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Agenda", short_name: "Agenda", url: "/agenda", icons: [{ src: "/app/icono-192.png", sizes: "192x192" }] },
      { name: "Clientes y cobranza", short_name: "Clientes", url: "/clientes", icons: [{ src: "/app/icono-192.png", sizes: "192x192" }] },
      { name: "Connect: mis clientes", short_name: "Connect", url: "/connect", icons: [{ src: "/app/icono-192.png", sizes: "192x192" }] },
      { name: "Calculadora de finiquito", short_name: "Finiquito", url: "/calculadora-finiquito", icons: [{ src: "/app/icono-192.png", sizes: "192x192" }] },
    ],
  };
}
