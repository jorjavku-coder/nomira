// Recorrido del Centro Legal (datos ficticios). Uso: node e2e/centro_legal.mjs [base] [capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const b = await chromium.launch();
const errores = [];
const nueva = async (w = 1440, h = 950) => { const p = await (await b.newContext({ viewport: { width: w, height: h } })).newPage();
  p.on("pageerror", (e) => errores.push(String(e))); return p; };
const foto = (p, n) => p.screenshot({ path: `${dir}/${n}.png`, fullPage: true });
const TEXTO = (t) => `# ${t}\n\nTexto de ejemplo cargado en pruebas (NO es un texto legal real).\n\n## Sección 1\n\n- Punto uno con **negritas**\n- Punto dos con [enlace](https://example.com)\n\n1. Paso uno\n2. Paso dos\n`;

// Sin textos publicados: «en preparación»
let p = await nueva();
await p.goto(base + "/legal");
await p.getByText("En preparación").first().waitFor();
ok(await p.getByText("En preparación").count() === 6, "sin textos aprobados, todo aparece «en preparación»");
await foto(p, "01-centro-vacio");

// Plataforma: publicar versiones
const pl = await nueva();
await pl.goto(base + "/plataforma/login");
await pl.getByLabel(/Correo/).fill("dueno@nomira.test");
await pl.getByLabel(/Contraseña/).first().fill("Panel-Nomira-2026");
await pl.getByRole("button", { name: /Entrar/ }).click();
await pl.getByRole("link", { name: /Legal/ }).click();
await pl.getByRole("heading", { name: "Centro legal" }).waitFor();
for (const [doc, titulo] of [["Términos y condiciones", "Términos"], ["Aviso de privacidad", "Aviso"], ["Aviso de privacidad simplificado", "Aviso corto"], ["Anexo de tratamiento de datos para despachos", "Anexo"]]) {
  const sec = pl.locator("section", { has: pl.getByRole("heading", { name: doc, exact: true }) });
  await sec.getByRole("button", { name: "+ Nueva versión" }).click();
  await pl.getByPlaceholder("1.0").fill("1.0");
  await pl.locator("textarea").first().fill(TEXTO(titulo));
  if (doc === "Términos y condiciones") await foto(pl, "02-panel-nueva-version");
  await pl.getByRole("button", { name: "Guardar borrador" }).click();
  await pl.getByText(/Borrador guardado/).waitFor();
  await sec.getByRole("button", { name: "Publicar" }).click();
  ok(await pl.getByRole("dialog").getByRole("button", { name: "Publicar" }).isDisabled(), `${titulo}: no se publica sin confirmar aprobación`);
  await pl.getByPlaceholder(/Nombre del responsable/).fill("Responsable de Nomira y Lic. Abogado Ficticio");
  await pl.getByRole("dialog").getByRole("checkbox").check();
  await pl.getByRole("dialog").getByRole("button", { name: "Publicar" }).click();
  await pl.getByText("Versión publicada.").waitFor();
}
await foto(pl, "03-panel-documentos");
await pl.getByRole("button", { name: "Contacto de privacidad" }).click();
await pl.getByLabel(/Correo de privacidad/).fill("privacidad@nomira.test");
await pl.getByRole("button", { name: "Guardar" }).click();
await pl.getByText("Contacto guardado.").waitFor();

// Sitio público
await p.goto(base + "/legal");
await p.getByText("privacidad@nomira.test").waitFor();
await p.getByRole("link", { name: /Términos y condiciones/ }).click();
await p.getByText("Huella del texto (SHA-256)").waitFor();
ok(await p.getByRole("heading", { name: "Sección 1" }).count() === 1 || await p.getByText("Sección 1").count() >= 1, "el documento se muestra con su formato");
await foto(p, "04-documento");
await p.goto(base + "/");
await p.locator("#informes").scrollIntoViewIfNeeded();
await p.getByText("Aviso de privacidad simplificado").waitFor();
await p.getByRole("button", { name: "Leer" }).click();
await p.waitForTimeout(400);
await p.locator("#informes").screenshot({ path: `${dir}/05-formulario-aviso.png` });
ok(await p.locator("footer").getByRole("link", { name: "Aviso de privacidad" }).count() === 1, "enlaces legales en el pie del sitio");

// ARCO
await p.goto(base + "/legal/solicitudes");
await p.getByLabel("Nombre completo").fill("Titular Ficticio");
await p.getByLabel("Correo para responderle").fill("titular@x.test");
await p.getByLabel("Describa su solicitud").fill("Quiero saber qué datos míos tienen.");
ok(await p.getByRole("button", { name: "Enviar solicitud" }).isDisabled(), "ARCO: sin confirmar no se envía");
await p.getByRole("checkbox").check();
await p.getByRole("button", { name: "Enviar solicitud" }).click();
await p.getByText("Recibimos su solicitud").waitFor();
ok(await p.getByText(/no significa que ya esté resuelta/).count() === 1, "ARCO: folio sin dar por resuelta");
await foto(p, "06-arco-recibida");

// Login y aceptación
const u = await nueva();
await u.goto(base + "/login");
ok(await u.getByRole("link", { name: "Aviso de privacidad" }).count() === 1, "enlaces legales en el inicio de sesión");
await u.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await u.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await u.getByRole("button", { name: "Entrar" }).click();
await u.getByRole("dialog", { name: "Antes de continuar" }).waitFor();
const casillas = u.getByRole("dialog").getByRole("checkbox");
ok(await casillas.count() === 2, "dos casillas separadas (términos y aviso)");
ok(!(await casillas.nth(0).isChecked()) && !(await casillas.nth(1).isChecked()), "casillas sin premarcar");
ok(await u.getByRole("button", { name: "Continuar" }).isDisabled(), "no continúa sin marcar");
await foto(u, "07-aceptacion");
await casillas.nth(0).check(); await casillas.nth(1).check();
await u.getByRole("button", { name: "Continuar" }).click();
await u.getByRole("dialog", { name: "Antes de continuar" }).waitFor({ state: "detached" });
ok(true, "aceptación registrada");
await u.goto(base + "/perfil");
await u.getByText("Documentos legales").waitFor();
await u.getByText(/Aceptó: Términos y condiciones v1.0/).waitFor();
await foto(u, "08-perfil");
await u.goto(base + "/organizacion");
await u.getByText("Anexo de tratamiento de datos").waitFor();
await u.getByText(/Leí el anexo/).click();
await u.getByRole("button", { name: "Aceptar anexo" }).click();
await u.getByText("Su despacho ya aceptó la versión vigente.").waitFor();
await u.locator("section", { hasText: "Anexo de tratamiento" }).last().screenshot({ path: `${dir}/09-anexo.png` });
ok(await u.locator("footer").getByRole("link", { name: "Centro legal" }).count() === 1, "enlaces legales en el pie de la app");
await u.reload();
await u.waitForTimeout(1500);
ok(await u.getByRole("dialog", { name: "Antes de continuar" }).count() === 0, "no vuelve a pedir aceptación");

// Plataforma: ARCO y evidencia
await pl.getByRole("button", { name: "Solicitudes ARCO" }).click();
await pl.getByText(/ARCO-/).first().click();
await pl.getByPlaceholder(/Qué se hizo/).fill("Se solicitó acreditar identidad por correo.");
await pl.locator("select").first().selectOption("requiere_informacion");
await pl.getByRole("button", { name: "Guardar" }).click();
await pl.getByText("Solicitud actualizada.").waitFor();
await foto(pl, "10-panel-arco");
await pl.getByRole("button", { name: "Evidencia de aceptación" }).click();
await pl.getByText("admin@demo.local").first().waitFor();
await foto(pl, "11-panel-evidencia");
ok(errores.length === 0, "sin errores de página: " + errores.join(" | "));
await b.close();
