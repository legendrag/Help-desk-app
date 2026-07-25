/**
 * Global Loading Indicators
 * Top progress bar + button spinners for HTMX, native forms, and navigation.
 * Every start path has a matching cleanup (success, error, abort, timeout, bfcache).
 * Also covers sidebar page selection and browser/programmatic refresh.
 */

document.addEventListener('DOMContentLoaded', function() {
    const progressBar = document.getElementById('global-progress-bar');
    const PAGE_LOADING_KEY = 'deskplus-page-loading';
    let activeRequests = 0;
    let progressTimer = null;
    let downloadWatchers = [];
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

    function markFullPageLoading() {
        try {
            sessionStorage.setItem(PAGE_LOADING_KEY, '1');
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

        if (isButtonLike(targetBtn)) {
            if (targetBtn.classList.contains('btn-loading')) return;

            targetBtn.style.minWidth = targetBtn.offsetWidth + 'px';
            targetBtn.style.minHeight = targetBtn.offsetHeight + 'px';
            targetBtn.classList.add('btn-loading');
            targetBtn.disabled = true;
            targetBtn.setAttribute('aria-busy', 'true');
        } else {
            if (targetBtn.style.pointerEvents === 'none') return;
            targetBtn.dataset.originalOpacity = targetBtn.style.opacity || '';
            targetBtn.style.opacity = '0.6';
            targetBtn.style.pointerEvents = 'none';
        }
    }

    function enableButton(btn) {
        if (!btn) return;

        const targetBtn = resolveButton(btn);
        if (!targetBtn) return;

        if (isButtonLike(targetBtn)) {
            targetBtn.classList.remove('btn-loading');
            targetBtn.disabled = false;
            targetBtn.style.minWidth = '';
            targetBtn.style.minHeight = '';
            targetBtn.removeAttribute('aria-busy');
        } else {
            targetBtn.style.opacity = targetBtn.dataset.originalOpacity || '';
            targetBtn.style.pointerEvents = '';
            delete targetBtn.dataset.originalOpacity;
        }
    }

    function clearAllButtonLoading() {
        document.querySelectorAll('.btn-loading').forEach(function(el) {
            enableButton(el);
        });
        document.querySelectorAll('[style*="pointer-events: none"], [style*="pointer-events:none"]').forEach(function(el) {
            if (el.dataset.originalOpacity !== undefined) {
                enableButton(el);
            }
        });
    }

    function cleanupRequest(elt) {
        if (elt && inFlight.has(elt)) {
            inFlight.delete(elt);
            finishProgress();
            enableButton(elt);
            return;
        }
        if (!elt) {
            finishProgress();
        }
    }

    function clearLoadingUI() {
        resetProgress();
        clearAllButtonLoading();
    }

    function reloadWithLoading() {
        markFullPageLoading();
        startProgress({ immediate: true });
        window.location.reload();
    }

    // Expose for maintenance export, reload triggers, and other manual flows
    window.startProgress = startProgress;
    window.finishProgress = finishProgress;
    window.clearLoadingUI = clearLoadingUI;
    window.reloadWithLoading = reloadWithLoading;

    function shouldTrackElement(elt) {
        return !isExcluded(elt);
    }

    function shouldDisableElement(elt) {
        if (!elt) return false;
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
        }, 60000);
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
            // Full-page posts (including sidebar logout) should persist loading into next paint
            markFullPageLoading();
            startProgress({ immediate: true });
            disableButton(form);
            watchForDownload(form);
        }
    });

    // --- Standard Navigation Hooks (including sidebar page selection) ---
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

        // Same-page hash-only or identical path without query change: skip
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
        } catch (e) { /* relative parse issues — continue */ }

        // Full-page navigation: sidebar links, top links, clickable rows
        markFullPageLoading();
        startProgress({ immediate: true });
        disableButton(target);
        watchForDownload(target);
    });

    // Keyboard refresh (F5 / Ctrl+R / Cmd+R) — show bar before unload
    document.addEventListener('keydown', function(evt) {
        const key = evt.key;
        const isF5 = key === 'F5';
        const isSoftReload = (key === 'r' || key === 'R') && (evt.ctrlKey || evt.metaKey);
        if (!isF5 && !isSoftReload) return;
        markFullPageLoading();
        startProgress({ immediate: true });
    });

    // Reset sticky loading UI when returning via bfcache / back-forward
    window.addEventListener('pageshow', function(evt) {
        if (evt.persisted) {
            clearLoadingUI();
        } else {
            clearProgressTimer();
            if (window.navigationSpinnerTimer) {
                clearTimeout(window.navigationSpinnerTimer);
                window.navigationSpinnerTimer = null;
            }
        }
    });
});
