<div align="center">

# Checkora

**An open-source chess platform with an AI opponent powered by minimax search with alpha-beta pruning.**

Built on Django with a high-performance C++ engine and a Python fallback for maximum compatibility.

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-092e20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
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

## Features

| Feature | Description |
|---------|-------------|
| AI Opponent | Minimax search with alpha-beta pruning for challenging gameplay |
| Hybrid Engine | C++ binary for maximum speed with an automatic Python fallback |
| Full Move Validation | Legal moves enforced for all pieces including castling and promotion (en passant pending — see #88) |
| Game Timer | Per-player countdown clocks with pause support |
| REST API | Clean JSON endpoints powering a decoupled frontend |
| PvP & PvE Modes | Play against a friend or challenge the AI |

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Checkora/Checkora.git
cd Checkora

# 2. Set up a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
# Copy example env file
# Windows (PowerShell)
copy .env.example .env

# macOS / Linux
cp .env.example .env

# Open `.env` and set SECRET_KEY if needed

# 5. Run migrations and start the server
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser and start playing.

### Compile the C++ Engine *(optional but recommended)*

The compiled binary is not committed to the repository. Each contributor compiles for their own platform. If the binary is absent, Checkora automatically falls back to the Python engine.

```bash
# Windows
g++ -O2 game/engine/main.cpp -o game/engine/main.exe

# macOS / Linux
g++ -O2 game/engine/main.cpp -o game/engine/main
```

---

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

| Layer | Technology | Path |
|-------|-----------|------|
| Frontend | HTML, CSS, JavaScript | `game/templates/game/board.html` |
| Backend | Django 5.x | `game/views.py`, `game/engine.py` |
| Engine (Primary) | C++17 | `game/engine/main.cpp` |
| Engine (Fallback) | Python 3.10+ | `game/engine/main.py` |

> For a full deep-dive into the backend components, execution flow, and AI internals, see the [Architecture Guide](structure.md).

### How It Works

When a player makes a move, the request flows through three layers:

1. **Browser** sends a `POST` request with the move coordinates
2. **Django** (`views.py`) receives it and delegates to the `ChessGame` wrapper in `engine.py`
3. **`engine.py`** serializes the board into a flat 64-character string and spawns the engine as a subprocess, sending commands via `stdin` and reading responses from `stdout`

The engine speaks a simple text-based protocol:

| Command | Example | Response |
|---|---|---|
| `VALIDATE` | `VALIDATE <board64> <rights> <turn> fr fc tr tc` | `VALID` / `INVALID <reason>` |
| `MOVES` | `MOVES <board64> <rights> <turn> row col` | `MOVES tr tc is_capture is_promotion ...` |
| `BESTMOVE` | `BESTMOVE <board64> <rights> <turn> <depth>` | `BESTMOVE fr fc tr tc` |
| `STATUS` | `STATUS <board64> <rights> <turn>` | `STATUS CHECK / CHECKMATE / STALEMATE / OK` |

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

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Render the board UI |
| `POST` | `/api/move/` | Execute a player move |
| `GET` | `/api/valid-moves/` | Get legal moves for a piece |
| `POST` | `/api/new-game/` | Start a new game (PvP or PvE) |
| `GET` | `/api/check-promotion/` | Check if a move triggers pawn promotion |
| `GET` | `/api/state/` | Retrieve the full current game state |
| `POST` | `/api/pause/` | Pause or resume the game clock |
| `POST` | `/api/ai-move/` | Request and execute an AI move |

---

## Tests

The test suite runs fully in-memory — no compiled engine binary required.

```bash
python manage.py test game
```

28 tests covering all API endpoints, move validation, engine path resolution, promotion logic, and AI mode enforcement.

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming conventions, commit message format, and PR guidelines before submitting.

---

## License

Released under the [MIT License](LICENSE).
