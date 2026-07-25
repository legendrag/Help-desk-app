self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', event => {
    let payload = {
        title: "mlameh ticket Notification",
        body: "You have a new notification",
        icon: "/static/images/mlameh-icon-fg.png",
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

    const displayTitle = payload.title || payload.head || "mlameh ticket Notification";
    const targetUrl = (payload.data && payload.data.url) ? payload.data.url : "/";
    const options = {
        body: payload.body || payload.message || "You have a new notification",
        icon: payload.icon || "/static/images/mlameh-icon-fg.png",
        data: payload.data || { url: "/" },
        badge: "/static/images/mlameh-icon-fg.png",
        vibrate: [100, 50, 100],
        // Collapse duplicate pushes for the same event into one OS toast
        tag: `mlameh:${displayTitle}:${targetUrl}`,
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

    const rawUrl = (event.notification.data && event.notification.data.url) || "/";
    // Push payloads use relative paths ("/tickets/1/"); client.url is absolute.
    const urlToOpen = new URL(rawUrl, self.location.origin).href;
    const targetPath = new URL(urlToOpen).pathname.replace(/\/+$/, "") || "/";

    event.waitUntil((async () => {
        const windowClients = await clients.matchAll({
            type: "window",
            includeUncontrolled: true,
        });

        // Reuse any already-open same-origin tab/window (installed PWA or browser),
        // then navigate it to the notification target instead of spawning a duplicate.
        for (const client of windowClients) {
            let clientUrl;
            try {
                clientUrl = new URL(client.url);
            } catch (e) {
                continue;
            }
            if (clientUrl.origin !== self.location.origin) {
                continue;
            }

            if ("focus" in client) {
                await client.focus();
            }

            const clientPath = clientUrl.pathname.replace(/\/+$/, "") || "/";
            if (clientPath !== targetPath && "navigate" in client) {
                try {
                    await client.navigate(urlToOpen);
                } catch (e) {
                    console.warn("[SW] Failed to navigate existing client:", e);
                }
            }
            return;
        }

        if (clients.openWindow) {
            await clients.openWindow(urlToOpen);
        }
    })());
});
