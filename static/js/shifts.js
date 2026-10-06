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
})();
