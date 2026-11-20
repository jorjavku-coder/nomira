// Recorrido de humo de Nomira Leads y Nomira Academia sobre la demo (datos ficticios).
// Uso: node e2e/leads_academia.mjs [http://localhost:3000] [carpeta_capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 1, acceptDownloads: true });
const page = await ctx.newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon|401|403|404|409|422/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));
const foto = async (n, p = page) => { await p.waitForTimeout(300); await p.screenshot({ path: `${dir}/${n}.png`, fullPage: true }); };

await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();

// ---------- Leads ----------
await page.getByRole("link", { name: "Leads", exact: true }).click();
await page.getByRole("heading", { name: "¿A quién hay que atender?" }).waitFor();
await page.getByText("Ana Demo Martínez").first().waitFor();
ok(await page.getByText("Prospectos nuevos").count() >= 1, "bandeja con prospectos nuevos");
await foto("ld-01-bandeja");
await page.getByRole("button", { name: "+ Agregar prospecto" }).first().click();
await page.getByLabel("Nombre", { exact: true }).fill("Gabriela Prueba Navegador");
await page.getByLabel("Teléfono (WhatsApp)").fill("5512340000");
await page.getByLabel("¿Qué necesita? (breve)").fill("Revisión de su liquidación");
await page.getByLabel("WhatsApp", { exact: true }).check();
await foto("ld-02-alta-rapida");
await page.getByRole("button", { name: "Agregar prospecto", exact: true }).click();
await page.getByRole("heading", { name: "Gabriela Prueba Navegador" }).waitFor();
ok(await page.getByText("Prospecto registrado.").count() === 1, "alta rápida guarda y abre la ficha");
await page.getByRole("button", { name: "Agendar consulta" }).click();
await page.getByRole("button", { name: "Agendar consulta" }).last().click();
await page.getByText("Consulta agendada.").waitFor();
await page.getByRole("button", { name: "Abrir en WhatsApp" }).count();
await page.getByPlaceholder("Escriba la respuesta").fill("Hola Gabriela, le confirmo su consulta.");
ok(await page.getByRole("link", { name: "Abrir en WhatsApp" }).count() === 1, "sin integración: ofrece abrir WhatsApp con el mensaje");
await page.getByRole("button", { name: "Ya lo envié (registrar)" }).click();
await page.getByText("Respuesta registrada.").waitFor();
await foto("ld-03-prospecto");
await page.getByRole("button", { name: "Cambiar etapa" }).click();
await page.getByText("No contratado", { exact: true }).click();
await page.getByLabel("Motivo").selectOption("Precio");
await page.getByRole("button", { name: "Guardar" }).click();
await page.getByText("Etapa actualizada.").waitFor();
ok(await page.getByText(/Motivo: Precio/).count() >= 1, "no contratado con motivo");

await page.getByRole("link", { name: "Seguimiento" }).click();
await page.getByRole("heading", { name: "Seguimiento" }).waitFor();
await page.getByText("Bruno Ficticio Ruiz").waitFor();
await foto("ld-04-tablero");
await page.getByLabel("Mover a Bruno Ficticio Ruiz").selectOption({ label: "Consulta agendada" });
await page.getByRole("button", { name: "Mover" }).click();
await page.getByText(/pasó a «Consulta agendada»/).waitFor();
ok(true, "mover tarjeta entre etapas");

await page.getByRole("link", { name: "Campañas y fuentes" }).click();
await page.getByText("Facebook — despidos (noviembre)").waitFor();
await page.getByRole("button", { name: "+ Nueva campaña" }).click();
await page.getByLabel("Nombre").fill("Instagram — pensiones");
await page.getByLabel("Canal").selectOption("instagram");
await page.getByLabel("Inversión (opcional)").fill("1200");
await page.getByRole("button", { name: "Crear campaña" }).click();
await page.getByText(/Campaña creada/).waitFor();
await foto("ld-05-campanas");
const enlace = await page.locator("article", { hasText: "Instagram — pensiones" }).locator("code").last().innerText();
ok(enlace.includes("/contacto?utm_source=instagram") && enlace.includes("#"), "la campaña da un enlace con parámetros");

// Formulario público (otra pestaña, sin sesión)
const pub = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await pub.goto(enlace);
await pub.getByRole("heading", { name: "Solicite que le contactemos" }).waitFor();
await pub.getByLabel("Nombre").fill("Hugo Formulario Ficticio");
await pub.getByLabel("Teléfono o WhatsApp").fill("5577001122");
await pub.getByLabel("¿En qué le podemos ayudar? (breve)").fill("Quiero saber de mi pensión");
await foto("ld-06-formulario-publico", pub);
await pub.getByRole("checkbox").check();
await pub.getByRole("button", { name: "Enviar solicitud" }).click();
await pub.getByRole("heading", { name: "Recibimos su solicitud" }).waitFor();
ok(!pub.url().includes("#"), "el enlace no queda en la barra de direcciones");
await foto("ld-07-formulario-enviado", pub);
await page.getByRole("link", { name: "Bandeja" }).click();
await page.getByText("Hugo Formulario Ficticio").first().waitFor();
ok(true, "el prospecto del formulario aparece en la bandeja");
await page.getByRole("link", { name: "Resultados" }).click();
await page.getByText("Por campaña").waitFor();
await foto("ld-08-resultados");
await page.getByRole("navigation", { name: "Nomira Leads" }).getByRole("link", { name: "Configuración" }).click();
await page.getByText("WhatsApp Business Platform (API oficial de Meta)").waitFor();
await foto("ld-09-configuracion");

// ---------- Academia ----------
await page.getByRole("link", { name: "Academia", exact: true }).click();
await page.getByRole("heading", { name: "Mi aprendizaje" }).waitFor();
await page.getByText("Atención inicial de clientes").first().waitFor();
await foto("ac-01-mi-aprendizaje");
await page.locator("article", { hasText: "Atención inicial de clientes" }).first().getByRole("link", { name: "Iniciar curso" }).click();
await page.getByRole("button", { name: "Iniciar curso" }).click();
await page.getByRole("heading", { name: "Prepárese en dos minutos" }).waitFor();
await page.getByText("Acordar una hora concreta para llamar").click();
await page.getByRole("button", { name: "Responder" }).click();
await page.getByText("¡Correcto!").waitFor();
await foto("ac-02-leccion");
for (let i = 0; i < 6; i++) {
  if (await page.getByRole("heading", { name: "Cuestionario final" }).count()) break;
  const resp = page.getByRole("button", { name: "Responder" });
  if (await resp.count()) { await page.locator("input[name=actividad]").nth(1).check(); await resp.click(); await page.waitForTimeout(300); }
  await page.getByRole("button", { name: /Completar|Terminar|Siguiente lección/ }).click();
  await page.waitForTimeout(700);
}
await page.getByRole("heading", { name: "Cuestionario final" }).waitFor();
for (const n of [0, 1, 2]) await page.locator("fieldset").nth(n).locator("input").nth(1).check();
await page.getByRole("button", { name: "Enviar respuestas" }).click();
await page.getByText(/Obtuvo 100 de 100/).waitFor();
ok(await page.getByText("¡Aprobado! Completó el curso.").count() === 1, "cuestionario aprobado y curso completado");
const [descarga] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Descargar constancia" }).click()]);
ok((await descarga.suggestedFilename()).endsWith(".pdf"), "constancia de participación en PDF");
await foto("ac-03-cuestionario");

await page.getByRole("link", { name: "Administrar" }).click();
await page.getByRole("button", { name: "+ Nuevo curso" }).click();
await page.getByLabel("Título").fill("Seguimiento de trámites ISSEMYM");
await page.getByLabel("Materia", { exact: true }).fill("ISSEMYM");
await page.getByLabel(/Tiene contenido jurídico/).check();
await page.getByRole("button", { name: "Crear y editar" }).click();
await page.getByRole("heading", { name: "Seguimiento de trámites ISSEMYM" }).waitFor();
await page.getByPlaceholder("Título de una nueva lección").fill("Documentos que suele pedir el instituto");
await page.getByRole("button", { name: "+ Lección" }).click();
await page.getByText(/Lección agregada/).waitFor();
await page.getByRole("button", { name: "Editar", exact: true }).first().click();
await page.getByLabel("Texto breve").fill("Lista de verificación interna del despacho.");
await page.getByLabel("Video (enlace https: YouTube, Vimeo u otro)").fill("https://www.youtube.com/watch?v=abcdefghijk");
await page.getByRole("button", { name: "Guardar lección" }).click();
await page.getByText("Lección guardada.").waitFor();
await page.getByRole("button", { name: "Publicar" }).click();
ok(await page.getByRole("button", { name: "Publicar" }).last().isDisabled(), "contenido jurídico: no se publica sin confirmar la revisión");
await page.getByText(/Revisé el contenido/).click();
await page.getByRole("button", { name: "Publicar" }).last().click();
await page.getByText("Curso publicado.").waitFor();
await foto("ac-04-editor");

await page.getByRole("link", { name: "Equipo" }).click();
await page.getByRole("button", { name: "Asignar curso" }).click();
await page.getByRole("dialog").locator("select").first().selectOption({ label: "Seguimiento de trámites ISSEMYM" });
await page.locator("label", { hasText: "Analista" }).first().locator("input").check();
await page.getByRole("button", { name: "Asignar curso" }).last().click();
await page.getByText("Curso asignado.").waitFor();
await foto("ac-05-equipo");
await page.getByRole("button", { name: "Por curso" }).click();
await page.getByText("Seguimiento de trámites ISSEMYM").waitFor();
ok(true, "avance por curso");

// Celular
const movil = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await movil.goto(base + "/login");
await movil.getByLabel("Correo electrónico").first().fill("analista@demo.local");
await movil.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await movil.getByRole("button", { name: "Entrar" }).click();
await movil.waitForTimeout(1500);
await movil.goto(base + "/academia");
await movil.getByRole("heading", { name: "Mi aprendizaje" }).waitFor();
await movil.getByText("Seguimiento de trámites ISSEMYM").first().waitFor();
ok(true, "el analista ve el curso asignado");
await foto("m-ac-inicio", movil);
await movil.goto(base + "/leads");
await movil.getByRole("heading", { name: "¿A quién hay que atender?" }).waitFor();
await foto("m-ld-bandeja", movil);
ok(errores.length === 0, "sin errores en la consola: " + errores.join(" | "));
await browser.close();
