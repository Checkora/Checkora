"""The engine levels a player can choose, and how long each may think."""

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from game import progression
from game.engine import ChessGame


def sent_budget(game, difficulty):
    """The time limit get_ai_move sends with BESTMOVE, in milliseconds."""
    with mock.patch.object(game, 'get_opening_book_move', return_value=None), \
            mock.patch.object(game, '_ask_engine', return_value=None) as ask:
        game.get_ai_move(difficulty=difficulty)
    return int(ask.call_args.args[0].split()[7])


class LevelsTest(TestCase):
    def test_every_level_has_a_rating(self):
        for level in ChessGame.LEVELS:
            with self.subTest(level=level):
                self.assertIn(level, progression.ENGINE_RATINGS)

    def test_levels_get_stronger(self):
        ratings = [progression.ENGINE_RATINGS[level] for level in ChessGame.LEVELS]
        self.assertEqual(ratings, sorted(ratings))
        budgets = [ChessGame.DIFFICULTY_SETTINGS[level]['time_budget_ms'] for level in ChessGame.LEVELS]
        self.assertEqual(budgets, sorted(budgets))

    def test_a_long_game_gives_master_its_full_time(self):
        game = ChessGame(time_limit=1800)
        expected = min(
            ChessGame.DIFFICULTY_SETTINGS['master']['time_budget_ms'],
            ChessGame.ANALYSIS_TIMEOUT_SECONDS * 1000 - ChessGame.REPLY_MARGIN_MS,
        )
        self.assertEqual(sent_budget(game, 'master'), expected)

    def test_a_low_clock_shortens_the_think(self):
        game = ChessGame(time_limit=180, increment=2)
        game.white_time = 30
        # 30 s left over 30 moves is a second, plus three quarters of the increment.
        self.assertEqual(sent_budget(game, 'master'), 1000 + 1500)

    def test_even_an_empty_clock_leaves_a_moment_to_move(self):
        game = ChessGame(time_limit=60)
        game.white_time = 0
        self.assertEqual(sent_budget(game, 'hard'), 100)


class MasterGameTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('player', 'p@example.com', 'x')
        self.client.force_login(self.user)

    def test_a_master_game_can_be_started(self):
        response = self.client.post(
            '/api/new-game/', data={'mode': 'ai', 'difficulty': 'master'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['difficulty'], 'master')
        self.assertEqual(self.client.session['black_name'], '♛ Master Queen')

    def test_an_unknown_level_falls_back_to_medium(self):
        self.client.post(
            '/api/new-game/', data={'mode': 'ai', 'difficulty': 'impossible'},
            content_type='application/json',
        )
        self.assertEqual(self.client.session['difficulty'], 'medium')

    def test_the_setup_screen_offers_master(self):
        self.assertContains(self.client.get('/play/'), '<option value="master">Master</option>', count=2)
