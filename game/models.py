from django.db import models        
from django.conf import settings


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

    class Meta:
        ordering = ["-played_at"]

    def __str__(self):
        return f"{self.mode} | {self.winner} | {self.end_reason}"


class Opening(models.Model):
    """Chess opening from the ECO classification system.

    Each row stores a single position reachable via a standard opening
    line.  The ``fen`` field uses the same 3-field format produced by
    ``ChessGame.generate_fen_key()`` (board / side / castling rights)
    so lookups are a direct string comparison.
    """
    eco = models.CharField(max_length=10, help_text="ECO code, e.g. B20")
    name = models.CharField(max_length=255, help_text="Opening name")
    moves = models.TextField(help_text="SAN move sequence, e.g. '1. e4 c5'")
    fen = models.TextField(unique=True, db_index=True,
                           help_text="3-field FEN (board side castling)")
    move_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of half-moves to reach this position",
    )

    class Meta:
        ordering = ["eco", "move_count"]
        indexes = [
            models.Index(fields=["eco"], name="idx_opening_eco"),
        ]

    def __str__(self):
        return f"{self.eco} — {self.name}"
