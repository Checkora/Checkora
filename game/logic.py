import math
from .models import RatingHistory, Profile, Achievement, UserAchievement

def calculate_elo(rating_a, rating_b, score_a, k=32):
    """
    Calculate new Elo rating.
    score_a: 1 for win, 0.5 for draw, 0 for loss.
    """
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    new_rating_a = rating_a + k * (score_a - expected_a)
    return round(new_rating_a)

def update_game_ratings(game_result):
    """
    Update ratings for both players after a game.
    """
    if game_result.mode != 'pvp':
        # Handle AI ratings if needed, or just return
        return

    white = game_result.white_player
    black = game_result.black_player
    
    if not white or not black:
        return

    white_profile = white.profile
    black_profile = black.profile

    old_white_rating = white_profile.rating
    old_black_rating = black_profile.rating

    if game_result.winner == 'white':
        score_white = 1
        score_black = 0
    elif game_result.winner == 'black':
        score_white = 0
        score_black = 1
    else:
        score_white = 0.5
        score_black = 0.5

    new_white_rating = calculate_elo(old_white_rating, old_black_rating, score_white)
    new_black_rating = calculate_elo(old_black_rating, old_white_rating, score_black)

    # Update profiles
    white_profile.rating = new_white_rating
    if new_white_rating > white_profile.peak_rating:
        white_profile.peak_rating = new_white_rating
    white_profile.save()

    black_profile.rating = new_black_rating
    if new_black_rating > black_profile.peak_rating:
        black_profile.peak_rating = new_black_rating
    black_profile.save()

    # Save to GameResult
    game_result.white_rating_after = new_white_rating
    game_result.black_rating_after = new_black_rating
    game_result.save()

    # Record history
    RatingHistory.objects.create(user=white, rating=new_white_rating, game=game_result)
    RatingHistory.objects.create(user=black, rating=new_black_rating, game=game_result)

    # Check achievements
    check_achievements(white)
    check_achievements(black)

def check_achievements(user):
    """
    Check and unlock achievements for a user.
    """
    from django.db.models import Count
    profile = user.profile
    games_count = (user.games_as_white.count() + user.games_as_black.count())
    wins_count = (user.games_as_white.filter(winner='white').count() + 
                  user.games_as_black.filter(winner='black').count())

    # Achievement definitions (could be in DB, but for simplicity here)
    achievements_to_check = [
        {'name': 'First Steps', 'desc': 'Play your first game', 'check': games_count >= 1, 'icon': 'footprints'},
        {'name': 'Winner', 'desc': 'Win your first game', 'check': wins_count >= 1, 'icon': 'trophy'},
        {'name': 'Veteran', 'desc': 'Play 50 games', 'check': games_count >= 50, 'icon': 'award'},
        {'name': 'Centurion', 'desc': 'Play 100 games', 'check': games_count >= 100, 'icon': 'shield-check'},
        {'name': 'Master', 'desc': 'Reach 1500 rating', 'check': profile.rating >= 1500, 'icon': 'crown'},
    ]

    for ach_data in achievements_to_check:
        if ach_data['check']:
            ach, created = Achievement.objects.get_or_create(
                name=ach_data['name'],
                defaults={'description': ach_data['desc'], 'icon_name': ach_data['icon']}
            )
            UserAchievement.objects.get_or_create(user=user, achievement=ach)
