/** El navegador solo habla con Next; /api se reenvía al backend (mismo origen, sin CORS). */
const destino = process.env.API_INTERNAL_URL || "http://localhost:8000";
const desarrollo = process.env.NODE_ENV !== "production";

/**
 * Política de contenido (CSP). Limita de dónde puede cargar cosas la página, para que un error de
 * programación no se convierta en robo de sesión:
 * - connect-src 'self': el navegador solo puede mandar datos a Nomira (ni siquiera un script inyectado
 *   podría enviar la sesión a otro sitio).
 * - frame-src: solo nuestro reproductor SCORM (aislado), vistas previas locales y videos de YouTube/Vimeo.
 * - frame-ancestors 'none': nadie puede meter Nomira dentro de su página (clickjacking).
 * Next necesita 'unsafe-inline' para sus scripts de arranque; en desarrollo además 'unsafe-eval'.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${desarrollo ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${desarrollo ? " ws:" : ""}`,
  "media-src 'self' blob:",
  "frame-src 'self' blob: https://www.youtube-nocookie.com https://player.vimeo.com",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(desarrollo ? [] : ["upgrade-insecure-requests"]),
].join("; ");

const comunes = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  // Solo HTTPS durante un año (el navegador ya no intenta HTTP). Sin «preload»: se puede revertir.
  ...(desarrollo ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]),
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Subidas grandes (videos y SCORM de Academia) pasan por este proxy hacia el backend.
  experimental: { proxyTimeout: 15 * 60 * 1000 },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${destino}/api/:path*` },
      { source: "/mcp", destination: `${destino}/api/mcp` },  // conector de Nomira para Claude (nomirasoft.com/mcp)
    ];
  },
  async headers() {
    return [
      // Reproductor SCORM: lo sirve el backend con su propia CSP «sandbox» y se muestra en un iframe aislado.
      { source: "/api/academia-medios/:path*", headers: comunes },
      {
        source: "/:path((?!api/academia-medios/).*)",
        headers: [
          ...comunes,
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: csp },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()" },
        ],
      },
    ];
  },
};
export default nextConfig;
