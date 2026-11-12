// Prueba de humo de la lectura automática en «Nuevo expediente» (datos sintéticos).
// Uso: node e2e/prelectura.mjs [http://localhost:3000] [carpeta_capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
const errores = [];
page.on("console", (m) => m.type() === "error" && errores.push(m.text()));
await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").fill("admin@demo.local");
await page.getByLabel(/Contraseña/).fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByRole("button", { name: "+ Nuevo expediente" }).click();
await page.locator('input[type="file"]').setInputFiles(new URL("../datos/ejemplos/recibos_sinteticos.pdf", import.meta.url).pathname);
await page.getByText("Detectamos").waitFor();
ok(await page.getByLabel("Nombre del trabajador").inputValue() === "DEMO FICTICIO JORGE ALBERTO", "nombre llenado desde el recibo");
ok(await page.getByLabel(/Identificador laboral/).inputValue() === "900000555", "clave de servidor llenada");
ok(await page.getByLabel("Periodo: inicio").inputValue() === "2025-12-01", "inicio de periodo detectado");
ok(await page.getByLabel("Periodo: fin").inputValue() === "2026-03-15", "fin de periodo detectado");
await page.screenshot({ path: `${dir}/12-nuevo-expediente-autollenado.png` });
await page.getByRole("button", { name: /Crear y procesar 1 PDF/ }).click();
await page.waitForURL("**/expedientes/*");
await page.getByText("Quincenas (7)").waitFor();
await page.getByRole("button", { name: /^1\. 1\.ª qna\. diciembre/ }).click();
ok(await page.getByText("$10,408.60").count() >= 1, "expediente creado y procesado: 1-15 dic = $10,408.60");
ok(await page.getByText("Pendientes que impiden validar").count() === 0, "sin pendientes");
ok(await page.getByText("7 / 7").count() + await page.getByText(/^7$/).count() >= 1, "7 quincenas con comprobante");
await page.evaluate(() => window.scrollTo(0, 0));
await page.screenshot({ path: `${dir}/13-expediente-desde-pdf.png`, fullPage: true });
ok(errores.length === 0, "sin errores de consola: " + errores.join(" | "));
await browser.close();
