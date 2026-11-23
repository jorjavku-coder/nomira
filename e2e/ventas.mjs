// Ventas de Nomira (CRM del panel): una solicitud del sitio entra sola, se registra la llamada, se programa una tarea,
// se cotiza desde la oportunidad con los datos del prospecto y se crea una campaña. Uso: node e2e/ventas.mjs [url] [carpeta]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));

// un prospecto llena el formulario del sitio
const r = await ctx.request.post(base + "/api/solicitudes", { data: { tipo: "suscripcion", nombre: "Lic. Rosa Prospecto", empresa: "Bufete Ficticio Rosa",
  email: "rosa@bufete-ficticio.test", telefono: "5512341234", mensaje: "Somos 6 abogados laborales, queremos ver Agenda.", acepta_contacto: true } });
ok(r.status() === 201, "solicitud desde el sitio");

await page.goto(base + "/plataforma/login");
await page.getByLabel(/Correo/).fill("dueno@nomira.test");
await page.getByLabel(/Contraseña/).first().fill("Panel-Nomira-2026");
await page.getByRole("button", { name: /Entrar/ }).click();
await page.getByRole("link", { name: /Ventas \(CRM\)/ }).click();
await page.getByRole("link", { name: "Leads (MQL)" }).click();
await page.getByRole("link", { name: "Lic. Rosa Prospecto" }).waitFor();
ok(await page.getByText("Sin intentos").count() === 1, "la solicitud entra a Leads (MQL), sin intentos");

// importar leads de Excel (archivo de ejemplo)
await page.getByRole("button", { name: "Importar Excel" }).click();
await page.getByLabel("Archivo de leads").setInputFiles(new URL("./fixtures/leads-ejemplo.csv", import.meta.url).pathname);
await page.getByText(/2 nuevos/).waitFor();
await page.getByRole("button", { name: "Cargar 2 lead(s)" }).click();
await page.getByText("Se cargaron 2 lead(s).").waitFor();
ok(await page.getByRole("link", { name: "Lic. Mario Excel" }).count() === 1, "importar Excel con vista previa");
await page.screenshot({ path: `${dir}/ventas-01-leads.png` });

// un intento sin respuesta no lo califica; la llamada efectiva sí
const fila = page.getByRole("row", { name: /Lic\. Rosa Prospecto/ });
await fila.getByRole("button", { name: "+ Intento" }).click();
await page.getByLabel("Qué pasó").fill("No contestó");
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.getByText("Actividad registrada.").waitFor();
ok(await page.getByRole("link", { name: "Lic. Rosa Prospecto" }).count() === 1, "el intento lo deja en MQL");
await page.getByRole("row", { name: /Lic\. Rosa Prospecto/ }).getByRole("button", { name: "Pasar a SQL" }).click();
await page.getByLabel("Valor mensual estimado (opcional)").fill("3490");
await page.getByRole("button", { name: "Pasar a SQL y abrir oportunidad" }).click();
await page.waitForURL(/oportunidades\/\d+/);
await page.getByText("Calificado como SQL: llamada efectiva").waitFor();
ok(true, "pasa a SQL y abre la oportunidad en Contactado con su historial");
await page.getByRole("button", { name: "+ Tarea" }).click();
await page.getByLabel("Qué hay que hacer").fill("Dar demo de Agenda");
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.getByText("Tarea: Dar demo de Agenda").waitFor();
await page.getByRole("button", { name: "Demo agendada" }).click();
await page.getByText("Etapa: Contactado (SQL) → Demo agendada").waitFor();
ok(true, "tarea programada y etapa movida");
await page.screenshot({ path: `${dir}/ventas-02-oportunidad.png`, fullPage: true });

await page.getByRole("link", { name: "+ Cotizar" }).click();
await page.getByRole("heading", { name: "Nueva cotización" }).waitFor();
await page.getByText("al enviarse o pagarse, la oportunidad avanza sola").waitFor();
ok(await page.locator("input").evaluateAll((xs) => xs.some((x) => x.value === "rosa@bufete-ficticio.test")), "la cotización llega con los datos del prospecto");

await page.goto(base + "/plataforma/ventas/campanas");
await page.getByRole("button", { name: "+ Nueva campaña" }).click();
await page.getByLabel("Nombre").fill("Facebook · laborales · noviembre");
await page.getByLabel(/Presupuesto/).fill("5000");
await page.getByRole("button", { name: "Guardar", exact: true }).click();
await page.getByText("Facebook · laborales · noviembre").waitFor();
ok(true, "campaña creada");
await page.goto(base + "/plataforma/ventas/tareas");
await page.getByText("Tarea: Dar demo de Agenda").waitFor();
ok(true, "la tarea aparece en Mis tareas");
await page.screenshot({ path: `${dir}/ventas-03-tareas.png` });
await page.goto(base + "/plataforma/ventas/contactos");
await page.getByRole("link", { name: "Lic. Rosa Prospecto" }).waitFor();
ok(await page.getByRole("link", { name: "Lic. Mario Excel" }).count() === 0, "Contactos (SQL) solo muestra los calificados");
await page.goto(base + "/plataforma/ventas");
await page.getByText("Pasaron a SQL este mes").waitFor();
await page.screenshot({ path: `${dir}/ventas-04-embudo.png` });
ok(errores.length === 0, "sin errores en consola: " + errores.join(" | "));
await browser.close();
