import { state, parseBoard } from './state.js';
import { post } from './api.js';
import { animateMove } from './animations.js';
import { syncPieces, applyCheckHighlight, highlightCheck, updateMaterialUI } from './board.js';
import { renderClocks, startTimer } from './clocks.js';
import { updateTurn, updateMoves, updateCaptured, showStatus, updatePlayerNames, announceMove } from './ui.js';
import { playSound } from './sound.js';
import { handleGameStatus } from './game.js';

export function isAITurn() {
    return state.gameMode === 'ai' && state.turn !== state.playerColor && !state.gameOver;
}

export function queueAIMoveIfNeeded() {
    if (!isAITurn() || state.aiThinking) return;
    setTimeout(() => {
        if (isAITurn() && !state.aiThinking) requestAIMove();
    }, 200);
}

export async function requestAIMove() {
    if (state.gameOver || state.aiThinking) return;
    state.aiThinking = true;
    showStatus('AI is thinking...', false);
    try {
        const data = await post('/api/ai-move/', {});
        if (data.valid) {
            playSound(data);
            const mv = data.ai_move;
            await animateMove(mv.from_row, mv.from_col, mv.to_row, mv.to_col);
            state.board     = parseBoard(data.board);
            state.turn      = data.current_turn;
            state.lastMove  = { from: [mv.from_row, mv.from_col], to: [mv.to_row, mv.to_col] };
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
                a11y = `AI played ${data.move_history[data.move_history.length - 1].notation}. `;
            }
            const ended = handleGameStatus(data.game_status, data.draw_reason);
            if (!ended) {
                if (data.game_status === 'check') {
                    applyCheckHighlight();
                    showStatus('You are in check!', true);
                    a11y += 'You are in check!';
                } else {
                    highlightCheck();
                    showStatus('Your turn.', false);
                }
                if (a11y) announceMove(a11y);
            }
        } else {
            showStatus(data.message, true);
        }
    } catch (e) {
        import('./game.js').then(m => m.handleReconnect());
    } finally {
        state.aiThinking = false;
    }
}