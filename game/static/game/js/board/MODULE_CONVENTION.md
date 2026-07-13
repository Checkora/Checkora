# Board Module Convention

## Namespace

All board modules share a single global namespace: `window.CB` (browser) or
`global.CB` (Node/Jest).  The `_ns.js` bootstrap creates it; every other file
reads from and writes to it.

## File Template

```js
// board/example.js
(function () {
  'use strict';
  var CB = (typeof window !== 'undefined' ? window : global).CB;

  // --- module body ---
  function myHelper() { /* ... */ }

  // --- module tail ---
  CB.myHelper = myHelper;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { myHelper: myHelper };
  }
})();
```

### Rules

1. **Wrap in an IIFE** — no stray globals.
2. **Resolve collaborators via `CB`** — e.g. `CB.S.board` for state,
   `CB.DOM.boardEl` for DOM refs.  Never create a second source of truth.
3. **Attach exports to `CB`** at the bottom of the IIFE so browser callers
   can reach them immediately.
4. **Also set `module.exports`** with the same names so Node/Jest `require()`
   picks them up.
5. **State lives in `CB.S`** (the mutable state object from `state.js`).
   Always mutate `CB.S.xxx`, never shadow with a local `let`.

## Load Order (browser)

`_ns.js` → `state.js` → `dom.js` → `sound.js` → `api.js` → `utils.js` →
`pieces.js` → `render.js` → `clocks.js` → `engine.js` → `promo.js` →
`endgame.js` → `dialogs.js` → `puzzle.js` → `moves.js` → `lifecycle.js` →
`replay.js` → `dragdrop.js` → `textinput.js` → `events.js`

## Node/Jest

`_barrel.js` requires every module in the same order and re-exports the 19+
names that `board.test.js` relies on.
