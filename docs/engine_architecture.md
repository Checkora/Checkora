# Checkora Engine Architecture

## Overview
Checkora uses a C++ chess engine for AI move generation and validation, coordinated through Django via subprocess communication.

## System Architecture
Browser (JS/HTML/CSS)
|
v
Django Views (views.py)
|
v
ChessGame Manager (game/engine.py)
|
|---> Opening Book (engine/opening_book.json)
|
v
C++ Binary (engine/main.exe or main)
|
v
Python Fallback (engine/main.py)

## Django to C++ Communication

Django communicates with the C++ engine via **stdin/stdout** using subprocess:

```python
proc = subprocess.Popen(
    engine_path,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)
stdout, _ = proc.communicate(input=command, timeout=5)
```

## Command Protocol

| Command | Purpose | Example |
|---------|---------|---------|
| `MOVES` | Get valid moves for a piece | `MOVES <board> <castling> <turn> <ep> <row> <col>` |
| `BESTMOVE` | Get AI best move | `BESTMOVE <board> <castling> <turn> <ep> <depth> [time_budget_ms]` |
| `STATUS` | Get game status | `STATUS <board> <castling> <turn> <ep>` |
| `PROMOTE` | Handle pawn promotion | `PROMOTE <board> <castling> <turn> <ep> <fr> <fc> <tr> <tc> <piece>` |
| `NOTATION` | Generate SAN notation | `NOTATION <board> <castling> <turn> <ep> <fr> <fc> <tr> <tc>` |

## Board Representation

The board is serialized as a **64-character string**:
- Uppercase = White pieces (K, Q, R, B, N, P)
- Lowercase = Black pieces (k, q, r, b, n, p)
- `.` = Empty square

rnbqkbnr
pppppppp
........
........
........
........
PPPPPPPP
RNBQKBNR

## Minimax Algorithm

The C++ engine uses **Minimax with Alpha-Beta Pruning**:

Minimax(position, depth, alpha, beta)
if depth == 0: return evaluate(position)

for each move:
    score = Minimax(next_position, depth-1, alpha, beta)
    alpha-beta pruning to cut unnecessary branches

return best score
### Search Depth
| Game Phase | C++ Depth | Python Depth |
|------------|-----------|--------------|
| Opening/Middlegame | 4 | 3 |
| Endgame (≤12 pieces) | 5 | 3 |
| Endgame (≤6 pieces) | 6 | 3 |

## Opening Book

For the first few moves, the engine uses a pre-built opening book:
- Location: `game/engine/opening_book.json`
- Keys: FEN strings (board + side + castling rights)
- Values: List of valid moves `[from_row, from_col, to_row, to_col]`

## Move Flow
1. Player clicks piece
2. Django calls `get_valid_moves()`
3. ChessGame checks DP cache
4. If not cached → sends `MOVES` command to C++ engine
5. C++ returns valid moves
6. Player selects destination
7. Django calls `make_move()`
8. Move validated and applied
9. If AI turn → `get_ai_move()` called
10. Opening book checked first
11. If not in book → `BESTMOVE` sent to C++ engine
12. AI move returned and applied

## Engine Fallback

If C++ binary is not found, the system automatically falls back to Python engine (`main.py`) with reduced search depth.

## Iterative Deepening

The engine search is upgraded from a fixed-depth search to time-bounded iterative deepening:
- The search starts at depth 1, then depth 2, depth 3, etc., up to the maximum depth allowed by the difficulty level.
- At the start of each depth iteration, the best move found from the previous depth is ordered first to maximize Alpha-Beta pruning.
- A clock is checked periodically during search. If the time budget expires, the search is aborted immediately, and the best move from the last fully completed depth is returned.

## Transposition Table (TT)

A Transposition Table is used to store previously searched positions to avoid redundant calculations:
- **Size**: $2^{19}$ entries (524,288 entries).
- **Replacement Strategy**: Depth-preferred (overwrite if the new search has a greater or equal depth).
- **Fields stored**: 64-bit board hash, search depth, evaluation score, best move, and bound type (`EXACT`, `LOWER_BOUND`, `UPPER_BOUND`).
- **TT Move Ordering**: Stored best moves are tried first at any node, greatly speeding up Alpha-Beta cut-offs.

## Zobrist Hash Design

To uniquely identify board positions without collisions:
- **Keys**: Deterministically generated using a 64-bit XORShift pseudo-random number generator (PRNG) with a fixed seed (`0x123456789ABCDEF`).
- **Components hashed**:
  - Piece type and color at each of the 64 squares (12 piece types total).
  - Side to move (turn).
  - Castling rights (16 combinations).
  - En passant target file (8 possible files).

## Engine Metrics

The engine returns performance metrics appended to the `BESTMOVE` command output:
- `DEPTH`: Maximum fully completed search depth.
- `NODES`: Total number of nodes evaluated.
- `TTHITS`: Number of transposition table cache hits.
- `TIME`: Total elapsed search time in milliseconds.
- `ENGINE`: Either `cpp` or `python` to identify the active engine.
- `STATUS`: Either `completed` (searched to max depth) or `timeout` (budget expired).
