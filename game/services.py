import time
from django.contrib.sessions.models import Session
from django.db import transaction
from django.contrib.auth import get_user_model
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from game.models import (
    GameResult,
    PuzzleStats,
    Achievement,
    UserAchievement,
)
from django.db.models import F

User = get_user_model()

def cleanup_stale_games():
    """
    Automated cleanup task for abandoned games.
    Iterates over all django_session records and applies rules to stale active games:
    Rule A (Low Engagement): < 5 moves -> hard deletion (remove game from session).
    Rule B (High Engagement): >= 5 moves -> auto-resign inactive player.
    """
    # 48 hours in seconds
    stale_threshold = time.time() - (48 * 3600)
    
    deleted_count = 0
    resigned_count = 0
    
    # Iterate over all sessions
    for session in Session.objects.iterator():
        try:
            session_data = session.get_decoded()
        except Exception:
            continue
            
        game_data = session_data.get('game')
        if not game_data or game_data.get('game_status') != 'active':
            continue
            
        last_ts = game_data.get('last_ts', 0)
        if last_ts > stale_threshold:
            continue
            
        moves_count = len(game_data.get('move_history', []))
        
        with transaction.atomic():
            if moves_count < 5:
                # Rule A: Hard deletion
                del session_data['game']
                session.session_data = Session.objects.encode(session_data)
                session.save()
                deleted_count += 1
            else:
                # Rule B: Auto-resignation
                current_turn = game_data.get('current_turn', 'white')
                player_color = game_data.get('player_color', 'white')
                mode = game_data.get('mode', 'pvp')
                
                # In AI mode, the human (player_color) is the inactive one
                # In PvP mode, the player whose turn it is is inactive
                if mode == 'ai':
                    winner = 'black' if player_color == 'white' else 'white'
                else:
                    winner = 'black' if current_turn == 'white' else 'white'
                
                game_data['game_status'] = 'resignation'
                session_data['game'] = game_data
                session.session_data = Session.objects.encode(session_data)
                session.save()
                
                # Create a GameResult historically linking to the user if auth is known
                user_id = session_data.get('_auth_user_id')
                user = User.objects.filter(pk=user_id).first() if user_id else None
                
                result = GameResult(
                    user=user,
                    mode=mode,
                    winner=winner,
                    end_reason='resign',
                    player_color=player_color,
                    moves=game_data.get('move_history', [])
                )
                result.full_clean()
                result.save()
                
                resigned_count += 1
                
    return deleted_count, resigned_count

# ==========================
# Achievement System
# ==========================

def unlock_achievement(user, code):
    """Unlock an achievement for a user."""
    if not user:
        return

    try:
        achievement = Achievement.objects.get(code=code)

        UserAchievement.objects.get_or_create(
            user=user,
            achievement=achievement
        )

    except Achievement.DoesNotExist:
        pass


def check_game_achievements(user):
    """Check and award achievements based on game statistics."""
    if not user:
        return

    total_games = GameResult.objects.filter(
        user=user
    ).count()

    wins = GameResult.objects.filter(
        user=user
    ).filter(
        winner=F("player_color")
    ).count()

    checkmates = GameResult.objects.filter(
        user=user,
        end_reason="checkmate",
        winner=F("player_color")
    ).count()

    stalemates = GameResult.objects.filter(
        user=user,
        end_reason="stalemate"
    ).count()

    fast_wins = GameResult.objects.filter(
        user=user
    ).filter(
        winner=F("player_color")
    )

    # First Win
    if wins >= 1:
        unlock_achievement(user, "FIRST_WIN")

    if wins >= 10:
        unlock_achievement(user, "WIN_10")

    if wins >= 50:
        unlock_achievement(user, "WIN_50")

    if wins >= 100:
        unlock_achievement(user, "WIN_100")

    # Games Played
    
    if total_games >= 10:
        unlock_achievement(user, "PLAY_10")

    if total_games >= 20:
        unlock_achievement(user, "PLAY_20")
    
    if total_games >= 50:
        unlock_achievement(user, "PLAY_50")
    
    if total_games >= 100:
        unlock_achievement(user, "PLAY_100")
        
    if total_games >= 500:
        unlock_achievement(user, "PLAY_500")

    # Checkmate
    if checkmates >= 1:
        unlock_achievement(user, "FIRST_CHECKMATE")

    if checkmates >= 5:
        unlock_achievement(user, "FIFTH_CHECKMATE")
    
    if checkmates >= 10:
        unlock_achievement(user, "CHECKMATE_10")
        
    if checkmates >= 20:
        unlock_achievement(user, "CHECKMATE_20")
    
    if checkmates >= 30:
        unlock_achievement(user, "CHECKMATE_30")
        
    if checkmates >= 50:
        unlock_achievement(user, "CHECKMATE_50")
    
    if checkmates >= 100:
        unlock_achievement(user, "CHECKMATE_100")

    # Stalemate
    if stalemates >= 1:
        unlock_achievement(user, "STALEMATE_DRAW")

    # Win in under 20 moves
    for game in fast_wins:
        if len(game.moves) < 20:
            unlock_achievement(user, "FAST_WIN")
            break


def check_puzzle_achievements(user, stats):
    """Check and award achievements based on puzzle progress."""
    if not user:
        return

    if stats.puzzles_solved >= 1:
        unlock_achievement(user, "FIRST_PUZZLE")
    
    if stats.puzzles_solved >= 10:
        unlock_achievement(user, "PUZZLE_10")

    if stats.puzzles_solved >= 25:
        unlock_achievement(user, "PUZZLE_25")
    
    if stats.puzzles_solved >= 50:
        unlock_achievement(user, "PUZZLE_50")
    
    if stats.puzzles_solved >= 75:
        unlock_achievement(user, "PUZZLE_75")
    
    if stats.puzzles_solved >= 100:
        unlock_achievement(user, "PUZZLE_100")
        
    if stats.puzzles_solved >= 200:
        unlock_achievement(user, "PUZZLE_200")
        
    if stats.current_streak >= 3:
        unlock_achievement(user, "STREAK_3")

    if stats.current_streak >= 7:
        unlock_achievement(user, "STREAK_7")
    
    if stats.current_streak >= 10:
        unlock_achievement(user, "STREAK_10")

    if stats.current_streak >= 30:
        unlock_achievement(user, "STREAK_30")
    
    if stats.current_streak >= 50:
        unlock_achievement(user, "STREAK_50")
    
    if stats.current_streak >= 100:
        unlock_achievement(user, "STREAK_100")


BASE_DIR = Path(__file__).resolve().parent


def generate_badge(user_achievement):
    achievement = user_achievement.achievement

    template_path = (
        BASE_DIR
        / "static"
        / "game"
        / "badges"
        / "templates"
        / f"{achievement.rarity}.png"
    )

    if not template_path.exists():
        raise FileNotFoundError(
            f"Badge template not found: {template_path}"
        )

    badge = Image.open(
        template_path
    ).convert("RGBA")

    draw = ImageDraw.Draw(badge)

    try:
        title_font = ImageFont.truetype(
            "C:/Windows/Fonts/georgiab.ttf",
            85
        )

        desc_font = ImageFont.truetype(
            "C:/Windows/Fonts/georgia.ttf",
            38
        )

        award_font = ImageFont.truetype(
            "C:/Windows/Fonts/georgiab.ttf",
            32
        )

        name_font = ImageFont.truetype(
            "C:/Windows/Fonts/georgiai.ttf",
            60
        )

    except Exception:
        title_font = ImageFont.load_default()
        desc_font = ImageFont.load_default()
        award_font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    title = achievement.title.upper()
    username = user_achievement.user.username

    # Handle long achievement names
    try:
        if len(title) > 15:
            title_font = ImageFont.truetype(
                "C:/Windows/Fonts/georgiab.ttf",
                60
            )

        if len(title) > 22:
            title_font = ImageFont.truetype(
                "C:/Windows/Fonts/georgiab.ttf",
                50
            )

        # Handle long usernames
        if len(username) > 15:
            name_font = ImageFont.truetype(
                "C:/Windows/Fonts/georgiai.ttf",
                45
            )

    except Exception:
        pass

    center_x = badge.width // 2

    # Achievement Title
    draw.text(
        (center_x, 675),
        title,
        fill="#0F2D62",
        font=title_font,
        anchor="mm"
    )

    # Description
    draw.text(
        (center_x, 760),
        achievement.description,
        fill="#444444",
        font=desc_font,
        anchor="mm"
    )

    # Awarded To
    draw.text(
        (center_x, 860),
        "Awarded To",
        fill="#B8860B",
        font=award_font,
        anchor="mm"
    )

    # Username
    draw.text(
        (center_x, 930),
        username,
        fill="#0F2D62",
        font=name_font,
        anchor="mm"
    )

    output_dir = BASE_DIR / "generated_badges"
    output_dir.mkdir(exist_ok=True)

    output_path = (
        output_dir /
        f"badge_{user_achievement.id}.png"
    )

    badge.save(output_path)

    return output_path
