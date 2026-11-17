(() => {
    'use strict';

    /* ==========================================================
    CONSTANTS & STATE
    ========================================================== */
    const MATERIAL_VALUES = {
        p: 1,
        n: 3,
        b: 3,
        r: 5,
        q: 9,
        k: 0
    };

    // The page sets data-static on <html> to the static prefix, ending in 'game/'.
    const STATIC_BASE = document.documentElement.dataset.static || '/static/game/';

    // staunton is the rendered wooden set (WebP); the other three are flat SVGs.
    // The flip animation's timer (see turnBoard).
    let turnTimer = 0;
    // Where the king beaten by checkmate lies, for as long as that game is
    // on the board (play.css lays it on its side).
    let fallenKing = null;

    const VALID_PIECE_STYLES = ['staunton', 'classic', 'wood', 'outline'];
    const PIECE_EXT = { staunton: 'webp' };
    const PIECE_IMG = {};
    // A piece shown on its own (taken pieces, the promotion choice). The
    // rendered set has its own pictures for that, each piece filling its
    // frame; a flat set uses the same pictures as on the board.
    const PIECE_ICON = {};

    // A style saved by an older version (neo, alpha, cburnett) falls back to staunton.
    function buildPieceImg(style) {
        const targetStyle = VALID_PIECE_STYLES.includes(style) ? style : 'staunton';
        const ext = PIECE_EXT[targetStyle] || 'svg';
        for (const c of ['w', 'b']) {
            for (const t of ['k', 'q', 'r', 'b', 'n', 'p']) {
                PIECE_IMG[c + t] = `${STATIC_BASE}pieces/${targetStyle}/${c}${t}.${ext}`;
                PIECE_ICON[c + t] = targetStyle === 'staunton'
                    ? `${STATIC_BASE}pieces/staunton-single/${c}${t}.webp`
                    : PIECE_IMG[c + t];
            }
        }
        // play.css sizes and stands the pieces differently for each set.
        document.documentElement.dataset.pieceStyle = targetStyle;
    }

    // Initialize piece style on page load
    buildPieceImg(localStorage.getItem('pieceStyle'));

    function updatePieceStyle(style) {
        buildPieceImg(style);
        
        // Re-draw board pieces
        if (typeof syncPieces === 'function') {
            syncPieces();
        }
        
        // Re-draw captured list pieces dynamically
        document.querySelectorAll('.captured-img').forEach(img => {
            const key = img.dataset.piece;
            if (key && PIECE_ICON[key]) {
                img.src = PIECE_ICON[key];
            }
        });
    }

    const PIECE_NAMES = {
        'p': 'Pawn',
        'r': 'Rook',
        'n': 'Knight',
        'b': 'Bishop',
        'q': 'Queen',
        'k': 'King'
    };

    /* ==========================================================
    SESSION SCORE TRACKER (W/L/D — persists via sessionStorage,
    resets automatically when the browser session ends)
    ========================================================== */
    const SESSION_STATS_KEY = 'checkoraSessionStats';

    function loadSessionStats() {
        try {
            const raw = sessionStorage.getItem(SESSION_STATS_KEY);
            if (!raw) return { wins: 0, losses: 0, draws: 0 };
            const parsed = JSON.parse(raw);
            return {
                wins: Number(parsed.wins) || 0,
                losses: Number(parsed.losses) || 0,
                draws: Number(parsed.draws) || 0
            };
        } catch (e) {
            return { wins: 0, losses: 0, draws: 0 };
        }
    }

    function saveSessionStats(stats) {
        try {
            sessionStorage.setItem(SESSION_STATS_KEY, JSON.stringify(stats));
        } catch (e) {
            // sessionStorage unavailable (e.g. private browsing) — fail silently
        }
    }

    function renderSessionTracker(stats) {
        const winsEl = document.getElementById('sessionWins');
        const lossesEl = document.getElementById('sessionLosses');
        const drawsEl = document.getElementById('sessionDraws');
        if (winsEl) winsEl.textContent = stats.wins;
        if (lossesEl) lossesEl.textContent = stats.losses;
        if (drawsEl) drawsEl.textContent = stats.draws;
    }

    function updateSessionTracker() {
        renderSessionTracker(loadSessionStats());
    }

    // outcome: 'victory' | 'defeat' | 'draw'
    function recordGameResult(outcome) {
        const stats = loadSessionStats();
        if (outcome === 'victory') stats.wins += 1;
        else if (outcome === 'defeat') stats.losses += 1;
        else if (outcome === 'draw') stats.draws += 1;
        else return;

        saveSessionStats(stats);
        renderSessionTracker(stats);
    }

    /* ==========================================================
    FIRST-TIME VISITOR ONBOARDING TOUR
    Shown once per browser (persisted via localStorage), then
    never shown again unless local storage is cleared.
    ========================================================== */
    const TOUR_SEEN_KEY = 'checkoraTourSeen';

    const TOUR_STEPS = [
        {
            selector: '#manualMoveInput',
            text: "Type your move here, like \"e2e4\" — or drag a piece on the board."
        },
        {
            selector: '#gameControlsCard',
            text: "These are your game controls — flip the board, offer a draw, or resign anytime."
        },
        {
            selector: '#boardThemeCard',
            text: "Customize your board here — pick a color theme or turn on square coordinates."
        },
        {
            selector: '#sessionScoreTracker',
            text: "This tracks your wins, losses, and draws for this session. Good luck!"
        }
    ];

    let tourStepIndex = 0;
    let tourActiveTarget = null;
    // Set once a step has been on screen. A tour that could show nothing is
    // not marked as seen, so the next visit offers it again.
    let tourStepShown = false;
    // The phone's controls drawer, while the tour is the one holding it open.
    let tourOpenedDrawer = false;
    // The new game's start countdown, held here until the tour closes.
    let afterTour = null;
    // Where the page was scrolled to when the tour opened; null while it is closed.
    let tourStartScroll = null;

    function hasTourAlreadyBeenSeen() {
        try {
            return localStorage.getItem(TOUR_SEEN_KEY) === 'true';
        } catch (e) {
            return true; // if localStorage is unavailable, don't force the tour
        }
    }

    function markTourAsSeen() {
        try {
            localStorage.setItem(TOUR_SEEN_KEY, 'true');
        } catch (e) {
            // ignore (e.g. private browsing)
        }
    }

    let tourHasBeenTriggeredThisPageLoad = false;

    // True until the tour has had its one start on this page load.
    function isTourDue() {
        return !tourHasBeenTriggeredThisPageLoad && !hasTourAlreadyBeenSeen();
    }

    // Call this right after the welcome/setup screen closes, from any
    // game-start path. Safe to call multiple times — only runs once.
    function maybeStartTourAfterWelcomeCloses() {
        if (tourHasBeenTriggeredThisPageLoad) return;
        if (hasTourAlreadyBeenSeen()) return;
        tourHasBeenTriggeredThisPageLoad = true;
        setTimeout(startTour, 400);
    }

    function positionTourTooltip(targetEl) {
        const tooltip = document.getElementById('tourTooltip');
        const rect = targetEl.getBoundingClientRect();
        const tooltipHeight = tooltip.offsetHeight || 120;
        const spacing = 12;

        let top = rect.bottom + spacing;
        // If tooltip would overflow the bottom of the screen, place it above instead
        if (top + tooltipHeight > window.innerHeight) {
            top = rect.top - tooltipHeight - spacing;
        }
        if (top < 8) top = 8;

        let left = rect.left;
        const tooltipWidth = tooltip.offsetWidth || 280;
        if (left + tooltipWidth > window.innerWidth) {
            left = window.innerWidth - tooltipWidth - 16;
        }
        if (left < 8) left = 8;

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
    }

    // Drawn and not hidden. Where it sits is not asked here: showTourStep
    // opens the drawer and scrolls to the target before it calls this.
    function isElementActuallyVisible(el) {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        return getComputedStyle(el).visibility !== 'hidden';
    }

    // On a phone the controls sit in a drawer. A step that points into it
    // opens it, and the next step outside it (or the end of the tour) puts it
    // away. Returns true when the drawer has only just started sliding up.
    function holdTourDrawer(targetEl) {
        const drawer = document.getElementById('mobilePanel');
        if (drawer && targetEl && drawer.contains(targetEl)) {
            const toggle = document.getElementById('mobileControlsToggle');
            // Only a phone shows the bar with the button that opens the drawer.
            if (!toggle || !toggle.offsetParent || drawer.classList.contains('active')) return false;
            toggle.click();
            tourOpenedDrawer = true;
            return true;
        }
        if (tourOpenedDrawer) {
            tourOpenedDrawer = false;
            const close = document.getElementById('mobileControlsClose');
            if (close) close.click();
        }
        return false;
    }

    function showTourStep(index) {
        if (tourActiveTarget) {
            tourActiveTarget.classList.remove('tour-spotlight');
            tourActiveTarget = null;
        }

        if (index >= TOUR_STEPS.length) {
            endTour();
            return;
        }

        const step = TOUR_STEPS[index];
        const targetEl = document.querySelector(step.selector);

        // Bring the target on screen before asking whether it shows: on a
        // phone it is below the board or inside the closed drawer.
        const drawerSliding = holdTourDrawer(targetEl);
        if (targetEl) targetEl.scrollIntoView({ behavior: 'instant', block: 'center' });

        // Skip a step gracefully if that element isn't on the page right now
        if (!targetEl || !isElementActuallyVisible(targetEl)) {
            showTourStep(index + 1);
            return;
        }

        targetEl.classList.add('tour-spotlight');
        tourActiveTarget = targetEl;
        tourStepIndex = index;
        tourStepShown = true;

        document.getElementById('tourStepLabel').textContent =
            `Step ${index + 1} of ${TOUR_STEPS.length}`;
        document.getElementById('tourStepText').textContent = step.text;
        document.getElementById('tourNextBtn').textContent =
            (index === TOUR_STEPS.length - 1) ? 'Finish' : 'Next →';

        // Give the page a moment to settle (longer while the drawer slides up)
        // before positioning the tooltip
        setTimeout(() => {
            if (tourActiveTarget === targetEl) positionTourTooltip(targetEl);
        }, drawerSliding ? 450 : 300);
    }

    let tourClickListenerAttached = false;

    function attachTourClickListener() {
        if (tourClickListenerAttached) return;
        const overlay = document.getElementById('tourOverlay');
        if (!overlay) return;
        tourClickListenerAttached = true;

        // Event delegation: listen on the overlay itself (which never gets
        // replaced), rather than binding directly to the buttons.
        overlay.addEventListener('click', (e) => {
            const target = e.target.closest('#tourSkipBtn, #tourNextBtn');
            if (!target) return;
            e.preventDefault();
            e.stopPropagation();

            if (target.id === 'tourSkipBtn') {
                endTour();
            } else if (target.id === 'tourNextBtn') {
                tourStepIndex += 1;
                showTourStep(tourStepIndex);
            }
        });

        // Keep Tab from leaving the tour dialog while it's open
        overlay.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;
            const focusable = overlay.querySelectorAll('#tourSkipBtn, #tourNextBtn');
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        });
    }

    function startTour() {
        const overlay = document.getElementById('tourOverlay');
        if (!overlay) {
            // No tour on this page; let go of whatever was waiting for it.
            endTour();
            return;
        }
        attachTourClickListener();
        overlay.style.display = 'block';
        tourStartScroll = window.scrollY;
        tourStepIndex = 0;
        showTourStep(tourStepIndex);
        const tooltip = document.getElementById('tourTooltip');
        if (tooltip) tooltip.focus();
    }

    function endTour() {
        if (tourActiveTarget) {
            tourActiveTarget.classList.remove('tour-spotlight');
            tourActiveTarget = null;
        }
        holdTourDrawer(null);
        const overlay = document.getElementById('tourOverlay');
        if (overlay) overlay.style.display = 'none';
        if (tourStepShown) markTourAsSeen();
        // A step may have scrolled the page away from the board.
        if (tourStartScroll !== null && window.scrollY !== tourStartScroll) {
            window.scrollTo({ top: tourStartScroll });
        }
        tourStartScroll = null;

        // The game that was started behind the tour gets its countdown now.
        const next = afterTour;
        afterTour = null;
        if (next) next();
    }

    function initOnboardingTour() {
        attachTourClickListener();

        const welcomeOverlay = document.getElementById('welcomeOverlay');

        // If there's no setup screen blocking the view at all (e.g. resuming
        // an existing game), it's safe to start the tour right away.
        if (!welcomeOverlay || !welcomeOverlay.classList.contains('active')) {
            maybeStartTourAfterWelcomeCloses();
        }
    }

    /* ==========================================================
    GAME COUNTER (Game #N badge — persists via sessionStorage,
    resets automatically when the browser session ends)
    ========================================================== */
    const GAME_COUNTER_KEY = 'checkoraGameCounter';

    function loadGameCounter() {
        try {
            const raw = sessionStorage.getItem(GAME_COUNTER_KEY);
            const n = Number(raw);
            return Number.isFinite(n) && n > 0 ? n : 0;
        } catch (e) {
            return 0;
        }
    }

    function saveGameCounter(count) {
        try {
            sessionStorage.setItem(GAME_COUNTER_KEY, String(count));
        } catch (e) {
            // sessionStorage unavailable (e.g. private browsing) — fail silently
        }
    }

    function renderGameCounter(count) {
        const counterEl = document.getElementById('game-counter');
        if (counterEl) counterEl.textContent = `Game #${count}`;
    }

    function updateGameCounterDisplay() {
        renderGameCounter(loadGameCounter() || 1);
    }

    function incrementGameCounter() {
        const count = loadGameCounter() + 1;
        saveGameCounter(count);
        renderGameCounter(count);
    }

    let board = [];
    let turn = 'white';
    let selected = null;
    let hints = [];
    let lastMove = null;
    // The side to move is in check; refreshHighlights keeps its king marked.
    let inCheck = false;
    let premoveQueue = [];
    let lastPremoveQueueStr = '';
    let highlightedSquare = null;

    let dragging = false;
    let dragSrc = null;

    // Touch drag-and-drop state variables
    let touchStartPos = null;
    let activeTouchPieceClone = null;
    let touchDragSrc = null;
    let touchDragging = false;
    let touchOffset = { x: 0, y: 0 };

    let whiteTime = 0;
    let blackTime = 0;
    let maxWhiteTime = 0;
    let maxBlackTime = 0;
    // Time control of the game on the board. The welcome-screen picker keeps
    // its own pair, so reloading the game state never changes what it starts.
    let selectedMins = 10;
    let selectedIncrement = 0;
    let pickedMins = 10;
    let pickedIncrement = 0;
    let paused = false;
    let timerInterval = null;
    let countdownInterval = null;
    let pauseTimerInterval = null; // Issue #12: drives the "Paused for: MM:SS" overlay counter
    let pauseElapsedSeconds = 0;
    let pauseStartedAt = null; // Date.now() anchor for this client's pause — see PR discussion on cross-client sync
    let pendingPromo = null;
    let blindfoldMode = false;
    let illegalMoveCount = 0;

    let whiteAlertFired = false;
    let blackAlertFired = false;

    let gameStartTime = null;

    let gameMode = 'pvp';
    let dailyPuzzleMode = false;
    let currentPuzzle = null;
    let puzzleMoveIndex = 0;
    let currentPuzzleFen = null;
    let puzzleAnalyzing = false;
    let stockfishWorker = null;
    let stockfishEvalSeq = 0;
    let stockfishActiveReject = null;

    let hintLevel = 0;

    let expectedMoveEval = null;
    let evaluationCache = {};
    let currentDifficulty = 'medium';
    let currentWhiteName = 'White';
    let currentBlackName = 'Black';
    // Updates UI to highlight selected game mode button
    function updateModeButtonsUI(mode) {
        const pvpBtn = document.getElementById("newPvPBtn");
        const aiBtn = document.getElementById("newAIBtn");

        if (!pvpBtn || !aiBtn) return;

        pvpBtn.classList.remove("active-mode");
        aiBtn.classList.remove("active-mode");

        if (mode === "pvp") {
            pvpBtn.classList.add("active-mode");
        } else {
            aiBtn.classList.add("active-mode");
        }
    }

    // =============================================
    // Daily Puzzle 
    // =============================================
    // Daily puzzles are fetched dynamically from the database.


    // =============================================
    // Daily Puzzle Streak
    // =============================================

    function getPuzzleStreak() {
        try {
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
            localStorage.setItem(
                "dailyPuzzleStreak",
                JSON.stringify(data)
            );
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

        if (
            streakData.streak >
            streakData.longestStreak
        ) {
            streakData.longestStreak =
                streakData.streak;
        }

        savePuzzleStreak(streakData);

        return streakData.streak;
    }
    // The puzzle streak to show: the server's for a signed-in player once it
    // has told us, the one kept in localStorage for guests.
    function shownPuzzleStreak() {
        if (serverPuzzleStreak) return serverPuzzleStreak;
        const local = getPuzzleStreak();
        return { streak: local.streak, longest: local.longestStreak };
    }

    // #streak-count is the account's day streak (loadGame fills it); the
    // puzzle streak is a different number and has its own element.
    function updateStreakDisplay() {
        const streakEl = document.getElementById("puzzle-streak-count");
        if (streakEl) {
            streakEl.textContent = shownPuzzleStreak().streak;
        }
    }

    async function refreshPuzzleStreak() {
        if (!signedIn) return;
        try {
            const stats = await get('/api/puzzle-stats/');
            if (typeof stats.streak === 'number') {
                serverPuzzleStreak = { streak: stats.streak, longest: stats.longest_streak };
            }
        } catch (e) {
            // keep showing the local figure
        }
        updateStreakDisplay();
    }

    // Called once, when the last solution move has been played. Signed-in
    // players get their streak from the server's answer. Guests (401) and a
    // server without this URL fall back to the streak kept in localStorage.
    async function submitPuzzleSolution() {
        if (currentPuzzle && currentPuzzle.id) {
            try {
                const data = await post(`/api/puzzles/${currentPuzzle.id}/solve/`, { moves: puzzleMoves });
                if (data.success) {
                    serverPuzzleStreak = { streak: data.streak, longest: data.longest_streak };
                    return serverPuzzleStreak;
                }
            } catch (e) {
                // an older server answers 404 with a page, not JSON
            }
        }
        const streak = updatePuzzleStreak();
        return { streak, longest: getPuzzleStreak().longestStreak };
    }

    function clearPuzzleHints() {
        hintLevel = 0;

        document.querySelectorAll(".square").forEach(square => {
            square.classList.remove("hint-source");
            square.classList.remove("hint-target");
        });
    }

    function showPuzzleHint() {
        if (!dailyPuzzleMode || !currentPuzzle) return;

        const move = currentPuzzle.solution[puzzleMoveIndex];

        if (!move) return;

        const fromFile = move.charCodeAt(0) - 97;
        const fromRank = 8 - parseInt(move[1], 10);

        const toFile = move.charCodeAt(2) - 97;
        const toRank = 8 - parseInt(move[3], 10);

        // clearPuzzleHints resets the level, so read it first.
        const level = hintLevel;
        clearPuzzleHints();
        const sourceSq = sq(fromRank, fromFile);
        const targetSq = sq(toRank, toFile);

        if (level === 0) {

            if (sourceSq) {
                sourceSq.classList.add("hint-source")
            };

            hintLevel = 1;

        } else {

            if (sourceSq) {
                sourceSq.classList.add("hint-source");
            }

            if (targetSq) {
                targetSq.classList.add("hint-target");
            }

            hintLevel = 2;
        }
    }

    // getCurrentWeeklyPuzzle is retired; puzzles are fetched dynamically.

    function initStockfish() {
        if (!stockfishWorker) {
            stockfishWorker = new Worker(`${STATIC_BASE}js/stockfish.js`);
            stockfishWorker.postMessage('setoption name Hash value 16');
            stockfishWorker.postMessage('setoption name Contempt value 0');
        }
    }

    function getStockfishEval(fen) {
        if (evaluationCache[fen]) {
            return Promise.resolve(evaluationCache[fen]);
        }

        // Cancel previous request if one is active to avoid leaks and settle the promise
        if (stockfishActiveReject) {
            try {
                stockfishActiveReject(new Error("Evaluation superseded"));
            } catch (e) {
                console.error("Error settling superseded evaluation:", e);
            }
            stockfishActiveReject = null;
        }

        // Stop the current computation of the worker immediately
        if (stockfishWorker) {
            stockfishWorker.postMessage('stop');
        }

        stockfishEvalSeq++;
        const currentEvalId = stockfishEvalSeq;

        return new Promise((resolve, reject) => {
            stockfishActiveReject = reject;
            initStockfish();

            const activeWorker = stockfishWorker;
            let scoreType = 'cp';
            let scoreValue = 0;

            const onMessage = (e) => {
                const line = e.data;
                const match = line.match(/score (cp|mate) (-?\d+)/);
                if (match) {
                    scoreType = match[1];
                    scoreValue = parseInt(match[2], 10);
                }

                if (line.startsWith('bestmove')) {
                    if (activeWorker) {
                        activeWorker.removeEventListener('message', onMessage);
                    }
                    if (currentEvalId === stockfishEvalSeq) {
                        stockfishActiveReject = null;
                        const result = { type: scoreType, value: scoreValue };
                        evaluationCache[fen] = result;
                        resolve(result);
                    } else {
                        reject(new Error("Evaluation superseded"));
                    }
                }
            };

            if (activeWorker) {
                activeWorker.addEventListener('message', onMessage);
                activeWorker.postMessage('ucinewgame');
                activeWorker.postMessage(`position fen ${fen}`);
                activeWorker.postMessage('go depth 6 movetime 100');
            } else {
                reject(new Error("Worker not initialized"));
            }
        });
    }

    function getPlayerScore(evalResult) {
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

    function updateEvalBarVisibility() {
        if (!evalBarContainer) return;
        const isPuzzle = dailyPuzzleMode;
        const show = (gameMode === 'ai' || replayMode) && !isPuzzle;
        if (show) {
            document.documentElement.classList.add('has-eval-bar');
            if (flipped) {
                evalBarContainer.classList.add('flipped');
            } else {
                evalBarContainer.classList.remove('flipped');
            }
        } else {
            document.documentElement.classList.remove('has-eval-bar');
        }
    }

    function updateEvalBar(evalResult, fen) {
        if (!evalBarWhite || !evalBarScore) return;
        let percentage = 50;
        let displayLabel = '0.0';
        if (evalResult) {
            const type = evalResult.type;
            const value = evalResult.value;
            const sideToMove = fen ? fen.split(' ')[1] : 'w';
            if (type === 'mate') {
                let isWhiteMate = false;
                if (evalResult.absolute) {
                    isWhiteMate = value > 0;
                } else {
                    if (sideToMove === 'w') {
                        isWhiteMate = value > 0;
                    } else {
                        isWhiteMate = value < 0;
                    }
                }
                displayLabel = evalResult.absolute ? 'M' : `M${Math.abs(value)}`;
                percentage = isWhiteMate ? 100 : 0;
            } else {
                let cp = value;
                if (!evalResult.absolute && sideToMove === 'b') {
                    cp = -cp;
                }
                const rawScore = cp / 100;
                displayLabel = (rawScore >= 0 ? '+' : '') + rawScore.toFixed(1);
                const val = 2 / (1 + Math.exp(-0.4 * rawScore)) - 1;
                percentage = 50 + 50 * val;
            }
        }
        evalBarWhite.style.height = `${percentage}%`;
        evalBarScore.textContent = displayLabel;
        const isWhiteAdvantage = percentage >= 50;
        evalBarScore.style.top = '';
        evalBarScore.style.bottom = '';
        if (!flipped) {
            if (isWhiteAdvantage) {
                evalBarScore.style.bottom = '8px';
                evalBarScore.style.color = '#1a1a2e';
            } else {
                evalBarScore.style.top = '8px';
                evalBarScore.style.color = '#ffffff';
            }
        } else {
            if (isWhiteAdvantage) {
                evalBarScore.style.top = '8px';
                evalBarScore.style.color = '#1a1a2e';
            } else {
                evalBarScore.style.bottom = '8px';
                evalBarScore.style.color = '#ffffff';
            }
        }
    }

    async function triggerPositionEvaluation() {
        if (!evalBarContainer || !document.documentElement.classList.contains('has-eval-bar')) {
            return;
        }
        const currentFen = liveFen;
        try {
            const result = await getStockfishEval(currentFen);
            if (liveFen === currentFen) {
                updateEvalBar(result, currentFen);
            }
        } catch (e) {
            console.error("Evaluation error:", e);
        }
    }

    async function precalculateExpectedMoveEval() {
        if (!currentPuzzle) return;
        const expectedMove = currentPuzzle.solution[puzzleMoveIndex];
        if (!expectedMove) return;
        try {
            if (!window.Chess) return;
            const chess = new window.Chess(currentPuzzleFen);
            const from = expectedMove.substring(0, 2);
            const to = expectedMove.substring(2, 4);
            const promo = expectedMove.length > 4 ? expectedMove.charAt(4) : undefined;
            chess.move({ from, to, promotion: promo });
            const expectedFen = chess.fen();
            expectedMoveEval = await getStockfishEval(expectedFen);
        } catch (e) {
            console.error("Error precalculating expected move eval:", e);
        }
    }

    async function validateMoveWithStockfish(previousFen, playedFen, expectedMove) {
        try {
            let expectedEval = expectedMoveEval;
            if (!expectedEval) {
                if (!window.Chess) {
                    console.error("Chess.js not loaded");
                    return false;
                }
                const chess = new window.Chess(previousFen);
                const from = expectedMove.substring(0, 2);
                const to = expectedMove.substring(2, 4);
                const promo = expectedMove.length > 4 ? expectedMove.charAt(4) : undefined;
                chess.move({ from, to, promotion: promo });
                const expectedFen = chess.fen();
                expectedEval = await getStockfishEval(expectedFen);
            }

            const playedEval = await getStockfishEval(playedFen);

            const valExpected = getPlayerScore(expectedEval);
            const valPlayed = getPlayerScore(playedEval);

            const isCorrect = (valPlayed >= 9000) ||
                (valPlayed >= valExpected - 50) ||
                (valPlayed >= 300 && valExpected >= 300);

            return isCorrect;
        } catch (e) {
            console.error("Stockfish validation error:", e);
            return false;
        }
    }

    function clearEvaluationCache() {
        evaluationCache = {};
    }

    async function startDailyPuzzle() {
        if (!(await confirmForfeit())) return false;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        try {
            const response = await fetch('/api/puzzles/daily/', {
                signal: controller.signal
            });
            if (!response.ok) {
                throw new Error(`Failed to fetch daily puzzle: ${response.statusText}`);
            }
            currentPuzzle = await response.json();
            if (currentPuzzle && currentPuzzle.id !== 0) {
                const solResponse = await fetch(`/api/puzzles/${currentPuzzle.id}/solution/`);
                if (solResponse.ok) {
                    const solData = await solResponse.json();
                    currentPuzzle.solution = solData.solution;
                } else {
                    throw new Error(`Failed to fetch puzzle solution: ${solResponse.statusText}`);
                }
            }
        } catch (error) {
            console.error("Error fetching daily puzzle:", error);
            // Fallback to a default puzzle in case API fails
            currentPuzzle = {
                id: 0,
                title: "Default Puzzle",
                fen: "6k1/5ppp/8/8/8/8/5PPP/6KQ w - - 0 1",
                solution: ["g2g4"],
                difficulty: "medium"
            };
        } finally {
            clearTimeout(timeoutId);
        }

        dailyPuzzleMode = true;
        document.getElementById("whiteClock").style.display = "none";
        document.getElementById("blackClock").style.display = "none";

        const puzzleStreakEl = document.getElementById("puzzle-streak-counter");
        if (puzzleStreakEl) puzzleStreakEl.style.display = "block";
        updateStreakDisplay();

        if (restartPuzzleBtn) {
            restartPuzzleBtn.style.display = 'block';
        }

        if (hintPuzzleBtn) {
            hintPuzzleBtn.style.display = 'block';
        }

        puzzleMoveIndex = 0;
        clearPuzzleHints();

        await startNewGame(
            "ai",
            "white",
            currentPuzzle.difficulty || "medium",
            currentPuzzle.fen,
            null,
            null,
            true
        );
        currentPuzzleFen = currentPuzzle.fen;
        expectedMoveEval = null;
        initStockfish();
        precalculateExpectedMoveEval();
        const today = new Date().toLocaleDateString();
        await refreshPuzzleStreak();
        const streakData = shownPuzzleStreak();
        showStatus(
            `Daily Puzzle Challenge - ${today} | 🔥 Current Streak: ${streakData.streak}`,
            false
        );

    }

    let playerColor = 'white';
    let flipped = false;
    let autoFlip = localStorage.getItem('autoFlip') === 'true';

    const sounds = {
        move: new Audio(`${SOUND_BASE_URL}move.wav`),
        capture: new Audio(`${SOUND_BASE_URL}capture.mp3`),
        check: new Audio(`${SOUND_BASE_URL}check.wav`),
        draw: new Audio(`${SOUND_BASE_URL}draw.mp3`),
        win: new Audio(`${SOUND_BASE_URL}win.mp3`),
        loss: new Audio(`${SOUND_BASE_URL}loss.mp3`),
        gameDraw: new Audio(`${SOUND_BASE_URL}draw_end.mp3`),
        timeout: new Audio(`${SOUND_BASE_URL}timeout.mp3`),
    };

    let soundEnabled = true;
    try {
        const savedSound = localStorage.getItem('chessSoundEnabled');
        if (savedSound !== null) {
            soundEnabled = (savedSound === 'true');
        }
    } catch (e) {
        console.error("Failed to load sound settings", e);
    }

    function validatePlayerNames() {
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


    function playSound(data) {
        if (!soundEnabled || !data?.valid) return;

        let sound = sounds.move;
        if (['checkmate', 'stalemate', 'draw', 'timeout'].includes(data.game_status)) {
            sound = sounds.draw;
        } else if (data.game_status === 'check') {
            sound = sounds.check;
        } else if (data.captured || data.is_capture) {
            sound = sounds.capture;
        }

        sound.currentTime = 0;
        const playback = sound.play();
        if (playback?.catch) playback.catch(() => { });
    }

    function playGameOverSound(reason, resultState) {
        if (!soundEnabled) return;


        let sound = null;

        if (reason === 'stalemate' || reason === 'draw') {
            sound = sounds.gameDraw;
        } else if (reason === 'timeout') {
            sound = sounds.timeout;
        }

        else if (reason === 'checkmate' || reason === 'resign') {
            if (resultState === 'defeat') {
                sound = sounds.loss;
            } else {
                sound = sounds.win;
            }
        }


        if (sound) {
            sound.currentTime = 0;
            sound.play().catch((e) => console.log('Sound play error:', e));
        }
    }


    /* ==========================================================
    DOM REFERENCES
    ========================================================== */
    const shareModal = document.getElementById('shareModal');
    const rulebookModal = document.getElementById('rulebookModal');
    const boardEl = document.getElementById('board');
    const countdownOverlay = document.getElementById('countdownOverlay');
    const countdownNumberEl = document.getElementById('countdownNumber');
    const turnEl = document.getElementById('turnBadge');
    const statusEl = document.getElementById('statusBar');
    const movesEl = document.getElementById('movesList');
    const wCapEl = document.getElementById('whiteCaptured');
    const bCapEl = document.getElementById('blackCaptured');
    const pauseBtn = document.getElementById('pauseBtn');
    const pauseOverlayEl = document.getElementById('pauseOverlay');
    const pauseTimerEl = document.getElementById('pause-timer');
    const flipBtn = document.getElementById('flipBtn');
    const promoOverlay = document.getElementById('promoOverlay');
    const promoChoices = document.getElementById('promoChoices');
    const modeBadge = document.getElementById('modeBadge');
    const copyFenBtn = document.getElementById('copyFenBtn');
    const copyPgnBtn = document.getElementById('copyPgnBtn');
    const evalBarContainer = document.getElementById('evalBarContainer');
    const evalBarWhite = document.getElementById('evalBarWhite');
    const evalBarScore = document.getElementById('evalBarScore');

    const welcomeOverlay = document.getElementById('welcomeOverlay');
    const welcomeResumeBtn = document.getElementById('welcomeResumeBtn');
    const welcomePvPBtn = document.getElementById('welcomePvPBtn');
    const welcomeAIBtn = document.getElementById('welcomeAIBtn');
    const welcomeDailyPuzzleBtn = document.getElementById("welcomeDailyPuzzleBtn");
    const welcomeFenInput = document.getElementById('welcomeFenInput');
    const welcomeFenError = document.getElementById('welcomeFenError');

    const modeSelection = document.getElementById('modeSelection');
    const pveOptions = document.getElementById('pveOptions');
    const startAIBtn = document.getElementById('startAIBtn');
    const backToModes = document.getElementById('backToModes');
    const gameLayout = document.querySelector('.game-layout');
    const nameInputs = document.getElementById('nameInputs');

    const confirmOverlay = document.getElementById('confirmOverlay');
    const confirmTitle = document.getElementById('confirmTitle');
    const confirmMessage = document.getElementById('confirmMessage');
    const confirmYesBtn = document.getElementById('confirmYesBtn');
    const confirmNoBtn = document.getElementById('confirmNoBtn');

    const newPvPBtn = document.getElementById('newPvPBtn');
    const newAIBtn = document.getElementById('newAIBtn');
    const dailyPuzzleBtn = document.getElementById('dailyPuzzleBtn');
    const restartPuzzleBtn = document.getElementById('restartPuzzleBtn');
    const hintPuzzleBtn = document.getElementById('hintPuzzleBtn');
    const newFenBtn = document.getElementById('newFenBtn');

    const fenOverlay = document.getElementById('fenOverlay');
    const fenInput = document.getElementById('fenInput');
    const fenError = document.getElementById('fenError');
    const fenStartBtn = document.getElementById('fenStartBtn');
    const fenCancelBtn = document.getElementById('fenCancelBtn');

    const gameOverOverlay = document.getElementById('gameOverOverlay');
    const gameOverTitle = document.getElementById('gameOverTitle');
    const gameOverMessage = document.getElementById('gameOverMessage');
    const gameOverStartBtn = document.getElementById('gameOverStartBtn');
    const gameOverExitBtn = document.getElementById('gameOverExitBtn');

    const replayControls = document.getElementById('replayControls');
    const firstReplayBtn = document.getElementById('firstReplayBtn');
    const prevReplayBtn = document.getElementById('prevReplayBtn');
    const playReplayBtn = document.getElementById('playReplayBtn');
    const nextReplayBtn = document.getElementById('nextReplayBtn');
    const lastReplayBtn = document.getElementById('lastReplayBtn');
    const replayGameBtn = document.getElementById('replayGameBtn');

    const resignBtn = document.getElementById('resignBtn');
    const drawBtn = document.getElementById('drawBtn');
    const drawOverlay = document.getElementById('drawOverlay');
    const drawMessage = document.getElementById('drawMessage');
    const drawAcceptBtn = document.getElementById('drawAcceptBtn');
    const drawDeclineBtn = document.getElementById('drawDeclineBtn');

    const whiteNameLabel = document.getElementById('whiteNameLabel');
    const blackNameLabel = document.getElementById('blackNameLabel');
    const whiteYouTag = document.getElementById('whiteYouTag');
    const blackYouTag = document.getElementById('blackYouTag');
    const whiteCapturedName = document.getElementById('whiteCapturedName');
    const blackCapturedName = document.getElementById('blackCapturedName');
    const turnBadgeText = document.getElementById('turnBadgeText');
    const a11yAnnouncer = document.getElementById('a11y-announcer');

    function announceMove(msg) {
        if (a11yAnnouncer) {
            a11yAnnouncer.textContent = '';
            setTimeout(() => { a11yAnnouncer.textContent = msg; }, 50);
        }
    }

    let flashTimeout = null;
    function flashBoard() {
        if (boardEl) {
            boardEl.classList.remove('flash-error');
            void boardEl.offsetWidth;
            boardEl.classList.add('flash-error');
            if (flashTimeout) clearTimeout(flashTimeout);
            flashTimeout = setTimeout(() => {
                boardEl.classList.remove('flash-error');
            }, 2000);
        }

        if (blindfoldMode) {
            illegalMoveCount++;
            if (illegalMoveCount >= 3) {
                illegalMoveCount = 0;
                document.body.classList.remove('blindfold-mode');
                setTimeout(() => {
                    if (blindfoldMode) {
                        document.body.classList.add('blindfold-mode');
                    }
                }, 3000);
            }
        }
    }

    let gameOver = false;
    let aiThinking = false;
    let aiRequestSeq = 0; // Sequence token to cancel stale AI responses
    let aiFailures = 0; // AI requests in a row that the server turned down
    const AI_MAX_RETRIES = 3;
    let moveInFlight = false; // a move request is out and not yet answered
    let flagFallPending = false; // the server is being asked about a clock at zero
    // Whether the server counts the game on the board towards rating, and how
    // many half-moves it has. A rated AI game with 5 or more is recorded as a
    // loss when a new game replaces it, so every path that does that asks first.
    let ratedGame = false;
    let halfMoves = 0;
    let forfeitAccepted = false;
    let signedIn = false;
    let puzzleMoves = []; // moves played in the puzzle on the board
    let serverPuzzleStreak = null; // { streak, longest } once the server has said
    let analysisRequestSeq = 0; // Sequence token to cancel stale analysis responses
    const DEFAULT_START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
    // Tracks the full FEN of the current live position so legal moves can be
    // computed on the client without a server round-trip (Issue #1445).
    let liveFen = DEFAULT_START_FEN;
    // Board and PGN as the server last sent them. The stepper shows liveBoard
    // on the latest move, and the PGN export uses livePgn, because once a game
    // is over the server may no longer have it.
    let liveBoard = null;
    let livePgn = '';
    // Square holding the board's single tab stop.
    let boardFocus = { r: 7, c: 4 };
    let boardOrientationSet = false;
    let gameFens = [];
    let stepperIndex = 0;
    let viewingPastState = false;

    let replayMode = false;
    let replayMoves = [];
    let rawAnalysisMoves = [];
    let replayIndex = 0;
    let replayBoard = null;
    let autoReplayInterval = null;
    let isAutoReplaying = false;
    let pgnDownloadTimeout = null;
    let fenCopyTimeout = null;

    // Full FEN the current game started from, saved by startNewGame.
    function startingFen() {
        return localStorage.getItem('checkora_starting_fen') || DEFAULT_START_FEN;
    }
    /* ==========================================================
    CSRF & API HELPERS
    ========================================================== */
    function calculateMaterial(board) {
        let white = 0;
        let black = 0;

        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const piece = board[r][c];
                if (!piece) continue;

                const value = MATERIAL_VALUES[piece.toLowerCase()] || 0;
                if (piece === piece.toUpperCase()) {
                    white += value;
                }
                else {
                    black += value;
                }
            }
        }

        return {
            white,
            black
        };
    }

    function updateMaterialUI(board) {
        const { white, black } = calculateMaterial(board);

        document.getElementById("whiteScore").innerText = white;

        document.getElementById("blackScore").innerText = black;

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

    // post() uses csrf()
    function csrf() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input?.value) {
            return input.value;
        }
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    async function get(url) {
        return (await fetch(url)).json();
    }

    async function post(url, body, extra = {}) {
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf()
            },
            body: JSON.stringify(body),
            ...extra
        });
        const data = await res.json();
        // Callers tell a rejected move from a busy engine by the status.
        if (data && typeof data === 'object') data.httpStatus = res.status;
        return data;
    }
    function isAITurn() {
        return gameMode === 'ai' && turn !== playerColor && !gameOver;
    }

    function queueAIMoveIfNeeded() {
        if (!isAITurn() || aiThinking) return;
        setTimeout(() => {
            if (isAITurn() && !aiThinking && !gameOver) requestAIMove();
        }, 200);
    }

    const pKey = p => p ? ((p === p.toUpperCase() ? 'w' : 'b') + p.toLowerCase()) : null;
    const pColor = p => p ? (p === p.toUpperCase() ? 'white' : 'black') : null;
    const sq = (r, c) => {
        const vr = flipped ? 7 - r : r;
        const vc = flipped ? 7 - c : c;
        return boardEl.children[vr * 8 + vc];
    };

    function getVirtualBoard() {
        let virtualBoard = board.map(row => [...row]);
        for (const pm of premoveQueue) {
            const piece = virtualBoard[pm.from.r][pm.from.c];
            if (piece) {
                const targetEmpty = !virtualBoard[pm.to.r][pm.to.c];
                virtualBoard[pm.to.r][pm.to.c] = piece;
                virtualBoard[pm.from.r][pm.from.c] = null;

                // Virtual castling handling
                if (piece.toLowerCase() === 'k' && Math.abs(pm.to.c - pm.from.c) === 2) {
                    const isKingside = pm.to.c > pm.from.c;
                    const rookColFrom = isKingside ? 7 : 0;
                    const rookColTo = isKingside ? 5 : 3;
                    const rook = virtualBoard[pm.from.r][rookColFrom];
                    if (rook && rook.toLowerCase() === 'r') {
                        virtualBoard[pm.from.r][rookColTo] = rook;
                        virtualBoard[pm.from.r][rookColFrom] = null;
                    }
                }

                // Virtual en passant handling
                if (piece.toLowerCase() === 'p' && pm.from.c !== pm.to.c && targetEmpty) {
                    virtualBoard[pm.from.r][pm.to.c] = null;
                }

                // Virtual pawn promotion (default to Queen for path selection)
                if (piece.toLowerCase() === 'p' && (pm.to.r === 0 || pm.to.r === 7)) {
                    const promotedPiece = piece === 'P' ? 'Q' : 'q';
                    virtualBoard[pm.to.r][pm.to.c] = promotedPiece;
                }
            }
        }
        return virtualBoard;
    }

    function drawPremoveArrows(force = false) {
        let overlay = document.getElementById('premove-svg-overlay');
        const currentStr = JSON.stringify(premoveQueue);

        // Short-circuit to avoid DOM churn if the queue contents are unchanged
        if (!force && overlay && currentStr === lastPremoveQueueStr) {
            return;
        }
        lastPremoveQueueStr = currentStr;

        if (overlay) {
            overlay.remove();
        }

        if (premoveQueue.length === 0) return;

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

        const boardRect = boardEl.getBoundingClientRect();
        if (boardRect.width === 0 || boardRect.height === 0) {
            return;
        }

        premoveQueue.forEach((pm, idx) => {
            const fromSq = sq(pm.from.r, pm.from.c);
            const toSq = sq(pm.to.r, pm.to.c);
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

            // Midpoint step indicator badge for chained and overlapping pre-moves
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

        boardEl.appendChild(overlay);
    }

    function getSquareSize() {
        const s = boardEl.querySelector('.square');
        return s ? s.getBoundingClientRect().width : 60;
    }

    // A move on screen. play.css flies the piece (.moving) using the lengths
    // set here, and this waits until it has landed; the caller then draws the
    // new position, which replaces the piece. Until then the piece stays on
    // the square it landed on.
    async function animateMove(fr, fc, tr, tc) {

        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

        const animations = [];
        const size = getSquareSize();
        const mult = flipped ? -1 : 1;
        const moverDistance = Math.hypot(tr - fr, tc - fc);

        // The move as two lengths in the board's own plane, and its length in
        // squares (play.css times the flight by it). The measured size is the
        // square as drawn on screen, which a tilted board shrinks, so the
        // square's laid-out width is used.
        function setMove(el, dRow, dCol, cell) {
            el.style.setProperty('--move-x', `${dCol * cell * mult}px`);
            el.style.setProperty('--move-y', `${dRow * cell * mult}px`);
            el.style.setProperty('--move-dist', Math.hypot(dRow, dCol).toFixed(2));
        }

        function createAnim(p, dRow, dCol) {
            return new Promise(resolve => {
                const originSquare = p.parentElement;
                const cell = originSquare ? parseFloat(getComputedStyle(originSquare).width) || size : size;

                if (originSquare) {
                    const ghost = p.cloneNode(true);
                    ghost.classList.add('piece-ghost');

                    originSquare.appendChild(ghost);

                    ghost.addEventListener(
                        'animationend',
                        () => ghost.remove(),
                        { once: true }
                    );

                    // A shadow that stays on the board under the piece in flight.
                    const shadow = document.createElement('span');
                    shadow.className = 'move-shadow';
                    setMove(shadow, dRow, dCol, cell);
                    originSquare.appendChild(shadow);
                }

                setMove(p, dRow, dCol, cell);
                p.classList.add('moving');

                // How long the flight takes is up to the stylesheet.
                const seconds = parseFloat(getComputedStyle(p).animationDuration);
                const wait = Number.isFinite(seconds) ? seconds * 1000 : 0;
                let landed = false;
                const onEnd = (event) => {
                    if (landed) return;
                    if (event && (event.target !== p || event.animationName !== 'piece-travel')) return;
                    landed = true;
                    p.removeEventListener('animationend', onEnd);
                    resolve();
                };
                p.addEventListener('animationend', onEnd);
                setTimeout(onEnd, wait + 60);
            });
        }

        // The taken piece is knocked off its square by the one arriving. A
        // copy of it goes into a box of its own on the board, so it can go on
        // falling after the new position is drawn; the box removes itself.
        function knockAway(target, square) {
            const dRow = tr - fr;
            const dCol = tc - fc;
            const length = Math.hypot(dRow, dCol) || 1;
            const debris = document.createElement('div');
            debris.className = 'piece-debris';
            debris.setAttribute('aria-hidden', 'true');
            debris.style.left = `${square.offsetLeft}px`;
            debris.style.top = `${square.offsetTop}px`;
            debris.style.width = `${square.offsetWidth}px`;
            debris.style.height = `${square.offsetHeight}px`;
            debris.style.setProperty('--knock-x', ((dCol * mult) / length).toFixed(3));
            debris.style.setProperty('--knock-y', ((dRow * mult) / length).toFixed(3));
            debris.style.setProperty('--knock-turn', dCol * mult < 0 ? '-1' : '1');
            debris.style.setProperty('--move-dist', moverDistance.toFixed(2));
            const copy = document.createElement('img');
            copy.src = target.src;
            copy.alt = '';
            copy.draggable = false;
            debris.appendChild(copy);
            boardEl.appendChild(debris);
            const clear = () => debris.remove();
            copy.addEventListener('animationend', clear, { once: true });
            setTimeout(clear, 2500);
        }

        const piece = sq(fr, fc).querySelector('.piece');
        if (piece) {
            animations.push(createAnim(piece, tr - fr, tc - fc));

            const pType = board[fr][fc];
            if (pType && pType.toLowerCase() === 'k' && Math.abs(tc - fc) === 2) {
                const isShort = tc > fc;
                const rookFr = fr;
                const rookFc = isShort ? 7 : 0;
                const rookTr = fr;
                const rookTc = isShort ? 5 : 3;
                const rook = sq(rookFr, rookFc).querySelector('.piece');
                if (rook) {
                    animations.push(createAnim(rook, rookTr - rookFr, rookTc - rookFc));
                }
            }
        }

        let capturedSq = sq(tr, tc);
        const mover = board[fr][fc];
        const isEnPassant = piece && mover && mover.toLowerCase() === 'p' && fc !== tc && !board[tr][tc];
        if (isEnPassant) {
            capturedSq = sq(fr, tc);
        }

        const targetPiece = capturedSq.querySelector('.piece');
        if (targetPiece) {
            knockAway(targetPiece, capturedSq);
            targetPiece.classList.add('captured');
        }

        await Promise.all(animations);
    }



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
    const whiteNameInput = document.getElementById('whiteNameInput');
    const blackNameInput = document.getElementById('blackNameInput');

    if (whiteNameInput) {
        whiteNameInput.addEventListener('input', () => {
            whiteNameInput.classList.remove('input-error');
            if (whiteNameInput.value.trim() && blackNameInput?.value.trim()) {
                document.getElementById('nameError').style.display = 'none';
            }
        });
    }
    if (blackNameInput) {
        blackNameInput.addEventListener('input', () => {
            blackNameInput.classList.remove('input-error');
            if (blackNameInput.value.trim() && whiteNameInput?.value.trim()) {
                document.getElementById('nameError').style.display = 'none';
            }
        });
    }
    // Enter in a name field starts the game the visible setup screen offers.
    [whiteNameInput, blackNameInput].forEach(input => {
        if (!input) return;
        input.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            const aiSetup = pveOptions && pveOptions.style.display !== 'none';
            (aiSetup ? startAIBtn : welcomePvPBtn)?.click();
        });
    });
    /* ==========================================================
    LOAD GAME STATE
    ========================================================== */
    async function loadGame() {
        // Move the AI request sequence on, so a request from before this load is ignored.
        // Setting it back to 0 would let the next request reuse a live number.
        aiRequestSeq++;
        analysisRequestSeq++;
        aiThinking = false;
        fallenKing = null;
        premoveQueue = [];
        refreshPremoveHighlight();
        whiteAlertFired = false;
        blackAlertFired = false;

        const urlParams = new URLSearchParams(window.location.search);
        const puzzleId = urlParams.get('puzzle_id');
        if (puzzleId) {
            // Remove the puzzle_id query param from the URL to prevent recursion loop
            const url = new URL(window.location);
            url.searchParams.delete('puzzle_id');
            window.history.replaceState({}, document.title, url.pathname + url.search);

            // The puzzle replaces whatever game the server holds, so look at
            // that game first and ask if leaving it would cost a rated loss.
            const current = await get('/api/state/');
            ratedGame = current.rated === true;
            gameMode = current.mode || 'pvp';
            halfMoves = current.move_history ? current.move_history.length : 0;
            signedIn = current.day_streak !== undefined;
            const startPuzzle = await confirmForfeit();

            try {
                const response = startPuzzle ? await fetch(`/api/puzzles/${puzzleId}/`) : null;
                if (response && response.ok) {
                    currentPuzzle = await response.json();
                    const solResponse = await fetch(`/api/puzzles/${puzzleId}/solution/`);
                    if (solResponse.ok) {
                        const solData = await solResponse.json();
                        currentPuzzle.solution = solData.solution;
                    }
                    dailyPuzzleMode = true;
                    document.getElementById("whiteClock").style.display = "none";
                    document.getElementById("blackClock").style.display = "none";
                    const puzzleStreakEl = document.getElementById("puzzle-streak-counter");
                    if (puzzleStreakEl) puzzleStreakEl.style.display = "block";
                    updateStreakDisplay();
                    if (restartPuzzleBtn) restartPuzzleBtn.style.display = 'block';
                    if (hintPuzzleBtn) hintPuzzleBtn.style.display = 'block';
                    puzzleMoveIndex = 0;
                    clearPuzzleHints();
                    await startNewGame(
                        "ai",
                        "white",
                        currentPuzzle.difficulty || "medium",
                        currentPuzzle.fen,
                        null,
                        null,
                        true
                    );
                    currentPuzzleFen = currentPuzzle.fen;
                    expectedMoveEval = null;
                    initStockfish();
                    precalculateExpectedMoveEval();
                    await refreshPuzzleStreak();
                    const streakData = shownPuzzleStreak();
                    showStatus(
                        `${currentPuzzle.title} | 🔥 Current Streak: ${streakData.streak}`,
                        false
                    );
                    welcomeOverlay.classList.remove('active');
                    maybeStartTourAfterWelcomeCloses();
                    gameLayout.style.visibility = 'visible';
                    return;
                }
            } catch (error) {
                console.error("Error loading puzzle from query params:", error);
            }
        }

        const data = await get('/api/state/');

        // A puzzle's clock is not a time control anyone chose; keep the last game's for a rematch.
        if (data.time_limit !== undefined && !dailyPuzzleMode) {
            selectedMins = data.time_limit / 60;
        }
        if (data.increment !== undefined && !dailyPuzzleMode) {
            selectedIncrement = data.increment;
        }

        board = parseBoard(data.board);
        liveBoard = board;
        if (data.fen) liveFen = data.fen;
        if (data.pgn) livePgn = data.pgn;
        turn = data.current_turn;
        // A reloaded game keeps the status "active"; in_check says the rest.
        inCheck = data.game_status === 'check' || data.in_check === true;
        whiteTime = data.white_time;
        blackTime = data.black_time;
        maxWhiteTime = Math.max(whiteTime || 0, Math.round(selectedMins * 60));
        maxBlackTime = Math.max(blackTime || 0, Math.round(selectedMins * 60));
        paused = data.paused;

        gameMode = data.mode || 'pvp';
        // Sync UI with current game mode
        updateModeButtonsUI(gameMode);
        playerColor = data.player_color || 'white';
        currentDifficulty = data.difficulty || currentDifficulty;
        ratedGame = data.rated === true;
        // Only signed-in players get a day streak in the state.
        signedIn = data.day_streak !== undefined;

        // Orientation is taken from the server once. A reload after a tab
        // switch must not undo a manual flip, and startNewGame sets its own.
        if (!boardOrientationSet) {
            flipped = gameMode === 'ai' && playerColor === 'black';
            boardOrientationSet = true;
        }

        if (modeBadge) {
            modeBadge.textContent = gameMode === 'ai' ? 'VS AI' : 'PVP';
            modeBadge.style.display = 'inline-block';
        }

        const emotePanel = document.getElementById('emotePanel');
        if (emotePanel) {
            emotePanel.style.display = gameMode === 'pvp' ? 'block' : 'none';
        }

        // Show Resume button if we have an ongoing game
        const hasMoves = data.move_history && data.move_history.length > 0;
        const isResumable = hasMoves && data.game_status === 'active';
        if (isResumable) {
            if (welcomeResumeBtn) {
                welcomeResumeBtn.style.display = 'block';
                welcomeResumeBtn.textContent = 'Resume Game';
            }
        } else {
            if (welcomeResumeBtn) welcomeResumeBtn.style.display = 'none';
        }

        if (drawBtn) drawBtn.style.display = gameMode === 'pvp' ? 'block' : 'none';
        if (pauseBtn) pauseBtn.style.display = 'block';
        if (resignBtn) {
            resignBtn.style.display = 'block';
            resignBtn.hidden = false;
        }

        updatePlayerNames(data);
        updateTurn();
        updateOpeningDisplay(data.opening_name);
        updateMoves(data.move_history);
        updateCaptured(data.captured_pieces);

        buildBoard();
        renderClocks();
        updatePauseUI();
        startTimer();
        // fix
        // Removed static styling for AI clock so it displays the countdown timer.

        // Restore check highlight if game was reloaded while in check
        if (inCheck) {
            applyCheckHighlight();
        } else {
            highlightCheck();
        }

        if (data.game_status && data.game_status !== 'active' && data.game_status !== 'ok') {
            handleGameStatus(data.game_status, data.draw_reason, data.winner);
        }
        if (!welcomeOverlay.classList.contains('active')) {
            queueAIMoveIfNeeded();
        }

        if (data.day_streak !== undefined) {
            const streakCounter = document.getElementById("streak-counter");
            const streakCount = document.getElementById("streak-count");
            if (streakCounter && streakCount) {
                streakCount.textContent = data.day_streak;
                streakCounter.style.display = "block";
            }
        }
        triggerPositionEvaluation();
    }

    function updatePlayerNames(data) {
        currentWhiteName = data.white_name || currentWhiteName || 'White';
        currentBlackName = data.black_name || currentBlackName || 'Black';
        let wName = currentWhiteName;
        let bName = currentBlackName;

        if (gameMode === 'ai') {
            const diffLabel = (currentDifficulty || 'medium').toUpperCase();
            const humanName = (playerColor === 'white' ? currentWhiteName : currentBlackName)
                || document.getElementById('whiteNameInput')?.value?.trim()?.slice(0, 17) || 'Player';
            if (playerColor === 'white') {
                wName = humanName;
                bName = `AI (Black)`;
            } else {
                bName = humanName;
                wName = `AI (White)`;
            }

            // Inject difficulty badge after names are set
            setTimeout(() => {
                const aiLabel = playerColor === 'white'
                    ? document.getElementById('blackNameLabel')
                    : document.getElementById('whiteNameLabel');
                if (aiLabel) {
                    aiLabel.innerHTML = '';
                    const textNode = document.createTextNode(`AI (${playerColor === 'white' ? 'BLACK' : 'WHITE'}) `);
                    const badge = document.createElement('span');
                    badge.textContent = diffLabel;
                    // easy, medium or hard: the stylesheet colours the badge by level
                    badge.dataset.difficulty = diffLabel.toLowerCase();
                    badge.setAttribute('aria-label', `AI difficulty: ${diffLabel}`);
                    aiLabel.appendChild(textNode);
                    aiLabel.appendChild(badge);
                }
            }, 0);
        }
        if (whiteNameLabel) whiteNameLabel.textContent = wName.toUpperCase();
        if (blackNameLabel) blackNameLabel.textContent = bName.toUpperCase();
        if (whiteCapturedName) whiteCapturedName.textContent = wName;
        if (blackCapturedName) blackCapturedName.textContent = bName;

        const whiteAvatarEl = document.getElementById('whitePlayerAvatar');
        const blackAvatarEl = document.getElementById('blackPlayerAvatar');
        const whiteCapturedAvatarEl = document.getElementById('whiteCapturedAvatar');
        const blackCapturedAvatarEl = document.getElementById('blackCapturedAvatar');

        if (gameMode === 'ai') {
            if (whiteYouTag) whiteYouTag.style.display = (playerColor === 'white') ? 'inline' : 'none';
            if (blackYouTag) blackYouTag.style.display = (playerColor === 'black') ? 'inline' : 'none';
            if (whiteAvatarEl && window.USER_AVATAR_URL) {
                whiteAvatarEl.src = window.USER_AVATAR_URL;
                whiteAvatarEl.style.display = (playerColor === 'white') ? 'inline-block' : 'none';
                if (whiteCapturedAvatarEl) {
                    whiteCapturedAvatarEl.src = window.USER_AVATAR_URL;
                    whiteCapturedAvatarEl.style.display = (playerColor === 'white') ? 'inline-block' : 'none';
                }
            }
            if (blackAvatarEl && window.USER_AVATAR_URL) {
                blackAvatarEl.src = window.USER_AVATAR_URL;
                blackAvatarEl.style.display = (playerColor === 'black') ? 'inline-block' : 'none';
                if (blackCapturedAvatarEl) {
                    blackCapturedAvatarEl.src = window.USER_AVATAR_URL;
                    blackCapturedAvatarEl.style.display = (playerColor === 'black') ? 'inline-block' : 'none';
                }
            }
        } else {
            if (whiteYouTag) whiteYouTag.style.display = 'none';
            if (blackYouTag) blackYouTag.style.display = 'none';
            if (whiteAvatarEl) whiteAvatarEl.style.display = 'none';
            if (blackAvatarEl) blackAvatarEl.style.display = 'none';
            if (whiteCapturedAvatarEl) whiteCapturedAvatarEl.style.display = 'none';
            if (blackCapturedAvatarEl) blackCapturedAvatarEl.style.display = 'none';
        }
    }


    /* ==========================================================
    BOARD RENDERING
    ========================================================== */
    function buildBoard() {
        clearTimeout(turnTimer);
        boardEl.classList.remove('turning');
        updateEvalBarVisibility();
        const bc = document.querySelector('.board-container');
        if (bc) bc.classList.toggle('flipped', flipped);
        // The squares are about to be replaced; note keyboard focus so it can be put back.
        const hadFocus = boardEl.contains(document.activeElement);
        // Only the squares go. A piece still falling after a capture stays,
        // and the new squares go in front of it so they keep their order.
        boardEl.querySelectorAll(':scope > .square').forEach(square => square.remove());
        const keptAfterSquares = boardEl.firstElementChild;
        for (let vr = 0; vr < 8; vr++) {
            for (let vc = 0; vc < 8; vc++) {
                const r = flipped ? 7 - vr : vr;
                const c = flipped ? 7 - vc : vc;
                const d = document.createElement('div');
                d.className = 'square ' + ((vr + vc) % 2 ? 'dark' : 'light');
                d.dataset.r = r;
                d.dataset.c = c;
                d.onclick = () => onClick(r, c);
                d.oncontextmenu = (e) => {
                    e.preventDefault();
                    toggleSquareHighlight(r, c);
                };
                d.ondragover = e => e.preventDefault();
                d.ondrop = e => onDrop(e, r, c);

                // ADD THESE:
                d.draggable = true;
                d.ondragstart = e => {
                    const isPremoveMode = gameMode === 'ai' && turn !== playerColor;
                    const vBoard = isPremoveMode ? getVirtualBoard() : board;
                    const piece = vBoard[r][c];
                    if (!piece) {
                        if (blindfoldMode) {
                            showStatus('No piece there', true);
                            flashBoard();
                        }
                        return e.preventDefault();
                    }
                    if (paused || gameOver || viewingPastState) return e.preventDefault();

                    const isPremovedDrag = gameMode === 'ai' && turn !== playerColor && pColor(piece) === playerColor;

                    // If it's the AI's turn, only allow dragging if it's a valid premove
                    if (gameMode === 'ai' && turn !== playerColor && !isPremovedDrag) {
                        return e.preventDefault();
                    }

                    // For all other normal moves, you can only drag your own pieces on your turn
                    if (!isPremovedDrag && pColor(piece) !== turn) {
                        return e.preventDefault();
                    }

                    if (e.dataTransfer) {
                        e.dataTransfer.setData('text/plain', 'piece-move');
                        e.dataTransfer.effectAllowed = 'move';
                    }

                    const pieceImg = d.querySelector('.piece');
                    if (pieceImg) e.dataTransfer.setDragImage(pieceImg, pieceImg.offsetWidth / 2, pieceImg.offsetHeight / 2);

                    dragging = true;
                    dragSrc = { r, c };
                    setTimeout(() => selectPiece(r, c), 10);
                };

                d.ondragend = () => {
                    dragging = false;
                    dragSrc = null;
                };

                // One tab stop for the whole board; the arrow keys move between squares.
                d.setAttribute('tabindex', (r === boardFocus.r && c === boardFocus.c) ? '0' : '-1');
                d.onfocus = () => moveBoardFocus(r, c);
                d.setAttribute('role', 'gridcell');
                d.setAttribute('data-row', r);
                d.setAttribute('data-col', c);
                d.setAttribute('aria-label', getSquareLabel(r, c));
                d.onkeydown = (e) => handleSquareKeydown(e, r, c);

                boardEl.insertBefore(d, keptAfterSquares);
            }
        }
        syncPieces();
        updateLabels();
        if (hadFocus) sq(boardFocus.r, boardFocus.c).focus();
    }

    function moveBoardFocus(r, c) {
        if (boardFocus.r === r && boardFocus.c === c) return;
        sq(boardFocus.r, boardFocus.c).setAttribute('tabindex', '-1');
        sq(r, c).setAttribute('tabindex', '0');
        boardFocus = { r, c };
    }

    function updateLabels() {
        const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];
        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
        if (flipped) {
            ranks.reverse();
            files.reverse();
        }
        const rLabels = document.getElementById('ranksLabels');
        const fLabels = document.getElementById('filesLabels');
        if (rLabels) rLabels.innerHTML = ranks.map(r => `<span>${r}</span>`).join('');
        if (fLabels) fLabels.innerHTML = files.map(f => `<span>${f}</span>`).join('');
    }

    function syncPieces() {
        for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
            const el = sq(r, c);
            el.innerHTML = '';
            const p = board[r][c];
            if (!p) continue;

            const img = document.createElement('img');
            img.src = PIECE_IMG[pKey(p)];
            img.className = 'piece';
            //Set to false, as the parent div now handles dragging
            img.draggable = false;
            // Keep this so drops work smoothly on occupied squares
            img.ondragover = e => e.preventDefault();
            img.onerror = onPieceImageError;
            el.appendChild(img);
        }
        refreshHighlights();
        markPlayable();
        updateMaterialUI(board);
    }

    function markPlayable() {
        boardEl.querySelectorAll('.piece').forEach(img => {
            const el = img.closest('.square');
            const r = parseInt(el.dataset.r);
            const c = parseInt(el.dataset.c);
            const p = board[r][c];
            // Against the engine only the player's own pieces can be picked up
            // (on the engine's turn too, to queue a premove); the engine's never.
            const isPlayable = !!p && pColor(p) === (gameMode === 'ai' ? playerColor : turn);
            img.classList.toggle('playable', isPlayable);
        });
    }

    function refreshHighlights() {
        const checked = checkedSquare();
        const fallen = fallenKing && stepperIndex >= gameFens.length - 1 ? sq(fallenKing.r, fallenKing.c) : null;
        boardEl.querySelectorAll('.square').forEach(el => {
            el.classList.remove('selected', 'last-move', 'custom-highlight');
            el.classList.toggle('in-check', el === checked);
            el.classList.toggle('king-fallen', el === fallen);
            el.querySelectorAll('.move-dot, .capture-ring').forEach(n => n.remove());
        });

        if (lastMove) {
            sq(lastMove.from[0], lastMove.from[1]).classList.add('last-move');
            sq(lastMove.to[0], lastMove.to[1]).classList.add('last-move');
        }
        if (highlightedSquare) {
            sq(highlightedSquare.r, highlightedSquare.c)
                .classList.add('custom-highlight');
        }
        if (selected) {
            sq(selected.r, selected.c).classList.add('selected');
            hints.forEach(h => {
                const el = sq(h.row, h.col);
                const d = document.createElement('div');
                d.className = h.is_capture ? 'capture-ring' : 'move-dot';
                // How far from the piece, so the marks come up in a ripple outwards.
                d.style.setProperty('--n', Math.max(Math.abs(h.row - selected.r), Math.abs(h.col - selected.c)) - 1);
                el.appendChild(d);
            });
        }
        refreshPremoveHighlight();
    }

    function refreshPremoveHighlight() {
        boardEl.querySelectorAll('.square').forEach(el => {
            el.classList.remove('premove');
        });

        premoveQueue.forEach(pm => {
            const fromSq = sq(pm.from.r, pm.from.c);
            const toSq = sq(pm.to.r, pm.to.c);
            if (fromSq) fromSq.classList.add('premove');
            if (toSq) toSq.classList.add('premove');
        });

        drawPremoveArrows();
    }

    function highlightCheck() {
        inCheck = false;
        boardEl.querySelectorAll('.square').forEach(el => {
            el.classList.remove('in-check');
        });
    }

    function applyCheckHighlight() {
        highlightCheck();
        inCheck = true;
        const checked = checkedSquare();
        if (checked) checked.classList.add('in-check');
    }

    // The square of the king in check, for as long as the board shows the
    // live position. An earlier move or a replay is not marked.
    function checkedSquare() {
        if (!inCheck || replayMode || stepperIndex < gameFens.length - 1) return null;
        // Use turn to find the king that's in check
        // After AI moves, turn has switched back to the player being checked
        const kingPiece = turn === 'white' ? 'K' : 'k';
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                if (board[r][c] === kingPiece) return sq(r, c);
            }
        }
        return null;
    }

    // converts row/col to chess notation e.g. row=0,col=0 → "a8"
    function getSquareLabel(row, col) {
        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
        const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];
        return files[col] + ranks[row];
    }

    // Arrow keys to move focus, Enter/Space to click, Escape to cancel
    function handleSquareKeydown(e, row, col) {
        let newRow = row;
        let newCol = col;

        // Rows and columns count from White's side, so a flipped board reverses the arrows.
        const step = flipped ? -1 : 1;

        switch (e.key) {
            case 'ArrowUp': e.preventDefault(); newRow = row - step; break;
            case 'ArrowDown': e.preventDefault(); newRow = row + step; break;
            case 'ArrowLeft': e.preventDefault(); newCol = col - step; break;
            case 'ArrowRight': e.preventDefault(); newCol = col + step; break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                onClick(row, col);
                return;
            case 'Escape':
                e.preventDefault();
                deselect();
                return;
            default:
                return;
        }
        // clamp within board
        newRow = Math.max(0, Math.min(7, newRow));
        newCol = Math.max(0, Math.min(7, newCol));
        const target = boardEl.querySelector(
            `[data-row="${newRow}"][data-col="${newCol}"]`
        );
        if (target) target.focus();
    }

    /* ==========================================================
    SELECTION & MOVES
    ========================================================== */

    /**
     * Convert a chess.js square label (e.g. "e4") to board array indices.
     * board[0][0] == a8, board[7][7] == h1.
     */
    function squareLabelToRowCol(square) {
        const file = square.charCodeAt(0) - 97; // 'a'=0 … 'h'=7
        const rank = parseInt(square[1], 10);    // 1–8
        const row  = 8 - rank;                   // rank 8 → row 0
        return { row, col: file };
    }

    /**
     * Compute legal moves for the piece at (r, c) using the chess.js library
     * that is already loaded on the page.  Returns an array of
     * { row, col, is_capture, is_promotion } objects — the same shape that
     * /api/valid-moves/ returns — so the rest of the UI is unchanged.
     *
     * Returns null if chess.js is not available so callers can fall back.
     */
    function computeLegalMovesClient(r, c) {
        if (!window.Chess) return null;
        try {
            const chess = new window.Chess(liveFen);
            const fromSquare = getSquareLabel(r, c); // e.g. "e2"
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
                        is_capture:   m.captured !== undefined,
                        is_promotion: m.promotion !== undefined,
                    };
                });
        } catch (e) {
            // Unexpected chess.js error — caller will fall back to the API.
            console.warn('computeLegalMovesClient error:', e);
            return null;
        }
    }

    async function selectPiece(r, c) {
        const isPremoveMode = gameMode === 'ai' && turn !== playerColor;
        const vBoard = isPremoveMode ? getVirtualBoard() : board;
        const p = vBoard[r][c];

        if (!p || paused || gameOver) return;

        selected = { r, c };

        // PREMOVE MODE DURING AI TURN
        if (
            gameMode === 'ai' &&
            turn !== playerColor &&
            pColor(p) === playerColor
        ) {
            hints = [];

            refreshHighlights();
            return;
        }

        // NORMAL MOVE LOGIC — try client-side first (Issue #1445)
        const clientMoves = computeLegalMovesClient(r, c);
        if (clientMoves !== null) {
            // Instant: no network request needed.
            hints = clientMoves;
            refreshHighlights();
            return;
        }

        // Fallback: chess.js unavailable — ask the server.
        const data = await get(`/api/valid-moves/?row=${r}&col=${c}`);
        hints = data.valid_moves || [];
        refreshHighlights();
    }
    function toggleSquareHighlight(r, c) {
        if (highlightedSquare) {
            sq(highlightedSquare.r, highlightedSquare.c)
                .classList.remove('custom-highlight');
        }

        if (
            highlightedSquare &&
            highlightedSquare.r === r &&
            highlightedSquare.c === c
        ) {
            highlightedSquare = null;
        } else {
            highlightedSquare = { r, c };
            sq(r, c).classList.add('custom-highlight');
        }
    }
    function deselect() {
        selected = null;
        hints = [];
        refreshHighlights();
    }

    function isPromotionMove(fr, fc, tr) {
        const p = board[fr][fc];
        if (!p) return false;
        return (p === 'P' && tr === 0) || (p === 'p' && tr === 7);
    }

    // False only when chess.js is loaded and says the piece cannot go there.
    function isLegalTarget(fr, fc, tr, tc) {
        const legal = computeLegalMovesClient(fr, fc);
        return legal === null || legal.some(m => m.row === tr && m.col === tc);
    }

    function showPromoModal(color) {
        const prefix = color === 'white' ? 'w' : 'b';
        const pieces = [
            { key: 'q', label: 'Queen' },
            { key: 'r', label: 'Rook' },
            { key: 'b', label: 'Bishop' },
            { key: 'n', label: 'Knight' },
        ];
        promoChoices.innerHTML = '';
        pieces.forEach(({ key, label }) => {
            const btn = document.createElement('button');
            btn.className = 'promo-btn';
            btn.setAttribute('aria-label', `${label} (${key})`);
            
            const img = document.createElement('img');
            img.src = PIECE_ICON[prefix + key];
            img.alt = '';
            img.setAttribute('aria-hidden', 'true');
            btn.appendChild(img);
            
            const labelSpan = document.createElement('span');
            labelSpan.className = 'promo-label';
            labelSpan.setAttribute('aria-hidden', 'true');
            const keySpan = document.createElement('span');
            keySpan.className = 'promo-key';
            keySpan.textContent = `(${key})`;
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'promo-text';
            nameSpan.textContent = ` ${label}`;
            
            labelSpan.appendChild(keySpan);
            labelSpan.appendChild(nameSpan);
            btn.appendChild(labelSpan);
            
            btn.onclick = () => onPromoChoice(key);
            promoChoices.appendChild(btn);
        });
        promoOverlay.classList.add('active');
    }

    function hidePromoModal() {
        promoOverlay.classList.remove('active');
        pendingPromo = null;
    }

    async function onPromoChoice(choice) {
        if (!pendingPromo) return;
        const { fr, fc, tr, tc } = pendingPromo;
        hidePromoModal();
        await executeMove(fr, fc, tr, tc, choice, true);
    }

    // Back out of a promotion: nothing has been sent yet, the pawn stays where it was.
    function cancelPromotion() {
        if (!pendingPromo) return;
        hidePromoModal();
        deselect();
        // The pawn was flown to the last rank before the question; draw it
        // back on its own square.
        syncPieces();
    }

    async function tryMove(fr, fc, tr, tc) {
        if (paused || gameOver) return;

        const isPremoveMode = gameMode === 'ai' && turn !== playerColor;
        const vBoard = isPremoveMode ? getVirtualBoard() : board;
        const p = vBoard[fr][fc];
        if (!p) return;

        // PREMOVE DURING AI TURN
        if (
            gameMode === 'ai' &&
            pColor(p) === playerColor &&
            turn !== playerColor
        ) {
            premoveQueue.push({
                from: { r: fr, c: fc },
                to: { r: tr, c: tc }
            });

            refreshPremoveHighlight();
            showStatus("Premove queued", false);

            selected = null;
            hints = [];
            refreshHighlights();

            return;
        }

        // NORMAL MOVE VALIDATION
        if (pColor(p) !== turn) {
            deselect();
            return;
        }

        if (fr === tr && fc === tc) {
            deselect();
            return;
        }

        // Ask for a piece only when the pawn can really get there. Anything else
        // goes to the server as a plain move and comes back with its message.
        if (isPromotionMove(fr, fc, tr) && isLegalTarget(fr, fc, tr, tc)) {
            await animateMove(fr, fc, tr, tc);

            pendingPromo = { fr, fc, tr, tc };

            const color = pColor(p);
            showPromoModal(color);

            return;
        }

        await executeMove(fr, fc, tr, tc, null);
    } let reconnecting = false;
    async function handleReconnect() {
        if (reconnecting) return;
        reconnecting = true;
        showStatus('Reconnecting...', false);
        let retries = 0;
        let success = false;
        while (retries < 3 && !success) {
            try {
                await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, retries)));
                await loadGame();
                success = true;
            } catch (err) {
                retries++;
            }
        }

        if (success) {
            showStatus('Connection restored', false);
            setTimeout(() => {
                showStatus('', false);
            }, 2000);
        } else {
            showStatus('Unable to reconnect. Please refresh.', true);
        }
        reconnecting = false;
    }
    
    // Take the server's state after it refused a request. A state read reports
    // "paused" whenever the clock has been idle for a while, and that must not
    // stop a game nobody paused.
    async function resync() {
        const wasPaused = paused;
        await loadGame();
        if (paused && !wasPaused && !gameOver) await resumeGame();
    }

    async function executeMove(fr, fc, tr, tc, promotionPiece, skipAnimation = false) {
        // A second click while the first request is out would send the move twice.
        if (moveInFlight) return { success: false, message: 'Move already in progress' };
        moveInFlight = true;
        try {
            const body = {
                from_row: fr, from_col: fc,
                to_row: tr, to_col: tc,
            };
            if (promotionPiece) body.promotion_piece = promotionPiece;

            const data = await post('/api/move/', body);

            if (data.valid) {
                illegalMoveCount = 0;
                playSound(data);
                if (!skipAnimation) await animateMove(fr, fc, tr, tc);
                board = parseBoard(data.board);
                liveBoard = board;
                if (data.fen) liveFen = data.fen;
                if (data.pgn) livePgn = data.pgn;
                turn = data.current_turn;
                inCheck = data.game_status === 'check';

                // The puzzle branches below return early, so they draw the move with this.
                const showMove = () => {
                    lastMove = { from: [fr, fc], to: [tr, tc] };
                    selected = null;
                    hints = [];
                    updateTurn();
                    updateMoves(data.move_history);
                    updateCaptured(data.captured_pieces);
                };

                const hasThreefoldWarning = data.threefold_warning;

                if (hasThreefoldWarning) {
                    showStatus(
                        '⚠️ This position has appeared twice. One more repetition will trigger a draw.',
                        false
                    );
                }

                // Daily Puzzle Validation
                if (dailyPuzzleMode && currentPuzzle && !puzzleAnalyzing) {

                    const playedMove =
                        `${String.fromCharCode(97 + fc)}${8 - fr}` +
                        `${String.fromCharCode(97 + tc)}${8 - tr}` +
                        (promotionPiece || '');

                    const expectedMove =
                        currentPuzzle.solution[puzzleMoveIndex];

                    if (playedMove === expectedMove) {

                        clearPuzzleHints();
                        puzzleMoves.push(playedMove);

                        puzzleMoveIndex++;
                        currentPuzzleFen = data.fen;
                        expectedMoveEval = null;
                        precalculateExpectedMoveEval();

                        if (puzzleMoveIndex >= currentPuzzle.solution.length) {

                            const { streak, longest } = await submitPuzzleSolution();
                            updateStreakDisplay();
                            if (data.game_status === 'checkmate') {
                                // Transition to standard game-over overlay for checkmates
                            } else {
                                showMove();
                                showConfirm(
                                    "🎉 Puzzle Solved!",
                                    `🔥 Current Streak: ${streak}<br> 
                                                        🏆 Best Streak: ${longest}<br>
                                                        Come back tomorrow for a new challenge.`,
                                    () => {
                                        gameLayout.style.visibility = "hidden";
                                        welcomeOverlay.classList.add("active");
                                    },
                                    "gold"
                                );
                                return { success: true };
                            }
                        }
                    } else {
                        // Start Stockfish validation for alternative moves
                        showMove();
                        puzzleAnalyzing = true;
                        const origStatus = document.getElementById("game-status") ? document.getElementById("game-status").textContent : "";
                        showStatus("Analyzing move with Stockfish...", false);

                        validateMoveWithStockfish(currentPuzzleFen, data.fen, expectedMove)
                            .then(async (isCorrect) => {
                                puzzleAnalyzing = false;
                                showStatus(origStatus, false);

                                if (isCorrect) {
                                    puzzleMoves.push(playedMove);
                                    puzzleMoveIndex++;
                                    currentPuzzleFen = data.fen;
                                    expectedMoveEval = null;
                                    precalculateExpectedMoveEval();

                                    if (puzzleMoveIndex >= currentPuzzle.solution.length) {
                                        const { streak, longest } = await submitPuzzleSolution();
                                        updateStreakDisplay();
                                        if (data.game_status === 'checkmate') {
                                            lastMove = { from: [fr, fc], to: [tr, tc] };
                                            whiteTime = data.white_time;
                                            blackTime = data.black_time;
                                            updatePlayerNames(data);
                                            updateTurn();
                                            updateMoves(data.move_history);
                                            updateCaptured(data.captured_pieces);
                                            syncPieces();
                                            renderClocks();
                                            updateMaterialUI(board);
                                            return endGame('checkmate', turn).catch(e => console.error("Error in endGame:", e));
                                        } else {
                                            showConfirm(
                                                "🎉 Puzzle Solved!",
                                                `🔥 Current Streak: ${streak}<br> 
                                                                    🏆 Best Streak: ${longest}<br>
                                                                    Come back tomorrow for a new challenge.`,
                                                () => {
                                                    gameLayout.style.visibility = "hidden";
                                                    welcomeOverlay.classList.add("active");
                                                },
                                                "gold"
                                            );
                                        }
                                    } else if (isAITurn()) {
                                        // More moves to find: the opponent replies, as it does after the listed move.
                                        requestAIMove();
                                    }
                                } else {
                                    showConfirm(
                                        "❌ Incorrect Move!",
                                        "Would you like to try again?",
                                        restartCurrentPuzzle,
                                        "danger"
                                    );
                                }
                            })
                            .catch((err) => {
                                console.error("Stockfish validation promise error:", err);
                                puzzleAnalyzing = false;
                                showStatus(origStatus, false);
                                showConfirm(
                                    "❌ Incorrect Move!",
                                    "Would you like to try again?",
                                    restartCurrentPuzzle,
                                    "danger"
                                );
                            });
                        return { success: true };
                    }
                }

                lastMove = { from: [fr, fc], to: [tr, tc] };

                if (gameMode === 'pvp' && autoFlip) {
                    const turnRound = flipped !== (turn === 'black');
                    flipped = (turn === 'black');
                    if (turnRound) turnBoard();
                    else buildBoard();
                }
                whiteTime = data.white_time;
                blackTime = data.black_time;

                selected = null;
                hints = [];
                updatePlayerNames(data);
                updateTurn();
                updateOpeningDisplay(data.opening_name);
                updateMoves(data.move_history);
                updateCaptured(data.captured_pieces);
                syncPieces();
                renderClocks();
                startTimer();
                updateMaterialUI(board);
                let a11yMsg = '';
                const playedColor = turn === 'white' ? 'Black' : 'White';
                if (data.captured) {
                    const targetSquare = getSquareLabel(tr, tc);
                    const pieceCode = (typeof data.captured === 'string') ? data.captured : '';
                    const pieceName = PIECE_NAMES[pieceCode.toLowerCase()] || 'piece';
                    const capturer = playedColor;
                    const capturedColor = capturer === 'White' ? 'Black' : 'White';
                    a11yMsg = `${capturer} captured ${capturedColor}'s ${pieceName} on ${targetSquare}. `;
                } else if (data.move_history && data.move_history.length > 0) {
                    const lastMove = data.move_history[data.move_history.length - 1].notation;
                    a11yMsg = `${playedColor} played ${lastMove}. `;
                }

                const gameEnded = handleGameStatus(data.game_status, data.draw_reason);
                if (!gameEnded) {
                    if (data.game_status === 'check') {
                        applyCheckHighlight();
                        const checkMsg = turn === 'white' ? 'Check to White King!' : 'Check to Black King!';

                        a11yMsg += checkMsg;
                    } else {
                        highlightCheck();
                        if (!hasThreefoldWarning) {
                            showStatus('', false);
                        }
                    }
                    if (a11yMsg) announceMove(a11yMsg);
                }

                triggerPositionEvaluation();

                if (gameMode === 'ai' && turn !== playerColor && !gameOver) {
                    requestAIMove();
                }
                return { success: true };
            } else {
                const reason = data.message || data.error || 'Move rejected';
                showStatus(reason, true);
                flashBoard();
                deselect();
                if (premoveQueue.length > 0) {
                    premoveQueue = [];
                    refreshPremoveHighlight();
                }
                if (data.game_status === 'timeout') {
                    // The server found the mover's clock at zero and has closed the game.
                    if (data.white_time !== undefined) whiteTime = data.white_time;
                    if (data.black_time !== undefined) blackTime = data.black_time;
                    renderClocks();
                    handleGameStatus('timeout', null, data.winner);
                } else if (data.httpStatus === 403 || data.httpStatus === 409) {
                    // The server disagrees about the position or whose turn it is: take its state.
                    await resync();
                    showStatus(reason, true);
                }
                return { success: false, message: reason };
            }
        } catch (e) {
            await handleReconnect();
            return { success: false, message: 'Connection lost' };
        } finally {
            moveInFlight = false;
        }
    }

    async function requestAIMove() {
        if (gameOver || aiThinking) return;
        // Increment and store current sequence value to identify this specific request
        const seq = ++aiRequestSeq;
        aiThinking = true;

       
        try {
            let piecesOnBoard = 0;
            for (let r = 0; r < 8; r++) {
                for (let c = 0; c < 8; c++) {
                    if (board[r][c]) piecesOnBoard++;
                }
            }

            // randomized delay per difficulty — feels realistic and unpredictable
            let delay;
            if (currentDifficulty === 'easy') delay = 800 + Math.random() * (1500 - 800);
            else if (currentDifficulty === 'hard') delay = 2500 + Math.random() * (4000 - 2500);
            else delay = 1500 + Math.random() * (2500 - 1500); // medium
            await new Promise(resolve => setTimeout(resolve, delay));

            // Abort if a new game started, reconnect happened, or another request took over during delay
            if (seq !== aiRequestSeq) return;

            // fix: abort if game ended during delay
            if (gameOver) return;

            // fix: abort if game paused during delay
            if (paused) return;

            const data = await post('/api/ai-move/', {});
            

            // Abort if sequence is no longer current after API call completes
            if (seq !== aiRequestSeq) {
                return;
            }

            if (data.valid) {
                aiFailures = 0;
                const mv = data.ai_move;
                if (!mv) {
                    // Nothing to play: the game was already decided (mate, stalemate or a draw).
                    handleGameStatus(data.game_status, data.draw_reason, data.winner);
                    return;
                }
                playSound(data);
                
                await animateMove(mv.from_row, mv.from_col, mv.to_row, mv.to_col);
                board = parseBoard(data.board);
                liveBoard = board;
                if (data.fen) liveFen = data.fen;
                if (data.pgn) livePgn = data.pgn;
                turn = data.current_turn;
                inCheck = data.game_status === 'check';
                const hasThreefoldWarning = data.threefold_warning;
                if (hasThreefoldWarning) {
                    showStatus(
                        '⚠️ This position has appeared twice. One more repetition will trigger a draw.',
                        false
                    );
                }

                lastMove = { from: [mv.from_row, mv.from_col], to: [mv.to_row, mv.to_col] };
                whiteTime = data.white_time;
                blackTime = data.black_time;

                selected = null;
                hints = [];
                updatePlayerNames(data);
                updateTurn();
                updateOpeningDisplay(data.opening_name);
                updateMoves(data.move_history);
                updateCaptured(data.captured_pieces);
                syncPieces();
                renderClocks();
                startTimer();
                updateMaterialUI(board);
                let a11yMsg = '';
                const playedColor = turn === 'white' ? 'Black' : 'White';
                if (data.captured) {
                    const targetSquare = getSquareLabel(mv.to_row, mv.to_col);
                    const pieceCode = (typeof data.captured === 'string') ? data.captured : '';
                    const pieceName = PIECE_NAMES[pieceCode.toLowerCase()] || 'piece';
                    const capturer = playedColor;
                    const capturedColor = capturer === 'White' ? 'Black' : 'White';
                    a11yMsg = `${capturer} captured ${capturedColor}'s ${pieceName} on ${targetSquare}. `;
                } else if (data.move_history && data.move_history.length > 0) {
                    const lastMove = data.move_history[data.move_history.length - 1].notation;
                    a11yMsg = `AI played ${lastMove}. `;
                }

                const gameEnded = handleGameStatus(data.game_status, data.draw_reason);
                if (!gameEnded) {
                    if (data.game_status === 'check') {
                        applyCheckHighlight();
                        const checkMsg = turn === 'white' ? 'Check to White King!' : 'Check to Black King!';

                        a11yMsg += checkMsg;
                    } else {
                        highlightCheck();
                        if (!hasThreefoldWarning) {
                            showStatus('Your turn.', false);
                        }
                    }
                    if (a11yMsg) announceMove(a11yMsg);

                    triggerPositionEvaluation();

                    // Trigger queued premove if it exists
                    if (premoveQueue.length > 0) {
                        const queued = premoveQueue.shift();
                        refreshPremoveHighlight();

                        const piece = board[queued.from.r][queued.from.c];
                        if (piece && pColor(piece) === turn) {
                            setTimeout(() => {
                                tryMove(queued.from.r, queued.from.c, queued.to.r, queued.to.c);
                            }, 150);
                        } else {
                            premoveQueue = [];
                            refreshPremoveHighlight();
                            showStatus("Premove cancelled: piece captured or invalid", true);
                        }
                    }
                }
            } else if (data.game_status === 'timeout') {
                // A clock ran out while the engine was thinking; the server has closed the game.
                if (data.white_time !== undefined) whiteTime = data.white_time;
                if (data.black_time !== undefined) blackTime = data.black_time;
                renderClocks();
                handleGameStatus('timeout', null, data.winner);
            } else {
                const reason = data.message || data.error || 'The AI could not move.';
                aiFailures++;
                if (data.httpStatus === 503 && aiFailures <= AI_MAX_RETRIES) {
                    // The engine gave no answer and the game is untouched, so ask again.
                    showStatus('The AI is taking longer than usual...', false);
                    setTimeout(() => {
                        if (seq === aiRequestSeq) queueAIMoveIfNeeded();
                    }, 1000);
                } else if (data.httpStatus === 429 || aiFailures > AI_MAX_RETRIES) {
                    const stop = /[.!?]$/.test(reason) ? '' : '.';
                    showStatus(`${reason}${stop} Pause and resume to ask the AI again.`, true);
                } else {
                    // Any other refusal means this page is out of step with the server
                    // (paused there, or not the AI's turn). Taking its state settles it,
                    // and loadGame asks again if the AI is still to move.
                    await resync();
                }
            }
            } catch (e) {
                await handleReconnect();
            } finally {
            // always reset aiThinking... a stale sequence means a newer request owns it, but it will set its own flag
            aiThinking = false;
        }
    }

    /* ==========================================================
    EVENTS
    ========================================================== */
    async function onClick(r, c) {
        if (replayMode || viewingPastState) return;
        if (dragging && !touchDragging) return;

        const isPremoveMode = gameMode === 'ai' && turn !== playerColor;
        const vBoard = isPremoveMode ? getVirtualBoard() : board;
        const piece = vBoard[r][c];

        const aiPremoveMode =
            gameMode === 'ai' &&
            turn !== playerColor;

        if (selected) {

            // deselect same square
            if (selected.r === r && selected.c === c) {
                return deselect();
            }

            // PREMOVE CLICK
            if (aiPremoveMode) {

                premoveQueue.push({
                    from: { r: selected.r, c: selected.c },
                    to: { r, c }
                });

                refreshPremoveHighlight();

                showStatus("Premove queued", false);

                selected = null;
                hints = [];
                refreshHighlights();

                return;
            }

            // NORMAL MOVE
            if (hints.some(h => h.row === r && h.col === c)) {
                return tryMove(selected.r, selected.c, r, c);
            }

            // reselect another piece
            if (piece && pColor(piece) === turn) {
                return selectPiece(r, c);
            }

            return deselect();
        }

        // selecting initial piece: on the engine's turn only the player's own, for a premove
        if (piece && pColor(piece) === (aiPremoveMode ? playerColor : turn)) {
            return selectPiece(r, c);
        }
    }

    async function onDrop(e, tr, tc) {
        // Otherwise the browser may treat the dragged text as a link to open.
        e.preventDefault();
        if (replayMode || viewingPastState) return;
        if (!dragSrc) return;
        await tryMove(dragSrc.r, dragSrc.c, tr, tc);
        dragSrc = null;
    }

    function resetReplayBoard() {
        if (window.Chess) {
            replayBoard = new window.Chess(startingFen());
        }
    }

    function renderReplayPosition() {

        if (!replayBoard) return;

        const fen = replayBoard.fen();
        const position = fen.split(' ')[0];
        const rows = fen.split(' ')[0].split('/');

        board = rows.map(row => {

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

        buildBoard();
        if (typeof syncPieces === 'function') {
            syncPieces();
        }

        if (typeof updateMaterialUI === 'function') {
            updateMaterialUI(board);
        }
        updateEvalBarVisibility();
        if (fen && !dailyPuzzleMode) {
            getStockfishEval(fen).then(result => {
                if (replayBoard && replayBoard.fen() === fen) {
                    updateEvalBar(result, fen);
                }
            }).catch(() => { }); // rejected when a newer position replaces this request
        }
    }
    function goToReplayMove(index) {

        if (!window.Chess) {
            console.error("Chess.js not loaded");
            return;
        }

        replayBoard = new window.Chess(startingFen());

        try {

            for (let i = 0; i < index; i++) {

                const move = replayMoves[i];

                if (move) {
                    const result = replayBoard.move(move);

                }
            }

            replayIndex = index;

            renderReplayPosition();

        } catch (e) {

            console.error("Replay move error:", e);
        }
    }

    function rebuildGameFens(moveHistory, startFen) {
        // Without chess.js there is nothing to replay with; the stepper only has the live position.
        if (!window.Chess) return [liveFen];
        const tempChess = new window.Chess(startFen || DEFAULT_START_FEN);
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
    board = rows.map(row => {
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
    buildBoard();
    if (typeof syncPieces === 'function') syncPieces();
    if (typeof updateMaterialUI === 'function') updateMaterialUI(board);
}

function updateStepperUI() {
    const fen = gameFens[stepperIndex];
    // The latest move shows the board the server sent. The chess.js replay is
    // only for looking back, and can be wrong if the starting FEN is not known here.
    if (liveBoard && stepperIndex >= gameFens.length - 1) {
        board = liveBoard.map(row => [...row]);
        buildBoard();
    } else if (fen) {
        renderStepperPosition(fen);
    }

    viewingPastState = (stepperIndex < gameFens.length - 1);

    updateEvalBarVisibility();

    if (fen && gameMode === 'ai' && !dailyPuzzleMode) {
        getStockfishEval(fen).then(result => {
            if (gameFens[stepperIndex] === fen) {
                updateEvalBar(result, fen);
            }
        }).catch(() => { }); // rejected when a newer position replaces this request
    }

    const resumeBtn = document.getElementById('resumeGameBtn');
    if (resumeBtn) resumeBtn.classList.toggle('hidden', !viewingPastState);

    const firstBtn = document.getElementById('stepperFirst');
    const prevBtn = document.getElementById('stepperPrev');
    const nextBtn = document.getElementById('stepperNext');
    const lastBtn = document.getElementById('stepperLast');

    if (firstBtn) firstBtn.disabled = (stepperIndex === 0);
    if (prevBtn) prevBtn.disabled = (stepperIndex === 0);
    if (nextBtn) nextBtn.disabled = (stepperIndex === gameFens.length - 1);
    if (lastBtn) lastBtn.disabled = (stepperIndex === gameFens.length - 1);

    document.querySelectorAll('.moves-list .selected-move').forEach(el => el.classList.remove('selected-move'));
    if (stepperIndex > 0) {
        const activeMoveEl = document.querySelector(`.moves-list span[data-move-index="${stepperIndex - 1}"]`);
        if (activeMoveEl) {
            activeMoveEl.classList.add('selected-move');
            // Scroll the move list, and only the move list. scrollIntoView
            // also scrolls the page, and where the list sits under the board
            // (phones, tablets) that pushed the board up under the navbar
            // after every move.
            const list = activeMoveEl.closest('.moves-list');
            if (list) {
                const box = list.getBoundingClientRect();
                const row = activeMoveEl.getBoundingClientRect();
                const by = row.top < box.top ? row.top - box.top : Math.max(0, row.bottom - box.bottom);
                if (by && typeof list.scrollBy === 'function') list.scrollBy({ top: by, behavior: 'smooth' });
                else if (by) list.scrollTop += by;
            }
        }
    }
}

    /* ==========================================================
    UI UPDATES
    ========================================================== */
    function updateTurn() {
        if (
            !turnEl ||
            !whiteNameLabel ||
            !blackNameLabel ||
            !wCapEl ||
            !bCapEl
        ) {
            return;
        }

        const badge = turnEl;
        badge.className = 'turn-badge ' + turn;

        let label = turn.charAt(0).toUpperCase() + turn.slice(1) + "'s Turn";
        const pName = turn === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;
        label = pName + "'s Turn";

        if (gameMode === 'ai') {
            if (turn === playerColor) {
                label = "Your Turn";
            } else {
                label = "AI is thinking...";
            }
        }
        // The label goes in the badge's own span, which is then its only
        // child: the "'s Turn" the template leaves after it would repeat.
        if (turnBadgeText) {
            turnBadgeText.textContent = label;
            badge.replaceChildren(turnBadgeText);
        } else {
            badge.textContent = label;
        }

        wCapEl.classList.toggle('active', turn === 'white');
        bCapEl.classList.toggle('active', turn === 'black');
    }

    function updateOpeningDisplay(openingName) {
        const openingDisplay = document.getElementById("openingDisplay");
        if (!openingDisplay) return;

        openingDisplay.textContent = openingName
            ? `Opening: ${openingName}`
            : "Opening: Custom Position";
    }

    function updateMoves(history) {
    const startFen = startingFen();
    halfMoves = history ? history.length : 0;
    gameFens = rebuildGameFens(history, startFen);

    if (!viewingPastState) {
        stepperIndex = gameFens.length - 1;
    }

    if (!history?.length) {
        movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
        updateStepperUI();
        return;
    }
    movesEl.innerHTML = '';
    // When the game was set up with Black to move, the first entry is Black's:
    // White's column starts with a gap and numbering starts at the FEN's move number.
    const fenParts = startFen.split(' ');
    const blackFirst = fenParts[1] === 'b' ? 1 : 0;
    const firstMoveNum = parseInt(fenParts[5], 10) || 1;
    for (let slot = history.length - 1 + blackFirst; slot >= 0; slot -= 2) {
        const whiteSlot = slot % 2 === 0 ? slot : slot - 1;
        const whiteIdx = whiteSlot - blackFirst;
        const blackIdx = whiteIdx + 1;
        const moveNum = Math.floor(whiteSlot / 2) + firstMoveNum;
        const row = document.createElement('div');
        row.className = 'move-row';

        const whiteSpan = document.createElement('span');
        whiteSpan.className = 'move-white';
        if (whiteIdx < 0) {
            whiteSpan.textContent = '...';
        } else {
            whiteSpan.textContent = history[whiteIdx]?.notation ?? '';
            whiteSpan.dataset.moveIndex = whiteIdx;
            whiteSpan.onclick = () => {
                stepperIndex = whiteIdx + 1;
                updateStepperUI();
            };
        }

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
                stepperIndex = blackIdx + 1;
                updateStepperUI();
            };
            row.appendChild(blackSpan);
        }
        movesEl.appendChild(row);
    }
    updateStepperUI();
    if (!viewingPastState) movesEl.scrollTop = 0;
}

    function updateCaptured(cap) {
        wCapEl.innerHTML = bCapEl.innerHTML = '';

        // Use global MATERIAL_VALUES instead of redefining locally (DRY principle)
        const sortByValue = (pieces) => [...pieces].sort((a, b) =>
            (MATERIAL_VALUES[b.toLowerCase()] || 0) - (MATERIAL_VALUES[a.toLowerCase()] || 0)
        );

        let whitePoints = cap.white.reduce((sum, p) => sum + (MATERIAL_VALUES[p.toLowerCase()] || 0), 0);
        let blackPoints = cap.black.reduce((sum, p) => sum + (MATERIAL_VALUES[p.toLowerCase()] || 0), 0);

        const pieceNames = { 'p': 'Pawn', 'n': 'Knight', 'b': 'Bishop', 'r': 'Rook', 'q': 'Queen' };

        // Use createElement instead of innerHTML to prevent XSS and avoid DOM reflows
        const makeImg = (p) => {
            const img = document.createElement('img');
            const key = pKey(p);
            img.src = PIECE_ICON[key];
            img.className = 'captured-img';
            img.dataset.piece = key; // Save key for live piece style switching
            const name = pieceNames[p.toLowerCase()] || p;
            img.title = name;
            img.alt = name;
            return img;
        };

        sortByValue(cap.white).forEach((p) => wCapEl.appendChild(makeImg(p)));
        sortByValue(cap.black).forEach((p) => bCapEl.appendChild(makeImg(p)));

        const wPointsEl = document.getElementById('whitePoints');
        const bPointsEl = document.getElementById('blackPoints');
        if (wPointsEl) wPointsEl.textContent = `+${whitePoints}`;
        if (bPointsEl) bPointsEl.textContent = `+${blackPoints}`;
    }

    function showStatus(msg, err) {
        const gameStatusEl = document.getElementById("game-status");

        if (gameStatusEl) {
            gameStatusEl.textContent = msg;
        }

        statusEl.className = 'status-bar' + (err ? ' error' : '');
    }

    function handleGameStatus(status, drawReason, winner) {
        if (dailyPuzzleMode && status !== 'checkmate') {
            return false;
        }
        if (status === 'checkmate') {
            // pass 'turn' as the loserColor since the current turn's player got checkmated
            endGame('checkmate', turn).catch(e => console.error("Error in endGame:", e));
            return true;
        }
        if (status === 'stalemate') {
            // pass 'turn' as the loserColor (unused for stalemate winner derivation)
            endGame('stalemate', turn).catch(e => console.error("Error in endGame:", e));
            return true;
        }
        if (status === 'draw') {
            endGame('draw', turn, drawReason).catch(e => console.error("Error in endGame:", e));
            return true;
        }
        if (status === 'timeout') {
            // An older server does not name the winner; then it is the side with time left.
            let flagged = whiteTime <= 0 ? 'white' : (blackTime <= 0 ? 'black' : turn);
            if (winner) flagged = winner === 'white' ? 'black' : 'white';
            endGame('timeout', flagged).catch(e => console.error("Error in endGame:", e));
            return true;
        }
        return false;
    }

    // loserColor always represents the losing side. Unused for winner derivation in draw/stalemate.
    async function endGame(reason, loserColor, drawReason = null) {
        if (gameOver) return;
        gameOver = true;

        // The beaten king goes over.
        if (reason === 'checkmate') {
            const king = loserColor === 'white' ? 'K' : 'k';
            for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
                if (board[r] && board[r][c] === king) fallenKing = { r, c };
            }
            if (fallenKing) refreshHighlights();
        }

        let title = '', message = '';
        let isCelebration = false;

        try {
            const frozenPlayerColor = playerColor;
            replayMode = true;
            paused = true;
            clearInterval(timerInterval);

            // Issue #12: hide the pause overlay and reset its timer — the
            // game is over now, so "paused" no longer means an active pause.
            stopPauseTimer();
            if (pauseOverlayEl) pauseOverlayEl.classList.remove('active');

        if (blindfoldMode) {
            blindfoldMode = false;
            document.body.classList.remove('blindfold-mode');
            const blindfoldBtn = document.getElementById('blindfoldBtn');
            if (blindfoldBtn) blindfoldBtn.textContent = 'Blindfold: OFF';
        }
        updateThinkingDots();

        title = ''; message = '';

        // Determine PVP or AI result relative to current player color
        const isWon = reason === 'checkmate' || reason === 'resign' || reason === 'timeout';
        const winnerColor = isWon ? (loserColor === 'white' ? 'black' : 'white') : null;

        let resultState = 'draw'; // 'victory', 'defeat', 'draw'
        if (isWon) {
            if (gameMode === 'ai') {
                resultState = (winnerColor === frozenPlayerColor) ? 'victory' : 'defeat';
            } else {
                resultState = 'victory'; // Celebrate PvP victory for either side
            }
        }

        isCelebration = (resultState === 'victory');

        // Update the session W/L/D tracker for this completed game
        if (gameMode === 'ai' || reason === 'draw' || reason === 'stalemate') {
    recordGameResult(resultState);
}

        // Play distinct game over sound
        playGameOverSound(reason, resultState);

        if (reason === 'checkmate') {
            const winnerName = loserColor === 'white' ? (blackNameLabel?.textContent || 'Black') : (whiteNameLabel?.textContent || 'White');
            title = 'Checkmate';
            message = `${winnerName} Wins!`;
        } else if (reason === 'stalemate') {
            title = 'Stalemate';
            message = 'The game is a draw.';
        } else if (reason === 'draw') {
            title = 'Draw';
            const drawMessages = {
                agreement: 'Draw by agreement.',
                threefold_repetition: 'Draw by repetition.',
                fifty_move_rule: 'Draw by fifty-move rule.',
                insufficient_material: 'Draw by insufficient material.',
            };
            message = drawMessages[drawReason] || 'The game is a draw.';
        } else if (reason === 'resign') {
            const winnerName = loserColor === 'white' ? (blackNameLabel?.textContent || 'Black') : (whiteNameLabel?.textContent || 'White');
            const loserName = loserColor === 'white' ? (whiteNameLabel?.textContent || 'White') : (blackNameLabel?.textContent || 'Black');
            title = 'Victory';
            message = `${loserName} resigned. ${winnerName} Wins!`;
        } else if (reason === 'timeout') {
            const winnerName = loserColor === 'white' ? (blackNameLabel?.textContent || 'Black') : (whiteNameLabel?.textContent || 'White');
            const loserName = loserColor === 'white' ? (whiteNameLabel?.textContent || 'White') : (blackNameLabel?.textContent || 'Black');
            title = 'Timeout';
            message = `${loserName} ran out of time. ${winnerName} Wins!`;
        }

        if (resignBtn) resignBtn.style.display = 'none';
        if (drawBtn) drawBtn.style.display = 'none';
        if (pauseBtn) pauseBtn.style.display = 'none';
        if (newPvPBtn) newPvPBtn.style.display = '';
        if (newAIBtn) newAIBtn.style.display = '';
        if (dailyPuzzleBtn) dailyPuzzleBtn.style.display = '';
        if (newFenBtn) newFenBtn.style.display = '';

        let durationText = '';

        if (gameStartTime) {
            const duration = Date.now() - gameStartTime;
            durationText = formatGameDuration(duration);
        }

        replayMoves = [];
        rawAnalysisMoves = [];
        replayIndex = 0;

        // Reverse the rows so we get the oldest moves first
        const moveRows = Array.from(document.querySelectorAll('.move-row')).reverse();

        moveRows.forEach(row => {
            const spans = row.querySelectorAll('.move-white, .move-black');
            spans.forEach(span => {
                const rawMove = span.textContent?.replace(/\s+/g, '')?.trim();
                const move = rawMove?.replace(/[+#]/g, '');

                if (rawMove && rawMove !== '...') {
                    rawAnalysisMoves.push(rawMove);
                }

                if (move && move !== '...') {
                    console.log("Replay move added:", move);
                    replayMoves.push(move);
                }
            });
        });

        console.log("FINAL REPLAY MOVES:", replayMoves);
        if (typeof process === 'undefined' || process.env.NODE_ENV !== 'test') {
            console.log("FINAL RAW MOVES:", rawAnalysisMoves);
        }

        resetReplayBoard();

        if (replayControls) {
            replayControls.classList.remove('hidden');
        }

        // 1. Dynamic Banner Setup
        const bannerEl = document.getElementById('gameOverBanner');
        const bannerIconEl = document.getElementById('bannerIcon');

        if (bannerEl) {
            bannerEl.className = 'result-banner';
            if (resultState === 'victory') {
                bannerEl.classList.add('banner-victory');
                if (bannerIconEl) bannerIconEl.textContent = '🏆';
                gameOverTitle.textContent = 'VICTORY';
            } else if (resultState === 'defeat') {
                bannerEl.classList.add('banner-defeat');
                if (bannerIconEl) bannerIconEl.textContent = '💀';
                gameOverTitle.textContent = 'DEFEAT';
            } else {
                bannerEl.classList.add('banner-draw');
                if (bannerIconEl) bannerIconEl.textContent = '🤝';
                gameOverTitle.textContent = 'DRAW';
            }
        }

        const messageEl = gameOverMessage || document.getElementById('gameOverMessage');
        if (messageEl) {
            messageEl.textContent = message;
        }

        // 2. Result Illustration injection
        const illustrationEl = document.getElementById('gameOverIllustration');
        if (illustrationEl) {
            let svgContent = '';
            if (resultState === 'defeat') {
                if (reason === 'timeout') {
                    svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M10 80 H90 L80 90 H20 Z" fill="#252545" opacity="0.6"/>
                                            <g class="svg-animate-hourglass">
                                                <path d="M35 20 H65 V30 L55 50 L65 70 V80 H35 V70 L45 50 L35 30 Z" fill="#7f8c8d" stroke="#5c6466" stroke-width="2"/>
                                                <path d="M38 25 H62 V28 L52 48 L48 48 L38 28 Z" fill="#95a5a6"/>
                                                <path d="M48 52 L52 52 L62 72 V75 H38 V72 Z" fill="#cbd5e0"/>
                                                <circle cx="50" cy="62" r="3" fill="#ffffff"/>
                                            </g>
                                        </svg>
                                    `;
                } else if (reason === 'checkmate') {
                    svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M10 80 H90 L80 90 H20 Z" fill="#2d1e1e" opacity="0.6"/>
                                            <g class="svg-animate-crown" transform="rotate(15 50 60)">
                                                <path d="M35 60 L40 35 L50 48 L60 35 L65 60 Z" fill="#7f8c8d" stroke="#5c6466" stroke-width="2"/>
                                                <circle cx="40" cy="33" r="2.5" fill="#95a5a6"/>
                                                <circle cx="50" cy="46" r="2.5" fill="#95a5a6"/>
                                                <circle cx="60" cy="33" r="2.5" fill="#95a5a6"/>
                                                <rect x="33" y="60" width="34" height="6" rx="2" fill="#5c6466"/>
                                                <rect x="37" y="66" width="26" height="4" fill="#3e4445"/>
                                            </g>
                                        </svg>
                                    `;
                } else {
                    svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <rect x="35" y="20" width="4" height="65" fill="#5c6466" rx="2"/>
                                            <g class="svg-animate-flag">
                                                <path d="M39 22 C48 18, 52 26, 65 22 C72 20, 75 23, 75 32 C75 42, 65 38, 55 42 C45 46, 39 38, 39 38 Z" fill="#7f8c8d" stroke="#5c6466" stroke-width="1"/>
                                            </g>
                                            <path d="M20 78 L23 68 L28 73 L33 68 L36 78 Z" fill="#95a5a6" transform="rotate(-15 20 78)"/>
                                        </svg>
                                    `;
                }
            } else if (resultState === 'draw') {
                svgContent = `
                                    <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <g class="svg-animate-handshake" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                            <path d="M15 50 H30 L45 40 L50 48 L40 55 H25" stroke="#3498db" stroke-width="4"/>
                                            <path d="M85 50 H70 L55 40 L50 48 L60 55 H75" stroke="#ffd700" stroke-width="4"/>
                                            <path d="M45 44 L48 52" stroke="#ffffff" stroke-width="3"/>
                                            <path d="M52 44 L55 52" stroke="#ffffff" stroke-width="3"/>
                                        </g>
                                        <circle cx="50" cy="50" r="35" stroke="rgba(255,255,255,0.06)" stroke-width="2" stroke-dasharray="4 4"/>
                                    </svg>
                                `;
            } else { // victory
                if (reason === 'checkmate') {
                    svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M10 80 H90 L80 90 H20 Z" fill="#252545" opacity="0.6"/>
                                            <g class="svg-animate-crown">
                                                <path d="M35 60 L40 35 L50 48 L60 35 L65 60 Z" fill="#ffd700" stroke="#b89000" stroke-width="2"/>
                                                <circle cx="40" cy="33" r="2.5" fill="#ffffff"/>
                                                <circle cx="50" cy="46" r="2.5" fill="#ffffff"/>
                                                <circle cx="60" cy="33" r="2.5" fill="#ffffff"/>
                                                <rect x="33" y="60" width="34" height="6" rx="2" fill="#d4af37"/>
                                                <rect x="37" y="66" width="26" height="4" fill="#a08020"/>
                                            </g>
                                        </svg>
                                    `;
                } else if (reason === 'timeout') {
                    svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <rect x="20" y="30" width="60" height="50" rx="8" fill="#1b1b32" stroke="#444" stroke-width="3"/>
                                            <circle cx="38" cy="55" r="16" fill="#111" stroke="#f0c040" stroke-width="2"/>
                                            <circle cx="38" cy="55" r="14" fill="#222"/>
                                            <line x1="38" y1="55" x2="38" y2="45" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
                                            <line x1="38" y1="55" x2="46" y2="55" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
                                            <g class="svg-animate-flag">
                                                <rect x="68" y="24" width="4" height="25" fill="#777"/>
                                                <path d="M68 28 L52 35 L68 42 Z" fill="#ef4444"/>
                                            </g>
                                        </svg>
                                    `;
                } else { // resignation / general victory
                    svgContent = `
                                        <svg class="res-svg-illustration" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <rect x="35" y="20" width="4" height="65" fill="#777" rx="2"/>
                                            <g class="svg-animate-flag">
                                                <path d="M39 22 C48 18, 52 26, 65 22 C72 20, 75 23, 75 32 C75 42, 65 38, 55 42 C45 46, 39 38, 39 38 Z" fill="#ffffff" stroke="#ddd" stroke-width="1"/>
                                                <path d="M45 27 H55 M45 33 H65" stroke="#eee" stroke-width="1.5" stroke-linecap="round"/>
                                            </g>
                                            <path d="M20 78 L23 68 L28 73 L33 68 L36 78 Z" fill="#d4af37" transform="rotate(-15 20 78)"/>
                                        </svg>
                                    `;
                }
            }
            illustrationEl.innerHTML = svgContent;
        }

        // 3. Stats Grid Populating
        const resReasonEl = document.getElementById('resSummaryReason');
        if (resReasonEl) {
            let reasonText = 'Draw';
            if (reason === 'checkmate') reasonText = 'Checkmate';
            else if (reason === 'resign') reasonText = 'Resigned';
            else if (reason === 'timeout') reasonText = 'Timeout';
            else if (reason === 'stalemate') reasonText = 'Stalemate';
            else if (reason === 'draw') {
                const drawLabels = {
                    agreement: 'Draw (Agreement)',
                    threefold_repetition: 'Draw (Repetition)',
                    fifty_move_rule: 'Draw (50-move)',
                    insufficient_material: 'Draw (Material)',
                };
                reasonText = drawLabels[drawReason] || 'Draw';
            }
            resReasonEl.textContent = reasonText;
        }

        const resMovesEl = document.getElementById('resSummaryMoves');
        if (resMovesEl) {
            const fullMoves = Math.ceil(replayMoves.length / 2);
            resMovesEl.textContent = `${fullMoves} ${fullMoves === 1 ? 'move' : 'moves'}`;
        }

        const durationElement = document.getElementById('gameDurationText');
        if (durationElement) {
            durationElement.textContent = durationText || '00:00';
        }

        // 4. Material Difference and Cloned Captured Pieces
        const { white: whiteMat, black: blackMat } = calculateMaterial(board);
        const resMatDiffEl = document.getElementById('resMaterialDiff');
        if (resMatDiffEl) {
            if (whiteMat === blackMat) {
                resMatDiffEl.textContent = 'Even';
            } else if (whiteMat > blackMat) {
                resMatDiffEl.textContent = `White +${whiteMat - blackMat}`;
            } else {
                resMatDiffEl.textContent = `Black +${blackMat - whiteMat}`;
            }
        }

        const modalWhiteCap = document.getElementById('modalWhiteCaptured');
        const modalBlackCap = document.getElementById('modalBlackCaptured');
        if (modalWhiteCap && wCapEl) {
            modalWhiteCap.innerHTML = '';
            Array.from(wCapEl.children).forEach(child => {
                modalWhiteCap.appendChild(child.cloneNode(true));
            });
        }
        if (modalBlackCap && bCapEl) {
            modalBlackCap.innerHTML = '';
            Array.from(bCapEl.children).forEach(child => {
                modalBlackCap.appendChild(child.cloneNode(true));
            });
        }

        // 5. Dynamic Achievements detection
        const achievementsListEl = document.getElementById('resAchievementsList');
        const achievementsSectionEl = document.getElementById('resAchievementsSection');

        if (achievementsListEl) {
            achievementsListEl.innerHTML = '';
            const badges = [];

            if (reason === 'timeout') {
                badges.push({ text: 'Won on Time', icon: '⏱️' });
            }
            if (reason === 'checkmate') {
                badges.push({ text: 'Master Tactician', icon: '🧩' });
            }

            let hasWhiteQueen = false;
            let hasBlackQueen = false;
            for (let r = 0; r < 8; r++) {
                for (let c = 0; c < 8; c++) {
                    if (board[r][c] === 'Q') hasWhiteQueen = true;
                    if (board[r][c] === 'q') hasBlackQueen = true;
                }
            }

            const wPoints = parseInt(document.getElementById('whitePoints')?.textContent.replace('+', '')) || 0;
            const bPoints = parseInt(document.getElementById('blackPoints')?.textContent.replace('+', '')) || 0;

            if (isWon) {
                if (winnerColor === 'white' && hasWhiteQueen) {
                    badges.push({ text: 'Queen Survived', icon: '👑' });
                } else if (winnerColor === 'black' && hasBlackQueen) {
                    badges.push({ text: 'Queen Survived', icon: '👑' });
                }

                if (replayMoves.length <= 30) {
                    badges.push({ text: 'Lightning Fast', icon: '⚡' });
                }

                if (winnerColor === 'white' && wPoints >= 15) {
                    badges.push({ text: 'Fierce Attacker', icon: '⚔️' });
                } else if (winnerColor === 'black' && bPoints >= 15) {
                    badges.push({ text: 'Fierce Attacker', icon: '⚔️' });
                }
            } else {
                if (whiteMat < blackMat) {
                    badges.push({ text: 'Resilient Defense (White)', icon: '🛡️' });
                } else if (blackMat < whiteMat) {
                    badges.push({ text: 'Resilient Defense (Black)', icon: '🛡️' });
                }
            }

            if (badges.length === 0) {
                badges.push({ text: 'Good Game', icon: '🤝' });
            }

            badges.forEach(badge => {
                const badgeDiv = document.createElement('div');
                badgeDiv.className = 'achievement-badge';
                badgeDiv.innerHTML = `<span class="achievement-badge-icon">${badge.icon}</span> ${badge.text}`;
                achievementsListEl.appendChild(badgeDiv);
            });

            if (achievementsSectionEl) {
                achievementsSectionEl.style.display = 'block';
            }
        }

        // 6. Opening Book and Review Highlights (Fetch in Background)
        let fenHistory = [];
        if (window.Chess) {
            try {
                let tempChess = new window.Chess(startingFen());
                fenHistory.push(tempChess.fen());
                for (let move of replayMoves) {
                    let res = tempChess.move(move);
                    if (!res) {
                        break;
                    }
                    fenHistory.push(tempChess.fen());
                }
            } catch (e) {
                console.error("Error replaying moves for history", e);
            }
        }
        
        const currentAnalysisSeq = ++analysisRequestSeq;

        // The analysis is for signed-in players; a guest's request is refused with a 401.
        // It replays the moves from the normal starting position, so it means
        // nothing for a puzzle or a game set up from a FEN; those are skipped.
        const fromStart = !dailyPuzzleMode && startingFen().split(' ')[0] === DEFAULT_START_FEN.split(' ')[0];
        const analysis = document.documentElement.dataset.auth === '1' && fromStart
            ? post('/api/analyze-game/', {
                moves: rawAnalysisMoves,
                fen_history: fenHistory,
                result: resultState,
                reason: reason
            })
            : Promise.resolve(null);
        analysis.then(analysisData => {
            if (!analysisData) return;
            if (currentAnalysisSeq !== analysisRequestSeq) return;

            const openingNameEl = document.getElementById('resOpeningName');
            if (openingNameEl) {
                openingNameEl.textContent = analysisData.opening || 'Standard Game';
            }

            // Populate new stats
            const capEl = document.getElementById('resAnalysisCaptures');
            if (capEl) capEl.textContent = analysisData.captures || 0;

            const chkEl = document.getElementById('resAnalysisChecks');
            if (chkEl) chkEl.textContent = analysisData.checks || 0;

            const matEl = document.getElementById('resAnalysisCheckmates');
            if (matEl) matEl.textContent = analysisData.checkmates || 0;

            const proEl = document.getElementById('resAnalysisPromotions');
            if (proEl) proEl.textContent = analysisData.promotions || 0;

            const accuracyEl = document.getElementById('resAccuracyScore');
            const panelAccuracyEl = document.getElementById('panelAccuracyScore');
            if (accuracyEl && analysisData.accuracy !== undefined) {
                // null: no move could be classified
                const accuracyText = analysisData.accuracy === null ? '-' : `${analysisData.accuracy}%`;
                accuracyEl.textContent = accuracyText;
                if (panelAccuracyEl) panelAccuracyEl.textContent = accuracyText;
            }

            const mistakesEl = document.getElementById('resMistakesCount');
            if (mistakesEl && analysisData.mistakes !== undefined) {
                mistakesEl.textContent = analysisData.mistakes;
            }

            const blundersEl = document.getElementById('resBlundersCount');
            const panelBlundersEl = document.getElementById('panelBlundersCount');
            if (blundersEl && analysisData.blunders !== undefined) {
                blundersEl.textContent = analysisData.blunders;
                if (panelBlundersEl) panelBlundersEl.textContent = analysisData.blunders;
            }

            const tbody = document.getElementById('postGameAnalysisTableBody');
            if (tbody && analysisData.move_analysis_details) {
                tbody.innerHTML = '';
                const panel = document.getElementById('postGameAnalysisPanel');
                if (panel) {
                    panel.style.display = analysisData.move_analysis_details.length ? 'block' : 'none';
                    let cutShort = document.getElementById('analysisTruncatedNote');
                    if (!cutShort) {
                        cutShort = document.createElement('p');
                        cutShort.id = 'analysisTruncatedNote';
                        panel.appendChild(cutShort);
                    }
                    cutShort.textContent = analysisData.truncated
                        ? 'The analysis ran out of time and covers only the first moves.'
                        : '';
                }
                analysisData.move_analysis_details.forEach((detail, index) => {
                    const tr = document.createElement('tr');
                    // best, inaccuracy, mistake, blunder or unknown: the stylesheet colours the row's verdict
                    tr.dataset.verdict = detail.class.toLowerCase();

                    const tdMove = document.createElement('td');
                    tdMove.textContent = detail.move_num;
                    tr.appendChild(tdMove);

                    const tdPlayed = document.createElement('td');
                    tdPlayed.textContent = detail.played;
                    tr.appendChild(tdPlayed);

                    const tdBest = document.createElement('td');
                    tdBest.textContent = detail.best;
                    tr.appendChild(tdBest);

                    const tdClass = document.createElement('td');

                    let nextEval = null;
                    if (index + 1 < analysisData.move_analysis_details.length) {
                        nextEval = analysisData.move_analysis_details[index + 1].eval;
                    } else {
                        nextEval = analysisData.final_eval;
                    }

                    let evalText = '';
                    if (nextEval !== undefined && nextEval !== null) {
                        if (Math.abs(nextEval) > 90000) {
                            evalText = ' (M)';
                        } else {
                            const score = nextEval / 100;
                            evalText = ` (${score >= 0 ? '+' : ''}${score.toFixed(1)})`;
                        }
                    }
                    tdClass.textContent = detail.class + evalText;
                    tr.appendChild(tdClass);

                    tbody.appendChild(tr);
                });
            }

            const bestMoveEl = document.getElementById('resBestMove');
            if (bestMoveEl) {
                if (analysisData.move_analysis_details && analysisData.move_analysis_details.length > 0) {
                    const bestMoves = analysisData.move_analysis_details.filter(d => d.class === 'Best');
                    if (bestMoves.length > 0) {
                        const lastBest = bestMoves[bestMoves.length - 1];
                        bestMoveEl.textContent = `${lastBest.played} (Best)`;
                    } else if (rawAnalysisMoves.length > 2) {
                        bestMoveEl.textContent = `${rawAnalysisMoves[2]} (Book)`;
                    } else {
                        bestMoveEl.textContent = '–';
                    }
                } else {
                    bestMoveEl.textContent = '–';
                }
            }

            const blunderEl = document.getElementById('resBlunder');
            if (blunderEl) {
                const blunderLabel = blunderEl.previousElementSibling;
                if (analysisData.blunders > 0) {
                    blunderEl.textContent = `${analysisData.blunders} Blunder${analysisData.blunders > 1 ? 's' : ''}`;
                    if (blunderLabel) blunderLabel.textContent = 'Blunder';
                } else if (analysisData.mistakes > 0) {
                    blunderEl.textContent = `${analysisData.mistakes} Mistake${analysisData.mistakes > 1 ? 's' : ''}`;
                    if (blunderLabel) blunderLabel.textContent = 'Mistake';
                } else {
                    blunderEl.textContent = 'None';
                    if (blunderLabel) blunderLabel.textContent = 'Blunder';
                }
            }
        }).catch(e => {
            console.error("Failed to fetch post-game analysis", e);
        });

        } catch (error) {
            console.error("Error during endGame setup:", error);
            if (!title) title = 'Game Over';
            if (!message) message = 'The game has ended.';
            isCelebration = false;
        }

        // Delay the overlay and celebration effects by 0.5 seconds; after a
        // checkmate a little longer, so the beaten king is seen to fall.
        const kingFalls = reason === 'checkmate' && fallenKing && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        setTimeout(() => {
            const overlayEl = gameOverOverlay || document.getElementById('gameOverOverlay');
            if (!overlayEl) return;
            // Add celebration effects for wins
            if (isCelebration) {
                overlayEl.classList.add('game-over-celebration');
                createConfetti();
                createSparkles();
            } else {
                overlayEl.classList.remove('game-over-celebration');
            }

            // Prepare for fade-in animation
            overlayEl.style.transition = 'opacity 0.5s ease-in-out';
            overlayEl.style.opacity = '0';
            overlayEl.classList.add('active');

            // Trigger fade-in after a short delay
            setTimeout(() => {
                if (overlayEl) overlayEl.style.opacity = '1';
            }, 500);
        }, kingFalls ? 1250 : 500);

        showStatus(title + ': ' + message, false);

        // Clean a11y announcement
        const winnerColorText = loserColor === 'white' ? 'Black' : 'White';
        let cleanMsg = '';
        if (reason === 'checkmate') {
            cleanMsg = `Checkmate. ${winnerColorText} wins!`;
        } else if (reason === 'resign') {
            const resigningColorText = loserColor === 'white' ? 'White' : 'Black';
            cleanMsg = `${resigningColorText} has resigned. ${winnerColorText} wins!`;
        } else if (reason === 'timeout') {
            const timeoutColorText = loserColor === 'white' ? 'White' : 'Black';
            cleanMsg = `${timeoutColorText} ran out of time. ${winnerColorText} wins!`;
        } else if (reason === 'stalemate') {
            cleanMsg = 'Game drawn by stalemate.';
        } else if (reason === 'draw') {
            if (drawReason === 'agreement') {
                cleanMsg = 'Game drawn by agreement.';
            } else if (drawReason === 'threefold_repetition') {
                cleanMsg = 'Game drawn by threefold repetition.';
            } else if (drawReason === 'fifty_move_rule') {
                cleanMsg = 'Game drawn by fifty-move rule.';
            } else if (drawReason === 'insufficient_material') {
                cleanMsg = 'Game drawn by insufficient material.';
            } else {
                cleanMsg = 'Game drawn by agreement / stalemate / threefold repetition.';
            }
        } else {
            cleanMsg = 'Game drawn by agreement / stalemate / threefold repetition.';
        }
        announceMove(cleanMsg);

        document.title = 'Game Over - Checkora';
    }

    /* ==========================================================
    CELEBRATION EFFECTS
    ========================================================== */
    function createConfetti() {
        const overlay = document.getElementById('gameOverOverlay');
        const dialog = overlay.querySelector('.promo-dialog');

        // Create confetti container if it doesn't exist
        let confettiContainer = dialog.querySelector('.confetti-container');
        if (!confettiContainer) {
            confettiContainer = document.createElement('div');
            confettiContainer.className = 'confetti-container';
            dialog.style.position = 'relative';
            dialog.appendChild(confettiContainer);
        }

        // Clear existing confetti
        confettiContainer.innerHTML = '';

        // Create confetti pieces
        const colors = ['#ffd700', '#f0c040', '#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ff9ff3'];
        const confettiCount = 50;

        for (let i = 0; i < confettiCount; i++) {
            const confetti = document.createElement('div');
            confetti.className = 'confetti';

            // Random properties
            const randomColor = colors[Math.floor(Math.random() * colors.length)];
            const randomLeft = Math.random() * 100;
            const randomDelay = Math.random() * 0.5;
            const randomDuration = 2 + Math.random() * 2;
            const randomRotation = Math.random() * 360;

            confetti.style.left = randomLeft + '%';
            confetti.style.background = randomColor;
            confetti.style.animationDelay = randomDelay + 's';
            confetti.style.animationDuration = randomDuration + 's';
            confetti.style.transform = `rotate(${randomRotation}deg)`;

            // Random shapes
            if (Math.random() > 0.5) {
                confetti.style.borderRadius = '50%';
            }

            confettiContainer.appendChild(confetti);
        }
    }

    function createSparkles() {
        const overlay = document.getElementById('gameOverOverlay');
        const dialog = overlay.querySelector('.promo-dialog');

        let confettiContainer = dialog.querySelector('.confetti-container');
        if (!confettiContainer) {
            confettiContainer = document.createElement('div');
            confettiContainer.className = 'confetti-container';
            dialog.style.position = 'relative';
            dialog.appendChild(confettiContainer);
        }

        // Create sparkles
        const sparkleCount = 20;

        for (let i = 0; i < sparkleCount; i++) {
            const sparkle = document.createElement('div');
            sparkle.className = 'sparkle';

            const randomLeft = Math.random() * 100;
            const randomTop = Math.random() * 100;
            const randomDelay = Math.random() * 1.5;

            sparkle.style.left = randomLeft + '%';
            sparkle.style.top = randomTop + '%';
            sparkle.style.animationDelay = randomDelay + 's';

            confettiContainer.appendChild(sparkle);
        }
    }

    /* ==========================================================
    CLOCKS & PAUSE
    ========================================================== */
    const fmt = t => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
    function formatTime(t) { return fmt(t); }

    function updateThinkingDots() {
        const whiteClock = document.getElementById('whiteClock');
        const blackClock = document.getElementById('blackClock');

        if (!whiteClock || !blackClock) return;

        // Determine target clock before any DOM changes
        let targetClock = null;

        if (!paused && !gameOver) {
            if (whiteClock.classList.contains('active')) {
                targetClock = whiteClock;
            } else if (blackClock.classList.contains('active')) {
                targetClock = blackClock;
            }
        }

        // Check if dots are already in the correct place
        const whiteTimeEl = whiteClock.querySelector('.time');
        const blackTimeEl = blackClock.querySelector('.time');

        const whiteHasDots =
            whiteTimeEl?.querySelector('.thinking-dots') !== null;

        const blackHasDots =
            blackTimeEl?.querySelector('.thinking-dots') !== null;

        if (targetClock === whiteClock && whiteHasDots && !blackHasDots) return;

        if (targetClock === blackClock && blackHasDots && !whiteHasDots) return;

        if (!targetClock && !whiteHasDots && !blackHasDots) return;


        // Remove existing dots
        whiteClock.querySelector('.thinking-dots')?.remove();
        blackClock.querySelector('.thinking-dots')?.remove();

        // Stop when game ends
        if (paused || gameOver) return;

        const activeClock =
            whiteClock.classList.contains('active')
                ? whiteClock
                : blackClock.classList.contains('active')
                    ? blackClock
                    : null;

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



    function formatGameDuration(ms) {
        const totalSeconds = Math.floor(ms / 1000);
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        return `${mins}m ${secs}s`;
    }

    function renderClocks() {
        const wTime = document.getElementById('whiteTime');
        const bTime = document.getElementById('blackTime');
        const whiteClock = document.getElementById('whiteClock');
        const blackClock = document.getElementById('blackClock');

        if (gameMode === 'ai') {
            const playerClock = playerColor === 'white' ? whiteClock : blackClock;
            const playerTimeEl = playerColor === 'white' ? wTime : bTime;
            const aiClock = playerColor === 'white' ? blackClock : whiteClock;
            const aiTimeEl = playerColor === 'white' ? bTime : wTime;

            // fix: update time text only, never re-toggle active class here
            // active class is set once in updateTurn() to avoid blinking
            if (playerTimeEl) playerTimeEl.textContent = formatTime(playerColor === 'white' ? whiteTime : blackTime);
            if (aiTimeEl) {
                aiTimeEl.textContent = formatTime(playerColor === 'white' ? blackTime : whiteTime);
                aiTimeEl.style.fontSize = '';
                aiTimeEl.style.color = '';
            }

            // fix: only set active once (not on every tick)
            const isAiTurn = turn !== playerColor;
            if (playerClock) {
                playerClock.classList.toggle('active', !isAiTurn);
                playerClock.classList.toggle('inactive', isAiTurn);
                const pt = playerColor === 'white' ? whiteTime : blackTime;
                playerClock.classList.toggle('low-1', pt <= 30 && pt > 20);
                playerClock.classList.toggle('low-2', pt <= 20 && pt > 10);
                playerClock.classList.toggle('low-3', pt <= 10 && pt > 0);
            }
            if (aiClock) {
                aiClock.style.border = '';
                aiClock.style.boxShadow = '';
                aiClock.classList.toggle('active', isAiTurn);
                aiClock.classList.toggle('inactive', !isAiTurn);
                const at = playerColor === 'white' ? blackTime : whiteTime;
                aiClock.classList.toggle('low-1', at <= 30 && at > 20);
                aiClock.classList.toggle('low-2', at <= 20 && at > 10);
                aiClock.classList.toggle('low-3', at <= 10 && at > 0);
            }
        } else {
            // PvP — both clocks update normally
            if (wTime) wTime.textContent = formatTime(whiteTime);
            if (bTime) bTime.textContent = formatTime(blackTime);
            if (whiteClock) {
                whiteClock.classList.toggle('active', turn === 'white');
                whiteClock.classList.remove('inactive'); // fix: clear AI-mode styling bleed
                whiteClock.classList.toggle('low-1', whiteTime <= 30 && whiteTime > 20);
                whiteClock.classList.toggle('low-2', whiteTime <= 20 && whiteTime > 10);
                whiteClock.classList.toggle('low-3', whiteTime <= 10 && whiteTime > 0);
            }
            if (blackClock) {
                blackClock.classList.toggle('active', turn === 'black');
                blackClock.classList.remove('inactive'); // fix: clear AI-mode styling bleed
                blackClock.classList.toggle('low-1', blackTime <= 30 && blackTime > 20);
                blackClock.classList.toggle('low-2', blackTime <= 20 && blackTime > 10);
                blackClock.classList.toggle('low-3', blackTime <= 10 && blackTime > 0);
            }
        }
        const wYou = document.getElementById('whiteYouTag');
        const bYou = document.getElementById('blackYouTag');
        if (wYou) wYou.style.display = (gameMode === 'ai' && playerColor === 'white') ? 'inline' : 'none';
        if (bYou) bYou.style.display = (gameMode === 'ai' && playerColor === 'black') ? 'inline' : 'none';
        
        const sessionMaxTime = Math.round(selectedMins * 60) || 600;
        if (whiteTime > maxWhiteTime || maxWhiteTime === 0) maxWhiteTime = Math.max(whiteTime, sessionMaxTime);
        if (blackTime > maxBlackTime || maxBlackTime === 0) maxBlackTime = Math.max(blackTime, sessionMaxTime);

        updateClockTimerBar('whiteTimerBarFill', whiteTime, maxWhiteTime);
        updateClockTimerBar('blackTimerBarFill', blackTime, maxBlackTime);

        updateThinkingDots();
    }

    function updateClockTimerBar(barFillId, currentTime, maxTime) {
        const barFill = document.getElementById(barFillId);
        if (!barFill) return;
        const total = maxTime > 0 ? maxTime : (selectedMins * 60 || 600);
        const pct = Math.min(100, Math.max(0, (currentTime / total) * 100));
        barFill.style.width = `${pct}%`;
        barFill.classList.toggle('timer-warning', currentTime <= 30 && currentTime > 10);
        barFill.classList.toggle('timer-critical', currentTime <= 10 && currentTime > 0);
    }

            /* ==========================================================
            PAUSE DURATION TIMER (Issue #12)
            Live counter shown inside the pause overlay: "Paused for: MM:SS".
            Starts at 00:00 when paused, counts up every second, and is
            stopped/reset whenever the game is resumed or ends.
            ========================================================== */
            function formatPauseDuration(totalSeconds) {
                const mins = Math.floor(totalSeconds / 60);
                const secs = totalSeconds % 60;
                return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            }

            function startPauseTimer() {
                if (pauseTimerInterval) return; // already running — avoid double intervals
                pauseStartedAt = Date.now();
                pauseElapsedSeconds = 0;
                if (pauseTimerEl) pauseTimerEl.textContent = formatPauseDuration(0);
                announceMove('Game paused.');
                pauseTimerInterval = setInterval(() => {
                    // Derive from the anchor rather than incrementing, so a
                    // throttled/backgrounded tab self-corrects instead of drifting.
                    pauseElapsedSeconds = Math.floor((Date.now() - pauseStartedAt) / 1000);
                    if (pauseTimerEl) pauseTimerEl.textContent = formatPauseDuration(pauseElapsedSeconds);
                }, 1000);
            }

            function stopPauseTimer() {
                const wasRunning = !!pauseTimerInterval;
                clearInterval(pauseTimerInterval);
                pauseTimerInterval = null;
                pauseStartedAt = null;
                pauseElapsedSeconds = 0;
                if (pauseTimerEl) pauseTimerEl.textContent = formatPauseDuration(0);
                if (wasRunning) announceMove('Game resumed.');
            }

            function updatePauseUI() {
    pauseBtn.innerHTML =
    `${paused ? 'Resume' : 'Pause'}<span class="btn-shortcut">P</span>`;
    pauseBtn.classList.toggle('paused', paused);
    boardEl.classList.toggle('paused', paused);

    // Issue #12: show/hide the pause overlay and drive its live timer.
    // gameOver guards against the overlay reappearing right as a game ends
    // while paused (e.g. a draw is accepted during a pause).
    if (pauseOverlayEl) pauseOverlayEl.classList.toggle('active', paused && !gameOver);
    if (paused && !gameOver) {
        startPauseTimer();
    } else {
        stopPauseTimer();
    }

    // Mobile FAB icon toggle
    const pauseFabIcon = document.getElementById('pauseFabIcon');
    const playFabIcon = document.getElementById('playFabIcon');
    const pauseFab = document.getElementById('pauseFab');

    if (pauseFabIcon && playFabIcon) {
        pauseFabIcon.style.display = paused ? 'none' : 'block';
        playFabIcon.style.display = paused ? 'block' : 'none';
    }
    if (pauseFab) {
    const fabLabel = paused ? 'Resume' : 'Pause';
    pauseFab.title = fabLabel;
    pauseFab.setAttribute('aria-label', fabLabel);
}

    updateThinkingDots();

    if (paused) {
        boardEl.setAttribute(
            'aria-label',
            'Game paused. Click board or press P to resume.'
        );
        boardEl.style.cursor = 'pointer';
        boardEl.style.pointerEvents = 'auto';
    } else {
        boardEl.removeAttribute('aria-label');
        boardEl.style.cursor = '';
        boardEl.style.pointerEvents = '';
    }
}
            function runStartCountdown(onComplete) {
    if (!countdownOverlay || !countdownNumberEl) {
        onComplete();
        return;
    }

    clearInterval(countdownInterval);

    const sequence = ['3', '2', '1', 'Go!'];
    let idx = 0;

    boardEl.classList.add('countdown-active');
    countdownNumberEl.textContent = sequence[idx];
    countdownOverlay.classList.add('active');

    countdownInterval = setInterval(() => {
        idx++;
        if (idx < sequence.length) {
            countdownNumberEl.textContent = sequence[idx];
        } else {
            clearInterval(countdownInterval);
            countdownOverlay.classList.remove('active');
            boardEl.classList.remove('countdown-active');
            onComplete();
        }
    }, 1000);
}
               
            function startTimer() {
                clearInterval(timerInterval);
                timerInterval = setInterval(() => {
                    // Puzzles hide the clocks and are not timed.
                    if (paused || gameOver || dailyPuzzleMode) return;

            // fix: in AI mode, tick only ONE clock exclusively
            if (gameMode === 'ai') {
                if (turn === playerColor) {
                    // Human's turn — only tick human's clock
                    if (playerColor === 'white' && whiteTime > 0) whiteTime--;
                    else if (playerColor === 'black' && blackTime > 0) blackTime--;
                } else if (aiThinking) {
                    // AI's turn — only tick AI's clock while actually thinking
                    if (playerColor === 'white' && blackTime > 0) blackTime--;
                    else if (playerColor === 'black' && whiteTime > 0) whiteTime--;
                } else {
                    return; // AI turn but not yet thinking (transition gap), don't tick
                }
            } else {
                // PvP — tick only the active player's clock
                if (turn === 'white' && whiteTime > 0) whiteTime--;
                else if (turn === 'black' && blackTime > 0) blackTime--;
            }

            renderClocks();

            // Low-time alert: play check.wav once per player when time crosses into <=30s
            if (soundEnabled) {
                if (!whiteAlertFired && whiteTime > 0 && whiteTime <= 30) {
                    whiteAlertFired = true;
                    sounds.check.currentTime = 0;
                    sounds.check.play().catch(() => { });
                }
                if (!blackAlertFired && blackTime > 0 && blackTime <= 30) {
                    blackAlertFired = true;
                    sounds.check.currentTime = 0;
                    sounds.check.play().catch(() => { });
                }
            }

            if (turn === 'white' && whiteTime === 0) {
                flagFall('white');
            } else if (turn === 'black' && blackTime === 0) {
                flagFall('black');
            }
        }, 1000);
    }

    // This page's clock reached zero. The server keeps its own clock and records
    // the result, so ask it. While its clock still has time, the timer runs on
    // from the server's figures and this is called again at the next zero.
    async function flagFall(color) {
        if (flagFallPending || gameOver) return;
        flagFallPending = true;
        try {
            const data = await post('/api/timeout/', {});
            if (data.valid) {
                const loser = data.winner ? (data.winner === 'white' ? 'black' : 'white') : color;
                endGame('timeout', loser);
            } else if (data.white_time !== undefined) {
                whiteTime = data.white_time;
                blackTime = data.black_time;
                renderClocks();
            } else if (data.httpStatus !== 409) {
                // No game there, or one that is already over: show the flag fall.
                // (After a 409 the next tick simply asks again.)
                endGame('timeout', color);
            }
        } catch (e) {
            // A server without this URL answers with a page, and offline there is
            // no answer at all. End the game here, as the page always did.
            endGame('timeout', color);
        } finally {
            flagFallPending = false;
        }
    }

    function toggleBoardOrientation() {
        flipped = !flipped;
        turnBoard();
    }

    // Flipping turns the board round on screen first (.turning in play.css)
    // and then draws it the other way up. buildBoard() cancels a turn that
    // is still going, so any other redraw wins.
    function turnBoard() {
        clearTimeout(turnTimer);
        boardEl.classList.remove('turning');
        if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && boardEl.children.length) {
            boardEl.classList.add('turning');
            const seconds = parseFloat(getComputedStyle(boardEl).animationDuration);
            if (seconds > 0) {
                turnTimer = setTimeout(buildBoard, seconds * 1000);
                return;
            }
        }
        buildBoard();
    }

    async function pauseGame(extra) {
        if (paused) return;
        aiFailures = 0;
        const d = await post('/api/pause/', { pause: true }, extra);
        // An error body has none of these fields; leave the clocks as they are.
        if (d.paused === undefined) return;
        paused = d.paused;
        if (d.white_time !== undefined) whiteTime = d.white_time;
        if (d.black_time !== undefined) blackTime = d.black_time;
        updatePauseUI();
        renderClocks();
    }

    async function resumeGame() {
        try {
            const d = await post('/api/pause/', { pause: false });

            paused = false;

            if (d.white_time !== undefined) {
                whiteTime = d.white_time;
            }

            if (d.black_time !== undefined) {
                blackTime = d.black_time;
            }

            updatePauseUI();
            renderClocks();

            clearInterval(timerInterval);
            startTimer();

            boardEl.classList.remove('paused');

            queueAIMoveIfNeeded();

        } catch (e) {
            console.error("Resume failed", e);
        }
    }

    /* ==========================================================
    WELCOME & CONFIRMATION LOGIC
    ========================================================== */
    let confirmCallback = null;
    let confirmCancel = null;
    // tone is 'danger' for a question that gives something up and 'gold' for
    // the rest. It goes on the title as data-tone, for the stylesheet.
    function showConfirm(title, msg, callback, tone = 'danger', onCancel = null) {
        if (confirmTitle) {
            confirmTitle.textContent = title;
            confirmTitle.dataset.tone = tone;
        }
        if (confirmMessage) confirmMessage.innerHTML = msg;
        // The time and difficulty pickers belong to the new-AI-game question only.
        ['confirmTimerContainer', 'confirmDifficultyContainer'].forEach(id => {
            const box = document.getElementById(id);
            if (box) box.style.display = 'none';
        });
        confirmCallback = callback;
        confirmCancel = onCancel;
        boardEl.classList.add('confirm-open');
        confirmOverlay.classList.add('active');
    }

    function newGameForfeits() {
        return ratedGame && gameMode === 'ai' && !gameOver && halfMoves >= 5;
    }

    // Added to the "start over?" questions when saying yes costs a rated game.
    function forfeitNote() {
        return newGameForfeits()
            ? '<br><br><b>This game is rated. Leaving it now counts as a loss.</b>'
            : '';
    }

    // Resolves true when the game on the board may be replaced. The buttons that
    // already ask "start over?" set forfeitAccepted; any other way in is asked here.
    function confirmForfeit() {
        if (!newGameForfeits() || forfeitAccepted) return Promise.resolve(true);
        return new Promise(resolve => {
            showConfirm(
                "Abandon Game?",
                "Your game against the AI is rated. Starting a new game now counts it as a loss.<br>Start a new game anyway?",
                () => { forfeitAccepted = true; resolve(true); },
                'danger',
                () => resolve(false)
            );
        });
    }

    function showSideSelectionModal(onChoose) {
        const modal = document.getElementById('sideModal');
        modal.style.display = 'flex';

        function pick(side) {
            modal.style.display = 'none';
            document.getElementById('chooseWhite').onclick = null;
            document.getElementById('chooseBlack').onclick = null;
            document.getElementById('chooseRandom').onclick = null;
            onChoose(side);
        }

        document.getElementById('chooseWhite').onclick = () => pick('white');
        document.getElementById('chooseBlack').onclick = () => pick('black');
        document.getElementById('chooseRandom').onclick = () =>
            pick(Math.random() < 0.5 ? 'white' : 'black');
    }

    function requestNewGame(mode) {
        showConfirm(
            "Abandon Game?",
            "Your current progress will be lost.<br>Are you sure you want to start a new game?" + forfeitNote(),
            () => {
                forfeitAccepted = true;
                const diff = document.getElementById('confirmDifficultySelect').value;
                // "minutes|increment"; startNewGame splits it
                const timeControl = document.getElementById('confirmTimerSelect').value;
                if (mode === 'ai') {
                    showSideSelectionModal(side => startNewGame('ai', side, diff, null, timeControl));
                } else {
                    startNewGame('pvp', 'white', diff, null, timeControl);
                }
            },
            'danger'
        );

        // Offer the time control of the game being left, when the list has it.
        const timerSelect = document.getElementById('confirmTimerSelect');
        const current = `${selectedMins}|${selectedIncrement}`;
        if (Array.from(timerSelect.options).some(o => o.value === current)) {
            timerSelect.value = current;
        }
        document.getElementById('confirmTimerContainer').style.display = 'block';
        document.getElementById('confirmDifficultyContainer').style.display = (mode === 'ai') ? 'block' : 'none';
    }

    async function offerDraw() {
        if (paused || gameOver || gameMode !== 'pvp') return;
        const offeringPlayer = turn === 'white' ? 'White' : 'Black';
        const receivingPlayer = turn === 'white' ? 'Black' : 'White';

        showConfirm(
            "Offer Draw?",
            `As <b>${offeringPlayer}</b>, do you want to offer a draw to ${receivingPlayer}?`,
            async () => {
                drawMessage.textContent = `${offeringPlayer} offers a draw. ${receivingPlayer}, do you accept?`;
                drawOverlay.classList.add('active');
                await pauseGame();
            },
            'gold'
        );
    }

    async function startNewGame(mode, pColor = 'white', difficulty = 'medium', fen = null, timeLimitMins = null, overrideNames = null, isPuzzle = false) {
        if (!(await confirmForfeit())) return false;
        evaluationCache = {};
        maxWhiteTime = 0;
        maxBlackTime = 0;
        if (!isPuzzle) {
            dailyPuzzleMode = false;
            currentPuzzle = null;
            currentPuzzleFen = null;
            puzzleAnalyzing = false;
            if (stockfishWorker) {
                stockfishWorker.terminate();
                stockfishWorker = null;
            }
            if (restartPuzzleBtn) restartPuzzleBtn.style.display = 'none';
            if (hintPuzzleBtn) hintPuzzleBtn.style.display = 'none';
            const puzzleStreakEl = document.getElementById("puzzle-streak-counter");
            if (puzzleStreakEl) puzzleStreakEl.style.display = "none";
        } else {
            puzzleMoves = [];
        }
        const analysisPanel = document.getElementById('postGameAnalysisPanel');
        if (analysisPanel) analysisPanel.style.display = 'none';
        const tbody = document.getElementById('postGameAnalysisTableBody');
        if (tbody) tbody.innerHTML = '';
        replayMode = false;
        // Show clocks for normal games. A puzzle has hidden them and is not timed.
        if (!isPuzzle) {
            document.getElementById("whiteClock").style.display = "";
            document.getElementById("blackClock").style.display = "";
        }

        const streakCounter =
            document.getElementById("streak-counter");

        if (streakCounter) {
            streakCounter.style.display = "none";
        }

        replayMode = false;
        viewingPastState = false;
        stepperIndex = 0;
        gameFens = [];

        if (autoReplayInterval) {
            clearInterval(autoReplayInterval);
            autoReplayInterval = null;
        }

        if (playReplayBtn) {
            playReplayBtn.textContent = '▶';
        }

        if (replayControls) {
            replayControls.classList.add('hidden');
        }
        // Move the AI request sequence on so a request from the old game is ignored
        aiRequestSeq++;
        aiFailures = 0;
        analysisRequestSeq++;
        aiThinking = false;
        premoveQueue = [];
        refreshPremoveHighlight();

        clearTimeout(pgnDownloadTimeout);
        clearTimeout(fenCopyTimeout);

        if (copyPgnBtn) {
            copyPgnBtn.textContent = 'Export as PGN';
        }

        if (copyFenBtn) {
            copyFenBtn.textContent = 'Copy FEN';
        }
        // Clear celebration effects
        const overlay = document.getElementById('gameOverOverlay');
        overlay.classList.remove('game-over-celebration');
        const confettiContainer = overlay.querySelector('.confetti-container');
        if (confettiContainer) {
            confettiContainer.remove();
        }

        const normalizeName = (name, fallback) => (name || fallback).trim().slice(0, 17);
        let wName = normalizeName(
            overrideNames ? overrideNames.white : document.getElementById('whiteNameInput')?.value,
            'White'
        );
        let bName = normalizeName(
            overrideNames ? overrideNames.black : document.getElementById('blackNameInput')?.value,
            'Black'
        );
        if (mode === 'ai') {
            // The server writes the bot's name over the AI's side, so send the
            // player's name for both and it survives whichever colour they get.
            // On a rematch the player's name is on the side they just played.
            const human = (overrideNames && pColor === 'black') ? bName : wName;
            wName = human;
            bName = human;
        }
        let currentMins = pickedMins;
        let currentInc = pickedIncrement;

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

        // A puzzle has no clock on the page, so it gets the longest one the server accepts.
        const timeLimit = isPuzzle ? 18000 : currentMins * 60;
        const increment = isPuzzle ? 0 : currentInc;

        const payload = {
            mode: mode,
            player_color: pColor,
            white_name: wName,
            black_name: bName,
            difficulty: difficulty,
            time_limit: timeLimit,
            increment: increment,
            opening: document.getElementById('welcomeOpeningSelect')?.value || '',
        };

        const fenValue = (fen && fen.trim()) ? fen.trim() : null;
        if (fenValue) payload.fen = fenValue;

        if (fenError) fenError.textContent = '';
        if (welcomeFenError) welcomeFenError.textContent = '';

        const d = await post('/api/new-game/', payload);

        if (d.valid === false || !d.board) {
            const message = d.message || d.error || 'Unable to start a new game.';
            if (fenError) fenError.textContent = message;
            if (welcomeFenError && welcomeOverlay?.classList.contains('active')) {
                welcomeFenError.textContent = message;
            }
            showStatus(message, true);
            return false;
        }

        // Saved only once the game exists, and in the server's full six-field
        // form, which is what chess.js needs to replay the moves.
        localStorage.setItem('checkora_starting_fen', d.fen || fenValue || DEFAULT_START_FEN);

        board = d.board;
        turn = d.current_turn;
        if (d.fen) liveFen = d.fen;
        livePgn = d.pgn || '';
        ratedGame = d.rated === true;
        halfMoves = 0;
        forfeitAccepted = false;
        paused = false;
        gameOver = false;
        fallenKing = null;
        whiteAlertFired = false;
        blackAlertFired = false;
        maxWhiteTime = Math.max(d.white_time || 0, Math.round(selectedMins * 60));
        maxBlackTime = Math.max(d.black_time || 0, Math.round(selectedMins * 60));
        incrementGameCounter();

        gameStartTime = Date.now();
        
        if (!isPuzzle) {
            gameMode = d.mode;
        }
        playerColor = d.player_color || 'white';
        currentDifficulty = d.difficulty || difficulty;
        if (resignBtn) {
            resignBtn.style.display = 'block';
            resignBtn.hidden = false;
        }
        if (pauseBtn) pauseBtn.style.display = '';
        if (drawBtn) drawBtn.style.display = (gameMode === 'pvp') ? 'block' : 'none';
        if (newPvPBtn) newPvPBtn.style.display = 'none';
        if (newAIBtn) newAIBtn.style.display = 'none';
        if (dailyPuzzleBtn) dailyPuzzleBtn.style.display = 'none';
        if (newFenBtn) newFenBtn.style.display = 'none';
        if (gameMode === 'ai') {
            flipped = (playerColor === 'black');
        } else {
            flipped = false;
        }
        boardOrientationSet = true;

        if (modeBadge) {
            if (isPuzzle) {
                modeBadge.textContent = 'DAILY PUZZLE';
            } else {
                modeBadge.textContent =
                    gameMode === 'ai' ? 'VS AI' : 'PVP';
            }
            modeBadge.style.display = 'inline-block';
        }

        const emotePanel = document.getElementById('emotePanel');
        if (emotePanel) {
            emotePanel.style.display = gameMode === 'pvp' ? 'block' : 'none';
        }
        movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
        wCapEl.innerHTML = bCapEl.innerHTML = '';
        // The last game's result is still in the status line.
        showStatus('Game started', false);
        lastMove = null;
        highlightedSquare = null;
        selected = null;
        hints = [];
        await loadGame();
        // Apply active state after UI reload
        if (!isPuzzle) {
            updateModeButtonsUI(gameMode);
        }
        paused = false;
        updatePauseUI();

        if (!isPuzzle) {
            // Hold the clocks and lock the board until the countdown finishes.
            // The server clock is held too, or the side to move pays for the countdown.
            clearInterval(timerInterval);
            const holdServerClock = countdownOverlay && countdownNumberEl;
            if (holdServerClock) post('/api/pause/', { pause: true }).catch(() => { });
            const beginCountdown = () => runStartCountdown(async () => {
                // If the player paused in the meantime (tab hidden), resuming releases the clock.
                if (holdServerClock && !paused) {
                    await post('/api/pause/', { pause: false }).catch(() => { });
                }
                startTimer();
                // Auto-trigger AI if it's their turn
                if (gameMode === 'ai' && turn !== playerColor) {
                    queueAIMoveIfNeeded();
                }
            });
            // A first-time player reads the tour before the clock matters:
            // endTour starts the countdown. The tour is asked for here as well
            // as by the callers, so a held countdown never waits for nothing.
            if (isTourDue()) {
                afterTour = beginCountdown;
                maybeStartTourAfterWelcomeCloses();
            } else {
                beginCountdown();
            }
        }

        return true;
    }


    if (nextReplayBtn) {
        nextReplayBtn.onclick = () => {
            if (replayIndex < replayMoves.length) {
                replayIndex++;
                goToReplayMove(replayIndex);
            }
        };
    }

    if (prevReplayBtn) {
        prevReplayBtn.onclick = () => {
            if (replayIndex > 0) {
                replayIndex--;
                goToReplayMove(replayIndex);
            }
        };
    }

    if (firstReplayBtn) {
        firstReplayBtn.onclick = () => {
            replayIndex = 0;

            goToReplayMove(0);
        };
    }

    if (lastReplayBtn) {
        lastReplayBtn.onclick = () => {
            replayIndex = replayMoves.length;
            goToReplayMove(replayIndex);
        };
    }
    if (replayGameBtn) {

        replayGameBtn.onclick = () => {

            // hide popup
            gameOverOverlay.classList.remove('active');

            // show replay controls
            replayControls.classList.remove('hidden');

            // stop old replay
            if (autoReplayInterval) {
                clearInterval(autoReplayInterval);
                autoReplayInterval = null;
            }
            replayIndex = 0;
            // reset replay
            goToReplayMove(0);

            // start autoplay
            playReplayBtn.textContent = '⏸';

            // 1. Define a function that plays a single move and schedules the next one
            const playNextMove = () => {
                // Check if we reached the end of the game
                if (replayIndex >= replayMoves.length) {
                    autoReplayInterval = null;
                    playReplayBtn.textContent = '▶';
                    return;
                }

                // Advance the index and play the move
                replayIndex++;
                goToReplayMove(replayIndex);
                // Schedule the NEXT move 1000ms (1 second) from now.
                autoReplayInterval = setTimeout(playNextMove, 1000);
            };

            // 2. Kick off the chain reaction
            autoReplayInterval = setTimeout(playNextMove, 1000);
        };
    }

    if (playReplayBtn) {
        playReplayBtn.onclick = () => {

            if (autoReplayInterval) {
                isAutoReplaying = false;
                clearTimeout(autoReplayInterval);
                autoReplayInterval = null;
                playReplayBtn.textContent = '▶';
                return;
            }
            playReplayBtn.textContent = '⏸';
            isAutoReplaying = true;

            // 1. Define the relay race function
            const playNextMove = () => {
                if (!isAutoReplaying) return;

                if (replayIndex >= replayMoves.length) {
                    autoReplayInterval = null;
                    isAutoReplaying = false;
                    playReplayBtn.textContent = '▶';
                    return;
                }

                replayIndex++;
                goToReplayMove(replayIndex);

                // Schedule the next move only after this one is triggered
                if (isAutoReplaying) {
                    autoReplayInterval = setTimeout(playNextMove, 1000);
                }
            };

            // 2. Kick off the chain reaction
            if (isAutoReplaying) {
                autoReplayInterval = setTimeout(playNextMove, 1000);
            }
        };

        const stepperFirst = document.getElementById('stepperFirst');
        const stepperPrev = document.getElementById('stepperPrev');
        const stepperNext = document.getElementById('stepperNext');
        const stepperLast = document.getElementById('stepperLast');
        const resumeGameBtn = document.getElementById('resumeGameBtn');

        if (stepperFirst) {
            stepperFirst.onclick = () => {
                stepperIndex = 0;
                updateStepperUI();
            };
        }
        if (stepperPrev) {
            stepperPrev.onclick = () => {
                if (stepperIndex > 0) {
                    stepperIndex--;
                    updateStepperUI();
                }
            };
        }
        if (stepperNext) {
            stepperNext.onclick = () => {
                if (stepperIndex < gameFens.length - 1) {
                    stepperIndex++;
                    updateStepperUI();
                }
            };
        }
        if (stepperLast) {
            stepperLast.onclick = () => {
                stepperIndex = gameFens.length - 1;
                updateStepperUI();
            };
        }
        if (resumeGameBtn) {
            resumeGameBtn.onclick = () => {
                stepperIndex = gameFens.length - 1;
                viewingPastState = false;
                updateStepperUI();
            };
        }
    }


    /* ==========================================================
    EVENT LISTENERS
    ========================================================== */
    let selectedPveColor = 'white';

    function prepareWelcomeForPvP(clearAIValue = false) {
        const whiteInput = document.getElementById('whiteNameInput');
        const blackInput = document.getElementById('blackNameInput');
        const errorDiv = document.getElementById('nameError');

        pveOptions.style.display = 'none';
        modeSelection.style.display = 'flex';
        nameInputs.style.display = 'flex';

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
        gameOverOverlay.classList.remove('active');
        gameOverOverlay.classList.remove('game-over-celebration');
        const confettiContainer = gameOverOverlay.querySelector('.confetti-container');
        if (confettiContainer) {
            confettiContainer.remove();
        }
    }

    function openWelcomeForNewGame() {
        dismissGameOverOverlay();
        prepareWelcomeForPvP(true);

        const whiteInput = document.getElementById('whiteNameInput');
        const blackInput = document.getElementById('blackNameInput');
        if (whiteInput) {
            whiteInput.value = currentWhiteName || '';
        }
        if (blackInput) {
            const aiNames = ['AI', 'ai'];
            blackInput.value = aiNames.includes(currentBlackName) ? '' : (currentBlackName || '');
        }
        if (welcomeFenInput) welcomeFenInput.value = '';
        if (welcomeFenError) welcomeFenError.textContent = '';

        selectedPveColor = 'white';
        pveOptions?.querySelectorAll('.color-choice').forEach(btn => {
            const isWhite = btn.dataset.color === 'white';
            btn.classList.toggle('active', isWhite);
        });

        if (welcomeResumeBtn && gameOver) {
            welcomeResumeBtn.style.display = 'none';
        }
        welcomeOverlay.classList.add('active');
    }

    if (welcomeFenInput) {
        welcomeFenInput.addEventListener('keydown', async (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            const fenValue = welcomeFenInput.value?.trim();
            if (!fenValue) return;
            const isAIMode = pveOptions.style.display !== 'none';
            const mode = isAIMode ? 'ai' : 'pvp';
            const pColor = isAIMode ? selectedPveColor : 'white';
            const diff = isAIMode
                ? (document.getElementById('welcomeDifficultySelect')?.value || 'medium')
                : 'medium';
            if (welcomeFenError) welcomeFenError.textContent = '';
            const started = await startNewGame(mode, pColor, diff, fenValue);
            if (!started) return;
            welcomeOverlay.classList.remove('active');
                    maybeStartTourAfterWelcomeCloses();
            gameLayout.style.visibility = 'visible';
        });
    }

    if (welcomePvPBtn) welcomePvPBtn.onclick = async () => {
        if (!validatePlayerNames()) return;
        const fen = welcomeFenInput?.value?.trim() || null;
        const started = await startNewGame('pvp', 'white', 'medium', fen);
        if (!started) return;
        welcomeOverlay.classList.remove('active');
                    maybeStartTourAfterWelcomeCloses();
        gameLayout.style.visibility = 'visible';
    };

    if (welcomeDailyPuzzleBtn) {
        welcomeDailyPuzzleBtn.onclick = async () => {

            if (await startDailyPuzzle() === false) return;

            welcomeOverlay.classList.remove('active');
                    maybeStartTourAfterWelcomeCloses();
            gameLayout.style.visibility = 'visible';
        };
    }

    if (welcomeAIBtn) welcomeAIBtn.onclick = () => {
        modeSelection.style.display = 'none';
        pveOptions.style.display = 'flex';

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

        if (errorDiv) {
            errorDiv.style.display = 'none';
        }

        nameInputs.style.display = 'flex';
    };


    if (backToModes) backToModes.onclick = () => {
        prepareWelcomeForPvP(false);

        const whiteInput = document.getElementById('whiteNameInput');
        const blackInput = document.getElementById('blackNameInput');
        const errorDiv = document.getElementById('nameError');

        if (whiteInput) {
            whiteInput.placeholder = 'White Player Name';
            whiteInput.classList.remove('input-error');
        }

        if (blackInput) {
            blackInput.style.display = 'block';
            blackInput.classList.remove('input-error');
        }

        if (errorDiv) {
            errorDiv.style.display = 'none';
        }
    };
    if (pveOptions) {
        const colorBtns = pveOptions.querySelectorAll('.color-choice');
        colorBtns.forEach(btn => {
            btn.onclick = () => {
                colorBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                selectedPveColor = btn.dataset.color;
            };
        });
    }
    if (startAIBtn) startAIBtn.onclick = async () => {
        const wNameInput = document.getElementById('whiteNameInput');
        const errorDiv = document.getElementById('nameError');

        const playerName = wNameInput?.value.trim();

        // Validate: AI mode only needs ONE name
        if (!playerName) {
            if (errorDiv) {
                errorDiv.style.display = 'block';
                errorDiv.textContent = ' Please enter your name';
            }
            if (wNameInput) {
                wNameInput.classList.add('input-error');
            }
            return;
        }

        // Clear error
        if (errorDiv) errorDiv.style.display = 'none';
        if (wNameInput) {
            wNameInput.classList.remove('input-error');
        }

        const diff = document.getElementById('welcomeDifficultySelect').value;
        const fen = welcomeFenInput?.value?.trim() || null;
        const started = await startNewGame('ai', selectedPveColor, diff, fen);
        if (!started) return;
        welcomeOverlay.classList.remove('active');
                    maybeStartTourAfterWelcomeCloses();
        gameLayout.style.visibility = 'visible';
    };

    if (copyPgnBtn) copyPgnBtn.onclick = async () => {
        // Once a game is over the server may not have it any more, so use
        // the PGN that came with the last move.
        const pgn = livePgn || (await get('/api/state/')).pgn;

        if (pgn) {
            const blob = new Blob([pgn], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            const wName = whiteNameLabel ? whiteNameLabel.textContent : 'White';
            const bName = blackNameLabel ? blackNameLabel.textContent : 'Black';
            const date = new Date().toISOString().split('T')[0];

            a.download = `checkora_${wName}_vs_${bName}_${date}.pgn`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            copyPgnBtn.textContent = 'Downloaded!';

            clearTimeout(pgnDownloadTimeout);

            pgnDownloadTimeout = setTimeout(() => {
                copyPgnBtn.textContent = 'Export as PGN';
            }, 2000);
        }
    };

    if (copyFenBtn) copyFenBtn.onclick = () => {
        navigator.clipboard.writeText(liveFen);

        copyFenBtn.textContent = 'Copied!';
        clearTimeout(fenCopyTimeout);

        fenCopyTimeout = setTimeout(() => {
            copyFenBtn.textContent = 'Copy FEN';
        }, 2000);
    };

    if (welcomeResumeBtn) welcomeResumeBtn.onclick = async () => {
        const data = await post('/api/resume/', {});
        if (!data.valid) {
            welcomeResumeBtn.style.display = 'none';
            return;
        }
        forfeitAccepted = false;
        welcomeOverlay.classList.remove('active');
                    maybeStartTourAfterWelcomeCloses();
        gameLayout.style.visibility = 'visible';
        paused = false;
        updatePauseUI();
        startTimer();
        queueAIMoveIfNeeded();
    };

    if (confirmYesBtn) confirmYesBtn.onclick = () => {
        boardEl.classList.remove('confirm-open');

        confirmOverlay.classList.remove('active');

        // Cleared first: the callback may open the next question.
        const callback = confirmCallback;
        confirmCallback = null;
        confirmCancel = null;
        if (callback) callback();
    };
    if (confirmNoBtn) confirmNoBtn.onclick = () => {
        boardEl.classList.remove('confirm-open');

        confirmOverlay.classList.remove('active');

        const cancel = confirmCancel;
        confirmCallback = null;
        confirmCancel = null;
        if (cancel) cancel();
    };

    if (newPvPBtn) newPvPBtn.onclick = () => {
        // Clear any lingering celebration effects
        const overlay = document.getElementById('gameOverOverlay');
        overlay.classList.remove('game-over-celebration');
        const confettiContainer = overlay.querySelector('.confetti-container');
        if (confettiContainer) {
            confettiContainer.remove();
        }

        showConfirm(
            "Abandon Game?",
            "Your current progress will be lost.<br>Are you sure you want to start a new game?" + forfeitNote(),
            () => {
                forfeitAccepted = true;
                openWelcomeForNewGame();
            },
            'danger'
        );
    };

    if (newAIBtn) newAIBtn.onclick = () => {
        // Clear any lingering celebration effects
        const overlay = document.getElementById('gameOverOverlay');
        overlay.classList.remove('game-over-celebration');
        const confettiContainer = overlay.querySelector('.confetti-container');
        if (confettiContainer) {
            confettiContainer.remove();
        }

        requestNewGame('ai');
    };
    if (dailyPuzzleBtn)
        dailyPuzzleBtn.onclick = async () => {

            showConfirm(
                "Start Daily Puzzle?",
                "Your current game will be lost." + forfeitNote(),
                async () => {

                    forfeitAccepted = true;
                    await startDailyPuzzle();

                },
                "gold"
            );
        };

    // Also the "try again" after a wrong move, so a puzzle opened from the
    // puzzle list restarts itself and not the daily one.
    async function restartCurrentPuzzle() {
        if (!currentPuzzle) return;

        puzzleMoveIndex = 0;
        clearPuzzleHints();

        await startNewGame(
            "ai",
            "white",
            currentPuzzle.difficulty || "medium",
            currentPuzzle.fen,
            null,
            null,
            true
        );
        currentPuzzleFen = currentPuzzle.fen;
        expectedMoveEval = null;
        initStockfish();
        precalculateExpectedMoveEval();

        showStatus(
            "Puzzle Restarted",
            false
        );
    }

    if (restartPuzzleBtn) restartPuzzleBtn.onclick = restartCurrentPuzzle;

    if (hintPuzzleBtn)
        hintPuzzleBtn.onclick = () => {
            showPuzzleHint();
        };

    if (newFenBtn) newFenBtn.onclick = () => {
        showConfirm(
            "Load from FEN?",
            "Your current progress will be lost.<br>Do you want to continue?" + forfeitNote(),
            () => {
                forfeitAccepted = true;
                if (fenError) fenError.textContent = '';
                if (fenInput) fenInput.value = '';
                fenOverlay.classList.add('active');
            },
            'danger'
        );
    };

    if (fenStartBtn) fenStartBtn.onclick = async () => {
        const fenValue = fenInput?.value?.trim() || '';
        if (!fenValue) {
            if (fenError) fenError.textContent = 'Please enter a FEN string.';
            return;
        }

        const mode = gameMode === 'ai' ? 'ai' : 'pvp';
        const pColor = mode === 'ai' ? playerColor : 'white';
        const diff = mode === 'ai' ? currentDifficulty : 'medium';
        const started = await startNewGame(mode, pColor, diff, fenValue);
        if (!started) return;

        fenOverlay.classList.remove('active');
        welcomeOverlay.classList.remove('active');
                    maybeStartTourAfterWelcomeCloses();
        gameLayout.style.visibility = 'visible';
    };

    if (fenCancelBtn) fenCancelBtn.onclick = () => {
        fenOverlay.classList.remove('active');
    };
    if (fenInput) {
        fenInput.addEventListener('keydown', async (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            fenStartBtn?.click();
        });
    }

    if (pauseBtn) pauseBtn.onclick = () => paused ? resumeGame() : pauseGame();
    if (flipBtn) flipBtn.onclick = toggleBoardOrientation;

    // Ways out of the promotion dialog besides choosing a piece.
    if (promoOverlay) {
        promoOverlay.addEventListener('click', (e) => {
            if (e.target === promoOverlay) cancelPromotion();
        });
    }
    const promoCancelBtn = document.getElementById('promoCancelBtn');
    if (promoCancelBtn) promoCancelBtn.onclick = cancelPromotion;

    const blindfoldBtn = document.getElementById('blindfoldBtn');
    if (blindfoldBtn) {
        blindfoldBtn.onclick = () => {
            blindfoldMode = !blindfoldMode;
            illegalMoveCount = 0;
            blindfoldBtn.textContent = 'Blindfold: ' + (blindfoldMode ? 'ON' : 'OFF');
            document.body.classList.toggle('blindfold-mode', blindfoldMode);
            const msg = `Blindfold mode ${blindfoldMode ? 'ON' : 'OFF'}`;
            showStatus(msg, false);
            setTimeout(() => {
                const gameStatusEl = document.getElementById("game-status");
                if (gameStatusEl && gameStatusEl.textContent === msg) {
                    showStatus('', false);
                }
            }, 2000);
        };
    }

    if (resignBtn) resignBtn.onclick = () => {
        if (!gameOver) {
            if (gameMode === 'pvp') {
                const modal = document.getElementById('resignModal');
                if (modal) {
                    modal.style.display = 'flex';
                    
                    const hideModal = () => {
                        modal.style.display = 'none';
                        document.getElementById('resignWhite').onclick = null;
                        document.getElementById('resignBlack').onclick = null;
                        document.getElementById('resignCancel').onclick = null;
                    };
                    
                    const confirmResign = (side) => {
                        hideModal();
                        showConfirm("Resign?", `Are you sure ${side} wants to resign?`, async () => {
                            try {
                                const result = await post('/api/resign/', { resigning_player: side });
                                if (result.valid) {
                                    if (soundEnabled) { sounds.draw.currentTime = 0; sounds.draw.play().catch(() => { }); }
                                    const loserColor = result.winner === 'white' ? 'black' : 'white';
                                    endGame('resign', loserColor);
                                } else {
                                    showStatus('Resign failed. Please try again.', true);
                                }
                            } catch (_) {
                                showStatus('Resign failed. Please check your connection and try again.', true);
                            }
                        });
                    };
                    
                    document.getElementById('resignWhite').onclick = () => confirmResign('white');
                    document.getElementById('resignBlack').onclick = () => confirmResign('black');
                    document.getElementById('resignCancel').onclick = hideModal;
                }
            } else {
                showConfirm("Resign?", "Are you sure you want to resign?", async () => {
                    try {
                        const result = await post('/api/resign/', {});
                        if (result.valid) {
                            if (soundEnabled) { sounds.draw.currentTime = 0; sounds.draw.play().catch(() => { }); }
                            const loserColor = result.winner === 'white' ? 'black' : 'white';
                            endGame('resign', loserColor);
                        } else {
                            showStatus('Resign failed. Please try again.', true);
                        }
                    } catch (_) {
                        showStatus('Resign failed. Please check your connection and try again.', true);
                    }
                });
            }
        }
    };

    if (drawBtn) drawBtn.onclick = offerDraw;
    if (drawAcceptBtn) drawAcceptBtn.onclick = async () => {
        drawOverlay.classList.remove('active');
        const data = await post('/api/draw/', { action: 'accept' });
        if (data.success) {
            if (soundEnabled) { sounds.draw.currentTime = 0; sounds.draw.play().catch(() => { }); }
            endGame('draw', turn, data.draw_reason);
        } else {
            // The offer paused the game; with no draw it goes on.
            showStatus(data.message || data.error || 'The draw was not accepted.', true);
            resumeGame();
        }
    };
    if (drawDeclineBtn) drawDeclineBtn.onclick = () => {
        drawOverlay.classList.remove('active');
        resumeGame();
    };

    if (gameOverStartBtn) gameOverStartBtn.onclick = () => {
        openWelcomeForNewGame();
    };
    const resRematchBtn = document.getElementById('resRematchBtn');
    if (resRematchBtn) {
        resRematchBtn.onclick = () => {
            dismissGameOverOverlay();
            const mode = gameMode;
            const pColor = playerColor;
            const diff = currentDifficulty;
            const timeLimitString = `${selectedMins}|${selectedIncrement}`;
            startNewGame(mode, pColor, diff, null, timeLimitString, {
                white: currentWhiteName,
                black: currentBlackName
            });
        };
    }
    const resDownloadPgnBtn = document.getElementById('resDownloadPgnBtn');
    if (resDownloadPgnBtn) {
        resDownloadPgnBtn.onclick = () => {
            const originalBtn = document.getElementById('copyPgnBtn');
            if (originalBtn) originalBtn.click();
        };
    }
    if (gameOverExitBtn) gameOverExitBtn.addEventListener('click', () => {
        const confettiContainer = gameOverOverlay.querySelector('.confetti-container');
        if (confettiContainer) confettiContainer.remove();
    });

    // Coordinates are switched in the settings dialog (#modalCoordsToggle).
    // This applies the saved choice when the page loads.
    function initCoordinatesToggle() {
        const savedShowCoords = localStorage.getItem('showCoordinates') !== 'false';
        if (!savedShowCoords && boardEl) {
            boardEl.classList.add('hide-coordinates');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initThemeSwitcher();
            initCoordinatesToggle();
        });
    } else {
        initThemeSwitcher();
        initCoordinatesToggle();
    }

    document.addEventListener('visibilitychange', async () => {
        // A finished game has nothing to pause, and reloading it would swap the
        // final position for whatever the server holds now.
        if (gameOver) return;
        if (document.hidden) {
            // keepalive lets the request finish if the page is being closed
            pauseGame({ keepalive: true }).catch(() => { });
        } else {
            await handleReconnect();
        }
    });

    window.addEventListener('online', async () => {
        if (!gameOver) {
            await handleReconnect();
        }
    });
    // --- SAN Quick Move Input ---
    const sanMoveInput = document.getElementById('sanMoveInput');
    const sanMoveBtn = document.getElementById('sanMoveBtn');
    const sanMoveError = document.getElementById('sanMoveError');

    let isSanMoveInFlight = false;  

async function handleSanMove() {
    if (!sanMoveInput) return;
    if (isSanMoveInFlight) return;
    let san = sanMoveInput.value.trim();
    if (!san) return;
    
    if (sanMoveError) sanMoveError.style.display = 'none';

    if (paused || gameOver) {
        if (sanMoveError) {
            sanMoveError.textContent = 'Game is not active';
            sanMoveError.style.display = 'block';
        }
        flashBoard();
        return;
    }

    if (gameMode === 'ai' && turn !== playerColor) {
        if (sanMoveError) {
            sanMoveError.textContent = 'Not your turn';
            sanMoveError.style.display = 'block';
        }
        flashBoard();
        return;
    }

    isSanMoveInFlight = true;
    if (sanMoveBtn) sanMoveBtn.disabled = true;

    try {
        const data = await get('/api/state/');
        if (!data.fen) throw new Error("No FEN");
        
        if (!window.Chess) throw new Error("Chess engine not loaded");
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
            flashBoard();
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
        
        const result = await executeMove(fr, fc, tr, tc, promo);
        if (result && result.success) {
            sanMoveInput.value = '';
            sanMoveInput.blur();
        } else {
            if (sanMoveError) {
                sanMoveError.textContent = (result && result.message) ? result.message : 'Move rejected';
                sanMoveError.style.display = 'block';
            }
            flashBoard();
        }
    } catch (err) {
        console.error('SAN Move Error:', err);
        if (sanMoveError) {
            sanMoveError.textContent = 'Error processing move';
            sanMoveError.style.display = 'block';
        }
    } finally {
        isSanMoveInFlight = false;
        if (sanMoveBtn) sanMoveBtn.disabled = false;
    }
}

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
    // ----------------------------

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
                    flashBoard();
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

                if (paused || gameOver) {
                    if (manualMoveError) {
                        manualMoveError.textContent = 'Game is not active';
                        manualMoveError.style.display = 'block';
                    }
                    flashBoard();
                    return;
                }
                if (gameMode === 'ai' && turn !== playerColor) {
                    if (manualMoveError) {
                        manualMoveError.textContent = 'Not your turn';
                        manualMoveError.style.display = 'block';
                    }
                    flashBoard();
                    return;
                }
                const p = board[fr][fc];
                if (!p || pColor(p) !== turn) {
                    if (manualMoveError) {
                        manualMoveError.textContent = 'Invalid piece';
                        manualMoveError.style.display = 'block';
                    }
                    flashBoard();
                    return;
                }

                if (isPromotionMove(fr, fc, tr) && !promo) {
                    if (manualMoveError) {
                        manualMoveError.textContent = 'Promotion piece required (e.g. e7e8q)';
                        manualMoveError.style.display = 'block';
                    }
                    flashBoard();
                    return;
                }

                manualMoveInput.value = '';
                await executeMove(fr, fc, tr, tc, promo);
            }
        });

        manualMoveInput.addEventListener('input', () => {
            if (manualMoveError) manualMoveError.style.display = 'none';
        });
    }

    document.addEventListener('keydown', e => {
        if (e.repeat) return;
        // Ctrl, Cmd and Alt combinations belong to the browser (reload, find, print).
        if (e.ctrlKey || e.metaKey || e.altKey) return;

        if (promoOverlay && promoOverlay.classList.contains('active')) {
            const key = e.key.toLowerCase();
            if (key === 'q' || key === 'r' || key === 'b' || key === 'n') {
                e.preventDefault();
                onPromoChoice(key);
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                cancelPromotion();
            }
            // Ignore all other game commands when promotion is pending
            return;
        }

        const tag = document.activeElement?.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

        if (e.key === '?') {
            e.preventDefault();
            toggleShortcutsModal();
            return;
        }

        if (replayMode) {
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                prevReplayBtn?.click();
                return;
            }
            if (e.key === 'ArrowRight') {
                e.preventDefault();
                nextReplayBtn?.click();
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                firstReplayBtn?.click();
                return;
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                lastReplayBtn?.click();
                return;
            }
        }

        const key = e.key.toLowerCase();
        const hasBlockingOverlay =
            (shareModal?.style.display === 'flex') ||
            (rulebookModal?.style.display === 'flex') ||
            fenOverlay?.classList.contains('active') ||
            confirmOverlay?.classList.contains('active') ||
            drawOverlay?.classList.contains('active') ||
            gameOverOverlay?.classList.contains('active') ||
            welcomeOverlay?.classList.contains('active') ||
            leaveConfirmOverlay?.classList.contains('active') ||
            shortcutsModal?.classList.contains('active') ||
            themeSettingsModal?.classList.contains('active') ||
            document.getElementById('sideModal')?.style.display === 'flex' ||
            document.getElementById('resignModal')?.style.display === 'flex';

        // Allow Escape to close overlays or mobile panel
        if (e.key === 'Escape') {
            const mobilePanel = document.getElementById('mobilePanel');
            const toggleBtn = document.getElementById('mobileControlsToggle');
            if (mobilePanel && mobilePanel.classList.contains('active')) {
                mobilePanel.classList.remove('active');
                if (toggleBtn) {
                    toggleBtn.setAttribute('aria-expanded', 'false');
                }
            }
        }

        if (hasBlockingOverlay && key !== 'escape') {
            return;
        }

        if ((key === 'm' || e.key === '/') && sanMoveInput) {
            e.preventDefault();
            sanMoveInput.focus();
        } else if (key === 'f' && flipBtn) {
            e.preventDefault();
            flipBtn.click();
        } else if (key === 'r' && resignBtn) {
            e.preventDefault();
            resignBtn.click();
        } else if (key === 'd' && drawBtn && drawBtn.style.display !== 'none' && !drawBtn.disabled) {
            e.preventDefault();
            drawBtn.click();
        } else if (key === 'p' && pauseBtn && pauseBtn.style.display !== 'none') {
            e.preventDefault();
            pauseBtn.click();
        } else if (key === 'n' && newPvPBtn) {
            e.preventDefault();
            newPvPBtn.click();

        } else if (key === 'a' && newAIBtn) {
            e.preventDefault();
            newAIBtn.click();
        } else if (key === 'h') {
            e.preventDefault();
            if (shouldConfirmLeave()) {
                openLeaveConfirm();
            } else {
                window.location.href = '/';
            }

        } else if (key === 'escape') {
            e.preventDefault();

            if (shortcutsModal?.classList.contains('active')) {
                closeShortcutsModal();
            }

            if (shareModal?.style.display === 'flex') {
                shareModal.style.display = 'none';
            }

            if (rulebookModal?.style.display === 'flex') {
                rulebookModal.style.display = 'none';
            }

            if (fenOverlay?.classList.contains('active')) {
                fenOverlay.classList.remove('active');
            }

            if (leaveConfirmOverlay?.classList.contains('active')) {
                closeLeaveConfirm();
            }
        }
    });
    // Emote Logic
    let emoteCooldown = false;
    document.querySelectorAll('.emote-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            if (gameMode !== 'pvp') return;
            if (emoteCooldown) {
                showStatus('Emote cooldown (1s)', true);
                setTimeout(() => showStatus(''), 1000);
                return;
            }
            emoteCooldown = true;
            setTimeout(() => emoteCooldown = false, 1000);

            const emoteChar = e.currentTarget.getAttribute('data-emote');
            const emoteEl = document.createElement('div');
            const emoteColor = turn;
            emoteEl.className = 'floating-emote ' + (emoteColor === 'white' ? 'white-emote' : 'black-emote');
            emoteEl.textContent = emoteChar;
            const boardOuter = document.querySelector('.board-outer');
            if (boardOuter) {
                boardOuter.appendChild(emoteEl);
                setTimeout(() => emoteEl.remove(), 2000);
            }
        });
    });

    // Leave Game confirmation modal logic
    const leaveConfirmOverlay = document.getElementById('leaveConfirmOverlay');
    const leaveConfirmDialog = document.getElementById('leaveConfirmDialog');
    const leaveConfirmYes = document.getElementById('leaveConfirmYes');
    const leaveConfirmNo = document.getElementById('leaveConfirmNo');
    const shouldConfirmLeave = () => !gameOver && !welcomeOverlay.classList.contains('active');
    let leaveConfirmFocusReturn = null;

    function openLeaveConfirm() {
        if (!leaveConfirmOverlay) return;
        leaveConfirmFocusReturn = document.activeElement;
        leaveConfirmOverlay.classList.add('active');
        leaveConfirmOverlay.setAttribute('aria-hidden', 'false');
        if (typeof announceMove === 'function') {
            announceMove('Confirm navigation to home page');
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
        if (!leaveConfirmOverlay) return;
        leaveConfirmOverlay.classList.remove('active');
        leaveConfirmOverlay.setAttribute('aria-hidden', 'true');
        if (leaveConfirmFocusReturn && typeof leaveConfirmFocusReturn.focus === 'function') {
            leaveConfirmFocusReturn.focus();
        }
        leaveConfirmFocusReturn = null;
    }

    function confirmLeave() {
        window.location.href = '/';
    }

    document.querySelectorAll('a[href="/"]').forEach(link => {
        link.addEventListener('click', (e) => {
            if (shouldConfirmLeave()) {
                e.preventDefault();
                openLeaveConfirm();
            }
        });
    });

    if (leaveConfirmYes) leaveConfirmYes.addEventListener('click', confirmLeave);

    if (leaveConfirmNo) leaveConfirmNo.addEventListener('click', closeLeaveConfirm);

    // ========== Theme & Settings Modal Logic ==========
    const themeSettingsModal = document.getElementById('themeSettingsModal');
    const openThemeModalBtn = document.getElementById('openThemeModalBtn');
    const closeThemeModalBtn = document.getElementById('closeThemeModalBtn');
    const saveThemeSettingsBtn = document.getElementById('saveThemeSettingsBtn');
    let themeModalFocusReturn = null;

    if (openThemeModalBtn && themeSettingsModal) {
        openThemeModalBtn.onclick = () => {
            themeModalFocusReturn = document.activeElement;

            // 1. Sync Board Theme radio
            const currentBoardTheme = document.documentElement.getAttribute('data-board-theme') || 'classic';
            const boardThemeRadio = themeSettingsModal.querySelector(`input[name="boardThemeRadio"][value="${currentBoardTheme}"]`);
            if (boardThemeRadio) boardThemeRadio.checked = true;

            // Sync Piece Style radio
            const savedPieceStyle = localStorage.getItem('pieceStyle');
            const currentPieceStyle = VALID_PIECE_STYLES.includes(savedPieceStyle) ? savedPieceStyle : 'staunton';
            const pieceStyleRadio = themeSettingsModal.querySelector(`input[name="pieceStyleRadio"][value="${currentPieceStyle}"]`);
            if (pieceStyleRadio) pieceStyleRadio.checked = true;

            // 2. Sync Sound Toggle
            const soundToggle = document.getElementById('modalSoundToggle');
            if (soundToggle) soundToggle.checked = soundEnabled;

            // 3. Sync Coordinates Toggle
            const coordsToggle = document.getElementById('modalCoordsToggle');
            const coordsEnabled = localStorage.getItem('showCoordinates') !== 'false';
            if (coordsToggle) coordsToggle.checked = coordsEnabled;

            // 4. Sync Auto-Flip Toggle
            const autoFlipToggle = document.getElementById('modalAutoFlipToggle');
            if (autoFlipToggle) autoFlipToggle.checked = autoFlip;

            // Open the Modal
            themeSettingsModal.classList.add('active');
            themeSettingsModal.setAttribute('aria-hidden', 'false');

            // Move focus to modal close button
            setTimeout(() => {
                if (closeThemeModalBtn) {
                    closeThemeModalBtn.focus();
                }
            }, 50);
        };
    }

    const closeThemeModal = () => {
        if (themeSettingsModal) {
            themeSettingsModal.classList.remove('active');
            themeSettingsModal.setAttribute('aria-hidden', 'true');
            if (themeModalFocusReturn && typeof themeModalFocusReturn.focus === 'function') {
                themeModalFocusReturn.focus();
            }
            themeModalFocusReturn = null;
        }
    };

    if (closeThemeModalBtn) closeThemeModalBtn.onclick = closeThemeModal;
    if (saveThemeSettingsBtn) saveThemeSettingsBtn.onclick = closeThemeModal;

    // Handle Escape key to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && themeSettingsModal && themeSettingsModal.classList.contains('active')) {
            closeThemeModal();
        }
    });

    if (themeSettingsModal) {
        // Close modal on click outside (backdrop)
        themeSettingsModal.addEventListener('click', (e) => {
            if (e.target === themeSettingsModal) {
                closeThemeModal();
            }
        });

        // Handle Board Theme swatch switches
        const boardRadios = themeSettingsModal.querySelectorAll('input[name="boardThemeRadio"]');
        boardRadios.forEach(radio => {
            radio.addEventListener('change', () => {
                const selectedTheme = radio.value;
                document.documentElement.setAttribute('data-board-theme', selectedTheme);
                localStorage.setItem('boardTheme', selectedTheme);
                localStorage.setItem('chessBoardTheme', selectedTheme);
                
                // Keep any other .theme-btn elements synced (if any exist)
                const originalThemeBtns = document.querySelectorAll('.theme-btn');
                originalThemeBtns.forEach(btn => {
                    if (btn.dataset.theme === selectedTheme) {
                        btn.classList.add('active');
                        btn.setAttribute('aria-pressed', 'true');
                    } else {
                        btn.classList.remove('active');
                        btn.setAttribute('aria-pressed', 'false');
                    }
                });
            });
        });

        // Handle Random Theme button
        const randomThemeBtn = document.getElementById('randomThemeBtn');
        if (randomThemeBtn) {
            randomThemeBtn.onclick = () => {
                const themeValues = Array.from(boardRadios).map(radio => radio.value);
                if (!themeValues.length) return;
                const randomTheme = themeValues[Math.floor(Math.random() * themeValues.length)];
                const targetRadio = themeSettingsModal.querySelector(`input[name="boardThemeRadio"][value="${randomTheme}"]`);
                if (targetRadio) {
                    targetRadio.checked = true;
                    targetRadio.dispatchEvent(new Event('change', { bubbles: true }));
                }
            };
        }

        // Handle Piece Style swatch switches
        const pieceRadios = themeSettingsModal.querySelectorAll('input[name="pieceStyleRadio"]');
        pieceRadios.forEach(radio => {
            radio.addEventListener('change', () => {
                const selectedStyle = radio.value;
                localStorage.setItem('pieceStyle', selectedStyle);
                updatePieceStyle(selectedStyle);
            });
        });

        // Handle Sound Toggle Switch
        const soundToggle = document.getElementById('modalSoundToggle');
        if (soundToggle) {
            soundToggle.addEventListener('change', () => {
                soundEnabled = soundToggle.checked;
                localStorage.setItem('chessSoundEnabled', String(soundEnabled));
            });
        }

        // Handle Coordinates Toggle Switch
        const coordsToggle = document.getElementById('modalCoordsToggle');
        if (coordsToggle) {
            coordsToggle.addEventListener('change', () => {
                const enabled = coordsToggle.checked;
                localStorage.setItem('showCoordinates', String(enabled));
                if (boardEl) {
                    if (enabled) {
                        boardEl.classList.remove('hide-coordinates');
                    } else {
                        boardEl.classList.add('hide-coordinates');
                    }
                }
            });
        }

        // Handle Auto-Flip Toggle Switch
        const autoFlipToggle = document.getElementById('modalAutoFlipToggle');
        if (autoFlipToggle) {
            autoFlipToggle.addEventListener('change', () => {
                autoFlip = autoFlipToggle.checked;
                localStorage.setItem('autoFlip', String(autoFlip));
                if (autoFlip && gameMode === 'pvp') {
                    flipped = (turn === 'black');
                    buildBoard();
                }
            });
        }
    }

    // ========== Keyboard Shortcuts Modal Logic ==========
    const shortcutsModal = document.getElementById('shortcutsModal');
    const shortcutsBtn = document.getElementById('shortcutsBtn');
    const closeShortcutsModalBtn = document.getElementById('closeShortcutsModalBtn');
    const saveShortcutsModalBtn = document.getElementById('saveShortcutsModalBtn');
    let shortcutsModalFocusReturn = null;

    function openShortcutsModal() {
        if (!shortcutsModal) return;
        shortcutsModalFocusReturn = document.activeElement;
        shortcutsModal.classList.add('active');
        shortcutsModal.setAttribute('aria-hidden', 'false');
        setTimeout(() => {
            if (closeShortcutsModalBtn) {
                closeShortcutsModalBtn.focus();
            }
        }, 50);
    }

    function closeShortcutsModal() {
        if (!shortcutsModal) return;
        shortcutsModal.classList.remove('active');
        shortcutsModal.setAttribute('aria-hidden', 'true');
        if (shortcutsModalFocusReturn && typeof shortcutsModalFocusReturn.focus === 'function') {
            shortcutsModalFocusReturn.focus();
        }
        shortcutsModalFocusReturn = null;
    }

    function toggleShortcutsModal() {
        if (!shortcutsModal) return;
        if (shortcutsModal.classList.contains('active')) {
            closeShortcutsModal();
        } else {
            openShortcutsModal();
        }
    }

    if (shortcutsBtn) shortcutsBtn.onclick = toggleShortcutsModal;
    if (closeShortcutsModalBtn) closeShortcutsModalBtn.onclick = closeShortcutsModal;
    if (saveShortcutsModalBtn) saveShortcutsModalBtn.onclick = closeShortcutsModal;

    if (shortcutsModal) {
        shortcutsModal.addEventListener('click', (e) => {
            if (e.target === shortcutsModal) {
                closeShortcutsModal();
            }
        });

        // Trap keyboard focus inside shortcutsModal while active
        shortcutsModal.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;
            const focusable = Array.from(
                shortcutsModal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
            ).filter(el => !el.disabled && el.offsetWidth > 0 && el.offsetHeight > 0);

            if (!focusable.length) {
                e.preventDefault();
                return;
            }
            const first = focusable[0];
            const last = focusable[focusable.length - 1];

            if (e.shiftKey) {
                if (document.activeElement === first || !shortcutsModal.contains(document.activeElement)) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last || !shortcutsModal.contains(document.activeElement)) {
                    e.preventDefault();
                    first.focus();
                }
            }
        });
    }

    // Theme Switcher
    function initThemeSwitcher() {
        const themeBtns = document.querySelectorAll('.theme-btn');
        const currentTheme = document.documentElement.getAttribute('data-board-theme') || 'classic';
        document.documentElement.setAttribute('data-board-theme', currentTheme);

        themeBtns.forEach(btn => {
            if (btn.dataset.theme === currentTheme) {
                btn.classList.add('active');
                btn.setAttribute('aria-pressed', 'true');
            }
            btn.onclick = () => {
                const theme = btn.dataset.theme;
                document.documentElement.setAttribute('data-board-theme', theme);
                localStorage.setItem('boardTheme', theme);
                localStorage.setItem('chessBoardTheme', theme);
                themeBtns.forEach(b => {
                    b.classList.remove('active');
                    b.setAttribute('aria-pressed', 'false');
                });
                btn.classList.add('active');
                btn.setAttribute('aria-pressed', 'true');
            };
        });
    }

    function showAssetWarning() {
        // 1. Pause the timer while the alert is open
        const pausedHere = !paused;
        if (pausedHere) {
            pauseGame().catch(() => { }); // Catch prevents crash if backend hasn't initialized
        }

        showConfirm( //the message on alert
            "⚠️ Assets Blocked",
            "<div style='line-height: 1.5; font-size: 0.95rem;'>The chess pieces failed to load.<br><br>Please check your browser permissions (allow images) or disable any ad-blockers on this site.</div>",
            () => {
                window.location.reload();
            },
            'gold'
        );

        const yesBtn = document.getElementById('confirmYesBtn');
        const noBtn = document.getElementById('confirmNoBtn');
        if (!yesBtn || !noBtn) return;

        // The confirm dialog is shared, so its buttons go back as they were when this one closes.
        const yesText = yesBtn.textContent;
        const noText = noBtn.textContent;
        const defaultClose = noBtn.onclick;
        yesBtn.textContent = 'Reload Page';
        noBtn.textContent = 'Close';

        // 2. Resume the timer if they click Close
        noBtn.onclick = () => {
            yesBtn.textContent = yesText;
            noBtn.textContent = noText;
            noBtn.onclick = defaultClose;
            if (defaultClose) defaultClose();
            if (pausedHere && paused) {
                resumeGame().catch(() => { });
            }
        };
    }

    // A piece image that fails to load leaves the board unusable, so say so once.
    // This is the image's own error event; polling naturalWidth is no use with
    // SVGs, which can report 0 when they load fine.
    function onPieceImageError() {
        if (window.assetWarningShown) return;
        window.assetWarningShown = true;
        showAssetWarning();
    }

    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    function setOfflineStatus() {
        if (!statusIndicator || !statusText) return;
        statusIndicator.classList.add("offline"); //fixed
        statusText.textContent = "Offline";
    }
    function setOnlineStatus() {
        if (!statusIndicator || !statusText) return;
        statusIndicator.classList.remove("offline");
        statusText.textContent = "Online";
    }
    window.addEventListener('offline', setOfflineStatus);
    window.addEventListener('online', setOnlineStatus);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            setOfflineStatus();
        } else {
            setOnlineStatus();
        }
    });
    if (typeof module !== "undefined" && module.exports) {
        module.exports = { 
            pColor, getSquareLabel, formatTime, getPlayerScore, validateMoveWithStockfish, clearEvaluationCache,
            onClick, onDrop, showPromoModal, hidePromoModal, onPromoChoice, toggleSquareHighlight, refreshHighlights, highlightCheck, startNewGame,
            squareLabelToRowCol, computeLegalMovesClient, updatePieceStyle, PIECE_IMG, VALID_PIECE_STYLES
        };
    } else {
        loadGame();
    }

    boardEl.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        // Right-click also highlights a square; only speak up when there was something to cancel.
        if (premoveQueue.length === 0) return;

        premoveQueue = [];
        refreshPremoveHighlight();
        showStatus("Premove cancelled", false);
    });

    // Mobile Touch Drag-and-Drop Implementation
    boardEl.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        const squareEl = e.target.closest('.square');
        if (!squareEl) return;

        const r = parseInt(squareEl.dataset.r);
        const c = parseInt(squareEl.dataset.c);
        const isPremoveMode = gameMode === 'ai' && turn !== playerColor;
        const vBoard = isPremoveMode ? getVirtualBoard() : board;
        const piece = vBoard[r][c];
        if (!piece || paused || gameOver || viewingPastState) return;

        // Check if the piece is playable by the current player (including AI premoves)
        const isPremoveDrag = gameMode === 'ai' && turn !== playerColor && pColor(piece) === playerColor;
        const isNormalDrag = gameMode === 'ai' ? (turn === playerColor && pColor(piece) === playerColor) : (pColor(piece) === turn);

        if (!isPremoveDrag && !isNormalDrag) return;

        touchDragSrc = { r, c };
        touchStartPos = { x: touch.clientX, y: touch.clientY };
    }, { passive: true });

    boardEl.addEventListener('touchmove', (e) => {
        if (!touchDragSrc || !touchStartPos) return;

        // The finger went down on a piece that can move. Keep the page from
        // scrolling, including over the first few pixels before the drag starts.
        if (e.cancelable) e.preventDefault();

        const touch = e.touches[0];

        if (!touchDragging) {
            const dx = touch.clientX - touchStartPos.x;
            const dy = touch.clientY - touchStartPos.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance > 8) {
                touchDragging = true;

                // Select the piece to show move hints
                selectPiece(touchDragSrc.r, touchDragSrc.c);

                // Find the original piece image
                const squareEl = sq(touchDragSrc.r, touchDragSrc.c);
                const pieceImg = squareEl ? squareEl.querySelector('.piece') : null;
                if (pieceImg) {
                    // Create premium floating clone
                    activeTouchPieceClone = pieceImg.cloneNode(true);
                    activeTouchPieceClone.className = 'piece touch-drag-clone';

                    // Measure and style the clone
                    const rect = pieceImg.getBoundingClientRect();
                    touchOffset = { x: rect.width / 2, y: rect.height / 2 };

                    activeTouchPieceClone.style.position = 'fixed';
                    activeTouchPieceClone.style.pointerEvents = 'none';
                    activeTouchPieceClone.style.zIndex = '9999';
                    activeTouchPieceClone.style.width = rect.width + 'px';
                    activeTouchPieceClone.style.height = rect.height + 'px';
                    activeTouchPieceClone.style.transform = 'scale(1.15)';
                    activeTouchPieceClone.style.filter = 'drop-shadow(0 8px 16px rgba(0, 0, 0, 0.45))';
                    activeTouchPieceClone.style.transition = 'none';
                    activeTouchPieceClone.style.willChange = 'left, top';

                    document.body.appendChild(activeTouchPieceClone);

                    // Make original piece semi-transparent
                    pieceImg.classList.add('touch-dragging-original');
                }
            }
        }

        if (touchDragging && activeTouchPieceClone) {
            activeTouchPieceClone.style.left = (touch.clientX - touchOffset.x) + 'px';
            activeTouchPieceClone.style.top = (touch.clientY - touchOffset.y) + 'px';
        }
    }, { passive: false });

    boardEl.addEventListener('touchend', async (e) => {
        const srcSquare = touchDragSrc;
        const wasDragging = touchDragging;
        // Clear the gesture now. The moves below wait on the server, and a new
        // touch may start before they come back.
        touchStartPos = null;
        touchDragSrc = null;
        touchDragging = false;

        if (!srcSquare && !selected) return;
        const touch = e.changedTouches[0];

        // Prevent click generation. This has to happen before any await.
        e.preventDefault();

        if (wasDragging && srcSquare) {
            // Clean up original piece transparency
            const srcSquareEl = sq(srcSquare.r, srcSquare.c);
            const pieceImg = srcSquareEl ? srcSquareEl.querySelector('.piece') : null;
            if (pieceImg) {
                pieceImg.classList.remove('touch-dragging-original');
            }

            // Clean up clone
            if (activeTouchPieceClone) {
                activeTouchPieceClone.remove();
                activeTouchPieceClone = null;
            }

            // Identify target square element under the touch coordinates
            const targetEl = document.elementFromPoint(touch.clientX, touch.clientY);
            const destSquareEl = targetEl ? targetEl.closest('.square') : null;
            const tr = destSquareEl ? parseInt(destSquareEl.dataset.r, 10) : -1;
            const tc = destSquareEl ? parseInt(destSquareEl.dataset.c, 10) : -1;

            if (destSquareEl && (tr !== srcSquare.r || tc !== srcSquare.c)) {
                await tryMove(srcSquare.r, srcSquare.c, tr, tc);
            } else {
                deselect();
            }
        } else {
            const targetEl = document.elementFromPoint(
                touch.clientX,
                touch.clientY
            );
            if (!targetEl) return;
            const squareEl = targetEl.closest('.square');

            if (!squareEl) return;

            const tr = parseInt(squareEl.dataset.r);
            const tc = parseInt(squareEl.dataset.c);
            await onClick(tr, tc);
        }
    }, { passive: false });

    boardEl.addEventListener('touchcancel', (e) => {
        if (!touchStartPos) return;

        if (touchDragging && touchDragSrc) {
            const srcSquareEl = sq(touchDragSrc.r, touchDragSrc.c);
            const pieceImg = srcSquareEl ? srcSquareEl.querySelector('.piece') : null;
            if (pieceImg) {
                pieceImg.classList.remove('touch-dragging-original');
            }

            if (activeTouchPieceClone) {
                activeTouchPieceClone.remove();
                activeTouchPieceClone = null;
            }

            deselect();
        }

        touchStartPos = null;
        touchDragSrc = null;
        touchDragging = false;
    }, { passive: true });

    // INLINE INITIALIZATION FOR CUSTOM TIME CONTROL POPUP
    function initTimeControlPicker() {
        const trigger = document.getElementById('timeControlTrigger');
        const popover = document.getElementById('timeControlPopover');
        const tabs = document.querySelectorAll('.tc-tab-btn');
        const tabContents = document.querySelectorAll('.tc-tab-content');
        const presetBtns = document.querySelectorAll('.tc-preset-btn');
        const applyCustomBtn = document.getElementById('applyCustomTCBtn');
        const display = document.getElementById('tcDisplayText');

        if (!trigger || !popover) return;

        // Toggle popover
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const isVisible = popover.style.display === 'flex';
            popover.style.display = isVisible ? 'none' : 'flex';
        });

        // Tab switching
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

        // Preset button selection
        presetBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                presetBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                pickedMins = parseInt(btn.dataset.mins, 10);
                pickedIncrement = parseInt(btn.dataset.inc, 10);

                // Update display text
                display.textContent = btn.textContent.trim();

                // Close popover
                popover.style.display = 'none';
            });
        });

        // Apply custom time control
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

                    // The server takes 1 minute to 5 hours.
                    if (mins * 60 + secs < 60) {
                        mins = 1;
                        secs = 0;
                    }
                    if (mins === 300) secs = 0;

                    minsInput.value = mins;
                    if (secsInput) secsInput.value = secs;
                    incInput.value = inc;

                    // Minutes as a decimal, e.g. 1.5 for 1:30
                    pickedMins = (mins * 60 + secs) / 60;
                    pickedIncrement = inc;

                    // Update active preset styling
                    presetBtns.forEach(b => b.classList.remove('active'));

                    // Build a human-readable display string
                    let displayText;
                    const finalTotalSecs = mins * 60 + secs;
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
                    display.textContent = displayText;

                    // Close popover
                    popover.style.display = 'none';
                }
            });
        }


        // Close popover when clicking anywhere else
        document.addEventListener('click', (e) => {
            if (!popover.contains(e.target) && e.target !== trigger) {
                popover.style.display = 'none';
            }
        });
    }

    // Call picker init immediately
    initTimeControlPicker();

    // Render any W/L/D counts already stored for this browser session
    updateSessionTracker();
    // Render the current game count already stored for this browser session
    updateGameCounterDisplay();
    // Wire up the onboarding tour's Skip/Next buttons and, if resuming a
    // game with no setup screen showing, start it right away
    initOnboardingTour();
    // Resume game by clicking the paused board overlay
    boardEl.addEventListener('click', async () => {
        if (!paused || gameOver) return;
        if (drawOverlay.classList.contains('active')) return;
        if (confirmOverlay.classList.contains('active')) return;
        if (gameOverOverlay.classList.contains('active')) return;
        await resumeGame();
    });

    let resizeTimeout;
    window.addEventListener('resize', () => {
        if (premoveQueue.length > 0) {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                drawPremoveArrows(true);
            }, 100);
        }
    });

})();
// Share dialog and the mobile controls drawer.
document.addEventListener("DOMContentLoaded", function () {
    const shareBtn = document.getElementById('shareResultBtn');
    if (shareBtn) {
        shareBtn.addEventListener('click', function () {
            const titleEl = document.getElementById('gameOverTitle');
            const messageEl = document.getElementById('gameOverMessage');
            const whiteNameEl = document.getElementById('whiteNameLabel');
            const blackNameEl = document.getElementById('blackNameLabel');
            const movesList = document.getElementById('movesList');
            
            const title = titleEl ? titleEl.innerText.trim() : '';
            const message = messageEl ? messageEl.innerText.trim() : '';
            const whiteName = whiteNameEl ? whiteNameEl.innerText.trim() : '';
            const blackName = blackNameEl ? blackNameEl.innerText.trim() : '';
            
            let moveCount = 0;
            if (movesList) {
                moveCount = movesList.querySelectorAll('span:not(.placeholder)').length ||
                            movesList.innerText.split('\n').filter(x => x.trim()).length;
            }

            const cardTitle = document.getElementById('cardTitle');
            const cardMessage = document.getElementById('cardMessage');
            const cardWhite = document.getElementById('cardWhite');
            const cardBlack = document.getElementById('cardBlack');
            const cardMoves = document.getElementById('cardMoves');
            
            if(cardTitle) cardTitle.innerText = title;
            if(cardMessage) cardMessage.innerText = message;
            if(cardWhite) cardWhite.innerText = whiteName;
            if(cardBlack) cardBlack.innerText = blackName;
            if(cardMoves) cardMoves.innerText = moveCount;

            const shareText =
`♟️ Checkora Chess
─────────────────
${title}
${message}

⚪ ${whiteName} vs ⚫ ${blackName}
🔢 Moves played: ${moveCount}
─────────────────
🎮 Play at: https://checkora.edward7780.com`;

            const modal = document.getElementById('shareModal');
            if (modal) modal.style.display = 'flex';

            const copyTextBtn = document.getElementById('copyTextBtn');
            if (copyTextBtn) {
                copyTextBtn.onclick = function () {
                    navigator.clipboard.writeText(shareText).then(() => {
                        this.innerText = 'Copied!';
                        setTimeout(() => this.innerText = 'Copy text', 2000);
                    });
                };
            }

            const copyLinkBtn = document.getElementById('copyLinkBtn');
            if (copyLinkBtn) {
                copyLinkBtn.onclick = function () {
                    navigator.clipboard.writeText('https://checkora.edward7780.com').then(() => {
                        this.innerText = 'Link copied!';
                        setTimeout(() => this.innerText = 'Copy link', 2000);
                    });
                };
            }

            const whatsappBtn = document.getElementById('whatsappBtn');
            if (whatsappBtn) {
                whatsappBtn.onclick = function () {
                    const encoded = encodeURIComponent(shareText);
                    window.open(`https://wa.me/?text=${encoded}`, '_blank', 'noopener,noreferrer');
                };
            }

            const twitterBtn = document.getElementById('twitterBtn');
            if (twitterBtn) {
                twitterBtn.onclick = function () {
                    const encoded = encodeURIComponent(shareText);
                    window.open(`https://twitter.com/intent/tweet?text=${encoded}`, '_blank', 'noopener,noreferrer');
                };
            }

            const closeShareBtn = document.getElementById('closeShareBtn');
            if (closeShareBtn && modal) {
                closeShareBtn.onclick = function () {
                    modal.style.display = 'none';
                };
            }
        });
    }

    // Mobile Controls Panel Toggle
    const mobilePanel = document.getElementById('mobilePanel');
    const toggleBtn = document.getElementById('mobileControlsToggle');
    const closeBtn = document.getElementById('mobileControlsClose');

    if (toggleBtn && mobilePanel) {
        toggleBtn.addEventListener('click', function () {
            const active = mobilePanel.classList.toggle('active');
            toggleBtn.setAttribute('aria-expanded', active ? 'true' : 'false');
        });
    }

    if (closeBtn && mobilePanel) {
        closeBtn.addEventListener('click', function () {
            mobilePanel.classList.remove('active');
            if (toggleBtn) {
                toggleBtn.setAttribute('aria-expanded', 'false');
            }
        });
    }
});