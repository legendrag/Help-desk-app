(function () {
  if (window.__shiftsBound) return;
  window.__shiftsBound = true;

  // Self-refreshing panes revalidate with their ETag: unchanged = 304, kept.
  var REVALIDATED = { "shifts-available-now": true, "shifts-rota-grid": true };
  document.body.addEventListener("htmx:configRequest", function (evt) {
    var elt = evt.detail.elt;
    if (!elt || !REVALIDATED[elt.id] || evt.detail.verb !== "get") return;
    var etag = elt.getAttribute("data-etag");
    if (etag) evt.detail.headers["If-None-Match"] = etag;
  });
  document.body.addEventListener("htmx:beforeSwap", function (evt) {
    var target = evt.detail.target;
    if (!target || !REVALIDATED[target.id]) return;
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

  // Centre the active tab in its strip. Only the strip scrolls sideways:
  // scrollIntoView also scrolled the page, so every update inside the Shifts
  // page (a calculator preview, a report refresh) jumped back to the top.
  function scrollActiveShiftTab() {
    var tab = document.querySelector("#shifts-shell-pane .settings-tab[aria-current='page'], #shifts-shell-pane .settings-tab.active");
    if (!tab) return;
    var strip = tab.parentElement;
    while (strip && strip !== document.body && strip.scrollWidth <= strip.clientWidth) strip = strip.parentElement;
    if (!strip || strip === document.body) return;
    var tabBox = tab.getBoundingClientRect();
    var stripBox = strip.getBoundingClientRect();
    strip.scrollLeft += (tabBox.left + tabBox.width / 2) - (stripBox.left + stripBox.width / 2);
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
  // Calculator → Bulk assign (shifts/calculator.html, calc_bulk.html).
  function bulkForm() { return document.getElementById("shifts-bulk-form"); }

  function syncBulkMode() {
    var form = bulkForm();
    if (!form) return;
    var everyone = form.querySelector('input[name="mode"][value="everyone"]');
    var perDay = form.querySelector("[data-bulk-per-day]");
    if (!perDay) return;
    var off = !!(everyone && everyone.checked);
    perDay.hidden = off;
    var input = perDay.querySelector("input");
    if (input) input.disabled = off;
  }

  function markBulkStale() {
    var result = document.getElementById("shifts-rotation-result");
    if (!result) return;
    var note = result.querySelector("[data-bulk-stale]");
    var apply = result.querySelector("[data-bulk-apply]");
    if (note) note.hidden = false;
    if (apply) apply.disabled = true;
  }

  function addSkipDate(form) {
    var input = form.querySelector("#rot-skip-date");
    var list = form.querySelector("[data-bulk-date-list]");
    if (!input || !list || !input.value) return;
    var value = input.value;
    input.value = "";
    if (list.querySelector('input[value="' + value + '"]')) return;
    var parts = value.split("-");
    var item = document.createElement("li");
    item.className = "shifts-chip-date";
    var text = document.createElement("bdi");
    text.setAttribute("dir", "ltr");
    text.textContent = parts.length === 3 ? parts[2] + "/" + parts[1] + "/" + parts[0] : value;
    var hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "skip_date";
    hidden.value = value;
    var remove = document.createElement("button");
    remove.type = "button";
    remove.setAttribute("data-bulk-remove-date", "");
    remove.setAttribute("aria-label", (list.getAttribute("data-remove-label") || "Remove") + " " + text.textContent);
    remove.textContent = "×";
    item.appendChild(text);
    item.appendChild(hidden);
    item.appendChild(remove);
    // Keep the chips in date order.
    var after = Array.prototype.find.call(list.children, function (other) {
      var otherInput = other.querySelector("input");
      return otherInput && otherInput.value > value;
    });
    list.insertBefore(item, after || null);
    markBulkStale();
  }

  document.addEventListener("click", function (evt) {
    var form = bulkForm();
    if (!form || !evt.target.closest || !form.contains(evt.target)) return;
    if (evt.target.closest("[data-bulk-add-date]")) {
      addSkipDate(form);
      return;
    }
    var remove = evt.target.closest("[data-bulk-remove-date]");
    if (remove) {
      remove.closest("li").remove();
      markBulkStale();
    }
  });
  document.addEventListener("keydown", function (evt) {
    if (evt.key !== "Enter" || !evt.target || evt.target.id !== "rot-skip-date") return;
    var form = bulkForm();
    if (!form) return;
    evt.preventDefault();  // Enter adds the date instead of sending a preview
    addSkipDate(form);
  });
  document.addEventListener("change", function (evt) {
    var form = bulkForm();
    if (!form || !form.contains(evt.target)) return;
    if (evt.target.name === "mode") syncBulkMode();
    if (evt.target.id !== "rot-skip-date") markBulkStale();
  });
  document.addEventListener("input", function (evt) {
    var form = bulkForm();
    if (form && form.contains(evt.target) && evt.target.id === "rot-per-day") markBulkStale();
  });
  syncBulkMode();
  document.body.addEventListener("htmx:afterSettle", function (evt) {
    syncBulkMode();
    var target = evt.detail && evt.detail.target;
    // Bring a new preview into view without jumping if it is already visible.
    if (target && target.id === "shifts-rotation-result" && target.scrollIntoView) {
      target.scrollIntoView({block: "nearest"});
    }
  });
})();
