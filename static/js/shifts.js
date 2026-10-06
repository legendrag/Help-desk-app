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
})();
