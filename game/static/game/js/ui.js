import { state, pKey, PIECE_IMG } from './state.js';

export function announceMove(msg) {
    const el = document.getElementById('a11y-announcer');
    if (el) { el.textContent = ''; setTimeout(() => { el.textContent = msg; }, 50); }
}

export function showStatus(msg, err) {
    const gameStatusEl = document.getElementById('game-status');
    const statusEl     = document.getElementById('statusBar');
    if (gameStatusEl) gameStatusEl.textContent = msg;
    if (statusEl) statusEl.className = 'status-bar' + (err ? ' error' : '');
}

export function updateTurn() {
    const badge          = document.getElementById('turnBadge');
    const whiteNameLabel = document.getElementById('whiteNameLabel');
    const blackNameLabel = document.getElementById('blackNameLabel');
    const turnBadgeText  = document.getElementById('turnBadgeText');
    const wCapEl         = document.getElementById('whiteCaptured');
    const bCapEl         = document.getElementById('blackCaptured');

    if (!badge || !whiteNameLabel || !blackNameLabel) return;
    badge.className = 'turn-badge ' + state.turn;
    const pName = state.turn === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;

    let label = pName + "'s Turn";
    if (state.gameMode === 'ai') {
        label = state.turn === state.playerColor ? 'Your Turn' : 'AI is thinking...';
    }
    badge.textContent = label;
    if (turnBadgeText) turnBadgeText.textContent = pName;

    if (wCapEl) wCapEl.classList.toggle('active', state.turn === 'white');
    if (bCapEl) bCapEl.classList.toggle('active', state.turn === 'black');
}

export function updatePlayerNames(data) {
    const whiteNameLabel  = document.getElementById('whiteNameLabel');
    const blackNameLabel  = document.getElementById('blackNameLabel');
    const whiteCapturedName = document.getElementById('whiteCapturedName');
    const blackCapturedName = document.getElementById('blackCapturedName');
    const whiteYouTag     = document.getElementById('whiteYouTag');
    const blackYouTag     = document.getElementById('blackYouTag');

    let wName = data.white_name || 'White';
    let bName = data.black_name || 'Black';

    if (state.gameMode === 'ai') {
        const diffLabel  = (state.currentDifficulty || 'medium').toUpperCase();
        const playerName = state.playerColor === 'white' ? data.white_name : data.black_name;
        if (state.playerColor === 'white') { wName = playerName; bName = 'AI (Black)'; }
        else                               { bName = playerName; wName = 'AI (White)'; }

        setTimeout(() => {
            const aiLabel = state.playerColor === 'white'
                ? document.getElementById('blackNameLabel')
                : document.getElementById('whiteNameLabel');
            if (aiLabel) {
                aiLabel.innerHTML = '';
                const textNode = document.createTextNode(`AI (${state.playerColor === 'white' ? 'BLACK' : 'WHITE'}) `);
                const badge    = document.createElement('span');
                badge.textContent  = diffLabel;
                badge.style.cssText = 'color:#f0c040 !important; font-weight:700; font-size:1.20em; letter-spacing:1px;';
                badge.setAttribute('aria-label', `AI difficulty: ${diffLabel}`);
                aiLabel.appendChild(textNode);
                aiLabel.appendChild(badge);
            }
        }, 0);
    }

    if (whiteNameLabel)    whiteNameLabel.textContent    = wName.toUpperCase();
    if (blackNameLabel)    blackNameLabel.textContent    = bName.toUpperCase();
    if (whiteCapturedName) whiteCapturedName.textContent = wName;
    if (blackCapturedName) blackCapturedName.textContent = bName;

    if (state.gameMode === 'ai') {
        if (whiteYouTag) whiteYouTag.style.display = state.playerColor === 'white' ? 'inline' : 'none';
        if (blackYouTag) blackYouTag.style.display = state.playerColor === 'black' ? 'inline' : 'none';
    } else {
        if (whiteYouTag) whiteYouTag.style.display = 'none';
        if (blackYouTag) blackYouTag.style.display = 'none';
    }
}

export function updateMoves(history) {
    const movesEl = document.getElementById('movesList');
    if (!movesEl) return;
    if (!history?.length) {
        movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
        return;
    }
    movesEl.innerHTML = '';
    for (let i = history.length - 1; i >= 0; i -= 2) {
        const whiteIdx = i % 2 === 0 ? i : i - 1;
        const blackIdx = whiteIdx + 1;
        const moveNum  = Math.floor(whiteIdx / 2) + 1;
        const row      = document.createElement('div');
        row.className  = 'move-row';

        const num = document.createElement('span');
        num.className = 'move-num';
        num.textContent = `${moveNum}.`;
        const w = document.createElement('span');
        w.className = 'move-white';
        w.textContent = history[whiteIdx]?.notation ?? '';
        row.append(num, w);
        if (history[blackIdx]) {
            const b = document.createElement('span');
            b.className = 'move-black';
            b.textContent = history[blackIdx].notation;
            row.appendChild(b);
        }
        
        movesEl.appendChild(row);
    }
}

export function updateCaptured(cap) {
    const wCapEl = document.getElementById('whiteCaptured');
    const bCapEl = document.getElementById('blackCaptured');
    if (!wCapEl || !bCapEl) return;
    wCapEl.innerHTML = bCapEl.innerHTML = '';

    const point_vals = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };
    const whitePoints = cap.white.reduce((s, p) => s + (point_vals[p.toLowerCase()] || 0), 0);
    const blackPoints = cap.black.reduce((s, p) => s + (point_vals[p.toLowerCase()] || 0), 0);

    cap.white.forEach(p => { wCapEl.innerHTML += `<img src="${PIECE_IMG[pKey(p)]}" class="captured-img">`; });
    cap.black.forEach(p => { bCapEl.innerHTML += `<img src="${PIECE_IMG[pKey(p)]}" class="captured-img">`; });

    const wP = document.getElementById('whitePoints');
    const bP = document.getElementById('blackPoints');
    if (wP) wP.textContent = `+${whitePoints}`;
    if (bP) bP.textContent = `+${blackPoints}`;
}