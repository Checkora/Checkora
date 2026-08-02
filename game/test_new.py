import json
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from .engine import ChessGame
from .models import GameResult, PlayerRating


class ResignTest(TestCase):
    """Test the /api/resign/ endpoint."""

    def setUp(self):
        cache.clear()
        self.client.get('/play/')

    def tearDown(self):
        cache.clear()

    def test_resign_ends_game_as_white(self):
        """Resigning as white should mark game status as resignation."""
        response = self.client.post(
            '/api/resign/',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('game_status', data)
        self.assertEqual(data['game_status'], 'resignation')

    def test_resign_records_correct_winner(self):
        """When white resigns, black should be the winner."""
        response = self.client.post(
            '/api/resign/',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('winner', data)
        self.assertEqual(data['winner'], 'black')

    def test_resign_rejects_get_method(self):
        """GET request to /api/resign/ should return 405."""
        response = self.client.get('/api/resign/')
        self.assertEqual(response.status_code, 405)

    def test_resign_after_game_over_is_rejected(self):
        """Resigning a game that is already over should be rejected."""
        session = self.client.session
        game_data = session['game']
        game_data['game_status'] = 'checkmate'
        session['game'] = game_data
        session.save()

        response = self.client.post(
            '/api/resign/',
            content_type='application/json',
        )
        self.assertIn(response.status_code, [400, 200])
        if response.status_code == 200:
            data = response.json()
            self.assertNotEqual(data.get('game_status'), 'active')

    def test_state_reflects_resignation_after_resign(self):
        """After resigning, /api/state/ should show resignation status."""
        self.client.post('/api/resign/', content_type='application/json')
        state = self.client.get('/api/state/').json()
        self.assertEqual(state['game_status'], 'resignation')

    def test_ai_resign_ignores_client_controlled_resigning_player(self):
        """AI games should resign the human player's stored color."""
        user = User.objects.create_user(username='airesign', password='password123')
        self.client.force_login(user)
        self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai',
                'player_color': 'white',
            }),
            content_type='application/json',
        )

        response = self.client.post(
            '/api/resign/',
            data=json.dumps({'resigning_player': 'black'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['winner'], 'black')
        result = GameResult.objects.get(user=user)
        self.assertEqual(result.winner, 'black')
        rating = PlayerRating.objects.get(user=user)
        self.assertEqual(rating.wins, 0)
        self.assertEqual(rating.losses, 1)

    def test_pvp_resign_rejects_opponent_color(self):
        """PvP resign cannot name the opponent as the resigning player."""
        user = User.objects.create_user(username='pvpresign', password='password123')
        self.client.force_login(user)
        self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'pvp',
                'player_color': 'white',
            }),
            content_type='application/json',
        )

        response = self.client.post(
            '/api/resign/',
            data=json.dumps({'resigning_player': 'black'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(GameResult.objects.filter(user=user).count(), 0)

    @override_settings(RESIGN_RATE_WINDOW_SECONDS=60, RESIGN_MAX_REQUESTS=1)
    def test_resign_rate_limit_rejects_excess_requests(self):
        """Excess resign requests from the same user should return 429."""
        user = User.objects.create_user(username='resignlimit', password='password123')
        self.client.force_login(user)

        first = self.client.post(
            '/api/resign/',
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )
        second = self.client.post(
            '/api/resign/',
            content_type='application/json',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)


class DrawAIModeTest(TestCase):
    """Test draw offer behaviour in AI mode."""

    def setUp(self):
        self.client.get('/play/')
        self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'ai'}),
            content_type='application/json',
        )

    def test_draw_offer_in_ai_mode_returns_200(self):
        """Draw endpoint should respond without crashing in AI mode."""
        response = self.client.post(
            '/api/draw/',
            data=json.dumps({'action': 'accept'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_draw_offer_in_ai_mode_returns_json(self):
        """Response should be valid JSON with a game_status field."""
        response = self.client.post(
            '/api/draw/',
            data=json.dumps({'action': 'accept'}),
            content_type='application/json',
        )
        data = response.json()
        self.assertIn('game_status', data)


class NewGameEdgeCaseTest(TestCase):
    """Edge cases for /api/new-game/ not covered by NewGameTest."""

    def setUp(self):
        self.client.get('/play/')

    def test_new_game_default_mode_is_pvp(self):
        """Calling /api/new-game/ with no body should default to pvp."""
        response = self.client.post(
            '/api/new-game/',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('mode'), 'pvp')

    def test_new_game_invalid_mode_handled(self):
        """An invalid mode value should not crash the server."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'invalid'}),
            content_type='application/json',
        )
        self.assertIn(response.status_code, [200, 400])

    def test_new_game_rejects_get_method(self):
        """GET on /api/new-game/ should return 405."""
        response = self.client.get('/api/new-game/')
        self.assertEqual(response.status_code, 405)

    def test_new_game_resets_captured_pieces(self):
        """Captured pieces should be empty after starting a new game."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'pvp'}),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['captured_pieces']['white'], [])
        self.assertEqual(data['captured_pieces']['black'], [])

    def test_new_game_board_has_correct_dimensions(self):
        """Board returned by /api/new-game/ should be 8x8."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'pvp'}),
            content_type='application/json',
        )
        board = response.json()['board']
        self.assertEqual(len(board), 8)
        for row in board:
            self.assertEqual(len(row), 8)

    def test_new_game_ai_difficulty_and_bot_names(self):
        """Test that starting an AI game correctly assigns bot names based on difficulty."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai', 'difficulty': 'easy', 'player_color': 'white'
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['black_name'], '♟️ Novice Pawn')
        self.assertEqual(data['difficulty'], 'easy')

        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai', 'difficulty': 'medium', 'player_color': 'white'
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['black_name'], '♗ Tactical Bishop')

        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai', 'difficulty': 'hard', 'player_color': 'white'
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['black_name'], '♜ Grandmaster Rook')

    def test_new_game_ai_invalid_difficulty_fallback(self):
        """Test that invalid difficulty falls back to medium personality."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai',
                'difficulty': 'invalid_level',
                'player_color': 'white'
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['black_name'], '♗ Tactical Bishop')

    def test_ai_search_depth_mapping(self):
        """Test that the engine properly maps difficulty to search depth."""

        game = ChessGame(difficulty='easy')
        self.assertEqual(game._get_ai_search_depth(), 2)

        game = ChessGame(difficulty='medium')
        self.assertEqual(game._get_ai_search_depth(), 4)

        game = ChessGame(difficulty='hard')
        self.assertEqual(game._get_ai_search_depth(), 6)

        game = ChessGame(difficulty='invalid_level')
        self.assertEqual(game._get_ai_search_depth(), 4)


class PuzzleStatsTest(TestCase):
    """Test the /api/puzzle-stats/ endpoint."""

    def test_puzzle_stats_returns_streak_fields(self):
        """Response must contain streak and longest_streak fields."""
        response = self.client.get('/api/puzzle-stats/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('streak', data)
        self.assertIn('longest_streak', data)

    def test_puzzle_stats_default_values_are_zero(self):
        """Fresh session should return streak of 0."""
        response = self.client.get('/api/puzzle-stats/')
        data = response.json()
        self.assertEqual(data['streak'], 0)
        self.assertEqual(data['longest_streak'], 0)

    def test_puzzle_stats_accepts_get(self):
        """GET to /api/puzzle-stats/ should return 200."""
        response = self.client.get('/api/puzzle-stats/')
        self.assertEqual(response.status_code, 200)


class SecurityHeadersTest(TestCase):
    """Test HTTP security headers applied by custom middleware."""

    def test_security_headers_present_on_pages(self):
        """Verify headers on standard HTML page responses."""
        response = self.client.get('/play/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Content-Security-Policy', response)
        self.assertIn('Permissions-Policy', response)
        self.assertTrue(response['Content-Security-Policy'].startswith("default-src 'self'"))
        self.assertIn("camera=()", response['Permissions-Policy'])
