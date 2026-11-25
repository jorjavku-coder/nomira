// Nomira Escrituración: semáforo, alta de expediente con partes, compartir el avance, el cliente abre su enlace y sube
// un documento, la notaría lo valida y marca una etapa (demo, datos ficticios). Uso: node e2e/escrituracion.mjs [url] [carpeta]
import { createRequire } from "node:module";
import { mkdirSync, readFileSync } from "node:fs";
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
const vigilar = (p) => { p.on("console", (m) => m.type() === "error" && !/favicon/.test(m.text()) && errores.push(m.text())); p.on("pageerror", (e) => errores.push(String(e))); };
vigilar(page);
await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.waitForURL(/\/(app|inicio)/);

await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Escrituración" }).click();
await page.getByText("Casa en Calle Ficticia 123").waitFor();
ok(await page.getByText("No está listo para firmar").count() >= 1, "expediente de ejemplo en rojo (faltan documentos)");
await page.screenshot({ path: `${dir}/escrituracion-01-lista.png` });

// nuevo expediente con una parte del directorio de Clientes y otra capturada
await page.getByRole("button", { name: "+ Nuevo expediente" }).click();
await page.getByLabel("Nombre del expediente").fill("Departamento 4B Torre Demo");
await page.getByLabel("Ubicación del inmueble").fill("Av. Ficticia 400 depto 4B, Toluca");
await page.getByLabel(/Comprador\(a\): elegir de Clientes: buscar/).fill("Juan");
await page.getByRole("option", { name: /Juan Demo Ficticio/ }).click();
await page.getByLabel("Nombre de la parte").fill("Rosa Vendedora Ficticia");
await page.getByLabel("Correo de la parte").fill("rosa@vendedora.test");
await page.getByRole("button", { name: "Crear expediente" }).click();
await page.waitForURL(/\/escrituracion\/\d+/);
await page.getByRole("heading", { name: "Departamento 4B Torre Demo" }).waitFor();
ok(await page.getByText("Certificado de libertad de gravamen").count() >= 1, "crea la lista de documentos del acto");
ok(await page.getByText("Firma de la escritura").count() >= 1, "crea las etapas del acto");

// compartir el avance con la vendedora
await page.getByRole("button", { name: "+ Compartir avance" }).click();
await page.getByLabel("¿Quién?").selectOption({ label: "Vendedor(a): Rosa Vendedora Ficticia" });
await page.getByRole("button", { name: "Crear enlace" }).click();
const mensaje = await page.getByLabel("Mensaje con el enlace").inputValue();
const enlace = mensaje.match(/https?:\/\/\S+/)[0].replace(/^https?:\/\/[^/]+/, base);
ok(enlace.includes("/seguimiento#"), "enlace de seguimiento listo para copiar o enviar por WhatsApp");
await page.getByRole("button", { name: "Listo" }).click();

// el cliente abre su enlace (sin cuenta) y sube un documento
const cli = await (await browser.newContext({ viewport: { width: 400, height: 860 } })).newPage();
vigilar(cli);
await cli.goto(enlace);
await cli.getByText("Hola, Rosa Vendedora Ficticia").waitFor();
ok(await cli.getByText("Escritura de propiedad (antecedente) inscrita").count() === 1, "la vendedora ve los documentos del inmueble");
ok(await cli.getByText("Juan Demo Ficticio").count() === 0, "no ve los documentos del comprador");
await cli.getByLabel("Subir Avalúo").setInputFiles({ name: "avaluo.pdf", mimeType: "application/pdf", buffer: readFileSync(new URL("./fixtures/csf-ejemplo.pdf", import.meta.url)) });
await cli.getByText("Recibimos su documento").waitFor();
ok(true, "el cliente sube su documento desde el celular");
await cli.screenshot({ path: `${dir}/escrituracion-02-cliente.png`, fullPage: true });

// la notaría lo valida y marca una etapa
await page.reload();
await page.getByText("lo subió el cliente").waitFor();
const fila = page.getByRole("listitem").filter({ hasText: /^Avalúo/ });
await fila.getByRole("button", { name: "Validar" }).click();
await page.getByLabel("Fecha de expedición").fill(new Date().toLocaleDateString("en-CA"));  // fecha local, no UTC
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.getByText("Documento actualizado.").waitFor();
await page.getByRole("listitem").filter({ hasText: "Documentos recibidos" }).getByRole("button", { name: "✓ Hecho" }).click();
await page.getByText(/marcado como hecho/).waitFor();
await page.screenshot({ path: `${dir}/escrituracion-03-expediente.png`, fullPage: true });
await cli.reload();
await cli.getByText("Listo ✓").first().waitFor();
ok(await cli.getByText("10%").count() >= 1, "el cliente ve su documento validado y el avance actualizado");
ok(errores.length === 0, "sin errores en consola: " + errores.join(" | "));
await browser.close();
