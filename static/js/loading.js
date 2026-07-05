/**
 * Global Loading Indicators
 * Handles top progress bar and automatic button spinners for all HTMX and native form requests.
 */

document.addEventListener('DOMContentLoaded', function() {
    const progressBar = document.getElementById('global-progress-bar');
    let activeRequests = 0;
    let progressTimer = null;

    // --- Progress Bar Logic ---
    function startProgress() {
        activeRequests++;
        if (activeRequests === 1 && progressBar) {
            // Debounce the progress bar for very fast requests
            progressTimer = setTimeout(() => {
                progressBar.classList.remove('finished');
                progressBar.classList.add('loading');
            }, 300);
        }
    }

    function finishProgress() {
        activeRequests = Math.max(0, activeRequests - 1);
        if (activeRequests === 0 && progressBar) {
            if (progressTimer) clearTimeout(progressTimer);
            
            // If it was already showing, animate to 100% then fade out
            if (progressBar.classList.contains('loading')) {
                progressBar.classList.remove('loading');
                progressBar.classList.add('finished');
                
                // Remove the finished class after the fade transition completes
                setTimeout(() => {
                    progressBar.classList.remove('finished');
                }, 400); // 400ms matches the CSS transition duration
            }
        }
    }

    // --- Button Spinner Logic ---
    function isExcluded(el) {
        if (!el) return true;
        // Exclude chat send button (has own optimistic UI)
        if (el.classList && el.classList.contains('chat-send-btn')) return true;
        // Exclude explicitly ignored elements
        if (el.hasAttribute('data-no-loading')) return true;
        // Exclude search inputs that trigger on typing
        if (el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'search')) {
            const trigger = el.getAttribute('hx-trigger') || '';
            if (trigger.includes('keyup') || trigger.includes('input')) return true;
        }
        return false;
    }

    function disableButton(btn) {
        if (!btn || isExcluded(btn) || btn.disabled) return;
        
        // Find the actual button element
        const targetBtn = btn.tagName === 'FORM' ? btn.querySelector('button[type="submit"]') : btn;
        
        if (targetBtn && !isExcluded(targetBtn)) {
            // If it's a real button, apply full loading styles
            if (targetBtn.tagName === 'BUTTON' || targetBtn.tagName === 'INPUT' || targetBtn.classList.contains('btn')) {
                if (targetBtn.classList.contains('btn-loading')) return;
                
                // Fix dimensions so button doesn't shrink when text is hidden
                targetBtn.style.minWidth = `${targetBtn.offsetWidth}px`;
                targetBtn.style.minHeight = `${targetBtn.offsetHeight}px`;
                
                targetBtn.classList.add('btn-loading');
                targetBtn.disabled = true;
            } else {
                // If it's a table row or simple link, just dim and disable pointer events
                if (targetBtn.style.pointerEvents === 'none') return;
                targetBtn.dataset.originalOpacity = targetBtn.style.opacity || '';
                targetBtn.style.opacity = '0.6';
                targetBtn.style.pointerEvents = 'none';
            }
        }
    }

    function enableButton(btn) {
        if (!btn || isExcluded(btn)) return;
        
        const targetBtn = btn.tagName === 'FORM' ? btn.querySelector('button[type="submit"]') : btn;
        
        if (targetBtn) {
            if (targetBtn.tagName === 'BUTTON' || targetBtn.tagName === 'INPUT' || targetBtn.classList.contains('btn')) {
                targetBtn.classList.remove('btn-loading');
                targetBtn.disabled = false;
                targetBtn.style.minWidth = '';
                targetBtn.style.minHeight = '';
            } else {
                targetBtn.style.opacity = targetBtn.dataset.originalOpacity || '';
                targetBtn.style.pointerEvents = '';
            }
        }
    }

    // --- HTMX Hooks ---
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        const elt = evt.detail.elt;
        if (!isExcluded(elt)) {
            startProgress();
            
            // If the triggering element is a button, or it's a form, show spinner
            if (elt.tagName === 'BUTTON' || elt.tagName === 'FORM' || elt.tagName === 'A' || elt.tagName === 'TR') {
                disableButton(elt);
            }
        }
    });

    document.body.addEventListener('htmx:afterRequest', function(evt) {
        const elt = evt.detail.elt;
        if (!isExcluded(elt)) {
            finishProgress();
            
            if (elt.tagName === 'BUTTON' || elt.tagName === 'FORM' || elt.tagName === 'A' || elt.tagName === 'TR') {
                enableButton(elt);
            }
        }
    });
    
    // Also handle htmx:responseError and htmx:sendError just in case afterRequest doesn't fire
    document.body.addEventListener('htmx:responseError', function(evt) {
        const elt = evt.detail.elt;
        if (!isExcluded(elt)) {
            finishProgress();
            enableButton(elt);
        }
    });
    
    document.body.addEventListener('htmx:sendError', function(evt) {
        const elt = evt.detail.elt;
        if (!isExcluded(elt)) {
            finishProgress();
            enableButton(elt);
        }
    });

    function watchForDownload(btnEl) {
        // Clear any old cookie
        document.cookie = "fileDownload=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        
        const checkCookie = setInterval(() => {
            if (document.cookie.includes('fileDownload=true')) {
                clearInterval(checkCookie);
                // Clear the cookie again
                document.cookie = "fileDownload=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                finishProgress();
                if (btnEl) enableButton(btnEl);
                if (window.navigationSpinnerTimer) clearTimeout(window.navigationSpinnerTimer);
                const overlay = document.getElementById('global-spinner-overlay');
                if (overlay) overlay.classList.remove('active');
            }
        }, 500);
        
        // Safety timeout (60 seconds) in case of silent failures
        setTimeout(() => {
            clearInterval(checkCookie);
            finishProgress();
            if (btnEl) enableButton(btnEl);
            const overlay = document.getElementById('global-spinner-overlay');
            if (overlay) overlay.classList.remove('active');
        }, 60000);
    }

    // --- Native Form Submit Hooks ---
    document.addEventListener('submit', function(evt) {
        const form = evt.target;
        // Ignore HTMX forms as they are handled by HTMX events
        if (form.hasAttribute('hx-post') || form.hasAttribute('hx-get') || form.hasAttribute('hx-put') || form.hasAttribute('hx-delete')) {
            return;
        }
        
        if (!isExcluded(form)) {
            startProgress();
            disableButton(form);
            watchForDownload(form);
        }
    });

    // --- Standard Navigation Hooks ---
    // Trigger progress bar on full page reloads for tickets, KBs, and announcements
    document.addEventListener('click', function(evt) {
        // Find closest anchor or clickable row
        const target = evt.target.closest('a[href], .clickable-row');
        if (!target) return;
        
        // Exclude HTMX triggers (handled above)
        if (target.hasAttribute('hx-get') || target.hasAttribute('hx-post') || target.hasAttribute('hx-put') || target.hasAttribute('hx-delete')) {
            return;
        }

        // Exclude javascript pseudo-links and anchor hashes
        const href = target.getAttribute('href') || target.dataset.href;
        if (!href || href.startsWith('#') || href.startsWith('javascript:')) {
            return;
        }

        // Exclude new tab/window links
        if (target.getAttribute('target') === '_blank') {
            return;
        }
        
        // Exclude explicit downloads or exclusions
        if (target.hasAttribute('download') || target.hasAttribute('data-no-loading')) {
            return;
        }
        
        // Exclude sidebar toggle or layout buttons
        if (target.classList.contains('menu-btn-universal') || target.classList.contains('theme-switch')) {
            return;
        }

        // Show the global spinner overlay for all full-page navigations with a debounce
        const overlay = document.getElementById('global-spinner-overlay');
        if (overlay) {
            window.navigationSpinnerTimer = setTimeout(() => {
                overlay.classList.add('active');
            }, 300);
        }
        
        // Only run the top progress bar and disable effects for non-sidebar links
        if (!target.closest('.sidebar')) {
            startProgress();
            disableButton(target);
        }
        
        // Watch for file downloads in case this link returns a file
        watchForDownload(target);
    });
});
