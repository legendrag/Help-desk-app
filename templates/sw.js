self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', event => {
    let payload = {
        title: "DeskPlus Notification",
        body: "You have a new notification",
        icon: "/static/images/deskplus-icon.svg",
        data: { url: "/" }
    };

    if (event.data) {
        console.log("[SW] Received raw event data text:", event.data.text());
        try {
            payload = event.data.json();
            if (typeof payload === 'string') {
                try {
                    payload = JSON.parse(payload);
                } catch (innerErr) {
                    console.warn("[SW] Failed to parse inner JSON string:", innerErr);
                }
            }
            console.log("[SW] Successfully parsed JSON payload:", payload);
        } catch (e) {
            console.warn("[SW] Failed to parse JSON, using text as body:", e);
            payload.body = event.data.text();
        }
    } else {
        console.warn("[SW] Received push event with no data.");
    }

    const displayTitle = payload.title || payload.head || "DeskPlus Notification";
    const targetUrl = (payload.data && payload.data.url) ? payload.data.url : "/";
    const options = {
        body: payload.body || payload.message || "You have a new notification",
        icon: payload.icon || "/static/images/deskplus-icon.svg",
        data: payload.data || { url: "/" },
        badge: "/static/images/deskplus-icon.svg",
        vibrate: [100, 50, 100],
        // Collapse duplicate pushes for the same event into one OS toast
        tag: `deskplus:${displayTitle}:${targetUrl}`,
        renotify: false,
    };

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(windowClients => {
                // Suppress OS toast only when the recipient is visibly in that ticket chat.
                // Everywhere else (list, other ticket, background, other app) → show toast.
                const normTarget = String(targetUrl || "/").replace(/\/+$/, '') || "/";
                const isInThatChat = windowClients.some(client => {
                    if (client.visibilityState !== 'visible') return false;
                    try {
                        const path = new URL(client.url).pathname.replace(/\/+$/, '') || "/";
                        return path === normTarget;
                    } catch (e) {
                        console.error("URL parse error in sw:", e);
                        return false;
                    }
                });

                if (isInThatChat) {
                    console.log("[SW] Suppressing push notification because user is in that chat");
                    return;
                }

                console.log("[SW] Showing notification:", displayTitle);
                return self.registration.showNotification(displayTitle, options);
            })
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();

    const urlToOpen = event.notification.data.url || "/";

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
            for (let client of windowClients) {
                if (client.url === urlToOpen && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});
