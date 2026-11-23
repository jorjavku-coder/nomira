// Estrados digitales (TRIJAEM) en Nomira Agenda: vigilar un expediente, cotejar la lista del día, aviso en Hoy,
// pasar al historial y calcular plazo (demo, datos ficticios). Uso: node e2e/estrados.mjs [url] [carpeta_capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => localStorage.setItem("nomira:bienvenida", "1"));
const page = await ctx.newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));
await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.waitForURL(/\/app/);

await page.goto(base + "/agenda/estrados");
await page.getByText("Revisión automática activa").waitFor();
ok(true, "indica que la revisión automática está activa");
ok(await page.getByText("Exp. JA-1234/2026").count() === 1, "expediente de ejemplo vigilado");

// vigilar otro asunto desde su ficha
await page.goto(base + "/agenda/asuntos");
await page.getByRole("link", { name: /Ruiz Ficticio/ }).first().click();
await page.getByRole("button", { name: "Vigilar en estrados" }).click();
await page.getByLabel(/Sala o sección/).selectOption({ label: "Tercera Sala Regional Tlalnepantla de Baz" });
await page.getByLabel(/Números de promoción/).fill("811204");
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.getByText("Vigilando").waitFor();
ok(true, "se activa la vigilancia desde el asunto");
await page.screenshot({ path: `${dir}/estrados-01-asunto.png`, fullPage: true });

// cotejar la lista del día
await page.goto(base + "/agenda/estrados");
await page.getByRole("button", { name: "Cotejar lista del día" }).click();
await page.getByLabel(/Pegue aquí/).fill("PRIMERA SALA REGIONAL\n3. JA-1234/2026 ACTOR: NULIDAD DEMO\n   Se admite la demanda y se requiere a la autoridad su contestación.\n4. 55/2026 Otro juicio");
await page.screenshot({ path: `${dir}/estrados-02-cotejo.png` });
await page.getByRole("button", { name: "Buscar mis expedientes" }).click();
await page.getByText(/Se encontraron 1 publicación/).waitFor();
ok(await page.getByText("Se admite la demanda y se requiere").count() === 1, "el cotejo encuentra el expediente vigilado");
ok(await page.getByText("Nueva", { exact: true }).count() === 1, "marcada como nueva");
await page.screenshot({ path: `${dir}/estrados-03-publicaciones.png`, fullPage: true });

await page.goto(base + "/agenda");
await page.getByText(/publicación\(es\) nueva\(s\) en estrados/).waitFor();
ok(true, "aviso en la vista Hoy");
await page.getByText(/publicación\(es\) nueva\(s\) en estrados/).click();
await page.getByRole("button", { name: "Pasar al historial y calcular plazo" }).click();
await page.waitForURL(/\/agenda\/asuntos\/\d+/);
await page.getByText(/Publicado en estrados/).waitFor();
ok(true, "pasa al historial del asunto como notificación");
await page.getByRole("button", { name: "Calcular plazo" }).first().click();
await page.getByRole("dialog").waitFor();
ok(true, "propone calcular el plazo desde la publicación");
await page.screenshot({ path: `${dir}/estrados-04-plazo.png`, fullPage: true });
ok(errores.length === 0, "sin errores en consola: " + errores.join(" | "));
await browser.close();
