// Módulos de su despacho: todos con interruptor; encender uno sin contratar muestra su precio + IVA.
// Uso: node e2e/modulos.mjs [base] [capturas]
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] || "http://127.0.0.1:3313", dir = process.argv[3] || "/tmp/cap_modulos";
mkdirSync(dir, { recursive: true });
let fallas = 0;
const ok = (c, t) => { console.log(`${c ? "ok " : "FALLA"} ${t}`); if (!c) fallas++; };
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1366, height: 900 } });
const errores = []; p.on("pageerror", (e) => errores.push(e.message));
await p.goto(base + "/login");
await p.getByLabel(/correo/i).fill("admin@demo.local"); await p.getByLabel(/contraseña/i).fill("Demo-Quincena-2025");
await p.getByRole("button", { name: /^entrar$/i }).click(); await p.waitForURL(/\/inicio/);
await p.getByRole("link", { name: "Agregar módulos" }).click();
await p.getByText("Módulos de su despacho").waitFor();
const apagados = p.getByRole("switch", { name: /^Encender / });
ok(await p.getByRole("switch").count() >= 9, "todos los módulos con su interruptor");
ok(await apagados.count() >= 1, "hay módulos apagados");
await p.getByRole("switch", { name: "Encender Nomira Academia" }).click().catch(async () => { await apagados.first().click(); });
await p.getByRole("dialog").waitFor();
ok(await p.getByRole("dialog").getByText("Total al mes").count() === 1, "precio con IVA en la ventana");
await p.screenshot({ path: dir + "/modulos-precio.png" });
await p.getByRole("dialog").getByRole("button", { name: "Cerrar" }).click();
ok(!errores.length, "sin errores de JavaScript" + (errores.length ? ": " + errores.join(" | ") : ""));
await b.close();
process.exit(fallas ? 1 : 0);
