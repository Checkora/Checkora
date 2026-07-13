/**
 * board/utils.js — Pure helpers and UI utility functions
 *
 * Extracted from board.js: pColor, pKey, sq, getSquareLabel, squareLabelToRowCol,
 * showStatus, flashBoard, announceMove, calculateMaterial, updateMaterialUI,
 * formatGameDuration, getPlayerScore, validatePlayerNames, computeLegalMovesClient,
 * getSquareSize, isAITurn.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  const pKey = p => p ? ((p === p.toUpperCase() ? 'w' : 'b') + p.toLowerCase()) : null;
  const pColor = p => p ? (p === p.toUpperCase() ? 'white' : 'black') : null;

  const sq = (r, c) => {
    const vr = CB.S.flipped ? 7 - r : r;
    const vc = CB.S.flipped ? 7 - c : c;
    return CB.DOM.boardEl ? CB.DOM.boardEl.children[vr * 8 + vc] : null;
  };

  function getSquareLabel(row, col) {
    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];
    return files[col] + ranks[row];
  }

  function squareLabelToRowCol(square) {
    const file = square.charCodeAt(0) - 97;
    const rank = parseInt(square[1], 10);
    const row = 8 - rank;
    return { row, col: file };
  }

  function computeLegalMovesClient(r, c) {
    if (typeof window === 'undefined' || !window.Chess) return null;
    try {
      const chess = new window.Chess(CB.S.liveFen);
      const fromSquare = getSquareLabel(r, c);
      const moves = chess.moves({ square: fromSquare, verbose: true });
      if (!moves) return null;

      const seen = new Set();
      return moves
        .filter(m => {
          if (seen.has(m.to)) return false;
          seen.add(m.to);
          return true;
        })
        .map(m => {
          const { row, col } = squareLabelToRowCol(m.to);
          return {
            row,
            col,
            is_capture: m.captured !== undefined,
            is_promotion: m.promotion !== undefined,
          };
        });
    } catch (e) {
      console.warn('computeLegalMovesClient error:', e);
      return null;
    }
  }

  function calculateMaterial(board) {
    let white = 0;
    let black = 0;
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const piece = board[r][c];
        if (!piece) continue;
        const value = CB.MATERIAL_VALUES[piece.toLowerCase()] || 0;
        if (piece === piece.toUpperCase()) {
          white += value;
        } else {
          black += value;
        }
      }
    }
    return { white, black };
  }

  function updateMaterialUI(board) {
    const { white, black } = calculateMaterial(board);
    const wScore = typeof document !== 'undefined' ? document.getElementById("whiteScore") : null;
    const bScore = typeof document !== 'undefined' ? document.getElementById("blackScore") : null;
    if (wScore) wScore.innerText = white;
    if (bScore) bScore.innerText = black;

    if (typeof document !== 'undefined') {
      const whiteAdv = document.getElementById("whiteAdvantage");
      const blackAdv = document.getElementById("blackAdvantage");
      if (whiteAdv && blackAdv) {
        if (white > black) {
          whiteAdv.innerText = `+${white - black}`;
          whiteAdv.style.display = "inline-block";
          blackAdv.style.display = "none";
        } else if (black > white) {
          blackAdv.innerText = `+${black - white}`;
          blackAdv.style.display = "inline-block";
          whiteAdv.style.display = "none";
        } else {
          whiteAdv.style.display = "none";
          blackAdv.style.display = "none";
        }
      }
    }
  }

  function getPlayerScore(evalResult) {
    if (!evalResult) return 0;
    const type = evalResult.type;
    const value = evalResult.value;
    if (type === 'mate') {
      if (value > 0) {
        return -10000 + value;
      } else {
        return 10000 + value;
      }
    } else {
      return -value || 0;
    }
  }

  function formatGameDuration(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}m ${secs}s`;
  }

  function validatePlayerNames() {
    if (typeof document === 'undefined') return true;
    const wNameInput = document.getElementById('whiteNameInput');
    const bNameInput = document.getElementById('blackNameInput');
    const errorDiv = document.getElementById('nameError');

    const wName = wNameInput?.value.trim();
    const bName = bNameInput?.value.trim();

    if (!wName || !bName) {
      if (errorDiv) {
        errorDiv.style.display = 'block';
        errorDiv.textContent = 'Please enter both player names';
      }
      if (!wName && wNameInput) wNameInput.classList.add('input-error');
      if (!bName && bNameInput) bNameInput.classList.add('input-error');
      return false;
    }

    if (errorDiv) errorDiv.style.display = 'none';
    if (wNameInput) wNameInput.classList.remove('input-error');
    if (bNameInput) bNameInput.classList.remove('input-error');
    return true;
  }

  function announceMove(msg) {
    if (CB.DOM.a11yAnnouncer) {
      CB.DOM.a11yAnnouncer.textContent = '';
      setTimeout(() => { if (CB.DOM.a11yAnnouncer) CB.DOM.a11yAnnouncer.textContent = msg; }, 50);
    }
  }

  function flashBoard() {
    if (CB.DOM.boardEl) {
      CB.DOM.boardEl.classList.remove('flash-error');
      void CB.DOM.boardEl.offsetWidth;
      CB.DOM.boardEl.classList.add('flash-error');
      if (CB.S.flashTimeout) clearTimeout(CB.S.flashTimeout);
      CB.S.flashTimeout = setTimeout(() => {
        if (CB.DOM.boardEl) CB.DOM.boardEl.classList.remove('flash-error');
      }, 2000);
    }

    if (CB.S.blindfoldMode && typeof document !== 'undefined') {
      CB.S.illegalMoveCount++;
      if (CB.S.illegalMoveCount >= 3) {
        CB.S.illegalMoveCount = 0;
        document.body.classList.remove('blindfold-mode');
        setTimeout(() => {
          if (CB.S.blindfoldMode) {
            document.body.classList.add('blindfold-mode');
          }
        }, 3000);
      }
    }
  }

  function showStatus(msg, err) {
    const gameStatusEl = typeof document !== 'undefined' ? document.getElementById("game-status") : null;
    if (gameStatusEl) {
      gameStatusEl.textContent = msg;
    }
    if (CB.DOM.statusEl) {
      CB.DOM.statusEl.className = 'status-bar' + (err ? ' error' : '');
    }
  }

  function getSquareSize() {
    if (!CB.DOM.boardEl) return 60;
    const s = CB.DOM.boardEl.querySelector('.square');
    return s ? s.getBoundingClientRect().width : 60;
  }

  function isAITurn() {
    return CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor && !CB.S.gameOver;
  }

  CB.pKey = pKey;
  CB.pColor = pColor;
  CB.sq = sq;
  CB.getSquareLabel = getSquareLabel;
  CB.squareLabelToRowCol = squareLabelToRowCol;
  CB.computeLegalMovesClient = computeLegalMovesClient;
  CB.calculateMaterial = calculateMaterial;
  CB.updateMaterialUI = updateMaterialUI;
  CB.getPlayerScore = getPlayerScore;
  CB.formatGameDuration = formatGameDuration;
  CB.validatePlayerNames = validatePlayerNames;
  CB.announceMove = announceMove;
  CB.flashBoard = flashBoard;
  CB.showStatus = showStatus;
  CB.getSquareSize = getSquareSize;
  CB.isAITurn = isAITurn;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      pKey: pKey,
      pColor: pColor,
      sq: sq,
      getSquareLabel: getSquareLabel,
      squareLabelToRowCol: squareLabelToRowCol,
      computeLegalMovesClient: computeLegalMovesClient,
      calculateMaterial: calculateMaterial,
      updateMaterialUI: updateMaterialUI,
      getPlayerScore: getPlayerScore,
      formatGameDuration: formatGameDuration,
      validatePlayerNames: validatePlayerNames,
      announceMove: announceMove,
      flashBoard: flashBoard,
      showStatus: showStatus,
      getSquareSize: getSquareSize,
      isAITurn: isAITurn
    };
  }
})();
