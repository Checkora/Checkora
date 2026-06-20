# Checkora API Reference Guide

This document outlines the REST API endpoints used by the Checkora frontend to communicate with the Django backend. Most requests that modify state require a CSRF token in the headers (`X-CSRFToken`). Exceptions are documented in the Authentication & Security section below.

---

## Authentication & Security

Most POST endpoints require a valid CSRF token supplied through the `X-CSRFToken` header.

Exceptions:

* `/api/pause/`
* `/api/analyze-game/`
* `/api/cron/cleanup-stale-games/`

These endpoints are exempt from CSRF validation.

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

### Analysis APIs
- Analyze Game

### Puzzle APIs
- Get Puzzle Stats
- Get Daily Puzzle

### User APIs
- Check Username Availability

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
      "board": [
        ["r", "n", "b", "q", "k", "b", "n", "r"],
        [null, null, null, null, null, null, null, null]
      ],
      "current_turn": "white",
      "white_time": 600,
      "black_time": 600,
      "paused": true,
      "move_history": [
        {
          "notation": "e4",
          "piece": "P",
          "from": [6, 4],
          "to": [4, 4],
          "color": "white"
        }
      ],
      "captured_pieces": {
        "white": [],
        "black": []
      },
      "mode": "pvp",
      "time_limit": 600,
      "increment": 5,
      "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "pgn": "[Event \"Checkora Game\"]",
      "game_status": "active",
      "draw_reason": null,
      "threefold_warning": false,
      "player_color": "white",
      "white_name": "White",
      "black_name": "Black"
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
      "promotion_piece": "q"
    }
    ```

    `promotion_piece` is optional and only required for pawn promotion.
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
      "game_status": "active",
      "time_limit": 600,
      "increment": 5,
      "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "pgn": "[Event \"Checkora Game\"]",
      "draw_reason": null,
      "threefold_warning": false,
      "player_color": "white",
      "white_name": "White",
      "black_name": "Black"
    }
    ```

    Possible values for `game_status`:
    - `active`
    - `check`
    - `checkmate`
    - `stalemate`
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

* **URL:** `/api/new-game/`
* **Method:** `POST`

### Request Parameters

| Parameter    | Type    | Required | Description                                              |
| ------------ | ------- | -------- | -------------------------------------------------------- |
| mode         | string  | No       | Game mode: `"pvp"` or `"ai"`                             |
| difficulty   | string  | No       | AI difficulty level. Default: `"medium"`                 |
| fen          | string  | No       | FEN position to initialize the board from                |
| time_limit   | integer | No       | Initial clock time in seconds for each player            |
| increment    | integer | No       | Increment (seconds added after each move)                |
| player_color | string  | No       | Human player's color in AI mode (`"white"` or `"black"`) |
| white_name   | string  | No       | Display name for White                                   |
| black_name   | string  | No       | Display name for Black                                   |

### Example Request Body

```json
{
  "mode": "ai",
  "difficulty": "medium",
  "time_limit": 300,
  "increment": 3,
  "player_color": "white",
  "white_name": "Alice",
  "black_name": "Checkora AI",
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
  "black_name": "Checkora AI",
  "difficulty": "medium",
  "time_limit": 300,
  "increment": 3,
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "pgn": "",
  "game_status": "active",
  "draw_reason": null
}
```

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
      "game_status": "active",
      "time_limit": 600,
      "increment": 5,
      "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "pgn": "[Event \"Checkora Game\"]",
      "draw_reason": null,
      "threefold_warning": false,
      "player_color": "white",
      "white_name": "White",
      "black_name": "Black"
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
      "pause": true
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
      "game_status": "draw_agreement",
      "draw_reason": "agreement"
    }
    ```

*   **Success Response (decline):**

    ```json
    {
      "success": true
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
  "solution": ["g2g4"],
  "difficulty": "medium"
}
```

**Notes:**

* Returns the puzzle selected for the current date.
* Falls back to a default puzzle when no dated puzzle exists.
* Used by the Daily Puzzle feature in the frontend.

---

## 16. Cleanup Stale Games

Administrative endpoint used to clean abandoned or inactive games.

* **URL:** `/api/cron/cleanup-stale-games/`
* **Method:** `POST`
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
  "resigned_games": 3
}
```

* **Unauthorized Response:**

```json
{
  "error": "Unauthorized"
}
```

**Status Code:** `401 Unauthorized`

**Notes:**

* Intended for scheduled maintenance jobs.
* Automatically cleans stale game sessions.
* Should not be called directly from the frontend.

---

## 17. Common Error Responses

Different endpoints may return different error payloads depending on the operation being performed. The examples below illustrate common error patterns used throughout the API but do not represent a guaranteed response schema for every endpoint.

### 400 Bad Request

```json
{
  "error": "Invalid request data"
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

### 500 Internal Server Error

```json
{
  "error": "Internal server error"
}
```

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
* Username or email conflicts.
* OTP delivery failure.

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
* **Methods:** `GET`
* **Authentication:** Public

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
* Redirects to `/home/`.

**Security Notes**

* Username-based lockout protection.
* IP-based lockout protection.
* Session fixation protection via session key rotation.

---

### 5. Logout

Ends the current authenticated session.

* **URL:** `/logout/`
* **Methods:** `GET`
* **Authentication:** Authenticated user

**Success Behavior**

* Logs out the current user.
* Redirects to `/home/`.

