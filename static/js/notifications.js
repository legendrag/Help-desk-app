function initNotifications() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const socket = new WebSocket(`${protocol}//${host}/ws/notifications/`);

    socket.onopen = function() {
        console.log("[Notifications WS] Connected");
    };

    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        console.log("[Notifications WS] message:", data);

        if (Notification.permission === "granted") {
            new Notification("Help Desk", {
                body: data.message || "New activity!",
                icon: "/static/favicon.ico"
            });
        }

        addNotificationToList(data, true);
    };

    socket.onclose = function(e) {
        console.log("[Notifications WS] Closed. Reconnecting in 3s...");
        setTimeout(initNotifications, 3000);
    };

    socket.onerror = function(err) {
        console.error("[Notifications WS] Error:", err);
    };
}

function getCsrfToken() {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput && csrfInput.value) {
        return csrfInput.value;
    }
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
}

function updateBadge(count) {
    const badge = document.getElementById("notification-count");
    if (!badge) return;
    if (count > 0) {
        badge.textContent = count;
        badge.style.display = "flex";
    } else {
        badge.textContent = "0";
        badge.style.display = "none";
    }
}

function formatTime(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString();
}

function buildNotificationItem(item) {
    const wrapper = document.createElement("div");
    wrapper.className = `notification-item ${item.is_read ? "read" : "unread"}`;

    const content = document.createElement("div");
    content.className = "notification-content";

    const title = document.createElement("strong");
    title.textContent = item.title || "Notification";

    const message = document.createElement("p");
    message.textContent = item.message || "";

    const time = document.createElement("span");
    time.className = "notification-time";
    time.textContent = formatTime(item.created_at);

    content.appendChild(title);
    content.appendChild(message);
    content.appendChild(time);

    const dot = document.createElement("span");
    dot.className = "notification-dot";

    wrapper.appendChild(content);
    if (!item.is_read) {
        wrapper.appendChild(dot);
    }

    wrapper.addEventListener("click", () => {
        if (item.link) {
            window.location.href = item.link;
        }
    });

    return wrapper;
}

function renderNotifications(items) {
    const list = document.getElementById("notification-list");
    const empty = document.getElementById("notification-empty");
    if (!list || !empty) return;

    list.innerHTML = "";

    if (!items || items.length === 0) {
        empty.style.display = "block";
        return;
    }

    empty.style.display = "none";
    items.forEach((item) => {
        list.appendChild(buildNotificationItem(item));
    });
}

function addNotificationToList(item, incrementBadge) {
    const list = document.getElementById("notification-list");
    const empty = document.getElementById("notification-empty");
    if (!list || !empty) return;

    const node = buildNotificationItem(item);
    list.prepend(node);
    empty.style.display = "none";

    if (incrementBadge) {
        const badge = document.getElementById("notification-count");
        const current = badge && badge.style.display !== "none" ? parseInt(badge.textContent, 10) || 0 : 0;
        updateBadge(current + 1);
    }
}

function fetchNotifications() {
    return fetch("/notifications/api/?limit=20", {
        credentials: "same-origin",
    })
        .then((response) => response.json())
        .then((data) => {
            renderNotifications(data.notifications || []);
            updateBadge(data.unread_count || 0);
        })
        .catch((err) => console.error("[Notifications] Fetch error:", err));
}

function markAllRead() {
    return fetch("/notifications/mark-read/", {
        method: "POST",
        headers: {
            "X-CSRFToken": getCsrfToken(),
        },
        credentials: "same-origin",
    })
        .then(() => {
            updateBadge(0);
            
            // Immediately visually update DOM items
            const unreadItems = document.querySelectorAll('.notification-item.unread');
            unreadItems.forEach(item => {
                item.classList.remove('unread');
                item.classList.add('read');
                const dot = item.querySelector('.notification-dot');
                if (dot) dot.remove();
            });
        })
        .catch((err) => console.error("[Notifications] Mark read error:", err));
}

function initNotificationUI() {
    const button = document.getElementById("notification-btn");
    const dropdown = document.getElementById("notification-dropdown");
    const markReadBtn = document.getElementById("notification-mark-read");

    if (!button || !dropdown) return;

    button.addEventListener("click", (event) => {
        event.stopPropagation();
        const isOpen = dropdown.style.display === "block";
        dropdown.style.display = isOpen ? "none" : "block";
        if (!isOpen) {
            fetchNotifications().then(markAllRead);
        }
    });

    document.addEventListener("click", (event) => {
        if (!dropdown.contains(event.target) && !button.contains(event.target)) {
            dropdown.style.display = "none";
        }
    });

    if (markReadBtn) {
        markReadBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            markAllRead();
        });
    }

    fetchNotifications();
}

if (window.Notification && Notification.permission === "default") {
    Notification.requestPermission();
}

if (window.userIsAuthenticated) {
    initNotifications();
    document.addEventListener("DOMContentLoaded", initNotificationUI);
}
