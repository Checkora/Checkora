from django.db import models
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
)
from django.conf import settings
from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

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
    replay_record = models.ForeignKey(
                    'GameRecord', null=True, blank=True, on_delete=models.SET_NULL
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
    
class OpeningProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="opening_progress"
    )

    opening_name = models.CharField(
        max_length=100
    )

    openings_started = models.PositiveIntegerField(
        default=0
    )

    openings_completed = models.PositiveIntegerField(
        default=0
    )

    correct_moves = models.PositiveIntegerField(
        default=0
    )

    incorrect_moves = models.PositiveIntegerField(
        default=0
    )

    last_checkpoint = models.PositiveIntegerField(
        default=0
    )

    completion_percentage = models.FloatField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    accuracy_percentage = models.FloatField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    last_practiced = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        unique_together = (
            "user",
            "opening_name"
        )
        
        indexes = [
            models.Index(
                fields=[
                    "user",
                    "openings_completed",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "openings_started",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.opening_name}"
        )
         
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
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

def _expires_at_default():
    """Return a timestamp 48 hours from now."""
    return timezone.now() + timedelta(hours=48)


class GameRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, db_index=True)
    white_label = models.CharField(max_length=64, default="White")
    black_label = models.CharField(max_length=64, default="Black")
    result = models.CharField(max_length=7, default="*")
    termination = models.CharField(max_length=32, default="unknown")
    pgn = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_expires_at_default, db_index=True)
    
    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Game {self.id} ({self.white_label} vs {self.black_label})"

class ActiveGame(models.Model):
    """Tracks active games for efficient cleanup."""

    class Meta:
        indexes = [
            models.Index(fields=["status", "last_active"]),
        ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    session_key = models.CharField(
        max_length=40,
        unique=True,
    )

    last_active = models.DateTimeField(
        auto_now=True,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        default="active",
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.session_key} ({self.status})"

class Discussion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discussions"
    )

    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def hours_remaining(self):
        delta = self.expires_at - timezone.now()
        if delta.total_seconds() <= 0:
            return 0
        return int(delta.total_seconds() // 3600)

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def __str__(self):
        return self.title


class Reply(models.Model):
    discussion = models.ForeignKey(
        Discussion,
        on_delete=models.CASCADE,
        related_name="replies"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_replies"
    )

    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_replies"
    )  

    content = models.TextField()

    is_edited = models.BooleanField(default=False)  
    is_deleted = models.BooleanField(default=False)  

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        super().clean()
        if self.reply_to_id:
            if self.reply_to_id == self.pk:
                raise ValidationError({"reply_to": "a reply cannot reference itself."})
            if self.reply_to and self.reply_to.discussion_id != self.discussion_id:
                raise ValidationError({"reply_to": "reply_to must belong to the same discussion."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.discussion.title}"
    
class DiscussionBookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discussion_bookmarks"
    )

    discussion = models.ForeignKey(
        Discussion,
        on_delete=models.CASCADE,
        related_name="bookmarks"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "discussion")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} bookmarked {self.discussion.title}"
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class UserProfile(models.Model):
    """Stores optional profile data for a user, including their avatar.

    The avatar is stored as a base64-encoded data URI (e.g.
    ``data:image/jpeg;base64,...``) so that it persists correctly on
    Vercel's ephemeral serverless filesystem without requiring external
    object storage or a persistent MEDIA_ROOT directory.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    # Stored as a base64 data URI. Empty string means no avatar set.
    avatar = models.TextField(blank=True, default="")

    def clean(self):
        super().clean()
        if self.avatar:
            if not self.avatar.startswith("data:image/"):
                raise ValidationError({"avatar": "Invalid avatar data URI."})
            if ";base64," not in self.avatar:
                raise ValidationError({"avatar": "Invalid avatar data URI."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} Profile"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a UserProfile whenever a new User is saved."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
