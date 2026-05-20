import { state, PIECE_IMG } from './state.js';
import { post } from './api.js';
import { pauseGame, resumeGame } from './clocks.js';

export function showPromoModal(color) {
    const prefix      = color === 'white' ? 'w' : 'b';
    const promoChoices = document.getElementById('promoChoices');
    const promoOverlay = document.getElementById('promoOverlay');
    promoChoices.innerHTML = '';
    [{ key: 'q' }, { key: 'r' }, { key: 'b' }, { key: 'n' }].forEach(({ key }) => {
        const btn = document.createElement('button');
        btn.className = 'promo-btn';
        const img = document.createElement('img');
        img.src = PIECE_IMG[prefix + key];
        btn.appendChild(img);
        btn.onclick = () => import('./moves.js').then(m => m.onPromoChoice(key));
        promoChoices.appendChild(btn);
    });
    promoOverlay.classList.add('active');
}

export function hidePromoModal() {
    document.getElementById('promoOverlay').classList.remove('active');
    state.pendingPromo = null;
}

let confirmCallback = null;

export function showConfirm(title, msg, callback, titleColor = '#ff6b6b') {
    const confirmOverlay  = document.getElementById('confirmOverlay');
    const confirmTitle    = document.getElementById('confirmTitle');
    const confirmMessage  = document.getElementById('confirmMessage');
    if (confirmTitle)   { confirmTitle.textContent = title; confirmTitle.style.color = titleColor; }
    if (confirmMessage)   confirmMessage.innerHTML  = msg;
    confirmCallback = callback;
    confirmOverlay.classList.add('active');
}

export function getConfirmCallback() { return confirmCallback; }
export function clearConfirmCallback() { confirmCallback = null; }

export function showSideSelectionModal(onChoose) {
    const modal = document.getElementById('sideModal');
    modal.style.display = 'flex';
    function pick(side) {
        modal.style.display = 'none';
        ['chooseWhite','chooseBlack','chooseRandom'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.onclick = null;
        });
        onChoose(side);
    }
    document.getElementById('chooseWhite').onclick  = () => pick('white');
    document.getElementById('chooseBlack').onclick  = () => pick('black');
    document.getElementById('chooseRandom').onclick = () => pick(Math.random() < 0.5 ? 'white' : 'black');
}

export async function offerDraw() {
    if (state.paused || state.gameOver || state.gameMode !== 'pvp') return;
    const offeringPlayer  = state.turn === 'white' ? 'White' : 'Black';
    const receivingPlayer = state.turn === 'white' ? 'Black' : 'White';
    showConfirm(
        'Offer Draw?',
        `As <b>${offeringPlayer}</b>, do you want to offer a draw to ${receivingPlayer}?`,
        async () => {
            const drawMessage = document.getElementById('drawMessage');
            const drawOverlay = document.getElementById('drawOverlay');
            if (drawMessage) drawMessage.textContent = `${offeringPlayer} offers a draw. ${receivingPlayer}, do you accept?`;
            if (drawOverlay) drawOverlay.classList.add('active');
            await pauseGame();
        },
        '#f0c040'
    );
}