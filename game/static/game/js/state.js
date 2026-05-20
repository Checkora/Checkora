// ============================================================
// SHARED STATE — import and mutate directly
// ============================================================
export const state = {
    board: [],
    turn: 'white',
    selected: null,
    hints: [],
    lastMove: null,

    dragging: false,
    dragSrc: null,

    whiteTime: 0,
    blackTime: 0,
    paused: false,
    timerInterval: null,
    pendingPromo: null,

    gameMode: 'pvp',
    currentDifficulty: 'medium',
    playerColor: 'white',
    flipped: false,
    autoFlip: false,

    gameOver: false,
    aiThinking: false,
    reconnecting: false,

    soundEnabled: true,

    pgnDownloadTimeout: null,
    fenCopyTimeout: null,
};

// ============================================================
// CONSTANTS
// ============================================================
export const MATERIAL_VALUES = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };

export const PIECE_IMG = {};
for (const c of ['w', 'b'])
    for (const t of ['k', 'q', 'r', 'b', 'n', 'p'])
        PIECE_IMG[c + t] = `https://images.chesscomfiles.com/chess-themes/pieces/neo/150/${c}${t}.png`;

// ============================================================
// PURE HELPERS (no DOM, no state mutation)
// ============================================================
export const pKey   = p => p ? ((p === p.toUpperCase() ? 'w' : 'b') + p.toLowerCase()) : null;
export const pColor = p => p ? (p === p.toUpperCase() ? 'white' : 'black') : null;

export function parseBoard(s) {
    if (!s || typeof s !== 'string') return s;
    if (s.length !== 64) return null;
    const b = [];
    for (let i = 0; i < 8; i++) {
        const row = [];
        for (let j = 0; j < 8; j++) {
            const ch = s[i * 8 + j];
            row.push(ch === '.' ? null : ch);
        }
        b.push(row);
    }
    return b;
}
import { getSquareLabel } from './board.js';
if (typeof module !== "undefined") module.exports = { pColor, getSquareLabel }; 