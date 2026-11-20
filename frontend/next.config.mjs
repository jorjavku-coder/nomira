/** El navegador solo habla con Next; /api se reenvía al backend (mismo origen, sin CORS). */
const destino = process.env.API_INTERNAL_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Subidas grandes (videos y SCORM de Academia) pasan por este proxy hacia el backend.
  experimental: { proxyTimeout: 15 * 60 * 1000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${destino}/api/:path*` }];
  },
  async headers() {
    return [{
      // El reproductor SCORM se muestra en un iframe AISLADO (sandbox): esa ruta no lleva DENY.
      source: "/:path((?!api/academia-medios/).*)",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "no-referrer" },
      ],
    }];
  },
};
export default nextConfig;
