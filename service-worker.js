const CACHE_NAME = "walkwithme-v1";

const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/icon-192.png",
  "/icon-512.png",
  "/manifest.json",
  "/ar3.html",
  "/nav_arrow.png"
];

// ------------------------------------------------------------
// INSTALL – Cache ONLY static frontend files (GitHub Pages)
// ------------------------------------------------------------
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

// ------------------------------------------------------------
// ACTIVATE – Remove old caches
// ------------------------------------------------------------
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ------------------------------------------------------------
// FETCH INTERCEPTOR
// ------------------------------------------------------------
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // ⭐ 1. If request goes to ANY other domain → DO NOT CACHE
  if (url.origin !== self.location.origin) {
    // backend Fly.io API, Valhalla DigitalOcean server, Photon, Nominatim, etc.
    return event.respondWith(fetch(event.request));
  }

  // ⭐ 2. If it's a dynamic local path → DO NOT CACHE
  const dynamicPaths = [
    "/route",
    "/trails",
    "/trail_route",
    "/reverse_geocode",
    "/vision",
    "/export_gpx"
  ];

  if (dynamicPaths.some(path => url.pathname.startsWith(path))) {
    return event.respondWith(fetch(event.request));
  }

  // ⭐ 3. Cache-first strategy for static assets only
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});
