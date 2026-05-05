(() => {
            'use strict';

            /* ==========================================================
            CONSTANTS & STATE
            ========================================================== */
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
            let paused = false;
            let timerInterval = null;
            let pendingPromo = null;

            let gameMode = 'pvp';
            let playerColor = 'white';
            let flipped = false;
            let autoFlip = false;

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
            const promoOverlay = document.getElementById('promoOverlay');
            const promoChoices = document.getElementById('promoChoices');
            const modeBadge = document.getElementById('modeBadge');
            const autoFlipBtn = document.getElementById('autoFlipBtn');
            const flipControls = document.getElementById('flipControls');
            const copyFenBtn = document.getElementById('copyFenBtn');

            const welcomeOverlay = document.getElementById('welcomeOverlay');
            const welcomeResumeBtn = document.getElementById('welcomeResumeBtn');
            const welcomePvPBtn = document.getElementById('welcomePvPBtn');
            const welcomeAIBtn = document.getElementById('welcomeAIBtn');
            
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

            const gameOverOverlay = document.getElementById('gameOverOverlay');
            const gameOverTitle = document.getElementById('gameOverTitle');
            const gameOverMessage = document.getElementById('gameOverMessage');
            const gameOverStartBtn = document.getElementById('gameOverStartBtn');
            const gameOverPvPBtn = document.getElementById('gameOverPvPBtn');
            const gameOverAIBtn = document.getElementById('gameOverAIBtn');

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

            let gameOver = false;

            /* ==========================================================
            CSRF & API HELPERS
            ========================================================== */
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

            const pKey = p => p ? ((p === p.toUpperCase() ? 'w' : 'b') + p.toLowerCase()) : null;
            const pColor = p => p ? (p === p.toUpperCase() ? 'white' : 'black') : null;
            const sq = (r, c) => {
                const vr = flipped ? 7 - r : r;
                const vc = flipped ? 7 - c : c;
                return boardEl.children[vr * 8 + vc];
            };

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

            /* ==========================================================
            LOAD GAME STATE
            ========================================================== */
            async function loadGame() {
                const data = await get('/api/state/');

                board = parseBoard(data.board);
                turn = data.current_turn;
                whiteTime = data.white_time;
                blackTime = data.black_time;
                paused = data.paused;

                gameMode = data.mode || 'pvp';
                playerColor = data.player_color || 'white';
                
                if (flipControls) {
                    flipControls.style.display = (gameMode === 'pvp') ? 'flex' : 'none';
                }

                if (gameMode === 'ai') {
                    flipped = (playerColor === 'black');
                } else {
                    flipped = false;
                }

                if (modeBadge) modeBadge.textContent = gameMode === 'ai' ? 'VS AI' : 'PVP';

                // Show Resume button if we have an ongoing game
                const hasMoves = data.move_history && data.move_history.length > 0;
                const isAI = data.mode === 'ai';
                if (hasMoves || isAI) {
                    if (welcomeResumeBtn) welcomeResumeBtn.style.display = 'block';
                } else {
                    if (welcomeResumeBtn) welcomeResumeBtn.style.display = 'none';
                }

                if (drawBtn) drawBtn.style.display = gameMode === 'pvp' ? 'block' : 'none';

                updatePlayerNames(data);
                updateTurn();
                updateMoves(data.move_history);
                updateCaptured(data.captured_pieces);

                buildBoard();
                renderClocks();
                updatePauseUI();
                startTimer();
            }

            function updatePlayerNames(data) {
                let wName = data.white_name || 'White';
                let bName = data.black_name || 'Black';
                
                if (gameMode === 'ai') {
                    if (playerColor === 'white') bName = bName + ' (AI)';
                    else wName = wName + ' (AI)';
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
                const ranks = ['8','7','6','5','4','3','2','1'];
                const files = ['a','b','c','d','e','f','g','h'];
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
                    img.draggable = true;
                    img.ondragstart = e => onDragStart(e, r, c);
                    img.ondragend = () => dragging = false;
                    el.appendChild(img);
                }
                refreshHighlights();
                markPlayable();
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
                    el.classList.remove('selected', 'last-move');
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

            // converts row/col to chess notation e.g. row=0,col=0 → "a8"
            function getSquareLabel(row, col) {
                const files = ['a','b','c','d','e','f','g','h'];
                const ranks = ['8','7','6','5','4','3','2','1'];
                    return files[col] + ranks[row];
            }

            // Arrow keys to move focus, Enter/Space to click, Escape to cancel
            function handleSquareKeydown(e, row, col) {
                let newRow = row;
                let newCol = col;

                switch (e.key) {
                    case 'ArrowUp':    e.preventDefault(); newRow = row - 1; break;
                    case 'ArrowDown':  e.preventDefault(); newRow = row + 1; break;
                    case 'ArrowLeft':  e.preventDefault(); newCol = col - 1; break;
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
                await executeMove(fr, fc, tr, tc, choice);
            }

            async function tryMove(fr, fc, tr, tc) {
                if (paused || gameOver) return;
                const p = board[fr][fc];
                if (!p || pColor(p) !== turn) return;

                if (isPromotionMove(fr, fc, tr)) {
                    pendingPromo = { fr, fc, tr, tc };
                    const color = pColor(p);
                    showPromoModal(color);
                    return;
                }
                await executeMove(fr, fc, tr, tc, null);
            }

            async function executeMove(fr, fc, tr, tc, promotionPiece) {
                try {
                    const body = {
                        from_row: fr, from_col: fc,
                        to_row: tr, to_col: tc,
                    };
                    if (promotionPiece) body.promotion_piece = promotionPiece;

                    const data = await post('/api/move/', body);
                    if (data.valid) {
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

                        if (data.game_status === 'checkmate') {
                            endGame('checkmate', turn);
                        } else if (data.game_status === 'stalemate') {
                            endGame('stalemate', turn);
                        } else if (data.game_status === 'check') {
                            showStatus(turn === 'white' ? 'White is in check!' : 'Black is in check!', true);
                        } else {
                            showStatus('', false);
                        }

                        if (gameMode === 'ai' && turn !== playerColor && !gameOver) {
                            requestAIMove();
                        }
                    } else {
                        showStatus(data.message, true);
                        deselect();
                    }
                } catch (e) {
                    showStatus('Connection error.', true);
                }
            }

            async function requestAIMove() {
                if (gameOver) return;
                showStatus('AI is thinking...', false);
                try {
                    const data = await post('/api/ai-move/', {});
                    if (data.valid) {
                        const mv = data.ai_move;
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

                        if (data.game_status === 'checkmate') {
                            endGame('checkmate', turn);
                        } else if (data.game_status === 'stalemate') {
                            endGame('stalemate', turn);
                        } else if (data.game_status === 'check') {
                            showStatus('You are in check!', true);
                        } else {
                            showStatus('Your turn.', false);
                        }
                    } else {
                        showStatus(data.message, true);
                    }
                } catch (e) {
                    showStatus('AI connection error.', true);
                }
            }

            /* ==========================================================
            EVENTS
            ========================================================== */
            async function onClick(r, c) {
                if (dragging) return;
                if (selected) {
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
                if (!dragSrc) return;
                await tryMove(dragSrc.r, dragSrc.c, tr, tc);
                dragSrc = null;
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
                for (let i = 0; i < history.length; i += 2) {
                    const row = document.createElement('div');
                    row.className = 'move-row';
                    row.innerHTML = `
                        <span class="move-num">${i / 2 + 1}.</span>
                        <span class="move-white">${history[i].notation}</span>
                        ${history[i + 1] ? `<span class="move-black">${history[i + 1].notation}</span>` : ''}
                    `;
                    movesEl.appendChild(row);
                }
            }

            function updateCaptured(cap) {
                wCapEl.innerHTML = bCapEl.innerHTML = '';
                cap.white.forEach(p => wCapEl.innerHTML += `<img src="${PIECE_IMG[pKey(p)]}" class="captured-img">`);
                cap.black.forEach(p => bCapEl.innerHTML += `<img src="${PIECE_IMG[pKey(p)]}" class="captured-img">`);
            }

            function showStatus(msg, err) {
                statusEl.textContent = msg;
                statusEl.className = 'status-bar' + (err ? ' error' : '');
            }

            function endGame(reason, color) {
                if (gameOver) return;
                gameOver = true;
                paused = true;
                clearInterval(timerInterval);

                let title = '', message = '';

                if (reason === 'checkmate') {
                    const winner = color === 'white' ? 'Black' : 'White';
                    title = 'Checkmate!';
                    message = `${winner} wins!`;
                } else if (reason === 'stalemate') {
                    title = 'Stalemate!';
                    message = 'The game is a draw.';
                } else if (reason === 'draw') {
                    title = 'Draw!';
                    message = 'Draw by Agreement.';
                } else if (reason === 'resign') {
                    const winner = color === 'white' ? 'Black' : 'White';
                    const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
                    const loserName = color === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;
                    title = 'Resignation';
                    message = `${loserName} resigned. ${winnerName} wins!`;
                }

                gameOverTitle.textContent = title;
                gameOverMessage.textContent = message;
                gameOverOverlay.classList.add('active');
                showStatus(title + ': ' + message, false);
                document.title = 'Game Over - Checkora';
            }

            /* ==========================================================
            CLOCKS & PAUSE
            ========================================================== */
            const fmt = t => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
            function formatTime(t) { return fmt(t); }

            function renderClocks() {
                const wTime = document.getElementById('whiteTime');
                const bTime = document.getElementById('blackTime');
                if (wTime) wTime.textContent = formatTime(whiteTime);
                if (bTime) bTime.textContent = formatTime(blackTime);

                const whiteClock = document.getElementById('whiteClock');
                const blackClock = document.getElementById('blackClock');
                if (whiteClock) whiteClock.classList.toggle('active', turn === 'white');
                if (blackClock) blackClock.classList.toggle('active', turn === 'black');

                const wYou = document.getElementById('whiteYouTag');
                const bYou = document.getElementById('blackYouTag');
                if (wYou) wYou.style.display = (gameMode === 'ai' && playerColor === 'white') ? 'inline' : 'none';
                if (bYou) bYou.style.display = (gameMode === 'ai' && playerColor === 'black') ? 'inline' : 'none';
            }

            function updatePauseUI() {
                pauseBtn.textContent = paused ? 'Resume' : 'Pause';
            }

            function startTimer() {
                clearInterval(timerInterval);
                timerInterval = setInterval(() => {
                    if (paused) return;
                    if (turn === 'white' && whiteTime > 0) whiteTime--;
                    if (turn === 'black' && blackTime > 0) blackTime--;
                    renderClocks();
                }, 1000);
            }

            async function pauseGame() {
                if (paused) return;
                const d = await post('/api/pause/', {
                    pause: true,
                    white_time: whiteTime,
                    black_time: blackTime
                });
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
                        startNewGame(mode, diff);
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

            async function startNewGame(mode, pColor = 'white', difficulty = 'medium') {
                const wName = document.getElementById('whiteNameInput')?.value || 'White';
                const bName = document.getElementById('blackNameInput')?.value || 'Black';

                const d = await post('/api/new-game/', {
                    mode: mode,
                    player_color: pColor,
                    white_name: wName,
                    black_name: bName,
                    difficulty: difficulty
                });

                board = d.board;
                turn = d.current_turn;
                paused = false;
                gameOver = false;
                gameMode = d.mode;
                playerColor = d.player_color || 'white';
                
                if (gameMode === 'ai') {
                    flipped = (playerColor === 'black');
                } else {
                    flipped = false;
                }

                if (modeBadge) modeBadge.textContent = gameMode === 'ai' ? 'VS AI' : 'PVP';
                movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
                wCapEl.innerHTML = bCapEl.innerHTML = '';

                await loadGame();
                paused = false;
                updatePauseUI();

                // Auto-trigger AI if it's their turn
                if (gameMode === 'ai' && turn !== playerColor) {
                    requestAIMove();
                }
            }

            /* ==========================================================
            EVENT LISTENERS
            ========================================================== */
            let selectedPveColor = 'white';

            if (welcomePvPBtn) welcomePvPBtn.onclick = () => {
                welcomeOverlay.classList.remove('active');
                gameLayout.style.visibility = 'visible';
                startNewGame('pvp');
            };

            if (welcomeAIBtn) welcomeAIBtn.onclick = () => {
                nameInputs.style.display = 'none';
                modeSelection.style.display = 'none';
                pveOptions.style.display = 'flex';
            };

            if (backToModes) backToModes.onclick = () => {
                pveOptions.style.display = 'none';
                modeSelection.style.display = 'flex';
                nameInputs.style.display = 'flex';
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

            if (startAIBtn) startAIBtn.onclick = () => {
                const diff = document.getElementById('welcomeDifficultySelect').value;
                welcomeOverlay.classList.remove('active');
                gameLayout.style.visibility = 'visible';
                startNewGame('ai', selectedPveColor, diff);
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

            if (copyFenBtn) copyFenBtn.onclick = async () => {
                const data = await get('/api/state/');
                if (data.fen) {
                    navigator.clipboard.writeText(data.fen);
                    const oldText = copyFenBtn.textContent;
                    copyFenBtn.textContent = 'Copied!';
                    setTimeout(() => copyFenBtn.textContent = oldText, 2000);
                }
            };

            if (welcomeResumeBtn) welcomeResumeBtn.onclick = () => {
                welcomeOverlay.classList.remove('active');
                gameLayout.style.visibility = 'visible';
                if (paused) resumeGame();
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

            if (newPvPBtn) newPvPBtn.onclick = () => requestNewGame('pvp');
            if (newAIBtn) newAIBtn.onclick = () => requestNewGame('ai');

            if (pauseBtn) pauseBtn.onclick = () => paused ? resumeGame() : pauseGame();

            if (resignBtn) resignBtn.onclick = () => {
                if (!gameOver && !paused) {
                    showConfirm("Resign?", "Are you sure you want to resign?", () => endGame('resign', turn));
                }
            };

            if (drawBtn) drawBtn.onclick = offerDraw;
            if (drawAcceptBtn) drawAcceptBtn.onclick = async () => {
                drawOverlay.classList.remove('active');
                const data = await post('/api/draw/', { action: 'accept' });
                if (data.success) endGame('draw', turn);
            };
            if (drawDeclineBtn) drawDeclineBtn.onclick = () => {
                drawOverlay.classList.remove('active');
                resumeGame();
            };

            if (gameOverStartBtn) gameOverStartBtn.onclick = () => {
                const mode = document.querySelector('input[name="go_mode"]:checked').value;
                const diff = document.getElementById('goDifficultySelect').value;
                gameOverOverlay.classList.remove('active');
                startNewGame(mode, diff);
            };

            // Theme Switcher
            const themeBtns = document.querySelectorAll('.theme-btn');
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'classic';
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

            document.addEventListener('visibilitychange', () => { if (document.hidden) pauseGame(); });
            window.addEventListener('beforeunload', () => {
                if (!paused) {
                    navigator.sendBeacon('/api/pause/', JSON.stringify({
                        pause: true, white_time: whiteTime, black_time: blackTime
                    }));
                }
            });

            /* ==========================================================
            INIT
            ========================================================== */
            loadGame();
        })();