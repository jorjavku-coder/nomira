// Registro en línea con prueba gratuita de 7 días (hasta 3 módulos), confirmación por código, aviso de días restantes,
// bloqueo al terminar la prueba y recuperación de contraseña (correo en modo de prueba: se lee de STORAGE_DIR/correos_prueba).
// Uso: node e2e/registro.mjs [base] [capturas] [carpeta_correos]
import { createRequire } from "node:module";
import { mkdirSync, readdirSync, readFileSync } from "node:fs";
import { execSync } from "node:child_process";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
const buzon = process.argv[4] || "/tmp/alm_ev/correos_prueba";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const codigoPara = (email, asunto) => {
  const xs = readdirSync(buzon).filter((f) => f.endsWith(".json")).sort().reverse();
  for (const f of xs) {
    const j = JSON.parse(readFileSync(`${buzon}/${f}`, "utf8"));
    if (j.para.includes(email) && j.asunto.includes(asunto)) return /(\d{6})/.exec(j.asunto)[1];
  }
  throw new Error("no llegó el correo " + asunto);
};
const b = await chromium.launch();
const errores = [];
const ctx = await b.newContext({ viewport: { width: 1366, height: 900 } });
const p = await ctx.newPage();
p.on("pageerror", (e) => errores.push(String(e)));
const email = `laura${Date.now()}@despacho-prueba.test`;

await p.goto(base + "/");
await p.getByRole("link", { name: "Pruebe 7 días gratis →" }).click();
await p.waitForURL(/\/login\?registro=1/);
await p.getByRole("heading", { name: "Pruebe Nomira 7 días gratis" }).waitFor();
ok(await p.getByText("Registrarse con Google").count() === 0, "sin credenciales de Google no se muestra el botón");
await p.getByLabel("Despacho o notaría").fill("Despacho Prueba Ficticio");
await p.getByLabel("Su nombre").fill("Lic. Laura Ficticia");
await p.getByLabel("Correo electrónico").fill(email);
await p.getByLabel("Contraseña (mínimo 10)").fill("Contrasena-Segura-9");
for (const m of ["Nómina y prestaciones", "Nomira Agenda Jurídica", "Nomira Escrituración"]) await p.getByLabel(m, { exact: true }).check();
ok(await p.getByLabel("Nomira Leads", { exact: true }).isDisabled(), "no deja elegir un cuarto módulo");
ok(await p.getByRole("button", { name: "Crear mi cuenta gratis" }).isDisabled(), "pide aceptar términos y aviso");
await p.getByLabel(/Acepto los/).check();
await p.screenshot({ path: `${dir}/rg-01-registro.png`, fullPage: true });
await p.getByRole("button", { name: "Crear mi cuenta gratis" }).click();
await p.getByRole("heading", { name: "Confirme su correo" }).waitFor();
await p.getByLabel("Código de 6 dígitos").fill(codigoPara(email, "Confirme su correo"));
await p.getByRole("button", { name: "Confirmar y empezar" }).click();
await p.getByText(/Prueba gratuita:/).waitFor();
ok(await p.getByText(/le quedan 7 días/).count() === 1, "cuenta creada: aviso de 7 días de prueba");
const nav = p.getByRole("navigation", { name: "Principal" });
for (const t of ["Liquidaciones", "Agenda", "Escrituración"]) ok(await nav.getByRole("link", { name: t }).count() >= 1, `módulo elegido activo: ${t}`);
for (const t of ["Evidencia", "AFORE", "Leads"]) ok(await nav.getByRole("link", { name: t }).count() === 0, `módulo no elegido oculto: ${t}`);
await p.screenshot({ path: `${dir}/rg-02-prueba.png` });

// fin de la prueba: se bloquea sin borrar nada
execSync(`PGPASSWORD=qc psql -h localhost -U qc -d q_ev -qc "UPDATE periodos_suscripcion SET inicio = CURRENT_DATE - 10, fin = CURRENT_DATE - 3 WHERE organizacion_id = (SELECT organizacion_id FROM usuarios WHERE email = '${email}')"`);
await p.goto(base + "/liquidaciones");
await p.getByRole("heading", { name: "Gracias por probar Nomira" }).waitFor();
ok(true, "al terminar la prueba se muestra la pantalla para contratar");
await p.getByRole("button", { name: "Quiero contratar" }).click();
await p.getByText(/Un asesor de Nomira le contactará/).waitFor();
ok(true, "la solicitud de contratación llega a Ventas");
await p.screenshot({ path: `${dir}/rg-03-terminada.png` });

// recuperar contraseña
const q = await (await b.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
await q.goto(base + "/login");
await q.getByRole("button", { name: "¿Olvidó su contraseña?" }).click();
await q.getByLabel("Correo electrónico").fill(email);
await q.getByRole("button", { name: "Enviarme un código" }).click();
await q.getByText(/Si ese correo tiene cuenta/).waitFor();
await q.getByLabel("Código de 6 dígitos").fill(codigoPara(email, "Restablezca su contraseña"));
await q.getByLabel("Contraseña nueva (mínimo 10)").fill("Nueva-Contrasena-77");
await q.getByRole("button", { name: "Guardar contraseña" }).click();
await q.getByText("Listo. Ya puede entrar con su contraseña nueva.").waitFor();
await q.getByLabel("Correo electrónico").fill(email);
await q.getByLabel("Contraseña", { exact: true }).fill("Nueva-Contrasena-77");
await q.getByRole("button", { name: "Entrar", exact: true }).click();
await q.getByRole("heading", { name: "Gracias por probar Nomira" }).waitFor();
ok(true, "recuperó su contraseña y entró con la nueva");
await q.goto(base + "/login");
await q.screenshot({ path: `${dir}/rg-04-login.png` });

// el panel ve el lead con los módulos elegidos
const pl = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await pl.goto(base + "/plataforma/login");
await pl.getByLabel(/Correo/).fill("dueno@nomira.test");
await pl.getByLabel(/Contraseña/).first().fill("Panel-Nomira-2026");
await pl.getByRole("button", { name: /Entrar/ }).click();
await pl.getByRole("navigation", { name: "Panel" }).getByRole("link", { name: /^Solicitudes/ }).click();
await pl.getByText("Prueba gratis en línea").first().waitFor();
ok(await pl.getByText(/Módulos elegidos: Nómina y prestaciones, Nomira Agenda Jurídica, Nomira Escrituración/).count() >= 1, "Solicitudes muestra la prueba con los módulos elegidos");
await pl.getByRole("navigation", { name: "Panel" }).getByRole("link", { name: "Clientes" }).click();
await pl.getByText("Prueba en línea").first().waitFor();
ok(true, "Clientes distingue las cuentas de prueba en línea");
await pl.screenshot({ path: `${dir}/rg-05-panel.png` });
ok(errores.length === 0, "sin errores de JavaScript " + errores.join(" | "));
await b.close();
