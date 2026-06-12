# Checkora API Reference Guide

This document outlines the REST API endpoints used by the Checkora frontend to communicate with the Django backend. All requests that modify state require a CSRF token in the headers (`X-CSRFToken`), except for the `@csrf_exempt` pause endpoint.

---

## 1. Get Game State
Retrieves the current game state from the user's session. It is typically called when the page is loaded or refreshed to restore an ongoing game.

*   **URL:** `/api/state/`
*   **Method:** `GET`
*   **Request Params:** None
*   **Success Response:**
    ```json
    {
      "board": [
        ["r", "n", "b", "q", "k", "b", "n", "r"],
        [null, null, null, null, null, null, null, null]
      ],
      "current_turn": "white",
      "white_time": 600,
      "black_time": 600,
      "paused": true,
      "move_history": [
        {"notation": "e4", "piece": "P", "from": [6, 4], "to": [4, 4], "color": "white"}
      ],
      "captured_pieces": {"white": [], "black": []},
      "mode": "pvp"
    }
    ```

---

## 2. Make a Move
Executes a move on the board after validating it via the C++ engine.

*   **URL:** `/api/move/`
*   **Method:** `POST`
*   **Request Body:**
    ```json
    {
      "from_row": 6,
      "from_col": 4,
      "to_row": 4,
      "to_col": 4,
      "promotion_piece": "q" // Optional: only required for pawn promotion
    }
    ```
*   **Success Response:**
    ```json
    {
      "valid": true,
      "message": "Move successful",
      "captured": null,
      "board": [[...]],
      "current_turn": "black",
      "white_time": 595,
      "black_time": 600,
      "move_history": [...],
      "captured_pieces": {"white": [], "black": []},
      "game_status": "active" // or 'check', 'checkmate', 'stalemate'
    }
    ```
*   **Error Response:**
    ```json
    {
      "valid": false,
      "message": "Invalid move"
    }
    ```

---

## 3. Get Valid Moves
Returns a list of all legal destination squares for a specific piece on the board.

*   **URL:** `/api/valid-moves/`
*   **Method:** `GET`
*   **Request Params:** `?row=6&col=4`
*   **Success Response:**
    ```json
    {
      "valid_moves": [
        {"row": 5, "col": 4, "is_capture": false},
        {"row": 4, "col": 4, "is_capture": false}
      ]
    }
    ```

---

## 4. Start New Game
Resets the session and initializes a fresh game board.

*   **URL:** `/api/new-game/`
*   **Method:** `POST`
*   **Request Body:**
    ```json
    {
      "mode": "pvp" // Can be "pvp" or "ai"
    }
    ```
*   **Success Response:**
    ```json
    {
      "board": [[...]],
      "current_turn": "white",
      "move_history": [],
      "captured_pieces": {"white": [], "black": []},
      "mode": "pvp"
    }
    ```

---

## 5. Check Promotion
Checks if a proposed pawn move will result in a promotion, allowing the frontend to display a piece selection modal *before* making the actual move request.

*   **URL:** `/api/check-promotion/`
*   **Method:** `GET`
*   **Request Params:** `?from_row=1&from_col=0&to_row=0`
*   **Success Response:**
    ```json
    {
      "is_promotion": true
    }
    ```

---

## 6. Request AI Move
Asks the backend C++ engine to calculate and execute the best move for the active side. Used in the `Play vs AI` mode.

*   **URL:** `/api/ai-move/`
*   **Method:** `POST`
*   **Request Body:** None
*   **Success Response:**
    ```json
    {
      "valid": true,
      "message": "Move successful",
      "captured": null,
      "board": [[...]],
      "current_turn": "white",
      "white_time": 600,
      "black_time": 598,
      "move_history": [...],
      "captured_pieces": {"white": [], "black": []},
      "ai_move": {
        "from_row": 1,
        "from_col": 3,
        "to_row": 3,
        "to_col": 3
      },
      "game_status": "active"
    }
    ```

---

## 7. Pause/Resume Game
Pauses or resumes the game clock. This endpoint is CSRF exempt to allow `navigator.sendBeacon` to use it when the user closes the browser tab.

*   **URL:** `/api/pause/`
*   **Method:** `POST`
*   **Request Body:**
    ```json
    {
      "pause": true,
      "white_time": 550,
      "black_time": 600
    }
    ```
*   **Success Response:**
    ```json
    {
      "paused": true,
      "white_time": 550,
      "black_time": 600
    }
    ```

---

## 8. Offer Draw
Allows players to offer or accept a draw agreement in PvP mode.

*   **URL:** `/api/draw/`
*   **Method:** `POST`
*   **Request Body:**
    ```json
    {
      "action": "offer" // Can be "offer" or "accept"
    }
    ```
*   **Success Response:**
    ```json
    {
      "success": true,
      "game_status": "draw_agreement" // Only present if action was "accept"
    }
    ```

---

## 9. Check Username Availability
Checks whether a username already exists in the system. Used during registration to provide live feedback before form submission.

- **URL:** `/api/check-username/`
- **Method:** `GET`
- **Auth Required:** No
- **Request Params:** `?username=your_username`

- **Success Response (username is free):**

```json
  {
    "available": true
  }
```

- **Username Taken Response:**

```json
  {
    "available": false
  }
```

- **Error Response (no username provided):**

```json
  {
    "available": false,
    "error": "No username provided"
  }
```

  - **Status Code:** `400 Bad Request`

---

## 10. Preloader

Serves the animated preloader screen. This is the root entry point of the application — all visitors land here first before being redirected to the main landing page.

*   **URL:** `/`
*   **Method:** `GET`
*   **Auth Required:** No
*   **Request Params:** None
*   **View:** `views.preloader`
*   **Template:** `game/preloading.html`
*   **Success Response:** Renders the preloader HTML page with animated chess engine boot sequence.
*   **Redirect Behaviour:** After 2.6s the client-side JavaScript redirects to `/home/`.

**Notes:**
- This endpoint has no JSON response — it returns a full HTML page.
- The redirect to `/home/` is handled entirely client-side via `window.location.href`.
- If `/home/` detects a page reload (`performance.getEntriesByType('navigation')[0].type === 'reload'`), it bounces the user back to `/` to replay the preloader.

---

## 11. Resume Game
Resumes an existing active game stored in the user's session without resetting the board, clocks, move history, or metadata.

*   **URL:** `/api/resume/`
*   **Method:** `POST`
*   **Auth Required:** No
*   **CSRF Required:** Yes, include `X-CSRFToken` in the request headers.
*   **Session Dependency:** Requires an existing `game` object in the session with `game_status` set to `active`.
*   **Request Body:** None
*   **Success Response:**
    ```json
    {
      "valid": true,
      "board": [[...]],
      "current_turn": "white",
      "white_time": 600,
      "black_time": 600,
      "time_limit": 600,
      "increment": 0,
      "move_history": [...],
      "captured_pieces": {"white": [], "black": []},
      "mode": "pvp",
      "player_color": "white",
      "white_name": "White",
      "black_name": "Black",
      "game_status": "active",
      "draw_reason": null,
      "threefold_warning": false,
      "fen": "current-fen-key",
      "pgn": "current-pgn-text",
      "difficulty": "medium"
    }
    ```
*   **Error Response (no saved game):**
    ```json
    {
      "valid": false,
      "message": "No saved game found."
    }
    ```
    - **Status Code:** `404 Not Found`
*   **Error Response (saved game is not active):**
    ```json
    {
      "valid": false,
      "message": "No active game to resume."
    }
    ```
    - **Status Code:** `404 Not Found`

---

## 12. Resign Game
Ends the current session game by recording a resignation and determining the winner from the current mode and active player.

*   **URL:** `/api/resign/`
*   **Method:** `POST`
*   **Auth Required:** No
*   **CSRF Required:** Yes, include `X-CSRFToken` in the request headers.
*   **Session Dependency:** Requires an existing `game` object in the session.
*   **Request Body:** None
*   **Success Response:**
    ```json
    {
      "valid": true,
      "message": "White resigned.",
      "winner": "black",
      "game_status": "resignation"
    }
    ```
*   **Error Response (no active game):**
    ```json
    {
      "valid": false,
      "message": "No active game."
    }
    ```
    - **Status Code:** `400 Bad Request`

---

## 13. Analyze Game
Analyzes a completed game's move history and returns summary statistics for the post-game analysis view.

*   **URL:** `/api/analyze-game/`
*   **Method:** `POST`
*   **Auth Required:** No
*   **CSRF Required:** No. This endpoint is decorated with `@csrf_exempt`.
*   **Request Body:**
    ```json
    {
      "moves": ["e4", "e5", "Nf3", "Nc6"],
      "result": "White wins",
      "reason": "checkmate"
    }
    ```
*   **Request Body Fields:**
    - `moves`: list of SAN notation strings. Non-list values are treated as an empty list.
    - `result`: optional result label. Defaults to `"Unknown"` if omitted.
    - `reason`: optional end reason. Defaults to `"Unknown"` if omitted.
*   **Success Response:**
    ```json
    {
      "opening": "Italian Game",
      "result": "White wins",
      "total_moves": 2,
      "captures": 0,
      "checks": 0,
      "checkmates": 0,
      "promotions": 0,
      "end_reason": "checkmate"
    }
    ```
*   **Error Response:**
    ```json
    {
      "error": "Failed to analyze game"
    }
    ```
    - **Status Code:** `400 Bad Request`

---

## 14. Get Puzzle Stats
Returns puzzle streak information for the puzzle interface.

*   **URL:** `/api/puzzle-stats/`
*   **Method:** `GET`
*   **Auth Required:** No
*   **Request Params:** None
*   **Success Response:**
    ```json
    {
      "streak": 0,
      "longest_streak": 0
    }
    ```

**Notes:**
- This endpoint currently returns placeholder values from `views.puzzle_stats_view`.
- Both `streak` and `longest_streak` are hardcoded to `0` until persistent puzzle statistics are wired into this response.

---
