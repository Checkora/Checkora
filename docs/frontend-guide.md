# Frontend JavaScript Module Guide

## Overview

Checkora uses JavaScript modules to power gameplay, lessons, puzzles, opening training, authentication, UI interactions, and real-time chess features.

All frontend scripts are located in:

```text
game/static/game/js/
```

The one exception is three.js, which is vendored in `game/static/game/vendor/three/` and imported by `scene3d.js`.

Pages are built on the base template and the stylesheet described in [design-system.md](design-system.md). `game/templates/game/base.html` loads `theme.js` and `perf.js` in the `<head>` and `toast.js`, `app.js` and `cursor.js` at the end of the body, so those five run on every page that extends it. Every other script is loaded by the page that needs it, through the `scripts` block.

---

# JavaScript Module Directory

| File                  | Purpose                             |
| --------------------- | ----------------------------------- |
| account.js            | Account pages: starts the turning 3D piece beside the form and counts up numbers marked `data-count` |
| app.js                | Shared behaviour on every page: the `tz` time zone cookie, navbar, dropdown menus, dialogs, scroll reveals, tilting cards, password show/hide buttons |
| auth.js               | Sign-in, registration and account settings forms: password toggle, password checklist, submit button state |
| board.js              | The game on the play page: board, moves, clocks, game API calls, puzzles, post-game analysis |
| community.js          | Forum list, leaderboard, achievements, stats and match history: 3D piece beside the title, numbers that count up |
| confetti.js           | Defines `window.triggerConfetti()`, a confetti burst drawn on a canvas |
| cursor.js             | The custom cursor effects and the menu that picks one |
| forum.js              | Tab switching on the forum list, kept in the URL hash |
| landing.js            | Landing page: starts the 3D board, prints its moves, runs the alpha-beta demonstration |
| lesson_coordinates.js | Shows or hides the coordinates on lesson boards |
| lesson_demo.js        | Example positions on a lesson page |
| lesson_practice.js    | The practice board on a lesson page |
| opening_trainer.js    | The trainer board on an opening's page |
| perf.js               | Chooses a performance tier, `high` or `low`, before the first paint: sets `data-perf` on `<html>` and exposes `window.checkoraPerf` to the other scripts |
| play_view.js          | Look of the play page: board theme, 3D view, setup screen, phone layout |
| roadmap_connectors.js | Draws the lines between lessons on the lesson map |
| scene3d.js            | three.js scenes: the landing page board and the single turning piece |
| stockfish.js          | Stockfish compiled to JavaScript and WebAssembly, run by `board.js` as a Web Worker |
| theme.js              | Light and dark theme: applies the saved theme before the first paint and wires the toggle buttons |
| toast.js              | Defines `window.showToast()`, and shows Django messages and `alert()` calls as toasts |
| username-check.js     | Says whether a username is free while it is typed, on the register page and the Google username page |

---

# Core Modules

## board.js

Largest frontend module. It owns the game on the play page and is responsible for:

* Chess board rendering, with the piece set chosen in Settings: `pieces/staunton` (the WebP pictures, and the default) or one of the SVG sets `pieces/classic`, `pieces/wood` and `pieces/outline`
* Move handling by click, drag, keyboard and typed moves, including promotion
* Game state updates through the game API (`/api/state/`, `/api/move/`, `/api/ai-move/`, `/api/new-game/` and the others in [API.md](API.md))
* In an AI game, the request for the engine's move. On easy and medium it first waits a short random moment, so the reply does not land the instant the piece is dropped. Hard and master already spend seconds thinking on the server and get no added wait
* Clocks, pause and resume, and the timeout claim sent to `/api/timeout/`
* Puzzle interactions: the daily puzzle, and a puzzle opened with `?puzzle_id=`
* Post-game analysis from `/api/analyze-game/`
* The first-visit tour, the session score, sounds and keyboard shortcuts

It talks to the server with `fetch` only. POST requests carry the CSRF token read from the hidden `csrfmiddlewaretoken` input.

### Used By

* The play page (`game/templates/game/board.html`, served at `/play/`)

---

## play_view.js

Handles how the play page looks, apart from the game itself. It never calls the game API and never changes a move, a clock or a result. It is loaded before `board.js`.

* Sets the board theme on `<html>` before the board is drawn
* Turns the 3D view of the board on and off and remembers the choice. Until the player chooses, it is off on phones, touch-only screens and the low performance tier
* Runs the two board sliders, view angle (`--tilt`, 15 to 65 degrees) and piece size (`--piece-scale`, 70 to 120%). Each value is kept in `localStorage` and set as a CSS property on `.play`, and a double click resets a slider
* Runs the setup screen: segmented buttons, remembered player names, the small board that shows your side
* Wires up the control bar and the drawer used on phones, and opens and closes the rulebook and share dialogs

---

## stockfish.js

A third-party build of Stockfish, compiled to JavaScript and WebAssembly. Its header carries the GPL v3 notice. `board.js` starts it as a Web Worker.

### Responsibilities

* Position evaluation for the evaluation bar
* Scoring a puzzle move that differs from the stored solution, so an equally good move is accepted

It plays no part in deciding which moves are legal or in the AI opponent. Both of those happen on the server.

---

## scene3d.js

An ES module with the three.js scenes. The chess set is built in code, so there are no model files.

* `mountHero(canvas, options)`: the board on the landing page, which replays Morphy's game against the Duke of Brunswick and Count Isouard
* `mountPiece(canvas, options)`: one piece turning on a plinth, for the smaller pages
* `canRender3D()`: whether the browser has WebGL
* `shouldMount3D(kind)`: what a page asks before it mounts a scene. It is `false` when the performance tier from `perf.js` rules the scene out or the browser has no WebGL. `kind` is `'hero'` or `'piece'`

A page that imports it needs an import map for `three`. [design-system.md](design-system.md) shows the markup.

---

## landing.js

An ES module for the landing page.

* Starts the hero board with `mountHero`, or leaves the flat board in place when `shouldMount3D('hero')` says no
* Prints the moves of the replayed game as they are played
* Runs the alpha-beta demonstration: a three-level tree with random leaf values, searched step by step

---

## account.js

An ES module for the sign-in, registration, OTP, password reset, profile, account deletion and Google username pages.

* Starts the turning piece beside the form with `mountPiece`. The stage is hidden on narrow screens, and `scene3d.js` is only imported once it is shown. On the low performance tier the flat piece stays and `scene3d.js` is not fetched
* Counts numbers marked `data-count` up from zero when they scroll into view, except on the low tier

---

## community.js

An ES module for the forum list, leaderboard, achievements, stats and match history pages.

* Starts the 3D piece in each `.piece-stage` once it is on screen. On the low performance tier the flat pieces stay and `scene3d.js` is not fetched
* Counts numbers marked `data-count` up from zero when they scroll into view, except on the low tier

---

## lesson_practice.js

Handles:

* Building the practice board from the position embedded in the lesson page
* Working out where the selected piece can move
* Checking each move against the expected move of the current step, and moving on to the next step

---

## lesson_demo.js

Handles:

* Drawing the example positions embedded in the lesson page, with their highlighted squares
* Stepping to the next example

---

## opening_trainer.js

Handles:

* The trainer board on an opening's page: moves by click, drag, touch or typed notation
* Checking each move against the opening line and playing the reply
* Hints, stepping back and forward through the line, and the board theme
* Sending the result of a finished run to `/api/opening-stats/`, for signed-in users

---

## auth.js

Handles the sign-in and registration forms, and the password form on the account settings page:

* Adds a show/hide button to each password field and blocks pasting into the confirmation field
* Shows the password checklist and strength meter on the registration page, and keeps the submit button disabled until the rules are met
* Puts the submit button into a loading state while the form is sent

---

## forum.js

Switches between the tabs on the forum list and keeps the open tab in the URL hash.

---

## username-check.js

Loaded by the register page and by the page where a new Google player picks a username. It reads the check URL from the `data-check-url` attribute of its own `<script>` tag, asks `/api/check-username/` 400 ms after the typing stops, and shows the answer in a status line it adds next to the `#id_username` field.

---

## lesson_coordinates.js

Shows or hides the coordinate labels on lesson boards and saves the choice in `localStorage`.

---

## roadmap_connectors.js

Draws the SVG curves between lesson roadmap nodes and redraws them when the map changes size.

# Event Flow

## Gameplay Flow

User Move
→ board.js
→ `POST /api/move/`
→ Server validates the move through the engine and saves the game
→ JSON game state comes back
→ Board Update
→ UI Refresh
→ In an AI game, `POST /api/ai-move/` for the engine's reply

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

## app.js

Loaded on every page by the base template.

* Puts the browser's time zone in the `tz` cookie. For a signed-in player `PlayerTimezoneMiddleware` in `game/middleware.py` stores it on the profile, and the day streak counts days in that zone
* Navbar: sticky state and the mobile menu
* Dropdown menus marked `data-menu`
* Dialogs opened with `data-open-dialog` and closed with `data-close-dialog`
* Scroll reveals (`data-reveal`) and tilting cards (`data-tilt`); the tilt is off on the low performance tier
* Show/hide buttons on password fields (`.field__reveal`)

## perf.js

Loaded in the `<head>` right after `theme.js`, so the tier is on the page before anything is painted. The `high` tier is the site as designed. The `low` tier keeps every page and control and drops the costly decoration.

* Picks the tier: `?perf=low` or `?perf=high` in the address wins and is kept for the browser session, and `?perf=auto` forgets it. Otherwise a first guess is made from the GPU name, the core count, the reported memory and the data-saver setting
* Watches the frame rate while the page animates. A one-second window under 40 frames per second is a strike and a good window takes one back; three strikes move a `high` page down to `low` for the rest of the session. It never moves a page back up
* Sets `data-perf` on `<html>`, which the stylesheets use for their `[data-perf='low']` rules
* Exposes `window.checkoraPerf`: `tier`, `low`, `reason`, `software`, `wants3D(kind)`, `onDemote(listener)` and `hold()`

## theme.js

* Theme selection
* Theme persistence in `localStorage`
* Exposes `window.checkoraTheme` and fires a `checkora:theme` event when the theme changes

## toast.js

* Success notifications
* Error notifications
* User feedback messages
* Replaces `window.alert` with a toast, and turns Django success and info messages into toasts

## cursor.js

* The custom cursor and its effects
* Saves the chosen effect in `localStorage`
* Uses the default cursor on touch devices, under reduced motion and on the low performance tier, whatever effect was saved

## confetti.js

* `window.triggerConfetti()`, used on the achievements and opening pages
* Does nothing when the user prefers reduced motion, and makes a smaller burst on the low performance tier

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

Common issues:

* JavaScript runtime errors
* Failed API requests
* Theme persistence issues

---

# Best Practices

* Keep frontend logic modular.
* Document complex interactions.
* Minimize duplicated code.
* Test changes on multiple pages.
* Prefer reusable utilities over page-specific implementations.
