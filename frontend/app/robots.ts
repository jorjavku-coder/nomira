import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: ["/", "/calculadora-finiquito", "/legal/"], disallow: ["/app", "/inicio", "/plataforma", "/api/", "/propuesta", "/portal", "/subir", "/seguimiento"] }],
    sitemap: "https://nomirasoft.com/sitemap.xml",
  };
}
