/* Service worker de Nomira: hace la app instalable y abre una pantalla amable sin conexión.
   Privacidad: NUNCA guarda respuestas de /api (expedientes, clientes, sesiones) ni páginas con datos.
   Solo guarda archivos estáticos públicos (código de la app, fuentes, imágenes del sitio). */
const VERSION = "nomira-v1";
const SIN_CONEXION = "/sin-conexion.html";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll([SIN_CONEXION, "/app/icono-192.png"])).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;  // datos: siempre a la red
  if (req.mode === "navigate") {  // páginas: siempre a la red; sin conexión, aviso
    e.respondWith(fetch(req).catch(() => caches.match(SIN_CONEXION)));
    return;
  }
  const estatico = url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/app/") || url.pathname.startsWith("/sitio/");
  if (!estatico) return;
  e.respondWith(caches.open(VERSION).then(async (c) => {
    const hit = await c.match(req);
    if (hit) return hit;
    const r = await fetch(req);
    if (r.ok) c.put(req, r.clone());
    return r;
  }));
});
