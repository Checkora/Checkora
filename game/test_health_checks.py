from unittest.mock import MagicMock, patch

from django.db.utils import DatabaseError
from django.test import TestCase

from game.health_checks import (
    check_database,
    check_puzzles,
    check_achievements,
    check_lessons,
    check_openings,
)


class DatabaseHealthCheckTests(TestCase):
    """Tests for the database connectivity health check."""

    @patch("game.health_checks.connection.cursor")
    def test_check_database_success(self, mock_cursor):
        """Returns True when the database query executes successfully."""
        mock_context = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_context
        mock_context.execute.return_value = None

        self.assertTrue(check_database())

        mock_context.execute.assert_called_once_with("SELECT 1")

    @patch("game.health_checks.connection.cursor")
    def test_check_database_database_error(self, mock_cursor):
        """Returns False when a DatabaseError occurs."""
        mock_context = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_context
        mock_context.execute.side_effect = DatabaseError()

        self.assertFalse(check_database())

        mock_context.execute.assert_called_once_with("SELECT 1")

    @patch("game.health_checks.logger.exception")
    @patch("game.health_checks.connection.cursor")
    def test_check_database_unexpected_exception_logs_and_returns_false(
        self,
        mock_cursor,
        mock_logger,
    ):
        """Logs unexpected exceptions and returns False."""
        mock_context = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_context
        mock_context.execute.side_effect = RuntimeError("Unexpected failure")

        self.assertFalse(check_database())

        mock_context.execute.assert_called_once_with("SELECT 1")
        mock_logger.assert_called_once_with(
            "Unexpected error during database health check"
        )


class ModelHealthCheckTests(TestCase):
    """Tests for model-based health check functions."""

    def _assert_success(self, patch_target, health_check):
        with patch(patch_target) as mock_exists:
            mock_exists.return_value = False

            self.assertTrue(health_check())

            mock_exists.assert_called_once_with()

    def _assert_database_error(self, patch_target, health_check):
        with patch(patch_target) as mock_exists:
            mock_exists.side_effect = DatabaseError()

            self.assertFalse(health_check())

            mock_exists.assert_called_once_with()

    def _assert_unexpected_exception(
        self,
        patch_target,
        health_check,
        expected_log_message,
    ):
        with (
            patch(patch_target) as mock_exists,
            patch("game.health_checks.logger.exception") as mock_logger,
        ):
            mock_exists.side_effect = RuntimeError("Unexpected failure")

            self.assertFalse(health_check())

            mock_exists.assert_called_once_with()
            mock_logger.assert_called_once_with(expected_log_message)

    def test_check_puzzles_success(self):
        """Returns True when the puzzle health check succeeds."""
        self._assert_success(
            "game.health_checks.ChessPuzzle.objects.exists",
            check_puzzles,
        )

    def test_check_puzzles_database_error(self):
        """Returns False when the achievement health check raises DatabaseError."""
        self._assert_database_error(
            "game.health_checks.ChessPuzzle.objects.exists",
            check_puzzles,
        )

    def test_check_puzzles_unexpected_exception(self):
        """Logs unexpected exceptions and returns False."""
        self._assert_unexpected_exception(
            "game.health_checks.ChessPuzzle.objects.exists",
            check_puzzles,
            "Unexpected error during puzzle health check",
        )

    def test_check_achievements_success(self):
        """Returns True when the achievement health check succeeds."""
        self._assert_success(
            "game.health_checks.Achievement.objects.exists",
            check_achievements,
        )

    def test_check_achievements_database_error(self):
        """
        Returns False when the achievement health check raises
        DatabaseError.
        """
        self._assert_database_error(
            "game.health_checks.Achievement.objects.exists",
            check_achievements,
        )

    def test_check_achievements_unexpected_exception(self):
        """Logs unexpected exceptions and returns False."""
        self._assert_unexpected_exception(
            "game.health_checks.Achievement.objects.exists",
            check_achievements,
            "Unexpected error during achievement health check",
        )

    def test_check_lessons_success(self):
        """Returns True when the lesson health check succeeds."""
        self._assert_success(
            "game.health_checks.LessonProgress.objects.exists",
            check_lessons,
        )

    def test_check_lessons_database_error(self):
        """Returns False when the lesson health check raises DatabaseError."""
        self._assert_database_error(
            "game.health_checks.LessonProgress.objects.exists",
            check_lessons,
        )

    def test_check_lessons_unexpected_exception(self):
        """Logs unexpected exceptions and returns False."""
        self._assert_unexpected_exception(
            "game.health_checks.LessonProgress.objects.exists",
            check_lessons,
            "Unexpected error during lesson health check",
        )

    def test_check_openings_success(self):
        """Returns True when the opening trainer health check succeeds."""
        self._assert_success(
            "game.health_checks.OpeningProgress.objects.exists",
            check_openings,
        )

    def test_check_openings_database_error(self):
        """
        Returns False when the opening trainer health check raises
        DatabaseError.
        """
        self._assert_database_error(
            "game.health_checks.OpeningProgress.objects.exists",
            check_openings,
        )

    def test_check_openings_unexpected_exception(self):
        """Logs unexpected exceptions and returns False."""
        self._assert_unexpected_exception(
            "game.health_checks.OpeningProgress.objects.exists",
            check_openings,
            "Unexpected error during opening trainer health check",
        )
