from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model


User = get_user_model()


def avatar_upload_to(instance: "Avatar", filename: str) -> str:
    """Upload to a deterministic per-user path.

    The original filename is intentionally ignored to reduce edge cases.
    """
    return f"avatars/{instance.user_id}/{instance.user_id}.webp"


class Avatar(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="avatar")
    image = models.ImageField(upload_to=avatar_upload_to, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Avatar(user_id={self.user_id})"

    @property
    def has_avatar(self) -> bool:
        return bool(self.image)

    @property
    def url(self) -> str | None:
        return self.image.url if self.image else None


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
