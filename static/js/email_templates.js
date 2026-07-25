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

  function setStatus(message, isError) {
    var el = document.getElementById("email-template-status");
    if (el) {
      el.textContent = message;
      el.hidden = !message;
      el.classList.toggle("email-templates-panel__status--error", !!isError);
      if (message) {
        setTimeout(function () {
          el.hidden = true;
        }, 4000);
      }
    }
    if (typeof window.showToast === "function") {
      window.showToast(message, isError ? "error" : "success");
    }
  }

  function showSavedToast() {
    setStatus("Email template saved.", false);
  }

  function onTestResult(event) {
    var detail = event.detail || {};
    setStatus(detail.message || (detail.ok ? "Test email sent." : "Test email failed."), !detail.ok);
  }

  document.addEventListener("click", onClick);
  document.body.addEventListener("emailTemplateSaved", showSavedToast);
  document.body.addEventListener("emailTemplateTestResult", onTestResult);
})();
