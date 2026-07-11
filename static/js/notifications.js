/**
 * Notification System
 * Real-time notifications via WebSocket with type-based icons,
 * relative timestamps, swipe-to-delete (mobile), and notification sound.
 */

// ── Notification Sound (subtle pop) ──
const NOTIF_SOUND_DATA = "data:audio/wav;base64,UklGRl4FAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YToFAAAAAAEAAgADAAQABQAIAAsADwATABcAGwAfACIAJQAnACgAKAAnACUAIgAeABkAEwANAAYA///4//D/6P/g/9j/0f/K/8P/vf+3/7L/rf+p/6X/ov+g/57/nf+d/53/nv+g/6L/pf+p/63/sv+3/73/w//K/9H/2P/g/+j/8P/4////BgANABMAGQAeACIAJQAnACgAKAAnACUAIgAfABsAFwATAA8ACwAIAAUABAADAAIAAQAAAA==";
let _notifSound = null;
function _getNotifSound() {
    if (!_notifSound) {
        _notifSound = new Audio(NOTIF_SOUND_DATA);
        _notifSound.volume = 0.3;
    }
    return _notifSound;
}
function playNotifSound() {
    try {
        const s = _getNotifSound();
        s.currentTime = 0;
        s.play().catch(() => {});
    } catch (e) { /* ignore */ }
}

// ── Type-based SVG Icons ──
const NOTIF_ICONS = {
    new_ticket: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="12" x2="12" y2="18"/><line x1="9" y1="15" x2="15" y2="15"/></svg>',
    ticket_picked: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/><polyline points="16 3 18 5 22 1"/></svg>',
    status_change: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
    message: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    transfer: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>',
    general: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
};

// ── CSRF Token ──
function getCsrfToken() {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput && csrfInput.value) return csrfInput.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
}

// ── Relative Time Formatter ──
function formatRelativeTime(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "";
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHr = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHr / 24);

    if (diffSec < 60) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDay === 1) return "Yesterday";
    if (diffDay < 7) return `${diffDay}d ago`;
    // Older than a week — show short date
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ── Badge ──
function updateBadge(count) {
    const badge = document.getElementById("notification-count");
    if (!badge) return;
    if (count > 0) {
        badge.textContent = count > 99 ? "99+" : count;
        badge.style.display = "flex";
    } else {
        badge.textContent = "0";
        badge.style.display = "none";
    }
}

// ── Build Notification Item ──
function buildNotificationItem(item) {
    const wrapper = document.createElement("div");
    wrapper.className = `notification-item ${item.is_read ? "read" : "unread"}`;
    wrapper.setAttribute("tabindex", "0");
    wrapper.setAttribute("role", "button");
    wrapper.dataset.notifId = item.id;
    wrapper.dataset.notifType = item.notification_type || "general";

    // Type icon
    const iconWrap = document.createElement("div");
    iconWrap.className = `notif-icon notif-icon-${item.notification_type || "general"}`;
    iconWrap.innerHTML = NOTIF_ICONS[item.notification_type] || NOTIF_ICONS.general;

    // Content
    const content = document.createElement("div");
    content.className = "notification-content";

    const title = document.createElement("strong");
    title.textContent = item.title || "Notification";

    const message = document.createElement("p");
    message.textContent = item.message || "";

    const time = document.createElement("span");
    time.className = "notification-time";
    time.textContent = formatRelativeTime(item.created_at);
    time.dataset.iso = item.created_at || "";

    content.appendChild(title);
    content.appendChild(message);
    content.appendChild(time);

    // Delete button (desktop X)
    const deleteBtn = document.createElement("button");
    deleteBtn.className = "notif-delete-btn";
    deleteBtn.setAttribute("aria-label", "Delete notification");
    deleteBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
    deleteBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteNotification(item, wrapper);
    });

    // Unread dot
    const dot = document.createElement("span");
    dot.className = "notification-dot";

    wrapper.appendChild(iconWrap);
    wrapper.appendChild(content);
    if (!item.is_read) {
        wrapper.appendChild(dot);
    }
    wrapper.appendChild(deleteBtn);

    // Click handler — mark read & navigate
    const onClick = () => {
        if (!item.is_read) {
            // Optimistic UI update
            wrapper.classList.remove("unread");
            wrapper.classList.add("read");
            const dotEl = wrapper.querySelector(".notification-dot");
            if (dotEl) dotEl.remove();
            item.is_read = true;

            const badge = document.getElementById("notification-count");
            if (badge && badge.style.display !== "none") {
                const current = parseInt(badge.textContent, 10) || 0;
                updateBadge(Math.max(0, current - 1));
            }

            fetch(`/notifications/mark-read/${item.id}/`, {
                method: "POST",
                headers: { "X-CSRFToken": getCsrfToken() },
                credentials: "same-origin",
            }).then(() => {
                if (item.link) window.location.href = item.link;
            }).catch(() => {
                if (item.link) window.location.href = item.link;
            });
        } else {
            if (item.link) window.location.href = item.link;
        }
    };

    wrapper.addEventListener("click", onClick);
    wrapper.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick();
        }
    });

    // ── Swipe-to-delete (mobile) ──
    setupSwipeDelete(wrapper, item);

    return wrapper;
}

// ── Swipe-to-Delete (touch) ──
function setupSwipeDelete(el, item) {
    let startX = 0;
    let currentX = 0;
    let isSwiping = false;
    const THRESHOLD = 80;

    el.addEventListener("touchstart", (e) => {
        startX = e.touches[0].clientX;
        currentX = startX;
        isSwiping = true;
        el.style.transition = "none";
    }, { passive: true });

    el.addEventListener("touchmove", (e) => {
        if (!isSwiping) return;
        currentX = e.touches[0].clientX;
        const diff = currentX - startX;
        // Only allow left swipe
        if (diff < 0) {
            el.style.transform = `translateX(${Math.max(diff, -120)}px)`;
            el.style.opacity = Math.max(1 + diff / 200, 0.3).toString();
        }
    }, { passive: true });

    el.addEventListener("touchend", () => {
        if (!isSwiping) return;
        isSwiping = false;
        const diff = currentX - startX;
        el.style.transition = "transform 0.3s ease, opacity 0.3s ease";
        if (diff < -THRESHOLD) {
            // Swiped far enough — delete
            el.style.transform = "translateX(-120%)";
            el.style.opacity = "0";
            setTimeout(() => deleteNotification(item, el), 300);
        } else {
            // Snap back
            el.style.transform = "translateX(0)";
            el.style.opacity = "1";
        }
    });
}

// ── Delete a notification ──
function deleteNotification(item, el) {
    // Animate out
    el.style.maxHeight = el.offsetHeight + "px";
    el.style.overflow = "hidden";
    requestAnimationFrame(() => {
        el.style.transition = "max-height 0.3s ease, opacity 0.2s ease, padding 0.3s ease";
        el.style.maxHeight = "0";
        el.style.opacity = "0";
        el.style.paddingTop = "0";
        el.style.paddingBottom = "0";
    });

    setTimeout(() => {
        el.remove();
        // Show empty state if needed
        const list = document.getElementById("notification-list");
        const empty = document.getElementById("notification-empty");
        if (list && list.children.length === 0 && empty) {
            empty.style.display = "flex";
        }
    }, 300);

    fetch(`/notifications/delete/${item.id}/`, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken() },
        credentials: "same-origin",
    }).then(r => r.json()).then(data => {
        if (data.unread_count !== undefined) updateBadge(data.unread_count);
    }).catch(err => console.error("[Notifications] Delete error:", err));
}

// ── Render Notifications List ──
function renderNotifications(items) {
    const list = document.getElementById("notification-list");
    const empty = document.getElementById("notification-empty");
    if (!list || !empty) return;

    list.innerHTML = "";

    if (!items || items.length === 0) {
        empty.style.display = "flex";
        return;
    }

    empty.style.display = "none";
    items.forEach((item) => {
        list.appendChild(buildNotificationItem(item));
    });
}

// ── Add notification to top of list ──
function addNotificationToList(item, incrementBadge) {
    const list = document.getElementById("notification-list");
    const empty = document.getElementById("notification-empty");
    if (!list || !empty) return;

    const node = buildNotificationItem(item);
    // Animate in
    node.style.opacity = "0";
    node.style.transform = "translateY(-10px)";
    list.prepend(node);
    empty.style.display = "none";

    requestAnimationFrame(() => {
        node.style.transition = "opacity 0.3s ease, transform 0.3s ease";
        node.style.opacity = "1";
        node.style.transform = "translateY(0)";
    });

    if (incrementBadge) {
        const badge = document.getElementById("notification-count");
        const current = badge && badge.style.display !== "none" ? parseInt(badge.textContent, 10) || 0 : 0;
        updateBadge(current + 1);
    }
}

// ── Fetch from API ──
function fetchNotifications() {
    return fetch("/notifications/api/?limit=20", { credentials: "same-origin" })
        .then((response) => response.json())
        .then((data) => {
            renderNotifications(data.notifications || []);
            updateBadge(data.unread_count || 0);
        })
        .catch((err) => console.error("[Notifications] Fetch error:", err));
}

// ── Mark All Read ──
function markAllRead() {
    return fetch("/notifications/mark-read/", {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken() },
        credentials: "same-origin",
    })
        .then(() => {
            updateBadge(0);
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

// ── Clear Read Notifications ──
function clearReadNotifications() {
    const readItems = document.querySelectorAll('.notification-item.read');
    readItems.forEach(item => {
        item.style.transition = "max-height 0.3s ease, opacity 0.2s ease, padding 0.3s ease";
        item.style.maxHeight = item.offsetHeight + "px";
        item.style.overflow = "hidden";
        requestAnimationFrame(() => {
            item.style.maxHeight = "0";
            item.style.opacity = "0";
            item.style.paddingTop = "0";
            item.style.paddingBottom = "0";
        });
    });
    setTimeout(() => {
        readItems.forEach(i => i.remove());
        const list = document.getElementById("notification-list");
        const empty = document.getElementById("notification-empty");
        if (list && list.children.length === 0 && empty) {
            empty.style.display = "flex";
        }
    }, 300);

    fetch("/notifications/clear-read/", {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken() },
        credentials: "same-origin",
    }).then(r => r.json()).then(data => {
        if (data.unread_count !== undefined) updateBadge(data.unread_count);
    }).catch((err) => console.error("[Notifications] Clear read error:", err));
}

// ── Dropdown Toggle (CSS class-based for animation) ──
function toggleDropdown(forceClose = false) {
    const dropdown = document.getElementById("notification-dropdown");
    if (!dropdown) return;
    const isOpen = dropdown.classList.contains("open");

    if (forceClose || isOpen) {
        dropdown.classList.remove("open");
    } else {
        dropdown.classList.add("open");
        fetchNotifications();
    }
}

// ── Update relative timestamps periodically ──
function refreshTimestamps() {
    document.querySelectorAll(".notification-time[data-iso]").forEach(el => {
        if (el.dataset.iso) {
            el.textContent = formatRelativeTime(el.dataset.iso);
        }
    });
}

// ── WebSocket Connection ──
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

        // Fix Bug 2: exact path matching for suppression
        const currentPath = window.location.pathname;
        const isRelatedPage = data.link && currentPath === data.link;
        const isFocused = document.hasFocus();

        if (isRelatedPage && isFocused) {
            // Suppress UI notification and silently mark as read
            fetch(`/notifications/mark-read/${data.id}/`, {
                method: "POST",
                headers: { "X-CSRFToken": getCsrfToken() },
                credentials: "same-origin",
            }).catch(err => console.error("Auto-mark read failed:", err));
            return;
        }

        // Browser push notification is handled by the Service Worker (sw.js)
        
        // Play sound
        playNotifSound();

        // Add to dropdown (works whether open or closed)
        addNotificationToList(data, true);
    };

    socket.onclose = function() {
        console.log("[Notifications WS] Closed. Reconnecting in 3s...");
        setTimeout(initNotifications, 3000);
    };

    socket.onerror = function(err) {
        console.error("[Notifications WS] Error:", err);
    };
}

// ── Init UI ──
function initNotificationUI() {
    const button = document.getElementById("notification-btn");
    const dropdown = document.getElementById("notification-dropdown");
    const markReadBtn = document.getElementById("notification-mark-read");
    const clearReadBtn = document.getElementById("notification-clear-read");
    const testPushBtn = document.getElementById("notification-test-push");

    if (!button || !dropdown) return;

    button.addEventListener("click", async (event) => {
        event.stopPropagation();
        toggleDropdown();
        
        // Ensure we ask for permissions upon user gesture if they haven't been asked yet
        if (window.Notification && Notification.permission === "default") {
            const perm = await Notification.requestPermission();
            if (perm === "granted") {
                initWebPush();
            }
        }
    });

    if (testPushBtn) {
        testPushBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const url = testPushBtn.dataset.url;
            if (!url) return;
            try {
                const res = await fetch(url, {
                    method: "POST",
                    headers: { "X-CSRFToken": getCsrfToken() },
                    credentials: "same-origin"
                });
                const data = await res.json();
                if (res.ok) {
                    alert(data.message);
                } else {
                    alert("Error: " + data.message);
                }
            } catch (err) {
                alert("Failed to send test push: " + err);
            }
        });
    }

    document.addEventListener("click", (event) => {
        if (!dropdown.contains(event.target) && !button.contains(event.target)) {
            toggleDropdown(true);
        }
    });

    document.addEventListener("focusin", (event) => {
        if (dropdown.classList.contains("open") && !dropdown.contains(event.target) && !button.contains(event.target)) {
            toggleDropdown(true);
        }
    });

    if (markReadBtn) {
        markReadBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            markAllRead();
        });
    }

    if (clearReadBtn) {
        clearReadBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            clearReadNotifications();
        });
    }

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            if (dropdown.classList.contains("open")) {
                toggleDropdown(true);
                button.focus();
            }
        }
    });

    fetchNotifications();

    // Initialize Web Push subscription
    initWebPush();

    // Refresh relative timestamps every minute
    setInterval(refreshTimestamps, 60000);
}

// ── Web Push Subscription ──
function urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

function initWebPush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        alert("[WebPush] Push notifications not supported in this browser. If on iOS, add this app to your Home Screen.");
        return;
    }

    const swMeta = document.querySelector('meta[name="service-worker-js"]');
    const vapidMeta = document.querySelector('meta[name="django-webpush-vapid-key"]');
    const saveUrlMeta = document.querySelector('meta[name="django-webpush-save-url"]');

    if (!swMeta || !vapidMeta || !saveUrlMeta) {
        alert("[WebPush] WebPush metadata missing from page! Is webpush_header included?");
        return;
    }

    const swUrl = swMeta.content;
    const vapidKey = vapidMeta.content;
    const saveUrl = saveUrlMeta.content;

    navigator.serviceWorker.register(swUrl).then(async (reg) => {
        console.log("[WebPush] Service Worker registered:", reg);

        if (Notification.permission !== "granted") {
            alert("Please allow notification permissions in your browser settings (click the lock icon next to the URL) to receive Push Notifications.");
            return;
        }

        try {
            let subscription = await reg.pushManager.getSubscription();

            if (!subscription) {
                console.log("[WebPush] No subscription found. Subscribing with new VAPID key...");
                subscription = await reg.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlB64ToUint8Array(vapidKey)
                });
                console.log("[WebPush] Subscribed successfully. Saving to server...");
            } else {
                console.log("[WebPush] Existing subscription found. Syncing with server...");
            }
            
            // Always sync the subscription with the server to prevent desync (e.g., if a previous save failed)
            await sendSubscriptionToServer(subscription, "subscribe", saveUrl);
        } catch (err) {
            console.error("[WebPush] Error during subscription flow:", err);
            alert("WebPush Subscription Error: " + err.message);
        }
    }).catch((err) => {
        console.error("[WebPush] Service Worker registration failed:", err);
        alert("WebPush Service Worker Error: " + err.message);
    });
}

function sendSubscriptionToServer(subscription, statusType, saveUrl) {
    let browser = "chrome";
    const userAgent = navigator.userAgent.toLowerCase();
    if (userAgent.includes("firefox")) browser = "firefox";
    else if (userAgent.includes("safari") && !userAgent.includes("chrome")) browser = "safari";

    const data = {
        status_type: statusType,
        subscription: subscription.toJSON(),
        browser: browser
    };

    return fetch(saveUrl, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(data),
        credentials: 'include'
    }).then(async response => {
        if (!response.ok) {
            const text = await response.text();
            console.error(`[WebPush] Server error ${response.status}: ${text}`);
            alert(`WebPush Server Error ${response.status}: ${text}`);
            throw new Error(`Server responded with ${response.status}`);
        }
        console.log("[WebPush] Subscription saved successfully.");
    });
}

// ── Bootstrap ──
if (window.Notification && Notification.permission === "default") {
    Notification.requestPermission();
}

if (window.userIsAuthenticated) {
    initNotifications();
    document.addEventListener("DOMContentLoaded", initNotificationUI);
}
