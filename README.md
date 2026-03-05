# Checkora

Chess platform with an AI opponent powered by minimax search with alpha-beta pruning, built on Django and a C++ engine.

## Setup

```bash
git clone https://github.com/Checkora/checkora.git
cd checkora
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

### Compile the Engine

The compiled binary is not committed. Each contributor compiles for their own platform.

```bash
# Windows
g++ -O2 game/engine/main.cpp -o game/engine/main.exe

# macOS / Linux
g++ -O2 game/engine/main.cpp -o game/engine/main
```

## Architecture

```
Frontend (JS) -> Django -> C++ Engine -> Django -> Frontend
```

| Layer | Tech | Path |
|-------|------|------|
| Frontend | HTML, CSS, JS | `game/templates/game/board.html` |
| Backend | Django 6.0 | `game/views.py`, `game/engine.py` |
| Engine | C++ | `game/engine/main.cpp` |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Board UI |
| POST | `/api/move/` | Execute a move |
| GET | `/api/valid-moves/` | Legal moves for a piece |
| POST | `/api/new-game/` | Start a new game |
| GET | `/api/check-promotion/` | Check if a move triggers promotion |
| GET | `/api/state/` | Current game state |
| POST | `/api/pause/` | Pause or resume the game |
| POST | `/api/ai-move/` | Get AI move |

## Tests

```bash
python manage.py test game
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
