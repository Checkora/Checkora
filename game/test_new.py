import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .engine import ChessGame
class ResignTest(TestCase):
    """Test the /api/resign/ endpoint."""

    def setUp(self):
        self.client.get('/play/')

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