const movesElement = document.getElementById("opening-moves");

if (!movesElement) {
    throw new Error("opening-moves element not found");
}

const OPENING_MOVES = JSON.parse(movesElement.textContent);

const openingNameElement = document.getElementById("opening-name");

if (!openingNameElement) {
    throw new Error("opening-name element not found");
}

const OPENING_NAME = JSON.parse(openingNameElement.textContent);

function csrf() {
    const input = document.querySelector(
        "[name=csrfmiddlewaretoken]"
    );

    if (input?.value) {
        return input.value;
    }

    const m = document.cookie.match(/csrftoken=([^;]+)/);

    return m ? decodeURIComponent(m[1]) : "";
}

const STARTING_BOARD_STATE = [
    ["br", "bn", "bb", "bq", "bk", "bb", "bn", "br"],
    ["bp", "bp", "bp", "bp", "bp", "bp", "bp", "bp"],
    ["", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["wp", "wp", "wp", "wp", "wp", "wp", "wp", "wp"],
    ["wr", "wn", "wb", "wq", "wk", "wb", "wn", "wr"]
];

let boardState = STARTING_BOARD_STATE.map(row => [...row]);
let currentMove = 0;
let viewingMoveIndex = 0;
let userColor = "w"; // 'w' or 'b'
let selectedSquare = null;
let lastMoveHighlight = null;
let opponentReplyTimeout = null;
let hintHighlight = null;
const hintButton = document.getElementById("get-hint-btn");
const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
const activeTouches = {};

const feedback = document.getElementById("trainer-feedback");
const progress = document.getElementById("move-progress");
const moveInput = document.getElementById("move-input");
const checkButton = document.getElementById("check-move-btn");
const boardElement = document.getElementById("board");
const playWhiteBtn = document.getElementById("play-white-btn");
const playBlackBtn = document.getElementById("play-black-btn");

function updateProgress() {
    progress.innerText = `${viewingMoveIndex} / ${OPENING_MOVES.length}`;
}


async function persistOpeningProgress() {
    const token = csrf();

    try {
        const response = await fetch("/api/opening-stats/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": token,
            },
            body: JSON.stringify({
                opening_name: OPENING_NAME,
                completed: true,
                accuracy: 100,
            }),
        });

        if (!response.ok) {
            throw new Error(
                `Failed to save progress (${response.status})`
            );
        }

        return await response.json();

    } catch (error) {
        console.error(
            "Failed to save opening progress:",
            error
        );
    }
}

function completeOpening() {
    feedback.innerText = "🎉 Opening completed successfully!";
    moveInput.disabled = true;
    checkButton.disabled = true;

    persistOpeningProgress();
}

// Checks if the squares between 'from' and 'to' are empty
function isPathClear(fromRow, fromCol, toRow, toCol) {
    const stepRow = toRow === fromRow ? 0 : (toRow > fromRow ? 1 : -1);
    const stepCol = toCol === fromCol ? 0 : (toCol > fromCol ? 1 : -1);
    let r = fromRow + stepRow;
    let c = fromCol + stepCol;
    while (r !== toRow || c !== toCol) {
        if (boardState[r][c] !== "") return false;
        r += stepRow;
        c += stepCol;
    }
    return true;
}

// Basic move validator for SAN matching
function canPieceMove(fromRow, fromCol, toRow, toCol, pieceType, color) {
    const dRow = Math.abs(toRow - fromRow);
    const dCol = Math.abs(toCol - fromCol);

    if (pieceType === "p") {
        const dir = color === "w" ? -1 : 1;
        // 1 step forward
        if (toCol === fromCol && toRow === fromRow + dir) {
            return boardState[toRow][toCol] === "";
        }
        // 2 steps forward from initial rank
        if (toCol === fromCol && toRow === fromRow + 2 * dir) {
            const startRow = color === "w" ? 6 : 1;
            return fromRow === startRow && boardState[fromRow + dir][fromCol] === "" && boardState[toRow][toCol] === "";
        }
        // Diagonal capture
        if (dCol === 1 && toRow === fromRow + dir) {
            return boardState[toRow][toCol] !== "" && !boardState[toRow][toCol].startsWith(color);
        }
        return false;
    }

    if (pieceType === "n") {
        return (dRow === 1 && dCol === 2) || (dRow === 2 && dCol === 1);
    }

    if (pieceType === "b") {
        return dRow === dCol && isPathClear(fromRow, fromCol, toRow, toCol);
    }

    if (pieceType === "r") {
        return (fromRow === toRow || fromCol === toCol) && isPathClear(fromRow, fromCol, toRow, toCol);
    }

    if (pieceType === "q") {
        return (dRow === dCol || fromRow === toRow || fromCol === toCol) && isPathClear(fromRow, fromCol, toRow, toCol);
    }

    if (pieceType === "k") {
        return dRow <= 1 && dCol <= 1;
    }

    return false;
}

// Parses SAN move string to resolve start and destination coordinates
function parseSAN(san, color) {
    san = san.replace(/[+#?!]/g, "");

    // Castling
    if (san === "O-O") {
        const r = color === "w" ? 7 : 0;
        return { fromRow: r, fromCol: 4, toRow: r, toCol: 6 };
    }
    if (san === "O-O-O") {
        const r = color === "w" ? 7 : 0;
        return { fromRow: r, fromCol: 4, toRow: r, toCol: 2 };
    }

    if (san.includes("=")) {
        san = san.split("=")[0];
    }

    const toSq = san.slice(-2);
    const toCol = toSq.charCodeAt(0) - 97;
    const toRow = 8 - parseInt(toSq[1], 10);

    let pieceType = "p";
    let rest = san.slice(0, -2);
    if (["K", "Q", "R", "B", "N"].includes(san[0])) {
        pieceType = san[0].toLowerCase();
        rest = san.slice(1, -2);
    }

    rest = rest.replace("x", "");

    const targetPieceCode = color + pieceType;
    const candidates = [];

    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            if (boardState[r][c] === targetPieceCode) {
                if (canPieceMove(r, c, toRow, toCol, pieceType, color)) {
                    candidates.push({ r, c });
                }
            }
        }
    }

    let finalFrom = null;
    if (candidates.length === 1) {
        finalFrom = candidates[0];
    } else if (candidates.length > 1) {
        if (rest.length > 0) {
            const disChar = rest[0];
            if (disChar >= "a" && disChar <= "h") {
                const disCol = disChar.charCodeAt(0) - 97;
                finalFrom = candidates.find(cand => cand.c === disCol);
            } else if (disChar >= "1" && disChar <= "8") {
                const disRow = 8 - parseInt(disChar, 10);
                finalFrom = candidates.find(cand => cand.r === disRow);
            }
        }
    }

    if (finalFrom) {
        return {
            fromRow: finalFrom.r,
            fromCol: finalFrom.c,
            toRow: toRow,
            toCol: toCol
        };
    }

    return null;
}

function applyMoveToBoardState(state, fromRow, fromCol, toRow, toCol) {
    const piece = state[fromRow][fromCol];
    state[fromRow][fromCol] = "";
    state[toRow][toCol] = piece;

    // Castling rook movement
    const pieceType = piece.slice(1);
    if (pieceType === "k" && Math.abs(fromCol - toCol) === 2) {
        if (toCol === 6) {
            const rook = state[toRow][7];
            state[toRow][7] = "";
            state[toRow][5] = rook;
        } else if (toCol === 2) {
            const rook = state[toRow][0];
            state[toRow][0] = "";
            state[toRow][3] = rook;
        }
    }
}

function applyMoveOnBoard(fromRow, fromCol, toRow, toCol) {
    applyMoveToBoardState(boardState, fromRow, fromCol, toRow, toCol);
    renderBoard();
}

function highlightLastMove(fromRow, fromCol, toRow, toCol) {
    lastMoveHighlight = { fromRow, fromCol, toRow, toCol };
    renderBoard();
}

function playOpponentMove() {
    if (currentMove >= OPENING_MOVES.length) return;

    // Bring boardState back to currentMove to make sure parseSAN/applyMove resolves against the latest actual state
    showMoveAt(currentMove);

    const color = currentMove % 2 === 0 ? "w" : "b";
    const moveStr = OPENING_MOVES[currentMove];
    const moveParsed = parseSAN(moveStr, color);

    if (moveParsed) {
        applyMoveOnBoard(moveParsed.fromRow, moveParsed.fromCol, moveParsed.toRow, moveParsed.toCol);
        currentMove++;
        viewingMoveIndex = currentMove;
        updateProgress();
        highlightLastMove(moveParsed.fromRow, moveParsed.fromCol, moveParsed.toRow, moveParsed.toCol);

        if (currentMove >= OPENING_MOVES.length) {
            completeOpening();
        }
        updateNavigationButtons();
    }
}

function makeUserMove(fromRow, fromCol, toRow, toCol) {
    if (viewingMoveIndex !== currentMove) return;
    if (currentMove >= OPENING_MOVES.length) return;

    const expectedMove = OPENING_MOVES[currentMove];
    const expectedParsed = parseSAN(expectedMove, userColor);

    if (expectedParsed &&
        expectedParsed.fromRow === fromRow &&
        expectedParsed.fromCol === fromCol &&
        expectedParsed.toRow === toRow &&
        expectedParsed.toCol === toCol) {

        applyMoveOnBoard(fromRow, fromCol, toRow, toCol);
        currentMove++;
        viewingMoveIndex = currentMove;
        feedback.innerText = "✅ Correct move!";
        updateProgress();
        highlightLastMove(fromRow, fromCol, toRow, toCol);

        if (currentMove >= OPENING_MOVES.length) {
            completeOpening();
            updateNavigationButtons();
            return;
        }

        updateNavigationButtons();

        // Auto-play opponent response after 800ms
        if (opponentReplyTimeout) clearTimeout(opponentReplyTimeout);
        opponentReplyTimeout = setTimeout(() => {
            playOpponentMove();
        }, 800);

    } else {
        feedback.innerText = `❌ Incorrect move. Expected: ${expectedMove}`;
    }
}

function handleSquareClick(row, col) {
    if (hintHighlight) {
        hintHighlight = null;
        renderBoard();
    }

    if (viewingMoveIndex !== currentMove) return;

    const isUserTurn = (userColor === "w" && currentMove % 2 === 0) || (userColor === "b" && currentMove % 2 === 1);
    if (!isUserTurn) return;

    const piece = boardState[row][col];

    if (selectedSquare) {
        if (selectedSquare.row === row && selectedSquare.col === col) {
            selectedSquare = null;
            renderBoard();
            return;
        }

        if (piece && piece.startsWith(userColor)) {
            selectedSquare = { row, col };
            renderBoard();
            return;
        }

        const fromRow = selectedSquare.row;
        const fromCol = selectedSquare.col;
        selectedSquare = null;
        makeUserMove(fromRow, fromCol, row, col);
    } else {
        if (piece && piece.startsWith(userColor)) {
            selectedSquare = { row, col };
            renderBoard();
        }
    }
}

function handleDragStart(e, row, col) {
    if (viewingMoveIndex !== currentMove) {
        e.preventDefault();
        return;
    }

    const isUserTurn = (userColor === "w" && currentMove % 2 === 0) || (userColor === "b" && currentMove % 2 === 1);
    if (!isUserTurn) {
        e.preventDefault();
        return;
    }
    const piece = boardState[row][col];
    if (!piece || !piece.startsWith(userColor)) {
        e.preventDefault();
        return;
    }
    e.dataTransfer.setData("text/plain", JSON.stringify({ row, col }));
    e.dataTransfer.effectAllowed = "move";
}

function handleDrop(e, targetRow, targetCol) {
    e.preventDefault();
    try {
        const data = JSON.parse(e.dataTransfer.getData("text/plain"));
        if (data && typeof data.row === "number" && typeof data.col === "number") {
            makeUserMove(data.row, data.col, targetRow, targetCol);
        }
    } catch (err) {
        console.error("Drop error:", err);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
}

function handleTouchStart(e, row, col) {
    if (viewingMoveIndex !== currentMove) return;

    const isUserTurn = (userColor === "w" && currentMove % 2 === 0) || (userColor === "b" && currentMove % 2 === 1);
    if (!isUserTurn) return;

    const piece = boardState[row][col];
    if (!piece || !piece.startsWith(userColor)) return;

    // Get the touch point that started this event
    const touch = e.changedTouches ? e.changedTouches[0] : null;
    if (!touch) return;

    // Prevent default scrolling/panning behavior on touch devices
    e.preventDefault();

    const img = e.currentTarget;
    const identifier = touch.identifier;

    const rect = img.getBoundingClientRect();
    const touchOffsetX = rect.width / 2;
    const touchOffsetY = rect.height / 2;

    // Store drag state for this touch identifier
    activeTouches[identifier] = {
        img: img,
        startRow: row,
        startCol: col,
        touchOffsetX: touchOffsetX,
        touchOffsetY: touchOffsetY
    };

    // Store the identifier on the element to reference in move/end events
    img.dataset.touchId = identifier;

    // Transition image to fixed positioning for dragging
    img.style.position = "fixed";
    img.style.width = `${rect.width}px`;
    img.style.height = `${rect.height}px`;
    img.style.zIndex = "1000";
    img.style.pointerEvents = "none"; // Crucial so document.elementFromPoint can hit the underlying squares

    img.style.left = `${touch.clientX - touchOffsetX}px`;
    img.style.top = `${touch.clientY - touchOffsetY}px`;
}

function handleTouchMove(e, img) {
    const touchIdAttr = img.dataset.touchId;
    if (touchIdAttr === undefined) return;
    const touchId = parseInt(touchIdAttr, 10);
    const touchState = activeTouches[touchId];
    if (!touchState) return;
    // Find the specific active touch point matching this identifier
    const touch = e.touches ? (Array.from(e.touches).find(t => t.identifier === touchId) || 
                               Array.from(e.changedTouches || []).find(t => t.identifier === touchId)) : null;
    if (!touch) return;
    e.preventDefault();
    img.style.left = `${touch.clientX - touchState.touchOffsetX}px`;
    img.style.top = `${touch.clientY - touchState.touchOffsetY}px`;
}

function handleTouchEnd(e, startRow, startCol) {
    const img = e.currentTarget;
    const touchIdAttr = img.dataset.touchId;
    
    try {
        if (touchIdAttr === undefined) return;
        const touchId = parseInt(touchIdAttr, 10);
        const touchState = activeTouches[touchId];
        if (!touchState) return;
        // Prevent click events / default behavior
        e.preventDefault();
        // Clean up active touch tracking
        delete activeTouches[touchId];
        delete img.dataset.touchId;

        // Do not commit moves from touchcancel
        if (e.type === "touchcancel") {
            return;
        }

        // Safely extract the corresponding touch point from changedTouches
        const touch = e.changedTouches ? Array.from(e.changedTouches).find(t => t.identifier === touchId) : null;
        if (touch) {
            // Find the element under the touch coordinates
            const element = document.elementFromPoint(touch.clientX, touch.clientY);
            const square = element ? element.closest(".square") : null;
            if (square) {
                const targetRow = parseInt(square.dataset.row, 10);
                const targetCol = parseInt(square.dataset.col, 10);
                // Call move logic only if dropped on a different square
                if (targetRow !== startRow || targetCol !== startCol) {
                    makeUserMove(startRow, startCol, targetRow, targetCol);
                }
            }
        }
    } catch (err) {
        console.error("Touch end error:", err);
    } finally {
        // ALWAYS run renderBoard() to restore layout, even if an error is thrown
        renderBoard();
    }
}

function renderBoard() {
    if (!boardElement) return;
    boardElement.innerHTML = "";
    const isFlipped = userColor === "b";

    for (let r = 0; r < 8; r++) {
        const actualRow = isFlipped ? 7 - r : r;
        for (let c = 0; c < 8; c++) {
            const actualCol = isFlipped ? 7 - c : c;
            const square = document.createElement("div");
            square.classList.add("square");
            square.classList.add((actualRow + actualCol) % 2 === 0 ? "light" : "dark");

            square.dataset.row = actualRow;
            square.dataset.col = actualCol;

            if (selectedSquare && selectedSquare.row === actualRow && selectedSquare.col === actualCol) {
                square.classList.add("selected");
            }

            if (lastMoveHighlight && (
                (lastMoveHighlight.fromRow === actualRow && lastMoveHighlight.fromCol === actualCol) ||
                (lastMoveHighlight.toRow === actualRow && lastMoveHighlight.toCol === actualCol)
            )) {
                square.classList.add(lastMoveHighlight.toRow === actualRow && lastMoveHighlight.toCol === actualCol ? "highlight-to" : "highlight-from");
            }
            // Apply hint styles if a hint is active
            if (hintHighlight) {
                if (hintHighlight.fromRow === actualRow && hintHighlight.fromCol === actualCol) {
                    square.classList.add("hint-from");
                }
                if (hintHighlight.toRow === actualRow && hintHighlight.toCol === actualCol) {
                    square.classList.add("hint-to");
                }
            }

            const piece = boardState[actualRow][actualCol];
            if (piece) {
                const img = document.createElement("img");
                img.src = `/static/game/pieces/${piece}.png`;
                img.alt = piece;
                img.draggable = true;
                img.addEventListener("dragstart", (e) => handleDragStart(e, actualRow, actualCol));
                img.addEventListener("touchstart", (e) => handleTouchStart(e, actualRow, actualCol), { passive: false });
                img.addEventListener("touchmove", (e) => handleTouchMove(e, img), { passive: false });
                img.addEventListener("touchend", (e) => handleTouchEnd(e, actualRow, actualCol), { passive: false });
                img.addEventListener("touchcancel", (e) => handleTouchEnd(e, actualRow, actualCol), { passive: false });
                square.appendChild(img);
            }

            square.addEventListener("click", () => handleSquareClick(actualRow, actualCol));
            square.addEventListener("dragover", handleDragOver);
            square.addEventListener("drop", (e) => handleDrop(e, actualRow, actualCol));

            boardElement.appendChild(square);
        }
    }
}

function showMoveAt(index) {
    if (index < 0 || index > currentMove) return;

    boardState = STARTING_BOARD_STATE.map(row => [...row]);
    lastMoveHighlight = null;
    hintHighlight = null; // Clear hint highlight state

    for (let i = 0; i < index; i++) {
        const color = i % 2 === 0 ? "w" : "b";
        const moveStr = OPENING_MOVES[i];
        const moveParsed = parseSAN(moveStr, color);

        if (moveParsed) {
            applyMoveToBoardState(boardState, moveParsed.fromRow, moveParsed.fromCol, moveParsed.toRow, moveParsed.toCol);

            lastMoveHighlight = {
                fromRow: moveParsed.fromRow,
                fromCol: moveParsed.fromCol,
                toRow: moveParsed.toRow,
                toCol: moveParsed.toCol
            };
        }
    }

    viewingMoveIndex = index;
    updateProgress();
    renderBoard();
    updateNavigationButtons();
}

function updateInputState() {
    const isLatest = viewingMoveIndex === currentMove;
    const isCompleted = currentMove >= OPENING_MOVES.length;

    if (moveInput) {
        moveInput.disabled = !isLatest || isCompleted;
    }
    if (checkButton) {
        checkButton.disabled = !isLatest || isCompleted;
    }
    if (hintButton) {
        hintButton.disabled = !isLatest || isCompleted;
    }
}

function updateNavigationButtons() {
    const prevBtn = document.getElementById("prev-move-btn");
    const nextBtn = document.getElementById("next-move-btn");

    if (prevBtn) {
        prevBtn.disabled = (viewingMoveIndex === 0);
    }
    if (nextBtn) {
        nextBtn.disabled = (viewingMoveIndex === currentMove);
    }

    updateInputState();
}

function resetGame() {
    currentMove = 0;
    viewingMoveIndex = 0;
    selectedSquare = null;
    lastMoveHighlight = null;
    hintHighlight = null; // Clear hint highlight state
    if (opponentReplyTimeout) {
        clearTimeout(opponentReplyTimeout);
        opponentReplyTimeout = null;
    }
    boardState = STARTING_BOARD_STATE.map(row => [...row]);
    moveInput.disabled = false;
    checkButton.disabled = false;
    feedback.innerText = "Ready to begin.";
    updateProgress();
    updateNavigationButtons();
    renderBoard();

    // If Black plays, the opponent makes the first White move immediately
    if (userColor === "b") {
        opponentReplyTimeout = setTimeout(() => {
            playOpponentMove();
        }, 800);
    }
}

// Color Toggle setup
if (playWhiteBtn && playBlackBtn) {
    playWhiteBtn.addEventListener("click", () => {
        if (userColor === "w") return;
        userColor = "w";
        playWhiteBtn.classList.add("active");
        playWhiteBtn.setAttribute("aria-pressed", "true");
        playBlackBtn.classList.remove("active");
        playBlackBtn.setAttribute("aria-pressed", "false");
        resetGame();
    });

    playBlackBtn.addEventListener("click", () => {
        if (userColor === "b") return;
        userColor = "b";
        playBlackBtn.classList.add("active");
        playBlackBtn.setAttribute("aria-pressed", "true");
        playWhiteBtn.classList.remove("active");
        playWhiteBtn.setAttribute("aria-pressed", "false");
        resetGame();
    });
}

// Support manual move text box validation in sync with the visual board
function validateMove(move) {
    if (hintHighlight) {
        hintHighlight = null;
        renderBoard();
    }

    if (viewingMoveIndex !== currentMove) return false;

    const isUserTurn = (userColor === "w" && currentMove % 2 === 0) || (userColor === "b" && currentMove % 2 === 1);
    if (!isUserTurn) {
        feedback.innerText = "⚠️ It is the opponent's turn. Please wait.";
        return false;
    }

    const expectedMove = OPENING_MOVES[currentMove];
    if (move.toLowerCase() === expectedMove.toLowerCase()) {
        const parsed = parseSAN(expectedMove, currentMove % 2 === 0 ? "w" : "b");
        if (parsed) {
            applyMoveOnBoard(parsed.fromRow, parsed.fromCol, parsed.toRow, parsed.toCol);
            highlightLastMove(parsed.fromRow, parsed.fromCol, parsed.toRow, parsed.toCol);
        }
        currentMove++;
        viewingMoveIndex = currentMove;
        feedback.innerText = "✅ Correct move!";
        updateProgress();
        moveInput.value = "";

        if (currentMove >= OPENING_MOVES.length) {
            completeOpening();
        } else {
            const nextTurnColor = currentMove % 2 === 0 ? "w" : "b";
            if (nextTurnColor !== userColor) {
                if (opponentReplyTimeout) clearTimeout(opponentReplyTimeout);
                opponentReplyTimeout = setTimeout(() => {
                    playOpponentMove();
                }, 800);
            }
        }
        updateNavigationButtons();
        return true;
    }

    feedback.innerText = `❌ Incorrect move. Expected: ${expectedMove}`;
    return false;
}

checkButton.addEventListener("click", () => {
    const move = moveInput.value.trim();
    if (!move) {
        feedback.innerText = "Please enter a move.";
        return;
    }
    validateMove(move);
});

moveInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
        checkButton.click();
    }
});

// Navigation Stepper Event Listeners
const prevBtn = document.getElementById("prev-move-btn");
const nextBtn = document.getElementById("next-move-btn");
const resetTrainerBtn = document.getElementById("reset-trainer-btn");

if (prevBtn) {
    prevBtn.addEventListener("click", () => {
        if (viewingMoveIndex > 0) {
            showMoveAt(viewingMoveIndex - 1);
        }
    });
}

if (nextBtn) {
    nextBtn.addEventListener("click", () => {
        if (viewingMoveIndex < currentMove) {
            showMoveAt(viewingMoveIndex + 1);
        }
    });
}

if (resetTrainerBtn) {
    resetTrainerBtn.addEventListener("click", () => {
        resetGame();
    });
}

// Keyboard Arrow Navigation
document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
        return; // Don't intercept arrow keys if typing in input fields
    }
    if (e.key === "ArrowLeft") {
        if (viewingMoveIndex > 0) {
            showMoveAt(viewingMoveIndex - 1);
        }
    } else if (e.key === "ArrowRight") {
        if (viewingMoveIndex < currentMove) {
            showMoveAt(viewingMoveIndex + 1);
        }
    }
});

// Theme Selection Setup
const themeSelect = document.getElementById("board-theme-select");

function applyTheme(theme) {
    if (!boardElement) return;

    // Remove any previous theme- classes
    boardElement.className.split(" ").forEach(className => {
        if (className.startsWith("theme-")) {
            boardElement.classList.remove(className);
        }
    });

    // Add selected theme class
    boardElement.classList.add(`theme-${theme}`);

    // Persist in localStorage
    localStorage.setItem("checkora-board-theme", theme);
}

if (themeSelect) {
    // Load persisted theme or default to classic
    const savedTheme = localStorage.getItem("checkora-board-theme") || "classic";
    themeSelect.value = savedTheme;
    applyTheme(savedTheme);

    // Event listener for user theme changes
    themeSelect.addEventListener("change", (e) => {
        applyTheme(e.target.value);
    });
}

    if (hintButton) {
    hintButton.addEventListener("click", () => {
        if (viewingMoveIndex !== currentMove) return;
        if (currentMove >= OPENING_MOVES.length) return;

        // Ensure it is the user's turn before showing a hint
        const isUserTurn = (userColor === "w" && currentMove % 2 === 0) || (userColor === "b" && currentMove % 2 === 1);
        if (!isUserTurn) return;

        const expectedMove = OPENING_MOVES[currentMove];
        const color = currentMove % 2 === 0 ? "w" : "b";
        const moveParsed = parseSAN(expectedMove, color);

        if (moveParsed) {
            hintHighlight = {
                fromRow: moveParsed.fromRow,
                fromCol: moveParsed.fromCol,
                toRow: moveParsed.toRow,
                toCol: moveParsed.toCol
            };
            renderBoard();
        }
    });
}

// Initialize game
resetGame();

