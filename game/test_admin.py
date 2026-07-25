from django.test import TestCase
from django.contrib import admin
from game.models import (
    ChessPuzzle,
    UserProfile,
    GameResult,
    PlayerRating,
    RatingHistory,
    ActiveGame,
    Discussion,
    Reply,
    Achievement,
    UserAchievement,
    FeaturedBadge,
)


class AdminRegistrationTests(TestCase):
    def test_all_models_registered_in_admin(self):
        registered_models = [
            ChessPuzzle,
            UserProfile,
            GameResult,
            PlayerRating,
            RatingHistory,
            ActiveGame,
            Discussion,
            Reply,
            Achievement,
            UserAchievement,
            FeaturedBadge,
        ]
        for model in registered_models:
            with self.subTest(model=model.__name__):
                self.assertTrue(
                    admin.site.is_registered(model),
                    f"{model.__name__} should be registered in admin.site"
                )

    def test_admin_model_options(self):
        models_and_expected_fields = [
            (GameResult, ('id', 'user', 'mode', 'player_color', 'winner', 'end_reason', 'played_at')),
            (PlayerRating, ('user', 'rating', 'games_played', 'wins', 'losses', 'draws', 'updated_at')),
            (RatingHistory, ('user', 'old_rating', 'new_rating', 'rating_change', 'result', 'created_at')),
            (ActiveGame, ('session_key', 'user', 'status', 'version', 'last_activity_at', 'created_at')),
            (Discussion, ('title', 'user', 'category', 'created_at', 'updated_at')),
            (Reply, ('id', 'discussion', 'user', 'is_edited', 'is_deleted', 'created_at')),
            (Achievement, ('code', 'title', 'category', 'rarity', 'icon')),
            (UserAchievement, ('user', 'achievement', 'unlocked_at')),
            (FeaturedBadge, ('user', 'achievement')),
        ]
        for model, expected_list_display in models_and_expected_fields:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertEqual(model_admin.list_display, expected_list_display)
