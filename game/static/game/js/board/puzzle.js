/**
 * board/puzzle.js — Daily puzzle logic, hints, and streak tracking
 *
 * Extracted from board.js: getPuzzleStreak, savePuzzleStreak, getLocalDateString,
 * updatePuzzleStreak, updateStreakDisplay, clearPuzzleHints, showPuzzleHint,
 * startDailyPuzzle.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  function getPuzzleStreak() {
    try {
      if (typeof localStorage === 'undefined') {
        return { streak: 0, lastCompleted: null, longestStreak: 0 };
      }
      return JSON.parse(
        localStorage.getItem("dailyPuzzleStreak")
      ) || {
        streak: 0,
        lastCompleted: null,
        longestStreak: 0
      };
    } catch (error) {
      console.error("Failed to load puzzle streak:", error);
      return {
        streak: 0,
        lastCompleted: null,
        longestStreak: 0
      };
    }
  }

  function savePuzzleStreak(data) {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem("dailyPuzzleStreak", JSON.stringify(data));
      }
    } catch (error) {
      console.error("Failed to save puzzle streak:", error);
    }
  }

  function getLocalDateString() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function updatePuzzleStreak() {
    const today = new Date();
    const todayStr = getLocalDateString();
    const streakData = getPuzzleStreak();

    if (streakData.lastCompleted === todayStr) {
      return streakData.streak;
    }

    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const yesterdayStr =
      `${yesterday.getFullYear()}-${String(
        yesterday.getMonth() + 1
      ).padStart(2, "0")}-${String(
        yesterday.getDate()
      ).padStart(2, "0")}`;

    if (streakData.lastCompleted === yesterdayStr) {
      streakData.streak++;
    } else {
      streakData.streak = 1;
    }

    streakData.lastCompleted = todayStr;

    if (streakData.streak > streakData.longestStreak) {
      streakData.longestStreak = streakData.streak;
    }

    savePuzzleStreak(streakData);
    return streakData.streak;
  }

  function updateStreakDisplay() {
    if (typeof document === 'undefined') return;
    const streakData = getPuzzleStreak();
    const streakEl = document.getElementById("streak-count");
    if (streakEl) {
      streakEl.textContent = streakData.streak;
    }
  }

  function clearPuzzleHints() {
    CB.S.hintLevel = 0;
    if (typeof document === 'undefined') return;
    document.querySelectorAll(".square").forEach(square => {
      square.classList.remove("hint-source");
      square.classList.remove("hint-target");
    });
  }

  function showPuzzleHint() {
    if (!CB.S.dailyPuzzleMode || !CB.S.currentPuzzle) return;

    const move = CB.S.currentPuzzle.solution[CB.S.puzzleMoveIndex];
    if (!move) return;

    const fromFile = move.charCodeAt(0) - 97;
    const fromRank = 8 - parseInt(move[1], 10);
    const toFile = move.charCodeAt(2) - 97;
    const toRank = 8 - parseInt(move[3], 10);

    clearPuzzleHints();
    const sourceSq = CB.sq ? CB.sq(fromRank, fromFile) : null;
    const targetSq = CB.sq ? CB.sq(toRank, toFile) : null;

    if (CB.S.hintLevel === 0) {
      if (sourceSq) sourceSq.classList.add("hint-source");
      CB.S.hintLevel = 1;
    } else if (CB.S.hintLevel === 1) {
      if (sourceSq) sourceSq.classList.add("hint-source");
      if (targetSq) targetSq.classList.add("hint-target");
      CB.S.hintLevel = 2;
    }
  }

  async function startDailyPuzzle() {
    if (typeof AbortController === 'undefined' || typeof fetch === 'undefined') return;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch('/api/puzzles/daily/', {
        signal: controller.signal
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch daily puzzle: ${response.statusText}`);
      }
      CB.S.currentPuzzle = await response.json();
      if (CB.S.currentPuzzle && CB.S.currentPuzzle.id !== 0) {
        const solResponse = await fetch(`/api/puzzles/${CB.S.currentPuzzle.id}/solution/`);
        if (solResponse.ok) {
          const solData = await solResponse.json();
          CB.S.currentPuzzle.solution = solData.solution;
        } else {
          throw new Error(`Failed to fetch puzzle solution: ${solResponse.statusText}`);
        }
      }
    } catch (error) {
      console.error("Error fetching daily puzzle:", error);
      CB.S.currentPuzzle = {
        id: 0,
        title: "Default Puzzle",
        fen: "6k1/5ppp/8/8/8/8/5PPP/6KQ w - - 0 1",
        solution: ["g2g4"],
        difficulty: "medium"
      };
    } finally {
      clearTimeout(timeoutId);
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
    updateStreakDisplay();

    if (CB.DOM.restartPuzzleBtn) CB.DOM.restartPuzzleBtn.style.display = 'block';
    if (CB.DOM.hintPuzzleBtn) CB.DOM.hintPuzzleBtn.style.display = 'block';

    CB.S.puzzleMoveIndex = 0;
    clearPuzzleHints();

    if (CB.startNewGame) {
      await CB.startNewGame(
        "ai",
        "white",
        CB.S.currentPuzzle.difficulty || "medium",
        CB.S.currentPuzzle.fen,
        null,
        null,
        true
      );
    }
    CB.S.currentPuzzleFen = CB.S.currentPuzzle.fen;
    CB.S.expectedMoveEval = null;
    if (CB.initStockfish) CB.initStockfish();
    if (CB.precalculateExpectedMoveEval) CB.precalculateExpectedMoveEval();
    const today = new Date().toLocaleDateString();
    const streakData = getPuzzleStreak();
    updateStreakDisplay();
    if (CB.showStatus) {
      CB.showStatus(
        `Daily Puzzle Challenge - ${today} | 🔥 Current Streak: ${streakData.streak}`,
        false
      );
    }
  }

  CB.getPuzzleStreak = getPuzzleStreak;
  CB.savePuzzleStreak = savePuzzleStreak;
  CB.getLocalDateString = getLocalDateString;
  CB.updatePuzzleStreak = updatePuzzleStreak;
  CB.updateStreakDisplay = updateStreakDisplay;
  CB.clearPuzzleHints = clearPuzzleHints;
  CB.showPuzzleHint = showPuzzleHint;
  CB.startDailyPuzzle = startDailyPuzzle;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      getPuzzleStreak: getPuzzleStreak,
      savePuzzleStreak: savePuzzleStreak,
      getLocalDateString: getLocalDateString,
      updatePuzzleStreak: updatePuzzleStreak,
      updateStreakDisplay: updateStreakDisplay,
      clearPuzzleHints: clearPuzzleHints,
      showPuzzleHint: showPuzzleHint,
      startDailyPuzzle: startDailyPuzzle
    };
  }
})();
