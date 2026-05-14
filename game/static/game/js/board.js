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
            let aiThinking = false;

            let pgnCopyTimeout = null;
            let fenCopyTimeout = null;
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

                board = parseBoard(data.board);
                turn = data.current_turn;
                whiteTime = data.white_time;
                blackTime = data.black_time;
                paused = data.paused;

                gameMode = data.mode || 'pvp';
                // Sync UI with current game mode
                updateModeButtonsUI(gameMode);
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
                
                if (gameMode === 'ai'){
                    // Fixing the naming system
                    let player_name = data.white_name;
                    if(playerColor === 'white'){
                        wName = player_name;
                        bName = 'AI (Black)';
                    }else{
                        bName = player_name;
                        wName = 'AI (White)';
                    }
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
            }

            async function executeMove(fr, fc, tr, tc, promotionPiece, skipAnimation = false) {
                try {
                    const body = {
                        from_row: fr, from_col: fc,
                        to_row: tr, to_col: tc,
                    };
                    if (promotionPiece) body.promotion_piece = promotionPiece;

                    const data = await post('/api/move/', body);
                        if (data.valid) {
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

                        if (handleGameStatus(data.game_status, data.draw_reason)) {
                            // Game-ending status has been handled.
                        } else if (data.game_status === 'check') {
                            applyCheckHighlight();
                            showStatus(turn === 'white' ? 'White is in check!' : 'Black is in check!', true);
                        } else {
                            highlightCheck();
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
                if (gameOver || aiThinking) return;
                aiThinking = true;
                showStatus('AI is thinking...', false);
                try {
                    const data = await post('/api/ai-move/', {});
                        if (data.valid) {
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

                        if (handleGameStatus(data.game_status, data.draw_reason)) {
                            // Game-ending status has been handled.
                        } else if (data.game_status === 'check') {
                            applyCheckHighlight();
                            showStatus('You are in check!', true);
                        } else {
                            highlightCheck();
                            showStatus('Your turn.', false);
                        }
                    } else {
                        showStatus(data.message, true);
                    }
                } catch (e) {
                    showStatus('AI connection error.', true);
                } finally {
                    aiThinking = false;
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
                statusEl.textContent = msg;
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

            function endGame(reason, color, drawReason = null) {
                if (gameOver) return;
                gameOver = true;
                paused = true;
                clearInterval(timerInterval);
            
                let title = '', message = '';
                let isCelebration = false; // Track if this is a win (not draw/stalemate)
            
                if (reason === 'checkmate') {
                    const winner = color === 'white' ? 'Black' : 'White';
                    const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
                    title = '🏆 CHECKMATE! 🏆';
                    message = `${winnerName} WINS!`;
                    isCelebration = true;
                } else if (reason === 'stalemate') {
                    title = 'Stalemate!';
                    message = 'The game is a draw.';
                } else if (reason === 'draw') {
                    title = 'Draw!';
                    const drawMessages = {
                        agreement: 'Draw by agreement.',
                        threefold_repetition: 'Draw by threefold repetition.',
                        fifty_move_rule: 'Draw by the fifty-move rule.',
                        insufficient_material: 'Draw by insufficient material.',
                    };
                    message = drawMessages[drawReason] || 'The game is a draw.';
                } else if (reason === 'resign') {
                    const winner = color === 'white' ? 'Black' : 'White';
                    const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
                    const loserName = color === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;
                    title = '🏆 VICTORY! 🏆';
                    message = `${loserName} resigned. ${winnerName} WINS!`;
                    isCelebration = true;
                }
            
                gameOverTitle.textContent = title;
                gameOverMessage.textContent = message;
                
                // Add celebration effects for wins
                if (isCelebration) {
                    gameOverOverlay.classList.add('game-over-celebration');
                    createConfetti();
                    createSparkles();
                } else {
                    gameOverOverlay.classList.remove('game-over-celebration');
                }
                
                gameOverOverlay.classList.add('active');
                showStatus(title + ': ' + message, false);
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
        if (playerClock) playerClock.classList.toggle('active', turn === playerColor);

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
                        if (mode === 'ai') {
                            showSideSelectionModal(side => startNewGame('ai', side, diff));
                        } else {
                            startNewGame('pvp');
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

            async function startNewGame(mode, pColor = 'white', difficulty = 'medium') {

                clearTimeout(pgnCopyTimeout);
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
                
            const wName = (document.getElementById('whiteNameInput')?.value || 'White').trim().slice(0, 17);
            const bName = (document.getElementById('blackNameInput')?.value || 'Black').trim().slice(0, 17);

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
                // Apply active state after UI reload
                updateModeButtonsUI(gameMode);
                paused = false;
                updatePauseUI();

                // Auto-trigger AI if it's their turn
                if (gameMode === 'ai' && turn !== playerColor) {
                    queueAIMoveIfNeeded();
                }
            }

            

            /* ==========================================================
            EVENT LISTENERS
            ========================================================== */
            let selectedPveColor = 'white';

            if (welcomePvPBtn) welcomePvPBtn.onclick = () => {
                if (!validatePlayerNames()) return;
                welcomeOverlay.classList.remove('active');
                gameLayout.style.visibility = 'visible';
                startNewGame('pvp');
            };

            if (welcomeAIBtn) welcomeAIBtn.onclick = () => {
                const whiteInput = document.getElementById('whiteNameInput');
                const blackInput = document.getElementById('blackNameInput');
                const errorDiv = document.getElementById('nameError');
                
                // Show ONLY white input for AI mode
                if (whiteInput) {
                    whiteInput.style.display = 'block';
                    whiteInput.placeholder = 'Your Name';
                    whiteInput.value = '';
                    whiteInput.classList.remove('input-error');
                }
                if (blackInput) {
                    blackInput.style.display = 'none';
                    blackInput.value = 'AI';
                    blackInput.classList.remove('input-error');
                }
                
                // Hide error
                if (errorDiv) errorDiv.style.display = 'none';
                
                nameInputs.style.display = 'flex';
                modeSelection.style.display = 'none';
                pveOptions.style.display = 'flex';
            };

            if (backToModes) backToModes.onclick = () => {
                const whiteInput = document.getElementById('whiteNameInput');
                const blackInput = document.getElementById('blackNameInput');
                const errorDiv = document.getElementById('nameError');
                
                pveOptions.style.display = 'none';
                modeSelection.style.display = 'flex';
                
                // Reset both inputs to visible for PvP
                if (whiteInput) {
                    whiteInput.style.display = 'block';
                    whiteInput.placeholder = 'White Player Name';
                    whiteInput.classList.remove('input-error');
                }
                if (blackInput) {
                    blackInput.style.display = 'block';
                    blackInput.placeholder = 'Black Player Name';
                    blackInput.classList.remove('input-error');
                }
                
                // Hide error
                if (errorDiv) errorDiv.style.display = 'none';
                
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
            if (copyPgnBtn) copyPgnBtn.onclick = async () => {
    const data = await get('/api/state/');

    if (data.pgn) {
        navigator.clipboard.writeText(data.pgn);

        

        copyPgnBtn.textContent = 'Copied!';

        clearTimeout(pgnCopyTimeout);

        pgnCopyTimeout = setTimeout(() => {
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

            if (welcomeResumeBtn) welcomeResumeBtn.onclick = () => {
                welcomeOverlay.classList.remove('active');
                gameLayout.style.visibility = 'visible';
                if (paused) {
                    resumeGame();
                } else {
                    startTimer();
                    queueAIMoveIfNeeded();
                }
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
                
                requestNewGame('pvp');
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

            if (pauseBtn) pauseBtn.onclick = () => paused ? resumeGame() : pauseGame();
            if (flipBtn) flipBtn.onclick = toggleBoardOrientation;

            if (resignBtn) resignBtn.onclick = () => {
                if (!gameOver && !paused) {
                    showConfirm("Resign?", "Are you sure you want to resign?", async () => {
                        await post('/api/resign/', {});
                        endGame('resign', turn);
                    });
                }
            };

            if (drawBtn) drawBtn.onclick = offerDraw;
            if (drawAcceptBtn) drawAcceptBtn.onclick = async () => {
                drawOverlay.classList.remove('active');
                const data = await post('/api/draw/', { action: 'accept' });
                if (data.success) endGame('draw', turn, data.draw_reason);
            };
            if (drawDeclineBtn) drawDeclineBtn.onclick = () => {
                drawOverlay.classList.remove('active');
                resumeGame();
            };

            if (gameOverStartBtn) gameOverStartBtn.onclick = () => {
                const mode = document.querySelector('input[name="go_mode"]:checked').value;
                const diff = document.getElementById('goDifficultySelect').value;
                gameOverOverlay.classList.remove('active');
                gameOverOverlay.classList.remove('game-over-celebration');
                
                // Add this: Clear confetti container
                const confettiContainer = gameOverOverlay.querySelector('.confetti-container');
                if (confettiContainer) {
                    confettiContainer.remove();
                }
                
                if (mode === 'ai') {
                    showSideSelectionModal(side => startNewGame(mode, side, diff));
                } else {
                    startNewGame(mode, 'white', diff);
                }
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
            // Show browser confirmation dialog if user tries to leave during an active game
            window.addEventListener('beforeunload', (e) => {
                if (!paused) {
                    navigator.sendBeacon('/api/pause/', JSON.stringify({ pause: true }));
                }
                if (!gameOver && !welcomeOverlay.classList.contains('active')) {
                    e.preventDefault();
                    e.returnValue = '';
                }
            });
            

          if (typeof module !== "undefined" && module.exports) {
          module.exports = { pColor, getSquareLabel, formatTime };
        } else {
          loadGame();
        }

})();


