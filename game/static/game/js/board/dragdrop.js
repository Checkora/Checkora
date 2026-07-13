/**
 * board/dragdrop.js — Mouse and touch drag-and-drop handling
 *
 * Extracted from board.js: onDragStart, onDrop, and touch event listeners
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  function onDragStart(e, r, c) {
    const isPremoveMode = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor;
    const vBoard = isPremoveMode && CB.getVirtualBoard ? CB.getVirtualBoard() : CB.S.board;
    if (!vBoard || !vBoard[r]) return e.preventDefault && e.preventDefault();
    const piece = vBoard[r][c];
    if (!piece) {
      if (CB.S.blindfoldMode) {
        if (CB.showStatus) CB.showStatus('No piece there', true);
        if (CB.flashBoard) CB.flashBoard();
      }
      return e.preventDefault && e.preventDefault();
    }
    if (CB.S.paused || CB.S.gameOver) return e.preventDefault && e.preventDefault();

    const isPremovedDrag = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor && CB.pColor(piece) === CB.S.playerColor;

    if (CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor && !isPremovedDrag) {
      return e.preventDefault && e.preventDefault();
    }

    if (!isPremovedDrag && CB.pColor(piece) !== CB.S.turn) {
      return e.preventDefault && e.preventDefault();
    }

    CB.S.dragging = true;
    CB.S.dragSrc = { r, c };
    if (CB.selectPiece) CB.selectPiece(r, c);
  }

  async function onDrop(e, tr, tc) {
    if (CB.S.replayMode || CB.S.viewingPastState) return;
    if (!CB.S.dragSrc) return;
    if (CB.tryMove) await CB.tryMove(CB.S.dragSrc.r, CB.S.dragSrc.c, tr, tc);
    CB.S.dragSrc = null;
  }

  function initTouchControls() {
    if (typeof document === 'undefined' || !CB.DOM.boardEl) return;
    const boardEl = CB.DOM.boardEl;

    boardEl.addEventListener('touchstart', (e) => {
      const touch = e.touches[0];
      const squareEl = e.target.closest('.square');
      if (!squareEl) return;

      const r = parseInt(squareEl.dataset.r);
      const c = parseInt(squareEl.dataset.c);
      const isPremoveMode = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor;
      const vBoard = isPremoveMode && CB.getVirtualBoard ? CB.getVirtualBoard() : CB.S.board;
      if (!vBoard || !vBoard[r]) return;
      const piece = vBoard[r][c];
      if (!piece || CB.S.paused || CB.S.gameOver) return;

      const isPremoveDrag = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor && CB.pColor(piece) === CB.S.playerColor;
      const isNormalDrag = CB.S.gameMode === 'ai' ? (CB.S.turn === CB.S.playerColor && CB.pColor(piece) === CB.S.playerColor) : (CB.pColor(piece) === CB.S.turn);

      if (!isPremoveDrag && !isNormalDrag) return;

      CB.S.touchDragSrc = { r, c };
    }, { passive: true });

    boardEl.addEventListener('touchmove', (e) => {
      if (!CB.S.touchDragSrc || !CB.S.touchStartPos) return;

      const touch = e.touches[0];

      if (!CB.S.touchDragging) {
        const dx = touch.clientX - CB.S.touchStartPos.x;
        const dy = touch.clientY - CB.S.touchStartPos.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > 8) {
          CB.S.touchDragging = true;

          if (CB.selectPiece) CB.selectPiece(CB.S.touchDragSrc.r, CB.S.touchDragSrc.c);

          const squareEl = CB.sq(CB.S.touchDragSrc.r, CB.S.touchDragSrc.c);
          const pieceImg = squareEl ? squareEl.querySelector('.piece') : null;
          if (pieceImg) {
            CB.S.activeTouchPieceClone = pieceImg.cloneNode(true);
            CB.S.activeTouchPieceClone.className = 'piece touch-drag-clone';

            const rect = pieceImg.getBoundingClientRect();
            CB.S.touchOffset = { x: rect.width / 2, y: rect.height / 2 };

            CB.S.activeTouchPieceClone.style.position = 'fixed';
            CB.S.activeTouchPieceClone.style.pointerEvents = 'none';
            CB.S.activeTouchPieceClone.style.zIndex = '9999';
            CB.S.activeTouchPieceClone.style.width = rect.width + 'px';
            CB.S.activeTouchPieceClone.style.height = rect.height + 'px';
            CB.S.activeTouchPieceClone.style.transform = 'scale(1.15)';
            CB.S.activeTouchPieceClone.style.filter = 'drop-shadow(0 8px 16px rgba(0, 0, 0, 0.45))';
            CB.S.activeTouchPieceClone.style.transition = 'none';
            CB.S.activeTouchPieceClone.style.willChange = 'left, top';

            document.body.appendChild(CB.S.activeTouchPieceClone);
            pieceImg.classList.add('touch-dragging-original');
          }
        }
      }

      if (CB.S.touchDragging && CB.S.activeTouchPieceClone) {
        CB.S.activeTouchPieceClone.style.left = (touch.clientX - CB.S.touchOffset.x) + 'px';
        CB.S.activeTouchPieceClone.style.top = (touch.clientY - CB.S.touchOffset.y) + 'px';

        if (e.cancelable) e.preventDefault();
      }
    }, { passive: false });

    boardEl.addEventListener('touchend', async (e) => {
      const srcSquare = CB.S.touchDragSrc;
      if (!srcSquare && !CB.S.selected) return;
      const touch = e.changedTouches[0];
      let movedToSquare = false;

      if (CB.S.touchDragging && CB.S.touchDragSrc) {
        const srcSquareEl = CB.sq(srcSquare.r, srcSquare.c);
        const pieceImg = srcSquareEl ? srcSquareEl.querySelector('.piece') : null;
        if (pieceImg) {
          pieceImg.classList.remove('touch-dragging-original');
        }

        if (CB.S.activeTouchPieceClone) {
          CB.S.activeTouchPieceClone.remove();
          CB.S.activeTouchPieceClone = null;
        }

        const targetEl = document.elementFromPoint(touch.clientX, touch.clientY);
        const destSquareEl = targetEl ? targetEl.closest('.square') : null;
        if (destSquareEl) {
          const tr = parseInt(destSquareEl.dataset.r, 10);
          const tc = parseInt(destSquareEl.dataset.c, 10);

          if (tr !== CB.S.touchDragSrc.r || tc !== CB.S.touchDragSrc.c) {
            if (CB.tryMove) await CB.tryMove(CB.S.touchDragSrc.r, CB.S.touchDragSrc.c, tr, tc);
            movedToSquare = true;
          }
        }

        if (!movedToSquare) {
          if (CB.deselect) CB.deselect();
        }

        e.preventDefault();
      } else {
        e.preventDefault();

        const targetEl = document.elementFromPoint(
          touch.clientX,
          touch.clientY
        );
        if (!targetEl) return;
        const squareEl = targetEl.closest('.square');

        if (!squareEl) return;

        const tr = parseInt(squareEl.dataset.r);
        const tc = parseInt(squareEl.dataset.c);
        if (CB.onClick) await CB.onClick(tr, tc);
      }

      CB.S.touchStartPos = null;
      CB.S.touchDragSrc = null;
      CB.S.touchTapSquare = null;
      CB.S.touchDragging = false;
    }, { passive: false });

    boardEl.addEventListener('touchcancel', (e) => {
      if (!CB.S.touchStartPos) return;

      if (CB.S.touchDragging && CB.S.touchDragSrc) {
        const srcSquareEl = CB.sq(CB.S.touchDragSrc.r, CB.S.touchDragSrc.c);
        const pieceImg = srcSquareEl ? srcSquareEl.querySelector('.piece') : null;
        if (pieceImg) {
          pieceImg.classList.remove('touch-dragging-original');
        }

        if (CB.S.activeTouchPieceClone) {
          CB.S.activeTouchPieceClone.remove();
          CB.S.activeTouchPieceClone = null;
        }

        if (CB.deselect) CB.deselect();
      }

      CB.S.touchStartPos = null;
      CB.S.touchDragSrc = null;
      CB.S.touchTapSquare = null;
      CB.S.touchDragging = false;
    }, { passive: true });
  }

  CB.onDragStart = onDragStart;
  CB.onDrop = onDrop;
  CB.initTouchControls = initTouchControls;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      onDragStart: onDragStart,
      onDrop: onDrop,
      initTouchControls: initTouchControls
    };
  }
})();
