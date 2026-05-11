from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_countries.fields import CountryField


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    country = CountryField(null=True, blank=True)
    rating = models.IntegerField(default=1200)
    peak_rating = models.IntegerField(default=1200)
    favorite_opening = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class Achievement(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon_name = models.CharField(max_length=50, help_text="Lucide icon name or emoji")
    
    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'achievement')


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
    
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    white_player = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='games_as_white')
    black_player = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='games_as_black')
    
    winner = models.CharField(max_length=10, choices=WINNER_CHOICES)
    end_reason = models.CharField(max_length=15, choices=END_REASON_CHOICES)
    
    white_rating_after = models.IntegerField(null=True, blank=True)
    black_rating_after = models.IntegerField(null=True, blank=True)
    
    pgn = models.TextField(blank=True)
    fen = models.CharField(max_length=100, blank=True)
    
    played_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mode} | {self.winner} | {self.end_reason} | {self.played_at.strftime('%Y-%m-%d %H:%M')}"


class RatingHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rating_history')
    rating = models.IntegerField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    game = models.ForeignKey(GameResult, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['recorded_at']
