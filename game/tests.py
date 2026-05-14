"""Tests for the Checkora chess engine and API endpoints."""

import json
import sys
from smtplib import SMTPException
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

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
            mock.patch(
                'game.engine.os.path.exists',
                side_effect=lambda path: path == candidates[0],
            ),
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
            mock.patch(
                'game.engine.os.path.exists',
                side_effect=lambda path: path in {
                    candidates[1], candidates[2]},
            ),
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
            mock.patch(
                'game.engine.os.path.exists',
                side_effect=lambda path: path == candidates[2],
            ),
        ):
            self.assertEqual(ChessGame._resolve_engine_path(), candidates[2])
            self.assertEqual(
                ChessGame._build_engine_command(candidates[2]),
                [sys.executable, candidates[2]],
            )


class BoardViewTest(TestCase):
    """The board page should load and initialise a session."""

    def test_page_loads(self):
        response = self.client.get('/play/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkora')


class LandingViewTest(TestCase):
    """The landing page at / should load and link to the game."""

    def test_landing_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkora')

    def test_landing_page_links_to_play(self):
        response = self.client.get('/')
        self.assertContains(response, '/play/')


class RegistrationViewTest(TestCase):
    """Registration should send OTP by email only and show failures."""

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_successful_registration_redirects_without_showing_otp(self):
        payload = {
            'username': 'devplayer',
            'email': 'devplayer@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }

        response = self.client.post('/register/', data=payload, follow=True)

        self.assertRedirects(response, '/verify-otp/')
        self.assertNotContains(response, 'Development mode OTP')
        self.assertTrue(User.objects.filter(username='devplayer').exists())

    def test_email_failure_renders_error_and_removes_pending_user(self):
        payload = {
            'username': 'newplayer',
            'email': 'newplayer@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }

        with mock.patch('game.views.send_mail', side_effect=SMTPException('SMTP unavailable')):
            response = self.client.post('/register/', data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Failed to send OTP email.')
        self.assertContains(response, 'Please check your email address and try again.')
        self.assertFalse(User.objects.filter(username='newplayer').exists())
        self.assertNotIn('registration_user_id', self.client.session)
        self.assertNotIn('registration_otp_hash', self.client.session)


class MoveValidationTest(TestCase):
    """Test move validation wrapper by mocking validate_move."""

    def setUp(self):
        self.client.get('/play/')

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
        """Black cannot move first."""
        self.mock_validate.return_value = (True, "")
        r = self.client.post(
            '/api/move/',
            data=json.dumps({
                'from_row': 1, 'from_col': 4,
                'to_row': 3, 'to_col': 4,
            }),
            content_type='application/json',
        )
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

        # To test capture, we spoof 'p' in the
        # destination square before sending move
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
    """Test /api/valid-moves/ endpoint."""

    def setUp(self):
        self.client.get('/play/')
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
        self.mock_engine.return_value = "MOVES"  # mock edge case
        r = self.client.get('/api/valid-moves/?row=1&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_rook_blocked_at_start(self):
        self.mock_engine.return_value = "MOVES"
        r = self.client.get('/api/valid-moves/?row=7&col=0')
        self.assertEqual(len(r.json()['valid_moves']), 0)


class NewGameTest(TestCase):
    """Test the /api/new-game/ endpoint."""

    def setUp(self):
        self.client.get('/play/')

    def test_reset(self):
        # Manually update board to simulate game progress
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
        self.client.get('/play/')
        self.promo_patcher = mock.patch('game.engine.ChessGame.is_promotion_move')
        self.mock_promo = self.promo_patcher.start()

    def tearDown(self):
        self.promo_patcher.stop()

    def test_white_pawn_promotion(self):
        self.mock_promo.return_value = True
        url = '/api/check-promotion/?from_row=1&from_col=0&to_row=0'
        r = self.client.get(url)
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
        self.client.get('/play/')

    def _set_game_session(self, game):
        session = self.client.session
        session['game'] = game.to_dict()
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def test_get_state(self):
        r = self.client.get('/api/state/')
        data = r.json()
        self.assertFalse(data['paused'])
        self.assertEqual(data['current_turn'], 'white')
        self.assertEqual(data['mode'], 'pvp')
        self.assertIn('board', data)

    def test_get_state_preserves_paused_games(self):
        game = ChessGame()
        game.paused = True
        game.last_ts = 100.0
        self._set_game_session(game)

        with (
            mock.patch('game.views.time.time', return_value=105.0),
            mock.patch('game.engine.time.time', return_value=105.0),
        ):
            response = self.client.get('/api/state/')

        data = response.json()
        self.assertTrue(data['paused'])
        self.assertEqual(data['white_time'], game.white_time)
        self.assertEqual(data['black_time'], game.black_time)

    def test_get_state_auto_pauses_long_idle_running_games(self):
        game = ChessGame()
        game.paused = False
        game.last_ts = 100.0
        game.white_time = 600
        game.black_time = 600
        self._set_game_session(game)

        with (
            mock.patch('game.views.time.time', return_value=111.0),
            mock.patch('game.engine.time.time', return_value=111.0),
        ):
            response = self.client.get('/api/state/')

        data = response.json()
        self.assertTrue(data['paused'])
        self.assertEqual(data['white_time'], 600)
        self.assertEqual(data['black_time'], 600)


class PauseTest(TestCase):
    """Test the /api/pause/ endpoint."""

    def setUp(self):
        self.client.get('/play/')

    def _set_game_session(self, game):
        session = self.client.session
        session['game'] = game.to_dict()
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

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

    def test_pause_endpoint_ignores_client_supplied_clock_values(self):
        game = ChessGame()
        game.white_time = 600
        game.black_time = 600
        game.last_ts = 100.0
        game.paused = False
        self._set_game_session(game)

        with (
            mock.patch('game.views.time.time', return_value=103.0),
            mock.patch('game.engine.time.time', return_value=103.0),
        ):
            response = self.client.post(
                '/api/pause/',
                data=json.dumps({
                    'pause': True,
                    'white_time': 1,
                    'black_time': 2,
                }),
                content_type='application/json',
            )

        data = response.json()
        self.assertTrue(data['paused'])
        self.assertEqual(data['white_time'], 597)
        self.assertEqual(data['black_time'], 600)


class DrawOfferTest(TestCase):
    """Test draw agreement persistence through the API."""

    def setUp(self):
        self.client.get('/play/')

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
        self.validate_patcher = mock.patch.object(
            ChessGame, 'validate_move',
            return_value=(True, 'ok'))
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
        self.client.get('/play/')
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
        # Just verify coordinates are present
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
        game.castling_rights = {
            'w_k': False, 'w_q': False,
            'b_k': False, 'b_q': False,
        }
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
        with mock.patch.object(
            ChessGame, 'OPENING_BOOK_PATH',
            '/nonexistent/path.json',
        ):
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

        with mock.patch.object(
            ChessGame, 'validate_move',
            return_value=(True, 'ok'),
        ):
            move = game.get_opening_book_move()

        self.assertIsNotNone(
            move, 'Expected a book move for starting pos')
        self.assertIn('from_row', move)
        self.assertIn('from_col', move)
        self.assertIn('to_row', move)
        self.assertIn('to_col', move)

    def test_unknown_position_returns_none(self):
        """Out-of-book position must return None."""
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

        with mock.patch.object(
            ChessGame, 'validate_move',
            return_value=(False, 'illegal'),
        ):
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

    def test_first_legal_candidate_when_first_malformed(self):
        """Valid second candidate returned after malformed first."""
        game = ChessGame()
        fen = game.generate_fen_key()
        ChessGame._opening_book = {
            fen: [[9, 9, 9, 9], [6, 4, 4, 4]],  # first entry out-of-range
        }

        def fake_validate(fr, fc, tr, tc):
            coords = [fr, fc, tr, tc]
            if coords == [6, 4, 4, 4]:
                return (True, 'ok')
            return (False, 'bad')

        with mock.patch.object(
            ChessGame, 'validate_move',
            side_effect=fake_validate,
        ):
            move = game.get_opening_book_move()

        self.assertIsNotNone(move)
        self.assertEqual(
            [move['from_row'], move['from_col'],
             move['to_row'], move['to_col']],
            [6, 4, 4, 4],
        )
        ChessGame._opening_book = None

    def test_book_moves_show_variety(self):
        """Multiple candidates should show variety."""
        game = ChessGame()
        fen = game.generate_fen_key()
        ChessGame._opening_book = {
            fen: [[6, 4, 4, 4], [6, 3, 4, 3], [7, 6, 5, 5]],
        }
        seen = set()
        with mock.patch.object(
            ChessGame, 'validate_move',
            return_value=(True, 'ok'),
        ):
            for _ in range(60):
                m = game.get_opening_book_move()
                if m:
                    seen.add((
                        m['from_row'], m['from_col'],
                        m['to_row'], m['to_col'],
                    ))

        self.assertGreater(
            len(seen), 1,
            'Book should produce variety across 60 calls')
        ChessGame._opening_book = None

    # ------------------------------------------------------------------
    # Integration: get_ai_move uses book on first move
    # ------------------------------------------------------------------

    def test_get_ai_move_uses_book_before_engine(self):
        """get_ai_move() must use the book first."""
        game = ChessGame()
        ChessGame._opening_book = None

        with (
            mock.patch.object(
                ChessGame, 'validate_move',
                return_value=(True, 'ok')),
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

        with mock.patch.object(
            ChessGame, '_call_engine',
            return_value='BESTMOVE 6 4 4 4',
        ) as mock_engine:
            move = game.get_ai_move()

        mock_engine.assert_called_once()
        self.assertIsNotNone(move)
        self.assertEqual(move['from_row'], 6)
        self.assertEqual(move['to_row'], 4)
        ChessGame._opening_book = None


class MoveHistoryColorTest(TestCase):
    """Test that move_history records the correct player color."""

    def test_move_history_records_correct_color(self):
        """White's first move must be 'white'. Black's reply, 'black'."""
        game = ChessGame()

        game.make_move(6, 4, 4, 4)  # White: e4
        self.assertEqual(
            game.move_history[0]['color'], 'white',
            "White's move must be recorded as 'white'."
        )

        game.make_move(1, 4, 3, 4)  # Black: e5
        self.assertEqual(
            game.move_history[1]['color'], 'black',
            "Black's move must be recorded as 'black'."
        )


class StatsCleanupTest(TestCase):
    """Tests for the cleaned-up stats view and user isolation."""

    def setUp(self):
        self.user_a = User.objects.create_user(username='usera', password='password123')
        self.user_b = User.objects.create_user(username='userb', password='password123')
        from .models import GameResult
        self.GameResult = GameResult

    def test_stats_requires_login(self):
        """Stats page should redirect unauthenticated users to login."""
        response = self.client.get('/stats/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_user_isolation(self):
        """Users should only see their own game results."""
        # Create game for user A
        self.GameResult.objects.create(user=self.user_a, mode='pvp', winner='white', end_reason='checkmate')
        # Create game for user B
        self.GameResult.objects.create(user=self.user_b, mode='ai', winner='black', end_reason='resign')

        # Check as User A
        self.client.login(username='usera', password='password123')
        response = self.client.get('/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<td>PvP</td>')
        self.assertNotContains(response, '<td>AI</td>')
        self.client.logout()

        # Check as User B
        self.client.login(username='userb', password='password123')
        response = self.client.get('/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<td>AI</td>')
        self.assertNotContains(response, '<td>PvP</td>')

    def test_empty_stats_page(self):
        """Users with no games should see a clean empty state."""
        self.client.login(username='usera', password='password123')
        response = self.client.get('/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No games played yet.')
        # Summary cards should show 0 (now 4 cards)
        self.assertContains(response, '<div class="num">0</div>', count=4)
        # No <tr> should be present in the tbody
        self.assertNotContains(response, '<tr><td>')

    def test_stats_aggregation(self):
        """Stats counts should accurately reflect only the current user's games."""
        # User A plays as white, wins as white (1 user win, 0 AI win)
        self.GameResult.objects.create(
            user=self.user_a, mode='ai', winner='white', player_color='white', end_reason='checkmate'
        )
        # User A plays as black, AI wins as white (0 user win, 1 AI win)
        self.GameResult.objects.create(
            user=self.user_a, mode='ai', winner='white', player_color='black', end_reason='checkmate'
        )
        # User A plays as black, wins as black (1 user win, 0 AI win)
        self.GameResult.objects.create(
            user=self.user_a, mode='ai', winner='black', player_color='black', end_reason='checkmate'
        )
        # User A draws
        self.GameResult.objects.create(
            user=self.user_a, mode='ai', winner='draw', player_color='white', end_reason='stalemate'
        )
        # User B has 5 AI wins
        for _ in range(5):
            self.GameResult.objects.create(
                user=self.user_b, mode='ai', winner='white', player_color='white', end_reason='checkmate'
            )

        self.client.login(username='usera', password='password123')
        response = self.client.get('/stats/')
        self.assertContains(response, '<div class="num">4</div>')  # Total AI Games
        self.assertContains(response, '<div class="num">2</div>')  # User Wins vs AI
        self.assertContains(response, '<div class="num">1</div>')  # AI Wins
        self.assertContains(response, '<div class="num">1</div>')  # Draws

    def test_filter_invalid_records(self):
        """Records with empty mode should be filtered out."""
        # This shouldn't happen with the model but the view handles it
        self.GameResult.objects.create(user=self.user_a, mode='', winner='white', end_reason='checkmate')
        self.client.login(username='usera', password='password123')
        response = self.client.get('/stats/')
        self.assertNotContains(response, 'Checkmate')
        self.assertContains(response, 'No games played yet.')
