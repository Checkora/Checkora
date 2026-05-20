import { state, pKey, pColor, PIECE_IMG, MATERIAL_VALUES } from './state.js';

const boardEl = () => document.getElementById('board');

// sq() helper — exported so animations.js can use it
export function sq(r, c) {
    const vr = state.flipped ? 7 - r : r;
    const vc = state.flipped ? 7 - c : c;
    return boardEl().children[vr * 8 + vc];
}

export function getSquareLabel(row, col) {
    const files = ['a','b','c','d','e','f','g','h'];
    const ranks = ['8','7','6','5','4','3','2','1'];
    return files[col] + ranks[row];
}

export function buildBoard() {
    const el = boardEl();
    el.innerHTML = '';
    for (let vr = 0; vr < 8; vr++) {
        for (let vc = 0; vc < 8; vc++) {
            const r = state.flipped ? 7 - vr : vr;
            const c = state.flipped ? 7 - vc : vc;
            const d = document.createElement('div');
            d.className = 'square ' + ((vr + vc) % 2 ? 'dark' : 'light');
            d.dataset.r = r;
            d.dataset.c = c;

            d.setAttribute('tabindex', '0');
            d.setAttribute('role', 'gridcell');
            d.setAttribute('data-row', r);
            d.setAttribute('data-col', c);
            d.setAttribute('aria-label', getSquareLabel(r, c));

            d.onclick    = () => import('./moves.js').then(m => m.onClick(r, c));
            d.ondragover = e => e.preventDefault();
            d.ondrop     = e => import('./moves.js').then(m => m.onDrop(e, r, c));
            d.draggable  = true;

            d.ondragstart = e => {
                const piece = state.board[r][c];
                if (!piece || pColor(piece) !== state.turn || state.paused || state.gameOver) return e.preventDefault();
                if (state.gameMode === 'ai' && state.turn !== state.playerColor) return e.preventDefault();
                if (e.dataTransfer) { e.dataTransfer.setData('text/plain', 'piece-move'); e.dataTransfer.effectAllowed = 'move'; }
                const pieceImg = d.querySelector('.piece');
                if (pieceImg) e.dataTransfer.setDragImage(pieceImg, pieceImg.offsetWidth / 2, pieceImg.offsetHeight / 2);
                state.dragging = true;
                state.dragSrc  = { r, c };
                setTimeout(() => import('./moves.js').then(m => m.selectPiece(r, c)), 10);
            };
            d.ondragend = () => { state.dragging = false; state.dragSrc = null; };
            d.onkeydown = e => handleSquareKeydown(e, r, c);

            el.appendChild(d);
        }
    }
    syncPieces();
    updateLabels();
}

export function updateLabels() {
    const ranks = ['8','7','6','5','4','3','2','1'];
    const files = ['a','b','c','d','e','f','g','h'];
    if (state.flipped) { ranks.reverse(); files.reverse(); }
    const rL = document.getElementById('ranksLabels');
    const fL = document.getElementById('filesLabels');
    if (rL) rL.innerHTML = ranks.map(r => `<span>${r}</span>`).join('');
    if (fL) fL.innerHTML = files.map(f => `<span>${f}</span>`).join('');
}

export function syncPieces() {
    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            const el = sq(r, c);
            el.innerHTML = '';
            const p = state.board[r][c];
            if (!p) continue;
            const img = document.createElement('img');
            img.src       = PIECE_IMG[pKey(p)];
            img.className = 'piece';
            img.draggable = false;
            img.ondragover = e => e.preventDefault();
            el.appendChild(img);
        }
    }
    refreshHighlights();
    markPlayable();
    updateMaterialUI();
}

export function markPlayable() {
    boardEl().querySelectorAll('.piece').forEach(img => {
        const el = img.closest('.square');
        const r  = parseInt(el.dataset.r);
        const c  = parseInt(el.dataset.c);
        const p  = state.board[r][c];
        const ok = p && pColor(p) === state.turn && !(state.gameMode === 'ai' && state.turn !== state.playerColor);
        img.classList.toggle('playable', ok);
    });
}

export function refreshHighlights() {
    boardEl().querySelectorAll('.square').forEach(el => {
        el.classList.remove('selected', 'last-move', 'in-check');
        el.querySelectorAll('.move-dot, .capture-ring').forEach(n => n.remove());
    });
    if (state.lastMove) {
        sq(state.lastMove.from[0], state.lastMove.from[1]).classList.add('last-move');
        sq(state.lastMove.to[0],   state.lastMove.to[1]).classList.add('last-move');
    }
    if (state.selected) {
        sq(state.selected.r, state.selected.c).classList.add('selected');
        state.hints.forEach(h => {
            const el = sq(h.row, h.col);
            const d  = document.createElement('div');
            d.className = h.is_capture ? 'capture-ring' : 'move-dot';
            el.appendChild(d);
        });
    }
}

export function highlightCheck() {
    boardEl().querySelectorAll('.square').forEach(el => el.classList.remove('in-check'));
}

export function applyCheckHighlight() {
    highlightCheck();
    const kingPiece = state.turn === 'white' ? 'K' : 'k';
    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            if (state.board[r][c] === kingPiece) { sq(r, c).classList.add('in-check'); return; }
        }
    }
}

export function updateMaterialUI() {
    let white = 0, black = 0;
    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            const p = state.board[r][c];
            if (!p) continue;
            const v = MATERIAL_VALUES[p.toLowerCase()] || 0;
            p === p.toUpperCase() ? white += v : black += v;
        }
    }
    const ws = document.getElementById('whiteScore');
    const bs = document.getElementById('blackScore');
    if (ws) ws.innerText = white;
    if (bs) bs.innerText = black;
}

export function toggleBoardOrientation() {
    state.flipped = !state.flipped;
    buildBoard();
}

function handleSquareKeydown(e, row, col) {
    let newRow = row, newCol = col;
    switch (e.key) {
        case 'ArrowUp':    e.preventDefault(); newRow = row - 1; break;
        case 'ArrowDown':  e.preventDefault(); newRow = row + 1; break;
        case 'ArrowLeft':  e.preventDefault(); newCol = col - 1; break;
        case 'ArrowRight': e.preventDefault(); newCol = col + 1; break;
        case 'Enter':
        case ' ':
            e.preventDefault();
            import('./moves.js').then(m => m.onClick(row, col));
            return;
        case 'Escape':
            e.preventDefault();
            document.querySelectorAll('.square.selected').forEach(s => s.classList.remove('selected'));
            return;
        default: return;
    }
    newRow = Math.max(0, Math.min(7, newRow));
    newCol = Math.max(0, Math.min(7, newCol));
    const target = boardEl().querySelector(`[data-row="${newRow}"][data-col="${newCol}"]`);
    if (target) target.focus();
}