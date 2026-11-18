# Checkora Engine Architecture

## Overview
Checkora uses a C++ chess engine for AI move generation and validation, coordinated through Django via subprocess communication. `game/engine/main.py` is the same engine in Python: it implements the same protocol, rules, evaluation and search as `game/engine/main.cpp`, and plays whenever no usable compiled binary is present. It searches less deep in the same time.

## System Architecture

```text
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
Engine client (game/engine_client.py)
|
v
Engine server, one per game (engine/persistent_server.py)
|
v
C++ Binary (engine/main.exe or main)
   or, when no usable binary is found,
Python Engine (engine/main.py)
```

## Django to C++ Communication

The engine reads commands on **stdin** and writes replies on **stdout**: one command per line, exactly one reply line per command.

`ChessGame._call_engine()` in `game/engine.py` builds the command line and hands it to `EngineClient` in `game/engine_client.py`, which owns finding, starting and talking to the engine. It does not start a new process for every command. For each game it starts `game/engine/persistent_server.py`, which keeps one engine process running and listens on a loopback port that the operating system picks. The port number is written to `checkora_engine_<game_id>.port` in the temp directory, and a lock file next to it makes sure only one request per game starts a server. The connection is authenticated with a key stored with the game, which reaches the server in the `CHECKORA_ENGINE_AUTHKEY` environment variable rather than on its command line.

- The server exits after 60 seconds without a request, and when the game ends (`ChessGame.cleanup_engine()` sends it `SHUTDOWN`). On the way out it removes the port file only if the file still names its own port, so an old server never deletes a newer one's.
- If the engine process dies, or does not answer in time, the server starts a new one.
- If a server takes a request and gives no answer at all, the bridge stops that server, so the next request starts afresh.
- If the server cannot be started or is busy, the command is answered by a one-off engine process instead (`EngineClient._ask_one_off()`):

```python
proc = subprocess.Popen(
    self.engine_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE, text=True,
)
stdout, stderr = proc.communicate(input=line + '\n', timeout=timeout)
```

The bridge waits `ANALYSIS_TIMEOUT_SECONDS` (10) for a reply. A new server gets `SERVER_START_SECONDS` (2) to come up. After a server has failed to start, no new one is tried for `RETRY_SECONDS` (60) in `engine_client.py`; the one-off process is used in the meantime.

## Command Protocol

This is version 2 of the protocol. The header comments of `main.cpp` and `main.py` are the reference; `PROTOCOL_VERSION` in both files and in `game/engine_client.py` must agree.

`<board>` is the 64-character board, `<castling>` a subset of `KQkq` or `-`, `<turn>` is `white` or `black`, and `<ep>` is the row and column of the en passant target square, or `-1 -1`.

| Command | Purpose | Example |
|---------|---------|---------|
| `VERSION` | Ask for the protocol version | `VERSION` → `VERSION 2` |
| `MOVES` | Get valid moves for a piece | `MOVES <board> <castling> <turn> <ep> <row> <col>` → `MOVES [<row> <col> <is_capture> <is_promotion> ...]` |
| `ATTACKED` | Is a square attacked by one colour | `ATTACKED <board> <castling> <attacker> <row> <col>` → `YES` or `NO` |
| `PROMOTE` | Handle pawn promotion | `PROMOTE <board> <castling> <turn> <ep> <fr> <fc> <tr> <tc> [piece]` → `PROMOTE <new board>` or `INVALID <reason>` |
| `STATUS` | Get game status | `STATUS <board> <castling> <turn> <ep>` → `STATUS CHECK`, `CHECKMATE`, `STALEMATE`, `DRAW` or `OK` |
| `NOTATION` | Generate SAN notation | `NOTATION <board> <castling> <turn> <ep> <fr> <fc> <tr> <tc> [piece]` → `NOTATION <san>`, or `NOTATION ?` when the move is not legal |
| `EVAL` | Static evaluation of a position | `EVAL <board> <castling> <turn> <ep>` → `EVAL <centipawns>`, positive is good for White |
| `PERFT` | Count the leaf positions at a depth, for testing move generation | `PERFT <board> <castling> <turn> <ep> <depth>` → `PERFT <leaf nodes>` |
| `BESTMOVE` | Get AI best move | `BESTMOVE <board> <castling> <turn> <ep> <depth> [time_limit_ms [halfmove_clock [alternatives [earlier positions...]]]]` |

Notes:

- A missing promotion piece means a queen.
- `STATUS DRAW` means legal moves exist but neither side has the material to mate.
- `PERFT` is capped at depth 6.
- A line that cannot be parsed is answered with `ERROR <reason>`.
- The earlier positions after `BESTMOVE` come in groups of four tokens: FEN piece placement, `w` or `b`, castling rights, and the en passant square as `row,col` or `-`. They are the positions of the game since the last capture or pawn move, and they let the search see repetitions. `ChessGame.get_ai_move()` sends up to 100 of them, together with the game's halfmove clock. A position the search reaches again counts as a draw when its earlier occurrence is on the line being searched, or when it occurred twice before in the game.
- `alternatives` after `BESTMOVE` defaults to 0. The game analysis asks for 3 and the `easy` level for 8; the other levels ask for none.
- `EVAL` and `PERFT` are not used by the web app. The tests use them.

The reply to `BESTMOVE` is described under Engine Metrics below.

## Board Representation

The board is serialized as a **64-character string**:
- Uppercase = White pieces (K, Q, R, B, N, P)
- Lowercase = Black pieces (k, q, r, b, n, p)
- `.` = Empty square

```text
rnbqkbnr
pppppppp
........
........
........
........
PPPPPPPP
RNBQKBNR
```

The string runs from rank 8 to rank 1 without line breaks. Inside both engines the position is held in a 10x12 mailbox: the 64 squares sit inside a border of off-board cells, so a piece that steps off the board lands on a border cell and no bounds check is needed.

## Minimax Algorithm

Both engines search with **Minimax with Alpha-Beta Pruning**, in its negamax form (principal variation search):

```text
search(position, depth, alpha, beta)
if depth == 0: return quiesce(position, alpha, beta)

for each move, best candidates first:
    score = -search(next_position, depth-1, -beta, -alpha)
    alpha-beta pruning to cut unnecessary branches

return best score
```

What the search does, in `search()` and `quiesce()` of both files:

- **Quiescence search**: when the depth is used up, captures and promotions are played out (and every reply to a check) until the position is quiet, so the evaluation is never taken in the middle of an exchange. Captures that lose material by static exchange evaluation are skipped, and so is a capture that cannot bring the score up to alpha even with 200 centipawns to spare (delta pruning).
- **Move ordering**: the move remembered in the transposition table first, then captures (most valuable victim first, with a static exchange evaluation to put losing captures last), then two killer moves per ply, then the history score of quiet moves (raised by the square of the depth each time a quiet move causes a cut-off).
- **Check extension**: a position in check is searched one ply deeper.
- **Mate distance pruning**: a line cannot score better than a mate already found closer to the root.
- **Pruning and reductions**, none of them in check. The first three are used only outside the principal variation:
  - reverse futility pruning: up to 3 plies from the horizon, a node whose static evaluation beats beta by at least 120 centipawns a ply returns at once;
  - null move pruning from depth 3, searched `2 + depth / 4` plies shallower, not when the side to move has only pawns;
  - futility pruning: up to 2 plies from the horizon, a quiet move that does not give check is skipped when the static evaluation is at least 100 plus 100 a ply below alpha;
  - late move reductions: from depth 3, quiet moves that do not give check, after the first 3 (5 on the principal variation), are searched `0.75 + ln(depth) * ln(move number) / 2.25` plies shallower (one ply less on the principal variation) and searched again at full depth if they beat alpha.
- **Draws**: a repeated position, a position where neither side can mate, and the fifty-move rule are scored as draws inside the search.
- **Promotions**: the search looks at queen and knight promotions. The move it returns always promotes to a queen.

### Difficulty levels

The bridge sets the limits of the search from `DIFFICULTY_SETTINGS` in `game/engine.py`. The search stops at the depth limit or when the time is used up, whichever comes first.

| Level | Depth limit (plies) | Time limit | Notes |
|-------|---------------------|------------|-------|
| `easy` | 2 | 500 ms | Makes deliberate mistakes, see below |
| `medium` | 6 | 1500 ms | |
| `hard` | none (64 is sent) | 5000 ms | Keeps deepening until the time is used |
| `master` | none (64 is sent) | 8500 ms | Keeps deepening until the time is used |

Both engines get the same limits. Where the time limit is what stops the search, the Python engine has reached a lower depth by then.

The time limit sent is the smallest of three: the level's own, the request timeout less 500 ms (`REPLY_MARGIN_MS`), and what the game clock allows. `ChessGame._clock_budget_ms()` gives the side to move a thirtieth of the time left on its clock (`CLOCK_MOVES_LEFT`) plus three quarters of the increment, and never less than 100 ms. A game without a clock has no such cap. That way `hard` and `master` can still finish a blitz game.

For `hard` and `master` the `max_depth` in `DIFFICULTY_SETTINGS` (10 and 14) is not sent. They are marked `time_only`, so the bridge sends 64 and only the time stops them; `max_depth` is the depth they are expected to pass.

`easy` is made beatable in `ChessGame._play_weaker()`. The engine is asked for 8 alternatives to its best move; the other levels ask for none. In about half of its moves (`error_rate` 0.5) the bridge plays one of those alternatives instead, chosen at random among the ones the engine scores no more than 900 centipawns (`error_max_loss`) below the best move.

An unknown difficulty is treated as `medium`. `get_ai_move(depth=N)` without a difficulty uses `N` as the depth limit and never plays a weaker move on purpose; the game analysis view calls it this way.

## Evaluation

`evaluate()` scores a position in centipawns, positive for White. It adds up:

- material and piece-square tables, with separate middlegame and endgame values (pawn 100/120, knight 320/310, bishop 330/330, rook 500/520, queen 900/940)
- the bishop pair
- mobility of knights, bishops, rooks and queens
- pawn structure: doubled, isolated and passed pawns. In the endgame a passed pawn is worth more the farther the enemy king is from the square in front of it and the nearer its own king is, the more so the farther the pawn has come.
- rooks on open and half-open files, and on the seventh rank when the enemy king is on the eighth
- the pawn shelter in front of a king that is still on its two home rows
- the king attack, in the middlegame: every square next to a king (or under it) that an enemy knight, bishop, rook or queen attacks counts 2, 2, 3 or 5 units. Once at least two pieces take part, the king's side loses `units * units / 4` centipawns, at most 500. The penalty grows faster than the number of attackers.
- a small bonus for the side to move

The middlegame and endgame scores are blended by the material left on the board. A few endgame rules sit on top: a position neither side can win on material scores 0, two knights against a bare king score 0, a small material lead without pawns is scaled down, and with a winning lead against a nearly bare king the score rewards driving that king to the edge.

`EvaluationTest` in `game/test_engine_rules.py` checks that both engines give the same score for the same position. `game/test_engine_evaluation.py` checks the king attack and the passed pawn term on positions built for them, and on the positions of seeded random games that both engines agree and that swapping the colours negates the score.

## Measuring Strength

`scripts/engine_match.py` plays two engine builds against each other and prints the result with an Elo difference and its 95% interval. The games come in pairs from the same opening with the colours swapped; the openings are seeded random lines that the second engine scores as level, or lines from a file. A change to the search or the evaluation should beat the build it started from before it is kept:

```bash
g++ -O2 -std=c++17 game/engine/main.cpp -o /tmp/new
.venv/bin/python scripts/engine_match.py /tmp/new /tmp/old --games 400 --movetime 50
```

With `--level1` and `--level2` the two sides play as levels of the site, with the limits and deliberate mistakes of `DIFFICULTY_SETTINGS`; `--time-scale` multiplies every level's time by the same factor. The script needs python-chess, from `requirements-dev.txt`, and its docstring lists the other options. The engine ratings in `game/progression.py` (easy 450, medium 1200, hard 1850, master 2000) put medium at the starting rating of a player; the gaps between the levels come from matches between them played this way.

## Opening Book

For the first few moves, the engine uses a pre-built opening book:
- Location: `game/engine/opening_book.json`
- Keys: FEN strings (board + side + castling rights)
- Values: List of valid moves `[from_row, from_col, to_row, to_col]`

When a position has several book moves, one is picked at random, and it is checked for legality before it is played. The file also has a `_named_lines` entry with whole opening lines; the AI follows one of those when a game is started with an `opening`.

`OpeningBookFileTest` in `game/test_engine_bridge.py` checks that every move in the book is legal in its position and that each named line can be played from the starting position.

## Move Flow
1. Player clicks piece
2. Django calls `get_valid_moves()`
3. ChessGame checks DP cache
4. If not cached → sends `MOVES` command to C++ engine
5. C++ returns valid moves
6. Player selects destination
7. Django calls `make_move()`
8. Move validated and applied; `NOTATION` and `STATUS` are sent to the engine for the move text and for check, mate or a draw
9. If AI turn → `get_ai_move()` called
10. Opening book checked first
11. If not in book → `BESTMOVE` sent to C++ engine
12. AI move returned and applied

## What the bridge reports

`ChessGame` keeps three things beside `game_status` that callers can read:

- `in_check`: `True` while the side to move is in check. It is set whenever the engine is asked for the status of the position, and it is stored with the game.
- `display_status`: `'check'` while the game is on and the side to move is in check, otherwise the same as `game_status`. `game_status` itself stays `'active'` during a check.
- `last_engine_error`: why the last engine request gave nothing usable. `None` means the engine answered, `'no_reply'` that it could not be started or did not answer in time, `'bad_reply'` that it answered something else. `get_ai_move()` returning `None` with `last_engine_error` still `None` means there is no legal move. It is not stored with the game.

## Engine Fallback

`ChessGame._resolve_engine_path()` calls `resolve_engine_path()` in `game/engine_client.py`, which goes through `main` and `main.exe` in `game/engine/` (`main.exe` first on Windows) and then `main.py`. A compiled binary is used only if it is executable and answers `VERSION` with `VERSION 2`; the check is made once per process. A binary that cannot run on this machine or was built from older sources is skipped with a warning in the log. When no binary is usable, or none exists, the Python engine (`main.py`) plays.

The binary is not committed, so it has to be rebuilt after every pull that changes `main.cpp`:

```bash
g++ -O2 -std=c++17 game/engine/main.cpp -o game/engine/main
```

On Windows the output file is `game/engine/main.exe`. Until the binary is rebuilt, the game runs on the Python engine.

## Iterative Deepening

The engine search is a time-bounded iterative deepening search:
- The search starts at depth 1, then depth 2, depth 3, etc., up to the maximum depth allowed by the difficulty level.
- At the start of each depth iteration, the best move found from the previous depth is ordered first to maximize Alpha-Beta pruning.
- From depth 4 on, each iteration first searches a narrow window around the previous score and widens it if the score falls outside.
- A clock is checked periodically during search. If the time budget expires, the search is aborted immediately. The reply is the best move of the last fully completed depth, unless the unfinished iteration had already searched a move to its full depth that beat the earlier best move; then that move is played, with its score. `DEPTH` still reports the last completed depth. When alternatives were asked for, the reply always stays with the completed depth, so that their scores compare with the best move's.
- A new iteration is not started when it could not finish in the time that is left, and a tenth of the time limit is left unused so the reply is on time. When alternatives are asked for, the main search takes only half of the rest and leaves the other half for scoring them.

## Transposition Table (TT)

A Transposition Table is used to store previously searched positions to avoid redundant calculations:
- **Size**: $2^{19}$ slots (524,288) with two entries each, in both engines (`main.py` keeps them in a list), so that both search the same tree.
- **Replacement Strategy**: the first entry of a slot keeps the deepest search stored there; the second is always replaced.
- **Fields stored**: 64-bit board hash, search depth, evaluation score, best move, and bound type (exact, lower bound, upper bound).
- **TT Move Ordering**: Stored best moves are tried first at any node, greatly speeding up Alpha-Beta cut-offs.
- The table is cleared at the start of every `BESTMOVE` command.

## Zobrist Hash Design

Positions are identified by a 64-bit hash:
- **Keys**: Deterministically generated using a 64-bit XORShift pseudo-random number generator (PRNG) with a fixed seed (`0x123456789ABCDEF`).
- **Components hashed**:
  - Piece type and color at each of the 64 squares (12 piece types total).
  - Side to move (turn).
  - Castling rights (16 combinations).
  - En passant target file (8 possible files), only when a pawn can make the capture.

## Engine Metrics

The reply to `BESTMOVE` starts with the move and carries the search figures after it:

```text
BESTMOVE <fr> <fc> <tr> <tc> EVAL <cp> [ALTS (<fr> <fc> <tr> <tc> <cp>)...] DEPTH <d> NODES <n> TTHITS <n> TIME <ms> ENGINE cpp|python STATUS completed|timeout
```

- `EVAL`: Score of the move in centipawns from White's side. Forced mates are reported close to plus or minus 99999.
- `ALTS`: The next best moves, each with its own score. At most as many as the `alternatives` argument asked for.
- `DEPTH`: Maximum fully completed search depth.
- `NODES`: Total number of nodes evaluated.
- `TTHITS`: Number of transposition table cache hits.
- `TIME`: Total elapsed search time in milliseconds.
- `ENGINE`: Either `cpp` or `python` to identify the active engine.
- `STATUS`: Either `completed` (searched to max depth) or `timeout` (budget expired).

When the side to move has no legal move the reply is `BESTMOVE NONE`.
