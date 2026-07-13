/**
 * board/dom.js — DOM element references
 *
 * Extracted from board.js lines 664–749.  Every getElementById / querySelector
 * that was a top-level `const` in the old IIFE lives here as CB.DOM.xxx.
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  var d = typeof document !== 'undefined' ? document : null;
  var byId = function (id) { return d ? d.getElementById(id) : null; };
  var byQS = function (sel) { return d ? d.querySelector(sel) : null; };

  var DOM = {};

  function initDOM() {
    d = typeof document !== 'undefined' ? document : null;
    Object.assign(DOM, {
      shareModal: byId('shareModal'),
      rulebookModal: byId('rulebookModal'),
      boardEl: byId('board'),
      countdownOverlay: byId('countdownOverlay'),
      countdownNumberEl: byId('countdownNumber'),
      turnEl: byId('turnBadge'),
      statusEl: byId('statusBar'),
      movesEl: byId('movesList'),
      wCapEl: byId('whiteCaptured'),
      bCapEl: byId('blackCaptured'),
      pauseBtn: byId('pauseBtn'),
      flipBtn: byId('flipBtn'),
      promoOverlay: byId('promoOverlay'),
      promoChoices: byId('promoChoices'),
      modeBadge: byId('modeBadge'),
      autoFlipBtn: byId('autoFlipBtn'),
      flipControls: byId('flipControls'),
      copyFenBtn: byId('copyFenBtn'),
      copyPgnBtn: byId('copyPgnBtn'),
      muteBtn: byId('muteBtn'),

      welcomeOverlay: byId('welcomeOverlay'),
      welcomeResumeBtn: byId('welcomeResumeBtn'),
      welcomePvPBtn: byId('welcomePvPBtn'),
      welcomeAIBtn: byId('welcomeAIBtn'),
      welcomeDailyPuzzleBtn: byId('welcomeDailyPuzzleBtn'),
      welcomeFenInput: byId('welcomeFenInput'),
      welcomeFenError: byId('welcomeFenError'),

      modeSelection: byId('modeSelection'),
      pveOptions: byId('pveOptions'),
      startAIBtn: byId('startAIBtn'),
      backToModes: byId('backToModes'),
      gameLayout: byQS('.game-layout'),
      nameInputs: byId('nameInputs'),

      confirmOverlay: byId('confirmOverlay'),
      confirmTitle: byId('confirmTitle'),
      confirmMessage: byId('confirmMessage'),
      confirmYesBtn: byId('confirmYesBtn'),
      confirmNoBtn: byId('confirmNoBtn'),

      newPvPBtn: byId('newPvPBtn'),
      newAIBtn: byId('newAIBtn'),
      dailyPuzzleBtn: byId('dailyPuzzleBtn'),
      restartPuzzleBtn: byId('restartPuzzleBtn'),
      hintPuzzleBtn: byId('hintPuzzleBtn'),
      newFenBtn: byId('newFenBtn'),

      fenOverlay: byId('fenOverlay'),
      fenInput: byId('fenInput'),
      fenError: byId('fenError'),
      fenStartBtn: byId('fenStartBtn'),
      fenCancelBtn: byId('fenCancelBtn'),

      gameOverOverlay: byId('gameOverOverlay'),
      gameOverTitle: byId('gameOverTitle'),
      gameOverMessage: byId('gameOverMessage'),
      gameOverStartBtn: byId('gameOverStartBtn'),
      gameOverExitBtn: byId('gameOverExitBtn'),
      gameOverPvPBtn: byId('gameOverPvPBtn'),
      gameOverAIBtn: byId('gameOverAIBtn'),

      replayControls: byId('replayControls'),
      firstReplayBtn: byId('firstReplayBtn'),
      prevReplayBtn: byId('prevReplayBtn'),
      playReplayBtn: byId('playReplayBtn'),
      nextReplayBtn: byId('nextReplayBtn'),
      lastReplayBtn: byId('lastReplayBtn'),
      replayGameBtn: byId('replayGameBtn'),

      resignBtn: byId('resignBtn'),
      drawBtn: byId('drawBtn'),
      drawOverlay: byId('drawOverlay'),
      drawMessage: byId('drawMessage'),
      drawAcceptBtn: byId('drawAcceptBtn'),
      drawDeclineBtn: byId('drawDeclineBtn'),

      whiteNameLabel: byId('whiteNameLabel'),
      blackNameLabel: byId('blackNameLabel'),
      whiteYouTag: byId('whiteYouTag'),
      blackYouTag: byId('blackYouTag'),
      whiteCapturedName: byId('whiteCapturedName'),
      blackCapturedName: byId('blackCapturedName'),
      turnBadgeText: byId('turnBadgeText'),
      a11yAnnouncer: byId('a11y-announcer'),
    });
  }

  initDOM();

  CB.DOM = DOM;
  CB.initDOM = initDOM;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DOM: DOM, initDOM: initDOM };
  }
})();
