(function () {
  const field = document.getElementById('kb-search-field');
  const input = document.getElementById('search-q');
  const suggestionsHost = document.getElementById('kb-search-suggestions');

  if (!field || !input || !suggestionsHost) {
    return;
  }

  function closeSuggestions() {
    suggestionsHost.innerHTML = '';
    field.classList.remove('kb-search-field--open');
  }

  document.addEventListener('click', function (event) {
    if (!field.contains(event.target)) {
      closeSuggestions();
    }
  });

  input.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      closeSuggestions();
      input.blur();
    }
  });

  document.body.addEventListener('htmx:afterSwap', function (event) {
    if (event.detail.target === suggestionsHost) {
      if (suggestionsHost.innerHTML.trim()) {
        field.classList.add('kb-search-field--open');
      } else {
        field.classList.remove('kb-search-field--open');
      }
    }
  });

  input.addEventListener('search', function () {
    if (!input.value.trim()) {
      closeSuggestions();
    }
  });
})();
