document.body.innerHTML = `
  <div id="board"></div>

  <div id="whiteClock"><span class="time" id="whiteTime"></span></div>
  <div id="blackClock"><span class="time" id="blackTime"></span></div>
  <div id="streak-counter"></div>
  <div id="whiteScore"></div>
  <div id="blackScore"></div>
  <div id="game-status"></div>
  <div id="status-indicator"></div>
  <div id="status-text"></div>
  <div id="manualMoveInput"></div>
  <div id="manualMoveError"></div>
  <input id="sanMoveInput" type="text" />
  <button id="sanMoveBtn"></button>
  <div id="sanMoveError" style="display: none;"></div>

  <div id="turnBadge"><span id="turnBadgeText">White</span>'s Turn</div>
  <div id="statusBar"></div>
  <div id="movesList"></div>
  <div id="whiteCaptured"></div>
  <div id="blackCaptured"></div>
  <button id="pauseBtn"></button>
  <div id="promoOverlay"></div>
  <div id="promoChoices"></div>
  <div id="modeBadge"></div>
  <button id="flipBtn"></button>
  <button id="copyFenBtn"></button>
  <div id="welcomeOverlay"></div>
  <button id="welcomeResumeBtn"></button>
  <button id="welcomePvPBtn"></button>
  <button id="welcomeAIBtn"></button>
  <button id="welcomeDailyPuzzleBtn"></button>
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
  <!-- Heuristic Report Stats -->
  <div id="resAccuracyScore"></div>
  <div id="resMistakesCount"></div>
  <div id="resBlundersCount"></div>
  <div id="resAnalysisCaptures"></div>
  <div id="resAnalysisChecks"></div>
  <div id="resAnalysisCheckmates"></div>
  <div id="resAnalysisPromotions"></div>
  <div><span class="detail-label">Best Move Found</span><span id="resBestMove">Nf3 (Excellent)</span></div>
  <div><span class="detail-label">Blunder</span><span id="resBlunder"></span></div>
  <div id="postGameAnalysisPanel" style="display: none;">
    <table><tbody id="postGameAnalysisTableBody"></tbody></table>
  </div>
  <div id="themeSettingsModal" class="theme-settings-modal">
    <button id="openThemeModalBtn"></button>
    <button id="closeThemeModalBtn"></button>
    <button id="saveThemeSettingsBtn"></button>
    <input type="checkbox" id="modalCoordsToggle">
    <div class="theme-swatches-grid">
      <label><input type="radio" name="boardThemeRadio" value="classic" class="theme-radio-input" aria-label="classic theme"><span class="theme-btn" data-theme="classic"></span></label>
      <label><input type="radio" name="boardThemeRadio" value="wood" class="theme-radio-input" aria-label="wood theme"><span class="theme-btn" data-theme="wood"></span></label>
      <label><input type="radio" name="boardThemeRadio" value="slate" class="theme-radio-input" aria-label="slate theme"><span class="theme-btn" data-theme="slate"></span></label>
      <label><input type="radio" name="boardThemeRadio" value="neon" class="theme-radio-input" aria-label="neon theme"><span class="theme-btn" data-theme="neon"></span></label>
      <label><input type="radio" name="boardThemeRadio" value="glass" class="theme-radio-input" aria-label="glass theme"><span class="theme-btn" data-theme="glass"></span></label>
      <label><input type="radio" name="boardThemeRadio" value="dark" class="theme-radio-input" aria-label="dark theme"><span class="theme-btn" data-theme="dark"></span></label>
      <label><input type="radio" name="boardThemeRadio" value="green" class="theme-radio-input" aria-label="green theme"><span class="theme-btn" data-theme="green"></span></label>
      <label><input type="radio" name="boardThemeRadio" value="blue" class="theme-radio-input" aria-label="blue theme"><span class="theme-btn" data-theme="blue"></span></label>
      <label><input type="radio" name="boardThemeRadio" value="pastel" class="theme-radio-input" aria-label="pastel theme"><span class="theme-btn" data-theme="pastel"></span></label>
    </div>
  </div>
`;

const flushPromises = () => new Promise(resolve => setTimeout(resolve, 0));

global.fetch = jest.fn((url, options) => {
  let boardData = [
    ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
    ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
    ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
  ];
  if (url && url.includes('/api/valid-moves/')) {
    return Promise.resolve({
      json: () => Promise.resolve({ valid_moves: [{row: 4, col: 4}, {row: 5, col: 4}, {row: 0, col: 0}] })
    });
  }
  if (url && url.includes('/api/move/')) {
    let newBoard = JSON.parse(JSON.stringify(boardData));
    
    // Simulate e2 to e4 move for click/drop tests
    newBoard[4][4] = 'P';
    newBoard[6][4] = null;
    
    // Simulate promotion test (a7 to a8 = Q)
    newBoard[0][0] = 'Q';
    newBoard[1][0] = null;

    return Promise.resolve({
      json: () => Promise.resolve({ 
        valid: true,
        board: newBoard,
        current_turn: 'black',
        player_color: 'white',
        game_mode: 'pvp',
        difficulty: 'medium',
        white_score: 0,
        black_score: 0,
        captured_pieces: { white: [], black: [] },
        move_history: []
      })
    });
  }
  if (url && url.includes('/api/analyze-game/')) {
    return Promise.resolve({
      json: () => Promise.resolve({
        accuracy: 95,
        mistakes: 1,
        blunders: 0,
        captures: 2,
        checks: 1,
        checkmates: 0,
        promotions: 0
      })
    });
  }
  return Promise.resolve({
    json: () => Promise.resolve({ 
      valid: true,
      fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
      board: boardData,
      current_turn: 'white',
      player_color: 'white',
      game_mode: 'pvp',
      difficulty: 'medium',
      white_score: 0,
      black_score: 0,
      captured_pieces: { white: [], black: [] },
      move_history: []
    }),
  });
});
global.SOUND_BASE_URL = '/static/game/sounds/';

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
    
    if (moveStr === 'invalid' || moveStr === 'illegal') return null;
    
    this._fen = `${this._fen}_then_${moveStr}`;
    
    if (moveStr === 'e4' || moveStr === 'e2e4') return { from: 'e2', to: 'e4', promotion: undefined };
    if (moveStr === 'Nf3') return { from: 'g1', to: 'f3', promotion: undefined };
    if (moveStr === 'O-O') return { from: 'e1', to: 'g1', promotion: undefined };
    if (moveStr === 'e8=Q' || moveStr === 'e8=q' || moveStr === 'e7e8q') return { from: 'e7', to: 'e8', promotion: 'q' };
    if (moveStr === 'Bxc6+') return { from: 'b5', to: 'c6', promotion: undefined };
    if (moveStr === 'Nbd7') return { from: 'b8', to: 'd7', promotion: undefined };
    if (moveStr === 'Qh5+') return { from: 'd1', to: 'h5', promotion: undefined };
    if (moveStr === 'b4') return { from: 'b2', to: 'b4', promotion: undefined };
    if (moveStr === 'bxc5') return { from: 'b4', to: 'c5', promotion: undefined };
    if (moveStr === 'exd5') return { from: 'e4', to: 'd5', promotion: undefined };
    
    return { from: 'a1', to: 'a2' };
  }
  /**
   * Minimal stub used by computeLegalMovesClient (Issue #1445 tests).
   * When called with { square: 'e2', verbose: true } it returns two
   * representative moves for a white pawn on e2.
   */
  moves({ square, verbose } = {}) {
    if (!verbose) return [];
    if (square === 'e2') {
      return [
        { from: 'e2', to: 'e3', piece: 'p', captured: undefined, promotion: undefined },
        { from: 'e2', to: 'e4', piece: 'p', captured: undefined, promotion: undefined },
      ];
    }
    if (square === 'a1') {
      // Simulate a rook that can capture on a8 (to test is_capture mapping)
      return [
        { from: 'a1', to: 'a8', piece: 'r', captured: 'r', promotion: undefined },
      ];
    }
    if (square === 'e7') {
      // Simulate a pawn about to promote
      return [
        { from: 'e7', to: 'e8', piece: 'p', captured: undefined, promotion: 'q' },
        { from: 'e7', to: 'e8', piece: 'p', captured: undefined, promotion: 'r' },
        { from: 'e7', to: 'e8', piece: 'p', captured: undefined, promotion: 'b' },
        { from: 'e7', to: 'e8', piece: 'p', captured: undefined, promotion: 'n' },
      ];
    }
    return [];
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
window.matchMedia = window.matchMedia || function() {
  return {
    matches: true,
    addListener: function() {},
    removeListener: function() {}
  };
};

// Saved before the script loads, to check that it applies the choice on its own.
localStorage.setItem('showCoordinates', 'false');

const { pColor, getSquareLabel, formatTime, getPlayerScore, validateMoveWithStockfish, clearEvaluationCache, onClick, onDrop, showPromoModal, hidePromoModal, onPromoChoice, toggleSquareHighlight, refreshHighlights, highlightCheck, startNewGame, squareLabelToRowCol, computeLegalMovesClient, updatePieceStyle, PIECE_IMG, VALID_PIECE_STYLES } = require("./game/static/game/js/board");

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

describe("Coordinates visibility", () => {
  test("the saved choice is applied when the script loads", () => {
    expect(document.getElementById("board").classList.contains("hide-coordinates")).toBe(true);
  });

  test("the settings toggle shows and hides them and saves the choice", () => {
    const toggle = document.getElementById("modalCoordsToggle");
    const board = document.getElementById("board");

    toggle.checked = true;
    toggle.dispatchEvent(new Event("change"));
    expect(board.classList.contains("hide-coordinates")).toBe(false);
    expect(localStorage.getItem("showCoordinates")).toBe("true");

    toggle.checked = false;
    toggle.dispatchEvent(new Event("change"));
    expect(board.classList.contains("hide-coordinates")).toBe(true);
    expect(localStorage.getItem("showCoordinates")).toBe("false");

    toggle.checked = true;
    toggle.dispatchEvent(new Event("change"));
  });
});

describe("Board UI Interactions", () => {
  beforeEach(async () => {
    document.getElementById("board").innerHTML = "";
    const overlay = document.getElementById("promoOverlay");
    if(overlay) overlay.classList.remove("active");
    
    // Call startNewGame to initialize board variable and DOM
    await startNewGame('pvp', 'white', 'medium', 'startpos', 10);
  });

  it('toggleSquareHighlight toggles custom-highlight class', () => {
    const sq = document.getElementById("board").children[52];
    toggleSquareHighlight(6, 4);
    expect(sq.classList.contains("custom-highlight")).toBe(true);
    toggleSquareHighlight(6, 4);
    expect(sq.classList.contains("custom-highlight")).toBe(false);
  });

  it('showPromoModal makes overlay active', () => {
    showPromoModal('white');
    const overlay = document.getElementById("promoOverlay");
    expect(overlay.classList.contains("active")).toBe(true);
  });

  it('hidePromoModal removes active class', () => {
    const overlay = document.getElementById("promoOverlay");
    overlay.classList.add("active");
    hidePromoModal();
    expect(overlay.classList.contains("active")).toBe(false);
  });

  it('handles hotkeys and visual labels for promotion', async () => {
    const originalFetch = global.fetch;
    const customBoard = [
      [null, null, null, null, null, null, null, null],
      [null, null, null, null, 'P', null, null, null],
      [null, null, null, null, null, null, null, null],
      [null, null, null, null, null, null, null, null],
      [null, null, null, null, null, null, null, null],
      [null, null, null, null, null, null, null, null],
      [null, null, null, null, null, null, null, null],
      [null, null, null, null, null, null, null, null]
    ];
    
    global.fetch = jest.fn((url) => {
      if (url.includes('/api/new-game/')) {
        return Promise.resolve({
          json: () => Promise.resolve({
            valid: true,
            board: customBoard,
            current_turn: 'white',
            player_color: 'white',
            game_mode: 'pvp',
          })
        });
      }
      if (url.includes('/api/state/')) {
        return Promise.resolve({
          json: () => Promise.resolve({
            valid: true,
            board: customBoard,
            current_turn: 'white',
            player_color: 'white',
            game_mode: 'pvp',
            white_time: 300,
            black_time: 300,
            paused: false,
            captured_pieces: { white: [], black: [] },
            move_history: []
          })
        });
      }
      if (url.includes('/api/valid-moves/')) {
        return Promise.resolve({
          json: () => Promise.resolve({
            valid_moves: [{ row: 0, col: 4 }]
          })
        });
      }
      if (url.includes('/api/move/')) {
        return Promise.resolve({
          json: () => Promise.resolve({
            valid: true,
            board: customBoard,
            current_turn: 'black',
            player_color: 'white',
            game_mode: 'pvp',
            captured_pieces: { white: [], black: [] },
            move_history: []
          })
        });
      }
      return Promise.resolve({
        json: () => Promise.resolve({ valid: true })
      });
    });

    try {
      // Re-initialize with custom board layout FEN
      await startNewGame('pvp', 'white', 'medium', '8/4P3/8/8/8/8/8/8 w - - 0 1', 10);

      // Trigger DOM clicks instead of calling onClick directly to avoid stale closures
      const boardEl = document.getElementById("board");
      const e7Square = boardEl.children[1 * 8 + 4]; // row 1, col 4
      const e8Square = boardEl.children[0 * 8 + 4]; // row 0, col 4

      // Select pawn on e7 (row 1, col 4)
      e7Square.click();
      await flushPromises();
 
      // Move to e8 (row 0, col 4) (promotes)
      e8Square.click();
      await flushPromises();
 
      const overlay = document.getElementById("promoOverlay");
      expect(overlay.classList.contains("active")).toBe(true);
 
      const promoChoices = document.getElementById("promoChoices");
      const buttons = promoChoices.querySelectorAll(".promo-btn");
      expect(buttons.length).toBe(4);
      expect(buttons[0].querySelector(".promo-key").textContent).toBe("(q)");
      expect(buttons[0].querySelector(".promo-text").textContent).toContain("Queen");
 
      global.fetch.mockClear();
 
      // Dispatch an invalid key 'x' and assert overlay stays active and no fetch call is made
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'x' }));
      await flushPromises();
      expect(overlay.classList.contains("active")).toBe(true);
      expect(global.fetch.mock.calls.length).toBe(0);
 
      // Focus an input element to verify keydown intercepts even when inputs are focused
      const inputEl = document.getElementById("sanMoveInput");
      inputEl.focus();
      expect(document.activeElement).toBe(inputEl);
 
      // Dispatch an uppercase 'Q' and assert overlay closes and correct move is submitted
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Q' }));
      await flushPromises();

      expect(overlay.classList.contains("active")).toBe(false);

      const moveCall = global.fetch.mock.calls.find(c => c[0].includes('/api/move/'));
      expect(moveCall).toBeDefined();
      const requestBody = JSON.parse(moveCall[1].body);
      expect(requestBody.promotion_piece).toBe('q');

      // Blur the input element at the end of the test to clean up focus state
      inputEl.blur();
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('onClick ignores invalid moves when game is over', async () => {
    global.fetch.mockClear();
    // Use valid bounds but empty square (or anything, just check it doesn't do a move fetch)
    await onClick(3, 3); 
    const fetchCalls = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(fetchCalls.length).toBe(0);
  });

  it('onDrop rejects drop on invalid square', async () => {
    global.fetch.mockClear();
    const e = { preventDefault: jest.fn(), stopPropagation: jest.fn() };
    await onDrop(e, -1, -1);
    const fetchCalls = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(fetchCalls.length).toBe(0);
  });

  it('onClick attempts to select piece', async () => {
    global.fetch.mockClear();
    try {
        await onClick(6, 4); 
    } catch(e) {}
    const moveReqs = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(0); // Only hints are fetched
  });

  it('a drag from an empty square is refused', () => {
    const e = { dataTransfer: { setData: jest.fn(), setDragImage: jest.fn() }, preventDefault: jest.fn() };
    const empty = document.getElementById("board").children[3 * 8 + 3];
    empty.ondragstart(e);
    expect(e.preventDefault).toHaveBeenCalled();
  });

  it('a drag of your own piece on your turn is allowed', () => {
    const e = { dataTransfer: { setData: jest.fn(), setDragImage: jest.fn() }, preventDefault: jest.fn() };
    const e2 = document.getElementById("board").children[6 * 8 + 4];
    e2.ondragstart(e);
    expect(e.preventDefault).not.toHaveBeenCalled();
    e2.ondragend();
  });

  it('a drop is handled by the page, not left to the browser', async () => {
    const e = { preventDefault: jest.fn() };
    await onDrop(e, 4, 4);
    expect(e.preventDefault).toHaveBeenCalled();
  });

  it('shortcuts leave Ctrl and Cmd combinations to the browser', () => {
    const resignBtn = document.getElementById("resignBtn");
    const click = jest.spyOn(resignBtn, 'click');

    const reload = new KeyboardEvent('keydown', { key: 'r', ctrlKey: true, cancelable: true });
    document.dispatchEvent(reload);
    expect(click).not.toHaveBeenCalled();
    expect(reload.defaultPrevented).toBe(false);

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'r', cancelable: true }));
    expect(click).toHaveBeenCalledTimes(1);
    click.mockRestore();
  });

  it('a second click while a move is being sent does not send it twice', async () => {
    global.fetch.mockClear();
    await onClick(6, 4);
    await Promise.all([onClick(4, 4), onClick(4, 4)]);
    const moveReqs = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
  });

  it('a touch drag from a piece to another square sends the move', async () => {
    global.fetch.mockClear();
    const boardEl = document.getElementById("board");
    const from = boardEl.children[6 * 8 + 4];
    const to = boardEl.children[4 * 8 + 4];
    const touchEvent = (type, x, y) => {
      const ev = new Event(type, { bubbles: true, cancelable: true });
      ev.touches = [{ clientX: x, clientY: y }];
      ev.changedTouches = [{ clientX: x, clientY: y }];
      return ev;
    };
    document.elementFromPoint = jest.fn(() => to); // jsdom has no layout to hit-test
    try {
      from.dispatchEvent(touchEvent('touchstart', 10, 10));
      from.dispatchEvent(touchEvent('touchmove', 10, 40));
      from.dispatchEvent(touchEvent('touchend', 10, 40));
      await flushPromises();
    } finally {
      delete document.elementFromPoint;
    }

    const moveReqs = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    const body = JSON.parse(moveReqs[0][1].body);
    expect([body.from_row, body.from_col, body.to_row, body.to_col]).toEqual([6, 4, 4, 4]);
  });

  it('the board is one tab stop and keeps keyboard focus after a move', async () => {
    const boardEl = document.getElementById("board");
    expect(boardEl.querySelectorAll('[tabindex="0"]').length).toBe(1);

    boardEl.children[6 * 8 + 4].focus();
    await onClick(6, 4);
    boardEl.children[4 * 8 + 4].focus();
    await onClick(4, 4);

    // the move rebuilt every square; focus is back on the square it was on
    expect(boardEl.contains(document.activeElement)).toBe(true);
    expect(document.activeElement.dataset.row).toBe('4');
    expect(document.activeElement.dataset.col).toBe('4');
    expect(boardEl.querySelectorAll('[tabindex="0"]').length).toBe(1);
  });

  it('arrow keys follow the screen when the board is flipped', () => {
    const boardEl = document.getElementById("board");
    const flipBtn = document.getElementById("flipBtn");
    const square = (r, c) => boardEl.querySelector(`[data-row="${r}"][data-col="${c}"]`);
    const press = (key) => document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));

    square(4, 4).focus();
    press('ArrowUp');
    expect(document.activeElement.dataset.row).toBe('3'); // towards rank 8, which is at the top

    flipBtn.onclick();
    try {
      square(4, 4).focus();
      press('ArrowUp');
      expect(document.activeElement.dataset.row).toBe('5'); // rank 1 is at the top now
      press('ArrowLeft');
      expect(document.activeElement.dataset.col).toBe('5'); // and the h-file is on the left
    } finally {
      flipBtn.onclick();
    }
  });

  it('second toggleSquareHighlight on different square changes highlight', () => {
    const sq1 = document.getElementById("board").children[52]; // 6,4
    const sq2 = document.getElementById("board").children[44]; // 5,4
    
    toggleSquareHighlight(6, 4); 
    expect(sq1.classList.contains("custom-highlight")).toBe(true);
    toggleSquareHighlight(5, 4);
    expect(sq1.classList.contains("custom-highlight")).toBe(false);
    expect(sq2.classList.contains("custom-highlight")).toBe(true);
  });

  it('onPromoChoice is a function that takes a string', () => {
    expect(typeof onPromoChoice).toBe('function');
  });
});

describe("SAN Quick Move Input", () => {
  beforeEach(async () => {
    document.getElementById("board").innerHTML = "";
    document.getElementById("sanMoveInput").value = "";
    document.getElementById("sanMoveError").style.display = "none";
    document.getElementById("sanMoveBtn").disabled = false;
    global.fetch.mockClear();
    
    // Call startNewGame to initialize board variable and DOM
    const { startNewGame } = require("./game/static/game/js/board");
    await startNewGame('pvp', 'white', 'medium', 'startpos', 10);
  });


  it('valid pawn move (e4) using Enter key clears input and calls /api/move/', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "e4";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    
    await flushPromises();
    
    expect(input.value).toBe('');
    
    const moveReqs = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    
    const body = JSON.parse(moveReqs[0][1].body);
    // e2 is (1, 4), e4 is (3, 4) -> indices: fr=6, fc=4, tr=4, tc=4
    expect(body.from_row).toBe(6);
    expect(body.from_col).toBe(4);
    expect(body.to_row).toBe(4);
    expect(body.to_col).toBe(4);
  });

  it('valid piece move (Nf3) using Move button', async () => {
    const input = document.getElementById("sanMoveInput");
    const btn = document.getElementById("sanMoveBtn");
    input.value = "Nf3";
    btn.click();
    
    await flushPromises();
    
    expect(input.value).toBe('');
    
    const moveReqs = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    const body = JSON.parse(moveReqs[0][1].body);
    // g1 is (0, 6), f3 is (2, 5) -> indices: fr=7, fc=6, tr=5, tc=5
    expect(body.from_row).toBe(7);
    expect(body.from_col).toBe(6);
    expect(body.to_row).toBe(5);
    expect(body.to_col).toBe(5);
  });

  it('castling (O-O) move mapping', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "O-O";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    
    await flushPromises();
    expect(input.value).toBe('');
    
    const moveReqs = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    const body = JSON.parse(moveReqs[0][1].body);
    // e1 to g1 -> fr=7, fc=4, tr=7, tc=6
    expect(body.from_row).toBe(7);
    expect(body.from_col).toBe(4);
    expect(body.to_row).toBe(7);
    expect(body.to_col).toBe(6);
  });

  it('invalid notation retains input and shows error', async () => {
    const input = document.getElementById("sanMoveInput");
    const err = document.getElementById("sanMoveError");
    input.value = "invalid";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    
    await flushPromises();
    
    expect(input.value).toBe('invalid'); // input retained
    expect(err.style.display).toBe('block');
    expect(err.textContent).toContain('Invalid or illegal move notation');
    
    const moveReqs = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(0);
  });
  
  it('illegal move retains input and shows error', async () => {
    const input = document.getElementById("sanMoveInput");
    const err = document.getElementById("sanMoveError");
    input.value = "illegal";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    
    await flushPromises();
    
    expect(input.value).toBe('illegal');
    expect(err.style.display).toBe('block');
  });

  it('Escape clears and blurs the input', () => {
    const input = document.getElementById("sanMoveInput");
    const err = document.getElementById("sanMoveError");
    input.value = "partial";
    err.style.display = "block";
    
    input.focus();
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    
    expect(input.value).toBe('');
    expect(err.style.display).toBe('none');
    // document.activeElement might not accurately reflect blur in jsdom without attached body, but value clearing is tested.
  });

  it('typing shortcut characters (f) while focused does not trigger global shortcuts', () => {
    const input = document.getElementById("sanMoveInput");
    const flipBtn = document.getElementById("flipBtn");
    // Mock the click on flipBtn
    flipBtn.click = jest.fn();

    // Save the original activeElement descriptor and restore it after the test
    const originalDescriptor = Object.getOwnPropertyDescriptor(document, 'activeElement');
    try {
      Object.defineProperty(document, 'activeElement', { value: input, configurable: true, writable: true });
      
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f' }));
      
      expect(flipBtn.click).not.toHaveBeenCalled();
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(document, 'activeElement', originalDescriptor);
      } else {
        delete document.activeElement;
      }
    }
  });

  it('backend move rejection retains input and shows error', async () => {
    const input = document.getElementById("sanMoveInput");
    const err = document.getElementById("sanMoveError");
    
    // Override fetch temporarily for this test
    const originalFetch = global.fetch;
    try {
      global.fetch = jest.fn(async (url, options) => {
        if (url && url.includes('/api/state/')) return { json: async () => ({ fen: 'startpos' }) };
        if (url && url.includes('/api/move/')) return { json: async () => ({ valid: false, message: 'Backend rejected' }) };
        return originalFetch(url, options);
      });

      input.value = "e4";
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      await flushPromises();
      
      expect(input.value).toBe('e4');
      expect(err.style.display).toBe('block');
      expect(err.textContent).toContain('Backend rejected');
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('SAN with capture and check (Bxc6+)', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "Bxc6+";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();
    
    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // b5 -> c6: fr=3, fc=1, tr=2, tc=2
    expect(body.from_row).toBe(3);
    expect(body.from_col).toBe(1);
    expect(body.to_row).toBe(2);
    expect(body.to_col).toBe(2);
  });

  it('SAN with disambiguation (Nbd7)', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "Nbd7";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();
    
    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // b8 -> d7: fr=0, fc=1, tr=1, tc=3
    expect(body.from_row).toBe(0);
    expect(body.from_col).toBe(1);
    expect(body.to_row).toBe(1);
    expect(body.to_col).toBe(3);
  });

  it('SAN with check suffix (Qh5+)', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "Qh5+";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();
    
    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // d1 -> h5: fr=7, fc=3, tr=3, tc=7
    expect(body.from_row).toBe(7);
    expect(body.from_col).toBe(3);
    expect(body.to_row).toBe(3);
    expect(body.to_col).toBe(7);
  });

  it('SAN with promotion (e8=Q)', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "e8=Q";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();
    
    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // e7 -> e8: fr=1, fc=4, tr=0, tc=4
    expect(body.from_row).toBe(1);
    expect(body.from_col).toBe(4);
    expect(body.to_row).toBe(0);
    expect(body.to_col).toBe(4);
    expect(body.promotion_piece).toBe('q');
  });

  it('fully-uppercase piece SAN (NF3) is normalized and executed', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "NF3";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();
    
    // Should normalize to Nf3 and succeed
    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // g1 -> f3: fr=7, fc=6, tr=5, tc=5
    expect(body.from_row).toBe(7);
    expect(body.from_col).toBe(6);
    expect(body.to_row).toBe(5);
    expect(body.to_col).toBe(5);
  });

  it('fully-uppercase pawn SAN (E4) is normalized and executed', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "E4";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();
    
    // Should normalize to e4 and succeed
    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // e2 -> e4: fr=6, fc=4, tr=4, tc=4
    expect(body.from_row).toBe(6);
    expect(body.from_col).toBe(4);
    expect(body.to_row).toBe(4);
    expect(body.to_col).toBe(4);
  });

  it('b-file pawn move (b4) is not treated as Bishop move', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "b4";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();

    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // b2 -> b4: fr=6, fc=1, tr=4, tc=1
    expect(body.from_row).toBe(6);
    expect(body.from_col).toBe(1);
    expect(body.to_row).toBe(4);
    expect(body.to_col).toBe(1);
  });

  it('b-file pawn capture (bxc5) is not treated as Bishop capture', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "bxc5";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();

    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // b4 -> c5: fr=4, fc=1, tr=3, tc=2
    expect(body.from_row).toBe(4);
    expect(body.from_col).toBe(1);
    expect(body.to_row).toBe(3);
    expect(body.to_col).toBe(2);
  });

  it('fully-uppercase pawn capture (EXD5) is normalized to exd5', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "EXD5";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await flushPromises();

    expect(input.value).toBe('');
    const moveReqs = global.fetch.mock.calls.filter(c => c[0] && c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
    const body = JSON.parse(moveReqs[moveReqs.length - 1][1].body);
    // e4 -> d5: fr=4, fc=4, tr=3, tc=3
    expect(body.from_row).toBe(4);
    expect(body.from_col).toBe(4);
    expect(body.to_row).toBe(3);
    expect(body.to_col).toBe(3);
  });
  it('rapid double Enter does not fire two overlapping move requests', async () => {
    const input = document.getElementById("sanMoveInput");
    input.value = "e4";
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));

    await flushPromises();

    const moveReqs = global.fetch.mock.calls.filter(c => c[0].includes('/api/move/'));
    expect(moveReqs.length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Issue #1445: client-side legal move computation
// ---------------------------------------------------------------------------
describe("Client-side legal move computation (Issue #1445)", () => {
  describe("squareLabelToRowCol", () => {
    it('converts a8 to row=0, col=0', () => {
      expect(squareLabelToRowCol('a8')).toEqual({ row: 0, col: 0 });
    });

    it('converts h1 to row=7, col=7', () => {
      expect(squareLabelToRowCol('h1')).toEqual({ row: 7, col: 7 });
    });

    it('converts e4 to row=4, col=4', () => {
      expect(squareLabelToRowCol('e4')).toEqual({ row: 4, col: 4 });
    });

    it('converts e3 to row=5, col=4', () => {
      expect(squareLabelToRowCol('e3')).toEqual({ row: 5, col: 4 });
    });

    it('converts e8 to row=0, col=4', () => {
      expect(squareLabelToRowCol('e8')).toEqual({ row: 0, col: 4 });
    });
  });

  describe("computeLegalMovesClient", () => {
    it('returns a non-null array when chess.js is available', () => {
      const result = computeLegalMovesClient(6, 4); // e2 pawn
      expect(result).not.toBeNull();
      expect(Array.isArray(result)).toBe(true);
    });

    it('maps pawn moves for e2 correctly (two forward squares)', () => {
      const result = computeLegalMovesClient(6, 4); // e2 square
      // MockChess.moves returns e3 and e4 for e2
      expect(result.length).toBe(2);
      // e3 => row 5, col 4
      expect(result).toContainEqual({ row: 5, col: 4, is_capture: false, is_promotion: false });
      // e4 => row 4, col 4
      expect(result).toContainEqual({ row: 4, col: 4, is_capture: false, is_promotion: false });
    });

    it('marks is_capture=true when captured field is present', () => {
      // a1 rook capturing a8 per MockChess stub
      const result = computeLegalMovesClient(7, 0); // a1
      expect(result).not.toBeNull();
      expect(result.length).toBe(1);
      expect(result[0].is_capture).toBe(true);
      expect(result[0].is_promotion).toBe(false);
    });

    it('marks is_promotion=true when promotion field is present and deduplicates promotion moves', () => {
      // e7 pawn promoting per MockChess stub
      const result = computeLegalMovesClient(1, 4); // e7
      expect(result).not.toBeNull();
      // Even though MockChess returns 4 promotion moves (q, r, b, n), they are deduplicated by destination
      expect(result.length).toBe(1);
      expect(result[0].is_promotion).toBe(true);
      expect(result[0].row).toBe(0); // e8 -> row 0
      expect(result[0].col).toBe(4); // e8 -> col 4
    });

    it('returns null when window.Chess is unavailable', () => {
      const saved = global.Chess;
      global.Chess = undefined;
      try {
        const result = computeLegalMovesClient(6, 4);
        expect(result).toBeNull();
      } finally {
        global.Chess = saved;
      }
    });

    it('returns an empty array for a square with no legal moves', () => {
      // MockChess returns [] for any square not explicitly handled
      const result = computeLegalMovesClient(3, 3); // d5, no piece stub
      expect(result).not.toBeNull();
      expect(result).toEqual([]);
    });
  });

  describe("onClick does not call /api/valid-moves/ when chess.js is available", () => {
    beforeEach(async () => {
      document.getElementById("board").innerHTML = "";
      global.fetch.mockClear();
      await startNewGame('pvp', 'white', 'medium', null, 10);
    });

    it('clicking a piece never calls /api/valid-moves/ (uses client computation)', async () => {
      await onClick(6, 4); // click the e2 pawn
      const validMovesReqs = global.fetch.mock.calls.filter(
        c => c[0] && c[0].includes('/api/valid-moves/')
      );
      expect(validMovesReqs.length).toBe(0);
    });

    it('clicking a piece still shows hints without a network round-trip', async () => {
      // computeLegalMovesClient returns moves synchronously so the board
      // should have hint dots right after onClick resolves.
      await onClick(6, 4);
      const boardEl = document.getElementById('board');
      // The highlights are added via refreshHighlights -> sq().appendChild(div.move-dot)
      const dots = boardEl.querySelectorAll('.move-dot');
      // MockChess returns 2 moves for e2 (e3, e4) - both are non-captures
      expect(dots.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Customizable Piece Styles Theme", () => {
    it("offers the three local piece sets", () => {
      expect(VALID_PIECE_STYLES).toEqual(["classic", "wood", "outline"]);
    });

    it("points PIECE_IMG at the local SVGs for the chosen style", () => {
      updatePieceStyle("wood");
      expect(PIECE_IMG["wk"]).toBe("/static/game/pieces/wood/wk.svg");
      expect(PIECE_IMG["bp"]).toBe("/static/game/pieces/wood/bp.svg");

      updatePieceStyle("outline");
      expect(PIECE_IMG["wk"]).toBe("/static/game/pieces/outline/wk.svg");
    });

    it("falls back to classic for a style saved by an older version", () => {
      for (const old of ["neo", "alpha", "cburnett", "invalid_theme_name"]) {
        updatePieceStyle(old);
        expect(PIECE_IMG["wk"]).toBe("/static/game/pieces/classic/wk.svg");
      }
    });
  });

  describe("Customizable Chessboard Themes", () => {
    it("supports switching board themes via modal radio buttons and persisting to localStorage", () => {
      const validThemes = ['classic', 'wood', 'slate', 'neon', 'glass', 'dark', 'green', 'blue', 'pastel'];
      validThemes.forEach(theme => {
        const radio = document.querySelector(`input[name="boardThemeRadio"][value="${theme}"]`);
        expect(radio).not.toBeNull();
        radio.checked = true;
        radio.dispatchEvent(new Event('change', { bubbles: true }));
        
        expect(document.documentElement.getAttribute('data-board-theme')).toBe(theme);
        expect(localStorage.getItem('boardTheme')).toBe(theme);
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Exchanges with the server: AI replies, clocks, post-game analysis, puzzles,
// and the question asked before a rated game is abandoned. fetch is mocked,
// so these check what the page does with each answer, not the server itself.
// ---------------------------------------------------------------------------
describe("Exchanges with the server", () => {
  const START = [
    ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
    ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
    ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
  ];
  const aiGame = {
    valid: true, board: START, fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', current_turn: 'white',
    mode: 'ai', player_color: 'white', difficulty: 'easy',
    white_time: 600, black_time: 600, time_limit: 600, increment: 0, paused: false,
    captured_pieces: { white: [], black: [] }, move_history: [], game_status: 'active'
  };
  const pvpGame = { ...aiGame, mode: 'pvp' };
  const afterWhiteMove = { ...aiGame, current_turn: 'black', move_history: [{ notation: 'e4' }] };
  const afterAiMove = {
    ...aiGame,
    move_history: [{ notation: 'e4' }, { notation: 'e5' }],
    ai_move: { from_row: 1, from_col: 4, to_row: 3, to_col: 4 }
  };

  let originalFetch;

  // routes maps a piece of the URL to the JSON body to answer with, or to
  // { body, status }, or to a function returning either. { notJson: true }
  // answers the way a server without that URL does: a 404 page.
  function mockServer(routes) {
    global.fetch = jest.fn((url) => {
      const key = Object.keys(routes).find(k => url.includes(k));
      let answer = key ? routes[key] : aiGame;
      if (typeof answer === 'function') answer = answer(url);
      if (answer.notJson) {
        return Promise.resolve({ status: 404, ok: false, json: () => Promise.reject(new SyntaxError('Unexpected token <')) });
      }
      const body = answer.body || answer;
      const status = answer.status || 200;
      return Promise.resolve({ status, ok: status < 400, json: () => Promise.resolve(body) });
    });
  }
  const calls = (part) => global.fetch.mock.calls.filter(c => c[0].includes(part));
  const statusLine = () => document.getElementById('game-status').textContent;
  const playE4 = async () => {
    await onClick(6, 4);
    await onClick(4, 4);
  };

  beforeEach(() => {
    originalFetch = global.fetch;
    document.getElementById("board").innerHTML = "";
    document.getElementById("confirmOverlay").classList.remove("active");
  });

  afterEach(async () => {
    jest.useRealTimers();
    // Let 0 ms timers from this test run now, not during the next one.
    await flushPromises();
    global.fetch = originalFetch;
  });

  describe("AI moves", () => {
    it('after the AI replies it is the player\'s turn and the state is not reloaded', async () => {
      mockServer({ '/api/move/': afterWhiteMove, '/api/ai-move/': afterAiMove });
      jest.useFakeTimers();
      await startNewGame('ai', 'white', 'easy', null, 10);
      await playE4();
      global.fetch.mockClear();

      await jest.advanceTimersByTimeAsync(1600); // the easy AI waits at most 1.5 s before moving

      expect(calls('/api/ai-move/').length).toBe(1);
      expect(calls('/api/state/').length).toBe(0);
      expect(statusLine()).toBe('Your turn.');
    });

    it('asks the engine again after a 503 and does not end the game', async () => {
      const answers = [
        { status: 503, body: { valid: false, message: 'The engine did not answer. Please try again.' } },
        afterAiMove
      ];
      mockServer({ '/api/move/': afterWhiteMove, '/api/ai-move/': () => answers.shift() });
      jest.useFakeTimers();
      await startNewGame('ai', 'white', 'easy', null, 10);
      await playE4();
      global.fetch.mockClear();

      await jest.advanceTimersByTimeAsync(1600);
      expect(statusLine()).toBe('The AI is taking longer than usual...');

      await jest.advanceTimersByTimeAsync(1000 + 200 + 1600);
      expect(calls('/api/ai-move/').length).toBe(2);
      expect(calls('/api/analyze-game/').length).toBe(0); // the game did not end
      expect(statusLine()).toBe('Your turn.');
    });

    it('takes the server\'s state when the server says it is not the computer\'s turn', async () => {
      mockServer({
        '/api/move/': afterWhiteMove,
        '/api/ai-move/': { status: 400, body: { valid: false, message: "It is not the computer's turn." } }
      });
      jest.useFakeTimers();
      await startNewGame('ai', 'white', 'easy', null, 10);
      await playE4();
      global.fetch.mockClear();

      await jest.advanceTimersByTimeAsync(1600);
      await jest.advanceTimersByTimeAsync(2000);

      expect(calls('/api/state/').length).toBe(1);
      expect(calls('/api/ai-move/').length).toBe(1); // the state says White to move, so no second request
      expect(statusLine()).not.toContain('undefined');
    });

    it('ends the game when the engine has no move because it is mated', async () => {
      mockServer({
        '/api/move/': afterWhiteMove,
        '/api/ai-move/': { ...afterWhiteMove, game_status: 'checkmate' }
      });
      jest.useFakeTimers();
      await startNewGame('ai', 'white', 'easy', null, 10);
      await playE4();

      await jest.advanceTimersByTimeAsync(1600);

      expect(calls('/api/state/').length).toBe(1); // only the one from starting the game
      expect(document.getElementById('gameOverMessage').textContent).toContain('Wins!');
    });
  });

  describe("Rejected moves", () => {
    it('shows the error text of an answer that has no message, and reloads on a conflict', async () => {
      mockServer({ '/api/move/': { status: 409, body: { error: 'Conflict: Stale game state.' } } });
      await startNewGame('ai', 'white', 'easy', null, 10);
      global.fetch.mockClear();
      await playE4();

      expect(statusLine()).toBe('Conflict: Stale game state.');
      expect(calls('/api/state/').length).toBe(1);
    });

    it('ends the game when the server says the mover\'s clock ran out', async () => {
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': pvpGame,
        '/api/move/': { ...pvpGame, valid: false, message: 'White ran out of time', game_status: 'timeout', winner: 'black', white_time: 0 }
      });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await playE4();

      expect(document.getElementById('gameOverMessage').textContent).toContain('ran out of time');
      expect(document.getElementById('gameOverMessage').textContent).toContain('BLACK Wins!');
    });
  });

  describe("Flag fall", () => {
    const lowOnTime = { ...pvpGame, white_time: 2 };

    it('asks /api/timeout/ and ends the game with the winner it names', async () => {
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': lowOnTime,
        '/api/timeout/': { valid: true, game_status: 'timeout', winner: 'black', white_time: 0, black_time: 600, version: 0 }
      });
      jest.useFakeTimers();
      await startNewGame('pvp', 'white', 'medium', null, 10);

      await jest.advanceTimersByTimeAsync(3000);

      expect(calls('/api/timeout/').length).toBe(1);
      expect(document.getElementById('gameOverMessage').textContent).toContain('BLACK Wins!');
    });

    it('runs on from the server\'s clock when the server says there is time left', async () => {
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': lowOnTime,
        '/api/timeout/': { status: 400, body: { valid: false, message: 'Clock has not run out.', white_time: 30, black_time: 600 } }
      });
      jest.useFakeTimers();
      await startNewGame('pvp', 'white', 'medium', null, 10);

      await jest.advanceTimersByTimeAsync(2500);

      expect(calls('/api/timeout/').length).toBe(1);
      expect(calls('/api/analyze-game/').length).toBe(0); // the game goes on
      expect(document.getElementById('whiteTime').textContent.trim()).toBe('0:30');
    });

    it('ends the game on the page when the server has no such URL', async () => {
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': lowOnTime,
        '/api/timeout/': { notJson: true }
      });
      jest.useFakeTimers();
      await startNewGame('pvp', 'white', 'medium', null, 10);

      await jest.advanceTimersByTimeAsync(3000);

      expect(calls('/api/timeout/').length).toBe(1);
      expect(document.getElementById('gameOverMessage').textContent).toContain('ran out of time');
    });
  });

  describe("Post-game analysis", () => {
    // The base template sets data-auth on <html>; only a signed-in player is sent the analysis.
    beforeEach(() => {
      document.documentElement.dataset.auth = '1';
      // Games here start from the normal position; an earlier test may have
      // left a custom starting FEN behind.
      localStorage.removeItem('checkora_starting_fen');
    });
    afterEach(() => {
      delete document.documentElement.dataset.auth;
    });

    it('fills the table and the summary, with a dash for no accuracy and a note when cut short', async () => {
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': pvpGame,
        '/api/move/': { ...pvpGame, current_turn: 'black', move_history: [{ notation: 'e4' }], game_status: 'checkmate' },
        '/api/analyze-game/': {
          accuracy: null, mistakes: 0, blunders: 0, truncated: true, final_eval: 10,
          move_analysis_details: [
            { move_num: 1, color: 'white', played: 'e4', best: 'e4', class: 'Best', eval: 20 },
            { move_num: 1, color: 'black', played: 'e5', best: '?', class: 'Unknown', eval: null }
          ]
        }
      });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await playE4();
      await flushPromises();

      const rows = document.getElementById('postGameAnalysisTableBody').children;
      expect(rows.length).toBe(2);
      expect(document.getElementById('postGameAnalysisPanel').style.display).toBe('block');
      expect(document.getElementById('resBestMove').textContent).toBe('e4 (Best)');
      expect(document.getElementById('resAccuracyScore').textContent).toBe('-');
      expect(document.getElementById('analysisTruncatedNote').textContent).toContain('only the first moves');
      // Each row carries its verdict for the stylesheet, and no colours of its own.
      expect(rows[0].dataset.verdict).toBe('best');
      expect(rows[1].dataset.verdict).toBe('unknown');
      expect(document.getElementById('postGameAnalysisTableBody').querySelector('[style]')).toBeNull();
    });

    it('is not asked for when the player is signed out', async () => {
      document.documentElement.dataset.auth = '0';
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': pvpGame,
        '/api/move/': { ...pvpGame, current_turn: 'black', move_history: [{ notation: 'e4' }], game_status: 'checkmate' }
      });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await playE4();
      await flushPromises();

      expect(document.getElementById('gameOverMessage').textContent).toContain('Wins!'); // the game did end
      expect(calls('/api/analyze-game/').length).toBe(0);
    });

    it('is asked for once when the player is signed in', async () => {
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': pvpGame,
        '/api/move/': { ...pvpGame, current_turn: 'black', move_history: [{ notation: 'e4' }], game_status: 'checkmate' },
        '/api/analyze-game/': { accuracy: 90, mistakes: 0, blunders: 0 }
      });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await playE4();
      await flushPromises();

      expect(calls('/api/analyze-game/').length).toBe(1);
    });
  });

  describe("Puzzles", () => {
    const puzzleRoutes = (solveAnswer) => ({
      '/api/puzzles/daily/': { id: 7, title: 'Test puzzle', fen: '6k1/5ppp/8/8/8/8/5PPP/6KQ w - - 0 1', difficulty: 'easy' },
      '/api/puzzles/7/solution/': { solution: ['e2e4'] },
      '/api/puzzles/7/solve/': solveAnswer,
      '/api/move/': afterWhiteMove
    });
    const startDailyPuzzle = async () => {
      document.getElementById('welcomeDailyPuzzleBtn').click();
      await flushPromises();
    };

    it('sends the moves played to /solve/ once and shows the streak from the answer', async () => {
      mockServer(puzzleRoutes({
        success: true, correct: true, newly_solved: true,
        puzzles_solved: 3, streak: 4, longest_streak: 9, daily_completions: 2
      }));
      await startDailyPuzzle();
      await playE4();

      const solve = calls('/api/puzzles/7/solve/');
      expect(solve.length).toBe(1);
      expect(JSON.parse(solve[0][1].body)).toEqual({ moves: ['e2e4'] });
      const message = document.getElementById('confirmMessage').innerHTML;
      expect(message).toContain('Current Streak: 4');
      expect(message).toContain('Best Streak: 9');
    });

    it('keeps the localStorage streak for a guest', async () => {
      localStorage.removeItem('dailyPuzzleStreak');
      mockServer(puzzleRoutes({ status: 401, body: { error: 'Unauthorized' } }));
      await startDailyPuzzle();
      await playE4();

      expect(calls('/api/puzzles/7/solve/').length).toBe(1);
      expect(document.getElementById('confirmMessage').innerHTML).toContain('Current Streak: 1');
      expect(JSON.parse(localStorage.getItem('dailyPuzzleStreak')).streak).toBe(1);
    });

    it('keeps both clocks hidden, and the next ordinary game shows them again', async () => {
      const whiteClock = document.getElementById('whiteClock');
      const blackClock = document.getElementById('blackClock');
      mockServer(puzzleRoutes({ notJson: true }));
      await startDailyPuzzle();
      expect(whiteClock.style.display).toBe('none');
      expect(blackClock.style.display).toBe('none');

      mockServer({ '/api/new-game/': pvpGame, '/api/state/': pvpGame });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      expect(whiteClock.style.display).toBe('');
      expect(blackClock.style.display).toBe('');
    });

    it('is not ended by the clock', async () => {
      mockServer({ ...puzzleRoutes({ notJson: true }), '/api/state/': { ...aiGame, white_time: 2 } });
      jest.useFakeTimers();
      document.getElementById('welcomeDailyPuzzleBtn').click();
      await jest.advanceTimersByTimeAsync(4000);

      expect(calls('/api/timeout/').length).toBe(0);
      expect(calls('/api/analyze-game/').length).toBe(0);
    });
  });

  describe("Check", () => {
    const whiteChecks = { ...pvpGame, current_turn: 'black', move_history: [{ notation: 'e4' }], game_status: 'check' };
    const square = (r, c) => document.getElementById('board').querySelector(`[data-row="${r}"][data-col="${c}"]`);

    it('keeps the king\'s square marked while the checked player selects and flips', async () => {
      mockServer({ '/api/new-game/': pvpGame, '/api/state/': pvpGame, '/api/move/': whiteChecks });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await playE4();
      expect(square(0, 4).classList.contains('in-check')).toBe(true);

      await onClick(1, 4); // Black picks up a pawn
      expect(square(1, 4).classList.contains('selected')).toBe(true);
      expect(square(0, 4).classList.contains('in-check')).toBe(true);

      await onClick(1, 4); // and puts it down again
      expect(square(0, 4).classList.contains('in-check')).toBe(true);

      const flipBtn = document.getElementById('flipBtn');
      flipBtn.onclick(); // every square is rebuilt
      try {
        expect(square(0, 4).classList.contains('in-check')).toBe(true);
        expect(document.querySelectorAll('#board .in-check').length).toBe(1);
      } finally {
        flipBtn.onclick();
      }
    });

    it('does not bring the mark back once the check is over', async () => {
      mockServer({ '/api/new-game/': pvpGame, '/api/state/': pvpGame, '/api/move/': whiteChecks });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await playE4();

      highlightCheck();
      refreshHighlights();
      expect(document.querySelectorAll('#board .in-check').length).toBe(0);
    });

    it('a new game starts without the last game\'s mark', async () => {
      mockServer({ '/api/new-game/': pvpGame, '/api/state/': pvpGame, '/api/move/': whiteChecks });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await playE4();
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await onClick(6, 4);
      expect(document.querySelectorAll('#board .in-check').length).toBe(0);
    });
  });

  describe("Pieces that can be picked up", () => {
    const square = (r, c) => document.getElementById('board').querySelector(`[data-row="${r}"][data-col="${c}"]`);
    const playable = (r, c) => square(r, c).querySelector('.piece').classList.contains('playable');

    it('against the engine, only the player\'s own, and never the engine\'s', async () => {
      mockServer({ '/api/move/': afterWhiteMove, '/api/ai-move/': afterAiMove });
      jest.useFakeTimers();
      await startNewGame('ai', 'white', 'easy', null, 10);
      expect(playable(6, 4)).toBe(true);
      expect(playable(1, 4)).toBe(false);

      await playE4(); // the engine is to move now
      expect(playable(1, 4)).toBe(false);
      expect(playable(0, 6)).toBe(false);
      expect(playable(6, 3)).toBe(true); // the player's, for a premove

      await onClick(1, 4); // a click on the engine's pawn picks nothing up
      expect(square(1, 4).classList.contains('selected')).toBe(false);
      expect(document.querySelectorAll('#board .move-dot, #board .capture-ring').length).toBe(0);

      await jest.advanceTimersByTimeAsync(1600);
    });

    it('in a two-player game, the side to move', async () => {
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': pvpGame,
        '/api/move/': { ...pvpGame, current_turn: 'black', move_history: [{ notation: 'e4' }] }
      });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      expect(playable(6, 4)).toBe(true);
      expect(playable(1, 4)).toBe(false);

      await playE4();
      expect(playable(1, 4)).toBe(true);
      expect(playable(6, 3)).toBe(false);
    });
  });

  describe("A new game", () => {
    it('clears the last game\'s result from the status line', async () => {
      mockServer({
        '/api/new-game/': pvpGame,
        '/api/state/': pvpGame,
        '/api/move/': { ...pvpGame, current_turn: 'black', move_history: [{ notation: 'e4' }], game_status: 'checkmate' }
      });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      await playE4();
      expect(statusLine()).toContain('Checkmate');

      await startNewGame('pvp', 'white', 'medium', null, 10);
      expect(statusLine()).toBe('Game started');
    });

    it('writes whose turn it is into the badge\'s own label and keeps that element', async () => {
      const badge = document.getElementById('turnBadge');
      const label = document.getElementById('turnBadgeText');

      mockServer({});
      await startNewGame('ai', 'white', 'easy', null, 10);
      expect(document.getElementById('turnBadgeText')).toBe(label);
      expect(badge.contains(label)).toBe(true);
      expect(label.textContent).toBe('Your Turn');
      expect(badge.textContent).toBe('Your Turn'); // nothing of the template's text is left beside it

      mockServer({ '/api/new-game/': pvpGame, '/api/state/': { ...pvpGame, white_name: 'Asha' } });
      await startNewGame('pvp', 'white', 'medium', null, 10);
      expect(badge.contains(label)).toBe(true);
      expect(badge.textContent).toBe("ASHA's Turn");
    });

    it('marks the engine\'s level for the stylesheet and writes no colour of its own', async () => {
      mockServer({});
      await startNewGame('ai', 'white', 'easy', null, 10);
      await flushPromises();

      const level = document.querySelector('#blackNameLabel span');
      expect(level.textContent).toBe('EASY');
      expect(level.dataset.difficulty).toBe('easy');
      expect(level.hasAttribute('style')).toBe(false);
    });

    it('choosing a side marks it with a class and no inline colour', () => {
      const choice = document.querySelector('#pveOptions .color-choice');
      choice.classList.remove('active');
      choice.onclick();
      expect(choice.classList.contains('active')).toBe(true);
      expect(choice.hasAttribute('style')).toBe(false);
    });
  });

  describe("Abandoning a rated game", () => {
    it('asks first, starts nothing on Cancel, and starts the new game on Yes', async () => {
      const sixMoves = ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5'].map(notation => ({ notation }));
      mockServer({
        '/api/new-game/': { ...aiGame, rated: true },
        '/api/state/': { ...aiGame, rated: true, move_history: sixMoves }
      });
      await startNewGame('ai', 'white', 'easy', null, 10);
      global.fetch.mockClear();

      let started = startNewGame('pvp', 'white', 'medium', null, 10);
      await flushPromises();
      expect(document.getElementById('confirmOverlay').classList.contains('active')).toBe(true);
      expect(document.getElementById('confirmMessage').innerHTML).toContain('counts it as a loss');
      // The question's tone is an attribute; the title and the overlay get no inline styles.
      expect(document.getElementById('confirmTitle').dataset.tone).toBe('danger');
      expect(document.getElementById('confirmTitle').hasAttribute('style')).toBe(false);
      expect(document.getElementById('confirmOverlay').hasAttribute('style')).toBe(false);
      document.getElementById('confirmNoBtn').click();
      expect(await started).toBe(false);
      expect(calls('/api/new-game/').length).toBe(0);

      // The next game is an ordinary one, so later tests are not asked anything.
      mockServer({ '/api/new-game/': pvpGame, '/api/state/': pvpGame });
      started = startNewGame('pvp', 'white', 'medium', null, 10);
      await flushPromises();
      document.getElementById('confirmYesBtn').click();
      expect(await started).toBe(true);
      expect(calls('/api/new-game/').length).toBe(1);
    });
  });
});

// ---------------------------------------------------------------------------
// A first visit: the tour and the start countdown. The script decides once per
// page load whether the tour is due, so each test here loads its own copy of
// it. This block stays last: the copies share the document with the one above.
// ---------------------------------------------------------------------------
describe("First visit", () => {
  const TOUR_SEEN = 'checkoraTourSeen';
  const hadScrollIntoView = 'scrollIntoView' in Element.prototype;
  const originalScrollIntoView = Element.prototype.scrollIntoView;
  let welcome, tour, countdown, firstTarget;

  // The page as it is when it loads: setup screen up, no tour, no countdown.
  function loadPage(tourSeen) {
    if (tourSeen) localStorage.setItem(TOUR_SEEN, 'true');
    else localStorage.removeItem(TOUR_SEEN);
    welcome.classList.add('active');
    tour.style.display = 'none';
    countdown.classList.remove('active');
    let page;
    jest.isolateModules(() => {
      page = require("./game/static/game/js/board");
    });
    return page;
  }

  // What the setup screen's buttons do: start the game, then get out of the way.
  async function startFromSetup(page) {
    await page.startNewGame('pvp', 'white', 'medium', null, 10);
    welcome.classList.remove('active');
  }

  beforeAll(() => {
    document.body.insertAdjacentHTML('beforeend', `
      <div id="countdownOverlay"><span id="countdownNumber"></span></div>
      <div id="tourOverlay" style="display: none;">
        <div id="tourTooltip" tabindex="-1">
          <p id="tourStepLabel"></p>
          <p id="tourStepText"></p>
          <button id="tourSkipBtn"></button>
          <button id="tourNextBtn"></button>
        </div>
      </div>
    `);
    welcome = document.getElementById('welcomeOverlay');
    tour = document.getElementById('tourOverlay');
    countdown = document.getElementById('countdownOverlay');
    firstTarget = document.getElementById('manualMoveInput');
    Element.prototype.scrollIntoView = jest.fn(); // jsdom has no layout to scroll
  });

  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    delete firstTarget.getBoundingClientRect;
  });

  afterAll(() => {
    if (hadScrollIntoView) Element.prototype.scrollIntoView = originalScrollIntoView;
    else delete Element.prototype.scrollIntoView;
    localStorage.removeItem(TOUR_SEEN);
  });

  it('a returning player gets the countdown straight away', async () => {
    const page = loadPage(true);
    await startFromSetup(page);

    expect(countdown.classList.contains('active')).toBe(true);
    expect(document.getElementById('countdownNumber').textContent).toBe('3');
    await jest.advanceTimersByTimeAsync(4000);
    expect(countdown.classList.contains('active')).toBe(false);
    expect(tour.style.display).toBe('none');
  });

  it('a tour with nothing it can show is not marked as seen, and the countdown still starts', async () => {
    const page = loadPage(false);
    await startFromSetup(page);
    expect(countdown.classList.contains('active')).toBe(false); // held for the tour

    // Nothing has a size in jsdom, so every step is skipped and the tour closes itself.
    await jest.advanceTimersByTimeAsync(500);
    expect(tour.style.display).toBe('none');
    expect(localStorage.getItem(TOUR_SEEN)).toBeNull();
    expect(countdown.classList.contains('active')).toBe(true);

    await jest.advanceTimersByTimeAsync(4000);
    expect(countdown.classList.contains('active')).toBe(false);
  });

  it('the countdown waits while the tour is read and starts when it is closed', async () => {
    const page = loadPage(false);
    firstTarget.getBoundingClientRect = () => ({ width: 200, height: 30, top: 10, left: 10, right: 210, bottom: 40 });
    await startFromSetup(page);

    await jest.advanceTimersByTimeAsync(500); // the tour opens 0.4 s after the setup screen closes
    expect(tour.style.display).toBe('block');
    expect(firstTarget.classList.contains('tour-spotlight')).toBe(true);
    expect(document.getElementById('tourStepLabel').textContent).toBe('Step 1 of 4');
    expect(countdown.classList.contains('active')).toBe(false);

    await jest.advanceTimersByTimeAsync(20000); // however long the reading takes
    expect(countdown.classList.contains('active')).toBe(false);

    document.getElementById('tourSkipBtn').click();
    expect(tour.style.display).toBe('none');
    expect(firstTarget.classList.contains('tour-spotlight')).toBe(false);
    expect(localStorage.getItem(TOUR_SEEN)).toBe('true');
    expect(countdown.classList.contains('active')).toBe(true);
    expect(document.getElementById('countdownNumber').textContent).toBe('3');

    await jest.advanceTimersByTimeAsync(4000);
    expect(countdown.classList.contains('active')).toBe(false);
  });
});
