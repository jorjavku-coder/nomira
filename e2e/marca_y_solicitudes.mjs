// Prueba de humo: formulario público, logotipo del cliente y bandeja de solicitudes en el panel de
// la plataforma (datos ficticios).
// Uso: node e2e/marca_y_solicitudes.mjs [http://localhost:3000] [carpeta_capturas]
// Requiere en el backend PLATAFORMA_ADMIN_EMAIL y PLATAFORMA_ADMIN_CONTRASENA; la prueba usa los
// mismos valores desde E2E_PLATAFORMA_EMAIL / E2E_PLATAFORMA_CONTRASENA.
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
await page.goto(base + "/#informes");  // el formulario de informes vive en el sitio público
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

await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
ok(await page.getByRole("link", { name: "Solicitudes" }).count() === 0, "un cliente no ve la bandeja de solicitudes");

await page.getByRole("link", { name: "Datos y módulos" }).click();
await page.locator('input[type="file"]').setInputFiles(new URL("../datos/ejemplos/logo_cliente_ficticio.png", import.meta.url).pathname);
await page.getByText("Logotipo actualizado.").waitFor();
await page.getByAltText(/^Logotipo de /).waitFor();
ok(true, "logotipo del cliente visible en la barra lateral");
ok(await page.getByText("Desarrollado por IMA").count() === 1, "pie de página con el crédito dentro del sistema");
await page.screenshot({ path: `${dir}/16-mi-empresa-logo.png` });
await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Revisión de nómina" }).click();
await page.getByRole("link", { name: "#1" }).waitFor();
await page.screenshot({ path: `${dir}/17-expedientes-con-marca.png` });

await page.goto(base + "/plataforma/login");
await page.getByLabel("Correo").fill(process.env.E2E_PLATAFORMA_EMAIL || "");
await page.getByLabel("Contraseña").fill(process.env.E2E_PLATAFORMA_CONTRASENA || "");
await page.getByRole("button", { name: "Entrar al panel" }).click();
await page.getByRole("navigation").getByRole("link", { name: /^Solicitudes/ }).first().click();
await page.getByText("Laura Prospecto Ficticia").waitFor();
await page.getByText("Quiere suscribirse").first().waitFor();
ok(true, "la solicitud aparece en el panel de la plataforma");
await page.screenshot({ path: `${dir}/15-solicitudes.png` });
ok(errores.length === 0, "sin errores de consola: " + errores.join(" | "));
await browser.close();
