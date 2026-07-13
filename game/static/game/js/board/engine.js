/**
 * board/engine.js — Stockfish worker and position evaluation
 *
 * Extracted from board.js lines 368–477: initStockfish, getStockfishEval,
 * validateMoveWithStockfish, clearEvaluationCache, precalculateExpectedMoveEval
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  function initStockfish() {
    if (!CB.S.stockfishWorker && typeof Worker !== 'undefined') {
      CB.S.stockfishWorker = new Worker('/static/game/js/stockfish.js');
      CB.S.stockfishWorker.postMessage('setoption name Hash value 16');
      CB.S.stockfishWorker.postMessage('setoption name Contempt value 0');
    }
  }

  function getStockfishEval(fen) {
    if (CB.S.evaluationCache[fen]) {
      return Promise.resolve(CB.S.evaluationCache[fen]);
    }
    return new Promise((resolve) => {
      initStockfish();
      if (!CB.S.stockfishWorker) {
        resolve({ type: 'cp', value: 0 });
        return;
      }

      let scoreType = 'cp';
      let scoreValue = 0;

      const onMessage = (e) => {
        const line = e.data;
        const match = line.match(/score (cp|mate) (-?\d+)/);
        if (match) {
          scoreType = match[1];
          scoreValue = parseInt(match[2], 10);
        }

        if (line.startsWith('bestmove')) {
          CB.S.stockfishWorker.removeEventListener('message', onMessage);
          const result = { type: scoreType, value: scoreValue };
          CB.S.evaluationCache[fen] = result;
          resolve(result);
        }
      };

      CB.S.stockfishWorker.addEventListener('message', onMessage);
      CB.S.stockfishWorker.postMessage('ucinewgame');
      CB.S.stockfishWorker.postMessage(`position fen ${fen}`);
      CB.S.stockfishWorker.postMessage('go depth 6 movetime 100');
    });
  }

  async function precalculateExpectedMoveEval() {
    if (!CB.S.currentPuzzle) return;
    const expectedMove = CB.S.currentPuzzle.solution[CB.S.puzzleMoveIndex];
    if (!expectedMove) return;
    try {
      if (typeof window === 'undefined' || !window.Chess) return;
      const chess = new window.Chess(CB.S.currentPuzzleFen);
      const from = expectedMove.substring(0, 2);
      const to = expectedMove.substring(2, 4);
      const promo = expectedMove.length > 4 ? expectedMove.charAt(4) : undefined;
      chess.move({ from, to, promotion: promo });
      const expectedFen = chess.fen();
      CB.S.expectedMoveEval = await getStockfishEval(expectedFen);
    } catch (e) {
      console.error("Error precalculating expected move eval:", e);
    }
  }

  async function validateMoveWithStockfish(previousFen, playedFen, expectedMove) {
    try {
      let expectedEval = CB.S.expectedMoveEval;
      if (!expectedEval) {
        if (typeof window === 'undefined' || !window.Chess) {
          console.error("Chess.js not loaded");
          return false;
        }
        const chess = new window.Chess(previousFen);
        const from = expectedMove.substring(0, 2);
        const to = expectedMove.substring(2, 4);
        const promo = expectedMove.length > 4 ? expectedMove.charAt(4) : undefined;
        chess.move({ from, to, promotion: promo });
        const expectedFen = chess.fen();
        expectedEval = await getStockfishEval(expectedFen);
      }

      const playedEval = await getStockfishEval(playedFen);

      const valExpected = CB.getPlayerScore(expectedEval);
      const valPlayed = CB.getPlayerScore(playedEval);

      const isCorrect = (valPlayed >= 9000) ||
        (valPlayed >= valExpected - 50) ||
        (valPlayed >= 300 && valExpected >= 300);

      return isCorrect;
    } catch (e) {
      console.error("Stockfish validation error:", e);
      return false;
    }
  }

  function clearEvaluationCache() {
    CB.S.evaluationCache = {};
  }

  CB.initStockfish = initStockfish;
  CB.getStockfishEval = getStockfishEval;
  CB.precalculateExpectedMoveEval = precalculateExpectedMoveEval;
  CB.validateMoveWithStockfish = validateMoveWithStockfish;
  CB.clearEvaluationCache = clearEvaluationCache;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      initStockfish: initStockfish,
      getStockfishEval: getStockfishEval,
      precalculateExpectedMoveEval: precalculateExpectedMoveEval,
      validateMoveWithStockfish: validateMoveWithStockfish,
      clearEvaluationCache: clearEvaluationCache
    };
  }
})();
