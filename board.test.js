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
`;

const { pColor, getSquareLabel, formatTime } = require("./game/static/game/js/board");

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

const { updateTimerState } = require("./game/static/game/js/board");

describe("updateTimerState", () => {
  test("decrements exactly 1 second when delta is 1000ms", () => {
    const result = updateTimerState(10, 0, 1000);
    expect(result.newSeconds).toBe(9);
    expect(result.newAccumulator).toBe(0);
  });

  test("does not decrement if delta is 500ms, accumulates time", () => {
    const result = updateTimerState(10, 0, 500);
    expect(result.newSeconds).toBe(10);
    expect(result.newAccumulator).toBe(500);
  });

  test("accumulates multiple partial deltas into a second", () => {
    let result = updateTimerState(10, 0, 400); // acc=400, sec=10
    result = updateTimerState(result.newSeconds, result.newAccumulator, 400); // acc=800, sec=10
    result = updateTimerState(result.newSeconds, result.newAccumulator, 300); // acc=1100 -> sec=9, acc=100
    
    expect(result.newSeconds).toBe(9);
    expect(result.newAccumulator).toBe(100);
  });

  test("handles large time jump correctly (e.g. inactive tab for 5.2 seconds)", () => {
    const result = updateTimerState(10, 0, 5200);
    expect(result.newSeconds).toBe(5);
    expect(result.newAccumulator).toBe(200);
  });

  test("does not decrement below zero", () => {
    const result = updateTimerState(2, 0, 5000);
    expect(result.newSeconds).toBe(0);
    expect(result.newAccumulator).toBe(0);
  });
});