# Frontend JavaScript Module Guide

## Overview

Checkora uses JavaScript modules to power gameplay, lessons, puzzles, opening training, authentication, UI interactions, and real-time chess features.

All frontend scripts are located in:

```text
game/static/game/js/
```

---

# JavaScript Module Directory

| File                  | Purpose                             |
| --------------------- | ----------------------------------- |
| auth.js               | Authentication related interactions |
| board.js              | Main chess board logic and gameplay |
| dropdown.js           | Navigation dropdown handling        |
| lesson_board.js       | Lesson board rendering              |
| lesson_coordinates.js | Coordinate helpers for lessons      |
| lesson_demo.js        | Interactive lesson demonstrations   |
| lesson_practice.js    | Lesson practice sessions            |
| opening_trainer.js    | Opening trainer functionality       |
| roadmap_connectors.js | Lesson roadmap visual connections   |
| stockfish.js          | Chess engine integration            |
| theme.js              | Theme switching and preferences     |
| toast.js              | Notification and toast messages     |

---

# Core Modules

## board/ Directory & board.js

The main chessboard logic (`board.js`) has been modularized into focused, single-responsibility modules inside `game/static/game/js/board/`.

### Modular Architecture (`/board/`)
All board modules follow our **dual-mode module convention**: they attach to `window.CB` in the browser and use `module.exports` under Node.js / Jest.

* `_ns.js` — Global `window.CB` namespace setup.
* `state.js` — Centralized mutable game state (`CB.S`).
* `dom.js` — Cached DOM references (`CB.DOM`) and query helpers.
* `sound.js` — Audio and sound effects (`CB.sounds`, `playSound`).
* `api.js` — CSRF tokens and HTTP API wrappers (`get`, `post`, `handleReconnect`).
* `utils.js` — Pure mathematical and board helper utilities.
* `pieces.js` — Chess piece styles and image constants.
* `render.js` — DOM rendering (`parseBoard`, `buildBoard`, status and badge updates).
* `clocks.js` — Game timers, clocks, and time control pickers.
* `engine.js` — Stockfish client-side evaluation, move validation, and AI logic.
* `promo.js` — Pawn promotion dialogs and choices.
* `endgame.js` — Game over conditions, celebrations (confetti/sparkles), and session statistics.
* `dialogs.js` — Confirmation, side-selection, and leave-confirmation modals.
* `puzzle.js` — Daily puzzles, streaks, and puzzle hints.
* `moves.js` — Core move execution (`tryMove`, `executeMove`) and click/drop handlers.
* `lifecycle.js` — Game lifecycle (`startNewGame`, `loadGame`, `pauseGame`, `resumeGame`).
* `replay.js` — Game history navigation and stepper controls.
* `dragdrop.js` — Mouse and mobile touch drag-and-drop interactions.
* `textinput.js` — Standard Algebraic Notation (SAN), manual move inputs, FEN loading, and PGN export.
* `events.js` — Global keyboard shortcuts, UI button handlers, and welcome screen setup.
* `_barrel.js` — Aggregator entrypoint for Node.js / Jest testing (`require('./board/_barrel.js')`).

### Deprecated Entrypoint
`board.js` now acts as a lightweight deprecation and forwarding wrapper:
* In Node/Jest environments, requiring `board.js` delegates to `_barrel.js`.
* In browser environments, templates directly include the `/board/*.js` scripts in dependency order (see `game/templates/game/board.html`).

### Used By

* Board page (`game/templates/game/board.html`)
* Puzzle pages
* Game analysis features

---

## stockfish.js

Provides chess engine functionality.

### Responsibilities

* Position evaluation
* Move analysis
* Engine calculations

---

## lesson_practice.js

Handles:

* Lesson exercises
* Move validation
* Practice progression

---

## lesson_demo.js

Handles:

* Interactive demonstrations
* Guided lesson walkthroughs

---

## opening_trainer.js

Handles:

* Opening training workflows
* Opening move validation
* Training progress tracking

---

## auth.js

Handles frontend authentication interactions including login, registration, session handling, and authentication-related requests.

---

## lesson_board.js

Provides reusable chessboard rendering functionality specifically for lesson pages and educational content.

---

## lesson_coordinates.js

Manages board coordinate labels and orientation used throughout lesson interfaces.

---

## roadmap_connectors.js

Draws and updates the visual connectors between lesson roadmap nodes, helping users understand lesson progression.

# Event Flow

## Gameplay Flow

## Gameplay Flow

User Move
→ board.js
→ Client-side Validation (Stockfish Worker)
→ WebSocket / Backend Communication
→ Opponent & Game State Update
→ Board Update
→ UI Refresh

## Lesson Flow

Lesson Load
→ Demo / Practice Module
→ Progress Validation
→ Completion Tracking

## Opening Trainer Flow

Opening Load
→ User Move
→ Validation
→ Feedback
→ Progress Update

---

# UI Utilities

## theme.js

* Theme selection
* Theme persistence

## toast.js

* Success notifications
* Error notifications
* User feedback messages

## dropdown.js

* Navigation menu interactions

---

# Contributor Guidelines

## Adding New Modules

* Keep modules focused on a single feature.
* Avoid global variables.
* Reuse existing utilities.
* Follow existing naming conventions.

## Debugging

Useful browser tools:

* Console
* Network tab
* WebSocket inspector

Common issues:

* JavaScript runtime errors
* Failed API requests
* Theme persistence issues
* WebSocket connection failures

---

# Best Practices

* Keep frontend logic modular.
* Document complex interactions.
* Minimize duplicated code.
* Test changes on multiple pages.
* Prefer reusable utilities over page-specific implementations.
