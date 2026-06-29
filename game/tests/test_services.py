from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware

from game.models import (
    ActiveGame,
    GameResult,
    PuzzleStats,
    Achievement,
    UserAchievement,
    OpeningProgress,
)
from game.services import (
    create_or_update_active_game,
    delete_active_game,
    unlock_achievement,
    check_game_achievements,
    check_puzzle_achievements,
    update_opening_progress,
)

User = get_user_model()


class TestAchievementServices(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        # Seed achievements
        achievement_codes = [
            "FIRST_WIN", "WIN_10", "WIN_50", "WIN_100",
            "PLAY_10", "PLAY_20", "PLAY_50", "PLAY_100", "PLAY_500",
            "FIRST_CHECKMATE", "FIFTH_CHECKMATE", "CHECKMATE_10",
            "CHECKMATE_20", "CHECKMATE_30", "CHECKMATE_50", "CHECKMATE_100",
            "STALEMATE_DRAW", "FAST_WIN",
            "FIRST_PUZZLE", "PUZZLE_10", "PUZZLE_25", "PUZZLE_50", "PUZZLE_75", "PUZZLE_100", "PUZZLE_200",
            "STREAK_3", "STREAK_7", "STREAK_10", "STREAK_30", "STREAK_50", "STREAK_100"
        ]
        for code in achievement_codes:
            Achievement.objects.create(code=code, title=code, description=code, rarity="common")

    def test_unlock_achievement(self):
        # Verify no-op when user is None
        unlock_achievement(None, "FIRST_WIN")
        self.assertEqual(UserAchievement.objects.count(), 0)

        # Ignore unknown achievement codes
        unlock_achievement(self.user, "UNKNOWN_CODE")
        self.assertEqual(UserAchievement.objects.count(), 0)

        # Ensure a UserAchievement is created for a valid code
        unlock_achievement(self.user, "FIRST_WIN")
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="FIRST_WIN").exists()
        )

        # Calling the function multiple times should not create duplicates (get_or_create behavior)
        unlock_achievement(self.user, "FIRST_WIN")
        self.assertEqual(
            UserAchievement.objects.filter(user=self.user, achievement__code="FIRST_WIN").count(), 1
        )

    def test_check_game_achievements(self):
        # Ensure no-op when user is None
        check_game_achievements(None)
        self.assertEqual(UserAchievement.objects.count(), 0)

        # Create games: 9 wins (play total 9)
        for _ in range(9):
            GameResult.objects.create(
                user=self.user, mode="pvp", winner="white", end_reason="resign", player_color="white"
            )
        
        check_game_achievements(self.user)
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="FIRST_WIN").exists()
        )
        self.assertFalse(
            UserAchievement.objects.filter(user=self.user, achievement__code="WIN_10").exists()
        )
        self.assertFalse(
            UserAchievement.objects.filter(user=self.user, achievement__code="PLAY_10").exists()
        )

        # Add 1 more win to reach 10
        GameResult.objects.create(
            user=self.user, mode="pvp", winner="white", end_reason="resign", player_color="white"
        )
        check_game_achievements(self.user)
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="WIN_10").exists()
        )
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="PLAY_10").exists()
        )

        # Checkmates
        GameResult.objects.create(
            user=self.user, mode="pvp", winner="white", end_reason="checkmate", player_color="white"
        )
        check_game_achievements(self.user)
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="FIRST_CHECKMATE").exists()
        )

        # FAST_WIN should unlock only when the game is won in fewer than 20 moves
        GameResult.objects.create(
            user=self.user, mode="pvp", winner="white", end_reason="resign", player_color="white",
            moves=["e4"] * 19
        )
        check_game_achievements(self.user)
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="FAST_WIN").exists()
        )

        # Validate that >= 20 moves does not unlock FAST_WIN
        UserAchievement.objects.all().delete()
        GameResult.objects.all().delete()
        GameResult.objects.create(
            user=self.user, mode="pvp", winner="white", end_reason="resign", player_color="white",
            moves=["e4"] * 20
        )
        check_game_achievements(self.user)
        self.assertFalse(
            UserAchievement.objects.filter(user=self.user, achievement__code="FAST_WIN").exists()
        )


    def test_check_puzzle_achievements(self):
        stats = PuzzleStats.objects.create(user=self.user, puzzles_solved=9, current_streak=2, best_streak=2)
        
        # Verify no-op when user is None
        check_puzzle_achievements(None, stats)
        self.assertEqual(UserAchievement.objects.count(), 0)

        # Test boundaries
        check_puzzle_achievements(self.user, stats)
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="FIRST_PUZZLE").exists()
        )
        self.assertFalse(
            UserAchievement.objects.filter(user=self.user, achievement__code="PUZZLE_10").exists()
        )
        self.assertFalse(
            UserAchievement.objects.filter(user=self.user, achievement__code="STREAK_3").exists()
        )

        stats.puzzles_solved = 10
        stats.current_streak = 3
        stats.best_streak = 3
        stats.save()
        check_puzzle_achievements(self.user, stats)
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="PUZZLE_10").exists()
        )
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, achievement__code="STREAK_3").exists()
        )


class TestOpeningServices(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")

    def test_update_opening_progress(self):
        # Verify accuracy_percentage calculation
        progress, first = update_opening_progress(self.user, "Italian Game", correct_move=True)
        self.assertEqual(progress.correct_moves, 1)
        self.assertEqual(progress.accuracy_percentage, 100.0)
        self.assertFalse(first)

        progress, first = update_opening_progress(self.user, "Italian Game", incorrect_move=True)
        self.assertEqual(progress.correct_moves, 1)
        self.assertEqual(progress.incorrect_moves, 1)
        self.assertEqual(progress.accuracy_percentage, 50.0)

        # Ensure completion_percentage is capped at 100%
        progress, first = update_opening_progress(self.user, "Italian Game", checkpoint=120)
        self.assertEqual(progress.completion_percentage, 100.0)

        # openings_completed should increment only the first time an opening is completed
        progress, first = update_opening_progress(self.user, "Italian Game", completed=True)
        self.assertTrue(first)
        self.assertEqual(progress.openings_completed, 1)

        progress, first = update_opening_progress(self.user, "Italian Game", completed=True)
        self.assertFalse(first)
        self.assertEqual(progress.openings_completed, 1)

        # Newly created progress should initialize openings_started = 1
        progress2, first2 = update_opening_progress(self.user, "Ruy Lopez")
        self.assertEqual(progress2.openings_started, 1)

        # Verify no-op when user is None
        self.assertIsNone(update_opening_progress(None, "Sicilian Defense"))


class TestActiveGameServices(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="password")

    def test_create_or_update_active_game(self):
        request = self.factory.get("/")
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        request.user = self.user

        # Create a record for an active game
        create_or_update_active_game(request, {"game_status": "active"})
        self.assertTrue(ActiveGame.objects.filter(session_key=request.session.session_key).exists())
        
        active_game = ActiveGame.objects.get(session_key=request.session.session_key)
        self.assertEqual(active_game.user, self.user)
        self.assertEqual(active_game.status, "active")

        # Delete the record when game_status is not "active"
        create_or_update_active_game(request, {"game_status": "checkmate"})
        self.assertFalse(ActiveGame.objects.filter(session_key=request.session.session_key).exists())

        # Support anonymous session-based games
        request.user = type("AnonymousUser", (object,), {"is_authenticated": False})()
        create_or_update_active_game(request, {"game_status": "active"})
        anon_game = ActiveGame.objects.get(session_key=request.session.session_key)
        self.assertIsNone(anon_game.user)

    def test_delete_active_game(self):
        request = self.factory.get("/")
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        ActiveGame.objects.create(session_key=request.session.session_key, status="active")
        
        # Delete the active game when a session exists
        delete_active_game(request)
        self.assertFalse(ActiveGame.objects.filter(session_key=request.session.session_key).exists())

        # No-op when no session key exists (not saved yet)
        request2 = self.factory.get("/")
        middleware.process_request(request2)
        delete_active_game(request2)  # Should not raise exception
