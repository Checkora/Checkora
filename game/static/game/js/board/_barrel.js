/**
 * board/_barrel.js — Aggregator module for Node.js / Jest testing and unified access
 *
 * Requires all extracted board modules in dependency order and re-exports
 * them as a single module matching the previous board.js exports interface.
 */
(function () {
  'use strict';

  if (typeof module !== 'undefined' && module.exports) {
    require('./_ns');
    const stateMod = require('./state');
    const domMod = require('./dom');
    
    var CB = (typeof window !== 'undefined' ? window : global).CB;
    if (CB.initDOM) CB.initDOM();

    require('./sound');
    require('./api');
    require('./utils');
    require('./pieces');
    require('./render');
    require('./clocks');
    require('./engine');
    require('./promo');
    require('./endgame');
    require('./dialogs');
    require('./puzzle');
    require('./moves');
    require('./lifecycle');
    require('./replay');
    require('./dragdrop');
    require('./textinput');
    require('./events');

    if (CB.initGame) CB.initGame();

    // Export the exact interface expected by board.test.js and full CB object
    module.exports = {
      ...CB,
      S: CB.S,
      DOM: CB.DOM,
      CB: CB,
      pColor: CB.pColor,
      getSquareLabel: CB.getSquareLabel,
      formatTime: CB.formatTime,
      getPlayerScore: CB.getPlayerScore,
      validateMoveWithStockfish: CB.validateMoveWithStockfish,
      clearEvaluationCache: CB.clearEvaluationCache,
      onClick: CB.onClick,
      onDragStart: CB.onDragStart,
      onDrop: CB.onDrop,
      showPromoModal: CB.showPromoModal,
      hidePromoModal: CB.hidePromoModal,
      onPromoChoice: CB.onPromoChoice,
      toggleSquareHighlight: CB.toggleSquareHighlight,
      refreshHighlights: CB.refreshHighlights,
      highlightCheck: CB.highlightCheck,
      startNewGame: CB.startNewGame,
      squareLabelToRowCol: CB.squareLabelToRowCol,
      computeLegalMovesClient: CB.computeLegalMovesClient,
      updatePieceStyle: CB.updatePieceStyle,
      PIECE_IMG: CB.PIECE_IMG,
      VALID_PIECE_STYLES: CB.VALID_PIECE_STYLES
    };
  } else {
    // In browser, this file does nothing if loaded since individual script tags attach directly to window.CB
    var CB = (typeof window !== 'undefined' ? window : global).CB;
  }
})();
