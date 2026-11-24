// Recorrido de humo de Nomira Evidencia sobre la demo (documentos ficticios).
// Uso: node e2e/evidencia.mjs [http://localhost:3000] [carpeta_capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 2, acceptDownloads: true });
const errores = [];
page.on("console", (m) => m.type() === "error" && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));
const foto = async (n) => { await page.waitForTimeout(250); await page.screenshot({ path: `${dir}/${n}.png`, fullPage: true }); };

await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByRole("link", { name: "Evidencia" }).click();
await page.getByRole("heading", { name: "Nomira Evidencia" }).waitFor();
await page.getByText("Juan Demo Ficticio vs. Empresa Ficticia Demo").waitFor();
await foto("ev-01-asuntos");
await page.getByText("Juan Demo Ficticio vs. Empresa Ficticia Demo").click();

// Pestaña Hechos (abre sola porque hay propuestas por revisar)
await page.getByRole("tab", { name: /Hechos/ }).waitFor();
ok(await page.getByRole("tab", { name: /Hechos/ }).getAttribute("aria-selected") === "true", "abre en Hechos cuando hay propuestas por revisar");
ok(await page.getByText("Por revisar", { exact: true }).count() >= 1, "las propuestas aparecen «Por revisar»");
await foto("ev-02-hechos");
// Ver la fuente: página del documento con la frase resaltada
await page.locator("article").first().getByRole("button", { name: /D\d+ ·/ }).click();
await page.getByText("Texto de origen").waitFor();
await page.locator("img[alt^='Página']").waitFor();
await foto("ev-03-fuente");
await page.getByRole("button", { name: "Cerrar", exact: true }).click();
// Confirmar la propuesta del finiquito (importe) y editar otra
const finiq = page.locator("article", { hasText: "42,300.00" });
await finiq.getByRole("button", { name: "Confirmar" }).click();
await page.getByText("Hecho confirmado.").waitFor();
const aviso = page.locator("article", { hasText: "Ciudad de México, a 30 de junio de 2025" });
await aviso.getByRole("button", { name: "Editar" }).click();
await page.getByLabel("Descripción del hecho").fill("Fecha del aviso de terminación entregado al trabajador");
await page.getByRole("button", { name: "Guardar" }).click();
await page.getByText("«Editado por usuario»").waitFor();
ok(true, "confirmar y editar hechos");

// Cronología: contradicción señalada sin decidir
await page.getByRole("tab", { name: /Cronología/ }).click();
await page.getByText("Posibles contradicciones para revisar").waitFor();
ok(await page.getByText("Posible contradicción para revisar").count() === 2, "ambas versiones marcadas en la cronología");
await foto("ev-04-cronologia");

// Matriz: sugerencia y decisión humana
await page.getByRole("tab", { name: /Matriz/ }).click();
const inicio = page.locator("section", { hasText: "Fecha de inicio de la relación de trabajo" }).first();
ok(await inicio.getByText(/Sugerencia del sistema \(por revisar\):/).count() === 1, "sugerencia visible como tal");
await inicio.getByLabel("Estado del punto").selectOption("contradictorio");
await page.getByText("Estado actualizado.").waitFor();
const prima = page.locator("section", { hasText: "Pago de la prima vacacional de 2024" }).first();
await prima.getByRole("button", { name: "+ Vincular evidencia" }).click();
await page.getByRole("button", { name: "Un documento o página" }).click();
await page.getByRole("dialog").locator("select").selectOption({ index: 4 });
await page.getByRole("dialog").locator('input[type="number"]').fill("1");
await page.getByRole("button", { name: "Vincular", exact: true }).click();
await page.getByText("Evidencia vinculada.").waitFor();
await foto("ev-05-matriz");
ok(true, "decidir estado y vincular evidencia");

// Pendientes y lista para el cliente
await page.getByRole("tab", { name: /Pendientes/ }).click();
await page.getByLabel("Documento o dato pendiente").fill("Contrato colectivo vigente");
await page.getByLabel("Responsable").fill("Cliente");
await page.getByRole("button", { name: "Agregar", exact: true }).click();
await page.getByText("Pendiente agregado.").waitFor();
await foto("ev-06-pendientes");
for (const [boton, ext] of [["Lista para el cliente (PDF)", "pdf"]]) {
  const [d] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: boton }).click()]);
  await d.saveAs(`${dir}/ev-pendientes.${ext}`);
}
for (const [boton, ext] of [["Exportar PDF", "pdf"], ["Exportar Excel", "xlsx"]]) {
  const [d] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: boton }).click()]);
  await d.saveAs(`${dir}/ev-expediente.${ext}`);
  ok(d.suggestedFilename().startsWith("evidencia-"), `${boton}: ${d.suggestedFilename()}`);
}

// Documentos: clasificar el que falta
await page.getByRole("tab", { name: /Documentos/ }).click();
await page.locator("tr", { hasText: "recibo_de_finiquito" }).getByRole("button", { name: "Clasificar" }).click();
await page.getByRole("button", { name: "Guardar" }).click();
await page.getByText("Clasificación guardada.").waitFor();
await foto("ev-07-documentos");

// Módulos: sin Nómina, el menú cambia y /app lleva a Evidencia; los datos siguen
await page.getByRole("link", { name: "Datos y módulos" }).click();
await page.getByText("Módulos", { exact: true }).waitFor();
await foto("ev-08-modulos");
page.once("dialog", (d) => d.accept());
await page.getByRole("switch", { name: /Desactivar Nómina y prestaciones/ }).click();
await page.getByText("Módulo desactivado. Sus datos se conservan.").waitFor();
await page.getByRole("link", { name: "Revisión de nómina" }).waitFor({ state: "detached" });
await page.goto(base + "/app");
await page.waitForURL("**/evidencia");
ok(true, "sin Nómina: el menú lo oculta y /app redirige a Evidencia");
await page.goto(base + "/catalogos");
await page.getByText("Módulo no activo").waitFor();
ok(true, "ruta de un módulo inactivo bloqueada en la interfaz");
await page.goto(base + "/organizacion");
await page.getByRole("switch", { name: /Activar Nómina y prestaciones/ }).click();
await page.getByText("Módulo activado.").waitFor();
await page.getByRole("link", { name: "Revisión de nómina" }).waitFor();
ok(true, "Nómina reactivada");
ok(errores.length === 0, "sin errores de consola: " + errores.join(" | "));
await browser.close();
