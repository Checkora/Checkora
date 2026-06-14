from django.db import models
from django.conf import settings
from django.db.models import Q
from django.core.exceptions import ValidationError

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


class UserProgress(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="progress"
    )

    xp = models.PositiveIntegerField(
        default=0,
        db_index=True
    )

    level = models.PositiveIntegerField(
        default=1,
        db_index=True
    )

    def __str__(self) -> str:
        return (
            f"{self.user.username} "
            f"(Level {self.level}, XP {self.xp})"
        )
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PlayerRating(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="player_rating"
    )

    rating = models.PositiveIntegerField(
        default=1200,
        db_index=True
    )

    games_played = models.PositiveIntegerField(
        default=0
    )

    wins = models.PositiveIntegerField(
        default=0
    )

    losses = models.PositiveIntegerField(
        default=0
    )

    draws = models.PositiveIntegerField(
        default=0
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    games_played=(
                        models.F("wins")
                        + models.F("losses")
                        + models.F("draws")
                    )
                ),
                name="games_played_matches_results",
            ),
        ]
        
    def __str__(self):
        return (
            f"{self.user.username} "
            f"(Rating {self.rating})"
        )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RatingHistory(models.Model):
    RESULT_CHOICES = [
        ("win", "Win"),
        ("loss", "Loss"),
        ("draw", "Draw"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rating_history"
    )

    old_rating = models.PositiveIntegerField()

    new_rating = models.PositiveIntegerField()

    rating_change = models.IntegerField()

    result = models.CharField(
        max_length=10,
        choices=RESULT_CHOICES
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.user.username} "
            f"{self.rating_change:+}"
        )

class LessonProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_progress"
    )

    lesson_name = models.CharField(
        max_length=100
    )

    completed = models.BooleanField(
        default=False
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        unique_together = (
            "user",
            "lesson_name"
        )

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.lesson_name}"
        )
        
class Achievement(models.Model):
    CATEGORY_CHOICES = [
        ("gameplay", "Gameplay"),
        ("puzzle", "Puzzle"),
        ("lessons", "Lessons"),
        ("streaks", "Streaks"),
        ("special", "Special Achievements"),
    ]

    RARITY_CHOICES = [
        ("common", "Common"),
        ("rare", "Rare"),
        ("epic", "Epic"),
        ("legendary", "Legendary"),
    ]

    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10)

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="gameplay"
    )

    rarity = models.CharField(
        max_length=20,
        choices=RARITY_CHOICES,
        default="common"
    )

    def __str__(self):
        return self.title
    
class UserAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE
    )

    unlocked_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = (
            "user",
            "achievement"
        )

    def __str__(self):
        return f"{self.user.username} - {self.achievement.title}"


class FeaturedBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="featured_badges"
    )

    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("user", "achievement")

    def __str__(self):
        return f"{self.user.username} - {self.achievement.title}"

    def save(self, *args, **kwargs):
        if not self.pk:
            count = FeaturedBadge.objects.filter(
                user=self.user
            ).count()

            if count >= 3:
                raise ValidationError(
                    "Users can only feature up to 3 badges"
                )

        self.full_clean()
        super().save(*args, **kwargs)


class ChessPuzzle(models.Model):
    title = models.CharField(max_length=200)
    fen = models.CharField(max_length=255)
    solution = models.JSONField(
        help_text=(
            "JSON array of moves representing the solution, "
            "e.g. ['g2g4']"
        )
    )
    difficulty = models.CharField(
        max_length=20,
        choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")],
        blank=True,
        default=""
    )
    date = models.DateField(
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Date when this puzzle should be served"
    )

    def clean(self):
        super().clean()
        if self.fen:
            parts = self.fen.split()
            if len(parts) < 4:
                raise ValidationError(
                    "Invalid FEN: must contain at least 4 fields: "
                    "placement, active color, castling, and en passant."
                )
            if len(parts[0].split('/')) != 8:
                raise ValidationError(
                    "Invalid FEN: piece placement must have exactly 8 ranks"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.difficulty or 'Unknown'})"
