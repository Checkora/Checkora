from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """Extends the user model to track aggregate statistics and streaks."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    total_wins = models.PositiveIntegerField(default=0)
    total_losses = models.PositiveIntegerField(default=0)
    total_draws = models.PositiveIntegerField(default=0)
    total_ai_wins = models.PositiveIntegerField(default=0)
    total_games = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    max_streak = models.PositiveIntegerField(default=0)
    last_game_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class Achievement(models.Model):
    """Metadata for achievements that can be earned by users."""
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]
    CATEGORY_CHOICES = [
        ('gameplay', 'Gameplay'),
        ('ai', 'AI Challenge'),
        ('streak', 'Streaks'),
        ('special', 'Special'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='gameplay')
    rarity = models.CharField(max_length=20, choices=RARITY_CHOICES, default='common')
    icon_name = models.CharField(max_length=50, help_text="CSS class or icon name")
    condition_type = models.CharField(max_length=50, help_text="e.g., 'wins', 'ai_wins', 'streak'")
    threshold = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    """Tracks which achievements a user has unlocked."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'achievement')

    def __str__(self):
        return f"{self.user.username} earned {self.achievement.name}"


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
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='game_results')
    opponent_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='opponent_game_results')
    player_color = models.CharField(max_length=10, choices=[('white', 'White'), ('black', 'Black')], default='white')
    ai_difficulty = models.CharField(max_length=10, null=True, blank=True)
    
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    winner = models.CharField(max_length=10, choices=WINNER_CHOICES)
    end_reason = models.CharField(max_length=15, choices=END_REASON_CHOICES)
    played_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mode} | {self.winner} | {self.end_reason}"
