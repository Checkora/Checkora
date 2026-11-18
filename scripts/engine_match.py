#!/usr/bin/env python3
"""Play two engines against each other and estimate the Elo difference.

Each engine is a program that speaks the line protocol described at the top
of game/engine/main.cpp: a compiled main.cpp, or a main.py (run with this
Python). The games come in pairs that start from the same opening, with the
engines swapping colours, so an unbalanced opening favours neither side.
python-chess keeps the game and ends it at mate, stalemate, insufficient
material, the fifty-move rule or a threefold repetition; a game still
going after --max-plies plies is scored as a draw.

The openings are random 6 to 8 ply lines from a seeded generator that the
second engine scores within --opening-margin centipawns at --vet-depth, or
lines read from a file (one per line: UCI moves from the starting
position, or a FEN). --save-openings writes the ones used, so a later
match can be played from exactly the same set.

A side can also play as one of the site's levels (--level1/--level2): its
depth, time and deliberate mistakes are read from DIFFICULTY_SETTINGS in
game/engine.py, with every time limit multiplied by --time-scale.

The result is given for the first engine: wins, draws and losses, the
score, and the Elo difference with its 95% interval, worked out from the
game pairs. Needs python-chess (requirements-dev.txt).

Examples:
    # A change in main.cpp against the build it started from
    g++ -O2 -std=c++17 game/engine/main.cpp -o /tmp/new
    .venv/bin/python scripts/engine_match.py /tmp/new /tmp/old --games 400 --movetime 50

    # Two of the site's levels, at a tenth of their thinking time
    .venv/bin/python scripts/engine_match.py game/engine/main game/engine/main \\
        --level1 medium --level2 hard --time-scale 0.1 --games 200
"""

import argparse
import collections
import math
import multiprocessing
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass

import chess
import chess.pgn

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Opening lines are this many plies long, chosen at random in the range
OPENING_MIN_PLIES, OPENING_MAX_PLIES = 6, 8
# The depth limit an engine is sent when only its time should stop it
NO_DEPTH_LIMIT = 64
# Two-sided 95% quantile of the normal distribution
Z_95 = 1.959964


@dataclass(frozen=True)
class Player:
    """One side of the match and the limits it plays with."""
    name: str
    command: tuple
    depth: int
    movetime_ms: int
    alternatives: int = 0
    error_rate: float = 0.0
    error_max_loss: int = 0


class Engine:
    """An engine process spoken to over its line protocol."""

    def __init__(self, command):
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )

    def ask(self, line):
        self.proc.stdin.write(line + '\n')
        self.proc.stdin.flush()
        reply = self.proc.stdout.readline()
        if not reply:
            raise RuntimeError(f'engine {self.proc.args} exited')
        return reply.strip()

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()


def engine_command(path):
    path = os.path.abspath(path)
    return (sys.executable, path) if path.endswith('.py') else (path,)


# ------------------------------------------------------------
#  Protocol fields
# ------------------------------------------------------------

def row_col(square):
    """python-chess square -> the protocol's row and column (row 0 is rank 8)."""
    return 7 - chess.square_rank(square), chess.square_file(square)


def castling_field(board):
    return ''.join(letter for letter, held in (
        ('K', board.has_kingside_castling_rights(chess.WHITE)),
        ('Q', board.has_queenside_castling_rights(chess.WHITE)),
        ('k', board.has_kingside_castling_rights(chess.BLACK)),
        ('q', board.has_queenside_castling_rights(chess.BLACK)),
    ) if held) or '-'


def position_fields(board):
    """<board64> <rights> <turn> <epRow> <epCol>"""
    board64 = ''.join(
        piece.symbol() if (piece := board.piece_at(chess.square(col, 7 - row))) else '.'
        for row in range(8) for col in range(8)
    )
    ep = '-1 -1' if board.ep_square is None else '%d %d' % row_col(board.ep_square)
    turn = 'white' if board.turn == chess.WHITE else 'black'
    return f'{board64} {castling_field(board)} {turn} {ep}'


def history_key(board):
    """An earlier position as BESTMOVE takes it: placement, side, rights, ep."""
    ep = '-' if board.ep_square is None else '%d,%d' % row_col(board.ep_square)
    turn = 'w' if board.turn == chess.WHITE else 'b'
    return f'{board.board_fen()} {turn} {castling_field(board)} {ep}'


def bestmove_command(board, keys, depth, movetime_ms, alternatives):
    """BESTMOVE for the position, with the earlier positions since the last
    capture or pawn move (at most 100, as the site sends) so the engine sees
    repetitions. keys holds the history key of every position of the game."""
    earlier = keys[-1 - min(board.halfmove_clock, 100):-1]
    command = (f'BESTMOVE {position_fields(board)} {depth} {movetime_ms}'
               f' {board.halfmove_clock} {alternatives}')
    return ' '.join([command] + earlier)


def parse_bestmove(reply):
    """(from_square, to_square, white_eval, [(from, to, white_eval)...], depth) or None."""
    tokens = reply.split()
    if len(tokens) < 5 or tokens[0] != 'BESTMOVE':
        return None

    def square(row, col):
        return chess.square(int(col), 7 - int(row))

    best = (square(tokens[1], tokens[2]), square(tokens[3], tokens[4]))
    score = int(tokens[tokens.index('EVAL') + 1])
    alts = []
    if 'ALTS' in tokens:
        values = tokens[tokens.index('ALTS') + 1:tokens.index('DEPTH')]
        for i in range(0, len(values), 5):
            alts.append((square(values[i], values[i + 1]), square(values[i + 2], values[i + 3]),
                         int(values[i + 4])))
    return best[0], best[1], score, alts, int(tokens[tokens.index('DEPTH') + 1])


def to_move(board, origin, target):
    """The legal move between the squares (promoting to a queen), or None."""
    piece = board.piece_at(origin)
    promotion = None
    if piece and piece.piece_type == chess.PAWN and chess.square_rank(target) in (0, 7):
        promotion = chess.QUEEN
    move = chess.Move(origin, target, promotion)
    return move if move in board.legal_moves else None


def play_weaker(board, best, score, alts, player, rng):
    """The move an erring level plays: ChessGame._play_weaker in
    game/engine.py. With probability error_rate it swaps the best move for
    a random alternative that the engine scores at most error_max_loss
    centipawns below it, from the mover's side."""
    if rng.random() >= player.error_rate:
        return best
    sign = 1 if board.turn == chess.WHITE else -1
    choices = [alt for alt in alts if sign * (score - alt[2]) <= player.error_max_loss]
    if not choices:
        return best
    origin, target, _ = rng.choice(choices)
    return origin, target


# ------------------------------------------------------------
#  Openings
# ------------------------------------------------------------

def read_openings(path):
    """Openings from a file as lists of UCI moves, or FEN strings."""
    openings = []
    with open(path) as handle:
        for line in handle:
            line = line.split('#')[0].strip()
            if line:
                openings.append(line if '/' in line else line.split())
    return openings


def opening_board(opening):
    if isinstance(opening, str):
        return chess.Board(opening)
    board = chess.Board()
    for uci in opening:
        board.push_uci(uci)
    return board


def random_openings(count, seed, engine_path, vet_depth, margin):
    """count distinct random opening lines that the engine scores close to
    level after a search to vet_depth (without a time limit, so the same
    seed and engine give the same set)."""
    rng = random.Random(seed)
    engine = Engine(engine_command(engine_path))
    openings, seen = [], set()
    try:
        while len(openings) < count:
            board = chess.Board()
            for _ in range(rng.randint(OPENING_MIN_PLIES, OPENING_MAX_PLIES)):
                if board.is_game_over():
                    break
                board.push(rng.choice(list(board.legal_moves)))
            if board.is_game_over() or board.fen() in seen:
                continue
            reply = parse_bestmove(engine.ask(f'BESTMOVE {position_fields(board)} {vet_depth} 0'))
            if reply is None or abs(reply[2]) > margin:
                continue
            seen.add(board.fen())
            openings.append([move.uci() for move in board.move_stack])
    finally:
        engine.close()
    return openings


# ------------------------------------------------------------
#  Games
# ------------------------------------------------------------

_players = None
_engines = None


def _start_worker(players):
    """Each worker process runs one process per player for all its games."""
    global _players, _engines
    _players = players
    _engines = [Engine(player.command) for player in players]


def ending(board, plies_played, max_plies):
    """(winner, reason) once the game is over, else None; winner is None
    for a draw."""
    if board.is_checkmate():
        return not board.turn, 'checkmate'
    for drawn, reason in ((board.is_stalemate, 'stalemate'),
                          (board.is_insufficient_material, 'insufficient material'),
                          (lambda: board.halfmove_clock >= 100, 'fifty-move rule'),
                          (lambda: board.is_repetition(3), 'threefold repetition'),
                          (lambda: plies_played >= max_plies, 'move limit')):
        if drawn():
            return None, reason
    return None


def play_game(task):
    """Play one game; the first player has White when first_is_white.
    Returns (game number, PGN text, termination, points of the first player,
    the depths each player reached)."""
    number, opening, first_is_white, max_plies, seed = task
    rng = random.Random(seed)
    board = opening_board(opening)
    opening_plies = len(board.move_stack)
    replay = board.root()
    keys = []
    for move in board.move_stack:
        keys.append(history_key(replay))
        replay.push(move)
    keys.append(history_key(board))

    white = 0 if first_is_white else 1
    depths = ([], [])  # completed search depth of each move, per player
    while (end := ending(board, len(board.move_stack) - opening_plies, max_plies)) is None:
        index = white if board.turn == chess.WHITE else 1 - white
        player, engine = _players[index], _engines[index]
        reply = engine.ask(bestmove_command(board, keys, player.depth, player.movetime_ms,
                                            player.alternatives))
        parsed = parse_bestmove(reply)
        move = None
        if parsed:
            origin, target, score, alts, depth = parsed
            depths[index].append(depth)
            if player.error_rate:
                origin, target = play_weaker(board, (origin, target), score, alts, player, rng)
            move = to_move(board, origin, target)
        if move is None:
            end = not board.turn, f'illegal reply from {player.name}: {reply}'
            break
        board.push(move)
        keys.append(history_key(board))

    winner, reason = end
    result = '1/2-1/2' if winner is None else '1-0' if winner == chess.WHITE else '0-1'
    game = chess.pgn.Game.from_board(board)
    game.headers.update({
        'Event': 'engine_match', 'Round': str(number + 1),
        'White': _players[white].name, 'Black': _players[1 - white].name,
        'Result': result, 'Termination': reason,
    })
    if winner is None:
        points = 0.5
    else:
        points = 1.0 if (winner == chess.WHITE) == first_is_white else 0.0
    return number, str(game), reason, points, depths


# ------------------------------------------------------------
#  Statistics
# ------------------------------------------------------------

def elo_from_score(score):
    score = min(max(score, 1e-6), 1 - 1e-6)
    return -400 * math.log10(1 / score - 1)


def elo_estimate(pair_scores):
    """Elo difference and the half-width of its 95% interval, from the
    scores (0 to 2 points) of game pairs. The two games of a pair share an
    opening, so they are not independent samples; the pair is."""
    pairs = len(pair_scores)
    score = sum(pair_scores) / (2 * pairs)
    variance = sum((points / 2 - score) ** 2 for points in pair_scores) / pairs
    spread = Z_95 * math.sqrt(variance / pairs)
    margin = (elo_from_score(score + spread) - elo_from_score(score - spread)) / 2
    return elo_from_score(score), margin


def summary(name, points):
    """points: the first player's result in each game, None while unplayed."""
    played = [result for result in points if result is not None]
    wins, draws, losses = played.count(1.0), played.count(0.5), played.count(0.0)
    text = (f'{name}: {len(played)} games, W/D/L {wins}/{draws}/{losses},'
            f' score {100 * sum(played) / len(played):.1f}%')
    pairs = [points[i] + points[i + 1] for i in range(0, len(points), 2)
             if points[i] is not None and points[i + 1] is not None]
    if pairs:
        elo, margin = elo_estimate(pairs)
        text += f', Elo {elo:+.1f} +- {margin:.1f}'
    return text


# ------------------------------------------------------------
#  Command line
# ------------------------------------------------------------

def level_player(name, path, level, time_scale):
    """A player with the limits of one of the site's levels."""
    sys.path.insert(0, REPO_ROOT)
    from game.engine import ChessGame

    cfg = ChessGame.DIFFICULTY_SETTINGS[level]
    error_rate = cfg.get('error_rate', 0)
    return Player(
        name=name, command=engine_command(path),
        depth=ChessGame.UNLIMITED_DEPTH if cfg.get('time_only') else cfg['max_depth'],
        movetime_ms=max(1, round(cfg['time_budget_ms'] * time_scale)),
        alternatives=ChessGame.ERROR_ALTERNATIVES if error_rate else 0,
        error_rate=error_rate, error_max_loss=cfg.get('error_max_loss', 0),
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__.split('\n\n')[0], epilog='See the module docstring for details.')
    parser.add_argument('first', help='engine whose Elo difference is reported')
    parser.add_argument('second', help='reference engine (also vets the random openings)')
    parser.add_argument('--games', type=int, default=200, help='games to play, rounded up to pairs')
    parser.add_argument('--movetime', type=int, default=50, help='milliseconds per move (0: none)')
    parser.add_argument('--depth', type=int, default=NO_DEPTH_LIMIT, help='depth limit per move')
    parser.add_argument('--level1', help='play the first engine as this level of the site')
    parser.add_argument('--level2', help='play the second engine as this level of the site')
    parser.add_argument('--time-scale', type=float, default=1.0,
                        help="multiply each level's time limit by this")
    parser.add_argument('--concurrency', type=int, default=max(1, (os.cpu_count() or 2) // 2),
                        help='games played at once')
    parser.add_argument('--max-plies', type=int, default=250,
                        help='plies after the opening before a game is scored a draw')
    parser.add_argument('--openings', help='file of openings to use instead of random ones')
    parser.add_argument('--save-openings', help='write the openings used to this file')
    parser.add_argument('--seed', type=int, default=1, help='seed for openings and mistakes')
    parser.add_argument('--vet-depth', type=int, default=6, help='search depth that vets random openings')
    parser.add_argument('--opening-margin', type=int, default=80,
                        help='largest score (centipawns) a random opening may have')
    parser.add_argument('--pgn', help='write the games to this PGN file')
    parser.add_argument('--name1', default='first', help='name of the first engine in the output')
    parser.add_argument('--name2', default='second', help='name of the second engine in the output')
    args = parser.parse_args()
    if args.depth < 1 or args.movetime < 0 or (args.movetime == 0 and args.depth == NO_DEPTH_LIMIT):
        parser.error('give a positive --depth, or a --movetime that stops the search')
    return args


def main():
    args = parse_args()
    players = []
    for name, path, level in ((args.name1, args.first, args.level1), (args.name2, args.second, args.level2)):
        if level:
            players.append(level_player(f'{name} ({level})', path, level, args.time_scale))
        else:
            players.append(Player(name=name, command=engine_command(path),
                                  depth=args.depth, movetime_ms=args.movetime))
    for player in players:
        print(f'{player.name}: {" ".join(player.command)}, depth {player.depth},'
              f' {player.movetime_ms} ms/move'
              + (f', mistakes {player.error_rate} up to {player.error_max_loss} cp' if player.error_rate else ''))

    pairs = (args.games + 1) // 2
    if args.openings:
        openings = read_openings(args.openings)
        if len(openings) < pairs:
            openings = (openings * (pairs // len(openings) + 1))
        openings = openings[:pairs]
    else:
        openings = random_openings(pairs, args.seed, args.second, args.vet_depth, args.opening_margin)
    if args.save_openings:
        with open(args.save_openings, 'w') as handle:
            for opening in openings:
                handle.write((opening if isinstance(opening, str) else ' '.join(opening)) + '\n')

    tasks = [(2 * i + swap, opening, swap == 0, args.max_plies, args.seed * 1_000_003 + 2 * i + swap)
             for i, opening in enumerate(openings) for swap in (0, 1)]
    games = [None] * len(tasks)
    points = [None] * len(tasks)
    endings = collections.Counter()
    all_depths = ([], [])
    started = time.monotonic()
    with multiprocessing.Pool(args.concurrency, _start_worker, (players,)) as pool:
        for done, (number, pgn, reason, result, depths) in enumerate(pool.imap_unordered(play_game, tasks), 1):
            games[number], points[number] = pgn, result
            for index in (0, 1):
                all_depths[index].extend(depths[index])
            endings[reason if not reason.startswith('illegal') else 'illegal reply'] += 1
            if done % 20 == 0 or done == len(tasks):
                print(f'[{time.monotonic() - started:.0f}s] ' + summary(players[0].name, points), flush=True)

    if args.pgn:
        with open(args.pgn, 'w') as handle:
            handle.write('\n\n'.join(games) + '\n')
    print('Average depth: ' + ', '.join(f'{player.name} {sum(d) / max(1, len(d)):.1f}'
                                        for player, d in zip(players, all_depths)))
    print('Endings: ' + ', '.join(f'{reason} {count}' for reason, count in endings.most_common()))
    print(summary(f'{players[0].name} vs {players[1].name}', points))


if __name__ == '__main__':
    main()
