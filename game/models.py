from django.db import models
from django.conf import settings
from django.db.models import Q


class GameResult(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="game_results"
    )
    MODE_CHOICES = [("pvp", "PvP"), ("ai", "AI")]
    WINNER_CHOICES = [("white", "White"), ("black", "Black"), ("draw", "Draw")]
    END_REASON_CHOICES = [
        ("checkmate", "Checkmate"),
        ("stalemate", "Stalemate"),
        ("resign", "Resignation"),
        ("timeout", "Timeout"),
        ("agreement", "Agreement"),
        ("threefold_repetition", "Threefold Repetition"),
        ("fifty_move_rule", "Fifty-Move Rule"),
        ("insufficient_material", "Insufficient Material"),
    ]
    PLAYER_COLOR_CHOICES = [("white", "White"), ("black", "Black")]

    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    player_color = models.CharField(max_length=5, choices=PLAYER_COLOR_CHOICES, default="white")
    winner = models.CharField(max_length=10, choices=WINNER_CHOICES)
    end_reason = models.CharField(max_length=25, choices=END_REASON_CHOICES)
    played_at = models.DateTimeField(auto_now_add=True)
    moves = models.JSONField(
        default=list,
        blank=True,
        help_text="List of moves played during the game in chronological order"
    )

    class Meta:
        ordering = ["-played_at"]

    def __str__(self):
        return f"{self.mode} | {self.winner} | {self.end_reason}"

class PuzzleStats(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="puzzle_stats"
    )

    puzzles_solved = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )
    current_streak = models.PositiveIntegerField(default=0)
    best_streak = models.PositiveIntegerField(
        default=0,
        db_index=True
    )
    daily_completions = models.PositiveIntegerField(default=0)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(best_streak__gte=models.F("current_streak")),
                name="best_streak_gte_current_streak",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} Puzzle Stats"
    
    