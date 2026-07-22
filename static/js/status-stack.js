(function () {
    function clearDetails(exceptDetail) {
        document.querySelectorAll(".status-stack-detail").forEach(function (detail) {
            if (exceptDetail && detail === exceptDetail) {
                return;
            }
            detail.hidden = true;
            detail.textContent = "";
        });
        document.querySelectorAll(".status-stack-segment.is-active").forEach(function (segment) {
            segment.classList.remove("is-active");
        });
    }

    function showDetail(segment) {
        var stack = segment.closest(".status-stack");
        if (!stack) {
            return;
        }
        var detail = stack.querySelector(".status-stack-detail");
        if (!detail) {
            return;
        }

        var label = segment.getAttribute("data-status-label") || "";
        var count = segment.getAttribute("data-status-count") || "0";
        var text = label + " · " + count;
        var alreadyActive = segment.classList.contains("is-active");

        clearDetails();

        if (alreadyActive) {
            return;
        }

        segment.classList.add("is-active");
        detail.textContent = text;
        detail.hidden = false;
    }

    document.addEventListener("click", function (event) {
        var segment = event.target.closest(".status-stack-segment");
        if (segment) {
            event.preventDefault();
            showDetail(segment);
            return;
        }

        if (!event.target.closest(".status-stack")) {
            clearDetails();
        }
    });
})();
