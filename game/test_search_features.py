"""Search features of the Python engine: hashing, iterative deepening, timeouts and metrics.

The engine is driven through its line protocol (main.reply), the same way
the bridge talks to it, so these tests don't depend on its internals beyond
the hash key.
"""

import os
import sys
from unittest import mock

from django.test import SimpleTestCase

from game.engine import ChessGame

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engine'))
import main as python_engine  # noqa: E402

START = 'rnbqkbnr' 'pppppppp' + '.' * 32 + 'PPPPPPPP' 'RNBQKBNR'


def board(*placements):
    """A board64 string with pieces at (row, col), row 0 being rank 8."""
    squares = ['.'] * 64
    for piece, row, col in placements:
        squares[row * 8 + col] = piece
    return ''.join(squares)


def position_hash(board64, rights='-', turn=python_engine.WHITE, ep_row=-1, ep_col=-1):
    python_engine.load_position(board64, rights, turn, ep_row, ep_col)
    return python_engine.hash_key


def bestmove(board64, depth, time_limit_ms, rights='-'):
    reply = python_engine.reply(['BESTMOVE', board64, rights, 'white', '-1', '-1', str(depth), str(time_limit_ms)])
    parts = reply.split()
    fields = {
        key: parts[parts.index(key) + 1]
        for key in ('EVAL', 'DEPTH', 'NODES', 'TTHITS', 'TIME', 'ENGINE', 'STATUS')
        if key in parts
    }
    return reply, fields


class SearchFeaturesTest(SimpleTestCase):
    def test_zobrist_hash_follows_every_part_of_the_position(self):
        castle_ready = board(('K', 7, 4), ('R', 7, 7), ('k', 0, 4))
        base = position_hash(castle_ready, rights='K')

        self.assertEqual(base, position_hash(castle_ready, rights='K'))
        self.assertNotEqual(base, position_hash(castle_ready, rights='K', turn=python_engine.BLACK))
        self.assertNotEqual(base, position_hash(castle_ready, rights='-'))
        self.assertNotEqual(base, position_hash(board(('K', 7, 4), ('R', 7, 6), ('k', 0, 4)), rights='-'))

        # Black has just played d7-d5 and the e5 pawn can take en passant.
        after_double_step = board(('K', 7, 4), ('k', 0, 4), ('P', 3, 4), ('p', 3, 3))
        self.assertNotEqual(
            position_hash(after_double_step),
            position_hash(after_double_step, ep_row=2, ep_col=3),
        )

    def test_timeout_returns_the_last_completed_move(self):
        reply, fields = bestmove(START, 12, time_limit_ms=1)

        self.assertTrue(reply.startswith('BESTMOVE'))
        self.assertNotIn('NONE', reply)
        self.assertEqual(fields.get('STATUS'), 'timeout')
        self.assertEqual(fields.get('ENGINE'), 'python')

    def test_completed_search_reports_its_depth(self):
        _, fields = bestmove(board(('K', 7, 4), ('R', 7, 0), ('k', 0, 4)), 1, time_limit_ms=5000)

        self.assertEqual(fields.get('STATUS'), 'completed')
        self.assertEqual(fields.get('DEPTH'), '1')

    def test_transposition_table_gets_hits(self):
        rooks = board(('K', 7, 4), ('R', 7, 0), ('k', 0, 4), ('r', 0, 0))
        _, fields = bestmove(rooks, 4, time_limit_ms=5000)

        self.assertGreater(int(fields['TTHITS']), 0)

    def test_wrapper_metrics_parsing(self):
        """ChessGame reads every metric from a BESTMOVE reply."""
        game = ChessGame()
        engine_reply = (
            "BESTMOVE 6 4 4 4 EVAL 30 ALTS 6 2 4 2 -10 "
            "DEPTH 4 NODES 1234 TTHITS 56 TIME 120 ENGINE cpp STATUS completed"
        )
        with mock.patch.object(game, '_call_engine', return_value=engine_reply):
            move_data = game.get_ai_move(depth=4)

        self.assertIsNotNone(move_data)
        self.assertEqual(
            (move_data['from_row'], move_data['from_col'], move_data['to_row'], move_data['to_col']),
            (6, 4, 4, 4),
        )
        self.assertEqual(move_data['eval'], 30)
        self.assertEqual(move_data['depth'], 4)
        self.assertEqual(move_data['nodes'], 1234)
        self.assertEqual(move_data['tthits'], 56)
        self.assertEqual(move_data['time'], 120)
        self.assertEqual(move_data['engine'], 'cpp')
        self.assertEqual(move_data['status'], 'completed')

    def test_opening_book_is_tried_before_the_search(self):
        game = ChessGame()
        game.board = [row[:] for row in ChessGame.INITIAL_BOARD]
        game.current_turn = 'white'
        game.castling_rights = {'w_k': True, 'w_q': True, 'b_k': True, 'b_q': True}
        game.en_passant_target = None
        game.move_history = []

        with mock.patch.object(game, 'validate_move', return_value=(True, "Valid")):
            with mock.patch.object(game, '_call_engine') as engine:
                move = game.get_ai_move()
                engine.assert_not_called()
                self.assertIsNotNone(move)
                self.assertIn('from_row', move)
                self.assertIn('to_row', move)
