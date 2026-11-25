/*
 * The pages' client for the JSON API (/api/v1/...).
 *
 * - Forms are sent with fetch() as JSON; errors come back as RFC 9457 Problem Details
 *   and are shown next to their fields ("errors") or above the form ("detail").
 * - Instant validation with the SAME rules and messages as the server: they are read
 *   from the JSON config the server renders into the page (common/validation.py is the
 *   single source of truth). This is a convenience only; the API validates again.
 * - Country -> dial code autofill, show/hide password, logout.
 *
 * Authentication is the session cookie (HttpOnly, sent by the browser automatically);
 * state-changing requests carry the CSRF token in the X-CSRFToken header.
 */
(() => {
    "use strict";

    // --- shared helpers -------------------------------------------------------------

    const format = (template, params = {}) =>
        template.replace(/\{(\w+)\}/g, (_, key) => String(params[key]));

    // Length in characters (code points), like Python's len(), not UTF-16 units.
    const charLength = (text) => [...text].length;

    // "a" | "a and b" | "a, b and c" (same as validation._join)
    const joinList = (items) =>
        items.length === 1 ? items[0] : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;

    const LETTER = /\p{L}/u;
    const LATIN_LETTER = /\p{Script=Latin}/u;
    const UPPERCASE = /\p{Lu}/u;
    const DIGIT = /[0-9]/;
    const SYMBOL = /[^\p{L}\p{N}\s]/u;
    const NAME_SEPARATORS = new Set([" ", "-", "'"]);

    // --- rules (mirror common/validation.py) ----------------------------------------

    function buildRules(config) {
        const { limits, labels, messages, passwordRequirements } = config;
        const emailPattern = new RegExp(config.emailPattern);
        const message = (key, params) => format(messages[key], params);
        const required = (field) => message("required", { label: labels[field] });

        const name = (field) => (value) => {
            const label = labels[field];
            const text = value.trim().normalize("NFC");
            const chars = [...text];
            if (!text) return required(field);
            if (chars.length <= limits.name_min_exclusive) {
                return message("name_too_short", { label, min: limits.name_min_exclusive });
            }
            if (chars.length > limits.name_max) {
                return message("name_too_long", { label, max: limits.name_max });
            }
            if (!chars.every((c) => LETTER.test(c) || NAME_SEPARATORS.has(c))) {
                return message("name_characters", { label });
            }
            if (!chars.filter((c) => LETTER.test(c)).every((c) => LATIN_LETTER.test(c))) {
                return message("name_latin", { label });
            }
            if (!LETTER.test(chars[0]) || !LETTER.test(chars.at(-1))) {
                return message("name_edges", { label });
            }
            return null;
        };

        const email = (value) => {
            const text = value.trim();
            if (!text) return required("email");
            if (charLength(text) > limits.email_max) {
                return message("email_too_long", { max: limits.email_max });
            }
            const localPart = text.slice(0, text.lastIndexOf("@"));
            if (!emailPattern.test(text) || charLength(localPart) > limits.email_local_max) {
                return message("email_invalid");
            }
            return null;
        };

        return {
            first_name: name("first_name"),
            last_name: name("last_name"),

            country: (value, form) => {
                if (!value) return message("country_required");
                if (!form.querySelector(`#country option[value="${CSS.escape(value)}"]`)) {
                    return message("country_invalid");
                }
                return null;
            },

            phone_code: (value, form) => {
                const code = value.trim();
                if (!code) return required("phone_code");
                if (!/^[0-9]{1,4}$/.test(code)) return message("code_numeric");
                const expected = form.querySelector("#country")?.selectedOptions[0]?.dataset.dialCode;
                if (expected && code !== expected) return message("code_mismatch");
                return null;
            },

            phone: (value) => {
                const digits = value.replace(/[\s-]/g, "");
                if (!digits) return required("phone");
                if (!/^[0-9]+$/.test(digits)) return message("phone_digits");
                if (digits.length < limits.phone_min || digits.length > limits.phone_max) {
                    return message("phone_length", { min: limits.phone_min, max: limits.phone_max });
                }
                return null;
            },

            email,

            new_password: (value) => {
                if (!value) return required("password");
                const length = charLength(value);
                if (length < limits.password_min) {
                    return message("password_too_short", { min: limits.password_min });
                }
                if (length > limits.password_max) {
                    return message("password_too_long", { max: limits.password_max });
                }
                const missing = [];
                if (!UPPERCASE.test(value)) missing.push(passwordRequirements.capital);
                if (!DIGIT.test(value)) missing.push(passwordRequirements.number);
                if (!SYMBOL.test(value)) missing.push(passwordRequirements.symbol);
                return missing.length ? message("password_missing", { missing: joinList(missing) }) : null;
            },

            // Login: only presence is checked, never the password policy.
            current_password: (value) => (value ? null : required("password")),

            terms: (_value, form) => (form.querySelector("[name=terms]").checked ? null : message("terms_required")),
        };
    }

    const FORMS = {
        register: {
            first_name: "first_name",
            last_name: "last_name",
            country: "country",
            phone_code: "phone_code",
            phone: "phone",
            email: "email",
            password: "new_password",
            terms: "terms",
        },
        login: {
            email: "email",
            password: "current_password",
        },
    };

    // --- API client ------------------------------------------------------------------------

    const GENERIC_ERROR = "Something went wrong. Please try again.";
    const NETWORK_ERROR = "We could not reach the server. Please check your connection and try again.";

    // Read on every request, not once: Django issues a new token at login.
    const csrfToken = () => {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    };

    /** Returns {ok, status, data}; data is the parsed JSON body (or null). Throws on network errors. */
    async function callApi(url, method, body) {
        const headers = { Accept: "application/json", "X-CSRFToken": csrfToken() };
        if (body !== undefined) headers["Content-Type"] = "application/json";

        const response = await fetch(url, {
            method,
            headers,
            body: body === undefined ? undefined : JSON.stringify(body),
            credentials: "same-origin",
        });
        const isJson = /json/.test(response.headers.get("Content-Type") ?? "");
        const data = isJson ? await response.json().catch(() => null) : null;
        return { ok: response.ok, status: response.status, data };
    }

    function showFormError(scope, text) {
        const element = scope.querySelector("[data-form-error]");
        if (!element) return;
        element.textContent = text ?? "";
        element.hidden = !text;
    }

    function setBusy(button, busy) {
        button.disabled = busy;
        button.toggleAttribute("aria-busy", busy);
    }

    // --- error display -----------------------------------------------------------------------

    function showError(input, text) {
        const host = input.closest(".field");
        const marker = input.closest(".phone__code, .phone__number, .field");
        const id = `${input.name}-error`;
        let error = document.getElementById(id);

        if (text) {
            if (!error) {
                error = document.createElement("p");
                error.className = "field__error";
                error.id = id;
                host.append(error);
            }
            error.textContent = text;
            marker.classList.add("field--invalid");
            input.setAttribute("aria-invalid", "true");
            input.setAttribute("aria-describedby", id);
        } else {
            error?.remove();
            marker.classList.remove("field--invalid");
            input.removeAttribute("aria-invalid");
            input.removeAttribute("aria-describedby");
        }

        // Keep messages in the same order as their inputs (Code before Phone).
        for (const field of host.querySelectorAll("input, select")) {
            const fieldError = document.getElementById(`${field.name}-error`);
            if (fieldError) host.append(fieldError);
        }
    }

    function setUpValidation(form, config) {
        const rules = buildRules(config);
        const fieldRules = FORMS[form.dataset.validate];
        const inputs = Object.keys(fieldRules).map((name) => form.elements[name]);
        const touched = new Set();

        const validate = (input) => {
            const rule = rules[fieldRules[input.name]];
            const text = rule(input.value, form);
            showError(input, text);
            return !text;
        };

        for (const input of inputs) {
            // First feedback when the user leaves a field, not while they start typing...
            input.addEventListener("blur", () => {
                touched.add(input.name);
                validate(input);
            });
            // ...then live, so a message disappears as soon as the field is fixed.
            input.addEventListener(input.type === "checkbox" || input.tagName === "SELECT" ? "change" : "input", () => {
                if (touched.has(input.name) || input.getAttribute("aria-invalid")) validate(input);
            });
        }

        // Field errors from the API (400, 409) go under their fields, anything else
        // (401, 403, 429, 5xx) above the form.
        const showProblem = (problem) => {
            const errors = problem?.errors ?? {};
            let first = null;
            for (const [name, text] of Object.entries(errors)) {
                const input = inputs.find((candidate) => candidate.name === name);
                if (input) {
                    showError(input, text);
                    touched.add(name);
                    first ??= input;
                } else {
                    showFormError(form, text);
                }
            }
            if (!Object.keys(errors).length) showFormError(form, problem?.detail ?? GENERIC_ERROR);
            first?.focus();
        };

        const payload = () =>
            Object.fromEntries(
                inputs.map((input) => [input.name, input.type === "checkbox" ? input.checked : input.value]),
            );

        const button = form.querySelector("[type=submit]");

        form.addEventListener("submit", async (event) => {
            event.preventDefault(); // sent by fetch(), not by the browser
            if (button.disabled) return; // a request is already in flight
            showFormError(form, null);

            const invalid = inputs.filter((input) => !validate(input));
            inputs.forEach((input) => touched.add(input.name));
            if (invalid.length) {
                invalid[0].focus();
                return;
            }

            form.dispatchEvent(new Event("api:submit")); // e.g. hide a revealed password
            setBusy(button, true);
            try {
                const result = await callApi(form.dataset.api, "POST", payload());
                if (result.ok) {
                    onSuccess(form, result.data);
                    return; // stays disabled: the page changes
                }
                showProblem(result.data);
            } catch {
                showFormError(form, NETWORK_ERROR);
            }
            setBusy(button, false);
        });

        return validate;
    }

    function onSuccess(form, data) {
        if (form.dataset.successUrl) {
            window.location.assign(form.dataset.successUrl);
            return;
        }
        // Replace the form with the success message, filled in as text (never as HTML).
        const template = document.getElementById(form.dataset.successTemplate);
        const content = template.content.cloneNode(true);
        for (const slot of content.querySelectorAll("[data-field]")) {
            slot.textContent = data?.[slot.dataset.field] ?? "";
        }
        form.closest("[data-replace-on-success]").replaceChildren(content);
    }

    // --- country -> dial code -----------------------------------------------------------

    function setUpDialCode(form, validate) {
        const country = form.querySelector("#country");
        const code = form.querySelector("#phone_code");
        if (!country || !code) return;

        // The code follows from the country (the input is read-only); the API checks the match.
        const sync = () => {
            code.value = country.selectedOptions[0]?.dataset.dialCode ?? "";
            if (code.getAttribute("aria-invalid")) validate(code);
        };
        country.addEventListener("change", sync);
        if (country.value && !code.value) sync();
    }

    // --- show / hide password ------------------------------------------------------------

    const EYE_ICON =
        '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">' +
        '<path fill="currentColor" d="M12 5C6.5 5 2.7 9.1 1.5 12c1.2 2.9 5 7 10.5 7s9.3-4.1 10.5-7C21.3 9.1 17.5 5 12 5zm0 11.5a4.5 4.5 0 1 1 0-9 4.5 4.5 0 0 1 0 9zm0-7a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"/></svg>';
    const EYE_OFF_ICON =
        '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">' +
        '<path fill="currentColor" d="M2.3 3.7 3.7 2.3l18 18-1.4 1.4-3.2-3.2A11.4 11.4 0 0 1 12 19C6.5 19 2.7 14.9 1.5 12a13 13 0 0 1 4-5.1L2.3 3.7zm5.1 5.1A4.5 4.5 0 0 0 15.2 16l-1.6-1.6A2.5 2.5 0 0 1 9.6 10.4L7.4 8.8zM12 5c5.5 0 9.3 4.1 10.5 7a13 13 0 0 1-3.3 4.5l-2.8-2.8A4.5 4.5 0 0 0 10.3 7.6L8.2 5.5C9.4 5.2 10.6 5 12 5z"/></svg>';

    function setUpPasswordToggles() {
        for (const wrapper of document.querySelectorAll(".password")) {
            const input = wrapper.querySelector("input");
            const button = document.createElement("button");
            button.type = "button";
            button.className = "password__toggle";

            const render = () => {
                const visible = input.type === "text";
                button.innerHTML = visible ? EYE_ICON : EYE_OFF_ICON;
                button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
                button.setAttribute("aria-pressed", String(visible));
            };

            button.addEventListener("click", () => {
                input.type = input.type === "password" ? "text" : "password";
                render();
                input.focus();
            });

            // Back to a password field before the form is sent, so the browser never stores
            // the password in its plain-text autofill history.
            input.form?.addEventListener("api:submit", () => {
                input.type = "password";
                render();
            });

            render();
            wrapper.append(button);
            wrapper.classList.add("password--enhanced");
        }
    }

    // --- logout ------------------------------------------------------------------------------

    function setUpLogout() {
        for (const button of document.querySelectorAll("[data-logout]")) {
            button.addEventListener("click", async () => {
                setBusy(button, true);
                try {
                    const result = await callApi(button.dataset.logout, "DELETE");
                    // 204: logged out; 401: the session had already expired. Either way, done.
                    if (result.ok || result.status === 401) {
                        window.location.assign(button.dataset.successUrl);
                        return;
                    }
                    showFormError(document, result.data?.detail ?? GENERIC_ERROR);
                } catch {
                    showFormError(document, NETWORK_ERROR);
                }
                setBusy(button, false);
            });
        }
    }

    // --- start -----------------------------------------------------------------------------

    const form = document.querySelector("form[data-validate]");
    const configElement = document.getElementById("validation-config");
    if (form && configElement) {
        const validate = setUpValidation(form, JSON.parse(configElement.textContent));
        setUpDialCode(form, validate);
    }
    setUpPasswordToggles();
    setUpLogout();
})();
