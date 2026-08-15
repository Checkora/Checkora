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

## board.js

Largest frontend module responsible for:

* Chess board rendering
* Move handling
* Game state updates
* Puzzle interactions
* Multiplayer integration
* WebSocket communication

### Used By

* Board page
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
