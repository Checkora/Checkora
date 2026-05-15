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
        e.preventDefault(); // This stops the paste action
        alert("For security, please type your password manually.");
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
});
