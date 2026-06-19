document.body.innerHTML = `
  <div id="board"></div>
  <div id="turnBadge"></div>
  <div id="statusBar"></div>
  <div id="movesList"></div>
  <div id="whiteCaptured"></div>
  <div id="blackCaptured"></div>
  <button id="pauseBtn"></button>
  <div id="promoOverlay"></div>
  <div id="promoChoices"></div>
  <div id="modeBadge"></div>
  <button id="autoFlipBtn"></button>
  <div id="flipControls"></div>
  <button id="copyFenBtn"></button>
  <div id="welcomeOverlay"></div>
  <button id="welcomeResumeBtn"></button>
  <button id="welcomePvPBtn"></button>
  <button id="welcomeAIBtn"></button>
  <div id="modeSelection"></div>
  <div id="pveOptions"><button class="color-choice" data-color="white"></button></div>
  <button id="startAIBtn"></button>
  <button id="backToModes"></button>
  <div class="game-layout"></div>
  <div id="confirmOverlay"></div>
  <div id="confirmTitle"></div>
  <div id="confirmMessage"></div>
  <button id="confirmYesBtn"></button>
  <button id="confirmNoBtn"></button>
  <button id="newPvPBtn"></button>
  <button id="newAIBtn"></button>
  <div id="gameOverOverlay"><div class="promo-dialog"></div></div>
  <div id="gameOverTitle"></div>
  <div id="gameOverMessage"></div>
  <button id="gameOverStartBtn"></button>
  <button id="gameOverPvPBtn"></button>
  <button id="gameOverAIBtn"></button>
  <button id="resignBtn"></button>
  <button id="drawBtn"></button>
  <div id="drawOverlay"></div>
  <div id="drawMessage"></div>
  <button id="drawAcceptBtn"></button>
  <button id="drawDeclineBtn"></button>
  <div id="whiteNameLabel"></div>
  <div id="blackNameLabel"></div>
  <div id="whiteYouTag"></div>
  <div id="blackYouTag"></div>
  <div id="whiteCapturedName"></div>
  <div id="blackCapturedName"></div>
  <div id="turnBadgeText"></div>
  <input type="checkbox" id="showCoordinatesCheckbox">
  <div id="game-status"></div>
  <span id="whiteScore"></span>
  <span id="blackScore"></span>
  <button id="shareResultBtn"></button>
  <div id="shareModal"></div>
  <div id="cardTitle"></div>
  <div id="cardMessage"></div>
  <div id="cardWhite"></div>
  <div id="cardBlack"></div>
  <div id="cardMoves"></div>
  <button id="copyTextBtn"></button>
  <button id="copyLinkBtn"></button>
  <button id="whatsappBtn"></button>
  <button id="twitterBtn"></button>
  <button id="closeShareBtn"></button>
`;
global.SOUND_BASE_URL = '/static/game/sounds/';
global.openingTrainerMode = false;
global.openingTrainerSteps = [];
global.currentTrainerStep = 0;
global.toSquare = function(r, c) {
  const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
  const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];
  return files[c] + ranks[r];
};

// Mock window.matchMedia to disable animation delays
window.matchMedia = function() {
  return {
    matches: true,
    addListener: function() {},
    removeListener: function() {}
  };
};

// Mock Worker for Jest
global.Worker = class MockWorker {
  constructor(url) {
    this.url = url;
    this.listeners = {};
  }
  postMessage(msg) {
    if (msg.startsWith('position fen ')) {
      this.currentFen = msg.replace('position fen ', '');
    } else if (msg.startsWith('go ')) {
      setTimeout(() => {
        let lines = ['info depth 10 score cp 0', 'bestmove e2e4'];
        if (global.mockScores && global.mockScores[this.currentFen]) {
          const mock = global.mockScores[this.currentFen];
          lines = [`info depth 10 score ${mock.type} ${mock.value}`, 'bestmove e2e4'];
        }
        for (const line of lines) {
          if (this.listeners['message']) {
            this.listeners['message']({ data: line });
          }
        }
      }, 0);
    }
  }
  addEventListener(event, callback) {
    this.listeners[event] = callback;
  }
  removeEventListener(event, callback) {
    if (this.listeners[event] === callback) {
      delete this.listeners[event];
    }
  }
  terminate() {}
};

// Mock Chess for Jest
global.Chess = class MockChess {
  constructor(fen) {
    this._fen = fen || 'startpos';
  }
  fen() {
    return this._fen;
  }
  move(moveObj) {
    const moveStr = typeof moveObj === 'string' ? moveObj : `${moveObj.from}${moveObj.to}`;
    this._fen = `${this._fen}_then_${moveStr}`;
    return {};
  }
};

global.SOUND_BASE_URL = '/static/game/sounds/';
global.Audio = class MockAudio {
  constructor(src) {
    this.src = src;
  }
  play() {
    return Promise.resolve();
  }
};

// Mock global fetch for API calls
global.fetch = jest.fn((url, options) => {
  if (url.includes('/api/valid-moves/')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid_moves: [
          { row: 2, col: 0, is_capture: false },
          { row: 3, col: 0, is_capture: true }
        ]
      })
    });
  }
  if (url.includes('/api/move/')) {
    // Return a basic mock response
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid: true,
        board: ".".repeat(64),
        current_turn: 'black'
      })
    });
  }
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({})
  });
});

const {
  pColor,
  getSquareLabel,
  formatTime,
  getPlayerScore,
  validateMoveWithStockfish,
  clearEvaluationCache,
  selectPiece,
  deselect,
  refreshHighlights,
  onClick,
  onDrop,
  tryMove,
  isPromotionMove,
  showPromoModal,
  hidePromoModal,
  toggleSquareHighlight,
  buildBoard,
  syncPieces,
  getBoard,
  setBoard,
  getTurn,
  setTurn,
  getSelected,
  setSelected,
  getHints,
  setHints,
  getHighlightedSquare,
  setHighlightedSquare,
  getGameMode,
  setGameMode,
  getPlayerColor,
  setPlayerColor,
  getPaused,
  setPaused,
  getGameOver,
  setGameOver,
  getPendingPromo,
  setPendingPromo
} = require("./game/static/game/js/board");

describe("pColor", () => {
  test("returns white for uppercase piece", () => {
    expect(pColor("K")).toBe("white");
  });

  test("returns black for lowercase piece", () => {
    expect(pColor("k")).toBe("black");
  });

  test("returns null for empty piece", () => {
    expect(pColor(null)).toBe(null);
  });
});

describe("getSquareLabel", () => {
  test("returns a8 for row 0 col 0", () => {
    expect(getSquareLabel(0, 0)).toBe("a8");
  });

  test("returns e4 for row 4 col 4", () => {
    expect(getSquareLabel(4, 4)).toBe("e4");
  });

  test("returns h1 for row 7 col 7", () => {
    expect(getSquareLabel(7, 7)).toBe("h1");
  });
});

describe("formatTime", () => {
  test("formats 125 seconds as 2:05", () => {
    expect(formatTime(125)).toBe("2:05");
  });

  test("formats 65 seconds as 1:05", () => {
    expect(formatTime(65)).toBe("1:05");
  });

  test("formats 0 seconds as 0:00", () => {
    expect(formatTime(0)).toBe("0:00");
  });
});

describe("getPlayerScore", () => {
  test("correctly converts cp scores", () => {
    expect(getPlayerScore({ type: 'cp', value: 100 })).toBe(-100);
    expect(getPlayerScore({ type: 'cp', value: -350 })).toBe(350);
    expect(getPlayerScore({ type: 'cp', value: 0 })).toBe(0);
  });

  test("correctly converts mate scores", () => {
    expect(getPlayerScore({ type: 'mate', value: 3 })).toBe(-9997);
    expect(getPlayerScore({ type: 'mate', value: -2 })).toBe(9998);
  });
});

describe("validateMoveWithStockfish", () => {
  beforeEach(() => {
    global.mockScores = {};
    clearEvaluationCache();
  });

  test("returns true for alternative mate move when expected is also mate", async () => {
    global.mockScores['startpos_then_g2g4'] = { type: 'mate', value: -2 };
    global.mockScores['played_fen'] = { type: 'mate', value: -3 };
    const result = await validateMoveWithStockfish("startpos", "played_fen", "g2g4");
    expect(result).toBe(true);
  });

  test("returns true for alternative winning move when within 50cp of expected", async () => {
    global.mockScores['startpos_then_e2e4'] = { type: 'cp', value: -100 };
    global.mockScores['played_fen'] = { type: 'cp', value: -80 };
    const result = await validateMoveWithStockfish("startpos", "played_fen", "e2e4");
    expect(result).toBe(true);
  });

  test("returns true for alternative winning move when both are highly winning (>= 300)", async () => {
    global.mockScores['startpos_then_e2e4'] = { type: 'cp', value: -400 };
    global.mockScores['played_fen'] = { type: 'cp', value: -310 };
    const result = await validateMoveWithStockfish("startpos", "played_fen", "e2e4");
    expect(result).toBe(true);
  });

  test("returns false for alternative move that is significantly worse than expected", async () => {
    global.mockScores['startpos_then_e2e4'] = { type: 'cp', value: -100 };
    global.mockScores['played_fen'] = { type: 'cp', value: 0 };
    const result = await validateMoveWithStockfish("startpos", "played_fen", "e2e4");
    expect(result).toBe(false);
  });

  test("returns false for alternative move that is losing", async () => {
    global.mockScores['startpos_then_e2e4'] = { type: 'cp', value: -100 };
    global.mockScores['played_fen'] = { type: 'cp', value: 200 };
    const result = await validateMoveWithStockfish("startpos", "played_fen", "e2e4");
    expect(result).toBe(false);
  });
});

describe("Coordinates visibility toggle", () => {
  test("toggles .hide-coordinates class on #board when checkbox changes state", () => {
    const checkbox = document.getElementById("showCoordinatesCheckbox");
    const board = document.getElementById("board");
    
    // Default should be checked (true) and class should not be present
    expect(checkbox.checked).toBe(true);
    expect(board.classList.contains("hide-coordinates")).toBe(false);
    
    // Simulate unchecking
    checkbox.checked = false;
    checkbox.dispatchEvent(new Event("change"));
    expect(board.classList.contains("hide-coordinates")).toBe(true);
    expect(localStorage.getItem("showCoordinates")).toBe("false");
    
    // Simulate checking again
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change"));
    expect(board.classList.contains("hide-coordinates")).toBe(false);
    expect(localStorage.getItem("showCoordinates")).toBe("true");
  });
});

describe("Square Highlighting and Selection", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    
    // Reset DOM and state
    const boardEl = document.getElementById("board");
    boardEl.innerHTML = '';
    
    // Set a blank board state for testing
    const testBoard = Array(8).fill(null).map(() => Array(8).fill(null));
    testBoard[6][4] = 'P'; // White pawn on e2
    testBoard[0][4] = 'k'; // Black king on e8
    setBoard(testBoard);
    setSelected(null);
    setHints([]);
    setHighlightedSquare(null);
    setTurn('white');
    setGameMode('pvp');
    setPlayerColor('white');
    setPaused(false);
    setGameOver(false);
    setPendingPromo(null);
    
    // Build the board DOM elements
    buildBoard();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("selecting a playable piece sets selected state and adds selected class to its square", async () => {
    const square = document.querySelector('[data-row="6"][data-col="4"]');
    expect(square.classList.contains("selected")).toBe(false);
    
    await selectPiece(6, 4);
    
    expect(getSelected()).toEqual({ r: 6, c: 4 });
    expect(square.classList.contains("selected")).toBe(true);
  });

  test("selecting an empty square does not select it and does not add selected class", async () => {
    await selectPiece(5, 4); // Empty square
    
    expect(getSelected()).toBeNull();
    const square = document.querySelector('[data-row="5"][data-col="4"]');
    expect(square.classList.contains("selected")).toBe(false);
  });

  test("deselect clears selected state and removes selected class", async () => {
    await selectPiece(6, 4);
    expect(getSelected()).toEqual({ r: 6, c: 4 });
    
    deselect();
    
    expect(getSelected()).toBeNull();
    const square = document.querySelector('[data-row="6"][data-col="4"]');
    expect(square.classList.contains("selected")).toBe(false);
  });

  test("right-clicking a square toggles custom-highlight class", () => {
    const square = document.querySelector('[data-row="6"][data-col="4"]');
    expect(square.classList.contains("custom-highlight")).toBe(false);
    
    toggleSquareHighlight(6, 4);
    expect(getHighlightedSquare()).toEqual({ r: 6, c: 4 });
    expect(square.classList.contains("custom-highlight")).toBe(true);
    
    toggleSquareHighlight(6, 4);
    expect(getHighlightedSquare()).toBeNull();
    expect(square.classList.contains("custom-highlight")).toBe(false);
  });
});

describe("Legal Move Display", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    
    const boardEl = document.getElementById("board");
    boardEl.innerHTML = '';
    const testBoard = Array(8).fill(null).map(() => Array(8).fill(null));
    testBoard[6][4] = 'P'; // White pawn
    testBoard[5][3] = 'p'; // Black pawn at d3 (diagonal capture target)
    setBoard(testBoard);
    setSelected(null);
    setHints([]);
    setTurn('white');
    setGameMode('pvp');
    setPlayerColor('white');
    setPaused(false);
    setGameOver(false);
    setPendingPromo(null);
    buildBoard();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("selecting a piece with valid moves renders move-dot elements in destination squares", async () => {
    // Mock valid moves: e2e3 (normal move), e2e4 (normal move)
    global.fetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid_moves: [
          { row: 5, col: 4, is_capture: false },
          { row: 4, col: 4, is_capture: false }
        ]
      })
    }));

    await selectPiece(6, 4);

    const targetSquare1 = document.querySelector('[data-row="5"][data-col="4"]');
    const targetSquare2 = document.querySelector('[data-row="4"][data-col="4"]');
    
    expect(targetSquare1.querySelector('.move-dot')).not.toBeNull();
    expect(targetSquare2.querySelector('.move-dot')).not.toBeNull();
    expect(targetSquare1.querySelector('.capture-ring')).toBeNull();
  });

  test("selecting a piece with capturing moves renders capture-ring elements in destination squares", async () => {
    // Mock valid moves: e2xd3 (capture)
    global.fetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid_moves: [
          { row: 5, col: 3, is_capture: true }
        ]
      })
    }));

    await selectPiece(6, 4);

    const targetSquare = document.querySelector('[data-row="5"][data-col="3"]');
    expect(targetSquare.querySelector('.capture-ring')).not.toBeNull();
    expect(targetSquare.querySelector('.move-dot')).toBeNull();
  });

  test("changing selection clears old move indicators and displays new ones", async () => {
    const testBoard = getBoard();
    testBoard[7][4] = 'K'; // King
    setBoard(testBoard);
    buildBoard();

    // Select pawn
    global.fetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid_moves: [{ row: 5, col: 4, is_capture: false }]
      })
    }));
    await selectPiece(6, 4);
    expect(document.querySelector('[data-row="5"][data-col="4"]').querySelector('.move-dot')).not.toBeNull();

    // Select king
    global.fetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid_moves: [{ row: 7, col: 3, is_capture: false }]
      })
    }));
    await selectPiece(7, 4);
    
    // Old move indicator should be cleared
    expect(document.querySelector('[data-row="5"][data-col="4"]').querySelector('.move-dot')).toBeNull();
    // New move indicator should be added
    expect(document.querySelector('[data-row="7"][data-col="3"]').querySelector('.move-dot')).not.toBeNull();
  });
});

describe("Click-to-Move and Drag-to-Move Handlers", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    
    const boardEl = document.getElementById("board");
    boardEl.innerHTML = '';
    const testBoard = Array(8).fill(null).map(() => Array(8).fill(null));
    testBoard[6][4] = 'P'; // White pawn
    setBoard(testBoard);
    setSelected(null);
    setHints([]);
    setTurn('white');
    setGameMode('pvp');
    setPlayerColor('white');
    setPaused(false);
    setGameOver(false);
    setPendingPromo(null);
    buildBoard();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("click-to-move: clicking a valid destination square calls executeMove via tryMove", async () => {
    // Select the pawn first
    global.fetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid_moves: [{ row: 5, col: 4, is_capture: false }]
      })
    }));
    await selectPiece(6, 4);
    
    // Mock the move response
    global.fetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid: true,
        board: ".".repeat(64), // Empty board
        current_turn: 'black',
        white_name: 'White',
        black_name: 'Black',
        white_time: 600,
        black_time: 600,
        move_history: [],
        captured_pieces: { white: [], black: [] }
      })
    }));
    await onClick(5, 4);

    // Verify fetch was called with the api/move/ endpoint
    const moveCall = global.fetch.mock.calls.find(call => call[0].includes('/api/move/'));
    expect(moveCall).toBeDefined();
    const payload = JSON.parse(moveCall[1].body);
    expect(payload.from_row).toBe(6);
    expect(payload.from_col).toBe(4);
    expect(payload.to_row).toBe(5);
    expect(payload.to_col).toBe(4);
  });

  test("drag-to-move: dropping a piece on a square calls executeMove via tryMove", async () => {
    // Mock drag source
    const dragSourceSquare = document.querySelector('[data-row="6"][data-col="4"]');
    
    // Simulate drag start
    const dragStartEvent = {
      preventDefault: jest.fn(),
      dataTransfer: {
        setData: jest.fn(),
        setDragImage: jest.fn(),
        effectAllowed: 'none'
      }
    };
    
    // Get dragstart listener from the square
    dragSourceSquare.ondragstart(dragStartEvent);

    // Mock the move response
    global.fetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid: true,
        board: ".".repeat(64),
        current_turn: 'black',
        white_name: 'White',
        black_name: 'Black',
        white_time: 600,
        black_time: 600,
        move_history: [],
        captured_pieces: { white: [], black: [] }
      })
    }));

    // Drop onto target square (5, 4)
    const dropEvent = {
      preventDefault: jest.fn()
    };
    const targetSquare = document.querySelector('[data-row="5"][data-col="4"]');
    await targetSquare.ondrop(dropEvent);

    // Verify the move API was called
    const moveCall = global.fetch.mock.calls.find(call => call[0].includes('/api/move/'));
    expect(moveCall).toBeDefined();
  });

  test("drag-to-move: dragging an opponent's piece on your turn is prevented", () => {
    const testBoard = getBoard();
    testBoard[1][4] = 'p'; // Black pawn (opponent piece)
    setBoard(testBoard);
    buildBoard();

    const square = document.querySelector('[data-row="1"][data-col="4"]');
    const dragStartEvent = {
      preventDefault: jest.fn(),
      dataTransfer: {
        setData: jest.fn(),
        setDragImage: jest.fn()
      }
    };

    square.ondragstart(dragStartEvent);
    expect(dragStartEvent.preventDefault).toHaveBeenCalled();
  });
});

describe("Promotion Modal Trigger Logic", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    
    const boardEl = document.getElementById("board");
    boardEl.innerHTML = '';
    const testBoard = Array(8).fill(null).map(() => Array(8).fill(null));
    testBoard[1][4] = 'P'; // White pawn near promotion
    testBoard[6][3] = 'p'; // Black pawn near promotion
    testBoard[1][3] = 'N'; // White knight near back rank
    setBoard(testBoard);
    setSelected(null);
    setHints([]);
    setTurn('white');
    setGameMode('pvp');
    setPlayerColor('white');
    setPaused(false);
    setGameOver(false);
    setPendingPromo(null);
    
    document.getElementById("promoOverlay").classList.remove("active");
    buildBoard();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("isPromotionMove detects pawns reaching back ranks", () => {
    // White pawn on row 1 moving to row 0 is promotion
    expect(isPromotionMove(1, 4, 0)).toBe(true);
    // White pawn moving elsewhere is not promotion
    expect(isPromotionMove(1, 4, 2)).toBe(false);
    // Black pawn on row 6 moving to row 7 is promotion
    expect(isPromotionMove(6, 3, 7)).toBe(true);
    // Non-pawn piece moving to back rank is not promotion
    expect(isPromotionMove(1, 3, 0)).toBe(false);
  });

  test("moving a promotion-ready pawn triggers the promotion overlay", async () => {
    const promoOverlay = document.getElementById("promoOverlay");
    expect(promoOverlay.classList.contains("active")).toBe(false);

    // Trigger tryMove for white pawn moving to rank 8 (row 0)
    await tryMove(1, 4, 0, 4);

    expect(getPendingPromo()).toEqual({ fr: 1, fc: 4, tr: 0, tc: 4 });
    expect(promoOverlay.classList.contains("active")).toBe(true);
  });

  test("moving a non-pawn to back rank does not trigger promotion overlay", async () => {
    const promoOverlay = document.getElementById("promoOverlay");
    expect(promoOverlay.classList.contains("active")).toBe(false);

    // Mock move response
    global.fetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        valid: true,
        board: ".".repeat(64),
        current_turn: 'black',
        white_name: 'White',
        black_name: 'Black',
        white_time: 600,
        black_time: 600,
        move_history: [],
        captured_pieces: { white: [], black: [] }
      })
    }));

    // Move Knight to row 0
    await tryMove(1, 3, 0, 3);

    expect(getPendingPromo()).toBeNull();
    expect(promoOverlay.classList.contains("active")).toBe(false);
  });
});