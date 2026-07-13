/**
 * game/static/game/js/board.js — Deprecated Monolithic Entry Point
 *
 * NOTE: The monolithic board.js has been modularized into game/static/game/js/board/
 * according to our dual-mode module convention (see game/static/game/js/board/MODULE_CONVENTION.md).
 *
 * For Node/Jest tests, requiring this file delegates directly to ./board/_barrel.js.
 * For browser environments, please ensure your templates/HTML load the individual
 * script modules inside /board/ in dependency order (as done in game/templates/game/board.html).
 */
(function () {
  'use strict';
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = require('./board/_barrel.js');
  } else if (typeof console !== 'undefined' && console.warn) {
    console.warn('board.js is deprecated. Please include the individual modules from static/game/js/board/ in your HTML templates.');
  }
})();
