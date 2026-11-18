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
from django.urls import reverse

from . import avatars


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
    # db_default keeps the column filled when code from before this field
    # writes a row, so the migration can run before the new code is deployed.
    rated = models.BooleanField(
        default=True,
        db_default=True,
        help_text="False for games that must not count towards rating or win achievements"
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
    last_daily_date = models.DateField(
        null=True,
        blank=True,
        help_text="Day the user last solved the daily puzzle"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(best_streak__gte=models.F("current_streak")),
                name="best_streak_gte_current_streak",
            ),
        ]

    def streak_on(self, day):
        """The daily-puzzle streak as it stands on `day`.

        A streak lapses once a whole day passes without the daily puzzle. That
        is worked out when it is read, so reading never writes, and a read
        racing a solve can't zero a streak that was just extended.
        """
        if self.last_daily_date and self.last_daily_date >= day - timedelta(days=1):
            return self.current_streak
        return 0

    def __str__(self):
        return f"{self.user.username} Puzzle Stats"


class PuzzleSolve(models.Model):
    """A puzzle the user has solved, recorded by the server."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="puzzle_solves"
    )
    puzzle = models.ForeignKey(
        'ChessPuzzle',
        on_delete=models.CASCADE,
        related_name="solves"
    )
    solved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "puzzle")

    def __str__(self):
        return f"{self.user.username} solved puzzle {self.puzzle_id}"


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

    day_streak = models.PositiveIntegerField(
        default=0
    )

    best_day_streak = models.PositiveIntegerField(default=0, db_default=0)

    last_played_date = models.DateField(
        null=True,
        blank=True
    )

    def record_play(self, day):
        """Count a game played on `day`, the player's own date.

        The caller holds this row with select_for_update.
        """
        if self.last_played_date == day:
            return
        if self.last_played_date == day - timedelta(days=1):
            self.day_streak += 1
        else:
            self.day_streak = 1
        self.best_day_streak = max(self.best_day_streak, self.day_streak)
        self.last_played_date = day
        self.save(update_fields=['day_streak', 'best_day_streak', 'last_played_date'])

    def streak_on(self, day):
        """The day streak as it stands on `day`; it lapses after a full day without a game."""
        if self.last_played_date and self.last_played_date >= day - timedelta(days=1):
            return self.day_streak
        return 0

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

    # The game that moved the rating. Empty for rows from before the link.
    game_result = models.ForeignKey(
        GameResult,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rating_changes",
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
    rating = models.IntegerField(
        default=1500,
        db_index=True,
        validators=[MinValueValidator(0), MaxValueValidator(3000)]
    )
    tags = models.CharField(max_length=255, blank=True, default="")
    date = models.DateField(
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Date when this puzzle should be served"
    )

    def clean(self):
        super().clean()
        if self.tags:
            self.tags = ",".join([t.strip() for t in self.tags.split(",") if t.strip()])
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
    pgn = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_expires_at_default, db_index=True)
    
    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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
        return f"Game {self.id} ({self.white_label} vs {self.black_label})"

def validate_game_state(value):
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValidationError("game_state must be a dictionary")
        
    required_keys = {'board', 'current_turn', 'white_time', 'black_time', 'last_ts'}
    missing = required_keys - value.keys()
    if missing:
        raise ValidationError(f"game_state missing required keys: {', '.join(sorted(missing))}")
        
    if value['current_turn'] not in ('white', 'black'):
        raise ValidationError("current_turn must be 'white' or 'black'")
        
    board = value['board']
    if not isinstance(board, list) or len(board) != 8 or not all(isinstance(row, list) and len(row) == 8 for row in board):
        raise ValidationError("board must be an 8x8 array")

class ActiveGame(models.Model):
    """Tracks active games for efficient cleanup."""

    class Meta:
        indexes = [
            models.Index(fields=["status", "last_activity_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="active", user__isnull=False),
                name="unique_active_game_per_user"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=0),
                name="activegame_version_gte_0"
            )
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

    last_activity_at = models.DateTimeField(
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

    game_state = models.JSONField(
        null=True,
        blank=True,
        validators=[validate_game_state]
    )

    version = models.IntegerField(
        default=0,
    )

    def __str__(self):
        return f"{self.session_key} ({self.status})"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Discussion(models.Model):
    CATEGORY_CHOICES = [
        ("general", "General"),
        ("puzzles", "Puzzles"),
        ("openings", "Openings"),
        ("feedback", "Feedback"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discussions"
    )

    title = models.CharField(max_length=200)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="general",
        db_index=True
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    category__in=["general", "puzzles", "openings", "feedback"]
                ),
                name="valid_discussion_category",
            ),
        ]

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
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

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
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} bookmarked {self.discussion.title}"
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
class ReplyVote(models.Model):
    UPVOTE = 1
    DOWNVOTE = -1

    VOTE_CHOICES = (
        (UPVOTE, "Upvote"),
        (DOWNVOTE, "Downvote"),
    )

    reply = models.ForeignKey(
        Reply,
        on_delete=models.CASCADE,
        related_name="votes"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reply_votes"
    )

    value = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("reply", "user")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.user.username} "
            f"{self.get_value_display().lower()}d reply {self.reply_id}"
        )

class UserProfile(models.Model):
    """Optional profile data for a user: their picture and when they last renamed.

    A picture is either one of the preset pieces in game.avatars or an
    upload, never both. An upload is stored as a base64 data URI so that it
    survives Vercel's ephemeral filesystem; see game.avatars for how it is
    served.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    # Stored as a base64 data URI. Empty string means no upload.
    avatar = models.TextField(blank=True, default="")
    # db_default on new NOT NULL columns lets the migration run before the
    # code that knows about them is deployed.
    avatar_preset = models.CharField(
        max_length=2, blank=True, default="", db_default="", choices=avatars.PRESETS,
    )
    # When the upload last changed. Its URL carries this, so browsers can
    # cache a picture for a year and still see a new one straight away. It
    # also says whether there is an upload without reading the column.
    avatar_updated_at = models.DateTimeField(null=True, blank=True)
    username_changed_at = models.DateTimeField(null=True, blank=True)
    # The IANA zone the player's browser reports, e.g. "Asia/Kolkata". Streak
    # days follow it, so a game at 1 am counts for the day the player is in.
    timezone = models.CharField(max_length=64, blank=True, default="", db_default="")

    def clean(self):
        super().clean()
        if 'avatar' in self.get_deferred_fields() or not self.avatar:
            return
        if not self.avatar.startswith("data:image/") or ";base64," not in self.avatar:
            raise ValidationError({"avatar": "Invalid avatar data URI."})
        if self.avatar_preset:
            raise ValidationError("A profile has an upload or a preset, not both.")

    def save(self, *args, **kwargs):
        if 'avatar' not in self.get_deferred_fields():
            # Keeps the flag right when the column is set directly, as the
            # admin does.
            if not self.avatar:
                self.avatar_updated_at = None
            elif self.avatar_updated_at is None:
                self.avatar_updated_at = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)

    def use_upload(self, data_uri):
        self.avatar = data_uri
        self.avatar_preset = ""
        self.avatar_updated_at = timezone.now()
        self.save()

    def use_preset(self, key):
        self.avatar = ""
        self.avatar_preset = key
        self.save()

    def clear_avatar(self):
        self.avatar = ""
        self.avatar_preset = ""
        self.save()

    @property
    def avatar_url(self):
        """Where the picture is, or "" for the initial-letter fallback.

        Reads only avatar_preset and avatar_updated_at, so lists can load
        profiles with .defer("avatar").
        """
        if self.avatar_preset:
            return avatars.preset_url(self.avatar_preset)
        if self.avatar_updated_at:
            version = int(self.avatar_updated_at.timestamp())
            return f"{reverse('user_avatar', args=[self.user_id])}?v={version}"
        return ""

    def __str__(self):
        return f"{self.user.username} Profile"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a UserProfile whenever a new User is saved."""
    if created:
        UserProfile.objects.get_or_create(user=instance)


class GoogleAccount(models.Model):
    """The Google account a player signs in with.

    ``sub`` is Google's permanent id for that account. People can change the
    address on a Google account, so ``email`` only records what Google sent
    when the two were linked, and sign-in never looks it up.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_account",
    )
    sub = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True, default="")
    linked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} (Google)"
