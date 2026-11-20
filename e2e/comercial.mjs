// Módulo Comercial de punta a punta (datos ficticios; correo en modo de prueba, sin cobros).
// Uso: node e2e/comercial.mjs [base] [capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const b = await chromium.launch();
const errores = [];
const nueva = async (w = 1440, h = 950) => { const ctx = await b.newContext({ viewport: { width: w, height: h }, acceptDownloads: true });
  const p = await ctx.newPage(); p.on("pageerror", (e) => errores.push(String(e))); return p; };
const foto = (p, n) => p.screenshot({ path: `${dir}/${n}.png`, fullPage: true });

const pl = await nueva();
await pl.goto(base + "/plataforma/login");
await pl.getByLabel(/Correo/).fill("dueno@nomira.test");
await pl.getByLabel(/Contraseña/).first().fill("Panel-Nomira-2026");
await pl.getByRole("button", { name: /Entrar/ }).click();
await pl.getByRole("link", { name: "Comercial" }).click();
await pl.getByText("Aún no hay cotizaciones.").waitFor();
ok(true, "superadministrador ve Comercial; sin datos no se inventan cifras");

// Configuración
await pl.getByRole("link", { name: "Configuración comercial" }).click();
await pl.getByRole("heading", { name: "Configuración comercial" }).waitFor();
await pl.getByLabel("Correo de ventas").fill("ventas@nomira.test");
await pl.getByLabel("Nota al pie del PDF (máx. 150)").fill("Nomira · Cada prestación, en claro");
await pl.getByLabel("Transferencia SPEI").check();
await pl.getByRole("button", { name: "Guardar configuración" }).click();
await pl.getByText(/faltan banco, titular o CLABE/).waitFor();
ok(true, "SPEI sin datos bancarios queda deshabilitado y se avisa");
await pl.getByLabel("Banco").fill("BANCO FICTICIO DE PRUEBAS");
await pl.getByLabel("Titular").first().fill("TITULAR FICTICIO");
await pl.getByLabel("CLABE (18 dígitos)").fill("000000000000000000");
await pl.getByLabel(/Mostrar solo «Paquetes desde/).check();
await pl.getByRole("button", { name: "Guardar configuración" }).click();
await pl.getByText(/Configuración guardada/).waitFor();
ok(await pl.getByText("Stripe conectado en MODO DE PRUEBA.").count() === 0, "sin llave de Stripe no se ofrece pago con tarjeta");
await foto(pl, "cm-01-configuracion");

// Paquetes
await pl.getByRole("link", { name: "Paquetes y precios" }).click();
await pl.getByRole("heading", { name: "Premium" }).waitFor();
ok(await pl.getByText("$1,790.00").count() >= 1 && await pl.getByText("$5,990.00").count() >= 1, "paquetes iniciales con sus precios");
await foto(pl, "cm-02-paquetes");

// Constructor
await pl.getByRole("link", { name: "Cotizaciones" }).click();
await pl.getByRole("link", { name: "+ Nueva cotización" }).click();
await pl.getByLabel("Nombre de contacto").fill("Lic. Ana Prospecto Ficticia");
await pl.getByLabel("Despacho o empresa").fill("Despacho Ficticio de Pruebas SC");
await pl.getByLabel("Correo electrónico").fill("ana@despacho-ficticio.test");
await pl.getByLabel(/Notas internas/).fill("NOTA-INTERNA-NO-VISIBLE");
await pl.getByRole("button", { name: "Siguiente →" }).click();
await pl.getByRole("button", { name: /^Medio/ }).click();
for (const m of ["Nómina y prestaciones", "Nomira Evidencia", "Nomira AFORE", "Nomira Leads"]) await pl.getByLabel(m, { exact: true }).check();
await pl.getByLabel("Usuarios internos adicionales").fill("2");
await pl.getByText("$5,124.88").waitFor(); // (3490 + 690 + 238) × 1.16 = 5124.88
ok(true, "el servidor recalcula: 4 módulos (uno adicional) y 2 usuarios");
await foto(pl, "cm-03-constructor");
await pl.getByRole("button", { name: "Siguiente →" }).click();
await pl.getByLabel("Valor del descuento").fill("10");
await pl.getByLabel("Capacitación").check();
await pl.getByLabel("Precio de Capacitación").fill("1500");
await pl.getByText("Todo descuento requiere un motivo").waitFor();
ok(true, "el descuento sin motivo se rechaza");
await pl.getByLabel("Motivo del descuento").fill("Cliente fundador aprobado");
await pl.getByLabel("Condiciones de pago").fill("Pago anticipado del primer mes.");
await pl.getByText("$6,178.39").waitFor(); // (4418 + 1500) × 0.9 × 1.16
await pl.getByRole("button", { name: "Siguiente →" }).click();
await pl.getByRole("button", { name: "Guardar cotización" }).click();
await pl.getByRole("heading", { name: "Revisión y envío" }).waitFor();
const folio = (await pl.locator("h1").first().innerText()).split(" ")[0];
ok(/^COT-\d{4}-\d{4}/.test(folio), "cotización guardada en borrador con folio " + folio);
await pl.locator('iframe[title="Vista previa del PDF"]').waitFor();
await pl.getByText("Correo en modo de prueba").waitFor();
await pl.getByLabel("Mensaje de presentación").fill("Hola Ana, le compartimos la propuesta que platicamos.");
await pl.getByRole("button", { name: "Actualizar vista previa" }).click();
await pl.waitForTimeout(600);
ok((await pl.locator('iframe[title="Vista previa del correo"]').getAttribute("srcdoc")).includes("Hola Ana, le compartimos"), "vista previa del correo con el mensaje editado");
await foto(pl, "cm-04-revision");
await pl.getByRole("button", { name: "Enviar cotización" }).click();
await pl.getByRole("dialog").getByRole("button", { name: "Enviar cotización" }).click();
await pl.getByText(/Enviada en MODO DE PRUEBA/).waitFor();
ok(true, "envío confirmado explícitamente (modo de prueba: no salió ningún correo)");
const enlace = await pl.locator("code", { hasText: "/propuesta#" }).innerText();

// Cliente
const cl = await nueva(400, 860);
await cl.goto(enlace);
await cl.getByRole("heading", { name: "Paquete Medio" }).waitFor();
const html = await cl.content();
ok(!html.includes("NOTA-INTERNA-NO-VISIBLE") && !html.includes("Cliente fundador aprobado"), "el cliente no ve notas internas ni el motivo del descuento");
ok(await cl.getByText("$6,178.39").count() >= 1, "el cliente ve el total calculado");
await foto(cl, "cm-05-propuesta-movil");
await cl.getByRole("button", { name: "Solicitar ajustes" }).click();
await cl.getByLabel("¿Qué le gustaría ajustar?").fill("¿Podemos empezar con 10 usuarios?");
await cl.getByRole("button", { name: "Enviar solicitud" }).click();
await cl.getByText(/Recibimos su solicitud/).waitFor();
await cl.getByRole("button", { name: "Aceptar la propuesta" }).click();
ok(await cl.getByRole("button", { name: "Registrar mi aceptación" }).isDisabled(), "la aceptación exige nombre y casilla sin marcar");
await cl.getByLabel("Su nombre completo").fill("Ana Prospecto Ficticia");
await cl.getByLabel(/Revisé la propuesta completa/).check();
await cl.getByRole("button", { name: "Registrar mi aceptación" }).click();
await cl.getByText(/Aceptación registrada/).waitFor();
await cl.getByRole("button", { name: "Pagaré por este medio" }).click();
await cl.getByText(/se confirmará cuando el equipo de Nomira verifique/).waitFor();
ok(true, "aviso de transferencia: no se marca pagada sola");
await foto(cl, "cm-06-propuesta-aceptada");

// Panel: pago y asignación
await pl.reload();
await pl.getByText("Pendiente de pago").first().waitFor();
ok(await pl.getByText("El cliente pidió ajustes").count() === 1 && await pl.getByText("El cliente registró su aceptación").count() === 1, "historial con ajuste y aceptación");
await pl.getByRole("button", { name: "Registrar pago recibido" }).click();
const dlg = pl.getByRole("dialog");
await dlg.getByLabel("Monto (MXN)").fill("6178.39");
await dlg.getByLabel("Referencia").fill("SPEI-PRUEBA-001");
await dlg.getByRole("button", { name: "Confirmar recepción" }).click();
await pl.getByText("Pago registrado.").waitFor();
await pl.getByRole("button", { name: "Asignar al despacho" }).click();
await pl.getByRole("dialog").getByLabel("Despacho (organización)").selectOption({ index: 1 });
await pl.getByRole("dialog").getByRole("button", { name: "Asignar" }).click();
await pl.getByText(/Paquete asignado/).waitFor();
await pl.getByText(/Asignada a/).first().waitFor();
ok(true, "cotización pagada asignada al despacho");
await foto(pl, "cm-07-detalle");
await pl.getByRole("navigation", { name: "Comercial" }).getByRole("link", { name: "Resumen" }).click();
await pl.getByText("Cobrado (pagos confirmados)").waitFor();
ok(await pl.getByText("$6,178.39").count() >= 2, "el resumen muestra lo aceptado y cobrado");
await foto(pl, "cm-08-resumen");

// Sitio público
const s = await nueva();
await s.goto(base + "/");
await s.getByText("Paquetes desde $1,790 MXN + IVA").waitFor();
ok(true, "el sitio muestra solo «Paquetes desde» (sin desglose)");
ok(errores.length === 0, "sin errores de JavaScript " + errores.join(" | "));
await b.close();
