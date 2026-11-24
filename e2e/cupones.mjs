// Cupones de descuento y perfil de ejecutivo comercial, de punta a punta (datos ficticios; correo en modo de prueba).
// Uso: node e2e/cupones.mjs [base] [capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const b = await chromium.launch();
const errores = [];
const nueva = async (w = 1440, h = 950) => { const ctx = await b.newContext({ viewport: { width: w, height: h } });
  const p = await ctx.newPage(); p.on("pageerror", (e) => errores.push(String(e))); return p; };
const foto = (p, n) => p.screenshot({ path: `${dir}/${n}.png`, fullPage: true });
const entrar = async (p, email, clave) => {
  await p.goto(base + "/plataforma/login");
  await p.getByLabel(/Correo/).fill(email);
  await p.getByLabel(/Contraseña/).first().fill(clave);
  await p.getByRole("button", { name: /Entrar/ }).click();
};

// Superadministrador: crea el cupón y al ejecutivo
const pl = await nueva();
await entrar(pl, "dueno@nomira.test", "Panel-Nomira-2026");
await pl.getByRole("link", { name: "Comercial" }).click();
await pl.getByRole("navigation", { name: "Comercial" }).getByRole("link", { name: "Cupones" }).click();
await pl.getByText("Aún no hay cupones.").waitFor();
await pl.getByRole("button", { name: "+ Nuevo cupón" }).click();
await pl.getByLabel("Código").fill("black day 2026");
await pl.getByLabel("Porcentaje de descuento").fill("20");
await pl.getByLabel("Descripción interna (opcional)").fill("Campaña Black Friday (interno)");
await pl.getByRole("button", { name: "Guardar cupón" }).click();
await pl.getByText("BLACKDAY2026").waitFor();
await pl.locator("td").getByText("Activo", { exact: true }).waitFor(); ok(await pl.locator("td").getByText("BLACKDAY2026").count() === 1, "cupón BLACKDAY2026 creado y activo");
await pl.getByRole("button", { name: "Suspender" }).click();
await pl.locator("td").getByText("Suspendido", { exact: true }).waitFor();
await pl.getByRole("button", { name: "Activar" }).click();
await pl.locator("td").getByText("Activo", { exact: true }).waitFor();
ok(true, "se suspende y se vuelve a activar");
await foto(pl, "cu-01-cupones");

await pl.getByRole("link", { name: "Administradores" }).click();
await pl.getByRole("button", { name: "+ Nuevo administrador" }).click();
const dlg = pl.getByRole("dialog");
await dlg.getByLabel("Nombre").fill("Ejecutiva Ficticia");
await dlg.getByLabel("Correo").fill("ejecutiva@nomira.test");
await dlg.getByLabel("Rol").selectOption("ejecutivo_comercial");
await dlg.getByRole("button", { name: "Crear" }).click();
const clave = (await pl.locator("code").filter({ hasText: /^\S{10,}$/ }).first().innerText()).trim();
ok(clave.length >= 10, "ejecutivo comercial creado con contraseña temporal");

// Ejecutivo comercial: solo ve ventas, solicitudes, cotizaciones y cupones
const ej = await nueva();
await entrar(ej, "ejecutiva@nomira.test", clave);
await ej.waitForURL(/\/plataforma\/ventas/);
await ej.getByRole("navigation", { name: "Panel" }).getByRole("link", { name: "Cupones" }).waitFor();
for (const t of ["Ventas (CRM)", "Solicitudes", "Cotizaciones", "Cupones"]) ok(await ej.getByRole("link", { name: t, exact: true }).count() >= 1, `menú del ejecutivo: ${t}`);
for (const t of ["Clientes", "Soporte", "Correos", "Administradores", "Legal", "Suscripciones"]) ok(await ej.getByRole("link", { name: t, exact: true }).count() === 0, `sin acceso: ${t}`);
await ej.goto(base + "/plataforma/clientes");
await ej.waitForURL(/\/plataforma\/ventas/);
ok(true, "si abre una sección ajena, regresa a Ventas");
await foto(ej, "cu-02-ejecutivo");
await ej.getByRole("link", { name: "Cupones", exact: true }).click();
await ej.getByText("BLACKDAY2026").waitFor();
await ej.getByRole("button", { name: "+ Nuevo cupón" }).click();
ok(await ej.getByLabel("Tipo").isDisabled(), "el ejecutivo solo crea cupones de porcentaje");
await ej.getByLabel("Código").fill("EJEC50");
await ej.getByLabel("Porcentaje de descuento").fill("50");
await ej.getByRole("button", { name: "Guardar cupón" }).click();
await ej.getByText(/supera el máximo autorizado/).waitFor();
ok(true, "no puede pasar el descuento máximo autorizado");
await ej.getByLabel("Porcentaje de descuento").fill("10");
await ej.getByRole("button", { name: "Guardar cupón" }).click();
await ej.getByText("EJEC50").waitFor();

// El ejecutivo arma una cotización con el cupón y la envía
await ej.getByRole("navigation", { name: "Panel" }).getByRole("link", { name: "Cotizaciones" }).click();
await ej.getByRole("link", { name: "+ Nueva cotización" }).click();
await ej.getByLabel("Nombre de contacto").fill("Lic. Bruno Prospecto Ficticio");
await ej.getByLabel("Despacho o empresa").fill("Bufete Ficticio SC");
await ej.getByLabel("Correo electrónico").fill("bruno@bufete-ficticio.test");
await ej.getByRole("button", { name: "Siguiente →" }).click();
await ej.getByRole("button", { name: /^Básico/ }).click();
await ej.getByLabel("Nómina y prestaciones", { exact: true }).check();
await ej.getByText("$2,076.40").first().waitFor();
await ej.getByRole("button", { name: "Siguiente →" }).click();
await ej.getByLabel("Cupón de descuento (opcional)").fill("ejec50");
await ej.getByText(/Cupón EJEC50/).first().waitFor();
ok(await ej.getByText("$1,868.76").count() >= 1, "cupón EJEC50 aplicado en el panel: $1,790 − 10 % + IVA = $1,868.76");
await ej.getByLabel("Cupón de descuento (opcional)").fill("");
await ej.getByRole("button", { name: "Siguiente →" }).click();
await ej.getByRole("button", { name: "Guardar cotización" }).click();
await ej.getByRole("heading", { name: "Revisión y envío" }).waitFor();
await ej.getByRole("button", { name: "Enviar cotización" }).click();
await ej.getByRole("dialog").getByRole("button", { name: "Enviar cotización" }).click();
await ej.getByText(/Enviada en MODO DE PRUEBA/).waitFor();
const enlace = await ej.locator("code", { hasText: "/propuesta#" }).innerText();
ok(true, "el ejecutivo envía la cotización");

// El cliente aplica BLACKDAY2026 en su propuesta antes de aceptar
const cl = await nueva(400, 860);
await cl.goto(enlace);
await cl.getByRole("heading", { name: "Paquete Básico" }).waitFor();
await cl.getByPlaceholder("¿Tiene un código de descuento?").fill("NOEXISTE");
await cl.getByRole("button", { name: "Aplicar" }).click();
await cl.getByText(/no existe/).waitFor();
await cl.getByPlaceholder("¿Tiene un código de descuento?").fill("blackday2026");
await cl.getByRole("button", { name: "Aplicar" }).click();
await cl.getByText(/Cupón BLACKDAY2026 aplicado/).waitFor();
ok(await cl.getByText("$1,661.12").count() >= 1, "el cliente ve el total con el cupón: $1,661.12");
ok(!(await cl.content()).includes("Campaña Black Friday"), "el cliente no ve la descripción interna del cupón");
ok(await cl.getByPlaceholder("¿Tiene un código de descuento?").count() === 0, "solo un cupón por propuesta");
await foto(cl, "cu-03-propuesta-cupon");
await cl.getByRole("button", { name: "Aceptar la propuesta" }).click();
await cl.getByText("versión 2", { exact: true }).waitFor();
ok(true, "la aceptación es de la versión con el cupón");

await pl.goto(base + "/plataforma/comercial/cotizaciones");
await pl.getByRole("link", { name: /^COT-/ }).first().click();
await pl.getByText("El cliente aplicó un cupón").waitFor();
ok(await pl.getByText(/Cupón: ninguno → BLACKDAY2026/).count() === 1, "la versión 2 explica el cambio de cupón");
await foto(pl, "cu-04-historial");
ok(true, "el historial de la cotización registra el cupón aplicado por el cliente");
ok(errores.length === 0, "sin errores de JavaScript " + errores.join(" | "));
await b.close();
