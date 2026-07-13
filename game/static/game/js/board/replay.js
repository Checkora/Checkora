/**
 * board/replay.js — Replay controls, stepping through move history, and game navigation
 *
 * Extracted from board.js: resetReplayBoard, renderReplayPosition,
 * goToReplayMove, rebuildGameFens, renderStepperPosition, updateStepperUI,
 * and replay button initialization.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  const DEFAULT_START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

  function resetReplayBoard() {
    if (typeof window !== 'undefined' && window.Chess) {
      CB.S.replayBoard = new window.Chess();
    }
  }

  function renderReplayPosition() {
    if (!CB.S.replayBoard) return;

    const fen = CB.S.replayBoard.fen();
    const position = fen.split(' ')[0];
    const rows = position.split('/');

    CB.S.board = rows.map(row => {
      const expanded = [];
      for (const ch of row) {
        if (!isNaN(ch)) {
          for (let i = 0; i < Number(ch); i++) {
            expanded.push(null);
          }
        } else {
          expanded.push(ch);
        }
      }
      return expanded;
    });

    if (CB.buildBoard) CB.buildBoard();
    if (CB.syncPieces) CB.syncPieces();
    if (CB.updateMaterialUI) CB.updateMaterialUI(CB.S.board);
  }

  function goToReplayMove(index) {
    if (typeof window === 'undefined' || !window.Chess) {
      console.error("Chess.js not loaded");
      return;
    }

    CB.S.replayBoard = new window.Chess();

    try {
      for (let i = 0; i < index; i++) {
        const move = CB.S.replayMoves[i];
        if (move) {
          CB.S.replayBoard.move(move);
        }
      }
      CB.S.replayIndex = index;
      renderReplayPosition();
    } catch (e) {
      console.error("Replay move error:", e);
    }
  }

  function rebuildGameFens(moveHistory, startingFen) {
    if (typeof window === 'undefined' || !window.Chess) return [startingFen || DEFAULT_START_FEN];
    const tempChess = new window.Chess(startingFen || DEFAULT_START_FEN);
    const fens = [tempChess.fen()];
    if (moveHistory && moveHistory.length > 0) {
      for (let m of moveHistory) {
        const res = tempChess.move(m.notation);
        if (!res) {
          fens.push(fens[fens.length - 1]);
          continue;
        }
        fens.push(tempChess.fen());
      }
    }
    return fens;
  }

  function renderStepperPosition(fen) {
    if (!fen || typeof fen !== 'string') return;
    if (fen.startsWith('startpos')) {
      fen = DEFAULT_START_FEN;
    }
    const position = fen.split(' ')[0];
    const rows = position.split('/');
    if (rows.length !== 8) {
      return;
    }
    CB.S.board = rows.map(row => {
      const expanded = [];
      for (const ch of row) {
        if (!isNaN(ch)) {
          for (let i = 0; i < Number(ch); i++) expanded.push(null);
        } else {
          expanded.push(ch);
        }
      }
      return expanded;
    });
    if (CB.buildBoard) CB.buildBoard();
    if (CB.syncPieces) CB.syncPieces();
    if (CB.updateMaterialUI) CB.updateMaterialUI(CB.S.board);
  }

  function updateStepperUI() {
    if (!CB.S.gameFens) return;
    const fen = CB.S.gameFens[CB.S.stepperIndex];
    if (fen) renderStepperPosition(fen);

    CB.S.viewingPastState = (CB.S.stepperIndex < CB.S.gameFens.length - 1);

    if (typeof document !== 'undefined') {
      const resumeBtn = document.getElementById('resumeGameBtn');
      if (resumeBtn) resumeBtn.classList.toggle('hidden', !CB.S.viewingPastState);

      const firstBtn = document.getElementById('stepperFirst');
      const prevBtn = document.getElementById('stepperPrev');
      const nextBtn = document.getElementById('stepperNext');
      const lastBtn = document.getElementById('stepperLast');

      if (firstBtn) firstBtn.disabled = (CB.S.stepperIndex === 0);
      if (prevBtn) prevBtn.disabled = (CB.S.stepperIndex === 0);
      if (nextBtn) nextBtn.disabled = (CB.S.stepperIndex === CB.S.gameFens.length - 1);
      if (lastBtn) lastBtn.disabled = (CB.S.stepperIndex === CB.S.gameFens.length - 1);

      document.querySelectorAll('.moves-list .selected-move').forEach(el => el.classList.remove('selected-move'));
      if (CB.S.stepperIndex > 0) {
        const activeMoveEl = document.querySelector(`.moves-list span[data-move-index="${CB.S.stepperIndex - 1}"]`);
        if (activeMoveEl) {
          activeMoveEl.classList.add('selected-move');
          activeMoveEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    }
  }

  function initReplayControls() {
    if (typeof document === 'undefined') return;

    if (CB.DOM.nextReplayBtn) {
      CB.DOM.nextReplayBtn.onclick = () => {
        if (CB.S.replayIndex < CB.S.replayMoves.length) {
          CB.S.replayIndex++;
          goToReplayMove(CB.S.replayIndex);
        }
      };
    }

    if (CB.DOM.prevReplayBtn) {
      CB.DOM.prevReplayBtn.onclick = () => {
        if (CB.S.replayIndex > 0) {
          CB.S.replayIndex--;
          goToReplayMove(CB.S.replayIndex);
        }
      };
    }

    if (CB.DOM.firstReplayBtn) {
      CB.DOM.firstReplayBtn.onclick = () => {
        CB.S.replayIndex = 0;
        goToReplayMove(0);
      };
    }

    if (CB.DOM.lastReplayBtn) {
      CB.DOM.lastReplayBtn.onclick = () => {
        CB.S.replayIndex = CB.S.replayMoves.length;
        goToReplayMove(CB.S.replayIndex);
      };
    }

    if (CB.DOM.replayGameBtn) {
      CB.DOM.replayGameBtn.onclick = () => {
        const gameOverOverlay = document.getElementById('gameOverOverlay');
        if (gameOverOverlay) gameOverOverlay.classList.remove('active');

        if (CB.DOM.replayControls) CB.DOM.replayControls.classList.remove('hidden');

        if (CB.S.autoReplayInterval && typeof clearInterval !== 'undefined') {
          clearInterval(CB.S.autoReplayInterval);
          CB.S.autoReplayInterval = null;
        }
        CB.S.replayIndex = 0;
        goToReplayMove(0);

        if (CB.DOM.playReplayBtn) CB.DOM.playReplayBtn.textContent = '⏸';

        const playNextMove = () => {
          if (CB.S.replayIndex >= CB.S.replayMoves.length) {
            CB.S.autoReplayInterval = null;
            if (CB.DOM.playReplayBtn) CB.DOM.playReplayBtn.textContent = '▶';
            return;
          }

          CB.S.replayIndex++;
          goToReplayMove(CB.S.replayIndex);
          if (typeof setTimeout !== 'undefined') {
            CB.S.autoReplayInterval = setTimeout(playNextMove, 1000);
          }
        };

        if (typeof setTimeout !== 'undefined') {
          CB.S.autoReplayInterval = setTimeout(playNextMove, 1000);
        }
      };
    }

    if (CB.DOM.playReplayBtn) {
      CB.DOM.playReplayBtn.onclick = () => {
        if (CB.S.autoReplayInterval && typeof clearTimeout !== 'undefined') {
          CB.S.isAutoReplaying = false;
          clearTimeout(CB.S.autoReplayInterval);
          CB.S.autoReplayInterval = null;
          CB.DOM.playReplayBtn.textContent = '▶';
          return;
        }
        CB.DOM.playReplayBtn.textContent = '⏸';
        CB.S.isAutoReplaying = true;

        const playNextMove = () => {
          if (!CB.S.isAutoReplaying) return;

          if (CB.S.replayIndex >= CB.S.replayMoves.length) {
            CB.S.autoReplayInterval = null;
            CB.S.isAutoReplaying = false;
            if (CB.DOM.playReplayBtn) CB.DOM.playReplayBtn.textContent = '▶';
            return;
          }

          CB.S.replayIndex++;
          goToReplayMove(CB.S.replayIndex);

          if (CB.S.isAutoReplaying && typeof setTimeout !== 'undefined') {
            CB.S.autoReplayInterval = setTimeout(playNextMove, 1000);
          }
        };

        if (CB.S.isAutoReplaying && typeof setTimeout !== 'undefined') {
          CB.S.autoReplayInterval = setTimeout(playNextMove, 1000);
        }
      };
    }

    const stepperFirst = document.getElementById('stepperFirst');
    const stepperPrev = document.getElementById('stepperPrev');
    const stepperNext = document.getElementById('stepperNext');
    const stepperLast = document.getElementById('stepperLast');
    const resumeGameBtn = document.getElementById('resumeGameBtn');

    if (stepperFirst) {
      stepperFirst.onclick = () => {
        CB.S.stepperIndex = 0;
        updateStepperUI();
      };
    }
    if (stepperPrev) {
      stepperPrev.onclick = () => {
        if (CB.S.stepperIndex > 0) {
          CB.S.stepperIndex--;
          updateStepperUI();
        }
      };
    }
    if (stepperNext) {
      stepperNext.onclick = () => {
        if (CB.S.gameFens && CB.S.stepperIndex < CB.S.gameFens.length - 1) {
          CB.S.stepperIndex++;
          updateStepperUI();
        }
      };
    }
    if (stepperLast) {
      stepperLast.onclick = () => {
        if (CB.S.gameFens) {
          CB.S.stepperIndex = CB.S.gameFens.length - 1;
          updateStepperUI();
        }
      };
    }
    if (resumeGameBtn) {
      resumeGameBtn.onclick = () => {
        if (CB.S.gameFens) {
          CB.S.stepperIndex = CB.S.gameFens.length - 1;
          CB.S.viewingPastState = false;
          updateStepperUI();
        }
      };
    }
  }

  CB.resetReplayBoard = resetReplayBoard;
  CB.renderReplayPosition = renderReplayPosition;
  CB.goToReplayMove = goToReplayMove;
  CB.rebuildGameFens = rebuildGameFens;
  CB.renderStepperPosition = renderStepperPosition;
  CB.updateStepperUI = updateStepperUI;
  CB.initReplayControls = initReplayControls;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      resetReplayBoard: resetReplayBoard,
      renderReplayPosition: renderReplayPosition,
      goToReplayMove: goToReplayMove,
      rebuildGameFens: rebuildGameFens,
      renderStepperPosition: renderStepperPosition,
      updateStepperUI: updateStepperUI,
      initReplayControls: initReplayControls
    };
  }
})();
