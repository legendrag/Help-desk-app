(function () {
  var lastFocusedId = "id_email_body";
  var baseline = { subject: "", body: "" };
  var selectSyncing = false;

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

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function bodyToHtml(body) {
    return escapeHtml(body).replace(/\r\n/g, "\n").replace(/\n/g, "<br>\n");
  }

  function buildEmailDocument(meta, bodyText) {
    var brand = escapeHtml(meta.brand_name || "MlamehTicket");
    var brandIcon = escapeHtml(meta.brand_icon_url || "");
    var brandLogo = escapeHtml(meta.brand_logo_url || "");
    var ctaLabel = escapeHtml(meta.cta_label || "Open");
    var ctaUrl = escapeHtml(meta.cta_url || "#");
    var footer = escapeHtml(
      meta.footer_note ||
        "You’re receiving this because email notifications are enabled for your MlamehTicket account."
    );
    var bodyHtml = bodyToHtml(bodyText);
    var bodyBlock = bodyHtml
      ? '<div style="margin:0 0 22px 0;font-size:15px;line-height:1.55;color:#1e293b;">' + bodyHtml + "</div>"
      : "";
    var ctaBlock =
      '<table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 8px 0;">' +
      "<tr>" +
      '<td style="border-radius:10px;background:#818cf8;">' +
      '<a href="' +
      ctaUrl +
      '" style="display:inline-block;padding:12px 18px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">' +
      ctaLabel +
      "</a>" +
      "</td>" +
      "</tr>" +
      "</table>" +
      '<p style="margin:10px 0 0 0;font-size:12px;line-height:1.5;color:#94a3b8;word-break:break-all;">' +
      'Or open: <a href="' +
      ctaUrl +
      '" style="color:#6366f1;text-decoration:underline;">' +
      ctaUrl +
      "</a>" +
      "</p>";

    var iconCell = brandIcon
      ? '<td style="vertical-align:middle;padding-right:10px;">' +
        '<img src="' +
        brandIcon +
        '" alt="" width="32" height="32" style="display:block;border:0;outline:none;text-decoration:none;">' +
        "</td>"
      : "";
    var logoCell = brandLogo
      ? '<td style="vertical-align:middle;">' +
        '<img src="' +
        brandLogo +
        '" alt="' +
        brand +
        '" height="28" style="display:block;border:0;outline:none;text-decoration:none;height:28px;width:auto;max-height:28px;">' +
        "</td>"
      : '<td style="vertical-align:middle;">' +
        '<div style="font-size:18px;font-weight:700;letter-spacing:0.02em;color:#ffffff;">' +
        brand +
        "</div>" +
        "</td>";

    return (
      "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">" +
      '<meta name="viewport" content="width=device-width, initial-scale=1">' +
      "<title>" +
      brand +
      "</title></head>" +
      '<body style="margin:0;padding:0;background:#f8fafc;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">' +
      '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;padding:24px 12px;">' +
      "<tr><td align=\"center\">" +
      '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">' +
      "<tr>" +
      '<td style="background:#818cf8;padding:16px 24px;">' +
      '<table role="presentation" cellspacing="0" cellpadding="0"><tr>' +
      iconCell +
      logoCell +
      "</tr></table>" +
      "</td>" +
      "</tr>" +
      "<tr>" +
      '<td style="padding:28px 24px 8px 24px;">' +
      bodyBlock +
      ctaBlock +
      "</td>" +
      "</tr>" +
      "<tr>" +
      '<td style="padding:18px 24px 24px 24px;border-top:1px solid #e2e8f0;">' +
      '<p style="margin:0;font-size:12px;line-height:1.5;color:#94a3b8;">' +
      footer +
      "</p>" +
      "</td>" +
      "</tr>" +
      "</table>" +
      "</td></tr></table>" +
      "</body></html>"
    );
  }

  function updatePreview() {
    var subjectEl = $("email-template-preview-subject");
    var frame = $("email-template-preview-frame");
    if (!subjectEl || !frame) return;
    var meta = readMeta();
    var values = currentValues();
    var sample = meta.sample || {};
    var subject = resolveTokens(values.subject, sample).trim();
    var body = resolveTokens(values.body, sample).trim();
    subjectEl.textContent = subject || "—";
    frame.srcdoc = buildEmailDocument(meta, body);
  }

  function syncSelect(eventType) {
    var select = $("email-type-select");
    if (!select || !eventType) return;
    selectSyncing = true;
    select.value = eventType;
    selectSyncing = false;
  }

  function loadType(eventType) {
    var select = $("email-type-select");
    if (!select || !window.htmx) return;
    var baseUrl = select.getAttribute("data-form-url");
    if (!baseUrl) return;
    var url = baseUrl + (baseUrl.indexOf("?") >= 0 ? "&" : "?") + "email_type=" + encodeURIComponent(eventType);
    syncSelect(eventType);
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

  function onTypeChange(event) {
    var select = event.target;
    if (!select || select.id !== "email-type-select" || selectSyncing) return;
    var nextType = select.value;
    if (!nextType) return;
    var form = $("email-template-editor");
    var currentType = form ? form.getAttribute("data-event-type") : null;
    if (currentType && nextType === currentType) return;
    if (isDirty() && !window.confirm("You have unsaved changes. Switch notification type and discard them?")) {
      syncSelect(currentType);
      return;
    }
    loadType(nextType);
  }

  function onClick(event) {
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
    if (form) syncSelect(form.getAttribute("data-event-type"));
  }

  function onAfterSwap(event) {
    var target = event.target;
    if (!target) return;
    if (
      target.id === "email-template-form-slot" ||
      target.id === "settings-content" ||
      (target.querySelector && target.querySelector("#email-template-editor"))
    ) {
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
    document.addEventListener("change", onTypeChange);
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("input", onInput);
    document.body.addEventListener("htmx:afterSwap", onAfterSwap);
    document.body.addEventListener("emailTemplateSaved", showSavedToast);
    document.body.addEventListener("emailTemplateTestResult", onTestResult);
  }

  initForm();
})();
