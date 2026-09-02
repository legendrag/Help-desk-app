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

    function isPeak(counts, index) {
        var value = counts[index];
        if (!value) return false;
        var left = index > 0 ? counts[index - 1] : Number.NEGATIVE_INFINITY;
        var right = index < counts.length - 1 ? counts[index + 1] : Number.NEGATIVE_INFINITY;
        return value >= left && value >= right && (value > left || value > right);
    }

    function pointRadiusFor(mobile, counts) {
        return function (context) {
            if (!isPeak(counts, context.dataIndex)) return 0;
            return mobile ? 2 : 3;
        };
    }

    function pointHoverRadiusFor(mobile, counts) {
        return function (context) {
            if (!isPeak(counts, context.dataIndex)) return 0;
            return mobile ? 4 : 5;
        };
    }

    function layoutPadding(mobile) {
        return mobile
            ? { top: 4, right: 2, bottom: 0, left: 0 }
            : { top: 0, right: 0, bottom: 0, left: 0 };
    }

    function applyMobileChartOptions(chart, mobile) {
        var dataset = chart.data.datasets[0];
        var counts = dataset.data;
        dataset.borderWidth = mobile ? 1.75 : 2;
        dataset.pointRadius = pointRadiusFor(mobile, counts);
        dataset.pointHoverRadius = pointHoverRadiusFor(mobile, counts);
        dataset.pointHitRadius = mobile ? 8 : 4;
        dataset.clip = false;

        chart.options.layout = {
            padding: layoutPadding(mobile)
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

    var mediaQuery = null;
    var mediaListener = null;

    function isDashboardLive(node) {
        if (!node) return false;
        if (node.id === "dashboard-live") return true;
        return typeof node.querySelector === "function" && !!node.querySelector("#dashboard-live");
    }

    function destroyVolumeTrendChart() {
        var canvas = document.getElementById("ticket-volume-chart");
        if (canvas && typeof Chart !== "undefined") {
            var existing = Chart.getChart(canvas);
            if (existing) existing.destroy();
        }
        if (mediaQuery && mediaListener) {
            if (typeof mediaQuery.removeEventListener === "function") {
                mediaQuery.removeEventListener("change", mediaListener);
            } else if (typeof mediaQuery.removeListener === "function") {
                mediaQuery.removeListener(mediaListener);
            }
        }
        mediaQuery = null;
        mediaListener = null;
    }

    function initVolumeTrendChart() {
        destroyVolumeTrendChart();

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
                    pointRadius: pointRadiusFor(mobile, counts),
                    pointHoverRadius: pointHoverRadiusFor(mobile, counts),
                    pointHitRadius: mobile ? 8 : 4,
                    clip: false,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: layoutPadding(mobile)
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

        mediaQuery = window.matchMedia(MOBILE_MQ);
        mediaListener = function () {
            applyMobileChartOptions(chart, mediaQuery.matches);
            chart.update("none");
            chart.resize();
        };
        if (typeof mediaQuery.addEventListener === "function") {
            mediaQuery.addEventListener("change", mediaListener);
        } else if (typeof mediaQuery.addListener === "function") {
            mediaQuery.addListener(mediaListener);
        }

        requestAnimationFrame(function () {
            chart.resize();
        });
    }

    window.initVolumeTrendChart = initVolumeTrendChart;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initVolumeTrendChart);
    } else {
        initVolumeTrendChart();
    }

    document.body.addEventListener("htmx:beforeSwap", function (evt) {
        var target = evt.detail && evt.detail.target;
        if (isDashboardLive(target)) {
            destroyVolumeTrendChart();
        }
    });

    document.body.addEventListener("htmx:afterSwap", function (evt) {
        var target = evt.detail && evt.detail.target;
        var elt = evt.detail && evt.detail.elt;
        if (isDashboardLive(target) || isDashboardLive(elt)) {
            initVolumeTrendChart();
        }
    });
})();
