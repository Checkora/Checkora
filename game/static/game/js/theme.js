// Light and dark theme. Loaded in <head> so the saved theme is on the page
// before anything is painted; the buttons are wired once the DOM is ready.
(function() {
    'use strict';

    const storage = {
        get(key) {
            try {
                return window.localStorage.getItem(key);
            } catch (error) {
                return null;
            }
        },
        set(key, value) {
            try {
                window.localStorage.setItem(key, value);
            } catch (error) {
                // Storage can be blocked; the theme then lasts for the page.
            }
        },
    };

    const valid = (value) => (value === 'light' || value === 'dark' ? value : null);
    // 'chessBoardTheme' is where an older version kept the same setting.
    const saved = valid(storage.get('theme')) || valid(storage.get('chessBoardTheme')) || 'dark';
    const root = document.documentElement;
    root.setAttribute('data-theme', saved);

    function describe(toggle, theme) {
        toggle.setAttribute('type', 'button');
        toggle.setAttribute('aria-pressed', theme === 'light' ? 'true' : 'false');
        toggle.setAttribute('aria-label', theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode');
        // A toggle with no icons inside falls back to a text symbol.
        if (!toggle.children.length) {
            toggle.textContent = theme === 'light' ? '☀️' : '🌙';
        }
    }

    function setTheme(theme) {
        root.classList.add('theme-transition');
        root.setAttribute('data-theme', theme);
        storage.set('theme', theme);
        document.querySelectorAll('.theme-toggle').forEach((toggle) => describe(toggle, theme));
        document.dispatchEvent(new CustomEvent('checkora:theme', { detail: { theme } }));
        window.setTimeout(() => root.classList.remove('theme-transition'), 320);
    }

    window.checkoraTheme = {
        get: () => root.getAttribute('data-theme'),
        set: (theme) => valid(theme) && setTheme(theme),
    };

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.theme-toggle').forEach((toggle) => {
            describe(toggle, root.getAttribute('data-theme'));
            toggle.addEventListener('click', () => {
                setTheme(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light');
            });
        });
    });
})();
