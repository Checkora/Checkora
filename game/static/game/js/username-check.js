// Says whether the username is free while it is being typed. Used on the
// register page and on the page where a new Google player picks a name.
(function () {
    const script = document.currentScript;
    const usernameInput = document.querySelector('#id_username');
    const checkUsernameUrl = script && script.dataset.checkUrl;

    if (!usernameInput || !checkUsernameUrl) return;

    let debounceTimer;
    let latestVal = '';
    const feedback = document.createElement('span');

    feedback.className = 'field__hint helptext';
    feedback.setAttribute('role', 'status');
    usernameInput.parentNode.appendChild(feedback);

    // The colour comes from the stylesheet, by state.
    const say = (text, state) => {
        feedback.textContent = text;
        feedback.dataset.state = state;
    };

    usernameInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const val = usernameInput.value.trim();
        latestVal = val;

        if (!val) {
            say('', '');
            return;
        }

        debounceTimer = setTimeout(async () => {
            if (val !== latestVal) return;

            try {
                const res = await fetch(
                    `${checkUsernameUrl}?username=${encodeURIComponent(val)}`
                );

                if (!res.ok) throw new Error('Request failed');

                const data = await res.json();

                if (val !== latestVal) return;

                if (data.available) say('Username available', 'ok');
                else say('Username already taken', 'taken');
            } catch (err) {
                say('Could not check username', 'unknown');
            }
        }, 400);
    });
})();
