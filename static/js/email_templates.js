(function () {
  var lastFocusedId = "id_email_body";
  var baseline = { subject: "", body: "" };

  function $(id) {
    return document.getElementById(id);
  }

  function readMeta() {
    var el = $("email-template-meta");
    if (!el) return { sample: {}, defaults: { subject: "", body: "" } };
    try {
      return JSON.parse(el.textContent);
    } catch (err) {
      return { sample: {}, defaults: { subject: "", body: "" } };
    }
  }

  function getInputs() {
    return {
      subject: $("id_email_subject"),
      body: $("id_email_body"),
    };
  }

  function currentValues() {
    var inputs = getInputs();
    return {
      subject: inputs.subject ? inputs.subject.value : "",
      body: inputs.body ? inputs.body.value : "",
    };
  }

  function isDirty() {
    if (!$("email-template-editor")) return false;
    var values = currentValues();
    return values.subject !== baseline.subject || values.body !== baseline.body;
  }

  function captureBaseline() {
    baseline = currentValues();
  }

  function insertAtCursor(input, text) {
    if (!input || input.readOnly || input.disabled) return;
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

  function resolveTokens(text, sample) {
    return String(text || "").replace(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g, function (_m, key) {
      var value = sample[key];
      return value == null ? "" : String(value);
    });
  }

  function updatePreview() {
    var subjectEl = $("email-template-preview-subject");
    var bodyEl = $("email-template-preview-body");
    if (!subjectEl || !bodyEl) return;
    var meta = readMeta();
    var values = currentValues();
    var sample = meta.sample || {};
    subjectEl.textContent = resolveTokens(values.subject, sample) || "—";
    bodyEl.textContent = resolveTokens(values.body, sample) || "—";
  }

  function setActiveChip(eventType) {
    var chips = document.querySelectorAll(".email-type-chip");
    chips.forEach(function (chip) {
      var active = chip.getAttribute("data-email-type") === eventType;
      chip.classList.toggle("is-active", active);
      chip.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  function loadType(eventType) {
    var chips = $("email-type-chips");
    if (!chips || !window.htmx) return;
    var baseUrl = chips.getAttribute("data-form-url");
    if (!baseUrl) return;
    var url = baseUrl + (baseUrl.indexOf("?") >= 0 ? "&" : "?") + "email_type=" + encodeURIComponent(eventType);
    setActiveChip(eventType);
    window.htmx.ajax("GET", url, {
      target: "#email-template-form-slot",
      swap: "innerHTML",
    });
  }

  function setStatus(message, isError) {
    var el = $("email-template-status");
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
    if (typeof window.showToast === "function" && message) {
      window.showToast(message, isError ? "error" : "success");
    }
  }

  function onClick(event) {
    var chip = event.target.closest(".email-type-chip");
    if (chip) {
      event.preventDefault();
      var nextType = chip.getAttribute("data-email-type");
      if (!nextType) return;
      var form = $("email-template-editor");
      var currentType = form ? form.getAttribute("data-event-type") : null;
      if (currentType && nextType === currentType) return;
      if (isDirty() && !window.confirm("You have unsaved changes. Switch notification type and discard them?")) {
        return;
      }
      loadType(nextType);
      return;
    }

    var resetBtn = event.target.closest(".email-template-reset-btn");
    if (resetBtn) {
      event.preventDefault();
      if (!window.confirm("Reset subject and body to the default template for this notification type?")) {
        return;
      }
      var meta = readMeta();
      var inputs = getInputs();
      if (inputs.subject) inputs.subject.value = (meta.defaults && meta.defaults.subject) || "";
      if (inputs.body) inputs.body.value = (meta.defaults && meta.defaults.body) || "";
      updatePreview();
      setStatus("Defaults restored. Click Save to keep them.", false);
      return;
    }

    var btn = event.target.closest(".email-template-field-btn");
    if (!btn) return;
    event.preventDefault();
    var key = btn.getAttribute("data-insert");
    if (!key) return;
    var target =
      $(lastFocusedId) ||
      $("id_email_body") ||
      $("id_email_subject");
    insertAtCursor(target, "{{ " + key + " }}");
  }

  function onFocusIn(event) {
    if (!event.target || !event.target.classList) return;
    if (!event.target.classList.contains("email-template-input")) return;
    lastFocusedId = event.target.id || lastFocusedId;
  }

  function onInput(event) {
    if (!event.target || !event.target.classList) return;
    if (!event.target.classList.contains("email-template-input")) return;
    updatePreview();
  }

  function initForm() {
    if (!$("email-template-editor")) return;
    lastFocusedId = "id_email_body";
    captureBaseline();
    updatePreview();
    var form = $("email-template-editor");
    if (form) setActiveChip(form.getAttribute("data-event-type"));
  }

  function onAfterSwap(event) {
    var target = event.target;
    if (!target) return;
    if (target.id === "email-template-form-slot" || target.id === "settings-content" || target.querySelector && target.querySelector("#email-template-editor")) {
      initForm();
    }
  }

  function showSavedToast() {
    captureBaseline();
    setStatus("Email template saved.", false);
  }

  function onTestResult(event) {
    var detail = event.detail || {};
    setStatus(detail.message || (detail.ok ? "Test email sent." : "Test email failed."), !detail.ok);
  }

  window.EmailTemplatesUX = {
    init: initForm,
  };

  if (!window.__emailTemplatesUxBound) {
    window.__emailTemplatesUxBound = true;
    document.addEventListener("click", onClick);
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("input", onInput);
    document.body.addEventListener("htmx:afterSwap", onAfterSwap);
    document.body.addEventListener("emailTemplateSaved", showSavedToast);
    document.body.addEventListener("emailTemplateTestResult", onTestResult);
  }

  initForm();
})();
