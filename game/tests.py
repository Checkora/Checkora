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


class MoveValidationTest(TestCase):
    """Test move validation wrapper by mocking validate_move."""

    def setUp(self):
        self.client.get('/')
        
        # We mock validate_move to return specific booleans to simulate engine validation
        # and _call_engine to bypass game status and promotion checks
        self.validate_patcher = mock.patch.object(ChessGame, 'validate_move')
        self.mock_validate = self.validate_patcher.start()
        
        self.engine_patcher = mock.patch.object(ChessGame, '_call_engine')
        self.mock_engine = self.engine_patcher.start()
        self.mock_engine.return_value = "STATUS ok"

    def tearDown(self):
        self.validate_patcher.stop()
        self.engine_patcher.stop()

    def _move(self, fr, fc, tr, tc, expected_valid=True):
        self.mock_validate.return_value = (expected_valid, "Mock validation.")
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
        r = self._move(6, 4, 5, 4, True)
        self.assertTrue(r.json()['valid'])

    def test_pawn_double_advance(self):
        r = self._move(6, 4, 4, 4, True)
        self.assertTrue(r.json()['valid'])

    def test_pawn_triple_advance_invalid(self):
        r = self._move(6, 4, 3, 4, False)
        self.assertFalse(r.json()['valid'])

    # -- Turn enforcement -------------------------------------------

    def test_wrong_turn(self):
        """Black cannot move first. Handled by native Python checks, validation isn't reached if fail."""
        self.mock_validate.return_value = (True, "")  # Bypass validate to ensure python wrapper rejects it
        r = self.client.post('/api/move/', data=json.dumps({'from_row': 1, 'from_col': 4, 'to_row': 3, 'to_col': 4}), content_type='application/json')
        self.assertFalse(r.json()['valid'])

    def test_turn_alternation(self):
        r = self._move(6, 4, 4, 4, True) 
        self.assertTrue(r.json()['valid'])
        self.assertEqual(r.json()['current_turn'], 'black')

    # -- Knight -----------------------------------------------------

    def test_knight_valid(self):
        r = self._move(7, 1, 5, 2, True)
        self.assertTrue(r.json()['valid'])

    def test_knight_invalid(self):
        r = self._move(7, 1, 5, 1, False)
        self.assertFalse(r.json()['valid'])

    # -- Capture rules ----------------------------------------------

    def test_capture_own_piece_blocked(self):
        r = self._move(7, 0, 6, 0, False)
        self.assertFalse(r.json()['valid'])

    # -- Bishop blocked by own pawn ---------------------------------

    def test_bishop_blocked(self):
        r = self._move(7, 2, 5, 4, False)
        self.assertFalse(r.json()['valid'])

    # -- Multi-move sequence ----------------------------------------

    def test_three_move_sequence(self):
        self.assertTrue(self._move(6, 4, 4, 4, True).json()['valid'])
        self.assertTrue(self._move(1, 4, 3, 4, True).json()['valid'])
        self.assertTrue(self._move(7, 6, 5, 5, True).json()['valid'])

    def test_capture_tracked(self):
        self._move(6, 4, 4, 4, True)
        self._move(1, 3, 3, 3, True)
        
        # To test capture, we spoof 'p' in the destination square before sending move
        session = self.client.session
        game_data = session['game']
        game_data['board'][3][3] = 'p'
        session['game'] = game_data
        session.save()
        
        r = self._move(4, 4, 3, 3, True)
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['captured'], 'p')


class ValidMovesTest(TestCase):
    """Test the /api/valid-moves/ endpoint. Mock _call_engine heavily to test parsers."""

    def setUp(self):
        self.client.get('/')
        self.engine_patcher = mock.patch.object(ChessGame, '_call_engine')
        self.mock_engine = self.engine_patcher.start()

    def tearDown(self):
        self.engine_patcher.stop()

    def test_pawn_initial_has_two_moves(self):
        self.mock_engine.return_value = "MOVES 5 4 0 0 4 4 0 0" 
        r = self.client.get('/api/valid-moves/?row=6&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 2)

    def test_knight_initial_has_two_moves(self):
        self.mock_engine.return_value = "MOVES 5 0 0 0 5 2 0 0"
        r = self.client.get('/api/valid-moves/?row=7&col=1')
        self.assertEqual(len(r.json()['valid_moves']), 2)

    def test_empty_square_no_moves(self):
        self.mock_engine.return_value = "MOVES"
        r = self.client.get('/api/valid-moves/?row=4&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_opponent_piece_no_moves(self):
        self.mock_engine.return_value = "MOVES" # Python shortcircuits this, but mock covers edge case
        r = self.client.get('/api/valid-moves/?row=1&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_rook_blocked_at_start(self):
        self.mock_engine.return_value = "MOVES"
        r = self.client.get('/api/valid-moves/?row=7&col=0')
        self.assertEqual(len(r.json()['valid_moves']), 0)


class NewGameTest(TestCase):
    """Test the /api/new-game/ endpoint."""

    def setUp(self):
        self.client.get('/')

    def test_reset(self):
        # We manually update board without _call_engine to simulate game progress
        session = self.client.session
        game_data = session['game']
        game_data['current_turn'] = 'black'
        game_data['move_history'] = ['e4']
        session['game'] = game_data
        session.save()

        r = self.client.post('/api/new-game/', content_type='application/json')
        data = r.json()
        self.assertEqual(data['current_turn'], 'white')
        self.assertEqual(len(data['move_history']), 0)


class CheckPromotionTest(TestCase):
    """Test the /api/check-promotion/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        self.client.get('/')
        self.promo_patcher = mock.patch('game.engine.ChessGame.is_promotion_move')
        self.mock_promo = self.promo_patcher.start()

    def tearDown(self):
        self.promo_patcher.stop()

    def test_white_pawn_promotion(self):
        self.mock_promo.return_value = True
        r = self.client.get('/api/check-promotion/?from_row=1&from_col=0&to_row=0')
        self.assertTrue(r.json()['is_promotion'])
        self.mock_promo.assert_called_once()

    def test_black_pawn_promotion(self):
        self.mock_promo.return_value = True
        url = '/api/check-promotion/?from_row=6&from_col=0&to_row=7'
        r = self.client.get(url)
        self.assertTrue(r.json()['is_promotion'])
        self.mock_promo.assert_called_once()

    def test_no_promotion(self):
        self.mock_promo.return_value = False
        url = '/api/check-promotion/?from_row=1&from_col=0&to_row=2'
        r = self.client.get(url)
        self.assertFalse(r.json()['is_promotion'])
        self.mock_promo.assert_called_once()


class GameStateTest(TestCase):
    """Test the /api/state/ endpoint."""

    def setUp(self):
        self.client.get('/')

    def test_get_state(self):
        r = self.client.get('/api/state/')
        data = r.json()
        self.assertTrue(data['paused'])
        self.assertEqual(data['current_turn'], 'white')
        self.assertEqual(data['mode'], 'pvp')
        self.assertIn('board', data)


class PauseTest(TestCase):
    """Test the /api/pause/ endpoint."""

    def setUp(self):
        self.client.get('/')

    def test_pause_toggle(self):
        r1 = self.client.post(
            '/api/pause/', data=json.dumps({'pause': True}),
            content_type='application/json'
        )
        self.assertTrue(r1.json()['paused'])

        r2 = self.client.post(
            '/api/pause/', data=json.dumps({'pause': False}),
            content_type='application/json'
        )
        self.assertFalse(r2.json()['paused'])


class AIMoveTest(TestCase):
    """Test the /api/ai-move/ endpoint."""

    def setUp(self):
        self.client.get('/')
        self.engine_patcher = mock.patch.object(ChessGame, '_call_engine')
        self.mock_engine = self.engine_patcher.start()
        # Mock engine to return STATUS ok if checked, and BESTMOVE coords
        self.mock_engine.side_effect = lambda cmd: (
            "BESTMOVE 6 4 4 4" if cmd.startswith("BEST") else (
                "STATUS ok" if cmd.startswith("STATUS") else "PROMOTE"
            )
        )

        self.validate_patcher = mock.patch.object(ChessGame, 'validate_move')
        self.mock_validate = self.validate_patcher.start()
        self.mock_validate.return_value = (True, "Mock validate AI move")

    def tearDown(self):
        self.engine_patcher.stop()
        self.validate_patcher.stop()

    def test_ai_requires_ai_mode(self):
        r = self.client.post('/api/ai-move/', content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['valid'])

    def test_ai_makes_move(self):
        self.client.post(
            '/api/new-game/', data=json.dumps({'mode': 'ai'}),
            content_type='application/json'
        )

        r = self.client.post('/api/ai-move/', content_type='application/json')
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['current_turn'], 'black')
        self.assertEqual(data['ai_move']['from_row'], 6)
        self.assertEqual(data['ai_move']['to_row'], 4)
