/**
 * board/events.js — Event listeners, UI button handlers, welcome setup, and main initialization
 *
 * Extracted from board.js: global keyboard shortcuts, UI button clicks,
 * welcome screen setup/validation, and initGame entrypoint.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

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

  function prepareWelcomeForPvP(clearAIValue = false) {
    if (typeof document === 'undefined') return;
    const whiteInput = document.getElementById('whiteNameInput');
    const blackInput = document.getElementById('blackNameInput');
    const errorDiv = document.getElementById('nameError');

    if (CB.DOM.pveOptions) CB.DOM.pveOptions.style.display = 'none';
    if (CB.DOM.modeSelection) CB.DOM.modeSelection.style.display = 'flex';
    if (CB.DOM.nameInputs) CB.DOM.nameInputs.style.display = 'flex';

    if (whiteInput) {
      whiteInput.style.display = 'block';
      whiteInput.placeholder = 'White Player Name';
      whiteInput.classList.remove('input-error');
    }
    if (blackInput) {
      blackInput.style.display = 'block';
      blackInput.placeholder = 'Black Player Name';
      blackInput.classList.remove('input-error');
      if (clearAIValue && blackInput.value === 'AI') {
        blackInput.value = '';
      }
    }
    if (errorDiv) errorDiv.style.display = 'none';
  }

  function dismissGameOverOverlay() {
    if (typeof document === 'undefined' || !CB.DOM.gameOverOverlay) return;
    CB.DOM.gameOverOverlay.classList.remove('active', 'game-over-celebration');
    const confettiContainer = CB.DOM.gameOverOverlay.querySelector('.confetti-container');
    if (confettiContainer) {
      confettiContainer.remove();
    }
  }

  function openWelcomeForNewGame() {
    if (typeof document === 'undefined') return;
    dismissGameOverOverlay();
    prepareWelcomeForPvP(true);

    const whiteInput = document.getElementById('whiteNameInput');
    const blackInput = document.getElementById('blackNameInput');
    if (whiteInput) {
      whiteInput.value = CB.S.currentWhiteName || '';
    }
    if (blackInput) {
      const aiNames = ['AI', 'ai'];
      blackInput.value = aiNames.includes(CB.S.currentBlackName) ? '' : (CB.S.currentBlackName || '');
    }
    if (CB.DOM.welcomeFenInput) CB.DOM.welcomeFenInput.value = '';
    if (CB.DOM.welcomeFenError) CB.DOM.welcomeFenError.textContent = '';

    CB.S.selectedPveColor = 'white';
    CB.DOM.pveOptions?.querySelectorAll('.color-choice').forEach(btn => {
      const isWhite = btn.dataset.color === 'white';
      btn.classList.toggle('active', isWhite);
      btn.style.borderColor = isWhite ? '#f0c040' : '#444';
    });

    if (CB.DOM.welcomeResumeBtn && CB.S.gameOver) {
      CB.DOM.welcomeResumeBtn.style.display = 'none';
    }
    if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.add('active');
  }

  function initThemeSwitcher() {
    if (typeof document === 'undefined') return;
    const themeBtns = document.querySelectorAll('.theme-btn');
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'classic';
    document.documentElement.setAttribute('data-theme', currentTheme);

    themeBtns.forEach(btn => {
      if (btn.dataset.theme === currentTheme) {
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
      }
      btn.onclick = () => {
        const theme = btn.dataset.theme;
        document.documentElement.setAttribute('data-theme', theme);
        if (typeof localStorage !== 'undefined') localStorage.setItem('chessBoardTheme', theme);
        themeBtns.forEach(b => {
          b.classList.remove('active');
          b.setAttribute('aria-pressed', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
      };
    });
  }

  function initSoundButtonState() {
    if (typeof document === 'undefined' || !CB.DOM.muteBtn) return;
    CB.DOM.muteBtn.textContent = CB.S.soundEnabled ? '🔊 Sound On' : '🔇 Muted';
    CB.DOM.muteBtn.setAttribute('aria-pressed', String(CB.S.soundEnabled));
  }

  function initCoordinatesToggle() {
    if (typeof document === 'undefined') return;
    const showCoordsBtn = document.getElementById('showCoordinatesCheckbox');
    if (!showCoordsBtn) return;

    const savedShowCoords = typeof localStorage !== 'undefined' && localStorage.getItem('showCoordinates') !== 'false';
    showCoordsBtn.checked = savedShowCoords;

    if (!savedShowCoords && CB.DOM.boardEl) {
      CB.DOM.boardEl.classList.add('hide-coordinates');
    }

    showCoordsBtn.addEventListener('change', () => {
      if (showCoordsBtn.checked) {
        if (CB.DOM.boardEl) CB.DOM.boardEl.classList.remove('hide-coordinates');
        if (typeof localStorage !== 'undefined') localStorage.setItem('showCoordinates', 'true');
      } else {
        if (CB.DOM.boardEl) CB.DOM.boardEl.classList.add('hide-coordinates');
        if (typeof localStorage !== 'undefined') localStorage.setItem('showCoordinates', 'false');
      }
    });
  }

  function initWelcomeControls() {
    if (typeof document === 'undefined') return;

    if (CB.DOM.welcomePvPBtn) {
      CB.DOM.welcomePvPBtn.onclick = async () => {
        if (!validatePlayerNames()) return;
        const fen = CB.DOM.welcomeFenInput?.value?.trim() || null;
        if (!CB.startNewGame) return;
        const started = await CB.startNewGame('pvp', 'white', 'medium', fen);
        if (!started) return;
        if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.remove('active');
        if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = 'visible';
      };
    }

    if (CB.DOM.welcomeDailyPuzzleBtn) {
      CB.DOM.welcomeDailyPuzzleBtn.onclick = async () => {
        if (CB.startDailyPuzzle) await CB.startDailyPuzzle();
        if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.remove('active');
        if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = 'visible';
      };
    }

    if (CB.DOM.welcomeAIBtn) {
      CB.DOM.welcomeAIBtn.onclick = () => {
        if (CB.DOM.modeSelection) CB.DOM.modeSelection.style.display = 'none';
        if (CB.DOM.pveOptions) CB.DOM.pveOptions.style.display = 'flex';

        const whiteInput = document.getElementById('whiteNameInput');
        const blackInput = document.getElementById('blackNameInput');
        const errorDiv = document.getElementById('nameError');

        if (whiteInput) {
          whiteInput.style.display = 'block';
          whiteInput.placeholder = 'Your Name';
          whiteInput.classList.remove('input-error');
        }
        if (blackInput) {
          blackInput.style.display = 'none';
          blackInput.value = 'AI';
          blackInput.classList.remove('input-error');
        }
        if (errorDiv) errorDiv.style.display = 'none';
        if (CB.DOM.nameInputs) CB.DOM.nameInputs.style.display = 'flex';
      };
    }

    if (CB.DOM.backToModes) {
      CB.DOM.backToModes.onclick = () => {
        prepareWelcomeForPvP(false);
      };
    }

    if (CB.DOM.pveOptions) {
      const colorBtns = CB.DOM.pveOptions.querySelectorAll('.color-choice');
      colorBtns.forEach(btn => {
        btn.onclick = () => {
          colorBtns.forEach(b => {
            b.classList.remove('active');
            b.style.borderColor = '#444';
          });
          btn.classList.add('active');
          btn.style.borderColor = '#f0c040';
          CB.S.selectedPveColor = btn.dataset.color;
        };
      });
    }

    if (CB.DOM.startAIBtn) {
      CB.DOM.startAIBtn.onclick = async () => {
        const wNameInput = document.getElementById('whiteNameInput');
        const errorDiv = document.getElementById('nameError');
        const playerName = wNameInput?.value.trim();

        if (!playerName) {
          if (errorDiv) {
            errorDiv.style.display = 'block';
            errorDiv.textContent = ' Please enter your name';
          }
          if (wNameInput) wNameInput.classList.add('input-error');
          return;
        }

        if (errorDiv) errorDiv.style.display = 'none';
        if (wNameInput) wNameInput.classList.remove('input-error');

        const diff = document.getElementById('welcomeDifficultySelect')?.value || 'medium';
        const fen = CB.DOM.welcomeFenInput?.value?.trim() || null;
        if (!CB.startNewGame) return;
        const started = await CB.startNewGame('ai', CB.S.selectedPveColor, diff, fen);
        if (!started) return;
        if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.remove('active');
        if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = 'visible';
      };
    }

    if (CB.DOM.welcomeFenInput) {
      CB.DOM.welcomeFenInput.addEventListener('keydown', async (e) => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        const fenValue = CB.DOM.welcomeFenInput.value?.trim();
        if (!fenValue) return;
        const isAIMode = CB.DOM.pveOptions && CB.DOM.pveOptions.style.display !== 'none';
        const mode = isAIMode ? 'ai' : 'pvp';
        const pColor = isAIMode ? CB.S.selectedPveColor : 'white';
        const diff = isAIMode
          ? (document.getElementById('welcomeDifficultySelect')?.value || 'medium')
          : 'medium';
        if (CB.DOM.welcomeFenError) CB.DOM.welcomeFenError.textContent = '';
        if (!CB.startNewGame) return;
        const started = await CB.startNewGame(mode, pColor, diff, fenValue);
        if (!started) return;
        if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.remove('active');
        if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = 'visible';
      });
    }

    if (CB.DOM.welcomeResumeBtn) {
      CB.DOM.welcomeResumeBtn.onclick = async () => {
        if (!CB.post) return;
        const data = await CB.post('/api/resume/', {});
        if (!data || !data.valid) {
          CB.DOM.welcomeResumeBtn.style.display = 'none';
          return;
        }
        if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.remove('active');
        if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = 'visible';
        CB.S.paused = false;
        if (CB.updatePauseUI) CB.updatePauseUI();
        if (CB.startTimer) CB.startTimer();
        if (CB.queueAIMoveIfNeeded) CB.queueAIMoveIfNeeded();
      };
    }

    if (CB.DOM.autoFlipBtn) {
      CB.DOM.autoFlipBtn.onclick = () => {
        CB.S.autoFlip = !CB.S.autoFlip;
        CB.DOM.autoFlipBtn.textContent = 'Auto-Flip: ' + (CB.S.autoFlip ? 'ON' : 'OFF');
        CB.DOM.autoFlipBtn.style.background = CB.S.autoFlip ? 'linear-gradient(135deg, #40c0f0, #2080d4)' : '';
        if (typeof localStorage !== 'undefined') localStorage.setItem('autoFlip', String(CB.S.autoFlip));
        if (CB.S.autoFlip && CB.S.gameMode === 'pvp') {
          CB.S.flipped = (CB.S.turn === 'black');
          if (CB.buildBoard) CB.buildBoard();
        }
      };
    }
  }

  function initGameButtons() {
    if (typeof document === 'undefined') return;

    if (CB.DOM.pauseBtn) {
      CB.DOM.pauseBtn.onclick = () => {
        if (CB.S.paused && CB.resumeGame) CB.resumeGame();
        else if (!CB.S.paused && CB.pauseGame) CB.pauseGame();
      };
    }
    if (CB.DOM.muteBtn && CB.toggleMute) {
      CB.DOM.muteBtn.onclick = CB.toggleMute;
    }
    if (CB.DOM.flipBtn && CB.toggleBoardOrientation) {
      CB.DOM.flipBtn.onclick = CB.toggleBoardOrientation;
    }

    const blindfoldBtn = document.getElementById('blindfoldBtn');
    if (blindfoldBtn) {
      blindfoldBtn.onclick = () => {
        CB.S.blindfoldMode = !CB.S.blindfoldMode;
        CB.S.illegalMoveCount = 0;
        blindfoldBtn.textContent = 'Blindfold: ' + (CB.S.blindfoldMode ? 'ON' : 'OFF');
        document.body.classList.toggle('blindfold-mode', CB.S.blindfoldMode);
        const msg = `Blindfold mode ${CB.S.blindfoldMode ? 'ON' : 'OFF'}`;
        if (CB.showStatus) CB.showStatus(msg, false);
        setTimeout(() => {
          const gameStatusEl = document.getElementById("game-status");
          if (gameStatusEl && gameStatusEl.textContent === msg && CB.showStatus) {
            CB.showStatus('', false);
          }
        }, 2000);
      };
    }

    if (CB.DOM.newPvPBtn) {
      CB.DOM.newPvPBtn.onclick = () => {
        dismissGameOverOverlay();
        if (CB.showConfirm) {
          CB.showConfirm(
            "Abandon Game?",
            "Your current progress will be lost.<br>Are you sure you want to start a new game?",
            () => { openWelcomeForNewGame(); },
            '#ff6b6b'
          );
        } else {
          openWelcomeForNewGame();
        }
      };
    }

    if (CB.DOM.newAIBtn) {
      CB.DOM.newAIBtn.onclick = () => {
        dismissGameOverOverlay();
        if (CB.requestNewGame) CB.requestNewGame('ai');
      };
    }

    if (CB.DOM.dailyPuzzleBtn) {
      CB.DOM.dailyPuzzleBtn.onclick = async () => {
        if (CB.showConfirm) {
          CB.showConfirm(
            "Start Daily Puzzle?",
            "Your current game will be lost.",
            async () => { if (CB.startDailyPuzzle) await CB.startDailyPuzzle(); },
            "#f0c040"
          );
        } else if (CB.startDailyPuzzle) {
          await CB.startDailyPuzzle();
        }
      };
    }

    if (CB.DOM.restartPuzzleBtn) {
      CB.DOM.restartPuzzleBtn.onclick = async () => {
        if (!CB.S.currentPuzzle || !CB.startNewGame) return;
        CB.S.puzzleMoveIndex = 0;
        if (CB.clearPuzzleHints) CB.clearPuzzleHints();
        await CB.startNewGame(
          "ai",
          "white",
          CB.S.currentPuzzle.difficulty || "medium",
          CB.S.currentPuzzle.fen,
          null,
          null,
          true
        );
        CB.S.currentPuzzleFen = CB.S.currentPuzzle.fen;
        CB.S.expectedMoveEval = null;
        if (CB.initStockfish) CB.initStockfish();
        if (CB.precalculateExpectedMoveEval) CB.precalculateExpectedMoveEval();
        if (CB.showStatus) CB.showStatus("Puzzle Restarted", false);
      };
    }

    if (CB.DOM.hintPuzzleBtn && CB.showPuzzleHint) {
      CB.DOM.hintPuzzleBtn.onclick = () => CB.showPuzzleHint();
    }

    if (CB.DOM.gameOverStartBtn) {
      CB.DOM.gameOverStartBtn.onclick = () => openWelcomeForNewGame();
    }

    const resRematchBtn = document.getElementById('resRematchBtn');
    if (resRematchBtn) {
      resRematchBtn.onclick = () => {
        dismissGameOverOverlay();
        const timeLimitString = `${CB.S.selectedMins}|${CB.S.selectedIncrement}`;
        if (CB.startNewGame) {
          CB.startNewGame(CB.S.gameMode, CB.S.playerColor, CB.S.currentDifficulty, null, timeLimitString, {
            white: CB.S.currentWhiteName,
            black: CB.S.currentBlackName
          });
        }
      };
    }

    const resDownloadPgnBtn = document.getElementById('resDownloadPgnBtn');
    if (resDownloadPgnBtn) {
      resDownloadPgnBtn.onclick = () => {
        const originalBtn = document.getElementById('copyPgnBtn');
        if (originalBtn) originalBtn.click();
      };
    }

    if (CB.DOM.gameOverExitBtn) {
      CB.DOM.gameOverExitBtn.addEventListener('click', () => {
        const confettiContainer = CB.DOM.gameOverOverlay?.querySelector('.confetti-container');
        if (confettiContainer) confettiContainer.remove();
      });
    }

    const exitToMenuBtn = document.getElementById('exitToMenuBtn');
    if (exitToMenuBtn) {
      exitToMenuBtn.onclick = () => {
        if (CB.DOM.gameOverOverlay) CB.DOM.gameOverOverlay.classList.remove('active', 'game-over-celebration');
        const confettiContainer = CB.DOM.gameOverOverlay?.querySelector('.confetti-container');
        if (confettiContainer) confettiContainer.remove();
        if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = 'hidden';
        prepareWelcomeForPvP(true);
        if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.add('active');
      };
    }

    if (CB.DOM.resignBtn) {
      CB.DOM.resignBtn.onclick = () => {
        if (CB.S.gameOver || !CB.post) return;
        if (CB.S.gameMode === 'pvp') {
          const modal = document.getElementById('resignModal');
          if (modal) {
            modal.style.display = 'flex';
            const hideModal = () => {
              modal.style.display = 'none';
              const rw = document.getElementById('resignWhite');
              const rb = document.getElementById('resignBlack');
              const rc = document.getElementById('resignCancel');
              if (rw) rw.onclick = null;
              if (rb) rb.onclick = null;
              if (rc) rc.onclick = null;
            };
            const confirmResign = (side) => {
              hideModal();
              if (CB.showConfirm) {
                CB.showConfirm("Resign?", `Are you sure ${side} wants to resign?`, async () => {
                  try {
                    const result = await CB.post('/api/resign/', { resigning_player: side });
                    if (result && result.valid) {
                      if (CB.S.soundEnabled && CB.sounds && CB.sounds.draw) {
                        CB.sounds.draw.currentTime = 0;
                        CB.sounds.draw.play().catch(() => {});
                      }
                      const loserColor = result.winner === 'white' ? 'black' : 'white';
                      if (CB.endGame) CB.endGame('resign', loserColor);
                    } else if (CB.showStatus) {
                      CB.showStatus('Resign failed. Please try again.', true);
                    }
                  } catch (_) {
                    if (CB.showStatus) CB.showStatus('Resign failed. Please check your connection and try again.', true);
                  }
                });
              }
            };
            const rw = document.getElementById('resignWhite');
            const rb = document.getElementById('resignBlack');
            const rc = document.getElementById('resignCancel');
            if (rw) rw.onclick = () => confirmResign('white');
            if (rb) rb.onclick = () => confirmResign('black');
            if (rc) rc.onclick = hideModal;
          }
        } else if (CB.showConfirm) {
          CB.showConfirm("Resign?", "Are you sure you want to resign?", async () => {
            try {
              const result = await CB.post('/api/resign/', {});
              if (result && result.valid) {
                if (CB.S.soundEnabled && CB.sounds && CB.sounds.draw) {
                  CB.sounds.draw.currentTime = 0;
                  CB.sounds.draw.play().catch(() => {});
                }
                const loserColor = result.winner === 'white' ? 'black' : 'white';
                if (CB.endGame) CB.endGame('resign', loserColor);
              } else if (CB.showStatus) {
                CB.showStatus('Resign failed. Please try again.', true);
              }
            } catch (_) {
              if (CB.showStatus) CB.showStatus('Resign failed. Please check your connection and try again.', true);
            }
          });
        }
      };
    }
  }

  function initGlobalListeners() {
    if (typeof document === 'undefined') return;

    if (CB.DOM.boardEl) {
      CB.DOM.boardEl.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        CB.S.premoveQueue = [];
        if (CB.refreshPremoveHighlight) CB.refreshPremoveHighlight();
        if (CB.showStatus) CB.showStatus("Premove cancelled", false);
      });
    }

    document.addEventListener('keydown', e => {
      if (e.repeat) return;
      const tag = document.activeElement && document.activeElement.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if (CB.S.replayMode) {
        if (e.key === 'ArrowLeft') { e.preventDefault(); CB.DOM.prevReplayBtn?.click(); return; }
        if (e.key === 'ArrowRight') { e.preventDefault(); CB.DOM.nextReplayBtn?.click(); return; }
        if (e.key === 'ArrowUp') { e.preventDefault(); CB.DOM.firstReplayBtn?.click(); return; }
        if (e.key === 'ArrowDown') { e.preventDefault(); CB.DOM.lastReplayBtn?.click(); return; }
      }

      const key = e.key.toLowerCase();
      const hasBlockingOverlay =
        (CB.DOM.shareModal?.style.display === 'flex') ||
        (CB.DOM.rulebookModal?.style.display === 'flex') ||
        CB.DOM.fenOverlay?.classList.contains('active') ||
        CB.DOM.confirmOverlay?.classList.contains('active') ||
        CB.DOM.drawOverlay?.classList.contains('active') ||
        CB.DOM.gameOverOverlay?.classList.contains('active') ||
        CB.DOM.welcomeOverlay?.classList.contains('active') ||
        document.getElementById('leaveConfirmOverlay')?.classList.contains('active');

      if (e.key === 'Escape') {
        const mobilePanel = document.getElementById('mobilePanel');
        const toggleBtn = document.getElementById('mobileControlsToggle');
        if (mobilePanel && mobilePanel.classList.contains('active')) {
          mobilePanel.classList.remove('active');
          if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
        }
      }

      if (hasBlockingOverlay && key !== 'escape') return;

      if (key === 'f' && CB.DOM.flipBtn) { e.preventDefault(); CB.DOM.flipBtn.click(); }
      else if (key === 'r' && CB.DOM.resignBtn) { e.preventDefault(); CB.DOM.resignBtn.click(); }
      else if (key === 'd' && CB.DOM.drawBtn && CB.DOM.drawBtn.style.display !== 'none' && !CB.DOM.drawBtn.disabled) { e.preventDefault(); CB.DOM.drawBtn.click(); }
      else if (key === 'p' && CB.DOM.pauseBtn && CB.DOM.pauseBtn.style.display !== 'none') { e.preventDefault(); CB.DOM.pauseBtn.click(); }
      else if (key === 'n' && CB.DOM.newPvPBtn) { e.preventDefault(); CB.DOM.newPvPBtn.click(); }
      else if (key === 'a' && CB.DOM.newAIBtn) { e.preventDefault(); CB.DOM.newAIBtn.click(); }
      else if (key === 'h') {
        e.preventDefault();
        if (CB.shouldConfirmLeave && CB.shouldConfirmLeave()) {
          if (CB.openLeaveConfirm) CB.openLeaveConfirm();
        } else if (typeof window !== 'undefined') {
          window.location.href = '/';
        }
      } else if (key === 'escape') {
        e.preventDefault();
        if (CB.DOM.shareModal?.style.display === 'flex') CB.DOM.shareModal.style.display = 'none';
        if (CB.DOM.rulebookModal?.style.display === 'flex') CB.DOM.rulebookModal.style.display = 'none';
        if (CB.DOM.fenOverlay?.classList.contains('active')) CB.DOM.fenOverlay.classList.remove('active');
        if (CB.closeLeaveConfirm && document.getElementById('leaveConfirmOverlay')?.classList.contains('active')) {
          CB.closeLeaveConfirm();
        }
      }
    });

    document.querySelectorAll('.emote-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        if (CB.S.gameMode !== 'pvp') return;
        if (CB.S.emoteCooldown) {
          if (CB.showStatus) {
            CB.showStatus('Emote cooldown (1s)', true);
            setTimeout(() => { if (CB.showStatus) CB.showStatus(''); }, 1000);
          }
          return;
        }
        CB.S.emoteCooldown = true;
        setTimeout(() => { CB.S.emoteCooldown = false; }, 1000);

        const emoteChar = e.currentTarget.getAttribute('data-emote');
        const emoteEl = document.createElement('div');
        emoteEl.className = 'floating-emote ' + (CB.S.turn === 'white' ? 'white-emote' : 'black-emote');
        emoteEl.textContent = emoteChar;
        const boardOuter = document.querySelector('.board-outer');
        if (boardOuter) {
          boardOuter.appendChild(emoteEl);
          setTimeout(() => emoteEl.remove(), 2000);
        }
      });
    });

    document.addEventListener('visibilitychange', async () => {
      if (document.hidden) {
        if (CB.pauseGame) CB.pauseGame().catch(() => {});
      } else {
        if (CB.handleReconnect) await CB.handleReconnect();
      }
    });

    if (typeof window !== 'undefined') {
      window.addEventListener('online', async () => {
        if (!CB.S.gameOver && CB.handleReconnect) {
          await CB.handleReconnect();
        }
      });
    }
  }

  function initEventListeners() {
    initThemeSwitcher();
    initSoundButtonState();
    initCoordinatesToggle();
    initWelcomeControls();
    initGameButtons();
    initGlobalListeners();
  }

  function initGame() {
    if (typeof document !== 'undefined') {
      const runInit = () => {
        if (CB.initDOM) CB.initDOM();
        if (CB.initSounds) CB.initSounds();
        if (CB.initStockfish) CB.initStockfish();
        if (CB.initTimeControlPicker) CB.initTimeControlPicker();
        if (CB.initPuzzle) CB.initPuzzle();
        if (CB.initReplayControls) CB.initReplayControls();
        if (CB.initDialogs) CB.initDialogs();
        if (CB.initTextInput) CB.initTextInput();
        if (CB.initDragDrop) CB.initDragDrop();
        if (CB.initTouchControls) CB.initTouchControls();
        initEventListeners();

        if (typeof module === 'undefined' || !module.exports) {
          if (CB.loadGame) CB.loadGame();
        }
      };

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', runInit);
      } else {
        runInit();
      }
    }
  }

  CB.validatePlayerNames = validatePlayerNames;
  CB.prepareWelcomeForPvP = prepareWelcomeForPvP;
  CB.dismissGameOverOverlay = dismissGameOverOverlay;
  CB.openWelcomeForNewGame = openWelcomeForNewGame;
  CB.initEventListeners = initEventListeners;
  CB.initGame = initGame;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      validatePlayerNames: validatePlayerNames,
      prepareWelcomeForPvP: prepareWelcomeForPvP,
      dismissGameOverOverlay: dismissGameOverOverlay,
      openWelcomeForNewGame: openWelcomeForNewGame,
      initEventListeners: initEventListeners,
      initGame: initGame
    };
  } else {
    initGame();
  }
})();
