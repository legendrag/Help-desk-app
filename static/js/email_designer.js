(function () {
  "use strict";

  var savedRange = null;
  var activeRegion = null;

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

  function applyBrandPreview() {
    var root = designerRoot();
    if (!root) return;
    var name = (document.getElementById("email-brand-name") || {}).value || "mlamehticket";
    var accent = (document.getElementById("email-brand-accent") || {}).value || "#4f46e5";
    var footer = (document.getElementById("email-brand-footer") || {}).value || "";
    root.querySelectorAll("[data-brand-name]").forEach(function (el) {
      el.textContent = name;
    });
    root.querySelectorAll("[data-brand-footer]").forEach(function (el) {
      el.textContent = footer;
    });
    if (/^#[0-9A-Fa-f]{6}$/.test(accent)) {
      root.querySelectorAll("[data-brand-accent]").forEach(function (el) {
        el.style.background = accent;
      });
      root.querySelectorAll("[data-brand-border]").forEach(function (el) {
        el.style.borderLeftColor = accent;
      });
      var mail = root.querySelector(".email-canvas__mail");
      if (mail) mail.style.setProperty("--email-accent", accent);
    }
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

    var picker = document.getElementById("email-brand-color-picker");
    var accent = document.getElementById("email-brand-accent");
    var nameInput = document.getElementById("email-brand-name");
    var footerInput = document.getElementById("email-brand-footer");
    var brandForm = document.getElementById("email-brand-form");

    function onBrandChange() {
      applyBrandPreview();
      markBrandDirty(true);
    }

    if (picker && accent) {
      picker.addEventListener("input", function () {
        accent.value = picker.value;
        onBrandChange();
      });
      accent.addEventListener("input", function () {
        if (/^#[0-9A-Fa-f]{6}$/.test(accent.value)) picker.value = accent.value;
        onBrandChange();
      });
    }
    if (nameInput) nameInput.addEventListener("input", onBrandChange);
    if (footerInput) footerInput.addEventListener("input", onBrandChange);

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
            applyBrandPreview();
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
    applyBrandPreview();
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
      applyBrandPreview();
      updateInsertBar(null);
      var canvas = document.getElementById("email-canvas");
      if (canvas) {
        canvas.classList.remove("is-entering");
        // Force reflow so enter animation can replay
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
