(function () {
  "use strict";

  function designerRoot() {
    return document.getElementById("email-designer");
  }

  function getCsrf() {
    var input = document.querySelector("#email-brand-form [name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var cookie = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return cookie ? decodeURIComponent(cookie[1]) : "";
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

  function showInsertMenu(show) {
    var menu = document.getElementById("email-insert-menu");
    if (!menu) return;
    menu.hidden = !show;
  }

  function insertChip(key, label) {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    var range = sel.getRangeAt(0);
    var node = range.commonAncestorContainer;
    var region = node.nodeType === 1 ? node.closest("[data-region]") : node.parentElement && node.parentElement.closest("[data-region]");
    if (!region || !region.isContentEditable) return;

    var chip = document.createElement("span");
    chip.className = "email-merge-chip";
    chip.setAttribute("data-merge-key", key);
    chip.setAttribute("contenteditable", "false");
    chip.textContent = label;

    range.deleteContents();
    range.insertNode(chip);
    range.setStartAfter(chip);
    range.collapse(true);
    sel.removeAllRanges();
    sel.addRange(range);
    region.focus();
  }

  function bindCanvas(canvas) {
    if (!canvas || canvas.dataset.bound === "1") return;
    canvas.dataset.bound = "1";
    var canEdit = canvas.dataset.canEdit === "true";
    if (!canEdit) return;

    canvas.querySelectorAll("[data-region].is-editable").forEach(function (region) {
      region.addEventListener("focus", function () {
        showInsertMenu(true);
      });
      region.addEventListener("keydown", function (e) {
        if (region.dataset.region === "subject" || region.dataset.region === "button_label" || region.dataset.region === "message_label") {
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
        fetch(url, {
          method: "POST",
          body: body,
          headers: { "HX-Request": "true", "X-CSRFToken": getCsrf() },
          credentials: "same-origin",
        })
          .then(function (res) {
            if (!res.ok) throw new Error("Save failed");
            saveBtn.textContent = "Saved";
            setTimeout(function () {
              saveBtn.textContent = "Save this email";
            }, 1200);
          })
          .catch(function () {
            alert("Could not save this email. Check the fields and try again.");
          })
          .finally(function () {
            saveBtn.disabled = false;
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

    if (picker && accent) {
      picker.addEventListener("input", function () {
        accent.value = picker.value;
        applyBrandPreview();
      });
      accent.addEventListener("input", function () {
        if (/^#[0-9A-Fa-f]{6}$/.test(accent.value)) picker.value = accent.value;
        applyBrandPreview();
      });
    }
    if (nameInput) nameInput.addEventListener("input", applyBrandPreview);
    if (footerInput) footerInput.addEventListener("input", applyBrandPreview);

    var brandForm = document.getElementById("email-brand-form");
    if (brandForm && root.dataset.canEdit === "true") {
      brandForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var url = root.dataset.brandSaveUrl;
        var body = new FormData(brandForm);
        var btn = document.getElementById("email-brand-save-btn");
        if (btn) btn.disabled = true;
        fetch(url, {
          method: "POST",
          body: body,
          headers: { "HX-Request": "true", "X-CSRFToken": getCsrf() },
          credentials: "same-origin",
        })
          .then(function (res) {
            if (!res.ok) throw new Error("Save failed");
            if (btn) {
              var prev = btn.textContent;
              btn.textContent = "Saved";
              setTimeout(function () {
                btn.textContent = prev;
              }, 1200);
            }
            applyBrandPreview();
          })
          .catch(function () {
            alert("Could not save email look.");
          })
          .finally(function () {
            if (btn) btn.disabled = false;
          });
      });
    }

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
      }
    });

    var select = document.getElementById("email-type-select");
    if (select) {
      select.addEventListener("change", function () {
        var type = select.value;
        root.querySelectorAll(".email-type-btn").forEach(function (btn) {
          btn.classList.toggle("is-active", btn.dataset.eventType === type);
        });
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
      bindCanvas(document.getElementById("email-canvas"));
      applyBrandPreview();
      showInsertMenu(false);
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
