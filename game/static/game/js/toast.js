/**
 * Checkora toasts: floating notifications in place of browser alerts.
 * Django messages and form errors on the page are shown the same way.
 */
(function() {
    'use strict';

    const ICONS = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    function ensureContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.setAttribute('role', 'status');
            container.setAttribute('aria-live', 'polite');
            document.body.appendChild(container);
        }
        return container;
    }

    // Messages can carry text a user typed (names, form input), so they are
    // set as text and never parsed as HTML.
    function fill(toast, message, type) {
        const kind = ICONS[type] ? type : 'info';
        toast.className = `toast toast-${kind}`;

        const icon = document.createElement('span');
        icon.className = 'toast-icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = ICONS[kind];

        const text = document.createElement('span');
        text.className = 'toast-message';
        text.textContent = String(message);

        toast.replaceChildren(icon, text);
    }

    function hideToast(toast) {
        clearTimeout(toast.dismissTimer);
        toast.classList.add('hiding');
        // Removed on a timer, not on animationend: with reduced motion or a
        // missing stylesheet the animation never runs.
        toast.removeTimer = setTimeout(() => toast.remove(), 300);
    }

    /**
     * Show a toast.
     * @param {string} message - text to display
     * @param {string} type - success, error, warning or info
     * @param {number} duration - milliseconds before it goes away
     * @param {string|null} key - a toast with the same key is updated in place
     */
    window.showToast = function(message, type = 'info', duration = 5000, key = null) {
        const container = ensureContainer();

        let toast = null;
        if (key) {
            toast = Array.from(container.children).find(item => item.dataset.toastKey === String(key)) || null;
        }

        if (!toast) {
            toast = document.createElement('div');
            if (key) {
                toast.dataset.toastKey = key;
            }
            toast.addEventListener('click', () => hideToast(toast));
            container.appendChild(toast);
        }

        // A toast that was on its way out is brought back.
        clearTimeout(toast.removeTimer);
        fill(toast, message, type);
        clearTimeout(toast.dismissTimer);
        toast.dismissTimer = setTimeout(() => hideToast(toast), duration);
    };

    window.alert = function(message) {
        window.showToast(message, 'warning');
    };

    // Confirmations become toasts. Errors and warnings stay where the page
    // put them: a toast is gone in five seconds, and a failed login or a bad
    // field needs to stay readable until it is fixed.
    function processDjangoMessages() {
        document.querySelectorAll('.messages .alert').forEach(msg => {
            const failed = ['alert-error', 'alert-danger', 'alert-warning'].some(name => msg.classList.contains(name));
            if (failed) return;

            const text = msg.textContent.trim().replace(/^[✅❌⚠️ℹ️]\s*/, '').trim();
            if (text) {
                window.showToast(text, msg.classList.contains('alert-success') ? 'success' : 'info');
            }
            // Taken out of the page, and its container with it once empty,
            // so no gap is left where the message was.
            const list = msg.closest('.messages');
            msg.remove();
            if (list && !list.children.length) list.remove();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', processDjangoMessages);
    } else {
        processDjangoMessages();
    }
})();
