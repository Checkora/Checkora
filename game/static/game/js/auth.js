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

  function togglePassword(input, btn) {
    const isHidden = input.type === "password";
    input.type = isHidden ? "text" : "password";
    btn.innerHTML = isHidden ? eyeOffIcon : eyeIcon;
    btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
    btn.setAttribute("aria-pressed", String(isHidden));
  }

  document.querySelectorAll('input[type="password"]').forEach((input, i) => {
    if (!input.id) input.id = "pw-field-" + i;

    const wrapper = document.createElement("div");
    wrapper.className = "pw-input-wrapper";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pw-toggle";
    btn.setAttribute("aria-label", "Show password");
    btn.setAttribute("aria-pressed", "false");
    btn.innerHTML = eyeIcon;
    btn.addEventListener("click", () => togglePassword(input, btn));
    wrapper.appendChild(btn);
  });


  const registerForm = document.getElementById("register-form");
  if (!registerForm) return;

  const usernameInput = document.getElementById("id_username");
  const feedbackEl = document.getElementById("username-feedback");
  const suggestionsEl = document.getElementById("username-suggestions");
  const charCountEl = document.getElementById("username-char-count");
  const submitBtn = document.getElementById("submit-btn");
  const CHECK_URL = registerForm.dataset.checkUrl;

  const MAX_LEN = 20;
  const USERNAME_RE = /^[a-zA-Z0-9_.]{3,20}$/;

  const ICON_OK = '<svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
  const ICON_ERR = '<svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
  const ICON_WARN = '<svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
  const ICON_SPIN = '<span class="spin-icon" aria-hidden="true"></span>';

  function showFeedback(state, message) {
    const icons = { available: ICON_OK, taken: ICON_ERR, invalid: ICON_WARN, loading: ICON_SPIN };
    feedbackEl.className = `username-feedback feedback-${state}`;
    feedbackEl.innerHTML = `${icons[state] || ''}<span>${message}</span>`;
    usernameInput.classList.remove("input-available", "input-taken", "input-invalid");
    if (state === "available") usernameInput.classList.add("input-available");
    else if (state === "taken") usernameInput.classList.add("input-taken");
    else if (state === "invalid") usernameInput.classList.add("input-invalid");
  }

  function clearFeedback() {
    feedbackEl.className = "username-feedback";
    feedbackEl.innerHTML = "";
    suggestionsEl.innerHTML = "";
    usernameInput.classList.remove("input-available", "input-taken", "input-invalid");
  }

  function setSubmit(enabled) {
    submitBtn.disabled = !enabled;
    submitBtn.setAttribute("aria-disabled", String(!enabled));
  }

  function applySuggestion(value) {
    usernameInput.value = value;
    usernameInput.dispatchEvent(new Event("input"));
    usernameInput.focus();
  }

  function renderSuggestions(suggestions) {
    suggestionsEl.innerHTML = "";
    if (!suggestions || suggestions.length === 0) return;

    const label = document.createElement("span");
    label.className = "suggestions-label";
    label.textContent = "Try:";
    suggestionsEl.appendChild(label);

    suggestions.forEach((s) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "suggestion-chip";
      chip.textContent = s;
      chip.setAttribute("aria-label", `Use username ${s}`);
      chip.addEventListener("click", () => applySuggestion(s));
      suggestionsEl.appendChild(chip);
    });
  }

  function debounce(fn, delay) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  let abortController = null;

  async function validateUsername(value) {
    charCountEl.textContent = `${value.length} / ${MAX_LEN}`;
    charCountEl.classList.toggle("char-count-warn", value.length > MAX_LEN - 3);

    clearFeedback();
    setSubmit(false);

    if (value.length === 0) return;

    if (value !== value.trim()) {
      showFeedback("invalid", "Username must not start or end with a space.");
      return;
    }
    if (!USERNAME_RE.test(value)) {
      const msg = value.length < 3
        ? `Username must be at least 3 characters (${value.length}/3).`
        : value.length > MAX_LEN
          ? `Username must be at most ${MAX_LEN} characters (${value.length}/${MAX_LEN}).`
          : "Only letters, numbers, underscores (_), and periods (.) allowed.";
      showFeedback("invalid", msg);
      return;
    }

    showFeedback("loading", "Checking availability…");
    if (abortController) abortController.abort();
    abortController = new AbortController();

    try {
      const url = `${CHECK_URL}?username=${encodeURIComponent(value)}`;
      const resp = await fetch(url, { signal: abortController.signal });
      if (!resp.ok) throw new Error("Network error");
      const data = await resp.json();

      if (data.error) {
        showFeedback("invalid", data.error);
        return;
      }

      if (data.available) {
        showFeedback("available", "Username is available ✓");
        setSubmit(true);
      } else {
        showFeedback("taken", "Username is already taken.");
        renderSuggestions(data.suggestions);
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      showFeedback("invalid", "Could not check availability. Please try again.");
    }
  }

  const debouncedValidate = debounce(validateUsername, 300);

  usernameInput.addEventListener("input", (e) => debouncedValidate(e.target.value));

  if (usernameInput.value) {
    validateUsername(usernameInput.value);
  }

  setSubmit(false);

});
