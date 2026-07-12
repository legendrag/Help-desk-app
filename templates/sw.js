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

    const options = {
        body: payload.body || payload.message || "You have a new notification",
        icon: payload.icon || "/static/images/deskplus-icon.svg",
        data: payload.data || { url: "/" },
        badge: "/static/images/deskplus-icon.svg",
        vibrate: [100, 50, 100],
    };

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(windowClients => {
                const targetUrl = payload.data ? payload.data.url : null;
                
                // Check if any window is visible and on the exact target URL
                let isViewingTarget = false;
                for (let client of windowClients) {
                    try {
                        const clientPath = new URL(client.url).pathname;
                        const normClient = clientPath.replace(/\/+$/, '');
                        const normTarget = targetUrl ? targetUrl.replace(/\/+$/, '') : null;
                        
                        // If the tab is visible (even if not strictly focused) and on the same ticket page
                        if (client.visibilityState === 'visible' && normTarget && normClient === normTarget) {
                            isViewingTarget = true;
                            break;
                        }
                    } catch (e) {
                        console.error("URL parse error in sw:", e);
                    }
                }

                // If they are actively looking at the page, don't show the OS notification
                if (isViewingTarget) {
                    console.log("[SW] Suppressing push notification because user is viewing target");
                    return;
                }

                const displayTitle = payload.title || payload.head || "DeskPlus Notification";
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
