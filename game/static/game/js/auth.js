document.addEventListener("DOMContentLoaded", () => {
  const eyeIcon = '<svg aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  const eyeOffIcon = '<svg aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

  function togglePw(id, btn) {
    const input = document.getElementById(id);
    const isHidden = input.type === "password";
    input.type = isHidden ? "text" : "password";
    btn.innerHTML = isHidden ? eyeOffIcon : eyeIcon;
    btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
    btn.setAttribute("aria-pressed", isHidden ? "true" : "false");
  }

  document.querySelectorAll('input[type="password"]').forEach((input, i) => {
    if (!input.id) input.id = "pw-field-" + i;
    input.classList.add("password-with-toggle");
    const parent = input.closest(".form-group") || input.parentNode;
    if (parent && parent.classList) parent.classList.add("pw-parent");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pw-toggle";
    btn.setAttribute("aria-label", "Show password");
    btn.setAttribute("aria-pressed", "false");
    btn.innerHTML = eyeIcon;
    btn.onclick = () => togglePw(input.id, btn);
    parent.appendChild(btn);

    const positionToggle = () => {
      const top = input.offsetTop + input.offsetHeight / 2;
      btn.style.top = top + "px";
    };

    positionToggle();
    window.addEventListener("resize", positionToggle);
  });
});
