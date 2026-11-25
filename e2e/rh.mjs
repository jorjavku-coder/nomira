// Recursos humanos: ficha con vacaciones LFT, acceso al portal (enlace + NIP), el empleado confirma un aviso, pide vacaciones
// y sube un documento; RH autoriza, acepta el documento, arma la quincena, la cierra y el empleado descarga su recibo.
// Uso: node e2e/rh.mjs [base] [capturas]
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const pdf = `${dir}/ine-prueba.pdf`;
writeFileSync(pdf, "%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true });
await ctx.addInitScript(() => localStorage.setItem("nomira:bienvenida", "1"));
const p = await ctx.newPage();
const errores = [];
p.on("pageerror", (e) => errores.push(String(e)));
await p.goto(base + "/login");
await p.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await p.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await p.getByRole("button", { name: "Entrar", exact: true }).click();
await p.waitForURL(/\/(app|inicio)/);
await p.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: /Recursos humanos/ }).click();
await p.getByRole("heading", { name: "Personal y nómina" }).waitFor();
await p.getByRole("link", { name: "Laura Ejemplo Méndez" }).waitFor();
ok(await p.getByRole("tab", { name: /Solicitudes/ }).innerText().then((t) => t.includes("2")), "2 solicitudes por autorizar en la pestaña");
await p.screenshot({ path: `${dir}/rh-01-empleados.png`, fullPage: true });
await p.getByRole("link", { name: "Laura Ejemplo Méndez" }).click();
await p.getByText("días disponibles").waitFor();
ok(await p.getByText(/Le corresponden 22 por su 6\.º año/).count() === 1, "vacaciones LFT: 22 días al sexto año");
await p.getByRole("button", { name: "Dar acceso al portal" }).click();
await p.getByRole("button", { name: "Generar acceso" }).click();
const txt = await p.getByRole("dialog").locator("p.break-all").innerText();
const url = txt.match(/https?:\S+/)[0], nip = txt.match(/NIP:\s*(\d{6})/)[1];
ok(url.includes("/mi-rh/") && nip.length === 6, "genera enlace y NIP");
await p.screenshot({ path: `${dir}/rh-02-acceso.png` });
await p.getByRole("button", { name: "Listo" }).click();

// el empleado, desde el celular
const cel = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
const m = await cel.newPage();
m.on("pageerror", (e) => errores.push(String(e)));
await m.goto(url.replace(/^https?:\/\/[^/]+/, base));
await m.getByText("Hola, Laura").waitFor();
await m.getByLabel(/NIP/).fill("000000" === nip ? "111111" : "000000");
await m.getByRole("button", { name: "Entrar" }).click();
await m.getByText("NIP incorrecto.").waitFor();
await m.getByLabel(/NIP/).fill(nip);
await m.getByRole("button", { name: "Entrar" }).click();
await m.getByText("Pago de aguinaldo").waitFor();
await m.screenshot({ path: `${dir}/rh-03-portal-avisos.png`, fullPage: true });
await m.getByRole("button", { name: "Enterado" }).click();
await m.getByText("✓ Confirmó que lo leyó").waitFor();
ok(true, "el empleado confirma que leyó el aviso");
await m.getByRole("tab", { name: "Vacaciones" }).click();
await m.getByText("días de vacaciones disponibles").waitFor();
const hoy = new Date(); const lunes = new Date(hoy); lunes.setDate(hoy.getDate() + ((8 - hoy.getDay()) % 7 || 7) + 21);
const iso = (d) => d.toLocaleDateString("en-CA");
const mar = new Date(lunes); mar.setDate(lunes.getDate() + 1);
await m.getByLabel("Desde").fill(iso(lunes));
await m.getByLabel("Hasta").fill(iso(mar));
await m.getByRole("button", { name: "Enviar solicitud" }).click();
await m.getByText("Solicitud enviada a Recursos Humanos.").waitFor();
ok(true, "pide 2 días de vacaciones");
await m.getByRole("tab", { name: /Documentos/ }).click();
await m.getByLabel("Foto o PDF").setInputFiles(pdf);
await m.getByRole("button", { name: "Enviar" }).click();
await m.getByText(/Recursos Humanos lo revisará/).waitFor();
ok(true, "sube un documento desde el portal");
await m.screenshot({ path: `${dir}/rh-04-portal-documentos.png`, fullPage: true });

// RH autoriza y revisa
await p.reload();
await p.getByText(/pidió 7 por autorizar/).waitFor();  // 5 de la demo + 2 nuevos
await p.getByRole("button", { name: "Autorizar" }).first().click();
await p.getByText("Autorizada.").waitFor();
await p.getByRole("button", { name: "Aceptar" }).first().click();
await p.getByText("Documento aceptado.").waitFor();
ok(true, "RH autoriza y acepta el documento");
// aviso: ya se ve leído
await p.goto(base + "/rh?tab=avisos");
await p.getByRole("button", { name: /Leído por 1 de 5/ }).waitFor();
ok(true, "acuse de lectura visible para RH");
// nómina
await p.getByRole("tab", { name: "Nómina" }).click();
await p.getByRole("button", { name: "+ Nuevo periodo" }).click();
const dlg = p.getByRole("dialog");
await dlg.getByLabel("Empresa").selectOption({ index: 0 });
await dlg.getByLabel("Del", { exact: true }).fill(iso(lunes)); const fin = new Date(lunes); fin.setDate(lunes.getDate() + 14);
await dlg.getByLabel("Al", { exact: true }).fill(iso(fin)); await dlg.getByLabel("Fecha de pago").fill(iso(fin));
await dlg.getByRole("button", { name: "Armar nómina" }).click();
await p.waitForURL(/\/rh\/nomina\/\d+/);
await p.getByText(/Prima vacacional/).first().waitFor();
ok(true, "la quincena trae la prima vacacional de las vacaciones autorizadas");
await p.screenshot({ path: `${dir}/rh-05-nomina.png`, fullPage: true });
await p.getByRole("button", { name: "Cerrar y publicar recibos" }).click();
await p.getByText(/los empleados ya ven su recibo/).waitFor();
await m.reload();
await m.getByRole("tab", { name: "Recibos" }).click();
const [desc] = await Promise.all([m.waitForEvent("download"), m.getByRole("button", { name: "PDF" }).first().click()]);
ok(desc.suggestedFilename().startsWith("recibo-"), "el empleado descarga su recibo");
ok(!errores.length, "sin errores de JavaScript " + errores.join(" "));
await b.close();
