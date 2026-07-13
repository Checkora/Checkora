/**
 * board/render.js — Board & UI rendering, animations, piece synchronization
 *
 * Extracted from board.js: parseBoard, buildBoard, updateLabels, syncPieces,
 * markPlayable, refreshHighlights, refreshPremoveHighlight, highlightCheck,
 * applyCheckHighlight, toggleSquareHighlight, drawPremoveArrows, animateMove,
 * updateTurn, updateMoves, updateCaptured, updatePlayerNames.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  function parseBoard(s) {
    if (!s || typeof s !== 'string') return s;
    const b = [];
    for (let i = 0; i < 8; i++) {
      const row = [];
      for (let j = 0; j < 8; j++) {
        const ch = s[i * 8 + j];
        row.push(ch === '.' ? null : ch);
      }
      b.push(row);
    }
    return b;
  }

  function updatePlayerNames(data) {
    if (data) {
      CB.S.currentWhiteName = data.white_name || CB.S.currentWhiteName || 'White';
      CB.S.currentBlackName = data.black_name || CB.S.currentBlackName || 'Black';
    }
    let wName = CB.S.currentWhiteName;
    let bName = CB.S.currentBlackName;

    if (CB.S.gameMode === 'ai' && typeof document !== 'undefined') {
      const diffLabel = (CB.S.currentDifficulty || 'medium').toUpperCase();
      const humanName = CB.S.currentWhiteName || document.getElementById('whiteNameInput')?.value?.trim()?.slice(0, 17) || 'Player';
      if (CB.S.playerColor === 'white') {
        wName = humanName;
        bName = `AI (Black)`;
      } else {
        bName = humanName;
        wName = `AI (White)`;
      }

      setTimeout(() => {
        const aiLabel = CB.S.playerColor === 'white'
          ? document.getElementById('blackNameLabel')
          : document.getElementById('whiteNameLabel');
        if (aiLabel && typeof document !== 'undefined') {
          aiLabel.innerHTML = '';
          const textNode = document.createTextNode(`AI (${CB.S.playerColor === 'white' ? 'BLACK' : 'WHITE'}) `);
          const badge = document.createElement('span');
          badge.textContent = diffLabel;
          badge.style.cssText = 'color:#f0c040 !important; font-weight:700; font-size:0.95em; letter-spacing:0.2px;';
          badge.setAttribute('aria-label', `AI difficulty: ${diffLabel}`);
          aiLabel.appendChild(textNode);
          aiLabel.appendChild(badge);
        }
      }, 0);
    }
    if (CB.DOM.whiteNameLabel) CB.DOM.whiteNameLabel.textContent = wName.toUpperCase();
    if (CB.DOM.blackNameLabel) CB.DOM.blackNameLabel.textContent = bName.toUpperCase();
    if (CB.DOM.whiteCapturedName) CB.DOM.whiteCapturedName.textContent = wName;
    if (CB.DOM.blackCapturedName) CB.DOM.blackCapturedName.textContent = bName;

    if (typeof document !== 'undefined') {
      const whiteAvatarEl = document.getElementById('whitePlayerAvatar');
      const blackAvatarEl = document.getElementById('blackPlayerAvatar');
      const whiteCapturedAvatarEl = document.getElementById('whiteCapturedAvatar');
      const blackCapturedAvatarEl = document.getElementById('blackCapturedAvatar');

      if (CB.S.gameMode === 'ai') {
        if (CB.DOM.whiteYouTag) CB.DOM.whiteYouTag.style.display = (CB.S.playerColor === 'white') ? 'inline' : 'none';
        if (CB.DOM.blackYouTag) CB.DOM.blackYouTag.style.display = (CB.S.playerColor === 'black') ? 'inline' : 'none';
        if (whiteAvatarEl && typeof window !== 'undefined' && window.USER_AVATAR_URL) {
          whiteAvatarEl.src = window.USER_AVATAR_URL;
          whiteAvatarEl.style.display = (CB.S.playerColor === 'white') ? 'inline-block' : 'none';
          if (whiteCapturedAvatarEl) {
            whiteCapturedAvatarEl.src = window.USER_AVATAR_URL;
            whiteCapturedAvatarEl.style.display = (CB.S.playerColor === 'white') ? 'inline-block' : 'none';
          }
        }
        if (blackAvatarEl && typeof window !== 'undefined' && window.USER_AVATAR_URL) {
          blackAvatarEl.src = window.USER_AVATAR_URL;
          blackAvatarEl.style.display = (CB.S.playerColor === 'black') ? 'inline-block' : 'none';
          if (blackCapturedAvatarEl) {
            blackCapturedAvatarEl.src = window.USER_AVATAR_URL;
            blackCapturedAvatarEl.style.display = (CB.S.playerColor === 'black') ? 'inline-block' : 'none';
          }
        }
      } else {
        if (CB.DOM.whiteYouTag) CB.DOM.whiteYouTag.style.display = 'none';
        if (CB.DOM.blackYouTag) CB.DOM.blackYouTag.style.display = 'none';
        if (whiteAvatarEl) whiteAvatarEl.style.display = 'none';
        if (blackAvatarEl) blackAvatarEl.style.display = 'none';
        if (whiteCapturedAvatarEl) whiteCapturedAvatarEl.style.display = 'none';
        if (blackCapturedAvatarEl) blackCapturedAvatarEl.style.display = 'none';
      }
    }
  }

  function updateLabels() {
    if (typeof document === 'undefined') return;
    const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];
    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    if (CB.S.flipped) {
      ranks.reverse();
      files.reverse();
    }
    const rLabels = document.getElementById('ranksLabels');
    const fLabels = document.getElementById('filesLabels');
    if (rLabels) rLabels.innerHTML = ranks.map(r => `<span>${r}</span>`).join('');
    if (fLabels) fLabels.innerHTML = files.map(f => `<span>${f}</span>`).join('');
  }

  function buildBoard() {
    if (!CB.DOM.boardEl) return;
    const bc = typeof document !== 'undefined' ? document.querySelector('.board-container') : null;
    if (bc) bc.classList.toggle('flipped', CB.S.flipped);
    CB.DOM.boardEl.innerHTML = '';
    for (let vr = 0; vr < 8; vr++) {
      for (let vc = 0; vc < 8; vc++) {
        const r = CB.S.flipped ? 7 - vr : vr;
        const c = CB.S.flipped ? 7 - vc : vc;
        const d = document.createElement('div');
        d.className = 'square ' + ((vr + vc) % 2 ? 'dark' : 'light');
        d.dataset.r = r;
        d.dataset.c = c;
        d.onclick = () => { if (CB.onClick) CB.onClick(r, c); };
        d.oncontextmenu = (e) => {
          e.preventDefault();
          toggleSquareHighlight(r, c);
        };
        d.ondragover = e => e.preventDefault();
        d.ondrop = e => { if (CB.onDrop) CB.onDrop(e, r, c); };

        d.draggable = true;
        d.ondragstart = e => {
          const isPremoveMode = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor;
          const vBoard = isPremoveMode && CB.getVirtualBoard ? CB.getVirtualBoard() : CB.S.board;
          const piece = vBoard[r][c];
          if (!piece) {
            if (CB.S.blindfoldMode) {
              if (CB.showStatus) CB.showStatus('No piece there', true);
              if (CB.flashBoard) CB.flashBoard();
            }
            return e.preventDefault();
          }
          if (CB.S.paused || CB.S.gameOver || CB.S.viewingPastState) return e.preventDefault();

          const isPremovedDrag = CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor && CB.pColor(piece) === CB.S.playerColor;

          if (CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor && !isPremovedDrag) {
            return e.preventDefault();
          }

          if (!isPremovedDrag && CB.pColor(piece) !== CB.S.turn) {
            return e.preventDefault();
          }

          if (e.dataTransfer) {
            e.dataTransfer.setData('text/plain', 'piece-move');
            e.dataTransfer.effectAllowed = 'move';
          }

          const pieceImg = d.querySelector('.piece');
          if (pieceImg && e.dataTransfer && e.dataTransfer.setDragImage) {
            e.dataTransfer.setDragImage(pieceImg, pieceImg.offsetWidth / 2, pieceImg.offsetHeight / 2);
          }

          CB.S.dragging = true;
          CB.S.dragSrc = { r, c };
          setTimeout(() => { if (CB.selectPiece) CB.selectPiece(r, c); }, 10);
        };

        d.ondragend = () => {
          CB.S.dragging = false;
          CB.S.dragSrc = null;
        };

        d.setAttribute('tabindex', '0');
        d.setAttribute('role', 'gridcell');
        d.setAttribute('data-row', r);
        d.setAttribute('data-col', c);
        d.setAttribute('aria-label', CB.getSquareLabel(r, c));
        d.onkeydown = (e) => { if (CB.handleSquareKeydown) CB.handleSquareKeydown(e, r, c); };

        CB.DOM.boardEl.appendChild(d);
      }
    }
    syncPieces();
    updateLabels();
  }

  function syncPieces() {
    if (!CB.DOM.boardEl || !CB.S.board || !CB.S.board.length) return;
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const el = CB.sq(r, c);
        if (!el) continue;
        el.innerHTML = '';
        const p = CB.S.board[r][c];
        if (!p) continue;

        const img = document.createElement('img');
        img.src = CB.PIECE_IMG[CB.pKey(p)];
        img.className = 'piece';
        img.draggable = false;
        img.ondragover = e => e.preventDefault();
        el.appendChild(img);
      }
    }
    refreshHighlights();
    markPlayable();
    if (CB.updateMaterialUI) CB.updateMaterialUI(CB.S.board);
  }

  function markPlayable() {
    if (!CB.DOM.boardEl) return;
    CB.DOM.boardEl.querySelectorAll('.piece').forEach(img => {
      const el = img.closest('.square');
      if (!el) return;
      const r = parseInt(el.dataset.r);
      const c = parseInt(el.dataset.c);
      const p = CB.S.board[r][c];
      const isPlayable = p && (
        CB.pColor(p) === CB.S.turn ||
        (CB.S.gameMode === 'ai' && CB.pColor(p) === CB.S.playerColor)
      );
      img.classList.toggle('playable', isPlayable);
    });
  }

  function refreshHighlights() {
    if (!CB.DOM.boardEl) return;
    CB.DOM.boardEl.querySelectorAll('.square').forEach(el => {
      el.classList.remove('selected', 'last-move', 'in-check', 'custom-highlight');
      el.querySelectorAll('.move-dot, .capture-ring').forEach(n => n.remove());
    });

    if (CB.S.lastMove) {
      const fromSq = CB.sq(CB.S.lastMove.from[0], CB.S.lastMove.from[1]);
      const toSq = CB.sq(CB.S.lastMove.to[0], CB.S.lastMove.to[1]);
      if (fromSq) fromSq.classList.add('last-move');
      if (toSq) toSq.classList.add('last-move');
    }
    if (CB.S.highlightedSquare) {
      const hSq = CB.sq(CB.S.highlightedSquare.r, CB.S.highlightedSquare.c);
      if (hSq) hSq.classList.add('custom-highlight');
    }
    if (CB.S.selected) {
      const sSq = CB.sq(CB.S.selected.r, CB.S.selected.c);
      if (sSq) sSq.classList.add('selected');
      if (CB.S.hints) {
        CB.S.hints.forEach(h => {
          const el = CB.sq(h.row, h.col);
          if (el) {
            const d = document.createElement('div');
            d.className = h.is_capture ? 'capture-ring' : 'move-dot';
            el.appendChild(d);
          }
        });
      }
    }
    refreshPremoveHighlight();
  }

  function refreshPremoveHighlight() {
    if (!CB.DOM.boardEl) return;
    CB.DOM.boardEl.querySelectorAll('.square').forEach(el => {
      el.classList.remove('premove');
    });

    if (CB.S.premoveQueue) {
      CB.S.premoveQueue.forEach(pm => {
        const fromSq = CB.sq(pm.from.r, pm.from.c);
        const toSq = CB.sq(pm.to.r, pm.to.c);
        if (fromSq) fromSq.classList.add('premove');
        if (toSq) toSq.classList.add('premove');
      });
    }

    drawPremoveArrows();
  }

  function highlightCheck() {
    if (!CB.DOM.boardEl) return;
    CB.DOM.boardEl.querySelectorAll('.square').forEach(el => {
      el.classList.remove('in-check');
    });
  }

  function applyCheckHighlight() {
    highlightCheck();
    const kingPiece = CB.S.turn === 'white' ? 'K' : 'k';
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        if (CB.S.board[r][c] === kingPiece) {
          const sqEl = CB.sq(r, c);
          if (sqEl) sqEl.classList.add('in-check');
          return;
        }
      }
    }
  }

  function toggleSquareHighlight(r, c) {
    if (CB.S.highlightedSquare) {
      const hSq = CB.sq(CB.S.highlightedSquare.r, CB.S.highlightedSquare.c);
      if (hSq) hSq.classList.remove('custom-highlight');
    }

    if (
      CB.S.highlightedSquare &&
      CB.S.highlightedSquare.r === r &&
      CB.S.highlightedSquare.c === c
    ) {
      CB.S.highlightedSquare = null;
    } else {
      CB.S.highlightedSquare = { r, c };
      const sqEl = CB.sq(r, c);
      if (sqEl) sqEl.classList.add('custom-highlight');
    }
  }

  function drawPremoveArrows(force = false) {
    if (typeof document === 'undefined' || !CB.DOM.boardEl) return;
    let overlay = document.getElementById('premove-svg-overlay');
    const currentStr = JSON.stringify(CB.S.premoveQueue || []);

    if (!force && overlay && currentStr === CB.S.lastPremoveQueueStr) {
      return;
    }
    CB.S.lastPremoveQueueStr = currentStr;

    if (overlay) {
      overlay.remove();
    }

    if (!CB.S.premoveQueue || CB.S.premoveQueue.length === 0) return;

    overlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    overlay.setAttribute('id', 'premove-svg-overlay');
    overlay.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:4;';

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'premove-arrowhead');
    marker.setAttribute('viewBox', '0 0 10 10');
    marker.setAttribute('refX', '8');
    marker.setAttribute('refY', '5');
    marker.setAttribute('markerWidth', '6');
    marker.setAttribute('markerHeight', '6');
    marker.setAttribute('orient', 'auto-start-reverse');

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M 0 1.5 L 10 5 L 0 8.5 z');
    path.setAttribute('fill', '#3b82f6');
    marker.appendChild(path);
    defs.appendChild(marker);
    overlay.appendChild(defs);

    const boardRect = CB.DOM.boardEl.getBoundingClientRect();
    if (boardRect.width === 0 || boardRect.height === 0) {
      return;
    }

    CB.S.premoveQueue.forEach((pm, idx) => {
      const fromSq = CB.sq(pm.from.r, pm.from.c);
      const toSq = CB.sq(pm.to.r, pm.to.c);
      if (!fromSq || !toSq) return;

      const fromRect = fromSq.getBoundingClientRect();
      const toRect = toSq.getBoundingClientRect();

      const x1 = (fromRect.left - boardRect.left) + fromRect.width / 2;
      const y1 = (fromRect.top - boardRect.top) + fromRect.height / 2;
      const x2 = (toRect.left - boardRect.left) + toRect.width / 2;
      const y2 = (toRect.top - boardRect.top) + toRect.height / 2;

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x1);
      line.setAttribute('y1', y1);
      line.setAttribute('x2', x2);
      line.setAttribute('y2', y2);
      line.setAttribute('stroke', '#3b82f6');
      line.setAttribute('stroke-width', '4');
      line.setAttribute('opacity', '0.75');
      line.setAttribute('marker-end', 'url(#premove-arrowhead)');
      overlay.appendChild(line);

      const midX = (x1 + x2) / 2;
      const midY = (y1 + y2) / 2;

      const badgeG = document.createElementNS('http://www.w3.org/2000/svg', 'g');

      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', midX);
      circle.setAttribute('cy', midY);
      circle.setAttribute('r', '8');
      circle.setAttribute('fill', '#16162a');
      circle.setAttribute('stroke', '#3b82f6');
      circle.setAttribute('stroke-width', '1.5');

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', midX);
      text.setAttribute('y', midY);
      text.setAttribute('fill', '#ffffff');
      text.setAttribute('font-size', '9px');
      text.setAttribute('font-weight', 'bold');
      text.setAttribute('font-family', 'sans-serif');
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('dominant-baseline', 'central');
      text.textContent = idx + 1;

      badgeG.appendChild(circle);
      badgeG.appendChild(text);
      overlay.appendChild(badgeG);
    });

    CB.DOM.boardEl.appendChild(overlay);
  }

  async function animateMove(fr, fc, tr, tc) {
    if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (!CB.DOM.boardEl) return;

    const animations = [];
    const size = CB.getSquareSize();
    const mult = CB.S.flipped ? -1 : 1;

    function createAnim(p, dRow, dCol) {
      return new Promise(resolve => {
        const originSquare = p.parentElement;

        if (originSquare) {
          const ghost = p.cloneNode(true);
          ghost.classList.add('piece-ghost');
          originSquare.appendChild(ghost);
          ghost.addEventListener(
            'animationend',
            () => ghost.remove(),
            { once: true }
          );
        }

        p.classList.add('moving');
        p.style.transition = 'transform 0.25s ease-in-out, opacity 0.2s ease';
        p.style.transform = `translate(${dCol * size * mult}px, ${dRow * size * mult}px)`;

        const onEnd = () => {
          p.removeEventListener('transitionend', onEnd);
          p.classList.remove('moving');
          p.style.transform = 'none';
          p.style.transition = '';
          resolve();
        };
        p.addEventListener('transitionend', onEnd);
        setTimeout(onEnd, 300);
      });
    }

    const pieceSq = CB.sq(fr, fc);
    const piece = pieceSq ? pieceSq.querySelector('.piece') : null;
    if (piece) {
      animations.push(createAnim(piece, tr - fr, tc - fc));

      const pType = CB.S.board[fr][fc];
      if (pType && pType.toLowerCase() === 'k' && Math.abs(tc - fc) === 2) {
        const isShort = tc > fc;
        const rookFr = fr;
        const rookFc = isShort ? 7 : 0;
        const rookTr = fr;
        const rookTc = isShort ? 5 : 3;
        const rookSq = CB.sq(rookFr, rookFc);
        const rook = rookSq ? rookSq.querySelector('.piece') : null;
        if (rook) {
          animations.push(createAnim(rook, rookTr - rookFr, rookTc - rookFc));
        }
      }
    }

    let capturedSq = CB.sq(tr, tc);
    const isEnPassant = piece && piece.src && piece.src.includes('p.png') && fc !== tc && !CB.S.board[tr][tc];
    if (isEnPassant) {
      capturedSq = CB.sq(fr, tc);
    }

    const targetPiece = capturedSq ? capturedSq.querySelector('.piece') : null;
    if (targetPiece) {
      targetPiece.classList.add('captured');
    }

    await Promise.all(animations);
  }

  function updateTurn() {
    if (
      !CB.DOM.turnEl ||
      !CB.DOM.whiteNameLabel ||
      !CB.DOM.blackNameLabel ||
      !CB.DOM.wCapEl ||
      !CB.DOM.bCapEl
    ) {
      return;
    }

    const badge = CB.DOM.turnEl;
    badge.className = 'turn-badge ' + CB.S.turn;

    let label = CB.S.turn.charAt(0).toUpperCase() + CB.S.turn.slice(1) + "'s Turn";
    const pName = CB.S.turn === 'white' ? CB.DOM.whiteNameLabel.textContent : CB.DOM.blackNameLabel.textContent;
    label = pName + "'s Turn";

    if (CB.S.gameMode === 'ai') {
      if (CB.S.turn === CB.S.playerColor) {
        label = "Your Turn";
      } else {
        label = "AI is thinking...";
      }
    }
    badge.textContent = label;
    if (CB.DOM.turnBadgeText) CB.DOM.turnBadgeText.textContent = pName;

    CB.DOM.wCapEl.classList.toggle('active', CB.S.turn === 'white');
    CB.DOM.bCapEl.classList.toggle('active', CB.S.turn === 'black');
  }

  function updateMoves(history) {
    if (!CB.DOM.movesEl) return;
    const startingFen = (typeof localStorage !== 'undefined' && localStorage.getItem('checkora_starting_fen')) || CB.DEFAULT_START_FEN;
    if (CB.rebuildGameFens) {
      CB.S.gameFens = CB.rebuildGameFens(history, startingFen);
    } else {
      CB.S.gameFens = [startingFen];
    }

    if (!CB.S.viewingPastState) {
      CB.S.stepperIndex = CB.S.gameFens.length - 1;
    }

    if (!history?.length) {
      CB.DOM.movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
      if (CB.updateStepperUI) CB.updateStepperUI();
      return;
    }
    CB.DOM.movesEl.innerHTML = '';
    for (let i = history.length - 1; i >= 0; i -= 2) {
      const whiteIdx = i % 2 === 0 ? i : i - 1;
      const blackIdx = whiteIdx + 1;
      const moveNum = Math.floor(whiteIdx / 2) + 1;
      const row = document.createElement('div');
      row.className = 'move-row';

      const whiteSpan = document.createElement('span');
      whiteSpan.className = 'move-white';
      whiteSpan.textContent = history[whiteIdx]?.notation ?? '';
      whiteSpan.dataset.moveIndex = whiteIdx;
      whiteSpan.onclick = () => {
        CB.S.stepperIndex = whiteIdx + 1;
        if (CB.updateStepperUI) CB.updateStepperUI();
      };

      const numSpan = document.createElement('span');
      numSpan.className = 'move-num';
      numSpan.textContent = `${moveNum}.`;
      row.appendChild(numSpan);
      row.appendChild(whiteSpan);

      if (history[blackIdx]) {
        const blackSpan = document.createElement('span');
        blackSpan.className = 'move-black';
        blackSpan.textContent = history[blackIdx].notation;
        blackSpan.dataset.moveIndex = blackIdx;
        blackSpan.onclick = () => {
          CB.S.stepperIndex = blackIdx + 1;
          if (CB.updateStepperUI) CB.updateStepperUI();
        };
        row.appendChild(blackSpan);
      }
      CB.DOM.movesEl.appendChild(row);
    }
    if (CB.updateStepperUI) CB.updateStepperUI();
    if (!CB.S.viewingPastState) CB.DOM.movesEl.scrollTop = 0;
  }

  function updateCaptured(cap) {
    if (!CB.DOM.wCapEl || !CB.DOM.bCapEl || !cap) return;
    CB.DOM.wCapEl.innerHTML = CB.DOM.bCapEl.innerHTML = '';

    const sortByValue = (pieces) => [...pieces].sort((a, b) =>
      (CB.MATERIAL_VALUES[b.toLowerCase()] || 0) - (CB.MATERIAL_VALUES[a.toLowerCase()] || 0)
    );

    let whitePoints = cap.white.reduce((sum, p) => sum + (CB.MATERIAL_VALUES[p.toLowerCase()] || 0), 0);
    let blackPoints = cap.black.reduce((sum, p) => sum + (CB.MATERIAL_VALUES[p.toLowerCase()] || 0), 0);

    const pieceNames = { 'p': 'Pawn', 'n': 'Knight', 'b': 'Bishop', 'r': 'Rook', 'q': 'Queen' };

    const makeImg = (p) => {
      const img = document.createElement('img');
      const key = CB.pKey(p);
      img.src = CB.PIECE_IMG[key];
      img.className = 'captured-img';
      img.dataset.piece = key;
      const name = pieceNames[p.toLowerCase()] || p;
      img.title = name;
      img.alt = name;
      return img;
    };

    sortByValue(cap.white).forEach((p) => CB.DOM.wCapEl.appendChild(makeImg(p)));
    sortByValue(cap.black).forEach((p) => CB.DOM.bCapEl.appendChild(makeImg(p)));

    if (typeof document !== 'undefined') {
      const wPointsEl = document.getElementById('whitePoints');
      const bPointsEl = document.getElementById('blackPoints');
      if (wPointsEl) wPointsEl.textContent = `+${whitePoints}`;
      if (bPointsEl) bPointsEl.textContent = `+${blackPoints}`;
    }
  }

  CB.parseBoard = parseBoard;
  CB.updatePlayerNames = updatePlayerNames;
  CB.updateLabels = updateLabels;
  CB.buildBoard = buildBoard;
  CB.syncPieces = syncPieces;
  CB.markPlayable = markPlayable;
  CB.refreshHighlights = refreshHighlights;
  CB.refreshPremoveHighlight = refreshPremoveHighlight;
  CB.highlightCheck = highlightCheck;
  CB.applyCheckHighlight = applyCheckHighlight;
  CB.toggleSquareHighlight = toggleSquareHighlight;
  CB.drawPremoveArrows = drawPremoveArrows;
  CB.animateMove = animateMove;
  CB.updateTurn = updateTurn;
  CB.updateMoves = updateMoves;
  CB.updateCaptured = updateCaptured;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      parseBoard: parseBoard,
      updatePlayerNames: updatePlayerNames,
      updateLabels: updateLabels,
      buildBoard: buildBoard,
      syncPieces: syncPieces,
      markPlayable: markPlayable,
      refreshHighlights: refreshHighlights,
      refreshPremoveHighlight: refreshPremoveHighlight,
      highlightCheck: highlightCheck,
      applyCheckHighlight: applyCheckHighlight,
      toggleSquareHighlight: toggleSquareHighlight,
      drawPremoveArrows: drawPremoveArrows,
      animateMove: animateMove,
      updateTurn: updateTurn,
      updateMoves: updateMoves,
      updateCaptured: updateCaptured
    };
  }
})();
