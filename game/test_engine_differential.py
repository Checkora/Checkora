"""Both engines against python-chess, over seeded random games.

At every position of every game the legal moves (MOVES for each piece of
the side to move), the status (STATUS) and the notation of the move played
(NOTATION) must match what python-chess says; every few positions the
notation of all legal moves is compared too. Random play reaches castling,
en passant, promotions, pins and the endings that the hand-written tests
in test_engine_rules.py only sample.

python-chess is a test-only dependency (requirements-dev.txt); without it
these tests are skipped.
"""
import random
import unittest

from django.test import SimpleTestCase

from game.test_engine_rules import EngineProcess, engine_commands

try:
    import chess
except ImportError:
    chess = None

# Long enough for random play to promote, sometimes several times, and to
# end in mates, stalemates and bare kings
GAMES = 16
MAX_PLIES = 300
# Every this many plies the notation of every legal move is compared
ALL_NOTATIONS_EVERY = 7


def row_col(square):
    """python-chess square -> the protocol's row and column (row 0 is rank 8)."""
    return 7 - chess.square_rank(square), chess.square_file(square)


def fields(board):
    """The protocol's position fields for a python-chess board."""
    board64 = ''.join(
        (piece.symbol() if (piece := board.piece_at(chess.square(col, 7 - row))) else '.')
        for row in range(8) for col in range(8)
    )
    rights = ''.join(letter for letter, held in (
        ('K', board.has_kingside_castling_rights(chess.WHITE)),
        ('Q', board.has_queenside_castling_rights(chess.WHITE)),
        ('k', board.has_kingside_castling_rights(chess.BLACK)),
        ('q', board.has_queenside_castling_rights(chess.BLACK)),
    ) if held) or '-'
    ep = '-1 -1' if board.ep_square is None else '%d %d' % row_col(board.ep_square)
    return f"{board64} {rights} {'white' if board.turn == chess.WHITE else 'black'} {ep}"


def expected_status(board):
    if board.is_checkmate():
        return 'STATUS CHECKMATE'
    if board.is_stalemate():
        return 'STATUS STALEMATE'
    if board.is_insufficient_material():
        return 'STATUS DRAW'
    return 'STATUS CHECK' if board.is_check() else 'STATUS OK'


def expected_moves(board, square):
    """MOVES as the engines list them: one entry per target square, in
    board order, a promotion standing for all four pieces."""
    targets = {}
    for move in board.legal_moves:
        if move.from_square == square:
            targets[row_col(move.to_square)] = (board.is_capture(move), move.promotion is not None)
    tokens = ['MOVES']
    for (row, col), (capture, promotion) in sorted(targets.items()):
        tokens += [str(row), str(col), str(int(capture)), str(int(promotion))]
    return ' '.join(tokens)


def notation_command(board, move):
    origin, target = row_col(move.from_square), row_col(move.to_square)
    promotion = f' {chess.piece_symbol(move.promotion)}' if move.promotion else ''
    return f'NOTATION {fields(board)} {origin[0]} {origin[1]} {target[0]} {target[1]}{promotion}'


@unittest.skipIf(chess is None, 'python-chess is not installed (pip install -r requirements-dev.txt)')
class DifferentialTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engines = {}
        for name, command in engine_commands().items():
            cls.engines[name] = EngineProcess(command)
            cls.addClassCleanup(cls.engines[name].close)

    def check_position(self, engine, board, check_all_notations):
        position = fields(board)
        self.assertEqual(engine.ask(f'STATUS {position}'), expected_status(board), board.fen())
        for square, piece in board.piece_map().items():
            if piece.color == board.turn:
                row, col = row_col(square)
                self.assertEqual(engine.ask(f'MOVES {position} {row} {col}'),
                                 expected_moves(board, square), f'{board.fen()} {chess.square_name(square)}')
        if check_all_notations:
            for move in board.legal_moves:
                self.assertEqual(engine.ask(notation_command(board, move)), f'NOTATION {board.san(move)}',
                                 f'{board.fen()} {move.uci()}')

    def test_random_games(self):
        for name, engine in self.engines.items():
            for game in range(GAMES):
                with self.subTest(engine=name, game=game):
                    rng = random.Random(game)
                    board = chess.Board()
                    for ply in range(MAX_PLIES):
                        self.check_position(engine, board, ply % ALL_NOTATIONS_EVERY == 0)
                        moves = list(board.legal_moves)
                        if not moves or board.is_insufficient_material():
                            break
                        move = rng.choice(moves)
                        self.assertEqual(engine.ask(notation_command(board, move)),
                                         f'NOTATION {board.san(move)}', f'{board.fen()} {move.uci()}')
                        board.push(move)
