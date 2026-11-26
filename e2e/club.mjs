// Club Nomira: una empresa se postula en /aliados; Nomira la convierte en aliada, sube su logo y publica un
// beneficio; un usuario del despacho lo ve, obtiene su código y muestra su credencial; el comercio la verifica.
// Uso: node e2e/club.mjs [url] [carpeta] [logo.png]   (el despacho demo debe tener un plan vigente)
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://localhost:3000";
const dir = process.argv[3] || "./capturas";
const logo = process.argv[4] || "/tmp/logo_aliado.png";
mkdirSync(dir, { recursive: true });
const ok = (c, m) => { if (!c) throw new Error("FALLÓ: " + m); console.log("ok  " + m); };
const b = await chromium.launch();
const errores = [];
const vigilar = (p) => { p.on("console", (x) => x.type() === "error" && !/favicon|401|404/.test(x.text()) && errores.push(x.text())); p.on("pageerror", (e) => errores.push(String(e))); };

// 1. la empresa se postula
const pub = await b.newPage({ viewport: { width: 1280, height: 900 } });
vigilar(pub);
await pub.goto(base + "/aliados");
await pub.getByRole("heading", { name: /Lleve su marca/ }).waitFor();
await pub.screenshot({ path: `${dir}/club-01-aliados.png`, fullPage: true });
await pub.getByLabel("Empresa").fill("Óptica Visión Ficticia");
await pub.getByLabel("Giro").fill("Salud visual");
await pub.getByLabel("Su nombre").fill("Ana Ejemplo");
await pub.getByLabel("Correo").fill("ana@optica.ejemplo.test");
await pub.getByLabel(/Qué le gustaría ofrecer/).fill("20% en lentes para despachos");
await pub.getByRole("checkbox").check();
await pub.getByRole("button", { name: "Enviar solicitud" }).click();
await pub.getByText(/Recibimos su solicitud/).waitFor();
ok(true, "la empresa se postula desde el sitio");

// 2. Nomira la convierte en aliada y publica un beneficio
const pl = await b.newPage({ viewport: { width: 1366, height: 900 } });
vigilar(pl);
await pl.goto(base + "/plataforma/login");
await pl.getByLabel(/Correo/).fill("dueno@nomira.test");
await pl.getByLabel(/Contraseña/).first().fill("Panel-Nomira-2026");
await pl.getByRole("button", { name: /Entrar/ }).click();
await pl.waitForURL(/\/plataforma(\/|$)/);
await pl.getByRole("link", { name: "Club Nomira" }).click();
await pl.getByRole("heading", { name: "Club Nomira" }).waitFor();
await pl.getByRole("button", { name: /Postulaciones/ }).click();
await pl.getByText("Óptica Visión Ficticia").waitFor();
await pl.getByRole("button", { name: "Convertir en aliado" }).click();
await pl.getByLabel("Estado del aliado").selectOption("activo");
await pl.locator('input[type="file"]').setInputFiles(logo);
await pl.getByRole("button", { name: "Guardar" }).click();
await pl.getByText("Aliado creado.").waitFor();
await pl.getByRole("button", { name: "+ Beneficio" }).click();
await pl.getByLabel("Beneficio en corto").fill("20% de descuento");
await pl.getByLabel("Título").fill("Lentes graduados y de sol");
await pl.getByLabel("Código", { exact: true }).fill("NOMIRA20");
await pl.getByLabel("Estado del beneficio").selectOption("publicado");
await pl.getByRole("checkbox", { name: /Destacado/ }).check();
await pl.getByRole("button", { name: "Guardar" }).click();
await pl.getByText("Beneficio creado.").waitFor();
await pl.locator("tr", { hasText: "Lentes graduados y de sol" }).waitFor();
ok(true, "Nomira publica el beneficio");

// 3. el despacho lo ve y lo canjea
const ctx = await b.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => localStorage.setItem("nomira:bienvenida", "1"));
const p = await ctx.newPage();
vigilar(p);
await p.goto(base + "/login");
await p.getByLabel("Correo electrónico").first().fill("admin@demo.local");
await p.getByLabel(/Contraseña/).first().fill("Demo-Quincena-2025");
await p.getByRole("button", { name: "Entrar" }).click();
await p.waitForURL(/\/(app|inicio)/);
await p.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: /Club Nomira/ }).click();
await p.getByRole("heading", { name: "Beneficios para su despacho" }).waitFor();
await p.getByText("20% de descuento").first().waitFor();
await p.screenshot({ path: `${dir}/club-02-despacho.png`, fullPage: true });
await p.getByText("Lentes graduados y de sol").click();
await p.getByRole("button", { name: "Ver mi código" }).click();
await p.getByText("NOMIRA20").waitFor();
ok(true, "el usuario obtiene su código");
await p.screenshot({ path: `${dir}/club-03-codigo.png` });
await p.getByRole("dialog").getByRole("button", { name: "Cerrar" }).first().click();
await p.getByRole("button", { name: /Mi credencial/ }).click();
const codigo = (await p.locator(".font-mono").filter({ hasText: /^NM-/ }).first().innerText()).trim();
ok(/^NM-[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(codigo), "credencial digital " + codigo);
await p.screenshot({ path: `${dir}/club-04-credencial.png` });

// 4. el comercio verifica la credencial
const v = await b.newPage({ viewport: { width: 390, height: 760 } });
await v.goto(`${base}/club/verificar/${codigo}`);
await v.getByText("Credencial vigente").waitFor();
await v.screenshot({ path: `${dir}/club-05-verificar.png` });
ok(true, "el comercio verifica la credencial");

// 5. métricas para el aliado (solo conteos)
await pl.reload();
await pl.getByText("Lentes graduados y de sol").waitFor();
const fila = pl.locator("tr", { hasText: "Lentes graduados y de sol" });
ok((await fila.locator("td.tabular-nums").allInnerTexts()).join(",") === "1,1,1", "métricas: 1 vista, 1 canje, 1 despacho");
await pl.screenshot({ path: `${dir}/club-06-panel.png`, fullPage: true });
ok(!errores.length, "sin errores en consola" + (errores.length ? ": " + errores.join(" | ") : ""));
await b.close();
