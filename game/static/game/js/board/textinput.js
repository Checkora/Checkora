/**
 * board/textinput.js — Text-based move input (SAN, manual e2e4), FEN loading, and PGN export
 *
 * Extracted from board.js: handleSanMove, manual move input,
 * FEN copy/load, PGN export, and button initializations.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  async function handleSanMove() {
    if (typeof document === 'undefined') return;
    const sanMoveInput = document.getElementById('sanMoveInput');
    const sanMoveBtn = document.getElementById('sanMoveBtn');
    const sanMoveError = document.getElementById('sanMoveError');

    if (!sanMoveInput) return;
    let san = sanMoveInput.value.trim();
    if (!san) return;

    if (sanMoveError) sanMoveError.style.display = 'none';

    if (CB.S.paused || CB.S.gameOver) {
      if (sanMoveError) {
        sanMoveError.textContent = 'Game is not active';
        sanMoveError.style.display = 'block';
      }
      if (CB.flashBoard) CB.flashBoard();
      return;
    }

    if (CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor) {
      if (sanMoveError) {
        sanMoveError.textContent = 'Not your turn';
        sanMoveError.style.display = 'block';
      }
      if (CB.flashBoard) CB.flashBoard();
      return;
    }

    if (sanMoveBtn) sanMoveBtn.disabled = true;

    try {
      if (!CB.get) throw new Error("API not loaded");
      const data = await CB.get('/api/state/');
      if (!data || !data.fen) throw new Error("No FEN");

      if (typeof window === 'undefined' || !window.Chess) throw new Error("Chess engine not loaded");
      const chess = new window.Chess(data.fen);

      if (/^[0oO]-[0oO]-[0oO]$/i.test(san)) {
        san = 'O-O-O';
      } else if (/^[0oO]-[0oO]$/i.test(san)) {
        san = 'O-O';
      } else {
        const promoMatch = san.match(/=([qrbnQRBN])([+#]?)$/);
        const suffix = promoMatch
          ? `=${promoMatch[1].toUpperCase()}${promoMatch[2]}`
          : san.match(/[+#]$/) ? san.slice(-1) : '';
        const body = promoMatch
          ? san.slice(0, san.lastIndexOf('='))
          : suffix ? san.slice(0, -1) : san;

        if (/^[NBRQK]/.test(san) || /^[nrqk]/.test(san)) {
          san = body.charAt(0).toUpperCase() + body.slice(1).toLowerCase() + suffix;
        } else if (/^[a-h]/i.test(san)) {
          san = body.toLowerCase() + suffix;
        }
      }

      const moveObj = chess.move(san);
      if (!moveObj) {
        if (sanMoveError) {
          sanMoveError.textContent = 'Invalid or illegal move notation';
          sanMoveError.style.display = 'block';
        }
        if (CB.flashBoard) CB.flashBoard();
        if (sanMoveBtn) sanMoveBtn.disabled = false;
        return;
      }

      const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
      const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];

      const fc = files.indexOf(moveObj.from[0]);
      const fr = ranks.indexOf(moveObj.from[1]);
      const tc = files.indexOf(moveObj.to[0]);
      const tr = ranks.indexOf(moveObj.to[1]);
      const promo = moveObj.promotion || null;

      if (!CB.executeMove) throw new Error("executeMove not loaded");
      const result = await CB.executeMove(fr, fc, tr, tc, promo);
      if (result && result.success) {
        sanMoveInput.value = '';
        sanMoveInput.blur();
      } else {
        if (sanMoveError) {
          sanMoveError.textContent = (result && result.message) ? result.message : 'Move rejected';
          sanMoveError.style.display = 'block';
        }
        if (CB.flashBoard) CB.flashBoard();
      }
    } catch (err) {
      console.error('SAN Move Error:', err);
      if (sanMoveError) {
        sanMoveError.textContent = 'Error processing move';
        sanMoveError.style.display = 'block';
      }
    } finally {
      if (sanMoveBtn) sanMoveBtn.disabled = false;
    }
  }

  async function downloadPgn() {
    if (typeof document === 'undefined' || !CB.get) return;
    const copyPgnBtn = document.getElementById('copyPgnBtn');
    const data = await CB.get('/api/state/');

    if (data && data.pgn) {
      const blob = new Blob([data.pgn], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      const wName = CB.DOM.whiteNameLabel ? CB.DOM.whiteNameLabel.textContent : 'White';
      const bName = CB.DOM.blackNameLabel ? CB.DOM.blackNameLabel.textContent : 'Black';
      const date = new Date().toISOString().split('T')[0];

      a.download = `checkora_${wName}_vs_${bName}_${date}.pgn`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      if (copyPgnBtn) copyPgnBtn.textContent = 'Downloaded!';

      if (typeof clearTimeout !== 'undefined' && CB.S.pgnDownloadTimeout) {
        clearTimeout(CB.S.pgnDownloadTimeout);
      }

      if (typeof setTimeout !== 'undefined') {
        CB.S.pgnDownloadTimeout = setTimeout(() => {
          if (copyPgnBtn) copyPgnBtn.textContent = 'Export as PGN';
        }, 2000);
      }
    }
  }

  async function copyFenToClipboard() {
    if (typeof navigator === 'undefined' || !navigator.clipboard || !CB.get) return;
    const copyFenBtn = document.getElementById('copyFenBtn');
    const data = await CB.get('/api/state/');
    if (data && data.fen) {
      navigator.clipboard.writeText(data.fen);

      if (copyFenBtn) copyFenBtn.textContent = 'Copied!';
      if (typeof clearTimeout !== 'undefined' && CB.S.fenCopyTimeout) {
        clearTimeout(CB.S.fenCopyTimeout);
      }

      if (typeof setTimeout !== 'undefined') {
        CB.S.fenCopyTimeout = setTimeout(() => {
          if (copyFenBtn) copyFenBtn.textContent = 'Copy FEN';
        }, 2000);
      }
    }
  }

  function initTextInput() {
    if (typeof document === 'undefined') return;

    const sanMoveInput = document.getElementById('sanMoveInput');
    const sanMoveBtn = document.getElementById('sanMoveBtn');
    const sanMoveError = document.getElementById('sanMoveError');

    if (sanMoveInput) {
      sanMoveInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          sanMoveInput.value = '';
          sanMoveInput.blur();
          if (sanMoveError) sanMoveError.style.display = 'none';
        } else if (e.key === 'Enter') {
          e.preventDefault();
          handleSanMove();
        }
      });
      sanMoveInput.addEventListener('input', () => {
        if (sanMoveError) sanMoveError.style.display = 'none';
      });
    }

    if (sanMoveBtn) {
      sanMoveBtn.addEventListener('click', handleSanMove);
    }

    const manualMoveInput = document.getElementById('manualMoveInput');
    const manualMoveError = document.getElementById('manualMoveError');

    if (manualMoveInput) {
      manualMoveInput.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const val = manualMoveInput.value.trim().toLowerCase();
          if (!val) return;

          const match = val.match(/^([a-h])([1-8])([a-h])([1-8])([qrbn])?$/);
          if (!match) {
            if (manualMoveError) {
              manualMoveError.textContent = 'Invalid format (e.g. e2e4)';
              manualMoveError.style.display = 'block';
            }
            if (CB.flashBoard) CB.flashBoard();
            return;
          }

          if (manualMoveError) manualMoveError.style.display = 'none';
          const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
          const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];

          const fc = files.indexOf(match[1]);
          const fr = ranks.indexOf(match[2]);
          const tc = files.indexOf(match[3]);
          const tr = ranks.indexOf(match[4]);
          const promo = match[5] || null;

          if (CB.S.paused || CB.S.gameOver) {
            if (manualMoveError) {
              manualMoveError.textContent = 'Game is not active';
              manualMoveError.style.display = 'block';
            }
            if (CB.flashBoard) CB.flashBoard();
            return;
          }
          if (CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor) {
            if (manualMoveError) {
              manualMoveError.textContent = 'Not your turn';
              manualMoveError.style.display = 'block';
            }
            if (CB.flashBoard) CB.flashBoard();
            return;
          }
          const p = CB.S.board[fr][fc];
          const pColorFunc = CB.pColor || ((piece) => (piece === piece.toUpperCase() ? 'white' : 'black'));
          if (!p || pColorFunc(p) !== CB.S.turn) {
            if (manualMoveError) {
              manualMoveError.textContent = 'Invalid piece';
              manualMoveError.style.display = 'block';
            }
            if (CB.flashBoard) CB.flashBoard();
            return;
          }

          if (CB.isPromotionMove && CB.isPromotionMove(fr, fc, tr) && !promo) {
            if (manualMoveError) {
              manualMoveError.textContent = 'Promotion piece required (e.g. e7e8q)';
              manualMoveError.style.display = 'block';
            }
            if (CB.flashBoard) CB.flashBoard();
            return;
          }

          manualMoveInput.value = '';
          if (CB.executeMove) await CB.executeMove(fr, fc, tr, tc, promo);
        }
      });

      manualMoveInput.addEventListener('input', () => {
        if (manualMoveError) manualMoveError.style.display = 'none';
      });
    }

    const copyPgnBtn = document.getElementById('copyPgnBtn');
    if (copyPgnBtn) copyPgnBtn.onclick = downloadPgn;

    const copyFenBtn = document.getElementById('copyFenBtn');
    if (copyFenBtn) copyFenBtn.onclick = copyFenToClipboard;

    const newFenBtn = document.getElementById('newFenBtn');
    const fenStartBtn = document.getElementById('fenStartBtn');
    const fenCancelBtn = document.getElementById('fenCancelBtn');
    const fenInput = document.getElementById('fenInput');
    const fenOverlay = document.getElementById('fenOverlay');
    const fenError = document.getElementById('fenError');

    if (newFenBtn) {
      newFenBtn.onclick = () => {
        if (CB.showConfirm) {
          CB.showConfirm(
            "Load from FEN?",
            "Your current progress will be lost.<br>Do you want to continue?",
            () => {
              if (fenError) fenError.textContent = '';
              if (fenInput) fenInput.value = '';
              if (fenOverlay) fenOverlay.classList.add('active');
            },
            '#ff6b6b'
          );
        }
      };
    }

    if (fenStartBtn) {
      fenStartBtn.onclick = async () => {
        const fenValue = fenInput?.value?.trim() || '';
        if (!fenValue) {
          if (fenError) fenError.textContent = 'Please enter a FEN string.';
          return;
        }

        const mode = CB.S.gameMode === 'ai' ? 'ai' : 'pvp';
        const pColor = mode === 'ai' ? CB.S.playerColor : 'white';
        const diff = mode === 'ai' ? CB.S.currentDifficulty : 'medium';
        if (CB.startNewGame) {
          const started = await CB.startNewGame(mode, pColor, diff, fenValue);
          if (!started) return;
        }

        if (fenOverlay) fenOverlay.classList.remove('active');
        if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.remove('active');
        if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = 'visible';
      };
    }

    if (fenCancelBtn) {
      fenCancelBtn.onclick = () => {
        if (fenOverlay) fenOverlay.classList.remove('active');
      };
    }

    if (fenInput) {
      fenInput.addEventListener('keydown', async (e) => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        fenStartBtn?.click();
      });
    }
  }

  CB.handleSanMove = handleSanMove;
  CB.downloadPgn = downloadPgn;
  CB.copyFenToClipboard = copyFenToClipboard;
  CB.initTextInput = initTextInput;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      handleSanMove: handleSanMove,
      downloadPgn: downloadPgn,
      copyFenToClipboard: copyFenToClipboard,
      initTextInput: initTextInput
    };
  }
})();
