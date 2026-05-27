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

    const PIECE_IMG = {};
    for (const c of ['w', 'b'])
        for (const t of ['k', 'q', 'r', 'b', 'n', 'p'])
            PIECE_IMG[c + t] = `https://images.chesscomfiles.com/chess-themes/pieces/neo/150/${c}${t}.png`;

    let board = [];
    let turn = 'white';
    let selected = null;
    let hints = [];
    let lastMove = null;

    let dragging = false;
    let dragSrc = null;

    let whiteTime = 0;
    let blackTime = 0;
    let selectedMins = 10;
    let selectedIncrement = 0;
    let paused = false;
    let timerInterval = null;
    let pendingPromo = null;

    let gameMode = 'pvp';
    let currentDifficulty = 'medium';
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
    let playerColor = 'white';
    let flipped = false;
    let autoFlip = false;

    const SOUND_BASE_URL = window.SOUND_BASE_URL || '/static/game/sounds/';
    const sounds = {
        move: new Audio(`${SOUND_BASE_URL}move.wav`),
        capture: new Audio(`${SOUND_BASE_URL}capture.mp3`),
        check: new Audio(`${SOUND_BASE_URL}check.wav`),
        draw: new Audio(`${SOUND_BASE_URL}draw.mp3`),
    };

    let soundEnabled = true;

    function validatePlayerNames() {
        const wNameInput = document.getElementById('whiteNameInput');
        const bNameInput = document.getElementById('blackNameInput');
        const errorDiv = document.getElementById('nameError');

        const wName = wNameInput?.value.trim();
        const bName = bNameInput?.value.trim();

        if (!wName || !bName) {
            if (errorDiv) {
                errorDiv.style.display = 'block';
                errorDiv.textContent = '⚠️ Please enter both player names';
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

    function toggleMute() {
        soundEnabled = !soundEnabled;
        if (muteBtn) {
            muteBtn.textContent = soundEnabled ? '🔊 Sound On' : '🔇 Muted';
            muteBtn.setAttribute('aria-pressed', String(soundEnabled));
        }
    }

    /* ==========================================================
    DOM REFERENCES
    ========================================================== */
    const boardEl = document.getElementById('board');
    const turnEl = document.getElementById('turnBadge');
    const statusEl = document.getElementById('statusBar');
    const movesEl = document.getElementById('movesList');
    const wCapEl = document.getElementById('whiteCaptured');
    const bCapEl = document.getElementById('blackCaptured');
    const pauseBtn = document.getElementById('pauseBtn');
    const flipBtn = document.getElementById('flipBtn');
    const promoOverlay = document.getElementById('promoOverlay');
    const promoChoices = document.getElementById('promoChoices');
    const modeBadge = document.getElementById('modeBadge');
    const autoFlipBtn = document.getElementById('autoFlipBtn');
    const flipControls = document.getElementById('flipControls');
    const copyFenBtn = document.getElementById('copyFenBtn');
    const copyPgnBtn = document.getElementById('copyPgnBtn');
    const muteBtn = document.getElementById('muteBtn');

    const welcomeOverlay = document.getElementById('welcomeOverlay');
    const welcomeResumeBtn = document.getElementById('welcomeResumeBtn');
    const welcomePvPBtn = document.getElementById('welcomePvPBtn');
    const welcomeAIBtn = document.getElementById('welcomeAIBtn');
    const welcomeFenInput = document.getElementById('welcomeFenInput');
    const welcomeFenError = document.getElementById('welcomeFenError');

    const modeSelection = document.getElementById('modeSelection');
    const pveOptions = document.getElementById('pveOptions');
    const startAIBtn = document.getElementById('startAIBtn');
    const backToModes = document.getElementById('backToModes');
    const gameLayout = document.querySelector('.game-layout');

    const confirmOverlay = document.getElementById('confirmOverlay');
    const confirmTitle = document.getElementById('confirmTitle');
    const confirmMessage = document.getElementById('confirmMessage');
    const confirmYesBtn = document.getElementById('confirmYesBtn');
    const confirmNoBtn = document.getElementById('confirmNoBtn');

    const newPvPBtn = document.getElementById('newPvPBtn');
    const newAIBtn = document.getElementById('newAIBtn');
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
    const gameOverPvPBtn = document.getElementById('gameOverPvPBtn');
    const gameOverAIBtn = document.getElementById('gameOverAIBtn');

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

    let gameOver = false;
    let aiThinking = false;
    let aiRequestSeq = 0; // Sequence token to cancel stale AI responses

    let replayMode = false;
    let replayMoves = [];
    let replayIndex = 0;
    let replayBoard = null;
    let autoReplayInterval = null;

    let pgnDownloadTimeout = null;
    let fenCopyTimeout = null;
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
    }

    function csrf() {
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    async function get(url) {
        return (await fetch(url)).json();
    }

    async function post(url, body) {
        return (await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf()
            },
            body: JSON.stringify(body)
        })).json();
    }

    function isAITurn() {
        return gameMode === 'ai' && turn !== playerColor && !gameOver;
    }

    function queueAIMoveIfNeeded() {
        if (!isAITurn() || aiThinking) return;
        setTimeout(() => {
            if (isAITurn() && !aiThinking) requestAIMove();
        }, 200);
    }

    const pKey = p => p ? ((p === p.toUpperCase() ? 'w' : 'b') + p.toLowerCase()) : null;
    const pColor = p => p ? (p === p.toUpperCase() ? 'white' : 'black') : null;
    const sq = (r, c) => {
        const vr = flipped ? 7 - r : r;
        const vc = flipped ? 7 - c : c;
        return boardEl.children[vr * 8 + vc];
    };

    function getSquareSize() {
        const s = boardEl.querySelector('.square');
        return s ? s.getBoundingClientRect().width : 60;
    }

    async function animateMove(fr, fc, tr, tc) {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

        const animations = [];
        const size = getSquareSize();
        const mult = flipped ? -1 : 1;

        function createAnim(p, dRow, dCol) {
            return new Promise(resolve => {
                p.style.transition = 'transform 0.25s ease-in-out, opacity 0.2s ease';
                p.style.transform = `translate(${dCol * size * mult}px, ${dRow * size * mult}px)`;
                p.classList.add('moving');

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

        // 1. Moving piece
        const piece = sq(fr, fc).querySelector('.piece');
        if (piece) {
            animations.push(createAnim(piece, tr - fr, tc - fc));

            // 2. Castling detection
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

        // 3. Capture detection (including En Passant)
        let capturedSq = sq(tr, tc);
        // En Passant: capture pawn is not on target square
        const isEnPassant = piece && piece.src.includes('p.png') && fc !== tc && !board[tr][tc];
        if (isEnPassant) {
            capturedSq = sq(fr, tc);
        }

        const targetPiece = capturedSq.querySelector('.piece');
        if (targetPiece) {
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
    /* ==========================================================
    LOAD GAME STATE
    ========================================================== */
    async function loadGame() {
        const data = await get('/api/state/');

        if (data.time_limit !== undefined) {
            selectedMins = data.time_limit / 60;
        }
        if (data.increment !== undefined) {
            selectedIncrement = data.increment;
        }

        board = parseBoard(data.board);
        turn = data.current_turn;
        whiteTime = data.white_time;
        blackTime = data.black_time;
        paused = data.paused;

        gameMode = data.mode || 'pvp';
        // Sync UI with current game mode
        updateModeButtonsUI(gameMode);
        playerColor = data.player_color || 'white';
        currentDifficulty = data.difficulty || currentDifficulty;

        if (flipControls) {
            flipControls.style.display = (gameMode === 'pvp') ? 'flex' : 'none';
        }

        if (gameMode === 'ai') {
            flipped = (playerColor === 'black');
        } else {
            flipped = false;
        }

        if (modeBadge) modeBadge.textContent = gameMode === 'ai' ? 'VS AI' : 'PVP';

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
                welcomeResumeBtn.textContent = data.mode === 'ai'
                    ? 'Replay Previous Game'
                    : 'Resume Game';
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
        updateMoves(data.move_history);
        updateCaptured(data.captured_pieces);

        buildBoard();
        renderClocks();
        updatePauseUI();
        startTimer();
        if (gameMode === 'ai') {
            const aiClock = playerColor === 'white' ?
                document.getElementById('blackClock') :
                document.getElementById('whiteClock');
            const aiTimeEl = playerColor === 'white' ?
                document.getElementById('blackTime') :
                document.getElementById('whiteTime');

            if (aiClock) {
                aiClock.style.border = '2px dashed #444';
                aiClock.style.boxShadow = 'none';
                aiClock.classList.remove('active');
            }
            if (aiTimeEl) {
                aiTimeEl.textContent = '🤖';
                aiTimeEl.style.fontSize = '1.8em';
                aiTimeEl.style.color = '#888';
            }
        }

        if (data.game_status && data.game_status !== 'active' && data.game_status !== 'ok') {
            handleGameStatus(data.game_status, data.draw_reason);
        }
        if (!welcomeOverlay.classList.contains('active')) {
            queueAIMoveIfNeeded();
        }
    }

    function updatePlayerNames(data) {
        let wName = data.white_name || 'White';
        let bName = data.black_name || 'Black';

        if (gameMode === 'ai') {
            const diffLabel = (currentDifficulty || 'medium').toUpperCase();
            const player_name = playerColor === 'white' ? data.white_name : data.black_name;
            if (playerColor === 'white') {
                wName = player_name;
                bName = `AI (Black)`;
            } else {
                bName = player_name;
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
                    badge.style.cssText = 'color:#f0c040 !important; font-weight:700; font-size:1.20em; letter-spacing:1px;';
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

        if (gameMode === 'ai') {
            if (whiteYouTag) whiteYouTag.style.display = (playerColor === 'white') ? 'inline' : 'none';
            if (blackYouTag) blackYouTag.style.display = (playerColor === 'black') ? 'inline' : 'none';
        } else {
            if (whiteYouTag) whiteYouTag.style.display = 'none';
            if (blackYouTag) blackYouTag.style.display = 'none';
        }
    }


    /* ==========================================================
    BOARD RENDERING
    ========================================================== */
    function buildBoard() {
        boardEl.innerHTML = '';
        for (let vr = 0; vr < 8; vr++) {
            for (let vc = 0; vc < 8; vc++) {
                const r = flipped ? 7 - vr : vr;
                const c = flipped ? 7 - vc : vc;
                const d = document.createElement('div');
                d.className = 'square ' + ((vr + vc) % 2 ? 'dark' : 'light');
                d.dataset.r = r;
                d.dataset.c = c;
                d.onclick = () => onClick(r, c);
                d.ondragover = e => e.preventDefault();
                d.ondrop = e => onDrop(e, r, c);

                // ADD THESE:
                d.draggable = true;
                d.ondragstart = e => {
                    const piece = board[r][c];
                    if (!piece || pColor(piece) !== turn || paused || gameOver) return e.preventDefault();
                    if (gameMode === 'ai' && turn !== playerColor) return e.preventDefault();

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

                d.setAttribute('tabindex', '0');
                d.setAttribute('role', 'gridcell');
                d.setAttribute('data-row', r);
                d.setAttribute('data-col', c);
                d.setAttribute('aria-label', getSquareLabel(r, c));
                d.onkeydown = (e) => handleSquareKeydown(e, r, c);

                boardEl.appendChild(d);
            }
        }
        syncPieces();
        updateLabels();
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
            const isPlayable = p && pColor(p) === turn
                && !(gameMode === 'ai' && turn !== playerColor);
            img.classList.toggle('playable', isPlayable);
        });
    }

    function refreshHighlights() {
        boardEl.querySelectorAll('.square').forEach(el => {
            el.classList.remove('selected', 'last-move', 'in-check');
            el.querySelectorAll('.move-dot, .capture-ring').forEach(n => n.remove());
        });

        if (lastMove) {
            sq(lastMove.from[0], lastMove.from[1]).classList.add('last-move');
            sq(lastMove.to[0], lastMove.to[1]).classList.add('last-move');
        }

        if (selected) {
            sq(selected.r, selected.c).classList.add('selected');
            hints.forEach(h => {
                const el = sq(h.row, h.col);
                const d = document.createElement('div');
                d.className = h.is_capture ? 'capture-ring' : 'move-dot';
                el.appendChild(d);
            });
        }
    }

    function highlightCheck() {
        boardEl.querySelectorAll('.square').forEach(el => {
            el.classList.remove('in-check');
        });
    }

    function applyCheckHighlight() {
        highlightCheck();
        const kingPiece = turn === 'white' ? 'K' : 'k';
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                if (board[r][c] === kingPiece) {
                    sq(r, c).classList.add('in-check');
                    return;
                }
            }
        }
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

        switch (e.key) {
            case 'ArrowUp': e.preventDefault(); newRow = row - 1; break;
            case 'ArrowDown': e.preventDefault(); newRow = row + 1; break;
            case 'ArrowLeft': e.preventDefault(); newCol = col - 1; break;
            case 'ArrowRight': e.preventDefault(); newCol = col + 1; break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                onClick(row, col);
                return;
            case 'Escape':
                e.preventDefault();
                document.querySelectorAll('.square.selected')
                    .forEach(s => s.classList.remove('selected'));
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
    async function selectPiece(r, c) {
        const p = board[r][c];
        if (!p || pColor(p) !== turn || paused || gameOver) return;

        if (gameMode === 'ai' && turn !== playerColor) {
            showStatus("Waiting for AI to move...", false);
            return;
        }

        selected = { r, c };
        const data = await get(`/api/valid-moves/?row=${r}&col=${c}`);
        hints = data.valid_moves || [];
        refreshHighlights();
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

    function showPromoModal(color) {
        const prefix = color === 'white' ? 'w' : 'b';
        const pieces = [
            { key: 'q', label: 'Queen' },
            { key: 'r', label: 'Rook' },
            { key: 'b', label: 'Bishop' },
            { key: 'n', label: 'Knight' },
        ];
        promoChoices.innerHTML = '';
        pieces.forEach(({ key }) => {
            const btn = document.createElement('button');
            btn.className = 'promo-btn';
            const img = document.createElement('img');
            img.src = PIECE_IMG[prefix + key];
            btn.appendChild(img);
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

    async function tryMove(fr, fc, tr, tc) {
        if (paused || gameOver) return;
        const p = board[fr][fc];
        if (!p || pColor(p) !== turn) return;

        if (isPromotionMove(fr, fc, tr)) {
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
    } async function executeMove(fr, fc, tr, tc, promotionPiece, skipAnimation = false) {
        try {
            const body = {
                from_row: fr, from_col: fc,
                to_row: tr, to_col: tc,
            };
            if (promotionPiece) body.promotion_piece = promotionPiece;

            const data = await post('/api/move/', body);
            if (data.valid) {
                playSound(data);
                if (!skipAnimation) await animateMove(fr, fc, tr, tc);
                board = parseBoard(data.board);
                turn = data.current_turn;
                lastMove = { from: [fr, fc], to: [tr, tc] };

                if (gameMode === 'pvp' && autoFlip) {
                    flipped = (turn === 'black');
                    buildBoard();
                }
                whiteTime = data.white_time;
                blackTime = data.black_time;

                selected = null;
                hints = [];
                updatePlayerNames(data);
                updateTurn();
                updateMoves(data.move_history);
                updateCaptured(data.captured_pieces);
                syncPieces();
                renderClocks();
                startTimer();
                updateMaterialUI(board);
                let a11yMsg = '';
                if (data.move_history && data.move_history.length > 0) {
                    const lastMove = data.move_history[data.move_history.length - 1].notation;
                    const playedColor = turn === 'white' ? 'Black' : 'White';
                    a11yMsg = `${playedColor} played ${lastMove}. `;
                }

                const gameEnded = handleGameStatus(data.game_status, data.draw_reason);
                if (!gameEnded) {
                    if (data.game_status === 'check') {
                        applyCheckHighlight();
                        const checkMsg = turn === 'white' ? 'White is in check!' : 'Black is in check!';
                        showStatus(checkMsg, true);
                        a11yMsg += checkMsg;
                    } else {
                        highlightCheck();
                        showStatus('', false);
                    }
                    if (a11yMsg) announceMove(a11yMsg);
                }

                if (gameMode === 'ai' && turn !== playerColor && !gameOver) {
                    requestAIMove();
                }
            } else {
                showStatus(data.message, true);
                deselect();
            }
        } catch (e) {
            await handleReconnect();
        }
    }

    async function requestAIMove() {
        if (gameOver || aiThinking) return;
        aiThinking = true;
        showStatus('AI is thinking...', false);
        try {
            const data = await post('/api/ai-move/', {});
            if (data.valid) {
                playSound(data);
                const mv = data.ai_move;
                await animateMove(mv.from_row, mv.from_col, mv.to_row, mv.to_col);
                board = parseBoard(data.board);
                turn = data.current_turn;
                lastMove = { from: [mv.from_row, mv.from_col], to: [mv.to_row, mv.to_col] };
                whiteTime = data.white_time;
                blackTime = data.black_time;

                selected = null;
                hints = [];
                updatePlayerNames(data);
                updateTurn();
                updateMoves(data.move_history);
                updateCaptured(data.captured_pieces);
                syncPieces();
                renderClocks();
                startTimer();
                updateMaterialUI(board);
                let a11yMsg = '';
                if (data.move_history && data.move_history.length > 0) {
                    const lastMove = data.move_history[data.move_history.length - 1].notation;
                    a11yMsg = `AI played ${lastMove}. `;
                }

                const gameEnded = handleGameStatus(data.game_status, data.draw_reason);
                if (!gameEnded) {
                    if (data.game_status === 'check') {
                        applyCheckHighlight();
                        showStatus('You are in check!', true);
                        a11yMsg += 'You are in check!';
                    } else {
                        highlightCheck();
                        showStatus('Your turn.', false);
                    }
                    if (a11yMsg) announceMove(a11yMsg);
                }
            } else {
                showStatus(data.message, true);
            }
        } catch (e) {

            await handleReconnect();
        } finally {
            aiThinking = false;
        }
    }

    /* ==========================================================
    EVENTS
    ========================================================== */
    async function onClick(r, c) {
        if (replayMode) return;
        if (dragging) return;
        if (selected) {

            //New toggle logic:
            //If the clicked square is the exact same as the selected square, deselect it.
            if (selected.r === r && selected.c === c) {
                return deselect();
            }
            if (hints.some(h => h.row === r && h.col === c))
                return tryMove(selected.r, selected.c, r, c);
            if (board[r][c] && pColor(board[r][c]) === turn)
                return selectPiece(r, c);
            return deselect();
        }
        selectPiece(r, c);
    }

    function onDragStart(e, r, c) {
        if (paused || pColor(board[r][c]) !== turn) return e.preventDefault();
        if (gameMode === 'ai' && turn !== playerColor) return e.preventDefault();
        dragging = true;
        dragSrc = { r, c };
        selectPiece(r, c);
    }

    async function onDrop(e, tr, tc) {
        if (replayMode) return;
        if (!dragSrc) return;
        await tryMove(dragSrc.r, dragSrc.c, tr, tc);
        dragSrc = null;
    }

    function resetReplayBoard() {
        if (window.Chess) {
            replayBoard = new window.Chess();
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
    }
    function goToReplayMove(index) {

        if (!window.Chess) {
            console.error("Chess.js not loaded");
            return;
        }

        replayBoard = new window.Chess();

        try {

            for (let i = 0; i < index; i++) {

                const move = replayMoves[i];

                if (move) {
                    const result = replayBoard.move(move);
                    console.log("Replaying:", move, result)
                }
            }

            replayIndex = index;

            renderReplayPosition();

        } catch (e) {

            console.error("Replay move error:", e);
        }
    }

    /* ==========================================================
    UI UPDATES
    ========================================================== */
    function updateTurn() {
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
        badge.textContent = label;
        if (turnBadgeText) turnBadgeText.textContent = pName;

        wCapEl.classList.toggle('active', turn === 'white');
        bCapEl.classList.toggle('active', turn === 'black');
    }

    function updateMoves(history) {
        if (!history?.length) {
            movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
            return;
        }
        movesEl.innerHTML = '';
        const totalPairs = Math.ceil(history.length / 2);
        for (let i = history.length - 1; i >= 0; i -= 2) {
            const whiteIdx = i % 2 === 0 ? i : i - 1;
            const blackIdx = whiteIdx + 1;
            const moveNum = Math.floor(whiteIdx / 2) + 1;
            const row = document.createElement('div');
            row.className = 'move-row';
            row.innerHTML = `
                        <span class="move-num">${moveNum}.</span>
                        <span class="move-white">${history[whiteIdx]?.notation ?? ''}</span>
                        ${history[blackIdx] ? `<span class="move-black">${history[blackIdx].notation}</span>` : ''}
                    `;
            movesEl.appendChild(row);
        }
    }

    function updateCaptured(cap) {
        wCapEl.innerHTML = bCapEl.innerHTML = '';

        const point_vals = { 'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 0 };

        let whitePoints = cap.white.reduce((sum, p) => sum + (point_vals[p.toLowerCase()] || 0), 0);
        let blackPoints = cap.black.reduce((sum, p) => sum + (point_vals[p.toLowerCase()] || 0), 0);

        cap.white.forEach((p) => {
            wCapEl.innerHTML += `<img src="${PIECE_IMG[pKey(p)]}" class="captured-img">`;
        });
        cap.black.forEach((p) => {
            bCapEl.innerHTML += `<img src="${PIECE_IMG[pKey(p)]}" class="captured-img">`;
        });

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

    function handleGameStatus(status, drawReason) {
        if (status === 'checkmate') {
            endGame('checkmate', turn);
            return true;
        }
        if (status === 'stalemate') {
            endGame('stalemate', turn);
            return true;
        }
        if (status === 'draw') {
            endGame('draw', turn, drawReason);
            return true;
        }
        return false;
    }

    function detectOpening(moves) {
        if (!moves || moves.length === 0) return 'Standard Game';

        const m1 = moves[0];
        const m2 = moves[1];
        const m3 = moves[2];
        const m4 = moves[3];
        const m5 = moves[4];

        if (m1 === 'e4') {
            if (m2 === 'c5') return 'Sicilian Defense';
            if (m2 === 'e5') {
                if (m3 === 'Nf3') {
                    if (m4 === 'Nc6') {
                        if (m5 === 'Bb5') return 'Ruy Lopez';
                        if (m5 === 'Bc4') return 'Italian Game';
                        if (m5 === 'd4') return 'Scotch Game';
                    }
                    if (m4 === 'Nf6') return 'Petrov Defense';
                }
                return 'King\'s Pawn Game';
            }
            if (m2 === 'e6') return 'French Defense';
            if (m2 === 'c6') return 'Caro-Kann Defense';
            if (m2 === 'd6') return 'Pirc Defense';
        }
        if (m1 === 'd4') {
            if (m2 === 'd5') {
                if (m3 === 'c4') return 'Queen\'s Gambit';
                return 'Queen\'s Pawn Game';
            }
            if (m2 === 'Nf6') {
                if (m3 === 'c4') {
                    if (m4 === 'e6') return 'Nimzo-Indian Defense';
                    if (m4 === 'g6') return 'King\'s Indian Defense';
                }
                return 'Indian Defense';
            }
        }
        if (m1 === 'Nf3') return 'Réti Opening';
        if (m1 === 'c4') return 'English Opening';
        if (m1 === 'f4') return 'Bird\'s Opening';

        return 'Open Game';
    }

    function endGame(reason, color, drawReason = null) {
        if (gameOver) return;
        gameOver = true;
        replayMode = true;
        paused = true;
        clearInterval(timerInterval);

        let title = '', message = '';

        // Determine PVP or AI result relative to current player color
        const isWon = reason === 'checkmate' || reason === 'resign' || reason === 'timeout';
        const winnerColor = isWon ? (color === 'white' ? 'black' : 'white') : null;

        let resultState = 'draw'; // 'victory', 'defeat', 'draw'
        if (isWon) {
            if (gameMode === 'ai') {
                resultState = (winnerColor === playerColor) ? 'victory' : 'defeat';
            } else {
                resultState = 'victory'; // Celebrate PvP victory for either side
            }
        }

        let isCelebration = (resultState === 'victory');

        if (reason === 'checkmate') {
            const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
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
            const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
            const loserName = color === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;
            title = 'Victory';
            message = `${loserName} resigned. ${winnerName} Wins!`;
        } else if (reason === 'timeout') {
            const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
            const loserName = color === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;
            title = 'Timeout';
            message = `${loserName} ran out of time. ${winnerName} Wins!`;
        }

        if (resignBtn) resignBtn.style.display = 'none';
        if (drawBtn) drawBtn.style.display = 'none';
        if (pauseBtn) pauseBtn.style.display = 'none';
        gameOverTitle.textContent = title;
        gameOverMessage.textContent = message;

        // Delay the overlay and celebration effects by 1 second
        if (newPvPBtn) newPvPBtn.style.display = '';
        if (newAIBtn) newAIBtn.style.display = '';
        if (newFenBtn) newFenBtn.style.display = '';

        let durationText = '';

        if (gameStartTime) {
            const duration = Date.now() - gameStartTime;
            durationText = formatGameDuration(duration);
        }

        replayMoves = [];
        replayIndex = 0;

        // USE ORIGINAL HISTORY INSTEAD OF REVERSED DOM
        const moveSpans = document.querySelectorAll('.move-white, .move-black');

        moveSpans.forEach(span => {
            const move = span.textContent
                ?.replace(/[+#]/g, '')
                ?.replace(/\s+/g, '')
                ?.trim();

            if (move && move !== '...') {
                console.log("Replay move added:", move);
                replayMoves.push(move);
            }
        });

        console.log("FINAL REPLAY MOVES:", replayMoves);

        if (window.Chess) {
            replayBoard = new window.Chess();
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
                gameOverTitle.textContent = gameMode === 'pvp' ? '🏆 VICTORY 🏆' : '🏆 VICTORY 🏆';
            } else if (resultState === 'defeat') {
                bannerEl.classList.add('banner-defeat');
                if (bannerIconEl) bannerIconEl.textContent = '💀';
                gameOverTitle.textContent = '💀 DEFEAT 💀';
            } else {
                bannerEl.classList.add('banner-draw');
                if (bannerIconEl) bannerIconEl.textContent = '🤝';
                gameOverTitle.textContent = '🤝 DRAW 🤝';
            }
        }

        gameOverMessage.textContent = message;

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

        // 6. Opening Book and Review Highlights
        const openingNameEl = document.getElementById('resOpeningName');
        if (openingNameEl) {
            openingNameEl.textContent = detectOpening(replayMoves);
        }

        const bestMoveEl = document.getElementById('resBestMove');
        if (bestMoveEl) {
            const highlightMoves = replayMoves.filter(m => m.includes('+') || m.includes('x'));
            if (highlightMoves.length > 0) {
                bestMoveEl.textContent = `${highlightMoves[highlightMoves.length - 1]} (Excellent)`;
            } else if (replayMoves.length > 2) {
                bestMoveEl.textContent = `${replayMoves[2]} (Book)`;
            } else {
                bestMoveEl.textContent = 'Available in full review';
            }
        }

        const blunderEl = document.getElementById('resBlunder');
        if (blunderEl) {
            blunderEl.textContent = replayMoves.length > 20 ? '1 mistake (Full review)' : 'None';
        }

        // Delay the overlay and celebration effects by 0.5 seconds
        setTimeout(() => {
            // Add celebration effects for wins
            if (isCelebration) {
                gameOverOverlay.classList.add('game-over-celebration');
                createConfetti();
                createSparkles();
            } else {
                gameOverOverlay.classList.remove('game-over-celebration');
            }

            // Prepare for fade-in animation
            gameOverOverlay.style.transition = 'opacity 0.5s ease-in-out';
            gameOverOverlay.style.opacity = '0';
            gameOverOverlay.classList.add('active');

            // Trigger fade-in after a short delay
            setTimeout(() => {
                gameOverOverlay.style.opacity = '1';
            }, 500);
        }, 500);

        showStatus(title + ': ' + message, false);

        // Clean a11y announcement
        const winnerColorText = color === 'white' ? 'Black' : 'White';
        let cleanMsg = reason === 'checkmate' || reason === 'resign'
            ? `Game over. ${winnerColorText} wins by ${reason}.`
            : `Game over. Draw by ${reason || 'stalemate'}.`;
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

            // Player clock — update time and highlight on their turn
            if (playerTimeEl) playerTimeEl.textContent = formatTime(playerColor === 'white' ? whiteTime : blackTime);
            if (playerClock) {
                playerClock.classList.toggle('active', turn === playerColor);
                const playerTime = playerColor === 'white' ? whiteTime : blackTime;
                playerClock.classList.toggle('low', playerTime <= 60 && playerTime > 0);
            }

            // AI clock — static, never highlights, never updates time
            if (aiTimeEl) aiTimeEl.textContent = '🤖';
            if (aiClock) aiClock.classList.remove('active');

        } else {
            // PvP — both clocks update normally
            if (wTime) wTime.textContent = formatTime(whiteTime);
            if (bTime) bTime.textContent = formatTime(blackTime);
            if (whiteClock) whiteClock.classList.toggle('active', turn === 'white');
            if (blackClock) blackClock.classList.toggle('active', turn === 'black');
        }
        const wYou = document.getElementById('whiteYouTag');
        const bYou = document.getElementById('blackYouTag');
        if (wYou) wYou.style.display = (gameMode === 'ai' && playerColor === 'white') ? 'inline' : 'none';
        if (bYou) bYou.style.display = (gameMode === 'ai' && playerColor === 'black') ? 'inline' : 'none';
    }

    function updatePauseUI() {
        pauseBtn.textContent = paused ? 'Resume' : 'Pause';
        pauseBtn.classList.toggle('paused', paused);
        boardEl.classList.toggle('paused', paused);
        if (paused) {
            boardEl.setAttribute('aria-label', 'Game paused. Click board or press P to resume.');
            boardEl.style.cursor = 'pointer';
            boardEl.style.pointerEvents = 'auto';
        } else {
            boardEl.removeAttribute('aria-label');
            boardEl.style.cursor = '';
            boardEl.style.pointerEvents = '';
        }
    }

    function startTimer() {
        clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            if (paused || gameOver) return;
            if (turn === 'white' && whiteTime > 0) whiteTime--;
            if (turn === 'black' && blackTime > 0) blackTime--;
            renderClocks();

            if (turn === 'white' && whiteTime === 0) {
                endGame('timeout', 'white');
            } else if (turn === 'black' && blackTime === 0) {
                endGame('timeout', 'black');
            }
        }, 1000);
    }

    function toggleBoardOrientation() {
        flipped = !flipped;
        buildBoard();
    }

    async function pauseGame() {
        if (paused) return;
        const d = await post('/api/pause/', { pause: true });
        paused = d.paused;
        whiteTime = d.white_time;
        blackTime = d.black_time;
        updatePauseUI();
        renderClocks();
    }

    async function resumeGame() {
        if (!paused) return;
        const d = await post('/api/pause/', { pause: false });
        paused = d.paused;
        whiteTime = d.white_time;
        blackTime = d.black_time;
        updatePauseUI();
        renderClocks();
        startTimer();
        queueAIMoveIfNeeded();
    }

    /* ==========================================================
    WELCOME & CONFIRMATION LOGIC
    ========================================================== */
    let confirmCallback = null;
    function showConfirm(title, msg, callback, titleColor = '#ff6b6b') {
        if (confirmTitle) {
            confirmTitle.textContent = title;
            confirmTitle.style.color = titleColor;
        }
        if (confirmMessage) confirmMessage.innerHTML = msg;
        confirmCallback = callback;
        confirmOverlay.classList.add('active');
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
        const diffContainer = document.getElementById('confirmDifficultyContainer');
        if (mode === 'ai') {
            diffContainer.style.display = 'block';
        } else {
            diffContainer.style.display = 'none';
        }

        showConfirm(
            "Abandon Game?",
            "Your current progress will be lost.<br>Are you sure you want to start a new game?",
            () => {
                const diff = document.getElementById('confirmDifficultySelect').value;
                const timeLimitMins = parseInt(document.getElementById('confirmTimerSelect').value, 10);
                if (mode === 'ai') {
                    showSideSelectionModal(side => startNewGame('ai', side, diff, null, timeLimitMins));
                } else {
                    startNewGame('pvp', 'white', diff, null, timeLimitMins);
                }
            },
            '#ff6b6b'
        );
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
            '#f0c040'
        );
    }


    async function startNewGame(mode, pColor = 'white', difficulty = 'medium', fen = null, timeLimitMins = null, overrideNames = null) {
        replayMode = false;

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
        // Reset AI request sequence and thinking state on new game
        aiRequestSeq = 0;
        aiThinking = false;


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
        const wName = normalizeName(
            overrideNames ? overrideNames.white : document.getElementById('whiteNameInput')?.value,
            'White'
        );
        const bName = normalizeName(
            overrideNames ? overrideNames.black : document.getElementById('blackNameInput')?.value,
            'Black'
        );
        let currentMins = selectedMins;
        let currentInc = selectedIncrement;

        if (timeLimitMins !== null) {
            const strVal = String(timeLimitMins);
            if (strVal.includes('|')) {
                const parts = strVal.split('|');
                currentMins = parseInt(parts[0], 10) || 10;
                currentInc = parseInt(parts[1], 10) || 0;
            } else {
                currentMins = parseInt(strVal, 10) || 10;
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
            increment: increment
        };

        const fenValue = fen ? fen.trim() : null;
        if (fenValue) payload.fen = fenValue;

        if (fenError) fenError.textContent = '';
        if (welcomeFenError) welcomeFenError.textContent = '';

        const d = await post('/api/new-game/', payload);

        if (d.valid === false || !d.board) {
            const message = d.message || 'Unable to start a new game.';
            if (fenError) fenError.textContent = message;
            if (welcomeFenError && welcomeOverlay?.classList.contains('active')) {
                welcomeFenError.textContent = message;
            }
            showStatus(message, true);
            return false;
        }

        board = d.board;
        turn = d.current_turn;
        paused = false;
        gameOver = false;
        gameMode = d.mode;
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
        if (newFenBtn) newFenBtn.style.display = 'none';
        if (gameMode === 'ai') {
            flipped = (playerColor === 'black');
        } else {
            flipped = false;
        }

        if (modeBadge) modeBadge.textContent = gameMode === 'ai' ? 'VS AI' : 'PVP';

        const emotePanel = document.getElementById('emotePanel');
        if (emotePanel) {
            emotePanel.style.display = gameMode === 'pvp' ? 'block' : 'none';
        }
        movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
        wCapEl.innerHTML = bCapEl.innerHTML = '';

        await loadGame();
        // Apply active state after UI reload
        updateModeButtonsUI(gameMode);
        paused = false;
        updatePauseUI();

        // Auto-trigger AI if it's their turn
        if (gameMode === 'ai' && turn !== playerColor) {
            queueAIMoveIfNeeded();
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

            autoReplayInterval = setInterval(() => {

                if (replayIndex >= replayMoves.length) {

                    clearInterval(autoReplayInterval);
                    autoReplayInterval = null;

                    playReplayBtn.textContent = '▶';

                    return;
                }
                replayIndex++;
                goToReplayMove(replayIndex);

            }, 1000);
        };
    }

    if (playReplayBtn) {
        playReplayBtn.onclick = () => {

            if (autoReplayInterval) {
                clearInterval(autoReplayInterval);
                autoReplayInterval = null;
                playReplayBtn.textContent = '▶';
                return;
            }
            playReplayBtn.textContent = '⏸';

            autoReplayInterval = setInterval(() => {

                if (replayIndex >= replayMoves.length) {
                    clearInterval(autoReplayInterval);
                    autoReplayInterval = null;
                    playReplayBtn.textContent = '▶';
                    return;
                }
                replayIndex++;
                goToReplayMove(replayIndex);

            }, 1000);
        };
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

    if (welcomePvPBtn) welcomePvPBtn.onclick = async () => {
        if (!validatePlayerNames()) return;
        const fen = welcomeFenInput?.value || null;
        const started = await startNewGame('pvp', 'white', 'medium', fen);
        if (!started) return;
        welcomeOverlay.classList.remove('active');
        gameLayout.style.visibility = 'visible';
    };


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
    const colorBtns = pveOptions.querySelectorAll('.color-choice');
    colorBtns.forEach(btn => {
        btn.onclick = () => {
            colorBtns.forEach(b => {
                b.classList.remove('active');
                b.style.borderColor = '#444';
            });
            btn.classList.add('active');
            btn.style.borderColor = '#f0c040';
            selectedPveColor = btn.dataset.color;
        };
    });

    if (startAIBtn) startAIBtn.onclick = async () => {
        const wNameInput = document.getElementById('whiteNameInput');
        const errorDiv = document.getElementById('nameError');

        const playerName = wNameInput?.value.trim();

        // Validate: AI mode only needs ONE name
        if (!playerName) {
            if (errorDiv) {
                errorDiv.style.display = 'block';
                errorDiv.textContent = '⚠️ Please enter your name';
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
        const fen = welcomeFenInput?.value || null;
        const started = await startNewGame('ai', selectedPveColor, diff, fen);
        if (!started) return;
        welcomeOverlay.classList.remove('active');
        gameLayout.style.visibility = 'visible';
    };

    if (autoFlipBtn) autoFlipBtn.onclick = () => {
        autoFlip = !autoFlip;
        autoFlipBtn.textContent = 'Auto-Flip: ' + (autoFlip ? 'ON' : 'OFF');
        autoFlipBtn.style.background = autoFlip ? 'linear-gradient(135deg, #40c0f0, #2080d4)' : '';
        if (autoFlip && gameMode === 'pvp') {
            flipped = (turn === 'black');
            buildBoard();
        }
    };
    if (copyPgnBtn) copyPgnBtn.onclick = async () => {
        const data = await get('/api/state/');

        if (data.pgn) {
            const blob = new Blob([data.pgn], { type: 'text/plain' });
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

    if (copyFenBtn) copyFenBtn.onclick = async () => {
        const data = await get('/api/state/');
        if (data.fen) {
            navigator.clipboard.writeText(data.fen);

            copyFenBtn.textContent = 'Copied!';
            clearTimeout(fenCopyTimeout);

            fenCopyTimeout = setTimeout(() => {
                copyFenBtn.textContent = 'Copy FEN';
            }, 2000);
        }
    };

    if (welcomeResumeBtn) welcomeResumeBtn.onclick = async () => {
        const data = await post('/api/resume/', {});
        if (!data.valid) {
            welcomeResumeBtn.style.display = 'none';
            return;
        }
        welcomeOverlay.classList.remove('active');
        gameLayout.style.visibility = 'visible';
        paused = false;
        updatePauseUI();
        startTimer();
        queueAIMoveIfNeeded();
    };

    if (confirmYesBtn) confirmYesBtn.onclick = () => {
        confirmOverlay.classList.remove('active');
        if (confirmCallback) confirmCallback();
        confirmCallback = null;
    };
    if (confirmNoBtn) confirmNoBtn.onclick = () => {
        confirmOverlay.classList.remove('active');
        confirmCallback = null;
    };
    //added new line here
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
            "Your current progress will be lost.<br>Are you sure you want to start a new game?",
            () => {
                prepareWelcomeForPvP(true);
                welcomeOverlay.classList.add('active');
            },
            '#ff6b6b'
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

    if (newFenBtn) newFenBtn.onclick = () => {
        showConfirm(
            "Load from FEN?",
            "Your current progress will be lost.<br>Do you want to continue?",
            () => {
                if (fenError) fenError.textContent = '';
                if (fenInput) fenInput.value = '';
                fenOverlay.classList.add('active');
            },
            '#ff6b6b'
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
        gameLayout.style.visibility = 'visible';
    };

    if (fenCancelBtn) fenCancelBtn.onclick = () => {
        fenOverlay.classList.remove('active');
    };

    if (pauseBtn) pauseBtn.onclick = () => paused ? resumeGame() : pauseGame();
    if (muteBtn) muteBtn.onclick = toggleMute;
    if (flipBtn) flipBtn.onclick = toggleBoardOrientation;

    if (resignBtn) resignBtn.onclick = () => {
        if (!gameOver && !paused) {
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
    };

    if (drawBtn) drawBtn.onclick = offerDraw;
    if (drawAcceptBtn) drawAcceptBtn.onclick = async () => {
        drawOverlay.classList.remove('active');
        const data = await post('/api/draw/', { action: 'accept' });
        if (data.success) {
            if (soundEnabled) { sounds.draw.currentTime = 0; sounds.draw.play().catch(() => { }); }
            endGame('draw', turn, data.draw_reason);
        }
    };
    if (drawDeclineBtn) drawDeclineBtn.onclick = () => {
        drawOverlay.classList.remove('active');
        resumeGame();
    };

    if (gameOverStartBtn) gameOverStartBtn.onclick = () => {
        const modeEl = document.querySelector('input[name="go_mode"]:checked');
        const diffEl = document.getElementById('goDifficultySelect');
        const timerEl = document.getElementById('goTimerSelect');

        if (!modeEl || !diffEl || !timerEl) {
            console.error('Game-over restart: missing UI elements');
            return;
        }

        const mode = modeEl.value;
        const diff = diffEl.value;
        const timeLimitMins = parseInt(timerEl.value, 10);
        gameOverOverlay.classList.remove('active');
        gameOverOverlay.classList.remove('game-over-celebration');

        const confettiContainer = gameOverOverlay.querySelector('.confetti-container');
        if (confettiContainer) {
            confettiContainer.remove();
        }

        if (mode === 'ai') {
            showSideSelectionModal(side => startNewGame(mode, side, diff, null, timeLimitMins));
        } else {
            startNewGame(mode, 'white', diff, null, timeLimitMins);
        }
    };
    const resRematchBtn = document.getElementById('resRematchBtn');
    if (resRematchBtn) {
        resRematchBtn.onclick = () => {
            gameOverOverlay.classList.remove('active', 'game-over-celebration');
            const cc = gameOverOverlay.querySelector('.confetti-container');
            if (cc) cc.remove();
            const mode = gameMode;
            const pColor = playerColor;
            const diff = currentDifficulty;
            const timeLimitString = `${selectedMins}|${selectedIncrement}`;
            startNewGame(mode, pColor, diff, null, timeLimitString, {
                white: whiteNameLabel?.textContent || 'White',
                black: blackNameLabel?.textContent || 'Black'
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

    // ========== Exit to Menu Logic ==========
    const exitToMenuBtn = document.getElementById('exitToMenuBtn');
    if (exitToMenuBtn) {
        exitToMenuBtn.onclick = () => {
            // 1. Hide the Game Over modal and clear celebrations
            gameOverOverlay.classList.remove('active', 'game-over-celebration');
            const confettiContainer = gameOverOverlay.querySelector('.confetti-container');
            if (confettiContainer) {
                confettiContainer.remove();
            }

            // 2. Hide the chess board layout
            gameLayout.style.visibility = 'hidden';

            // 3. Reset and show the Welcome/Setup Menu
            prepareWelcomeForPvP(true);
            welcomeOverlay.classList.add('active');
        };
    }

    // Theme Switcher
    function initThemeSwitcher() {
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

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initThemeSwitcher);
    } else {
        initThemeSwitcher();
    }

    document.addEventListener('visibilitychange', async () => {
        if (document.hidden) {
            pauseGame().catch(() => { });
        } else {
            await handleReconnect();
        }
    });

    window.addEventListener('online', async () => {
        if (!gameOver) {
            await handleReconnect();
        }
    });
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
                    return;
                }
                if (gameMode === 'ai' && turn !== playerColor) {
                    if (manualMoveError) {
                        manualMoveError.textContent = 'Not your turn';
                        manualMoveError.style.display = 'block';
                    }
                    return;
                }
                const p = board[fr][fc];
                if (!p || pColor(p) !== turn) {
                    if (manualMoveError) {
                        manualMoveError.textContent = 'Invalid piece';
                        manualMoveError.style.display = 'block';
                    }
                    return;
                }

                if (isPromotionMove(fr, fc, tr) && !promo) {
                    if (manualMoveError) {
                        manualMoveError.textContent = 'Promotion piece required (e.g. e7e8q)';
                        manualMoveError.style.display = 'block';
                    }
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

        const tag = document.activeElement && document.activeElement.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

        if (document.querySelector('.modal.show, [role="dialog"]:not([hidden]), .promo-overlay.active')) return;

        const key = e.key.toLowerCase();
        if (key === 'f' && flipBtn) {
            e.preventDefault();
            flipBtn.click();
        } else if (key === 'r' && resignBtn) {
            e.preventDefault();
            resignBtn.click();
        } else if (key === 'd' && drawBtn && drawBtn.style.display !== 'none' && !drawBtn.disabled) {
            e.preventDefault();
            drawBtn.click();
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
            emoteEl.className = 'floating-emote ' + (turn === 'white' ? 'white-emote' : 'black-emote');
            emoteEl.textContent = emoteChar;
            const boardOuter = document.querySelector('.board-outer');
            if (boardOuter) {
                boardOuter.appendChild(emoteEl);
                setTimeout(() => emoteEl.remove(), 2000);
            }
        });
    });

    // Show browser confirmation dialog if user tries to leave during an active game
    // Skip beforeunload alert in Selenium tests to prevent UnexpectedAlertPresentException
    if (!navigator.webdriver) {
        window.addEventListener('beforeunload', (e) => {
            if (!paused) {
                navigator.sendBeacon('/api/pause/', JSON.stringify({ pause: true }));
            }
            if (!gameOver && !welcomeOverlay.classList.contains('active')) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    }


    if (typeof module !== "undefined" && module.exports) {
        module.exports = { pColor, getSquareLabel, formatTime };
    } else {
        loadGame();
    }

})();


