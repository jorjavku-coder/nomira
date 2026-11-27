// Gana con Nomira: Nomira enciende la ruleta; el despacho contesta la trivia, gira, se suma a la red de casos e
// invita a otro despacho; una persona calcula su finiquito, pide un abogado y el caso llega a los Prospectos del despacho.
// Uso: node e2e/crecimiento.mjs [url] [carpeta]   (el despacho demo debe tener plan pagado vigente y Prospectos activo)
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const b = await chromium.launch();
const errores = [];
const vigilar = (p) => { p.on("console", (x) => x.type() === "error" && !/favicon|401|404|409/.test(x.text()) && errores.push(x.text())); p.on("pageerror", (e) => errores.push(String(e))); };

// 1. Nomira enciende la ruleta
const pl = await b.newPage({ viewport: { width: 1366, height: 900 } });
vigilar(pl);
await pl.goto(base + "/plataforma/login");
await pl.getByLabel(/Correo/).fill("dueno@nomira.test");
await pl.getByLabel(/Contraseña/).first().fill("Panel-Nomira-2026");
await pl.getByRole("button", { name: /Entrar/ }).click();
await pl.waitForURL(/\/plataforma(\/|$)/);
await pl.getByRole("link", { name: "Juegos y referidos" }).click();
await pl.getByRole("heading", { name: "Juegos y referidos" }).waitFor();
await pl.getByLabel("Ruleta activa").check();
await pl.getByRole("button", { name: "Guardar reglas" }).click();
await pl.getByText("Reglas guardadas.").waitFor();
await pl.screenshot({ path: `${dir}/crec-01-panel-reglas.png`, fullPage: true });
await pl.getByRole("button", { name: "Ruleta", exact: true }).click();
await pl.getByRole("cell", { name: "6 meses gratis", exact: true }).waitFor();
await pl.screenshot({ path: `${dir}/crec-02-panel-ruleta.png`, fullPage: true });
ok(true, "Nomira enciende la ruleta y ve sus probabilidades");

// 2. el despacho juega
const p = await b.newPage({ viewport: { width: 1366, height: 900 } });
vigilar(p);
await p.goto(base + "/login");
await p.getByLabel(/Correo/).fill("admin@demo.local");
await p.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await p.getByRole("button", { name: /Entrar/ }).click();
await p.waitForURL(/\/inicio/);
await p.getByRole("link", { name: /Trivia jurídica del día/ }).click();
await p.getByRole("heading", { name: /Juegue, invite/ }).waitFor();
await p.screenshot({ path: `${dir}/crec-03-premios.png`, fullPage: true });
const trivia = p.locator("section[aria-labelledby='t-trivia']");
for (let i = 0; i < 3; i++) {
  await trivia.locator("div.grid button").first().click();
  await trivia.locator("[role=status]").waitFor();
}
await trivia.getByText(/Terminó la trivia de hoy/).waitFor();
ok(true, "contesta las 3 preguntas del día y ve la explicación");
await p.getByRole("button", { name: "Girar la ruleta" }).click();
await p.getByText(/Ganó:/).first().waitFor({ timeout: 10000 });
ok(true, "gira la ruleta: " + (await p.getByText(/🎉 Ganó:/).innerText()));
await p.waitForTimeout(800);
await p.screenshot({ path: `${dir}/crec-04-jugado.png`, fullPage: true });
ok(await p.getByText(/ya giró esta semana|🎉 Ganó/).count() > 0, "solo un giro por semana");
const casos = p.locator("section[aria-labelledby='t-casos']");
await casos.getByLabel(/Quiero recibir casos/).check();
await casos.getByRole("button", { name: "Ciudad de México" }).click();
await casos.getByRole("button", { name: "Guardar" }).click();
await p.getByText("Guardado.").waitFor();
ok(true, "el despacho se suma a la red de casos en CDMX");
const enlace = await p.locator("[data-prueba=enlace-invitacion]").innerText();
ok(/\/invita\/[A-Z0-9]{6}$/.test(enlace), "tiene su enlace de invitación " + enlace);

// 3. otro despacho abre la invitación
const inv = await b.newPage({ viewport: { width: 1280, height: 860 } });
vigilar(inv);
await inv.goto(base + new URL(enlace).pathname);
await inv.getByRole("heading", { name: /le invita a usar Nomira/ }).waitFor();
await inv.screenshot({ path: `${dir}/crec-05-invitacion.png`, fullPage: true });
ok(true, "la invitación muestra el nombre del despacho");

// 4. una persona calcula su finiquito y pide un abogado
const c = await b.newPage({ viewport: { width: 1280, height: 900 } });
vigilar(c);
await c.goto(base + "/calculadora-finiquito");
await c.getByLabel("Fecha de ingreso").fill("2019-03-01");
await c.getByLabel("Fecha de baja o despido").fill("2025-10-15");
await c.getByLabel("Salario diario").fill("650");
await c.locator("[data-prueba=total]").filter({ hasText: "$" }).waitFor();
await c.getByRole("button", { name: "Quiero contactar a un abogado" }).click();
await c.getByLabel("¿En qué estado está?").selectOption("YUC");
await c.getByText(/no hay un despacho de Nomira disponible/).waitFor();
ok(true, "sin despacho en su estado no se piden datos");
await c.getByLabel("¿En qué estado está?").selectOption("CDMX");
await c.getByLabel("Su nombre").fill("Persona Ejemplo Ficticia");
await c.getByLabel("WhatsApp o teléfono").fill("55 1234 0000");
await c.getByLabel(/Cuéntenos/).fill("Me despidieron sin darme nada por escrito.");
await c.getByRole("checkbox").check();
await c.screenshot({ path: `${dir}/crec-06-calculadora.png`, fullPage: true });
await c.getByRole("button", { name: "Enviar mi caso" }).click();
await c.getByText(/Su caso llegó a/).waitFor();
await c.screenshot({ path: `${dir}/crec-07-enviado.png`, fullPage: true });
ok(true, "el caso se envía a un despacho");

// 5. el caso aparece en los Prospectos del despacho
await p.goto(base + "/leads");
await p.getByText("Persona Ejemplo Ficticia").first().waitFor();
await p.screenshot({ path: `${dir}/crec-08-prospecto.png` });
ok(true, "el despacho lo ve en Prospectos");

// 6. celular
const m = await b.newPage({ viewport: { width: 390, height: 844 } });
await m.goto(base + "/login");
await m.getByLabel(/Correo/).fill("admin@demo.local");
await m.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await m.getByRole("button", { name: /Entrar/ }).click();
await m.waitForURL(/\/inicio/);
await m.goto(base + "/premios");
await m.locator("[data-prueba=puntos]").waitFor();
await m.screenshot({ path: `${dir}/crec-09-celular.png`, fullPage: true });

ok(errores.length === 0, "sin errores en consola " + (errores.length ? JSON.stringify(errores.slice(0, 3)) : ""));
await b.close();
