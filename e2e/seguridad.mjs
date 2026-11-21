// Seguridad: encabezados, verificación en dos pasos y cierre de sesiones (demo, datos ficticios).
// Uso: node e2e/seguridad.mjs [http://localhost:3000] [carpeta_capturas]
import { createRequire } from "node:module";
import { createHmac } from "node:crypto";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };

function totp(secreto, desfase = 0) {
  const abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of secreto.replace(/\s/g, "")) bits += abc.indexOf(c).toString(2).padStart(5, "0");
  const clave = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const paso = Buffer.alloc(8); paso.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000) + desfase));
  const h = createHmac("sha1", clave).update(paso).digest();
  const o = h[h.length - 1] & 15;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, "0");
}

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errores = [];
page.on("console", (m) => m.type() === "error" && !/favicon|401|422/.test(m.text()) && errores.push(m.text()));
page.on("pageerror", (e) => errores.push(String(e)));

const r = await page.request.get(base + "/login");
const h = r.headers();
ok(/frame-ancestors 'none'/.test(h["content-security-policy"] || "") && /connect-src 'self'/.test(h["content-security-policy"]), "la página lleva política de contenido (CSP)");
ok(h["x-frame-options"] === "DENY" && h["x-content-type-options"] === "nosniff" && !!h["permissions-policy"], "encabezados contra clickjacking y rastreo");

async function entrar(p) {
  await p.goto(base + "/login");
  await p.getByLabel("Correo electrónico").first().fill("admin@demo.local");
  await p.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
  await p.getByRole("button", { name: "Entrar" }).click();
}
await entrar(page);
await page.waitForURL((u) => !u.pathname.startsWith("/login"));
await page.goto(base + "/perfil");
await page.getByRole("button", { name: "Activar verificación en dos pasos" }).click();
await page.getByRole("dialog").getByLabel("Contraseña actual").fill("Demo-Quincena-2025");
await page.getByRole("button", { name: "Continuar" }).click();
await page.getByRole("img", { name: "Código QR para su app de autenticación" }).waitFor();
const secreto = (await page.locator("p.font-mono").first().innerText()).replace(/\s/g, "");
await page.screenshot({ path: `${dir}/seg-01-qr.png` });
await page.getByLabel("Código de 6 dígitos").fill(totp(secreto));
await page.getByRole("dialog").getByRole("button", { name: "Activar", exact: true }).click();
await page.getByText("No se volverán a mostrar").waitFor();
const respaldo = (await page.locator("ul.font-mono li").allInnerTexts());
ok(respaldo.length === 8, "se muestran 8 códigos de respaldo una sola vez");
await page.screenshot({ path: `${dir}/seg-02-respaldo.png` });
await page.getByRole("button", { name: "Ya los guardé" }).click();
await page.getByText("Activa.").waitFor();

const otra = await (await browser.newContext()).newPage();
await entrar(otra);
await otra.getByRole("heading", { name: "Verificación en dos pasos" }).waitFor();
ok(true, "con la contraseña correcta se pide el código");
await otra.getByLabel("Código", { exact: true }).fill("000000");
await otra.getByRole("button", { name: "Verificar y entrar" }).click();
await otra.getByText("Código incorrecto o ya usado.").waitFor();
await otra.getByRole("button", { name: "No tengo mi celular" }).click();
await otra.getByLabel("Código de respaldo").fill(respaldo[0]);
await otra.getByRole("button", { name: "Verificar y entrar" }).click();
await otra.waitForURL((u) => !u.pathname.startsWith("/login"));
ok(true, "se entra con un código de respaldo");
await otra.screenshot({ path: `${dir}/seg-03-dentro.png` });

await page.getByRole("button", { name: "Cerrar sesión en los demás dispositivos" }).click();
await page.getByText("Se cerró su sesión en los demás").waitFor();
await otra.goto(base + "/perfil");
await otra.waitForURL((u) => u.pathname.startsWith("/login"), { timeout: 15000 });
ok(true, "«cerrar sesión en los demás dispositivos» saca a la otra sesión");

await page.reload();
await page.getByText("Activa.").waitFor();
await page.getByRole("button", { name: "Desactivar" }).click();
await page.getByRole("dialog").getByLabel("Contraseña", { exact: true }).fill("Demo-Quincena-2025");
await page.getByLabel("Código de la app o de respaldo").fill(totp(secreto, 1));
await page.getByRole("dialog").getByRole("button", { name: "Desactivar" }).click();
await page.getByText("Verificación en dos pasos desactivada.").waitFor();
ok(true, "desactivar exige contraseña y código");
ok(errores.length === 0, "sin errores ni bloqueos de CSP en la consola: " + errores.join(" | "));
await browser.close();
