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
        """generate_badge draws the PNG in memory and download_badge streams it."""
        from pathlib import Path
        from unittest import mock
        from PIL import ImageFont
        from game import services

        self.client.login(username='chess_master', password='Password123!')
        achievement, _ = Achievement.objects.update_or_create(
            code="FIRST_WIN",
            defaults={
                "title": "First Victory",
                "description": "Win your first chess game",
                "rarity": "common",
                "category": "gameplay",
            },
        )
        user_ach = UserAchievement.objects.create(
            user=self.user,
            achievement=achievement
        )

        # Older code wrote badges into this folder; it may still be around.
        badge_dir = Path(services.__file__).parent / 'generated_badges'
        files_before = sorted(badge_dir.glob('*')) if badge_dir.exists() else None

        with mock.patch.object(
            services.ImageFont, 'load_default', wraps=ImageFont.load_default
        ) as load_default:
            badge = generate_badge(user_ach)

        self.assertEqual(badge.read(8), b'\x89PNG\r\n\x1a\n')
        # Sized text from Pillow's own font: title, description, label, name.
        sizes = sorted(call.kwargs['size'] for call in load_default.call_args_list)
        self.assertEqual(sizes, [32, 38, 60, 85])
        # Nothing is written next to the code; the deployment cannot write there.
        files_after = sorted(badge_dir.glob('*')) if badge_dir.exists() else None
        self.assertEqual(files_before, files_after)

        dl_resp = self.client.get(f'/achievement/{achievement.id}/download/')
        self.assertEqual(dl_resp.status_code, 200)
        self.assertEqual(dl_resp['Content-Type'], 'image/png')
        self.assertIn('first-victory.png', dl_resp['Content-Disposition'])
        self.assertEqual(b''.join(dl_resp.streaming_content)[:8], b'\x89PNG\r\n\x1a\n')

    def test_badge_download_reports_a_missing_template(self):
        self.client.login(username='chess_master', password='Password123!')
        achievement, _ = Achievement.objects.update_or_create(
            code="FIRST_WIN", defaults={"title": "First Victory", "rarity": "nosuchrarity"},
        )
        UserAchievement.objects.create(user=self.user, achievement=achievement)

        with self.assertLogs('game.views', level='ERROR') as logs:
            response = self.client.get(f'/achievement/{achievement.id}/download/')

        self.assertEqual(response.status_code, 500)
        self.assertIn('Badge template not found', logs.output[0])

    def test_update_opening_progress_null_user(self):
        """Verify update_opening_progress returns tuple when user is None."""
        res = update_opening_progress(None, "Italian Game")
        self.assertEqual(res, (None, False))

    def test_award_xp_progression_level_calculation(self):
        """Verify award_xp correctly updates progress and calculates level."""
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
        """Authenticated client receives history ordered by newest created_at and id descending."""
        self.client.login(username='chess_master', password='Password123!')
        now = timezone.now()
        rec1 = GameRecord.objects.create(
            user=self.user,
            session_key="test-session-1",
            white_label="Player1",
            black_label="AI",
            result="1-0",
            termination="checkmate",
            pgn="1. e4",
        )
        rec2 = GameRecord.objects.create(
            user=self.user,
            session_key="test-session-1",
            white_label="Player1",
            black_label="AI",
            result="0-1",
            termination="resignation",
            pgn="1. d4",
        )
        GameRecord.objects.filter(pk__in=[rec1.pk, rec2.pk]).update(created_at=now)

        resp = self.client.get('/api/history/')
        self.assertEqual(resp.status_code, 200)
        games = resp.json()['games']
        self.assertEqual(len(games), 2)
        self.assertEqual(games[0]['id'], rec2.id)
        self.assertEqual(games[1]['id'], rec1.id)

    def test_logged_in_new_game_replaces_active_game(self):
        """Logged in user starting a new game replaces the active game and resets history."""
        self.client.login(username='chess_master', password='Password123!')
        move_resp = self.client.post(
            '/api/move/',
            json.dumps({'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4}),
            content_type='application/json'
        )
        self.assertEqual(move_resp.status_code, 200)

        state_resp = self.client.get('/api/state/')
        self.assertEqual(state_resp.status_code, 200)
        self.assertEqual(len(state_resp.json().get('move_history', [])), 1)

        new_game_resp = self.client.post(
            '/api/new-game/',
            json.dumps({'mode': 'pvp'}),
            content_type='application/json'
        )
        self.assertEqual(new_game_resp.status_code, 200)
        self.assertTrue(new_game_resp.json().get('valid'))

        state_after = self.client.get('/api/state/')
        self.assertEqual(state_after.status_code, 200)
        self.assertEqual(state_after.json().get('move_history', []), [])

    def test_analyze_game_view_requires_post(self):
        """GET request to /api/analyze-game/ must return 405 Method Not Allowed."""
        self.client.login(username='chess_master', password='Password123!')
        resp = self.client.get('/api/analyze-game/')
        self.assertEqual(resp.status_code, 405)

    def test_request_with_session_middleware(self):
        """Verify load_game_state_helper and record_game_result handle standard session middleware."""
        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware
        from game.views import record_game_result
        from game.services import load_game_state_helper, save_game_state_helper
        from game.engine import ChessGame

        factory = RequestFactory()
        req = factory.post('/api/move/')
        req.user = self.user
        SessionMiddleware(lambda r: None).process_request(req)
        req.session.save()

        # load_game_state_helper should return cleanly
        ag, game_dict, ver = load_game_state_helper(req)
        self.assertIsNone(ag)
        self.assertIsNone(game_dict)
        self.assertEqual(ver, 0)

        # save_game_state_helper should succeed
        valid_state = ChessGame().to_dict()
        saved, new_ag = save_game_state_helper(req, None, valid_state, 0)
        self.assertTrue(saved)
        self.assertIsNotNone(new_ag)

        # record_game_result should succeed
        res = record_game_result(req, 'pvp', 'white', 'checkmate', 'white')
        self.assertEqual(res.winner, 'white')

