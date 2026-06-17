const CACHE_NAME = "weat-v1";
const SHELL = ["/", "/index.html"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request).catch(() =>
        caches.match("/index.html").then(
          (cached) =>
            cached ||
            new Response("<h1>网络不可用</h1><p>请检查网络连接后刷新。</p>", {
              headers: { "Content-Type": "text/html; charset=utf-8" },
            })
        )
      )
    );
  }
});
