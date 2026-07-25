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
    // Hard cap so a missed cleanup can never leave the bar parked at 80%
    const PROGRESS_MAX_MS = 8000;
    const NAV_CANCEL_MS = 400;

    let activeRequests = 0;
    let progressTimer = null;
    let progressMaxTimer = null;
    let trickleTimer = null;
    let progressValue = 0;
    let downloadWatchers = [];
    let navStallTimer = null;
    let navCancelTimer = null;
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

    function clearProgressMaxTimer() {
        if (progressMaxTimer) {
            clearTimeout(progressMaxTimer);
            progressMaxTimer = null;
        }
    }

    function clearTrickleTimer() {
        if (trickleTimer) {
            clearTimeout(trickleTimer);
            trickleTimer = null;
        }
    }

    function clearNavCancelTimer() {
        if (navCancelTimer) {
            clearTimeout(navCancelTimer);
            navCancelTimer = null;
        }
    }

    function setProgressWidth(pct) {
        progressValue = Math.max(0, Math.min(100, pct));
        if (progressBar) {
            progressBar.style.setProperty('--progress', progressValue + '%');
        }
    }

    function armProgressMaxTimer() {
        clearProgressMaxTimer();
        progressMaxTimer = setTimeout(function() {
            if (activeRequests > 0 || (progressBar && progressBar.classList.contains('loading'))) {
                forceFinishProgress();
            }
        }, PROGRESS_MAX_MS);
    }

    /**
     * NProgress-style trickle: quick early jumps, then slower crawl toward ~94%.
     * Never reaches 100% until finish — that snap is the "done" signal.
     */
    function scheduleTrickle() {
        clearTrickleTimer();
        if (!progressBar || !progressBar.classList.contains('loading')) return;

        let delay;
        if (progressValue < 20) delay = 180 + Math.random() * 120;
        else if (progressValue < 40) delay = 280 + Math.random() * 200;
        else if (progressValue < 60) delay = 400 + Math.random() * 300;
        else if (progressValue < 80) delay = 600 + Math.random() * 400;
        else delay = 900 + Math.random() * 600;

        trickleTimer = setTimeout(function() {
            if (!progressBar || !progressBar.classList.contains('loading')) return;

            let step;
            if (progressValue < 20) step = 8 + Math.random() * 10;
            else if (progressValue < 40) step = 4 + Math.random() * 6;
            else if (progressValue < 60) step = 2 + Math.random() * 4;
            else if (progressValue < 80) step = 1 + Math.random() * 2;
            else step = 0.3 + Math.random() * 0.7;

            // Asymptote just under 95% so finish still feels like a completion
            const next = Math.min(94, progressValue + step);
            if (next > progressValue) {
                setProgressWidth(next);
            }
            if (progressValue < 94) {
                scheduleTrickle();
            }
        }, delay);
    }

    function beginBar() {
        if (!progressBar) return;
        clearProgressTimer();
        clearTrickleTimer();
        progressBar.classList.remove('finished');
        // Start at 0 without transition, then animate the first jump
        progressBar.style.transition = 'none';
        setProgressWidth(0);
        progressBar.classList.add('loading');
        // Force reflow so the 0% → first jump animates
        void progressBar.offsetWidth;
        progressBar.style.transition = '';
        setProgressWidth(12 + Math.random() * 8);
        scheduleTrickle();
    }

    function completeBar() {
        if (!progressBar) return;
        clearTrickleTimer();
        clearProgressTimer();
        clearProgressMaxTimer();
        progressBar.classList.remove('loading');
        setProgressWidth(100);
        progressBar.classList.add('finished');
        setTimeout(function() {
            progressBar.classList.remove('finished');
            progressBar.style.transition = 'none';
            setProgressWidth(0);
            void progressBar.offsetWidth;
            progressBar.style.transition = '';
        }, 420);
    }

    function hideBarQuietly() {
        if (!progressBar) return;
        clearTrickleTimer();
        progressBar.classList.remove('loading', 'finished');
        progressBar.style.transition = 'none';
        setProgressWidth(0);
        void progressBar.offsetWidth;
        progressBar.style.transition = '';
    }

    /** Complete the bar to 100% and zero the counter (missed cleanup / hung assets). */
    function forceFinishProgress() {
        clearProgressTimer();
        clearProgressMaxTimer();
        clearTrickleTimer();
        activeRequests = 0;
        if (!progressBar) return;
        if (progressBar.classList.contains('loading')) {
            completeBar();
        } else {
            hideBarQuietly();
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

    function startProgress(options) {
        const immediate = options && options.immediate;
        activeRequests++;
        armProgressMaxTimer();
        if (activeRequests === 1 && progressBar) {
            if (immediate) {
                beginBar();
            } else {
                progressTimer = setTimeout(beginBar, 300);
            }
        }
    }

    function finishProgress() {
        activeRequests = Math.max(0, activeRequests - 1);
        if (activeRequests === 0 && progressBar) {
            clearProgressTimer();
            clearProgressMaxTimer();

            if (progressBar.classList.contains('loading')) {
                completeBar();
            } else {
                hideBarQuietly();
            }
        }
    }

    function resetProgress() {
        activeRequests = 0;
        clearProgressTimer();
        clearProgressMaxTimer();
        clearTrickleTimer();
        clearDownloadWatchers();
        clearNavStallTimer();
        clearNavCancelTimer();
        fullPageNavPending = false;
        hideBarQuietly();
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

    /**
     * Background / automatic HTMX (polling, hx-trigger=load, silent refreshes).
     * These should not drive the top progress bar or disable controls.
     */
    function isAutomaticHtmxRequest(elt, evt) {
        if (!elt) return false;
        if (elt.hasAttribute('data-no-progress')) return true;

        const detail = evt && evt.detail ? evt.detail : {};
        const triggeringEvent = (detail.requestConfig && detail.requestConfig.triggeringEvent)
            || detail.triggeringEvent
            || null;
        const eventType = triggeringEvent && triggeringEvent.type ? triggeringEvent.type : '';

        // App-driven silent refreshes (ticket poll refresh, settings refresh after save)
        if (eventType === 'refreshTickets' || eventType === 'refreshSettings') {
            return true;
        }

        const trigger = elt.getAttribute('hx-trigger') || '';

        // Interval polling: hx-trigger="every 20s ..."
        if (/\bevery\b/i.test(trigger)) {
            // Treat as automatic unless a clear user gesture started it
            if (!triggeringEvent || !/^(click|submit|change|keydown|keyup|input|search)$/i.test(eventType)) {
                return true;
            }
        }

        // Initial page auto-fetch: hx-trigger="load"
        if (/(^|,\s*)load(\s*,|$)/i.test(trigger) || trigger.trim() === 'load') {
            if (!triggeringEvent || eventType === 'load' || eventType === '') {
                return true;
            }
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

    function normalizePathname(pathname) {
        if (!pathname) return '/';
        var path = pathname.split('?')[0].split('#')[0];
        if (path.length > 1 && path.endsWith('/')) {
            path = path.slice(0, -1);
        }
        return path || '/';
    }

    /**
     * Map a destination URL to a skeleton variant id.
     * Match order matters (dashboard/settings before ticket id, kb detail before list).
     */
    function classifyNavSkeleton(href) {
        if (!href) return 'default';
        var path;
        try {
            path = normalizePathname(new URL(href, window.location.origin).pathname);
        } catch (e) {
            return 'default';
        }

        if (path === '/tickets/dashboard') return 'dashboard';
        if (path === '/tickets/settings') return 'settings';
        if (/^\/tickets\/\d+$/.test(path)) return 'ticket-detail';
        if (path === '/tickets') return 'ticket-list';
        if (/^\/kb\/\d+$/.test(path)) return 'kb-detail';
        if (path === '/kb' || path.indexOf('/kb/') === 0) return 'kb-list';
        if (path === '/news' || path.indexOf('/news/') === 0) return 'news-list';
        return 'default';
    }

    function showNavSkeleton(variantId) {
        const overlay = getNavOverlay();
        if (!overlay) return;
        const id = variantId || 'default';
        const screens = overlay.querySelectorAll('[data-skeleton]');
        let matched = false;
        screens.forEach(function(screen) {
            const isMatch = screen.getAttribute('data-skeleton') === id;
            screen.hidden = !isMatch;
            screen.classList.toggle('is-active', isMatch);
            if (isMatch) matched = true;
        });
        if (!matched) {
            const fallback = overlay.querySelector('[data-skeleton="default"]');
            if (fallback) {
                fallback.hidden = false;
                fallback.classList.add('is-active');
            }
        }
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
        overlay.querySelectorAll('[data-skeleton]').forEach(function(screen) {
            screen.hidden = true;
            screen.classList.remove('is-active');
        });
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

    function resolveNavHref(target, href) {
        if (href) return href;
        if (!target) return '';
        if (target.tagName === 'FORM' && target.getAttribute('action')) {
            return target.getAttribute('action');
        }
        return target.getAttribute('href') || target.dataset.href || target.getAttribute('data-href') || '';
    }

    /**
     * Start a full-page navigation loading state.
     * @returns {boolean} false if a nav is already pending (spam ignored)
     */
    function beginFullPageNavigation(target, href) {
        // Anti-spam: ignore further card/link clicks while a nav is in flight.
        // Stall watchdog below unlocks after NAV_STALL_MS so the UI never freezes forever.
        if (fullPageNavPending) {
            return false;
        }

        fullPageNavPending = true;
        if (target) {
            target.classList.add('is-navigating');
            // Nav bar / sidebar selection → close the drawer so the full-screen skeleton shows
            if (target.closest('.sidebar') && typeof window.closeSidebar === 'function') {
                window.closeSidebar();
            }
        }

        const destination = resolveNavHref(target, href);
        showNavSkeleton(classifyNavSkeleton(destination));

        // Paint press state + full-screen skeleton before any navigation work
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
                forceFinishProgress();
            }
        }, NAV_STALL_MS);
        return true;
    }

    function reloadWithLoading() {
        beginFullPageNavigation(null, window.location.href);
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
    // Finish once the document is usable — do NOT wait for window.load.
    // Slow images/analytics/fonts can delay load forever and park the bar at 80%
    // even though the page is already interactive.
    if (consumeFullPageLoadingFlag() || isReloadNavigation()) {
        startProgress({ immediate: true });
        let arrivalFinished = false;
        function completeArrivalProgress() {
            if (arrivalFinished) return;
            arrivalFinished = true;
            finishProgress();
        }
        if (document.readyState === 'complete') {
            completeArrivalProgress();
        } else {
            // Two frames: let the loading class paint, then complete to 100%.
            requestAnimationFrame(function() {
                requestAnimationFrame(completeArrivalProgress);
            });
            // Fallback if rAF is delayed/throttled in background tabs
            setTimeout(completeArrivalProgress, 1500);
        }
    }

    // --- HTMX Hooks ---
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        const elt = evt.detail.elt;
        if (!shouldTrackElement(elt)) return;
        // Polling / hx-load / silent refresh: no top bar, no button lock
        if (isAutomaticHtmxRequest(elt, evt)) return;
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
        if (isAutomaticHtmxRequest(elt, evt)) return;
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
            beginFullPageNavigation(form, form.getAttribute('action') || '');
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

        beginFullPageNavigation(target, href);
    }, true);

    // Keyboard refresh (F5 / Ctrl+R / Cmd+R)
    document.addEventListener('keydown', function(evt) {
        const key = evt.key;
        const isF5 = key === 'F5';
        const isSoftReload = (key === 'r' || key === 'R') && (evt.ctrlKey || evt.metaKey);
        if (!isF5 && !isSoftReload) return;
        beginFullPageNavigation(null, window.location.href);
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

    // Leaving the page: keep the flag for the next document's arrival progress.
    // pagehide also fires when a navigation is attempted then cancelled — in that
    // case the stall timer was cleared and the bar would stay at 80% forever.
    window.addEventListener('pagehide', function(evt) {
        clearNavStallTimer();
        const wasNavigating = fullPageNavPending;
        fullPageNavPending = false;
        if (evt.persisted) {
            // Going into bfcache — unlock so Back doesn't restore a frozen UI
            clearLoadingUI();
            return;
        }
        if (wasNavigating) {
            clearNavCancelTimer();
            navCancelTimer = setTimeout(function() {
                navCancelTimer = null;
                // Still on this document → navigation cancelled / never completed
                if (!document.hidden) {
                    clearFullPageLoadingFlag();
                    clearAllButtonLoading();
                    setPageNavigating(false);
                    forceFinishProgress();
                }
            }, NAV_CANCEL_MS);
        }
    });

    // Reset sticky loading UI when returning via bfcache / back-forward
    window.addEventListener('pageshow', function(evt) {
        if (evt.persisted) {
            clearLoadingUI();
        } else {
            clearProgressTimer();
            clearNavStallTimer();
            clearNavCancelTimer();
            fullPageNavPending = false;
            if (window.navigationSpinnerTimer) {
                clearTimeout(window.navigationSpinnerTimer);
                window.navigationSpinnerTimer = null;
            }
        }
    });
});
