/**
 * board/dom.js — DOM element references
 *
 * Extracted from board.js lines 664–749.  Every getElementById / querySelector
 * that was a top-level `const` in the old IIFE lives here as CB.DOM.xxx.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  // ponytail: In Node/Jest the DOM is set up before require(), so
  // document.getElementById works fine here.  In browser, this script
  // runs after the HTML body is parsed (script tag at bottom of body).
  var d = typeof document !== 'undefined' ? document : null;
  var byId = function (id) { return d ? d.getElementById(id) : null; };
  var byQS = function (sel) { return d ? d.querySelector(sel) : null; };

  var DOM = {
    shareModal:        byId('shareModal'),
    rulebookModal:     byId('rulebookModal'),
    boardEl:           byId('board'),
    countdownOverlay:  byId('countdownOverlay'),
    countdownNumberEl: byId('countdownNumber'),
    turnEl:            byId('turnBadge'),
    statusEl:          byId('statusBar'),
    movesEl:           byId('movesList'),
    wCapEl:            byId('whiteCaptured'),
    bCapEl:            byId('blackCaptured'),
    pauseBtn:          byId('pauseBtn'),
    flipBtn:           byId('flipBtn'),
    promoOverlay:      byId('promoOverlay'),
    promoChoices:      byId('promoChoices'),
    modeBadge:         byId('modeBadge'),
    autoFlipBtn:       byId('autoFlipBtn'),
    flipControls:      byId('flipControls'),
    copyFenBtn:        byId('copyFenBtn'),
    copyPgnBtn:        byId('copyPgnBtn'),
    muteBtn:           byId('muteBtn'),

    welcomeOverlay:       byId('welcomeOverlay'),
    welcomeResumeBtn:     byId('welcomeResumeBtn'),
    welcomePvPBtn:        byId('welcomePvPBtn'),
    welcomeAIBtn:         byId('welcomeAIBtn'),
    welcomeDailyPuzzleBtn: byId('welcomeDailyPuzzleBtn'),
    welcomeFenInput:      byId('welcomeFenInput'),
    welcomeFenError:      byId('welcomeFenError'),

    modeSelection:  byId('modeSelection'),
    pveOptions:     byId('pveOptions'),
    startAIBtn:     byId('startAIBtn'),
    backToModes:    byId('backToModes'),
    gameLayout:     byQS('.game-layout'),
    nameInputs:     byId('nameInputs'),

    confirmOverlay:  byId('confirmOverlay'),
    confirmTitle:    byId('confirmTitle'),
    confirmMessage:  byId('confirmMessage'),
    confirmYesBtn:   byId('confirmYesBtn'),
    confirmNoBtn:    byId('confirmNoBtn'),

    newPvPBtn:        byId('newPvPBtn'),
    newAIBtn:         byId('newAIBtn'),
    dailyPuzzleBtn:   byId('dailyPuzzleBtn'),
    restartPuzzleBtn: byId('restartPuzzleBtn'),
    hintPuzzleBtn:    byId('hintPuzzleBtn'),
    newFenBtn:        byId('newFenBtn'),

    fenOverlay:   byId('fenOverlay'),
    fenInput:     byId('fenInput'),
    fenError:     byId('fenError'),
    fenStartBtn:  byId('fenStartBtn'),
    fenCancelBtn: byId('fenCancelBtn'),

    gameOverOverlay:  byId('gameOverOverlay'),
    gameOverTitle:    byId('gameOverTitle'),
    gameOverMessage:  byId('gameOverMessage'),
    gameOverStartBtn: byId('gameOverStartBtn'),
    gameOverExitBtn:  byId('gameOverExitBtn'),
    gameOverPvPBtn:   byId('gameOverPvPBtn'),
    gameOverAIBtn:    byId('gameOverAIBtn'),

    replayControls:  byId('replayControls'),
    firstReplayBtn:  byId('firstReplayBtn'),
    prevReplayBtn:   byId('prevReplayBtn'),
    playReplayBtn:   byId('playReplayBtn'),
    nextReplayBtn:   byId('nextReplayBtn'),
    lastReplayBtn:   byId('lastReplayBtn'),
    replayGameBtn:   byId('replayGameBtn'),

    resignBtn:      byId('resignBtn'),
    drawBtn:        byId('drawBtn'),
    drawOverlay:    byId('drawOverlay'),
    drawMessage:    byId('drawMessage'),
    drawAcceptBtn:  byId('drawAcceptBtn'),
    drawDeclineBtn: byId('drawDeclineBtn'),

    whiteNameLabel:    byId('whiteNameLabel'),
    blackNameLabel:    byId('blackNameLabel'),
    whiteYouTag:       byId('whiteYouTag'),
    blackYouTag:       byId('blackYouTag'),
    whiteCapturedName: byId('whiteCapturedName'),
    blackCapturedName: byId('blackCapturedName'),
    turnBadgeText:     byId('turnBadgeText'),
    a11yAnnouncer:     byId('a11y-announcer'),
  };

  function initDOM() {
    if (typeof document === 'undefined') return;
    d = document;
    DOM.shareModal = byId('shareModal');
    DOM.rulebookModal = byId('rulebookModal');
    DOM.boardEl = byId('board');
    DOM.countdownOverlay = byId('countdownOverlay');
    DOM.countdownNumberEl = byId('countdownNumber');
    DOM.turnEl = byId('turnBadge');
    DOM.statusEl = byId('statusBar');
    DOM.movesEl = byId('movesList');
    DOM.wCapEl = byId('whiteCaptured');
    DOM.bCapEl = byId('blackCaptured');
    DOM.pauseBtn = byId('pauseBtn');
    DOM.flipBtn = byId('flipBtn');
    DOM.promoOverlay = byId('promoOverlay');
    DOM.promoChoices = byId('promoChoices');
    DOM.modeBadge = byId('modeBadge');
    DOM.autoFlipBtn = byId('autoFlipBtn');
    DOM.flipControls = byId('flipControls');
    DOM.copyFenBtn = byId('copyFenBtn');
    DOM.copyPgnBtn = byId('copyPgnBtn');
    DOM.muteBtn = byId('muteBtn');
    DOM.welcomeOverlay = byId('welcomeOverlay');
    DOM.welcomeResumeBtn = byId('welcomeResumeBtn');
    DOM.welcomePvPBtn = byId('welcomePvPBtn');
    DOM.welcomeAIBtn = byId('welcomeAIBtn');
    DOM.welcomeDailyPuzzleBtn = byId('welcomeDailyPuzzleBtn');
    DOM.welcomeFenInput = byId('welcomeFenInput');
    DOM.welcomeFenError = byId('welcomeFenError');
    DOM.modeSelection = byId('modeSelection');
    DOM.pveOptions = byId('pveOptions');
    DOM.startAIBtn = byId('startAIBtn');
    DOM.backToModes = byId('backToModes');
    DOM.gameLayout = byQS('.game-layout');
    DOM.nameInputs = byId('nameInputs');
    DOM.confirmOverlay = byId('confirmOverlay');
    DOM.confirmTitle = byId('confirmTitle');
    DOM.confirmMessage = byId('confirmMessage');
    DOM.confirmYesBtn = byId('confirmYesBtn');
    DOM.confirmNoBtn = byId('confirmNoBtn');
    DOM.newPvPBtn = byId('newPvPBtn');
    DOM.newAIBtn = byId('newAIBtn');
    DOM.dailyPuzzleBtn = byId('dailyPuzzleBtn');
    DOM.restartPuzzleBtn = byId('restartPuzzleBtn');
    DOM.hintPuzzleBtn = byId('hintPuzzleBtn');
    DOM.newFenBtn = byId('newFenBtn');
    DOM.fenOverlay = byId('fenOverlay');
    DOM.fenInput = byId('fenInput');
    DOM.fenError = byId('fenError');
    DOM.fenStartBtn = byId('fenStartBtn');
    DOM.fenCancelBtn = byId('fenCancelBtn');
    DOM.gameOverOverlay = byId('gameOverOverlay');
    DOM.gameOverTitle = byId('gameOverTitle');
    DOM.gameOverMessage = byId('gameOverMessage');
    DOM.gameOverStartBtn = byId('gameOverStartBtn');
    DOM.gameOverExitBtn = byId('gameOverExitBtn');
    DOM.gameOverPvPBtn = byId('gameOverPvPBtn');
    DOM.gameOverAIBtn = byId('gameOverAIBtn');
    DOM.replayControls = byId('replayControls');
    DOM.firstReplayBtn = byId('firstReplayBtn');
    DOM.prevReplayBtn = byId('prevReplayBtn');
    DOM.playReplayBtn = byId('playReplayBtn');
    DOM.nextReplayBtn = byId('nextReplayBtn');
    DOM.lastReplayBtn = byId('lastReplayBtn');
    DOM.replayGameBtn = byId('replayGameBtn');
    DOM.resignBtn = byId('resignBtn');
    DOM.drawBtn = byId('drawBtn');
    DOM.drawOverlay = byId('drawOverlay');
    DOM.drawMessage = byId('drawMessage');
    DOM.drawAcceptBtn = byId('drawAcceptBtn');
    DOM.drawDeclineBtn = byId('drawDeclineBtn');
    DOM.whiteNameLabel = byId('whiteNameLabel');
    DOM.blackNameLabel = byId('blackNameLabel');
    DOM.whiteYouTag = byId('whiteYouTag');
    DOM.blackYouTag = byId('blackYouTag');
    DOM.whiteCapturedName = byId('whiteCapturedName');
    DOM.blackCapturedName = byId('blackCapturedName');
    DOM.turnBadgeText = byId('turnBadgeText');
    DOM.a11yAnnouncer = byId('a11y-announcer');
  }

  CB.DOM = DOM;
  CB.initDOM = initDOM;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DOM: DOM, initDOM: initDOM };
  }
})();
