// Aviso de privacidad del despacho en Nomira Leads (datos ficticios). Uso: node e2e/aviso_despacho.mjs [base] [capturas]
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

const p = await nueva();
await p.goto(base + "/login");
await p.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await p.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await p.getByRole("button", { name: "Entrar" }).click();
await p.getByRole("link", { name: "Prospectos", exact: true }).click();
await p.getByText("Falta el aviso de privacidad de su despacho.").waitFor();
ok(true, "Leads avisa al despacho que falta su aviso de privacidad");
await foto(p, "av-01-falta-aviso");
await p.getByRole("link", { name: "Agregue el enlace en Configuración" }).click();
await p.getByRole("heading", { name: "Aviso de privacidad del despacho" }).waitFor();
const enlace = await p.locator("section", { hasText: "Formulario de contacto" }).locator("code").first().innerText();

// Formulario público sin aviso
const pub = await nueva(390, 844);
await pub.goto(enlace);
await pub.getByText(/aún no ha publicado aquí su aviso de privacidad/).waitFor();
ok(true, "el formulario dice con honestidad que el despacho no ha publicado su aviso");

// Guardar enlace inválido y luego válido
const campo = p.getByLabel("Dirección de su aviso de privacidad (https://…)");
await campo.fill("http://despacho.test/aviso");
await p.getByRole("button", { name: "Guardar enlace" }).click();
await p.getByText(/debe ser una dirección completa que empiece con https/).waitFor();
ok(true, "rechaza un enlace que no es https");
await campo.fill("https://www.despacho-ficticio.mx/aviso-de-privacidad");
await p.getByRole("button", { name: "Guardar enlace" }).click();
await p.getByText("Enlace del aviso guardado.").waitFor();
await p.waitForTimeout(400);
ok(await p.getByText("Falta el aviso de privacidad de su despacho.").count() === 0, "al guardar, desaparece el aviso de que falta");
await foto(p, "av-02-configuracion");

await pub.reload();
const liga = pub.getByRole("link", { name: "aviso de privacidad" });
await liga.waitFor();
ok(await liga.getAttribute("href") === "https://www.despacho-ficticio.mx/aviso-de-privacidad", "el formulario enlaza al aviso propio del despacho");
ok((await liga.getAttribute("rel")).includes("noopener"), "el enlace externo abre sin dar acceso a la página");
await foto(pub, "av-03-formulario");

// Centro Legal: los dos documentos nuevos
const lg = await nueva();
await lg.goto(base + "/legal");
await lg.getByText("Uso aceptable y seguridad").waitFor();
ok(await lg.getByText("Inteligencia artificial e integraciones").count() >= 1, "Centro Legal lista Uso aceptable e IA e integraciones");
await lg.getByText("Inteligencia artificial e integraciones").click();
await lg.getByText(/en preparación/i).first().waitFor();
ok(true, "sin texto aprobado, el anexo de IA aparece «en preparación» y no se inventa contenido");
await foto(lg, "av-04-anexo-ia");

ok(errores.length === 0, "sin errores de JavaScript " + errores.join(" | "));
await b.close();
