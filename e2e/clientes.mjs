// Clientes y cobranza: directorio, alta desde constancia fiscal, ficha, honorario, pago con recibo, selector en Agenda
// y unir clientes capturados en los módulos (demo, datos ficticios). Uso: node e2e/clientes.mjs [url] [carpeta_capturas]
import { createRequire } from "node:module";
import { mkdirSync, readFileSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => localStorage.setItem("nomira:bienvenida", "1"));
const page = await ctx.newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon|409|Conflict/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));
await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.waitForURL(/\/app/);

await page.getByRole("link", { name: "Clientes y cobranza" }).click();
await page.getByRole("heading", { name: "Clientes y cobranza" }).waitFor();
await page.getByText("Comercializadora Demo SA de CV").waitFor();
ok(await page.getByText("Por cobrar").count() === 1, "directorio con totales de cobranza");
await page.screenshot({ path: `${dir}/clientes-01-lista.png` });

// alta desde la constancia fiscal (PDF sintético generado con texto)
const pdf = readFileSync(new URL("./fixtures/csf-ejemplo.pdf", import.meta.url));
await page.getByRole("button", { name: "+ Nuevo cliente" }).click();
await page.getByLabel("Subir constancia de situación fiscal").setInputFiles({ name: "csf.pdf", mimeType: "application/pdf", buffer: pdf });
await page.getByText(/Leímos de la constancia/).waitFor();
ok(await page.getByLabel("Nombre completo").inputValue() === "MARTA EJEMPLO LOPEZ", "la constancia llena el nombre");
ok(await page.getByLabel("RFC").inputValue() === "EELM850505AB1", "y el RFC");
await page.screenshot({ path: `${dir}/clientes-02-constancia.png` });
await page.getByRole("button", { name: "Guardar cliente" }).click();
await page.waitForURL(/\/clientes\/\d+$/);
await page.getByRole("heading", { name: "MARTA EJEMPLO LOPEZ" }).waitFor();
await page.getByText("Constancia de situación fiscal").first().waitFor();
ok(true, "ficha creada y la constancia quedó en Documentos");

// honorario y pago
await page.getByRole("button", { name: "+ Honorario" }).click();
await page.getByLabel("Concepto").fill("Honorarios por amparo");
await page.getByLabel("Monto").fill("10000");
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.getByText("Honorarios por amparo").waitFor();
await page.getByRole("button", { name: "Registrar pago" }).click();
await page.getByLabel("Monto recibido").fill("2500");
await page.getByRole("button", { name: "Registrar y ver recibo" }).click();
await page.waitForURL(/\/clientes\/recibo\/\d+/);
await page.getByText("DOS MIL QUINIENTOS PESOS 00/100 M.N.").waitFor();
ok(true, "recibo con importe con letra");
await page.screenshot({ path: `${dir}/clientes-03-recibo.png`, fullPage: true });
await page.getByRole("button", { name: "← Volver" }).click();
await page.getByText("Pago parcial").waitFor();
ok(true, "el cargo queda como pago parcial");

// abrir asunto en Agenda desde la ficha: llega con el cliente elegido
await page.getByRole("link", { name: "+ Asunto en Agenda" }).click();
await page.getByRole("dialog").waitFor();
ok((await page.getByLabel("Nombre del asunto").inputValue()).startsWith("MARTA EJEMPLO LOPEZ vs."), "Agenda abre el alta con el cliente");
await page.getByLabel("Nombre del asunto").fill("MARTA EJEMPLO LOPEZ vs. Autoridad Demo");
await page.getByLabel("Materia").selectOption({ index: 1 });
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.waitForURL(/\/agenda\/asuntos\/\d+/);
await page.getByRole("link", { name: /MARTA EJEMPLO LOPEZ/ }).first().click();
await page.waitForURL(/\/clientes\/\d+$/);
await page.getByText("Asunto en Agenda", { exact: true }).first().waitFor();
ok(true, "el asunto aparece en la ficha del cliente");
await page.screenshot({ path: `${dir}/clientes-04-ficha.png`, fullPage: true });

// selector en Evidencia: buscar un cliente existente
await page.goto(base + "/evidencia");
await page.getByRole("button", { name: /Nuevo asunto/ }).click();
await page.getByLabel(/Cliente \(de su directorio\): buscar/).fill("Laura");
await page.getByRole("option", { name: /Laura Ficticia Ramírez/ }).click();
ok(await page.getByText("Laura Ficticia Ramírez").count() >= 1, "Evidencia elige al cliente del directorio");
ok(errores.length === 0, "sin errores en consola: " + errores.join(" | "));
await browser.close();
