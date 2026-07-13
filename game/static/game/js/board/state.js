/**
 * board/state.js — Mutable game state
 *
 * One object (CB.S) holds every piece of mutable state that was previously
 * a closure-scoped `let` inside the board.js IIFE.  All modules read/write
 * CB.S.xxx so mutations are visible everywhere.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  var S = {
    // --- Core board state ---
    board: [],
    turn: 'white',
    selected: null,
    hints: [],
    lastMove: null,
    premoveQueue: [],
    lastPremoveQueueStr: '',
    highlightedSquare: null,

    // --- Mouse drag state ---
    dragging: false,
    dragSrc: null,

    // --- Touch drag state ---
    touchStartPos: null,
    activeTouchPieceClone: null,
    touchDragSrc: null,
    touchTapSquare: null,
    touchDragging: false,
    touchOffset: { x: 0, y: 0 },

    // --- Clock / timer state ---
    whiteTime: 0,
    blackTime: 0,
    selectedMins: 10,
    selectedIncrement: 0,
    paused: false,
    timerInterval: null,
    countdownInterval: null,

    // --- Promotion ---
    pendingPromo: null,

    // --- Blindfold ---
    blindfoldMode: false,
    illegalMoveCount: 0,

    // --- Low-time alerts ---
    whiteAlertFired: false,
    blackAlertFired: false,

    // --- Timing ---
    gameStartTime: null,

    // --- Game mode ---
    gameMode: 'pvp',
    playerColor: 'white',
    flipped: false,
    autoFlip: (typeof localStorage !== 'undefined' && localStorage.getItem('autoFlip') === 'true'),
    currentDifficulty: 'medium',
    currentWhiteName: 'White',
    currentBlackName: 'Black',

    // --- Sound ---
    soundEnabled: true, // ponytail: overwritten in sound.js init from localStorage

    // --- Puzzle ---
    dailyPuzzleMode: false,
    currentPuzzle: null,
    puzzleMoveIndex: 0,
    currentPuzzleFen: null,
    puzzleAnalyzing: false,
    stockfishWorker: null,
    hintLevel: 0,
    expectedMoveEval: null,
    evaluationCache: {},

    // --- Game flow ---
    gameOver: false,
    aiThinking: false,
    isMoving: false,
    isSanSubmitting: false,
    aiRequestSeq: 0,
    analysisRequestSeq: 0,
    liveFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    gameFens: [],
    stepperIndex: 0,
    viewingPastState: false,

    // --- Replay ---
    replayMode: false,
    replayMoves: [],
    rawAnalysisMoves: [],
    replayIndex: 0,
    replayBoard: null,
    autoReplayInterval: null,
    isAutoReplaying: false,

    // --- Misc timeouts ---
    pgnDownloadTimeout: null,
    fenCopyTimeout: null,
    flashTimeout: null,

    // --- Confirm dialog ---
    confirmCallback: null,

    // --- Welcome / PvE ---
    selectedPveColor: 'white',

    // --- Emote ---
    emoteCooldown: false,

    // --- Leave confirm ---
    leaveConfirmFocusReturn: null,

    // --- Theme modal ---
    themeModalFocusReturn: null,

    // --- Resize ---
    resizeTimeout: undefined,
  };

  CB.S = S;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { S: S };
  }
})();
