// Prueba de humo: formulario público, bandeja de solicitudes y logotipo del cliente (datos ficticios).
// Uso: node e2e/marca_y_solicitudes.mjs [http://localhost:3000] [carpeta_capturas]
// Requiere CORREOS_PLATAFORMA=admin@demo.local en el backend.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 2 });
const errores = [];
page.on("console", (m) => m.type() === "error" && errores.push(m.text()));

await page.goto(base + "/login");
ok(await page.getByText("Desarrollado por IMA").count() === 1, "pie de página con el crédito en la página de inicio");
await page.getByRole("link", { name: "Solicitar informes o suscripción" }).click();
await page.getByText("Quiero suscribirme").click();
await page.getByLabel("Nombre completo").fill("Laura Prospecto Ficticia");
await page.getByLabel("Empresa o despacho").fill("Despacho de Prueba");
await page.getByLabel("Correo electrónico").last().fill("laura@prueba.test");
await page.getByLabel(/Expedientes que analiza/).selectOption("11-50");
await page.getByLabel(/Mensaje/).fill("Quiero contratar para mi despacho.");
await page.locator("#informes").screenshot({ path: `${dir}/14-formulario-informes.png` });
await page.getByLabel(/Acepto que se usen/).check();
await page.getByRole("button", { name: "Solicitar suscripción" }).click();
await page.getByText("Recibimos su solicitud").waitFor();
ok(true, "solicitud enviada sin iniciar sesión");

await page.evaluate(() => window.scrollTo(0, 0));
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByRole("link", { name: "Solicitudes" }).click();
await page.getByText("Laura Prospecto Ficticia").waitFor();
ok(await page.getByText("Suscripción").count() >= 1, "la solicitud aparece en la bandeja");
await page.screenshot({ path: `${dir}/15-solicitudes.png` });

await page.getByRole("link", { name: "Mi empresa" }).click();
await page.locator('input[type="file"]').setInputFiles(new URL("../datos/ejemplos/logo_cliente_ficticio.png", import.meta.url).pathname);
await page.getByText("Logotipo actualizado.").waitFor();
await page.getByAltText(/^Logotipo de /).waitFor();
ok(true, "logotipo del cliente visible en la barra lateral");
ok(await page.getByText("Desarrollado por IMA").count() === 1, "pie de página con el crédito dentro del sistema");
await page.screenshot({ path: `${dir}/16-mi-empresa-logo.png` });
await page.getByRole("link", { name: "Expedientes" }).click();
await page.getByRole("link", { name: "#1" }).waitFor();
await page.screenshot({ path: `${dir}/17-expedientes-con-marca.png` });
ok(errores.length === 0, "sin errores de consola: " + errores.join(" | "));
await browser.close();
