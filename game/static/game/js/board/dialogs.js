/**
 * board/dialogs.js — Confirmation dialogs, side selection, and leave confirmation
 *
 * Extracted from board.js: showConfirm, hideConfirm, showSideSelectionModal,
 * requestNewGame, offerDraw, openLeaveConfirm, closeLeaveConfirm, confirmLeave,
 * and dialog button initialization.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  function showConfirm(title, msg, callback, titleColor = '#ff6b6b') {
    if (CB.DOM.confirmTitle) {
      CB.DOM.confirmTitle.textContent = title;
      CB.DOM.confirmTitle.style.color = titleColor;
    }
    if (CB.DOM.confirmMessage) CB.DOM.confirmMessage.innerHTML = msg;
    CB.S.confirmCallback = callback;
    if (CB.DOM.boardEl) CB.DOM.boardEl.classList.add('confirm-open');
    if (CB.DOM.confirmOverlay) CB.DOM.confirmOverlay.classList.add('active');
  }

  function hideConfirm() {
    if (CB.DOM.boardEl) CB.DOM.boardEl.classList.remove('confirm-open');
    if (CB.DOM.confirmOverlay) CB.DOM.confirmOverlay.classList.remove('active');
    CB.S.confirmCallback = null;
  }

  function showSideSelectionModal(onChoose) {
    if (typeof document === 'undefined') return;
    const modal = document.getElementById('sideModal');
    if (!modal) return;
    modal.style.display = 'flex';

    function pick(side) {
      modal.style.display = 'none';
      const w = document.getElementById('chooseWhite');
      const b = document.getElementById('chooseBlack');
      const r = document.getElementById('chooseRandom');
      if (w) w.onclick = null;
      if (b) b.onclick = null;
      if (r) r.onclick = null;
      onChoose(side);
    }

    const w = document.getElementById('chooseWhite');
    const b = document.getElementById('chooseBlack');
    const r = document.getElementById('chooseRandom');
    if (w) w.onclick = () => pick('white');
    if (b) b.onclick = () => pick('black');
    if (r) r.onclick = () => pick(Math.random() < 0.5 ? 'white' : 'black');
  }

  function requestNewGame(mode) {
    if (typeof document === 'undefined') return;
    const diffContainer = document.getElementById('confirmDifficultyContainer');
    if (diffContainer) {
      if (mode === 'ai') {
        diffContainer.style.display = 'block';
      } else {
        diffContainer.style.display = 'none';
      }
    }

    showConfirm(
      "Abandon Game?",
      "Your current progress will be lost.<br>Are you sure you want to start a new game?",
      () => {
        const diffSel = document.getElementById('confirmDifficultySelect');
        const timerSel = document.getElementById('confirmTimerSelect');
        const diff = diffSel ? diffSel.value : 'medium';
        const timeLimitMins = timerSel ? parseInt(timerSel.value, 10) : null;
        if (mode === 'ai') {
          showSideSelectionModal(side => {
            if (CB.startNewGame) CB.startNewGame('ai', side, diff, null, timeLimitMins);
          });
        } else {
          if (CB.startNewGame) CB.startNewGame('pvp', 'white', diff, null, timeLimitMins);
        }
      },
      '#ff6b6b'
    );
  }

  async function offerDraw() {
    if (CB.S.paused || CB.S.gameOver || CB.S.gameMode !== 'pvp') return;
    const offeringPlayer = CB.S.turn === 'white' ? 'White' : 'Black';
    const receivingPlayer = CB.S.turn === 'white' ? 'Black' : 'White';

    showConfirm(
      "Offer Draw?",
      `As <b>${offeringPlayer}</b>, do you want to offer a draw to ${receivingPlayer}?`,
      async () => {
        if (CB.DOM.drawMessage) {
          CB.DOM.drawMessage.textContent = `${offeringPlayer} offers a draw. ${receivingPlayer}, do you accept?`;
        }
        if (CB.DOM.drawOverlay) CB.DOM.drawOverlay.classList.add('active');
        if (CB.pauseGame) await CB.pauseGame();
      },
      '#f0c040'
    );
  }

  function shouldConfirmLeave() {
    return !CB.S.gameOver && CB.DOM.welcomeOverlay && !CB.DOM.welcomeOverlay.classList.contains('active');
  }

  function openLeaveConfirm() {
    if (typeof document === 'undefined') return;
    const leaveConfirmOverlay = document.getElementById('leaveConfirmOverlay');
    const leaveConfirmDialog = document.getElementById('leaveConfirmDialog');
    const leaveConfirmNo = document.getElementById('leaveConfirmNo');
    if (!leaveConfirmOverlay) return;

    CB.S.leaveConfirmFocusReturn = document.activeElement;
    leaveConfirmOverlay.classList.add('active');
    leaveConfirmOverlay.setAttribute('aria-hidden', 'false');
    if (typeof CB.announceMove === 'function') {
      CB.announceMove('Confirm navigation to home page');
    }
    setTimeout(() => {
      if (leaveConfirmNo) {
        leaveConfirmNo.focus();
      } else if (leaveConfirmDialog) {
        leaveConfirmDialog.focus();
      }
    }, 0);
  }

  function closeLeaveConfirm() {
    if (typeof document === 'undefined') return;
    const leaveConfirmOverlay = document.getElementById('leaveConfirmOverlay');
    if (!leaveConfirmOverlay) return;
    leaveConfirmOverlay.classList.remove('active');
    leaveConfirmOverlay.setAttribute('aria-hidden', 'true');
    if (CB.S.leaveConfirmFocusReturn && typeof CB.S.leaveConfirmFocusReturn.focus === 'function') {
      CB.S.leaveConfirmFocusReturn.focus();
    }
    CB.S.leaveConfirmFocusReturn = null;
  }

  function confirmLeave() {
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
  }

  function initDialogs() {
    if (typeof document === 'undefined') return;

    if (CB.DOM.confirmYesBtn) {
      CB.DOM.confirmYesBtn.onclick = () => {
        if (CB.DOM.boardEl) CB.DOM.boardEl.classList.remove('confirm-open');
        if (CB.DOM.confirmOverlay) CB.DOM.confirmOverlay.classList.remove('active');
        if (CB.S.confirmCallback) CB.S.confirmCallback();
        CB.S.confirmCallback = null;
      };
    }

    if (CB.DOM.confirmNoBtn) {
      CB.DOM.confirmNoBtn.onclick = () => {
        if (CB.DOM.boardEl) CB.DOM.boardEl.classList.remove('confirm-open');
        if (CB.DOM.confirmOverlay) CB.DOM.confirmOverlay.classList.remove('active');
        CB.S.confirmCallback = null;
      };
    }

    if (CB.DOM.drawAcceptBtn) {
      CB.DOM.drawAcceptBtn.onclick = async () => {
        if (CB.DOM.drawOverlay) CB.DOM.drawOverlay.classList.remove('active');
        if (CB.post) {
          const data = await CB.post('/api/draw/', { action: 'accept' });
          if (data.success) {
            if (CB.S.soundEnabled && CB.sounds && CB.sounds.draw) {
              CB.sounds.draw.currentTime = 0;
              const playback = CB.sounds.draw.play();
              if (playback?.catch) playback.catch(() => {});
            }
            if (CB.endGame) CB.endGame('draw', CB.S.turn, data.draw_reason);
          }
        }
      };
    }

    if (CB.DOM.drawDeclineBtn) {
      CB.DOM.drawDeclineBtn.onclick = () => {
        if (CB.DOM.drawOverlay) CB.DOM.drawOverlay.classList.remove('active');
        if (CB.resumeGame) CB.resumeGame();
      };
    }

    const leaveConfirmYes = document.getElementById('leaveConfirmYes');
    const leaveConfirmNo = document.getElementById('leaveConfirmNo');
    if (leaveConfirmYes) leaveConfirmYes.addEventListener('click', confirmLeave);
    if (leaveConfirmNo) leaveConfirmNo.addEventListener('click', closeLeaveConfirm);

    document.querySelectorAll('a[href="/"]').forEach(link => {
      link.addEventListener('click', (e) => {
        if (shouldConfirmLeave()) {
          e.preventDefault();
          openLeaveConfirm();
        }
      });
    });

    if (typeof navigator !== 'undefined' && !navigator.webdriver && typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => {
        if (!CB.S.paused && typeof navigator.sendBeacon === 'function') {
          const blob = new Blob([JSON.stringify({ pause: true })], { type: 'application/json' });
          navigator.sendBeacon('/api/pause/', blob);
        }
      });
    }
  }

  CB.showConfirm = showConfirm;
  CB.hideConfirm = hideConfirm;
  CB.showSideSelectionModal = showSideSelectionModal;
  CB.requestNewGame = requestNewGame;
  CB.offerDraw = offerDraw;
  CB.shouldConfirmLeave = shouldConfirmLeave;
  CB.openLeaveConfirm = openLeaveConfirm;
  CB.closeLeaveConfirm = closeLeaveConfirm;
  CB.confirmLeave = confirmLeave;
  CB.initDialogs = initDialogs;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      showConfirm: showConfirm,
      hideConfirm: hideConfirm,
      showSideSelectionModal: showSideSelectionModal,
      requestNewGame: requestNewGame,
      offerDraw: offerDraw,
      shouldConfirmLeave: shouldConfirmLeave,
      openLeaveConfirm: openLeaveConfirm,
      closeLeaveConfirm: closeLeaveConfirm,
      confirmLeave: confirmLeave,
      initDialogs: initDialogs
    };
  }
})();
