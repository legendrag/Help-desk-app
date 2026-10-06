// History snapshots used to be the whole body. Drop any of those so a back
// navigation cannot inject a full document into #shell-content.
try {
    if (localStorage.getItem("htmx-history-elt") !== "shell-content") {
        localStorage.removeItem("htmx-history-cache");
        localStorage.setItem("htmx-history-elt", "shell-content");
    }
} catch (e) {}

// Dark mode toggle
function toggleDarkMode() {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('theme', 'light');
    } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
    }
}

// Language switch: animate first, then POST with progress bar only
(function () {
    var form = document.getElementById('lang-switch-form');
    var btn = document.getElementById('lang-toggle-btn');
    if (!form || !btn) return;

    btn.addEventListener('click', function () {
        if (btn.dataset.animating === '1') return;
        btn.dataset.animating = '1';

        var toAr = !btn.classList.contains('is-ar');
        // Force a paint so the class change always transitions
        void btn.offsetWidth;
        btn.classList.toggle('is-ar', toAr);
        btn.setAttribute('aria-checked', toAr ? 'true' : 'false');

        var knob = btn.querySelector('.lang-switch-knob');
        var done = false;
        function go() {
            if (done) return;
            done = true;
            if (knob) knob.removeEventListener('transitionend', onEnd);
            if (typeof window.beginProgressNavigation === 'function') {
                window.beginProgressNavigation();
                requestAnimationFrame(function () { form.submit(); });
                return;
            }
            form.submit();
        }
        function onEnd(ev) {
            if (ev.target !== knob) return;
            if (ev.propertyName && ev.propertyName !== 'transform') return;
            go();
        }
        if (knob) knob.addEventListener('transitionend', onEnd);
        setTimeout(go, 420);
    });
})();

function setMenuButtonOpen(isOpen) {
    const menuBtn = document.getElementById('menu-btn') || document.querySelector('.menu-btn-universal');
    if (!menuBtn) return;
    menuBtn.classList.toggle('is-open', isOpen);
    menuBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    menuBtn.setAttribute('aria-label', isOpen ? (window.I18N && window.I18N.closeMenu) || 'Close menu' : (window.I18N && window.I18N.openMenu) || 'Open menu');
}

const NAV_PREFETCH_ORDER = ["tickets", "dashboard", "news", "kb"];
let navPrefetchStarted = false;

function navPrefetchKey(pathname) {
    const path = (pathname || "").replace(/\/+$/, "") || "/";
    if (path === "/tickets") return "tickets";
    if (path === "/tickets/dashboard") return "dashboard";
    if (path === "/news") return "news";
    if (path === "/kb") return "kb";
    return null;
}

function prefetchUrl(url, done) {
    const script = document.createElement("script");
    script.type = "speculationrules";
    script.textContent = JSON.stringify({
        prefetch: [{ urls: [url], eagerness: "immediate" }]
    });
    let finished = false;
    let timer = null;
    let observer = null;
    const finish = () => {
        if (finished) return;
        finished = true;
        if (observer) observer.disconnect();
        clearTimeout(timer);
        done();
    };
    observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
            let entryPath = "";
            try {
                entryPath = new URL(entry.name).pathname;
            } catch (e) {
                continue;
            }
            if (entryPath === url || entryPath + "/" === url || entryPath === url + "/") {
                finish();
                return;
            }
        }
    });
    // Speculation prefetches do not show up in resource timing, so this gap
    // is what actually starts the next page. Keep it short enough that the
    // rest of the menu is requested before a normal click.
    timer = setTimeout(finish, 400);
    observer.observe({ type: "resource", buffered: true });
    document.head.appendChild(script);
}

function startNavPrefetch() {
    if (navPrefetchStarted) return;
    if (!window.HTMLScriptElement || !HTMLScriptElement.supports || !HTMLScriptElement.supports("speculationrules")) {
        return;
    }
    navPrefetchStarted = true;

    const here = (location.pathname || "").replace(/\/+$/, "") || "/";
    const byKey = {};
    document.querySelectorAll("#sidebar .sidebar-nav a[href]").forEach((anchor) => {
        if (anchor.hasAttribute("hx-get") || anchor.hasAttribute("hx-post") || anchor.hasAttribute("download")) return;
        const href = anchor.getAttribute("href");
        if (!href || href.charAt(0) === "#") return;
        let url;
        try {
            url = new URL(href, location.origin);
        } catch (e) {
            return;
        }
        if (url.origin !== location.origin) return;
        const key = navPrefetchKey(url.pathname);
        if (!key) return;
        const path = url.pathname.replace(/\/+$/, "") || "/";
        if (path === here) return;
        byKey[key] = url.pathname + url.search;
    });

    const queue = [];
    NAV_PREFETCH_ORDER.forEach((key) => {
        if (byKey[key]) queue.push(byKey[key]);
    });

    const prefetchNext = () => {
        const next = queue.shift();
        if (!next) return;
        prefetchUrl(next, prefetchNext);
    };
    prefetchNext();
}

function openSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    if (!sidebar || !overlay) return;
    sidebar.classList.add('open');
    overlay.classList.add('open');
    document.body.classList.add('sidebar-open');
    setMenuButtonOpen(true);
    startNavPrefetch();
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
    document.body.classList.remove('sidebar-open');
    setMenuButtonOpen(false);
}
window.closeSidebar = closeSidebar;
window.openSidebar = openSidebar;

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar && sidebar.classList.contains('open')) {
        closeSidebar();
    } else {
        openSidebar();
    }
}

document.getElementById('sidebar').addEventListener('keydown', function (e) {
    if (e.key === 'Tab') {
        const focusableElements = this.querySelectorAll('a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])');
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
            if (document.activeElement === firstElement) {
                lastElement.focus();
                e.preventDefault();
            }
        } else {
            if (document.activeElement === lastElement) {
                firstElement.focus();
                e.preventDefault();
            }
        }
    }
});

function openModal() {
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
    document.documentElement.style.setProperty('--scrollbar-width', `${scrollbarWidth}px`);
    document.documentElement.classList.add('modal-open');

    // Skeleton placeholder while HTMX fills the modal
    const content = document.getElementById('modal-content');
    if (content) {
        const textWithoutComments = content.innerHTML.replace(new RegExp('<!--[\\\\s\\\\S]*?-->', 'g'), '').trim();
        if (!textWithoutComments) {
            const tpl = document.getElementById('modal-skeleton');
            if (tpl && tpl.content) {
                content.replaceChildren(tpl.content.cloneNode(true));
            }
        }
    }

    const container = document.getElementById('modal-container');
    if (container) {
        container.style.display = 'flex';
        container.dataset.dirty = 'false';
    }
}
let discardCallback = null;

function closeModal(force = false) {
    const container = document.getElementById('modal-container');
    if (!force && container && container.dataset.dirty === 'true') {
        discardCallback = function () {
            performCloseModal();
        };
        document.getElementById('discard-confirm-modal').style.display = 'flex';
        return;
    }
    performCloseModal();
}

function performCloseModal() {
    document.documentElement.classList.remove('modal-open');
    document.documentElement.style.removeProperty('--scrollbar-width');
    const container = document.getElementById('modal-container');
    const content = document.getElementById('modal-content');
    // Destroy Tom Selects before clearing HTML — body-mounted dropdowns otherwise linger
    if (content) {
        content.querySelectorAll('select').forEach((select) => {
            if (select.tomselect) {
                select.tomselect.destroy();
            }
        });
    }
    if (container) {
        container.style.display = 'none';
        container.dataset.dirty = 'false';
    }
    setTimeout(() => {
        if (content) content.innerHTML = '';
    }, 100);
}

function confirmDiscard() {
    document.getElementById('discard-confirm-modal').style.display = 'none';
    if (discardCallback) {
        discardCallback();
        discardCallback = null;
    }
}

function cancelDiscard() {
    document.getElementById('discard-confirm-modal').style.display = 'none';
    discardCallback = null;
}

let globalConfirmCallback = null;

let defaultConfirmCancelText = null;

function showConfirmModal(options) {
    const titleEl = document.getElementById('global-confirm-title');
    titleEl.textContent = options.title || 'Confirm Action';
    document.getElementById('global-confirm-text').textContent = options.message || 'Are you sure you want to proceed?';

    const actionBtn = document.getElementById('global-confirm-action-btn');
    actionBtn.textContent = options.yesText || 'Yes, Delete';

    const cancelBtn = document.getElementById('global-confirm-cancel-btn');
    if (cancelBtn) {
        if (defaultConfirmCancelText === null) {
            defaultConfirmCancelText = cancelBtn.textContent;
        }
        cancelBtn.textContent = options.cancelText || defaultConfirmCancelText;
    }

    if (options.isDanger === false) {
        actionBtn.className = 'btn primary discard-modal-btn';
        titleEl.classList.remove('is-danger');
    } else {
        actionBtn.className = 'btn danger discard-modal-btn';
        titleEl.classList.add('is-danger');
    }

    globalConfirmCallback = options.onConfirm || null;
    document.getElementById('global-confirm-modal').style.display = 'flex';
    document.documentElement.classList.add('modal-open');
}

function closeGlobalConfirmModal() {
    document.getElementById('global-confirm-modal').style.display = 'none';
    document.documentElement.classList.remove('modal-open');
    globalConfirmCallback = null;
}

document.addEventListener('DOMContentLoaded', function () {
    const confirmActionBtn = document.getElementById('global-confirm-action-btn');
    if (confirmActionBtn) {
        confirmActionBtn.addEventListener('click', function () {
            if (globalConfirmCallback) {
                globalConfirmCallback();
            }
            closeGlobalConfirmModal();
        });
    }
});

// Intercept HTMX confirm requests
document.body.addEventListener('htmx:confirm', function (evt) {
    const confirmQuestion = evt.detail.question;
    if (confirmQuestion) {
        evt.preventDefault();
        const element = evt.detail.elt;
        const host = element.closest('[hx-confirm]') || element;
        const confirmAttr = function (name) {
            return element.getAttribute(name) || host.getAttribute(name);
        };

        // Smart defaults based on context/classes
        const isDelete = confirmQuestion.toLowerCase().includes('delete') ||
            element.classList.contains('danger') ||
            (element.getAttribute('hx-post') && element.getAttribute('hx-post').toLowerCase().includes('delete')) ||
            (element.getAttribute('hx-get') && element.getAttribute('hx-get').toLowerCase().includes('delete'));

        const title = confirmAttr('data-confirm-title') || (isDelete ? 'Confirm Deletion' : 'Confirm Action');
        const yesText = confirmAttr('data-confirm-ok') || confirmAttr('data-confirm-button') || (isDelete ? 'Yes, Delete' : 'Yes, Proceed');
        const isDanger = element.getAttribute('data-confirm-type') !== 'primary' && (isDelete || element.classList.contains('danger'));

        showConfirmModal({
            title: title,
            message: confirmQuestion,
            yesText: yesText,
            cancelText: confirmAttr('data-confirm-cancel'),
            isDanger: isDanger,
            onConfirm: function () {
                evt.detail.issueRequest();
            }
        });
    }
});

// Listen for input/change inside the modal container to track dirty state
document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('modal-container');
    if (container) {
        const markDirty = function (e) {
            // Only mark dirty for real user interactions, ignore programmatic events (like TomSelect init)
            if (!e.isTrusted) return;

            if (e.target && e.target.tagName) {
                const tagName = e.target.tagName.toLowerCase();
                if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
                    container.dataset.dirty = 'true';
                }
            }
        };
        container.addEventListener('input', markDirty);
        container.addEventListener('change', markDirty);
    }
});


function attachPasswordToggle(input) {
    if (!input) return;
    if (input.dataset.passwordReady === 'true') return;

    let wrapper = input.closest('.password-field');
    if (!wrapper) {
        wrapper = document.createElement('div');
        wrapper.className = 'password-field';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
    }

    let toggle = wrapper.querySelector('.password-toggle');
    if (!toggle) {
        toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'password-toggle';
        toggle.setAttribute('tabindex', '-1');
        toggle.setAttribute('aria-label', 'Toggle password visibility');
        toggle.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
        wrapper.appendChild(toggle);
    }

    input.dataset.passwordReady = 'true';
}

function initPasswordToggles(container) {
    const root = container || document;
    const passwordInputs = root.querySelectorAll('input[type="password"]');
    passwordInputs.forEach((input) => attachPasswordToggle(input));
}

document.addEventListener('click', (event) => {
    const toggle = event.target.closest('.password-toggle');
    if (!toggle) return;

    const wrapper = toggle.closest('.password-field');
    const input = wrapper ? wrapper.querySelector('input') : null;
    if (!input) return;

    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    toggle.innerHTML = isHidden
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a21.73 21.73 0 0 1 5.06-6.94"></path><path d="M1 1l22 22"></path><path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a21.83 21.83 0 0 1-5.06 6.94"></path><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"></path></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
});

function initUserTypeToggle(container) {
    const root = container || document;
    const userType = root.querySelector("#id_user_type");
    if (!userType) return;

    const branchGroup = root.querySelector('[data-field="branch"]');
    const deptGroup = root.querySelector('[data-field="department"]');
    const branchInput = root.querySelector("#id_branch");
    const deptInput = root.querySelector("#id_department");

    function show(el) {
        if (el) el.style.display = "block";
    }

    function hide(el) {
        if (el) el.style.display = "none";
    }

    function syncUserTypeFields() {
        const value = userType.value;
        if (value === "branch") {
            show(branchGroup);
            hide(deptGroup);
            if (branchInput) branchInput.required = true;
            if (deptInput) {
                deptInput.required = false;
                deptInput.value = "";
            }
        } else if (value === "support") {
            show(deptGroup);
            hide(branchGroup);
            if (deptInput) deptInput.required = true;
            if (branchInput) {
                branchInput.required = false;
                branchInput.value = "";
            }
        } else {
            show(branchGroup);
            show(deptGroup);
            if (branchInput) branchInput.required = false;
            if (deptInput) deptInput.required = false;
        }
    }

    userType.addEventListener("change", syncUserTypeFields);
    syncUserTypeFields();
}

function openAdminModal(url) {
    const content = document.getElementById('modal-content');
    content.innerHTML = `
        <div class="modal-header">
            <h2>Admin Action</h2>
            <button type="button" class="modal-close" onclick="closeModal()">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <iframe src="${url}" style="width: 100%; height: 70vh; border: none; border-radius: 8px;"></iframe>
    `;
    openModal();
}

// Close modal or sidebar on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();

        const sidebar = document.getElementById('sidebar');
        if (sidebar && sidebar.classList.contains('open')) {
            closeSidebar();
            const menuBtn = document.getElementById('menu-btn') || document.querySelector('.menu-btn-universal');
            if (menuBtn) menuBtn.focus();
        }

        // Handle custom modals from detail.html
        const customModals = ['custom-close-modal', 'custom-merge-modal', 'custom-transfer-modal', 'lightbox-modal'];
        customModals.forEach(id => {
            const el = document.getElementById(id);
            if (el && el.style.display !== 'none' && el.style.display !== '') {
                if (id === 'lightbox-modal') {
                    if (typeof closeLightbox === 'function') closeLightbox();
                } else {
                    el.style.display = 'none';
                }
            }
        });

        // Handle action bar dropdown
        const actionMenu = document.getElementById('action-bar-menu');
        const actionToggle = document.getElementById('action-bar-toggle');
        if (actionMenu && actionMenu.classList.contains('show')) {
            actionMenu.classList.remove('show');
            if (actionToggle) {
                actionToggle.setAttribute('aria-expanded', 'false');
                actionToggle.focus();
            }
        }
    }
});

document.addEventListener('DOMContentLoaded', () => {
    initUserTypeToggle(document);
    initPasswordToggles(document);
});

// Listen for HX-Trigger: closeModal from server
document.body.addEventListener('closeModal', function () {
    closeModal(true); // Force close since the server instructed it
});

document.body.addEventListener('htmx:afterOnLoad', function (evt) {
    // Re-bind items if needed after HTMX swaps
    if (evt.detail.target.id === 'modal-content' && evt.detail.xhr && evt.detail.xhr.status !== 204) {
        openModal();
        initUserTypeToggle(evt.detail.target);
    }
    initPasswordToggles(document);
});

document.body.addEventListener('reloadPage', function () {
    if (typeof window.reloadWithLoading === 'function') {
        window.reloadWithLoading();
    } else {
        window.location.reload();
    }
});

document.body.addEventListener('refreshTickets', function () {
    const list = document.getElementById('tickets-live') || document.getElementById('ticket-list');
    if (list && window.htmx) {
        // Prefer the live partial's own hx-trigger; this ajax is a fallback.
        // source + data-no-progress keeps the top progress bar off.
        window.htmx.ajax('GET', window.location.href, {
            target: '#' + list.id,
            source: list,
            swap: 'outerHTML'
        });
    }
});

document.addEventListener('htmx:afterRequest', function (evt) {
    const xhr = evt.detail.xhr;
    if (!xhr) return;

    const trigger = xhr.getResponseHeader('HX-Trigger') || '';
    const isNoContent = xhr.status === 204;

    if (isNoContent || trigger.includes('closeModal')) {
        closeModal(true);
    }
    if (trigger.includes('refreshSettings')) {
        document.body.dispatchEvent(new CustomEvent('refreshSettings'));
    }
    if (trigger.includes('refreshTickets')) {
        document.body.dispatchEvent(new CustomEvent('refreshTickets'));
    }
    if (trigger.includes('reloadPage')) {
        if (typeof window.reloadWithLoading === 'function') {
            window.reloadWithLoading();
        } else {
            window.location.reload();
        }
    }
});

// Initialize Tom Select robustly
function initializeChoices(targetElement) {
    const selects = Array.from(targetElement.querySelectorAll ? targetElement.querySelectorAll('select:not(.tomselected):not(.no-tomselect)') : []);

    if (targetElement.tagName && targetElement.tagName.toLowerCase() === 'select') {
        if (!targetElement.classList.contains('tomselected')) {
            selects.push(targetElement);
        }
    }

    const iconSvgMap = {
        "document": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>',
        "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>',
        "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>',
        "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>',
        "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>',
        "info": '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>',
        "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path>',
        "help": '<circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line>',
        "globe": '<circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>'
    };

    selects.forEach(select => {
        if (select.tomselect || select.classList.contains('tomselected') || select.classList.contains('no-tomselect')) {
            return;
        }

        let options = {
            controlInput: null,
            sortField: null,
            searchField: []
        };

        // Modal/offcanvas use overflow:hidden — keep the menu outside so it isn't clipped
        if (select.closest('.modal-content, .modal-overlay, .ticket-offcanvas')) {
            options.dropdownParent = 'body';
        }

        if (select.classList.contains('icon-select')) {
            const renderIcon = function (data, escape) {
                const svgInner = iconSvgMap[data.value] || iconSvgMap['document'];
                if (!data.value) return '<div>' + escape(data.text) + '</div>'; // Handle empty placeholder if any
                return '<div>' +
                    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px; vertical-align: middle;">' +
                    svgInner +
                    '</svg>' +
                    '<span style="vertical-align: middle;">' + escape(data.text) + '</span>' +
                    '</div>';
            };
            options.render = {
                option: renderIcon,
                item: renderIcon
            };
            // Icon list is always opened from the KB category modal
            options.dropdownParent = 'body';
        }

        new TomSelect(select, options);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initializeChoices(document);

    // Automatic Scroll Lock Observer for all popups/modals/overlays
    const checkScrollLock = () => {
        let isLocked = false;
        const overlays = document.querySelectorAll('.modal-overlay, .lightbox-modal, .ticket-offcanvas, #overlay');

        overlays.forEach(el => {
            if (el.classList.contains('ticket-offcanvas') || el.id === 'overlay' || el.classList.contains('lightbox-modal')) {
                if (el.classList.contains('open')) {
                    isLocked = true;
                }
            } else if (el.classList.contains('modal-overlay')) {
                const display = el.style.display || window.getComputedStyle(el).display;
                if (display === 'flex' || display === 'block') {
                    isLocked = true;
                }
            }
        });

        if (isLocked) {
            if (!document.documentElement.classList.contains('modal-open')) {
                const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
                document.documentElement.style.setProperty('--scrollbar-width', `${scrollbarWidth}px`);
                document.documentElement.classList.add('modal-open');
            }
        } else {
            document.documentElement.classList.remove('modal-open');
            document.documentElement.style.removeProperty('--scrollbar-width');
        }
    };

    const observer = new MutationObserver(() => {
        checkScrollLock();
    });

    const overlaySelector = '.modal-overlay, .lightbox-modal, .ticket-offcanvas, #overlay';
    const observeOverlay = (el) => {
        if (!el || el.nodeType !== 1 || el.dataset.scrollLockObserved === '1') return;
        el.dataset.scrollLockObserved = '1';
        observer.observe(el, {
            attributes: true,
            subtree: true,
            attributeFilter: ['style', 'class']
        });
    };

    document.querySelectorAll(overlaySelector).forEach(observeOverlay);

    // Watch for new overlays only. Class/style changes elsewhere no longer wake this.
    const overlayMounts = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (!node || node.nodeType !== 1) return;
                if (node.matches && node.matches(overlaySelector)) observeOverlay(node);
                if (node.querySelectorAll) node.querySelectorAll(overlaySelector).forEach(observeOverlay);
            });
        });
    });
    overlayMounts.observe(document.body, { childList: true, subtree: true });

    checkScrollLock();
});

var SHELL_PAGE_CLASSES = [
    "ticket-detail-page",
    "kb-page",
    "kb-search-page",
    "kb-detail-page",
    "kb-form-page",
    "settings-page",
    "dashboard-page"
];

function shellPageKindFromHtml(html) {
    if (!html) return "";
    if (html.indexOf('id="ticket-shell-pane"') !== -1) return "ticket";
    if (html.indexOf('id="tickets-live"') !== -1) return "tickets";
    if (html.indexOf('id="kb-shell-pane"') !== -1) return "kb";
    if (html.indexOf('id="shifts-shell-pane"') !== -1) return "shifts";
    if (html.indexOf('id="settings-shell-pane"') !== -1) return "settings";
    if (html.indexOf('id="news-shell-pane"') !== -1) return "news";
    return "";
}

function shellPageKindFromDom() {
    if (document.getElementById("ticket-shell-pane")) return "ticket";
    if (document.getElementById("tickets-live")) return "tickets";
    if (document.getElementById("kb-shell-pane")) return "kb";
    if (document.getElementById("shifts-shell-pane")) return "shifts";
    if (document.getElementById("settings-shell-pane")) return "settings";
    if (document.getElementById("news-shell-pane")) return "news";
    if (document.body.classList.contains("dashboard-page")) return "dashboard";
    return "";
}

function applyShellChrome(kind) {
    SHELL_PAGE_CLASSES.forEach(function (cls) {
        document.body.classList.remove(cls);
    });
    document.documentElement.classList.remove("ticket-detail-html");
    if (kind === "ticket") {
        document.body.classList.add("ticket-detail-page");
        document.documentElement.classList.add("ticket-detail-html");
    } else if (kind === "kb") {
        document.body.classList.add("kb-page", "kb-search-page");
    } else if (kind === "settings") {
        document.body.classList.add("settings-page");
    } else if (kind === "dashboard") {
        document.body.classList.add("dashboard-page");
    }
}

function updateActiveNav() {
    var path = (location.pathname || "/").replace(/\/+$/, "") || "/";
    var key = "";
    if (path === "/tickets/dashboard" || path.indexOf("/tickets/dashboard/") === 0) key = "dashboard";
    else if (path === "/tickets/settings" || path.indexOf("/tickets/settings/") === 0) key = "settings";
    else if (path === "/news" || path.indexOf("/news/") === 0) key = "news";
    else if (path === "/kb" || path.indexOf("/kb/") === 0) key = "kb";
    else if (path === "/shifts" || path.indexOf("/shifts/") === 0) key = "shifts";
    else if (path === "/tickets" || path.indexOf("/tickets/") === 0) key = "tickets";
    document.querySelectorAll("#sidebar .sidebar-nav a[data-nav-key]").forEach(function (anchor) {
        var on = anchor.getAttribute("data-nav-key") === key;
        anchor.classList.toggle("active", on);
        if (on) anchor.setAttribute("aria-current", "page");
        else anchor.removeAttribute("aria-current");
    });
}
window.updateActiveNav = updateActiveNav;
updateActiveNav();

// One in-shell swap into #shell-content at a time. A second menu or ticket
// click while that request is open used to start another hop and leave a
// half-swapped pane. Modified clicks and Dashboard are not part of this lock.
var activeShellSwap = 0;
var shellSwapSerial = 0;
var shellSwapTimer = null;
var SHELL_SWAP_STALL_MS = 30000;

function eventElement(event) {
    var node = event && event.target;
    if (!node) return null;
    if (node.nodeType === 1) return node;
    return node.parentElement || null;
}

function isPlainPrimaryClick(event) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
    return event.button === 0;
}

function isShellContentTarget(evt) {
    var target = evt && evt.detail && evt.detail.target;
    return !!(target && target.id === "shell-content");
}

function shellSwapHref(elt) {
    if (!elt || !elt.getAttribute) return "";
    return elt.getAttribute("hx-get") || elt.getAttribute("href") || elt.getAttribute("data-href") || "";
}

function releaseShellSwap(token) {
    if (!token || token !== activeShellSwap) return;
    activeShellSwap = 0;
    if (shellSwapTimer) {
        clearTimeout(shellSwapTimer);
        shellSwapTimer = null;
    }
    if (typeof window.clearShellSwapSkeleton === "function") window.clearShellSwapSkeleton();
}

function releaseShellSwapFromEvent(evt) {
    var xhr = evt && evt.detail && evt.detail.xhr;
    var token = xhr && xhr.__shellSwapToken;
    releaseShellSwap(token || activeShellSwap);
}

function armShellSwapLock(evt) {
    if (!isShellContentTarget(evt)) return;
    shellSwapSerial += 1;
    var token = shellSwapSerial;
    activeShellSwap = token;
    var xhr = evt.detail && evt.detail.xhr;
    if (xhr) xhr.__shellSwapToken = token;
    if (shellSwapTimer) clearTimeout(shellSwapTimer);
    shellSwapTimer = setTimeout(function () {
        releaseShellSwap(token);
    }, SHELL_SWAP_STALL_MS);
    if (typeof window.armShellSwapSkeleton === "function") {
        window.armShellSwapSkeleton(shellSwapHref(evt.detail.elt));
    }
}

document.body.addEventListener("htmx:beforeRequest", armShellSwapLock);
document.body.addEventListener("htmx:afterSettle", function (evt) {
    if (!isShellContentTarget(evt)) return;
    releaseShellSwapFromEvent(evt);
});
document.body.addEventListener("htmx:responseError", function (evt) {
    if (!isShellContentTarget(evt)) return;
    releaseShellSwapFromEvent(evt);
});
document.body.addEventListener("htmx:sendError", function (evt) {
    if (!isShellContentTarget(evt)) return;
    releaseShellSwapFromEvent(evt);
});
document.body.addEventListener("htmx:timeout", function (evt) {
    if (!isShellContentTarget(evt)) return;
    releaseShellSwapFromEvent(evt);
});
document.body.addEventListener("htmx:sendAbort", function (evt) {
    if (!isShellContentTarget(evt)) return;
    releaseShellSwapFromEvent(evt);
});
document.body.addEventListener("htmx:swapError", function (evt) {
    if (!isShellContentTarget(evt)) return;
    releaseShellSwapFromEvent(evt);
});
document.body.addEventListener("htmx:abort", function (evt) {
    var node = evt.target;
    if (node && node.id === "shell-content") releaseShellSwap(activeShellSwap);
});
document.body.addEventListener("htmx:historyRestore", function () {
    releaseShellSwap(activeShellSwap);
});

// Capture so a second plain click never reaches the shell-nav / ticket-open
// triggers. Ctrl/cmd/shift/alt-click still follows the real href.
document.addEventListener("click", function (event) {
    if (!activeShellSwap || !isPlainPrimaryClick(event)) return;
    var el = eventElement(event);
    if (!el || !el.closest) return;
    var link = el.closest("a[data-shell-nav]");
    var row = el.closest(".clickable-row");
    if (row && el.closest("button, input, select, textarea, form, .action-cell")) row = null;
    if (row && (row.getAttribute("hx-target") !== "#shell-content" || !row.getAttribute("hx-get"))) row = null;
    if (!link && !row) return;
    event.preventDefault();
    event.stopPropagation();
}, true);

// Plain left-clicks on menu links swap #shell-content. Modified clicks keep
// the real href so new tabs and no-JS still load a full document.
document.addEventListener("click", function (event) {
    var link = event.target && event.target.closest ? event.target.closest("a[data-shell-nav]") : null;
    if (!link) return;
    if (!isPlainPrimaryClick(event)) return;
    if (!window.htmx || !document.getElementById("shell-content")) return;
    // Dashboard stays a full document, including Back from a later menu page.
    if (document.body.classList.contains("dashboard-page")) return;
    if (activeShellSwap) {
        event.preventDefault();
        return;
    }
    var data = link["htmx-internal-data"];
    if (!data || !data.listenerInfos || !data.listenerInfos.length) return;
    event.preventDefault();
    if (typeof window.closeSidebar === "function") window.closeSidebar();
    window.htmx.trigger(link, "shell-nav");
});

function remountShellPage(kind) {
    if (kind === "ticket") return;
    if (kind === "tickets" && typeof window.mountTicketListWS === "function") {
        window.mountTicketListWS();
    }
    if (kind === "kb" && typeof window.mountKbSearch === "function") {
        window.mountKbSearch();
    }
}

window.addEventListener("pageshow", function (evt) {
    if (!evt.persisted) return;
    // bfcache restores a dead in-flight XHR. Drop the lock with the skeleton.
    releaseShellSwap(activeShellSwap);
    updateActiveNav();
    var kind = shellPageKindFromDom();
    if (kind === "ticket" && typeof window.mountTicketChat === "function") {
        window.mountTicketChat();
        return;
    }
    remountShellPage(kind);
});

function canonicalShellPath(path) {
    try {
        var url = new URL(path, location.origin);
        var pathname = url.pathname.replace(/\/+$/, "") || "/";
        return pathname + url.search;
    } catch (e) {
        return "";
    }
}

function shellPaneEtag(kind) {
    var ids = {
        news: "news-shell-pane",
        kb: "kb-shell-pane",
        settings: "settings-shell-pane",
        shifts: "shifts-shell-pane"
    };
    var id = ids[kind];
    if (!id) return "";
    var el = document.getElementById(id);
    return el ? (el.getAttribute("data-etag") || "") : "";
}

// Revalidate the pane already on screen. A different destination must not
// send If-None-Match: a 304 would keep the previous pane's HTML.
function attachShellPaneEtag(evt) {
    var target = evt.detail && evt.detail.target;
    if (!target || target.id !== "shell-content") return;
    var headers = evt.detail.headers;
    if (!headers || headers["HX-History-Restore-Request"]) return;
    var requested = canonicalShellPath(evt.detail.path || "");
    var here = canonicalShellPath(location.pathname + location.search);
    if (!requested || requested !== here) return;
    var etag = shellPaneEtag(shellPageKindFromDom());
    if (etag) headers["If-None-Match"] = etag;
}

document.body.addEventListener("htmx:beforeSwap", function (evt) {
    var target = evt.detail && evt.detail.target;
    if (!target || target.id !== "shell-content") return;
    var xhr = evt.detail.xhr;
    if (xhr && xhr.status === 304) {
        evt.detail.shouldSwap = false;
        evt.detail.isError = false;
        releaseShellSwapFromEvent(evt);
        return;
    }
    if (!evt.detail.shouldSwap) return;
    var html = evt.detail.serverResponse || "";
    var kind = shellPageKindFromHtml(html);
    // Leaving the locked chat layout: htmx's smooth show:window:top scroll and
    // the document's smooth scroll-behavior run after the swap and flash the list.
    if (kind !== "ticket" && document.body.classList.contains("ticket-detail-page")) {
        useInstantShellScroll();
    }
    applyShellChrome(kind);
    if (typeof window.unmountTicketChat === "function") window.unmountTicketChat();
    // The list socket lives in this document. Replacing the list must not
    // leave its onclose handler reconnecting into an empty shell.
    if (kind !== "tickets" && typeof window.unmountTicketListWS === "function") {
        window.unmountTicketListWS();
    }
    if (kind !== "kb" && typeof window.unmountKbSearch === "function") {
        window.unmountKbSearch();
    }
});

document.body.addEventListener("htmx:beforeSwap", function (evt) {
    if (!isShellContentTarget(evt) || !evt.detail || evt.detail.shouldSwap) return;
    releaseShellSwapFromEvent(evt);
});

document.body.addEventListener("htmx:pushedIntoHistory", function () {
    updateActiveNav();
});

function useInstantShellScroll() {
    var root = document.documentElement;
    var prevCss = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";
    var prevHtmx = window.htmx ? window.htmx.config.scrollBehavior : null;
    if (window.htmx) window.htmx.config.scrollBehavior = "auto";
    setTimeout(function () {
        root.style.scrollBehavior = prevCss;
        if (window.htmx && prevHtmx !== null) window.htmx.config.scrollBehavior = prevHtmx;
    }, 0);
}

document.body.addEventListener("htmx:historyRestore", function () {
    // htmx queues scrollTo(saved) on a timeout. Smooth scrolling animates that
    // restore and flickers the list in under the old chat scroll position.
    useInstantShellScroll();
    var kind = shellPageKindFromDom();
    if (kind) applyShellChrome(kind);
    updateActiveNav();
    // Ticket pane script mounts chat. List and KB mounts are idempotent.
    remountShellPage(kind);
});

document.body.addEventListener('htmx:beforeSwap', (evt) => {
    const target = evt.detail.target;
    if (target && target.tagName) {
        const select = target.tagName.toLowerCase() === 'select' ? target : (typeof target.closest === 'function' ? target.closest('select') : null);
        if (select && select.tomselect) {
            select.tomselect.destroy();
        }
    }
});

document.body.addEventListener('htmx:load', (evt) => {
    const elt = evt.detail.elt;
    initializeChoices(elt);

    // If options inside a select were swapped, re-initialize the parent select
    if (elt && typeof elt.closest === 'function') {
        const parentSelect = elt.closest('select');
        if (parentSelect) {
            initializeChoices(parentSelect);
        }
    }
});

document.body.addEventListener('htmx:configRequest', function (evt) {
    var elt = evt.detail.elt;
    if (!elt) return;
    attachShellPaneEtag(evt);
    if (elt.classList && elt.classList.contains('tickets-filters')) {
        document.body.classList.remove('pause-polling');
    }
    var live = document.getElementById('tickets-live');
    if (!live || elt.id !== 'tickets-live') return;
    var path = evt.detail.path || '';
    if (path.indexOf('append=true') !== -1) return;
    var etag = live.getAttribute('data-etag');
    if (etag) evt.detail.headers['If-None-Match'] = etag;
    
    // Rule A: Requests from #tickets-live always omit loaded_pages.
    // When elt.id === 'tickets-live', the request is either:
    // - Timer poll (every 20s) → should fetch page 1 only (bounded depth)
    // - refreshTickets event (manual dispatch) → should reset to page 1
    //
    // By omitting loaded_pages, server defaults to depth=1, avoiding re-fetch of
    // hundreds of rows after load-more. Load-more rows stay in DOM until full reload.
    //
    // Filter form (.tickets-filters) is a different element, handled earlier in this
    // handler. It also omits loaded_pages, resetting to page 1 on filter change.
});

document.body.addEventListener('htmx:afterSwap', function (evt) {
    // Check if this was a load-more request by checking the URL
    var pathInfo = evt.detail.pathInfo;
    if (!pathInfo || !pathInfo.requestPath) return;
    
    // If this was an append=true request (load-more), update depth and resume polling
    if (pathInfo.requestPath.indexOf('append=true') !== -1) {
        var live = document.getElementById('tickets-live');
        if (!live) return;
        var depth = parseInt(live.getAttribute('data-loaded-pages') || '1', 10);
        if (!depth || depth < 1) depth = 1;
        live.setAttribute('data-loaded-pages', String(depth + 1));
        
        // Resume polling after successful load-more
        document.body.classList.remove('pause-polling');
    }
});

function ticketsLiveSignature(el) {
    if (!el) return '';
    var rows = el.querySelectorAll('#tickets-tbody tr');
    var parts = [el.getAttribute('hx-get') || ''];
    rows.forEach(function (row) {
        var badge = row.querySelector('[class*="badge-"]');
        parts.push(row.getAttribute('data-href') || '');
        parts.push(badge ? badge.className : '');
        parts.push((row.textContent || '').replace(/\s+/g, ' ').trim());
    });
    return parts.join('|');
}

// 20s ticket poll: skip the table swap when the visible rows did not change.
document.body.addEventListener('htmx:beforeSwap', function (evt) {
    var target = evt.detail.target;
    if (!target || target.id !== 'tickets-live') return;
    var xhr = evt.detail.xhr;
    if (xhr && (xhr.status === 304 || xhr.status === 204)) {
        evt.detail.shouldSwap = false;
        evt.detail.isError = false;
        return;
    }
    if (!xhr || typeof xhr.responseText !== 'string') return;
    var doc = new DOMParser().parseFromString(xhr.responseText, 'text/html');
    var incoming = doc.getElementById('tickets-live');
    if (!incoming) return;
    if (ticketsLiveSignature(incoming) === ticketsLiveSignature(target)) {
        evt.detail.shouldSwap = false;
    }
});
