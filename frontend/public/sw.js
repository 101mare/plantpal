// PlantPal service worker.
// App-shell precache for offline launch; NetworkOnly for /api + /auth so private
// API/auth responses are NEVER cached (consolidation decision K7).
const CACHE = "plantpal-shell-v4";
const SHELL = [
  "/",
  "/index.html",
  "/backgrounds/vines.webp",
  "/backgrounds/vines-light.webp", // N20: light-theme bg must be offline-available too
  "/wordmark.png",
  "/placeholder.png",
  "/manifest.webmanifest",
  "/fonts/press-start-2p-latin.woff2",
  "/fonts/vt323-latin.woff2",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return; // never touch mutations
  // K7: private API/auth traffic must bypass the cache entirely.
  if (url.pathname.startsWith("/api") || url.pathname.startsWith("/auth")) return;
  // HTML navigations: network-first so a fresh deploy's shell (and its new JS bundle) is
  // picked up when online; fall back to the cached shell offline (A11Y-07: no stale pinning).
  if (event.request.mode === "navigate") {
    const fromCache = () => caches.match(event.request).then((hit) => hit || caches.match("/"));
    const net = fetch(event.request).then((resp) => {
      const isHtml = (resp.headers.get("Content-Type") || "").includes("text/html");
      if (resp.ok && url.origin === self.location.origin && isHtml) {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put("/", copy));
      }
      return resp;
    });
    // Network-first, but don't hang on a flaky mobile connection: if the network hasn't answered
    // within 3s, serve the cached shell so the PWA still launches instantly (the put() above keeps
    // revalidating in the background). On a hard network error, also fall back to cache.
    const timeout = new Promise((resolve) => setTimeout(() => resolve(fromCache()), 3000));
    event.respondWith(Promise.race([net, timeout]).catch(fromCache));
    return;
  }
  // Other same-origin static assets: cache-first, fall back to network, then to "/".
  event.respondWith(
    caches.match(event.request).then(
      (hit) =>
        hit ||
        fetch(event.request)
          .then((resp) => {
            if (resp.ok && url.origin === self.location.origin) {
              const copy = resp.clone();
              caches.open(CACHE).then((c) => c.put(event.request, copy));
            }
            return resp;
          })
          .catch(() => caches.match("/")),
    ),
  );
});
