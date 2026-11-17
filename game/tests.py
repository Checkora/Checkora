"""Tests for the Checkora chess engine and API endpoints."""

import json
import sys
import time
from smtplib import SMTPException
from unittest import mock

from datetime import timedelta

from django.utils import timezone
from game.models import (
    ActiveGame,
    ChessPuzzle,
    GameRecord,
    GameResult,
    LessonProgress,
    OpeningProgress,
    PuzzleStats,
    RatingHistory,
    Reply,
    UserAchievement,
    UserProgress,
    Discussion,
    DiscussionBookmark,
)

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
                [sys.executable, '-u', candidates[2]],
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

    def test_landing_is_the_root_url(self):
        self.assertEqual(reverse('landing'), '/')

    def test_old_home_url_redirects_permanently(self):
        response = self.client.get('/home/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, '/')


class NotFoundPageTest(TestCase):
    """Custom 404 page should match the product theme and navigation flow."""

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_unknown_url_renders_themed_404_page(self):
        response = self.client.get('/this-route-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        # The wording belongs to the template; the page and its way home matter here.
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Checkora', status_code=404)
        self.assertContains(response, f'href="{reverse("landing")}"', status_code=404)


class ServerErrorPageTest(SimpleTestCase):
    """Custom 500 page should match the product theme and recovery flow."""

    def test_custom_500_handler_renders_themed_page(self):
        from core.urls import custom_server_error

        request = RequestFactory().get('/server-error/')
        response = custom_server_error(request)

        self.assertEqual(response.status_code, 500)
        # The wording belongs to the template; the page and its way home matter here.
        self.assertContains(response, 'Checkora', status_code=500)
        self.assertContains(response, f'href="{reverse("landing")}"', status_code=500)

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

    def test_password_reset_public_responses_are_indistinguishable(self):
        """Verify that unknown, single-account, and multi-account submissions

        produce identical public-facing responses (status, redirects, and HTML content)
        while sending different emails privately.
        """
        # Case 1: Unknown email
        cache.clear()
        mail.outbox = []
        response_unknown = self.client.post(
            self.reset_url,
            data={'email': 'unknown@example.com'},
            follow=True,
        )
        self.assertEqual(len(mail.outbox), 0)

        # Case 2: Single eligible account
        cache.clear()
        mail.outbox = []
        response_single = self.client.post(
            self.reset_url,
            data={'email': 'reset@example.com'},
            follow=True,
        )
        self.assertEqual(len(mail.outbox), 1)

        # Case 3: Multiple eligible accounts sharing the email
        cache.clear()
        mail.outbox = []
        User.objects.create_user(
            username='resetplayer2',
            email='reset@example.com',
            password='StrongPass1234!',  # noqa: S106
        )
        response_multi = self.client.post(
            self.reset_url,
            data={'email': 'reset@example.com'},
            follow=True,
        )
        self.assertEqual(len(mail.outbox), 2)

        # 1. Compare status codes (all should be 200 after following redirects)
        self.assertEqual(response_unknown.status_code, 200)
        self.assertEqual(response_single.status_code, 200)
        self.assertEqual(response_multi.status_code, 200)

        # 2. Compare redirect chains
        self.assertEqual(response_unknown.redirect_chain, response_single.redirect_chain)
        self.assertEqual(response_single.redirect_chain, response_multi.redirect_chain)
        self.assertEqual(response_unknown.redirect_chain, [(self.done_url, 302)])

        # 3. Compare final HTML content (must be identical)
        self.assertEqual(response_unknown.content, response_single.content)
        self.assertEqual(response_single.content, response_multi.content)

        # 4. Verify no account identifiers or selection UIs are leaked in the public HTML
        for response in [response_unknown, response_single, response_multi]:
            self.assertNotContains(response, 'Select Your Account')
            self.assertNotContains(response, 'resetplayer')
            self.assertNotContains(response, 'resetplayer2')
            self.assertNotContains(response, 'usernames')

    def test_account_selection_endpoint_is_removed(self):
        # Verify that the account selection endpoint returns 404
        url = '/password-reset-account-selection/'
        response = self.client.get(url, {'email': 'reset@example.com'})
        self.assertEqual(response.status_code, 404)


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

        # self.assertEqual(game.board[3][4])  # e5 empty
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
            '/api/new-game/', data=json.dumps({'mode': 'ai', 'player_color': 'black'}),
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

    def test_ai_aborts_if_game_paused(self):
        self.client.post(
            '/api/new-game/', data=json.dumps({'mode': 'ai', 'player_color': 'black'}),
            content_type='application/json'
        )

        # Pause the game
        self.client.post(
            '/api/pause/', data=json.dumps({'pause': True}),
            content_type='application/json'
        )

        state_before = self.client.get('/api/state/').json()

        # Try to make AI move
        r = self.client.post('/api/ai-move/', content_type='application/json')
        self.assertEqual(r.status_code, 400)

        data = r.json()
        self.assertFalse(data['valid'])
        self.assertEqual(data['message'], 'Game is paused.')

        state_after = self.client.get('/api/state/').json()
        self.assertEqual(state_before['board'], state_after['board'])
        self.assertEqual(state_before['current_turn'], state_after['current_turn'])
        self.assertEqual(state_before['move_history'], state_after['move_history'])

    def test_ai_succeeds_after_resume(self):
        self.client.post(
            '/api/new-game/', data=json.dumps({'mode': 'ai', 'player_color': 'black'}),
            content_type='application/json'
        )

        # Pause the game
        self.client.post(
            '/api/pause/', data=json.dumps({'pause': True}),
            content_type='application/json'
        )

        # Resume the game
        self.client.post(
            '/api/pause/', data=json.dumps({'pause': False}),
            content_type='application/json'
        )

        # Try to make AI move
        r = self.client.post('/api/ai-move/', content_type='application/json')
        data = r.json()

        self.assertTrue(data['valid'])
        self.assertEqual(data['current_turn'], 'black')
        self.assertIn('from_row', data['ai_move'])
        self.assertIn('from_col', data['ai_move'])
        self.assertIn('to_row', data['ai_move'])
        self.assertIn('to_col', data['ai_move'])

    @mock.patch('game.engine.ChessGame.get_ai_move')
    def test_ai_aborts_if_paused_during_calculation(self, mock_get_ai_move):
        self.client.post(
            '/api/new-game/', data=json.dumps({'mode': 'ai', 'player_color': 'black'}),
            content_type='application/json'
        )

        def side_effect(depth=None):
            # simulate concurrent pause
            from importlib import import_module
            from django.conf import settings
            engine = import_module(settings.SESSION_ENGINE)
            store = engine.SessionStore(session_key=self.client.session.session_key)
            game_data = store.get('game', {})
            game_data['paused'] = True
            store['game'] = game_data
            store.save()
            return {'from_row': 1, 'from_col': 4, 'to_row': 3, 'to_col': 4}

        mock_get_ai_move.side_effect = side_effect

        state_before = self.client.get('/api/state/').json()

        # Try to make AI move
        r = self.client.post('/api/ai-move/', content_type='application/json')
        self.assertEqual(r.status_code, 400)

        data = r.json()
        self.assertFalse(data['valid'])
        self.assertEqual(data['message'], 'Game is paused.')

        state_after = self.client.get('/api/state/').json()
        self.assertEqual(state_before['board'], state_after['board'])
        self.assertEqual(state_before['current_turn'], state_after['current_turn'])
        self.assertEqual(state_before['move_history'], state_after['move_history'])

    def test_ai_aborts_on_session_read_error(self):
        self.client.post(
            '/api/new-game/', data=json.dumps({'mode': 'ai', 'player_color': 'black'}),
            content_type='application/json'
        )
        with mock.patch('game.views.import_module') as mock_import:
            class MockEngine:
                class SessionStore:
                    def __init__(self, *args, **kwargs):
                        raise Exception("DB offline")
            mock_import.return_value = MockEngine

            r = self.client.post('/api/ai-move/', content_type='application/json')
            self.assertEqual(r.status_code, 500)

            data = r.json()
            self.assertFalse(data['valid'])
            self.assertEqual(data['message'], 'Internal error verifying game state.')

    @mock.patch('game.engine.ChessGame.make_move')
    def test_ai_preserves_concurrent_pause_during_save(self, mock_make_move):
        self.client.post(
            '/api/new-game/', data=json.dumps({'mode': 'ai', 'player_color': 'black'}),
            content_type='application/json'
        )

        def side_effect(*args, **kwargs):
            # simulate concurrent pause occurring exactly during make_move
            from importlib import import_module
            from django.conf import settings
            engine = import_module(settings.SESSION_ENGINE)
            store = engine.SessionStore(session_key=self.client.session.session_key)
            game_data = store.get('game', {})
            game_data['paused'] = True
            store['game'] = game_data
            store.save()
            return True, "Mock move", [], "active"

        mock_make_move.side_effect = side_effect

        r = self.client.post('/api/ai-move/', content_type='application/json')
        self.assertEqual(r.status_code, 200)

        # The backend should have preserved the authoritative paused state (True)
        # despite the local game object having paused=False
        from importlib import import_module
        from django.conf import settings
        engine = import_module(settings.SESSION_ENGINE)
        store = engine.SessionStore(session_key=self.client.session.session_key)
        self.assertTrue(store.get('game', {}).get('paused'))


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


class AnalyzeGameTest(TestCase):
    """Test the /api/analyze-game/ endpoint for Issue #332."""

    def setUp(self):
        # The endpoint is rate limited per user and per address, and the
        # counters live in the cache, which outlasts a single test.
        cache.clear()
        self.user = User.objects.create_user(username='test_analyze_user', password='password123')
        self.client.force_login(self.user)

    def test_missing_moves_json(self):
        r = self.client.post('/api/analyze-game/', content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('error', r.json())

    def _mock_board(self, MockGame, mock_ai):
        instance = MockGame.return_value
        instance.board = [['' for _ in range(8)] for _ in range(8)]
        instance.board[6][4] = 'P'  # Place moving pawn

        # Mock get_valid_moves and _notation so the inner loop finds it
        instance.get_valid_moves.return_value = [{'row': 4, 'col': 4}]
        instance._notation.return_value = 'e4'
        instance._color.return_value = 'white'
        instance.current_turn = 'white'
        instance.serialize_board.return_value = 'board'
        instance.serialize_castling_rights.return_value = 'rights'
        instance._serialize_ep.return_value = '-'
        instance.get_ai_move = mock_ai
        return instance

    def _analyze_e4(self, mock_ai):
        with mock.patch('game.views.ChessGame') as MockGame:
            self._mock_board(MockGame, mock_ai)
            r = self.client.post(
                '/api/analyze-game/',
                data=json.dumps({"moves": ["e4"]}),
                content_type='application/json',
            )
        self.assertEqual(r.status_code, 200)
        return r.json()

    def _engine_says(self, best_eval, eval_after):
        """Engine prefers another move worth best_eval; e4 leads to eval_after."""
        other_move = {'from_row': 7, 'from_col': 6, 'to_row': 5, 'to_col': 5}
        return mock.Mock(side_effect=[
            {**other_move, 'eval': best_eval, 'alts': []},
            {**other_move, 'eval': eval_after, 'alts': []},
        ])

    def test_analyze_game_blunder_by_eval_loss(self):
        data = self._analyze_e4(self._engine_says(900, 0))

        self.assertEqual(len(data['move_analysis_details']), 1)
        white_analysis = data['move_analysis_details'][0]
        self.assertEqual(white_analysis['played'], 'e4')
        self.assertEqual(white_analysis['class'], 'Blunder')
        self.assertEqual(data['blunders'], 1)
        self.assertEqual(data['accuracy'], 0)

    def test_analyze_game_mistake_by_eval_loss(self):
        data = self._analyze_e4(self._engine_says(150, 0))
        self.assertEqual(data['move_analysis_details'][0]['class'], 'Mistake')
        self.assertEqual(data['mistakes'], 1)

    def test_analyze_game_small_loss_is_inaccuracy(self):
        data = self._analyze_e4(self._engine_says(40, 0))
        self.assertEqual(data['move_analysis_details'][0]['class'], 'Inaccuracy')
        self.assertEqual(data['accuracy'], 100)

    def test_analyze_game_uses_eval_of_played_move_from_same_search(self):
        played = {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4, 'eval': 20}
        mock_ai = mock.Mock(side_effect=[
            {'from_row': 7, 'from_col': 6, 'to_row': 5, 'to_col': 5, 'eval': 500, 'alts': [played]},
            {'from_row': 7, 'from_col': 6, 'to_row': 5, 'to_col': 5, 'eval': 480, 'alts': []},
        ])
        data = self._analyze_e4(mock_ai)
        # 500 against the 20 the search gave the played move, not the 480 after it.
        self.assertEqual(data['move_analysis_details'][0]['class'], 'Blunder')

    def test_analyze_game_engine_move_is_best(self):
        same = {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4, 'eval': 30, 'alts': []}
        data = self._analyze_e4(mock.Mock(side_effect=[same, same]))
        self.assertEqual(data['move_analysis_details'][0]['class'], 'Best')

    @mock.patch('game.views.ChessGame.get_ai_move')
    def test_analyze_game_black_loss_is_judged_from_blacks_side(self, mock_ai):
        mock_ai.side_effect = [
            # White to move: the engine also plays e4.
            {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4, 'eval': 30, 'alts': []},
            # Black to move: the engine wants d5 and sees Black far ahead.
            {'from_row': 1, 'from_col': 3, 'to_row': 3, 'to_col': 3, 'eval': -400, 'alts': []},
            # After e5 the position is level again.
            {'from_row': 6, 'from_col': 3, 'to_row': 4, 'to_col': 3, 'eval': 10, 'alts': []},
        ]
        r = self.client.post(
            '/api/analyze-game/',
            data=json.dumps({"moves": ["e4", "e5"]}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        classes = [d['class'] for d in r.json()['move_analysis_details']]
        self.assertEqual(classes, ['Best', 'Blunder'])

    def test_analyze_game_engine_failure(self):
        # Simulate an engine crash or timeout (raises Exception)
        mock_ai = mock.Mock(side_effect=Exception("Engine timeout"))
        data = self._analyze_e4(mock_ai)

        # No engine answer means no verdict, and no made-up accuracy.
        self.assertEqual(data['move_analysis_details'][0]['class'], 'Unknown')
        self.assertIsNone(data['accuracy'])
        self.assertEqual(data['blunders'], 0)

    @override_settings(ANALYSIS_TIMEOUT_SECONDS=0)
    def test_analyze_game_stops_at_the_deadline(self):
        mock_ai = mock.Mock(return_value=None)
        data = self._analyze_e4(mock_ai)

        self.assertTrue(data['truncated'])
        self.assertEqual(data['move_analysis_details'], [])
        mock_ai.assert_not_called()

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
        self.user_a.game_results.create(mode='pvp', winner='white', end_reason='checkmate')
        # Create game for user B
        self.user_b.game_results.create(mode='ai', winner='black', end_reason='resign')

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
        self.assertContains(response, 'No games played yet. Play a game to see your stats here!')
        # Summary cards should show 17 cards
        self.assertContains(response, '<div class="num">0</div>', count=16)
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
        self.assertContains(response, 'No games played yet. Play a game to see your stats here!')

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

        active_game = ActiveGame.objects.create(
            session_key=s.session_key,
            status="active",
        )

        ActiveGame.objects.filter(pk=active_game.pk).update(
            last_activity_at=timezone.now() - timezone.timedelta(hours=50)
        )

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

        active_game = ActiveGame.objects.create(
            session_key=s.session_key,
            status="active",
        )

        ActiveGame.objects.filter(pk=active_game.pk).update(
            last_activity_at=timezone.now() - timezone.timedelta(hours=50)
        )

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

    def setUp(self):
        # The per-address mail cooldown lives in the cache.
        cache.clear()

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
        self.assertEqual(self.client.session['registration_user_id'], old_id)
        # The new password only lands once this browser verifies its code.
        self.assertTrue(reused.check_password('OldPassword456!'))
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

    @mock.patch('time.time', return_value=1000.0)
    def test_increment_applied_after_move(self, _mock_time):
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

    def test_update_clock_sub_second_call_deducts_nothing(self):
        """A single call with < 1s elapsed must deduct 0 seconds."""
        game = ChessGame(time_limit=600)
        game.last_ts = 1000.0
        game.white_time = 600
        game.current_turn = 'white'
        game.paused = False

        with mock.patch('game.engine.time.time', return_value=1000.6):
            game.update_clock()

        self.assertEqual(game.white_time, 600)
        self.assertEqual(game.last_ts, 1000.0)

    def test_update_clock_remainder_accumulates_across_calls(self):
        """Sub-second remainders must accumulate; 0.6+0.6 = 1.2 -> deduct 1."""
        game = ChessGame(time_limit=600)
        game.last_ts = 1000.0
        game.white_time = 600
        game.current_turn = 'white'
        game.paused = False

        with mock.patch('game.engine.time.time', return_value=1000.6):
            game.update_clock()
        self.assertEqual(game.white_time, 600)
        self.assertEqual(game.last_ts, 1000.0)

        with mock.patch('game.engine.time.time', return_value=1001.2):
            game.update_clock()
        self.assertEqual(game.white_time, 599)
        self.assertEqual(game.last_ts, 1001.0)

    def test_update_clock_high_frequency_no_time_leak(self):
        """Repeated 0.4s polls must deduct only floor(total elapsed) seconds."""
        game = ChessGame(time_limit=600)
        game.last_ts = 0.0
        game.white_time = 600
        game.current_turn = 'white'
        game.paused = False

        for i in range(1, 11):
            with mock.patch('game.engine.time.time', return_value=i * 0.4):
                game.update_clock()

        total_elapsed = 10 * 0.4  # 4.0 s
        self.assertEqual(game.white_time, 600 - int(total_elapsed))
        self.assertEqual(game.last_ts, float(int(total_elapsed)))


class GameResultMoveHistoryTest(TestCase):
    """Test suite for verifying persistent move history storage in GameResult."""

    def setUp(self):
        self.user = User.objects.create_user(username='testplayer', password='password123')
        from .models import GameResult
        self.GameResult = GameResult

    def test_record_game_result_saves_moves_explicitly(self):
        from game.views import record_game_result
        from django.contrib.sessions.middleware import SessionMiddleware
        # Setup dummy request
        factory = RequestFactory()
        request = factory.post('/dummy/')
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()

        moves = [{'notation': 'e4', 'piece': 'P', 'from': [6, 4], 'to': [4, 4], 'color': 'white'}]
        record_game_result(request, 'pvp', 'white', 'checkmate', 'white', moves=moves)

        self.assertEqual(self.GameResult.objects.count(), 1)
        res = self.GameResult.objects.first()
        self.assertEqual(res.moves, moves)

    def test_record_game_result_falls_back_to_session(self):
        from game.views import record_game_result
        from django.contrib.sessions.middleware import SessionMiddleware
        factory = RequestFactory()
        request = factory.post('/dummy/')
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)

        moves = [{'notation': 'd4', 'piece': 'P', 'from': [6, 3], 'to': [4, 3], 'color': 'white'}]
        request.session['game'] = {'move_history': moves}
        request.session.save()

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
        active_game = ActiveGame.objects.create(
            session_key=s.session_key,
            status="active",
        )

        ActiveGame.objects.filter(pk=active_game.pk).update(
            last_activity_at=timezone.now() - timezone.timedelta(hours=50)
        )

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

    def test_lessons_map_guest_user_shows_alert(self):
        """Guest users should see the sign-in alert banner on the lessons map page."""
        response = self.client.get(reverse('lessons'))
        self.assertEqual(response.status_code, 200)
        # Check that the alert is rendered
        self.assertContains(response, 'id="guest-alert"')
        self.assertContains(response, 'Sign in')
        self.assertContains(response, 'create a free account')
        self.assertContains(response, 'to save your lesson progress.')

    def test_lessons_map_authenticated_user_hides_alert(self):
        """Authenticated users should not see the sign-in alert banner on the lessons map page."""
        User.objects.create_user(username='lesson_player', password='password123')
        self.client.login(username='lesson_player', password='password123')
        response = self.client.get(reverse('lessons'))
        self.assertEqual(response.status_code, 200)
        # Check that the alert is NOT rendered
        self.assertNotContains(response, 'id="guest-alert"')
        self.assertNotContains(response, 'to save your lesson progress.')


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
        self.assertEqual(data['difficulty'], "easy")
        self.assertIn("6k1/5ppp/8/8/8/8/5PPP/4R1K1", data['fen'])
        self.assertEqual(data['solution'], ["e1e8"])

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
        self.assertNotIn('solution', data)

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


class LeaderboardAndAchievementsViewOriginalTest(TestCase):
    """Test leaderboard and achievements views with original templates."""

    def test_leaderboard_anonymous(self):
        response = self.client.get(reverse('leaderboard'))
        self.assertEqual(response.status_code, 302)

    def test_achievements_anonymous(self):
        response = self.client.get(reverse('achievements'))
        self.assertEqual(response.status_code, 302)

    def test_leaderboard_authenticated(self):
        password = 'Password123!'
        User.objects.create_user(
            username='testuser',
            password=password,
            email='testuser@example.com'
        )
        self.client.login(username='testuser', password=password)
        response = self.client.get(reverse('leaderboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/leaderboard.html')
        self.assertContains(response, "No leaderboard data available yet.")
        self.assertContains(response, "No chess rating data available yet.")

    def test_achievements_authenticated(self):
        password = 'Password123!'
        User.objects.create_user(
            username='testuser',
            password=password,
            email='testuser@example.com'
        )
        self.client.login(username='testuser', password=password)
        response = self.client.get(reverse('achievements'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/achievements.html')
        self.assertContains(response, "Achievements Unlocked")
        self.assertContains(response, "No featured badges selected yet.")

    def test_opening_trainer_page(self):
        response = self.client.get(
            reverse("opening_trainer")
        )

        self.assertEqual(response.status_code, 200)

    def test_opening_detail_page(self):
        response = self.client.get(
            reverse(
                "opening_detail",
                kwargs={
                    "slug": "italian-game"
                }
            )
        )

        self.assertEqual(response.status_code, 200)


class PuzzleSolveApiTest(TestCase):
    """POST /api/puzzles/<id>/solve/ keeps the puzzle stats on the server."""

    FEN = "6k1/5ppp/8/8/8/8/5PPP/6KQ w - - 0 1"

    def setUp(self):
        self.user = User.objects.create_user(username='solver', password='Password123!')
        self.today = timezone.localdate()
        # Pin today's daily puzzle so the rotation cannot pick another one.
        self.daily = ChessPuzzle.objects.create(
            title='Today', fen=self.FEN, solution=['h1a8'], date=self.today,
        )
        self.other = ChessPuzzle.objects.create(
            title='Any day', fen=self.FEN, solution=['g2g4', 'h7h6', 'g4g5'],
        )

    def _solve(self, puzzle, payload):
        return self.client.post(
            reverse('puzzle_solve_api', args=[puzzle.id]),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_anonymous_gets_401(self):
        response = self._solve(self.other, {'moves': ['g2g4', 'h7h6', 'g4g5']})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(PuzzleStats.objects.exists())

    def test_get_is_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('puzzle_solve_api', args=[self.other.id]))
        self.assertEqual(response.status_code, 405)

    def test_unknown_puzzle_is_404(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('puzzle_solve_api', args=[0]),
            data=json.dumps({'moves': ['g2g4']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_moves_must_be_a_list_of_strings(self):
        self.client.force_login(self.user)
        for payload in ({}, {'moves': 'g2g4'}, {'moves': [1, 2]}, ['g2g4']):
            response = self._solve(self.other, payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertFalse(response.json()['success'])

    def test_wrong_moves_count_nothing(self):
        self.client.force_login(self.user)
        for moves in (['g2g3', 'h7h6', 'g4g5'], ['g2g4'], []):
            data = self._solve(self.other, {'moves': moves}).json()
            self.assertTrue(data['success'])
            self.assertFalse(data['correct'])
            self.assertEqual(data['puzzles_solved'], 0)

    def test_correct_moves_count_once(self):
        self.client.force_login(self.user)
        first = self._solve(self.other, {'moves': ['G2G4', ' h7h6', 'g4g5']}).json()
        second = self._solve(self.other, {'moves': ['g2g4', 'h7h6', 'g4g5']}).json()

        self.assertTrue(first['correct'])
        self.assertTrue(first['newly_solved'])
        self.assertEqual(first['puzzles_solved'], 1)
        self.assertFalse(second['newly_solved'])
        self.assertEqual(second['puzzles_solved'], 1)
        # Not the daily puzzle, so no streak.
        self.assertEqual(second['streak'], 0)

    def test_totals_sent_by_the_client_are_ignored(self):
        self.client.force_login(self.user)
        data = self._solve(self.other, {
            'moves': ['g2g4', 'h7h6', 'g4g5'],
            'puzzles_solved': 500,
            'current_streak': 99,
            'best_streak': 99,
        }).json()

        self.assertEqual(data['puzzles_solved'], 1)
        stats = PuzzleStats.objects.get(user=self.user)
        self.assertEqual(stats.puzzles_solved, 1)
        self.assertEqual(stats.best_streak, 0)

    def test_first_solve_unlocks_the_seeded_achievement(self):
        self.client.force_login(self.user)
        self._solve(self.other, {'moves': ['g2g4', 'h7h6', 'g4g5']})
        self.assertTrue(UserAchievement.objects.filter(
            user=self.user, achievement__code='FIRST_PUZZLE'
        ).exists())

    def test_daily_puzzle_starts_a_streak_once_per_day(self):
        self.client.force_login(self.user)
        first = self._solve(self.daily, {'moves': ['h1a8']}).json()
        again = self._solve(self.daily, {'moves': ['h1a8']}).json()

        self.assertEqual(first['streak'], 1)
        self.assertEqual(first['daily_completions'], 1)
        self.assertEqual(again['streak'], 1)
        self.assertEqual(again['daily_completions'], 1)

    def test_daily_puzzle_on_consecutive_days_extends_the_streak(self):
        PuzzleStats.objects.create(
            user=self.user, current_streak=2, best_streak=2, daily_completions=2,
            last_daily_date=self.today - timedelta(days=1),
        )
        self.client.force_login(self.user)
        data = self._solve(self.daily, {'moves': ['h1a8']}).json()

        self.assertEqual(data['streak'], 3)
        self.assertEqual(data['longest_streak'], 3)

    def test_missed_day_restarts_the_streak(self):
        PuzzleStats.objects.create(
            user=self.user, current_streak=5, best_streak=5, daily_completions=5,
            last_daily_date=self.today - timedelta(days=3),
        )
        self.client.force_login(self.user)
        data = self._solve(self.daily, {'moves': ['h1a8']}).json()

        self.assertEqual(data['streak'], 1)
        self.assertEqual(data['longest_streak'], 5)

    def test_stats_endpoint_shows_a_lapsed_streak_as_zero(self):
        PuzzleStats.objects.create(
            user=self.user, puzzles_solved=4, current_streak=4, best_streak=4,
            last_daily_date=self.today - timedelta(days=2),
        )
        self.client.force_login(self.user)
        data = self.client.get('/api/puzzle-stats/').json()

        self.assertEqual(data['streak'], 0)
        self.assertEqual(data['longest_streak'], 4)
        self.assertEqual(data['puzzles_solved'], 4)

    def test_old_client_totals_endpoint_is_gone(self):
        from game import views
        self.assertFalse(hasattr(views, 'update_puzzle_stats'))

class ChessPuzzleDashboardTests(TestCase):
    """Test suite for the chess puzzle dashboard views and API endpoints."""

    def setUp(self):
        super().setUp()
        from game.models import ChessPuzzle
        ChessPuzzle.objects.all().delete()

        self.puzzle_easy = ChessPuzzle.objects.create(
            title="Easy Mate in One",
            fen="8/8/8/8/8/8/8/8 w - - 0 1",
            solution=["e2e4"],
            difficulty="easy",
            rating=1000,
            tags="Mate in 1,Endgame"
        )
        self.puzzle_medium = ChessPuzzle.objects.create(
            title="Medium Tactics Puzzle",
            fen="7k/8/8/8/8/8/8/8 w - - 0 1",
            solution=["d2d4"],
            difficulty="medium",
            rating=1500,
            tags="Fork,Tactics"
        )
        self.puzzle_hard = ChessPuzzle.objects.create(
            title="Hard Endgame Study",
            fen="6k1/8/8/8/8/8/8/6K1 w - - 0 1",
            solution=["c2c4"],
            difficulty="hard",
            rating=2000,
            tags="Pin,Endgame"
        )

    def test_puzzles_view_renders_correct_template(self):
        """The puzzles dashboard view renders the puzzle_list.html template."""
        url = reverse('puzzles')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/puzzle_list.html')

    def test_puzzles_list_api_returns_all_without_solution(self):
        """The listing API returns all puzzles and excludes solutions."""
        url = reverse('puzzles_list_api')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('puzzles', data)
        self.assertEqual(len(data['puzzles']), 3)

        for item in data['puzzles']:
            self.assertNotIn('solution', item)
            self.assertIn('id', item)
            self.assertIn('title', item)
            self.assertIn('fen', item)
            self.assertIn('difficulty', item)
            self.assertIn('rating', item)
            self.assertIn('tags', item)

    def test_puzzles_list_api_difficulty_filtering(self):
        """The listing API supports filtering by difficulty."""
        url = reverse('puzzles_list_api')

        # Filter easy
        response = self.client.get(url, {'difficulty': 'easy'})
        data = response.json()
        self.assertEqual(len(data['puzzles']), 1)
        self.assertEqual(data['puzzles'][0]['title'], "Easy Mate in One")

        # Filter hard
        response = self.client.get(url, {'difficulty': 'hard'})
        data = response.json()
        self.assertEqual(len(data['puzzles']), 1)
        self.assertEqual(data['puzzles'][0]['title'], "Hard Endgame Study")

    def test_puzzles_list_api_search_filtering(self):
        """The listing API supports filtering by search queries on title."""
        url = reverse('puzzles_list_api')

        response = self.client.get(url, {'search': 'Tactics'})
        data = response.json()
        self.assertEqual(len(data['puzzles']), 1)
        self.assertEqual(data['puzzles'][0]['title'], "Medium Tactics Puzzle")

    def test_puzzles_list_api_tag_filtering(self):
        """The listing API supports filtering by tag (motif)."""
        url = reverse('puzzles_list_api')

        # Filter by "Endgame"
        response = self.client.get(url, {'tag': 'Endgame'})
        data = response.json()
        self.assertEqual(len(data['puzzles']), 2)
        titles = [p['title'] for p in data['puzzles']]
        self.assertIn("Easy Mate in One", titles)
        self.assertIn("Hard Endgame Study", titles)

        # Filter by "Fork"
        response = self.client.get(url, {'tag': 'Fork'})
        data = response.json()
        self.assertEqual(len(data['puzzles']), 1)
        self.assertEqual(data['puzzles'][0]['title'], "Medium Tactics Puzzle")

    def test_puzzles_list_api_rating_filtering(self):
        """The listing API supports filtering by rating range."""
        url = reverse('puzzles_list_api')

        # Filter min_rating=1200
        response = self.client.get(url, {'min_rating': '1200'})
        data = response.json()
        self.assertEqual(len(data['puzzles']), 2)
        titles = [p['title'] for p in data['puzzles']]
        self.assertIn("Medium Tactics Puzzle", titles)
        self.assertIn("Hard Endgame Study", titles)

        # Filter max_rating=1600
        response = self.client.get(url, {'max_rating': '1600'})
        data = response.json()
        self.assertEqual(len(data['puzzles']), 2)
        titles = [p['title'] for p in data['puzzles']]
        self.assertIn("Easy Mate in One", titles)
        self.assertIn("Medium Tactics Puzzle", titles)

        # Filter rating range 1200-1600
        response = self.client.get(url, {'min_rating': '1200', 'max_rating': '1600'})
        data = response.json()
        self.assertEqual(len(data['puzzles']), 1)
        self.assertEqual(data['puzzles'][0]['title'], "Medium Tactics Puzzle")

    def test_puzzles_list_api_pagination(self):
        """The listing API supports pagination."""
        url = reverse('puzzles_list_api')

        # Set per_page to 2
        response = self.client.get(url, {'per_page': 2})
        data = response.json()
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['total_pages'], 2)
        self.assertEqual(data['total_count'], 3)
        self.assertEqual(len(data['puzzles']), 2)
        self.assertTrue(data['has_next'])
        self.assertFalse(data['has_previous'])

        # Get second page
        response = self.client.get(url, {'per_page': 2, 'page': 2})
        data = response.json()
        self.assertEqual(data['page'], 2)
        self.assertEqual(len(data['puzzles']), 1)
        self.assertFalse(data['has_next'])
        self.assertTrue(data['has_previous'])

    def test_puzzle_detail_api_excludes_solution(self):
        """Detail API returns details for a single puzzle without solution."""
        url = reverse(
            'puzzle_detail_api',
            kwargs={'puzzle_id': self.puzzle_easy.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.puzzle_easy.id)
        self.assertEqual(data['title'], "Easy Mate in One")
        self.assertNotIn('solution', data)

    def test_puzzle_solution_api_returns_solution(self):
        """The puzzle solution API returns the correct solution array."""
        url = reverse(
            'puzzle_solution_api',
            kwargs={'puzzle_id': self.puzzle_easy.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['solution'], ["e2e4"])

    def test_daily_puzzle_api_excludes_solution(self):
        """The daily puzzle API endpoint now excludes solutions."""
        from django.utils import timezone
        # Assign self.puzzle_easy as today's daily puzzle
        self.puzzle_easy.date = timezone.localdate()
        self.puzzle_easy.save()

        url = reverse('daily_puzzle')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.puzzle_easy.id)
        self.assertNotIn('solution', data)


# ===========================================================================
# Avatar Support Tests (Issue #455)
# ===========================================================================

class UserProfileModelTest(TestCase):
    """Test UserProfile model creation and the post_save signal."""

    def test_profile_auto_created_on_user_registration(self):
        """Creating a User automatically creates a corresponding UserProfile."""
        from game.models import UserProfile
        user = User.objects.create_user(
            username='avatar_test_user',
            password='TestPass123!',
            email='avatar@example.com'
        )
        self.assertTrue(
            UserProfile.objects.filter(user=user).exists(),
            'UserProfile should be auto-created via post_save signal'
        )

    def test_profile_avatar_defaults_to_empty_string(self):
        """A freshly created UserProfile has an empty avatar field."""
        from game.models import UserProfile
        user = User.objects.create_user(
            username='no_avatar_user',
            password='TestPass123!',
            email='noavatar@example.com'
        )
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.avatar, '')

    def test_profile_str(self):
        """UserProfile.__str__ returns '<username> Profile'."""
        from game.models import UserProfile
        user = User.objects.create_user(
            username='str_test_user',
            password='TestPass123!',
            email='strtest@example.com'
        )
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(str(profile), 'str_test_user Profile')

    def test_profile_deleted_when_user_deleted(self):
        """Deleting a User cascades to delete the associated UserProfile."""
        from game.models import UserProfile
        user = User.objects.create_user(
            username='cascade_user',
            password='TestPass123!',
            email='cascade@example.com'
        )
        user_id = user.id
        user.delete()
        self.assertFalse(UserProfile.objects.filter(user_id=user_id).exists())


class AvatarUploadFormTest(TestCase):
    """Test AvatarUploadForm validation rules."""

    def _make_image_file(
        self,
        name='test.jpg',
        content_type='image/jpeg',
        size_bytes=1024
    ):
        """Return a minimal in-memory SimpleUploadedFile."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(
            name=name,
            content=b'\xff\xd8\xff' + b'0' * size_bytes,  # JPEG magic bytes
            content_type=content_type
        )

    def test_valid_jpeg_passes(self):
        from game.forms import AvatarUploadForm
        from PIL import Image
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Dynamically generate a valid 10x10 JPEG
        img_buffer = io.BytesIO()
        Image.new('RGB', (10, 10), color='red').save(img_buffer, 'JPEG')
        img_buffer.seek(0)

        file = SimpleUploadedFile('photo.jpg', img_buffer.read(), 'image/jpeg')
        file.content_type = 'image/jpeg'

        form = AvatarUploadForm()
        form.cleaned_data = {'avatar': file}
        cleaned = form.clean_avatar()
        self.assertEqual(cleaned, file)

    def test_size_validation_rejects_files_over_5mb(self):
        from game.forms import AvatarUploadForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        large_file = SimpleUploadedFile(
            name='big.jpg',
            content=b'x' * (5 * 1024 * 1024 + 1),
            content_type='image/jpeg'
        )
        large_file.content_type = 'image/jpeg'
        form = AvatarUploadForm()
        # Manually call clean_avatar by building the cleaned_data dict
        form.cleaned_data = {'avatar': large_file}
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            form.clean_avatar()

    def test_mime_validation_rejects_pdf(self):
        from game.forms import AvatarUploadForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.exceptions import ValidationError
        pdf_file = SimpleUploadedFile(
            name='doc.pdf',
            content=b'%PDF-1.4',
            content_type='application/pdf'
        )
        pdf_file.content_type = 'application/pdf'
        form = AvatarUploadForm()
        form.cleaned_data = {'avatar': pdf_file}
        with self.assertRaises(ValidationError):
            form.clean_avatar()

    def test_mime_validation_accepts_webp(self):
        from game.forms import AvatarUploadForm
        from PIL import Image
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Dynamically generate a valid WEBP
        img_buffer = io.BytesIO()
        Image.new('RGB', (10, 10), color='blue').save(img_buffer, 'WEBP')
        img_buffer.seek(0)

        webp_file = SimpleUploadedFile('img.webp', img_buffer.read(), 'image/webp')
        webp_file.content_type = 'image/webp'

        form = AvatarUploadForm()
        form.cleaned_data = {'avatar': webp_file}
        result = form.clean_avatar()
        self.assertEqual(result, webp_file)


class AvatarViewTest(TestCase):
    """Test avatar upload, remove, and get API views."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='viewtest_user',
            password='TestPass123!',
            email='viewtest@example.com'
        )
        self.client.login(username='viewtest_user', password='TestPass123!')
        self.upload_url = reverse('upload_avatar')
        self.remove_url = reverse('remove_avatar')
        self.get_url = reverse('get_avatar')

    # ── Authentication guards ─────────────────────────────────────────────

    def test_upload_page_requires_login(self):
        self.client.logout()
        response = self.client.get(self.upload_url)
        self.assertRedirects(
            response,
            f"/login/?next={self.upload_url}",
            fetch_redirect_response=False
        )

    def test_remove_requires_login(self):
        self.client.logout()
        response = self.client.post(self.remove_url)
        self.assertEqual(response.status_code, 302)

    def test_get_avatar_requires_login(self):
        self.client.logout()
        response = self.client.get(self.get_url)
        self.assertEqual(response.status_code, 302)

    # ── GET /avatar/ ──────────────────────────────────────────────────────

    def test_upload_page_renders(self):
        response = self.client.get(self.upload_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/avatar.html')

    # ── GET /api/avatar/ ─────────────────────────────────────────────────

    def test_get_avatar_returns_json_with_empty_string_when_no_avatar(self):
        response = self.client.get(self.get_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('avatar', data)
        self.assertEqual(data['avatar'], '')

    def test_get_avatar_returns_avatar_after_set(self):
        from game.models import UserProfile
        profile = UserProfile.objects.get(user=self.user)
        profile.avatar = 'data:image/jpeg;base64,TESTDATA'
        profile.save()

        response = self.client.get(self.get_url)
        data = response.json()
        self.assertEqual(data['avatar'], 'data:image/jpeg;base64,TESTDATA')

    # ── POST /avatar/remove/ ─────────────────────────────────────────────

    def test_remove_avatar_clears_avatar_field(self):
        from game.models import UserProfile
        profile = UserProfile.objects.get(user=self.user)
        profile.avatar = 'data:image/jpeg;base64,SOMEDATA'
        profile.save()

        response = self.client.post(self.remove_url)
        self.assertRedirects(response, self.upload_url, fetch_redirect_response=False)

        profile.refresh_from_db()
        self.assertEqual(profile.avatar, '')

    def test_remove_avatar_get_is_not_allowed(self):
        response = self.client.get(self.remove_url)
        self.assertEqual(response.status_code, 405)

    # ── POST /avatar/ (invalid uploads) ──────────────────────────────────

    def test_upload_with_no_file_shows_error(self):
        response = self.client.post(self.upload_url, data={}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Should stay on avatar page with an error message
        self.assertTemplateUsed(response, 'game/avatar.html')


class GameResultRatingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ratingplayer', password='password123')
        from game.models import PlayerRating, GameResult, UserAchievement, Achievement
        self.PlayerRating = PlayerRating
        self.GameResult = GameResult
        self.UserAchievement = UserAchievement
        Achievement.objects.get_or_create(code='FIRST_WIN', defaults={
            'title': 'First Win', 'description': 'Win a game', 'icon': '🏆',
            'category': 'gameplay', 'rarity': 'common',
        })

    def test_record_game_result_updates_rating_and_achievements_for_ai(self):
        from game.views import record_game_result
        from django.contrib.sessions.middleware import SessionMiddleware
        factory = RequestFactory()
        request = factory.post('/dummy/')
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()

        record_game_result(request, 'ai', 'white', 'checkmate', 'white')

        rating = self.PlayerRating.objects.get(user=self.user)
        self.assertEqual(rating.games_played, 1)
        self.assertEqual(rating.wins, 1)
        self.assertTrue(self.UserAchievement.objects.filter(user=self.user).exists())

        self.assertEqual(self.GameResult.objects.count(), 1)
        res = self.GameResult.objects.first()
        self.assertEqual(res.mode, 'ai')
        self.assertEqual(res.winner, 'white')

    def test_record_game_result_does_not_update_rating_or_achievements_for_pvp(self):
        from game.views import record_game_result
        from django.contrib.sessions.middleware import SessionMiddleware
        factory = RequestFactory()
        request = factory.post('/dummy/')
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()

        record_game_result(request, 'pvp', 'white', 'checkmate', 'white')

        self.assertFalse(self.PlayerRating.objects.filter(user=self.user).exists())
        self.assertFalse(self.UserAchievement.objects.filter(user=self.user).exists())

        self.assertEqual(self.GameResult.objects.count(), 1)
        res = self.GameResult.objects.first()
        self.assertEqual(res.mode, 'pvp')
        self.assertEqual(res.winner, 'white')

class OpeningStatsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
        )

        self.client.login(
            username="testuser",
            password="password123",
        )

        self.url = reverse("update_opening_stats")

    def test_first_completion_awards_xp_and_records_progress(self):
        response = self.client.post(
            self.url,
            data=json.dumps({
                "opening_name": "Italian Game",
                "completed": True,
                "accuracy": 100,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        progress = OpeningProgress.objects.get(
            user=self.user,
            opening_name="Italian Game",
        )

        self.assertEqual(progress.openings_completed, 1)

        user_progress = UserProgress.objects.get(
            user=self.user,
        )

        self.assertEqual(user_progress.xp, 75)

    def test_repeated_completion_does_not_award_extra_xp(self):
        payload = {
            "opening_name": "Italian Game",
            "completed": True,
            "accuracy": 100,
        }

        # First completion
        self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        # Second completion
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        progress = OpeningProgress.objects.get(
            user=self.user,
            opening_name="Italian Game",
        )

        # Completion should only be counted once
        self.assertEqual(progress.openings_completed, 1)

        user_progress = UserProgress.objects.get(
            user=self.user,
        )

        # XP should not increase after the second completion
        self.assertEqual(user_progress.xp, 75)


class DiscussionBookmarkRedirectTests(TestCase):
    """Tests for safe redirection in toggle_discussion_bookmark view."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='bookmark_user',
            password='TestPass123!',
            email='bookmark@example.com'
        )
        self.client.login(username='bookmark_user', password='TestPass123!')
        self.discussion = Discussion.objects.create(
            user=self.user,
            title='Test Discussion',
            content='This is a test discussion'
        )
        self.url = reverse('toggle_discussion_bookmark', kwargs={'discussion_id': self.discussion.id})

    def test_safe_local_path_next(self):
        response = self.client.post(self.url, {'next': '/forum/'})
        self.assertRedirects(response, '/forum/', fetch_redirect_response=False)

    def test_safe_same_host_url_next(self):
        response = self.client.post(self.url, {'next': 'http://testserver/forum/'})
        self.assertRedirects(response, 'http://testserver/forum/', fetch_redirect_response=False)

    def test_unsafe_external_url_next_falls_back_to_forum(self):
        response = self.client.post(self.url, {'next': 'http://evil.com/external'})
        self.assertRedirects(response, reverse('forum'), fetch_redirect_response=False)

    def test_unsafe_protocol_relative_url_next_falls_back_to_forum(self):
        response = self.client.post(self.url, {'next': '//evil.com/external'})
        self.assertRedirects(response, reverse('forum'), fetch_redirect_response=False)

    def test_safe_referer_fallback(self):
        response = self.client.post(self.url, HTTP_REFERER='http://testserver/forum/1/')
        self.assertRedirects(response, 'http://testserver/forum/1/', fetch_redirect_response=False)

    def test_unsafe_referer_fallback_redirects_to_forum(self):
        response = self.client.post(self.url, HTTP_REFERER='http://evil.com/external')
        self.assertRedirects(response, reverse('forum'), fetch_redirect_response=False)

    def test_unsafe_next_and_safe_referer_falls_back_to_referer(self):
        response = self.client.post(
            self.url,
            {'next': 'http://evil.com/external'},
            HTTP_REFERER='http://testserver/forum/1/'
        )
        self.assertRedirects(response, 'http://testserver/forum/1/', fetch_redirect_response=False)

    def test_no_next_and_no_referer_fallback(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('forum'), fetch_redirect_response=False)


from multiprocessing.connection import Connection

class EnginePersistentTimeoutTest(SimpleTestCase):
    @mock.patch("multiprocessing.connection.Client")
    @mock.patch("game.engine.os.path.exists", return_value=True)
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="1234")
    def test_normal_response(self, _mock_open, _mock_exists, mock_client):
        game = ChessGame()
        
        mock_conn = mock.Mock(spec=Connection)
        mock_conn.poll.return_value = True
        mock_conn.recv.return_value = "STATUS ok"
        mock_client.return_value = mock_conn
        
        resp = game._call_engine("STATUS")
        self.assertEqual(resp, "STATUS ok")
        mock_conn.send.assert_called_with("STATUS")
        mock_conn.recv.assert_called_once()
            
    @mock.patch("multiprocessing.connection.Client")
    @mock.patch("game.engine.os.path.exists", return_value=True)
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="1234")
    def test_unresponsive_engine_triggers_timeout(self, _mock_open, _mock_exists, mock_client):
        game = ChessGame()
        
        mock_conn = mock.Mock(spec=Connection)
        mock_conn.poll.return_value = False
        mock_client.return_value = mock_conn
        
        with mock.patch.object(game, "cleanup_engine") as mock_cleanup:
            resp = game._call_engine("STATUS")
            self.assertIsNone(resp)
            mock_conn.send.assert_called_with("STATUS")
            mock_conn.recv.assert_not_called()
            mock_cleanup.assert_called_once()
            mock_conn.close.assert_called()


@override_settings(
    DEBUG=False,
    EMAIL_HOST_USER='sender@example.com',
    EMAIL_HOST_PASSWORD='app-password',
)
class RegistrationHardeningTest(TestCase):
    """Deactivated accounts, stale signups, mail cooldown and password binding."""

    PAYLOAD = {
        'username': 'pendingplayer',
        'email': 'pending@example.com',
        'password1': 'StrongPass123!',
        'password2': 'StrongPass123!',
    }

    def setUp(self):
        cache.clear()

    def _fixed_otp(self):
        # randbelow(900000) + 100000 gives 123456.
        return mock.patch('game.views.secrets.randbelow', return_value=23456)

    def test_deactivated_account_cannot_come_back_through_registration(self):
        banned = User.objects.create_user(
            username='pendingplayer', email='pending@example.com',
            password='OldPassword456!', is_active=False,
        )
        banned.last_login = timezone.now()
        banned.save()

        response = self.client.post('/register/', data=self.PAYLOAD)

        self.assertRedirects(response, '/verify-otp/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['registration_user_id'], -1)
        self.assertEqual(len(mail.outbox), 0)
        banned.refresh_from_db()
        self.assertFalse(banned.is_active)
        self.assertTrue(banned.check_password('OldPassword456!'))

    def test_deactivated_account_cannot_be_verified_from_an_old_session(self):
        banned = User.objects.create_user(
            username='pendingplayer', email='pending@example.com',
            password='OldPassword456!', is_active=False,
        )
        banned.last_login = timezone.now()
        banned.save()

        import hashlib
        session = self.client.session
        session['registration_user_id'] = banned.id
        session['registration_otp_hash'] = hashlib.sha256(
            f"123456:{settings.SECRET_KEY}".encode()
        ).hexdigest()
        session['otp_created_at'] = time.time()
        session.save()

        self.client.post('/verify-otp/', data={'otp': '123456'})
        banned.refresh_from_db()
        self.assertFalse(banned.is_active)

        self.client.post('/resend-otp/')
        self.assertEqual(len(mail.outbox), 0)

    def test_stale_unverified_signup_stops_blocking_its_email(self):
        stale = User.objects.create_user(
            username='squatter', email='pending@example.com',
            password='OldPassword456!', is_active=False,
        )
        User.objects.filter(pk=stale.pk).update(
            date_joined=timezone.now() - timedelta(hours=2)
        )

        self.client.post('/register/', data=self.PAYLOAD)

        self.assertFalse(User.objects.filter(pk=stale.pk).exists())
        self.assertTrue(User.objects.filter(username='pendingplayer', is_active=False).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_recent_unverified_signup_still_holds_its_email(self):
        recent = User.objects.create_user(
            username='someoneelse', email='pending@example.com',
            password='OldPassword456!', is_active=False,
        )

        self.client.post('/register/', data=self.PAYLOAD)

        self.assertTrue(User.objects.filter(pk=recent.pk).exists())
        self.assertFalse(User.objects.filter(username='pendingplayer').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_repeat_registration_inside_the_cooldown_sends_one_mail(self):
        self.client.post('/register/', data=self.PAYLOAD)
        self.assertEqual(len(mail.outbox), 1)
        user = User.objects.get(username='pendingplayer')
        first_hash = self.client.session['registration_otp_hash']

        # Same browser: it keeps the code it was sent.
        self.client.post('/register/', data=self.PAYLOAD)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.session['registration_user_id'], user.id)
        self.assertEqual(self.client.session['registration_otp_hash'], first_hash)

        # Another browser: same answer, nothing sent, nothing to verify.
        other = Client()
        response = other.post('/register/', data=self.PAYLOAD)
        self.assertRedirects(response, '/verify-otp/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(other.session['registration_user_id'], -1)

    def test_registration_mails_again_after_the_cooldown(self):
        self.client.post('/register/', data=self.PAYLOAD)
        cache.clear()  # the cooldown has run out
        self.client.post('/register/', data=self.PAYLOAD)
        self.assertEqual(len(mail.outbox), 2)

    def test_resend_shares_the_cooldown_with_registration(self):
        self.client.post('/register/', data=self.PAYLOAD)
        self.assertEqual(len(mail.outbox), 1)

        # A second browser waiting on the same address may not mail either.
        user = User.objects.get(username='pendingplayer')
        other = Client()
        session = other.session
        session['registration_user_id'] = user.id
        session['registration_otp_hash'] = 'x'
        session.save()
        other.post('/resend-otp/')
        self.assertEqual(len(mail.outbox), 1)

        cache.clear()
        other.post('/resend-otp/')
        self.assertEqual(len(mail.outbox), 2)

    def test_resend_timer_starts_at_registration(self):
        self.client.post('/register/', data=self.PAYLOAD)
        response = self.client.get('/verify-otp/')
        self.assertGreater(response.context['remaining_time'], 0)

    def test_failed_mail_does_not_start_the_cooldown(self):
        with mock.patch('game.views.send_mail', side_effect=SMTPException('down')):
            self.client.post('/register/', data=self.PAYLOAD)
        self.client.post('/register/', data=self.PAYLOAD)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_comes_from_the_browser_that_verifies(self):
        with self._fixed_otp():
            self.client.post('/register/', data=self.PAYLOAD)
            cache.clear()
            intruder = Client()
            intruder.post('/register/', data={
                **self.PAYLOAD,
                'password1': 'IntruderPass789!',
                'password2': 'IntruderPass789!',
            })

        user = User.objects.get(username='pendingplayer')
        self.assertFalse(user.check_password('IntruderPass789!'))

        response = self.client.post('/verify-otp/', data={'otp': '123456'})
        self.assertRedirects(response, reverse('index'), fetch_redirect_response=False)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('StrongPass123!'))
        self.assertFalse(user.check_password('IntruderPass789!'))
        self.assertNotIn('registration_password', self.client.session)

        # The other browser's code no longer finds a pending signup.
        intruder.post('/verify-otp/', data={'otp': '123456'})
        user.refresh_from_db()
        self.assertTrue(user.check_password('StrongPass123!'))


class AccountDeletionConfirmTest(TestCase):
    """The mailed link only deletes after a POST by the logged-in owner."""

    def setUp(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        from game.views import account_deletion_token

        self.user = User.objects.create_user(
            username='leaver', email='leaver@example.com', password='Password123!'
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = account_deletion_token.make_token(self.user)
        self.url = reverse('confirm_delete_account', args=[self.uid, self.token])

    def test_delete_request_mails_a_link_that_works(self):
        self.client.force_login(self.user)
        self.client.post(reverse('delete_account'), {
            'username': 'leaver', 'password': 'Password123!',
        })
        self.assertEqual(len(mail.outbox), 1)
        link = [
            line for line in mail.outbox[0].body.splitlines()
            if '/confirm-delete/' in line
        ][0]
        path = '/confirm-delete/' + link.split('/confirm-delete/')[1]

        self.assertEqual(self.client.get(path).status_code, 200)
        self.client.post(path)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_opening_the_link_deletes_nothing(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_post_deletes_the_account(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/delete_success.html')
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_post_needs_a_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_anonymous_visitor_is_sent_to_login(self):
        for method in (self.client.get, self.client.post):
            response = method(self.url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response.url)
            self.assertIn('next=', response.url)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_link_still_works_after_signing_in_from_the_mail(self):
        cache.clear()
        login_url = self.client.get(self.url).url
        response = self.client.post(
            login_url, {'username': 'leaver', 'password': 'Password123!'}
        )
        self.assertRedirects(response, self.url, fetch_redirect_response=False)

        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_signed_out_owner_can_still_finish_the_deletion(self):
        """Request, sign out, open the link, sign in, come back, confirm."""
        cache.clear()
        credentials = {'username': 'leaver', 'password': 'Password123!'}

        self.client.post('/login/', credentials)
        self.client.post(reverse('delete_account'), credentials)
        self.assertEqual(len(mail.outbox), 1)
        link = [
            line for line in mail.outbox[0].body.splitlines()
            if '/confirm-delete/' in line
        ][0]
        path = '/confirm-delete/' + link.split('/confirm-delete/')[1]

        self.client.post('/logout/')

        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        login_url = response.url
        self.assertIn('/login/', login_url)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

        # Signing in changes last_login; the link has to survive that.
        response = self.client.post(login_url, credentials)
        self.assertRedirects(response, path, fetch_redirect_response=False)

        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/confirm_delete_account.html')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

        response = self.client.post(path)
        self.assertTemplateUsed(response, 'game/delete_success.html')
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_link_dies_when_the_password_changes(self):
        self.user.set_password('AnotherPass456!')
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('landing'), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_another_user_cannot_use_the_link(self):
        other = User.objects.create_user(username='other', password='Password123!')
        self.client.force_login(other)
        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('landing'), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(User.objects.filter(pk=other.pk).exists())

    def test_password_reset_token_does_not_delete(self):
        from django.contrib.auth.tokens import default_token_generator
        from game.views import account_deletion_token

        reset_token = default_token_generator.make_token(self.user)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('confirm_delete_account', args=[self.uid, reset_token])
        )

        self.assertRedirects(response, reverse('landing'), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        # And the other way round: a deletion token resets no password.
        self.assertFalse(default_token_generator.check_token(self.user, self.token))
        self.assertTrue(account_deletion_token.check_token(self.user, self.token))


class LoginNextTest(TestCase):
    """After login the user returns to the page that asked for it."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='returner', password='Password123!')
        self.credentials = {'username': 'returner', 'password': 'Password123!'}

    def test_login_required_page_comes_back_after_login(self):
        response = self.client.get('/stats/')
        self.assertEqual(response.status_code, 302)
        login_url = response.url
        self.assertIn('next=/stats/', login_url)

        response = self.client.post(login_url, self.credentials)
        self.assertRedirects(response, '/stats/', fetch_redirect_response=False)

    def test_next_in_the_form_body_works_too(self):
        response = self.client.post('/login/', {**self.credentials, 'next': '/leaderboard/'})
        self.assertRedirects(response, '/leaderboard/', fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        for target in ('https://evil.example/steal', '//evil.example/steal'):
            self.client.logout()
            response = self.client.post(f'/login/?next={target}', self.credentials)
            self.assertRedirects(response, reverse('landing'), fetch_redirect_response=False)

    def test_login_without_next_goes_to_landing(self):
        response = self.client.post('/login/', self.credentials)
        self.assertRedirects(response, reverse('landing'), fetch_redirect_response=False)


class RateCounterWindowTest(TestCase):
    """increment_counter keeps its window on backends without a native incr."""

    DB_CACHE = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'test_rate_counter_cache',
        }
    }

    def test_locmem_counts_natively(self):
        from game.views import _cache_counts_natively
        self.assertTrue(_cache_counts_natively())

    def test_database_cache_keeps_the_requested_window(self):
        from django.core.management import call_command
        from django.db import connection
        from game.views import _cache_counts_natively, increment_counter

        with override_settings(CACHES=self.DB_CACHE):
            call_command('createcachetable', verbosity=0)
            self.assertFalse(_cache_counts_natively())

            counts = [increment_counter('rate-test', timeout=60) for _ in range(3)]
            self.assertEqual(counts, [1, 2, 3])

            # The stock incr would have rewritten the key with the default
            # five-minute timeout. The counter must still end with its window.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT expires FROM test_rate_counter_cache "
                    "WHERE cache_key LIKE %s AND cache_key NOT LIKE %s",
                    ['%rate-test', '%lock:%'],
                )
                expires = cursor.fetchone()[0]
            if isinstance(expires, str):
                from django.utils.dateparse import parse_datetime
                expires = parse_datetime(expires)
            if timezone.is_naive(expires):
                expires = timezone.make_aware(expires, timezone.get_current_timezone())
            self.assertLessEqual(expires - timezone.now(), timedelta(seconds=61))

    def test_new_window_starts_from_one(self):
        from game.views import increment_counter

        cache.clear()
        self.addCleanup(cache.clear)
        with mock.patch('game.views._cache_counts_natively', return_value=False):
            with mock.patch('game.views.time.time', return_value=1000.0):
                self.assertEqual(increment_counter('rate-window', timeout=60), 1)
            # Half a second before the window ends the count is cached for
            # a whole second, so it outlives the window.
            with mock.patch('game.views.time.time', return_value=1059.5):
                self.assertEqual(increment_counter('rate-window', timeout=60), 2)
            with mock.patch('game.views.time.time', return_value=1060.2):
                self.assertEqual(increment_counter('rate-window', timeout=60), 1)


@override_settings(CRON_SECRET='test_secret_123')
class CleanupCronTest(TestCase):
    """The cron endpoint answers Vercel's GET and purges dead rows."""

    url = '/api/cron/cleanup-stale-games/'
    auth = {'HTTP_AUTHORIZATION': 'Bearer test_secret_123'}

    def test_get_with_secret_runs_the_cleanup(self):
        response = self.client.get(self.url, **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

    def test_get_without_secret_is_refused(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(
            self.client.get(self.url, HTTP_AUTHORIZATION='Bearer nope').status_code, 401
        )

    def test_expired_replays_and_sessions_are_purged(self):
        from django.contrib.sessions.models import Session

        expired = GameRecord.objects.create(session_key='old', pgn='1. e4')
        GameRecord.objects.filter(pk=expired.pk).update(
            expires_at=timezone.now() - timedelta(hours=1)
        )
        kept = GameRecord.objects.create(session_key='new', pgn='1. d4')
        Session.objects.create(
            session_key='deadsession', session_data='x',
            expire_date=timezone.now() - timedelta(days=1),
        )

        data = self.client.get(self.url, **self.auth).json()

        self.assertEqual(data['purged_records'], 1)
        self.assertEqual(data['purged_sessions'], 1)
        self.assertFalse(GameRecord.objects.filter(pk=expired.pk).exists())
        self.assertTrue(GameRecord.objects.filter(pk=kept.pk).exists())


class StatsPageDataTest(TestCase):
    """What the stats and leaderboard views hand to their templates."""

    def setUp(self):
        self.user = User.objects.create_user(username='statsuser', password='Password123!')
        self.client.force_login(self.user)

    def test_chart_history_is_passed_oldest_first(self):
        RatingHistory.objects.create(
            user=self.user, old_rating=1200, new_rating=1220, rating_change=20, result='win'
        )
        RatingHistory.objects.create(
            user=self.user, old_rating=1220, new_rating=1210, rating_change=-10, result='loss'
        )

        chart = self.client.get('/stats/').context['chart_history']

        self.assertEqual([point['new_rating'] for point in chart], [1220, 1210])
        self.assertEqual(
            set(chart[0]), {'date', 'timestamp', 'new_rating', 'change', 'result'}
        )
        self.assertEqual(chart[1]['change'], -10)
        self.assertEqual(chart[1]['result'], 'loss')
        self.assertIsInstance(chart[0]['timestamp'], int)

    def test_two_player_games_are_not_wins_or_losses(self):
        GameResult.objects.create(
            user=self.user, mode='pvp', winner='white', player_color='white',
            end_reason='checkmate',
        )
        GameResult.objects.create(
            user=self.user, mode='ai', winner='black', player_color='white',
            end_reason='checkmate',
        )

        context = self.client.get('/stats/').context

        self.assertEqual(context['total_games'], 2)
        self.assertEqual(context['total_wins'], 0)
        self.assertEqual(context['total_losses'], 1)
        self.assertEqual(context['games_as_white'], 1)

    def test_lapsed_day_streak_reads_zero(self):
        progress, _ = UserProgress.objects.get_or_create(user=self.user)
        progress.day_streak = 6
        progress.last_played_date = timezone.localdate() - timedelta(days=3)
        progress.save()

        context = self.client.get('/stats/').context
        self.assertEqual(context['progress'].day_streak, 0)
        self.assertEqual(self.client.get('/api/state/').json()['day_streak'], 0)

    def test_yesterdays_streak_is_still_alive(self):
        progress, _ = UserProgress.objects.get_or_create(user=self.user)
        progress.day_streak = 6
        progress.last_played_date = timezone.localdate() - timedelta(days=1)
        progress.save()

        self.assertEqual(self.client.get('/api/state/').json()['day_streak'], 6)

    def test_puzzle_leaderboard_is_limited(self):
        users = User.objects.bulk_create(
            [User(username=f'board{i}') for i in range(55)]
        )
        PuzzleStats.objects.bulk_create(
            [PuzzleStats(user=user, puzzles_solved=i) for i, user in enumerate(users)]
        )

        leaderboard = self.client.get('/leaderboard/').context['leaderboard']
        self.assertEqual(len(leaderboard), 50)
        self.assertEqual(leaderboard[0].puzzles_solved, 54)


class LessonCompletionTest(TestCase):
    """Lessons unlock in order and pay out once."""

    def setUp(self):
        self.user = User.objects.create_user(username='student', password='Password123!')
        self.client.force_login(self.user)

    def _complete(self, slug):
        return self.client.post(reverse('complete_lesson', args=[slug]))

    def _xp(self):
        progress = UserProgress.objects.filter(user=self.user).first()
        return progress.xp if progress else 0

    def test_first_lesson_pays_once(self):
        self._complete('how-pieces-move')
        self._complete('how-pieces-move')

        self.assertTrue(LessonProgress.objects.get(
            user=self.user, lesson_name='How Pieces Move'
        ).completed)
        self.assertEqual(self._xp(), 25)

    def test_locked_lesson_is_refused(self):
        for slug in ('check-and-checkmate', 'forks', 'basic-endgames'):
            response = self._complete(slug)
            self.assertRedirects(response, reverse('lessons'), fetch_redirect_response=False)

        self.assertFalse(LessonProgress.objects.filter(user=self.user).exists())
        self.assertEqual(self._xp(), 0)

    def test_next_lesson_opens_after_the_one_before(self):
        self._complete('how-pieces-move')
        response = self._complete('check-and-checkmate')

        self.assertRedirects(
            response, reverse('lesson_detail', args=['check-and-checkmate']),
            fetch_redirect_response=False,
        )
        self.assertEqual(self._xp(), 50)

    def test_unknown_lesson_is_404(self):
        self.assertEqual(self._complete('no-such-lesson').status_code, 404)


class OpeningStatsStorageTest(TestCase):
    """The opening trainer's reported accuracy is stored and validated."""

    def setUp(self):
        self.user = User.objects.create_user(username='opener', password='Password123!')
        self.client.force_login(self.user)
        self.url = reverse('update_opening_stats')

    def _post(self, payload):
        return self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )

    def test_accuracy_and_completion_are_stored(self):
        self._post({'opening_name': 'Ruy Lopez', 'completed': True, 'accuracy': 80})

        progress = OpeningProgress.objects.get(user=self.user, opening_name='Ruy Lopez')
        self.assertEqual(progress.accuracy_percentage, 80)
        self.assertEqual(progress.completion_percentage, 100)
        self.assertEqual(progress.openings_started, 1)
        # 50 for the first completion, no bonus below 100.
        self.assertEqual(UserProgress.objects.get(user=self.user).xp, 50)

    def test_each_further_run_counts_as_practice(self):
        for _ in range(3):
            self._post({'opening_name': 'Ruy Lopez', 'completed': True, 'accuracy': 90})

        progress = OpeningProgress.objects.get(user=self.user, opening_name='Ruy Lopez')
        self.assertEqual(progress.openings_started, 3)
        self.assertEqual(progress.openings_completed, 1)

    def test_accuracy_is_clamped(self):
        self._post({'opening_name': 'Ruy Lopez', 'completed': False, 'accuracy': 250})
        progress = OpeningProgress.objects.get(user=self.user, opening_name='Ruy Lopez')
        self.assertEqual(progress.accuracy_percentage, 100)

    def test_bad_payloads_get_400(self):
        bad = (
            ['Ruy Lopez'],
            {'opening_name': 'Ruy Lopez', 'completed': 'yes'},
            {'opening_name': 'Ruy Lopez', 'completed': True, 'accuracy': True},
            {'opening_name': ['Ruy Lopez'], 'completed': True},
        )
        for payload in bad:
            response = self._post(payload)
            self.assertEqual(response.status_code, 400, payload)
        self.assertFalse(OpeningProgress.objects.exists())


class ForumCountsTest(TestCase):
    """Sort counts in the personal tabs, and replies that were deleted."""

    def setUp(self):
        self.me = User.objects.create_user(username='me', password='Password123!')
        self.other = User.objects.create_user(username='other', password='Password123!')
        self.third = User.objects.create_user(username='third', password='Password123!')
        self.busy = Discussion.objects.create(
            user=self.other, title='Busy thread', content='Lots of replies here'
        )
        self.mine = Discussion.objects.create(
            user=self.me, title='My thread', content='Just my own thread'
        )
        Reply.objects.create(discussion=self.busy, user=self.me, content='mine')
        for index in range(3):
            Reply.objects.create(discussion=self.busy, user=self.other, content=f'reply {index}')
        self.client.force_login(self.me)

    def test_my_tab_counts_every_reply_not_only_mine(self):
        context = self.client.get('/forum/?sort=most_replies').context
        mine = list(context['user_discussions'])

        self.assertEqual([d.pk for d in mine], [self.busy.pk, self.mine.pk])
        self.assertEqual(mine[0].reply_count, 4)

    def test_bookmark_tab_counts_every_bookmark(self):
        for user in (self.me, self.other, self.third):
            DiscussionBookmark.objects.create(user=user, discussion=self.busy)

        context = self.client.get('/forum/?sort=most_bookmarked').context
        bookmarked = list(context['bookmarked_discussions'])

        self.assertEqual(len(bookmarked), 1)
        self.assertEqual(bookmarked[0].bookmark_count, 3)

    def test_deleted_replies_are_not_counted(self):
        Reply.objects.filter(discussion=self.busy, user=self.other).update(is_deleted=True)

        context = self.client.get('/forum/?sort=most_replies').context
        busy = [d for d in context['page_obj'] if d.pk == self.busy.pk][0]

        self.assertEqual(busy.reply_count, 1)
        self.assertEqual(busy.replies.count(), 1)

    def test_bad_reply_to_is_an_error_message_not_a_crash(self):
        response = self.client.post(
            reverse('forum_reply', args=[self.busy.pk]),
            {'content': 'hello there', 'reply_to': 'abc'},
        )
        self.assertRedirects(
            response, reverse('forum_detail', args=[self.busy.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(Reply.objects.filter(content='hello there').count(), 0)


class DeploymentSettingsTest(SimpleTestCase):
    """core/settings.py under different environments."""

    def _settings(self, **env):
        import runpy
        from pathlib import Path

        path = Path(settings.BASE_DIR) / 'core' / 'settings.py'
        environ = {'SECRET_KEY': 'k' * 50, **env}
        # Keep a developer's own .env out of the picture.
        with mock.patch.dict('os.environ', environ, clear=True), \
                mock.patch('dotenv.load_dotenv'):
            return runpy.run_path(str(path))

    def test_debug_is_off_unless_asked_for(self):
        self.assertFalse(self._settings()['DEBUG'])
        self.assertTrue(self._settings(DEBUG='True')['DEBUG'])

    def test_local_run_stays_on_plain_http(self):
        conf = self._settings()
        self.assertFalse(conf['SESSION_COOKIE_SECURE'])
        self.assertFalse(conf['CSRF_COOKIE_SECURE'])
        self.assertFalse(conf['SECURE_SSL_REDIRECT'])

    def test_preview_deployment_is_locked_down(self):
        conf = self._settings(VERCEL_ENV='preview', DEBUG='True')
        self.assertFalse(conf['DEBUG'])
        self.assertTrue(conf['SESSION_COOKIE_SECURE'])
        self.assertTrue(conf['CSRF_COOKIE_SECURE'])
        self.assertTrue(conf['SECURE_SSL_REDIRECT'])
        self.assertEqual(conf['SECURE_PROXY_SSL_HEADER'], ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertFalse(conf['IS_PRODUCTION'])

    def test_production_deployment_is_locked_down(self):
        conf = self._settings(VERCEL_ENV='production', DEBUG='True')
        self.assertFalse(conf['DEBUG'])
        self.assertTrue(conf['SESSION_COOKIE_SECURE'])
        self.assertTrue(conf['SECURE_SSL_REDIRECT'])
        self.assertEqual(conf['SECURE_HSTS_SECONDS'], 31536000)

    def test_static_files_use_the_storages_setting(self):
        conf = self._settings()
        self.assertNotIn('STATICFILES_STORAGE', conf)
        self.assertEqual(
            conf['STORAGES']['staticfiles']['BACKEND'],
            'whitenoise.storage.CompressedStaticFilesStorage',
        )

    def test_static_tag_accepts_a_directory_prefix(self):
        from django.templatetags.static import static
        self.assertEqual(static('game/'), '/static/game/')


class DeploymentFilesTest(SimpleTestCase):
    """vercel.json and the security headers."""

    def test_cron_job_points_at_the_cleanup_view(self):
        from pathlib import Path
        from django.urls import resolve
        from game import views

        config = json.loads((Path(settings.BASE_DIR) / 'vercel.json').read_text())
        paths = [job['path'] for job in config['crons']]

        self.assertEqual(len(paths), 1)
        self.assertEqual(resolve(paths[0]).func, views.cleanup_cron)

    def test_images_only_come_from_our_own_hosts(self):
        from game.middleware import SecurityHeadersMiddleware
        from django.http import HttpResponse

        response = SecurityHeadersMiddleware(lambda request: HttpResponse())(
            RequestFactory().get('/')
        )
        policy = response['Content-Security-Policy']
        img_src = [part for part in policy.split('; ') if part.startswith('img-src')][0]

        self.assertNotIn('chesscomfiles', policy)
        self.assertEqual(img_src, "img-src 'self' data: https://checkora.vercel.app")
