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
`;
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

const { pColor, getSquareLabel, formatTime, getPlayerScore, validateMoveWithStockfish, clearEvaluationCache } = require("./game/static/game/js/board");

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