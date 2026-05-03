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
