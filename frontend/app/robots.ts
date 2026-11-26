import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: ["/", "/calculadora-finiquito", "/legal/"], disallow: ["/app", "/inicio", "/rh", "/mi-rh", "/plataforma", "/api/", "/propuesta", "/portal", "/subir", "/seguimiento", "/mi-asunto", "/connect", "/club"] }],
    sitemap: "https://nomirasoft.com/sitemap.xml",
  };
}
