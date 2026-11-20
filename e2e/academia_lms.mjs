// Recorrido de Nomira Academia como LMS: importar SCORM y enlaces, subir video, catálogo con costo,
// acceso de cortesía y verificación pública del diploma. Datos ficticios.
// Uso: node e2e/academia_lms.mjs [http://localhost:3000] [carpeta_capturas] [carpeta_archivos]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
const arch = process.argv[4] || "/tmp/lmsf"; // paquete.zip (SCORM 1.2) y video.mp4
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const browser = await chromium.launch();
const errores = [];
async function nueva() {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 }, acceptDownloads: true });
  const p = await ctx.newPage();
  p.on("console", (m) => m.type() === "error" && !/favicon|401|402|403|404|409|422/.test(m.text()) && errores.push(m.text()));
  p.on("pageerror", (e) => errores.push(String(e)));
  return p;
}
const foto = async (p, n) => { await p.waitForTimeout(300); await p.screenshot({ path: `${dir}/${n}.png`, fullPage: true }); };

const page = await nueva();
await page.goto(base + "/login");
await page.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await page.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByRole("link", { name: "Academia", exact: true }).click();
await page.getByRole("heading", { name: "Mi aprendizaje" }).waitFor();
await page.goto(base + "/academia/administrar");
await page.getByText("Cursos propios", { exact: true }).waitFor();
ok(await page.getByText(/de 5/).count() >= 1, "muestra el límite de 5 cursos propios");
await foto(page, "lms-01-administrar");

// SCORM
await page.getByRole("button", { name: "Importar o pedir ayuda" }).click();
await page.getByRole("tab", { name: "Archivo SCORM" }).click();
await page.getByLabel("Paquete SCORM").setInputFiles(`${arch}/paquete.zip`);
await foto(page, "lms-02-importar-scorm");
await page.getByRole("button", { name: "Importar SCORM" }).click();
await page.waitForURL(/\/academia\/administrar\/\d+/);
await page.getByText("Curso SCORM de prueba").first().waitFor();
ok(true, "SCORM importado: abre el editor con el título del paquete");
const idScorm = page.url().match(/(\d+)$/)[1];
await page.getByRole("button", { name: "Publicar", exact: true }).first().click();
await page.getByText("Revisé el contenido").click();
await page.getByRole("button", { name: "Publicar", exact: true }).last().click();
await page.getByText("Curso publicado.").waitFor();
await page.getByRole("link", { name: "Vista previa" }).click();
await page.waitForURL(/\/academia\/cursos\/\d+/);
await page.locator("a[href^='/academia/lecciones/']").first().click();
const marco = page.frameLocator('iframe[title="Contenido SCORM"]');
await marco.getByText("iniciado").waitFor();
ok(true, "el paquete SCORM corre aislado y encuentra la API");
await marco.getByRole("button", { name: "Terminar unidad" }).click();
await page.getByText(/completad|Completad/).first().waitFor({ timeout: 15000 });
ok(true, "al terminar el SCORM se guarda el avance y la lección queda completada");
await foto(page, "lms-03-scorm");

// Enlaces + video subido
await page.goto(base + "/academia/administrar");
await page.getByRole("button", { name: "Importar o pedir ayuda" }).click();
await page.getByLabel("Enlaces").fill("https://www.youtube.com/watch?v=dQw4w9WgXcQ\nhttps://vimeo.com/76979871");
await page.getByLabel("Título del curso (opcional)").fill("Inducción con videos (prueba)");
await page.getByLabel("Materia").fill("Inducción");
await page.getByRole("button", { name: "Crear curso" }).click();
await page.waitForURL(/\/academia\/administrar\/\d+/);
await page.getByText("Inducción con videos (prueba)").first().waitFor();
ok(await page.getByRole("button", { name: "Editar" }).count() === 2, "una lección por enlace pegado");
await page.getByRole("button", { name: "Editar" }).first().click();
await page.getByLabel("Archivo de video").setInputFiles(`${arch}/video.mp4`);
await page.getByRole("button", { name: "Subir video" }).click();
await page.getByText("Video cargado.").waitFor();
ok(true, "video subido como archivo");
await foto(page, "lms-04-video");
await page.keyboard.press("Escape");
await page.goto(page.url());
await page.getByRole("button", { name: "Publicar", exact: true }).first().click();
await page.getByText("Revisé el contenido").click();
await page.getByRole("button", { name: "Publicar", exact: true }).last().click();
await page.getByText("Curso publicado.").waitFor();
await page.getByRole("link", { name: "Vista previa" }).click();
await page.waitForURL(/\/academia\/cursos\/\d+/);
await page.locator("a[href^='/academia/lecciones/']").first().click();
const src = await page.locator("video").getAttribute("src", { timeout: 15000 });
const r = await page.request.get(base + src, { headers: { Range: "bytes=0-99" } });
ok(r.status() === 206, "el video se reproduce con descarga por partes (206)");
ok(!r.headers()["x-frame-options"], "los medios de Academia no llevan X-Frame-Options DENY");

// Panel de Nomira: catálogo con costo y cortesía
const pl = await nueva();
await pl.goto(base + "/plataforma/login");
await pl.getByLabel(/Correo/).fill("dueno@nomira.test");
await pl.getByLabel(/Contraseña/).first().fill("Panel-Nomira-2026");
await pl.getByRole("button", { name: /Entrar/ }).click();
await pl.getByRole("link", { name: "Academia" }).click();
await pl.getByRole("heading", { name: "Academia" }).waitFor();
await pl.getByLabel("Cuenta editora del catálogo").selectOption({ index: 1 });
await pl.getByRole("button", { name: "Guardar", exact: true }).first().click();
await pl.getByText("Configuración guardada.").waitFor();
const fila = pl.locator("li", { hasText: "Curso SCORM de prueba" }).first();
await fila.getByRole("button", { name: "Publicar en catálogo" }).click();
await pl.getByText("Con costo (pago único por despacho)").click();
await pl.getByLabel("Precio antes de IVA (MXN)").fill("1500");
await pl.getByRole("button", { name: "Publicar", exact: true }).click();
await pl.getByText("Catálogo actualizado.").waitFor();
ok(await pl.getByText("con costo $1,500.00 + IVA").count() >= 1, "Nomira publica el curso en el catálogo con costo");
await foto(pl, "lms-05-panel-academia");

await page.goto(base + "/academia/cursos");
await page.getByText(/Con costo · \$1,740\.00/).first().waitFor();
ok(true, "el despacho ve el curso con su precio con IVA en el catálogo");
await page.getByRole("link", { name: "Ver curso y precio" }).first().click();
await page.getByText("Comprar con tarjeta").waitFor();
ok(await page.getByText("Prefiero cotización o transferencia").count() === 1, "curso con costo: compra en línea o por cotización");
ok(await page.locator("a[aria-disabled='true']").count() >= 1, "las lecciones quedan bloqueadas hasta tener acceso");
await foto(page, "lms-06-curso-con-costo");

await pl.getByLabel("Despacho", { exact: true }).selectOption({ index: 1 });
await pl.getByLabel("Curso de cortesía").selectOption({ label: "Curso SCORM de prueba" });
await pl.getByRole("button", { name: "Dar acceso" }).click();
await pl.getByText("Acceso otorgado.").waitFor();
await page.reload();
await page.getByText("Curso SCORM de prueba").first().waitFor();
ok(await page.getByText("Comprar con tarjeta").count() === 0, "con acceso de cortesía el curso se desbloquea");
await foto(pl, "lms-07-cortesia");

// Verificación pública
const pub = await nueva();
await pub.goto(base + "/verificar?folio=NA-NOEXISTE");
await pub.getByRole("alert").waitFor();
ok(true, "un folio inexistente no se valida");
const folio = process.env.FOLIO;
if (folio) {
  await pub.goto(base + `/verificar?folio=${folio}`);
  await pub.getByText(/auténtic/).waitFor();
  ok(true, "el folio del diploma se verifica públicamente");
  await foto(pub, "lms-08-verificar");
}
ok(errores.length === 0, "sin errores en la consola: " + errores.join(" | "));
await browser.close();
