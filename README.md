<div align="center">

# Checkora

**An open-source chess platform with an AI opponent powered by minimax search with alpha-beta pruning.**

Built on Django with a high-performance C++ engine and a Python fallback for maximum compatibility.

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.x-092e20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![C++](https://img.shields.io/badge/Engine-C++17-00599c?style=flat&logo=c%2B%2B&logoColor=white)](https://isocpp.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-28%20passing-brightgreen?style=flat&logo=github-actions&logoColor=white)](#tests)
[![Issues](https://img.shields.io/github/issues/Checkora/Checkora?style=flat)](https://github.com/Checkora/Checkora/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat)](CONTRIBUTING.md)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/DvW3xVXw8g)

Join our Discord community for updates, support, and games: https://discord.gg/DvW3xVXw8g

### Core Maintainers

<table>
       <tr>
              <td align="center" style="padding: 6px 18px;">
                     <a href="https://github.com/EDWARD-012">
                            <img src="https://github.com/EDWARD-012.png?size=160" width="120" height="120" alt="EDWARD-012" style="border-radius: 50%; border: 3px solid #16A34A;" />
                     </a>
                     <br />
                     <a href="https://github.com/EDWARD-012"><strong>@EDWARD-012</strong></a>
                     <br />
                     <a href="https://github.com/EDWARD-012">
                            <img src="https://img.shields.io/badge/Follow-EDWARD--012-16A34A?style=for-the-badge&logo=github" alt="Follow EDWARD-012" />
                     </a>
              </td>
              <td align="center" style="padding: 6px 18px;">
                     <a href="https://github.com/triemerge">
                            <img src="https://github.com/triemerge.png?size=160" width="120" height="120" alt="triemerge" style="border-radius: 50%; border: 3px solid #16A34A;" />
                     </a>
                     <br />
                     <a href="https://github.com/triemerge"><strong>@triemerge</strong></a>
                     <br />
                     <a href="https://github.com/triemerge">
                            <img src="https://img.shields.io/badge/Follow-triemerge-16A34A?style=for-the-badge&logo=github" alt="Follow triemerge" />
                     </a>
              </td>
       </tr>
</table>

<sub>Click a profile or follow badge for release drops, roadmap notes, and engine updates.</sub>

</div>

---

## Table of contents 

- [Contributors](#contributors)
- [Features](#features)
- [Quick Start](#quick-start)
- [Testing Guide](#testing-guide)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Request/Response JSON Examples](#requestresponse-json-examples)
- [Tests](#tests)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Contributor Support & Feedback](#contributor-support--feedback)
- [Contributing](#contributing)
- [License](#license)

---

## Contributors

<!-- CONTRIBUTORS_START -->

<!-- CONTRIBUTORS_END -->

## Features

| Feature              | Description                                                                                         |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| AI Opponent          | Minimax search with alpha-beta pruning for challenging gameplay                                     |
| Hybrid Engine        | C++ binary for maximum speed with an automatic Python fallback                                      |
| Full Move Validation | Legal moves enforced for all pieces including castling, en passant, and promotion |
| Game Timer           | Per-player countdown clocks with pause support                                                      |
| Material Score Panel | Live material advantage tracking that updates dynamically during gameplay                           |
| REST API             | Clean JSON endpoints powering a decoupled frontend                                                  |
| PvP & PvE Modes      | Play against a friend or challenge the AI                                                           |

---

## Quick Start

**1. Clone the repository**
```bash
git clone https://github.com/Checkora/Checkora.git
cd Checkora
```

**2. Set up a virtual environment**

> **Note:** Django 6.0 requires Python 3.12 or higher. If you have multiple versions on Windows, use a compatible installed version, for example: `py -3.12 -m venv venv`.

**On Windows:**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

If you see the error *"Script execution is disabled on this system"*, run the following command in PowerShell before activating:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
This temporarily allows script execution for the current session. For more details, see the [Troubleshooting Guide](#troubleshooting-guide).

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Set up environment variables**

Copy the example environment file:
* **Windows (PowerShell):** `copy .env.example .env`
* **macOS / Linux:** `cp .env.example .env`

Open `.env` and configure:
* `SECRET_KEY` if needed.
* `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` for OTP and password reset emails.

**5. Run migrations and start the server**
```bash
python manage.py migrate
python manage.py runserver
```

Open **`http://127.0.0.1:8000/`** in your browser and start playing. The terminal shows this same address — always use **`http://`**, never **`https://`**, because the development server does not support SSL.

### Compile the C++ Engine _(optional but recommended)_

The compiled binary is not committed to the repository. Each contributor compiles for their own platform. If the binary is absent, Checkora automatically falls back to the Python engine.

```bash
# Windows
g++ -O2 game/engine/main.cpp -o game/engine/main.exe

# macOS / Linux
g++ -O2 game/engine/main.cpp -o game/engine/main
```

## Development Documentation

For detailed local development setup, environment configuration, common development commands, troubleshooting, and contributor workflow guidance, see:

- [Local Development Setup Guide](docs/development.md)

This guide expands on the Quick Start instructions and provides a complete development workflow for contributors.

## Testing Guide

For detailed testing instructions, see:

- [Testing & QA Guide](docs/testing.md)

This guide covers:

- Running unit tests
- Running Selenium tests
- Debugging test failures
- Contributor testing best practices

## Project Structure

Checkora follows a modular project structure to separate the frontend, backend, engine logic, and documentation clearly.

An exhaustive file-level overview of the entire repository is detailed below:

```text
Checkora/
├── .github/                       # GitHub configurations
│   ├── ISSUE_TEMPLATE/            # Issue blueprints for contributors
│   │   ├── bug_report.md          # Form for reporting software bugs
│   │   └── feature_request.md     # Form for proposing feature improvements
│   ├── workflows/                 # CI/CD automation pipelines
│   │   ├── ci.yml                 # Main test and lint automation workflow
│   │   ├── contributors.yml       # Automatically maintains the contributor catalog in README
│   │   └── label-gssoc.yml        # Automatically labels issues for GSSoC contributors
│   └── PULL_REQUEST_TEMPLATE.md   # PR template establishing code quality requirements
├── api/                           # Serverless API configurations
│   └── wsgi.py                    # Vercel-specific WSGI application configuration
├── core/                          # Django project core configuration
│   ├── __init__.py                # Package initialization marker
│   ├── asgi.py                    # Entry point for ASGI-compatible web servers
│   ├── settings.py                # Global settings (DB config, middleware, security headers)
│   ├── urls.py                    # Root URL router mapping to views
│   └── wsgi.py                    # Entry point for WSGI-compatible web servers
├── docs/                          # Detailed architecture guides
│   ├── API.md                     # Raw technical spec for REST API endpoints
│   ├── SECURITY_HEADERS_AUDIT.md  # Deep security analysis and policy audit reports
│   └── engine_architecture.md     # Detailed minimax and communication workflow analysis
├── game/                          # Core Chess application module
│   ├── engine/                    # The AI Chess engine directory
│   │   ├── main.cpp               # High-performance C++17 Minimax + Alpha-Beta pruning engine
│   │   ├── main.py                # Pure Python 3.12 fallback replica of the C++ engine
│   │   └── opening_book.json      # Structured dictionary mapping classic opening moves
│   ├── migrations/                # Database schema version histories
│   │   ├── 0001_initial.py        # Relational schema for GameResult and Profiles
│   │   ├── 0002_add_missing...   # Database schema patch adding draw reason records
│   │   ├── 0003_alter_game...     # Migration establishing foreign key user associations
│   │   ├── 0004_gameresult...     # Migration adding active game player color records
│   │   └── __init__.py            # Package initialization marker
│   ├── selenium_tests/            # UI browser integration tests
│   │   ├── __init__.py            # Package initialization marker
│   │   ├── base.py                # Setup, teardown, and WebDriver helpers for integration runs
│   │   ├── test_boards.py         # Automated UI click-and-drag gameplay flow tests
│   │   └── test_navigation.py     # Automated browser routing and navigation validation tests
│   ├── static/                    # Frontend client-side resources
│   │   └── game/                  # Main namespace directory
│   │       ├── css/               # Modular stylesheet templates
│   │       │   ├── 404.css        # Clean layout styles for page not found errors
│   │       │   ├── auth.css       # Forms and secure login layouts
│   │       │   ├── board.css      # Chessboard alignments, active highlights, and action panels
│   │       │   ├── landing.css    # Interactive hero screens and mode selectors
│   │       │   └── toast.css      # Custom popup and notification toaster styles
│   │       ├── js/                # Client-side dynamic scripts
│   │       │   ├── auth.js        # Validates dynamic auth form submissions
│   │       │   ├── board.js       # Chess grid events, capture drawers, API calls, clock tickers
│   │       │   └── toast.js       # Manages toast alert popups and life-cycles
│   │       ├── sounds/            # Gameplay sound effects
│   │       │   ├── capture.mp3    # Capture sound alert
│   │       │   ├── check.wav      # Check sound warning
│   │       │   ├── draw.mp3       # Game draw chime
│   │       │   └── move.wav       # Chess piece move tick
│   │       ├── checkora_icon_only.png # Project brand mark
│   │       └── favicon.jpeg       # Small browser favicon
│   ├── templates/                 # Server-side HTML render blueprints
│   │   ├── 404.html               # Custom 404 error page template
│   │   ├── robots.txt             # Web crawler configuration instructions
│   │   ├── sitemap.xml            # SEO indexing guide
│   │   └── game/                  # Namespace folder matching Django conventions
│   │       ├── includes/          # Reusable UI partial layout blocks
│   │       │   └── messages.html  # Banner rendering Django alert notifications
│   │       ├── board.html         # Interactive gameplay chessboard and player cards
│   │       ├── landing.html       # Mode lobby selection screen
│   │       ├── login.html         # Sign-in form interface
│   │       ├── register.html      # Create account interface
│   │       ├── verify_otp.html    # Two-factor verification panel
│   │       ├── rules.html         # Gameplay and chess educational rules guide
│   │       ├── stats.html         # User match metrics, profiles, and scoreboards
│   │       ├── welcome_email.html # HTML email template sent to users after successful registration
│   │       ├── password_reset.html # Password reset trigger page
│   │       ├── password_reset_complete.html # Confirmation of successful reset
│   │       ├── password_reset_confirm.html  # Verification form link target
│   │       ├── password_reset_done.html     # Outlines password email delivery status
│   │       ├── password_reset_email.html    # HTML layout for reset emails
│   │       └── password_reset_subject.txt   # Email subject text file
│   ├── __init__.py                # Package initialization marker
│   ├── apps.py                    # Django configuration class definition
│   ├── engine.py                  # Translates Python arrays to C++/Python subprocess stdin/stdout
│   ├── forms.py                   # Form validation classes for User registration and session keys
│   ├── icon.jpeg                  # Main project thumbnail graphic
│   ├── models.py                  # Database schemas mapping matches and profiles
│   ├── services.py                # Standalone functions managing core business logic
│   ├── tests.py                   # 80+ unit and integration test assertions
│   ├── urls.py                    # Application level router mapping endpoints
│   └── views.py                   # Django controller layer dispatching API and HTML requests
├── .env.example                   # Baseline local configuration variables blueprint
├── .gitignore                     # Configures Git to ignore builds, caches, and database logs
├── CODE_OF_CONDUCT.md             # Contributor environment code of conduct guidelines
├── CONTRIBUTING.md                # Guide detailing branch formats and pull request rules
├── LICENSE                        # Open-source MIT license deed
├── README.md                      # Primary project overview
├── requirements.txt               # Required Python packages
├── manage.py                      # Django CLI control center script
├── package.json                   # Specifies frontend tooling scripts
├── package-lock.json              # Locked frontend dependency version tree
├── structure.md                   # Extended architectural blueprint documentation
└── vercel.json                    # Configuration for serverless Django routing on Vercel
```

## Contributor Quick Reference

| Looking For        | Location                        |
| ------------------ | ------------------------------- |
| API Endpoints      | `game/views.py`, `game/urls.py` |
| Frontend Templates | `game/templates/`               |
| CSS Files          | `game/static/game/css/`         |
| JavaScript Files   | `game/static/game/js/`          |
| Images & Sounds    | `game/static/game/`             |
| Chess Engine       | `game/engine/`                  |
| Database Models    | `game/models.py`                |
| Forms              | `game/forms.py`                 |
| Business Logic     | `game/services.py`              |
| Unit Tests         | `game/tests.py`                 |
| Selenium Tests     | `game/selenium_tests/`          |
| Documentation      | `docs/`                         |
| Django Settings    | `core/settings.py`              |
| Root Routing       | `core/urls.py`                  |

## Directory Overview

### `core/`

Contains Django project configuration including settings, root URL routing, and WSGI/ASGI entry points.

### `game/`

Main application module containing gameplay logic, API endpoints, templates, static assets, models, forms, and tests.

### `game/engine/`

Contains the chess engine implementations, including the high-performance C++ engine and Python fallback engine.

### `docs/`

Project documentation covering APIs, architecture, security reviews, and contributor resources.

### `.github/`

Repository workflows, issue templates, pull request templates, and automation configuration.

## Architecture

Checkora uses a clean three-layer architecture:

```
Browser (JS/HTML/CSS)
       |
       v
Django Views (views.py)          <- HTTP request handling & session state
       |
       v
ChessGame Wrapper (engine.py)    <- Translates board state into engine commands
       |
       |---> C++ Binary (main.exe / main)   <- Primary: fast minimax AI
       +---> Python Script (main.py)        <- Fallback: identical logic in Python
```

| Layer             | Technology            | Path                              |
| ----------------- | --------------------- | --------------------------------- |
| Frontend          | HTML, CSS, JavaScript | `game/templates/game/board.html`  |
| Backend           | Django 6.x            | `game/views.py`, `game/engine.py` |
| Engine (Primary)  | C++17                 | `game/engine/main.cpp`            |
| Engine (Fallback) | Python 3.12+          | `game/engine/main.py`             |

> For a full deep-dive into the backend components, execution flow, and AI internals, see the [Architecture Guide](structure.md).

### How It Works

When a player makes a move, the request flows through three layers:

1. **Browser** sends a `POST` request with the move coordinates
2. **Django** (`views.py`) receives it and delegates to the `ChessGame` wrapper in `engine.py`
3. **`engine.py`** serializes the board into a flat 64-character string and spawns the engine as a subprocess, sending commands via `stdin` and reading responses from `stdout`

The engine speaks a simple text-based protocol:

| Command    | Example                                          | Response                                    |
| ---------- | ------------------------------------------------ | ------------------------------------------- |
| `VALIDATE` | `VALIDATE <board64> <rights> <turn> fr fc tr tc` | `VALID` / `INVALID <reason>`                |
| `MOVES`    | `MOVES <board64> <rights> <turn> row col`        | `MOVES tr tc is_capture is_promotion ...`   |
| `BESTMOVE` | `BESTMOVE <board64> <rights> <turn> <depth>`     | `BESTMOVE fr fc tr tc`                      |
| `STATUS`   | `STATUS <board64> <rights> <turn>`               | `STATUS CHECK / CHECKMATE / STALEMATE / OK` |

```mermaid
flowchart TD
    A[Browser\nJS / HTML] -->|HTTP POST /api/move/| B[Django Views\nviews.py]
    B -->|delegates to| C[ChessGame Wrapper\nengine.py]
    C -->|board64 + command via stdin| D{Engine}
    D -->|C++ binary\nmain.exe / main| E[Minimax + Alpha-Beta\nPrimary]
    D -->|Python fallback\nmain.py| F[Minimax + Alpha-Beta\nFallback]
    E -->|response via stdout| C
    F -->|response via stdout| C
    C -->|updated state| B
    B -->|JSON response| A
```

---

## API Reference

Checkora features a decoupled API layer. Below is the endpoint catalog accompanied by explicit request and response structures to assist frontend integrations.

> [!NOTE]
> All state-modifying requests (`POST`) require a CSRF token passed via the `X-CSRFToken` HTTP header, except for `/api/pause/` which is CSRF-exempt to support page close events via `navigator.sendBeacon`.

| Method | Endpoint | Description | Request Example |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Render the board UI | *N/A (Standard HTML Page)* |
| `GET` | `/api/state/` | Retrieve full game state from session | `/api/state/` |
| `POST` | `/api/move/` | Execute a move on the board | `/api/move/` |
| `GET` | `/api/valid-moves/` | Get all legal moves for a selected piece | `/api/valid-moves/?row=6&col=4` |
| `POST` | `/api/new-game/` | Start a new PvP or PvE game | `/api/new-game/` |
| `GET` | `/api/check-promotion/` | Check if a pawn reaches the promotion rank | `/api/check-promotion/?from_row=1&from_col=0&to_row=0` |
| `POST` | `/api/ai-move/` | Request the engine to compute the best move | `/api/ai-move/` |
| `POST` | `/api/pause/` | Pause/Resume game timer countdown | `/api/pause/` |
| `POST` | `/api/resume/` | Resume a previously saved game | `/api/resume/` |
| `POST` | `/api/resign/` | Resign the current game | `/api/resign/` |
| `POST` | `/api/draw/` | Offer or accept a draw in PvP mode | `/api/draw/` |
| `GET` | `/api/check-username/` | Check if a username is available | `/api/check-username/?username=player1` |
| `POST` | `/api/analyze-game/` | Analyze a completed game and return statistics | `/api/analyze-game/` |
| `GET` | `/api/puzzle-stats/` | Retrieve puzzle streak and statistics | `/api/puzzle-stats/` |
| `POST` | `/api/cron/cleanup-stale-games/` | Secure cron-triggered cleanup for abandoned games | `/api/cron/cleanup-stale-games/` |

---

### Request/Response JSON Examples

#### 1. Retrieve Game State (`GET /api/state/`)
Called on board load to restore ongoing match positions and clocks.

**Response (Success - `200 OK`):**

```json
{
  "board": [
    ["r", "n", "b", "q", "k", "b", "n", "r"],
    ["p", "p", "p", "p", "p", "p", "p", "p"],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null],
    ["P", "P", "P", "P", "P", "P", "P", "P"],
    ["R", "N", "B", "Q", "K", "B", "N", "R"]
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

#### 2. Execute a Move (`POST /api/move/`)
Triggered when a player releases a piece onto a destination square.

**Request Body:**

*Note: `promotion_piece` is optional ("q", "r", "b", "n") and required only if `check-promotion` is true.*

```json
{
  "from_row": 6,
  "from_col": 4,
  "to_row": 4,
  "to_col": 4,
  "promotion_piece": "q"
}
```

**Response (Success - `200 OK`):**

*Note: `board` is an 8x8 array reflecting the updated state. `game_status` can be "active", "check", "checkmate", "stalemate", or "draw".*

```json
{
  "valid": true,
  "message": "Move successful",
  "captured": null,
  "board": [],
  "current_turn": "black",
  "white_time": 595,
  "black_time": 600,
  "move_history": [
    {"notation": "e4", "piece": "P", "from": [6, 4], "to": [4, 4], "color": "white"}
  ],
  "captured_pieces": {"white": [], "black": []},
  "game_status": "active"
}
```

**Response (Error - `400 Bad Request` / `200 OK` with invalid):**

```json
{
  "valid": false,
  "message": "Invalid move: King would be in check"
}
```

#### 3. Get Valid Moves (`GET /api/valid-moves/`)
Instructs the frontend UI where the selected piece can legally go.

**Request Parameters:** `?row=6&col=4`

**Response (Success - `200 OK`):**

```json
{
  "valid_moves": [
    {"row": 5, "col": 4, "is_capture": false},
    {"row": 4, "col": 4, "is_capture": false}
  ]
}
```

#### 4. Request AI Move (`POST /api/ai-move/`)
Triggers background minimax engine search. Returns the move calculated by the C++/Python engine.

**Response (Success - `200 OK`):**

*Note: `board` is an 8x8 array reflecting the updated state. `move_history` contains the list of moves.*

```json
{
  "valid": true,
  "message": "Move successful",
  "captured": "p",
  "board": [],
  "current_turn": "white",
  "white_time": 600,
  "black_time": 598,
  "move_history": [],
  "captured_pieces": {"white": ["p"], "black": []},
  "ai_move": {
    "from_row": 1,
    "from_col": 3,
    "to_row": 3,
    "to_col": 3
  },
  "game_status": "active"
}
```

#### 5. Start New Game (`POST /api/new-game/`)
Resets current session variables and starts a fresh match.

**Request Body:**

*Note: `mode` can be "pvp" or "ai".*

```json
{
  "mode": "ai"
}
```

**Response (Success - `200 OK`):**

*Note: `board` is an 8x8 array containing the clean initial board configuration.*

```json
{
  "board": [],
  "current_turn": "white",
  "move_history": [],
  "captured_pieces": {"white": [], "black": []},
  "mode": "ai"
}
```

#### 6. Analyze Game (`POST /api/analyze-game/`)
Analyzes a completed game based on its move history and returns statistics.

**Request Body:**

```json
{
  "moves": ["e4", "e5", "Nf3", "Nc6"],
  "result": "White wins",
  "reason": "checkmate"
}
```

**Response (Success - `200 OK`):**

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

#### 7. Get Puzzle Stats (`GET /api/puzzle-stats/`)
Returns puzzle streak information for the puzzle interface.

**Response (Success - `200 OK`):**

```json
{
  "streak": 0,
  "longest_streak": 0
}
```

#### 8. Cleanup Cron (`POST /api/cron/cleanup-stale-games/`)
Secure cron-triggered cleanup endpoint for abandoned games.

**Request Headers:**

```http
Authorization: Bearer <cron_secret>
```

**Response (Success - `200 OK`):**

```json
{
  "status": "success",
  "deleted_games": 2,
  "resigned_games": 1
}
```

---

## Tests

The test suite runs fully in-memory — no compiled engine binary required.

```bash
python manage.py test game
```

28 tests covering all API endpoints, move validation, engine path resolution, promotion logic, and AI mode enforcement.

---

## Troubleshooting Guide

Below are solutions to common setup, installation, and environment issues contributors encounter when getting Checkora running locally.

### 🐍 1. Python Version Mismatch
Django 6.x is built on modern Python paradigms and strictly requires **Python 3.12 or higher**. If you run an older version, dependencies in `requirements.txt` will fail to resolve or throw syntax errors during server boot.

*   **Check version:**
    ```bash
    python --version
    ```
*   **Resolution (Windows multiple installations):**
    Use the Python Launcher to explicitly target 3.12+ when creating your virtual environment:
    ```bash
    py -3.12 -m venv venv
    ```
*   **Resolution (macOS/Linux):**
    Ensure `python3` points to a 3.12+ installation (e.g., via Homebrew: `brew install python@3.12`).

### 📦 2. Virtual Environment Activation Issues
Depending on your terminal shell or system policies, activating the virtual environment might throw permission or script execution errors.

*   **Windows PowerShell execution restriction error:**
    If you see an error like `Script execution is disabled on this system`, bypass the policy for the active process:
    ```powershell
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    venv\Scripts\Activate.ps1
    ```
*   **Activation commands for different shells:**

    | Shell | Command |
    | :--- | :--- |
    | **Windows Cmd** | `venv\Scripts\activate.bat` |
    | **Windows PowerShell** | `venv\Scripts\Activate.ps1` |
    | **Git Bash / WSL / Linux / macOS** | `source venv/bin/activate` |
    | **Fish Shell** | `source venv/bin/activate.fish` |

### 🛠️ 3. g++ Compiler Installation & Configuration Problems
Checkora attempts to compile the C++ chess engine locally to maximize Minimax performance. If `g++` is missing or not configured correctly, it will throw compilation errors. 

> [!TIP]
> If `g++` setup is too tricky for your system, you can skip compiling it! Checkora will automatically detect the absence of the binary and fall back to the Python engine in `game/engine/main.py`.

*   **Check compiler availability:**

    ```bash
    g++ --version
    ```
*   **Resolution (Windows):**
    1. Download the MinGW-w64 compiler suite (we recommend the simple, portable [w64-devkit](https://github.com/skeeto/w64-devkit)).
    2. Add the `bin` directory (containing `g++.exe`) to your system's **Environment Variables** -> **PATH** list.
    3. Restart your terminal so the new path takes effect.
*   **Resolution (macOS):**
    Install the Xcode Command Line Tools:

    ```bash
    xcode-select --install
    ```
*   **Resolution (Ubuntu/Debian Linux):**

    ```bash
    sudo apt update && sudo apt install build-essential
    ```

### 💾 4. Database Migration Errors
If migrations fail to run, or database models get out of sync, you may encounter relational database exceptions.

*   **Resolution:**
    Reset your local SQLite database structure by running:

    ```bash
    # 1. Generate any missing database schema blueprints
    python manage.py makemigrations game
    
    # 2. Safely apply schema blueprints
    python manage.py migrate
    ```
    *If conflicts persist, delete the local `db.sqlite3` file and re-run the commands above to construct a clean database.*

### 🔑 5. Missing `.env` Configuration File
If you attempt to launch the Django server without setting up a local configuration file, Django will throw `KeyError` or configuration load failures for crucial settings.

*   **Resolution:**
    Ensure you clone the template configuration into a new active `.env` file in the root directory:

    ```bash
    # Windows PowerShell
    copy .env.example .env
    
    # macOS / Linux
    cp .env.example .env
    ```
    Open `.env` and verify you have a robust string under `SECRET_KEY`.
    Additionally, ensure `TRUSTED_PROXIES` is configured (defaulting to
    `127.0.0.1,::1` for local development).
    Similarly, `TRUSTED_PROXY_IPS` must be configured for password reset rate limiting.

    > **⚠️ Security Warning for Production:**
    > When deploying behind reverse proxies (Vercel, Cloudflare, AWS ALB,
    > etc.), you must set `TRUSTED_PROXIES` to your platform's upstream
    > proxy IPs. Incorrect configuration allows attackers to spoof their
    > IP address and bypass rate limiting entirely.
    > Furthermore, `TRUSTED_PROXY_IPS` must be set in production to enforce proxy validation
    > for password reset rate limiting. If `TRUSTED_PROXY_IPS` is empty in production,
    > the server will raise an `ImproperlyConfigured` exception and fail to start.

### 🔌 6. Port Conflicts (Port 8000 Already in Use)
If you already have another service running on your local port 8000, Django will fail to bind and throw `Error: That port is already in use.`

*   **Resolution:**
    Instruct Django to boot the local server on an alternative unoccupied port, for example, `8080` or `8001`:

    ```bash
    python manage.py runserver 8080
    ```

### 🔒 7. Local SSL Error (`ERR_SSL_PROTOCOL_ERROR`)

If the browser shows `ERR_SSL_PROTOCOL_ERROR` or the terminal prints *"You're accessing the development server over HTTPS, but it only supports HTTP"*, the browser is using HTTPS against the local HTTP dev server.

*   **Resolution:**
    1. Copy the example env file if you have not already: `copy .env.example .env` (Windows) or `cp .env.example .env` (macOS/Linux).
    2. Copy the exact URL from the terminal, for example **`http://127.0.0.1:8000/`** — include `http://` and do not let the browser change it to `https://`.
    3. Disable your browser's HTTPS-upgrade setting for local development (for example, Chrome/Brave: "Always use secure connections" / "Upgrade connections to HTTPS").
    4. Clear cached HSTS for `127.0.0.1` if the browser keeps forcing HTTPS (Chrome/Brave: `chrome://net-internals/#hsts`; steps vary by browser).

## Contributor Support & Feedback

We want your contribution journey with Checkora to be smooth, welcoming, and productive! If you hit roadblocks or have ideas, please utilize the following channels:

### 💬 1. Join our Discord Community
Our central hub for live discussions, playtesting matches, roadmap announcements, and direct maintainer support.
- **Invite Link:** [Join the Checkora Discord Server](https://discord.gg/DvW3xVXw8g)
- **Active Channels:**
  - `#setup-help`: For environment, dependencies, or local compilation challenges.
  - `#engine-chat`: For deep-dives into minimax heuristics, board representation, and alpha-beta pruning.
  - `#suggestions`: For sharing your design mocks, UI improvements, or gameplay feature proposals.

### ❓ 2. Ask Setup & Installation Questions
If you prefer forum-style threading over live Discord chat:
- Open a question on our [GitHub Discussions page](https://github.com/Checkora/Checkora/discussions) under the **Q&A / Help** category.
- Search prior threads; many common setups or dependencies are documented by fellow contributors.

### 📚 3. Report Documentation Confusion
If a section of this guide, `structure.md`, or `API.md` is unclear, out of date, or missing steps:
- File a [GitHub Issue](https://github.com/Checkora/Checkora/issues/new) using the **Documentation Confusion** template or attach the `documentation` label.
- *Better yet:* Submit a quick pull request correcting the text! We love docs-focused contributions.

### 💡 4. Share Feature Proposals & Suggestions
Want to introduce a new gameplay timer format, customize themes, or build a matching lobby?
- Share your proposals in [GitHub Discussions Ideas](https://github.com/Checkora/Checkora/discussions/categories/ideas).
- Align with core maintainers (@EDWARD-012 & @triemerge) before writing significant logic to ensure architectural compatibility.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming conventions, commit message format, and PR guidelines before submitting.

---

## License

Released under the [MIT License](LICENSE).
