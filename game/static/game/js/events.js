import { state } from './state.js';
import { get, post } from './api.js';
import { toggleBoardOrientation, buildBoard } from './board.js';
import { pauseGame, resumeGame, startTimer } from './clocks.js';
import { toggleMute, sounds } from './sound.js';
import { showConfirm, showSideSelectionModal, offerDraw, getConfirmCallback, clearConfirmCallback } from './modals.js';
import { startNewGame, loadGame, endGame, validatePlayerNames, updateModeButtonsUI } from './game.js';
import { queueAIMoveIfNeeded } from './ai.js';
import { updatePauseUI } from './clocks.js';

// ── Name inputs ──────────────────────────────────────────────
const whiteNameInput = document.getElementById('whiteNameInput');
const blackNameInput = document.getElementById('blackNameInput');

if (whiteNameInput) {
    whiteNameInput.addEventListener('input', () => {
        whiteNameInput.classList.remove('input-error');
        if (whiteNameInput.value.trim() && blackNameInput?.value.trim())
            document.getElementById('nameError').style.display = 'none';
    });
}
if (blackNameInput) {
    blackNameInput.addEventListener('input', () => {
        blackNameInput.classList.remove('input-error');
        if (blackNameInput.value.trim() && whiteNameInput?.value.trim())
            document.getElementById('nameError').style.display = 'none';
    });
}

// ── Welcome overlay helpers ──────────────────────────────────
function prepareWelcomeForPvP() {
    const wInput   = document.getElementById('whiteNameInput');
    const bInput   = document.getElementById('blackNameInput');
    const errorDiv = document.getElementById('nameError');
    document.getElementById('pveOptions').style.display    = 'none';
    document.getElementById('modeSelection').style.display = 'flex';
    document.getElementById('nameInputs').style.display    = 'flex';
    if (wInput)   { wInput.style.display = 'block'; wInput.placeholder = 'White Player Name'; wInput.classList.remove('input-error'); }
    if (bInput)   { bInput.style.display = 'block'; bInput.placeholder = 'Black Player Name'; bInput.classList.remove('input-error'); }
    if (errorDiv)   errorDiv.style.display = 'none';
}

// ── PvE color selection ──────────────────────────────────────
let selectedPveColor = 'white';
const colorBtns = document.querySelectorAll('#pveOptions .color-choice');
colorBtns.forEach(btn => {
    btn.onclick = () => {
        colorBtns.forEach(b => { b.classList.remove('active'); b.style.borderColor = '#444'; });
        btn.classList.add('active');
        btn.style.borderColor  = '#f0c040';
        selectedPveColor = btn.dataset.color;
    };
});

// ── Welcome buttons ──────────────────────────────────────────
const welcomePvPBtn  = document.getElementById('welcomePvPBtn');
const welcomeAIBtn   = document.getElementById('welcomeAIBtn');
const welcomeResumeBtn = document.getElementById('welcomeResumeBtn');
const backToModes    = document.getElementById('backToModes');
const startAIBtn     = document.getElementById('startAIBtn');
const welcomeOverlay = document.getElementById('welcomeOverlay');
const gameLayout     = document.querySelector('.game-layout');

if (welcomePvPBtn) welcomePvPBtn.onclick = async () => {
    if (!validatePlayerNames()) return;
    const fen     = document.getElementById('welcomeFenInput')?.value || null;
    const started = await startNewGame('pvp', 'white', 'medium', fen);
    if (!started) return;
    welcomeOverlay.classList.remove('active');
    gameLayout.style.visibility = 'visible';
};

if (welcomeAIBtn) welcomeAIBtn.onclick = () => {
    document.getElementById('modeSelection').style.display = 'none';
    document.getElementById('pveOptions').style.display    = 'flex';
    document.getElementById('nameInputs').style.display    = 'flex';
    const wInput   = document.getElementById('whiteNameInput');
    const bInput   = document.getElementById('blackNameInput');
    const errorDiv = document.getElementById('nameError');
    if (wInput)   { wInput.style.display = 'block'; wInput.placeholder = 'Your Name'; wInput.classList.remove('input-error'); }
    if (bInput)   { bInput.style.display = 'none';  bInput.value = 'AI'; bInput.classList.remove('input-error'); }
    if (errorDiv)   errorDiv.style.display = 'none';
};

if (backToModes) backToModes.onclick = () => {
    prepareWelcomeForPvP();
    const bInput = document.getElementById('blackNameInput');
    if (bInput) bInput.style.display = 'block';
};

if (startAIBtn) startAIBtn.onclick = async () => {
    const wInput   = document.getElementById('whiteNameInput');
    const errorDiv = document.getElementById('nameError');
    const name     = wInput?.value.trim();
    if (!name) {
        if (errorDiv) { errorDiv.style.display = 'block'; errorDiv.textContent = '⚠️ Please enter your name'; }
        if (wInput)     wInput.classList.add('input-error');
        return;
    }
    if (errorDiv) errorDiv.style.display = 'none';
    if (wInput)   wInput.classList.remove('input-error');
    const diff    = document.getElementById('welcomeDifficultySelect').value;
    const fen     = document.getElementById('welcomeFenInput')?.value || null;
    const started = await startNewGame('ai', selectedPveColor, diff, fen);
    if (!started) return;
    welcomeOverlay.classList.remove('active');
    gameLayout.style.visibility = 'visible';
};

if (welcomeResumeBtn) welcomeResumeBtn.onclick = async () => {
    const data = await post('/api/resume/', {});
    if (!data.valid) { welcomeResumeBtn.style.display = 'none'; return; }
    welcomeOverlay.classList.remove('active');
    gameLayout.style.visibility = 'visible';
    state.paused = false;
    updatePauseUI();
    startTimer();
    queueAIMoveIfNeeded();
};

// ── Confirm overlay ──────────────────────────────────────────
const confirmYesBtn = document.getElementById('confirmYesBtn');
const confirmNoBtn  = document.getElementById('confirmNoBtn');
const confirmOverlay = document.getElementById('confirmOverlay');

if (confirmYesBtn) confirmYesBtn.onclick = () => {
    confirmOverlay.classList.remove('active');
    const cb = getConfirmCallback();
    if (cb) cb();
    clearConfirmCallback();
};
if (confirmNoBtn) confirmNoBtn.onclick = () => {
    confirmOverlay.classList.remove('active');
    clearConfirmCallback();
};

// ── In-game controls ─────────────────────────────────────────
const flipBtn    = document.getElementById('flipBtn');
const pauseBtn   = document.getElementById('pauseBtn');
const muteBtn    = document.getElementById('muteBtn');
const resignBtn  = document.getElementById('resignBtn');
const drawBtn    = document.getElementById('drawBtn');
const autoFlipBtn = document.getElementById('autoFlipBtn');
const newPvPBtn  = document.getElementById('newPvPBtn');
const newAIBtn   = document.getElementById('newAIBtn');
const newFenBtn  = document.getElementById('newFenBtn');
const copyFenBtn = document.getElementById('copyFenBtn');
const copyPgnBtn = document.getElementById('copyPgnBtn');

if (flipBtn)   flipBtn.onclick   = toggleBoardOrientation;
if (pauseBtn)  pauseBtn.onclick  = () => state.paused ? resumeGame() : pauseGame();
if (muteBtn)   muteBtn.onclick   = toggleMute;
if (drawBtn)   drawBtn.onclick   = offerDraw;

if (resignBtn) resignBtn.onclick = () => {
    if (!state.gameOver && !state.paused) {
        showConfirm('Resign?', 'Are you sure you want to resign?', async () => {
            try {
                const result = await post('/api/resign/', {});
                if (result.valid) {
                    if (state.soundEnabled) { sounds.draw.currentTime = 0; sounds.draw.play().catch(() => {}); }
                    endGame('resign', state.turn);
                } else {
                    showStatus('Resign failed. Please try again.', true);
                }
            } catch (_) {
                showStatus('Resign failed. Please check your connection and try again.', true);
            }
        });
    }
};

if (autoFlipBtn) autoFlipBtn.onclick = () => {
    state.autoFlip = !state.autoFlip;
    autoFlipBtn.textContent   = 'Auto-Flip: ' + (state.autoFlip ? 'ON' : 'OFF');
    autoFlipBtn.style.background = state.autoFlip ? 'linear-gradient(135deg, #40c0f0, #2080d4)' : '';
    if (state.autoFlip && state.gameMode === 'pvp') { state.flipped = state.turn === 'black'; buildBoard(); }
};

function clearCelebration() {
    const overlay = document.getElementById('gameOverOverlay');
    overlay.classList.remove('game-over-celebration');
    const c = overlay.querySelector('.confetti-container');
    if (c) c.remove();
}

if (newPvPBtn) newPvPBtn.onclick = () => {
    clearCelebration();
    showConfirm('Abandon Game?', 'Your current progress will be lost.<br>Are you sure you want to start a new game?', () => {
        prepareWelcomeForPvP();
        const bInput = document.getElementById('blackNameInput');
        if (bInput && bInput.value === 'AI') bInput.value = '';
        welcomeOverlay.classList.add('active');
    }, '#ff6b6b');
};

if (newAIBtn) newAIBtn.onclick = () => {
    clearCelebration();
    const diffContainer   = document.getElementById('confirmDifficultyContainer');
    const timerContainer  = document.getElementById('confirmTimerContainer');
    if (diffContainer)  diffContainer.style.display  = 'block';
    if (timerContainer) timerContainer.style.display = 'block';
    showConfirm('Abandon Game?', 'Your current progress will be lost.<br>Are you sure you want to start a new game?', () => {
        const diff         = document.getElementById('confirmDifficultySelect').value;
        const timeLimitMins = parseInt(document.getElementById('confirmTimerSelect').value, 10);
        showSideSelectionModal(side => startNewGame('ai', side, diff, null, timeLimitMins));
    }, '#ff6b6b');
};

if (newFenBtn) newFenBtn.onclick = () => {
    showConfirm('Load from FEN?', 'Your current progress will be lost.<br>Do you want to continue?', () => {
        const fenError = document.getElementById('fenError');
        const fenInput = document.getElementById('fenInput');
        if (fenError) fenError.textContent = '';
        if (fenInput) fenInput.value = '';
        document.getElementById('fenOverlay').classList.add('active');
    }, '#ff6b6b');
};

// ── FEN overlay ──────────────────────────────────────────────
const fenStartBtn  = document.getElementById('fenStartBtn');
const fenCancelBtn = document.getElementById('fenCancelBtn');
const fenOverlay   = document.getElementById('fenOverlay');
const fenInput     = document.getElementById('fenInput');
const fenError     = document.getElementById('fenError');

if (fenStartBtn) fenStartBtn.onclick = async () => {
    const val = fenInput?.value?.trim() || '';
    if (!val) { if (fenError) fenError.textContent = 'Please enter a FEN string.'; return; }
    const mode   = state.gameMode === 'ai' ? 'ai' : 'pvp';
    const started = await startNewGame(mode, state.playerColor, state.currentDifficulty, val);
    if (!started) return;
    fenOverlay.classList.remove('active');
    welcomeOverlay.classList.remove('active');
    gameLayout.style.visibility = 'visible';
};
if (fenCancelBtn) fenCancelBtn.onclick = () => fenOverlay.classList.remove('active');

// ── Copy FEN / PGN ───────────────────────────────────────────
if (copyFenBtn) copyFenBtn.onclick = async () => {
    const data = await get('/api/state/');
    if (data.fen) {
        navigator.clipboard.writeText(data.fen);
        copyFenBtn.textContent = 'Copied!';
        clearTimeout(state.fenCopyTimeout);
        state.fenCopyTimeout = setTimeout(() => { copyFenBtn.textContent = 'Copy FEN'; }, 2000);
    }
};

if (copyPgnBtn) copyPgnBtn.onclick = async () => {
    const data = await get('/api/state/');
    if (data.pgn) {
        const blob = new Blob([data.pgn], { type: 'text/plain' });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        const wName = document.getElementById('whiteNameLabel')?.textContent || 'White';
        const bName = document.getElementById('blackNameLabel')?.textContent || 'Black';
        a.download  = `checkora_${wName}_vs_${bName}_${new Date().toISOString().split('T')[0]}.pgn`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        copyPgnBtn.textContent = 'Downloaded!';
        clearTimeout(state.pgnDownloadTimeout);
        state.pgnDownloadTimeout = setTimeout(() => { copyPgnBtn.textContent = 'Export as PGN'; }, 2000);
    }
};

// ── Draw overlay ─────────────────────────────────────────────
const drawAcceptBtn  = document.getElementById('drawAcceptBtn');
const drawDeclineBtn = document.getElementById('drawDeclineBtn');
const drawOverlay    = document.getElementById('drawOverlay');

if (drawAcceptBtn) drawAcceptBtn.onclick = async () => {
    drawOverlay.classList.remove('active');
    const data = await post('/api/draw/', { action: 'accept' });
    if (data.success) {
        if (state.soundEnabled) { sounds.draw.currentTime = 0; sounds.draw.play().catch(() => {}); }
        endGame('draw', state.turn, data.draw_reason);
    }
};
if (drawDeclineBtn) drawDeclineBtn.onclick = () => { drawOverlay.classList.remove('active'); resumeGame(); };

// ── Game Over overlay ────────────────────────────────────────
const gameOverStartBtn = document.getElementById('gameOverStartBtn');
const gameOverOverlay  = document.getElementById('gameOverOverlay');

if (gameOverStartBtn) gameOverStartBtn.onclick = () => {
    const mode         = document.querySelector('input[name="go_mode"]:checked').value;
    const diff         = document.getElementById('goDifficultySelect').value;
    const timeLimitMins = parseInt(document.getElementById('goTimerSelect').value, 10);
    gameOverOverlay.classList.remove('active');
    clearCelebration();
    if (mode === 'ai') showSideSelectionModal(side => startNewGame(mode, side, diff, null, timeLimitMins));
    else startNewGame(mode, 'white', diff, null, timeLimitMins);
};

// ── Manual move input ────────────────────────────────────────
const manualMoveInput = document.getElementById('manualMoveInput');
const manualMoveError = document.getElementById('manualMoveError');

if (manualMoveInput) {
    manualMoveInput.addEventListener('keydown', async e => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        const val   = manualMoveInput.value.trim().toLowerCase();
        if (!val) return;
        const match = val.match(/^([a-h])([1-8])([a-h])([1-8])([qrbn])?$/);
        if (!match) { if (manualMoveError) { manualMoveError.textContent = 'Invalid format (e.g. e2e4)'; manualMoveError.style.display = 'block'; } return; }
        if (manualMoveError) manualMoveError.style.display = 'none';
        const files = ['a','b','c','d','e','f','g','h'];
        const ranks = ['8','7','6','5','4','3','2','1'];
        const fc = files.indexOf(match[1]), fr = ranks.indexOf(match[2]);
        const tc = files.indexOf(match[3]), tr = ranks.indexOf(match[4]);
        const promo = match[5] || null;
        if (state.paused || state.gameOver) { if (manualMoveError) { manualMoveError.textContent = 'Game is not active'; manualMoveError.style.display = 'block'; } return; }
        if (state.gameMode === 'ai' && state.turn !== state.playerColor) { if (manualMoveError) { manualMoveError.textContent = 'Not your turn'; manualMoveError.style.display = 'block'; } return; }
        const { pColor } = await import('./state.js');
        const p = state.board[fr][fc];
        if (!p || pColor(p) !== state.turn) { if (manualMoveError) { manualMoveError.textContent = 'Invalid piece'; manualMoveError.style.display = 'block'; } return; }
        const { isPromotionMove, executeMove } = await import('./moves.js');
        if (isPromotionMove(fr, fc, tr) && !promo) { if (manualMoveError) { manualMoveError.textContent = 'Promotion piece required (e.g. e7e8q)'; manualMoveError.style.display = 'block'; } return; }
        manualMoveInput.value = '';
        await executeMove(fr, fc, tr, tc, promo);
    });
    manualMoveInput.addEventListener('input', () => { if (manualMoveError) manualMoveError.style.display = 'none'; });
}

// ── Keyboard shortcuts ───────────────────────────────────────
document.addEventListener('keydown', e => {
    if (e.repeat) return;
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (document.querySelector('.promo-overlay.active')) return;
    const key = e.key.toLowerCase();
    if      (key === 'f' && flipBtn)                                             { e.preventDefault(); flipBtn.click(); }
    else if (key === 'r' && resignBtn)                                           { e.preventDefault(); resignBtn.click(); }
    else if (key === 'd' && drawBtn && drawBtn.style.display !== 'none')         { e.preventDefault(); drawBtn.click(); }
    else if (key === 'p' && pauseBtn && pauseBtn.style.display !== 'none')       { e.preventDefault(); pauseBtn.click(); }
});

// ── Emotes ───────────────────────────────────────────────────
let emoteCooldown = false;
document.querySelectorAll('.emote-btn').forEach(btn => {
    btn.addEventListener('click', e => {
        if (state.gameMode !== 'pvp') return;
        if (emoteCooldown) { import('./ui.js').then(m => { m.showStatus('Emote cooldown (1s)', true); setTimeout(() => m.showStatus(''), 1000); }); return; }
        emoteCooldown = true;
        setTimeout(() => emoteCooldown = false, 1000);
        const emoteEl   = document.createElement('div');
        emoteEl.className = 'floating-emote ' + (state.turn === 'white' ? 'white-emote' : 'black-emote');
        emoteEl.textContent = e.currentTarget.getAttribute('data-emote');
        const boardOuter = document.querySelector('.board-outer');
        if (boardOuter) { boardOuter.appendChild(emoteEl); setTimeout(() => emoteEl.remove(), 2000); }
    });
});

// ── Visibility / online ──────────────────────────────────────
document.addEventListener('visibilitychange', async () => {
    if (document.hidden) pauseGame().catch(() => {});
    else { const { handleReconnect } = await import('./game.js'); handleReconnect(); }
});

window.addEventListener('online', async () => {
    if (!state.gameOver) { const { handleReconnect } = await import('./game.js'); handleReconnect(); }
});

// ── beforeunload ─────────────────────────────────────────────
if (!navigator.webdriver) {
    window.addEventListener('beforeunload', e => {
        if (!state.paused) navigator.sendBeacon('/api/pause/', JSON.stringify({ pause: true }));
        const welcomeOverlay = document.getElementById('welcomeOverlay');
        if (!state.gameOver && !welcomeOverlay.classList.contains('active')) { e.preventDefault(); e.returnValue = ''; }
    });
}

// ── Asset warning ────────────────────────────────────────────
function showAssetWarning() {
    const t = document.getElementById('confirmTimerContainer');
    const d = document.getElementById('confirmDifficultyContainer');
    if (t) t.style.display = 'none';
    if (d) d.style.display = 'none';
    if (!state.paused) pauseGame().catch(() => {});
    showConfirm(
        '⚠️ Assets Blocked',
        "<div style='line-height:1.5;font-size:0.95rem;'>The chess pieces failed to load.<br><br>Please check your browser permissions or disable any ad-blockers on this site.</div>",
        () => { sessionStorage.setItem('checkoraAutoResume', 'true'); window.location.reload(); },
        '#f0c040'
    );
    const yesBtn = document.getElementById('confirmYesBtn');
    const noBtn  = document.getElementById('confirmNoBtn');
    if (yesBtn) yesBtn.textContent = 'Reload Page';
    if (noBtn)  { noBtn.textContent = 'Close'; const orig = noBtn.onclick; noBtn.onclick = () => { if (orig) orig(); if (state.paused) resumeGame().catch(() => {}); }; }
}

setInterval(() => {
    const img = document.querySelector('.piece');
    if (img && img.naturalWidth === 0 && !window.assetWarningShown) {
        window.assetWarningShown = true;
        showAssetWarning();
    }
}, 5000);
