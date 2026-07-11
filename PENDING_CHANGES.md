# Exact Patch File for Antigravity

**AI INSTRUCTION:** When you are asked to apply this file, use your file editing tools (`replace_file_content`, `multi_replace_file_content`, `write_to_file`) to apply the exact `ReplacementChunks` provided below to the target files in the newly cloned repository.

---

## 1. `requirements.txt`
**Tool:** `replace_file_content` or simply append.
**Action:** Add `six==1.17.0` to the end of the file.

---

## 2. `templates/webpush/webpush_header.html`
**Tool:** `write_to_file`
**Content:**
```html
{% if user.is_authenticated or group %}
  {% load static %}
  <script src="{% url 'javascript-catalog' %}"></script>
  <script id="webpush-js" type="text/javascript" src="{% static 'webpush/webpush.js' %}"></script>
  <!-- Point to OUR custom service worker instead of django-webpush's default -->
  <meta name="service-worker-js" content="{% url 'sw.js' %}">
  <meta name="django-webpush-vapid-key" content="{{ vapid_public_key }}">
{% endif %}
```

---

## 3. `templates/sw.js`
**Tool:** `replace_file_content`
**TargetContent:**
```javascript
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: false })
            .then(windowClients => {
                const anyFocused = windowClients.some(client => client.focused);
                if (anyFocused) return;

                return self.registration.showNotification(
                    payload.title || payload.head, options
                );
            })
    );
```
**ReplacementContent:**
```javascript
    event.waitUntil(
        self.registration.showNotification(payload.title || payload.head, options)
    );
```

---

## 4. `static/js/notifications.js`
**Tool:** `multi_replace_file_content`

**Chunk 1 (Remove auto-subscribe from toggleDropdown):**
**TargetContent:**
```javascript
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
        
        // Auto-subscribe to Web Push
        if ("Notification" in window && Notification.permission === "default") {
            const hiddenWebpushButton = document.querySelector("#hidden-webpush-container button");
            if (hiddenWebpushButton) {
                hiddenWebpushButton.click();
            }
        }
    }
}
```
**ReplacementContent:**
```javascript
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
```

**Chunk 2 (Remove duplicate browser notification):**
**TargetContent:**
```javascript
        // Browser push notification
        if (Notification.permission === "granted") {
            new Notification("DeskPlus", {
                body: data.message || "New activity!",
                icon: "/static/favicon.ico"
            });
        }

        // Play sound
```
**ReplacementContent:**
```javascript
        // Browser push notification is handled by the Service Worker (sw.js)
        
        // Play sound
```

**Chunk 3 (Add auto-subscribe to page load):**
**TargetContent:**
```javascript
    fetchNotifications();

    // Refresh relative timestamps every minute
    setInterval(refreshTimestamps, 60000);
}
```
**ReplacementContent:**
```javascript
    fetchNotifications();

    // Auto-subscribe to Web Push on page load
    if ("Notification" in window && Notification.permission !== "denied") {
        const hiddenWebpushButton = document.querySelector("#hidden-webpush-container button");
        if (hiddenWebpushButton) {
            hiddenWebpushButton.click();
        }
    }

    // Refresh relative timestamps every minute
    setInterval(refreshTimestamps, 60000);
}
```

---

## 5. `templates/base.html`
**Tool:** `multi_replace_file_content`

**Chunk 1 (Remove Theme Switch from Topbar):**
**TargetContent:**
```html
                <button type="button" class="theme-switch" id="theme-toggle-btn" onclick="toggleDarkMode()" aria-label="Toggle dark mode" title="Toggle dark mode" role="switch">
                    <span class="theme-switch-track">
                        <span class="theme-switch-knob">
                            <svg class="icon-sun" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="12" cy="12" r="5"></circle><rect x="11" y="0" width="2" height="4" rx="1"></rect><rect x="11" y="20" width="2" height="4" rx="1"></rect><rect x="0" y="11" width="4" height="2" rx="1"></rect><rect x="20" y="11" width="4" height="2" rx="1"></rect><rect x="3.3" y="3.3" width="2" height="4" rx="1" transform="rotate(-45 4.3 5.3)"></rect><rect x="18.7" y="16.7" width="2" height="4" rx="1" transform="rotate(-45 19.7 18.7)"></rect><rect x="16.7" y="3.3" width="4" height="2" rx="1" transform="rotate(-45 18.7 4.3)"></rect><rect x="3.3" y="18.7" width="4" height="2" rx="1" transform="rotate(-45 5.3 19.7)"></rect></svg>
                            <svg class="icon-moon" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                        </span>
                    </span>
                </button>
```
**ReplacementContent:**
```html

```

**Chunk 2 (Add Theme Switch to Sidebar below Logout):**
**TargetContent:**
```html
                <form action="{% url 'logout' %}" method="post">
                    {% csrf_token %}
                    <button type="submit" class="sidebar-action-btn danger">Logout</button>
                </form>
            </nav>
```
**ReplacementContent:**
```html
                <form action="{% url 'logout' %}" method="post">
                    {% csrf_token %}
                    <button type="submit" class="sidebar-action-btn danger">Logout</button>
                </form>

                <div style="margin-top: 1rem; display: flex; justify-content: center; align-items: center; gap: 0.5rem; color: var(--text-secondary); font-size: 0.9rem;">
                    <span>Theme</span>
                    <button type="button" class="theme-switch" id="theme-toggle-btn" onclick="toggleDarkMode()" aria-label="Toggle dark mode" title="Toggle dark mode" role="switch">
                        <span class="theme-switch-track">
                            <span class="theme-switch-knob">
                                <svg class="icon-sun" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="12" cy="12" r="5"></circle><rect x="11" y="0" width="2" height="4" rx="1"></rect><rect x="11" y="20" width="2" height="4" rx="1"></rect><rect x="0" y="11" width="4" height="2" rx="1"></rect><rect x="20" y="11" width="4" height="2" rx="1"></rect><rect x="3.3" y="3.3" width="2" height="4" rx="1" transform="rotate(-45 4.3 5.3)"></rect><rect x="18.7" y="16.7" width="2" height="4" rx="1" transform="rotate(-45 19.7 18.7)"></rect><rect x="16.7" y="3.3" width="4" height="2" rx="1" transform="rotate(-45 18.7 4.3)"></rect><rect x="3.3" y="18.7" width="4" height="2" rx="1" transform="rotate(-45 5.3 19.7)"></rect></svg>
                                <svg class="icon-moon" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                            </span>
                        </span>
                    </button>
                </div>
            </nav>
```
