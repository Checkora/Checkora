// Behaviour shared by every page: the navbar, menus, dialogs, scroll
// reveals and the cards that lean toward the pointer.
(function() {
    'use strict';

    const root = document.documentElement;
    root.classList.remove('no-js');

    // Streak days follow the player's own clock; the server reads this cookie.
    // IANA names (Asia/Kolkata) are safe as cookie values without escaping.
    try {
        const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (zone && !document.cookie.split('; ').includes(`tz=${zone}`)) {
            document.cookie = `tz=${zone}; path=/; max-age=31536000; samesite=lax`;
        }
    } catch (error) {
        // A browser without Intl time zones keeps UTC days.
    }

    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    function initNav() {
        const nav = document.querySelector('.site-nav');
        if (!nav) return;

        const stick = () => nav.classList.toggle('is-stuck', window.scrollY > 12);
        stick();
        window.addEventListener('scroll', stick, { passive: true });

        const button = nav.querySelector('.nav-menu-button');
        const close = () => {
            nav.classList.remove('is-open');
            button?.setAttribute('aria-expanded', 'false');
        };
        button?.addEventListener('click', () => {
            const open = nav.classList.toggle('is-open');
            button.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        nav.querySelectorAll('.site-nav__links a').forEach((link) => link.addEventListener('click', close));
        window.addEventListener('resize', () => window.innerWidth > 1040 && close());
        document.addEventListener('keydown', (event) => event.key === 'Escape' && close());
    }

    // A menu is a button and the panel it opens. One is open at a time.
    function initMenus() {
        const menus = Array.from(document.querySelectorAll('[data-menu]'));
        const close = (menu) => {
            menu.classList.remove('is-open');
            menu.querySelector('[data-menu-button]')?.setAttribute('aria-expanded', 'false');
        };
        menus.forEach((menu) => {
            const button = menu.querySelector('[data-menu-button]');
            if (!button) return;
            button.setAttribute('aria-expanded', 'false');
            button.addEventListener('click', () => {
                const open = !menu.classList.contains('is-open');
                menus.forEach(close);
                menu.classList.toggle('is-open', open);
                button.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
            menu.addEventListener('focusout', () => {
                window.setTimeout(() => !menu.contains(document.activeElement) && close(menu), 10);
            });
        });
        document.addEventListener('click', (event) => {
            menus.forEach((menu) => !menu.contains(event.target) && close(menu));
        });
        document.addEventListener('keydown', (event) => {
            if (event.key !== 'Escape') return;
            menus.forEach((menu) => {
                if (menu.classList.contains('is-open')) {
                    close(menu);
                    menu.querySelector('[data-menu-button]')?.focus();
                }
            });
        });
    }

    // <button data-open-dialog="id"> opens <dialog id="id">;
    // [data-close-dialog] inside it, or a click on the backdrop, closes it.
    function initDialogs() {
        document.addEventListener('click', (event) => {
            const opener = event.target.closest('[data-open-dialog]');
            if (opener) {
                const dialog = document.getElementById(opener.dataset.openDialog);
                if (dialog && typeof dialog.showModal === 'function') {
                    event.preventDefault();
                    dialog.showModal();
                }
                return;
            }
            const closer = event.target.closest('[data-close-dialog]');
            if (closer) {
                closer.closest('dialog')?.close();
                return;
            }
            if (event.target instanceof HTMLDialogElement && event.target.classList.contains('modal')) {
                event.target.close();
            }
        });
    }

    function initReveals() {
        const items = document.querySelectorAll('[data-reveal]');
        if (!items.length) return;
        if (calm || !('IntersectionObserver' in window)) {
            items.forEach((item) => item.classList.add('is-in'));
            return;
        }
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;
                    entry.target.classList.add('is-in');
                    observer.unobserve(entry.target);
                });
            },
            { rootMargin: '0px 0px -8% 0px', threshold: 0.08 },
        );
        items.forEach((item) => observer.observe(item));
    }

    // Listened for on the document, so a card a page script adds later
    // leans like the ones that were in the page from the start.
    function initTilt() {
        if (calm || !finePointer) return;
        // Not on the low performance tier; and if perf.js moves the page
        // down to it later, the card being leaned is set straight.
        if (window.checkoraPerf && window.checkoraPerf.low) return;
        let off = false;
        let tilted = null;
        const settle = () => {
            if (!tilted) return;
            tilted.classList.remove('is-tilting');
            tilted.style.setProperty('--tilt-x', '0deg');
            tilted.style.setProperty('--tilt-y', '0deg');
            tilted = null;
        };
        document.addEventListener('checkora:perf', () => {
            settle();
            off = true;
        });
        document.addEventListener('pointermove', (event) => {
            if (off) return;
            const card = event.target instanceof Element ? event.target.closest('[data-tilt]') : null;
            if (card !== tilted) settle();
            if (!card) return;
            tilted = card;
            const max = Number(card.dataset.tilt) || 7;
            const box = card.getBoundingClientRect();
            const x = (event.clientX - box.left) / box.width;
            const y = (event.clientY - box.top) / box.height;
            card.classList.add('is-tilting');
            card.style.setProperty('--tilt-x', `${((0.5 - y) * max).toFixed(2)}deg`);
            card.style.setProperty('--tilt-y', `${((x - 0.5) * max).toFixed(2)}deg`);
            card.style.setProperty('--glare-x', `${(x * 100).toFixed(1)}%`);
            card.style.setProperty('--glare-y', `${(y * 100).toFixed(1)}%`);
        });
        // pointerleave does not bubble; this is the pointer going out of the card.
        document.addEventListener('pointerout', (event) => {
            if (tilted && !tilted.contains(event.relatedTarget)) settle();
        });
    }

    function initPasswordReveal() {
        document.querySelectorAll('.field__reveal').forEach((button) => {
            const input = button.closest('.field')?.querySelector('input');
            if (!input) return;
            button.addEventListener('click', () => {
                const show = input.type === 'password';
                input.type = show ? 'text' : 'password';
                button.setAttribute('aria-pressed', show ? 'true' : 'false');
                button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
            });
        });
    }

    function init() {
        initNav();
        initMenus();
        initDialogs();
        initReveals();
        initTilt();
        initPasswordReveal();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
