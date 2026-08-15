import json
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from game.models import UserProgress
from game.views import record_game_result

class StreakCounterTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.force_login(self.user)

    def test_first_completed_game_sets_streak_to_1(self):
        request = mock.MagicMock()
        request.user = self.user
        request.session = {}
        
        record_game_result(request, mode='pvp', winner='white', reason='checkmate', player_color='white', moves=[])
        
        progress = UserProgress.objects.get(user=self.user)
        self.assertEqual(progress.day_streak, 1)
        self.assertEqual(progress.last_played_date, timezone.localdate())

    def test_same_day_completed_games_no_increment(self):
        request = mock.MagicMock()
        request.user = self.user
        request.session = {}
        
        record_game_result(request, mode='pvp', winner='white', reason='checkmate', player_color='white', moves=[])
        progress = UserProgress.objects.get(user=self.user)
        self.assertEqual(progress.day_streak, 1)
        
        # Second game same day
        record_game_result(request, mode='pvp', winner='black', reason='resign', player_color='white', moves=[])
        progress.refresh_from_db()
        self.assertEqual(progress.day_streak, 1)

    def test_consecutive_day_increments_streak(self):
        request = mock.MagicMock()
        request.user = self.user
        request.session = {}
        
        # First game today
        record_game_result(request, mode='pvp', winner='white', reason='checkmate', player_color='white', moves=[])
        progress = UserProgress.objects.get(user=self.user)
        self.assertEqual(progress.day_streak, 1)
        
        # Manually set last played date to yesterday to simulate consecutive day
        yesterday = timezone.localdate() - timedelta(days=1)
        progress.last_played_date = yesterday
        progress.save()
        
        # Second game today
        record_game_result(request, mode='pvp', winner='white', reason='checkmate', player_color='white', moves=[])
        progress.refresh_from_db()
        self.assertEqual(progress.day_streak, 2)
        self.assertEqual(progress.last_played_date, timezone.localdate())

    def test_missed_day_resets_streak(self):
        request = mock.MagicMock()
        request.user = self.user
        request.session = {}
        
        record_game_result(request, mode='pvp', winner='white', reason='checkmate', player_color='white', moves=[])
        progress = UserProgress.objects.get(user=self.user)
        self.assertEqual(progress.day_streak, 1)
        
        # Set to 2 days ago
        progress.last_played_date = timezone.localdate() - timedelta(days=2)
        progress.day_streak = 5
        progress.save()
        
        # Game today
        record_game_result(request, mode='pvp', winner='white', reason='checkmate', player_color='white', moves=[])
        progress.refresh_from_db()
        self.assertEqual(progress.day_streak, 1)

    def test_authenticated_state_api_returns_persisted_day_streak(self):
        # Initial game to set streak
        progress, _ = UserProgress.objects.get_or_create(user=self.user)
        progress.day_streak = 3
        progress.save()
        
        response = self.client.get('/api/state/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('day_streak'), 3)

    def test_anonymous_behavior_api(self):
        self.client.logout()
        response = self.client.get('/api/state/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data.get('day_streak'))

