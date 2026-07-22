import time
import json
import logging
import os
from django.contrib.sessions.models import Session
from django.db import transaction
from django.contrib.auth import get_user_model
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from django.utils import timezone

from game.models import (
    ActiveGame,
    GameResult,
    PuzzleStats,
    Achievement,
    UserAchievement,
    OpeningProgress,
    validate_game_state,
    PlayerRating,
    RatingHistory,
    UserProgress,
)
from .rating_service import calculate_rating_change
from django.db.models import F

logger = logging.getLogger(__name__)

User = get_user_model()

def load_game_state_helper(request):
    """
    Load game state for current request.
    Returns: (active_game_record, game_dict, current_version)
    For authenticated users, loads from ActiveGame database record.
    For anonymous users, loads from request.session['game'].
    """
    if hasattr(request, 'user') and request.user.is_authenticated:
        active_game = ActiveGame.objects.filter(user=request.user, status="active").first()
        if not active_game and request.session.session_key:
            active_game = ActiveGame.objects.filter(session_key=request.session.session_key, status="active").first()
            if active_game:
                active_game.user = request.user
                active_game.save(update_fields=['user'])
        
        if active_game:
            if request.session.session_key and active_game.session_key != request.session.session_key:
                ActiveGame.objects.filter(session_key=request.session.session_key).exclude(pk=active_game.pk).delete()
                active_game.session_key = request.session.session_key
                active_game.save(update_fields=['session_key'])
            # Restore session metadata from the persisted game_state so that
            # cross-device resumes receive the correct difficulty, opening, and
            # player names even on a brand-new session with no prior context.
            metadata = (active_game.game_state or {}).get('metadata') if active_game.game_state else None
            if metadata and isinstance(metadata, dict):
                for key in ('difficulty', 'opening', 'white_name', 'black_name'):
                    if key in metadata and key not in request.session:
                        request.session[key] = metadata[key]
            return active_game, active_game.game_state, active_game.version
        return None, None, 0
    else:
        return None, request.session.get('game'), 0


def save_game_state_helper(request, active_game, game_dict, current_version):
    """
    Save game state for current request.
    For authenticated users, updates database ActiveGame record with optimistic locking.
    Returns True if successfully saved, False if optimistic locking conflict occurred.
    For anonymous users, saves to request.session['game'] and updates metadata tracker.
    """
    # Carry forward session metadata if it exists and hasn't been explicitly provided.
    # This prevents mutations (like moves) from wiping out the metadata dictionary.
    if 'metadata' not in game_dict:
        if active_game and active_game.game_state and 'metadata' in active_game.game_state:
            game_dict['metadata'] = active_game.game_state['metadata']
        elif 'game' in request.session and isinstance(request.session['game'], dict) and 'metadata' in request.session['game']:
            game_dict['metadata'] = request.session['game']['metadata']

    validate_game_state(game_dict)
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        if not request.session.session_key:
            request.session.save()
        
        if not active_game:
            with transaction.atomic():
                # Lock the user row to serialize concurrent replacements
                User.objects.select_for_update().get(pk=request.user.pk)

                ActiveGame.objects.filter(user=request.user).delete()
                ActiveGame.objects.filter(session_key=request.session.session_key).delete()
                active_game = ActiveGame.objects.create(
                    user=request.user,
                    session_key=request.session.session_key,
                    game_state=game_dict,
                    version=1,
                    status="active"
                )
                if 'game' in request.session:
                    del request.session['game']
                return True, active_game

        updated = ActiveGame.objects.filter(
            pk=active_game.pk,
            version=current_version
        ).update(
            game_state=game_dict,
            version=current_version + 1,
            last_activity_at=timezone.now()
        )
        if updated == 0:
            return False, None
        
        active_game.version = current_version + 1
        active_game.game_state = game_dict
        active_game.last_activity_at = timezone.now()
        
        if 'game' in request.session:
            del request.session['game']
        return True, active_game
    else:
        request.session['game'] = game_dict
        request.session.modified = True
        
        game_status = game_dict.get("game_status", "active")
        if game_status != "active":
            delete_active_game(request)
        else:
            if not request.session.session_key:
                request.session.save()
            ActiveGame.objects.update_or_create(
                session_key=request.session.session_key,
                defaults={
                    "user": None,
                    "status": "active",
                    "last_activity_at": timezone.now(),
                },
            )
        return True, None


def create_or_update_active_game(request, game_state):
    """Create or update an active game record (convenience wrapper)."""
    game_status = game_state.get("game_status", "active")
    if game_status != "active":
        delete_active_game(request)
        return

    active_game, _, version = load_game_state_helper(request)
    success_save, active_game_result = save_game_state_helper(request, active_game, game_state, version)
    return success_save, active_game_result


def delete_active_game(request):
    """Remove the active game record."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        ActiveGame.objects.filter(user=request.user).delete()
    if request.session.session_key:
        ActiveGame.objects.filter(
            session_key=request.session.session_key
        ).delete()

@transaction.atomic
def update_player_rating(user, winner, player_color):
    rating, _ = PlayerRating.objects.select_for_update().get_or_create(
        user=user
    )

    old_rating = rating.rating

    if winner == "draw":
        result = "draw"

    elif winner == player_color:
        result = "win"

    else:
        result = "loss"

    change = calculate_rating_change(result)

    new_rating = max(
        100,
        old_rating + change
    )

    actual_change = (
        new_rating - old_rating
    )
    rating.rating = new_rating
    rating.games_played += 1

    if result == "win":
        rating.wins += 1

    elif result == "loss":
        rating.losses += 1

    else:
        rating.draws += 1

    rating.full_clean()
    rating.save()

    RatingHistory.objects.create(
        user=user,
        old_rating=old_rating,
        new_rating=rating.rating,
        rating_change=actual_change,
        result=result
    )

@transaction.atomic
def process_game_completion(user, mode, winner, reason, player_color='white', moves=None):
    """Shared logic to finalize a game and update progressions."""
    if moves is None:
        moves = []
        
    result = GameResult(
        user=user,
        mode=mode,
        winner=winner,
        end_reason=reason,
        player_color=player_color,
        moves=moves
    )
    result.full_clean()
    result.save()

    if user:
        progress, _ = UserProgress.objects.select_for_update().get_or_create(user=user)
        progress.update_streak()

    if user and mode == 'ai':
        update_player_rating(
            user,
            winner,
            player_color
        )
        
        check_game_achievements(user)
        
    return result


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

    stale_games = ActiveGame.objects.filter(
        status="active",
        last_activity_at__lt=timezone.now() - timezone.timedelta(hours=48),
    )

    for stale_game in stale_games:
        # Authenticated user flow (database-backed state)
        if stale_game.user and stale_game.game_state:
            with transaction.atomic():
                active_game = ActiveGame.objects.select_for_update(skip_locked=True).filter(
                    pk=stale_game.pk,
                    status="active",
                    last_activity_at__lt=timezone.now() - timezone.timedelta(hours=48)
                ).first()

                if not active_game:
                    continue

                game_data = active_game.game_state
                moves_count = len(game_data.get('move_history', []))
                if moves_count < 5:
                    # Rule A: Hard deletion
                    active_game.delete()
                    deleted_count += 1
                else:
                    # Rule B: Auto-resignation
                    current_turn = game_data.get('current_turn', 'white')
                    player_color = game_data.get('player_color', 'white')
                    mode = game_data.get('mode', 'pvp')

                    if mode == 'ai':
                        winner = 'black' if player_color == 'white' else 'white'
                    else:
                        winner = 'black' if current_turn == 'white' else 'white'

                    process_game_completion(
                        user=active_game.user,
                        mode=mode,
                        winner=winner,
                        reason='resign',
                        player_color=player_color,
                        moves=game_data.get('move_history', [])
                    )

                    active_game.delete()
                    resigned_count += 1
            continue

        # Anonymous / Session-based flow (existing fallback behavior)
        with transaction.atomic():
            active_game = ActiveGame.objects.select_for_update(skip_locked=True).filter(
                pk=stale_game.pk,
                status="active",
                last_activity_at__lt=timezone.now() - timezone.timedelta(hours=48)
            ).first()

            if not active_game:
                continue

            try:
                session = Session.objects.get(
                    session_key=active_game.session_key
                )
                session_data = session.get_decoded()
            except Session.DoesNotExist:
                active_game.delete()
                deleted_count += 1
                continue
            except Exception:
                logger.warning("cleanup: failed decoding session %s", active_game.session_key)
                active_game.delete()
                deleted_count += 1
                continue

            game_data = session_data.get('game')
            if not game_data or not isinstance(game_data, dict):
                active_game.delete()
                deleted_count += 1
                continue

            last_ts = game_data.get('last_ts', 0)
            if last_ts > stale_threshold:
                continue

            moves_count = len(game_data.get('move_history', []))
            if moves_count < 5:
                # Rule A: Hard deletion
                active_game.delete()
                del session_data['game']
                session.session_data = Session.objects.encode(session_data)
                session.save()
                deleted_count += 1
            else:
                # Rule B: Auto-resignation
                current_turn = game_data.get('current_turn', 'white')
                player_color = game_data.get('player_color', 'white')
                mode = game_data.get('mode', 'pvp')

                if mode == 'ai':
                    winner = 'black' if player_color == 'white' else 'white'
                else:
                    winner = 'black' if current_turn == 'white' else 'white'

                game_data['game_status'] = 'resignation'
                session_data['game'] = game_data
                session.session_data = Session.objects.encode(session_data)
                session.save()

                process_game_completion(
                    user=None,
                    mode=mode,
                    winner=winner,
                    reason='resign',
                    player_color=player_color,
                    moves=game_data.get('move_history', [])
                )

                active_game.delete()
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

def update_opening_progress(
    user,
    opening_name,
    correct_move=False,
    incorrect_move=False,
    completed=False,
    checkpoint=None,
):
    if not user:
        return None

    with transaction.atomic():
        progress, created = (
            OpeningProgress.objects
            .select_for_update()
            .get_or_create(
                user=user,
                opening_name=opening_name,
            )
        )

        if created:
            progress.openings_started = 1
    
        if correct_move:
            progress.correct_moves += 1

        if incorrect_move:
            progress.incorrect_moves += 1

        if checkpoint is not None:
            progress.last_checkpoint = checkpoint
        
            progress.completion_percentage = min(
                100,
                checkpoint,
            )

        total_moves = (
            progress.correct_moves +
            progress.incorrect_moves
        )

        if total_moves > 0:
            progress.accuracy_percentage = round(
                (progress.correct_moves / total_moves) * 100,
                2
            )

        first_completion = False

        if completed and progress.openings_completed == 0:
            progress.openings_completed = 1
            first_completion = True

        progress.save()

        return progress, first_completion

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


_NAMED_LINES_CACHE = None


def _load_named_lines():
    global _NAMED_LINES_CACHE
    if _NAMED_LINES_CACHE is None:
        book_path = os.path.join(os.path.dirname(__file__), 'engine', 'opening_book.json')
        try:
            with open(book_path) as f:
                _NAMED_LINES_CACHE = json.load(f).get('_named_lines', {})
        except (OSError, json.JSONDecodeError):
            _NAMED_LINES_CACHE = {}
    return _NAMED_LINES_CACHE


def get_opening_line(name):
    """return full move list for a named opening, or empty list if not found"""
    lines = _load_named_lines()
    opening = lines.get(name, {})
    return opening.get('moves', [])[:]  # [:] copies so callers can't mutate the cache


def get_opening_reply(name, move_index, played_moves):
    """
    played_moves: list of (from_row, from_col, to_row, to_col) tuples
    actually played so far in the game.
    Returns None if the game has diverged from the book line.
    """
    moves = get_opening_line(name)
    if move_index >= len(moves):
        return None
    # normalize book moves to tuples for comparison against played_moves
    expected = [tuple(m) for m in moves[:move_index]]
    if list(played_moves) != expected:
        return None
    return moves[move_index]

def get_valid_openings():
    """return the set of opening names available in the book"""
    return set(_load_named_lines().keys())