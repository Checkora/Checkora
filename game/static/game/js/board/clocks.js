/**
 * board/clocks.js — Clock rendering, timer ticks, and time control picker
 *
 * Extracted from board.js: formatTime, updateThinkingDots, renderClocks,
 * startTimer, initTimeControlPicker
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  const fmt = t => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
  function formatTime(t) { return fmt(t); }

  function updateThinkingDots() {
    if (typeof document === 'undefined') return;
    const whiteClock = document.getElementById('whiteClock');
    const blackClock = document.getElementById('blackClock');

    if (!whiteClock || !blackClock) return;

    let targetClock = null;

    if (!CB.S.paused && !CB.S.gameOver) {
      if (whiteClock.classList.contains('active')) {
        targetClock = whiteClock;
      } else if (blackClock.classList.contains('active')) {
        targetClock = blackClock;
      }
    }

    const whiteTimeEl = whiteClock.querySelector('.time');
    const blackTimeEl = blackClock.querySelector('.time');

    const whiteHasDots = whiteTimeEl?.querySelector('.thinking-dots') !== null && whiteTimeEl?.querySelector('.thinking-dots') !== undefined;
    const blackHasDots = blackTimeEl?.querySelector('.thinking-dots') !== null && blackTimeEl?.querySelector('.thinking-dots') !== undefined;

    if (targetClock === whiteClock && whiteHasDots && !blackHasDots) return;
    if (targetClock === blackClock && blackHasDots && !whiteHasDots) return;
    if (!targetClock && !whiteHasDots && !blackHasDots) return;

    const wDots = whiteClock.querySelector('.thinking-dots');
    if (wDots) wDots.remove();
    const bDots = blackClock.querySelector('.thinking-dots');
    if (bDots) bDots.remove();

    if (CB.S.paused || CB.S.gameOver) return;

    if (!targetClock) return;

    const dots = document.createElement('span');
    dots.className = 'thinking-dots';
    dots.innerHTML = `
            <span></span>
            <span></span>
            <span></span>
        `;

    const timeEl = targetClock.querySelector('.time');
    if (timeEl) {
      timeEl.appendChild(dots);
    }
  }

  function renderClocks() {
    if (typeof document === 'undefined') return;
    const wTime = document.getElementById('whiteTime');
    const bTime = document.getElementById('blackTime');
    const whiteClock = document.getElementById('whiteClock');
    const blackClock = document.getElementById('blackClock');

    if (CB.S.gameMode === 'ai') {
      const playerClock = CB.S.playerColor === 'white' ? whiteClock : blackClock;
      const playerTimeEl = CB.S.playerColor === 'white' ? wTime : bTime;
      const aiClock = CB.S.playerColor === 'white' ? blackClock : whiteClock;
      const aiTimeEl = CB.S.playerColor === 'white' ? bTime : wTime;

      if (playerTimeEl) playerTimeEl.textContent = formatTime(CB.S.playerColor === 'white' ? CB.S.whiteTime : CB.S.blackTime);
      if (aiTimeEl) {
        aiTimeEl.textContent = formatTime(CB.S.playerColor === 'white' ? CB.S.blackTime : CB.S.whiteTime);
        aiTimeEl.style.fontSize = '';
        aiTimeEl.style.color = '';
      }

      const isAiTurn = CB.S.turn !== CB.S.playerColor;
      if (playerClock) {
        playerClock.classList.toggle('active', !isAiTurn);
        playerClock.classList.toggle('inactive', isAiTurn);
        const pt = CB.S.playerColor === 'white' ? CB.S.whiteTime : CB.S.blackTime;
        playerClock.classList.toggle('low-1', pt <= 30 && pt > 20);
        playerClock.classList.toggle('low-2', pt <= 20 && pt > 10);
        playerClock.classList.toggle('low-3', pt <= 10 && pt > 0);
      }
      if (aiClock) {
        aiClock.style.border = '';
        aiClock.style.boxShadow = '';
        aiClock.classList.toggle('active', isAiTurn);
        aiClock.classList.toggle('inactive', !isAiTurn);
        const at = CB.S.playerColor === 'white' ? CB.S.blackTime : CB.S.whiteTime;
        aiClock.classList.toggle('low-1', at <= 30 && at > 20);
        aiClock.classList.toggle('low-2', at <= 20 && at > 10);
        aiClock.classList.toggle('low-3', at <= 10 && at > 0);
      }
    } else {
      if (wTime) wTime.textContent = formatTime(CB.S.whiteTime);
      if (bTime) bTime.textContent = formatTime(CB.S.blackTime);
      if (whiteClock) {
        whiteClock.classList.toggle('active', CB.S.turn === 'white');
        whiteClock.classList.remove('inactive');
        whiteClock.classList.toggle('low-1', CB.S.whiteTime <= 30 && CB.S.whiteTime > 20);
        whiteClock.classList.toggle('low-2', CB.S.whiteTime <= 20 && CB.S.whiteTime > 10);
        whiteClock.classList.toggle('low-3', CB.S.whiteTime <= 10 && CB.S.whiteTime > 0);
      }
      if (blackClock) {
        blackClock.classList.toggle('active', CB.S.turn === 'black');
        blackClock.classList.remove('inactive');
        blackClock.classList.toggle('low-1', CB.S.blackTime <= 30 && CB.S.blackTime > 20);
        blackClock.classList.toggle('low-2', CB.S.blackTime <= 20 && CB.S.blackTime > 10);
        blackClock.classList.toggle('low-3', CB.S.blackTime <= 10 && CB.S.blackTime > 0);
      }
    }
    if (CB.DOM.whiteYouTag) CB.DOM.whiteYouTag.style.display = (CB.S.gameMode === 'ai' && CB.S.playerColor === 'white') ? 'inline' : 'none';
    if (CB.DOM.blackYouTag) CB.DOM.blackYouTag.style.display = (CB.S.gameMode === 'ai' && CB.S.playerColor === 'black') ? 'inline' : 'none';
    updateThinkingDots();
  }

  function startTimer() {
    if (typeof clearInterval !== 'undefined') clearInterval(CB.S.timerInterval);
    if (typeof setInterval === 'undefined') return;
    CB.S.timerInterval = setInterval(() => {
      if (CB.S.paused || CB.S.gameOver) return;

      if (CB.S.gameMode === 'ai') {
        if (CB.S.turn === CB.S.playerColor) {
          if (CB.S.playerColor === 'white' && CB.S.whiteTime > 0) CB.S.whiteTime--;
          else if (CB.S.playerColor === 'black' && CB.S.blackTime > 0) CB.S.blackTime--;
        } else if (CB.S.aiThinking) {
          if (CB.S.playerColor === 'white' && CB.S.blackTime > 0) CB.S.blackTime--;
          else if (CB.S.playerColor === 'black' && CB.S.whiteTime > 0) CB.S.whiteTime--;
        } else {
          return;
        }
      } else {
        if (CB.S.turn === 'white' && CB.S.whiteTime > 0) CB.S.whiteTime--;
        else if (CB.S.turn === 'black' && CB.S.blackTime > 0) CB.S.blackTime--;
      }

      renderClocks();

      if (CB.S.soundEnabled && CB.sounds && CB.sounds.check) {
        if (!CB.S.whiteAlertFired && CB.S.whiteTime > 0 && CB.S.whiteTime <= 30) {
          CB.S.whiteAlertFired = true;
          CB.sounds.check.currentTime = 0;
          const playback = CB.sounds.check.play();
          if (playback?.catch) playback.catch(() => {});
        }
        if (!CB.S.blackAlertFired && CB.S.blackTime > 0 && CB.S.blackTime <= 30) {
          CB.S.blackAlertFired = true;
          CB.sounds.check.currentTime = 0;
          const playback = CB.sounds.check.play();
          if (playback?.catch) playback.catch(() => {});
        }
      }

      if (CB.S.turn === 'white' && CB.S.whiteTime === 0) {
        if (CB.endGame) CB.endGame('timeout', 'white');
      } else if (CB.S.turn === 'black' && CB.S.blackTime === 0) {
        if (CB.endGame) CB.endGame('timeout', 'black');
      }
    }, 1000);
  }

  function initTimeControlPicker() {
    if (typeof document === 'undefined') return;
    const trigger = document.getElementById('timeControlTrigger');
    const popover = document.getElementById('timeControlPopover');
    const tabs = document.querySelectorAll('.tc-tab-btn');
    const tabContents = document.querySelectorAll('.tc-tab-content');
    const presetBtns = document.querySelectorAll('.tc-preset-btn');
    const applyCustomBtn = document.getElementById('applyCustomTCBtn');
    const display = document.getElementById('tcDisplayText');

    if (!trigger || !popover) return;

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const isVisible = popover.style.display === 'flex';
      popover.style.display = isVisible ? 'none' : 'flex';
    });

    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        e.stopPropagation();
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        const targetTab = tab.dataset.tab;
        tabContents.forEach(content => {
          if (content.id === `tab-${targetTab}`) {
            content.style.display = 'block';
          } else {
            content.style.display = 'none';
          }
        });
      });
    });

    presetBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        presetBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        CB.S.selectedMins = parseInt(btn.dataset.mins, 10);
        CB.S.selectedIncrement = parseInt(btn.dataset.inc, 10);

        if (display) display.textContent = btn.textContent.trim();
        popover.style.display = 'none';
      });
    });

    if (applyCustomBtn) {
      applyCustomBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const minsInput = document.getElementById('customMinsInput');
        const secsInput = document.getElementById('customSecsInput');
        const incInput = document.getElementById('customIncInput');

        if (minsInput && incInput) {
          let mins = parseInt(minsInput.value, 10);
          let secs = secsInput ? parseInt(secsInput.value, 10) : 0;
          let inc = parseInt(incInput.value, 10);

          if (isNaN(mins) || mins < 0) mins = 0;
          if (mins > 300) mins = 300;
          if (isNaN(secs) || secs < 0) secs = 0;
          if (secs > 59) secs = 59;
          if (isNaN(inc) || inc < 0) inc = 0;
          if (inc > 180) inc = 180;

          const totalSecs = mins * 60 + secs;
          if (totalSecs <= 0) {
            if (secsInput) secsInput.value = 30;
            secs = 30;
          }

          minsInput.value = mins;
          if (secsInput) secsInput.value = secs;
          incInput.value = inc;

          CB.S.selectedMins = (mins * 60 + secs) / 60;
          CB.S.selectedIncrement = inc;

          presetBtns.forEach(b => b.classList.remove('active'));

          let displayText;
          if (mins === 0) {
            displayText = `${secs}s`;
          } else if (secs === 0) {
            displayText = `${mins} min`;
          } else {
            displayText = `${mins}:${String(secs).padStart(2, '0')} min`;
          }
          if (inc > 0) {
            displayText += ` | ${inc}`;
          }
          if (display) display.textContent = displayText;
          popover.style.display = 'none';
        }
      });
    }

    document.addEventListener('click', (e) => {
      if (!popover.contains(e.target) && e.target !== trigger) {
        popover.style.display = 'none';
      }
    });
  }

  CB.formatTime = formatTime;
  CB.updateThinkingDots = updateThinkingDots;
  CB.renderClocks = renderClocks;
  CB.startTimer = startTimer;
  CB.initTimeControlPicker = initTimeControlPicker;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      formatTime: formatTime,
      updateThinkingDots: updateThinkingDots,
      renderClocks: renderClocks,
      startTimer: startTimer,
      initTimeControlPicker: initTimeControlPicker
    };
  }
})();
