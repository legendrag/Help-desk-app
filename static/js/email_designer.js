(function () {
  "use strict";

  var savedRange = null;
  var activeRegion = null;

  var COLOR_PRESETS = {
    light: {
      accent_color: "#4f46e5",
      page_background: "#f8fafc",
      card_background: "#ffffff",
      table_header_bg: "#f8fafc",
      table_border_color: "#e2e8f0",
      text_color: "#0f172a",
      muted_text_color: "#64748b",
    },
    soft: {
      accent_color: "#0f766e",
      page_background: "#ecfdf5",
      card_background: "#ffffff",
      table_header_bg: "#f0fdfa",
      table_border_color: "#99f6e4",
      text_color: "#134e4a",
      muted_text_color: "#0f766e",
    },
    dark: {
      accent_color: "#818cf8",
      page_background: "#0f172a",
      card_background: "#1e293b",
      table_header_bg: "#0f172a",
      table_border_color: "#334155",
      text_color: "#f1f5f9",
      muted_text_color: "#94a3b8",
    },
  };

  var LAYOUT_DEFAULTS = {
    classic: {
      table_radius: 12,
      table_row_padding_y: 10,
      table_row_padding_x: 14,
      table_label_width: 38,
      table_show_outer_border: true,
      table_show_row_dividers: true,
      table_fill_mode: "striped",
    },
    compact: {
      table_radius: 8,
      table_row_padding_y: 6,
      table_row_padding_x: 10,
      table_label_width: 34,
      table_show_outer_border: true,
      table_show_row_dividers: true,
      table_fill_mode: "striped",
    },
    minimal: {
      table_radius: 0,
      table_row_padding_y: 8,
      table_row_padding_x: 0,
      table_label_width: 36,
      table_show_outer_border: false,
      table_show_row_dividers: true,
      table_fill_mode: "none",
    },
    pills: {
      table_radius: 18,
      table_row_padding_y: 10,
      table_row_padding_x: 14,
      table_label_width: 38,
      table_show_outer_border: false,
      table_show_row_dividers: false,
      table_fill_mode: "labels",
    },
  };

  var FIELD_IDS = {
    accent_color: "email-brand-accent",
    page_background: "email-page-bg",
    card_background: "email-card-bg",
    table_header_bg: "email-table-bg",
    table_border_color: "email-table-border",
    text_color: "email-text-color",
    muted_text_color: "email-muted-color",
  };

  function designerRoot() {
    return document.getElementById("email-designer");
  }

  function getCsrf() {
    var input = document.querySelector("#email-brand-form [name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var cookie = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return cookie ? decodeURIComponent(cookie[1]) : "";
  }

  function setStatus(el, text, kind) {
    if (!el) return;
    if (!text) {
      el.hidden = true;
      el.textContent = "";
      el.className = "email-save-status";
      return;
    }
    el.hidden = false;
    el.textContent = text;
    el.className = "email-save-status" + (kind ? " is-" + kind : "");
  }

  function markBrandDirty(dirty) {
    var root = designerRoot();
    if (!root) return;
    root.classList.toggle("is-brand-dirty", !!dirty);
    var btn = document.getElementById("email-brand-save-btn");
    if (btn) btn.disabled = !dirty;
    setStatus(
      document.getElementById("email-brand-status"),
      dirty ? "Unsaved look" : "",
      dirty ? "warn" : ""
    );
  }

  function markMessageDirty(dirty) {
    var canvas = document.getElementById("email-canvas");
    if (!canvas) return;
    canvas.classList.toggle("is-message-dirty", !!dirty);
    var btn = document.getElementById("email-message-save-btn");
    if (btn) {
      btn.disabled = !dirty;
      btn.textContent = dirty ? "Save this email" : "Saved";
    }
    setStatus(
      document.getElementById("email-message-status"),
      dirty ? "Unsaved changes" : "",
      dirty ? "warn" : ""
    );
  }

  function readHex(id, fallback) {
    var el = document.getElementById(id);
    var value = el ? el.value.trim() : "";
    return /^#[0-9A-Fa-f]{6}$/.test(value) ? value : fallback;
  }

  function numVal(id, fallback) {
    var el = document.getElementById(id);
    var n = el ? parseInt(el.value, 10) : NaN;
    return isNaN(n) ? fallback : n;
  }

  function applyBrandPreview(flashDetails) {
    var root = designerRoot();
    if (!root) return;
    var name = (document.getElementById("email-brand-name") || {}).value || "mlamehticket";
    var accent = readHex("email-brand-accent", "#4f46e5");
    var footer = (document.getElementById("email-brand-footer") || {}).value || "";
    var pageBg = readHex("email-page-bg", "#f8fafc");
    var cardBg = readHex("email-card-bg", "#ffffff");
    var tableBg = readHex("email-table-bg", "#f8fafc");
    var tableBorder = readHex("email-table-border", "#e2e8f0");
    var text = readHex("email-text-color", "#0f172a");
    var muted = readHex("email-muted-color", "#64748b");
    var layout = (document.getElementById("email-table-layout") || {}).value || "classic";
    var fill = (document.getElementById("email-table-fill") || {}).value || "striped";
    var radius = numVal("email-table-radius", 12);
    var padY = numVal("email-table-pad-y", 10);
    var padX = numVal("email-table-pad-x", 14);
    var labelW = numVal("email-table-label-width", 38);
    var outer = !!(document.getElementById("email-table-outer-border") || {}).checked;
    var dividers = !!(document.getElementById("email-table-row-dividers") || {}).checked;

    var readout = document.getElementById("email-label-width-readout");
    if (readout) readout.textContent = labelW + "%";

    root.querySelectorAll("[data-brand-name]").forEach(function (el) {
      el.textContent = name;
    });
    root.querySelectorAll("[data-brand-footer]").forEach(function (el) {
      el.textContent = footer;
    });
    root.querySelectorAll("[data-brand-accent]").forEach(function (el) {
      el.style.background = accent;
    });
    root.querySelectorAll("[data-brand-border]").forEach(function (el) {
      el.style.borderLeftColor = accent;
    });

    var stage = root.querySelector(".email-canvas__stage");
    if (stage) stage.style.setProperty("--email-page-bg", pageBg);

    var mail = root.querySelector(".email-canvas__mail");
    if (mail) {
      mail.style.setProperty("--email-accent", accent);
      mail.style.setProperty("--email-card-bg", cardBg);
      mail.style.setProperty("--email-table-bg", tableBg);
      mail.style.setProperty("--email-table-border", tableBorder);
      mail.style.setProperty("--email-text", text);
      mail.style.setProperty("--email-muted", muted);
      mail.style.setProperty("--email-table-radius", radius + "px");
      mail.style.setProperty("--email-table-pad-y", padY + "px");
      mail.style.setProperty("--email-table-pad-x", padX + "px");
      mail.style.setProperty("--email-table-label-width", labelW + "%");
      mail.dataset.tableLayout = layout;
      mail.dataset.tableFill = fill;
      mail.dataset.tableOuterBorder = outer ? "true" : "false";
      mail.dataset.tableRowDividers = dividers ? "true" : "false";
    }

    if (flashDetails) {
      var wrap = document.getElementById("email-details-wrap");
      if (wrap) {
        wrap.classList.remove("is-flashing");
        void wrap.offsetWidth;
        wrap.classList.add("is-flashing");
      }
    }
  }

  function setFillMode(mode) {
    var hidden = document.getElementById("email-table-fill");
    if (hidden) hidden.value = mode;
    document.querySelectorAll("[data-fill-mode]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.dataset.fillMode === mode);
    });
  }

  function setLayout(layout, applyDefaults) {
    var hidden = document.getElementById("email-table-layout");
    if (hidden) hidden.value = layout;
    document.querySelectorAll(".email-layout-card").forEach(function (card) {
      var active = card.dataset.tableLayout === layout;
      card.classList.toggle("is-active", active);
      card.setAttribute("aria-checked", active ? "true" : "false");
    });
    if (applyDefaults && LAYOUT_DEFAULTS[layout]) {
      var d = LAYOUT_DEFAULTS[layout];
      var radius = document.getElementById("email-table-radius");
      var padY = document.getElementById("email-table-pad-y");
      var padX = document.getElementById("email-table-pad-x");
      var labelW = document.getElementById("email-table-label-width");
      var outer = document.getElementById("email-table-outer-border");
      var dividers = document.getElementById("email-table-row-dividers");
      if (radius) radius.value = d.table_radius;
      if (padY) padY.value = d.table_row_padding_y;
      if (padX) padX.value = d.table_row_padding_x;
      if (labelW) labelW.value = d.table_label_width;
      if (outer) outer.checked = d.table_show_outer_border;
      if (dividers) dividers.checked = d.table_show_row_dividers;
      setFillMode(d.table_fill_mode);
    }
    applyBrandPreview(true);
    markBrandDirty(true);
  }

  function applyColorPreset(name) {
    var preset = COLOR_PRESETS[name];
    if (!preset) return;
    Object.keys(FIELD_IDS).forEach(function (key) {
      var input = document.getElementById(FIELD_IDS[key]);
      if (!input) return;
      input.value = preset[key];
      var pickerId = input.getAttribute("data-sync-picker");
      var picker = pickerId ? document.getElementById(pickerId) : null;
      if (picker) picker.value = preset[key];
    });
    applyBrandPreview(false);
    markBrandDirty(true);
  }

  function bindColorPairs(root) {
    root.querySelectorAll('input[type="color"][data-sync-hex]').forEach(function (picker) {
      picker.addEventListener("input", function () {
        var hex = document.getElementById(picker.getAttribute("data-sync-hex"));
        if (hex) hex.value = picker.value;
        applyBrandPreview(false);
        markBrandDirty(true);
      });
    });
    root.querySelectorAll("input[data-sync-picker]").forEach(function (hex) {
      hex.addEventListener("input", function () {
        if (/^#[0-9A-Fa-f]{6}$/.test(hex.value)) {
          var picker = document.getElementById(hex.getAttribute("data-sync-picker"));
          if (picker) picker.value = hex.value;
        }
        applyBrandPreview(false);
        markBrandDirty(true);
      });
    });
  }

  function updateInsertBar(region) {
    var menu = document.getElementById("email-insert-menu");
    var hint = document.getElementById("email-insert-hint");
    if (!menu) return;
    if (region) {
      menu.dataset.active = "true";
      if (hint) {
        hint.textContent = "Insert into “" + (region.dataset.regionLabel || "selection") + "”";
      }
    } else {
      menu.dataset.active = "false";
      if (hint) hint.textContent = "Click highlighted text below, then add a field";
    }
  }

  function rememberSelection() {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    var range = sel.getRangeAt(0);
    var node = range.commonAncestorContainer;
    var region =
      node.nodeType === 1
        ? node.closest("[data-region]")
        : node.parentElement && node.parentElement.closest("[data-region]");
    if (!region || !region.isContentEditable) return;
    savedRange = range.cloneRange();
    activeRegion = region;
  }

  function restoreSelection() {
    if (!savedRange) return false;
    var sel = window.getSelection();
    if (!sel) return false;
    sel.removeAllRanges();
    sel.addRange(savedRange);
    return true;
  }

  function insertChip(key, label) {
    if (!restoreSelection() && activeRegion) {
      activeRegion.focus();
      rememberSelection();
      if (!restoreSelection()) return;
    }
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    var range = sel.getRangeAt(0);
    var node = range.commonAncestorContainer;
    var region =
      node.nodeType === 1
        ? node.closest("[data-region]")
        : node.parentElement && node.parentElement.closest("[data-region]");
    if (!region || !region.isContentEditable) return;

    var chip = document.createElement("span");
    chip.className = "email-merge-chip";
    chip.setAttribute("data-merge-key", key);
    chip.setAttribute("contenteditable", "false");
    chip.textContent = label;

    range.deleteContents();
    range.insertNode(chip);
    var space = document.createTextNode("\u00a0");
    chip.after(space);
    range.setStartAfter(space);
    range.collapse(true);
    sel.removeAllRanges();
    sel.addRange(range);
    savedRange = range.cloneRange();
    activeRegion = region;
    region.focus();
    markMessageDirty(true);
  }

  function bindCanvas(canvas) {
    if (!canvas || canvas.dataset.bound === "1") return;
    canvas.dataset.bound = "1";
    var canEdit = canvas.dataset.canEdit === "true";
    markMessageDirty(false);
    updateInsertBar(null);

    if (!canEdit) return;

    canvas.querySelectorAll("[data-region].is-editable").forEach(function (region) {
      region.addEventListener("focus", function () {
        canvas.querySelectorAll("[data-region].is-focused").forEach(function (el) {
          el.classList.remove("is-focused");
        });
        region.classList.add("is-focused");
        activeRegion = region;
        updateInsertBar(region);
        rememberSelection();
      });
      region.addEventListener("blur", function () {
        region.classList.remove("is-focused");
      });
      region.addEventListener("keyup", rememberSelection);
      region.addEventListener("mouseup", rememberSelection);
      region.addEventListener("input", function () {
        rememberSelection();
        markMessageDirty(true);
      });
      region.addEventListener("keydown", function (e) {
        if (
          region.dataset.region === "subject" ||
          region.dataset.region === "button_label" ||
          region.dataset.region === "message_label"
        ) {
          if (e.key === "Enter") e.preventDefault();
        }
      });
    });

    var saveBtn = canvas.querySelector("#email-message-save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        var url = canvas.dataset.saveUrl;
        var body = new FormData();
        body.append("csrfmiddlewaretoken", getCsrf());
        ["subject", "title", "opening", "message_label", "button_label"].forEach(function (key) {
          var el = canvas.querySelector('[data-region="' + key + '"]');
          body.append(key + "_html", el ? el.innerHTML : "");
        });
        saveBtn.disabled = true;
        setStatus(document.getElementById("email-message-status"), "Saving…", "busy");
        fetch(url, {
          method: "POST",
          body: body,
          headers: { "HX-Request": "true", "X-CSRFToken": getCsrf() },
          credentials: "same-origin",
        })
          .then(function (res) {
            if (!res.ok) throw new Error("Save failed");
            markMessageDirty(false);
            setStatus(document.getElementById("email-message-status"), "Saved", "ok");
            setTimeout(function () {
              setStatus(document.getElementById("email-message-status"), "", "");
            }, 1600);
          })
          .catch(function () {
            markMessageDirty(true);
            setStatus(document.getElementById("email-message-status"), "Couldn’t save", "error");
          });
      });
    }
  }

  function bindDesigner() {
    var root = designerRoot();
    if (!root || root.dataset.bound === "1") return;
    root.dataset.bound = "1";

    var nameInput = document.getElementById("email-brand-name");
    var footerInput = document.getElementById("email-brand-footer");
    var brandForm = document.getElementById("email-brand-form");

    bindColorPairs(root);

    function onBrandChange() {
      applyBrandPreview(false);
      markBrandDirty(true);
    }

    if (nameInput) nameInput.addEventListener("input", onBrandChange);
    if (footerInput) footerInput.addEventListener("input", onBrandChange);

    ["email-table-radius", "email-table-pad-y", "email-table-pad-x", "email-table-label-width"].forEach(
      function (id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener("input", onBrandChange);
      }
    );
    ["email-table-outer-border", "email-table-row-dividers"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener("change", onBrandChange);
    });

    root.querySelectorAll("[data-preset]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyColorPreset(btn.dataset.preset);
      });
    });

    root.querySelectorAll(".email-layout-card").forEach(function (card) {
      card.addEventListener("click", function () {
        if (card.disabled) return;
        setLayout(card.dataset.tableLayout, true);
      });
    });

    root.querySelectorAll("[data-fill-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (btn.disabled) return;
        setFillMode(btn.dataset.fillMode);
        applyBrandPreview(false);
        markBrandDirty(true);
      });
    });

    markBrandDirty(false);

    if (brandForm && root.dataset.canEdit === "true") {
      brandForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var url = root.dataset.brandSaveUrl;
        var body = new FormData(brandForm);
        var btn = document.getElementById("email-brand-save-btn");
        if (btn) btn.disabled = true;
        setStatus(document.getElementById("email-brand-status"), "Saving…", "busy");
        fetch(url, {
          method: "POST",
          body: body,
          headers: { "HX-Request": "true", "X-CSRFToken": getCsrf() },
          credentials: "same-origin",
        })
          .then(function (res) {
            if (!res.ok) throw new Error("Save failed");
            markBrandDirty(false);
            setStatus(document.getElementById("email-brand-status"), "Saved", "ok");
            setTimeout(function () {
              setStatus(document.getElementById("email-brand-status"), "", "");
            }, 1600);
            applyBrandPreview(false);
          })
          .catch(function () {
            markBrandDirty(true);
            setStatus(document.getElementById("email-brand-status"), "Couldn’t save", "error");
          });
      });
    }

    root.addEventListener("mousedown", function (e) {
      if (e.target.closest(".email-merge-chip-btn")) {
        rememberSelection();
        e.preventDefault();
      }
    });

    root.addEventListener("click", function (e) {
      var chipBtn = e.target.closest(".email-merge-chip-btn");
      if (chipBtn) {
        e.preventDefault();
        insertChip(chipBtn.dataset.mergeKey, chipBtn.dataset.mergeLabel);
        return;
      }
      var typeBtn = e.target.closest(".email-type-btn");
      if (typeBtn) {
        root.querySelectorAll(".email-type-btn").forEach(function (btn) {
          btn.classList.toggle("is-active", btn === typeBtn);
        });
        var select = document.getElementById("email-type-select");
        if (select) select.value = typeBtn.dataset.eventType;
        var host = document.getElementById("email-canvas-host");
        if (host) host.classList.add("is-loading");
      }
    });

    var select = document.getElementById("email-type-select");
    if (select) {
      select.addEventListener("change", function () {
        var type = select.value;
        root.querySelectorAll(".email-type-btn").forEach(function (btn) {
          btn.classList.toggle("is-active", btn.dataset.eventType === type);
        });
        var host = document.getElementById("email-canvas-host");
        if (host) host.classList.add("is-loading");
        if (window.htmx) {
          window.htmx.ajax("GET", "/core/email-designer/messages/" + type + "/", {
            target: "#email-canvas-host",
            swap: "innerHTML",
          });
        }
      });
    }

    bindCanvas(document.getElementById("email-canvas"));
    applyBrandPreview(false);
  }

  function boot() {
    if (designerRoot()) bindDesigner();
  }

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    var target = evt.detail && evt.detail.target;
    if (!target) return;
    if (target.id === "settings-content") {
      var root = designerRoot();
      if (root) {
        root.dataset.bound = "";
        bindDesigner();
      }
      return;
    }
    if (target.id === "email-canvas-host") {
      target.classList.remove("is-loading");
      savedRange = null;
      activeRegion = null;
      bindCanvas(document.getElementById("email-canvas"));
      applyBrandPreview(false);
      updateInsertBar(null);
      var canvas = document.getElementById("email-canvas");
      if (canvas) {
        canvas.classList.remove("is-entering");
        void canvas.offsetWidth;
        canvas.classList.add("is-entering");
      }
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
