// Ayuda y manuales por módulo, aviso de bienvenida y botón «¿Cómo se usa?» (demo, datos ficticios).
// Uso: node e2e/ayuda.mjs [http://localhost:3000] [carpeta_capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));
await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByText("¿Primera vez en Nomira?").waitFor();
ok(true, "aviso de bienvenida la primera vez");
for (const g of ["Nómina", "Módulos", "Mi despacho"]) ok(await page.getByRole("navigation", { name: "Principal" }).getByText(g, { exact: true }).count() === 1, `menú agrupado: ${g}`);
await page.getByRole("link", { name: "Ver la guía" }).click();
await page.getByRole("heading", { name: "Primeros pasos", level: 1 }).waitFor();
await page.screenshot({ path: `${dir}/ayuda-01-primeros-pasos.png`, fullPage: true });
await page.goto(base + "/app");
ok(await page.getByText("¿Primera vez en Nomira?").count() === 0, "la bienvenida ya no vuelve a salir");

await page.goto(base + "/ayuda");
const tarjetas = await page.locator("a[href^='/ayuda/']").count();
ok(tarjetas >= 7, `centro de ayuda con ${tarjetas} manuales`);
await page.getByLabel("Buscar en los manuales").fill("validar");
await page.locator("a[href*='#paso-']").first().waitFor();
ok(true, "la búsqueda encuentra pasos de los manuales");
await page.screenshot({ path: `${dir}/ayuda-02-centro.png` });

for (const m of ["primeros-pasos", "nomina", "evidencia", "afore", "leads", "academia", "agenda"]) {
  await page.goto(base + `/ayuda/${m}`);
  await page.locator("h1").waitFor();
  await page.waitForTimeout(400);
  const imgs = page.locator("article img");
  const n = await imgs.count();
  for (let i = 0; i < n; i++) await imgs.nth(i).scrollIntoViewIfNeeded();
  const rotas = await imgs.evaluateAll((xs) => xs.filter((x) => !x.complete || x.naturalWidth === 0).length);
  ok(n >= 2 && rotas === 0, `manual «${m}»: ${n} capturas, todas cargan`);
}
await page.goto(base + "/agenda");
await page.getByRole("link", { name: "¿Cómo se usa?" }).click();
await page.getByRole("heading", { name: "Agenda Jurídica", level: 1 }).waitFor();
ok(true, "el botón «¿Cómo se usa?» del módulo abre su manual");
await page.screenshot({ path: `${dir}/ayuda-03-agenda.png` });
ok(errores.length === 0, "sin errores en la consola: " + errores.join(" | "));
await browser.close();
