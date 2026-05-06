from django.db import models
from django.contrib.auth.models import User


class GameResult(models.Model):
    MODE_CHOICES = [("pvp", "PvP"), ("ai", "AI")]
    WINNER_CHOICES = [("white", "White"), ("black", "Black"), ("draw", "Draw")]
    END_REASON_CHOICES = [
        ("checkmate", "Checkmate"),
        ("stalemate", "Stalemate"),
        ("resign", "Resignation"),
        ("timeout", "Timeout"),
        ("agreement", "Agreement"),
    ]
    player = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='game_results',
    )
    
    player_color = models.CharField(max_length=5, null=True, blank=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    winner = models.CharField(max_length=10, choices=WINNER_CHOICES)
    end_reason = models.CharField(max_length=15, choices=END_REASON_CHOICES)
    played_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mode} | {self.winner} | {self.end_reason}"
