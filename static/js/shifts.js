(function () {
  if (window.__shiftsBound) return;
  window.__shiftsBound = true;

  document.body.addEventListener("htmx:configRequest", function (evt) {
    var elt = evt.detail.elt;
    if (!elt || elt.id !== "shifts-available-now") return;
    var etag = elt.getAttribute("data-etag");
    if (etag) evt.detail.headers["If-None-Match"] = etag;
  });
  document.body.addEventListener("htmx:beforeSwap", function (evt) {
    var target = evt.detail.target;
    if (!target || target.id !== "shifts-available-now") return;
    var xhr = evt.detail.xhr;
    if (xhr && xhr.status === 304) {
      evt.detail.shouldSwap = false;
      evt.detail.isError = false;
    }
  });
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) return;
    var board = document.getElementById("shifts-available-now");
    if (board && window.htmx) window.htmx.trigger(board, "refresh");
  });

  document.body.addEventListener("change", function (evt) {
    var box = evt.target;
    if (!box || !box.closest) return;
    var root = box.closest(".shifts-people");
    if (!root) return;
    var people = root.querySelectorAll('input[name="users"]');
    var all = root.querySelector(".shifts-select-all");
    if (box.classList.contains("shifts-select-all")) {
      people.forEach(function (item) { item.checked = box.checked; });
      return;
    }
    if (box.name === "users" && all) {
      all.checked = Array.prototype.every.call(people, function (item) { return item.checked; });
    }
  });

  // My shifts: when the check-in panels change state (a check-in, or the window
  // opening or closing), ask the nearby table rows to reload their status.
  var checkInSig = null;
  function readCheckInSig() {
    var list = document.getElementById("shifts-check-in");
    return list ? list.getAttribute("data-sig") : null;
  }
  checkInSig = readCheckInSig();
  document.body.addEventListener("htmx:afterSettle", function (evt) {
    var target = evt.detail && evt.detail.target;
    var sig = readCheckInSig();
    if (target && target.id === "shell-content") {
      checkInSig = sig;
      return;
    }
    if (sig === null) return;
    if (checkInSig !== null && sig !== checkInSig) {
      document.body.dispatchEvent(new CustomEvent("shiftsCheckIn"));
    }
    checkInSig = sig;
  });

  // Available now: filter people and departments as you type. The board
  // reloads on its own, so the filter runs again after every swap.
  function filterAvailable() {
    var input = document.getElementById("shifts-avail-filter");
    var board = document.getElementById("shifts-available-now");
    if (!input || !board) return;
    var query = input.value.trim().toLowerCase();
    var shown = 0;
    board.querySelectorAll("[data-filter-group]").forEach(function (group) {
      var groupMatch = !query || group.getAttribute("data-filter-group").indexOf(query) !== -1;
      var items = group.querySelectorAll("[data-filter-item]");
      var visible = 0;
      items.forEach(function (item) {
        var match = groupMatch || item.getAttribute("data-filter-item").indexOf(query) !== -1;
        item.hidden = !match;
        if (match) visible++;
      });
      group.hidden = items.length ? visible === 0 : !groupMatch;
      if (!group.hidden) shown++;
    });
    // The count in the page header sits outside the board that reloads.
    var total = document.getElementById("shifts-avail-total");
    if (total && board.getAttribute("data-total")) total.textContent = board.getAttribute("data-total");
    // The first department still showing takes the corner instead of its own band.
    var corner = board.querySelector(".shifts-tl-corner-name");
    var cornerCount = board.querySelector(".shifts-tl-corner-count");
    var lead = null;
    board.querySelectorAll(".shifts-tl-dept").forEach(function (section) {
      var band = section.querySelector(".shifts-tl-dept-row");
      var isLead = !lead && !section.hidden;
      if (isLead) lead = section;
      if (band) band.hidden = isLead;
    });
    if (corner) corner.textContent = lead ? lead.getAttribute("data-dept-name") : "";
    if (cornerCount) {
      var count = lead ? lead.getAttribute("data-on-count") : "0";
      cornerCount.textContent = count;
      cornerCount.hidden = count === "0";
    }
    var none = board.querySelector(".shifts-avail-nomatch");
    if (none) none.hidden = !query || shown > 0;
    var unscheduled = board.querySelector(".shifts-tl-unscheduled");
    if (unscheduled) unscheduled.hidden = !!query;
  }

  // Available now: slide the red "now" line between board reloads.
  function moveNowLine() {
    var board = document.getElementById("shifts-available-now");
    if (!board) return;
    var start = Number(board.getAttribute("data-day-start")) * 1000;
    var end = Number(board.getAttribute("data-day-end")) * 1000;
    if (!start || !end || end <= start) return;
    var nowMs = Date.now();
    var percent = Math.min(Math.max((nowMs - start) / (end - start), 0), 1) * 100;
    board.style.setProperty("--tl-now", percent.toFixed(3) + "%");
    // 6 to 9 AM: the board shows the day about to start, with no line yet.
    board.toggleAttribute("data-now-outside", nowMs < start || nowMs >= end);
    var label = board.querySelector(".shifts-tl-now-label");
    if (!label || !window.Intl) return;
    try {
      // The app's own time zone and Latin digits, like the server-rendered times.
      var arabic = (document.documentElement.lang || "").indexOf("ar") === 0;
      label.textContent = new Intl.DateTimeFormat(arabic ? "ar-u-nu-latn" : "en-US", {
        hour: "numeric",
        minute: "2-digit",
        timeZone: board.getAttribute("data-time-zone") || undefined,
      }).format(new Date());
    } catch (err) { /* keep the server-rendered label */ }
  }
  setInterval(moveNowLine, 30000);
  document.body.addEventListener("htmx:afterSettle", moveNowLine);
  document.body.addEventListener("input", function (evt) {
    if (evt.target && evt.target.id === "shifts-avail-filter") filterAvailable();
  });
  document.body.addEventListener("htmx:afterSettle", filterAvailable);

  function scrollActiveShiftTab() {
    var tab = document.querySelector("#shifts-shell-pane .settings-tab[aria-current='page'], #shifts-shell-pane .settings-tab.active");
    if (tab && tab.scrollIntoView) tab.scrollIntoView({inline: "center", block: "nearest"});
  }
  scrollActiveShiftTab();
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    var target = evt.detail && evt.detail.target;
    if (!target || !target.querySelector) return;
    if (target.id === "shell-content" || (target.closest && target.closest("#shifts-shell-pane"))) {
      scrollActiveShiftTab();
    }
  });
  // Calculator → Work hours → Shifts (shifts/calc_work_shifts.html). No shift
  // type ticked means all shifts; "Night shifts only" ticks the night types.
  // Capture phase: this runs before htmx reads the form for the report.
  function syncShiftSwitches(root, changed) {
    var all = root.querySelector("[data-multi-all]");
    var night = root.querySelector("[data-multi-night]");
    var mode = root.querySelector("[data-multi-mode]");
    var summary = root.querySelector(".shifts-multi-summary");
    var types = Array.prototype.slice.call(root.querySelectorAll('input[name="shift_type"]'));
    var nights = types.filter(function (box) { return box.hasAttribute("data-night"); });
    if (changed && changed === all) {
      types.forEach(function (box) { box.checked = false; });
    } else if (changed && changed === night) {
      types.forEach(function (box) { box.checked = night.checked && box.hasAttribute("data-night"); });
    }
    var on = types.filter(function (box) { return box.checked; });
    if (types.length && on.length === types.length) {
      // Every type ticked is the same as all shifts.
      types.forEach(function (box) { box.checked = false; });
      on = [];
    }
    var isNight = nights.length > 0 && nights.length < types.length && on.length === nights.length &&
      on.every(function (box) { return box.hasAttribute("data-night"); });
    if (all) all.checked = on.length === 0;
    if (night) night.checked = isNight;
    if (mode) mode.value = isNight ? "night" : "all";
    if (summary) {
      var names = on.map(function (box) {
        var text = box.parentNode.querySelector(".shifts-switch-text");
        return text ? text.textContent.trim() : "";
      });
      if (!on.length) summary.textContent = summary.getAttribute("data-all");
      else if (isNight) summary.textContent = summary.getAttribute("data-night");
      else if (names.length <= 2) summary.textContent = names.join(", ");
      else summary.textContent = names.slice(0, 2).join(", ") + " +" + (names.length - 2);
    }
  }
  document.addEventListener("change", function (evt) {
    var root = evt.target && evt.target.closest && evt.target.closest("[data-shifts-multi]");
    if (root) syncShiftSwitches(root, evt.target);
  }, true);
  function syncAllShiftSwitches() {
    document.querySelectorAll("[data-shifts-multi]").forEach(function (root) { syncShiftSwitches(root, null); });
  }
  // On load too: a browser going Back can restore the switches' old state.
  syncAllShiftSwitches();
  document.body.addEventListener("htmx:afterSettle", syncAllShiftSwitches);
  // Close the drop-down on a click outside it or on Escape.
  document.addEventListener("click", function (evt) {
    document.querySelectorAll("[data-shifts-multi][open]").forEach(function (root) {
      if (!root.contains(evt.target)) root.removeAttribute("open");
    });
  });
  document.addEventListener("keydown", function (evt) {
    if (evt.key !== "Escape") return;
    document.querySelectorAll("[data-shifts-multi][open]").forEach(function (root) {
      root.removeAttribute("open");
      var button = root.querySelector("summary");
      if (button) button.focus();
    });
  });
})();
