/**
 * Checkora Toast System
 * Modern floating toast notifications with animations,
 * close button, progress bar, and Django integration.
 */

(function () {
    'use strict';

    function ensureContainer() {
        let container = document.getElementById('toast-container');

        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';

            container.style.position = 'fixed';
            container.style.top = '20px';
            container.style.right = '20px';
            container.style.zIndex = '9999';
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.gap = '12px';

            document.body.appendChild(container);
        }

        return container;
    }

    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    window.showToast = function (
        message,
        type = 'info',
        duration = 5000
    ) {

        const container = ensureContainer();

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        toast.style.position = 'relative';
        toast.style.minWidth = '300px';
        toast.style.maxWidth = '420px';
        toast.style.padding = '14px 18px';
        toast.style.borderRadius = '12px';
        toast.style.color = '#fff';
        toast.style.fontWeight = '500';
        toast.style.display = 'flex';
        toast.style.alignItems = 'center';
        toast.style.gap = '12px';
        toast.style.boxShadow = '0 10px 30px rgba(0,0,0,0.25)';
        toast.style.animation = 'slideIn 0.35s ease';
        toast.style.cursor = 'pointer';
        toast.style.overflow = 'hidden';

        const colors = {
            success: '#22c55e',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };

        toast.style.background = colors[type] || colors.info;

        toast.innerHTML = `
            <span style="font-size:20px;">
                ${icons[type] || icons.info}
            </span>

            <span style="flex:1;">
                ${message}
            </span>

            <button class="toast-close"
                style="
                    background:none;
                    border:none;
                    color:white;
                    font-size:18px;
                    cursor:pointer;
                ">
                ×
            </button>

            <div class="toast-progress"
                style="
                    position:absolute;
                    left:0;
                    bottom:0;
                    height:4px;
                    width:100%;
                    background:rgba(255,255,255,0.4);
                    animation:progress ${duration}ms linear forwards;
                ">
            </div>
        `;

        container.appendChild(toast);

        const timeout = setTimeout(() => {
            hideToast(toast);
        }, duration);

        const closeBtn = toast.querySelector('.toast-close');

        closeBtn.onclick = (e) => {
            e.stopPropagation();
            clearTimeout(timeout);
            hideToast(toast);
        };

        
        toast.onclick = () => {
            clearTimeout(timeout);
            hideToast(toast);
        };
    };

    function hideToast(toast) {

        toast.style.animation = 'slideOut 0.3s ease forwards';

        toast.addEventListener('animationend', () => {
            toast.remove();
        });
    }

   
    const originalAlert = window.alert;

    window.alert = function (message) {

        window.showToast(message, 'warning');

        console.log('Browser alert intercepted:', message);
    };

   
    function processDjangoMessages() {

        
        const djangoMessages =
            document.querySelectorAll('.messages .alert');

        djangoMessages.forEach(msg => {

            const text = msg.textContent
                .trim()
                .replace(/^[✅❌⚠️ℹ️]\s*/, '')
                .trim();

            let type = 'info';

            if (msg.classList.contains('alert-success')) {
                type = 'success';
            }
            else if (
                msg.classList.contains('alert-error') ||
                msg.classList.contains('alert-danger')
            ) {
                type = 'error';
            }
            else if (msg.classList.contains('alert-warning')) {
                type = 'warning';
            }

            window.showToast(text, type);

            msg.style.display = 'none';
        });

      
        const formErrors =
            document.querySelectorAll('.errorlist li');

        formErrors.forEach(err => {

            const text = err.textContent.trim();

            if (text) {
                window.showToast(text, 'error');

                const parent = err.closest('.errorlist');

                if (parent) {
                    parent.style.display = 'none';
                }
            }
        });
    }

  
    if (document.readyState === 'loading') {
        document.addEventListener(
            'DOMContentLoaded',
            processDjangoMessages
        );
    } else {
        processDjangoMessages();
    }

    const style = document.createElement('style');

    style.innerHTML = `
        @keyframes slideIn {
            from {
                transform: translateX(120%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(120%);
                opacity: 0;
            }
        }

        @keyframes progress {
            from {
                width: 100%;
            }
            to {
                width: 0%;
            }
        }

        .toast:hover {
            transform: scale(1.02);
            transition: 0.2s ease;
        }

        @media (max-width: 600px) {
            #toast-container {
                left: 10px !important;
                right: 10px !important;
                top: 10px !important;
            }

            .toast {
                min-width: unset !important;
                width: 100%;
            }
        }
    `;

    document.head.appendChild(style);

})();