// Bolsa de trabajo: vacante de la demo con resultados; nueva vacante (filtro antidiscriminación), publicación en el portal,
// postulación pública con CV, envío de una prueba, el candidato la contesta y el despacho ve el resultado.
// Uso: node e2e/bolsa.mjs [base] [capturas]
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const cv = `${dir}/cv-prueba.pdf`;
writeFileSync(cv, "%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => localStorage.setItem("nomira:bienvenida", "1"));
const p = await ctx.newPage();
const errores = [];
p.on("pageerror", (e) => errores.push(String(e)));
await p.goto(base + "/login");
await p.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await p.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await p.getByRole("button", { name: "Entrar", exact: true }).click();
await p.waitForURL(/\/(app|inicio)/);
await p.getByRole("navigation", { name: "Principal" }).getByRole("button", { name: "Más" }).click();  // menú «Más»
await p.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Bolsa de trabajo" }).click();
await p.getByRole("heading", { name: "Bolsa de trabajo" }).waitFor();
await p.getByRole("link", { name: /Abogado\(a\) litigante laboral/ }).click();
await p.getByText("Mariana Ejemplo Torres").waitFor();
ok(await p.getByText(/derecho laboral 90%/).count() === 1, "la demo muestra el resultado de la prueba en la lista");
await p.getByRole("button", { name: "Mariana Ejemplo Torres" }).click();
await p.getByRole("button", { name: /90% · Ver/ }).click();
await p.getByText("9 de 10").waitFor();
ok(true, "el resultado muestra aciertos");
await p.screenshot({ path: `${dir}/bt-01-resultado.png` });

// nueva vacante
await p.goto(base + "/bolsa");
await p.getByRole("button", { name: "+ Nueva vacante" }).click();
const dlg = p.getByRole("dialog");
await dlg.getByLabel("Título del puesto").fill("Pasante de derecho civil E2E");
await dlg.locator("label", { hasText: "Materia" }).locator("select").selectOption("civil");
await dlg.locator("label", { hasText: "Tipo de puesto" }).locator("select").selectOption("pasante");
await dlg.locator("label", { hasText: /^Estado/ }).locator("select").selectOption("Jalisco");
await dlg.getByLabel("¿Qué hará la persona?").fill("Apoyar en la elaboración de escritos y el seguimiento de expedientes civiles en juzgados de Guadalajara.");
await dlg.getByLabel(/Requisitos/).fill("Estudiante de derecho. Soltero, buena presentación.");
await dlg.getByRole("button", { name: "Guardar borrador" }).click();
await dlg.getByText(/discriminatorios/).waitFor();
ok(true, "avisa de requisitos discriminatorios");
await dlg.getByLabel(/Requisitos/).fill("Estudiante de derecho de 7.º semestre en adelante.");
await dlg.getByRole("button", { name: "Guardar borrador" }).click();
await p.waitForURL(/\/bolsa\/\d+$/);
await p.getByRole("button", { name: "Publicar" }).click();
await p.getByText("Vacante publicada.").waitFor();
const vacanteUrl = p.url();

// candidato en el portal público
const pub = await ctx.newPage();
pub.on("pageerror", (e) => errores.push(String(e)));
await pub.goto(base + "/empleos");
await pub.getByRole("link", { name: /Pasante de derecho civil E2E/ }).click();
await pub.getByRole("heading", { name: "Pasante de derecho civil E2E" }).waitFor();
const f = pub.getByRole("form", { name: "Postularme" });
await f.getByLabel("Nombre completo").fill("Candidata De Prueba");
await f.getByLabel("Correo").fill("candidata.e2e@ejemplo.test");
await f.getByLabel(/Teléfono/).fill("5512345678");
await f.getByLabel(/CV en PDF/).setInputFiles(cv);
await f.getByRole("checkbox").check();
await pub.screenshot({ path: `${dir}/bt-02-postular.png`, fullPage: true });
await f.getByRole("button", { name: "Enviar postulación" }).click();
await pub.getByText("¡Listo, ya te postulaste!").waitFor();
ok(true, "postulación pública con CV");

// enviar prueba
await p.goto(vacanteUrl);
await p.getByRole("button", { name: "Candidata De Prueba" }).click();
await p.getByRole("button", { name: "Enviar pruebas" }).click();
const ep = p.getByRole("dialog", { name: /Enviar pruebas/ });
await ep.getByText("Razonamiento numérico").click();
await ep.getByLabel(/Mandar los enlaces/).uncheck();
await ep.getByRole("button", { name: /Crear 1 enlace/ }).click();
const enlace = (await ep.locator("span.break-all").first().innerText()).trim();
ok(/\/prueba\//.test(enlace), "crea el enlace personal de la prueba");
await ep.getByRole("button", { name: "Terminar" }).click();

// el candidato contesta
const t = await ctx.newPage();
t.on("pageerror", (e) => errores.push(String(e)));
await t.goto(enlace.replace(/^https?:\/\/[^/]+/, base));
await t.getByRole("heading", { name: "Razonamiento numérico" }).waitFor();
await t.getByRole("checkbox").check();
await t.getByRole("button", { name: "Empezar" }).click();
const grupos = t.locator("fieldset");
await grupos.first().waitFor();
const n = await grupos.count();
for (let i = 0; i < n; i++) await grupos.nth(i).getByRole("radio").nth(2).check();
await t.screenshot({ path: `${dir}/bt-03-prueba.png` });
await t.getByRole("button", { name: "Terminar y enviar" }).click();
await t.getByText("¡Gracias! Terminaste la prueba").waitFor();
ok(n === 12, "el candidato contesta las 12 preguntas");

await p.goto(vacanteUrl);
await p.getByText(/Razonamiento numérico \d+%/).waitFor();
ok(true, "el despacho ve el porcentaje en la lista de candidatos");
await p.screenshot({ path: `${dir}/bt-04-candidatos.png`, fullPage: true });
await p.goto(base + "/bolsa");
await p.getByRole("tab", { name: "Pruebas psicométricas" }).click();
await p.getByRole("button", { name: "Ver preguntas" }).first().click();
await p.getByRole("dialog").getByText("Soy el alma de la fiesta.").waitFor();
ok(true, "vista previa del cuestionario de personalidad");
ok(!errores.length, "sin errores de JavaScript " + errores.join(" "));
await b.close();
