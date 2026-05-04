(() => {
    'use strict';

    /* ==========================================================
    CONSTANTS & STATE
    ========================================================== */
    const PIECE_IMG = {};
    for (const c of ['w','b'])
        for (const t of ['k','q','r','b','n','p'])
            PIECE_IMG[c+t] = `https://images.chesscomfiles.com/chess-themes/pieces/neo/150/${c}${t}.png`;

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

    /* ==========================================================
    DOM REFERENCES
    ========================================================== */
    const boardEl   = document.getElementById('board');
    const turnEl    = document.getElementById('turnBadge');
    const statusEl  = document.getElementById('statusBar');
    const movesEl   = document.getElementById('movesList');
    const wCapEl    = document.getElementById('whiteCaptured');
    const bCapEl    = document.getElementById('blackCaptured');
    const pauseBtn  = document.getElementById('pauseBtn');
    const promoOverlay = document.getElementById('promoOverlay');
    const promoChoices = document.getElementById('promoChoices');
    const modeBadge = document.getElementById('modeBadge'); 

    const welcomeOverlay = document.getElementById('welcomeOverlay');
    const welcomeResumeBtn = document.getElementById('welcomeResumeBtn');
    const welcomePvPBtn = document.getElementById('welcomePvPBtn');
    const welcomeAIBtn = document.getElementById('welcomeAIBtn');
    const confirmOverlay = document.getElementById('confirmOverlay');
    const confirmYesBtn = document.getElementById('confirmYesBtn');
    const confirmNoBtn = document.getElementById('confirmNoBtn');
    const newPvPBtn = document.getElementById('newPvPBtn');
    const newAIBtn = document.getElementById('newAIBtn');
    const gameOverOverlay = document.getElementById('gameOverOverlay');
    const gameOverTitle = document.getElementById('gameOverTitle');
    const gameOverMessage = document.getElementById('gameOverMessage');
    const gameOverPvPBtn = document.getElementById('gameOverPvPBtn');
    const gameOverAIBtn = document.getElementById('gameOverAIBtn');

    const drawBtn = document.getElementById('drawBtn');
    const drawOverlay = document.getElementById('drawOverlay');
    const drawMessage = document.getElementById('drawMessage');
    const drawAcceptBtn = document.getElementById('drawAcceptBtn');
    const drawDeclineBtn = document.getElementById('drawDeclineBtn');

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

    const pKey   = p => p ? ((p === p.toUpperCase() ? 'w' : 'b') + p.toLowerCase()) : null;
    const pColor = p => p ? (p === p.toUpperCase() ? 'white' : 'black') : null;
    const sq     = (r,c) => boardEl.children[r*8 + c];

    /* ==========================================================
    LOAD GAME STATE
    ========================================================== */
    async function loadGame() {
        const data = await get('/api/state/');

        board = data.board;
        turn = data.current_turn;
        whiteTime = data.white_time;
        blackTime = data.black_time;
        paused = data.paused;

        const wSaved = data.white_name || 'White';
        const bSaved = data.black_name || 'Black';

        document.getElementById('whiteNameLabel').textContent = wSaved.toUpperCase();
        document.getElementById('blackNameLabel').textContent = bSaved.toUpperCase();

        document.getElementById('whiteNameInput').value = wSaved;
        document.getElementById('blackNameInput').value = bSaved;
        
        document.getElementById('whiteCapturedName').textContent = wSaved;
        document.getElementById('blackCapturedName').textContent = bSaved;

        const currentName = (turn === 'white' ? wSaved : bSaved);
        if (document.getElementById('turnBadgeText')) {
            document.getElementById('turnBadgeText').textContent = currentName;
        }

        gameMode = data.mode || 'pvp';
        if (modeBadge) modeBadge.textContent = gameMode === 'ai' ? 'VS AI' : 'PVP';

        if (data.move_history && data.move_history.length > 0) {
            if (welcomeResumeBtn) welcomeResumeBtn.style.display = 'block';
        } else {
            if (welcomeResumeBtn) welcomeResumeBtn.style.display = 'none';
        }

        if (drawBtn) drawBtn.style.display = gameMode === 'pvp' ? 'block' : 'none';

        updateTurn();
        updateMoves(data.move_history);
        updateCaptured(data.captured_pieces);

        buildBoard();
        renderClocks();
        updatePauseUI();
        startTimer();
    }

    /* ==========================================================
    BOARD RENDERING
    ========================================================== */
    function buildBoard() {
        boardEl.innerHTML = '';
        for (let r=0; r<8; r++) {
            for (let c=0; c<8; c++) {
                const d = document.createElement('div');
                d.className = 'square ' + ((r+c)%2 ? 'dark' : 'light');
                d.onclick = () => onClick(r,c);
                d.ondragover = e => e.preventDefault();
                d.ondrop = e => onDrop(e,r,c);
                boardEl.appendChild(d);
            }
        }
        syncPieces();
    }

    function syncPieces() {
        for (let r=0; r<8; r++) for (let c=0; c<8; c++) {
            const el = sq(r,c);
            el.innerHTML = '';
            const p = board[r][c];
            if (!p) continue;

            const img = document.createElement('img');
            img.src = PIECE_IMG[pKey(p)];
            img.className = 'piece';
            img.draggable = true;
            img.ondragstart = e => onDragStart(e,r,c);
            img.ondragend = () => dragging = false;
            el.appendChild(img);
        }
        refreshHighlights();
        markPlayable();
    }

    function markPlayable() {
        boardEl.querySelectorAll('.piece').forEach(img => {
            const el = img.closest('.square');
            const idx = Array.from(boardEl.children).indexOf(el);
            const r = Math.floor(idx / 8);
            const c = idx % 8;
            const p = board[r][c];
            const isPlayable = p && pColor(p) === turn
                && !(gameMode === 'ai' && turn === 'black');
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

    /* ==========================================================
    SELECTION & MOVES
    ========================================================== */
    async function selectPiece(r,c) {
        const p = board[r][c];
        if (!p || pColor(p) !== turn || paused || gameOver) return;

        if (gameMode === 'ai' && turn === 'black') {
            showStatus("Waiting for AI to move...", false);
            return;
        }

        selected = {r,c};
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
                board = data.board;
                turn  = data.current_turn;
                lastMove = { from: [fr, fc], to: [tr, tc] };
                
                whiteTime = data.white_time;
                blackTime = data.black_time;
                
                selected = null;
                hints = [];
                updateTurn();
                updateMoves(data.move_history);
                updateCaptured(data.captured_pieces);
                syncPieces();
                renderClocks(); 
                startTimer();

                if (data.game_status === 'checkmate') {
                    handleGameOver('checkmate', turn);
                    return;
                } else if (data.game_status === 'stalemate') {
                    handleGameOver('stalemate', turn);
                    return;
                } else if (data.game_status === 'draw') {
                    handleGameOver('insufficient', turn);
                    return;
                } else if (data.game_status === 'check') {
                    showStatus(turn === 'white' ? 'White is in check!' : 'Black is in check!', true);
                } else {
                    showStatus('', false);
                }

                if (gameMode === 'ai' && turn === 'black') {
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
        showStatus('AI is thinking...', false);
        try {
            const data = await post('/api/ai-move/', {});
            if (data.valid) {
                const mv = data.ai_move;
                board = data.board;
                turn  = data.current_turn;
                lastMove = { from: [mv.from_row, mv.from_col], to: [mv.to_row, mv.to_col] };

                whiteTime = data.white_time;
                blackTime = data.black_time;

                selected = null;
                hints = [];
                updateTurn();
                updateMoves(data.move_history);
                updateCaptured(data.captured_pieces);
                syncPieces();
                renderClocks();
                startTimer();

                if (data.game_status === 'checkmate') {
                    handleGameOver('checkmate', turn);
                    return;
                } else if (data.game_status === 'stalemate') {
                    handleGameOver('stalemate', turn);
                    return;
                } else if (data.game_status === 'draw') {
                    handleGameOver('insufficient', turn);
                    return;
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

    async function onClick(r,c) {
        if (dragging) return;
        if (selected) {
            if (hints.some(h => h.row===r && h.col===c))
                return tryMove(selected.r,selected.c,r,c);
            if (board[r][c] && pColor(board[r][c])===turn)
                return selectPiece(r,c);
            return deselect();
        }
        selectPiece(r,c);
    }

    function onDragStart(e,r,c) {
        if (paused || pColor(board[r][c])!==turn) return e.preventDefault();
        if (gameMode === 'ai' && turn === 'black') return e.preventDefault();
        dragging = true;
        dragSrc = {r,c};
        selectPiece(r,c);
    }

    async function onDrop(e,tr,tc) {
        if (!dragSrc) return;
        await tryMove(dragSrc.r,dragSrc.c,tr,tc);
        dragSrc = null;
    }

    function updateTurn() {
        const wName = document.getElementById('whiteNameInput').value.trim() || 'White';
        const bName = document.getElementById('blackNameInput').value.trim() || 'Black';
        const currentName = (turn === 'white' ? wName : bName);

        if (document.getElementById('turnBadgeText')) {
            document.getElementById('turnBadgeText').textContent = currentName;
        } else {
            turnEl.textContent = currentName + "'s Turn";
        }

        turnEl.className = 'turn-badge ' + turn;
        document.getElementById('whiteClock').classList.toggle('active', turn === 'white');
        document.getElementById('blackClock').classList.toggle('active', turn === 'black');
        
        markPlayable();

        if (!gameOver) {
            document.title = `${currentName} to Move - Checkora`;
        }
    }

    function updateMoves(history) {
        if (!history?.length) {
            movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
            return;
        }
        movesEl.innerHTML = '';
        for (let i=0;i<history.length;i+=2) {
            const row = document.createElement('div');
            row.className = 'move-row';
            row.innerHTML = `
                <span class="move-num">${i/2+1}.</span>
                <span class="move-white">${history[i].notation}</span>
                ${history[i+1]?`<span class="move-black">${history[i+1].notation}</span>`:''}
            `;
            movesEl.appendChild(row);
        }
    }

    function updateCaptured(cap) {
        wCapEl.innerHTML = bCapEl.innerHTML = '';
        cap.white.forEach(p => wCapEl.innerHTML += `<img src="${PIECE_IMG[pKey(p)]}" class="captured-img">`);
        cap.black.forEach(p => bCapEl.innerHTML += `<img src="${PIECE_IMG[pKey(p)]}" class="captured-img">`);
    }

    function showStatus(msg,err) {
        statusEl.textContent = msg;
        statusEl.className = 'status-bar' + (err?' error':'');
    }

    function handleGameOver(status, currentTurn) {
        gameOver = true;
        paused = true;
        clearInterval(timerInterval);

        const whiteName = document.getElementById('whiteNameLabel').textContent;
        const blackName = document.getElementById('blackNameLabel').textContent;

        let title, message;
        if (status === 'checkmate') {
            const winner = (currentTurn === 'white') ? blackName : whiteName;
            title = 'Checkmate!';
            message = `${winner} wins!`;
        } else if (status === 'stalemate') {
            title = 'Stalemate!';
            message = 'The game is a draw.';
        } else if (status === 'draw') {
            title = 'Draw!';
            message = 'Draw by Agreement.';
        } else if (status === 'insufficient') {
            title = 'Draw!';
            message = 'Draw due to Insufficient Material.';
        } else if (status === 'resign') {
            const winner = (currentTurn === 'white') ? blackName : whiteName;
            title = 'Resignation';
            message = `${winner} wins!`;
        }

        gameOverTitle.textContent = title;
        gameOverMessage.textContent = message;
        gameOverOverlay.classList.add('active');
        showStatus(title + ' ' + message, false);
        
        document.title = 'Game Over - Checkora';
    }

    const fmt = t => `${Math.floor(t/60)}:${String(t%60).padStart(2,'0')}`;

    function renderClocks() {
        document.querySelector('#whiteClock .time').textContent = fmt(whiteTime);
        document.querySelector('#blackClock .time').textContent = fmt(blackTime);
    }

    function updatePauseUI() {
        pauseBtn.textContent = paused ? 'Resume' : 'Pause';
    }

    function startTimer() {
        clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            if (paused) return;
            if (turn==='white' && whiteTime>0) whiteTime--;
            if (turn==='black' && blackTime>0) blackTime--;
            renderClocks();
        },1000);
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

    pauseBtn.onclick = () => paused ? resumeGame() : pauseGame();

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) pauseGame();
    });

    window.addEventListener('beforeunload', () => {
        if (!paused) {
            navigator.sendBeacon('/api/pause/', JSON.stringify({
                pause: true,
                white_time: whiteTime,
                black_time: blackTime
            }));
        }
    });

    let confirmCallback = null;
    function showConfirm(title, msg, callback, titleColor = '#ff6b6b') {
        const titleEl = document.getElementById('confirmTitle');
        const msgEl = document.getElementById('confirmMessage');
        if (titleEl) {
            titleEl.textContent = title;
            titleEl.style.color = titleColor;
        }
        if (msgEl) msgEl.innerHTML = msg;
        confirmCallback = callback;
        confirmOverlay.classList.add('active');
    }

    if (welcomePvPBtn) welcomePvPBtn.onclick = () => { welcomeOverlay.classList.remove('active'); startNewGame('pvp'); };
    if (welcomeAIBtn) welcomeAIBtn.onclick = () => { welcomeOverlay.classList.remove('active'); startNewGame('ai'); };
    if (welcomeResumeBtn) welcomeResumeBtn.onclick = () => { 
        welcomeOverlay.classList.remove('active'); 
        if (paused) resumeGame();
    };

    function requestNewGame(mode) {
        showConfirm(
            "Abandon Game?", 
            "Your current progress will be lost.<br>Are you sure you want to start a new game?", 
            () => startNewGame(mode),
            '#ff6b6b'
        );
    }

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

    async function offerDraw() {
        if (paused || gameOver || gameMode !== 'pvp') return;

        const wName = document.getElementById('whiteNameInput').value.trim() || 'White';
        const bName = document.getElementById('blackNameInput').value.trim() || 'Black';

        const offeringPlayer = turn === 'white' ? wName : bName;
        const receivingPlayer = turn === 'white' ? bName : wName;
        
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

    if (drawBtn) drawBtn.onclick = offerDraw;
    if (drawAcceptBtn) drawAcceptBtn.onclick = async () => {
        drawOverlay.classList.remove('active');
        const data = await post('/api/draw/', { action: 'accept' });
        if (data.success) {
            handleGameOver('draw', turn);
        }
    };
    if (drawDeclineBtn) drawDeclineBtn.onclick = () => {
        drawOverlay.classList.remove('active');
        resumeGame();
    };

    if (gameOverPvPBtn) gameOverPvPBtn.onclick = () => { gameOverOverlay.classList.remove('active'); startNewGame('pvp'); };
    if (gameOverAIBtn) gameOverAIBtn.onclick = () => { gameOverOverlay.classList.remove('active'); startNewGame('ai'); };

    async function startNewGame(mode) {
        const wName = document.getElementById('whiteNameInput').value.trim() || 'White';
        const bName = document.getElementById('blackNameInput').value.trim() || 'Black';

        const d = await post('/api/new-game/', { 
            mode: mode,
            white_name: wName,
            black_name: bName
        });

        board = d.board;
        turn = d.current_turn;
        paused = false;
        gameOver = false;  
        gameMode = d.mode;
        
        document.getElementById('whiteNameLabel').textContent = wName.toUpperCase();
        document.getElementById('blackNameLabel').textContent = bName.toUpperCase();

        document.getElementById('whiteCapturedName').textContent = wName;
        document.getElementById('blackCapturedName').textContent = bName;
        document.getElementById('turnBadgeText').textContent = (turn === 'white' ? wName : bName);

        if (document.getElementById('resignBtn')) document.getElementById('resignBtn').style.display = 'inline-block';
        if (document.getElementById('pauseBtn')) document.getElementById('pauseBtn').style.display = 'inline-block';

        if (modeBadge) modeBadge.textContent = gameMode === 'ai' ? 'VS AI' : 'PVP';
        movesEl.innerHTML = '<span class="placeholder">No moves yet</span>';
        wCapEl.innerHTML = bCapEl.innerHTML = '';
        
        loadGame();
    }

    window.showResignModal = function() {
        document.getElementById('resignModal').style.display = 'flex';
    };

    window.closeResignModal = function() {
        document.getElementById('resignModal').style.display = 'none';
    };

    window.confirmResign = async function() {
        closeResignModal();
        try {
            const response = await post('/api/resign/');
            if (response.valid) {
                gameOver = true;
                paused = true;
        
                clearInterval(timerInterval);

                const wName = document.getElementById('whiteNameLabel').textContent;
                const bName = document.getElementById('blackNameLabel').textContent;
                const loserName = (turn === 'white' ? wName : bName);
                const winnerName = (turn === 'white' ? bName : wName);
                
                const statusEl = document.getElementById('statusBar');
                if (statusEl) {
                    statusEl.textContent = `${loserName} resigned. ${winnerName} wins!`;
                    statusEl.style.color = "#f0c040";
                }

                document.getElementById('gameOverTitle').textContent = "Game Over";
                document.getElementById('gameOverMessage').textContent = `${loserName} resigned. ${winnerName} wins!`;
                document.getElementById('gameOverOverlay').style.display = 'flex';

                document.getElementById('resignBtn').style.display = 'none';
                document.getElementById('pauseBtn').style.display = 'none';
                
                document.getElementById('gameOverPvPBtn').onclick = async () => { 
                    document.getElementById('gameOverOverlay').style.display = 'none';
                    gameOver = false; 
                    paused = false; 
                    await startNewGame('pvp'); 
                };

                document.getElementById('gameOverAIBtn').onclick = async () => { 
                    document.getElementById('gameOverOverlay').style.display = 'none';
                    gameOver = false; 
                    paused = false; 
                    await startNewGame('ai'); 
                };

                await loadGame();
            }
        } catch (error) {
            console.error("Resign failed:", error);
        }
    };
    function generateFEN() {
    let fenRows = [];
    for (let r = 0; r < 8; r++) {
        let row = '';
        let empty = 0;
        for (let c = 0; c < 8; c++) {
            const p = board[r][c];
            if (!p) { empty++; }
            else {
                if (empty > 0) { row += empty; empty = 0; }
                row += p;
            }
        }
        if (empty > 0) row += empty;
        fenRows.push(row);
    }
        const activeColor = turn === 'white' ? 'w' : 'b';
        const movesList = movesEl.querySelectorAll('.move-row');
        const fullMove = movesList.length + 1;
        return `${fenRows.join('/')} ${activeColor} KQkq - 0 ${fullMove}`;
    }

    async function copyFEN() {
        const fen = generateFEN();
        await navigator.clipboard.writeText(fen);
        showStatus('FEN copied to clipboard!', false);
        setTimeout(() => showStatus('', false), 2000);
    }

    const copyFenBtn = document.getElementById('copyFenBtn');
    if (copyFenBtn) copyFenBtn.onclick = copyFEN;
    loadGame();
    window.addEventListener('pageshow', (event) => {
    loadGame();
});
})();
