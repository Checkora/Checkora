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
| `BESTMOVE` | Get AI best move | `BESTMOVE <board> <castling> <turn> <ep> <depth>` |
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
1.Player clicks piece
2.Django calls get_valid_moves()
3.ChessGame checks DP cache
4.If not cached → sends MOVES command to C++ engine
5.C++ returns valid moves
6.Player selects destination
7.Django calls make_move()
8.Move validated and applied
9.If AI turn → get_ai_move() called
10.Opening book checked first
11.If not in book → BESTMOVE sent to C++ engine
12.AI move returned and applied

## Engine Fallback

If C++ binary is not found, the system automatically falls back to Python engine (`main.py`) with reduced search depth.