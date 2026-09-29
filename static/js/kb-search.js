(function () {
  var cleanups = [];

  function unmountKbSearch() {
    cleanups.forEach(function (fn) { fn(); });
    cleanups = [];
  }

  function mountKbSearch() {
    unmountKbSearch();
    var field = document.getElementById("kb-search-field");
    var input = document.getElementById("search-q");
    var suggestionsHost = document.getElementById("kb-search-suggestions");
    if (!field || !input || !suggestionsHost) return;

    function closeSuggestions() {
      suggestionsHost.innerHTML = "";
      field.classList.remove("kb-search-field--open");
    }

    function onDocClick(event) {
      if (!field.contains(event.target)) closeSuggestions();
    }

    function onKeydown(event) {
      if (event.key === "Escape") {
        closeSuggestions();
        input.blur();
      }
    }

    function onAfterSwap(event) {
      if (!event.detail || event.detail.target !== suggestionsHost) return;
      if (suggestionsHost.innerHTML.trim()) {
        field.classList.add("kb-search-field--open");
      } else {
        field.classList.remove("kb-search-field--open");
      }
    }

    function onSearch() {
      if (!input.value.trim()) closeSuggestions();
    }

    document.addEventListener("click", onDocClick);
    input.addEventListener("keydown", onKeydown);
    document.body.addEventListener("htmx:afterSwap", onAfterSwap);
    input.addEventListener("search", onSearch);
    cleanups.push(function () {
      document.removeEventListener("click", onDocClick);
      input.removeEventListener("keydown", onKeydown);
      document.body.removeEventListener("htmx:afterSwap", onAfterSwap);
      input.removeEventListener("search", onSearch);
    });
  }

  window.mountKbSearch = mountKbSearch;
  window.unmountKbSearch = unmountKbSearch;

  // Full document loads run this after parse. In-shell swaps call mountKbSearch
  // from the pane, because this file stays loaded on the shell.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      if (document.getElementById("kb-search-field")) mountKbSearch();
    });
  } else if (document.getElementById("kb-search-field")) {
    mountKbSearch();
  }
})();
