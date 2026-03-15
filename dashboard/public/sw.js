const CACHE_NAME = 'nirvaah-v1';
const ASSETS = ['/', '/index.html'];

// Install — cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch — API calls queue offline, static assets serve from cache
self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/api/') || event.request.url.includes('/webhook')) {
    event.respondWith(networkFirstWithQueue(event.request));
  } else {
    event.respondWith(
      caches.match(event.request).then((r) => r || fetch(event.request))
    );
  }
});

async function networkFirstWithQueue(request) {
  try {
    return await fetch(request.clone());
  } catch {
    // Offline — save to IndexedDB queue
    try {
      const body = await request.clone().json();
      await saveToOfflineQueue(body);
    } catch {
      // Body may not be JSON — that is fine, just queue the URL
      await saveToOfflineQueue({ url: request.url, queued: true });
    }
    return new Response(JSON.stringify({ queued: true, offline: true }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

// Background Sync — fires automatically when connectivity returns
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-records') {
    event.waitUntil(flushOfflineQueue());
  }
});

// --- IndexedDB helpers ---

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('nirvaah-offline', 1);
    req.onupgradeneeded = (e) => {
      e.target.result.createObjectStore('queue', { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

async function saveToOfflineQueue(data) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('queue', 'readwrite');
    tx.objectStore('queue').add({ data, timestamp: Date.now() });
    tx.oncomplete = resolve;
    tx.onerror = (e) => reject(e.target.error);
  });
}

async function getOfflineQueue() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('queue', 'readonly');
    const req = tx.objectStore('queue').getAll();
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

async function removeFromQueue(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('queue', 'readwrite');
    tx.objectStore('queue').delete(id);
    tx.oncomplete = resolve;
    tx.onerror = (e) => reject(e.target.error);
  });
}

async function flushOfflineQueue() {
  const queue = await getOfflineQueue();
  for (const item of queue) {
    try {
      await fetch('/api/webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item.data),
      });
      await removeFromQueue(item.id);
    } catch (e) {
      console.error('Flush failed for item', item.id, e);
    }
  }
}
