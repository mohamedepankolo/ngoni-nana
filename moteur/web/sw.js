// Garde juste la coquille de l'app en cache (fonctionne hors-ligne pour
// l'affichage) : parler avec N'GONI NANA a toujours besoin du reseau pour
// joindre le serveur (ASR, moteur, TTS), ce service worker ne change rien a ca.
// v2 : bascule la coquille HTML en strategie "reseau d'abord" (voir plus bas)
// pour qu'une correction publiee atteigne une utilisatrice qui a deja
// installe l'app des sa prochaine ouverture avec reseau, plutot que de
// rester bloquee sur une version en cache jusqu'a desinstallation manuelle.
const CACHE = "ngoni-nana-v2";
const FICHIERS = ["/web/", "/web/index.html", "/web/manifest.json",
                  "/web/icon-192.png", "/web/icon-512.png",
                  "/web/assets/erreur.wav"];

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
  const estCoquille = evt.request.mode === "navigate" || evt.request.url.endsWith("/index.html");
  if (estCoquille) {
    // Reseau d'abord : l'utilisatrice a presque toujours du reseau pour
    // parler avec N'GONI NANA de toute facon (ASR/TTS le demandent), donc ca
    // ne coute rien de l'essayer avant le cache, et ca garantit la derniere
    // version du code plutot qu'une ancienne figee a l'installation.
    evt.respondWith(
      fetch(evt.request)
        .then((reponse) => {
          caches.open(CACHE).then((c) => c.put(evt.request, reponse.clone()));
          return reponse;
        })
        .catch(() => caches.match(evt.request))
    );
    return;
  }
  evt.respondWith(
    caches.match(evt.request).then((reponse) => reponse || fetch(evt.request))
  );
});
