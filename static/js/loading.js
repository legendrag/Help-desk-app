/**
 * Global Loading Indicators
 * Top progress bar + button spinners for HTMX, native forms, and navigation.
 * Every start path has a matching cleanup (success, error, abort, timeout, bfcache).
 *
 * Slow-network note: full-page navigations only show the progress bar and a soft
 * "is-navigating" cue — they do NOT hard-disable the page. A short watchdog
 * unlocks the UI if the document never unloads (hung request / cancelled nav).
 */

document.addEventListener('DOMContentLoaded', function() {
    const progressBar = document.getElementById('global-progress-bar');
    const PAGE_LOADING_KEY = 'mlamehticket-page-loading';
    const NAV_STALL_MS = 10000;      // unlock if full-page nav never leaves
    const DOWNLOAD_SAFETY_MS = 60000;
    const HTMX_STALL_MS = 30000;

    let activeRequests = 0;
    let progressTimer = null;
    let downloadWatchers = [];
    let navStallTimer = null;
    let htmxStallTimers = new WeakMap();
    let fullPageNavPending = false;
    // Track in-flight HTMX triggers so success/error/abort only clean up once
    const inFlight = new WeakSet();

    function clearProgressTimer() {
        if (progressTimer) {
            clearTimeout(progressTimer);
            progressTimer = null;
        }
    }

    function clearDownloadWatchers() {
        downloadWatchers.forEach(function(id) {
            clearInterval(id);
            clearTimeout(id);
        });
        downloadWatchers = [];
    }

    function clearNavStallTimer() {
        if (navStallTimer) {
            clearTimeout(navStallTimer);
            navStallTimer = null;
        }
    }

    function markFullPageLoading() {
        try {
            sessionStorage.setItem(PAGE_LOADING_KEY, '1');
        } catch (e) { /* private mode */ }
    }

    function clearFullPageLoadingFlag() {
        try {
            sessionStorage.removeItem(PAGE_LOADING_KEY);
        } catch (e) { /* private mode */ }
    }

    function consumeFullPageLoadingFlag() {
        try {
            const flagged = sessionStorage.getItem(PAGE_LOADING_KEY) === '1';
            if (flagged) sessionStorage.removeItem(PAGE_LOADING_KEY);
            return flagged;
        } catch (e) {
            return false;
        }
    }

    function isReloadNavigation() {
        try {
            const entries = performance.getEntriesByType('navigation');
            if (entries && entries[0]) return entries[0].type === 'reload';
            if (performance.navigation) return performance.navigation.type === 1;
        } catch (e) { /* ignore */ }
        return false;
    }

    function showProgressNow() {
        if (!progressBar) return;
        clearProgressTimer();
        progressBar.classList.remove('finished');
        progressBar.classList.add('loading');
    }

    function startProgress(options) {
        const immediate = options && options.immediate;
        activeRequests++;
        if (activeRequests === 1 && progressBar) {
            if (immediate) {
                showProgressNow();
            } else {
                progressTimer = setTimeout(function() {
                    progressBar.classList.remove('finished');
                    progressBar.classList.add('loading');
                }, 300);
            }
        }
    }

    function finishProgress() {
        activeRequests = Math.max(0, activeRequests - 1);
        if (activeRequests === 0 && progressBar) {
            clearProgressTimer();

            if (progressBar.classList.contains('loading')) {
                progressBar.classList.remove('loading');
                progressBar.classList.add('finished');

                setTimeout(function() {
                    progressBar.classList.remove('finished');
                }, 400);
            } else {
                progressBar.classList.remove('loading', 'finished');
            }
        }
    }

    function resetProgress() {
        activeRequests = 0;
        clearProgressTimer();
        clearDownloadWatchers();
        clearNavStallTimer();
        fullPageNavPending = false;
        if (progressBar) {
            progressBar.classList.remove('loading', 'finished');
        }
        if (window.navigationSpinnerTimer) {
            clearTimeout(window.navigationSpinnerTimer);
            window.navigationSpinnerTimer = null;
        }
    }

    function isExcluded(el) {
        if (!el) return true;
        if (el.classList && el.classList.contains('chat-send-btn')) return true;
        if (el.hasAttribute('data-no-loading')) return true;
        if (el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'search')) {
            const trigger = el.getAttribute('hx-trigger') || '';
            if (trigger.includes('keyup') || trigger.includes('input')) return true;
        }
        return false;
    }

    function resolveButton(btn) {
        if (!btn) return null;
        if (btn.tagName === 'FORM') {
            return btn.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
        }
        return btn;
    }

    function isButtonLike(el) {
        if (!el) return false;
        return (
            el.tagName === 'BUTTON' ||
            (el.tagName === 'INPUT' && (el.type === 'submit' || el.type === 'button')) ||
            el.classList.contains('btn') ||
            el.classList.contains('button') ||
            el.classList.contains('settings-tab')
        );
    }

    function disableButton(btn) {
        if (!btn || isExcluded(btn)) return;

        const targetBtn = resolveButton(btn);
        if (!targetBtn || isExcluded(targetBtn)) return;

        // Only hard-disable real buttons/inputs — never lock links/rows
        // (that freezes the UI on slow networks when the document never unloads).
        if (!isButtonLike(targetBtn)) {
            targetBtn.classList.add('is-navigating');
            return;
        }

        if (targetBtn.classList.contains('btn-loading')) return;

        targetBtn.style.minWidth = targetBtn.offsetWidth + 'px';
        targetBtn.style.minHeight = targetBtn.offsetHeight + 'px';
        targetBtn.classList.add('btn-loading');
        targetBtn.disabled = true;
        targetBtn.setAttribute('aria-busy', 'true');
    }

    function enableButton(btn) {
        if (!btn) return;

        const targetBtn = resolveButton(btn);
        if (!targetBtn) return;

        targetBtn.classList.remove('is-navigating');

        if (isButtonLike(targetBtn)) {
            targetBtn.classList.remove('btn-loading');
            targetBtn.disabled = false;
            targetBtn.style.minWidth = '';
            targetBtn.style.minHeight = '';
            targetBtn.removeAttribute('aria-busy');
        }
    }

    function clearAllButtonLoading() {
        document.querySelectorAll('.btn-loading').forEach(function(el) {
            enableButton(el);
        });
        document.querySelectorAll('.is-navigating').forEach(function(el) {
            el.classList.remove('is-navigating');
        });
        // Legacy cleanup if any old pointer-events locks remain
        document.querySelectorAll('[data-original-opacity]').forEach(function(el) {
            el.style.opacity = el.dataset.originalOpacity || '';
            el.style.pointerEvents = '';
            delete el.dataset.originalOpacity;
        });
    }

    function cleanupRequest(elt) {
        if (elt && inFlight.has(elt)) {
            inFlight.delete(elt);
            const stall = htmxStallTimers.get(elt);
            if (stall) {
                clearTimeout(stall);
                htmxStallTimers.delete(elt);
            }
            finishProgress();
            enableButton(elt);
            return;
        }
        if (!elt) {
            finishProgress();
        }
    }

    function getNavOverlay() {
        return document.getElementById('page-nav-overlay');
    }

    function showNavOverlay() {
        const overlay = getNavOverlay();
        if (!overlay) return;
        overlay.hidden = false;
        overlay.setAttribute('aria-hidden', 'false');
        overlay.classList.add('is-visible');
    }

    function hideNavOverlay() {
        const overlay = getNavOverlay();
        if (!overlay) return;
        overlay.classList.remove('is-visible');
        overlay.hidden = true;
        overlay.setAttribute('aria-hidden', 'true');
    }

    function setPageNavigating(on) {
        document.body.classList.toggle('is-page-navigating', !!on);
        if (on) {
            showNavOverlay();
        } else {
            hideNavOverlay();
        }
    }

    function clearLoadingUI() {
        resetProgress();
        clearAllButtonLoading();
        clearFullPageLoadingFlag();
        setPageNavigating(false);
    }

    /**
     * Start a full-page navigation loading state.
     * @returns {boolean} false if a nav is already pending (spam ignored)
     */
    function beginFullPageNavigation(target) {
        // Anti-spam: ignore further card/link clicks while a nav is in flight.
        // Stall watchdog below unlocks after NAV_STALL_MS so the UI never freezes forever.
        if (fullPageNavPending) {
            return false;
        }

        fullPageNavPending = true;
        if (target) {
            target.classList.add('is-navigating');
        }
        // Paint press state + overlay before any navigation work
        setPageNavigating(true);
        markFullPageLoading();
        startProgress({ immediate: true });

        clearNavStallTimer();
        navStallTimer = setTimeout(function() {
            // Still on this document → navigation stalled or was cancelled
            if (fullPageNavPending && !document.hidden) {
                fullPageNavPending = false;
                setPageNavigating(false);
                clearFullPageLoadingFlag();
                clearAllButtonLoading();
                activeRequests = 0;
                clearProgressTimer();
                if (progressBar) {
                    progressBar.classList.remove('loading', 'finished');
                }
            }
        }, NAV_STALL_MS);
        return true;
    }

    function reloadWithLoading() {
        beginFullPageNavigation(null);
        window.location.reload();
    }

    // Expose for maintenance export, reload triggers, and other manual flows
    window.startProgress = startProgress;
    window.finishProgress = finishProgress;
    window.clearLoadingUI = clearLoadingUI;
    window.reloadWithLoading = reloadWithLoading;
    window.isPageNavigating = function() { return fullPageNavPending; };

    function shouldTrackElement(elt) {
        return !isExcluded(elt);
    }

    function shouldDisableElement(elt) {
        if (!elt) return false;
        // HTMX: only spinner-disable real buttons/forms, soft-cue links/rows
        return (
            elt.tagName === 'BUTTON' ||
            elt.tagName === 'FORM' ||
            elt.tagName === 'A' ||
            elt.tagName === 'TR' ||
            isButtonLike(elt)
        );
    }

    // --- Arrival loading after sidebar nav / refresh ---
    if (consumeFullPageLoadingFlag() || isReloadNavigation()) {
        startProgress({ immediate: true });
        if (document.readyState === 'complete') {
            finishProgress();
        } else {
            window.addEventListener('load', function() {
                finishProgress();
            }, { once: true });
        }
    }

    // --- HTMX Hooks ---
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        const elt = evt.detail.elt;
        if (!shouldTrackElement(elt)) return;
        if (elt && inFlight.has(elt)) return;
        if (elt) inFlight.add(elt);
        startProgress();
        if (shouldDisableElement(elt)) {
            disableButton(elt);
        }
        // Absolute safety: unlock if HTMX never settles (bad network / hung XHR)
        if (elt) {
            const prev = htmxStallTimers.get(elt);
            if (prev) clearTimeout(prev);
            htmxStallTimers.set(elt, setTimeout(function() {
                if (inFlight.has(elt)) {
                    cleanupRequest(elt);
                }
            }, HTMX_STALL_MS));
        }
    });

    function onHtmxSettled(evt) {
        const elt = evt.detail.elt;
        if (!shouldTrackElement(elt)) return;
        cleanupRequest(elt);
    }

    document.body.addEventListener('htmx:afterRequest', onHtmxSettled);
    document.body.addEventListener('htmx:responseError', onHtmxSettled);
    document.body.addEventListener('htmx:sendError', onHtmxSettled);
    document.body.addEventListener('htmx:abort', onHtmxSettled);
    document.body.addEventListener('htmx:timeout', onHtmxSettled);

    document.body.addEventListener('htmx:historyRestore', function() {
        clearLoadingUI();
    });

    function watchForDownload(btnEl) {
        document.cookie = 'fileDownload=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';

        const checkCookie = setInterval(function() {
            if (document.cookie.includes('fileDownload=true')) {
                clearInterval(checkCookie);
                document.cookie = 'fileDownload=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
                finishProgress();
                if (btnEl) enableButton(btnEl);
            }
        }, 500);
        downloadWatchers.push(checkCookie);

        const safety = setTimeout(function() {
            clearInterval(checkCookie);
            finishProgress();
            if (btnEl) enableButton(btnEl);
        }, DOWNLOAD_SAFETY_MS);
        downloadWatchers.push(safety);
    }

    // --- Native Form Submit Hooks ---
    document.addEventListener('submit', function(evt) {
        const form = evt.target;
        if (
            form.hasAttribute('hx-post') ||
            form.hasAttribute('hx-get') ||
            form.hasAttribute('hx-put') ||
            form.hasAttribute('hx-delete')
        ) {
            return;
        }

        if (!isExcluded(form)) {
            beginFullPageNavigation(form);
            disableButton(form);
            watchForDownload(form);
        }
    });

    // --- Standard Navigation Hooks (including sidebar / cards / back links) ---
    // Capture phase so we can block spam before other handlers (e.g. row → location.href)
    document.addEventListener('click', function(evt) {
        const target = evt.target.closest('a[href], .clickable-row');
        if (!target) return;

        if (target.classList.contains('clickable-row')) {
            const interactive = evt.target.closest('button, input, select, textarea, form, .action-cell');
            if (interactive) return;
        }

        if (
            target.hasAttribute('hx-get') ||
            target.hasAttribute('hx-post') ||
            target.hasAttribute('hx-put') ||
            target.hasAttribute('hx-delete')
        ) {
            return;
        }

        const href = target.getAttribute('href') || target.dataset.href;
        if (!href || href.startsWith('#') || href.startsWith('javascript:')) {
            return;
        }

        if (target.getAttribute('target') === '_blank') {
            return;
        }

        if (target.hasAttribute('download') || target.hasAttribute('data-no-loading')) {
            return;
        }

        if (target.classList.contains('menu-btn-universal') || target.classList.contains('theme-switch')) {
            return;
        }

        // Same-page hash-only navigations: skip loading UI
        try {
            const url = new URL(href, window.location.origin);
            if (
                url.origin === window.location.origin &&
                url.pathname === window.location.pathname &&
                url.search === window.location.search &&
                url.hash
            ) {
                return;
            }
        } catch (e) { /* continue */ }

        // Already navigating → swallow spam clicks (unlocks via stall watchdog if hung)
        if (fullPageNavPending) {
            evt.preventDefault();
            evt.stopPropagation();
            return;
        }

        beginFullPageNavigation(target);
    }, true);

    // Keyboard refresh (F5 / Ctrl+R / Cmd+R)
    document.addEventListener('keydown', function(evt) {
        const key = evt.key;
        const isF5 = key === 'F5';
        const isSoftReload = (key === 'r' || key === 'R') && (evt.ctrlKey || evt.metaKey);
        if (!isF5 && !isSoftReload) return;
        beginFullPageNavigation(null);
    });

    // If the document never unloads (stall) but tab becomes visible again, unlock
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden && fullPageNavPending) {
            // Give a moment in case unload is mid-flight, then unlock if still here
            setTimeout(function() {
                if (fullPageNavPending && !document.hidden) {
                    clearLoadingUI();
                }
            }, 500);
        }
    });

    // Leaving the page: keep the flag for the next document's arrival progress
    window.addEventListener('pagehide', function(evt) {
        clearNavStallTimer();
        fullPageNavPending = false;
        if (evt.persisted) {
            // Going into bfcache — unlock so Back doesn't restore a frozen UI
            clearLoadingUI();
        }
    });

    // Reset sticky loading UI when returning via bfcache / back-forward
    window.addEventListener('pageshow', function(evt) {
        if (evt.persisted) {
            clearLoadingUI();
        } else {
            clearProgressTimer();
            clearNavStallTimer();
            fullPageNavPending = false;
            if (window.navigationSpinnerTimer) {
                clearTimeout(window.navigationSpinnerTimer);
                window.navigationSpinnerTimer = null;
            }
        }
    });
});
