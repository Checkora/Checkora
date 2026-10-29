import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from game.models import (
    ActiveGame, Achievement, UserAchievement, GameRecord
)
from game.services import (
    generate_badge, update_opening_progress
)
from game.progression import award_xp


class SecurityAndFixesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chess_master',
            password='Password123!',
            email='master@example.com'
        )
        self.client = Client()

    def test_authenticated_valid_moves_and_promotion_and_draw(self):
        """Verify that authenticated active games correctly sync with valid-moves,

        check-promotion, get_state, and offer_draw endpoints."""
        self.client.login(username='chess_master', password='Password123!')
        self.client.get('/play/')

        # Get initial state and version
        state_resp = self.client.get('/api/state/')
        self.assertEqual(state_resp.status_code, 200)

        active = ActiveGame.objects.filter(user=self.user, status='active').first()
        self.assertIsNotNone(active)

        # Make move 1. e4 (6,4 -> 4,4) using current version
        move_resp = self.client.post(
            '/api/move/',
            data=json.dumps({
                'from_row': 6, 'from_col': 4,
                'to_row': 4, 'to_col': 4,
                'version': active.version
            }),
            content_type='application/json'
        )
        self.assertEqual(move_resp.status_code, 200)
        self.assertTrue(move_resp.json()['valid'])

        # Verify active game is in DB
        self.assertTrue(ActiveGame.objects.filter(user=self.user, status='active').exists())

        # Test valid_moves endpoint for black pawn at (1, 4)
        vm_resp = self.client.get('/api/valid-moves/?row=1&col=4')
        self.assertEqual(vm_resp.status_code, 200)
        moves = vm_resp.json()['valid_moves']
        self.assertTrue(len(moves) > 0, "Valid moves should not be empty for active game")

        # Test check_promotion endpoint
        cp_resp = self.client.get('/api/check-promotion/?from_row=1&from_col=4&to_row=2')
        self.assertEqual(cp_resp.status_code, 200)
        self.assertFalse(cp_resp.json()['is_promotion'])

        # Test state endpoint
        state_resp = self.client.get('/api/state/')
        self.assertEqual(state_resp.status_code, 200)
        self.assertEqual(state_resp.json()['current_turn'], 'black')

        # Test draw agreement
        draw_resp = self.client.post(
            '/api/draw/',
            data=json.dumps({'action': 'accept'}),
            content_type='application/json'
        )
        self.assertEqual(draw_resp.status_code, 200)
        self.assertTrue(draw_resp.json()['success'])
        self.assertEqual(draw_resp.json()['game_status'], 'draw')

        # ActiveGame record should be cleaned up after draw agreement
        self.assertFalse(ActiveGame.objects.filter(user=self.user, status='active').exists())

    def test_badge_generation_and_download(self):
        """Test generate_badge resolves template correctly and download_badge streams it."""
        self.client.login(username='chess_master', password='Password123!')
        achievement = Achievement.objects.create(
            code="FIRST_WIN",
            title="First Victory",
            description="Win your first chess game",
            rarity="common",
            category="tactics"
        )
        user_ach = UserAchievement.objects.create(
            user=self.user,
            achievement=achievement
        )

        badge_path = generate_badge(user_ach)
        self.assertTrue(badge_path.exists())

        dl_resp = self.client.get(f'/achievement/{achievement.id}/download/')
        self.assertEqual(dl_resp.status_code, 200)
        self.assertEqual(dl_resp['Content-Type'], 'image/png')

    def test_update_opening_progress_null_user(self):
        """Verify update_opening_progress returns tuple when user is None."""
        res = update_opening_progress(None, "Italian Game")
        self.assertEqual(res, (None, False))

    def test_award_xp_atomicity(self):
        """Verify award_xp correctly updates progress under atomic transaction."""
        prog = award_xp(self.user, 150)
        self.assertEqual(prog.xp, 150)
        self.assertEqual(prog.level, 2)

    def test_api_history_anonymous_no_session(self):
        """Unauthenticated client with no session receives empty games list."""
        anon_client = Client()
        resp = anon_client.get('/api/history/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"games": []})

    def test_api_history_authenticated_ordered(self):
        """Authenticated client receives history ordered by newest first."""
        self.client.login(username='chess_master', password='Password123!')
        rec1 = GameRecord.objects.create(
            user=self.user,
            session_key="test-session-1",
            white_label="Player1",
            black_label="AI",
            result="1-0",
            termination="checkmate",
            pgn="1. e4"
        )
        rec2 = GameRecord.objects.create(
            user=self.user,
            session_key="test-session-1",
            white_label="Player1",
            black_label="AI",
            result="0-1",
            termination="resignation",
            pgn="1. d4"
        )

        resp = self.client.get('/api/history/')
        self.assertEqual(resp.status_code, 200)
        games = resp.json()['games']
        self.assertEqual(len(games), 2)
        self.assertEqual(games[0]['id'], rec2.id)
        self.assertEqual(games[1]['id'], rec1.id)

    def test_analyze_game_view_requires_post(self):
        """GET request to /api/analyze-game/ must return 405 Method Not Allowed."""
        self.client.login(username='chess_master', password='Password123!')
        resp = self.client.get('/api/analyze-game/')
        self.assertEqual(resp.status_code, 405)
