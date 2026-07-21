(function () {
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

        new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Tickets",
                    data: counts,
                    borderColor: primary,
                    backgroundColor: hexToRgba(primary, 0.15),
                    borderWidth: 2,
                    pointBackgroundColor: primary,
                    pointBorderColor: "#fff",
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
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
                            maxRotation: 45,
                            minRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 12
                        },
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        },
                        grid: {
                            color: "rgba(0, 0, 0, 0.06)"
                        }
                    }
                }
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initVolumeTrendChart);
    } else {
        initVolumeTrendChart();
    }
})();
