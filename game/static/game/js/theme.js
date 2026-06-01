(function () {
    'use strict';

    var STORAGE_KEY = 'checkoraColorScheme';
    var VALID = ['light', 'dark'];

    function getStored() {
        try {
            var value = localStorage.getItem(STORAGE_KEY);
            if (value && VALID.indexOf(value) !== -1) {
                return value;
            }
        } catch (e) { /* ignore */ }
        return 'dark';
    }

    function apply(scheme) {
        if (VALID.indexOf(scheme) === -1) {
            scheme = 'dark';
        }
        document.documentElement.setAttribute('data-color-scheme', scheme);
        try {
            localStorage.setItem(STORAGE_KEY, scheme);
        } catch (e) { /* ignore */ }
        syncToggleButtons(scheme);
    }

    function syncToggleButtons(scheme) {
        var next = scheme === 'dark' ? 'light' : 'dark';
        var label = scheme === 'dark'
            ? 'Switch to light mode'
            : 'Switch to dark mode';

        document.querySelectorAll('[data-color-scheme-toggle]').forEach(function (btn) {
            btn.setAttribute('aria-label', label);
            btn.setAttribute('aria-pressed', scheme === 'light' ? 'true' : 'false');
            btn.setAttribute('title', label);
            btn.dataset.nextScheme = next;
        });
    }

    function initToggleButtons() {
        var scheme = document.documentElement.getAttribute('data-color-scheme') || getStored();
        syncToggleButtons(scheme);

        document.querySelectorAll('[data-color-scheme-toggle]').forEach(function (btn) {
            if (btn.dataset.themeBound === 'true') {
                return;
            }
            btn.dataset.themeBound = 'true';
            btn.addEventListener('click', function () {
                var current = document.documentElement.getAttribute('data-color-scheme') || 'dark';
                apply(current === 'dark' ? 'light' : 'dark');
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initToggleButtons);
    } else {
        initToggleButtons();
    }

    window.CheckoraTheme = {
        get: getStored,
        apply: apply,
        toggle: function () {
            var current = document.documentElement.getAttribute('data-color-scheme') || getStored();
            apply(current === 'dark' ? 'light' : 'dark');
        }
    };
})();
