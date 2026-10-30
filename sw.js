// Страница игры на случай, когда нет интернета. Сначала всегда сеть, чтобы обновления доходили сразу;
// записи голоса кладёт в свой кеш сама игра (кнопка «Скачать голос»), их здесь нет.
const PAGE = 'leon-page-1';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  if (e.request.mode !== 'navigate') return;
  e.respondWith(fetch(e.request).then(r => {
    const copy = r.clone();
    caches.open(PAGE).then(c => c.put('index.html', copy));
    return r;
  }).catch(() => caches.open(PAGE).then(c => c.match('index.html'))));
});
