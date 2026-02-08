# Checkora — AI Chess Platform

A high-performance hybrid chess platform with a Django backend, vanilla JavaScript frontend, and a C++ engine for move validation.

## Quick Start

### Prerequisites

- **Python 3.10+**
- **C++ compiler** (g++, clang++, or MSVC) — only needed to recompile the engine

### Setup

```bash
# Clone the repository
git clone https://github.com/Checkora/checkora.git
cd checkora

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser.

### Compiling the C++ Engine (Optional)

The platform includes a pure-Python fallback, so the C++ engine is optional. To compile it for faster validation:

```bash
# Windows (g++)
g++ -o game/engine/main.exe game/engine/main.cpp -O2

# macOS / Linux
g++ -o game/engine/main.out game/engine/main.cpp -O2
```

> **Note:** The compiled binary is not committed to the repo. Each contributor compiles for their own platform.

## Architecture

```
User Move → Frontend (JS) → Django Backend → C++ Engine → Validation → Backend → Frontend → UI Update
```

| Layer | Tech | Location |
|-------|------|----------|
| Frontend | HTML / CSS / Vanilla JS | `game/templates/game/board.html` |
| Backend | Django 6.0 | `game/views.py`, `game/engine.py` |
| Engine | C++ | `game/engine/main.cpp` |

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/` | Serve the board UI |
| `POST` | `/api/move/` | Validate and execute a move |
| `GET` | `/api/valid-moves/?row=&col=` | Get legal destinations for a piece |
| `POST` | `/api/new-game/` | Reset the game |

## Running Tests

```bash
python manage.py test game
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit format, and PR guidelines.

## License

See [LICENSE](LICENSE) for details.
