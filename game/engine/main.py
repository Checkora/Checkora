#!/usr/bin/env python3
"""Checkora chess engine implemented in Python.

The fallback for machines without the compiled engine. It implements the
same protocol, rules, evaluation and search as main.cpp and must be kept
in step with that file; it only searches less deep in the same time.
Given the same command without a time limit, both give the same reply
apart from TIME and ENGINE. That covers the order in which moves are
generated and tried and the transposition table (two entries per slot,
2^19 slots, the first keeping the deepest search).

Protocol: one command per line, exactly one reply line per command.
<board64> is 64 characters, rank 8 first, "." for an empty square.
<rights> is a subset of "KQkq" or "-", <turn> is "white" or "black",
<ep_row> <ep_col> is the en passant target square or "-1 -1".

VERSION
-> VERSION <protocol version>

MOVES <board64> <rights> <turn> <ep_row> <ep_col> <row> <col>
-> MOVES [<row> <col> <is_capture> <is_promotion> ...]

ATTACKED <board64> <rights> <attackerColor> <row> <col>
-> YES | NO

PROMOTE <board64> <rights> <turn> <ep_row> <ep_col> <fr> <fc> <tr> <tc> [promoPiece]
-> PROMOTE <newBoard64> | INVALID <reason>

STATUS <board64> <rights> <turn> <ep_row> <ep_col>
-> STATUS CHECK | CHECKMATE | STALEMATE | DRAW | OK

NOTATION <board64> <rights> <turn> <ep_row> <ep_col> <fr> <fc> <tr> <tc> [promoPiece]
-> NOTATION <san>
-> NOTATION ?               (the move is not legal)

EVAL <board64> <rights> <turn> <ep_row> <ep_col>
-> EVAL <centipawns, positive is good for White>

PERFT <board64> <rights> <turn> <ep_row> <ep_col> <depth>
-> PERFT <leaf nodes>

BESTMOVE <board64> <rights> <turn> <ep_row> <ep_col> <depth> [time_limit_ms
         [halfmove_clock [alternatives [<placement> <w|b> <rights> <ep>]...]]]
-> BESTMOVE <fr> <fc> <tr> <tc> EVAL <cp> [ALTS (<fr> <fc> <tr> <tc> <cp>)...]
   DEPTH <d> NODES <n> TTHITS <n> TIME <ms> ENGINE python STATUS completed|timeout
-> BESTMOVE NONE            (no legal moves)
   A time limit of 0 or less means none. alternatives (default 0) is how
   many of the next best moves to score as well; they are searched to the
   same depth as the best move, so their scores compare with EVAL, and one
   that the time limit cuts off is left out.
   The trailing groups of four tokens are the earlier positions of the game
   since the last capture or pawn move (FEN piece placement, side, castling
   rights, en passant square as "row,col" or "-"). A position the search
   reaches again counts as a draw when its earlier occurrence is on the
   line being searched, or when it has occurred twice before in the game.
   A promotion is always to a queen.

EVAL and PERFT are not used by the web app; the tests use them to check
that both engines evaluate alike and generate the right moves.

A line that cannot be parsed is answered with "ERROR <reason>".
"""

from __future__ import annotations

import math
import sys
import time

PROTOCOL_VERSION = 2

# ============================================================
#  Board representation
# ============================================================
#
# 10x12 mailbox: the 64 squares sit inside a border of OFFBOARD cells so a
# piece stepping off the board lands on a sentinel instead of needing a
# bounds check. Row 0 is rank 8, as in the protocol.

EMPTY, WP, WN, WB, WR, WQ, WK, BP, BN, BB, BR, BQ, BK, OFFBOARD = range(14)
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = range(6)
WHITE, BLACK = 0, 1
CASTLE_WK, CASTLE_WQ, CASTLE_BK, CASTLE_BQ = 1, 2, 4, 8

PIECE_CHARS = '.PNBRQKpnbrqk'
# Lookups by piece code; index 0 (empty) and 13 (off board) are placeholders
COLOR_OF = [-1] + [WHITE] * 6 + [BLACK] * 6 + [-1]
TYPE_OF = [-1] + [PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING] * 2 + [-1]


def SQ(row, col):
    return 21 + row * 10 + col


ROW_OF = [sq // 10 - 2 for sq in range(120)]
COL_OF = [sq % 10 - 1 for sq in range(120)]
SQUARES = [SQ(r, c) for r in range(8) for c in range(8)]
# (square, row, file index 1..8) for loops that need all three
SQUARE_ROW_FILE = [(SQ(r, c), r, c + 1) for r in range(8) for c in range(8)]

A1, B1, C1, D1, E1, F1, G1, H1 = range(91, 99)
A8, B8, C8, D8, E8, F8, G8, H8 = range(21, 29)

KNIGHT_DIRS = (-21, -19, -12, -8, 8, 12, 19, 21)
KING_DIRS = (-11, -10, -9, -1, 1, 9, 10, 11)
BISHOP_DIRS = (-11, -9, 9, 11)
ROOK_DIRS = (-10, -1, 1, 10)


def _on_board(sq):
    return 21 <= sq <= 98 and 1 <= sq % 10 <= 8


def _ray(sq, step):
    squares = []
    sq += step
    while _on_board(sq):
        squares.append(sq)
        sq += step
    return tuple(squares)


# Precomputed targets so the hot loops need no bounds checks
KNIGHT_TARGETS = [tuple(sq + d for d in KNIGHT_DIRS if _on_board(sq + d)) if _on_board(sq) else ()
                  for sq in range(120)]
KING_TARGETS = [tuple(sq + d for d in KING_DIRS if _on_board(sq + d)) if _on_board(sq) else ()
                for sq in range(120)]
BISHOP_RAYS = [tuple(r for r in (_ray(sq, d) for d in BISHOP_DIRS) if r) if _on_board(sq) else ()
               for sq in range(120)]
ROOK_RAYS = [tuple(r for r in (_ray(sq, d) for d in ROOK_DIRS) if r) if _on_board(sq) else ()
             for sq in range(120)]
QUEEN_RAYS = [tuple(r for r in (_ray(sq, d) for d in KING_DIRS) if r) if _on_board(sq) else ()
              for sq in range(120)]
# KING_ZONE[k][sq]: sq is the square k or one next to it (nothing for k = 0, no king)
KING_ZONE = [[_on_board(k) and _on_board(sq) and abs(sq // 10 - k // 10) <= 1 and abs(sq % 10 - k % 10) <= 1
              for sq in range(120)] for k in range(120)]

board = [OFFBOARD] * 120
side = WHITE          # side to move
castling = 0          # CASTLE_* bits
ep_square = 0         # en passant target, 0 if none can be captured
halfmove = 0          # plies since the last capture or pawn move
king_sq = [0, 0]
piece_count = [0] * 14
hash_key = 0
# Material plus piece-square score, kept up to date by every move.
# Positive is good for White. phase runs from 24 (all pieces) to 0.
psq_mg = 0
psq_eg = 0
phase = 0

# A move packs from, to, the promotion piece type and a flag into one int:
# from | to << 7 | promo << 14 | flag << 17
FLAG_NONE, FLAG_DOUBLE, FLAG_EP, FLAG_CASTLE = range(4)

MAX_PLY = 96
MAX_GAME = 1024
# A deeper perft takes minutes; a stray request must not stall the engine
MAX_PERFT_DEPTH = 6
undo_stack = []
# Hashes of the positions before the current one: first the game history
# sent with BESTMOVE, then the moves made by the search. The root of the
# search is pushed at index root_rep.
rep_stack = []
root_rep = 0

# ============================================================
#  Evaluation tables
# ============================================================

MATERIAL_MG = (100, 320, 330, 500, 900, 0)
MATERIAL_EG = (120, 310, 330, 520, 940, 0)
PHASE_WEIGHT = (0, 1, 1, 2, 4, 0)

# Piece-square tables from White's side, row 0 = rank 8. Black mirrors them.
PST_MG = (
    (  # pawn
        0, 0, 0, 0, 0, 0, 0, 0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5, 5, 10, 25, 25, 10, 5, 5,
        0, 0, 0, 20, 20, 0, 0, 0,
        5, -5, -10, 0, 0, -10, -5, 5,
        5, 10, 10, -20, -20, 10, 10, 5,
        0, 0, 0, 0, 0, 0, 0, 0),
    (  # knight
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20, 0, 0, 0, 0, -20, -40,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -40, -20, 0, 5, 5, 0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50),
    (  # bishop
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 5, 0, 0, 0, 0, 5, -10,
        -20, -10, -10, -10, -10, -10, -10, -20),
    (  # rook
        0, 0, 0, 0, 0, 0, 0, 0,
        5, 10, 10, 10, 10, 10, 10, 5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        0, 0, 0, 5, 5, 0, 0, 0),
    (  # queen
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5,
        0, 0, 5, 5, 5, 5, 0, -5,
        -10, 5, 5, 5, 5, 5, 0, -10,
        -10, 0, 5, 0, 0, 0, 0, -10,
        -20, -10, -10, -5, -5, -10, -10, -20),
    (  # king, middlegame: stay behind the pawns
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -10, -20, -20, -20, -20, -20, -20, -10,
        20, 20, 0, 0, 0, 0, 20, 20,
        20, 30, 10, 0, 0, 10, 30, 20),
)

PST_EG = (
    (  # pawn: advancing matters more than the file
        0, 0, 0, 0, 0, 0, 0, 0,
        60, 60, 60, 60, 60, 60, 60, 60,
        35, 35, 35, 35, 35, 35, 35, 35,
        20, 20, 20, 20, 20, 20, 20, 20,
        10, 10, 10, 10, 10, 10, 10, 10,
        5, 5, 5, 5, 5, 5, 5, 5,
        0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0),
    PST_MG[KNIGHT],
    PST_MG[BISHOP],
    (0,) * 64,  # rook
    (  # queen
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5,
        -5, 0, 5, 5, 5, 5, 0, -5,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -20, -10, -10, -5, -5, -10, -10, -20),
    (  # king, endgame: come to the centre
        -50, -30, -30, -30, -30, -30, -30, -50,
        -30, -10, -10, -10, -10, -10, -10, -30,
        -30, -10, 20, 30, 30, 20, -10, -30,
        -30, -10, 30, 40, 40, 30, -10, -30,
        -30, -10, 30, 40, 40, 30, -10, -30,
        -30, -10, 20, 30, 30, 20, -10, -30,
        -30, -20, -10, 0, 0, -10, -20, -30,
        -50, -40, -30, -20, -20, -30, -40, -50),
)

# Evaluation weights (centipawns, middlegame / endgame)
BISHOP_PAIR_MG, BISHOP_PAIR_EG = 30, 50
DOUBLED_MG, DOUBLED_EG = 8, 16
ISOLATED_MG, ISOLATED_EG = 12, 14
# Passed pawn bonus by how far the pawn has come (index 1 = still at home)
PASSED_MG = (0, 0, 5, 10, 20, 35, 60, 0)
PASSED_EG = (0, 5, 10, 20, 40, 70, 120, 0)
# In the endgame the kings decide whether a passed pawn gets through: per
# step the pawn has taken past its second row, this much per square that
# the enemy king is away from the square in front of it, and less this
# much per square that our own king is
PASSER_ENEMY_KING, PASSER_OWN_KING = 4, 2
MOBILITY_BASE = (0, 4, 6, 7, 13, 0)
MOBILITY_MG = (0, 4, 5, 2, 1, 0)
MOBILITY_EG = (0, 4, 5, 4, 2, 0)
ROOK_OPEN_MG, ROOK_OPEN_EG = 20, 10
ROOK_SEMI_MG, ROOK_SEMI_EG = 10, 5
ROOK_SEVENTH_MG, ROOK_SEVENTH_EG = 15, 25
SHIELD_NEAR, SHIELD_FAR, SHIELD_MISSING, KING_OPEN_FILE = 12, 6, 10, 15
TEMPO = 10
# King attack: every square next to the king (or the king's own) that an
# enemy piece attacks counts that piece's weight. Once two pieces or more
# take part, the king's side loses units * units // KING_ATTACK_DIVISOR in
# the middlegame, at most KING_ATTACK_MAX: a lone attacker is seldom a
# threat, and each one that joins makes the others more dangerous.
KING_ATTACK_WEIGHT = (0, 2, 2, 3, 5, 0)
KING_ATTACK_MIN_ATTACKERS = 2
KING_ATTACK_DIVISOR, KING_ATTACK_MAX = 4, 500

# PIECE_MG / PIECE_EG[piece][sq120]: material + table value, signed for the colour
PIECE_MG = [[0] * 120 for _ in range(14)]
PIECE_EG = [[0] * 120 for _ in range(14)]
PIECE_PHASE = [0] * 14
CASTLE_MASK = [15] * 120
LMR = [[0] * 64 for _ in range(64)]

MASK64 = 0xFFFFFFFFFFFFFFFF
_prng_state = 0x123456789ABCDEF


def _next_random():
    global _prng_state
    _prng_state ^= (_prng_state << 13) & MASK64
    _prng_state ^= _prng_state >> 7
    _prng_state ^= (_prng_state << 17) & MASK64
    return _prng_state


Z_PIECE = [[0] * 120 for _ in range(14)]
for _p in range(WP, BK + 1):
    for _sq in SQUARES:
        Z_PIECE[_p][_sq] = _next_random()
Z_SIDE = _next_random()
Z_CASTLE = [_next_random() for _ in range(16)]
Z_EP = [_next_random() for _ in range(8)]

for _p in range(WP, BK + 1):
    _type = TYPE_OF[_p]
    PIECE_PHASE[_p] = PHASE_WEIGHT[_type]
    for _r in range(8):
        for _c in range(8):
            _idx = (_r if COLOR_OF[_p] == WHITE else 7 - _r) * 8 + _c
            _sign = 1 if COLOR_OF[_p] == WHITE else -1
            PIECE_MG[_p][SQ(_r, _c)] = _sign * (MATERIAL_MG[_type] + PST_MG[_type][_idx])
            PIECE_EG[_p][SQ(_r, _c)] = _sign * (MATERIAL_EG[_type] + PST_EG[_type][_idx])

CASTLE_MASK[E1] = 15 & ~(CASTLE_WK | CASTLE_WQ)
CASTLE_MASK[H1] = 15 & ~CASTLE_WK
CASTLE_MASK[A1] = 15 & ~CASTLE_WQ
CASTLE_MASK[E8] = 15 & ~(CASTLE_BK | CASTLE_BQ)
CASTLE_MASK[H8] = 15 & ~CASTLE_BK
CASTLE_MASK[A8] = 15 & ~CASTLE_BQ

for _d in range(1, 64):
    for _n in range(1, 64):
        LMR[_d][_n] = int(0.75 + math.log(_d) * math.log(_n) / 2.25)


def _aligned(a, b):
    dr = ROW_OF[a] - ROW_OF[b]
    dc = COL_OF[a] - COL_OF[b]
    return dr == 0 or dc == 0 or dr == dc or dr == -dc


# ALIGNED[a][b]: the two squares share a rank, file or diagonal
ALIGNED = [[_on_board(a) and _on_board(b) and _aligned(a, b) for b in range(120)] for a in range(120)]


def tdiv(a, b):
    """Integer division that rounds towards zero, as C++ does."""
    return a // b if a >= 0 else -((-a) // b)


# ============================================================
#  Position set-up and updates
# ============================================================

def add_piece(piece, sq):
    global hash_key, psq_mg, psq_eg, phase
    board[sq] = piece
    hash_key ^= Z_PIECE[piece][sq]
    psq_mg += PIECE_MG[piece][sq]
    psq_eg += PIECE_EG[piece][sq]
    phase += PIECE_PHASE[piece]
    piece_count[piece] += 1
    if piece == WK:
        king_sq[WHITE] = sq
    elif piece == BK:
        king_sq[BLACK] = sq


def remove_piece(sq):
    global hash_key, psq_mg, psq_eg, phase
    piece = board[sq]
    board[sq] = EMPTY
    hash_key ^= Z_PIECE[piece][sq]
    psq_mg -= PIECE_MG[piece][sq]
    psq_eg -= PIECE_EG[piece][sq]
    phase -= PIECE_PHASE[piece]
    piece_count[piece] -= 1


def clear_board():
    global side, castling, ep_square, halfmove, hash_key, psq_mg, psq_eg, phase, root_rep
    for i in range(120):
        board[i] = OFFBOARD
    for sq in SQUARES:
        board[sq] = EMPTY
    for i in range(14):
        piece_count[i] = 0
    side = WHITE
    castling = 0
    ep_square = 0
    halfmove = 0
    king_sq[WHITE] = king_sq[BLACK] = 0
    hash_key = 0
    psq_mg = psq_eg = phase = 0
    del undo_stack[:]
    del rep_stack[:]
    root_rep = 0


def finish_setup(turn, rights, ep_row, ep_col):
    """Finish loading: side, castling rights and en passant square.

    A castling right only counts while king and rook are at home, and an en
    passant square only if the pawn that double-stepped is there and one of
    the mover's pawns stands beside it. The hash follows the same rule, so a
    position reached again compares equal.
    """
    global side, castling, ep_square, hash_key
    # A second king of the same colour is not chess; keep the first one.
    king_sq[WHITE] = king_sq[BLACK] = 0
    for sq in SQUARES:
        piece = board[sq]
        if piece == WK and not king_sq[WHITE]:
            king_sq[WHITE] = sq
        if piece == BK and not king_sq[BLACK]:
            king_sq[BLACK] = sq

    side = turn
    castling = 0
    for ch in rights:
        if ch == 'K' and board[E1] == WK and board[H1] == WR:
            castling |= CASTLE_WK
        elif ch == 'Q' and board[E1] == WK and board[A1] == WR:
            castling |= CASTLE_WQ
        elif ch == 'k' and board[E8] == BK and board[H8] == BR:
            castling |= CASTLE_BK
        elif ch == 'q' and board[E8] == BK and board[A8] == BR:
            castling |= CASTLE_BQ

    ep_square = 0
    if 0 <= ep_col < 8 and ep_row == (2 if side == WHITE else 5):
        target = SQ(ep_row, ep_col)
        pawn_sq = target + (10 if side == WHITE else -10)
        mine, theirs = (WP, BP) if side == WHITE else (BP, WP)
        if (board[target] == EMPTY and board[pawn_sq] == theirs
                and (board[pawn_sq - 1] == mine or board[pawn_sq + 1] == mine)):
            ep_square = target

    if side == BLACK:
        hash_key ^= Z_SIDE
    hash_key ^= Z_CASTLE[castling]
    if ep_square:
        hash_key ^= Z_EP[COL_OF[ep_square]]


def load_position(board64, rights, turn, ep_row, ep_col):
    """Load a position from the protocol fields. Raises ValueError on bad input."""
    if len(board64) != 64:
        raise ValueError('bad board')
    clear_board()
    for i, ch in enumerate(board64):
        piece = PIECE_CHARS.find(ch)
        if piece < 0:
            raise ValueError('bad piece')
        if piece != EMPTY:
            add_piece(piece, SQUARES[i])
    finish_setup(turn, rights, ep_row, ep_col)


def serialize_board():
    return ''.join(PIECE_CHARS[board[sq]] for sq in SQUARES)


# ============================================================
#  Attacks
# ============================================================

def attacked(sq, by):
    """Is the square attacked by any piece of colour `by`?"""
    b = board
    if by == WHITE:
        if b[sq + 11] == WP or b[sq + 9] == WP:
            return True
        knight, bishop, rook, queen, king = WN, WB, WR, WQ, WK
    else:
        if b[sq - 11] == BP or b[sq - 9] == BP:
            return True
        knight, bishop, rook, queen, king = BN, BB, BR, BQ, BK
    for t in KNIGHT_TARGETS[sq]:
        if b[t] == knight:
            return True
    for t in KING_TARGETS[sq]:
        if b[t] == king:
            return True
    for ray in BISHOP_RAYS[sq]:
        for t in ray:
            piece = b[t]
            if piece:
                if piece == bishop or piece == queen:
                    return True
                break
    for ray in ROOK_RAYS[sq]:
        for t in ray:
            piece = b[t]
            if piece:
                if piece == rook or piece == queen:
                    return True
                break
    return False


def in_check_now():
    return bool(king_sq[side]) and attacked(king_sq[side], side ^ 1)


# ============================================================
#  Move generation
# ============================================================

PROMO_QUEEN_ONLY, PROMO_QUEEN_KNIGHT, PROMO_ALL = range(3)
_PROMO_SETS = ((QUEEN,), (QUEEN, KNIGHT), (QUEEN, KNIGHT, ROOK, BISHOP))


def generate_moves(noisy_only, promo_mode):
    """Pseudo-legal moves for the side to move: every rule except "do not
    leave your own king in check", which the caller tests after making the
    move. Castling is only generated when it is fully legal. With
    noisy_only, only captures and promotions are produced (for the
    quiescence search)."""
    b = board
    moves = []
    add = moves.append
    us = side
    them = us ^ 1
    color_of = COLOR_OF
    if us == WHITE:
        forward, start_row, promo_from = -10, 6, 1
    else:
        forward, start_row, promo_from = 10, 1, 6
    promos = _PROMO_SETS[promo_mode]

    for frm in SQUARES:
        piece = b[frm]
        if not piece or color_of[piece] != us:
            continue
        kind = TYPE_OF[piece]

        if kind == PAWN:
            row = ROW_OF[frm]
            to = frm + forward
            if b[to] == EMPTY:
                if row == promo_from:
                    for promo in promos:
                        add(frm | to << 7 | promo << 14)
                elif not noisy_only:
                    add(frm | to << 7)
                    if row == start_row and b[to + forward] == EMPTY:
                        add(frm | (to + forward) << 7 | FLAG_DOUBLE << 17)
            for to in (frm + forward - 1, frm + forward + 1):
                target = b[to]
                if target and color_of[target] == them:
                    if row == promo_from:
                        for promo in promos:
                            add(frm | to << 7 | promo << 14)
                    else:
                        add(frm | to << 7)
                elif to == ep_square and ep_square:
                    add(frm | to << 7 | FLAG_EP << 17)
        elif kind == KNIGHT or kind == KING:
            for to in (KNIGHT_TARGETS if kind == KNIGHT else KING_TARGETS)[frm]:
                target = b[to]
                if target == EMPTY:
                    if not noisy_only:
                        add(frm | to << 7)
                elif color_of[target] == them:
                    add(frm | to << 7)
        else:
            rays = (BISHOP_RAYS if kind == BISHOP else ROOK_RAYS if kind == ROOK else QUEEN_RAYS)[frm]
            for ray in rays:
                for to in ray:
                    target = b[to]
                    if target == EMPTY:
                        if not noisy_only:
                            add(frm | to << 7)
                    else:
                        if color_of[target] == them:
                            add(frm | to << 7)
                        break

    if noisy_only:
        return moves

    # Castling: right held, rook at home, squares between empty, and the
    # king neither in check nor passing over or landing on an attacked square.
    if us == WHITE and b[E1] == WK:
        if (castling & CASTLE_WK and b[H1] == WR and b[F1] == EMPTY and b[G1] == EMPTY
                and not attacked(E1, BLACK) and not attacked(F1, BLACK) and not attacked(G1, BLACK)):
            add(E1 | G1 << 7 | FLAG_CASTLE << 17)
        if (castling & CASTLE_WQ and b[A1] == WR and b[D1] == EMPTY and b[C1] == EMPTY
                and b[B1] == EMPTY and not attacked(E1, BLACK) and not attacked(D1, BLACK)
                and not attacked(C1, BLACK)):
            add(E1 | C1 << 7 | FLAG_CASTLE << 17)
    elif us == BLACK and b[E8] == BK:
        if (castling & CASTLE_BK and b[H8] == BR and b[F8] == EMPTY and b[G8] == EMPTY
                and not attacked(E8, WHITE) and not attacked(F8, WHITE) and not attacked(G8, WHITE)):
            add(E8 | G8 << 7 | FLAG_CASTLE << 17)
        if (castling & CASTLE_BQ and b[A8] == BR and b[D8] == EMPTY and b[C8] == EMPTY
                and b[B8] == EMPTY and not attacked(E8, WHITE) and not attacked(D8, WHITE)
                and not attacked(C8, WHITE)):
            add(E8 | C8 << 7 | FLAG_CASTLE << 17)
    return moves


# ============================================================
#  Make / unmake: the only place where the position changes
# ============================================================

def make_move(move):
    global side, castling, ep_square, halfmove, hash_key
    frm = move & 127
    to = (move >> 7) & 127
    promo = (move >> 14) & 7
    flag = (move >> 17) & 3
    piece = board[frm]
    cap_sq = to
    if flag == FLAG_EP:
        cap_sq = to + (10 if side == WHITE else -10)
    captured = board[cap_sq]

    undo_stack.append((move, captured, castling, ep_square, halfmove, psq_mg, psq_eg, phase, hash_key))
    rep_stack.append(hash_key)

    if ep_square:
        hash_key ^= Z_EP[COL_OF[ep_square]]
    hash_key ^= Z_CASTLE[castling]
    halfmove += 1

    if captured != EMPTY:
        remove_piece(cap_sq)
        halfmove = 0
    elif piece == WP or piece == BP:
        halfmove = 0

    remove_piece(frm)
    add_piece(side * 6 + promo + 1 if promo else piece, to)

    if flag == FLAG_CASTLE:
        if to > frm:
            rook_from, rook_to = to + 1, to - 1
        else:
            rook_from, rook_to = to - 2, to + 1
        rook = board[rook_from]
        remove_piece(rook_from)
        add_piece(rook, rook_to)

    castling &= CASTLE_MASK[frm] & CASTLE_MASK[to]
    ep_square = 0
    if flag == FLAG_DOUBLE:
        enemy_pawn = BP if side == WHITE else WP
        if board[to - 1] == enemy_pawn or board[to + 1] == enemy_pawn:
            ep_square = (frm + to) // 2
    hash_key ^= Z_CASTLE[castling]
    if ep_square:
        hash_key ^= Z_EP[COL_OF[ep_square]]

    side ^= 1
    hash_key ^= Z_SIDE


def unmake_move():
    global side, castling, ep_square, halfmove, hash_key, psq_mg, psq_eg, phase
    move, captured, old_castling, old_ep, old_halfmove, old_mg, old_eg, old_phase, old_hash = undo_stack.pop()
    rep_stack.pop()
    side ^= 1

    frm = move & 127
    to = (move >> 7) & 127
    flag = (move >> 17) & 3

    if flag == FLAG_CASTLE:
        if to > frm:
            rook_from, rook_to = to + 1, to - 1
        else:
            rook_from, rook_to = to - 2, to + 1
        rook = board[rook_to]
        remove_piece(rook_to)
        add_piece(rook, rook_from)

    piece = board[to]
    remove_piece(to)
    add_piece(side * 6 + 1 if (move >> 14) & 7 else piece, frm)

    if captured:
        cap_sq = to + (10 if side == WHITE else -10) if flag == FLAG_EP else to
        add_piece(captured, cap_sq)

    castling = old_castling
    ep_square = old_ep
    halfmove = old_halfmove
    psq_mg = old_mg
    psq_eg = old_eg
    phase = old_phase
    hash_key = old_hash


def make_null():
    """Pass the turn (used by null-move pruning only)."""
    global side, ep_square, halfmove, hash_key
    undo_stack.append((ep_square, halfmove, hash_key))
    rep_stack.append(hash_key)
    if ep_square:
        hash_key ^= Z_EP[COL_OF[ep_square]]
    ep_square = 0
    halfmove = 0  # a repetition cannot reach across a pass
    side ^= 1
    hash_key ^= Z_SIDE


def unmake_null():
    global side, ep_square, halfmove, hash_key
    ep_square, halfmove, hash_key = undo_stack.pop()
    rep_stack.pop()
    side ^= 1


def make_if_legal(move):
    """Make the move if it is legal. Returns False (and changes nothing) if not."""
    make_move(move)
    king = king_sq[side ^ 1]
    if king and attacked(king, side):
        unmake_move()
        return False
    return True


def generate_legal(promo_mode):
    """All legal moves of the side to move."""
    legal = []
    for move in generate_moves(False, promo_mode):
        if make_if_legal(move):
            unmake_move()
            legal.append(move)
    return legal


def has_legal_move():
    for move in generate_moves(False, PROMO_QUEEN_ONLY):
        if make_if_legal(move):
            unmake_move()
            return True
    return False


def is_capture(move):
    return board[(move >> 7) & 127] != EMPTY or (move >> 17) & 3 == FLAG_EP


def is_insufficient_material():
    """Checks if the current board state is a draw due to insufficient material.
    Cases: K vs K, K+N vs K, and kings with any number of bishops that all
    stand on squares of one colour (K+B vs K, K+B vs K+B same colour).
    """
    pc = piece_count
    if pc[WP] or pc[BP] or pc[WR] or pc[BR] or pc[WQ] or pc[BQ]:
        return False
    knights = pc[WN] + pc[BN]
    bishops = pc[WB] + pc[BB]
    if knights == 0:
        if bishops <= 1:
            return True
        light = dark = 0
        for sq in SQUARES:
            if board[sq] == WB or board[sq] == BB:
                if (ROW_OF[sq] + COL_OF[sq]) % 2 == 0:
                    light += 1
                else:
                    dark += 1
        return light == 0 or dark == 0
    # A single knight draws only against a bare king
    return knights == 1 and bishops == 0


def perft(depth):
    nodes = 0
    for move in generate_moves(False, PROMO_ALL):
        if not make_if_legal(move):
            continue
        nodes += 1 if depth <= 1 else perft(depth - 1)
        unmake_move()
    return nodes


# ============================================================
#  Static evaluation
# ============================================================

def king_distance(a, b):
    """King moves from one square to another, 0 to 7."""
    return max(abs(ROW_OF[a] - ROW_OF[b]), abs(COL_OF[a] - COL_OF[b]))


def centre_distance(sq):
    """Distance of a square from the four centre squares, 0 to 6."""
    r, c = ROW_OF[sq], COL_OF[sq]
    return max(3 - r, r - 4) + max(3 - c, c - 4)


def evaluate():
    """Static evaluation of the current board in centipawns.
    Positive => white advantage, negative => black advantage.

    Material and piece-square tables (kept incrementally), bishop pair,
    mobility, pawn structure (doubled, isolated, passed, and how near the
    kings are to a passed pawn's path), rooks on open files and on the
    seventh rank, pawn shelter of the king, pieces attacking the squares
    around the enemy king, and for bare endgames a term that drives the
    losing king to the edge. Middlegame and endgame scores are blended by
    the material left on the board.
    """
    if is_insufficient_material():
        return 0

    b = board
    pc = piece_count
    mg = psq_mg
    eg = psq_eg
    color_of = COLOR_OF
    type_of = TYPE_OF

    # Pawns per file; index 0 and 9 stand for the files beside a and h.
    # black_rear / white_rear: per file the row of the pawn nearest its own
    # side. A white pawn is passed when no black pawn on its own or a
    # neighbouring file stands on a row in front of it.
    white_pawns = [0] * 10
    black_pawns = [0] * 10
    black_rear = [8] * 10
    white_rear = [-1] * 10
    pieces = []
    for sq, r, f in SQUARE_ROW_FILE:
        piece = b[sq]
        if not piece:
            continue
        pieces.append((sq, r, f, piece))
        if piece == WP:
            white_pawns[f] += 1
            if r > white_rear[f]:
                white_rear[f] = r
        elif piece == BP:
            black_pawns[f] += 1
            if r < black_rear[f]:
                black_rear[f] = r
    pawns = (white_pawns, black_pawns)
    king_zone = (KING_ZONE[king_sq[WHITE]], KING_ZONE[king_sq[BLACK]])
    attack_units = [0, 0]  # by the attacking colour
    attackers = [0, 0]

    for sq, r, f, piece in pieces:
        us = color_of[piece]
        them = us ^ 1
        kind = type_of[piece]
        sign = 1 if us == WHITE else -1

        if kind == PAWN:
            own = pawns[us]
            if own[f] > 1:
                mg -= sign * DOUBLED_MG
                eg -= sign * DOUBLED_EG
            if not own[f - 1] and not own[f + 1]:
                mg -= sign * ISOLATED_MG
                eg -= sign * ISOLATED_EG
            if us == WHITE:
                passed = black_rear[f - 1] >= r and black_rear[f] >= r and black_rear[f + 1] >= r
                advance = 7 - r  # 1 on the home row .. 6 one step from promotion
            else:
                passed = white_rear[f - 1] <= r and white_rear[f] <= r and white_rear[f + 1] <= r
                advance = r
            if passed:
                mg += sign * PASSED_MG[advance]
                eg += sign * PASSED_EG[advance]
                if king_sq[WHITE] and king_sq[BLACK]:
                    front = sq + (-10 if us == WHITE else 10)
                    eg += sign * (advance - 1) * (PASSER_ENEMY_KING * king_distance(king_sq[them], front)
                                                  - PASSER_OWN_KING * king_distance(king_sq[us], front))
            continue

        if kind == KING:
            # Pawn shelter, only while the king is on its two home rows
            home_row = 7 if us == WHITE else 0
            if abs(r - home_row) <= 1:
                ahead = -10 if us == WHITE else 10
                pawn = WP if us == WHITE else BP
                shelter = 0
                c = f - 1
                for kc in range(max(0, c - 1), min(7, c + 1) + 1):
                    s = SQ(r, kc)
                    if b[s + ahead] == pawn:
                        shelter += SHIELD_NEAR
                    elif b[s + 2 * ahead] == pawn:
                        shelter += SHIELD_FAR
                    else:
                        shelter -= SHIELD_MISSING
                        if not pawns[us][kc + 1]:
                            shelter -= KING_OPEN_FILE
                mg += sign * shelter
            continue

        # Mobility: squares the piece can move to. Squares it attacks
        # around the enemy king count for the king attack, whoever stands
        # on them.
        mobility = 0
        zone_attacks = 0
        zone = king_zone[them]
        if kind == KNIGHT:
            for t in KNIGHT_TARGETS[sq]:
                target = b[t]
                if not target or color_of[target] == them:
                    mobility += 1
                if zone[t]:
                    zone_attacks += 1
        else:
            rays = (BISHOP_RAYS if kind == BISHOP else ROOK_RAYS if kind == ROOK else QUEEN_RAYS)[sq]
            for ray in rays:
                for t in ray:
                    if zone[t]:
                        zone_attacks += 1
                    target = b[t]
                    if not target:
                        mobility += 1
                    else:
                        if color_of[target] == them:
                            mobility += 1
                        break
        mobility -= MOBILITY_BASE[kind]
        mg += sign * MOBILITY_MG[kind] * mobility
        eg += sign * MOBILITY_EG[kind] * mobility
        if zone_attacks:
            attack_units[us] += KING_ATTACK_WEIGHT[kind] * zone_attacks
            attackers[us] += 1

        if kind == ROOK:
            if not pawns[us][f]:
                if not pawns[them][f]:
                    mg += sign * ROOK_OPEN_MG
                    eg += sign * ROOK_OPEN_EG
                else:
                    mg += sign * ROOK_SEMI_MG
                    eg += sign * ROOK_SEMI_EG
            # On the seventh with the enemy king cut off on the eighth
            seventh, eighth = (1, 0) if us == WHITE else (6, 7)
            if r == seventh and king_sq[them] and ROW_OF[king_sq[them]] == eighth:
                mg += sign * ROOK_SEVENTH_MG
                eg += sign * ROOK_SEVENTH_EG

    for s in (WHITE, BLACK):
        if attackers[s] >= KING_ATTACK_MIN_ATTACKERS:
            danger = min(KING_ATTACK_MAX, attack_units[s] * attack_units[s] // KING_ATTACK_DIVISOR)
            mg += danger if s == WHITE else -danger

    if pc[WB] >= 2:
        mg += BISHOP_PAIR_MG
        eg += BISHOP_PAIR_EG
    if pc[BB] >= 2:
        mg -= BISHOP_PAIR_MG
        eg -= BISHOP_PAIR_EG

    # Endgame knowledge
    material = [0, 0]
    for s in (WHITE, BLACK):
        for kind in range(PAWN, QUEEN + 1):
            material[s] += pc[s * 6 + kind + 1] * MATERIAL_EG[kind]
    strong = WHITE if material[WHITE] >= material[BLACK] else BLACK
    weak = strong ^ 1
    lead = material[strong] - material[weak]
    strong_sign = 1 if strong == WHITE else -1
    strong_has_pawns = pc[strong * 6 + 1] > 0
    weak_has_pawns = pc[weak * 6 + 1] > 0

    if (not strong_has_pawns and not weak_has_pawns and material[weak] == 0
            and pc[strong * 6 + KNIGHT + 1] == 2 and material[strong] == 2 * MATERIAL_EG[KNIGHT]):
        return 0  # two knights cannot force mate
    if (lead >= 400 and not weak_has_pawns and material[weak] <= MATERIAL_EG[BISHOP]
            and king_sq[WHITE] and king_sq[BLACK]):
        # Winning material against a nearly bare king: push that king to
        # the edge and bring our own king up.
        kings_apart = (abs(ROW_OF[king_sq[WHITE]] - ROW_OF[king_sq[BLACK]])
                       + abs(COL_OF[king_sq[WHITE]] - COL_OF[king_sq[BLACK]]))
        eg += strong_sign * (10 * centre_distance(king_sq[weak]) + 4 * (14 - kings_apart))
    elif not strong_has_pawns and not weak_has_pawns and lead < 400:
        # Without pawns a small material lead rarely wins (R v B, R+B v R)
        mg = tdiv(mg, 4)
        eg = tdiv(eg, 4)

    p = 24 if phase > 24 else phase
    score = tdiv(mg * p + eg * (24 - p), 24)
    return score + (TEMPO if side == WHITE else -TEMPO)


# hash -> evaluate() for positions already scored in this search. The same
# position comes back often (re-searches, transpositions) and evaluate() is
# by far the most expensive call in Python.
eval_cache = {}


def eval_for_side():
    e = eval_cache.get(hash_key)
    if e is None:
        e = eval_cache[hash_key] = evaluate()
    return e if side == WHITE else -e


# ============================================================
#  Search
# ============================================================

INF = 32000
MATE = 31000
MATE_BOUND = MATE - 512  # scores beyond this are forced mates
MAX_DEPTH = 64

# Pruning margins in centipawns. A node this far above beta at the given
# depth is not searched (reverse futility); a quiet move this far below
# alpha is not either (futility).
RFP_MAX_DEPTH, RFP_MARGIN_PER_PLY = 3, 120
FUTILITY_MAX_DEPTH, FUTILITY_MARGIN, FUTILITY_MARGIN_PER_PLY = 2, 100, 100
# Null move: tried from this depth, searched this much shallower
NULL_MIN_DEPTH = 3


def null_reduction(depth):
    return 2 + depth // 4


# Quiescence: a capture whose gain plus this margin cannot reach alpha is
# skipped, and a promotion counts as gaining this much on top
DELTA_MARGIN, PROMOTION_GAIN = 200, 800
# Aspiration window around the last score, from this depth; it doubles on
# every failure and is given up once it is wider than the limit
ASPIRATION_MIN_DEPTH, ASPIRATION_WINDOW, ASPIRATION_LIMIT = 4, 40, 600
# History scores are halved once one of them passes this
HISTORY_LIMIT = 1 << 20
# Percentage of the time limit the main search may use when alternatives
# are wanted as well. Each of them is a full-window search at the final
# depth and costs about as much as the main search's last iteration.
MAIN_SHARE_WITH_ALTS = 50

BOUND_EXACT, BOUND_LOWER, BOUND_UPPER = 1, 2, 3

# The same table as in main.cpp, so that both engines search the same tree:
# TT_SLOTS slots of two entries (key, move, score, depth, bound); the first
# keeps the deepest search of the slot, the second is always replaced.
TT_SLOTS = 1 << 19
transposition_table = [None] * (2 * TT_SLOTS)

start_time = 0.0
deadline_ms = -1.0  # hard stop, measured from start_time
search_aborted = False
nodes_searched = 0
tthits = 0
killers = [[0, 0] for _ in range(MAX_PLY + 2)]
history_table = [[0] * 120 for _ in range(14)]


def elapsed_ms():
    return (time.perf_counter() - start_time) * 1000


def count_node():
    global nodes_searched, search_aborted
    nodes_searched += 1
    # Python searches far fewer nodes per second, so it looks at the clock
    # more often than main.cpp does.
    if nodes_searched & 31 == 0 and deadline_ms >= 0 and elapsed_ms() >= deadline_ms:
        search_aborted = True


def probe_tt(key):
    """The table entry (key, move, score, depth, bound) for the key, or None."""
    i = (key & (TT_SLOTS - 1)) << 1
    entry = transposition_table[i]
    if entry is not None and entry[0] == key:
        return entry
    entry = transposition_table[i + 1]
    if entry is not None and entry[0] == key:
        return entry
    return None


def store_tt(key, move, score, depth, bound, ply):
    # Mate scores are stored relative to the node, not to the root, so an
    # entry is still right when the position is reached at another depth.
    if score >= MATE_BOUND:
        score += ply
    elif score <= -MATE_BOUND:
        score -= ply
    table = transposition_table
    i = (key & (TT_SLOTS - 1)) << 1
    first = table[i]
    if first is None or first[0] == key or depth >= first[3]:
        if first is not None and first[0] != key:
            table[i + 1] = first
    else:
        i += 1
    old = table[i]
    if move == 0 and old is not None and old[0] == key:
        move = old[1]  # keep the known best move
    table[i] = (key, move, score, depth, bound)


def is_repetition():
    """Does the search score the current position as a draw by repetition?
    It does when the position occurred before on the line being searched,
    after the root. An occurrence in the game itself (the root included) is
    real, so it takes two of those, a threefold repetition."""
    n = len(rep_stack)
    limit = halfmove if halfmove < n else n
    key = hash_key
    in_game = 0
    back = 2
    while back <= limit:
        i = n - back
        if rep_stack[i] == key:
            if i > root_rep:
                return True
            in_game += 1
            if in_game == 2:
                return True
        back += 2
    return False


def has_non_pawn_material(s):
    base = s * 6
    pc = piece_count
    return pc[base + 2] or pc[base + 3] or pc[base + 4] or pc[base + 5]


# Knight and bishop count the same here, so that bishop takes knight
# (or the reverse) is an even trade and not a loss of ten points.
SEE_VALUE = (100, 325, 325, 500, 900, 20000)


def least_attacker(sq, by):
    """The least valuable piece of colour `by` that attacks sq, or 0."""
    b = board
    if by == WHITE:
        if b[sq + 11] == WP:
            return sq + 11
        if b[sq + 9] == WP:
            return sq + 9
        knight, bishop, rook, queen, king = WN, WB, WR, WQ, WK
    else:
        if b[sq - 11] == BP:
            return sq - 11
        if b[sq - 9] == BP:
            return sq - 9
        knight, bishop, rook, queen, king = BN, BB, BR, BQ, BK
    for t in KNIGHT_TARGETS[sq]:
        if b[t] == knight:
            return t
    best = 0
    best_type = KING + 1
    for t in KING_TARGETS[sq]:
        if b[t] == king:
            best, best_type = t, KING
    for ray in BISHOP_RAYS[sq]:
        for t in ray:
            piece = b[t]
            if piece:
                if piece == bishop and BISHOP < best_type:
                    best, best_type = t, BISHOP
                elif piece == queen and QUEEN < best_type:
                    best, best_type = t, QUEEN
                break
    for ray in ROOK_RAYS[sq]:
        for t in ray:
            piece = b[t]
            if piece:
                if piece == rook and ROOK < best_type:
                    best, best_type = t, ROOK
                elif piece == queen and QUEEN < best_type:
                    best, best_type = t, QUEEN
                break
    return best


def see(move):
    """Static exchange evaluation: the material balance of the capture
    sequence on the target square if both sides keep recapturing with their
    least valuable piece and stop when it no longer pays."""
    b = board
    frm = move & 127
    to = (move >> 7) & 127
    promo = (move >> 14) & 7
    removed = []

    target = b[to]
    if (move >> 17) & 3 == FLAG_EP:
        cap_sq = to + (10 if side == WHITE else -10)
        removed.append((cap_sq, b[cap_sq]))
        b[cap_sq] = EMPTY
        gain = [SEE_VALUE[PAWN]]
    else:
        gain = [SEE_VALUE[TYPE_OF[target]] if target else 0]
    on_square = SEE_VALUE[TYPE_OF[b[frm]]]  # value now standing on `to`
    if promo:
        gain[0] += SEE_VALUE[promo] - SEE_VALUE[PAWN]
        on_square = SEE_VALUE[promo]
    removed.append((frm, b[frm]))
    b[frm] = EMPTY

    by = side ^ 1
    while len(gain) < 31:
        attacker = least_attacker(to, by)
        if not attacker:
            break
        gain.append(on_square - gain[-1])
        on_square = SEE_VALUE[TYPE_OF[b[attacker]]]
        removed.append((attacker, b[attacker]))
        b[attacker] = EMPTY
        by ^= 1
    for sq, piece in reversed(removed):
        b[sq] = piece

    n = len(gain) - 1
    while n > 0:
        gain[n - 1] = -max(-gain[n - 1], gain[n])
        n -= 1
    return gain[0]


SCORE_TT = 1 << 30
SCORE_GOOD_CAPTURE = 1 << 24
SCORE_KILLER = 1 << 22
SCORE_BAD_CAPTURE = -(1 << 24)
# Orders a queen promotion ahead of any capture but that of a queen
SCORE_QUEEN_PROMOTION = 7000


def victim_type(move):
    """Type of the piece the move captures, -1 if none."""
    if (move >> 17) & 3 == FLAG_EP:
        return PAWN
    target = board[(move >> 7) & 127]
    return TYPE_OF[target] if target else -1


def order_moves(moves, tt_move, ply):
    """Sort the moves, best candidates first; returns (score, move) pairs.
    The sort is stable, as pickMove() in main.cpp is: moves that score the
    same stay in the order they were generated in."""
    b = board
    killer1, killer2 = killers[ply] if ply >= 0 else (0, 0)
    scored = []
    for move in moves:
        to = (move >> 7) & 127
        promo = (move >> 14) & 7
        target = b[to]
        is_ep = (move >> 17) & 3 == FLAG_EP
        if move == tt_move:
            score = SCORE_TT
        elif target or is_ep or promo:
            victim = victim_type(move)
            attacker = TYPE_OF[b[move & 127]]
            # Most valuable victim first, least valuable attacker first
            mvv_lva = (SEE_VALUE[victim] if victim >= 0 else 0) * 8 - SEE_VALUE[attacker] // 100
            if promo == QUEEN:
                mvv_lva += SCORE_QUEEN_PROMOTION
            # A capture that may lose material is checked exactly
            risky = victim < 0 or SEE_VALUE[victim] < SEE_VALUE[attacker]
            if risky and promo != QUEEN and see(move) < 0:
                score = SCORE_BAD_CAPTURE + mvv_lva
            else:
                score = SCORE_GOOD_CAPTURE + mvv_lva
        elif move == killer1:
            score = SCORE_KILLER
        elif move == killer2:
            score = SCORE_KILLER - 1
        else:
            score = history_table[b[move & 127]][to]
        scored.append((score, move))
    scored.sort(key=_first, reverse=True)
    return scored


def _first(pair):
    return pair[0]


def quiesce(alpha, beta, ply, in_check):
    """Quiescence search: play out captures and promotions (and every reply
    while in check) until the position is quiet, so that the static
    evaluation is never taken in the middle of an exchange."""
    if search_aborted:
        return 0
    count_node()
    if ply >= MAX_PLY - 1:
        return eval_for_side()

    best = -INF
    stand_pat = -INF
    if not in_check:
        stand_pat = eval_for_side()
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        best = stand_pat

    legal = 0
    for order_score, move in order_moves(generate_moves(not in_check, PROMO_QUEEN_ONLY), 0, -1):
        if not in_check:
            # Losing captures are not worth following, and neither is a
            # capture that cannot bring the score back up to alpha.
            if order_score < 0:
                break
            victim = victim_type(move)
            gain = SEE_VALUE[victim] if victim >= 0 else 0
            if (move >> 14) & 7:
                gain += PROMOTION_GAIN
            if stand_pat + gain + DELTA_MARGIN <= alpha:
                continue
        if not make_if_legal(move):
            continue
        legal += 1
        score = -quiesce(-beta, -alpha, ply + 1, in_check_now())
        unmake_move()
        if search_aborted:
            return 0
        if score > best:
            best = score
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    break

    if in_check and legal == 0:
        return -MATE + ply
    return best


def search(depth, alpha, beta, ply, in_check, null_ok):
    """Principal variation search (negamax alpha-beta).

      depth      : remaining plies to search
      alpha/beta : window, from the point of view of the side to move
      ply        : distance from the root
      in_check   : the side to move is in check
      null_ok    : a null move may be tried here

    Returns the score for the side to move.
    """
    global tthits
    if search_aborted:
        return 0

    pv_node = beta - alpha > 1

    # Draws: repetition, dead position, fifty-move rule (mate comes first)
    if is_repetition() or is_insufficient_material():
        return 0
    if halfmove >= 100 and (not in_check or has_legal_move()):
        return 0

    # A shorter mate found elsewhere makes this line pointless
    if alpha < -MATE + ply:
        alpha = -MATE + ply
    if beta > MATE - ply - 1:
        beta = MATE - ply - 1
    if alpha >= beta:
        return alpha

    if ply >= MAX_PLY - 1:
        return eval_for_side()

    if in_check:
        depth += 1  # never stop while in check
    if depth <= 0:
        return quiesce(alpha, beta, ply, False)

    count_node()

    key = hash_key
    tt_move = 0
    entry = probe_tt(key)
    if entry:
        tthits += 1
        _, tt_move, score, entry_depth, bound = entry
        if not pv_node and entry_depth >= depth:
            if score >= MATE_BOUND:
                score -= ply
            elif score <= -MATE_BOUND:
                score += ply
            if bound == BOUND_EXACT:
                return score
            if bound == BOUND_LOWER and score >= beta:
                return score
            if bound == BOUND_UPPER and score <= alpha:
                return score

    static_eval = -INF if in_check else eval_for_side()

    if not pv_node and not in_check and -MATE_BOUND < beta < MATE_BOUND:
        # Reverse futility: far above beta close to the horizon
        if depth <= RFP_MAX_DEPTH and static_eval - RFP_MARGIN_PER_PLY * depth >= beta:
            return static_eval

        # Null move: if passing still holds beta, a real move will too.
        # Not with only pawns left, where having to move can be a loss.
        if null_ok and depth >= NULL_MIN_DEPTH and static_eval >= beta and has_non_pawn_material(side):
            make_null()
            score = -search(depth - 1 - null_reduction(depth), -beta, -beta + 1, ply + 1, False, False)
            unmake_null()
            if search_aborted:
                return 0
            if score >= beta:
                return beta if score >= MATE_BOUND else score

    original_alpha = alpha
    best_score = -INF
    best_move = 0
    legal = 0
    us = side
    own_king = king_sq[us]
    b = board

    for _, move in order_moves(generate_moves(False, PROMO_QUEEN_KNIGHT), tt_move, ply):
        frm = move & 127
        piece = b[frm]
        flag = (move >> 17) & 3
        quiet = b[(move >> 7) & 127] == EMPTY and flag != FLAG_EP and not (move >> 14) & 7

        # Only a king move, an en passant capture or a piece on a line
        # with the king can expose the king when it is not in check.
        must_verify = (in_check or piece == WK or piece == BK or flag == FLAG_EP
                       or ALIGNED[frm][own_king])
        make_move(move)
        if must_verify and king_sq[us] and attacked(king_sq[us], side):
            unmake_move()
            continue
        legal += 1
        gives_check = bool(king_sq[side]) and attacked(king_sq[side], us)

        # Futility: a quiet move that cannot lift a hopeless position
        if (not pv_node and not in_check and quiet and not gives_check and legal > 1
                and depth <= FUTILITY_MAX_DEPTH
                and static_eval + FUTILITY_MARGIN + FUTILITY_MARGIN_PER_PLY * depth <= alpha
                and -MATE_BOUND < alpha < MATE_BOUND):
            unmake_move()
            continue

        new_depth = depth - 1
        if legal == 1:
            score = -search(new_depth, -beta, -alpha, ply + 1, gives_check, True)
        else:
            # Late move reduction: moves ordered far back are searched
            # shallower first and again at full depth only if they surprise.
            reduction = 0
            if (depth >= 3 and legal > (5 if pv_node else 3) and quiet
                    and not in_check and not gives_check):
                reduction = LMR[min(depth, 63)][min(legal, 63)]
                if pv_node and reduction > 0:
                    reduction -= 1
                if reduction > new_depth - 1:
                    reduction = max(0, new_depth - 1)
            score = -search(new_depth - reduction, -alpha - 1, -alpha, ply + 1, gives_check, True)
            if score > alpha and reduction > 0:
                score = -search(new_depth, -alpha - 1, -alpha, ply + 1, gives_check, True)
            if alpha < score < beta:
                score = -search(new_depth, -beta, -alpha, ply + 1, gives_check, True)
        unmake_move()
        if search_aborted:
            return 0

        if score > best_score:
            best_score = score
            best_move = move
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    if quiet:
                        slot = killers[ply]
                        if slot[0] != move:
                            slot[1] = slot[0]
                            slot[0] = move
                        row = history_table[piece]
                        to = (move >> 7) & 127
                        row[to] += depth * depth
                        if row[to] > HISTORY_LIMIT:
                            for table_row in history_table:
                                for i in range(120):
                                    table_row[i] //= 2
                    break

    if legal == 0:
        return -MATE + ply if in_check else 0  # checkmate or stalemate

    if best_score >= beta:
        bound = BOUND_LOWER
    elif best_score > original_alpha:
        bound = BOUND_EXACT
    else:
        bound = BOUND_UPPER
    store_tt(key, best_move, best_score, depth, bound, ply)
    return best_score


# The last root move found to raise alpha in the current iteration, and
# its score. It was searched to the iteration's full depth and beat every
# move searched before it, the previous best among them, so it is worth
# playing even when the iteration is cut off before it ends.
lead_move = 0
lead_score = 0


def search_root(depth, alpha, beta, root_moves, excluded):
    """Search the root moves in the given order. Moves in `excluded` are
    skipped (used to find the next best alternatives).
    Returns (best score, best move); on abort the result is void."""
    global lead_move, lead_score
    best_score = -INF
    best_move = 0
    searched = 0
    for i in range(len(root_moves)):
        move = root_moves[i]
        if move in excluded:
            continue
        make_move(move)
        gives_check = in_check_now()
        if searched == 0:
            score = -search(depth - 1, -beta, -alpha, 1, gives_check, True)
        else:
            score = -search(depth - 1, -alpha - 1, -alpha, 1, gives_check, True)
            if alpha < score < beta:
                score = -search(depth - 1, -beta, -alpha, 1, gives_check, True)
        unmake_move()
        if search_aborted:
            return 0, 0
        searched += 1
        if score > best_score:
            best_score = score
            best_move = move
            if score > alpha:
                alpha = score
                lead_move = move
                lead_score = score
                # Try the new best move first in the next iteration
                root_moves.insert(0, root_moves.pop(i))
                if alpha >= beta:
                    break
    return best_score, best_move


def report_score(score, mover):
    """Score as sent to the bridge: from White's side, mates near +-99999."""
    if score >= MATE_BOUND:
        score = 99999 - (MATE - score)
    elif score <= -MATE_BOUND:
        score = -99999 + (MATE + score)
    return score if mover == WHITE else -score


def search_best_move(max_depth, time_limit_ms, alternatives):
    """BESTMOVE handler: iterative deepening with aspiration windows.
    Stops at max_depth or when the time is used up, and answers with the
    best move of the last iteration that was searched completely, or with
    the move that an iteration cut off by the time limit had found to be
    better.
    Returns the reply line."""
    global start_time, deadline_ms, search_aborted, nodes_searched, tthits, transposition_table, root_rep
    global lead_move
    max_depth = min(max(1, max_depth), MAX_DEPTH)  # depth 0 would return an unsearched move
    alternatives = max(0, alternatives)

    start_time = time.perf_counter()
    search_aborted = False
    nodes_searched = 0
    tthits = 0
    transposition_table = [None] * (2 * TT_SLOTS)
    eval_cache.clear()
    for slot in killers:
        slot[0] = slot[1] = 0
    for row in history_table:
        for i in range(120):
            row[i] = 0
    root_rep = len(rep_stack)

    mover = side
    legal = generate_legal(PROMO_QUEEN_ONLY)
    if not legal:
        return 'BESTMOVE NONE'

    # Order the root moves once: captures first, as in the tree
    root_moves = [move for _, move in order_moves(legal, 0, -1)]

    # A tenth of the limit is left unused, so that the reply is still on
    # time when the machine is busy and this process is not run for a
    # moment. When alternatives are wanted, the main search leaves them
    # part of the rest.
    hard_limit = max(1, time_limit_ms - max(10, time_limit_ms // 10)) if time_limit_ms > 0 else -1
    main_limit = hard_limit
    if hard_limit > 0 and alternatives > 0 and len(root_moves) > 1:
        main_limit = hard_limit * MAIN_SHARE_WITH_ALTS // 100
    deadline_ms = main_limit

    best = root_moves[0]
    best_score = 0
    depth_reached = 0
    completed_all = True

    for d in range(1, max_depth + 1):
        iteration_start = elapsed_ms()
        lead_move = 0
        if d >= ASPIRATION_MIN_DEPTH:
            window = ASPIRATION_WINDOW
            alpha = max(-INF, best_score - window)
            beta = min(INF, best_score + window)
            while True:
                score, move = search_root(d, alpha, beta, root_moves, ())
                if search_aborted:
                    break
                if score <= alpha:
                    alpha = max(-INF, alpha - window)
                elif score >= beta:
                    beta = min(INF, beta + window)
                else:
                    break
                window *= 2
                if window > ASPIRATION_LIMIT:
                    alpha, beta = -INF, INF
        else:
            score, move = search_root(d, -INF, INF, root_moves, ())
        if search_aborted:
            completed_all = False
            # Alternatives are scored at the depth of the last finished
            # iteration, and their scores must compare with the best move's
            if lead_move and depth_reached > 0 and alternatives == 0:
                best = lead_move
                best_score = lead_score
            break

        best = move
        best_score = score
        depth_reached = d

        if len(root_moves) == 1:
            break
        # A forced mate will not get shorter by looking deeper than its length
        if abs(score) >= MATE_BOUND and MATE - abs(score) <= d:
            break
        if main_limit > 0 and d < max_depth:
            # The next iteration costs at least about twice the last
            # one; do not start it if it cannot finish.
            now = elapsed_ms()
            if now + 2 * (now - iteration_start) >= main_limit:
                completed_all = False
                break

    if depth_reached == 0:
        # Not even depth 1 was finished (a limit of a few milliseconds):
        # fall back to the first move by capture ordering.
        best = root_moves[0]
        search_aborted = False
        deadline_ms = -1
        make_move(best)
        best_score = -quiesce(-INF, INF, 1, in_check_now())
        unmake_move()

    # The next best moves, each found by searching the root again without
    # the moves already chosen. They are searched to the depth of the best
    # move so that their scores compare with its score; the table filled by
    # the main search makes that cheap. One the time limit cuts off is left
    # out rather than reported with a shallower score.
    alts = []
    if alternatives > 0 and depth_reached > 0:
        search_aborted = False
        deadline_ms = hard_limit
        excluded = [best]
        while len(alts) < alternatives and len(excluded) < len(root_moves):
            score, move = search_root(depth_reached, -INF, INF, root_moves, excluded)
            if search_aborted or move == 0:
                break
            alts.append((move, score))
            excluded.append(move)
        search_aborted = False

    def squares(move):
        frm, to = move & 127, (move >> 7) & 127
        return f'{ROW_OF[frm]} {COL_OF[frm]} {ROW_OF[to]} {COL_OF[to]}'

    out = f'BESTMOVE {squares(best)} EVAL {report_score(best_score, mover)}'
    if alts:
        out += ' ALTS'
        for move, score in alts:
            out += f' {squares(move)} {report_score(score, mover)}'
    status = 'completed' if completed_all else 'timeout'
    out += (f' DEPTH {depth_reached} NODES {nodes_searched} TTHITS {tthits}'
            f' TIME {int(elapsed_ms())} ENGINE python STATUS {status}')
    return out


# ============================================================
#  Command handlers
# ============================================================

def find_legal_move(frm, to, promo_type):
    """The legal move from one square to another (promoting to promo_type), or 0."""
    for move in generate_legal(PROMO_ALL):
        promo = (move >> 14) & 7
        if move & 127 == frm and (move >> 7) & 127 == to and (not promo or promo == promo_type):
            return move
    return 0


def handle_moves(row, col):
    frm = SQ(row, col)
    # One entry per target square, in board order
    targets = sorted(
        ((move >> 7) & 127, move) for move in generate_legal(PROMO_QUEEN_ONLY) if move & 127 == frm
    )
    output = ['MOVES']
    for to, move in targets:
        output.extend([
            str(ROW_OF[to]), str(COL_OF[to]),
            '1' if is_capture(move) else '0',
            '1' if (move >> 14) & 7 else '0',
        ])
    return ' '.join(output)


def promo_type_from_char(ch):
    return {'r': ROOK, 'b': BISHOP, 'n': KNIGHT}.get(ch.lower(), QUEEN)


def handle_promote(fr, fc, tr, tc, promo_piece):
    """Validates a promotion move, applies it on the board, and returns
    the new 64-char board string so the Python layer stays in sync."""
    frm, to = SQ(fr, fc), SQ(tr, tc)
    piece = board[frm]
    if piece == EMPTY or COLOR_OF[piece] != side or TYPE_OF[piece] != PAWN:
        return 'INVALID Not a pawn'
    if tr != (0 if side == WHITE else 7):
        return 'INVALID Not a promotion square'
    move = find_legal_move(frm, to, promo_type_from_char(promo_piece))
    if not move:
        return 'INVALID Illegal move'
    make_move(move)
    return f'PROMOTE {serialize_board()}'


def handle_status():
    """STATUS -> CHECK (in check, has legal moves), CHECKMATE, STALEMATE,
    DRAW (legal moves exist but neither side can ever mate), OK."""
    in_check = in_check_now()
    if not has_legal_move():
        return 'STATUS CHECKMATE' if in_check else 'STATUS STALEMATE'
    if is_insufficient_material():
        # A dead position is a draw even while the king is in check.
        return 'STATUS DRAW'
    return 'STATUS CHECK' if in_check else 'STATUS OK'


def handle_notation(fr, fc, tr, tc, promo):
    """NOTATION handler: Standard Algebraic Notation for a legal move, with
    disambiguation (Rfe1, N5f3), promotion and the check or mate suffix.
    Any other move is answered with "?"."""
    frm, to = SQ(fr, fc), SQ(tr, tc)
    piece = board[frm]
    promotes = piece != EMPTY and TYPE_OF[piece] == PAWN and tr in (0, 7)
    move = find_legal_move(frm, to, promo_type_from_char(promo) if promotes else 0) if piece else 0
    if not move:
        return 'NOTATION ?'
    kind = TYPE_OF[piece]
    files = 'abcdefgh'

    if (move >> 17) & 3 == FLAG_CASTLE:
        res = 'O-O' if tc == 6 else 'O-O-O'
    elif kind == PAWN:
        res = ''
        # A diagonal pawn move is always a capture
        if fc != tc:
            res += files[fc] + 'x'
        res += files[tc] + str(8 - tr)
        promo_type = (move >> 14) & 7
        if promo_type:
            res += '=' + 'PNBRQK'[promo_type]
    else:
        res = 'PNBRQK'[kind]

        # Disambiguation: other pieces of the same kind that can legally
        # move to the same square
        others = same_file = same_rank = False
        for other in generate_legal(PROMO_QUEEN_ONLY):
            other_from = other & 127
            if (other >> 7) & 127 != to or other_from == frm or board[other_from] != piece:
                continue
            others = True
            if COL_OF[other_from] == fc:
                same_file = True
            if ROW_OF[other_from] == fr:
                same_rank = True
        if others:
            if not same_file:
                res += files[fc]
            elif not same_rank:
                res += str(8 - fr)
            else:
                res += files[fc] + str(8 - fr)

        if board[to] != EMPTY:
            res += 'x'
        res += files[tc] + str(8 - tr)

    # Play the move to see whether it gives check or mate
    make_move(move)
    if in_check_now():
        res += '+' if has_legal_move() else '#'
    unmake_move()

    return f'NOTATION {res}'


def load_history(tokens):
    """Read the earlier positions of the game that follow a BESTMOVE command
    and return their hashes. The current position is loaded again afterwards
    by the caller."""
    if len(tokens) % 4 or len(tokens) > 4 * MAX_GAME:
        raise ValueError('bad history')
    hashes = []
    for i in range(0, len(tokens), 4):
        placement, turn, rights, ep = tokens[i:i + 4]
        if turn not in ('w', 'b'):
            raise ValueError('bad history')
        clear_board()
        rows = placement.split('/')
        if len(rows) != 8:
            raise ValueError('bad history')
        for r, row in enumerate(rows):
            c = 0
            for ch in row:
                if '1' <= ch <= '8':
                    c += int(ch)
                else:
                    piece = PIECE_CHARS.find(ch)
                    if piece <= EMPTY or c > 7:
                        raise ValueError('bad history')
                    add_piece(piece, SQ(r, c))
                    c += 1
            if c != 8:
                raise ValueError('bad history')
        ep_row = ep_col = -1
        if ep != '-':
            ep_row, ep_col = (int(value) for value in ep.split(','))
        finish_setup(WHITE if turn == 'w' else BLACK, rights, ep_row, ep_col)
        hashes.append(hash_key)
    return hashes


COMMANDS = ('MOVES', 'ATTACKED', 'PROMOTE', 'STATUS', 'BESTMOVE', 'NOTATION', 'EVAL', 'PERFT')


def handle_command(parts):
    """Run one command and return its reply. Raises ValueError (or
    IndexError) when the line is malformed."""
    global halfmove
    command = parts[0]
    # Every command starts with <board64> <rights> <colour> and two
    # integers: the en passant target, or the square for ATTACKED.
    board64, rights, colour = parts[1:4]
    n1, n2 = int(parts[4]), int(parts[5])
    if colour not in ('white', 'black'):
        raise ValueError('bad colour')
    turn = WHITE if colour == 'white' else BLACK

    def squares(count):
        values = [int(value) for value in parts[6:6 + count]]
        if len(values) != count or not all(0 <= value < 8 for value in values):
            raise ValueError('bad square')
        return values

    if command == 'ATTACKED':
        if not (0 <= n1 < 8 and 0 <= n2 < 8):
            raise ValueError('bad square')
        load_position(board64, rights, WHITE, -1, -1)
        return 'YES' if attacked(SQ(n1, n2), turn) else 'NO'

    if command == 'MOVES':
        row, col = squares(2)
    elif command in ('BESTMOVE', 'PERFT'):
        depth = int(parts[6])
    elif command not in ('STATUS', 'EVAL'):
        fr, fc, tr, tc = squares(4)

    load_position(board64, rights, turn, n1, n2)
    # A missing promotion piece means a queen
    promo = parts[10][:1] if len(parts) > 10 else 'q'

    if command == 'MOVES':
        return handle_moves(row, col)
    if command == 'PROMOTE':
        return handle_promote(fr, fc, tr, tc, promo)
    if command == 'STATUS':
        return handle_status()
    if command == 'NOTATION':
        return handle_notation(fr, fc, tr, tc, promo)
    if command == 'EVAL':
        return f'EVAL {evaluate()}'
    if command == 'PERFT':
        return f'PERFT {perft(min(depth, MAX_PERFT_DEPTH)) if depth >= 1 else 1}'
    limit_ms = int(parts[7]) if len(parts) > 7 else -1
    clock = int(parts[8]) if len(parts) > 8 else 0
    alternatives = int(parts[9]) if len(parts) > 9 else 0
    earlier = load_history(parts[10:])
    load_position(board64, rights, turn, n1, n2)
    rep_stack.extend(earlier)
    halfmove = max(0, clock)
    return search_best_move(depth, limit_ms, alternatives)


def reply(parts):
    """The reply line for one command line, split into tokens."""
    if parts[0] == 'VERSION':
        return f'VERSION {PROTOCOL_VERSION}'
    if parts[0] not in COMMANDS:
        return 'ERROR unknown command'
    try:
        return handle_command(parts)
    except (ValueError, IndexError):
        return 'ERROR malformed command'


def run():
    # One command per line and exactly one reply line per command, so the
    # caller can never be left waiting and replies cannot get out of step.
    # The reply is flushed at once: the caller waits for it while the pipe
    # stays open.
    for raw in sys.stdin:
        parts = raw.split()
        if parts:
            print(reply(parts), flush=True)


if __name__ == '__main__':
    run()
