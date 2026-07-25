(function () {
  function insertAtCursor(input, text) {
    if (!input) return;
    input.focus();
    var start = input.selectionStart ?? input.value.length;
    var end = input.selectionEnd ?? input.value.length;
    var value = input.value || "";
    input.value = value.slice(0, start) + text + value.slice(end);
    var pos = start + text.length;
    if (typeof input.setSelectionRange === "function") {
      input.setSelectionRange(pos, pos);
    }
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function onClick(event) {
    var btn = event.target.closest(".email-template-field-btn");
    if (!btn) return;
    event.preventDefault();
    var key = btn.getAttribute("data-insert");
    var targetId = btn.getAttribute("data-target");
    if (!key || !targetId) return;
    insertAtCursor(document.getElementById(targetId), "{{ " + key + " }}");
  }

  function showSavedToast() {
    if (typeof window.showToast === "function") {
      window.showToast("Email template saved.", "success");
      return;
    }
    var el = document.getElementById("email-template-status");
    if (el) {
      el.textContent = "Saved.";
      el.hidden = false;
      setTimeout(function () {
        el.hidden = true;
      }, 2500);
    }
  }

  document.addEventListener("click", onClick);
  document.body.addEventListener("emailTemplateSaved", showSavedToast);
})();
