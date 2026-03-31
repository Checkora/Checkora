"""Tests for the Checkora chess engine and API endpoints."""

import json
import sys
from unittest import mock

from django.test import SimpleTestCase, TestCase

from .engine import ChessGame


class EnginePathResolutionTest(SimpleTestCase):
    """Engine path selection should work across local platforms."""

    def test_uses_first_existing_engine_binary(self):
        candidates = [
            r'C:\fake\game\engine\main.exe',
            '/fake/game/engine/main',
            r'C:\fake\game\engine\main.py',
        ]

        with (
            mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', candidates),
            mock.patch('game.engine.os.path.exists', side_effect=lambda path: path == candidates[0]),
        ):
            self.assertEqual(ChessGame._resolve_engine_path(), candidates[0])

    def test_prefers_cpp_binary_before_python_fallback(self):
        candidates = [
            r'C:\fake\game\engine\main.exe',
            '/fake/game/engine/main',
            r'C:\fake\game\engine\main.py',
        ]

        with (
            mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', candidates),
            mock.patch('game.engine.os.path.exists', side_effect=lambda path: path in {candidates[1], candidates[2]}),
        ):
            self.assertEqual(ChessGame._resolve_engine_path(), candidates[1])

    def test_falls_back_to_python_engine_script(self):
        candidates = [
            r'C:\fake\game\engine\main.exe',
            '/fake/game/engine/main',
            r'C:\fake\game\engine\main.py',
        ]

        with (
            mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', candidates),
            mock.patch('game.engine.os.path.exists', side_effect=lambda path: path == candidates[2]),
        ):
            self.assertEqual(ChessGame._resolve_engine_path(), candidates[2])
            self.assertEqual(
                ChessGame._build_engine_command(candidates[2]),
                [sys.executable, candidates[2]],
            )


class BoardViewTest(TestCase):
    """The board page should load and initialise a session."""

    def test_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkora')


_ENGINE_MOD = None


def _get_engine_mod():
    """Lazily load the Python engine module, registered in sys.modules."""
    global _ENGINE_MOD
    if _ENGINE_MOD is not None:
        return _ENGINE_MOD

    import importlib.util
    import sys
    import os

    engine_py = os.path.join(os.path.dirname(__file__), 'engine', 'main.py')
    mod_name = 'chess_engine_test_mod'
    spec = importlib.util.spec_from_file_location(mod_name, engine_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod          # register BEFORE exec so @dataclass sees the module
    spec.loader.exec_module(mod)
    _ENGINE_MOD = mod
    return mod


def mock_engine_response(cmd):
    """Smart mock: delegates to the imported Python engine without spawning main.exe."""
    import io
    import contextlib

    mod = _get_engine_mod()
    tokens = cmd.split()
    command = tokens[0]

    if command == 'MOVES':
        board64, rights, turn, row, col = tokens[1], tokens[2], tokens[3], int(tokens[4]), int(tokens[5])
        mod.load_board(board64)
        mod.load_castling_rights(rights)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.handle_moves(turn, row, col)
        return buf.getvalue().strip()

    elif command == 'STATUS':
        board64, rights, turn = tokens[1], tokens[2], tokens[3]
        mod.load_board(board64)
        mod.load_castling_rights(rights)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.handle_status(turn)
        return buf.getvalue().strip()

    elif command == 'BESTMOVE':
        board64, rights, turn = tokens[1], tokens[2], tokens[3]
        mod.load_board(board64)
        mod.load_castling_rights(rights)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.handle_bestmove(turn, 1)   # depth=1 keeps tests fast
        return buf.getvalue().strip()

    elif command == 'PROMOTE':
        board64, rights, turn = tokens[1], tokens[2], tokens[3]
        fr, fc, tr, tc, promo = int(tokens[4]), int(tokens[5]), int(tokens[6]), int(tokens[7]), tokens[8]
        mod.load_board(board64)
        mod.load_castling_rights(rights)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.handle_promote(turn, fr, fc, tr, tc, promo)
        return buf.getvalue().strip()

    return ''


class MoveValidationTest(TestCase):
    """Test move validation through the /api/move/ endpoint."""

    def setUp(self):
        self.patcher = mock.patch.object(ChessGame, '_call_engine', side_effect=mock_engine_response)
        self.patcher.start()
        self.client.get('/')  # initialise game session
        
    def tearDown(self):
        self.patcher.stop()

    def _move(self, fr, fc, tr, tc):
        return self.client.post(
            '/api/move/',
            data=json.dumps({
                'from_row': fr, 'from_col': fc,
                'to_row': tr, 'to_col': tc,
            }),
            content_type='application/json',
        )

    # -- Pawn -------------------------------------------------------

    def test_pawn_single_advance(self):
        """e2-e3 is valid."""
        r = self._move(6, 4, 5, 4)
        self.assertTrue(r.json()['valid'])

    def test_pawn_double_advance(self):
        """e2-e4 is valid from the starting rank."""
        r = self._move(6, 4, 4, 4)
        self.assertTrue(r.json()['valid'])

    def test_pawn_triple_advance_invalid(self):
        """e2-e5 (three squares) is never valid."""
        r = self._move(6, 4, 3, 4)
        self.assertFalse(r.json()['valid'])

    # -- Turn enforcement -------------------------------------------

    def test_wrong_turn(self):
        """Black cannot move first."""
        r = self._move(1, 4, 3, 4)
        self.assertFalse(r.json()['valid'])

    def test_turn_alternation(self):
        """After white moves the turn switches to black."""
        r = self._move(6, 4, 4, 4)  # e4
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['current_turn'], 'black')

    # -- Knight -----------------------------------------------------

    def test_knight_valid(self):
        """b1-c3 (L-shape) is valid."""
        r = self._move(7, 1, 5, 2)
        self.assertTrue(r.json()['valid'])

    def test_knight_invalid(self):
        """b1-b3 (straight line) is not an L-shape."""
        r = self._move(7, 1, 5, 1)
        self.assertFalse(r.json()['valid'])

    # -- Capture rules ----------------------------------------------

    def test_capture_own_piece_blocked(self):
        """Rook a1 cannot land on own pawn a2."""
        r = self._move(7, 0, 6, 0)
        self.assertFalse(r.json()['valid'])

    # -- Bishop blocked by own pawn ---------------------------------

    def test_bishop_blocked(self):
        """c1-bishop cannot jump over d2-pawn."""
        r = self._move(7, 2, 5, 4)
        self.assertFalse(r.json()['valid'])

    # -- Multi-move sequence ----------------------------------------

    def test_three_move_sequence(self):
        """Play e4, e5, Nf3 - all valid."""
        r1 = self._move(6, 4, 4, 4).json()
        self.assertTrue(r1['valid'], r1.get('message', ''))  # e4
        r2 = self._move(1, 4, 3, 4).json()
        self.assertTrue(r2['valid'], r2.get('message', ''))  # e5
        r3 = self._move(7, 6, 5, 5).json()
        self.assertTrue(r3['valid'], r3.get('message', ''))  # Nf3

    def test_capture_tracked(self):
        """Captured pieces should appear in the response."""
        self._move(6, 4, 4, 4)  # e4
        self._move(1, 3, 3, 3)  # d5
        r = self._move(4, 4, 3, 3)  # exd5
        data = r.json()
        self.assertTrue(data['valid'], data.get('message', ''))
        self.assertEqual(data['captured'], 'p')


class ValidMovesTest(TestCase):
    """Test the /api/valid-moves/ endpoint."""

    def setUp(self):
        self.patcher = mock.patch.object(ChessGame, '_call_engine', side_effect=mock_engine_response)
        self.patcher.start()
        self.client.get('/')
        
    def tearDown(self):
        self.patcher.stop()

    def test_pawn_initial_has_two_moves(self):
        """e2-pawn can go to e3 or e4."""
        r = self.client.get('/api/valid-moves/?row=6&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 2)

    def test_knight_initial_has_two_moves(self):
        """b1-knight can go to a3 or c3."""
        r = self.client.get('/api/valid-moves/?row=7&col=1')
        self.assertEqual(len(r.json()['valid_moves']), 2)

    def test_empty_square_no_moves(self):
        """An empty square returns zero moves."""
        r = self.client.get('/api/valid-moves/?row=4&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_opponent_piece_no_moves(self):
        """Black's piece should yield nothing on white's turn."""
        r = self.client.get('/api/valid-moves/?row=1&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_rook_blocked_at_start(self):
        """a1-rook has zero moves - surrounded by own pieces."""
        r = self.client.get('/api/valid-moves/?row=7&col=0')
        self.assertEqual(len(r.json()['valid_moves']), 0)


class NewGameTest(TestCase):
    """Test the /api/new-game/ endpoint."""

    def setUp(self):
        self.patcher = mock.patch.object(ChessGame, '_call_engine', side_effect=mock_engine_response)
        self.patcher.start()
        self.client.get('/')
        
    def tearDown(self):
        self.patcher.stop()

    def test_reset(self):
        """After making a move, new-game restores the initial position."""
        self.client.post(
            '/api/move/',
            data=json.dumps({
                'from_row': 6, 'from_col': 4,
                'to_row': 4, 'to_col': 4,
            }),
            content_type='application/json',
        )
        r = self.client.post('/api/new-game/', content_type='application/json')
        data = r.json()
        self.assertEqual(data['current_turn'], 'white')
        self.assertEqual(len(data['move_history']), 0)

class CheckPromotionTest(TestCase):
    """Test the /api/check-promotion/ endpoint."""

    def setUp(self):
        self.patcher = mock.patch.object(ChessGame, '_call_engine', side_effect=mock_engine_response)
        self.patcher.start()
        self.client.get('/')
        
    def tearDown(self):
        self.patcher.stop()

    def test_promotion_triggered(self):
        """A white pawn moving to rank 0 triggers promotion."""
        # Build a minimal board where white pawn is on rank 1 (one step from promotion)
        board = [[None] * 8 for _ in range(8)]
        board[1][4] = 'P'  # white pawn on rank 1
        self.assertTrue(ChessGame.is_promotion_move(board, 1, 4, 0))
        
    def test_promotion_triggered_black(self):
        """A black pawn moving to rank 7 triggers promotion."""
        board = [[None] * 8 for _ in range(8)]
        board[6][4] = 'p'  # black pawn on rank 6
        self.assertTrue(ChessGame.is_promotion_move(board, 6, 4, 7))
        
    def test_promotion_not_triggered(self):
        r = self.client.get('/api/check-promotion/?from_row=6&from_col=0&to_row=5')
        self.assertFalse(r.json()['is_promotion'])


class GetStateTest(TestCase):
    """Test the /api/state/ endpoint."""

    def setUp(self):
        self.patcher = mock.patch.object(ChessGame, '_call_engine', side_effect=mock_engine_response)
        self.patcher.start()
        self.client.get('/')

    def tearDown(self):
        self.patcher.stop()

    def test_get_state(self):
        r = self.client.get('/api/state/')
        data = r.json()
        self.assertIn('board', data)
        self.assertEqual(data['current_turn'], 'white')
        self.assertTrue(data['paused'])


class PauseGameTest(TestCase):
    """Test the /api/pause/ endpoint."""

    def setUp(self):
        self.patcher = mock.patch.object(ChessGame, '_call_engine', side_effect=mock_engine_response)
        self.patcher.start()
        self.client.get('/')

    def tearDown(self):
        self.patcher.stop()

    def test_pause_game(self):
        r = self.client.post('/api/pause/', data=json.dumps({'pause': True}), content_type='application/json')
        self.assertTrue(r.json()['paused'])
        
        r = self.client.post('/api/pause/', data=json.dumps({'pause': False}), content_type='application/json')
        self.assertFalse(r.json()['paused'])


class AIMoveTest(TestCase):
    """Test the /api/ai-move/ endpoint."""

    def setUp(self):
        self.patcher = mock.patch.object(ChessGame, '_call_engine', side_effect=mock_engine_response)
        self.patcher.start()
        # Start game in AI mode via the new-game endpoint
        self.client.get('/')
        self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'ai'}),
            content_type='application/json',
        )

    def tearDown(self):
        self.patcher.stop()

    def test_ai_move(self):
        r = self.client.post('/api/ai-move/')
        data = r.json()
        self.assertTrue(data['valid'], data.get('message', ''))
        # ai_move should contain the coordinates the engine chose
        self.assertIn('ai_move', data)
        self.assertIn('from_row', data['ai_move'])
        self.assertIn('to_row', data['ai_move'])
        
    def test_ai_move_not_in_ai_mode(self):
        # Reset game back to pvp mode via API
        self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'pvp'}),
            content_type='application/json',
        )
        r = self.client.post('/api/ai-move/')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['valid'])


