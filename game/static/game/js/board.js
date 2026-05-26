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
            let premove = null;
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
            let selectedMins = 10;
            let selectedIncrement = 0;
            let paused = false;
            let timerInterval = null;
            let pendingPromo = null;
            let blindfoldMode = false;
            let illegalMoveCount = 0;

            let whiteAlertFired = false;
            let blackAlertFired = false;

            let gameStartTime = null;
    
            let gameMode = 'pvp';
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
            let playerColor = 'white';
            let flipped = false;
            let autoFlip = false;

            const SOUND_BASE_URL = window.SOUND_BASE_URL || '/static/game/sounds/';
            const sounds = {
              move:    new Audio(`${SOUND_BASE_URL}move.wav`),
              capture: new Audio(`${SOUND_BASE_URL}capture.mp3`),
              check:   new Audio(`${SOUND_BASE_URL}check.wav`),
              draw:    new Audio(`${SOUND_BASE_URL}draw.mp3`),
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
                if (playback?.catch) playback.catch(() => {});
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
            const shareModal = document.getElementById('shareModal');
            const rulebookModal = document.getElementById('rulebookModal');
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
            const nameInputs = document.getElementById('nameInputs'); 

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
            const gameOverExitBtn = document.getElementById('gameOverExitBtn');
            const gameOverPvPBtn = document.getElementById('gameOverPvPBtn');
            const gameOverAIBtn = document.getElementById('gameOverAIBtn');

            const resignBtn = document.getElementById('resignBtn');
            const drawBtn = document.getElementById('drawBtn');
            let wasPaused = false;
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
            
            // post() uses csrf()
            function csrf() {
                const m = document.cookie.match(/csrftoken=([^;]+)/);
                return m ? decodeURIComponent(m[1]) : '';  // ← returns empty on Vercel
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
                // Reset AI request sequence and thinking state on load/reconnect to cancel stale requests
                aiRequestSeq = 0;
                aiThinking = false;
                premove = null;
                refreshPremoveHighlight();
                whiteAlertFired = false;
                blackAlertFired = false;

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
                if (pauseBtn)  pauseBtn.style.display  = 'block';  
                if (resignBtn) resignBtn.style.display = 'block'; 
                const isActive = ['active', 'check', 'ok'].includes(data.game_status);
                if (newPvPBtn) newPvPBtn.style.display = isActive ? 'none' : '';
                if (newAIBtn) newAIBtn.style.display = isActive ? 'none' : '';
                if (newFenBtn) newFenBtn.style.display = isActive ? 'none' : '';

                updatePlayerNames(data);
                updateTurn();
                updateMoves(data.move_history);
                updateCaptured(data.captured_pieces);

                buildBoard();
                renderClocks();
                updatePauseUI();
                startTimer();
                // fix
                // Removed static styling for AI clock so it displays the countdown timer.

                if (data.game_status && data.game_status !== 'active' && data.game_status !== 'ok') {
                    handleGameStatus(data.game_status, data.draw_reason);
                }
                if (!welcomeOverlay.classList.contains('active')) {
                    queueAIMoveIfNeeded();
                }
            }

            function updatePlayerNames(data) {
                currentWhiteName = data.white_name || currentWhiteName || 'White';
                currentBlackName = data.black_name || currentBlackName || 'Black';
                let wName = currentWhiteName;
                let bName = currentBlackName;
                
                if (gameMode === 'ai'){
                    const diffLabel = (currentDifficulty || 'medium').toUpperCase();
                    const player_name = playerColor === 'white' ? data.white_name : data.black_name;
                    if(playerColor === 'white'){
                        wName = player_name;
                        bName = `AI (Black)`;
                    }else{
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
                        d.oncontextmenu = (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            toggleSquareHighlight(r, c);
                        };
                        d.ondragover = e => e.preventDefault();
                        d.ondrop = e => onDrop(e, r, c);

                        // ADD THESE:
                        d.draggable = true;
                        d.ondragstart = e => {
                            const piece = board[r][c];
                            if (!piece) {
                                if (blindfoldMode) {
                                    showStatus('No piece there', true);
                                    flashBoard();
                                }
                                return e.preventDefault();
                            }
                            if (paused || gameOver) return e.preventDefault();
                            
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
                    const isPlayable = p && (
                        pColor(p) === turn ||
                        (gameMode === 'ai' && pColor(p) === playerColor)
                    );
                    img.classList.toggle('playable', isPlayable);
                });
            }

            function refreshHighlights() {
                boardEl.querySelectorAll('.square').forEach(el => {
                    el.classList.remove('selected', 'last-move', 'in-check', 'custom-highlight');
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
                        el.appendChild(d);
                    });
                }
                refreshPremoveHighlight();
            }

            function refreshPremoveHighlight() {
                boardEl.querySelectorAll('.square').forEach(el => {
                    el.classList.remove('premove');
                });

                if (!premove) return;

                sq(premove.from.r, premove.from.c).classList.add('premove');
                sq(premove.to.r, premove.to.c).classList.add('premove');
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

                // NORMAL MOVE LOGIC
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
                if (!p) return;

                // PREMOVE DURING AI TURN
                if (
                    gameMode === 'ai' &&
                    pColor(p) === playerColor &&
                    turn !== playerColor
                ) {
                    premove = {
                        from: { r: fr, c: fc },
                        to: { r: tr, c: tc }
                    };

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

                if (isPromotionMove(fr, fc, tr)) {
                    await animateMove(fr, fc, tr, tc);

                    pendingPromo = { fr, fc, tr, tc };

                    const color = pColor(p);
                    showPromoModal(color);

                    return;
                }

                await executeMove(fr, fc, tr, tc, null);
            }            let reconnecting = false;
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
            }async function executeMove(fr, fc, tr, tc, promotionPiece, skipAnimation = false) {
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
                        flashBoard();
                        deselect();
                    }
                } catch (e) {
                        await handleReconnect();
                }
            }

            async function requestAIMove() {
                if (gameOver || aiThinking) return;
                // Increment and store current sequence value to identify this specific request
                const seq = ++aiRequestSeq;
                aiThinking = true;
                
                // fix: animated thinking dots
                let dots = 1;
                const thinkingInterval = setInterval(() => {
                    if (!aiThinking) { clearInterval(thinkingInterval); return; }
                    showStatus('AI is thinking' + '.'.repeat(dots), false);
                    dots = (dots % 3) + 1;
                }, 400);

                try {
                    let piecesOnBoard = 0;
                    for (let r = 0; r < 8; r++) {
                        for (let c = 0; c < 8; c++) {
                            if (board[r][c]) piecesOnBoard++;
                        }
                    }

                    // randomized delay per difficulty — feels realistic and unpredictable
                    let delay;
                    if (currentDifficulty === 'easy')       delay = 800  + Math.random() * (1500 - 800);
                    else if (currentDifficulty === 'hard')  delay = 2500 + Math.random() * (4000 - 2500);
                    else                                    delay = 1500 + Math.random() * (2500 - 1500); // medium
                    await new Promise(resolve => setTimeout(resolve, delay));

                    // Abort if a new game started, reconnect happened, or another request took over during delay
                    if (seq !== aiRequestSeq) {
                        clearInterval(thinkingInterval);
                        return;
                    }

                    // fix: abort if game ended during delay
                    if (gameOver) {
                        clearInterval(thinkingInterval);
                        return;
                    }

                    const data = await post('/api/ai-move/', {});
                    clearInterval(thinkingInterval); // fix: clear after API call completes, not before

                    // Abort if sequence is no longer current after API call completes
                    if (seq !== aiRequestSeq) {
                        return;
                    }

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

                            // Trigger queued premove if it exists
                            if (premove) {
                                const queued = premove;
                                premove = null;
                                refreshPremoveHighlight();

                                const piece = board[queued.from.r][queued.from.c];
                                if (piece && pColor(piece) === turn) {
                                    setTimeout(() => {
                                        tryMove(queued.from.r, queued.from.c, queued.to.r, queued.to.c);
                                    }, 150);
                                } else {
                                    showStatus("Premove cancelled: piece captured or invalid", true);
                                }
                            }
                        }
                    } else {
                        showStatus(data.message, true);
                    }
                } catch (e) {
                    clearInterval(thinkingInterval);
                    await handleReconnect();
                } finally {
                    if (seq === aiRequestSeq) {
                        aiThinking = false;
                    }
                }
            }

            /* ==========================================================
            EVENTS
            ========================================================== */
            async function onClick(r, c) {
                if (dragging) return;

                const piece = board[r][c];

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

                        premove = {
                            from: { r: selected.r, c: selected.c },
                            to: { r, c }
                        };

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

                // selecting initial piece
                if (
                    piece &&
                    (
                        pColor(piece) === turn ||
                        (
                            aiPremoveMode &&
                            pColor(piece) === playerColor
                        )
                    )
                ) {
                    return selectPiece(r, c);
                }
            }

            function onDragStart(e, r, c) {

                const piece = board[r][c];
                if (!piece) {
                    if (blindfoldMode) {
                        showStatus('No piece there', true);
                        flashBoard();
                    }
                    return e.preventDefault();
                }
                if (paused || gameOver) return e.preventDefault();
                
                const isPremovedDrag = gameMode === 'ai' && turn !== playerColor && pColor(piece) === playerColor;
                
                // If it's the AI's turn, only allow dragging if it's a valid premove
                if (gameMode === 'ai' && turn !== playerColor && !isPremovedDrag) {
                    return e.preventDefault();
                }
                
                // For all normal moves, you can only drag your own pieces on your turn
                if (!isPremovedDrag && pColor(piece) !== turn) {
                    return e.preventDefault();
                }

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
                    img.src = PIECE_IMG[pKey(p)];
                    img.className = 'captured-img';
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
                
                if (blindfoldMode) {
                    blindfoldMode = false;
                    document.body.classList.remove('blindfold-mode');
                    const blindfoldBtn = document.getElementById('blindfoldBtn');
                    if (blindfoldBtn) blindfoldBtn.textContent = 'Blindfold: OFF';
                }
            
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
                } else if (reason === 'timeout') {
                    const winnerName = color === 'white' ? blackNameLabel.textContent : whiteNameLabel.textContent;
                    const loserName = color === 'white' ? whiteNameLabel.textContent : blackNameLabel.textContent;
                    title = 'Timeout!';
                    message = `${loserName} ran out of time. ${winnerName} wins!`;
                }
                if (resignBtn) resignBtn.style.display = 'none';
                if (drawBtn) drawBtn.style.display = 'none';
                if (pauseBtn) pauseBtn.style.display = 'none';
                if (newPvPBtn) newPvPBtn.style.display = '';
                if (newAIBtn) newAIBtn.style.display = '';
                if (newFenBtn) newFenBtn.style.display = '';

                let durationText = '';

                if (gameStartTime) {
                    const duration = Date.now() - gameStartTime;
                    durationText = `\nGame duration: ${formatGameDuration(duration)}.`;
                }

                gameOverTitle.textContent = title;
                gameOverMessage.textContent = message + durationText;

                const durationElement = document.getElementById('gameDurationText');
                
                if (durationElement) {
                    durationElement.textContent = durationText;
                }

                // Delay the overlay and celebration effects by 1 second
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
                    }, 700);
                }, 500);
                
                showStatus(title + ': ' + message, false);
                
                // Clean a11y announcement
                const winnerColor = color === 'white' ? 'Black' : 'White';
                let cleanMsg = reason === 'checkmate' || reason === 'resign' 
                    ? `Game over. ${winnerColor} wins by ${reason}.` 
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
            }

            function updatePauseUI() {
                pauseBtn.textContent = paused ? 'Resume' : 'Pause';
                pauseBtn.classList.toggle('paused', paused);
                boardEl.classList.toggle('paused', paused);
            }

            function startTimer() {
                clearInterval(timerInterval);
                timerInterval = setInterval(() => {
                    if (paused || gameOver) return;

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
                            sounds.check.play().catch(() => {});
                        }
                        if (!blackAlertFired && blackTime > 0 && blackTime <= 30) {
                            blackAlertFired = true;
                            sounds.check.currentTime = 0;
                            sounds.check.play().catch(() => {});
                        }
                    }

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
                // Reset AI request sequence and thinking state on new game
                aiRequestSeq = 0;
                aiThinking = false;
                premove = null;
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

                const fenValue = (fen && fen.trim()) ? fen.trim() : null;
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
                whiteAlertFired = false;
                blackAlertFired = false;
                
                gameStartTime = Date.now();
                
                gameMode = d.mode;
                playerColor = d.player_color || 'white';
                currentDifficulty = d.difficulty || difficulty;
                if (resignBtn) resignBtn.style.display = '';
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
                lastMove = null;
                highlightedSquare = null;
                selected = null;
                hints = [];
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
                    btn.style.borderColor = isWhite ? '#f0c040' : '#444';
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
                    gameLayout.style.visibility = 'visible';
                });
            }
            
            if (welcomePvPBtn) welcomePvPBtn.onclick = async () => {            
                if (!validatePlayerNames()) return;
                const fen = welcomeFenInput?.value?.trim() || null;
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

                if (wasPaused) {
                    boardEl.classList.add('paused');
                }

                confirmCallback = null;
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
                    "Your current progress will be lost.<br>Are you sure you want to start a new game?",
                    () => {
                        openWelcomeForNewGame();
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
            if (fenInput) {
                fenInput.addEventListener('keydown', async (e) => {
                    if (e.key !== 'Enter') return;
                    e.preventDefault();
                    fenStartBtn?.click();
                });
            }

            if (pauseBtn) pauseBtn.onclick = () => paused ? resumeGame() : pauseGame();
            if (muteBtn) muteBtn.onclick = toggleMute;
            if (flipBtn) flipBtn.onclick = toggleBoardOrientation;
if (resignBtn) resignBtn.onclick = () => {
    if (gameOver) return;

    wasPaused = paused;

    if (wasPaused) {
        boardEl.classList.remove('paused');
    }

    showConfirm("Resign?", "Are you sure you want to resign?", async () => {
        try {
            const result = await post('/api/resign/', {});

            if (result.valid) {
                if (soundEnabled) {
                    sounds.draw.currentTime = 0;
                    sounds.draw.play().catch(() => {});
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
                    showConfirm("Resign?", "Are you sure you want to resign?", async () => {
                        try {
                            const result = await post('/api/resign/', {});
                            if (result.valid) {
                                if (soundEnabled) { sounds.draw.currentTime = 0; sounds.draw.play().catch(() => {}); }
                                endGame('resign', turn);
                            } else {
                                showStatus('Resign failed. Please try again.', true);
                            }
                        } catch (_) {
                            showStatus('Resign failed. Please check your connection and try again.', true);
                        }
                    });
                }
                endGame('resign', turn);
            } else {
                if (wasPaused) boardEl.classList.add('paused');
                showStatus('Resign failed. Please try again.', true);
            }
        } catch (_) {
            if (wasPaused) boardEl.classList.add('paused');
            showStatus('Resign failed. Please check your connection and try again.', true);
        }
    });
};

            if (drawBtn) drawBtn.onclick = offerDraw;
            if (drawAcceptBtn) drawAcceptBtn.onclick = async () => {
                drawOverlay.classList.remove('active');
                const data = await post('/api/draw/', { action: 'accept' });
                if (data.success) {
                    if (soundEnabled) { sounds.draw.currentTime = 0; sounds.draw.play().catch(() => {}); }
                    endGame('draw', turn, data.draw_reason);
                }
            };
            if (drawDeclineBtn) drawDeclineBtn.onclick = () => {
                drawOverlay.classList.remove('active');
                resumeGame();
            };

            if (gameOverStartBtn) gameOverStartBtn.onclick = () => {
                openWelcomeForNewGame();
            };
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

    document.addEventListener('visibilitychange', async() => {
        if (document.hidden) {
            pauseGame().catch(() => {});
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
                            flashBoard();
                            return;
                        }
                        
                        if (manualMoveError) manualMoveError.style.display = 'none';
                        const files = ['a','b','c','d','e','f','g','h'];
                        const ranks = ['8','7','6','5','4','3','2','1'];
                        
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

                const tag = document.activeElement && document.activeElement.tagName;
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

                

                const key = e.key.toLowerCase();
                const hasBlockingOverlay =
                    document.querySelector(
                        '.modal.show, [role="dialog"]:not([hidden]), .promo-overlay.active'
                    ) ||
                    (shareModal?.style.display && shareModal.style.display !== 'none') ||
                    (rulebookModal?.style.display && rulebookModal.style.display !== 'none') ||
                    fenOverlay?.classList.contains('active') ||
                    confirmOverlay?.classList.contains('active') ||
                    drawOverlay?.classList.contains('active') ||
                    gameOverOverlay?.classList.contains('active') ||
                    welcomeOverlay?.classList.contains('active');

            // Allow Escape to close overlays
            if (hasBlockingOverlay && key !== 'escape') {
                return;
            }

                if (key === 'f' && flipBtn) {
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

                } else if (key === 'escape') {
                    e.preventDefault();

                    if (shareModal?.style.display === 'flex') {
                        shareModal.style.display = 'none';
                    }

                    if (rulebookModal?.style.display === 'flex') {
                        rulebookModal.style.display = 'none';
                    }

                    if (fenOverlay?.classList.contains('active')) {
                        fenOverlay.classList.remove('active');
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

           // Custom leave confirmation modal instead of browser default dialog
            if (!navigator.webdriver) {
                window.addEventListener('beforeunload', (e) => {
               if (!paused) {
                    const blob = new Blob([JSON.stringify({ pause: true })], { type: 'application/json' });
                    navigator.sendBeacon('/api/pause/', blob);
                   }
                });
            }

// Leave Game confirmation modal logic
const leaveConfirmOverlay = document.getElementById('leaveConfirmOverlay');
const leaveConfirmYes = document.getElementById('leaveConfirmYes');
const leaveConfirmNo = document.getElementById('leaveConfirmNo');

document.querySelectorAll('a[href="/"]').forEach(link => {
    link.addEventListener('click', (e) => {
        if (!gameOver && !welcomeOverlay.classList.contains('active')) {
            e.preventDefault();
            leaveConfirmOverlay.style.display = 'flex';
        }
    });
});

if (leaveConfirmYes) leaveConfirmYes.addEventListener('click', () => {
    window.location.href = '/';
});

if (leaveConfirmNo) leaveConfirmNo.addEventListener('click', () => {
    leaveConfirmOverlay.style.display = 'none';
});

            
            function showAssetWarning() {
                const t = document.getElementById('confirmTimerContainer');
                const d = document.getElementById('confirmDifficultyContainer');
                if (t) t.style.display = 'none';
                if (d) d.style.display = 'none';

                // 1. Pause the timer while the alert is open
                if (!paused && typeof pauseGame === 'function') {
                    pauseGame().catch(() => {}); // Catch prevents crash if backend hasn't initialized
                }

                showConfirm( //the message on alert
                    "⚠️ Assets Blocked",
                    "<div style='line-height: 1.5; font-size: 0.95rem;'>The chess pieces failed to load.<br><br>Please check your browser permissions (allow images) or disable any ad-blockers on this site.</div>",
                    () => { 
                        // 2. Set a memory flag to bypass the main menu on reload
                        sessionStorage.setItem('checkoraAutoResume', 'true');
                        window.location.reload(); 
                    },
                    '#f0c040'
                );
                
                const yesBtn = document.getElementById('confirmYesBtn');
                const noBtn = document.getElementById('confirmNoBtn');
                if (yesBtn) yesBtn.textContent = 'Reload Page';
                
                // 3. Resume the timer if they click Close
                if (noBtn) {
                    noBtn.textContent = 'Close';
                    const defaultClose = noBtn.onclick; 
                    noBtn.onclick = () => {
                        if (defaultClose) defaultClose();
                        if (paused && typeof resumeGame === 'function') {
                            resumeGame().catch(() => {});
                        }
                    };
                }
            }            function checkAssets() {
                const img = document.querySelector('.piece');
                
                // If a piece exists in the HTML but still has 0 width after 2 seconds, Chrome blocked it.
                if (img && img.naturalWidth === 0) {
                    if (!window.assetWarningShown) {
                        window.assetWarningShown = true;
                        showAssetWarning();
                    }
                }
            }

            // Wait exactly 2 seconds after the script loads to check the assets
            // This gives normal connections plenty of time to load, while catching strict blockers.
            setInterval(checkAssets, 5000);

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
                module.exports = { pColor, getSquareLabel, formatTime };
            } else {
                loadGame();
            }

            boardEl.addEventListener('contextmenu', (e) => {
                e.preventDefault();

                premove = null;
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
                const piece = board[r][c];
                if (!piece || paused || gameOver) return;

                // Check if the piece is playable by the current player (including AI premoves)
                const isPremoveDrag = gameMode === 'ai' && turn !== playerColor && pColor(piece) === playerColor;
                const isNormalDrag = gameMode === 'ai' ? (turn === playerColor && pColor(piece) === playerColor) : (pColor(piece) === turn);

                if (!isPremoveDrag && !isNormalDrag) return;

                touchStartPos = { x: touch.clientX, y: touch.clientY };
                touchDragSrc = { r, c };
                touchDragging = false;
            }, { passive: true });

            boardEl.addEventListener('touchmove', (e) => {
                if (!touchDragSrc) return;

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
                    
                    // Prevent page scrolling while dragging
                    if (e.cancelable) e.preventDefault();
                }
            }, { passive: false });

            boardEl.addEventListener('touchend', (e) => {
                if (!touchDragSrc) return;

                const touch = e.changedTouches[0];
                let movedToSquare = false;

                if (touchDragging) {
                    // Clean up original piece transparency
                    const srcSquareEl = sq(touchDragSrc.r, touchDragSrc.c);
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
                    if (destSquareEl) {
                        const tr = parseInt(destSquareEl.dataset.r);
                        const tc = parseInt(destSquareEl.dataset.c);

                        if (tr !== touchDragSrc.r || tc !== touchDragSrc.c) {
                            tryMove(touchDragSrc.r, touchDragSrc.c, tr, tc);
                            movedToSquare = true;
                        }
                    }

                    if (!movedToSquare) {
                        deselect();
                    }

                    // Prevent click generation
                    e.preventDefault();
                } else {
                    // Quick tap -> trigger default click/tap behavior
                    onClick(touchDragSrc.r, touchDragSrc.c);
                }

                // Reset state
                touchStartPos = null;
                touchDragSrc = null;
                touchDragging = false;
            }, { passive: false });

            boardEl.addEventListener('touchcancel', (e) => {
                if (!touchDragSrc) return;

                if (touchDragging) {
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

                        selectedMins = parseInt(btn.dataset.mins, 10);
                        selectedIncrement = parseInt(btn.dataset.inc, 10);

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
                        const incInput = document.getElementById('customIncInput');

                        if (minsInput && incInput) {
                            let mins = parseInt(minsInput.value, 10);
                            let inc = parseInt(incInput.value, 10);

                            if (isNaN(mins) || mins < 1) mins = 10;
                            if (mins > 300) mins = 300;
                            if (isNaN(inc) || inc < 0) inc = 0;
                            if (inc > 180) inc = 180;

                            minsInput.value = mins;
                            incInput.value = inc;

                            selectedMins = mins;
                            selectedIncrement = inc;

                            // Update active preset styling
                            presetBtns.forEach(b => b.classList.remove('active'));

                            if (inc > 0) {
                                display.textContent = `${mins} | ${inc}`;
                            } else {
                                display.textContent = `${mins} min`;
                            }

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

})();