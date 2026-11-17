// How the play page looks and feels, apart from the game itself.
// board.js owns the game: this file never calls the game API and never
// changes a move, a clock or a result. It is loaded before board.js so the
// board theme and the 3D view are in place before the board is drawn.
(function() {
    'use strict';

    const root = document.documentElement;
    const byId = (id) => document.getElementById(id);
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const store = {
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
                // Storage can be blocked; the choice then lasts for the page.
            }
        },
    };

    /* ---------- board theme ---------- */

    // board.js falls back to "classic" when the attribute is missing, so the
    // new default has to be on <html> before it runs.
    const BOARD_THEMES = ['gilded', 'classic', 'wood', 'slate', 'neon', 'glass', 'dark', 'green', 'blue', 'pastel'];
    const savedBoard = [store.get('boardTheme'), store.get('chessBoardTheme')].find((name) => BOARD_THEMES.includes(name));
    root.setAttribute('data-board-theme', savedBoard || 'gilded');

    /* ---------- 3D view ---------- */

    const VIEW_KEY = 'checkoraBoard3d';
    // Off until asked for on phones and other touch-only screens, where a
    // tilted board makes the far squares small under a finger.
    const smallOrTouch = window.matchMedia('(max-width: 759px), (hover: none) and (pointer: coarse)');
    // Also off until asked for on the low performance tier (see perf.js):
    // a tilted board is a layer for every square and every piece.
    const lowTier = () => Boolean(window.checkoraPerf && window.checkoraPerf.low);
    let leaveTimer = 0;

    function saved3d() {
        const saved = store.get(VIEW_KEY);
        if (saved === '1') return true;
        if (saved === '0') return false;
        return !smallOrTouch.matches && !lowTier();
    }

    function show3d(on, remember) {
        const button = byId('view3dBtn');
        window.clearTimeout(leaveTimer);
        if (!on && root.classList.contains('board-3d') && !calm) {
            // Keep the 3D space until the board has finished lying flat.
            root.classList.add('board-3d-leaving');
            leaveTimer = window.setTimeout(() => root.classList.remove('board-3d-leaving'), 850);
        } else {
            root.classList.remove('board-3d-leaving');
        }
        root.classList.toggle('board-3d', on);
        if (button) button.setAttribute('aria-pressed', on ? 'true' : 'false');
        if (remember) store.set(VIEW_KEY, on ? '1' : '0');
    }

    show3d(saved3d(), false);

    // perf.js can move the page down to the low tier in the middle of a
    // game. A board that is tilted only because that was the default then
    // lies flat; a player who asked for 3D keeps it.
    document.addEventListener('checkora:perf', () => {
        if (root.classList.contains('board-3d') && store.get(VIEW_KEY) !== '1') show3d(false, false);
    });

    function dialogOpen() {
        if (document.querySelector('.promo-overlay.active, .theme-settings-modal.active')) return true;
        return ['sideModal', 'resignModal', 'rulebookModal', 'shareModal', 'tourOverlay'].some((id) => {
            const element = byId(id);
            return element && element.style.display && element.style.display !== 'none';
        });
    }

    function init3d() {
        const button = byId('view3dBtn');
        if (!button) return;
        button.setAttribute('aria-pressed', root.classList.contains('board-3d') ? 'true' : 'false');
        button.addEventListener('click', () => show3d(!root.classList.contains('board-3d'), true));

        document.addEventListener('keydown', (event) => {
            if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
            if (event.key !== 'v' && event.key !== 'V') return;
            const tag = document.activeElement && document.activeElement.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
            if (dialogOpen()) return;
            event.preventDefault();
            show3d(!root.classList.contains('board-3d'), true);
        });
    }

    /* ---------- the game coming on screen ---------- */

    // board.js shows the game by setting visibility on .game-layout. The
    // panels' entrance is tied to a class so it plays each time that happens.
    function initEntrance() {
        const layout = document.querySelector('.game-layout');
        if (!layout) return;
        const sync = () => layout.classList.toggle('is-live', layout.style.visibility === 'visible');
        new MutationObserver(sync).observe(layout, { attributes: true, attributeFilter: ['style'] });
        sync();
    }

    /* ---------- the phone bar and the drawer ---------- */

    function initPhoneBar() {
        // A bar button presses the real control, so there is one of each.
        document.querySelectorAll('[data-press]').forEach((proxy) => {
            const target = byId(proxy.dataset.press);
            if (!target) return;
            proxy.addEventListener('click', () => target.click());
            // When board.js hides the control (the game is over), its copy goes too.
            const sync = () => {
                proxy.hidden = target.style.display === 'none';
            };
            new MutationObserver(sync).observe(target, { attributes: true, attributeFilter: ['style'] });
            sync();
        });

        // board.js keeps the pause button's aria-label current; the word
        // under the icon follows it.
        const pauseFab = byId('pauseFab');
        const pauseWord = pauseFab && pauseFab.querySelector('span');
        if (pauseFab && pauseWord) {
            new MutationObserver(() => {
                pauseWord.textContent = pauseFab.getAttribute('aria-label') || 'Pause';
            }).observe(pauseFab, { attributes: true, attributeFilter: ['aria-label'] });
        }

        // A tap outside the drawer closes it.
        const drawer = byId('mobilePanel');
        const toggle = byId('mobileControlsToggle');
        const close = byId('mobileControlsClose');
        if (drawer && close) {
            document.addEventListener('pointerdown', (event) => {
                if (!drawer.classList.contains('active')) return;
                if (drawer.contains(event.target) || (toggle && toggle.contains(event.target))) return;
                // The tour covers the page and opens the drawer itself to point into it.
                if (event.target.closest('.promo-overlay, .theme-settings-modal, .frame-modal, .share-modal, .tour-overlay')) return;
                close.click();
            });
            // Opening a dialog from the drawer, or tilting the board, puts the
            // drawer away so what was asked for can be seen.
            drawer.addEventListener('click', (event) => {
                if (event.target.closest('#openThemeModalBtn, #shortcutsBtn, #rulebookBtn, #newFenBtn, #view3dBtn')) close.click();
            });
        }
    }

    /* ---------- the rulebook and the share dialog ---------- */

    function initFrames() {
        const modal = byId('rulebookModal');
        const frame = byId('rulebookFrame');
        const opener = byId('rulebookBtn');
        const closer = byId('rulebookCloseBtn');
        if (modal && opener && closer) {
            let returnTo = null;
            // board.js closes this on Escape by reading style.display, so
            // it is opened the same way.
            const open = () => {
                if (frame && !frame.getAttribute('src')) frame.setAttribute('src', frame.dataset.src);
                returnTo = document.activeElement;
                modal.style.display = 'flex';
                closer.focus();
            };
            const close = () => {
                modal.style.display = 'none';
                if (returnTo && typeof returnTo.focus === 'function') returnTo.focus();
                returnTo = null;
            };
            opener.addEventListener('click', open);
            closer.addEventListener('click', close);
            modal.addEventListener('click', (event) => event.target === modal && close());
        }

        const share = byId('shareModal');
        if (share) {
            share.addEventListener('click', (event) => {
                if (event.target === share) share.style.display = 'none';
            });
        }
    }

    /* ---------- setup ---------- */

    // A select marked data-segmented becomes a row of buttons. The select
    // stays in the page, hidden, and keeps the value board.js reads.
    function segment(select) {
        const label = document.querySelector(`label[for="${select.id}"]`);
        const group = document.createElement('div');
        group.className = 'seg';
        group.setAttribute('role', 'radiogroup');
        if (label) {
            if (!label.id) label.id = `${select.id}Label`;
            group.setAttribute('aria-labelledby', label.id);
        }
        const buttons = Array.from(select.options).map((option) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.setAttribute('role', 'radio');
            button.dataset.value = option.value;
            button.textContent = option.textContent;
            group.append(button);
            return button;
        });
        const paint = () => buttons.forEach((button) => {
            const on = button.dataset.value === select.value;
            button.setAttribute('aria-checked', on ? 'true' : 'false');
            button.tabIndex = on ? 0 : -1;
        });
        const choose = (button, focus) => {
            select.value = button.dataset.value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
            paint();
            if (focus) button.focus();
        };
        buttons.forEach((button, index) => {
            button.addEventListener('click', () => choose(button, false));
            button.addEventListener('keydown', (event) => {
                const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
                if (!step) return;
                event.preventDefault();
                choose(buttons[(index + step + buttons.length) % buttons.length], true);
            });
        });
        select.addEventListener('change', paint);
        select.hidden = true;
        select.after(group);
        paint();
    }

    // The names typed last time come back, so a returning player only has
    // to choose an opponent. A signed-in player's own name is already in
    // the field, put there by the template.
    function initNames() {
        const white = byId('whiteNameInput');
        const black = byId('blackNameInput');
        const fields = [[white, 'checkoraPlayerName'], [black, 'checkoraOpponentName']];
        fields.forEach(([input, key]) => {
            if (!input) return;
            const saved = store.get(key);
            if (!input.value && saved) input.value = saved.slice(0, Number(input.maxLength) > 0 ? input.maxLength : 17);
            input.addEventListener('input', () => store.set(key, input.value.trim()));
        });
    }

    // The board on the setup screen: the starting position in CSS 3D, with
    // a name plate for each side. It turns to show the side you will play.
    function initSeat() {
        const stage = byId('seatStage');
        const overlay = byId('welcomeOverlay');
        if (!stage || !overlay) return;

        // An illustration, so it always uses the classic set.
        const base = `${root.dataset.static || '/static/game/'}pieces/classic/`;
        const backRank = ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'];

        const seat = document.createElement('div');
        seat.className = 'seat';
        seat.dataset.seat = 'white';
        const board = document.createElement('div');
        board.className = 'seat__board';
        let order = 0;
        [[0, 'b', null], [1, 'b', 'p'], [6, 'w', 'p'], [7, 'w', null]].forEach(([rank, colour, type]) => {
            for (let file = 0; file < 8; file++) {
                const piece = document.createElement('img');
                piece.className = 'seat__piece';
                piece.alt = '';
                piece.src = `${base}${colour}${type || backRank[file]}.svg`;
                piece.style.setProperty('--f', file);
                piece.style.setProperty('--r', rank);
                piece.style.setProperty('--i', order++);
                board.append(piece);
            }
        });
        const table = document.createElement('div');
        table.className = 'seat__table';
        table.append(board);

        const plate = (where) => {
            const element = document.createElement('div');
            element.className = `seat__plate seat__plate--${where}`;
            const dot = document.createElement('span');
            dot.className = 'seat-dot';
            const name = document.createElement('b');
            element.append(dot, name);
            return { element, dot, name };
        };
        const far = plate('far');
        const near = plate('near');
        const clock = document.createElement('div');
        clock.className = 'seat__clock';
        const row = document.createElement('div');
        row.className = 'seat__row';
        row.append(near.element, clock);
        seat.append(far.element, table, row);
        stage.replaceChildren(seat);

        const white = byId('whiteNameInput');
        const black = byId('blackNameInput');
        const engineOptions = byId('pveOptions');
        const strength = byId('welcomeDifficultySelect');
        const clockText = byId('tcDisplayText');

        function paint() {
            const againstEngine = Boolean(engineOptions) && engineOptions.style.display === 'flex';
            const chosen = overlay.querySelector('.color-choice.active');
            const side = againstEngine && chosen ? chosen.dataset.color : 'white';
            seat.dataset.seat = side;

            const whiteName = (white && white.value.trim()) || (againstEngine ? 'You' : 'White');
            const level = strength ? strength.options[strength.selectedIndex].textContent : '';
            const blackName = againstEngine ? `Engine · ${level}` : (black && black.value.trim()) || 'Black';

            // In an engine game the name typed is yours whichever side you take.
            const nearIsBlack = side === 'black';
            near.name.textContent = whiteName;
            far.name.textContent = blackName;
            near.dot.className = `seat-dot seat-dot--${side === 'random' ? 'random' : nearIsBlack ? 'black' : 'white'}`;
            far.dot.className = `seat-dot seat-dot--${side === 'random' ? 'random' : nearIsBlack ? 'white' : 'black'}`;
            clock.textContent = clockText ? clockText.textContent.trim() : '';
        }

        // board.js changes this screen through inline styles, classes and
        // text, so one observer over the whole card catches every case. The
        // card only: the board drawn here is in the same overlay, and
        // watching it would have this function answer its own changes.
        const card = overlay.querySelector('.setup__card') || overlay;
        let queued = 0;
        const queue = () => {
            if (queued) return;
            queued = window.requestAnimationFrame(() => {
                queued = 0;
                paint();
            });
        };
        new MutationObserver(queue).observe(card, {
            subtree: true,
            childList: true,
            characterData: true,
            attributes: true,
            attributeFilter: ['style', 'class'],
        });
        card.addEventListener('input', queue);
        card.addEventListener('change', queue);
        paint();
    }

    function init() {
        init3d();
        initEntrance();
        initPhoneBar();
        initFrames();
        document.querySelectorAll('select[data-segmented]').forEach(segment);
        initNames();
        initSeat();
    }

    // The script tag sits after the page's markup, so everything it needs
    // is already there.
    init();
})();
