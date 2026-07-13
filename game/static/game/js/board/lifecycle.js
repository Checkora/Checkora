/**
 * board/lifecycle.js — Game lifecycle management (start, load, pause, resume)
 *
 * Extracted from board.js: startNewGame, loadGame, updatePlayerNames,
 * runStartCountdown, toggleBoardOrientation, pauseGame, resumeGame.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  const DEFAULT_START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

  function runStartCountdown(onComplete) {
    if (typeof document === 'undefined') {
      if (onComplete) onComplete();
      return;
    }
    const countdownOverlay = CB.DOM.countdownOverlay || document.getElementById('countdownOverlay');
    const countdownNumberEl = CB.DOM.countdownNumberEl || document.getElementById('countdownNumber');
    const boardEl = CB.DOM.boardEl || document.getElementById('board');

    if (!countdownOverlay || !countdownNumberEl) {
      if (onComplete) onComplete();
      return;
    }

    if (typeof clearInterval !== 'undefined' && CB.S.countdownInterval) {
      clearInterval(CB.S.countdownInterval);
    }

    const sequence = ['3', '2', '1', 'Go!'];
    let idx = 0;

    if (boardEl) boardEl.classList.add('countdown-active');
    countdownNumberEl.textContent = sequence[idx];
    countdownOverlay.classList.add('active');

    CB.S.countdownInterval = setInterval(() => {
      idx++;
      if (idx < sequence.length) {
        countdownNumberEl.textContent = sequence[idx];
      } else {
        if (typeof clearInterval !== 'undefined') clearInterval(CB.S.countdownInterval);
        countdownOverlay.classList.remove('active');
        if (boardEl) boardEl.classList.remove('countdown-active');
        if (onComplete) onComplete();
      }
    }, 1000);
  }

  function toggleBoardOrientation() {
    CB.S.flipped = !CB.S.flipped;
    if (CB.buildBoard) CB.buildBoard();
  }

  async function pauseGame() {
    if (CB.S.paused) return;
    if (!CB.post) return;
    const d = await CB.post('/api/pause/', { pause: true });
    if (d && d.paused !== undefined) {
      CB.S.paused = d.paused;
      CB.S.whiteTime = d.white_time;
      CB.S.blackTime = d.black_time;
      if (CB.updatePauseUI) CB.updatePauseUI();
      if (CB.renderClocks) CB.renderClocks();
    }
  }

  async function resumeGame() {
    try {
      if (!CB.post) return;
      const d = await CB.post('/api/pause/', { pause: false });
      CB.S.paused = false;

      if (d && d.white_time !== undefined) CB.S.whiteTime = d.white_time;
      if (d && d.black_time !== undefined) CB.S.blackTime = d.black_time;

      if (CB.updatePauseUI) CB.updatePauseUI();
      if (CB.renderClocks) CB.renderClocks();

      if (typeof clearInterval !== 'undefined') clearInterval(CB.S.timerInterval);
      if (CB.startTimer) CB.startTimer();

      if (CB.DOM.boardEl) CB.DOM.boardEl.classList.remove('paused');

      if (CB.queueAIMoveIfNeeded) CB.queueAIMoveIfNeeded();
    } catch (e) {
      console.error("Resume failed", e);
    }
  }

  function updatePlayerNames(data) {
    CB.S.currentWhiteName = data.white_name || CB.S.currentWhiteName || 'White';
    CB.S.currentBlackName = data.black_name || CB.S.currentBlackName || 'Black';
    let wName = CB.S.currentWhiteName;
    let bName = CB.S.currentBlackName;

    if (CB.S.gameMode === 'ai') {
      const diffLabel = (CB.S.currentDifficulty || 'medium').toUpperCase();
      const humanName = CB.S.currentWhiteName || (typeof document !== 'undefined' && document.getElementById('whiteNameInput')?.value?.trim()?.slice(0, 17)) || 'Player';
      if (CB.S.playerColor === 'white') {
        wName = humanName;
        bName = `AI (Black)`;
      } else {
        bName = humanName;
        wName = `AI (White)`;
      }

      if (typeof setTimeout !== 'undefined' && typeof document !== 'undefined') {
        setTimeout(() => {
          const aiLabel = CB.S.playerColor === 'white'
            ? document.getElementById('blackNameLabel')
            : document.getElementById('whiteNameLabel');
          if (aiLabel) {
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
        if (whiteAvatarEl && window.USER_AVATAR_URL) {
          whiteAvatarEl.src = window.USER_AVATAR_URL;
          whiteAvatarEl.style.display = (CB.S.playerColor === 'white') ? 'inline-block' : 'none';
          if (whiteCapturedAvatarEl) {
            whiteCapturedAvatarEl.src = window.USER_AVATAR_URL;
            whiteCapturedAvatarEl.style.display = (CB.S.playerColor === 'white') ? 'inline-block' : 'none';
          }
        }
        if (blackAvatarEl && window.USER_AVATAR_URL) {
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

  async function startNewGame(mode, pColor = 'white', difficulty = 'medium', fen = null, timeLimitMins = null, overrideNames = null, isPuzzle = false) {
    if (CB.clearEvaluationCache) CB.clearEvaluationCache();
    else CB.S.evaluationCache = {};

    if (!isPuzzle) {
      CB.S.dailyPuzzleMode = false;
      CB.S.currentPuzzle = null;
      CB.S.currentPuzzleFen = null;
      CB.S.puzzleAnalyzing = false;
      if (CB.S.stockfishWorker) {
        CB.S.stockfishWorker.terminate();
        CB.S.stockfishWorker = null;
      }
    }

    if (typeof document !== 'undefined') {
      const analysisPanel = document.getElementById('postGameAnalysisPanel');
      if (analysisPanel) analysisPanel.style.display = 'none';
      const tbody = document.getElementById('postGameAnalysisTableBody');
      if (tbody) tbody.innerHTML = '';
      const wc = document.getElementById("whiteClock");
      const bc = document.getElementById("blackClock");
      if (wc) wc.style.display = "";
      if (bc) bc.style.display = "";
      const sc = document.getElementById("streak-counter");
      if (sc) sc.style.display = "none";
    }

    CB.S.replayMode = false;
    CB.S.viewingPastState = false;
    CB.S.stepperIndex = 0;
    CB.S.gameFens = [];

    if (typeof clearInterval !== 'undefined' && CB.S.autoReplayInterval) {
      clearInterval(CB.S.autoReplayInterval);
      CB.S.autoReplayInterval = null;
    }

    if (CB.DOM.playReplayBtn) CB.DOM.playReplayBtn.textContent = '▶';
    if (CB.DOM.replayControls) CB.DOM.replayControls.classList.add('hidden');

    CB.S.aiRequestSeq = 0;
    CB.S.analysisRequestSeq++;
    CB.S.aiThinking = false;
    CB.S.premoveQueue = [];
    if (CB.refreshPremoveHighlight) CB.refreshPremoveHighlight();

    if (typeof clearTimeout !== 'undefined') {
      clearTimeout(CB.S.pgnDownloadTimeout);
      clearTimeout(CB.S.fenCopyTimeout);
    }

    if (CB.DOM.copyPgnBtn) CB.DOM.copyPgnBtn.textContent = 'Export as PGN';
    if (CB.DOM.copyFenBtn) CB.DOM.copyFenBtn.textContent = 'Copy FEN';

    if (typeof document !== 'undefined') {
      const overlay = document.getElementById('gameOverOverlay');
      if (overlay) {
        overlay.classList.remove('game-over-celebration');
        const cc = overlay.querySelector('.confetti-container');
        if (cc) cc.remove();
      }
    }

    const normalizeName = (name, fallback) => (name || fallback).trim().slice(0, 17);
    const wName = normalizeName(
      overrideNames ? overrideNames.white : (typeof document !== 'undefined' && document.getElementById('whiteNameInput')?.value),
      'White'
    );
    const bName = normalizeName(
      overrideNames ? overrideNames.black : (typeof document !== 'undefined' && document.getElementById('blackNameInput')?.value),
      'Black'
    );
    let currentMins = CB.S.selectedMins;
    let currentInc = CB.S.selectedIncrement;

    if (timeLimitMins !== null) {
      const strVal = String(timeLimitMins);
      if (strVal.includes('|')) {
        const parts = strVal.split('|');
        currentMins = parseFloat(parts[0]) || 10;
        currentInc = parseInt(parts[1], 10) || 0;
      } else {
        currentMins = parseFloat(strVal) || 10;
        currentInc = 0;
      }
    }

    const timeLimit = currentMins * 60;
    const increment = currentInc;

    const payload = {
      mode: mode,
      player_color: pColor,
      white_name: wName,
      black_name: bName,
      difficulty: difficulty,
      time_limit: timeLimit,
      increment: increment,
      opening: (typeof document !== 'undefined' && document.getElementById('welcomeOpeningSelect')?.value) || '',
    };

    const fenValue = (fen && fen.trim()) ? fen.trim() : null;
    if (typeof localStorage !== 'undefined') {
      if (fenValue) localStorage.setItem('checkora_starting_fen', fenValue);
      else localStorage.setItem('checkora_starting_fen', DEFAULT_START_FEN);
    }

    if (fenValue) payload.fen = fenValue;

    if (CB.DOM.fenError) CB.DOM.fenError.textContent = '';
    if (CB.DOM.welcomeFenError) CB.DOM.welcomeFenError.textContent = '';

    if (!CB.post) return false;
    const d = await CB.post('/api/new-game/', payload);

    if (d.valid === false || !d.board) {
      const message = d.message || 'Unable to start a new game.';
      if (CB.DOM.fenError) CB.DOM.fenError.textContent = message;
      if (CB.DOM.welcomeFenError && CB.DOM.welcomeOverlay?.classList.contains('active')) {
        CB.DOM.welcomeFenError.textContent = message;
      }
      if (CB.showStatus) CB.showStatus(message, true);
      return false;
    }

    if (CB.parseBoard) CB.S.board = CB.parseBoard(d.board);
    else CB.S.board = d.board;

    CB.S.turn = d.current_turn;
    if (d.fen) CB.S.liveFen = d.fen;
    CB.S.paused = false;
    CB.S.gameOver = false;
    CB.S.whiteAlertFired = false;
    CB.S.blackAlertFired = false;
    if (CB.incrementGameCounter) CB.incrementGameCounter();

    CB.S.gameStartTime = Date.now();

    if (!isPuzzle) {
      CB.S.gameMode = d.mode;
    }
    CB.S.playerColor = d.player_color || 'white';
    CB.S.currentDifficulty = d.difficulty || difficulty;

    if (CB.DOM.resignBtn) {
      CB.DOM.resignBtn.style.display = 'block';
      CB.DOM.resignBtn.hidden = false;
    }
    if (CB.DOM.pauseBtn) CB.DOM.pauseBtn.style.display = '';
    if (CB.DOM.drawBtn) CB.DOM.drawBtn.style.display = (CB.S.gameMode === 'pvp') ? 'block' : 'none';
    if (CB.DOM.newPvPBtn) CB.DOM.newPvPBtn.style.display = 'none';
    if (CB.DOM.newAIBtn) CB.DOM.newAIBtn.style.display = 'none';
    if (CB.DOM.dailyPuzzleBtn) CB.DOM.dailyPuzzleBtn.style.display = 'none';
    if (CB.DOM.newFenBtn) CB.DOM.newFenBtn.style.display = 'none';

    if (CB.S.gameMode === 'ai') {
      CB.S.flipped = (CB.S.playerColor === 'black');
    } else {
      CB.S.flipped = false;
    }

    if (CB.DOM.modeBadge) {
      if (isPuzzle) {
        CB.DOM.modeBadge.textContent = 'DAILY PUZZLE';
      } else {
        CB.DOM.modeBadge.textContent = CB.S.gameMode === 'ai' ? 'VS AI' : 'PVP';
      }
      CB.DOM.modeBadge.style.display = 'inline-block';
    }

    if (typeof document !== 'undefined') {
      const ep = document.getElementById('emotePanel');
      if (ep) ep.style.display = CB.S.gameMode === 'pvp' ? 'block' : 'none';
    }

    if (CB.DOM.movesEl) CB.DOM.movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
    if (CB.DOM.wCapEl) CB.DOM.wCapEl.innerHTML = '';
    if (CB.DOM.bCapEl) CB.DOM.bCapEl.innerHTML = '';
    CB.S.lastMove = null;
    CB.S.highlightedSquare = null;
    CB.S.selected = null;
    CB.S.hints = [];

    await loadGame();

    if (!isPuzzle && CB.updateModeButtonsUI) {
      CB.updateModeButtonsUI(CB.S.gameMode);
    }
    CB.S.paused = false;
    if (CB.updatePauseUI) CB.updatePauseUI();

    if (!isPuzzle) {
      if (typeof clearInterval !== 'undefined') clearInterval(CB.S.timerInterval);
      runStartCountdown(() => {
        if (CB.startTimer) CB.startTimer();
        if (CB.S.gameMode === 'ai' && CB.S.turn !== CB.S.playerColor && CB.queueAIMoveIfNeeded) {
          CB.queueAIMoveIfNeeded();
        }
      });
    }

    return true;
  }

  async function loadGame() {
    CB.S.aiRequestSeq = 0;
    CB.S.analysisRequestSeq++;
    CB.S.aiThinking = false;
    CB.S.premoveQueue = [];
    if (CB.refreshPremoveHighlight) CB.refreshPremoveHighlight();
    CB.S.whiteAlertFired = false;
    CB.S.blackAlertFired = false;

    if (typeof window !== 'undefined' && typeof URLSearchParams !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const puzzleId = urlParams.get('puzzle_id');
      if (puzzleId) {
        const url = new URL(window.location);
        url.searchParams.delete('puzzle_id');
        window.history.replaceState({}, document.title, url.pathname + url.search);

        try {
          const response = await fetch(`/api/puzzles/${puzzleId}/`);
          if (response.ok) {
            CB.S.currentPuzzle = await response.json();
            const solResponse = await fetch(`/api/puzzles/${puzzleId}/solution/`);
            if (solResponse.ok) {
              const solData = await solResponse.json();
              CB.S.currentPuzzle.solution = solData.solution;
            }
            CB.S.dailyPuzzleMode = true;
            if (typeof document !== 'undefined') {
              const wc = document.getElementById("whiteClock");
              const bc = document.getElementById("blackClock");
              const sc = document.getElementById("streak-counter");
              if (wc) wc.style.display = "none";
              if (bc) bc.style.display = "none";
              if (sc) sc.style.display = "block";
            }
            if (CB.updateStreakDisplay) CB.updateStreakDisplay();
            if (CB.DOM.restartPuzzleBtn) CB.DOM.restartPuzzleBtn.style.display = 'block';
            if (CB.DOM.hintPuzzleBtn) CB.DOM.hintPuzzleBtn.style.display = 'block';
            CB.S.puzzleMoveIndex = 0;
            if (CB.clearPuzzleHints) CB.clearPuzzleHints();
            await startNewGame(
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
            if (CB.updateStreakDisplay) CB.updateStreakDisplay();
            const streakData = CB.getPuzzleStreak ? CB.getPuzzleStreak() : { streak: 0 };
            if (CB.showStatus) {
              CB.showStatus(
                `${CB.S.currentPuzzle.title} | 🔥 Current Streak: ${streakData.streak}`,
                false
              );
            }
            if (CB.DOM.welcomeOverlay) CB.DOM.welcomeOverlay.classList.remove('active');
            if (CB.DOM.gameLayout) CB.DOM.gameLayout.style.visibility = 'visible';
            return;
          }
        } catch (error) {
          console.error("Error loading puzzle from query params:", error);
        }
      }
    }

    if (!CB.get) return;
    const data = await CB.get('/api/state/');

    if (data.time_limit !== undefined) {
      CB.S.selectedMins = data.time_limit / 60;
    }
    if (data.increment !== undefined) {
      CB.S.selectedIncrement = data.increment;
    }

    if (CB.parseBoard) CB.S.board = CB.parseBoard(data.board);
    else CB.S.board = data.board;

    if (data.fen) CB.S.liveFen = data.fen;
    CB.S.turn = data.current_turn;
    CB.S.whiteTime = data.white_time;
    CB.S.blackTime = data.black_time;
    CB.S.paused = data.paused;

    CB.S.gameMode = data.mode || 'pvp';
    if (CB.updateModeButtonsUI) CB.updateModeButtonsUI(CB.S.gameMode);
    CB.S.playerColor = data.player_color || 'white';
    CB.S.currentDifficulty = data.difficulty || CB.S.currentDifficulty;

    if (CB.DOM.flipControls) {
      CB.DOM.flipControls.style.display = (CB.S.gameMode === 'pvp') ? 'flex' : 'none';
    }

    if (CB.S.gameMode === 'ai') {
      CB.S.flipped = (CB.S.playerColor === 'black');
    } else {
      CB.S.flipped = false;
    }

    if (CB.DOM.modeBadge) {
      CB.DOM.modeBadge.textContent = CB.S.gameMode === 'ai' ? 'VS AI' : 'PVP';
      CB.DOM.modeBadge.style.display = 'inline-block';
    }

    if (typeof document !== 'undefined') {
      const ep = document.getElementById('emotePanel');
      if (ep) ep.style.display = CB.S.gameMode === 'pvp' ? 'block' : 'none';
    }

    const hasMoves = data.move_history && data.move_history.length > 0;
    const isResumable = hasMoves && data.game_status === 'active';
    if (isResumable) {
      if (CB.DOM.welcomeResumeBtn) {
        CB.DOM.welcomeResumeBtn.style.display = 'block';
        CB.DOM.welcomeResumeBtn.textContent = data.mode === 'ai'
          ? 'Replay Previous Game'
          : 'Resume Game';
      }
    } else {
      if (CB.DOM.welcomeResumeBtn) CB.DOM.welcomeResumeBtn.style.display = 'none';
    }

    if (CB.DOM.drawBtn) CB.DOM.drawBtn.style.display = CB.S.gameMode === 'pvp' ? 'block' : 'none';
    if (CB.DOM.pauseBtn) CB.DOM.pauseBtn.style.display = 'block';
    if (CB.DOM.resignBtn) {
      CB.DOM.resignBtn.style.display = 'block';
      CB.DOM.resignBtn.hidden = false;
    }

    updatePlayerNames(data);
    if (CB.updateTurn) CB.updateTurn();
    if (CB.updateMoves) CB.updateMoves(data.move_history);
    if (CB.updateCaptured) CB.updateCaptured(data.captured_pieces);

    if (CB.buildBoard) CB.buildBoard();
    if (CB.renderClocks) CB.renderClocks();
    if (CB.updatePauseUI) CB.updatePauseUI();
    if (CB.startTimer) CB.startTimer();

    if (data.game_status === 'check') {
      if (CB.applyCheckHighlight) CB.applyCheckHighlight();
    } else {
      if (CB.highlightCheck) CB.highlightCheck();
    }

    if (data.game_status && data.game_status !== 'active' && data.game_status !== 'ok') {
      if (CB.handleGameStatus) CB.handleGameStatus(data.game_status, data.draw_reason);
    }
    if (CB.DOM.welcomeOverlay && !CB.DOM.welcomeOverlay.classList.contains('active')) {
      if (CB.queueAIMoveIfNeeded) CB.queueAIMoveIfNeeded();
    }

    if (data.day_streak !== undefined && typeof document !== 'undefined') {
      const streakCounter = document.getElementById("streak-counter");
      const streakCount = document.getElementById("streak-count");
      if (streakCounter && streakCount) {
        streakCount.textContent = data.day_streak;
        streakCounter.style.display = "block";
      }
    }
  }

  CB.runStartCountdown = runStartCountdown;
  CB.toggleBoardOrientation = toggleBoardOrientation;
  CB.pauseGame = pauseGame;
  CB.resumeGame = resumeGame;
  CB.updatePlayerNames = updatePlayerNames;
  CB.startNewGame = startNewGame;
  CB.loadGame = loadGame;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      runStartCountdown: runStartCountdown,
      toggleBoardOrientation: toggleBoardOrientation,
      pauseGame: pauseGame,
      resumeGame: resumeGame,
      updatePlayerNames: updatePlayerNames,
      startNewGame: startNewGame,
      loadGame: loadGame
    };
  }
})();
