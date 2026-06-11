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

## 15. Get Daily Puzzle

Retrieves the daily chess puzzle corresponding to the current date. If no puzzle is assigned to the current date, the endpoint falls back to a rotating puzzle from the database. If no puzzles exist, a default puzzle is returned.

* **URL:** `/api/puzzles/daily/`
* **Method:** `GET`
* **Auth Required:** No
* **Request Params:** None
* **Success Response:**

  ```json
  {
    "id": 42,
    "title": "Mate in Two",
    "fen": "8/8/8/8/8/8/8/8 w - - 0 1",
    "solution": ["Qh7#"],
    "difficulty": "easy"
  }
  ```
* **Fallback Response (No Puzzles Available):**

  ```json
  {
    "id": 0,
    "title": "Default Puzzle",
    "fen": "6k1/5ppp/8/8/8/8/5PPP/6KQ w - - 0 1",
    "solution": ["g2g4"],
    "difficulty": "medium"
  }
  ```

---

## 16. Complete Lesson

Marks a lesson as completed for the authenticated user and awards XP for the first completion.

* **URL:** `/lessons/<lesson_name>/complete/`
* **Method:** `POST`
* **Auth Required:** Yes
* **CSRF Required:** Yes
* **Request Body:** None
* **Success Response:** Redirects to the lesson detail page for the completed lesson.
* **Behavior:**

  * Resolves lesson aliases to their canonical lesson names.
  * Records completion status and completion timestamp.
  * Awards 25 XP if the lesson has not been completed previously.
* **Error Response:**

  ```text
  Lesson not found
  ```

  * **Status Code:** `404 Not Found`

---

## 17. Download Achievement Badge

Generates and returns a downloadable PNG badge image for an unlocked achievement.

* **URL:** `/achievement/<achievement_id>/download/`
* **Method:** `GET`
* **Auth Required:** Yes
* **Request Params:** None
* **Success Response:** Returns a downloadable PNG file attachment.
* **Error Response (Achievement Not Found):**

  * **Status Code:** `404 Not Found`
* **Error Response (Badge Generation Failure):**

  ```text
  Badge generation failed.
  ```

  * **Status Code:** `500 Internal Server Error`

---

## 18. Feature Achievement Badge

Adds an unlocked achievement badge to the user's featured badge collection.

* **URL:** `/feature-badge/<achievement_id>/`
* **Method:** `GET`
* **Auth Required:** Yes
* **Request Params:** None
* **Success Response:** Redirects to the achievements page and displays:

  ```text
  Badge featured successfully.
  ```
* **Error Response (Achievement Not Unlocked):**

  ```text
  You can only feature unlocked badges.
  ```
* **Error Response (Maximum Featured Badges Reached):**

  ```text
  You can only feature up to 3 badges.
  ```
* **Notes:**

  * Maximum featured badges per user: 3.
  * Duplicate requests do not create duplicate featured badges.

---

## 19. Remove Featured Badge

Removes a badge from the authenticated user's featured badge collection.

* **URL:** `/remove-featured-badge/<badge_id>/`
* **Method:** `GET`
* **Auth Required:** Yes
* **Request Params:** None
* **Success Response:** Redirects to the achievements page and displays:

  ```text
  Featured badge removed.
  ```
* **Notes:**

  * Only badges belonging to the authenticated user can be removed.
  * Missing badges are ignored without raising an error.

---

## 20. Cleanup Stale Games (Internal)

Administrative endpoint used by scheduled jobs to clean abandoned game sessions and resign inactive players.

* **URL:** `/api/cron/cleanup-stale-games/`
* **Method:** `POST`
* **Auth Required:** Bearer Token
* **CSRF Required:** No (`@csrf_exempt`)
* **Request Body:** None
* **Required Header:**

  ```http
  Authorization: Bearer <CRON_SECRET>
  ```
* **Success Response:**

  ```json
  {
    "status": "success",
    "deleted_games": 12,
    "resigned_games": 4
  }
  ```
* **Error Response (Unauthorized):**

  ```json
  {
    "error": "Unauthorized"
  }
  ```

  * **Status Code:** `401 Unauthorized`
* **Error Response (Server Error):**

  ```json
  {
    "status": "error",
    "message": "<error details>"
  }
  ```

  * **Status Code:** `500 Internal Server Error`

---

## 21. Password Reset Account Selection

Displays all accounts associated with an email address during the password reset workflow.

* **URL:** `/password-reset-account-selection/`
* **Method:** `GET`
* **Auth Required:** No
* **Request Params:** `?email=user@example.com`
* **Success Response:** Renders the password reset account selection page.
* **Template:** `game/password_reset_account_selection.html`
* **Context Variables:**

  * `users` — matching accounts.
  * `email` — supplied email address.

---

## 22. Verify OTP

Verifies the registration OTP and activates the user account.

* **URL:** `/verify-otp/`
* **Method:** `GET`, `POST`
* **Auth Required:** No
* **Request Params (GET):** None
* **Request Body (POST):**

  ```text
  otp=<6-digit-code>
  ```
* **Success Behavior:**

  * Validates OTP hash.
  * Activates the user account.
  * Sends a welcome email.
  * Logs the user in.
  * Cycles the session key.
  * Clears registration session data.
  * Redirects to the home page.
* **Error Response (Expired OTP):**

  ```text
  OTP has expired. Please register again.
  ```

  * Redirects to `/register/`
* **Error Response (Invalid OTP):**

  ```text
  Invalid OTP. Please try again.
  ```
* **Error Response (Too Many Attempts):**

  ```text
  Too many incorrect attempts. Please register again.
  ```

  * Redirects to `/register/`
* **Error Response (User Not Found):**

  ```text
  User not found. Please register again.
  ```

  * Redirects to `/register/`
* **Notes:**

  * OTP expires after 300 seconds.
  * Maximum failed attempts: 5.
  * OTP values are stored as SHA-256 hashes.

---

## 23. Resend OTP

Generates and sends a new OTP during account registration.

* **URL:** `/resend-otp/`
* **Method:** `POST`
* **Auth Required:** No
* **CSRF Required:** Yes
* **Request Body:** None
* **Success Response:** Redirects to `/verify-otp/` and displays:

  ```text
  A new OTP has been sent to your email.
  ```
* **Error Response (Session Expired):**

  ```text
  Session expired. Please register again.
  ```

  * Redirects to `/register/`
* **Error Response (Rate Limited):**

  ```text
  Please wait <n> seconds before requesting a new OTP.
  ```

  * Redirects to `/verify-otp/`
* **Error Response (Email Failure):**

  ```text
  Failed to resend OTP. Please try again.
  ```

  * Redirects to `/verify-otp/`
* **Notes:**

  * OTP requests are limited to one request every 60 seconds.
  * Newly generated OTPs replace previously issued OTPs.

---

## 24. Delete Account

Initiates the account deletion workflow by sending a confirmation email.

* **URL:** `/delete-account/`
* **Method:** `GET`, `POST`
* **Auth Required:** Yes
* **Request Params (GET):** None
* **Request Body (POST):**

  ```text
  username=<username>
  password=<password>
  ```
* **Success Response:** Sends a confirmation email and redirects to the home page.
* **Success Message:**

  ```text
  Confirmation email sent to your registered email.
  ```
* **Error Response (Invalid Credentials):**

  ```text
  Invalid username or password.
  ```
* **Error Response (Email Failure):**

  ```text
  Failed to send confirmation email.
  ```
* **Notes:**

  * The account is not deleted during this step.
  * Deletion requires email confirmation.

---

## 25. Confirm Account Deletion

Validates a secure deletion token and permanently removes the user account.

* **URL:** `/confirm-delete/<uidb64>/<token>/`
* **Method:** `GET`
* **Auth Required:** No
* **Request Params:** None
* **Success Response:** Logs out the user, deletes the account, and renders:

  ```text
  game/delete_success.html
  ```
* **Error Response:**

  ```text
  Invalid or expired deletion link.
  ```

  * Redirects to the landing page.
* **Notes:**

  * User identity is validated using `uidb64`.
  * Token validation uses Django's `default_token_generator`.
  * Account deletion is permanent.


Final confirmation endpoint for permanent account deletion.

* **URL:** `/confirm-delete/<uidb64>/<token>/`
* **Method:** `GET`
* **Auth Required:** No

### Parameters

| Parameter | Description             |
| --------- | ----------------------- |
| uidb64    | Encoded user identifier |
| token     | Secure deletion token   |

### Purpose

Validates the deletion token and permanently removes the account.

### Success Response

Renders a confirmation page and deletes the account if the token is valid.

### Possible Error Cases

* Invalid token
* Expired token
* User not found
* Already deleted account

---
---
