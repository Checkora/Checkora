#!/usr/bin/env python3
"""Checkora chess engine implemented in Python.

Protocol:
VALIDATE <board64> <castling_rights> <turn> <ep_row> <ep_col> <fr> <fc> <tr> <tc>
-> VALID | INVALID <reason>

MOVES <board64> <castling_rights> <turn> <ep_row> <ep_col> <row> <col>
-> MOVES [<row> <col> <is_capture> <is_promotion> ...]

ATTACKED <board64> <castling_rights> <attackerColor> <row> <col>
-> YES | NO

PROMOTE <board64> <castling_rights> <turn> <fr> <fc> <tr> <tc> <promoPiece>
-> PROMOTE <newBoard64>
-> INVALID <reason>

STATUS <board64> <castling_rights> <turn> <ep_row> <ep_col>
-> STATUS CHECK | CHECKMATE | STALEMATE | OK

BESTMOVE <board64> <castling_rights> <turn> <ep_row> <ep_col> <depth>
-> BESTMOVE <fr> <fc> <tr> <tc>
-> BESTMOVE NONE
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


BOARD = [['.'] * 8 for _ in range(8)]
NO_PROMOTION = '\0'
W_K_CASTLE = False
W_Q_CASTLE = False
B_K_CASTLE = False
B_Q_CASTLE = False
EN_PASSANT_R = -1
EN_PASSANT_C = -1


def load_board(board64):
    for index, piece in enumerate(board64):
        BOARD[index // 8][index % 8] = piece


def load_castling_rights(rights_str):
    global W_K_CASTLE, W_Q_CASTLE, B_K_CASTLE, B_Q_CASTLE
    W_K_CASTLE = W_Q_CASTLE = B_K_CASTLE = B_Q_CASTLE = False
    for char in rights_str:
        if char == 'K': W_K_CASTLE = True
        elif char == 'Q': W_Q_CASTLE = True
        elif char == 'k': B_K_CASTLE = True
        elif char == 'q': B_Q_CASTLE = True

def load_en_passant(row, col):
    global EN_PASSANT_R, EN_PASSANT_C
    EN_PASSANT_R = row
    EN_PASSANT_C = col


def serialize_board():
    return ''.join(''.join(row) for row in BOARD)


def is_white(piece):
    return 'A' <= piece <= 'Z'


def is_black(piece):
    return 'a' <= piece <= 'z'


def is_empty(piece):
    return piece == '.'


def color_of(piece):
    if is_white(piece):
        return 'white'
    if is_black(piece):
        return 'black'
    return 'none'


def in_bounds(row, col):
    return 0 <= row < 8 and 0 <= col < 8


def is_promotion_move(piece, to_row):
    return (piece == 'P' and to_row == 0) or (piece == 'p' and to_row == 7)


def resolve_promotion(pawn, choice):
    lower = choice.lower()
    if lower not in {'q', 'r', 'b', 'n'}:
        lower = 'q'
    return lower.upper() if is_white(pawn) else lower


def path_clear(fr, fc, tr, tc):
    row_step = 1 if tr > fr else -1 if tr < fr else 0
    col_step = 1 if tc > fc else -1 if tc < fc else 0
    row = fr + row_step
    col = fc + col_step
    while row != tr or col != tc:
        if not is_empty(BOARD[row][col]):
            return False
        row += row_step
        col += col_step
    return True


def is_square_attacked(target_row, target_col, attacker_color):
    knight_offsets = [
        (-2, -1), (-2, 1), (-1, -2), (-1, 2),
        (1, -2), (1, 2), (2, -1), (2, 1),
    ]
    target_knight = 'N' if attacker_color == 'white' else 'n'
    for dr, dc in knight_offsets:
        row = target_row + dr
        col = target_col + dc
        if in_bounds(row, col) and BOARD[row][col] == target_knight:
            return True

    directions = [
        (0, 1), (0, -1), (1, 0), (-1, 0),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ]
    for index, (dr, dc) in enumerate(directions):
        row = target_row + dr
        col = target_col + dc
        while in_bounds(row, col):
            piece = BOARD[row][col]
            if not is_empty(piece):
                if color_of(piece) == attacker_color:
                    piece_type = piece.lower()
                    if index < 4 and piece_type in {'r', 'q'}:
                        return True
                    if index >= 4 and piece_type in {'b', 'q'}:
                        return True
                break
            row += dr
            col += dc

    pawn_dir = 1 if attacker_color == 'white' else -1
    target_pawn = 'P' if attacker_color == 'white' else 'p'
    for dc in (-1, 1):
        row = target_row + pawn_dir
        col = target_col + dc
        if in_bounds(row, col) and BOARD[row][col] == target_pawn:
            return True

    target_king = 'K' if attacker_color == 'white' else 'k'
    for row in range(target_row - 1, target_row + 2):
        for col in range(target_col - 1, target_col + 2):
            if in_bounds(row, col) and (row != target_row or col != target_col):
                if BOARD[row][col] == target_king:
                    return True

    return False


def valid_pawn(color, fr, fc, tr, tc):
    direction = -1 if color == 'white' else 1
    start_row = 6 if color == 'white' else 1
    row_delta = tr - fr
    col_delta = tc - fc

    if col_delta == 0 and row_delta == direction and is_empty(BOARD[tr][tc]):
        return True

    if col_delta == 0 and row_delta == 2 * direction and fr == start_row:
        return is_empty(BOARD[fr + direction][fc]) and is_empty(BOARD[tr][tc])

    if abs(col_delta) == 1 and row_delta == direction and not is_empty(BOARD[tr][tc]):
        return True

    if abs(col_delta) == 1 and row_delta == direction and tr == EN_PASSANT_R and tc == EN_PASSANT_C:
        return True

    return False


def valid_rook(fr, fc, tr, tc):
    return (fr == tr or fc == tc) and path_clear(fr, fc, tr, tc)


def valid_knight(fr, fc, tr, tc):
    row_delta = abs(tr - fr)
    col_delta = abs(tc - fc)
    return (row_delta == 2 and col_delta == 1) or (row_delta == 1 and col_delta == 2)


def valid_bishop(fr, fc, tr, tc):
    return abs(tr - fr) == abs(tc - fc) and path_clear(fr, fc, tr, tc)


def valid_queen(fr, fc, tr, tc):
    return valid_rook(fr, fc, tr, tc) or valid_bishop(fr, fc, tr, tc)


def valid_king(color, fr, fc, tr, tc):
    if abs(tr - fr) <= 1 and abs(tc - fc) <= 1:
        return True
        
    if fr == tr and abs(tc - fc) == 2:
        if color == 'white' and fr == 7 and fc == 4:
            if tc == 6 and W_K_CASTLE and is_empty(BOARD[7][5]) and is_empty(BOARD[7][6]):
                if not is_square_attacked(7, 4, 'black') and not is_square_attacked(7, 5, 'black') and not is_square_attacked(7, 6, 'black'):
                    return True
            if tc == 2 and W_Q_CASTLE and is_empty(BOARD[7][3]) and is_empty(BOARD[7][2]) and is_empty(BOARD[7][1]):
                if not is_square_attacked(7, 4, 'black') and not is_square_attacked(7, 3, 'black') and not is_square_attacked(7, 2, 'black'):
                    return True
        elif color == 'black' and fr == 0 and fc == 4:
            if tc == 6 and B_K_CASTLE and is_empty(BOARD[0][5]) and is_empty(BOARD[0][6]):
                if not is_square_attacked(0, 4, 'white') and not is_square_attacked(0, 5, 'white') and not is_square_attacked(0, 6, 'white'):
                    return True
            if tc == 2 and B_Q_CASTLE and is_empty(BOARD[0][3]) and is_empty(BOARD[0][2]) and is_empty(BOARD[0][1]):
                if not is_square_attacked(0, 4, 'white') and not is_square_attacked(0, 3, 'white') and not is_square_attacked(0, 2, 'white'):
                    return True
                    
    return False


def validate_move(turn, fr, fc, tr, tc, silent=False):
    piece = BOARD[fr][fc]
    if is_empty(piece):
        return False
    if color_of(piece) != turn:
        return False
    if fr == tr and fc == tc:
        return False

    target = BOARD[tr][tc]
    if not is_empty(target) and color_of(target) == turn:
        return False

    validators = {
        'p': lambda: valid_pawn(turn, fr, fc, tr, tc),
        'r': lambda: valid_rook(fr, fc, tr, tc),
        'n': lambda: valid_knight(fr, fc, tr, tc),
        'b': lambda: valid_bishop(fr, fc, tr, tc),
        'q': lambda: valid_queen(fr, fc, tr, tc),
        'k': lambda: valid_king(turn, fr, fc, tr, tc),
    }
    is_valid = validators.get(piece.lower(), lambda: False)()

    if is_valid and not silent:
        print('VALID')
    elif not is_valid and not silent:
        print('INVALID Illegal move')

    return is_valid


@dataclass
class Move:
    fr: int
    fc: int
    tr: int
    tc: int
    promo_piece: str = NO_PROMOTION


def find_king(color):
    target = 'K' if color == 'white' else 'k'
    for row in range(8):
        for col in range(8):
            if BOARD[row][col] == target:
                return row, col
    return -1, -1


def leaves_king_in_check(move, side):
    src_piece = BOARD[move.fr][move.fc]
    dst_piece = BOARD[move.tr][move.tc]
    ep_capture_piece = '.'
    ep_capture_row = move.fr
    ep_capture_col = move.tc

    if src_piece.lower() == 'p' and move.fc != move.tc and is_empty(dst_piece):
        ep_capture_piece = BOARD[ep_capture_row][ep_capture_col]
        BOARD[ep_capture_row][ep_capture_col] = '.'

    BOARD[move.tr][move.tc] = move.promo_piece if move.promo_piece != NO_PROMOTION else src_piece
    BOARD[move.fr][move.fc] = '.'

    rook_fr, rook_fc, rook_tr, rook_tc = -1, -1, -1, -1
    if src_piece.lower() == 'k' and abs(move.tc - move.fc) == 2:
        if move.tc == 6:
            rook_fr, rook_fc, rook_tr, rook_tc = move.fr, 7, move.tr, 5
        elif move.tc == 2:
            rook_fr, rook_fc, rook_tr, rook_tc = move.fr, 0, move.tr, 3
        if rook_fr != -1:
            BOARD[rook_tr][rook_tc] = BOARD[rook_fr][rook_fc]
            BOARD[rook_fr][rook_fc] = '.'

    opponent = 'black' if side == 'white' else 'white'
    king_row, king_col = find_king(side)
    in_check = king_row >= 0 and is_square_attacked(king_row, king_col, opponent)

    BOARD[move.fr][move.fc] = src_piece
    BOARD[move.tr][move.tc] = dst_piece
    if ep_capture_piece != '.':
        BOARD[ep_capture_row][ep_capture_col] = ep_capture_piece
    if rook_fr != -1:
        BOARD[rook_fr][rook_fc] = BOARD[rook_tr][rook_tc]
        BOARD[rook_tr][rook_tc] = '.'
    return in_check


def handle_moves(turn, row, col):
    piece = BOARD[row][col]
    if is_empty(piece) or color_of(piece) != turn:
        print('MOVES')
        return

    output = ['MOVES']
    for tr in range(8):
        for tc in range(8):
            if validate_move(turn, row, col, tr, tc, True):
                move = Move(
                    fr=row,
                    fc=col,
                    tr=tr,
                    tc=tc,
                    promo_piece=('Q' if is_white(piece) else 'q') if is_promotion_move(piece, tr) else NO_PROMOTION,
                )
                if leaves_king_in_check(move, turn):
                    continue

                is_ep_capture = piece.lower() == 'p' and col != tc and tr == EN_PASSANT_R and tc == EN_PASSANT_C
                is_capture = 1 if is_ep_capture or not is_empty(BOARD[tr][tc]) else 0
                is_promotion = 1 if is_promotion_move(piece, tr) else 0
                output.extend([str(tr), str(tc), str(is_capture), str(is_promotion)])

    print(' '.join(output))


def handle_promote(turn, fr, fc, tr, tc, promo_piece):
    piece = BOARD[fr][fc]
    if is_empty(piece) or color_of(piece) != turn or piece.lower() != 'p':
        print('INVALID Not a pawn')
        return

    if not validate_move(turn, fr, fc, tr, tc, True):
        print('INVALID Illegal move')
        return

    if not is_promotion_move(piece, tr):
        print('INVALID Not a promotion square')
        return

    BOARD[tr][tc] = resolve_promotion(piece, promo_piece)
    BOARD[fr][fc] = '.'
    print(f'PROMOTE {serialize_board()}')


def piece_value(piece):
    return {
        'p': 100,
        'n': 320,
        'b': 330,
        'r': 500,
        'q': 900,
        'k': 20000,
    }.get(piece.lower(), 0)


PAWN_TABLE = (
    (0, 0, 0, 0, 0, 0, 0, 0),
    (50, 50, 50, 50, 50, 50, 50, 50),
    (10, 10, 20, 30, 30, 20, 10, 10),
    (5, 5, 10, 25, 25, 10, 5, 5),
    (0, 0, 0, 20, 20, 0, 0, 0),
    (5, -5, -10, 0, 0, -10, -5, 5),
    (5, 10, 10, -20, -20, 10, 10, 5),
    (0, 0, 0, 0, 0, 0, 0, 0),
)
KNIGHT_TABLE = (
    (-50, -40, -30, -30, -30, -30, -40, -50),
    (-40, -20, 0, 0, 0, 0, -20, -40),
    (-30, 0, 10, 15, 15, 10, 0, -30),
    (-30, 5, 15, 20, 20, 15, 5, -30),
    (-30, 0, 15, 20, 20, 15, 0, -30),
    (-30, 5, 10, 15, 15, 10, 5, -30),
    (-40, -20, 0, 5, 5, 0, -20, -40),
    (-50, -40, -30, -30, -30, -30, -40, -50),
)
BISHOP_TABLE = (
    (-20, -10, -10, -10, -10, -10, -10, -20),
    (-10, 0, 0, 0, 0, 0, 0, -10),
    (-10, 0, 10, 10, 10, 10, 0, -10),
    (-10, 5, 5, 10, 10, 5, 5, -10),
    (-10, 0, 5, 10, 10, 5, 0, -10),
    (-10, 10, 10, 10, 10, 10, 10, -10),
    (-10, 5, 0, 0, 0, 0, 5, -10),
    (-20, -10, -10, -10, -10, -10, -10, -20),
)
ROOK_TABLE = (
    (0, 0, 0, 0, 0, 0, 0, 0),
    (5, 10, 10, 10, 10, 10, 10, 5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (0, 0, 0, 5, 5, 0, 0, 0),
)
QUEEN_TABLE = (
    (-20, -10, -10, -5, -5, -10, -10, -20),
    (-10, 0, 0, 0, 0, 0, 0, -10),
    (-10, 0, 5, 5, 5, 5, 0, -10),
    (-5, 0, 5, 5, 5, 5, 0, -5),
    (0, 0, 5, 5, 5, 5, 0, -5),
    (-10, 5, 5, 5, 5, 5, 0, -10),
    (-10, 0, 5, 0, 0, 0, 0, -10),
    (-20, -10, -10, -5, -5, -10, -10, -20),
)
KING_MIDDLE_TABLE = (
    (-30, -40, -40, -50, -50, -40, -40, -30),
    (-30, -40, -40, -50, -50, -40, -40, -30),
    (-30, -40, -40, -50, -50, -40, -40, -30),
    (-30, -40, -40, -50, -50, -40, -40, -30),
    (-20, -30, -30, -40, -40, -30, -30, -20),
    (-10, -20, -20, -20, -20, -20, -20, -10),
    (20, 20, 0, 0, 0, 0, 20, 20),
    (20, 30, 10, 0, 0, 10, 30, 20),
)


def positional_bonus(piece, row, col):
    lookup = {
        'p': PAWN_TABLE,
        'n': KNIGHT_TABLE,
        'b': BISHOP_TABLE,
        'r': ROOK_TABLE,
        'q': QUEEN_TABLE,
        'k': KING_MIDDLE_TABLE,
    }
    mirrored_row = row if is_white(piece) else 7 - row
    table = lookup.get(piece.lower())
    return table[mirrored_row][col] if table else 0


def evaluate():
    score = 0
    for row in range(8):
        for col in range(8):
            piece = BOARD[row][col]
            if is_empty(piece):
                continue
            value = piece_value(piece) + positional_bonus(piece, row, col)
            score += value if is_white(piece) else -value
    return score


def generate_moves(side):
    moves = []
    for row in range(8):
        for col in range(8):
            piece = BOARD[row][col]
            if is_empty(piece) or color_of(piece) != side:
                continue
            for tr in range(8):
                for tc in range(8):
                    if validate_move(side, row, col, tr, tc, True):
                        moves.append(
                            Move(
                                fr=row,
                                fc=col,
                                tr=tr,
                                tc=tc,
                                promo_piece=('Q' if is_white(piece) else 'q') if is_promotion_move(piece, tr) else NO_PROMOTION,
                            )
                        )
    return moves


def order_moves(moves):
    def move_score(move):
        score = 0
        if not is_empty(BOARD[move.tr][move.tc]):
            score += piece_value(BOARD[move.tr][move.tc]) + 1000
        if move.promo_piece != NO_PROMOTION:
            score += 900
        return score

    moves.sort(key=move_score, reverse=True)


def minimax(depth, alpha, beta, maximizing):
    global W_K_CASTLE, W_Q_CASTLE, B_K_CASTLE, B_Q_CASTLE
    if depth == 0:
        return evaluate()

    side = 'white' if maximizing else 'black'
    moves = generate_moves(side)
    order_moves(moves)
    legal_moves = [move for move in moves if not leaves_king_in_check(move, side)]

    if not legal_moves:
        opponent = 'black' if maximizing else 'white'
        king_row, king_col = find_king(side)
        if king_row >= 0 and is_square_attacked(king_row, king_col, opponent):
            return -99999 + (100 - depth) if maximizing else 99999 - (100 - depth)
        return 0

    if maximizing:
        best_value = -(10 ** 9)
        for move in legal_moves:
            src_piece = BOARD[move.fr][move.fc]
            dst_piece = BOARD[move.tr][move.tc]
            BOARD[move.tr][move.tc] = move.promo_piece if move.promo_piece != NO_PROMOTION else src_piece
            BOARD[move.fr][move.fc] = '.'

            rook_fr, rook_fc, rook_tr, rook_tc = -1, -1, -1, -1
            if src_piece.lower() == 'k' and abs(move.tc - move.fc) == 2:
                if move.tc == 6:
                    rook_fr, rook_fc, rook_tr, rook_tc = move.fr, 7, move.tr, 5
                elif move.tc == 2:
                    rook_fr, rook_fc, rook_tr, rook_tc = move.fr, 0, move.tr, 3
                if rook_fr != -1:
                    BOARD[rook_tr][rook_tc] = BOARD[rook_fr][rook_fc]
                    BOARD[rook_fr][rook_fc] = '.'

            old_wk, old_wq = W_K_CASTLE, W_Q_CASTLE
            old_bk, old_bq = B_K_CASTLE, B_Q_CASTLE

            if src_piece == 'K': W_K_CASTLE = W_Q_CASTLE = False
            if src_piece == 'k': B_K_CASTLE = B_Q_CASTLE = False
            if src_piece == 'R':
                if move.fr == 7 and move.fc == 0: W_Q_CASTLE = False
                if move.fr == 7 and move.fc == 7: W_K_CASTLE = False
            if src_piece == 'r':
                if move.fr == 0 and move.fc == 0: B_Q_CASTLE = False
                if move.fr == 0 and move.fc == 7: B_K_CASTLE = False
            if dst_piece == 'R':
                if move.tr == 7 and move.tc == 0: W_Q_CASTLE = False
                if move.tr == 7 and move.tc == 7: W_K_CASTLE = False
            if dst_piece == 'r':
                if move.tr == 0 and move.tc == 0: B_Q_CASTLE = False
                if move.tr == 0 and move.tc == 7: B_K_CASTLE = False

            value = minimax(depth - 1, alpha, beta, False)

            W_K_CASTLE, W_Q_CASTLE = old_wk, old_wq
            B_K_CASTLE, B_Q_CASTLE = old_bk, old_bq

            BOARD[move.fr][move.fc] = src_piece
            BOARD[move.tr][move.tc] = dst_piece
            if rook_fr != -1:
                BOARD[rook_fr][rook_fc] = BOARD[rook_tr][rook_tc]
                BOARD[rook_tr][rook_tc] = '.'

            best_value = max(best_value, value)
            alpha = max(alpha, value)
            if beta <= alpha:
                break
        return best_value

    best_value = 10 ** 9
    for move in legal_moves:
        src_piece = BOARD[move.fr][move.fc]
        dst_piece = BOARD[move.tr][move.tc]
        BOARD[move.tr][move.tc] = move.promo_piece if move.promo_piece != NO_PROMOTION else src_piece
        BOARD[move.fr][move.fc] = '.'

        rook_fr, rook_fc, rook_tr, rook_tc = -1, -1, -1, -1
        if src_piece.lower() == 'k' and abs(move.tc - move.fc) == 2:
            if move.tc == 6:
                rook_fr, rook_fc, rook_tr, rook_tc = move.fr, 7, move.tr, 5
            elif move.tc == 2:
                rook_fr, rook_fc, rook_tr, rook_tc = move.fr, 0, move.tr, 3
            if rook_fr != -1:
                BOARD[rook_tr][rook_tc] = BOARD[rook_fr][rook_fc]
                BOARD[rook_fr][rook_fc] = '.'

        old_wk, old_wq = W_K_CASTLE, W_Q_CASTLE
        old_bk, old_bq = B_K_CASTLE, B_Q_CASTLE

        if src_piece == 'K': W_K_CASTLE = W_Q_CASTLE = False
        if src_piece == 'k': B_K_CASTLE = B_Q_CASTLE = False
        if src_piece == 'R':
            if move.fr == 7 and move.fc == 0: W_Q_CASTLE = False
            if move.fr == 7 and move.fc == 7: W_K_CASTLE = False
        if src_piece == 'r':
            if move.fr == 0 and move.fc == 0: B_Q_CASTLE = False
            if move.fr == 0 and move.fc == 7: B_K_CASTLE = False
        if dst_piece == 'R':
            if move.tr == 7 and move.tc == 0: W_Q_CASTLE = False
            if move.tr == 7 and move.tc == 7: W_K_CASTLE = False
        if dst_piece == 'r':
            if move.tr == 0 and move.tc == 0: B_Q_CASTLE = False
            if move.tr == 0 and move.tc == 7: B_K_CASTLE = False

        value = minimax(depth - 1, alpha, beta, True)

        W_K_CASTLE, W_Q_CASTLE = old_wk, old_wq
        B_K_CASTLE, B_Q_CASTLE = old_bk, old_bq

        BOARD[move.fr][move.fc] = src_piece
        BOARD[move.tr][move.tc] = dst_piece
        if rook_fr != -1:
            BOARD[rook_fr][rook_fc] = BOARD[rook_tr][rook_tc]
            BOARD[rook_tr][rook_tc] = '.'

        best_value = min(best_value, value)
        beta = min(beta, value)
        if beta <= alpha:
            break
    return best_value


def handle_status(turn):
    opponent = 'black' if turn == 'white' else 'white'
    king_row, king_col = find_king(turn)
    in_check = king_row >= 0 and is_square_attacked(king_row, king_col, opponent)

    has_legal_move = False
    for move in generate_moves(turn):
        if not leaves_king_in_check(move, turn):
            has_legal_move = True
            break

    if not has_legal_move:
        print('STATUS CHECKMATE' if in_check else 'STATUS STALEMATE')
        return

    print('STATUS CHECK' if in_check else 'STATUS OK')


def handle_bestmove(turn, depth):
    global W_K_CASTLE, W_Q_CASTLE, B_K_CASTLE, B_Q_CASTLE
    maximizing = turn == 'white'
    moves = generate_moves(turn)
    order_moves(moves)
    legal_moves = [move for move in moves if not leaves_king_in_check(move, turn)]

    if not legal_moves:
        print('BESTMOVE NONE')
        return

    best_move = legal_moves[0]
    best_value = -(10 ** 9) if maximizing else 10 ** 9

    for move in legal_moves:
        src_piece = BOARD[move.fr][move.fc]
        dst_piece = BOARD[move.tr][move.tc]
        BOARD[move.tr][move.tc] = move.promo_piece if move.promo_piece != NO_PROMOTION else src_piece
        BOARD[move.fr][move.fc] = '.'

        rook_fr, rook_fc, rook_tr, rook_tc = -1, -1, -1, -1
        if src_piece.lower() == 'k' and abs(move.tc - move.fc) == 2:
            if move.tc == 6:
                rook_fr, rook_fc, rook_tr, rook_tc = move.fr, 7, move.tr, 5
            elif move.tc == 2:
                rook_fr, rook_fc, rook_tr, rook_tc = move.fr, 0, move.tr, 3
            if rook_fr != -1:
                BOARD[rook_tr][rook_tc] = BOARD[rook_fr][rook_fc]
                BOARD[rook_fr][rook_fc] = '.'

        old_wk, old_wq = W_K_CASTLE, W_Q_CASTLE
        old_bk, old_bq = B_K_CASTLE, B_Q_CASTLE

        if src_piece == 'K': W_K_CASTLE = W_Q_CASTLE = False
        if src_piece == 'k': B_K_CASTLE = B_Q_CASTLE = False
        if src_piece == 'R':
            if move.fr == 7 and move.fc == 0: W_Q_CASTLE = False
            if move.fr == 7 and move.fc == 7: W_K_CASTLE = False
        if src_piece == 'r':
            if move.fr == 0 and move.fc == 0: B_Q_CASTLE = False
            if move.fr == 0 and move.fc == 7: B_K_CASTLE = False
        if dst_piece == 'R':
            if move.tr == 7 and move.tc == 0: W_Q_CASTLE = False
            if move.tr == 7 and move.tc == 7: W_K_CASTLE = False
        if dst_piece == 'r':
            if move.tr == 0 and move.tc == 0: B_Q_CASTLE = False
            if move.tr == 0 and move.tc == 7: B_K_CASTLE = False

        value = minimax(depth - 1, -(10 ** 9), 10 ** 9, not maximizing)

        W_K_CASTLE, W_Q_CASTLE = old_wk, old_wq
        B_K_CASTLE, B_Q_CASTLE = old_bk, old_bq

        BOARD[move.fr][move.fc] = src_piece
        BOARD[move.tr][move.tc] = dst_piece
        if rook_fr != -1:
            BOARD[rook_fr][rook_fc] = BOARD[rook_tr][rook_tc]
            BOARD[rook_tr][rook_tc] = '.'

        if maximizing and value > best_value:
            best_value = value
            best_move = move
        if not maximizing and value < best_value:
            best_value = value
            best_move = move

    print(f'BESTMOVE {best_move.fr} {best_move.fc} {best_move.tr} {best_move.tc}')


def run():
    tokens = iter(sys.stdin.read().split())
    for command in tokens:
        if command == 'VALIDATE':
            board64 = next(tokens)
            rights = next(tokens)
            turn = next(tokens)
            ep_row = int(next(tokens))
            ep_col = int(next(tokens))
            fr = int(next(tokens))
            fc = int(next(tokens))
            tr = int(next(tokens))
            tc = int(next(tokens))
            load_board(board64)
            load_castling_rights(rights)
            load_en_passant(ep_row, ep_col)
            validate_move(turn, fr, fc, tr, tc)
        elif command == 'MOVES':
            board64 = next(tokens)
            rights = next(tokens)
            turn = next(tokens)
            ep_row = int(next(tokens))
            ep_col = int(next(tokens))
            row = int(next(tokens))
            col = int(next(tokens))
            load_board(board64)
            load_castling_rights(rights)
            load_en_passant(ep_row, ep_col)
            handle_moves(turn, row, col)
        elif command == 'ATTACKED':
            board64 = next(tokens)
            rights = next(tokens)
            attacker_color = next(tokens)
            row = int(next(tokens))
            col = int(next(tokens))
            load_board(board64)
            load_castling_rights(rights)
            print('YES' if is_square_attacked(row, col, attacker_color) else 'NO')
        elif command == 'PROMOTE':
            board64 = next(tokens)
            rights = next(tokens)
            turn = next(tokens)
            ep_row = int(next(tokens))
            ep_col = int(next(tokens))
            fr = int(next(tokens))
            fc = int(next(tokens))
            tr = int(next(tokens))
            tc = int(next(tokens))
            promo_piece = next(tokens)
            load_board(board64)
            load_castling_rights(rights)
            load_en_passant(ep_row, ep_col)
            handle_promote(turn, fr, fc, tr, tc, promo_piece)
        elif command == 'STATUS':
            board64 = next(tokens)
            rights = next(tokens)
            turn = next(tokens)
            ep_row = int(next(tokens))
            ep_col = int(next(tokens))
            load_board(board64)
            load_castling_rights(rights)
            load_en_passant(ep_row, ep_col)
            handle_status(turn)
        elif command == 'BESTMOVE':
            board64 = next(tokens)
            rights = next(tokens)
            turn = next(tokens)
            ep_row = int(next(tokens))
            ep_col = int(next(tokens))
            depth = int(next(tokens))
            load_board(board64)
            load_castling_rights(rights)
            load_en_passant(ep_row, ep_col)
            handle_bestmove(turn, depth)


if __name__ == '__main__':
    run()
