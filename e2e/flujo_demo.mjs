// Recorrido de humo sobre la demo SINTÉTICA (requiere `npm i -g playwright` o Playwright disponible).
// Uso: node e2e/flujo_demo.mjs [http://localhost:3000] [carpeta_capturas] [pdf_real_opcional]
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");
import { mkdirSync } from "node:fs";

const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
const pdfReal = process.argv[4];
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
const errores = [];
page.on("console", (m) => m.type() === "error" && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));
const foto = (n) => page.screenshot({ path: `${dir}/${n}.png`, fullPage: true });

await page.goto(base + "/");
await page.waitForURL("**/login");
await page.getByLabel("Correo electrónico").fill("admin@demo.local");
await page.getByLabel(/Contraseña/).fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByRole("heading", { name: "Expedientes" }).waitFor();
await page.getByText("EJEMPLO SINTETICO").first().waitFor();
await foto("01-expedientes");
ok(await page.getByText("por resolver").count() >= 1, "la lista prioriza expedientes con pendientes");

// Expediente con incidencias
await page.getByRole("link", { name: "#2" }).click();
await page.getByText("Pendientes que impiden validar").waitFor();
await foto("02-revision-pendientes");
ok(await page.getByRole("button", { name: "Validar resultado" }).isDisabled(), "no se puede validar con pendientes");
await page.getByRole("button", { name: /^1\. 1\.ª qna\. enero/ }).click();
ok(await page.getByText("$10,408.60").count() >= 1, "quincena del caso de aceptación = $10,408.60");
ok(await page.getByText("La clave no está en el catálogo autorizado").count() === 4, "4 claves excluidas con motivo");
await foto("03-quincena-incluidos-excluidos");

// Visor del original + corrección de la fila sin importe
await page.getByRole("button", { name: /4\. 2\.ª qna\. febrero/ }).click();
await page.getByText("Importe faltante o ilegible").first().waitFor();
await page.locator("tr", { hasText: "Importe faltante o ilegible" }).getByRole("button").click();
await page.getByText("Fila seleccionada: 0512").waitFor();
await page.locator("img[alt^='Página']").waitFor();
await page.waitForTimeout(400);
await foto("04-visor-original");
await page.getByLabel("Importe", { exact: true }).fill("483.75");
await page.getByLabel("Motivo (obligatorio)").first().fill("Importe verificado contra el original");
await page.getByRole("button", { name: "Guardar corrección" }).click();
await page.getByText("Corrección registrada.").waitFor();
// importe negativo: confirmar
await page.getByRole("dialog").locator("tr", { hasText: "0607" }).first().click();
await page.getByText("Fila seleccionada: 0607").waitFor();
await page.getByLabel("Motivo (obligatorio)").first().fill("Descuento confirmado en el original");
await page.getByRole("button", { name: "Confirmar lectura tal cual" }).click();
await page.getByText("Lectura confirmada.").waitFor();
await page.getByRole("button", { name: "Cerrar" }).click();

// Resolver alertas de recibo: duplicado -> excluir, complementario -> incluir, otro trabajador -> excluir
async function decidir(texto, boton) {
  await page.locator("li", { hasText: texto }).getByRole("button", { name: "Revisar" }).first().click();
  await page.getByText("Acciones sobre el recibo").waitFor();
  await page.getByRole("dialog").locator("details").getByLabel("Motivo (obligatorio)").fill("Revisado contra el original");
  await page.getByRole("button", { name: boton }).click();
  await page.getByText(/Recibo (incluido|excluido)/).waitFor();
  await page.getByRole("button", { name: "Cerrar" }).click();
}
await decidir("Posible recibo duplicado", "Excluir este recibo");
await decidir("posible complementario", "Incluir este recibo");
await decidir("trabajador distinto", "Excluir este recibo");
await page.getByRole("button", { name: "Mantener separadas" }).click();
await page.getByText("Plazas separadas.").waitFor();
await page.getByText("Pendientes que impiden validar").waitFor({ state: "hidden" });
ok(await page.getByRole("button", { name: "Validar resultado" }).isEnabled(), "todos los pendientes resueltos");
await foto("05-revision-resuelta");

// Resultados, trazabilidad, validación y exportaciones
await page.getByRole("tab", { name: "Resultados" }).click();
await page.getByText("Total por clave de prestación").waitFor();
await foto("06-resultados");
await page.getByRole("tab", { name: /Trazabilidad/ }).click();
ok(await page.locator("tbody tr").count() >= 5, "correcciones y decisiones registradas");
await foto("07-trazabilidad");
await page.getByRole("button", { name: "Validar resultado" }).click();
ok(await page.getByRole("button", { name: "Validar", exact: true }).isDisabled(), "validar exige reconocer quincenas faltantes");
await page.getByRole("dialog").getByRole("checkbox").check();
await page.getByRole("button", { name: "Validar", exact: true }).click();
await page.getByText("Expediente validado.").waitFor();
ok(await page.getByText("Resultado provisional").count() === 0, "validado deja de ser provisional");
for (const [boton, ext] of [["Exportar Excel", "xlsx"], ["Exportar PDF", "pdf"]]) {
  const [d] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: boton }).click()]);
  await d.saveAs(`${dir}/expediente-demo.${ext}`);
  ok(d.suggestedFilename().includes("validado"), `${boton}: ${d.suggestedFilename()}`);
}
await foto("08-validado");

// Documentos, catálogos, usuarios
await page.getByRole("tab", { name: /Documentos/ }).click();
await page.getByText("Huella SHA-256").waitFor();
await foto("09-documentos");
await page.getByRole("link", { name: "Catálogos" }).click();
await page.getByRole("link", { name: "Versión 1" }).click();
await page.getByText("Es inmutable").waitFor();
await foto("10-catalogo-version");
await page.getByRole("link", { name: "Usuarios" }).click();
await page.getByText("Registro de auditoría").waitFor();
await page.getByText("expediente_validado").first().waitFor();
await foto("11-usuarios-auditoria");

if (pdfReal) { // Prueba privada con el PDF real: SIN capturas (contiene datos personales).
  const s = await page.evaluate(() => JSON.parse(sessionStorage.getItem("qc_sesion")));
  const h = { Authorization: `Bearer ${s.token}` };
  const { readFileSync } = await import("node:fs");
  const { default: mu } = await import("node:child_process");
  const nombre = mu.execSync(`python3 -I -c "import pymupdf,sys;print(pymupdf.open(sys.argv[1])[0].get_text().split(chr(10))[7])" "${pdfReal}"`).toString().trim();
  const e = await (await page.request.post(base + "/api/expedientes", { headers: h, data: { trabajador_nombre: nombre, periodo_inicio: "2025-12-01", periodo_fin: "2026-07-31", catalogo_version_id: 1 } })).json();
  const up = await page.request.post(`${base}/api/expedientes/${e.id}/documentos`, { headers: h, timeout: 120000,
    multipart: { archivos: { name: "comprobantes.pdf", mimeType: "application/pdf", buffer: readFileSync(pdfReal) } } });
  ok(up.ok(), "PDF real (20 MB) cargado a través del proxy de Next");
  let r;
  for (let i = 0; i < 60; i++) {
    r = await (await page.request.get(`${base}/api/expedientes/${e.id}/resultado`, { headers: h })).json();
    if (!r.alertas.some((a) => a.tipo === "documento_en_proceso")) break;
    await page.waitForTimeout(1000);
  }
  ok(r.quincenas.length === 16 && r.resumen.recibos === 16, "PDF real: 32 páginas -> 16 recibos -> 16 quincenas");
  ok(r.quincenas[0].total === "10408.60", "PDF real: 1-15 dic 2025 = 10,408.60");
  ok(r.puede_validarse && r.resumen.filas_pendientes === 0, `PDF real: sin pendientes; total ${r.total_expediente}`);
}
ok(errores.length === 0, "sin errores de consola: " + errores.join(" | "));
await browser.close();
