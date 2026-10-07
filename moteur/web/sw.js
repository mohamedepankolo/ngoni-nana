// Garde juste la coquille de l'app en cache (fonctionne hors-ligne pour
// l'affichage) : parler avec N'GONI NANA a toujours besoin du reseau pour
// joindre le serveur (ASR, moteur, TTS), ce service worker ne change rien a ca.
const CACHE = "ngoni-nana-v1";
const FICHIERS = ["/web/", "/web/index.html", "/web/manifest.json",
                  "/web/icon-192.png", "/web/icon-512.png"];

self.addEventListener("install", (evt) => {
  evt.waitUntil(caches.open(CACHE).then((c) => c.addAll(FICHIERS)));
  self.skipWaiting();
});

self.addEventListener("activate", (evt) => {
  evt.waitUntil(
    caches.keys().then((cles) => Promise.all(cles.filter((c) => c !== CACHE).map((c) => caches.delete(c))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (evt) => {
  if (evt.request.method !== "GET") return;
  evt.respondWith(
    caches.match(evt.request).then((reponse) => reponse || fetch(evt.request))
  );
});
