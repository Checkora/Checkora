/**
 * Checkora Toast System
 * Replaces default alerts with modern, floating toast notifications.
 */

(function() {
    'use strict';

    // Create toast container if it doesn't exist
    function ensureContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * Show a toast notification
     * @param {string} message - The message to display
     * @param {string} type - success, error, warning, info
     * @param {number} duration - in milliseconds
     */
    window.showToast = function(message, type = 'info', duration = 5000) {
        const container = ensureContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
        `;

        container.appendChild(toast);

        // Auto remove
        const timeout = setTimeout(() => {
            hideToast(toast);
        }, duration);

        // Allow manual dismissal on click
        toast.onclick = () => {
            clearTimeout(timeout);
            hideToast(toast);
        };
    };

    function hideToast(toast) {
        toast.classList.add('hiding');
        toast.addEventListener('animationend', () => {
            toast.remove();
        });
    }

    // Override window.alert
    const originalAlert = window.alert;
    window.alert = function(message) {
        window.showToast(message, 'warning');
        console.log('Browser alert intercepted:', message);
    };

    // Auto-detect Django messages and show as toasts
    function processDjangoMessages() {
        // 1. Handle Django Messages Framework
        const djangoMessages = document.querySelectorAll('.messages .alert');
        djangoMessages.forEach(msg => {
            const text = msg.textContent.trim().replace(/^[✅❌⚠️ℹ️]\s*/, '').trim();
            let type = 'info';
            
            if (msg.classList.contains('alert-success')) type = 'success';
            else if (msg.classList.contains('alert-error') || msg.classList.contains('alert-danger')) type = 'error';
            else if (msg.classList.contains('alert-warning')) type = 'warning';
            
            window.showToast(text, type);
            msg.style.display = 'none';
        });

        // 2. Handle Django Form Errors (errorlist)
        const formErrors = document.querySelectorAll('.errorlist li');
        formErrors.forEach(err => {
            const text = err.textContent.trim();
            if (text) {
                window.showToast(text, 'error');
                err.closest('.errorlist').style.display = 'none';
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', processDjangoMessages);
    } else {
        processDjangoMessages();
    }

})();
