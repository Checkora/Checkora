import { state, pColor, parseBoard } from './state.js';
import { get, post } from './api.js';
import { animateMove } from './animations.js';
import { refreshHighlights, syncPieces, buildBoard, applyCheckHighlight, highlightCheck, updateMaterialUI } from './board.js';
import { renderClocks, startTimer } from './clocks.js';
import { updateTurn, updateMoves, updateCaptured, showStatus, updatePlayerNames, announceMove } from './ui.js';
import { showPromoModal, hidePromoModal } from './modals.js';
import { playSound } from './sound.js';
import { handleGameStatus } from './game.js';

export async function selectPiece(r, c) {
    const p = state.board[r][c];
    if (!p || pColor(p) !== state.turn || state.paused || state.gameOver) return;
    if (state.gameMode === 'ai' && state.turn !== state.playerColor) {
        showStatus('Waiting for AI to move...', false);
        return;
    }
    state.selected = { r, c };
    try {
        const data = await get(`/api/valid-moves/?row=${r}&col=${c}`);
        state.hints = data.valid_moves || [];
        refreshHighlights();
    } catch {
        state.selected = null;
        state.hints = [];
        refreshHighlights();
        showStatus('Unable to load valid moves. Please try again.', true);
    }
}

export function deselect() {
    state.selected = null;
    state.hints    = [];
    refreshHighlights();
}

export function isPromotionMove(fr, fc, tr) {
    const p = state.board[fr][fc];
    if (!p) return false;
    return (p === 'P' && tr === 0) || (p === 'p' && tr === 7);
}

export async function tryMove(fr, fc, tr, tc) {
    if (state.paused || state.gameOver) return;
    const p = state.board[fr][fc];
    if (!p || pColor(p) !== state.turn) return;
    if (isPromotionMove(fr, fc, tr)) {
        await animateMove(fr, fc, tr, tc);
        state.pendingPromo = { fr, fc, tr, tc };
        showPromoModal(pColor(p));
        return;
    }
    await executeMove(fr, fc, tr, tc, null);
}

export async function onPromoChoice(choice) {
    if (!state.pendingPromo) return;
    const { fr, fc, tr, tc } = state.pendingPromo;
    hidePromoModal();
    await executeMove(fr, fc, tr, tc, choice, true);
}

export async function executeMove(fr, fc, tr, tc, promotionPiece, skipAnimation = false) {
    try {
        const body = { from_row: fr, from_col: fc, to_row: tr, to_col: tc };
        if (promotionPiece) body.promotion_piece = promotionPiece;

        const data = await post('/api/move/', body);
        if (data.valid) {
            playSound(data);
            if (!skipAnimation) await animateMove(fr, fc, tr, tc);
            state.board     = parseBoard(data.board);
            state.turn      = data.current_turn;
            state.lastMove  = { from: [fr, fc], to: [tr, tc] };

            if (state.gameMode === 'pvp' && state.autoFlip) {
                state.flipped = state.turn === 'black';
                buildBoard();
            }
            state.whiteTime = data.white_time;
            state.blackTime = data.black_time;
            state.selected  = null;
            state.hints     = [];

            updatePlayerNames(data);
            updateTurn();
            updateMoves(data.move_history);
            updateCaptured(data.captured_pieces);
            syncPieces();
            renderClocks();
            startTimer();
            updateMaterialUI();

            let a11y = '';
            if (data.move_history?.length) {
                const last = data.move_history[data.move_history.length - 1].notation;
                a11y = `${state.turn === 'white' ? 'Black' : 'White'} played ${last}. `;
            }
            const ended = handleGameStatus(data.game_status, data.draw_reason);
            if (!ended) {
                if (data.game_status === 'check') {
                    applyCheckHighlight();
                    const msg = state.turn === 'white' ? 'White is in check!' : 'Black is in check!';
                    showStatus(msg, true);
                    a11y += msg;
                } else {
                    highlightCheck();
                    showStatus('', false);
                }
                if (a11y) announceMove(a11y);
            }
            if (state.gameMode === 'ai' && state.turn !== state.playerColor && !state.gameOver) {
                import('./ai.js').then(m => m.requestAIMove());
            }
        } else {
            showStatus(data.message, true);
            deselect();
        }
    } catch (e) {
        import('./game.js').then(m => m.handleReconnect());
    }
}

export async function onClick(r, c) {
    if (state.dragging) return;
    if (state.selected) {
        if (state.selected.r === r && state.selected.c === c) return deselect();
        if (state.hints.some(h => h.row === r && h.col === c)) return tryMove(state.selected.r, state.selected.c, r, c);
        if (state.board[r][c] && pColor(state.board[r][c]) === state.turn) return selectPiece(r, c);
        return deselect();
    }
    selectPiece(r, c);
}

export async function onDrop(e, tr, tc) {
    if (!state.dragSrc) return;
    await tryMove(state.dragSrc.r, state.dragSrc.c, tr, tc);
    state.dragSrc = null;
}