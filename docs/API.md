# Checkora API Reference Guide

This document outlines the REST API endpoints used by the Checkora frontend to communicate with the Django backend. Most requests that modify state require a CSRF token in the headers (`X-CSRFToken`). Exceptions are documented in the Authentication & Security section below.

---

## Authentication & Security

Most POST endpoints require a valid CSRF token supplied through the `X-CSRFToken` header.

Exception:

* `/api/cron/cleanup-stale-games/`

This endpoint is exempt from CSRF validation. `/api/pause/` and `/api/analyze-game/` are not exempt and need the token like every other POST.

Administrative endpoints such as `/api/cron/cleanup-stale-games/` require Bearer Token authentication and are intended for internal maintenance operations.

## Endpoint Categories

### Gameplay APIs
- Get Game State
- Make a Move
- Get Valid Moves
- Start New Game
- Check Promotion
- Request AI Move
- Pause/Resume Game
- Offer Draw
- Resume Game
- Resign Game
- Claim Timeout

### Analysis APIs
- Analyze Game

### Puzzle APIs
- Get Puzzle Stats
- Get Daily Puzzle
- Solve Puzzle

### Opening trainer APIs
- Update Opening Stats

### User APIs
- Check Username Availability
- Get Avatar (under Profile pictures in the Authentication Endpoints)

### Maintenance APIs
- Cleanup Stale Games

## 1. Get Game State
Retrieves the current game state from the user's session. It is typically called when the page is loaded or refreshed to restore an ongoing game.

*   **URL:** `/api/state/`
*   **Method:** `GET`
*   **Request Params:** None
*   **Success Response:**
    ```json
    {
      "version": 0,
      "board": [
        ["r", "n", "b", "q", "k", "b", "n", "r"],
        [null, null, null, null, null, null, null, null]
      ],
      "current_turn": "black",
      "white_time": 600,
      "black_time": 600,
      "paused": true,
      "move_history": [
        {
          "notation": "e4",
          "piece": "P",
          "from": [6, 4],
          "to": [4, 4],
          "captured": null,
          "color": "white",
          "promoted_to": null
        }
      ],
      "captured_pieces": {
        "white": [],
        "black": []
      },
      "mode": "pvp",
      "time_limit": 600,
      "increment": 5,
      "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
      "pgn": "[Event \"Checkora Match\"]",
      "game_status": "active",
      "in_check": false,
      "draw_reason": null,
      "threefold_warning": false,
      "player_color": "white",
      "difficulty": "medium",
      "white_name": "White",
      "black_name": "Black",
      "opening_name": "King's Pawn Game",
      "opening_moves": "e4",
      "rated": false
    }
    ```

**Notes:**
- `version` is the version number of a logged-in user's stored game. Send it back with `/api/move/` and `/api/ai-move/` so a stale request is refused with `409`. For an anonymous game, which lives in the session, it is `0`.
- `rated` is `true` only for a logged-in user playing the AI from the standard starting position.
- `opening_name` and `opening_moves` are filled once the moves played match a known opening, and `null` otherwise.
- `day_streak` is added for logged-in users.
- `game_status` is the stored status of the game: `active`, `checkmate`, `stalemate`, `draw`, `resignation` or `timeout`.
- `in_check` is `true` while the side to move is in check. `game_status` stays `active` during a check, so a client that wants to show the check reads this field. `/api/new-game/` and `/api/resume/` send it too.
- If the game is not paused and its clock was last updated more than 10 seconds ago, the response reports `"paused": true` without taking that time off the clock. The stored game is not changed.
- If a clock has run out, this request ends the game as a loss on time. The response then has `"game_status": "timeout"` and a `winner` field (`"white"` or `"black"`).


---

## 2. Make a Move
Executes a move on the board after validating it via the chess engine (the compiled C++ engine, or the Python engine when no usable binary is present).

*   **URL:** `/api/move/`
*   **Method:** `POST`
*   **Request Body:**
    ```json
    {
      "from_row": 6,
      "from_col": 4,
      "to_row": 4,
      "to_col": 4,
      "promotion_piece": "q"
    }
    ```

    `promotion_piece` is optional and only required for pawn promotion. The four coordinates must be integers from 0 to 7.

    A logged-in client can also send `version`, the number it last received. If the stored game has moved on since then, the request is refused with `409`.
*   **Success Response:**
    ```json
    {
      "valid": true,
      "message": "e4",
      "captured": null,
      "board": [[...]],
      "current_turn": "black",
      "white_time": 595,
      "black_time": 600,
      "time_limit": 600,
      "increment": 5,
      "move_history": [...],
      "opening_name": "King's Pawn Game",
      "opening_moves": "e4",
      "captured_pieces": {"white": [], "black": []},
      "game_status": "ok",
      "draw_reason": null,
      "threefold_warning": false,
      "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
      "pgn": "[Event \"Checkora Match\"]",
      "white_name": "White",
      "black_name": "Black",
      "version": 0
    }
    ```

    On success `message` is the move in algebraic notation.

    Possible values for `game_status`:
    - `ok` (the move was played and the game goes on)
    - `check`
    - `checkmate`
    - `stalemate`
    - `draw` (`draw_reason` says why: `insufficient_material`, `threefold_repetition` or `fifty_move_rule`)
    - `timeout` (the clock had already run out, so the move was not played; the response has `"valid": false` and a `winner` field)

    A move that ends the game is also recorded as a finished game.
*   **Error Response (move rejected):**

    The status code is `200`, and the body is the same object as above with the position unchanged.
    ```json
    {
      "valid": false,
      "message": "Illegal move.",
      "game_status": "active"
    }
    ```
*   **Error Response (bad coordinates):**
    ```json
    {
      "error": "Invalid board coordinates"
    }
    ```
    - **Status Code:** `400 Bad Request`
*   **Error Response (AI game, not the player's turn):**
    ```json
    {
      "valid": false,
      "message": "It is the computer's turn."
    }
    ```
    - **Status Code:** `403 Forbidden`
*   **Error Response (stale `version`, or the game changed while the move was saved):**
    ```json
    {
      "error": "Conflict: Stale game state."
    }
    ```
    - **Status Code:** `409 Conflict`

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
        {"row": 4, "col": 4, "is_capture": false, "is_promotion": false},
        {"row": 5, "col": 4, "is_capture": false, "is_promotion": false}
      ]
    }
    ```

---

## 4. Start New Game

Resets the session and initializes a fresh game board.

* **URL:** `/api/new-game/`
* **Method:** `POST`

### Request Parameters

| Parameter    | Type    | Required | Description                                              |
| ------------ | ------- | -------- | -------------------------------------------------------- |
| mode         | string  | No       | Game mode: `"pvp"` or `"ai"`. Default: `"pvp"`           |
| difficulty   | string  | No       | AI difficulty level: `"easy"`, `"medium"`, `"hard"` or `"master"`. Default: `"medium"` |
| fen          | string  | No       | FEN position to initialize the board from                |
| time_limit   | integer | No       | Initial clock time in seconds for each player, kept between 60 and 18000. Default: 600 |
| increment    | integer | No       | Increment (seconds added after each move), kept between 0 and 180. Default: 0 |
| player_color | string  | No       | Human player's color in AI mode (`"white"`, `"black"` or `"random"`) |
| white_name   | string  | No       | Display name for White, up to 30 characters              |
| black_name   | string  | No       | Display name for Black, up to 30 characters              |
| opening      | string  | No       | AI mode only: a named line from `_named_lines` in `game/engine/opening_book.json` for the engine to follow |

`time_limit` can also be a string of the form `"minutes|increment"`, for example `"5|3"`.

### Example Request Body

```json
{
  "mode": "ai",
  "difficulty": "medium",
  "time_limit": 300,
  "increment": 3,
  "player_color": "white",
  "white_name": "Alice",
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
}
```

### Success Response

```json
{
  "valid": true,
  "board": [[...]],
  "current_turn": "white",
  "move_history": [],
  "captured_pieces": {
    "white": [],
    "black": []
  },
  "mode": "ai",
  "player_color": "white",
  "white_name": "Alice",
  "black_name": "♗ Tactical Bishop",
  "difficulty": "medium",
  "time_limit": 300,
  "increment": 3,
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "pgn": "[Event \"Checkora Match\"]",
  "game_status": "active",
  "in_check": false,
  "draw_reason": null,
  "opening": "",
  "version": 0,
  "rated": false,
  "forfeited": false
}
```

**Notes:**
- In AI mode the engine's side takes a name that goes with the difficulty, whatever name was sent for it.
- A game started from a `fen` can begin in check, or be over before the first move. `in_check` and `game_status` (`checkmate`, `stalemate` or `draw`) say so.
- `rated` is `true` for a logged-in user starting an AI game from the standard starting position.
- `forfeited` is `true` when a logged-in user had a rated game in progress with at least 5 half-moves played. That game is recorded as a resignation by the user, or as decided on time if one of its clocks had already run out, before the new one starts.
- `version` is the version of the stored game for a logged-in user and `0` otherwise.

### Error Responses

A body that is not a JSON object:

```json
{
  "valid": false,
  "message": "Invalid request data."
}
```

A FEN that cannot be parsed, or one in which the side that is not to move is in check. The game in progress is left as it was:

```json
{
  "valid": false,
  "message": "Invalid FEN: FEN must have 8 ranks."
}
```

**Status Code:** `400 Bad Request`

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
Asks the backend chess engine to calculate and execute the best move for the active side. Used in the `Play vs AI` mode. How hard it searches depends on the game's `difficulty`; the levels are described in [engine_architecture.md](engine_architecture.md).

*   **URL:** `/api/ai-move/`
*   **Method:** `POST`
*   **Request Body:** None required. A logged-in client can send `{"version": <number>}` as for `/api/move/`.
*   **Success Response:**
    ```json
    {
      "valid": true,
      "message": "d5",
      "captured": null,
      "board": [[...]],
      "current_turn": "white",
      "white_time": 600,
      "black_time": 598,
      "time_limit": 600,
      "increment": 5,
      "move_history": [...],
      "opening_name": "Queen's Pawn Game",
      "opening_moves": "d4 d5",
      "captured_pieces": {"white": [], "black": []},
      "ai_move": {
        "from_row": 1,
        "from_col": 3,
        "to_row": 3,
        "to_col": 3
      },
      "game_status": "ok",
      "draw_reason": null,
      "threefold_warning": false,
      "fen": "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq d6 0 2",
      "pgn": "[Event \"Checkora Match\"]",
      "white_name": "White",
      "black_name": "Black",
      "opening": "",
      "version": 0
    }
    ```

    `message` and `game_status` work as in `/api/move/`. `ai_move` always has the four coordinates. A move found by the search, as opposed to one taken from the opening book, also carries `eval` (centipawns from White's side), `alts` (the next best moves with their scores; only `easy` asks the engine for them, so the list is empty on the other levels), `depth`, `nodes`, `tthits`, `time` (milliseconds), `engine` (`cpp` or `python`) and `status` (`completed` or `timeout`), and `promotion_piece` when the move promotes. `opening` is the named opening line the engine is still following, or an empty string. When the engine's clock has run out, `game_status` is `"timeout"` and a `winner` field is added.

    If the engine has no legal move, the game is finished here: the response has `"valid": true`, `game_status` set to `checkmate`, `stalemate` or `draw`, and no `ai_move`.
*   **Error Responses:**

    | Status | Body | When |
    | ------ | ---- | ---- |
    | `400` | `{"valid": false, "message": "No active game."}` | There is no game to move in |
    | `400` | `{"valid": false, "message": "Not in AI mode."}` | The game is a two-player game |
    | `400` | `{"valid": false, "message": "Game is already over."}` | The game has finished |
    | `400` | `{"valid": false, "message": "Game is paused."}` | The clock is paused |
    | `400` | `{"valid": false, "message": "It is not the computer's turn."}` | It is the player's move |
    | `409` | `{"error": "Conflict: Stale game state."}` | The game changed since `version`, or while the engine was thinking |
    | `429` | `{"error": "Too many AI move requests. Please try again shortly."}` | Rate limit reached; a `Retry-After` header gives the window in seconds |
    | `503` | `{"valid": false, "message": "The engine did not answer. Please try again."}` | The engine returned nothing for a position that is not finished |

---

## 7. Pause/Resume Game
Pauses or resumes the game clock. It needs the CSRF token like the other POST endpoints. When the tab is hidden or closed, `board.js` sends the pause as a `fetch` with `keepalive` so the request can still finish.

*   **URL:** `/api/pause/`
*   **Method:** `POST`
*   **Request Body:**
    ```json
    {
      "pause": true
    }
    ```
*   **Success Response:**
    ```json
    {
      "paused": true,
      "white_time": 550,
      "black_time": 600,
      "version": 0
    }
    ```

    With no stored game the response is `{"paused": false}`. A body that is not a JSON object gets `400`, and a save that loses to a concurrent change gets `409`.

---

## 8. Offer Draw
Allows players to offer or accept a draw agreement in PvP mode.

*   **URL:** `/api/draw/`
*   **Method:** `POST`
*   **Request Body:**

    ```json
    {
      "action": "offer"
    }
    ```

Valid values for `action`:

- `offer`
- `accept`
- `decline`

*   **Success Response (offer):**

    ```json
    {
      "success": true
    }
    ```

*   **Success Response (accept):**

    ```json
    {
      "success": true,
      "game_status": "draw",
      "draw_reason": "agreement"
    }
    ```

    Accepting ends the game and records it as a draw by agreement.

*   **Success Response (decline):**

    ```json
    {
      "success": true
    }
    ```

*   **Error Responses:**

    All of these have status `400 Bad Request`, except the last.

    | Body | When |
    | ---- | ---- |
    | `{"success": false, "message": "No active game."}` | There is no game |
    | `{"valid": false, "message": "Invalid request data."}` | The body is not a JSON object |
    | `{"success": false, "message": "Invalid action."}` | `action` is not one of the three values |
    | `{"success": false, "message": "Game is not active."}` | `accept` on a game that has finished |
    | `{"success": false, "message": "Draws by agreement are only available in two-player games."}` | `accept` in an AI game |
    | `{"error": "State conflict, please retry"}` | `accept` lost to a concurrent change (status `409`) |

---

## 9. Check Username Availability
Checks whether a username already exists in the system, ignoring case. A signup still waiting for its email code holds its name for an hour, as on `/register/`; after that the name shows as free. The check only reads, it never deletes anything. `username-check.js` calls it on the register page and on the page where a new Google player picks a username, to give live feedback before the form is sent.

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

## 10. Landing page

Serves the landing page. This is the root entry point of the application.

*   **URL:** `/`
*   **Method:** `GET`
*   **Auth Required:** No
*   **Request Params:** None
*   **View:** `views.landing`
*   **Template:** `game/landing.html`
*   **Success Response:** Renders the landing page.

**Notes:**
- This endpoint has no JSON response. It returns a full HTML page.
- `/home/`, where the landing page used to be, answers with a permanent redirect to `/`.
- The board is at `/play/` (`views.index`, template `game/board.html`).
- `/privacy/` and `/terms/` are plain pages (`game/privacy.html` and `game/terms.html`) with the privacy policy and the terms. The footer opens the same text in dialogs, from `game/includes/privacy_text.html` and `game/includes/terms_text.html`.

---

## 11. Resume Game
Resumes an existing active game stored in the user's session without resetting the board, clocks, move history, or metadata.

*   **URL:** `/api/resume/`
*   **Method:** `POST`
*   **Auth Required:** No
*   **CSRF Required:** Yes, include `X-CSRFToken` in the request headers.
*   **Session Dependency:** Requires a stored game with `game_status` set to `active`. An anonymous visitor's game is the `game` object in the session; a logged-in user's game is an `ActiveGame` row in the database.
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
      "in_check": false,
      "draw_reason": null,
      "threefold_warning": false,
      "fen": "current-fen-key",
      "pgn": "current-pgn-text",
      "difficulty": "medium",
      "version": 0
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
*   **Session Dependency:** Requires a stored game that is still active (see Resume Game for where it is stored).
*   **Request Body:** Optional. In a two-player game `{"resigning_player": "white"}` or `"black"` says who resigns; without it the side to move resigns. In an AI game the human player always resigns, whatever is sent.
*   **Success Response:**
    ```json
    {
      "valid": true,
      "message": "White resigned.",
      "winner": "black",
      "game_status": "resignation",
      "version": 0
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
*   **Error Response (game already finished):**
    ```json
    {
      "valid": false,
      "message": "Game is already over."
    }
    ```
    - **Status Code:** `400 Bad Request`
*   **Error Response (the game changed while the resignation was saved):**
    ```json
    {
      "error": "Conflict: Stale game state."
    }
    ```
    - **Status Code:** `409 Conflict`

---

## 13. Analyze Game
Analyzes a completed game's move history and returns summary statistics for the post-game analysis view.

*   **URL:** `/api/analyze-game/`
*   **Method:** `POST`
*   **Auth Required:** Yes. An anonymous request gets `401` with `{"error": "Unauthorized"}`.
*   **CSRF Required:** Yes, include `X-CSRFToken` in the request headers.
*   **Request Body:**
    ```json
    {
      "moves": ["e4", "e5", "Nf3", "Nc6"],
      "result": "White wins",
      "reason": "checkmate"
    }
    ```
*   **Request Body Fields:**
    - `moves`: required list of SAN notation strings, at most 500 entries of at most 20 characters each. Only the first 80 are analysed.
    - `result`: optional result label. Defaults to `"Unknown"` if omitted.
    - `reason`: optional end reason. Defaults to `"Unknown"` if omitted.
*   **Success Response:**
    ```json
    {
      "result": "White wins",
      "end_reason": "checkmate",
      "opening": "King's Pawn Game",
      "captures": 0,
      "checks": 0,
      "checkmates": 0,
      "promotions": 0,
      "blunders": 0,
      "mistakes": 0,
      "accuracy": 100,
      "total_moves": 2,
      "move_analysis_details": [
        {"move_num": 1, "color": "White", "played": "e4", "best": "Nf3", "class": "Unknown", "eval": null},
        {"move_num": 1, "color": "Black", "played": "e5", "best": "d5", "class": "Unknown", "eval": null},
        {"move_num": 2, "color": "White", "played": "Nf3", "best": "Nc3", "class": "Unknown", "eval": null},
        {"move_num": 2, "color": "Black", "played": "Nc6", "best": "Nc6", "class": "Best", "eval": null}
      ],
      "move_analysis": ["Unknown", "Unknown", "Unknown", "Best"],
      "analysis_timeout_seconds": 10,
      "truncated": false,
      "final_eval": null
    }
    ```

    - `move_analysis_details` has one entry per analysed half-move: the move played, the engine's choice, and a `class` of `Best`, `Inaccuracy`, `Mistake`, `Blunder` or `Unknown`. `Unknown` means the engine gave no evaluation to compare with, as in the example, where the engine's choices came without one. `move_analysis` is the list of those classes on their own.
    - `eval` and `final_eval` are in centipawns from White's side.
    - `accuracy` is the share of judged moves that were neither a mistake nor a blunder, as a whole percentage, or `null` when no move could be judged.
    - The analysis has a time budget, reported in `analysis_timeout_seconds` and in the `X-Analysis-Timeout` response header. When it runs out, the moves analysed so far are returned and `truncated` is `true`.
*   **Error Responses:**

    | Status | Body | When |
    | ------ | ---- | ---- |
    | `400` | `{"error": "Missing moves field"}` | The body has no `moves` |
    | `400` | `{"error": "Moves must be a list"}` | `moves` is not a list |
    | `400` | `{"error": "Moves list cannot exceed 500 entries"}` | Too many moves |
    | `400` | `{"error": "Move must be a string of at most 20 characters"}` | A move is not a string, or is too long |
    | `400` | `{"error": "Failed to analyze game"}` | Anything else that goes wrong, including a body that is not JSON |
    | `401` | `{"error": "Unauthorized"}` | Not logged in |
    | `429` | `{"error": "Too many requests"}` | Rate limit reached, per user or per IP address |

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
      "longest_streak": 0,
      "puzzles_solved": 0,
      "daily_completions": 0
    }
    ```

**Notes:**
- For a logged-in user the values come from that user's `PuzzleStats` row. A streak that has lapsed, because a whole day (UTC) passed without the daily puzzle, reads `0`. Reading it writes nothing.
- An anonymous request gets all four values as `0`.
- The only endpoint that changes them is `POST /api/puzzles/<id>/solve/` (section 19).

---

## 15. Get Daily Puzzle

Returns the puzzle assigned for the current day.

* **URL:** `/api/puzzles/daily/`

* **Method:** `GET`

* **Auth Required:** No

* **Request Params:** None

* **Success Response:**

```json
{
  "id": 1,
  "title": "Daily Puzzle",
  "fen": "6k1/5ppp/8/8/8/8/5PPP/6KQ w - - 0 1",
  "difficulty": "medium"
}
```

**Notes:**

* Returns the puzzle selected for the current date.
* When no puzzle is dated today, one is picked from the stored puzzles by the day number, so the same puzzle is served all day.
* The solution is not part of the response. `GET /api/puzzles/<id>/solution/` returns it.
* When the database has no puzzles at all, a built-in default puzzle with `"id": 0` is returned, and that one does include a `solution` field.
* Used by the Daily Puzzle feature in the frontend.

---

## 16. Cleanup Stale Games

Administrative endpoint used to clean abandoned or inactive games.

* **URL:** `/api/cron/cleanup-stale-games/`
* **Method:** `GET` or `POST`
* **Auth Required:** Yes
* **Authentication:** Bearer Token

**Required Header**

```http
Authorization: Bearer <CRON_SECRET>
```

* **Success Response:**

```json
{
  "status": "success",
  "deleted_games": 12,
  "resigned_games": 3,
  "purged_records": 5,
  "purged_sessions": 40
}
```

* **Unauthorized Response:**

```json
{
  "error": "Unauthorized"
}
```

**Status Code:** `401 Unauthorized`

* **Failure Response:**

```json
{
  "status": "error",
  "message": "<the exception text>"
}
```

**Status Code:** `500 Internal Server Error`

**Notes:**

* Intended for scheduled maintenance jobs. `vercel.json` schedules it once a day (`0 3 * * *`). The view accepts `GET` because, as its docstring notes, Vercel calls cron paths with GET; `POST` stays for manual runs.
* The token is the `CRON_SECRET` environment variable. While that variable is unset, every request gets `401`.
* Active games untouched for 48 hours are removed: with fewer than 5 half-moves they are deleted (`deleted_games`), otherwise they are recorded as resigned (`resigned_games`).
* Expired replay records (`purged_records`) and expired sessions (`purged_sessions`) are deleted in the same run.
* Should not be called directly from the frontend.

---

## 17. Common Error Responses

Different endpoints may return different error payloads depending on the operation being performed. The examples below illustrate common error patterns used throughout the API but do not represent a guaranteed response schema for every endpoint.

### 400 Bad Request

```json
{
  "valid": false,
  "message": "Invalid request data."
}
```

### 401 Unauthorized

```json
{
  "error": "Unauthorized"
}
```

### 404 Not Found

```json
{
  "valid": false,
  "message": "No saved game found."
}
```

### 409 Conflict

Returned by the gameplay endpoints when a logged-in user's stored game changed between the read and the write, for example when two requests arrive at once.

```json
{
  "error": "Conflict: Stale game state."
}
```

### 500 Internal Server Error

```json
{
  "valid": false,
  "message": "Internal error verifying game state."
}
```

---

## 18. Claim timeout

Ends the game on time. The client calls this when its own clock reaches zero. The server decides from the clock it has stored, not from anything in the request.

*   **URL:** `/api/timeout/`
*   **Method:** `POST`
*   **Auth Required:** No
*   **CSRF Required:** Yes, include `X-CSRFToken` in the request headers.
*   **Request Body:** None
*   **Success Response:**
    ```json
    {
      "valid": true,
      "game_status": "timeout",
      "winner": "black",
      "white_time": 0,
      "black_time": 412,
      "version": 0
    }
    ```

    The game is recorded as a loss on time for the side whose clock ran out. In an AI game, a timeout of the engine's clock does not count towards the rating.
*   **Error Response (the server's clock still has time):**
    ```json
    {
      "valid": false,
      "message": "Clock has not run out.",
      "white_time": 3,
      "black_time": 412
    }
    ```
    - **Status Code:** `400 Bad Request`

    The response carries the server's clock values so the client can correct its own.
*   **Other Error Responses:** `400` with `{"valid": false, "message": "No active game."}` or `{"valid": false, "message": "Game is already over."}`, and `409` with `{"error": "Conflict: Stale game state."}`.

---

## 19. Solve puzzle

Checks the moves a user played against the stored solution of a puzzle and, when they match, counts the solve. The totals and the streak are worked out on the server.

*   **URL:** `/api/puzzles/<id>/solve/`
*   **Method:** `POST`
*   **Auth Required:** Yes. An anonymous request gets `401` with `{"error": "Unauthorized"}`.
*   **CSRF Required:** Yes, include `X-CSRFToken` in the request headers.
*   **Request Body:**
    ```json
    {
      "moves": ["g2g4"]
    }
    ```

    `moves` is the list of moves played, written the way the puzzle's `solution` is stored. The comparison ignores case and surrounding spaces, and the list must have the same length as the solution.
*   **Success Response:**
    ```json
    {
      "success": true,
      "correct": true,
      "counted": true,
      "newly_solved": true,
      "puzzles_solved": 1,
      "streak": 1,
      "longest_streak": 1,
      "daily_completions": 1
    }
    ```

    - `correct` says whether the moves matched. A wrong attempt still gets `200`, with `"correct": false` and the user's current numbers.
    - `newly_solved` is `true` the first time this user solves this puzzle. `puzzles_solved` goes up only then.
    - `counted` is `false` when this user opened the puzzle's solution (`/api/puzzles/<id>/solution/`) in the last seven days. The answer is still checked, but nothing is counted.
    - `streak`, `longest_streak` and `daily_completions` go up only when the puzzle is the daily puzzle and it has not been counted for that day yet. The daily puzzle changes at midnight UTC; yesterday's still counts for yesterday when it is solved within 15 minutes of midnight. `streak` reads `0` once a whole day has passed without the daily puzzle.
    - A new solve earns 10 XP, and the daily puzzle 15 XP more.
*   **Rate limit:** `PUZZLE_SOLVE_MAX_REQUESTS` answers per `PUZZLE_SOLVE_RATE_WINDOW_SECONDS` per user (20 a minute by default), then `429`.
*   **Error Responses:** `400` with `{"success": false, "error": "moves must be a list of strings"}`, `401` as above, `404` when no puzzle has that id, and `429` as above.

---

## 20. Update opening stats

Saves the result of an opening trainer run for the logged-in user.

*   **URL:** `/api/opening-stats/`
*   **Method:** `POST`
*   **Auth Required:** Yes. The view uses `@login_required`, so an anonymous request is redirected to the login page.
*   **CSRF Required:** Yes, include `X-CSRFToken` in the request headers.
*   **Request Body:**
    ```json
    {
      "opening_name": "Italian Game",
      "completed": true,
      "accuracy": 87.5
    }
    ```

    - `opening_name`: required. It must be the `name` of an opening in `game/opening_trainer_data.py`.
    - `completed`: optional boolean. Defaults to `false`.
    - `accuracy`: optional number. Defaults to `0`. Values outside 0 to 100 are brought into that range.
*   **Success Response:**
    ```json
    {
      "success": true,
      "accuracy": 87.5
    }
    ```

    `accuracy` is the value after it was brought into range. The first completed run of an opening gives the user 50 XP, and 25 more when `accuracy` is 100.
*   **Error Responses:**

    All have status `400 Bad Request`.

    | Body | When |
    | ---- | ---- |
    | `{"success": false, "error": "Invalid JSON payload"}` | The body is not a JSON object |
    | `{"success": false, "error": "Opening name is required"}` | `opening_name` is missing or empty |
    | `{"success": false, "error": "Invalid opening name"}` | The name is not in the opening list |
    | `{"success": false, "error": "Invalid completed flag"}` | `completed` is not a boolean |
    | `{"success": false, "error": "Invalid accuracy"}` | `accuracy` is not a number |

## Authentication Endpoints

### 1. Register User

Creates a new user account and sends an OTP verification code to the registered email address.

* **URL:** `/register/`
* **Methods:** `GET`, `POST`
* **Authentication:** Public
* **CSRF Protection:** Required for POST requests

**POST Parameters**

| Parameter | Type   | Required | Description           |
| --------- | ------ | -------- | --------------------- |
| username  | string | Yes      | Desired username      |
| email     | string | Yes      | User email address    |
| password1 | string | Yes      | Password              |
| password2 | string | Yes      | Password confirmation |

**Success Behavior**

* Creates an inactive user account.
* Sends a verification OTP to the provided email address.
* Redirects to `/verify-otp/`.

**Error Conditions**

* Invalid form data.
* OTP delivery failure.

A username or email that is already taken is not reported as an error. The response is the same redirect and message as for a successful registration, and no code is sent.

**Security Notes**

* OTP expires after 5 minutes.
* Registration flow includes protections against account enumeration.
* Concurrent registration requests are rate-limited.

---

### 2. Verify OTP

Activates a newly registered account.

* **URL:** `/verify-otp/`
* **Methods:** `GET`, `POST`
* **Authentication:** Public
* **CSRF Protection:** Required for POST requests

**POST Parameters**

| Parameter | Type   | Required |
| --------- | ------ | -------- |
| otp       | string | Yes      |

**Success Behavior**

* Activates the user account.
* Logs the user in.
* Redirects to the application.

**Error Conditions**

* Invalid OTP.
* Expired OTP.
* Missing registration session.

**Security Notes**

* OTP expires after 5 minutes.
* Maximum 5 failed verification attempts.

---

### 3. Resend OTP

Generates and sends a new verification code.

* **URL:** `/resend-otp/`
* **Methods:** `POST`
* **Authentication:** Public
* **CSRF Protection:** Required

**Success Behavior**

* Generates a new OTP.
* Sends the OTP to the registered email address.
* Redirects back to the verification page.

**Security Notes**

* 60-second cooldown between OTP requests.

---

### 4. Login

Authenticates a user and creates a session.

* **URL:** `/login/`
* **Methods:** `GET`, `POST`
* **Authentication:** Public
* **CSRF Protection:** Required for POST requests

**POST Parameters**

| Parameter   | Type    | Required |
| ----------- | ------- | -------- |
| username    | string  | Yes      |
| password    | string  | Yes      |
| remember_me | boolean | No       |

**Success Behavior**

* Creates an authenticated session.
* Redirects to the `next` URL when one was passed and it points at this site, otherwise to the landing page at `/`.

**Security Notes**

* Username-based lockout protection.
* IP-based lockout protection.
* Session fixation protection via session key rotation.

---

### 4.1 Continue with Google

Signs in or signs up with a Google account. The button on `/login/` and `/register/` appears only when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set.

* **URL:** `/auth/google/`
* **Methods:** `GET`
* **Authentication:** Public

Starts the sign-in. The session stores a random `state`, `nonce` and PKCE verifier, plus the `next` page when one was passed and it points at this site, and the browser is redirected to Google.

* **URL:** `/auth/google/callback/`
* **Methods:** `GET`
* **Authentication:** Public

Google sends the browser back here with `code` and `state`. A `state` that does not match the session, or one already used, is refused. The code is exchanged for an ID token, whose issuer, audience, expiry, nonce and `email_verified` claim are checked. Then:

* A Google account already linked to a player signs that player in.
* A verified address that belongs to exactly one existing account links the Google account to it and signs in. Signups that never verified their email do not count.
* Anyone else is a new player. Nothing is created yet: the Google identity waits in the session for 15 minutes and the browser goes to `/auth/google/username/`.
* A deactivated account is never signed in.

* **URL:** `/auth/google/username/`
* **Methods:** `GET`, `POST`
* **Authentication:** A Google sign-in waiting for its username
* **CSRF Protection:** Required for POST requests

**POST Parameters**

| Parameter | Type   | Required |
| --------- | ------ | -------- |
| username  | string | Yes      |

The account is created only when a valid, free username is posted. The username follows the same rules as `/register/` and is compared without case. The new account has no password, is linked to the Google account in `GoogleAccount`, gets the welcome email and is signed in.

---

### 5. Logout

Ends the current authenticated session.

* **URL:** `/logout/`
* **Methods:** `POST`
* **Authentication:** Authenticated user
* **CSRF Protection:** Required

**Success Behavior**

* Logs out the current user.
* Redirects to the landing page at `/`.

---

### 6. Delete account

Deleting an account takes two requests and an email in between.

* **URL:** `/delete-account/`
* **Methods:** `GET`, `POST`
* **Authentication:** Authenticated user
* **CSRF Protection:** Required for POST requests

**POST Parameters**

| Parameter | Type   | Required |
| --------- | ------ | -------- |
| username  | string | Yes      |
| password  | string | Yes, except for accounts made with Google, which have none |

When the username and password are those of the logged-in user, a confirmation link is emailed to the account's address and the user is redirected to `/account/`. Nothing is deleted at this point. A wrong username or password gets `400`, and a mail that can't be sent `502`.

* **URL:** `/confirm-delete/<uidb64>/<token>/`
* **Methods:** `GET`, `POST`
* **Authentication:** The owner of the account must be logged in. An anonymous visitor is sent to the login page and comes back to the link afterwards.
* **CSRF Protection:** Required for POST requests

**Behavior**

* `GET` renders a confirmation page (`game/confirm_delete_account.html`) and changes nothing, so opening the emailed link does not delete the account.
* `POST` from that page logs the user out, deletes the account and renders `game/delete_success.html`.
* A link that is invalid, has expired or belongs to another account redirects to `/` with an error message.

**Security Notes**

* The token comes from a subclass of Django's password reset token generator with its own salt, so a password reset token cannot delete an account. It expires after `PASSWORD_RESET_TIMEOUT`, which `core/settings.py` sets to 300 seconds.

---

### 7. Account settings

`/account/` shows the forms below. Each form posts to its own URL, needs a signed-in user and a CSRF token, and redirects back to `/account/` with a message; a form error re-renders the page with `400`.

| URL | Fields | What it does |
| --- | --- | --- |
| `/account/username/` | `username` | Renames the account. Same rules as `/register/`, compared without case. Once every 30 days. A change of case only is allowed at any time and does not start the 30 days. |
| `/account/email/` | `email` | Mails a six-digit code to the new address and redirects to `/account/email/verify/`. An address another account uses gets the same answer and no mail. One code per address per minute (`429` otherwise). |
| `/account/email/verify/` | `code` | Switches the email when the code matches. Codes last 10 minutes and allow 5 tries. The old address is told about the change. |
| `/account/password/` | `old_password`, `new_password1`, `new_password2` | Changes the password and keeps this browser signed in. An account made with Google has no `old_password` field and sets its first password here. The account's email is told. |
| `/account/google/unlink/` | none | Removes the Google link. Refused while the account has no password, since nothing else could sign in to it. |

`/auth/google/?link=1` links a Google account to the signed-in player; see 4.1.

---

### 8. Profile pictures

A picture is one of twelve Staunton pieces or an uploaded image, never both.

* `GET /avatar/` shows the picker. `POST /avatar/` takes a file in `avatar` (PNG, JPEG or WEBP, up to 5 MB and 4096 px a side). It is re-encoded to PNG or JPEG at most 256 px a side.
* `POST /avatar/preset/` with `preset` set to one of `wk wq wr wb wn wp bk bq br bb bn bp`.
* `POST /avatar/remove/` clears either kind.
* `GET /api/avatar/` returns `{"avatar": "<url>"}` for the signed-in user, `""` when there is none.
* `GET /u/<user_id>/avatar/` serves an uploaded picture's bytes to anyone, with `Cache-Control: public, max-age=31536000, immutable`. Pages link to it with `?v=<time of upload>`, so a new upload gets a new URL. A preset or no picture gives `404`.

---

### 9. Rating, rank, points and streaks

The rules live in `game/progression.py`.

* **Rating.** Rated games are AI games from the normal start position. The rating is Elo against the engine level played: easy counts as 450, medium 1200, hard 1850, master 2000. Medium is the starting rating; the gaps between the levels were measured in engine-against-engine matches with `scripts/engine_match.py`. K is 32 for a player's first 20 rated games, when the rating is shown as provisional, and 16 after. The floor is 100. Every change is stored in `RatingHistory`, linked to the game.
* **Rank.** A title for a band of rating: Pawn below 800, Knight from 800, Bishop from 1100, Rook from 1400, Queen from 1700, King from 2000.
* **Points (XP).** A rated game of at least 5 moves gives 30 for a win, 15 for a draw and 5 for a loss; a new puzzle 10, the daily puzzle 15 more, a lesson 25, an opening 50 (75 at 100% accuracy). Levels start at 0, 100, 250, 500, 1000, 1500, 2200 and 3000 XP.
* **Day streak.** Goes up on each day with a finished game of at least 5 moves, in the player's own time zone (the `tz` cookie set by `app.js`). Games resigned by the stale-game cleanup don't count. It reads `0` once a whole day passes without a game; the best streak is kept.
* **Leaderboard.** `/leaderboard/` needs a signed-in user and has two tables. The rating table lists players with at least one rated game, by rating. The puzzle table lists players who solved a puzzle, by puzzles solved and then best streak. Players level on a table share a place, each table shows the top 50, and a signed-in player outside them sees their own row below.
* **Profile.** `/profile/` shows the signed-in player's rating, rank, level and points, both streaks and their bests, and their results.


