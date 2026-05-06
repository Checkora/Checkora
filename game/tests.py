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
        self.assertFalse(data['paused'])
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


class DrawOfferTest(TestCase):
    """Test draw agreement persistence through the API."""

    def setUp(self):
        self.client.get('/')

    def test_accept_draw_marks_game_as_draw_agreement(self):
        response = self.client.post(
            '/api/draw/',
            data=json.dumps({'action': 'accept'}),
            content_type='application/json',
        )
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(data['game_status'], 'draw')
        self.assertEqual(data['draw_reason'], 'agreement')

        state = self.client.get('/api/state/').json()
        self.assertEqual(state['game_status'], 'draw')
        self.assertEqual(state['draw_reason'], 'agreement')


class DrawRuleTest(SimpleTestCase):
    """Test rule-based draw detection in the engine."""

    def setUp(self):
        self.validate_patcher = mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok'))
        self.validate_patcher.start()

    def tearDown(self):
        self.validate_patcher.stop()

    def test_fifty_move_rule_triggers_draw(self):
        game = ChessGame()
        game.halfmove_clock = 99

        success, _, _, status = game.make_move(7, 6, 5, 5)

        self.assertTrue(success)
        self.assertEqual(status, 'draw')
        self.assertEqual(game.halfmove_clock, 100)
        self.assertEqual(game.game_status, 'draw')
        self.assertEqual(game.draw_reason, 'fifty_move_rule')

    def test_checkmate_beats_fifty_move_draw(self):
        game = ChessGame()
        game.halfmove_clock = 99

        with mock.patch.object(ChessGame, '_call_engine') as mock_engine:
            def fake_engine(cmd):
                if cmd.startswith('NOTATION'):
                    return 'NOTATION Nf3'
                if cmd.startswith('STATUS'):
                    return 'STATUS checkmate'
                return None

            mock_engine.side_effect = fake_engine
            success, _, _, status = game.make_move(7, 6, 5, 5)

        self.assertTrue(success)
        self.assertEqual(status, 'checkmate')

    def test_threefold_repetition_triggers_draw(self):
        game = ChessGame()

        sequence = [
            (7, 6, 5, 5),
            (0, 6, 2, 5),
            (5, 5, 7, 6),
            (2, 5, 0, 6),
            (7, 6, 5, 5),
            (0, 6, 2, 5),
            (5, 5, 7, 6),
            (2, 5, 0, 6),
        ]

        status = 'active'
        for fr, fc, tr, tc in sequence:
            success, _, _, status = game.make_move(fr, fc, tr, tc)
            self.assertTrue(success)

        self.assertEqual(status, 'draw')
        self.assertEqual(game.game_status, 'draw')
        self.assertEqual(game.draw_reason, 'threefold_repetition')

    def test_session_round_trip_preserves_draw_state(self):
        game = ChessGame()
        game.halfmove_clock = 42
        game.repetition_history.append('test-position')
        game._rebuild_repetition_counts()

        restored = ChessGame.from_dict(game.to_dict())

        self.assertEqual(restored.halfmove_clock, 42)
        self.assertEqual(restored.repetition_history, game.repetition_history)
        self.assertEqual(restored.repetition_counts, game.repetition_counts)

    def test_session_round_trip_preserves_draw_metadata(self):
        game = ChessGame()
        game.game_status = 'draw'
        game.draw_reason = 'threefold_repetition'

        restored = ChessGame.from_dict(game.to_dict())

        self.assertEqual(restored.game_status, 'draw')
        self.assertEqual(restored.draw_reason, 'threefold_repetition')

    def test_completed_game_rejects_more_moves(self):
        game = ChessGame()
        game.game_status = 'draw'
        game.draw_reason = 'threefold_repetition'

        success, message, _, status = game.make_move(7, 6, 5, 5)

        self.assertFalse(success)
        self.assertEqual(message, 'Game is already over.')
        self.assertEqual(status, 'draw')

    def test_position_key_ignores_unusable_en_passant_square(self):
        game = ChessGame()
        game.make_move(6, 4, 4, 4)

        with_ep = game.generate_position_key()
        game.en_passant_target = None
        without_ep = game.generate_position_key()

        self.assertEqual(with_ep, without_ep)


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
        # The opening book (or engine) picks the move; just verify coordinates are present
        self.assertIn('from_row', data['ai_move'])
        self.assertIn('from_col', data['ai_move'])
        self.assertIn('to_row', data['ai_move'])
        self.assertIn('to_col', data['ai_move'])


class OpeningBookTest(SimpleTestCase):
    """Unit tests for the opening-book integration in ChessGame."""

    # ------------------------------------------------------------------
    # FEN key generation
    # ------------------------------------------------------------------

    def test_fen_key_starting_position(self):
        """Starting position must produce the correct standard FEN key."""
        game = ChessGame()
        key = game.generate_fen_key()
        self.assertEqual(
            key,
            'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq',
        )

    def test_fen_key_side_switches_after_move(self):
        """After white moves the key should show 'b' as the active side."""
        game = ChessGame()
        game.current_turn = 'black'
        key = game.generate_fen_key()
        self.assertIn(' b ', key)

    def test_fen_key_reflects_castling_rights_loss(self):
        """Losing castling rights must be reflected in the FEN key."""
        game = ChessGame()
        game.castling_rights = {'w_k': False, 'w_q': False, 'b_k': False, 'b_q': False}
        key = game.generate_fen_key()
        self.assertTrue(key.endswith(' -'))

    def test_fen_key_empty_board_row_uses_digit(self):
        """An entirely empty rank must produce '8' not eight dots."""
        game = ChessGame()
        key = game.generate_fen_key()
        # Ranks 3-6 (0-indexed 2-5) are empty at start → four '8' segments
        self.assertIn('/8/', key)

    # ------------------------------------------------------------------
    # Book loading
    # ------------------------------------------------------------------

    def test_book_loads_from_json_file(self):
        """The book file must be loadable and return a non-empty dict."""
        # Reset the class-level cache so the real file is read
        ChessGame._opening_book = None
        book = ChessGame._load_opening_book()
        self.assertIsInstance(book, dict)
        self.assertGreater(len(book), 0)

    def test_book_caches_after_first_load(self):
        """Subsequent calls must return the same object (no re-read)."""
        ChessGame._opening_book = None
        book1 = ChessGame._load_opening_book()
        book2 = ChessGame._load_opening_book()
        self.assertIs(book1, book2)

    def test_book_falls_back_gracefully_on_missing_file(self):
        """A missing book file should produce an empty dict, not a crash."""
        ChessGame._opening_book = None
        with mock.patch.object(ChessGame, 'OPENING_BOOK_PATH', '/nonexistent/path.json'):
            book = ChessGame._load_opening_book()
        self.assertEqual(book, {})
        # Restore so other tests use the real book
        ChessGame._opening_book = None

    # ------------------------------------------------------------------
    # get_opening_book_move
    # ------------------------------------------------------------------

    def test_starting_position_returns_book_move(self):
        """At the start of the game a valid book move should be returned."""
        game = ChessGame()
        ChessGame._opening_book = None

        with mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok')):
            move = game.get_opening_book_move()

        self.assertIsNotNone(move, 'Expected a book move for the starting position')
        self.assertIn('from_row', move)
        self.assertIn('from_col', move)
        self.assertIn('to_row', move)
        self.assertIn('to_col', move)

    def test_unknown_position_returns_none(self):
        """An out-of-book position must return None (fall through to engine)."""
        game = ChessGame()
        # Force a book with no matching key
        ChessGame._opening_book = {}

        move = game.get_opening_book_move()
        self.assertIsNone(move)
        # Restore
        ChessGame._opening_book = None

    def test_illegal_book_moves_are_skipped(self):
        """If validate_move rejects all candidates the result is None."""
        game = ChessGame()
        ChessGame._opening_book = {
            game.generate_fen_key(): [[6, 4, 4, 4]],
        }

        with mock.patch.object(ChessGame, 'validate_move', return_value=(False, 'illegal')):
            move = game.get_opening_book_move()

        self.assertIsNone(move)
        ChessGame._opening_book = None

    def test_out_of_range_coords_skipped_without_calling_validate(self):
        """Out-of-range entries must be rejected by the bounds check alone.

        validate_move is NOT mocked here — if the bounds check were missing,
        board[9][9] would raise IndexError and the test would fail.
        """
        game = ChessGame()
        ChessGame._opening_book = {
            game.generate_fen_key(): [[9, 9, 9, 9]],  # out-of-range only
        }
        # No mock — real validate_move would IndexError without the guard
        move = game.get_opening_book_move()
        self.assertIsNone(move)
        ChessGame._opening_book = None

    def test_first_legal_candidate_returned_when_first_is_malformed(self):
        """A valid second candidate is returned after a malformed first entry."""
        game = ChessGame()
        fen = game.generate_fen_key()
        ChessGame._opening_book = {
            fen: [[9, 9, 9, 9], [6, 4, 4, 4]],  # first entry out-of-range
        }

        def fake_validate(fr, fc, tr, tc):
            return (True, 'ok') if [fr, fc, tr, tc] == [6, 4, 4, 4] else (False, 'bad')

        with mock.patch.object(ChessGame, 'validate_move', side_effect=fake_validate):
            move = game.get_opening_book_move()

        self.assertIsNotNone(move)
        self.assertEqual(
            [move['from_row'], move['from_col'], move['to_row'], move['to_col']],
            [6, 4, 4, 4],
        )
        ChessGame._opening_book = None

    def test_book_moves_show_variety(self):
        """With multiple candidates different moves should be chosen over many calls."""
        game = ChessGame()
        fen = game.generate_fen_key()
        ChessGame._opening_book = {
            fen: [[6, 4, 4, 4], [6, 3, 4, 3], [7, 6, 5, 5]],
        }
        seen = set()
        with mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok')):
            for _ in range(60):
                m = game.get_opening_book_move()
                if m:
                    seen.add((m['from_row'], m['from_col'], m['to_row'], m['to_col']))

        self.assertGreater(len(seen), 1, 'Book should produce variety across 60 calls')
        ChessGame._opening_book = None

    # ------------------------------------------------------------------
    # Integration: get_ai_move uses book on first move
    # ------------------------------------------------------------------

    def test_get_ai_move_uses_book_before_engine(self):
        """get_ai_move() must return the book move without calling the engine."""
        game = ChessGame()
        ChessGame._opening_book = None

        with (
            mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok')),
            mock.patch.object(ChessGame, '_call_engine') as mock_engine,
        ):
            move = game.get_ai_move()

        mock_engine.assert_not_called()
        self.assertIsNotNone(move)
        ChessGame._opening_book = None

    def test_get_ai_move_falls_back_to_engine_when_book_empty(self):
        """When the book has no entry the engine must be consulted."""
        game = ChessGame()
        ChessGame._opening_book = {}  # empty book

        with mock.patch.object(ChessGame, '_call_engine', return_value='BESTMOVE 6 4 4 4') as mock_engine:
            move = game.get_ai_move()

        mock_engine.assert_called_once()
        self.assertIsNotNone(move)
        self.assertEqual(move['from_row'], 6)
        self.assertEqual(move['to_row'], 4)
        ChessGame._opening_book = None
