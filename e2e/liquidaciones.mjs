// Liquidaciones LFT: cálculo en vivo, ajustes, guardar ligado al asunto, exposición económica en la Agenda,
// hoja para imprimir y CSV (demo, datos ficticios). Uso: node e2e/liquidaciones.mjs [url] [carpeta]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true });
await ctx.addInitScript(() => localStorage.setItem("nomira:bienvenida", "1"));
const page = await ctx.newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));
await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.waitForURL(/\/(app|inicio)/);

await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Liquidaciones LFT" }).click();
await page.getByText("Pedro Ruiz Ficticio").waitFor();
ok(await page.getByText("Laura Ruiz Ficticia").count() === 1, "lista con los cálculos de ejemplo");

await page.getByRole("link", { name: "+ Nuevo cálculo" }).click();
await page.getByLabel("Persona trabajadora *").fill("Ana Torres Ficticia");
await page.getByLabel("Patrón o empresa").fill("Comercializadora Demo");
await page.getByLabel("Asunto de la Agenda").selectOption({ label: "Ruiz Ficticio vs. Comercializadora Demo (1450/2026)" });
await page.getByLabel("Fecha de ingreso *").fill("2016-06-01");
await page.getByLabel("Fecha de baja o despido *").fill("2026-05-31");
await page.getByLabel("Salario diario *").fill("1000");
await page.getByLabel("Zona del salario mínimo").selectOption("frontera");
await page.getByLabel("Calcular salarios caídos al").fill("2026-11-30");
await page.getByLabel("20 días por año").selectOption("si");
const total = page.locator("[data-prueba=total]");
await page.waitForFunction(() => document.querySelector("[data-prueba=total]")?.textContent === "$639,077.96");
ok(true, "total en vivo: $639,077.96 (caso resuelto a mano)");
ok(await page.getByText("Prima de antigüedad").count() >= 1 && await page.getByText(/tope: 2 salarios mínimos/).count() >= 1, "prima de antigüedad con tope de 2 mínimos de la frontera");
ok(await page.getByText("Salarios caídos (máximo 12 meses)").count() === 1, "salarios caídos");

// horas extra en 2026 (jornada de 48 h; 9 dobles y el resto triples)
await page.getByRole("button", { name: "+ Agregar periodo" }).click();
await page.getByLabel("Desde", { exact: true }).fill("2026-03-02");
await page.getByLabel("Hasta", { exact: true }).fill("2026-03-29");
await page.getByLabel("Horas por semana").fill("60");
await page.getByText(/Horas extra del 02\/03\/2026/).waitFor();
ok(await page.getByText(/9 h × 2 \+ 3 h × 3/).count() === 1, "horas extra: 9 dobles y 3 triples con jornada de 48 h");
ok(await page.getByText(/pueden estar prescritas/).count() === 0, "sin aviso de prescripción dentro del último año");
await page.getByLabel("Monto que se propone").fill("400000");
ok(await page.getByText(/% del total/).count() >= 1, "porcentaje de la propuesta");
await page.screenshot({ path: `${dir}/liquidaciones-01-calculo.png`, fullPage: true });
await page.getByRole("button", { name: "Guardar cálculo" }).click();
await page.waitForURL(/\/liquidaciones\/\d+$/);
await page.getByRole("button", { name: "Excel (CSV)" }).waitFor();
ok(true, "cálculo guardado");

const [desc] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Excel (CSV)" }).click()]);
ok(/liquidacion-Ana-Torres-Ficticia\.csv/.test(desc.suggestedFilename()), "descarga CSV");

await page.getByRole("link", { name: "Imprimir o PDF" }).click();
await page.getByText("Cálculo de prestaciones (LFT)").waitFor();
ok(await page.getByText("Propuesta de convenio").count() === 0, "la hoja no muestra la propuesta si no se marca");
await page.getByLabel("Incluir propuesta y notas internas").check();
ok(await page.getByText(/Propuesta de convenio/).count() === 1, "propuesta al marcarla");
await page.screenshot({ path: `${dir}/liquidaciones-02-imprimir.png`, fullPage: true });

// exposición económica en el asunto
await page.goto(base + "/agenda/asuntos");
await page.getByText("Ruiz Ficticio vs. Comercializadora Demo").first().click();
await page.getByRole("heading", { name: "Exposición económica" }).waitFor();
ok(await page.getByText("Ana Torres Ficticia").count() === 1 && await page.getByText("Pedro Ruiz Ficticio").count() === 1, "exposición económica con las tres personas");
await page.screenshot({ path: `${dir}/liquidaciones-03-asunto.png` });
ok(errores.length === 0, "sin errores en consola: " + errores.join(" | "));
await browser.close();
