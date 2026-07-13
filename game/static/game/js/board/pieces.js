/**
 * board/pieces.js — Piece constants, image map, piece style
 *
 * Extracted from board.js lines 7–55 (MATERIAL_VALUES, PIECE_IMG, etc.)
 */
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  var MATERIAL_VALUES = {
    p: 1, n: 3, b: 3, r: 5, q: 9, k: 0
  };

  var VALID_PIECE_STYLES = ['neo', 'classic', 'alpha', 'cburnett'];
  var PIECE_IMG = {};

  var PIECE_NAMES = {
    'p': 'Pawn', 'r': 'Rook', 'n': 'Knight',
    'b': 'Bishop', 'q': 'Queen', 'k': 'King'
  };

  var DEFAULT_START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

  function buildPieceImg(style) {
    var targetStyle = VALID_PIECE_STYLES.includes(style) ? style : 'neo';
    for (var ci = 0; ci < 2; ci++) {
      var c = ['w', 'b'][ci];
      for (var ti = 0; ti < 6; ti++) {
        var t = ['k', 'q', 'r', 'b', 'n', 'p'][ti];
        PIECE_IMG[c + t] = 'https://images.chesscomfiles.com/chess-themes/pieces/' + targetStyle + '/150/' + c + t + '.png';
      }
    }
  }

  // Initialize piece style on load
  if (typeof localStorage !== 'undefined') {
    buildPieceImg(localStorage.getItem('pieceStyle'));
  } else {
    buildPieceImg(null);
  }

  function updatePieceStyle(style) {
    buildPieceImg(style);
    // Re-draw board pieces
    if (typeof CB.syncPieces === 'function') {
      CB.syncPieces();
    }
    // Re-draw captured list pieces dynamically
    if (typeof document !== 'undefined') {
      document.querySelectorAll('.captured-img').forEach(function (img) {
        var key = img.dataset.piece;
        if (key && PIECE_IMG[key]) {
          img.src = PIECE_IMG[key];
        }
      });
    }
  }

  // Attach to namespace
  CB.MATERIAL_VALUES = MATERIAL_VALUES;
  CB.VALID_PIECE_STYLES = VALID_PIECE_STYLES;
  CB.PIECE_IMG = PIECE_IMG;
  CB.PIECE_NAMES = PIECE_NAMES;
  CB.DEFAULT_START_FEN = DEFAULT_START_FEN;
  CB.buildPieceImg = buildPieceImg;
  CB.updatePieceStyle = updatePieceStyle;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      MATERIAL_VALUES: MATERIAL_VALUES,
      VALID_PIECE_STYLES: VALID_PIECE_STYLES,
      PIECE_IMG: PIECE_IMG,
      PIECE_NAMES: PIECE_NAMES,
      DEFAULT_START_FEN: DEFAULT_START_FEN,
      buildPieceImg: buildPieceImg,
      updatePieceStyle: updatePieceStyle
    };
  }
})();
