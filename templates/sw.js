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
        try {
            payload = event.data.json();
        } catch (e) {
            payload.body = event.data.text();
        }
    }

    const options = {
        body: payload.body || payload.message,
        icon: payload.icon || "/static/images/deskplus-logo.png",
        data: payload.data || { url: "/" },
        badge: "/static/images/deskplus-logo.png",
        vibrate: [100, 50, 100],
    };

    event.waitUntil(
        self.registration.showNotification(payload.title || payload.head, options)
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
