document.addEventListener("DOMContentLoaded", () => {
  /* ── SVG icons (inline – no external dependency) ── */
  const eyeIcon =
    '<svg aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" ' +
    'width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>' +
    '<circle cx="12" cy="12" r="3"/></svg>';

  const eyeOffIcon =
    '<svg aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" ' +
    'width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>' +
    '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>' +
    '<line x1="1" y1="1" x2="23" y2="23"/></svg>';

  /* ── Toggle handler ── */
  function togglePassword(input, btn) {
    const isHidden = input.type === "password";
    input.type = isHidden ? "text" : "password";
    btn.innerHTML = isHidden ? eyeOffIcon : eyeIcon;
    btn.setAttribute(
      "aria-label",
      isHidden ? "Hide password" : "Show password"
    );
    btn.setAttribute("aria-pressed", String(isHidden));
  }

  /* ── Inject toggle into every password field ── */
  document.querySelectorAll('input[type="password"]').forEach((input, i) => {
    if (!input.id) input.id = "pw-field-" + i;
    // This checks if the field name contains 'confirm' or '2' (standard Django naming)
    if (input.name.includes("confirm") || input.name.includes("2")|| input.id.includes("confirm")) {
      input.addEventListener("paste", (e) => {
        e.preventDefault();
        const msg = document.createElement("div");
        msg.setAttribute("role", "alert");
        msg.className = "paste-block-msg";
        msg.textContent = "For security, please type your password manually.";
        input.parentNode.parentNode.insertBefore(msg, input.parentNode.nextSibling);
        setTimeout(() => msg.remove(), 3000);
      });
    }
    /* Create a wrapper that sits inside .form-group, around the input only.
       This keeps the toggle button positioned relative to the input,
       regardless of labels, help-text or error messages around it. */
    const wrapper = document.createElement("div");
    wrapper.className = "pw-input-wrapper";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    /* Build toggle button */
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pw-toggle";
    btn.setAttribute("aria-label", "Show password");
    btn.setAttribute("aria-pressed", "false");
    btn.innerHTML = eyeIcon;
    btn.addEventListener("click", () => togglePassword(input, btn));
    wrapper.appendChild(btn);
  });

  /* ── Loading spinner on form submit ── */
  document.querySelectorAll(".auth-card form").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector('button[type="submit"]');
      if (btn && !btn.classList.contains("is-loading")) {
        btn.classList.add("is-loading");
        btn.setAttribute("disabled", "disabled");
      }
    });
  });

  /* Reset button state when user navigates back (bfcache) */
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) {
      document.querySelectorAll(".btn.is-loading").forEach((btn) => {
        btn.classList.remove("is-loading");
        btn.removeAttribute("disabled");
      });
    }
  });

  /* ── Password validation checklist (register page only) ── */
  const passwordInput = document.querySelector('input[name="password1"]');
  if (passwordInput) {
    const rules = [
      { id: "rule-length", text: "Minimum 8 characters", test: (v) => v.length >= 8 },
      { id: "rule-upper", text: "At least 1 uppercase letter", test: (v) => /[A-Z]/.test(v) },
      { id: "rule-number", text: "At least 1 number", test: (v) => /[0-9]/.test(v) },
      { id: "rule-special", text: "At least 1 special character", test: (v) => /[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;'/`~]/.test(v) },
    ];

    const checklist = document.createElement("ul");
    checklist.className = "password-checklist";
    checklist.setAttribute("role", "status");
    checklist.setAttribute("aria-live", "polite");

    rules.forEach((rule) => {
      const li = document.createElement("li");
      li.id = rule.id;
      li.innerHTML = `<span class="check-icon" aria-hidden="true"></span>${rule.text}`;
      checklist.appendChild(li);
    });

    // Insert checklist after the password input wrapper
    const wrapper = passwordInput.closest(".pw-input-wrapper") || passwordInput.parentNode;
    wrapper.parentNode.insertBefore(checklist, wrapper.nextSibling);

    // Real-time validation
    const validatePassword = () => {
      const value = passwordInput.value;
      let allMet = true;

      rules.forEach((rule) => {
        const li = document.getElementById(rule.id);
        const met = rule.test(value);
        li.classList.toggle("met", met);
        if (!met) allMet = false;
      });

      checklist.classList.toggle("all-met", allMet && value.length > 0);
    };

    passwordInput.addEventListener("input", validatePassword);
    validatePassword(); // Run on initial load (handles autofill/form restoration)
  }
});
