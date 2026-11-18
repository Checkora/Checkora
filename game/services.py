import io
import time
import json
import logging
import os
from datetime import timedelta
from django.contrib.sessions.models import Session
from django.db import transaction
from django.contrib.auth import get_user_model
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from django.utils import timezone

from game.models import (
    ActiveGame,
    ChessPuzzle,
    GameRecord,
    GameResult,
    PuzzleSolve,
    PuzzleStats,
    Achievement,
    UserAchievement,
    OpeningProgress,
    validate_game_state,
    PlayerRating,
    RatingHistory,
    UserProgress,
)
from . import progression
from django.db.models import F

logger = logging.getLogger(__name__)

User = get_user_model()

# Placement, side to move, castling and en passant of the normal start.
STANDARD_START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"

# A win is "fast" when it took fewer full moves than this.
FAST_WIN_MOVES = 20


def is_rated_game(mode, initial_fen=None):
    """Only AI games played from the normal starting position are rated."""
    if mode != 'ai':
        return False
    fen = (initial_fen or '').strip()
    return not fen or ' '.join(fen.split()[:4]) == STANDARD_START


def _get_session_key(request):
    """Safely get session_key from request.session if present."""
    session = getattr(request, 'session', None)
    return getattr(session, 'session_key', None)


def load_game_state_helper(request):
    """
    Load game state for current request.
    Returns: (active_game_record, game_dict, current_version)
    For authenticated users, loads from ActiveGame database record.
    For anonymous users, loads from request.session['game'].
    """
    session_key = _get_session_key(request)

    if hasattr(request, 'user') and request.user.is_authenticated:
        active_game = ActiveGame.objects.filter(user=request.user, status="active").first()
        if not active_game and session_key:
            active_game = ActiveGame.objects.filter(session_key=session_key, status="active").first()
            if active_game:
                active_game.user = request.user
                active_game.save(update_fields=['user'])
        
        if active_game:
            if session_key and active_game.session_key != session_key:
                ActiveGame.objects.filter(session_key=session_key).exclude(pk=active_game.pk).delete()
                active_game.session_key = session_key
                active_game.save(update_fields=['session_key'])
            # Restore session metadata from the persisted game_state so that
            # cross-device resumes receive the correct difficulty, opening, and
            # player names even on a brand-new session with no prior context.
            metadata = (active_game.game_state or {}).get('metadata') if active_game.game_state else None
            if metadata and isinstance(metadata, dict) and hasattr(request, 'session') and request.session is not None:
                for key in ('difficulty', 'opening', 'white_name', 'black_name'):
                    if key in metadata and key not in request.session:
                        request.session[key] = metadata[key]
            return active_game, active_game.game_state, active_game.version
        return None, None, 0
    else:
        game_data = request.session.get('game') if hasattr(request, 'session') and request.session is not None else None
        return None, game_data, 0


def save_game_state_helper(request, active_game, game_dict, current_version, bump_version=True):
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
        elif hasattr(request, 'session') and 'game' in request.session and isinstance(request.session['game'], dict) and 'metadata' in request.session['game']:
            game_dict['metadata'] = request.session['game']['metadata']

    validate_game_state(game_dict)
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        if not request.session.session_key:
            request.session.save()
        
        if not active_game:
            if game_dict.get("game_status", "active") != "active":
                return True, None

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

        target_version = current_version + 1 if bump_version else current_version
        updated = ActiveGame.objects.filter(
            pk=active_game.pk,
            version=current_version
        ).update(
            game_state=game_dict,
            version=target_version,
            last_activity_at=timezone.now()
        )
        if updated == 0:
            return False, None
        
        active_game.version = target_version
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
    session_key = _get_session_key(request)
    if session_key:
        ActiveGame.objects.filter(
            session_key=session_key
        ).delete()

def outcome_for(winner, player_color):
    if winner == 'draw':
        return 'draw'
    return 'win' if winner == player_color else 'loss'


@transaction.atomic
def update_player_rating(user, winner, player_color, difficulty=None, game_result=None):
    """Apply one rated game against the engine and return 'win', 'draw' or 'loss'."""
    rating, _ = PlayerRating.objects.select_for_update().get_or_create(user=user)
    result = outcome_for(winner, player_color)

    old_rating = rating.rating
    change = progression.rating_change(
        old_rating, progression.engine_rating(difficulty), result, rating.games_played,
    )
    rating.rating = max(progression.RATING_FLOOR, old_rating + change)
    rating.games_played += 1
    if result == 'win':
        rating.wins += 1
    elif result == 'loss':
        rating.losses += 1
    else:
        rating.draws += 1
    rating.save()

    RatingHistory.objects.create(
        user=user,
        old_rating=old_rating,
        new_rating=rating.rating,
        rating_change=rating.rating - old_rating,
        result=result,
        game_result=game_result,
    )
    return result


@transaction.atomic
def process_game_completion(user, mode, winner, reason, player_color='white', moves=None,
                            rated=None, difficulty=None, counts_for_streak=True):
    """Record a finished game and everything it earns.

    Only AI games can be rated. Callers pass rated=False for AI games that
    must not move the rating, such as games from a custom position, and
    counts_for_streak=False when nobody played (the stale-game cleanup).
    A game too short to have really been played earns no streak and no XP.
    """
    moves = moves or []
    if rated is None:
        rated = True
    rated = bool(user) and mode == 'ai' and bool(rated)

    result = GameResult(
        user=user,
        mode=mode,
        winner=winner,
        end_reason=reason,
        player_color=player_color,
        moves=moves,
        rated=rated,
    )
    result.full_clean()
    result.save()

    if not user:
        return result

    played = len(moves) >= progression.STREAK_MIN_HALF_MOVES
    if counts_for_streak and played:
        progress, _ = UserProgress.objects.select_for_update().get_or_create(user=user)
        progress.record_play(progression.player_today(user))

    if rated:
        outcome = update_player_rating(user, winner, player_color, difficulty, game_result=result)
        if played:
            progression.award_xp(user, progression.XP_FOR_RESULT[outcome])

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
                        moves=game_data.get('move_history', []),
                        rated=is_rated_game(mode, game_data.get('initial_fen')),
                        difficulty=game_data.get('difficulty'),
                        # Walking away from a game is not playing one today.
                        counts_for_streak=False,
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
                    moves=game_data.get('move_history', []),
                    counts_for_streak=False,
                )

                active_game.delete()
                resigned_count += 1

    return deleted_count, resigned_count


def purge_expired_records():
    """Delete rows nothing can reach any more: expired replays and sessions."""
    now = timezone.now()
    records, _ = GameRecord.objects.filter(expires_at__lte=now).delete()
    sessions, _ = Session.objects.filter(expire_date__lt=now).delete()
    return records, sessions


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


# Achievement codes by the count that unlocks them.
WIN_MILESTONES = {1: "FIRST_WIN", 10: "WIN_10", 50: "WIN_50", 100: "WIN_100"}
PLAY_MILESTONES = {10: "PLAY_10", 20: "PLAY_20", 50: "PLAY_50", 100: "PLAY_100", 500: "PLAY_500"}
CHECKMATE_MILESTONES = {
    1: "FIRST_CHECKMATE", 5: "FIFTH_CHECKMATE", 10: "CHECKMATE_10", 20: "CHECKMATE_20",
    30: "CHECKMATE_30", 50: "CHECKMATE_50", 100: "CHECKMATE_100",
}
PUZZLE_MILESTONES = {
    1: "FIRST_PUZZLE", 10: "PUZZLE_10", 25: "PUZZLE_25", 50: "PUZZLE_50",
    75: "PUZZLE_75", 100: "PUZZLE_100", 200: "PUZZLE_200",
}
PUZZLE_STREAK_MILESTONES = (3, 7, 10, 30, 50, 100)


def _unlock_reached(user, count, milestones):
    for needed, code in milestones.items():
        if count >= needed:
            unlock_achievement(user, code)


def check_game_achievements(user):
    """Unlock the game achievements a player has earned. Runs after every finished game."""
    if not user:
        return

    _unlock_reached(user, GameResult.objects.filter(user=user).count(), PLAY_MILESTONES)

    # Results only count from rated games against the engine. In a
    # two-player game on one board the account plays both sides.
    rated_games = GameResult.objects.filter(user=user, mode="ai", rated=True)
    wins = rated_games.filter(winner=F("player_color"))

    _unlock_reached(user, wins.count(), WIN_MILESTONES)
    _unlock_reached(user, wins.filter(end_reason="checkmate").count(), CHECKMATE_MILESTONES)

    if rated_games.filter(end_reason="stalemate").exists():
        unlock_achievement(user, "STALEMATE_DRAW")

    # Win in under 20 moves. `moves` holds one entry per half-move.
    if any((len(moves) + 1) // 2 < FAST_WIN_MOVES for moves in wins.values_list("moves", flat=True)):
        unlock_achievement(user, "FAST_WIN")


def check_puzzle_achievements(user, stats):
    """Unlock the puzzle achievements a player has earned."""
    if not user:
        return
    _unlock_reached(user, stats.puzzles_solved, PUZZLE_MILESTONES)
    for length in PUZZLE_STREAK_MILESTONES:
        if stats.current_streak >= length:
            unlock_achievement(user, f"STREAK_{length}")


def daily_puzzle_for(day):
    """Return the puzzle served as the daily puzzle on `day`, or None."""
    puzzle = ChessPuzzle.objects.filter(date=day).first()
    if not puzzle:
        total_puzzles = ChessPuzzle.objects.count()
        if total_puzzles > 0:
            index = day.toordinal() % total_puzzles
            puzzle = ChessPuzzle.objects.order_by('id')[index]
    return puzzle


# Yesterday's daily puzzle still counts when it is solved this soon after
# midnight, so a player who loaded it at 23:58 is not cheated out of a day.
DAILY_PUZZLE_GRACE = timedelta(minutes=15)


def daily_puzzle_day(puzzle, now=None):
    """The day `puzzle` was the daily puzzle for, if solving it now counts for that day."""
    now = now or timezone.localtime()
    today = now.date()
    daily = daily_puzzle_for(today)
    if daily and daily.pk == puzzle.pk:
        return today
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now - midnight <= DAILY_PUZZLE_GRACE:
        yesterday = today - timedelta(days=1)
        previous = daily_puzzle_for(yesterday)
        if previous and previous.pk == puzzle.pk:
            return yesterday
    return None


def record_puzzle_solve(user, puzzle):
    """Count a solved puzzle once, keep the daily streak and award points.

    Returns (stats, newly_solved). The totals are worked out here so the
    client never reports its own numbers. The daily puzzle is the same for
    everyone and changes at midnight UTC, so its streak runs on UTC days.
    """
    daily_day = daily_puzzle_day(puzzle)
    xp = 0

    with transaction.atomic():
        stats, _ = PuzzleStats.objects.select_for_update().get_or_create(user=user)
        _, newly_solved = PuzzleSolve.objects.get_or_create(user=user, puzzle=puzzle)
        if newly_solved:
            stats.puzzles_solved += 1
            xp += progression.XP_PUZZLE

        if daily_day and (stats.last_daily_date is None or stats.last_daily_date < daily_day):
            if stats.last_daily_date == daily_day - timedelta(days=1):
                stats.current_streak += 1
            else:
                stats.current_streak = 1
            stats.best_streak = max(stats.best_streak, stats.current_streak)
            stats.daily_completions += 1
            stats.last_daily_date = daily_day
            xp += progression.XP_DAILY_PUZZLE

        stats.save()
        if xp:
            progression.award_xp(user, xp)

    check_puzzle_achievements(user, stats)
    return stats, newly_solved


BASE_DIR = Path(__file__).resolve().parent

def update_opening_progress(
    user,
    opening_name,
    correct_move=False,
    incorrect_move=False,
    completed=False,
    checkpoint=None,
    accuracy=None,
):
    if not user:
        return None, False

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
        elif completed:
            # Every finished run after the first counts as one more practice.
            progress.openings_started += 1

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
        elif accuracy is not None:
            # No per-move counts: keep the accuracy reported for this run.
            progress.accuracy_percentage = accuracy

        first_completion = False

        if completed:
            progress.completion_percentage = 100

            if progress.openings_completed == 0:
                progress.openings_completed = 1
                first_completion = True

        progress.save()

        return progress, first_completion

def _badge_font(size):
    """Pillow's built-in font at the given size, so no font file is needed."""
    return ImageFont.load_default(size=size)


def generate_badge(user_achievement):
    """Render the badge for an unlocked achievement and return it as PNG bytes.

    The image is drawn in memory: the deployment has no writable app directory.
    """
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

    title = achievement.title.upper()
    username = user_achievement.user.username

    # Handle long achievement names
    title_size = 85
    if len(title) > 22:
        title_size = 50
    elif len(title) > 15:
        title_size = 60

    # Handle long usernames
    name_size = 45 if len(username) > 15 else 60

    title_font = _badge_font(title_size)
    desc_font = _badge_font(38)
    award_font = _badge_font(32)
    name_font = _badge_font(name_size)

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

    buffer = io.BytesIO()
    badge.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


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
    if not isinstance(opening, dict):
        return []
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
    # The book also carries a "_named_lines_comment" string next to the lines.
    return {
        name for name, line in _load_named_lines().items()
        if isinstance(line, dict)
    }