// Sitio público: módulos, «Cómo empezar», «Por qué Nomira», calculadora gratuita de finiquito (sin sesión) y SEO básico.
// Uso: node e2e/sitio.mjs [base] [capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const b = await chromium.launch();
const errores = [];
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
p.on("pageerror", (e) => errores.push(String(e)));
p.on("console", (m) => m.type() === "error" && !/favicon/.test(m.text()) && errores.push(m.text()));
await p.goto(base + "/");
await p.getByRole("heading", { name: "Un módulo para cada parte de su trabajo" }).waitFor();
for (const t of ["Nómina y liquidaciones", "Agenda Jurídica", "Escrituración para notarías", "Recursos humanos", "Pruebas psicométricas"])
  ok(await p.getByRole("heading", { name: t }).count() === 1, `módulo en el sitio: ${t}`);
ok(await p.getByRole("heading", { name: "Más que un control de expedientes" }).count() === 1, "sección «Por qué Nomira»");
ok(await p.getByRole("heading", { name: "En tres pasos, sin compromiso" }).count() === 1, "sección «Cómo empezar»");
ok(await p.getByText("Incluido en todos los planes").count() === 1, "lo incluido en todos los planes");
ok(await p.locator("#preguntas details").count() <= 10, "preguntas frecuentes cortas");
ok((await p.title()).includes("notarías"), "título para buscadores actualizado");
// que se vean las secciones animadas al desplazarse
for (let y = 0; y < 14000; y += 700) { await p.mouse.wheel(0, 700); await p.waitForTimeout(80); }
await p.waitForTimeout(500);
await p.screenshot({ path: `${dir}/sitio-completo.png`, fullPage: true });
await p.getByRole("link", { name: "Abrir la calculadora →" }).click();
await p.waitForURL(/calculadora-finiquito/);
await p.getByLabel("Fecha de ingreso").fill("2016-06-01");
await p.getByLabel("Fecha de baja o despido").fill("2026-05-31");
await p.getByLabel("Salario diario").fill("1000");
await p.getByLabel("Zona").selectOption("frontera");
await p.getByLabel("20 días por año").selectOption("si");
await p.getByLabel("Calcular salarios caídos al").fill("2026-11-30");
await p.waitForFunction(() => document.querySelector("[data-prueba=total]")?.textContent === "$639,077.96");
ok(true, "calculadora pública sin sesión: mismo resultado que el módulo ($639,077.96)");
await p.screenshot({ path: `${dir}/calculadora.png`, fullPage: true });
const m = await b.newContext({ viewport: { width: 390, height: 844 } });
const pm = await m.newPage();
await pm.goto(base + "/calculadora-finiquito");
await pm.getByLabel("Fecha de ingreso").fill("2023-01-16");
await pm.getByLabel("Fecha de baja o despido").fill("2026-07-15");
await pm.getByLabel("Salario diario").fill("400");
await pm.getByLabel("¿Cómo terminó la relación?").selectOption("renuncia");
await pm.waitForFunction(() => document.querySelector("[data-prueba=total]")?.textContent === "$7,684.93");
ok(true, "en el celular también funciona (renuncia: $7,684.93)");
await pm.screenshot({ path: `${dir}/calculadora-movil.png`, fullPage: true });
const r = await p.request.get(base + "/sitemap.xml");
ok(r.ok() && (await r.text()).includes("calculadora-finiquito"), "sitemap.xml con la calculadora");
const rb = await p.request.get(base + "/robots.txt");
ok(rb.ok() && (await rb.text()).includes("Disallow: /plataforma"), "robots.txt no indexa los paneles");
ok(errores.length === 0, "sin errores en consola " + errores.join(" | "));
await b.close();
