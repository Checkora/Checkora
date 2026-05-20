import { state, parseBoard } from './state.js';
import { get, post } from './api.js';
import { buildBoard } from './board.js';
import { renderClocks, startTimer, updatePauseUI } from './clocks.js';
import { updateTurn, updateMoves, updateCaptured, showStatus, updatePlayerNames } from './ui.js';
import { createConfetti, createSparkles } from './animations.js';
import { queueAIMoveIfNeeded, resetAIState } from './ai.js';
import { sounds } from './sound.js';

export function updateModeButtonsUI(mode) {
    const pvpBtn = document.getElementById('newPvPBtn');
    const aiBtn  = document.getElementById('newAIBtn');
    if (!pvpBtn || !aiBtn) return;
    pvpBtn.classList.toggle('active-mode', mode === 'pvp');
    aiBtn.classList.toggle('active-mode',  mode === 'ai');
}

export function validatePlayerNames() {
    const wInput   = document.getElementById('whiteNameInput');
    const bInput   = document.getElementById('blackNameInput');
    const errorDiv = document.getElementById('nameError');
    const wName    = wInput?.value.trim();
    const bName    = bInput?.value.trim();
    if (!wName || !bName) {
        if (errorDiv) { errorDiv.style.display = 'block'; errorDiv.textContent = '⚠️ Please enter both player names'; }
        if (!wName && wInput) wInput.classList.add('input-error');
        if (!bName && bInput) bInput.classList.add('input-error');
        return false;
    }
    if (errorDiv) errorDiv.style.display = 'none';
    if (wInput)   wInput.classList.remove('input-error');
    if (bInput)   bInput.classList.remove('input-error');
    return true;
}

export async function loadGame() {
    // Reset stale AI request state on every load/reconnect
    resetAIState();

    const data = await get('/api/state/');
    state.board       = parseBoard(data.board);
    state.turn        = data.current_turn;
    state.whiteTime   = data.white_time;
    state.blackTime   = data.black_time;
    state.paused      = data.paused;
    state.gameMode    = data.mode || 'pvp';
    state.playerColor = data.player_color || 'white';
    state.currentDifficulty = data.difficulty || state.currentDifficulty;

    updateModeButtonsUI(state.gameMode);

    const flipControls = document.getElementById('flipControls');
    if (flipControls) flipControls.style.display = state.gameMode === 'pvp' ? 'flex' : 'none';

    state.flipped = state.gameMode === 'ai' ? (state.playerColor === 'black') : false;

    const modeBadge = document.getElementById('modeBadge');
    if (modeBadge) modeBadge.textContent = state.gameMode === 'ai' ? 'VS AI' : 'PVP';

    const emotePanel = document.getElementById('emotePanel');
    if (emotePanel) emotePanel.style.display = state.gameMode === 'pvp' ? 'block' : 'none';

    const hasMoves     = data.move_history?.length > 0;
    const isResumable  = hasMoves && data.game_status === 'active';
    const resumeBtn    = document.getElementById('welcomeResumeBtn');
    if (resumeBtn) {
        resumeBtn.style.display = isResumable ? 'block' : 'none';
        if (isResumable) resumeBtn.textContent = data.mode === 'ai' ? 'Replay Previous Game' : 'Resume Game';
    }

    const drawBtn = document.getElementById('drawBtn');
    if (drawBtn) drawBtn.style.display = state.gameMode === 'pvp' ? 'block' : 'none';

    // Always show these on load unless game is already over
    const resignBtn2 = document.getElementById('resignBtn');
    const pauseBtn2  = document.getElementById('pauseBtn');
    if (resignBtn2) resignBtn2.style.display = 'block';
    if (pauseBtn2)  pauseBtn2.style.display  = 'block';

    updatePlayerNames(data);
    updateTurn();
    updateMoves(data.move_history);
    updateCaptured(data.captured_pieces);
    buildBoard();
    renderClocks();
    updatePauseUI();
    startTimer();

    if (state.gameMode === 'ai') {
        const aiClockId  = state.playerColor === 'white' ? 'blackClock' : 'whiteClock';
        const aiTimeId   = state.playerColor === 'white' ? 'blackTime'  : 'whiteTime';
        const aiClock    = document.getElementById(aiClockId);
        const aiTimeEl   = document.getElementById(aiTimeId);
        if (aiClock)  { aiClock.style.border = '2px dashed #444'; aiClock.style.boxShadow = 'none'; aiClock.classList.remove('active'); }
        if (aiTimeEl) { aiTimeEl.textContent = '🤖'; aiTimeEl.style.fontSize = '1.8em'; aiTimeEl.style.color = '#888'; }
    }

    if (data.game_status && data.game_status !== 'active' && data.game_status !== 'ok') {
        handleGameStatus(data.game_status, data.draw_reason);
    }

    const welcomeOverlay = document.getElementById('welcomeOverlay');
    if (!welcomeOverlay || !welcomeOverlay.classList.contains('active')) queueAIMoveIfNeeded();
}

export async function startNewGame(mode, pColor = 'white', difficulty = 'medium', fen = null, timeLimitMins = null) {
    // Reset stale AI state on new game
    resetAIState();
    clearTimeout(state.fenCopyTimeout);

    const copyPgnBtn = document.getElementById('copyPgnBtn');
    const copyFenBtn = document.getElementById('copyFenBtn');
    if (copyPgnBtn) copyPgnBtn.textContent = 'Export as PGN';
    if (copyFenBtn) copyFenBtn.textContent = 'Copy FEN';

    // Clear celebration
    const overlay          = document.getElementById('gameOverOverlay');
    const confettiContainer = overlay.querySelector('.confetti-container');
    overlay.classList.remove('game-over-celebration');
    if (confettiContainer) confettiContainer.remove();

    const wName          = (document.getElementById('whiteNameInput')?.value || 'White').trim().slice(0, 17);
    const bName          = (document.getElementById('blackNameInput')?.value || 'Black').trim().slice(0, 17);
    const defaultMins    = parseInt(document.getElementById('timeLimitInput')?.value || 10, 10);
    const timeLimit      = (timeLimitMins !== null ? timeLimitMins : defaultMins) * 60;

    const payload = { mode, player_color: pColor, white_name: wName, black_name: bName, difficulty, time_limit: timeLimit };
    if (fen?.trim()) payload.fen = fen.trim();

    const fenError        = document.getElementById('fenError');
    const welcomeFenError = document.getElementById('welcomeFenError');
    if (fenError)        fenError.textContent = '';
    if (welcomeFenError) welcomeFenError.textContent = '';

    const d = await post('/api/new-game/', payload);
    if (d.valid === false || !d.board) {
        const msg = d.message || 'Unable to start a new game.';
        if (fenError)        fenError.textContent = msg;
        if (welcomeFenError && document.getElementById('welcomeOverlay')?.classList.contains('active')) welcomeFenError.textContent = msg;
        showStatus(msg, true);
        return false;
    }

    state.board             = d.board;
    state.turn              = d.current_turn;
    state.paused            = false;
    state.gameOver          = false;
    state.gameMode          = d.mode;
    state.playerColor       = d.player_color || 'white';
    state.currentDifficulty = d.difficulty || difficulty;
    state.flipped           = state.gameMode === 'ai' ? state.playerColor === 'black' : false;

    const resignBtn  = document.getElementById('resignBtn');
    const pauseBtn   = document.getElementById('pauseBtn');
    const drawBtn    = document.getElementById('drawBtn');
    const modeBadge  = document.getElementById('modeBadge');
    const emotePanel = document.getElementById('emotePanel');
    const movesEl    = document.getElementById('movesList');
    const wCapEl     = document.getElementById('whiteCaptured');
    const bCapEl     = document.getElementById('blackCaptured');

    if (resignBtn)  resignBtn.style.display  = '';
    if (pauseBtn)   pauseBtn.style.display   = '';
    if (drawBtn)    drawBtn.style.display    = state.gameMode === 'pvp' ? 'block' : 'none';
    if (modeBadge)  modeBadge.textContent    = state.gameMode === 'ai' ? 'VS AI' : 'PVP';
    if (emotePanel) emotePanel.style.display = state.gameMode === 'pvp' ? 'block' : 'none';
    if (movesEl)    movesEl.innerHTML        = '<span class="placeholder">No moves yet</span>';
    if (wCapEl)     wCapEl.innerHTML         = '';
    if (bCapEl)     bCapEl.innerHTML         = '';

    await loadGame();
    updateModeButtonsUI(state.gameMode);
    state.paused = false;
    updatePauseUI();

    if (state.gameMode === 'ai' && state.turn !== state.playerColor) queueAIMoveIfNeeded();
    return true;
}

export function handleGameStatus(status, drawReason) {
    if (status === 'checkmate') { endGame('checkmate', state.turn); return true; }
    if (status === 'stalemate') { endGame('stalemate', state.turn); return true; }
    if (status === 'draw')      { endGame('draw',      state.turn, drawReason); return true; }
    return false;
}

export function endGame(reason, color, drawReason = null) {
    if (state.gameOver) return;
    state.gameOver = true;
    state.paused   = true;
    clearInterval(state.timerInterval);

    const whiteNameLabel = document.getElementById('whiteNameLabel');
    const blackNameLabel = document.getElementById('blackNameLabel');

    let title = '', message = '', isCelebration = false;
    if (reason === 'checkmate') {
        const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
        title = '🏆 CHECKMATE! 🏆'; message = `${winnerName} WINS!`; isCelebration = true;
    } else if (reason === 'stalemate') {
        title = 'Stalemate!'; message = 'The game is a draw.';
    } else if (reason === 'draw') {
        title = 'Draw!';
        const drawMessages = { agreement: 'Draw by agreement.', threefold_repetition: 'Draw by threefold repetition.', fifty_move_rule: 'Draw by the fifty-move rule.', insufficient_material: 'Draw by insufficient material.' };
        message = drawMessages[drawReason] || 'The game is a draw.';
    } else if (reason === 'resign') {
        const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
        const loserName  = color === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;
        title = '🏆 VICTORY! 🏆'; message = `${loserName} resigned. ${winnerName} WINS!`; isCelebration = true;
    } else if (reason === 'timeout') {
        const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
        const loserName  = color === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;
        title = 'Timeout!'; message = `${loserName} ran out of time. ${winnerName} wins!`;
    }

    const resignBtn      = document.getElementById('resignBtn');
    const drawBtn        = document.getElementById('drawBtn');
    const pauseBtn       = document.getElementById('pauseBtn');
    const gameOverOverlay = document.getElementById('gameOverOverlay');
    const gameOverTitle  = document.getElementById('gameOverTitle');
    const gameOverMessage = document.getElementById('gameOverMessage');

    if (resignBtn)  resignBtn.style.display  = 'none';
    if (drawBtn)    drawBtn.style.display    = 'none';
    if (pauseBtn)   pauseBtn.style.display   = 'none';
    gameOverTitle.textContent   = title;
    gameOverMessage.textContent = message;

    setTimeout(() => {
        if (isCelebration) {
            gameOverOverlay.classList.add('game-over-celebration');
            createConfetti();
            createSparkles();
        } else {
            gameOverOverlay.classList.remove('game-over-celebration');
        }
        gameOverOverlay.style.transition = 'opacity 0.5s ease-in-out';
        gameOverOverlay.style.opacity    = '0';
        gameOverOverlay.classList.add('active');
        setTimeout(() => { gameOverOverlay.style.opacity = '1'; }, 700);
    }, 500);

    showStatus(title + ': ' + message, false);
    const winnerColor = color === 'white' ? 'Black' : 'White';
    const cleanMsg    = reason === 'checkmate' || reason === 'resign'
        ? `Game over. ${winnerColor} wins by ${reason}.`
        : `Game over. Draw by ${reason || 'stalemate'}.`;
    import('./ui.js').then(m => m.announceMove(cleanMsg));
    document.title = 'Game Over - Checkora';
}

export async function handleReconnect() {
    if (state.reconnecting) return;
    state.reconnecting = true;
    showStatus('Reconnecting...', false);
    let retries = 0, success = false;
    while (retries < 3 && !success) {
        try {
            await new Promise(r => setTimeout(r, 1000 * Math.pow(2, retries)));
            await loadGame();
            success = true;
        } catch { retries++; }
    }
    if (success) { showStatus('Connection restored', false); setTimeout(() => showStatus('', false), 2000); }
    else           showStatus('Unable to reconnect. Please refresh.', true);
    state.reconnecting = false;
}
