/**
 * Visible, named messages for HTML5 constraint validation.
 * Native bubbles are skipped for Tom Select (original <select> is hidden and
 * not focusable), so submit otherwise fails with no explanation.
 */
(function () {
    function i18n(key, fallback) {
        var dict = window.I18N || {};
        return dict[key] || fallback;
    }

    function format(template, vars) {
        var out = String(template);
        Object.keys(vars).forEach(function (name) {
            var value = vars[name] != null ? String(vars[name]) : "";
            out = out.split("{" + name + "}").join(value);
            out = out.split("%(" + name + ")s").join(value);
        });
        return out;
    }

    function isValidatable(field) {
        if (!field || field.disabled) return false;
        var type = (field.type || "").toLowerCase();
        if (type === "hidden" || type === "submit" || type === "button" || type === "reset" || type === "image") {
            return false;
        }
        return true;
    }

    function fieldGroup(field) {
        return field.closest(".form-group") || field.parentElement;
    }

    function fieldLabel(field) {
        var group = field.closest(".form-group");
        if (group) {
            var label = group.querySelector("label");
            if (label) return label.textContent.replace(/\s*\*\s*$/, "").trim();
        }
        if (field.labels && field.labels.length) {
            return field.labels[0].textContent.replace(/\s*\*\s*$/, "").trim();
        }
        return field.getAttribute("aria-label") || field.name || i18n("thisField", "This field");
    }

    function messageFor(field) {
        var label = fieldLabel(field);
        if (field.validity.valueMissing) {
            return format(i18n("fieldRequired", "{label} is required."), { label: label });
        }
        if (field.validity.tooShort) {
            return format(i18n("fieldTooShort", "{label} must be at least {min} characters."), {
                label: label,
                min: field.minLength,
            });
        }
        if (field.validity.patternMismatch || field.validity.typeMismatch) {
            return format(i18n("fieldInvalid", "Enter a valid {label}."), { label: label });
        }
        return field.validationMessage || format(i18n("fieldRequired", "{label} is required."), { label: label });
    }

    function showFieldError(field, message) {
        var group = fieldGroup(field);
        if (!group) return;
        var id = (field.id || field.name || "field") + "_js_error";
        var el = group.querySelector(".js-field-error, .field-error");
        if (!el) {
            el = document.createElement("div");
            el.className = "field-error js-field-error";
            el.id = id;
            group.appendChild(el);
        } else {
            el.classList.add("js-field-error");
            if (!el.id) el.id = id;
        }
        el.textContent = message;
        el.hidden = false;
        field.setAttribute("aria-invalid", "true");
        field.setAttribute("aria-describedby", id);
        field.classList.add("is-invalid");
        if (field.tomselect && field.tomselect.wrapper) {
            field.tomselect.wrapper.classList.add("is-invalid");
        }
    }

    function clearFieldError(field) {
        if (!isValidatable(field) || (field.validity && !field.validity.valid)) return;
        var group = fieldGroup(field);
        if (group) {
            var el = group.querySelector(".js-field-error");
            if (el) el.remove();
        }
        field.removeAttribute("aria-invalid");
        field.classList.remove("is-invalid");
        if (field.tomselect && field.tomselect.wrapper) {
            field.tomselect.wrapper.classList.remove("is-invalid");
        }
    }

    function focusInvalid(field) {
        var target = field.tomselect && field.tomselect.control ? field.tomselect.control : field;
        if (target && target.scrollIntoView) {
            target.scrollIntoView({ block: "center", behavior: "smooth" });
        }
        if (field.tomselect) {
            try {
                field.tomselect.focus();
            } catch (err) {}
        } else if (field.focus) {
            try {
                field.focus({ preventScroll: true });
            } catch (err) {
                field.focus();
            }
        }
    }

    document.addEventListener(
        "invalid",
        function (e) {
            var field = e.target;
            if (!isValidatable(field) || !field.form) return;
            if (field.form.classList.contains("no-js-validation")) return;
            e.preventDefault();

            var form = field.form;
            if (!form._jsInvalidBatch) {
                form._jsInvalidBatch = [];
                requestAnimationFrame(function () {
                    var batch = form._jsInvalidBatch || [];
                    form._jsInvalidBatch = null;
                    if (!batch.length) return;
                    batch.forEach(function (item) {
                        showFieldError(item, messageFor(item));
                    });
                    focusInvalid(batch[0]);
                });
            }
            form._jsInvalidBatch.push(field);
        },
        true
    );

    document.addEventListener(
        "input",
        function (e) {
            if (e.target && e.target.form) clearFieldError(e.target);
        },
        true
    );

    document.addEventListener(
        "change",
        function (e) {
            if (e.target && e.target.form) clearFieldError(e.target);
        },
        true
    );

    function markServerInvalid(root) {
        var scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll("select[aria-invalid='true']").forEach(function (select) {
            if (select.tomselect && select.tomselect.wrapper) {
                select.tomselect.wrapper.classList.add("is-invalid");
            }
        });
        scope.querySelectorAll(".form-control[aria-invalid='true']").forEach(function (el) {
            el.classList.add("is-invalid");
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        markServerInvalid(document);
        document.body.addEventListener("htmx:load", function (evt) {
            markServerInvalid(evt.detail && evt.detail.elt ? evt.detail.elt : document);
        });
    });
})();
