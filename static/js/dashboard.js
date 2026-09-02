/**
 * Dashboard widgets that must re-run after HTMX filter swaps.
 */
(function () {
    var PIE_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4', '#3b82f6', '#14b8a6'];

    function escapeText(value) {
        return String(value == null ? '' : value);
    }

    function initCategoryPie() {
        var dataEl = document.getElementById('category-data');
        var svg = document.getElementById('category-pie');
        var legend = document.getElementById('pie-legend');
        var tooltip = document.getElementById('pie-tooltip');
        var tooltipLabel = document.getElementById('pie-tooltip-label');
        var tooltipVal = document.getElementById('pie-tooltip-val');
        if (!dataEl || !svg || !legend) return;

        while (svg.firstChild) {
            svg.removeChild(svg.firstChild);
        }
        legend.textContent = '';

        var data;
        try {
            data = JSON.parse(dataEl.textContent);
        } catch (e) {
            console.error('Error drawing pie chart:', e);
            return;
        }
        if (!Array.isArray(data)) return;

        var total = data.reduce(function (sum, item) {
            return sum + (item.count || 0);
        }, 0);
        if (total === 0) return;

        var offset = 0;
        data.forEach(function (item, index) {
            if (!item.count) return;
            var percent = (item.count / total) * 100;
            var color = PIE_COLORS[index % PIE_COLORS.length];

            var circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('r', '15.91549430918954');
            circle.setAttribute('cx', '16');
            circle.setAttribute('cy', '16');
            circle.setAttribute('fill', 'none');
            circle.setAttribute('stroke', color);
            circle.setAttribute('stroke-width', '32');
            circle.setAttribute('stroke-dasharray', percent + ' ' + (100 - percent));
            circle.setAttribute('stroke-dashoffset', String(-offset));
            circle.style.transition = 'opacity 0.2s';

            circle.addEventListener('mouseenter', function () {
                if (!tooltip || !tooltipLabel || !tooltipVal) return;
                tooltipLabel.textContent = '';
                var title = document.createElement('div');
                title.style.fontWeight = '600';
                title.style.fontSize = '0.85rem';
                title.textContent = escapeText(item.label);
                tooltipLabel.appendChild(title);
                if (item.department) {
                    var dept = document.createElement('div');
                    dept.style.fontSize = '0.65rem';
                    dept.style.color = 'var(--text-muted)';
                    dept.style.marginTop = '2px';
                    dept.textContent = 'DEPT: ' + escapeText(item.department);
                    tooltipLabel.appendChild(dept);
                }
                tooltipVal.textContent = '';
                var val = document.createElement('div');
                val.style.fontSize = '0.8rem';
                val.style.marginTop = '3px';
                val.textContent = item.count + ' tickets (' + Math.round(percent) + '%)';
                tooltipVal.appendChild(val);
                tooltip.style.opacity = '1';
                circle.style.opacity = '0.8';
            });
            circle.addEventListener('mouseleave', function () {
                if (tooltip) tooltip.style.opacity = '0';
                circle.style.opacity = '1';
            });

            svg.appendChild(circle);
            offset += percent;

            var legItem = document.createElement('div');
            legItem.className = 'pie-legend-item';
            var labelWrap = document.createElement('div');
            labelWrap.className = 'pie-legend-label';
            var swatch = document.createElement('span');
            swatch.className = 'pie-legend-swatch';
            swatch.style.background = color;
            labelWrap.appendChild(swatch);
            labelWrap.appendChild(document.createTextNode(' ' + escapeText(item.label)));
            var countEl = document.createElement('div');
            countEl.className = 'pie-legend-count';
            countEl.textContent = String(item.count);
            legItem.appendChild(labelWrap);
            legItem.appendChild(countEl);
            legend.appendChild(legItem);
        });
    }

    function syncExportLink() {
        var btn = document.getElementById('dashboard-export-btn');
        if (!btn) return;
        var base = btn.getAttribute('data-base') || btn.getAttribute('href') || '';
        var qIndex = base.indexOf('?');
        if (qIndex !== -1) {
            base = base.slice(0, qIndex);
        }
        btn.setAttribute('data-base', base);
        btn.href = base + window.location.search;
    }

    function isDashboardSwap(evt) {
        var target = evt.detail && (evt.detail.target || evt.detail.elt);
        if (!target) return false;
        if (target.id === 'dashboard-live') return true;
        return typeof target.querySelector === 'function' && !!target.querySelector('#dashboard-live');
    }

    function refreshDashboardWidgets() {
        initCategoryPie();
        syncExportLink();
    }

    window.initCategoryPie = initCategoryPie;

    document.addEventListener('DOMContentLoaded', refreshDashboardWidgets);

    document.body.addEventListener('htmx:afterSwap', function (evt) {
        if (isDashboardSwap(evt)) {
            refreshDashboardWidgets();
        }
    });
})();
