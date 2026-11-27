import type { MetadataRoute } from "next";

const BASE = "https://nomirasoft.com";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${BASE}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${BASE}/calculadora-finiquito`, changeFrequency: "monthly", priority: 0.9 },
    { url: `${BASE}/precios`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE}/empleos`, changeFrequency: "daily", priority: 0.8 },
  ];
}
