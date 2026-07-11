import json
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from game.views import MAX_ANALYSIS_MOVES, MAX_MOVE_LENGTH
from game.analysis import (
    detect_opening,
    count_captures,
    count_checks,
    count_checkmates,
    count_promotions,
    build_summary
)

@override_settings(SECURE_SSL_REDIRECT=False)
class AnalysisTest(TestCase):
    def test_detect_opening(self):
        self.assertEqual(detect_opening(['e4', 'e5', 'Nf3', 'Nc6', 'Bc4']), 'Italian Game')
        self.assertEqual(detect_opening(['e4', 'c5']), 'Sicilian Defense')
        self.assertEqual(detect_opening(['d4', 'd5', 'c4']), "Queen's Gambit")
        self.assertIsNone(detect_opening(['a3', 'a6']))
        self.assertIsNone(detect_opening([]))
        self.assertEqual(detect_opening(['e4', 'e5', 'Nf3']), "King's Pawn Game")
        self.assertEqual(detect_opening(['d4', 'Nf6', 'c4', 'e6']), 'Nimzo-Indian Defense')
        self.assertEqual(detect_opening(['d4', 'Nf6', 'c4', 'd5']), 'Indian Defense')
        self.assertEqual(detect_opening(['f4', 'd5']), "Bird's Opening")

    def test_count_captures(self):
        self.assertEqual(count_captures(['e4', 'e5', 'exd5']), 1)
        self.assertEqual(count_captures(['Nxe4', 'Qxd4']), 2)
        self.assertEqual(count_captures(['e4', 'e5']), 0)

    def test_count_checks(self):
        self.assertEqual(count_checks(['e4', 'e5', 'Bb5+']), 1)
        self.assertEqual(count_checks(['e4', 'e5']), 0)

    def test_count_checkmates(self):
        self.assertEqual(count_checkmates(['e4', 'e5', 'Qh5#']), 1)
        self.assertEqual(count_checkmates(['e4', 'e5']), 0)

    def test_count_promotions(self):
        self.assertEqual(count_promotions(['e8=Q', 'd1=N']), 2)
        self.assertEqual(count_promotions(['e4', 'e5']), 0)

    def test_build_summary(self):
        moves = ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'exd4', 'Bb5+']
        summary = build_summary(moves, 'Win', 'Checkmate')
        self.assertEqual(summary['opening'], 'Italian Game')
        self.assertEqual(summary['result'], 'Win')
        self.assertEqual(summary['total_moves'], 4) # 7 moves -> 4 total full moves
        self.assertEqual(summary['captures'], 1)
        self.assertEqual(summary['checks'], 1)
        self.assertEqual(summary['checkmates'], 0)
        self.assertEqual(summary['promotions'], 0)
        self.assertEqual(summary['end_reason'], 'Checkmate')

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='password123')

    def test_api_endpoint_requires_login(self):
        payload = {
            "moves": ["e4", "e5"],
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {'error': 'Unauthorized'})

    def test_api_endpoint_success(self):
        self.client.force_login(self.user)
        payload = {
            "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['opening'], 'Italian Game')
        self.assertEqual(data['result'], 'Win')
        self.assertEqual(data['total_moves'], 3)
        self.assertEqual(data['captures'], 0)
        self.assertEqual(data['checks'], 0)
        self.assertEqual(data['checkmates'], 0)
        self.assertEqual(data['promotions'], 0)
        self.assertEqual(data['end_reason'], 'Checkmate')

    def test_api_endpoint_moves_not_list(self):
        self.client.force_login(self.user)
        payload = {
            "moves": "not a list",
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Moves must be a list'})

    def test_api_endpoint_moves_too_long(self):
        self.client.force_login(self.user)
        payload = {
            "moves": ["e4"] * (MAX_ANALYSIS_MOVES + 1),
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': f'Moves list cannot exceed {MAX_ANALYSIS_MOVES} entries'})

    def test_api_endpoint_move_string_too_long(self):
        self.client.force_login(self.user)
        payload = {
            "moves": ["e4", "a" * (MAX_MOVE_LENGTH + 1)],
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': f'Move must be a string of at most {MAX_MOVE_LENGTH} characters'})

    def test_api_endpoint_move_not_string(self):
        self.client.force_login(self.user)
        payload = {
            "moves": ["e4", 123],
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': f'Move must be a string of at most {MAX_MOVE_LENGTH} characters'})

    def test_api_endpoint_moves_exact_limit(self):
        self.client.force_login(self.user)
        payload = {
            "moves": ["e4"] * MAX_ANALYSIS_MOVES,
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_moves', data)

    def test_api_endpoint_move_string_exact_limit(self):
        self.client.force_login(self.user)
        payload = {
            "moves": ["e4", "a" * MAX_MOVE_LENGTH],
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_moves', data)


@override_settings(SECURE_SSL_REDIRECT=False)
class AnalyzeGameCsrfTest(TestCase):
    """Verify that CSRF protection is enforced on analyze_game_view."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(
            username='csrfuser', password='password123'
        )

    def test_post_without_csrf_token_is_rejected(self):
        """POST without a CSRF token must return 403."""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            reverse('analyze_game'),
            data=json.dumps({
                'moves': ['e4', 'e5'],
                'result': 'Win',
                'reason': 'Checkmate',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_post_with_valid_csrf_token_succeeds(self):
        """POST with a valid X-CSRFToken header must return 200."""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        # Fetch a CSRF cookie by hitting a GET endpoint
        csrf_client.get(reverse('index'))
        token = csrf_client.cookies['csrftoken'].value

        response = csrf_client.post(
            reverse('analyze_game'),
            data=json.dumps({
                'moves': ['e4', 'e5'],
                'result': 'Win',
                'reason': 'Checkmate',
            }),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)


@override_settings(SECURE_SSL_REDIRECT=False)
class AnalyzeGameRateLimitTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from django.core.cache import cache
        self.user1 = User.objects.create_user(username='ratelimituser1', password='password123')
        self.user2 = User.objects.create_user(username='ratelimituser2', password='password123')
        cache.clear()

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    @override_settings(ANALYZE_GAME_RATE_WINDOW_SECONDS=60, ANALYZE_GAME_USER_MAX_REQUESTS=2, ANALYZE_GAME_IP_MAX_REQUESTS=3)
    def test_normal_usage_under_limit(self):
        self.client.force_login(self.user1)
        payload = {"moves": ["e4", "e5"], "result": "Win", "reason": "Checkmate"}
        
        response = self.client.post(reverse('analyze_game'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)

    @override_settings(ANALYZE_GAME_RATE_WINDOW_SECONDS=60, ANALYZE_GAME_USER_MAX_REQUESTS=2, ANALYZE_GAME_IP_MAX_REQUESTS=3)
    def test_limit_enforcement(self):
        self.client.force_login(self.user1)
        payload = {"moves": ["e4", "e5"], "result": "Win", "reason": "Checkmate"}
        
        for _ in range(2):
            response = self.client.post(reverse('analyze_game'), data=json.dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            
        response = self.client.post(reverse('analyze_game'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {'error': 'Too many requests'})

    @override_settings(ANALYZE_GAME_RATE_WINDOW_SECONDS=60, ANALYZE_GAME_USER_MAX_REQUESTS=3, ANALYZE_GAME_IP_MAX_REQUESTS=2)
    def test_per_ip_independence(self):
        payload = {"moves": ["e4", "e5"], "result": "Win", "reason": "Checkmate"}
        
        self.client.force_login(self.user1)
        for _ in range(2):
            response = self.client.post(reverse('analyze_game'), data=json.dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            
        self.client.force_login(self.user2)
        same_ip_response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json',
            REMOTE_ADDR='127.0.0.1'
        )
        self.assertEqual(same_ip_response.status_code, 429)

        response = self.client.post(
            reverse('analyze_game'),
            data=json.dumps(payload),
            content_type='application/json',
            REMOTE_ADDR='203.0.113.10'
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(ANALYZE_GAME_RATE_WINDOW_SECONDS=60, ANALYZE_GAME_USER_MAX_REQUESTS=2, ANALYZE_GAME_IP_MAX_REQUESTS=3)
    def test_timeout_recovery(self):
        from unittest.mock import patch
        self.client.force_login(self.user1)
        payload = {"moves": ["e4", "e5"], "result": "Win", "reason": "Checkmate"}
        
        mock_time = 100000.0
        
        with patch('time.time', return_value=mock_time) as mock_t:
            for _ in range(2):
                self.client.post(reverse('analyze_game'), data=json.dumps(payload), content_type='application/json')
                
            response = self.client.post(reverse('analyze_game'), data=json.dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 429)
            
            # Advance time by 61 seconds (past the 60 second window)
            mock_t.return_value = mock_time + 61.0
            
            response = self.client.post(reverse('analyze_game'), data=json.dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 200)


@override_settings(SECURE_SSL_REDIRECT=False)
class AiMoveRateLimitTest(TestCase):
    """
    Issue #1625: Rate limiting for the /api/ai-move/ endpoint.
    """

    def _make_ai_game_session(self):
        """Set an AI-mode chess game in the test client's session."""
        from game.engine import ChessGame
        game = ChessGame()
        game.mode = 'ai'
        game.paused = False
        session = self.client.session
        session['game'] = game.to_dict()
        session['difficulty'] = 'easy'
        session.save()

    def setUp(self):
        from django.contrib.auth.models import User
        from django.core.cache import cache
        self.user1 = User.objects.create_user(username='ai_rl_user1', password='pass123')
        self.user2 = User.objects.create_user(username='ai_rl_user2', password='pass123')
        cache.clear()

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    @override_settings(
        AI_MOVE_RATE_WINDOW_SECONDS=60,
        AI_MOVE_USER_MAX_REQUESTS=2,
        AI_MOVE_IP_MAX_REQUESTS=1000,
    )
    def test_request_under_limit_not_rejected(self):
        """A single request well below the limit must not return 429 and process normally."""
        self.client.force_login(self.user1)
        self._make_ai_game_session()

        from unittest.mock import patch
        with patch('game.engine.ChessGame.get_ai_move', return_value={'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4}):
            response = self.client.post(reverse('ai_move'), HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('valid'))
        self.assertIn('game_status', data)

    @override_settings(
        AI_MOVE_RATE_WINDOW_SECONDS=60,
        AI_MOVE_USER_MAX_REQUESTS=2,
        AI_MOVE_IP_MAX_REQUESTS=1000,
    )
    def test_user_limit_enforcement(self):
        """After exceeding AI_MOVE_USER_MAX_REQUESTS the endpoint returns 429."""
        self.client.force_login(self.user1)
        self._make_ai_game_session()

        for _ in range(2):
            r = self.client.post(reverse('ai_move'), HTTP_ACCEPT='application/json')
            self.assertNotEqual(r.status_code, 429)

        r = self.client.post(reverse('ai_move'), HTTP_ACCEPT='application/json')
        self.assertEqual(r.status_code, 429)
        self.assertIn('error', r.json())

    @override_settings(
        AI_MOVE_RATE_WINDOW_SECONDS=60,
        AI_MOVE_USER_MAX_REQUESTS=1000,
        AI_MOVE_IP_MAX_REQUESTS=2,
    )
    def test_ip_limit_enforcement(self):
        """After exceeding AI_MOVE_IP_MAX_REQUESTS the endpoint returns 429."""
        self.client.force_login(self.user1)
        self._make_ai_game_session()

        for _ in range(2):
            r = self.client.post(reverse('ai_move'), REMOTE_ADDR='10.0.0.1', HTTP_ACCEPT='application/json')
            self.assertNotEqual(r.status_code, 429)

        r = self.client.post(reverse('ai_move'), REMOTE_ADDR='10.0.0.1', HTTP_ACCEPT='application/json')
        self.assertEqual(r.status_code, 429)
        self.assertIn('error', r.json())

    @override_settings(
        AI_MOVE_RATE_WINDOW_SECONDS=60,
        AI_MOVE_USER_MAX_REQUESTS=2,
        AI_MOVE_IP_MAX_REQUESTS=1000,
    )
    def test_separate_users_have_independent_buckets(self):
        """Exhausting user1's quota must not affect user2's quota."""
        self.client.force_login(self.user1)
        self._make_ai_game_session()
        for _ in range(2):
            self.client.post(reverse('ai_move'), HTTP_ACCEPT='application/json')
        r = self.client.post(reverse('ai_move'), HTTP_ACCEPT='application/json')
        self.assertEqual(r.status_code, 429)

        self.client.force_login(self.user2)
        self._make_ai_game_session()
        r2 = self.client.post(reverse('ai_move'), HTTP_ACCEPT='application/json')
        self.assertNotEqual(r2.status_code, 429)

    @override_settings(
        AI_MOVE_RATE_WINDOW_SECONDS=60,
        AI_MOVE_USER_MAX_REQUESTS=1000,
        AI_MOVE_IP_MAX_REQUESTS=2,
    )
    def test_separate_ips_have_independent_buckets(self):
        """Exhausting one IP's quota must not throttle a different IP."""
        self.client.force_login(self.user1)
        self._make_ai_game_session()

        for _ in range(2):
            self.client.post(reverse('ai_move'), REMOTE_ADDR='10.0.0.1', HTTP_ACCEPT='application/json')
        r = self.client.post(reverse('ai_move'), REMOTE_ADDR='10.0.0.1', HTTP_ACCEPT='application/json')
        self.assertEqual(r.status_code, 429)

        r2 = self.client.post(reverse('ai_move'), REMOTE_ADDR='10.0.0.2', HTTP_ACCEPT='application/json')
        self.assertNotEqual(r2.status_code, 429)

    @override_settings(
        AI_MOVE_RATE_WINDOW_SECONDS=60,
        AI_MOVE_USER_MAX_REQUESTS=1000,
        AI_MOVE_IP_MAX_REQUESTS=2,
    )
    def test_anonymous_requests_limited_by_ip(self):
        """Unauthenticated requests fall back to IP-based limiting."""
        self._make_ai_game_session()

        for _ in range(2):
            r = self.client.post(reverse('ai_move'), REMOTE_ADDR='192.0.2.1', HTTP_ACCEPT='application/json')
            self.assertNotEqual(r.status_code, 429)

        r = self.client.post(reverse('ai_move'), REMOTE_ADDR='192.0.2.1', HTTP_ACCEPT='application/json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r['Retry-After'], '60')
        self.assertIn('error', r.json())

    @override_settings(
        AI_MOVE_RATE_WINDOW_SECONDS=60,
        AI_MOVE_USER_MAX_REQUESTS=1,
        AI_MOVE_IP_MAX_REQUESTS=1000,
    )
    def test_429_response_is_json_with_error_key(self):
        """The throttled response must be JSON with an 'error' key and a Retry-After header."""
        self.client.force_login(self.user1)
        self._make_ai_game_session()

        self.client.post(reverse('ai_move'), HTTP_ACCEPT='application/json')
        r = self.client.post(reverse('ai_move'), HTTP_ACCEPT='application/json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r['Retry-After'], '60')
        data = r.json()
        self.assertIn('error', data)
        self.assertIsInstance(data['error'], str)
        self.assertGreater(len(data['error']), 0)
