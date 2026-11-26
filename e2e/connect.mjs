// Nomira Connect: el despacho mueve una etapa con nota pública e interna, responde un mensaje y crea el enlace;
// el cliente entra desde el celular con código, ve su seguimiento (sin la nota interna) y escribe. Datos ficticios.
// Uso: node e2e/connect.mjs [url] [carpeta] [carpeta_de_correos_de_prueba]
import { createRequire } from "node:module";
import { mkdirSync, readdirSync, readFileSync, statSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
const correos = process.argv[4] || "/tmp/alm_ev/correos_prueba";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const INTERNA = "Revisar contradicciones del testigo (INTERNO-E2E)";
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => localStorage.setItem("nomira:bienvenida", "1"));
const page = await ctx.newPage();
const errores = [];
const vigilar = (p) => { p.on("console", (m) => m.type() === "error" && !/favicon|401/.test(m.text()) && errores.push(m.text())); p.on("pageerror", (e) => errores.push(String(e))); };
vigilar(page);
await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.waitForURL(/\/(app|inicio)/);

await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: /Connect/ }).click();
await page.getByRole("heading", { name: "Nomira Connect" }).waitFor();
await page.getByText("Ruiz Ficticio vs. Comercializadora Demo").waitFor();
ok(await page.getByText("Publicado", { exact: true }).count() >= 1, "el asunto de la demo aparece publicado");
ok(await page.getByRole("button", { name: /Mensajes \(1\)/ }).count() === 1, "un mensaje nuevo del cliente");
await page.screenshot({ path: `${dir}/connect-01-panel.png` });

// mensajes: leer y responder
await page.getByRole("button", { name: /Mensajes \(1\)/ }).click();
await page.getByRole("button", { name: /Juan Demo Ficticio/ }).click();
await page.getByText(/ya hay fecha para la audiencia/).waitFor();
await page.getByPlaceholder(/Escriba su respuesta/).fill("Sí, Juan. Es el próximo martes; le confirmamos si necesita asistir.");
await page.getByRole("button", { name: "Enviar" }).click();
await page.getByText(/Es el próximo martes/).waitFor();
await page.getByRole("button", { name: "Marcar como atendido" }).waitFor({ state: "detached", timeout: 5000 }).catch(() => {});
ok(await page.getByRole("button", { name: "Marcar como atendido" }).count() === 0, "responder deja el mensaje atendido");
await page.screenshot({ path: `${dir}/connect-02-mensajes.png` });

// seguimiento: mover etapa con nota pública e interna
await page.getByRole("button", { name: "Asuntos" }).click();
await page.getByRole("link", { name: "Abrir" }).first().click();
await page.waitForURL(/\/connect\/\d+/);
await page.getByRole("heading", { name: "Etapas" }).waitFor();
await page.getByRole("button", { name: /Desahogo de pruebas/ }).click();
await page.getByPlaceholder(/Presentamos su demanda/).fill("Ya se celebró la audiencia; ahora se revisan las pruebas.");
await page.getByLabel(/Nota interna/).fill(INTERNA);
await page.getByRole("button", { name: "Es la etapa actual" }).click();
await page.getByText("Seguimiento actualizado.").waitFor();
ok(await page.getByText("Nueva etapa: Desahogo de pruebas").count() >= 1, "el cambio queda en el historial");
await page.getByRole("button", { name: "Crear un enlace nuevo" }).or(page.getByRole("button", { name: "Crear enlace para el cliente" })).click();
const url = (await page.locator("p.break-all").innerText()).trim();
ok(url.includes("/mi-asunto#"), "enlace del portal del cliente");
await page.screenshot({ path: `${dir}/connect-03-seguimiento.png`, fullPage: true });

// el cliente, en su celular
const cel = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
const c = await cel.newPage();
vigilar(c);
const antes = Date.now();
await c.goto(url.replace(/^https?:\/\/[^/]+/, base));
await c.getByRole("heading", { name: /Hola, Juan/ }).waitFor();
await c.screenshot({ path: `${dir}/connect-04-codigo.png` });
await c.getByRole("button", { name: "Enviarme el código" }).click();
await c.getByText(/Le enviamos el código/).waitFor();
const ult = readdirSync(correos).map((f) => `${correos}/${f}`).filter((f) => statSync(f).mtimeMs >= antes - 2000).sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs)[0];
const codigo = readFileSync(ult, "utf8").match(/\b(\d{6})\b/)[1];
await c.getByLabel("Código").fill(codigo);
await c.getByRole("button", { name: "Entrar" }).click();
await c.getByText("Etapa actual").first().waitFor();
ok(await c.getByText("Desahogo de pruebas").count() >= 1, "el cliente ve la etapa actual");
ok(!(await c.content()).includes("INTERNO-E2E"), "la nota interna NUNCA llega al portal");
await c.screenshot({ path: `${dir}/connect-05-portal-inicio.png`, fullPage: true });
await c.getByRole("button", { name: /Ver detalle/ }).click();
await c.getByText("Su asunto está en").waitFor();
ok(await c.getByText("Ya se celebró la audiencia; ahora se revisan las pruebas.").count() >= 1, "ve la nota pública de su abogado");
ok(await c.getByText("Última revisión de su despacho").count() === 1 && await c.getByText("Último movimiento en el expediente").count() === 1, "revisión y movimiento por separado");
await c.screenshot({ path: `${dir}/connect-06-portal-detalle.png`, fullPage: true });
await c.getByRole("button", { name: "Letra más grande" }).click();
await c.getByRole("button", { name: "Alto contraste" }).click();
await c.screenshot({ path: `${dir}/connect-07-accesible.png` });
await c.getByRole("button", { name: "Alto contraste" }).click();
await c.getByRole("button", { name: "Letra más grande" }).click();
await c.getByRole("button", { name: /Preguntar a mi abogado/ }).click();
ok(await c.getByText("Sí, Juan. Es el próximo martes").count() === 1, "ve la respuesta del despacho");
await c.getByRole("button", { name: /Quiero que me llamen/ }).click();
await c.getByPlaceholder("Escriba aquí su mensaje").fill("¿Me pueden llamar el lunes por la mañana?");
await c.getByRole("button", { name: "Enviar mensaje" }).click();
await c.getByText(/Su mensaje llegó al despacho/).waitFor();
await c.screenshot({ path: `${dir}/connect-08-portal-mensajes.png`, fullPage: true });

// avisos: el cliente elige cómo recibirlos
await c.getByRole("button", { name: "Inicio" }).click();
await c.getByText("Avisos de su asunto").waitFor();
await c.getByRole("switch").first().click();
await c.waitForTimeout(600);
ok(await c.getByRole("switch").first().getAttribute("aria-checked") === "false", "el cliente puede apagar los avisos por correo");
await c.getByRole("switch").first().click();

// el despacho lo recibe
await page.goto(base + "/connect?tab=mensajes");
await page.getByText("Pide una llamada").first().waitFor();
ok(true, "el despacho recibe la solicitud de llamada");
await page.getByRole("button", { name: "Avisos automáticos" }).click();
await page.getByText("Historial de avisos").waitFor();
ok(await page.getByText("WhatsApp: pendiente de conexión").count() === 1, "WhatsApp aparece como pendiente de conexión (no se simula)");
ok(await page.getByText("Cambio de etapa").count() >= 1, "el cambio de etapa generó su aviso");
await page.screenshot({ path: `${dir}/connect-09-avisos.png`, fullPage: true });
ok(!errores.length, "sin errores en consola" + (errores.length ? ": " + errores.join(" | ") : ""));
await browser.close();
