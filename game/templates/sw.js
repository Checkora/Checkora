// Service Worker for Checkora
const CACHE_NAME = 'checkora-cache-v1';

// We cache the core UI assets to allow offline loading
const ASSETS_TO_CACHE = [
    '/',
    '/static/game/css/landing.css',
    '/static/game/css/board.css',
    '/static/game/js/board.js',
    '/static/game/checkora_icon_only.png',
    '/static/game/favicon.jpeg',
    // Pre-cache all chess pieces for offline availability
    ...['w','b'].flatMap(c => ['p','r','n','b','q','k'].map(t => 
        `https://images.chesscomfiles.com/chess-themes/pieces/neo/150/${c}${t}.png`
    ))
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Opened cache');
                return Promise.all(
                    ASSETS_TO_CACHE.map(url => {
                        return fetch(url, { mode: url.startsWith('http') ? 'no-cors' : 'cors' })
                            .then(response => {
                                if (response.ok || response.type === 'opaque') {
                                    return cache.put(url, response);
                                }
                            })
                            .catch(err => console.log('Failed to cache:', url, err));
                    })
                );
            })
    );
});

self.addEventListener('fetch', event => {
    // Basic cache-first strategy for static assets, network-first for everything else
    if (event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then(cachedResponse => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                
                return fetch(event.request).then(response => {
                    // Cache the new response if it's a valid static asset
                    if (!response || response.status !== 200 || response.type !== 'basic') {
                        return response;
                    }
                    
                    // Clone the response to cache it
                    const responseToCache = response.clone();
                    caches.open(CACHE_NAME)
                        .then(cache => {
                            if (event.request.url.includes('/static/') || event.request.url.includes('images.chesscomfiles.com')) {
                                cache.put(event.request, responseToCache);
                            }
                        });
                        
                    return response;
                }).catch(() => {
                    // Network error, maybe return a fallback if needed
                });
            })
    );
});
