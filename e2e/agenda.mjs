// Recorrido de Nomira Agenda Jurídica sobre la demo (datos ficticios).
// Uso: node e2e/agenda.mjs [http://localhost:3000] [carpeta_capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 }, acceptDownloads: true });
const page = await ctx.newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon|401|403|404|409|422/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));
const foto = async (n, p = page) => { await p.waitForTimeout(300); await p.screenshot({ path: `${dir}/${n}.png`, fullPage: true }); };
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByRole("link", { name: /^Agenda/ }).first().click();
await page.getByRole("heading", { name: "Agenda de hoy" }).waitFor();
await page.getByText("Desahogar vista (ejemplo)").first().waitFor();
ok(await page.getByLabel(/pendientes vencidos o de hoy/).count() === 1, "el menú muestra cuántos pendientes vencidos o de hoy hay");
ok(await page.getByText("Audiencia preliminar").count() >= 1, "la audiencia de hoy aparece en la vista diaria");
ok(await page.getByText("Cálculo sin validar").count() >= 1, "el plazo calculado aparece como «sin validar»");
await foto("ag-01-hoy");

// Asunto nuevo → actuación con notificación → plazo calculado
await page.getByRole("link", { name: "Asuntos", exact: true }).click();
await page.getByRole("button", { name: "+ Nuevo asunto" }).click();
await page.getByLabel("Nombre del asunto").fill("Gómez Ficticia vs. Servicios Demo");
await page.getByLabel("Número de expediente o juicio").fill("2001/2026");
await page.getByLabel("Materia").selectOption("laboral");
await page.getByLabel("Tribunal o autoridad").fill("Tribunal Laboral Ficticio");
await page.getByRole("button", { name: "Guardar" }).click();
await page.getByRole("heading", { name: "Gómez Ficticia vs. Servicios Demo" }).waitFor();
ok(true, "asunto creado con su calendario por omisión");
const hoy = new Date(), notif = new Date(hoy); notif.setDate(hoy.getDate() - 1);
await page.getByLabel("Fecha", { exact: true }).fill(iso(notif));
await page.getByLabel("Qué se acordó o sucedió").fill("Se requiere al actor para que aclare su demanda");
await page.getByLabel("Fecha en que se notificó al despacho (opcional)").fill(iso(notif));
await page.getByRole("button", { name: "Registrar actuación" }).click();
await page.getByRole("heading", { name: "Nuevo pendiente en la agenda" }).waitFor();
ok(true, "al capturar la notificación se propone calcular el plazo");
await page.getByLabel("Qué hay que hacer").fill("Desahogar prevención");
await page.getByLabel("Días de plazo").fill("3");
await page.getByLabel("La notificación surte efectos").selectOption("dia_habil_siguiente");
await page.getByText(/^Vence el/).first().waitFor();
await page.getByRole("button", { name: "Ver días contados y saltados" }).click();
ok(await page.getByText(/Contados \(3\)/).count() === 1, "el desglose muestra los días contados");
await foto("ag-02-calculo");
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.getByText("Agregado a la agenda.").waitFor();
await page.getByRole("link", { name: "Desahogar prevención" }).click();
await page.getByRole("heading", { name: "Desahogar prevención" }).waitFor();
await page.getByRole("button", { name: "Validar fecha" }).click();
await page.getByText(/Validado por Admin Demo/).waitFor();
ok(true, "el abogado valida el plazo y queda su nombre");
await foto("ag-03-plazo");
await page.getByRole("button", { name: "Marcar como cumplido" }).click();
await page.getByLabel(/Nota/).fill("Se presentó el escrito de desahogo");
await page.getByRole("button", { name: "Confirmar" }).click();
await page.getByText("Marcado como cumplido.").waitFor();
ok(true, "plazo marcado como cumplido con nota");

// Audiencia con enlace de Meet desde la vista diaria
await page.getByRole("link", { name: "Hoy", exact: true }).click();
await page.getByRole("button", { name: "+ Audiencia" }).click();
await page.getByLabel("Qué hay que hacer").fill("Audiencia de juicio (prueba)");
const manana = new Date(hoy); manana.setDate(hoy.getDate() + 1);
await page.getByLabel("Fecha", { exact: true }).fill(iso(manana));
await page.getByLabel("Hora").fill("10:30");
await page.getByLabel("Enlace (Zoom, Meet, Teams)").fill("https://zoom.us/j/123456789");
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.getByText("Audiencia de juicio (prueba)").first().waitFor();
ok(await page.getByRole("link", { name: /Unirse \(Zoom\)/ }).count() >= 1, "la audiencia muestra el botón para unirse por Zoom");

// Calendario mensual
await page.getByRole("link", { name: "Calendario", exact: true }).click();
await page.getByText("Audiencia preliminar").first().waitFor();
ok(true, "calendario mensual con los pendientes");
await foto("ag-04-calendario");

// Días hábiles y plazos frecuentes
await page.getByRole("link", { name: "Días hábiles" }).click();
await page.getByRole("heading", { name: "Tribunal Laboral Ficticio (demostración)" }).waitFor();
await page.getByLabel("Desde").fill(`${hoy.getFullYear()}-12-21`);
await page.getByLabel("Hasta (periodo)").fill(`${hoy.getFullYear()}-12-31`);
await page.getByLabel("Motivo").fill("Segundo periodo vacacional (ejemplo)");
await page.getByRole("button", { name: "Agregar" }).click();
await page.getByText("11 día(s) guardados.").waitFor();
ok(await page.getByText("ART. 74 LFT").count() >= 1, "el calendario muestra los días del art. 74 LFT y los capturados");
await page.getByRole("button", { name: "+ Plazo frecuente" }).click();
await page.getByLabel("Nombre").fill("Desahogo de prevención (ejemplo)");
await page.getByLabel("Días", { exact: true }).fill("3");
await page.getByLabel("Surte efectos").selectOption("dia_habil_siguiente");
await page.getByLabel("Fundamento (artículo y ley)").fill("Capture aquí el artículo aplicable");
await page.getByRole("button", { name: "Guardar" }).click();
await page.getByText("Desahogo de prevención (ejemplo)").waitFor();
ok(true, "plazo frecuente definido por el despacho");
await foto("ag-05-dias-habiles");

// Avisos y calendario externo
await page.getByRole("link", { name: "Avisos y ajustes" }).click();
await page.getByRole("button", { name: "Generar enlace" }).click();
const url = await page.getByLabel("Enlace privado").inputValue();
const ics = await page.request.get(base + url.slice(url.indexOf("/api/agenda-feed/")));
ok(ics.status() === 200 && (await ics.text()).includes("BEGIN:VCALENDAR"), "el enlace privado entrega el calendario para Google u Outlook");
await foto("ag-06-ajustes");

const movil = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await movil.goto(base + "/login");
await movil.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await movil.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await movil.getByRole("button", { name: "Entrar" }).click();
await movil.waitForURL((u) => !u.pathname.startsWith("/login"));
await movil.goto(base + "/agenda");
await movil.getByRole("heading", { name: "Agenda de hoy" }).waitFor();
await foto("ag-07-movil", movil);
ok(errores.length === 0, "sin errores en la consola: " + errores.join(" | "));
await browser.close();
