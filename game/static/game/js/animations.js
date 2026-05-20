import { state, pColor } from './state.js';
import { sq } from './board.js';

export async function animateMove(fr, fc, tr, tc) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const animations = [];
    const size = getSquareSize();
    const mult = state.flipped ? -1 : 1;

    function createAnim(p, dRow, dCol) {
        return new Promise(resolve => {
            p.style.transition = 'transform 0.25s ease-in-out, opacity 0.2s ease';
            p.style.transform = `translate(${dCol * size * mult}px, ${dRow * size * mult}px)`;
            p.classList.add('moving');
            const onEnd = () => {
                p.removeEventListener('transitionend', onEnd);
                p.classList.remove('moving');
                p.style.transform = 'none';
                p.style.transition = '';
                resolve();
            };
            p.addEventListener('transitionend', onEnd);
            setTimeout(onEnd, 300);
        });
    }

    const piece = sq(fr, fc).querySelector('.piece');
    if (piece) {
        animations.push(createAnim(piece, tr - fr, tc - fc));

        const pType = state.board[fr][fc];
        if (pType && pType.toLowerCase() === 'k' && Math.abs(tc - fc) === 2) {
            const isShort = tc > fc;
            const rookFc = isShort ? 7 : 0;
            const rookTc = isShort ? 5 : 3;
            const rook = sq(fr, rookFc).querySelector('.piece');
            if (rook) animations.push(createAnim(rook, 0, rookTc - rookFc));
        }
    }

    let capturedSq = sq(tr, tc);
    const isEnPassant = piece && piece.src.includes('p.png') && fc !== tc && !state.board[tr][tc];
    if (isEnPassant) capturedSq = sq(fr, tc);

    const targetPiece = capturedSq.querySelector('.piece');
    if (targetPiece) targetPiece.classList.add('captured');

    await Promise.all(animations);
}

function getSquareSize() {
    const boardEl = document.getElementById('board');
    const s = boardEl.querySelector('.square');
    return s ? s.getBoundingClientRect().width : 60;
}

export function createConfetti() {
    const overlay  = document.getElementById('gameOverOverlay');
    const dialog   = overlay.querySelector('.promo-dialog');
    let container  = dialog.querySelector('.confetti-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'confetti-container';
        dialog.style.position = 'relative';
        dialog.appendChild(container);
    }
    container.innerHTML = '';

    const colors = ['#ffd700','#f0c040','#ff6b6b','#4ecdc4','#45b7d1','#96ceb4','#ff9ff3'];
    for (let i = 0; i < 50; i++) {
        const el = document.createElement('div');
        el.className = 'confetti';
        el.style.left              = Math.random() * 100 + '%';
        el.style.background        = colors[Math.floor(Math.random() * colors.length)];
        el.style.animationDelay    = Math.random() * 0.5 + 's';
        el.style.animationDuration = (2 + Math.random() * 2) + 's';
        el.style.transform         = `rotate(${Math.random() * 360}deg)`;
        if (Math.random() > 0.5) el.style.borderRadius = '50%';
        container.appendChild(el);
    }
}

export function createSparkles() {
    const overlay  = document.getElementById('gameOverOverlay');
    const dialog   = overlay.querySelector('.promo-dialog');
    let container  = dialog.querySelector('.confetti-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'confetti-container';
        dialog.style.position = 'relative';
        dialog.appendChild(container);
    }
    for (let i = 0; i < 20; i++) {
        const el = document.createElement('div');
        el.className = 'sparkle';
        el.style.left           = Math.random() * 100 + '%';
        el.style.top            = Math.random() * 100 + '%';
        el.style.animationDelay = Math.random() * 1.5 + 's';
        container.appendChild(el);
    }
}