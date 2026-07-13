/**
 * board/_ns.js — Namespace bootstrap (load first)
 *
 * Creates the shared window.CB namespace used by every board/* module.
 * Under Node/Jest the namespace lives on `global.CB` instead.
 *
 * Convention: each module does
 *   const CB = (typeof window !== 'undefined' ? window : global).CB;
 * at the top, then attaches its exports to CB at the bottom.
 */
(function () {
  'use strict';
  var root = typeof window !== 'undefined' ? window : global;
  if (!root.CB) root.CB = {};
})();
