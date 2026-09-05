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

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
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
            field.tomselect.wrapper.classList.add("invalid");
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
            field.tomselect.wrapper.classList.remove("invalid");
        }
        refreshSummary(field.form);
    }

    function insertSummary(form, labels) {
        var existing = form.querySelector(".js-form-error-summary, .form-error-summary");
        if (existing) existing.remove();
        if (!labels.length) return;

        var el = document.createElement("div");
        el.className = "notice notice-error form-error-summary js-form-error-summary";
        el.setAttribute("role", "alert");
        var heading = i18n("completeTheFollowing", "Please complete the following:");
        el.innerHTML =
            "<div><strong>" +
            escapeHtml(heading) +
            '</strong><ul class="form-error-summary__list">' +
            labels
                .map(function (label) {
                    return "<li>" + escapeHtml(label) + "</li>";
                })
                .join("") +
            "</ul></div>";

        var actions = form.querySelector(".form-actions, .form-actions--end, .form-actions--spaced");
        if (actions && actions.parentNode) {
            actions.parentNode.insertBefore(el, actions);
        } else {
            var host = form.querySelector(".modal-body") || form.querySelector(".form-stack") || form;
            host.insertBefore(el, host.firstChild);
        }
    }

    function refreshSummary(form) {
        if (!form) return;
        var remaining = [];
        var seen = {};
        form.querySelectorAll(".js-field-error").forEach(function (el) {
            var text = (el.textContent || "").trim();
            if (text && !seen[text]) {
                seen[text] = true;
                remaining.push(text);
            }
        });
        insertSummary(form, remaining);
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
                    var labels = [];
                    var seen = {};
                    batch.forEach(function (item) {
                        var msg = messageFor(item);
                        showFieldError(item, msg);
                        if (!seen[msg]) {
                            seen[msg] = true;
                            labels.push(msg);
                        }
                    });
                    insertSummary(form, labels);
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
                select.tomselect.wrapper.classList.add("invalid");
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
