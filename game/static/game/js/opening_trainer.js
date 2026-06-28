const movesElement = document.getElementById("opening-moves");

if (!movesElement) {
    throw new Error("opening-moves element not found");
}

const OPENING_MOVES = JSON.parse(movesElement.textContent);
let currentMove = 0;
let userColor = "w"; // 'w' or 'b'
let selectedSquare = null;
let lastMoveHighlight = null;
let opponentReplyTimeout = null;
const files = ["a", "b", "c", "d", "e", "f", "g", "h"];

// Standard 8x8 starting setup
let boardState = [
    ["br", "bn", "bb", "bq", "bk", "bb", "bn", "br"],
    ["bp", "bp", "bp", "bp", "bp", "bp", "bp", "bp"],
    ["", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["wp", "wp", "wp", "wp", "wp", "wp", "wp", "wp"],
    ["wr", "wn", "wb", "wq", "wk", "wb", "wn", "wr"]
];

const feedback = document.getElementById("trainer-feedback");
const progress = document.getElementById("move-progress");
const moveInput = document.getElementById("move-input");
const checkButton = document.getElementById("check-move-btn");
const boardElement = document.getElementById("board");
const playWhiteBtn = document.getElementById("play-white-btn");
const playBlackBtn = document.getElementById("play-black-btn");

function updateProgress() {
    progress.innerText = `${currentMove} / ${OPENING_MOVES.length}`;
}

function completeOpening() {
    feedback.innerText = "🎉 Opening completed successfully!";
    moveInput.disabled = true;
    checkButton.disabled = true;
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

function applyMoveOnBoard(fromRow, fromCol, toRow, toCol) {
    const piece = boardState[fromRow][fromCol];
    boardState[fromRow][fromCol] = "";
    boardState[toRow][toCol] = piece;

    // Castling rook movement
    const pieceType = piece.slice(1);
    if (pieceType === "k" && Math.abs(fromCol - toCol) === 2) {
        if (toCol === 6) {
            const rook = boardState[toRow][7];
            boardState[toRow][7] = "";
            boardState[toRow][5] = rook;
        } else if (toCol === 2) {
            const rook = boardState[toRow][0];
            boardState[toRow][0] = "";
            boardState[toRow][3] = rook;
        }
    }

    renderBoard();
}

function highlightLastMove(fromRow, fromCol, toRow, toCol) {
    lastMoveHighlight = { fromRow, fromCol, toRow, toCol };
    renderBoard();
}

function playOpponentMove() {
    if (currentMove >= OPENING_MOVES.length) return;

    const color = currentMove % 2 === 0 ? "w" : "b";
    const moveStr = OPENING_MOVES[currentMove];
    const moveParsed = parseSAN(moveStr, color);

    if (moveParsed) {
        applyMoveOnBoard(moveParsed.fromRow, moveParsed.fromCol, moveParsed.toRow, moveParsed.toCol);
        currentMove++;
        updateProgress();
        highlightLastMove(moveParsed.fromRow, moveParsed.fromCol, moveParsed.toRow, moveParsed.toCol);

        if (currentMove >= OPENING_MOVES.length) {
            completeOpening();
        }
    }
}

function makeUserMove(fromRow, fromCol, toRow, toCol) {
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
        feedback.innerText = "✅ Correct move!";
        updateProgress();
        highlightLastMove(fromRow, fromCol, toRow, toCol);

        if (currentMove >= OPENING_MOVES.length) {
            completeOpening();
            return;
        }

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

            const piece = boardState[actualRow][actualCol];
            if (piece) {
                const img = document.createElement("img");
                img.src = `/static/game/pieces/${piece}.png`;
                img.alt = piece;
                img.draggable = true;
                img.addEventListener("dragstart", (e) => handleDragStart(e, actualRow, actualCol));
                square.appendChild(img);
            }

            square.addEventListener("click", () => handleSquareClick(actualRow, actualCol));
            square.addEventListener("dragover", handleDragOver);
            square.addEventListener("drop", (e) => handleDrop(e, actualRow, actualCol));

            boardElement.appendChild(square);
        }
    }
}

function resetGame() {
    currentMove = 0;
    selectedSquare = null;
    lastMoveHighlight = null;
    if (opponentReplyTimeout) {
        clearTimeout(opponentReplyTimeout);
        opponentReplyTimeout = null;
    }
    boardState = [
        ["br", "bn", "bb", "bq", "bk", "bb", "bn", "br"],
        ["bp", "bp", "bp", "bp", "bp", "bp", "bp", "bp"],
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["wp", "wp", "wp", "wp", "wp", "wp", "wp", "wp"],
        ["wr", "wn", "wb", "wq", "wk", "wb", "wn", "wr"]
    ];
    moveInput.disabled = false;
    checkButton.disabled = false;
    feedback.innerText = "Ready to begin.";
    updateProgress();
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

// Initialize game
resetGame();
