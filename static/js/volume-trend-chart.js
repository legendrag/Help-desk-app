(function () {
    var MOBILE_MQ = "(max-width: 768px)";

    function getPrimaryColor() {
        var styles = getComputedStyle(document.documentElement);
        return styles.getPropertyValue("--primary").trim() || "#4f46e5";
    }

    function hexToRgba(hex, alpha) {
        var cleaned = hex.replace("#", "");
        if (cleaned.length === 3) {
            cleaned = cleaned.split("").map(function (c) { return c + c; }).join("");
        }
        if (cleaned.length !== 6) {
            return "rgba(79, 70, 229, " + alpha + ")";
        }
        var r = parseInt(cleaned.slice(0, 2), 16);
        var g = parseInt(cleaned.slice(2, 4), 16);
        var b = parseInt(cleaned.slice(4, 6), 16);
        return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
    }

    function isMobileViewport() {
        return window.matchMedia(MOBILE_MQ).matches;
    }

    // Hide dots for zero values on desktop; hide all dots on mobile.
    function pointRadiusFor(mobile) {
        if (mobile) {
            return 0;
        }
        return function (context) {
            var value = context.parsed && context.parsed.y;
            return value === 0 || value == null ? 0 : 3;
        };
    }

    function pointHoverRadiusFor(mobile) {
        if (mobile) {
            return 4;
        }
        return function (context) {
            var value = context.parsed && context.parsed.y;
            return value === 0 || value == null ? 0 : 5;
        };
    }

    function applyMobileChartOptions(chart, mobile) {
        var dataset = chart.data.datasets[0];
        dataset.borderWidth = mobile ? 1.75 : 2;
        dataset.pointRadius = pointRadiusFor(mobile);
        dataset.pointHoverRadius = pointHoverRadiusFor(mobile);
        dataset.pointHitRadius = mobile ? 8 : 4;

        chart.options.layout = {
            padding: mobile
                ? { top: 4, right: 2, bottom: 0, left: 0 }
                : { top: 0, right: 0, bottom: 0, left: 0 }
        };

        chart.options.scales.x.ticks.maxRotation = mobile ? 0 : 45;
        chart.options.scales.x.ticks.minRotation = 0;
        chart.options.scales.x.ticks.maxTicksLimit = mobile ? 5 : 12;
        chart.options.scales.x.ticks.font = { size: mobile ? 10 : 12 };
        chart.options.scales.x.ticks.padding = mobile ? 4 : 6;

        chart.options.scales.y.ticks.font = { size: mobile ? 10 : 12 };
        chart.options.scales.y.ticks.maxTicksLimit = mobile ? 5 : undefined;
        chart.options.scales.y.ticks.padding = mobile ? 4 : 8;
    }

    function initVolumeTrendChart() {
        var dataEl = document.getElementById("volume-trend-data");
        var canvas = document.getElementById("ticket-volume-chart");
        if (!dataEl || !canvas || typeof Chart === "undefined") {
            return;
        }

        var items;
        try {
            items = JSON.parse(dataEl.textContent);
        } catch (e) {
            console.error("Error parsing volume trend data:", e);
            return;
        }

        if (!Array.isArray(items) || !items.length) {
            return;
        }

        var primary = getPrimaryColor();
        var labels = items.map(function (item) { return item.label; });
        var counts = items.map(function (item) { return item.count; });
        var mobile = isMobileViewport();

        var chart = new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Tickets",
                    data: counts,
                    borderColor: primary,
                    backgroundColor: hexToRgba(primary, 0.15),
                    borderWidth: mobile ? 1.75 : 2,
                    pointBackgroundColor: primary,
                    pointBorderColor: "#fff",
                    pointRadius: pointRadiusFor(mobile),
                    pointHoverRadius: pointHoverRadiusFor(mobile),
                    pointHitRadius: mobile ? 8 : 4,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: mobile
                        ? { top: 4, right: 2, bottom: 0, left: 0 }
                        : { top: 0, right: 0, bottom: 0, left: 0 }
                },
                interaction: {
                    mode: "index",
                    intersect: false
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                var value = context.parsed.y;
                                return value + (value === 1 ? " ticket" : " tickets");
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            maxRotation: mobile ? 0 : 45,
                            minRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: mobile ? 5 : 12,
                            font: { size: mobile ? 10 : 12 },
                            padding: mobile ? 4 : 6
                        },
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0,
                            font: { size: mobile ? 10 : 12 },
                            maxTicksLimit: mobile ? 5 : undefined,
                            padding: mobile ? 4 : 8
                        },
                        grid: {
                            color: "rgba(0, 0, 0, 0.06)"
                        }
                    }
                }
            }
        });

        // Keep desktop options intact when the viewport crosses the breakpoint.
        var media = window.matchMedia(MOBILE_MQ);
        var onViewportChange = function () {
            applyMobileChartOptions(chart, media.matches);
            chart.update("none");
            chart.resize();
        };
        if (typeof media.addEventListener === "function") {
            media.addEventListener("change", onViewportChange);
        } else if (typeof media.addListener === "function") {
            media.addListener(onViewportChange);
        }

        // Mobile layout can settle after first paint; force a resize so the
        // canvas isn't left at 0×0 from the initial measure.
        requestAnimationFrame(function () {
            chart.resize();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initVolumeTrendChart);
    } else {
        initVolumeTrendChart();
    }
})();
