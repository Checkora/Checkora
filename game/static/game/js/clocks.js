import { state } from './state.js';
import { post } from './api.js';
import { queueAIMoveIfNeeded } from './ai.js';

export const fmt = t => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
export const formatTime = fmt;

export function renderClocks() {
    const wTime    = document.getElementById('whiteTime');
    const bTime    = document.getElementById('blackTime');
    const wClock   = document.getElementById('whiteClock');
    const bClock   = document.getElementById('blackClock');

    if (state.gameMode === 'ai') {
        const playerClock  = state.playerColor === 'white' ? wClock  : bClock;
        const playerTimeEl = state.playerColor === 'white' ? wTime   : bTime;
        const aiClock      = state.playerColor === 'white' ? bClock  : wClock;
        const aiTimeEl     = state.playerColor === 'white' ? bTime   : wTime;

        if (playerTimeEl) playerTimeEl.textContent = fmt(state.playerColor === 'white' ? state.whiteTime : state.blackTime);
        if (playerClock)  playerClock.classList.toggle('active', state.turn === state.playerColor);
        if (aiTimeEl)     { aiTimeEl.textContent = '🤖'; aiTimeEl.style.fontSize = '1.8em'; aiTimeEl.style.color = '#888'; }
        if (aiClock)      aiClock.classList.remove('active');
    } else {
        if (wTime)  wTime.textContent = fmt(state.whiteTime);
        if (bTime)  bTime.textContent = fmt(state.blackTime);
        if (wClock) wClock.classList.toggle('active', state.turn === 'white');
        if (bClock) bClock.classList.toggle('active', state.turn === 'black');
    }

    const wYou = document.getElementById('whiteYouTag');
    const bYou = document.getElementById('blackYouTag');
    if (wYou) wYou.style.display = (state.gameMode === 'ai' && state.playerColor === 'white') ? 'inline' : 'none';
    if (bYou) bYou.style.display = (state.gameMode === 'ai' && state.playerColor === 'black') ? 'inline' : 'none';
}

export function startTimer() {
    clearInterval(state.timerInterval);
    state.timerInterval = setInterval(() => {
        if (state.paused || state.gameOver) return;
        if (state.turn === 'white' && state.whiteTime > 0) state.whiteTime--;
        if (state.turn === 'black' && state.blackTime > 0) state.blackTime--;
        renderClocks();

        if (state.turn === 'white' && state.whiteTime === 0) {
            import('./game.js').then(m => m.endGame('timeout', 'white'));
        } else if (state.turn === 'black' && state.blackTime === 0) {
            import('./game.js').then(m => m.endGame('timeout', 'black'));
        }
    }, 1000);
}

export function updatePauseUI() {
    const pauseBtn = document.getElementById('pauseBtn');
    const boardEl  = document.getElementById('board');
    if (pauseBtn) { pauseBtn.textContent = state.paused ? 'Resume' : 'Pause'; pauseBtn.classList.toggle('paused', state.paused); }
    if (boardEl)  boardEl.classList.toggle('paused', state.paused);
}

export async function pauseGame() {
    if (state.paused) return;
    const d = await post('/api/pause/', { pause: true });
    state.paused    = d.paused;
    state.whiteTime = d.white_time;
    state.blackTime = d.black_time;
    updatePauseUI();
    renderClocks();
}

export async function resumeGame() {
    if (!state.paused) return;
    const d = await post('/api/pause/', { pause: false });
    state.paused    = d.paused;
    state.whiteTime = d.white_time;
    state.blackTime = d.black_time;
    updatePauseUI();
    renderClocks();
    startTimer();
    queueAIMoveIfNeeded();
}

if (typeof module !== "undefined") module.exports = { formatTime };