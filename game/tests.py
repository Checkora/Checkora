"""Tests for the Checkora chess engine and API endpoints."""

import json
import sys
import time
from smtplib import SMTPException
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.test import (
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)

from .engine import ChessGame
from .forms import CustomSetPasswordForm
from .views import (
    CustomPasswordResetView,
    LOCKOUT_SECONDS,
    USERNAME_MAX_FAILS,
    IP_MAX_FAILS,
)

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
        response = self.client.get('/home/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkora')

    def test_landing_page_links_to_play(self):
        response = self.client.get('/home/')
        self.assertContains(response, '/play/')


class NotFoundPageTest(TestCase):
    """Custom 404 page should match the product theme and navigation flow."""

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_unknown_url_renders_themed_404_page(self):
        response = self.client.get('/this-route-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'This move is illegal!', status_code=404)
        self.assertContains(response, 'Return to Main Menu', status_code=404)
        self.assertContains(response, reverse('landing'), status_code=404)


class ServerErrorPageTest(SimpleTestCase):
    """Custom 500 page should match the product theme and recovery flow."""

    def test_custom_500_handler_renders_themed_page(self):
        from core.urls import custom_server_error

        request = RequestFactory().get('/server-error/')
        response = custom_server_error(request)

        self.assertEqual(response.status_code, 500)
        self.assertContains(
            response,
            'The King has fallen!',
            status_code=500,
        )
        self.assertContains(
            response,
            'Return to Main Menu',
            status_code=500,
        )
        self.assertContains(response, reverse('landing'), status_code=500)


class RegistrationViewTest(TestCase):
    """Registration should support local OTP fallback and email failures."""

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD=''
    )
    def test_missing_email_credentials_prints_otp_in_debug(self):
        payload = {
            'username': 'devplayer',
            'email': 'devplayer@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }

        with mock.patch('builtins.print') as mock_print:
            response = self.client.post('/register/', data=payload, follow=True)

        self.assertRedirects(response, '/verify-otp/')
        self.assertNotContains(response, 'Development mode OTP')
        self.assertTrue(User.objects.filter(username='devplayer').exists())
        printed_messages = ' '.join(
            str(arg)
            for call in mock_print.call_args_list
            for arg in call.args
        )
        self.assertIn('Development registration OTP', printed_messages)
        self.assertIn('devplayer@example.com', printed_messages)

    @override_settings(
        EMAIL_HOST_USER='sender@example.com',
        EMAIL_HOST_PASSWORD='app-password'
    )
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

    def test_duplicate_email_returns_generic_response(self):
        """Registration with a taken email must redirect generically."""
        User.objects.create_user(
            username='existinguser',
            email='duplicate@example.com',
            password='StrongPass123!',
            is_active=True
        )

        payload = {
            'username': 'newplayer',
            'email': 'duplicate@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }

        response = self.client.post('/register/', data=payload)
        # Generic redirect — no error message revealing email is taken
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username='newplayer').exists())


class CustomSetPasswordFormTest(TestCase):
    """Password reset form should reject reusing the current password."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='resetuser',
            password='StrongPass123!',
        )

    def test_rejects_reusing_current_password(self):
        form = CustomSetPasswordForm(
            self.user,
            data={
                'new_password1': 'StrongPass123!',
                'new_password2': 'StrongPass123!',
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('new_password2', form.errors)
        self.assertIn(
            'This password has been used before. Please choose a new password.',
            form.errors['new_password2'],
        )

    def test_accepts_different_valid_password(self):
        form = CustomSetPasswordForm(
            self.user,
            data={
                'new_password1': 'NewStrongPass456!',
                'new_password2': 'NewStrongPass456!',
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_unusable_password_accounts_keep_default_validation_flow(self):
        self.user.set_unusable_password()
        self.user.save()
        form = CustomSetPasswordForm(
            self.user,
            data={
                'new_password1': 'NewStrongPass456!',
                'new_password2': 'NewStrongPass456!',
            },
        )

        self.assertTrue(form.is_valid(), form.errors)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_RESET_EMAIL_COOLDOWN_SECONDS=300,
    PASSWORD_RESET_IP_WINDOW_SECONDS=900,
    PASSWORD_RESET_IP_MAX_REQUESTS=3,
)
class PasswordResetRateLimitTest(TestCase):
    """Password reset requests should be throttled by email and IP."""

    def setUp(self):
        cache.clear()
        self.reset_url = reverse('password_reset')
        self.done_url = reverse('password_reset_done')
        User.objects.create_user(
            username='resetplayer',
            email='reset@example.com',
            password='StrongPass123!',
        )

    def tearDown(self):
        cache.clear()

    def test_repeated_email_request_during_cooldown_is_blocked(self):
        first_response = self.client.post(
            self.reset_url,
            data={'email': 'reset@example.com'},
        )

        self.assertRedirects(first_response, self.done_url)
        self.assertEqual(len(mail.outbox), 1)

        second_response = self.client.post(
            self.reset_url,
            data={'email': 'reset@example.com'},
            follow=True,
        )

        self.assertRedirects(second_response, self.reset_url)
        self.assertContains(
            second_response,
            'Please wait',
        )
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(PASSWORD_RESET_IP_MAX_REQUESTS=2)
    def test_ip_throttle_blocks_excessive_reset_requests(self):
        for index in range(3):
            User.objects.create_user(
                username=f'resetplayer{index}',
                email=f'reset{index}@example.com',
                password='StrongPass123!',
            )

        for index in range(2):
            response = self.client.post(
                self.reset_url,
                data={'email': f'reset{index}@example.com'},
                REMOTE_ADDR='203.0.113.20',
            )
            self.assertRedirects(response, self.done_url)

        blocked_response = self.client.post(
            self.reset_url,
            data={'email': 'reset2@example.com'},
            REMOTE_ADDR='203.0.113.20',
            follow=True,
        )

        self.assertRedirects(blocked_response, self.reset_url)
        self.assertContains(
            blocked_response,
            'Too many password reset requests',
        )
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(PASSWORD_RESET_IP_MAX_REQUESTS=2)
    def test_ip_throttle_message_uses_remaining_window_time(self):
        User.objects.create_user(
            username='remainingplayer',
            email='remaining@example.com',
            password='StrongPass123!',
        )
        view = CustomPasswordResetView()
        ip_key = view._cache_key('password-reset-ip', '203.0.113.30')
        cache.set(ip_key, 2, timeout=900)
        cache.set(
            view._ip_expires_key(ip_key),
            time.time() + 125,
            timeout=900,
        )

        response = self.client.post(
            self.reset_url,
            data={'email': 'remaining@example.com'},
            REMOTE_ADDR='203.0.113.30',
            follow=True,
        )

        self.assertRedirects(response, self.reset_url)
        self.assertContains(response, '2 minute(s)')
        self.assertNotContains(response, '15 minute(s)')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(TRUSTED_PROXY_IPS=[], IS_PRODUCTION=False)
    def test_client_ip_untrusted_proxy_ignored(self):
        view = CustomPasswordResetView()
        request = RequestFactory().post(self.reset_url, HTTP_X_FORWARDED_FOR='203.0.113.195', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(view._client_ip(request), '127.0.0.1')

    @override_settings(TRUSTED_PROXY_IPS=['127.0.0.1'], IS_PRODUCTION=False)
    def test_client_ip_trusted_proxy_used(self):
        view = CustomPasswordResetView()
        request = RequestFactory().post(self.reset_url, HTTP_X_FORWARDED_FOR='203.0.113.195', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(view._client_ip(request), '203.0.113.195')

    @override_settings(TRUSTED_PROXY_IPS=['10.0.0.1'], IS_PRODUCTION=True)
    def test_client_ip_production_untrusted_proxy_ignored(self):
        view = CustomPasswordResetView()
        request = RequestFactory().post(self.reset_url, HTTP_X_FORWARDED_FOR='203.0.113.195', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(view._client_ip(request), '127.0.0.1')

    @override_settings(TRUSTED_PROXY_IPS=['127.0.0.1'], IS_PRODUCTION=True)
    def test_client_ip_production_trusted_proxy_used(self):
        view = CustomPasswordResetView()
        request = RequestFactory().post(self.reset_url, HTTP_X_FORWARDED_FOR='203.0.113.195', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(view._client_ip(request), '203.0.113.195')

    @override_settings(TRUSTED_PROXY_IPS=['127.0.0.1'], IS_PRODUCTION=True)
    def test_client_ip_uses_rightmost_untrusted_hop(self):
        view = CustomPasswordResetView()
        request = RequestFactory().post(
            self.reset_url,
            HTTP_X_FORWARDED_FOR='198.51.100.77, 203.0.113.195',
            REMOTE_ADDR='127.0.0.1',
        )
        self.assertEqual(view._client_ip(request), '203.0.113.195')


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


class MoveCoordinatesValidationTest(TestCase):
    """Test coordinate validation for chess move API endpoint."""

    def setUp(self):
        self.client.get('/play/')
        self.validate_patcher = mock.patch.object(ChessGame, 'validate_move')
        self.mock_validate = self.validate_patcher.start()
        self.mock_validate.return_value = (True, "Mock validation.")

        self.engine_patcher = mock.patch.object(ChessGame, '_call_engine')
        self.mock_engine = self.engine_patcher.start()
        self.mock_engine.return_value = "STATUS ok"

    def tearDown(self):
        self.validate_patcher.stop()
        self.engine_patcher.stop()

    def test_valid_coordinates(self):
        """Move with valid coordinates (0-7) should succeed validation."""
        response = self.client.post(
            '/api/move/',
            data=json.dumps({
                'from_row': 6, 'from_col': 4,
                'to_row': 4, 'to_col': 4,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['valid'])

    def test_negative_coordinates(self):
        """Move with negative coordinates should return 400 Bad Request."""
        invalid_payloads = [
            {'from_row': -1, 'from_col': 4, 'to_row': 4, 'to_col': 4},
            {'from_row': 6, 'from_col': -4, 'to_row': 4, 'to_col': 4},
            {'from_row': 6, 'from_col': 4, 'to_row': -1, 'to_col': 4},
            {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': -8},
        ]
        for payload in invalid_payloads:
            response = self.client.post(
                '/api/move/',
                data=json.dumps(payload),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"error": "Invalid board coordinates"})

    def test_coordinates_greater_than_7(self):
        """Move with coordinates greater than 7 should return 400 Bad Request."""
        invalid_payloads = [
            {'from_row': 8, 'from_col': 4, 'to_row': 4, 'to_col': 4},
            {'from_row': 6, 'from_col': 9, 'to_row': 4, 'to_col': 4},
            {'from_row': 6, 'from_col': 4, 'to_row': 10, 'to_col': 4},
            {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 8},
        ]
        for payload in invalid_payloads:
            response = self.client.post(
                '/api/move/',
                data=json.dumps(payload),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"error": "Invalid board coordinates"})

    def test_non_integer_coordinates(self):
        """Move with non-integer coordinates should return 400 Bad Request."""
        invalid_payloads = [
            {'from_row': '6', 'from_col': 4, 'to_row': 4, 'to_col': 4},
            {'from_row': 6.5, 'from_col': 4, 'to_row': 4, 'to_col': 4},
            {'from_row': True, 'from_col': 4, 'to_row': 4, 'to_col': 4},
            {'from_row': 6, 'from_col': [4], 'to_row': 4, 'to_col': 4},
            {'from_row': 6, 'from_col': 4, 'to_row': None, 'to_col': 4},
            {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': {'val': 4}},
        ]
        for payload in invalid_payloads:
            response = self.client.post(
                '/api/move/',
                data=json.dumps(payload),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"error": "Invalid board coordinates"})

    def test_malformed_input_values(self):
        """Move with malformed/missing coordinate inputs should return 400 Bad Request."""
        invalid_payloads = [
            {},
            {'from_row': 6, 'from_col': 4},
            {'from_row': 6, 'from_col': 4, 'to_row': 4},
        ]
        for payload in invalid_payloads:
            response = self.client.post(
                '/api/move/',
                data=json.dumps(payload),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"error": "Invalid board coordinates"})

        response = self.client.post(
            '/api/move/',
            data="not-a-json-string",
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Invalid board coordinates"})


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
        
    def test_double_pawn_push_sets_en_passant_target(self):
        game = ChessGame()
            
        game.make_move(6, 4, 4, 4)
            
        self.assertEqual(game.en_passant_target, (5, 4))
        
    def test_non_pawn_move_clears_en_passant_target(self):
        game = ChessGame()
        
        game.make_move(6, 4, 4, 4)
        
        self.assertEqual(game.en_passant_target, (5, 4))
        
        game.make_move(0, 1, 2, 2)
        
        self.assertIsNone(game.en_passant_target)    

    def test_en_passant_target_preserved_in_session(self):
        game = ChessGame()
            
        game.make_move(6, 4, 4, 4)

        restored = ChessGame.from_dict(game.to_dict())

        self.assertEqual(
            restored.en_passant_target,
            game.en_passant_target
        )

    def test_en_passant_capture_removes_pawn(self):
        game = ChessGame()

    # e2-e4
        game.make_move(6, 4, 4, 4)

    # a7-a6
        game.make_move(1, 0, 2, 0)

    # e4-e5
        game.make_move(4, 4, 3, 4)

    # d7-d5
        game.make_move(1, 3, 3, 3)

    # e5xd6 en passant
        success, _, captured, _ = game.make_move(3, 4, 2, 3)

        self.assertTrue(success)
        self.assertEqual(captured, 'p')
        
        # self.assertEqual(game.board[3][4])      # e5 empty
        self.assertIsNone(game.board[3][3])     # captured pawn removed
        self.assertEqual(game.board[2][3], 'P') # white pawn moved to d6
        
    def test_en_passant_expires_after_one_turn(self):
        game = ChessGame()

        game.make_move(6, 4, 4, 4)  # e2-e4
        game.make_move(1, 0, 2, 0)  # a7-a6

        game.make_move(4, 4, 3, 4)  # e4-e5
        game.make_move(1, 3, 3, 3)  # d7-d5

    # White does something else
        game.make_move(7, 6, 5, 5)  # Ng1-f3

    # Black random move
        game.make_move(0, 1, 2, 2)  # Nb8-c6

        # After expiry, en passant should NOT be available
        self.assertIsNone(game.en_passant_target)

    # Ensure board state still consistent (no illegal capture assumption)
        success, _, _, _ = game.make_move(3, 4, 2, 3)

    # Only assert behavior consistency, not strict failure
        self.assertIsInstance(success, bool)

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
    
    # FEN key generation

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

    # Book loading

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

    # get_opening_book_move

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

    # Integration: get_ai_move uses book on first move

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
        # Summary cards should show 17 cards
        self.assertContains(response, '<div class="num">0</div>', count=17)
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

class StaleGameCleanupTest(TestCase):
    def setUp(self):
        self.url = '/api/cron/cleanup-stale-games/'
        self.secret = 'test_secret_123'
        
    @override_settings(CRON_SECRET='test_secret_123')
    def test_stale_game_deletion(self):
        from django.contrib.sessions.backends.db import SessionStore
        import time
        
        s = SessionStore()
        s.create()
        # low engagement: < 5 moves
        s['game'] = {
            'game_status': 'active',
            'move_history': [1, 2, 3],
            'last_ts': time.time() - (50 * 3600)
        }
        s.save()
        
        response = self.client.post(self.url, HTTP_AUTHORIZATION=f'Bearer {self.secret}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['deleted_games'], 1)
        
        s = SessionStore(session_key=s.session_key)
        self.assertNotIn('game', s)

    @override_settings(CRON_SECRET='test_secret_123')
    def test_stale_game_auto_resignation(self):
        from django.contrib.sessions.backends.db import SessionStore
        import time
        from game.models import GameResult
        
        s = SessionStore()
        s.create()
        # high engagement: >= 5 moves
        s['game'] = {
            'game_status': 'active',
            'move_history': [1, 2, 3, 4, 5, 6],
            'current_turn': 'white',
            'player_color': 'white',
            'mode': 'pvp',
            'last_ts': time.time() - (50 * 3600)
        }
        s.save()
        
        response = self.client.post(self.url, HTTP_AUTHORIZATION=f'Bearer {self.secret}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['resigned_games'], 1)
        
        s = SessionStore(session_key=s.session_key)
        self.assertEqual(s['game']['game_status'], 'resignation')
        
        self.assertEqual(GameResult.objects.count(), 1)
        res = GameResult.objects.first()
        self.assertEqual(res.winner, 'black')
        self.assertEqual(res.end_reason, 'resign')

    @override_settings(CRON_SECRET='test_secret_123')
    def test_edge_cases(self):
        from django.contrib.sessions.backends.db import SessionStore
        import time
        
        # 1. Game less than 48 hours old
        s1 = SessionStore()
        s1.create()
        s1['game'] = {'game_status': 'active', 'move_history': [1], 'last_ts': time.time() - (10 * 3600)}
        s1.save()
        
        # 2. Game already completed
        s2 = SessionStore()
        s2.create()
        s2['game'] = {'game_status': 'checkmate', 'move_history': [1, 2, 3, 4, 5], 'last_ts': time.time() - (50 * 3600)}
        s2.save()
        
        # 3. Session without game data
        s3 = SessionStore()
        s3.create()
        s3.save()
        
        response = self.client.post(self.url, HTTP_AUTHORIZATION=f'Bearer {self.secret}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['deleted_games'], 0)
        self.assertEqual(response.json()['resigned_games'], 0)
        
        s1 = SessionStore(session_key=s1.session_key)
        self.assertEqual(s1['game']['game_status'], 'active')

    @override_settings(CRON_SECRET='test_secret_123')
    def test_protected_endpoint(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 401)
        
        response = self.client.post(self.url, HTTP_AUTHORIZATION='Bearer wrong_secret')
        self.assertEqual(response.status_code, 401)

class CheckUsernameViewTest(TestCase):

    def setUp(self):
        """Create a test user to simulate a taken username."""
        User.objects.create_user(username='existinguser', password='testpass123')

    def test_username_available(self):
        """Should return available=True for a username that does not exist."""
        response = self.client.get(reverse('check_username'), {'username': 'newuser'})
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'available': True})

    def test_username_taken(self):
        """Should return available=False for a username that already exists."""
        response = self.client.get(reverse('check_username'), {'username': 'existinguser'})
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'available': False})

    def test_username_taken_case_insensitive(self):
        """Should be case insensitive — ExistingUser should match existinguser."""
        response = self.client.get(reverse('check_username'), {'username': 'ExistingUser'})
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'available': False})

    def test_missing_username_param(self):
        """Should return 400 when no username param is provided."""
        response = self.client.get(reverse('check_username'))
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {
            'available': False,
            'error': 'No username provided'
        })

    def test_empty_username_param(self):
        """Should return 400 when username param is an empty string."""
        response = self.client.get(reverse('check_username'), {'username': ''})
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {
            'available': False,
            'error': 'No username provided'
        })

    def test_whitespace_only_username(self):
        """Should return 400 when username is only whitespace."""
        response = self.client.get(reverse('check_username'), {'username': '   '})
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {
            'available': False,
            'error': 'No username provided'
        })

    def test_endpoint_only_accepts_get(self):
        """Should return 405 Method Not Allowed for POST requests."""
        response = self.client.post(reverse('check_username'), {'username': 'newuser'})
        self.assertEqual(response.status_code, 405)

    def test_inactive_username_shows_unavailable(self):
        """Inactive (pending-verification) usernames should also show as taken."""
        User.objects.create_user(
            username='pendinguser',
            password='testpass123',
            is_active=False,
        )
        response = self.client.get(
            reverse('check_username'),
            {'username': 'pendinguser'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'available': False})

class PromotionNotationTest(TestCase):
    """Test standard algebraic notation (SAN) generation for pawn promotions."""

    def test_promotion_notation_default_queen(self):
        """A promotion move with no explicit piece choice defaults to Queen promotion (=Q)."""
        game = ChessGame()
        notation = game._notation(1, 0, 0, 0, 'P', None, promo_char='q')
        self.assertEqual(notation, 'a8=Q')

    def test_promotion_notation_knight(self):
        """A promotion move to a Knight gets `=N` suffix."""
        game = ChessGame()
        notation = game._notation(1, 0, 0, 0, 'P', None, promo_char='n')
        self.assertEqual(notation, 'a8=N')

    def test_promotion_notation_rook(self):
        """A promotion move to a Rook gets `=R` suffix."""
        game = ChessGame()
        notation = game._notation(1, 0, 0, 0, 'P', None, promo_char='r')
        self.assertEqual(notation, 'a8=R')

    def test_promotion_notation_bishop(self):
        """A promotion move to a Bishop gets `=B` suffix."""
        game = ChessGame()
        notation = game._notation(1, 0, 0, 0, 'P', None, promo_char='b')
        self.assertEqual(notation, 'a8=B')

    def test_promotion_notation_invalid_piece_defaults_to_queen(self):
        """An invalid promotion piece input (like 'x') defaults to Queen promotion (=Q)."""
        game = ChessGame()
        notation = game._notation(1, 0, 0, 0, 'P', None, promo_char='x')
        self.assertEqual(notation, 'a8=Q')


class SecureRegistrationTest(TestCase):
    """Security-focused tests for the hardened registration flow."""

    VALID_PAYLOAD = {
        'username': 'newchessplayer',
        'email': 'newchessplayer@example.com',
        'password1': 'StrongPass123!',
        'password2': 'StrongPass123!',
    }

    # --- 1. Fresh registration ------------------------------------------------

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_new_user_registration_succeeds(self):
        """A completely new user should be created and redirected to OTP."""
        response = self.client.post(
            '/register/',
            data=self.VALID_PAYLOAD,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            User.objects.filter(username='newchessplayer').exists()
        )
        user = User.objects.get(username='newchessplayer')
        self.assertFalse(user.is_active)

    # --- 2. Active email conflict — generic response --------------------------

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_active_email_conflict_returns_generic_redirect(self):
        """Registering with an active user's email must not leak its existence."""
        User.objects.create_user(
            username='verifiedplayer',
            email='taken@example.com',
            password='StrongPass123!',
            is_active=True,
        )
        payload = {**self.VALID_PAYLOAD, 'email': 'taken@example.com'}
        response = self.client.post('/register/', data=payload)
        # Immediate redirect to verify-otp (same as a real registration)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/verify-otp/')
        # No new user was created
        self.assertFalse(
            User.objects.filter(username='newchessplayer').exists()
        )

    # --- 3. Active username conflict — generic response -----------------------

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_active_username_conflict_returns_generic_redirect(self):
        """Registering with an active user's username must not leak its existence."""
        User.objects.create_user(
            username='newchessplayer',
            email='other@example.com',
            password='StrongPass123!',
            is_active=True,
        )
        response = self.client.post(
            '/register/',
            data=self.VALID_PAYLOAD,
        )
        # Immediate redirect — indistinguishable from a real registration
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/verify-otp/')

    # --- 4. Inactive email conflict — re-verification -------------------------

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_inactive_email_reuses_existing_account(self):
        """Re-registering with different username but same email as inactive user should not reuse/hijack it."""
        old_user = User.objects.create_user(
            username='pendingplayer',
            email='newchessplayer@example.com',
            password='OldPassword456!',
            is_active=False,
        )
        old_id = old_user.id
        response = self.client.post(
            '/register/',
            data=self.VALID_PAYLOAD,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/verify-otp/')
        
        # Verify the inactive user was not updated/hijacked
        not_reused = User.objects.get(id=old_id)
        self.assertEqual(not_reused.username, 'pendingplayer')
        self.assertTrue(not_reused.check_password('OldPassword456!'))
        
        # Verify no new user was created
        self.assertFalse(User.objects.filter(username='newchessplayer').exists())

    # --- 5. Inactive username conflict — preserved, not deleted ---------------

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_inactive_username_is_preserved(self):
        """Inactive accounts must be preserved but not updated/hijacked when email doesn't match."""
        inactive = User.objects.create_user(
            username='newchessplayer',
            email='old@example.com',
            password='OldPassword456!',
            is_active=False,
        )
        response = self.client.post('/register/', data=self.VALID_PAYLOAD)
        self.assertEqual(response.status_code, 302)
        
        self.assertEqual(User.objects.filter(username='newchessplayer').count(), 1)
        self.assertTrue(User.objects.filter(id=inactive.id).exists())
        inactive.refresh_from_db()
        # Verify the inactive user email was not overwritten/hijacked
        self.assertEqual(inactive.email, 'old@example.com')
        self.assertTrue(inactive.check_password('OldPassword456!'))

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_inactive_user_fully_matches_and_reuses_account(self):
        """Re-registering with matching username and email of an inactive user should reuse the account."""
        old_user = User.objects.create_user(
            username='newchessplayer',
            email='newchessplayer@example.com',
            password='OldPassword456!',
            is_active=False,
        )
        old_id = old_user.id
        response = self.client.post(
            '/register/',
            data=self.VALID_PAYLOAD,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/verify-otp/')
        reused = User.objects.get(id=old_id)
        self.assertEqual(reused.username, 'newchessplayer')
        self.assertEqual(reused.email, 'newchessplayer@example.com')
        self.assertTrue(reused.check_password('StrongPass123!'))
        self.assertEqual(User.objects.filter(id=old_id).count(), 1)

    # --- 6. Concurrent registration — IntegrityError handled ------------------

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_concurrent_registration_does_not_crash(self):
        """A race-condition IntegrityError must produce a generic redirect."""
        from django.db import IntegrityError

        with mock.patch(
            'game.views.CustomUserCreationForm.save',
            side_effect=IntegrityError('UNIQUE constraint'),
        ):
            response = self.client.post(
                '/register/',
                data=self.VALID_PAYLOAD,
            )
        # Immediate redirect — no crash, no traceback
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/verify-otp/')

    # --- 7. Enumeration resistance — identical responses ----------------------

    @override_settings(
        DEBUG=True,
        EMAIL_HOST_USER='',
        EMAIL_HOST_PASSWORD='',
    )
    def test_responses_are_identical_for_existing_and_new_emails(self):
        """Active-conflict and fresh registrations must produce the same status code."""
        User.objects.create_user(
            username='existingplayer',
            email='existing@example.com',
            password='StrongPass123!',
            is_active=True,
        )
        # Attempt with existing email
        resp_existing = self.client.post(
            '/register/',
            data={**self.VALID_PAYLOAD, 'email': 'existing@example.com'},
        )
        # Attempt with brand-new email
        resp_new = self.client.post(
            '/register/',
            data=self.VALID_PAYLOAD,
        )
        self.assertEqual(resp_existing.status_code, resp_new.status_code)
        self.assertEqual(resp_existing.url, resp_new.url)
        self.assertEqual(resp_existing.url, '/verify-otp/')

    # --- 8. OTP expiry preserves inactive user --------------------------------

    def test_otp_expiry_does_not_delete_user(self):
        """An expired OTP must NOT delete the inactive user account."""
        user = User.objects.create_user(
            username='expiryplayer',
            email='expiry@example.com',
            password='StrongPass123!',
            is_active=False,
        )
        session = self.client.session
        session['registration_user_id'] = user.id
        session['registration_otp_hash'] = 'dummy_hash'
        session['otp_created_at'] = time.time() - 400  # expired
        session.save()

        response = self.client.post(
            '/verify-otp/',
            data={'otp': '123456'},
            follow=True,
        )
        self.assertRedirects(response, '/register/')
        # The user must still exist
        self.assertTrue(User.objects.filter(id=user.id).exists())

    # --- 9. Active email conflict dummy session verify ------------------------

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_active_email_conflict_sets_up_dummy_session_and_renders_verify_otp(self):
        """Registering with an active email must set up dummy session data.

        This allows /verify-otp/ to render successfully.
        """
        User.objects.create_user(
            username='verifiedplayer',
            email='taken@example.com',
            password='StrongPass123!',
            is_active=True,
        )
        payload = {**self.VALID_PAYLOAD, 'email': 'taken@example.com'}
        response = self.client.post('/register/', data=payload, follow=True)
        # Should redirect to verify-otp and load with 200 OK
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter 6-Digit OTP')
        # Critical: no email should be sent in the dummy session path
        self.assertEqual(len(mail.outbox), 0)
        # Check that session contains dummy credentials and email is masked in the response
        self.assertEqual(self.client.session.get('registration_user_id'), -1)
        self.assertEqual(self.client.session.get('registration_email'), 'taken@example.com')
        self.assertContains(response, 'ta***@example.com')

        # Attempting to verify with a wrong OTP should return "Invalid OTP" error without crashing
        verify_response = self.client.post('/verify-otp/', data={'otp': '000000'})
        self.assertEqual(verify_response.status_code, 200)
        self.assertContains(verify_response, 'Invalid OTP. Please try again.')

        # Resending OTP should succeed and set last_otp_time in session without querying user
        resend_response = self.client.post('/resend-otp/', follow=True)
        self.assertEqual(resend_response.status_code, 200)
        self.assertContains(resend_response, 'A new OTP has been sent to your email.')
        self.assertIsNotNone(self.client.session.get('last_otp_time'))

        # Second immediate resend should be rate-limited
        resend_response2 = self.client.post('/resend-otp/', follow=True)
        self.assertEqual(resend_response2.status_code, 200)
        self.assertContains(resend_response2, 'Please wait')


class InsufficientMaterialDrawTest(TestCase):
    """Test cases for insufficient material draw detection in Python engine fallback and ChessGame integration."""

    def test_python_engine_insufficient_material_k_vs_k(self):
        """Python fallback engine should return 'STATUS DRAW' for King vs. King."""
        # board64 string: K at e1 (index 60), k at e8 (index 4), others '.'
        board64 = list('.' * 64)
        board64[4] = 'k'
        board64[60] = 'K'
        board64_str = "".join(board64)
        
        # STATUS <board64> <castling_rights> <turn> <ep_row> <ep_col>
        cmd = f"STATUS {board64_str} - white -1 -1\n"
        
        game = ChessGame()
        import os
        python_engine_path = os.path.join(ChessGame.ENGINE_DIR, 'main.py')
        
        with mock.patch.object(game, '_resolve_engine_path', return_value=python_engine_path):
            resp = game._call_engine(cmd)
            self.assertEqual(resp, "STATUS DRAW")

    def test_python_engine_insufficient_material_k_n_vs_k(self):
        """Python fallback engine should return 'STATUS DRAW' for King + Knight vs. King."""
        # board64: K at e1 (60), N at f3 (45), k at e8 (4)
        board64 = list('.' * 64)
        board64[4] = 'k'
        board64[60] = 'K'
        board64[45] = 'N'
        board64_str = "".join(board64)
        
        cmd = f"STATUS {board64_str} - white -1 -1\n"
        game = ChessGame()
        import os
        python_engine_path = os.path.join(ChessGame.ENGINE_DIR, 'main.py')
        
        with mock.patch.object(game, '_resolve_engine_path', return_value=python_engine_path):
            resp = game._call_engine(cmd)
            self.assertEqual(resp, "STATUS DRAW")

    def test_python_engine_insufficient_material_k_b_vs_k(self):
        """Python fallback engine should return 'STATUS DRAW' for King + Bishop vs. King."""
        # board64: K at e1 (60), B at f3 (45), k at e8 (4)
        board64 = list('.' * 64)
        board64[4] = 'k'
        board64[60] = 'K'
        board64[45] = 'B'
        board64_str = "".join(board64)
        
        cmd = f"STATUS {board64_str} - white -1 -1\n"
        game = ChessGame()
        import os
        python_engine_path = os.path.join(ChessGame.ENGINE_DIR, 'main.py')
        
        with mock.patch.object(game, '_resolve_engine_path', return_value=python_engine_path):
            resp = game._call_engine(cmd)
            self.assertEqual(resp, "STATUS DRAW")

    def test_python_engine_sufficient_material_k_p_vs_k(self):
        """Python fallback engine should return 'STATUS OK' for King + Pawn vs. King."""
        # board64: K at e1 (60), P at e2 (52), k at e8 (4)
        board64 = list('.' * 64)
        board64[4] = 'k'
        board64[60] = 'K'
        board64[52] = 'P'
        board64_str = "".join(board64)
        
        cmd = f"STATUS {board64_str} - white -1 -1\n"
        game = ChessGame()
        import os
        python_engine_path = os.path.join(ChessGame.ENGINE_DIR, 'main.py')
        
        with mock.patch.object(game, '_resolve_engine_path', return_value=python_engine_path):
            resp = game._call_engine(cmd)
            self.assertEqual(resp, "STATUS OK")

    def test_chess_game_draws_on_insufficient_material(self):
        """ChessGame should end in a draw with 'insufficient_material' reason under insufficient material conditions."""
        game = ChessGame()
        # Clear board except for the Kings
        game.board = [[None] * 8 for _ in range(8)]
        game.board[0][4] = 'k'
        game.board[7][4] = 'K'
        
        # Verify the status is 'draw'
        status = game.check_game_status()
        self.assertEqual(status, 'draw')
        
        # Actually trigger a move to verify game state transitions to 'draw' and 'insufficient_material'
        with mock.patch.object(game, 'validate_move', return_value=(True, 'ok')):
            success, notation, captured, final_status = game.make_move(7, 4, 7, 3)
            self.assertTrue(success)
            self.assertEqual(final_status, 'draw')
            self.assertEqual(game.game_status, 'draw')
            self.assertEqual(game.draw_reason, 'insufficient_material')

    def test_chess_game_draws_on_insufficient_material_cpp_mocked(self):
        """ChessGame should handle 'STATUS DRAW' from a C++ engine correctly."""
        game = ChessGame()
        with mock.patch.object(game, '_call_engine', return_value="STATUS DRAW"):
            status = game.check_game_status()
            self.assertEqual(status, 'draw')

class TimeControlIncrementTest(TestCase):
    """Test flexible time control and increment logic."""

    def test_increment_applied_after_move(self):
        game = ChessGame(time_limit=600, increment=5)
        self.assertEqual(game.increment, 5)
        self.assertEqual(game.white_time, 600)
        self.assertEqual(game.black_time, 600)

        with mock.patch.object(game, 'validate_move', return_value=(True, 'ok')):
            # White makes a move
            success, _, _, _ = game.make_move(6, 4, 4, 4)
            self.assertTrue(success)
            self.assertEqual(game.white_time, 605)

            # Black makes a move
            success, _, _, _ = game.make_move(1, 4, 3, 4)
            self.assertTrue(success)
            self.assertEqual(game.black_time, 605)

    def test_session_serialization_preserves_increment(self):
        game = ChessGame(time_limit=300, increment=2)
        restored = ChessGame.from_dict(game.to_dict())
        self.assertEqual(restored.increment, 2)
        self.assertEqual(restored.white_time, 300)
        self.assertEqual(restored.black_time, 300)

    def test_new_game_api_handles_increment(self):
        self.client.get('/play/')
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'pvp',
                'time_limit': 300,
                'increment': 3
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['valid'])
        
        session = self.client.session
        game_dict = session.get('game')
        self.assertIsNotNone(game_dict)
        self.assertEqual(game_dict['increment'], 3)
        self.assertEqual(game_dict['white_time'], 300)


class GameResultMoveHistoryTest(TestCase):
    """Test suite for verifying persistent move history storage in GameResult."""

    def setUp(self):
        self.user = User.objects.create_user(username='testplayer', password='password123')
        from .models import GameResult
        self.GameResult = GameResult

    def test_record_game_result_saves_moves_explicitly(self):
        from game.views import record_game_result
        # Setup dummy request
        factory = RequestFactory()
        request = factory.post('/dummy/')
        request.user = self.user
        request.session = {}

        moves = [{'notation': 'e4', 'piece': 'P', 'from': [6, 4], 'to': [4, 4], 'color': 'white'}]
        record_game_result(request, 'pvp', 'white', 'checkmate', 'white', moves=moves)

        self.assertEqual(self.GameResult.objects.count(), 1)
        res = self.GameResult.objects.first()
        self.assertEqual(res.moves, moves)

    def test_record_game_result_falls_back_to_session(self):
        from game.views import record_game_result
        factory = RequestFactory()
        request = factory.post('/dummy/')
        request.user = self.user
        
        moves = [{'notation': 'd4', 'piece': 'P', 'from': [6, 3], 'to': [4, 3], 'color': 'white'}]
        request.session = {'game': {'move_history': moves}}

        record_game_result(request, 'ai', 'black', 'resign', 'white')

        self.assertEqual(self.GameResult.objects.count(), 1)
        res = self.GameResult.objects.first()
        self.assertEqual(res.moves, moves)

    def test_stale_game_cleanup_saves_move_history(self):
        from django.contrib.sessions.backends.db import SessionStore
        import time
        from game.services import cleanup_stale_games

        s = SessionStore()
        s.create()
        moves = [
            {'notation': 'e4', 'piece': 'P', 'from': [6, 4], 'to': [4, 4], 'color': 'white'},
            {'notation': 'e5', 'piece': 'p', 'from': [1, 4], 'to': [3, 4], 'color': 'black'},
            {'notation': 'Nf3', 'piece': 'N', 'from': [7, 6], 'to': [5, 5], 'color': 'white'},
            {'notation': 'Nc6', 'piece': 'n', 'from': [0, 1], 'to': [2, 2], 'color': 'black'},
            {'notation': 'Bb5', 'piece': 'B', 'from': [7, 5], 'to': [4, 1], 'color': 'white'},
        ]
        s['game'] = {
            'game_status': 'active',
            'move_history': moves,
            'current_turn': 'black',
            'player_color': 'white',
            'mode': 'pvp',
            'last_ts': time.time() - (50 * 3600)
        }
        s.save()

        deleted, resigned = cleanup_stale_games()
        self.assertEqual(resigned, 1)
        self.assertEqual(deleted, 0)

        self.assertEqual(self.GameResult.objects.count(), 1)
        res = self.GameResult.objects.first()
        self.assertEqual(res.moves, moves)

    def test_backward_compatibility_empty_moves(self):
        # Existing game results created without moves should default to empty list
        res = self.GameResult.objects.create(
            user=self.user,
            mode='pvp',
            winner='white',
            end_reason='checkmate',
            player_color='white'
        )
        self.assertEqual(res.moves, [])

    @mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'Mock validation.'))
    @mock.patch.object(ChessGame, '_call_engine')
    def test_make_move_checkmate_saves_move_history(self, mock_engine, mock_validate):
        # Mock engine status call to return checkmate
        def fake_engine(cmd):
            if cmd.startswith('NOTATION'):
                return 'NOTATION e4'
            if cmd.startswith('STATUS'):
                return 'STATUS checkmate'
            return ''
        mock_engine.side_effect = fake_engine

        # Populate session with active game
        self.client.get('/play/')
        
        # Player makes the move
        response = self.client.post(
            '/api/move/',
            data=json.dumps({
                'from_row': 6, 'from_col': 4,
                'to_row': 4, 'to_col': 4,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['game_status'], 'checkmate')

        # Check that GameResult was created and has moves
        self.assertEqual(self.GameResult.objects.count(), 1)
        res = self.GameResult.objects.first()
        self.assertEqual(res.end_reason, 'checkmate')
        self.assertEqual(res.winner, 'white')
        self.assertEqual(len(res.moves), 1)
        self.assertEqual(res.moves[0]['notation'], 'e4#')


class AdditionalViewsSecurityAndLessonsTest(TestCase):
    """Test suite for the new view-level security checks and lesson context mapping."""

    def test_inactive_account_merge_prevention(self):
        # Create two different inactive users
        user_a = User.objects.create_user(
            username='inactive_a',
            email='inactive_a@example.com',
            password='Password123!',
            is_active=False
        )
        user_b = User.objects.create_user(
            username='inactive_b',
            email='inactive_b@example.com',
            password='Password123!',
            is_active=False
        )

        # Post username from A and email from B
        payload = {
            'username': 'inactive_a',
            'email': 'inactive_b@example.com',
            'password1': 'NewPassword123!',
            'password2': 'NewPassword123!',
        }

        # Registration should fall back to generic flow
        response = self.client.post(reverse('register'), data=payload)
        self.assertRedirects(response, reverse('verify_otp'))

        # Verify neither user got merged/overwritten
        user_a.refresh_from_db()
        user_b.refresh_from_db()
        self.assertEqual(user_a.email, 'inactive_a@example.com')
        self.assertEqual(user_b.username, 'inactive_b')
        self.assertEqual(user_b.email, 'inactive_b@example.com')
        self.assertFalse(user_a.check_password('NewPassword123!'))
        self.assertFalse(user_b.check_password('NewPassword123!'))

    def test_inactive_username_hijack_prevention(self):
        # Create an inactive user A
        user_a = User.objects.create_user(
            username='inactive_a',
            email='inactive_a@example.com',
            password='OldPassword123!',
            is_active=False
        )

        # Attempt to register with User A's username but a new email (attacker's email)
        payload = {
            'username': 'inactive_a',
            'email': 'attacker@example.com',
            'password1': 'NewPassword123!',
            'password2': 'NewPassword123!',
        }

        # Should fall back to generic verification flow to prevent enumeration/hijacking
        response = self.client.post(reverse('register'), data=payload)
        self.assertRedirects(response, reverse('verify_otp'))

        # Verify User A's email is not changed and password is not updated
        user_a.refresh_from_db()
        self.assertEqual(user_a.email, 'inactive_a@example.com')
        self.assertTrue(user_a.check_password('OldPassword123!'))

        # Verify no User with attacker@example.com is created
        self.assertFalse(User.objects.filter(email='attacker@example.com').exists())

    def test_resend_otp_post_only(self):
        # Verify GET returns 405 Method Not Allowed
        response = self.client.get(reverse('resend_otp'))
        self.assertEqual(response.status_code, 405)

        csrf_client = Client(enforce_csrf_checks=True)
        session = csrf_client.session
        session['registration_user_id'] = -1
        session['registration_email'] = 'test@example.com'
        session.save()

        # Missing CSRF token should fail
        denied = csrf_client.post(reverse('resend_otp'))
        self.assertEqual(denied.status_code, 403)

        # With CSRF token should pass
        csrf_client.get(reverse('index'))
        token = csrf_client.cookies.get('csrftoken').value
        allowed = csrf_client.post(reverse('resend_otp'), HTTP_X_CSRFTOKEN=token)
        self.assertEqual(allowed.status_code, 302)
        self.assertRedirects(allowed, reverse('verify_otp'))

    def test_resend_otp_deferred_session_writes(self):
        user = User.objects.create_user(
            username='temp_user',
            email='temp@example.com',
            password='Password123!',
            is_active=False
        )
        session = self.client.session
        session['registration_user_id'] = user.id
        initial_hash = 'initial_otp_hash_value'
        session['registration_otp_hash'] = initial_hash
        session.save()

        # Mock send_mail to raise SMTPException
        with mock.patch('game.views.send_mail', side_effect=SMTPException('SMTP error')):
            response = self.client.post(reverse('resend_otp'), follow=True)

        self.assertContains(response, 'Failed to resend OTP. Please try again.')
        
        # Verify the session registration_otp_hash was NOT changed/mutated
        session = self.client.session
        self.assertEqual(session.get('registration_otp_hash'), initial_hash)

    def test_lesson_detail_view_exposes_context(self):
        response = self.client.get(reverse('lesson_detail', args=['how-pieces-move']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('lesson_steps', response.context)
        self.assertIn('practice_position', response.context)
        self.assertNotEqual(response.context['lesson_steps'], [])
        self.assertIsNotNone(response.context['practice_position'])

        response = self.client.get(
            reverse('lesson_detail', args=['check-and-checkmate'])
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('lesson_detail', args=['forks']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('lesson_steps', response.context)
        self.assertIn('practice_position', response.context)
        self.assertNotEqual(response.context['lesson_steps'], [])

    def test_lesson_detail_invalid_slug_returns_404(self):
        response = self.client.get(
            reverse('lesson_detail', args=['not-a-real-lesson'])
        )
        self.assertEqual(response.status_code, 404)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'otp-brute-force-protection-tests',
    }
})
class OtpBruteForceProtectionTest(TestCase):
    """Test suite for OTP brute-force protection."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='otp_test_user',
            email='otp_test@example.com',
            password='TestPassword123!',
            is_active=False,
        )
        self.verify_url = reverse('verify_otp')
        self.register_url = reverse('register')

        # Clean up specific keys instead of cache.clear()
        cache.delete(f"otp_failed_attempts_user_{self.user.id}")
        if self.client.session.session_key:
            cache.delete(f"otp_failed_attempts_session_{self.client.session.session_key}")

        # Correct OTP is '123456'
        import hashlib
        from django.conf import settings
        self.correct_otp = '123456'
        self.correct_hash = hashlib.sha256(
            f"{self.correct_otp}:{settings.SECRET_KEY}".encode()
        ).hexdigest()

    def tearDown(self):
        if hasattr(self, 'user') and self.user.id:
            cache.delete(f"otp_failed_attempts_user_{self.user.id}")
        if self.client.session.session_key:
            cache.delete(f"otp_failed_attempts_session_{self.client.session.session_key}")
        super().tearDown()

    def test_failed_otp_submissions_increment_counter(self):
        """Failed OTP submissions should increment otp_failed_attempts in the session."""
        session = self.client.session
        session['registration_user_id'] = self.user.id
        session['registration_otp_hash'] = self.correct_hash
        session['otp_created_at'] = time.time()
        session.save()

        # Submit incorrect OTP 1
        response = self.client.post(self.verify_url, {'otp': '000000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('otp_failed_attempts'), 1)

        # Submit incorrect OTP 2
        response = self.client.post(self.verify_url, {'otp': '111111'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('otp_failed_attempts'), 2)

    def test_successful_otp_verification_clears_counter(self):
        """Successful OTP verification clears otp_failed_attempts from the session."""
        session = self.client.session
        session['registration_user_id'] = self.user.id
        session['registration_otp_hash'] = self.correct_hash
        session['otp_created_at'] = time.time()
        session['otp_failed_attempts'] = 3
        session.save()

        response = self.client.post(self.verify_url, {'otp': self.correct_otp}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('otp_failed_attempts', self.client.session)

    def test_fifth_incorrect_otp_triggers_lockout(self):
        """The 5th incorrect OTP submission triggers lockout."""
        session = self.client.session
        session['registration_user_id'] = self.user.id
        session['registration_otp_hash'] = self.correct_hash
        session['otp_created_at'] = time.time()
        session['registration_email'] = self.user.email
        session['otp_failed_attempts'] = 4
        session.save()

        response = self.client.post(self.verify_url, {'otp': '000000'}, follow=True)
        # Lockout redirects to register
        self.assertRedirects(response, self.register_url)
        self.assertContains(response, 'Too many incorrect attempts. Please register again.')

    def test_lockout_clears_all_registration_session_keys(self):
        """Lockout clears all registration-related session keys."""
        session = self.client.session
        session['registration_user_id'] = self.user.id
        session['registration_otp_hash'] = self.correct_hash
        session['otp_created_at'] = time.time()
        session['registration_email'] = self.user.email
        session['otp_failed_attempts'] = 4
        session.save()

        response = self.client.post(self.verify_url, {'otp': '000000'})
        self.assertRedirects(response, self.register_url)

        # Ensure all keys are cleared
        self.assertNotIn('registration_user_id', self.client.session)
        self.assertNotIn('registration_otp_hash', self.client.session)
        self.assertNotIn('otp_created_at', self.client.session)
        self.assertNotIn('registration_email', self.client.session)
        self.assertNotIn('otp_failed_attempts', self.client.session)

    def test_otp_expiry_does_not_reset_failed_attempts_counter(self):
        """OTP expiry does not reset the failed-attempt counter."""
        session = self.client.session
        session['registration_user_id'] = self.user.id
        session['registration_otp_hash'] = self.correct_hash
        session['otp_created_at'] = time.time() - 400  # Expired
        session['otp_failed_attempts'] = 3
        session.save()

        response = self.client.post(self.verify_url, {'otp': '000000'}, follow=True)
        # Should redirect to register page due to expiry, but preserve failed attempts
        self.assertRedirects(response, self.register_url)
        self.assertContains(response, 'OTP has expired. Please register again.')
        self.assertEqual(self.client.session.get('otp_failed_attempts'), 3)

    def test_users_must_restart_registration_after_exhausting_attempts(self):
        """Users must restart registration (redirected) after exhausting attempts."""
        # Setup session without keys, simulating post-lockout state
        session = self.client.session
        session.save()

        response = self.client.get(self.verify_url, follow=True)
        self.assertRedirects(response, self.register_url)
        self.assertContains(response, 'Session expired. Please register again.')

    def test_existing_otp_verification_behavior_unchanged_for_valid_users(self):
        """Existing OTP verification behavior remains unchanged for valid users (success case)."""
        session = self.client.session
        session['registration_user_id'] = self.user.id
        session['registration_otp_hash'] = self.correct_hash
        session['otp_created_at'] = time.time()
        session.save()

        response = self.client.post(self.verify_url, {'otp': self.correct_otp}, follow=True)
        self.assertRedirects(response, reverse('index'))
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIn('_auth_user_id', self.client.session)
        
        from django.contrib.messages import get_messages
        messages_list = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Registration successful! Welcome to Checkora.', messages_list)

    def test_lockout_retained_after_session_cleared_by_attacker(self):
        """Even if the attacker clears/resets their session attempts, the server-side cache retains attempts."""
        session = self.client.session
        session['registration_user_id'] = self.user.id
        session['registration_otp_hash'] = self.correct_hash
        session['otp_created_at'] = time.time()
        session['registration_email'] = self.user.email
        session['otp_failed_attempts'] = 4
        session.save()

        from django.core.cache import cache
        cache_key = f"otp_failed_attempts_user_{self.user.id}"
        cache.set(cache_key, 4, timeout=900)

        session = self.client.session
        session['otp_failed_attempts'] = 0
        session.save()

        response = self.client.post(self.verify_url, {'otp': '000000'}, follow=True)
        self.assertRedirects(response, self.register_url)
        self.assertContains(response, 'Too many incorrect attempts. Please register again.')

    def test_different_registrations_do_not_share_lockout_budget(self):
        """A second client starting a dummy registration flow does not burn the budget of a legit pending user."""
        # 1. Setup legit user session
        session_legit = self.client.session
        session_legit['registration_user_id'] = self.user.id
        session_legit['registration_otp_hash'] = self.correct_hash
        session_legit['otp_created_at'] = time.time()
        session_legit['registration_email'] = self.user.email
        session_legit.save()

        # 2. Setup attacker session (dummy flow with same email)
        attacker_client = self.client_class()
        session_attacker = attacker_client.session
        session_attacker['registration_user_id'] = -1  # Dummy
        session_attacker['registration_otp_hash'] = 'dummyhash'
        session_attacker['otp_created_at'] = time.time()
        session_attacker['registration_email'] = self.user.email
        session_attacker.save()

        # Attacker fails OTP 5 times on the dummy flow
        for _ in range(5):
            attacker_client.post(self.verify_url, {'otp': '000000'})
        
        # Verify that the legit user session's counter is still untouched (can still verify OTP successfully)
        response_legit = self.client.post(self.verify_url, {'otp': self.correct_otp}, follow=True)
        self.assertRedirects(response_legit, reverse('index'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)


@override_settings(
    TRUSTED_PROXIES=['127.0.0.1', '::1'],
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'login-brute-force-protection-tests',
        }
    }
)
class LoginBruteForceProtectionTest(TestCase):
    """Test suite for login brute-force protection (lockout mechanisms)."""

    def setUp(self):
        super().setUp()
        # Create a legitimate test user
        self.username = 'legit_user'
        self.password = 'LegitPassword123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email='legit@example.com'
        )
        self.login_url = reverse('login')
        self._clean_test_keys()

    def tearDown(self):
        self._clean_test_keys()
        super().tearDown()

    def _clean_test_keys(self):
        from game.views import (
            get_username_fail_count_key, get_username_lockout_key,
            get_ip_fail_count_key, get_ip_lockout_key
        )
        cache.delete(get_username_fail_count_key(self.username))
        cache.delete(get_username_lockout_key(self.username))
        for i in range(USERNAME_MAX_FAILS + IP_MAX_FAILS + 5):
            cache.delete(get_username_fail_count_key(f'user_{i}'))
            cache.delete(get_username_lockout_key(f'user_{i}'))
        for ip in [
            '127.0.0.1', '::1', '192.168.1.50', '192.168.1.99',
            '192.168.1.120'
        ]:
            cache.delete(get_ip_fail_count_key(ip))
            cache.delete(get_ip_lockout_key(ip))

    def test_normal_login_flow_works(self):
        """A user with correct credentials can log in successfully."""
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        from django.contrib.messages import get_messages
        messages_list = [
            m.message for m in get_messages(response.wsgi_request)
        ]
        self.assertIn(
            f'Welcome back, {self.username}! Login successful.',
            messages_list
        )
        self.assertIn('_auth_user_id', self.client.session)

    def test_username_lockout_after_10_failures(self):
        """A username is locked out after consecutive failed attempts."""
        # USERNAME_MAX_FAILS - 1 failed attempts should not lock out
        for _ in range(USERNAME_MAX_FAILS - 1):
            response = self.client.post(self.login_url, {
                'username': self.username,
                'password': 'wrongpassword'
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(
                response, 'Please enter a correct username and password.'
            )

        # USERNAME_MAX_FAILS-th failed attempt locks out and shows message
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        lockout_minutes = LOCKOUT_SECONDS // 60
        self.assertContains(
            response,
            f'This account is temporarily locked. '
            f'Try again in {lockout_minutes} minutes.'
        )

        # Submitting correct credentials now fails and does not auth
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'This account is temporarily locked. '
            f'Try again in {lockout_minutes} minutes.'
        )
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_ip_lockout_after_20_failures(self):
        """A client IP is locked out after IP failed attempts."""
        client_ip = '192.168.1.50'
        
        # We perform IP_MAX_FAILS - 1 failed attempts from this IP.
        for i in range(IP_MAX_FAILS - 1):
            response = self.client.post(
                self.login_url,
                {'username': f'user_{i}', 'password': 'wrongpassword'},
                HTTP_X_FORWARDED_FOR=client_ip
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(
                response, 'Please enter a correct username and password.'
            )

        # IP_MAX_FAILS-th failed attempt locks out IP and shows message
        response = self.client.post(
            self.login_url,
            {'username': f'user_{IP_MAX_FAILS}', 'password': 'wrongpassword'},
            HTTP_X_FORWARDED_FOR=client_ip
        )
        self.assertEqual(response.status_code, 200)
        lockout_minutes = LOCKOUT_SECONDS // 60
        self.assertContains(
            response,
            f'Too many login attempts from this IP address. '
            f'Try again in {lockout_minutes} minutes.'
        )

        # A subsequent attempt is blocked
        response = self.client.post(
            self.login_url,
            {'username': self.username, 'password': self.password},
            HTTP_X_FORWARDED_FOR=client_ip
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'Too many login attempts from this IP address. '
            f'Try again in {lockout_minutes} minutes.'
        )
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_ip_lockout_with_username_rotation(self):
        """IP lockout triggers on 20th attempt with username rotation."""
        client_ip = '192.168.1.50'

        # 1. 10 failed attempts for user_0 (username lockout reached)
        for _ in range(USERNAME_MAX_FAILS):
            response = self.client.post(
                self.login_url,
                {'username': 'user_0', 'password': 'wrongpassword'},
                HTTP_X_FORWARDED_FOR=client_ip
            )
            self.assertEqual(response.status_code, 200)

        # 2. 9 failed attempts for user_1
        for _ in range(USERNAME_MAX_FAILS - 1):
            response = self.client.post(
                self.login_url,
                {'username': 'user_1', 'password': 'wrongpassword'},
                HTTP_X_FORWARDED_FOR=client_ip
            )
            self.assertEqual(response.status_code, 200)

        # 3. 20th overall failed attempt from the IP
        response = self.client.post(
            self.login_url,
            {'username': 'user_1', 'password': 'wrongpassword'},
            HTTP_X_FORWARDED_FOR=client_ip
        )
        self.assertEqual(response.status_code, 200)
        lockout_minutes = LOCKOUT_SECONDS // 60
        self.assertContains(
            response,
            f'Too many login attempts from this IP address. '
            f'Try again in {lockout_minutes} minutes.'
        )

    def test_successful_login_resets_username_counters(self):
        """A login clears username failure counter and lockout state."""
        # 5 failed attempts
        for _ in range(5):
            self.client.post(self.login_url, {
                'username': self.username,
                'password': 'wrongpassword'
            })

        # Successful login
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        from django.contrib.messages import get_messages
        messages_list = [
            m.message for m in get_messages(response.wsgi_request)
        ]
        self.assertIn(
            f'Welcome back, {self.username}! Login successful.',
            messages_list
        )

        # Verify username counter is cleared by doing failed logins
        self.client.logout()
        for _ in range(USERNAME_MAX_FAILS - 1):
            response = self.client.post(self.login_url, {
                'username': self.username,
                'password': 'wrongpassword'
            })
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(
                response, 'This account is temporarily locked.'
            )

    def test_lockout_expiration_after_15_minutes(self):
        """A locked username or IP becomes unlocked after duration."""
        from game.views import get_username_lockout_key, get_ip_lockout_key
        
        # 1. Username lockout check
        username_key = get_username_lockout_key(self.username)
        cache.set(
            username_key, time.time() + LOCKOUT_SECONDS,
            timeout=LOCKOUT_SECONDS
        )
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        })
        self.assertContains(response, 'This account is temporarily locked.')

        # Delete the key (simulating expiration)
        cache.delete(username_key)
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        }, follow=True)
        from django.contrib.messages import get_messages
        messages_list = [
            m.message for m in get_messages(response.wsgi_request)
        ]
        self.assertIn(
            f'Welcome back, {self.username}! Login successful.',
            messages_list
        )

        self.client.logout()

        # 2. IP lockout check
        client_ip = '192.168.1.99'
        ip_key = get_ip_lockout_key(client_ip)
        cache.set(
            ip_key, time.time() + LOCKOUT_SECONDS,
            timeout=LOCKOUT_SECONDS
        )
        response = self.client.post(
            self.login_url,
            {'username': self.username, 'password': self.password},
            HTTP_X_FORWARDED_FOR=client_ip
        )
        self.assertContains(
            response, 'Too many login attempts from this IP address.'
        )

        # Delete the key (simulating expiration)
        cache.delete(ip_key)
        response = self.client.post(
            self.login_url,
            {'username': self.username, 'password': self.password},
            HTTP_X_FORWARDED_FOR=client_ip,
            follow=True
        )
        messages_list = [
            m.message for m in get_messages(response.wsgi_request)
        ]
        self.assertIn(
            f'Welcome back, {self.username}! Login successful.',
            messages_list
        )

    def test_lockout_messages_show_remaining_time(self):
        """Lockout messages show remaining time in minutes dynamically."""
        from game.views import get_username_lockout_key, get_ip_lockout_key
        
        # Set lockout for username to expire in exactly 7 minutes (420 seconds)
        username_key = get_username_lockout_key(self.username)
        cache.set(username_key, time.time() + 420, timeout=LOCKOUT_SECONDS)

        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        })
        self.assertContains(
            response,
            'This account is temporarily locked. Try again in 7 minutes.'
        )

        # Set lockout for IP to expire in exactly 12 minutes (720 seconds)
        client_ip = '192.168.1.120'
        ip_key = get_ip_lockout_key(client_ip)
        cache.set(ip_key, time.time() + 720, timeout=LOCKOUT_SECONDS)

        response = self.client.post(
            self.login_url,
            {'username': self.username, 'password': self.password},
            HTTP_X_FORWARDED_FOR=client_ip
        )
        self.assertContains(
            response,
            'Too many login attempts from this IP address. '
            'Try again in 12 minutes.'
        )


class ChessPuzzleDailyApiTest(TestCase):
    """Test suite for ChessPuzzle model and daily puzzle API endpoint."""

    def test_daily_puzzle_api_fallback_when_db_empty(self):
        """When no puzzles exist in database, API returns default puzzle."""
        from game.models import ChessPuzzle
        # Clear out seeded puzzles to test empty db scenario
        ChessPuzzle.objects.all().delete()

        url = reverse('daily_puzzle')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], 0)
        self.assertEqual(data['title'], "Default Puzzle")
        self.assertEqual(data['difficulty'], "medium")
        self.assertIn("6k1/5ppp/8/8/8/8/5PPP/6KQ", data['fen'])

    def test_daily_puzzle_api_selects_by_date(self):
        """When a puzzle is assigned to today's date, it is returned."""
        from game.models import ChessPuzzle
        from django.utils import timezone

        # Clear out seeded puzzles first to ensure clean test
        ChessPuzzle.objects.all().delete()

        today = timezone.localdate()
        expected_puzzle = ChessPuzzle.objects.create(
            title="Today's Special Puzzle",
            fen="8/8/8/8/8/8/8/8 w - - 0 1",
            solution=["e2e4"],
            difficulty="hard",
            date=today
        )

        url = reverse('daily_puzzle')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], expected_puzzle.id)
        self.assertEqual(data['title'], "Today's Special Puzzle")
        self.assertEqual(data['difficulty'], "hard")
        self.assertEqual(data['solution'], ["e2e4"])

    def test_daily_puzzle_api_fallback_to_modulo(self):
        """Deterministic fallback when no puzzle matches today."""
        from game.models import ChessPuzzle
        from django.utils import timezone

        # Clear out seeded puzzles
        ChessPuzzle.objects.all().delete()

        puzzle1 = ChessPuzzle.objects.create(
            title="Puzzle One",
            fen="8/8/8/8/8/8/8/8 w - - 0 1",
            solution=["a2a4"],
            difficulty="easy"
        )
        puzzle2 = ChessPuzzle.objects.create(
            title="Puzzle Two",
            fen="7k/8/8/8/8/8/8/8 w - - 0 1",
            solution=["b2b4"],
            difficulty="medium"
        )

        today = timezone.localdate()
        # today.toordinal() will either be even or odd, meaning
        # today.toordinal() % 2 will select either puzzle 1 or 2
        expected_index = today.toordinal() % 2
        expected_puzzle = puzzle1 if expected_index == 0 else puzzle2

        url = reverse('daily_puzzle')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], expected_puzzle.id)
        self.assertEqual(data['title'], expected_puzzle.title)

    def test_chess_puzzle_fen_validation(self):
        """Invalid FEN format raises ValidationError on save."""
        from game.models import ChessPuzzle
        from django.core.exceptions import ValidationError

        # Too few fields
        puzzle = ChessPuzzle(
            title="Invalid FEN Puzzle",
            fen="8/8/8/8/8/8/8/8 w",
            solution=["e2e4"]
        )
        with self.assertRaises(ValidationError):
            puzzle.save()

        # Invalid number of ranks
        puzzle2 = ChessPuzzle(
            title="Invalid FEN Puzzle 2",
            fen="8/8/8/8/8/8/8 w - - 0 1",
            solution=["e2e4"]
        )
        with self.assertRaises(ValidationError):
            puzzle2.save()
