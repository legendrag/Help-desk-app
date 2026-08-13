/**
 * PWA bootstrap: register SW early, capture beforeinstallprompt immediately,
 * and show Install controls when the site is not already installed.
 */
(function () {
    const SW_URL = "/sw.js";
    let deferredPrompt = null;
    let bipListenerBound = false;

    function isStandalone() {
        return (
            window.matchMedia("(display-mode: standalone)").matches ||
            window.matchMedia("(display-mode: window-controls-overlay)").matches ||
            window.navigator.standalone === true
        );
    }

    function installButtons() {
        return Array.from(document.querySelectorAll("[data-pwa-install]"));
    }

    function setInstallVisible(visible) {
        installButtons().forEach((btn) => {
            btn.hidden = !visible;
            btn.setAttribute("aria-hidden", visible ? "false" : "true");
        });
    }

    function registerServiceWorker() {
        if (!("serviceWorker" in navigator)) return;
        navigator.serviceWorker.register(SW_URL).catch((err) => {
            console.warn("[PWA] Service worker registration failed:", err);
        });
    }

    async function promptInstall(event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        if (!deferredPrompt) {
            const msg =
                (window.I18N && window.I18N.installViaBrowser) ||
                "Use Chrome menu (⋮) → Cast, save and share → Install page as app…";
            window.alert(msg);
            return;
        }

        const btn = event && event.currentTarget;
        if (btn) btn.disabled = true;

        const promptEvent = deferredPrompt;
        deferredPrompt = null;

        try {
            promptEvent.prompt();
            const choice = await promptEvent.userChoice;
            if (choice && choice.outcome === "accepted") {
                setInstallVisible(false);
            }
            // Dismissed: keep the button so the user can try browser menu / wait for BIP again.
        } catch (err) {
            console.warn("[PWA] Install prompt failed:", err);
        } finally {
            if (btn) btn.disabled = false;
            if (!isStandalone()) {
                setInstallVisible(true);
            }
        }
    }

    function bindInstallButtons() {
        installButtons().forEach((btn) => {
            if (btn.dataset.pwaBound === "1") return;
            btn.dataset.pwaBound = "1";
            btn.addEventListener("click", promptInstall);
        });
    }

    function onBeforeInstallPrompt(event) {
        event.preventDefault();
        deferredPrompt = event;
        bindInstallButtons();
        if (!isStandalone()) {
            setInstallVisible(true);
            console.info("[PWA] beforeinstallprompt received — native install available");
        }
    }

    // Capture BIP as early as possible (before DOMContentLoaded) so we do not miss it.
    if (!bipListenerBound) {
        bipListenerBound = true;
        window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
        window.addEventListener("appinstalled", () => {
            deferredPrompt = null;
            setInstallVisible(false);
            document.documentElement.dataset.pwaDisplay = "standalone";
            console.info("[PWA] App installed");
        });
    }

    function initDom() {
        bindInstallButtons();
        registerServiceWorker();

        if (isStandalone()) {
            setInstallVisible(false);
            document.documentElement.dataset.pwaDisplay = "standalone";
            return;
        }

        // Always show Install when not installed. Click uses native BIP when
        // available, otherwise points the user at Chrome's Install menu.
        setInstallVisible(true);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initDom);
    } else {
        initDom();
    }
})();
