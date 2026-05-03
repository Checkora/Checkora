import { gameApi } from './api.js';
import { PIECE_IMAGES, PROMOTION_CHOICES, pieceColor, pieceKey } from './pieces.js';

const BOARD_SIZE = 8;
const DEFAULT_TIME = 10 * 60;
const DEFAULT_NAMES = { white: 'White', black: 'Black' };

const byId = id => document.getElementById(id);
const secondsOr = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback;

const dom = {
    board: byId('board'),
    turnBadge: byId('turnBadge'),
    turnBadgeText: byId('turnBadgeText'),
    status: byId('statusBar'),
    moves: byId('movesList'),
    modeBadge: byId('modeBadge'),
    inputs: {
        white: byId('whiteNameInput'),
        black: byId('blackNameInput'),
    },
    clocks: {
        white: byId('whiteClock'),
        black: byId('blackClock'),
    },
    clockNames: {
        white: byId('whiteNameLabel'),
        black: byId('blackNameLabel'),
    },
    clockTimes: {
        white: document.querySelector('#whiteClock .time'),
        black: document.querySelector('#blackClock .time'),
    },
    capturedNames: {
        white: byId('whiteCapturedName'),
        black: byId('blackCapturedName'),
    },
    captured: {
        white: byId('whiteCaptured'),
        black: byId('blackCaptured'),
    },
    buttons: {
        pause: byId('pauseBtn'),
        resign: byId('resignBtn'),
        welcomePvP: byId('welcomePvPBtn'),
        welcomeAI: byId('welcomeAIBtn'),
        welcomeResume: byId('welcomeResumeBtn'),
        confirmYes: byId('confirmYesBtn'),
        confirmNo: byId('confirmNoBtn'),
        newPvP: byId('newPvPBtn'),
        newAI: byId('newAIBtn'),
        draw: byId('drawBtn'),
        drawAccept: byId('drawAcceptBtn'),
        drawDecline: byId('drawDeclineBtn'),
        gameOverPvP: byId('gameOverPvPBtn'),
        gameOverAI: byId('gameOverAIBtn'),
        resignConfirm: byId('resignConfirmBtn'),
        resignCancel: byId('resignCancelBtn'),
    },
    overlays: {
        welcome: byId('welcomeOverlay'),
        confirm: byId('confirmOverlay'),
        draw: byId('drawOverlay'),
        promo: byId('promoOverlay'),
        gameOver: byId('gameOverOverlay'),
        resign: byId('resignModal'),
    },
    confirmTitle: byId('confirmTitle'),
    confirmMessage: byId('confirmMessage'),
    drawMessage: byId('drawMessage'),
    promoChoices: byId('promoChoices'),
    gameOverTitle: byId('gameOverTitle'),
    gameOverMessage: byId('gameOverMessage'),
};

const state = {
    board: [],
    turn: 'white',
    selected: null,
    hints: [],
    lastMove: null,
    dragging: false,
    dragSource: null,
    whiteTime: DEFAULT_TIME,
    blackTime: DEFAULT_TIME,
    paused: false,
    timerId: null,
    pendingPromotion: null,
    gameMode: 'pvp',
    gameOver: false,
};

let confirmCallback = null;

function readPlayerNames() {
    return {
        white: dom.inputs.white.value.trim() || DEFAULT_NAMES.white,
        black: dom.inputs.black.value.trim() || DEFAULT_NAMES.black,
    };
}

function setPlayerNames(names) {
    const white = names.white || DEFAULT_NAMES.white;
    const black = names.black || DEFAULT_NAMES.black;

    dom.inputs.white.value = white;
    dom.inputs.black.value = black;
    dom.clockNames.white.textContent = white.toUpperCase();
    dom.clockNames.black.textContent = black.toUpperCase();
    dom.capturedNames.white.textContent = white;
    dom.capturedNames.black.textContent = black;
}

function playerName(color) {
    return readPlayerNames()[color] || DEFAULT_NAMES[color];
}

function otherColor(color) {
    return color === 'white' ? 'black' : 'white';
}

function setOverlay(overlay, active) {
    overlay.classList.toggle('is-active', Boolean(active));
}

function showStatus(message, isError = false) {
    dom.status.textContent = message;
    dom.status.classList.toggle('error', isError);
}

function squareAt(row, col) {
    return dom.board.children[row * BOARD_SIZE + col];
}

function resetInteraction() {
    state.selected = null;
    state.hints = [];
    state.dragSource = null;
    state.pendingPromotion = null;
}

function formatTime(totalSeconds) {
    const safeSeconds = Math.max(0, totalSeconds);
    return `${Math.floor(safeSeconds / 60)}:${String(safeSeconds % 60).padStart(2, '0')}`;
}

function renderMode() {
    dom.modeBadge.textContent = state.gameMode === 'ai' ? 'VS AI' : 'PVP';
}

function renderTurn() {
    const name = playerName(state.turn);
    dom.turnBadgeText.textContent = name;
    dom.turnBadge.className = `turn-badge ${state.turn}`;
    dom.clocks.white.classList.toggle('active', state.turn === 'white');
    dom.clocks.black.classList.toggle('active', state.turn === 'black');
    markPlayable();

    if (!state.gameOver) {
        document.title = `${name} to Move - Checkora`;
    }
}

function renderControls() {
    dom.buttons.draw.hidden = state.gameMode !== 'pvp' || state.gameOver;
    dom.buttons.pause.hidden = state.gameOver;
    dom.buttons.resign.hidden = state.gameOver;
}

function renderClocks() {
    dom.clockTimes.white.textContent = formatTime(state.whiteTime);
    dom.clockTimes.black.textContent = formatTime(state.blackTime);

    for (const color of ['white', 'black']) {
        const time = color === 'white' ? state.whiteTime : state.blackTime;
        dom.clocks[color].classList.toggle('low', time > 0 && time <= 30);
        dom.clocks[color].classList.toggle('dead', time <= 0);
    }
}

function updatePauseButton() {
    dom.buttons.pause.textContent = state.paused ? 'Resume' : 'Pause';
}

function renderHistory(history = []) {
    dom.moves.innerHTML = '';

    if (!history.length) {
        const placeholder = document.createElement('span');
        placeholder.className = 'placeholder';
        placeholder.textContent = 'No moves yet';
        dom.moves.appendChild(placeholder);
        return;
    }

    for (let index = 0; index < history.length; index += 2) {
        const row = document.createElement('div');
        row.className = 'move-row';

        const moveNumber = document.createElement('span');
        moveNumber.className = 'move-num';
        moveNumber.textContent = `${index / 2 + 1}.`;

        const whiteMove = document.createElement('span');
        whiteMove.className = 'move-white';
        whiteMove.textContent = history[index]?.notation || '';

        row.append(moveNumber, whiteMove);

        if (history[index + 1]) {
            const blackMove = document.createElement('span');
            blackMove.className = 'move-black';
            blackMove.textContent = history[index + 1].notation;
            row.appendChild(blackMove);
        }

        dom.moves.appendChild(row);
    }
}

function renderCaptured(captured = { white: [], black: [] }) {
    for (const color of ['white', 'black']) {
        dom.captured[color].innerHTML = '';
        for (const piece of captured[color] || []) {
            const img = document.createElement('img');
            img.src = PIECE_IMAGES[pieceKey(piece)];
            img.className = 'captured-img';
            img.alt = '';
            dom.captured[color].appendChild(img);
        }
    }
}

function buildBoard() {
    dom.board.innerHTML = '';

    for (let row = 0; row < BOARD_SIZE; row += 1) {
        for (let col = 0; col < BOARD_SIZE; col += 1) {
            const square = document.createElement('div');
            square.className = `square ${(row + col) % 2 ? 'dark' : 'light'}`;
            square.dataset.row = row;
            square.dataset.col = col;
            square.addEventListener('click', () => onSquareClick(row, col));
            square.addEventListener('dragover', event => event.preventDefault());
            square.addEventListener('drop', event => onDrop(event, row, col));
            dom.board.appendChild(square);
        }
    }

    syncPieces();
}

function syncPieces() {
    for (let row = 0; row < BOARD_SIZE; row += 1) {
        for (let col = 0; col < BOARD_SIZE; col += 1) {
            const square = squareAt(row, col);
            square.innerHTML = '';

            const piece = state.board[row]?.[col];
            if (!piece) continue;

            const img = document.createElement('img');
            img.src = PIECE_IMAGES[pieceKey(piece)];
            img.className = 'piece';
            img.draggable = true;
            img.alt = '';
            img.addEventListener('dragstart', event => onDragStart(event, row, col));
            img.addEventListener('dragend', () => {
                state.dragging = false;
                state.dragSource = null;
            });
            square.appendChild(img);
        }
    }

    refreshHighlights();
    markPlayable();
}

function markPlayable() {
    dom.board.querySelectorAll('.piece').forEach(img => {
        const square = img.closest('.square');
        const row = Number(square.dataset.row);
        const col = Number(square.dataset.col);
        const piece = state.board[row]?.[col];
        const isPlayable = piece
            && pieceColor(piece) === state.turn
            && !state.paused
            && !state.gameOver
            && !(state.gameMode === 'ai' && state.turn === 'black');

        img.classList.toggle('playable', Boolean(isPlayable));
    });
}

function refreshHighlights() {
    dom.board.querySelectorAll('.square').forEach(square => {
        square.classList.remove('selected', 'last-move');
        square.querySelectorAll('.move-dot, .capture-ring').forEach(node => node.remove());
    });

    if (state.lastMove) {
        squareAt(state.lastMove.from[0], state.lastMove.from[1]).classList.add('last-move');
        squareAt(state.lastMove.to[0], state.lastMove.to[1]).classList.add('last-move');
    }

    if (!state.selected) return;

    squareAt(state.selected.row, state.selected.col).classList.add('selected');
    for (const hint of state.hints) {
        const marker = document.createElement('div');
        marker.className = hint.is_capture ? 'capture-ring' : 'move-dot';
        squareAt(hint.row, hint.col).appendChild(marker);
    }
}

async function selectPiece(row, col) {
    const piece = state.board[row]?.[col];
    if (!piece || pieceColor(piece) !== state.turn || state.paused || state.gameOver) return;

    if (state.gameMode === 'ai' && state.turn === 'black') {
        showStatus('Waiting for AI to move...');
        return;
    }

    state.selected = { row, col };
    try {
        const data = await gameApi.validMoves(row, col);
        state.hints = data.valid_moves || [];
        refreshHighlights();
    } catch (error) {
        showStatus('Could not load legal moves.', true);
    }
}

function deselect() {
    resetInteraction();
    refreshHighlights();
}

function isPromotionMove(fromRow, fromCol, toRow) {
    const piece = state.board[fromRow]?.[fromCol];
    return (piece === 'P' && toRow === 0) || (piece === 'p' && toRow === 7);
}

function showPromotionModal(color) {
    const prefix = color === 'white' ? 'w' : 'b';
    dom.promoChoices.innerHTML = '';

    for (const choice of PROMOTION_CHOICES) {
        const button = document.createElement('button');
        button.className = 'promo-btn';
        button.type = 'button';
        button.setAttribute('aria-label', `Promote to ${choice.label}`);

        const img = document.createElement('img');
        img.src = PIECE_IMAGES[`${prefix}${choice.key}`];
        img.alt = '';
        button.appendChild(img);
        button.addEventListener('click', () => choosePromotion(choice.key));
        dom.promoChoices.appendChild(button);
    }

    setOverlay(dom.overlays.promo, true);
}

function hidePromotionModal() {
    setOverlay(dom.overlays.promo, false);
    state.pendingPromotion = null;
}

async function choosePromotion(choice) {
    if (!state.pendingPromotion) return;

    const { fromRow, fromCol, toRow, toCol } = state.pendingPromotion;
    hidePromotionModal();
    await executeMove(fromRow, fromCol, toRow, toCol, choice);
}

async function tryMove(fromRow, fromCol, toRow, toCol) {
    if (state.paused || state.gameOver) return;

    const piece = state.board[fromRow]?.[fromCol];
    if (!piece || pieceColor(piece) !== state.turn) return;

    if (isPromotionMove(fromRow, fromCol, toRow)) {
        state.pendingPromotion = { fromRow, fromCol, toRow, toCol };
        showPromotionModal(pieceColor(piece));
        return;
    }

    await executeMove(fromRow, fromCol, toRow, toCol);
}

async function executeMove(fromRow, fromCol, toRow, toCol, promotionPiece = null) {
    try {
        const payload = {
            from_row: fromRow,
            from_col: fromCol,
            to_row: toRow,
            to_col: toCol,
        };

        if (promotionPiece) {
            payload.promotion_piece = promotionPiece;
        }

        const data = await gameApi.move(payload);
        if (!data.valid) {
            showStatus(data.message || 'Illegal move.', true);
            deselect();
            return;
        }

        applyMoveResponse(data, {
            from: [fromRow, fromCol],
            to: [toRow, toCol],
        });

        const ended = handleServerStatus(data.game_status, 'player');
        if (!ended && state.gameMode === 'ai' && state.turn === 'black') {
            await requestAIMove();
        }
    } catch (error) {
        showStatus('Connection error.', true);
    }
}

async function requestAIMove() {
    showStatus('AI is thinking...');

    try {
        const data = await gameApi.aiMove();
        if (!data.valid) {
            showStatus(data.message || 'AI move failed.', true);
            return;
        }

        const move = data.ai_move;
        applyMoveResponse(data, {
            from: [move.from_row, move.from_col],
            to: [move.to_row, move.to_col],
        });

        handleServerStatus(data.game_status, 'ai');
    } catch (error) {
        showStatus('AI connection error.', true);
    }
}

function applyMoveResponse(data, lastMove) {
    state.board = data.board;
    state.turn = data.current_turn;
    state.lastMove = lastMove;
    state.whiteTime = secondsOr(data.white_time, state.whiteTime);
    state.blackTime = secondsOr(data.black_time, state.blackTime);
    resetInteraction();

    syncPieces();
    renderTurn();
    renderHistory(data.move_history || []);
    renderCaptured(data.captured_pieces || { white: [], black: [] });
    renderClocks();
    renderControls();
    startTimer();
}

function handleServerStatus(status, source) {
    if (status === 'checkmate' || status === 'stalemate') {
        handleGameOver(status, state.turn);
        return true;
    }

    if (status === 'check') {
        const message = source === 'ai' ? 'You are in check!' : `${playerName(state.turn)} is in check!`;
        showStatus(message, true);
        return false;
    }

    showStatus(source === 'ai' ? 'Your turn.' : '');
    return false;
}

function onSquareClick(row, col) {
    if (state.dragging) return;

    if (state.selected) {
        const isHint = state.hints.some(hint => hint.row === row && hint.col === col);
        if (isHint) {
            void tryMove(state.selected.row, state.selected.col, row, col);
            return;
        }

        if (state.board[row]?.[col] && pieceColor(state.board[row][col]) === state.turn) {
            void selectPiece(row, col);
            return;
        }

        deselect();
        return;
    }

    void selectPiece(row, col);
}

function onDragStart(event, row, col) {
    if (
        state.paused
        || state.gameOver
        || pieceColor(state.board[row]?.[col]) !== state.turn
        || (state.gameMode === 'ai' && state.turn === 'black')
    ) {
        event.preventDefault();
        return;
    }

    state.dragging = true;
    state.dragSource = { row, col };
    void selectPiece(row, col);
}

async function onDrop(event, toRow, toCol) {
    event.preventDefault();
    if (!state.dragSource) return;

    await tryMove(state.dragSource.row, state.dragSource.col, toRow, toCol);
    state.dragSource = null;
}

function handleGameOver(status, currentTurn) {
    state.gameOver = true;
    state.paused = true;
    clearInterval(state.timerId);

    let title = 'Game Over';
    let message = '';

    if (status === 'checkmate') {
        const winner = playerName(otherColor(currentTurn));
        title = 'Checkmate!';
        message = `${winner} wins!`;
    } else if (status === 'stalemate') {
        title = 'Stalemate!';
        message = 'The game is a draw.';
    } else if (status === 'draw') {
        title = 'Draw!';
        message = 'Draw by agreement.';
    } else if (status === 'resign') {
        const winner = playerName(otherColor(currentTurn));
        title = 'Resignation';
        message = `${winner} wins!`;
    }

    dom.gameOverTitle.textContent = title;
    dom.gameOverMessage.textContent = message;
    setOverlay(dom.overlays.gameOver, true);
    showStatus(`${title} ${message}`);
    updatePauseButton();
    renderControls();
    markPlayable();
    document.title = 'Game Over - Checkora';
}

function startTimer() {
    clearInterval(state.timerId);
    state.timerId = setInterval(() => {
        if (state.paused || state.gameOver) return;
        if (state.turn === 'white' && state.whiteTime > 0) state.whiteTime -= 1;
        if (state.turn === 'black' && state.blackTime > 0) state.blackTime -= 1;
        renderClocks();
    }, 1000);
}

async function pauseGame() {
    if (state.paused || state.gameOver) return;

    const data = await gameApi.pause({
        pause: true,
        white_time: state.whiteTime,
        black_time: state.blackTime,
    });

    state.paused = data.paused;
    state.whiteTime = secondsOr(data.white_time, state.whiteTime);
    state.blackTime = secondsOr(data.black_time, state.blackTime);
    updatePauseButton();
    renderClocks();
    markPlayable();
}

async function resumeGame() {
    if (!state.paused || state.gameOver) return;

    const data = await gameApi.pause({ pause: false });
    state.paused = data.paused;
    state.whiteTime = secondsOr(data.white_time, state.whiteTime);
    state.blackTime = secondsOr(data.black_time, state.blackTime);
    updatePauseButton();
    renderClocks();
    markPlayable();
    startTimer();
}

function showConfirm(title, message, callback, tone = 'danger') {
    dom.confirmTitle.textContent = title;
    dom.confirmMessage.textContent = message;
    dom.confirmTitle.classList.toggle('is-danger', tone === 'danger');
    dom.confirmTitle.classList.toggle('is-gold', tone === 'gold');
    confirmCallback = callback;
    setOverlay(dom.overlays.confirm, true);
}

function requestNewGame(mode) {
    showConfirm(
        'Abandon Game?',
        'Your current progress will be lost. Are you sure you want to start a new game?',
        () => startNewGame(mode),
    );
}

async function startNewGame(mode) {
    const names = readPlayerNames();

    try {
        const data = await gameApi.newGame({
            mode,
            white_name: names.white,
            black_name: names.black,
        });

        state.board = data.board;
        state.turn = data.current_turn;
        state.whiteTime = secondsOr(data.white_time, DEFAULT_TIME);
        state.blackTime = secondsOr(data.black_time, DEFAULT_TIME);
        state.paused = Boolean(data.paused ?? false);
        state.gameMode = data.mode || mode;
        state.gameOver = false;
        state.lastMove = null;
        resetInteraction();

        setPlayerNames({
            white: data.white_name || names.white,
            black: data.black_name || names.black,
        });
        setOverlay(dom.overlays.welcome, false);
        setOverlay(dom.overlays.gameOver, false);
        setOverlay(dom.overlays.confirm, false);

        renderMode();
        buildBoard();
        renderTurn();
        renderHistory(data.move_history || []);
        renderCaptured(data.captured_pieces || { white: [], black: [] });
        renderClocks();
        updatePauseButton();
        renderControls();
        showStatus('');
        startTimer();
    } catch (error) {
        showStatus('Could not start a new game.', true);
    }
}

async function offerDraw() {
    if (state.paused || state.gameOver || state.gameMode !== 'pvp') return;

    const offeringPlayer = playerName(state.turn);
    const receivingPlayer = playerName(otherColor(state.turn));

    showConfirm(
        'Offer Draw?',
        `As ${offeringPlayer}, do you want to offer a draw to ${receivingPlayer}?`,
        async () => {
            dom.drawMessage.textContent = `${offeringPlayer} offers a draw. ${receivingPlayer}, do you accept?`;
            setOverlay(dom.overlays.draw, true);
            await pauseGame();
        },
        'gold',
    );
}

async function acceptDraw() {
    setOverlay(dom.overlays.draw, false);
    const data = await gameApi.draw({ action: 'accept' });
    if (data.success) {
        handleGameOver('draw', state.turn);
    }
}

async function confirmResign() {
    setOverlay(dom.overlays.resign, false);

    try {
        const data = await gameApi.resign();
        if (!data.valid) {
            showStatus(data.message || 'Resign failed.', true);
            return;
        }

        const loser = state.turn;
        handleGameOver('resign', loser);
        showStatus(`${playerName(loser)} resigned. ${playerName(otherColor(loser))} wins!`);
    } catch (error) {
        showStatus('Resign failed.', true);
    }
}

function applyLoadedState(data) {
    state.board = data.board || [];
    state.turn = data.current_turn || 'white';
    state.whiteTime = secondsOr(data.white_time, DEFAULT_TIME);
    state.blackTime = secondsOr(data.black_time, DEFAULT_TIME);
    state.paused = Boolean(data.paused);
    state.gameMode = data.mode || 'pvp';
    state.gameOver = false;
    resetInteraction();

    setPlayerNames({
        white: data.white_name || DEFAULT_NAMES.white,
        black: data.black_name || DEFAULT_NAMES.black,
    });

    renderMode();
    buildBoard();
    renderTurn();
    renderHistory(data.move_history || []);
    renderCaptured(data.captured_pieces || { white: [], black: [] });
    renderClocks();
    updatePauseButton();
    renderControls();
    startTimer();

    dom.buttons.welcomeResume.hidden = !(data.move_history && data.move_history.length > 0);
}

async function loadGame() {
    try {
        const data = await gameApi.state();
        applyLoadedState(data);
    } catch (error) {
        showStatus('Could not load the game.', true);
    }
}

function bindEvents() {
    dom.buttons.pause.addEventListener('click', () => {
        void (state.paused ? resumeGame() : pauseGame());
    });
    dom.buttons.resign.addEventListener('click', () => setOverlay(dom.overlays.resign, true));

    dom.buttons.welcomePvP.addEventListener('click', () => void startNewGame('pvp'));
    dom.buttons.welcomeAI.addEventListener('click', () => void startNewGame('ai'));
    dom.buttons.welcomeResume.addEventListener('click', () => {
        setOverlay(dom.overlays.welcome, false);
        if (state.paused) void resumeGame();
    });

    dom.buttons.confirmYes.addEventListener('click', () => {
        const callback = confirmCallback;
        confirmCallback = null;
        setOverlay(dom.overlays.confirm, false);
        if (callback) Promise.resolve(callback()).catch(() => showStatus('Action failed.', true));
    });
    dom.buttons.confirmNo.addEventListener('click', () => {
        confirmCallback = null;
        setOverlay(dom.overlays.confirm, false);
    });

    dom.buttons.newPvP.addEventListener('click', () => requestNewGame('pvp'));
    dom.buttons.newAI.addEventListener('click', () => requestNewGame('ai'));

    dom.buttons.draw.addEventListener('click', () => void offerDraw());
    dom.buttons.drawAccept.addEventListener('click', () => void acceptDraw());
    dom.buttons.drawDecline.addEventListener('click', () => {
        setOverlay(dom.overlays.draw, false);
        void resumeGame();
    });

    dom.buttons.gameOverPvP.addEventListener('click', () => void startNewGame('pvp'));
    dom.buttons.gameOverAI.addEventListener('click', () => void startNewGame('ai'));
    dom.buttons.resignConfirm.addEventListener('click', () => void confirmResign());
    dom.buttons.resignCancel.addEventListener('click', () => setOverlay(dom.overlays.resign, false));

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) void pauseGame();
    });

    window.addEventListener('beforeunload', () => {
        if (!state.paused && !state.gameOver) {
            navigator.sendBeacon('/api/pause/', JSON.stringify({
                pause: true,
                white_time: state.whiteTime,
                black_time: state.blackTime,
            }));
        }
    });
}

bindEvents();
void loadGame();
