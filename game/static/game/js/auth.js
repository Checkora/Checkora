(function () {
    const eyeIcon = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"></path>
            <circle cx="12" cy="12" r="3"></circle>
        </svg>
    `;
    const eyeOffIcon = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
            <path d="M3 3l18 18"></path>
            <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"></path>
            <path d="M9.9 4.2A10.7 10.7 0 0 1 12 4c6.5 0 10 8 10 8a18.5 18.5 0 0 1-3.2 4.4"></path>
            <path d="M6.6 6.6C3.7 8.6 2 12 2 12s3.5 8 10 8c1.2 0 2.3-.2 3.3-.6"></path>
        </svg>
    `;

    function getFieldLabel(input) {
        const label = input.labels?.[0] || input.closest('.form-group')?.querySelector('label');
        const labelText = label?.textContent.trim();

        if (labelText) {
            return labelText;
        }

        return input.getAttribute('name') || 'password';
    }

    function setToggleState(input, toggle, label, isVisible) {
        input.type = isVisible ? 'text' : 'password';
        toggle.innerHTML = isVisible ? eyeOffIcon : eyeIcon;
        toggle.setAttribute('aria-label', `${isVisible ? 'Hide' : 'Show'} ${label}`);
        toggle.setAttribute('aria-pressed', String(isVisible));
    }

    document.querySelectorAll('input').forEach(input => {
        if (input.type !== 'submit') {
            input.classList.add('form-control');
        }
    });

    document.querySelectorAll('input[type="password"]').forEach(input => {
        if (input.closest('.password-field')) {
            return;
        }

        const wrapper = document.createElement('div');
        const toggle = document.createElement('button');
        const label = getFieldLabel(input).toLowerCase();

        wrapper.className = 'password-field';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        toggle.type = 'button';
        toggle.className = 'password-toggle';
        wrapper.appendChild(toggle);
        setToggleState(input, toggle, label, false);

        toggle.addEventListener('click', () => {
            setToggleState(input, toggle, label, input.type === 'password');
        });
    });
})();
