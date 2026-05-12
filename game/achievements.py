from .models import Achievement, UserAchievement, UserProfile
from django.utils import timezone
from django.db import transaction

class AchievementEngine:
    @staticmethod
    def initialize_default_achievements():
        """Ensure default achievements exist in the database."""
        defaults = [
            {
                'name': 'First Victory',
                'description': 'Win your first chess match.',
                'category': 'gameplay',
                'rarity': 'common',
                'icon_name': 'trophy',
                'condition_type': 'total_wins',
                'threshold': 1
            },
            {
                'name': 'Grandmaster Aspirant',
                'description': 'Win 50 matches.',
                'category': 'gameplay',
                'rarity': 'epic',
                'icon_name': 'crown',
                'condition_type': 'total_wins',
                'threshold': 50
            },
            {
                'name': 'Turing Tester',
                'description': 'Defeat the AI 10 times.',
                'category': 'ai',
                'rarity': 'rare',
                'icon_name': 'cpu',
                'condition_type': 'total_ai_wins',
                'threshold': 10
            },
            {
                'name': 'On Fire',
                'description': 'Reach a win streak of 5.',
                'category': 'streak',
                'rarity': 'rare',
                'icon_name': 'flame',
                'condition_type': 'max_streak',
                'threshold': 5
            },
            {
                'name': 'Deep Blue Rival',
                'description': 'Defeat the AI on Hard difficulty.',
                'category': 'ai',
                'rarity': 'legendary',
                'icon_name': 'zap',
                'condition_type': 'total_ai_wins',  # We can specialize this later
                'threshold': 1
            },
            {
                'name': 'Consistent Player',
                'description': 'Play 100 games.',
                'category': 'gameplay',
                'rarity': 'epic',
                'icon_name': 'activity',
                'condition_type': 'total_games',
                'threshold': 100
            },
        ]
        for data in defaults:
            Achievement.objects.get_or_create(name=data['name'], defaults=data)

    @staticmethod
    def update_stats_and_check(user, game_result):
        """Update user profile stats and check for newly unlocked achievements."""
        if not user.is_authenticated:
            return []

        with transaction.atomic():
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.total_games += 1
            
            # Determine if user won
            user_won = (game_result.winner == game_result.player_color)
            user_draw = (game_result.winner == 'draw')

            if user_won:
                profile.total_wins += 1
                profile.current_streak += 1
                if profile.current_streak > profile.max_streak:
                    profile.max_streak = profile.current_streak
                if game_result.mode == 'ai':
                    profile.total_ai_wins += 1
            elif user_draw:
                profile.total_draws += 1
                # In this system, draw doesn't break the win streak but doesn't increase it.
                pass 
            else:
                profile.total_losses += 1
                profile.current_streak = 0
            
            profile.last_game_at = timezone.now()
            profile.save()

            # Check for new achievements
            new_unlocks = []
            # Prefetch achievements already unlocked to avoid repeated checks
            unlocked_ids = set(UserAchievement.objects.filter(user=user).values_list('achievement_id', flat=True))
            
            achievements = Achievement.objects.all()

            for ach in achievements:
                if ach.id in unlocked_ids:
                    continue
                
                # Check condition
                value = getattr(profile, ach.condition_type, 0)
                
                # Special handling for difficulty-based achievement
                if ach.name == 'Deep Blue Rival':
                    if game_result.mode == 'ai' and game_result.ai_difficulty == 'hard' and user_won:
                        UserAchievement.objects.create(user=user, achievement=ach)
                        new_unlocks.append(ach)
                    continue

                if value >= ach.threshold:
                    UserAchievement.objects.create(user=user, achievement=ach)
                    new_unlocks.append(ach)
            
            return new_unlocks
