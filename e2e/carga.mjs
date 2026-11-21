// Indicador de carga con el logotipo de Nomira y aviso de éxito; eliminar catálogos (demo, datos ficticios).
// Uso: node e2e/carga.mjs [http://localhost:3000] [carpeta_capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
const pdf = fileURLToPath(new URL("../datos/catalogo/Prestaciones.pdf", import.meta.url));
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 860 } })).newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon|409/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));

await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByText("Sesión iniciada. ¡Bienvenido!").waitFor();
ok(true, "al iniciar sesión avisa que entró");

await page.goto(base + "/catalogos");
await page.getByRole("heading", { name: "Catálogos de prestaciones" }).waitFor();
await page.getByLabel("Nuevo catálogo").fill("Catálogo de prueba para borrar");
await page.getByRole("button", { name: "Crear catálogo" }).click();
const sec = page.locator("section", { hasText: "Catálogo de prueba para borrar" });
await sec.waitFor();
await sec.locator('input[type="file"]').setInputFiles(pdf);
await page.getByText("Subiendo «Prestaciones.pdf»…").waitFor({ timeout: 5000 });
ok(await page.locator("svg.nm-carga").count() >= 1, "mientras sube, aparece el logotipo de Nomira animado");
await page.screenshot({ path: `${dir}/carga-01-subiendo.png` });
await page.getByText("«Prestaciones.pdf» se cargó con éxito.").waitFor({ timeout: 120000 });
ok(true, "al terminar avisa que el archivo se cargó con éxito");
await page.screenshot({ path: `${dir}/carga-02-exito.png` });

await page.goto(base + "/catalogos");
const sec2 = page.locator("section", { hasText: "Catálogo de prueba para borrar" });
await sec2.locator("button.btn-peligro").click();
await page.getByRole("dialog").getByRole("button", { name: "Eliminar" }).click();
await page.getByText("Se eliminó el catálogo «Catálogo de prueba para borrar».").waitFor();
await page.getByRole("heading", { name: "Catálogo de prueba para borrar" }).waitFor({ state: "detached" });
ok(true, "se elimina un catálogo que ningún expediente usa");
const usado = page.locator("section button.btn-peligro[disabled]");
ok(await usado.count() >= 1, "un catálogo que usan expedientes no se puede eliminar");
await page.screenshot({ path: `${dir}/carga-03-catalogos.png`, fullPage: true });
ok(errores.length === 0, "sin errores en la consola: " + errores.join(" | "));
await browser.close();
