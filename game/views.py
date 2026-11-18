"""Game views for the Checkora chess platform."""
import logging
import json
import time
from importlib import import_module
from functools import wraps
import hashlib
import math
import io
import base64
import ipaddress
import re
import secrets
from game.views_history import save_game_record
from django.http import HttpResponse, HttpResponseServerError
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.utils.http import (
    urlsafe_base64_encode,
    urlsafe_base64_decode,
    url_has_allowed_host_and_scheme
)
from django.core.paginator import Paginator, EmptyPage
from django.utils.encoding import (
    force_bytes,
    force_str
)
from django.utils.text import slugify
from . import progression
from .progression import award_xp
from .accounts import PENDING_REGISTRATION_MAX_AGE_SECONDS, pending_registrations
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.forms.utils import ErrorDict
from django.contrib.auth.views import PasswordResetView, redirect_to_login
from smtplib import SMTPException
from django.core.mail import (
    BadHeaderError,
    send_mail,
    EmailMultiAlternatives
)
from django.template.loader import render_to_string
from django.contrib import messages
from django.core.cache import cache, caches, DEFAULT_CACHE_ALIAS
from django.core.cache.backends.base import BaseCache
from django.db import IntegrityError, transaction
from django.db.models import F, Prefetch, Q, Sum
from .forms import CustomUserCreationForm
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import (
    require_GET,
    require_POST,
    require_http_methods,
)
from django.contrib.auth.decorators import login_required
from django.db import models

from django.db.models import Count, Avg, Max, Min, Window
from django.db.models.functions import Rank
from datetime import timedelta

from .opening_trainer_data import OPENINGS

from .engine import ChessGame
from .models import (
    PuzzleStats,
    LessonProgress,
    Achievement,
    UserAchievement,
    FeaturedBadge,
    UserProgress,
    ChessPuzzle,
    PlayerRating,
    RatingHistory,
    OpeningProgress,
    UserProfile,
)

from .models import Discussion, Reply, DiscussionBookmark, ReplyVote
from .forms import DiscussionForm, ReplyForm

logger = logging.getLogger(__name__)

# Brute force protection parameters
LOCKOUT_SECONDS = 900
USERNAME_MAX_FAILS = 10
IP_MAX_FAILS = 20

# Limits for game analysis
MAX_ANALYSIS_MOVES = 500
MAX_MOVE_LENGTH = 20

from game.services import (
    cleanup_stale_games,
    purge_expired_records,
    process_game_completion,
    is_rated_game,
    generate_badge,
    update_opening_progress,
    create_or_update_active_game,
    delete_active_game,
    get_opening_reply,
    get_valid_openings,
    load_game_state_helper,
    save_game_state_helper,
    daily_puzzle_for,
    record_puzzle_solve,
)

from django.http import FileResponse

from .analysis import detect_opening, match_opening
VALID_OPENINGS = get_valid_openings()

# Abandoning a rated game after this many half-moves counts as resigning it.
# The stale-game cleanup uses the same threshold.
ABANDON_MIN_MOVES = 5

PGN_RESULTS = {'white': '1-0', 'black': '0-1', 'draw': '1/2-1/2'}


def _json_object(request):
    """Return the request body as a dict, or None when it is not a JSON object."""
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def update_opening_metadata(game):
    match = match_opening([move["notation"] for move in game.move_history])
    game.opening_name, game.opening_moves = match if match else (None, None)


def landing(request):
    """Render the landing page introduction to Checkora."""
    return render(request, 'game/landing.html')


@ensure_csrf_cookie
def index(request):
    """Render the board, starting a game only when none is in progress."""
    if 'game' in request.session:
        game_data = request.session['game']
        status = game_data.get('game_status', 'active')
        if status != 'active':
            del request.session['game']

    has_game = 'game' in request.session
    if not has_game and request.user.is_authenticated:
        # A logged-in user's game lives in ActiveGame, never in the session.
        _, stored_game, _ = load_game_state_helper(request)
        has_game = bool(stored_game)

    if not has_game:
        game = ChessGame()
        request.session['game'] = game.to_dict()
        create_or_update_active_game(
            request,
            request.session['game']
        )

    avatar_url = ''
    if request.user.is_authenticated:
        profile = UserProfile.objects.defer('avatar').filter(user=request.user).first()
        avatar_url = profile.avatar_url if profile else ''
    return render(request, 'game/board.html', {'user_avatar_url': avatar_url})


def record_game_result(request, mode, winner, reason, player_color='white', moves=None, rated=None):
    """Save a completed game result to the database."""
    user = request.user if request.user.is_authenticated else None
    if moves is None:
        _, game_data, _ = load_game_state_helper(request)
        if not game_data:
            game_data = request.session.get('game')
        if game_data and isinstance(game_data, dict):
            moves = game_data.get('move_history', [])
        else:
            moves = []

    return process_game_completion(user, mode, winner, reason, player_color, moves, rated=rated)


def _pgn_with_result(pgn, result):
    """Write the real result into a PGN.

    generate_pgn() works the result out from the position, which is wrong for
    a resignation by the side not on move and unknown for a loss on time.
    """
    headers, _, movetext = pgn.partition("\n\n")
    headers = re.sub(r'\[Result "[^"]*"\]', f'[Result "{result}"]', headers, count=1)
    tokens = movetext.split(" ")
    tokens[-1] = result
    return headers + "\n\n" + " ".join(tokens)


def finish_game(request, game, winner, reason, rated=None):
    """Book a finished game: result, rating, replay record, cleanup.

    Every view that ends a game calls this after saving the final state.
    `rated=False` keeps an AI game out of the rating; by default AI games
    from the normal starting position are rated.
    """
    if rated is None:
        rated = is_rated_game(game.mode, getattr(game, 'initial_fen', None))

    white_name = request.session.get('white_name', 'White')
    black_name = request.session.get('black_name', 'Black')
    result = PGN_RESULTS[winner]

    game_result = record_game_result(
        request, game.mode, winner, reason, game.player_color,
        moves=game.move_history, rated=rated,
    )
    replay_record = save_game_record(
        request,
        pgn=_pgn_with_result(game.generate_pgn(white_name, black_name), result),
        result=result,
        termination='resignation' if reason == 'resign' else reason,
        white_label=white_name,
        black_label=black_name,
    )
    if game_result is not None and replay_record is not None:
        game_result.replay_record = replay_record
        game_result.save(update_fields=['replay_record'])

    delete_active_game(request)
    if request.user.is_authenticated:
        # A game carried over from before login must not be finished twice.
        request.session.pop('game', None)

    return game_result


def _end_on_time(request, game, active_game, version):
    """Finish a game whose clock has run out.

    Returns the winner, or None when the state could not be saved because
    another request changed the game first.
    """
    loser = 'white' if game.white_time <= 0 else 'black'
    winner = 'black' if loser == 'white' else 'white'
    game.game_status = 'timeout'

    saved, _ = save_game_state_helper(request, active_game, game.to_dict(), version)
    if not saved:
        return None

    # The engine's clock only runs out when the client holds back its move
    # request, so that never moves the rating.
    rated = False if (game.mode == 'ai' and loser != game.player_color) else None
    finish_game(request, game, winner, 'timeout', rated=rated)
    return winner


@require_POST
def make_move(request):
    """Validate and execute a chess move via the C++ engine."""
    try:
        data = json.loads(request.body)
        coords = ['from_row', 'from_col', 'to_row', 'to_col']
        for coord in coords:
            if coord not in data:
                return JsonResponse(
                    {"error": "Invalid board coordinates"},
                    status=400,
                )
            val = data[coord]
            if not isinstance(val, int) or isinstance(val, bool):
                return JsonResponse(
                    {"error": "Invalid board coordinates"},
                    status=400,
                )
            if not (0 <= val <= 7):
                return JsonResponse(
                    {"error": "Invalid board coordinates"},
                    status=400,
                )
        from_row = data['from_row']
        from_col = data['from_col']
        to_row = data['to_row']
        to_col = data['to_col']
        promotion_piece = data.get('promotion_piece', None)
        client_version = data.get('version', None)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse(
            {"error": "Invalid board coordinates"},
            status=400,
        )

    active_game, game_data, version = load_game_state_helper(request)
    
    if request.user.is_authenticated and client_version is not None and version != client_version:
        return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

    game = ChessGame.from_dict(game_data) if game_data else ChessGame()

    if (
        game.mode == 'ai'
        and game.game_status == 'active'
        and game.current_turn != game.player_color
    ):
        # Against the engine the client only moves its own side.
        return JsonResponse(
            {'valid': False, 'message': "It is the computer's turn."},
            status=403,
        )

    success, message, captured, game_status = game.make_move(
        from_row, from_col, to_row, to_col, promotion_piece,
    )

    winner = None
    if success:
        update_opening_metadata(game)
        success_save, active_game = save_game_state_helper(request, active_game, game.to_dict(), version)
        if not success_save:
            return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

        if game_status == 'checkmate':
            winner = 'black' if game.current_turn == 'white' else 'white'
            finish_game(request, game, winner, 'checkmate')
        elif game_status in ('stalemate', 'draw'):
            finish_game(request, game, 'draw', game.draw_reason or 'stalemate')
    elif game_status == 'timeout':
        winner = _end_on_time(request, game, active_game, version)
        if winner is None:
            return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

    res_version = active_game.version if (active_game and request.user.is_authenticated) else 0

    response_data = {
        'valid': success,
        'message': message,
        'captured': captured,
        'board': game.board,
        'current_turn': game.current_turn,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'time_limit': getattr(game, 'time_limit', 600),
        'increment': getattr(game, 'increment', 0),
        'move_history': game.move_history,
        'opening_name': getattr(game, 'opening_name', None),
        'opening_moves': getattr(game, 'opening_moves', None),
        'captured_pieces': game.captured,
        'game_status': game_status,
        'draw_reason': game.draw_reason,
        'threefold_warning': game.threefold_warning,
        'fen': game.generate_full_fen(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'white_name': request.session.get('white_name', 'White'),
        'black_name': request.session.get('black_name', 'Black'),
        'version': res_version
    }
    if game_status == 'timeout':
        response_data['winner'] = winner

    return JsonResponse(response_data)


@require_GET
def valid_moves(request):
    """Return every legal destination for a piece."""
    try:
        row = int(request.GET['row'])
        col = int(request.GET['col'])
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'valid_moves': []}, status=400)

    if not (0 <= row < 8 and 0 <= col < 8):
        return JsonResponse({'valid_moves': []}, status=400)

    _, game_data, _ = load_game_state_helper(request)
    if not game_data:
        game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'valid_moves': []})

    game = ChessGame.from_dict(game_data)
    moves = game.get_valid_moves(row, col)
    return JsonResponse({'valid_moves': moves})


def _forfeit_abandoned_game(request):
    """Record a rated game the user is walking away from.

    It counts as a resignation, or as a loss on time when a clock had
    already run out. Returns True when the game was recorded. Unrated games,
    and games with fewer than ABANDON_MIN_MOVES half-moves, are simply
    replaced.
    """
    if not request.user.is_authenticated:
        return False

    active_game, game_data, version = load_game_state_helper(request)
    if not game_data or game_data.get('game_status', 'active') != 'active':
        return False
    if not is_rated_game(game_data.get('mode'), game_data.get('initial_fen')):
        return False
    if len(game_data.get('move_history', [])) < ABANDON_MIN_MOVES:
        return False

    game = ChessGame.from_dict(game_data)

    game.update_clock()
    if min(game.white_time, game.black_time) <= 0:
        # The game was already decided on the clock, whoever's it was.
        return _end_on_time(request, game, active_game, version) is not None

    game.game_status = 'resignation'
    saved, _ = save_game_state_helper(request, active_game, game.to_dict(), version)
    if not saved:
        return False

    winner = 'black' if game.player_color == 'white' else 'white'
    finish_game(request, game, winner, 'resign')
    return True


@require_POST
def new_game(request):
    """Reset the game to the initial position with selected mode."""
    data = _json_object(request)
    if data is None:
        return JsonResponse({'valid': False, 'message': 'Invalid request data.'}, status=400)

    mode = data.get('mode', 'pvp')
    difficulty = data.get('difficulty', 'medium')
    if not isinstance(difficulty, str) or difficulty not in ('easy', 'medium', 'hard'):
        difficulty = 'medium'
    fen = data.get('fen')
    time_limit_raw = data.get('time_limit', 600)
    increment_raw = data.get('increment', 0)

    if isinstance(time_limit_raw, str) and '|' in time_limit_raw:
        try:
            parts = time_limit_raw.split('|')
            time_limit = max(60, min(18000, int(parts[0]) * 60))
            increment = max(0, min(180, int(parts[1])))
        except (ValueError, IndexError, TypeError):
            time_limit = 600
            increment = 0
    else:
        try:
            time_limit = int(time_limit_raw)
            time_limit = max(60, min(18000, time_limit))
        except (ValueError, TypeError, OverflowError):
            time_limit = 600

        try:
            increment = int(increment_raw)
            increment = max(0, min(180, increment))
        except (ValueError, TypeError, OverflowError):
            increment = 0

    if mode not in ('pvp', 'ai'):
        mode = 'pvp'
    player_color = data.get('player_color', 'white')
    if player_color == 'random':
        player_color = secrets.choice(['white', 'black'])
    elif player_color not in ('white', 'black'):
        player_color = 'white'

    # Build the new game before touching anything else, so a bad FEN
    # leaves the session and the game in progress as they were.
    fen = fen.strip() if isinstance(fen, str) else None
    if fen:
        try:
            game = ChessGame.from_fen(fen, time_limit=time_limit, increment=increment, difficulty=difficulty)
        except ValueError as exc:
            return JsonResponse(
                {'valid': False, 'message': f'Invalid FEN: {exc}'},
                status=400,
            )
    else:
        game = ChessGame(time_limit=time_limit, increment=increment, difficulty=difficulty)
    game.mode = mode
    game.player_color = player_color
    game.paused = False

    forfeited = _forfeit_abandoned_game(request)

    def _clean_name(raw, fallback):
        name = raw.strip() if isinstance(raw, str) else ''
        if not name or len(name) > 30:
            return fallback
        return name

    request.session['white_name'] = _clean_name(
        data.get('white_name'), 'White'
    )
    request.session['black_name'] = _clean_name(
        data.get('black_name'), 'Black'
    )
    request.session['difficulty'] = difficulty
    request.session['player_color'] = player_color

    if mode == 'ai':
        bot_names = {
            'easy': '♟️ Novice Pawn',
            'medium': '♗ Tactical Bishop',
            'hard': '♜ Grandmaster Rook'
        }
        bot_name = bot_names.get(difficulty, '♗ Tactical Bishop')
        if player_color == 'white':
            request.session['black_name'] = bot_name
        else:
            request.session['white_name'] = bot_name

    raw_opening = data.get('opening', '') if mode == 'ai' else ''
    opening = raw_opening if isinstance(raw_opening, str) and raw_opening in VALID_OPENINGS else ''
    request.session['opening'] = opening

    game_dict = game.to_dict()
    # Embed session metadata so it can be restored on a different device/session.
    # Stored under a 'metadata' sub-key inside the existing game_state JSONField;
    # no model change or migration is required.
    game_dict['metadata'] = {
        'difficulty': difficulty,
        'opening': opening,
        'white_name': request.session.get('white_name', 'White'),
        'black_name': request.session.get('black_name', 'Black'),
    }
    _success, active_game = save_game_state_helper(request, None, game_dict, 0)
    res_version = active_game.version if (active_game and request.user.is_authenticated) else 0

    return JsonResponse({
        'valid': True,
        'board': game.board,
        'current_turn': game.current_turn,
        'move_history': [],
        'captured_pieces': {'white': [], 'black': []},
        'mode': game.mode,
        'player_color': game.player_color,
        'white_name': request.session['white_name'],
        'black_name': request.session['black_name'],
        'difficulty': difficulty,
        'time_limit': getattr(game, 'time_limit', 600),
        'increment': getattr(game, 'increment', 0),
        'fen': game.generate_full_fen(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'game_status': game.game_status,
        'in_check': bool(getattr(game, 'in_check', False)),
        'draw_reason': game.draw_reason,
        'opening': opening,
        'version': res_version,
        'rated': request.user.is_authenticated and is_rated_game(game.mode, game.initial_fen),
        'forfeited': forfeited,
    })


@require_POST
def resume_game(request):
    """Resume the existing session game without resetting it."""
    active_game, game_data, version = load_game_state_helper(request)
    if not game_data:
        return JsonResponse({'valid': False, 'message': 'No saved game found.'}, status=404)

    game = ChessGame.from_dict(game_data)

    if game.game_status != 'active':
        return JsonResponse({'valid': False, 'message': 'No active game to resume.'}, status=404)

    game.paused = False
    game.last_ts = time.time()
    
    success_save, active_game = save_game_state_helper(request, active_game, game.to_dict(), version)
    if not success_save:
        return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

    res_version = active_game.version if (active_game and request.user.is_authenticated) else 0
    return JsonResponse({
        'valid': True,
        'board': game.board,
        'current_turn': game.current_turn,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'time_limit': getattr(game, 'time_limit', 600),
        'increment': getattr(game, 'increment', 0),
        'move_history': game.move_history,
        'captured_pieces': game.captured,
        'mode': game.mode,
        'player_color': game.player_color,
        'white_name': request.session.get('white_name', 'White'),
        'black_name': request.session.get('black_name', 'Black'),
        'game_status': game.game_status,
        'in_check': bool(getattr(game, 'in_check', False)),
        'draw_reason': game.draw_reason,
        'threefold_warning': game.threefold_warning,
        'fen': game.generate_full_fen(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'difficulty': request.session.get('difficulty', 'medium'),
        'version': res_version
    })


@require_GET
def check_promotion(request):
    """Return whether a planned move triggers pawn promotion."""
    try:
        from_row = int(request.GET['from_row'])
        from_col = int(request.GET['from_col'])
        to_row = int(request.GET['to_row'])
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'is_promotion': False})

    if not (0 <= from_row < 8 and 0 <= from_col < 8 and 0 <= to_row < 8):
        return JsonResponse({'is_promotion': False})

    _, game_data, _ = load_game_state_helper(request)
    if not game_data:
        game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'is_promotion': False})

    is_promo = ChessGame.is_promotion_move(
        game_data['board'], from_row, from_col, to_row,
    )
    return JsonResponse({'is_promotion': is_promo})


@require_GET
def get_state(request):
    """Return the full current game state.

    Reading the state never pauses the stored game. It can end it: when a
    clock has run out, the game is finished as a loss on time.
    """
    active_game, game_data, version = load_game_state_helper(request)
    auto_paused = False
    winner = None
    if not game_data:
        game_data = request.session.get('game')

    if not game_data:
        game = ChessGame()
    else:
        game = ChessGame.from_dict(game_data)

        elapsed = time.time() - game.last_ts
        if elapsed > 10 and not game.paused:
            # The tab was probably closed. Report the game as paused so the
            # page offers to resume without the lost time, but leave the
            # stored game alone: the client also reads the state mid-game.
            game.paused = True
            auto_paused = True
        else:
            game.update_clock()

    saved = True
    saved_ag = active_game
    flag_fell = (
        not auto_paused
        and game.game_status == 'active'
        and min(game.white_time, game.black_time) <= 0
    )
    if flag_fell:
        winner = _end_on_time(request, game, active_game, version)
        saved = winner is not None
    elif not auto_paused:
        saved, saved_ag = save_game_state_helper(
            request, active_game, game.to_dict(), version, bump_version=False
        )

    if not saved:
        # If a concurrent move updated the version, reload the authoritative state
        active_game, game_data, version = load_game_state_helper(request)
        if game_data:
            game = ChessGame.from_dict(game_data)
        saved_ag = active_game

    res_version = saved_ag.version if (saved_ag and request.user.is_authenticated) else version

    response_data = {
        'version': res_version,
        'board': game.board,
        'current_turn': game.current_turn,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'time_limit': getattr(game, 'time_limit', 600),
        'increment': getattr(game, 'increment', 0),
        'paused': game.paused,
        'move_history': game.move_history,
        'captured_pieces': game.captured,
        'mode': game.mode,
        'player_color': game.player_color,
        'difficulty': request.session.get('difficulty', 'medium'),
        'white_name': request.session.get('white_name', 'White'),
        'black_name': request.session.get('black_name', 'Black'),
        'fen': game.generate_full_fen(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'game_status': game.game_status,
        'in_check': bool(getattr(game, 'in_check', False)),
        'draw_reason': game.draw_reason,
        'threefold_warning': game.threefold_warning,
        'opening_name': getattr(game, 'opening_name', None),
        'opening_moves': getattr(game, 'opening_moves', None),
        'rated': request.user.is_authenticated and is_rated_game(
            game.mode, getattr(game, 'initial_fen', None)
        ),
    }
    if winner:
        response_data['winner'] = winner

    if request.user.is_authenticated:
        progress = UserProgress.objects.filter(user=request.user).first()
        response_data['day_streak'] = (
            progress.streak_on(progression.player_today(request.user)) if progress else 0
        )

    return JsonResponse(response_data)


@require_POST
def set_pause(request):
    """Toggle the game clock between paused and running."""
    active_game, game_data, version = load_game_state_helper(request)
    if not game_data:
        return JsonResponse({'paused': False})

    data = _json_object(request)
    if data is None:
        return JsonResponse({'valid': False, 'message': 'Invalid request data.'}, status=400)

    pause = bool(data.get('pause', True))

    game = ChessGame.from_dict(game_data)

    # Only deduct elapsed time when transitioning from running to paused.
    if pause and not game.paused:
        game.update_clock()
    game.paused = pause
    game.last_ts = time.time()

    success_save, active_game = save_game_state_helper(request, active_game, game.to_dict(), version)
    if not success_save:
        return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

    res_version = active_game.version if (active_game and request.user.is_authenticated) else 0

    return JsonResponse({
        'paused': game.paused,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'version': res_version
    })


@require_POST
def claim_timeout(request):
    """End the game on time once the server's own clock agrees it ran out.

    The client calls this when its clock reaches zero. The decision is made
    from the stored clock, not from anything the client sends.
    """
    active_game, game_data, version = load_game_state_helper(request)
    if not game_data:
        return JsonResponse({'valid': False, 'message': 'No active game.'}, status=400)

    game = ChessGame.from_dict(game_data)
    if game.game_status != 'active':
        return JsonResponse({'valid': False, 'message': 'Game is already over.'}, status=400)

    game.update_clock()
    if min(game.white_time, game.black_time) > 0:
        return JsonResponse({
            'valid': False,
            'message': 'Clock has not run out.',
            'white_time': game.white_time,
            'black_time': game.black_time,
        }, status=400)

    winner = _end_on_time(request, game, active_game, version)
    if winner is None:
        return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

    return JsonResponse({
        'valid': True,
        'game_status': 'timeout',
        'winner': winner,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'version': 0,
    })


@require_POST
def ai_move(request):
    """Let the engine compute and play the best move for the current side."""
    # Issue #1625: Rate-limit this endpoint to prevent computational DoS.
    # Apply both a per-user limit (for authenticated sessions) and a per-IP
    # limit (for anonymous or shared-IP scenarios), matching the pattern used
    # in analyze_game_view.
    window = getattr(settings, 'AI_MOVE_RATE_WINDOW_SECONDS', 60)
    ip = get_client_ip(request)
    ip_key = get_ai_move_rate_ip_key(ip)
    ip_count = increment_counter(ip_key, timeout=window)
    if ip_count > getattr(settings, 'AI_MOVE_IP_MAX_REQUESTS', 240):
        response = JsonResponse(
            {'error': 'Too many AI move requests. Please try again shortly.'},
            status=429,
        )
        response['Retry-After'] = str(window)
        return response
    if request.user.is_authenticated:
        user_key = get_ai_move_rate_user_key(request.user.id)
        user_count = increment_counter(user_key, timeout=window)
        if user_count > getattr(settings, 'AI_MOVE_USER_MAX_REQUESTS', 120):
            response = JsonResponse(
                {'error': 'Too many AI move requests. Please try again shortly.'},
                status=429,
            )
            response['Retry-After'] = str(window)
            return response

    data = _json_object(request) or {}
    client_version = data.get('version')

    active_game, game_data, version = load_game_state_helper(request)
    if request.user.is_authenticated and client_version is not None and version != client_version:
        return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

    if not game_data:
        err_msg = 'No active game.'
        return JsonResponse(
            {'valid': False, 'message': err_msg}, status=400
        )

    game = ChessGame.from_dict(game_data)

    if game.mode != 'ai':
        err_msg = 'Not in AI mode.'
        return JsonResponse(
            {'valid': False, 'message': err_msg}, status=400
        )

    if game.game_status != 'active':
        err_msg = 'Game is already over.'
        return JsonResponse(
            {'valid': False, 'message': err_msg}, status=400
        )

    if game.paused:
        err_msg = 'Game is paused.'
        return JsonResponse(
            {'valid': False, 'message': err_msg}, status=400
        )

    if game.current_turn == game.player_color:
        err_msg = "It is not the computer's turn."
        return JsonResponse(
            {'valid': False, 'message': err_msg}, status=400
        )

    opening = request.session.get('opening', '')
    book_move = None
    if opening:
        try:
            played = [
                (m['from'][0], m['from'][1], m['to'][0], m['to'][1])
                for m in game.move_history
            ]
            book_move = get_opening_reply(opening, len(played), played)
        except Exception:
            book_move = None

    if book_move:
        best = {
            'from_row': book_move[0],
            'from_col': book_move[1],
            'to_row':   book_move[2],
            'to_col':   book_move[3],
        }
        valid = game.get_valid_moves(best['from_row'], best['from_col'])
        if not any(m['row'] == best['to_row'] and m['col'] == best['to_col'] for m in valid):
            request.session['opening'] = ''
            request.session.modified = True
            best = game.get_ai_move()
    else:
        request.session['opening'] = ''
        request.session.modified = True
        best = game.get_ai_move()

    if not best:
        # get_ai_move() also returns None when the engine fails, so ask for
        # the position's status before calling the game over.
        status = game.check_game_status()
        if status == 'checkmate':
            winner = 'black' if game.current_turn == 'white' else 'white'
            reason = 'checkmate'
        elif status in ('stalemate', 'draw'):
            winner = 'draw'
            reason = 'stalemate' if status == 'stalemate' else 'insufficient_material'
            game.draw_reason = reason
        else:
            # The engine gave no answer. The game stays as it is.
            return JsonResponse(
                {'valid': False, 'message': 'The engine did not answer. Please try again.'},
                status=503,
            )

        game.game_status = status

        success_save, active_game = save_game_state_helper(request, active_game, game.to_dict(), version)
        if not success_save:
            return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

        finish_game(request, game, winner, reason)

        return JsonResponse({
            'valid': True,
            'game_status': status,
            'draw_reason': game.draw_reason,
            'board': game.board,
            'current_turn': game.current_turn,
            'white_time': game.white_time,
            'black_time': game.black_time,
            'move_history': game.move_history,
            'opening_name': getattr(game, 'opening_name', None),
            'opening_moves': getattr(game, 'opening_moves', None),
            'captured_pieces': game.captured,
            'message': '',
            'version': 0
        })

    # An anonymous game lives in the session, so a pause sent while the
    # engine was thinking only shows up there. Logged-in games are covered
    # by the version check when saving.
    anonymous = not request.user.is_authenticated
    engine = import_module(settings.SESSION_ENGINE)
    if anonymous:
        try:
            store = engine.SessionStore(session_key=request.session.session_key)
            latest_game = store.get('game', {})
        except Exception as e:
            logger.error(f"Failed to read session state during AI move: {e}")
            return JsonResponse({'valid': False, 'message': 'Internal error verifying game state.'}, status=500)

        if latest_game.get('paused'):
            err_msg = 'Game is paused.'
            return JsonResponse(
                {'valid': False, 'message': err_msg}, status=400
            )

    success, message, captured, game_status = game.make_move(
        best['from_row'], best['from_col'],
        best['to_row'], best['to_col'],
    )

    winner = None
    if success:
        update_opening_metadata(game)
        game_dict = game.to_dict()
        if anonymous:
            try:
                final_store = engine.SessionStore(session_key=request.session.session_key)
                final_game = final_store.get('game', {})
                game_dict['paused'] = final_game.get('paused', game.paused)
            except Exception as e:
                logger.error(f"Failed to read session state during AI save: {e}")
                return JsonResponse({'valid': False, 'message': 'Internal error saving game state.'}, status=500)

        success_save, active_game = save_game_state_helper(request, active_game, game_dict, version)
        if not success_save:
            return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

        if game_status == 'checkmate':
            winner = 'black' if game.current_turn == 'white' else 'white'
            finish_game(request, game, winner, 'checkmate')
        elif game_status in ('stalemate', 'draw'):
            finish_game(request, game, 'draw', game.draw_reason or 'stalemate')
    elif game_status == 'timeout':
        winner = _end_on_time(request, game, active_game, version)
        if winner is None:
            return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

    res_version = active_game.version if (active_game and request.user.is_authenticated) else 0

    response_data = {
        'valid': success,
        'message': message,
        'captured': captured,
        'board': game.board,
        'current_turn': game.current_turn,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'time_limit': getattr(game, 'time_limit', 600),
        'increment': getattr(game, 'increment', 0),
        'move_history': game.move_history,
        'opening_name': getattr(game, 'opening_name', None),
        'opening_moves': getattr(game, 'opening_moves', None),
        'captured_pieces': game.captured,
        'ai_move': best,
        'game_status': game_status,
        'draw_reason': game.draw_reason,
        'threefold_warning': game.threefold_warning,
        'fen': game.generate_full_fen(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'white_name': request.session.get('white_name', 'White'),
        'black_name': request.session.get('black_name', 'Black'),
        'opening': request.session.get('opening', ''),
        'version': res_version
    }
    if game_status == 'timeout':
        response_data['winner'] = winner

    return JsonResponse(response_data)

@require_POST
def offer_draw(request):
    """Handle draw offers and agreements."""
    active_game, game_data, version = load_game_state_helper(request)
    if not game_data:
        game_data = request.session.get('game')
    if not game_data:
        return JsonResponse(
            {'success': False, 'message': 'No active game.'}, status=400
        )

    data = _json_object(request)
    if data is None:
        return JsonResponse(
            {'valid': False, 'message': 'Invalid request data.'}, status=400
        )

    action = data.get('action')

    if action not in ('offer', 'accept', 'decline'):
        return JsonResponse(
            {'success': False, 'message': 'Invalid action.'}, status=400
        )

    if action == 'accept':
        game = ChessGame.from_dict(game_data)
        if game.game_status != 'active':
            return JsonResponse(
                {'success': False, 'message': 'Game is not active.'}, status=400
            )
        if game.mode != 'pvp':
            # The engine never offers or accepts a draw, and a draw against
            # it would move the rating.
            return JsonResponse(
                {
                    'success': False,
                    'message': 'Draws by agreement are only available in two-player games.',
                },
                status=400,
            )
        game.game_status = 'draw'
        game.draw_reason = 'agreement'
        saved, _ = save_game_state_helper(request, active_game, game.to_dict(), version)
        if not saved:
            return JsonResponse({'error': 'State conflict, please retry'}, status=409)

        finish_game(request, game, 'draw', 'agreement')
        return JsonResponse({
            'success': True,
            'game_status': game.game_status,
            'draw_reason': game.draw_reason,
        })

    return JsonResponse({'success': True})

@require_POST
def resign_game(request):
    """Handle a player resigning the game."""
    active_game, game_data, version = load_game_state_helper(request)
    if not game_data:
        return JsonResponse({'valid': False, 'message': 'No active game.'}, status=400)

    game = ChessGame.from_dict(game_data)

    if game.game_status != 'active':
        return JsonResponse({'valid': False, 'message': 'Game is already over.'}, status=400)

    data = _json_object(request) or {}
    resigning_player = data.get('resigning_player')

    if game.mode == 'ai':
        # Against the engine only the human can resign, whatever was sent.
        resigning_player = game.player_color
    elif resigning_player not in ('white', 'black'):
        resigning_player = game.current_turn

    winner = 'black' if resigning_player == 'white' else 'white'
    game_status = 'resignation'

    game.game_status = game_status

    success_save, active_game = save_game_state_helper(request, active_game, game.to_dict(), version)
    if not success_save:
        return JsonResponse({'error': 'Conflict: Stale game state.'}, status=409)

    finish_game(request, game, winner, 'resign')

    return JsonResponse({
        'valid': True,
        'message': f'{resigning_player.capitalize()} resigned.',
        'winner': winner,
        'game_status': game_status,
        'version': 0
    })

@require_GET
def check_username(request):
    """Check if a username is already taken.

    Checks both active and inactive users to avoid leaking
    whether a pending-verification account exists.
    """
    username = request.GET.get('username', '').strip()
    if not username:
        return JsonResponse({'available': False, 'error': 'No username provided'}, status=400)
    exists = User.objects.filter(username__iexact=username).exists()
    return JsonResponse({'available': not exists})


REGISTRATION_SESSION_KEYS = (
    'registration_user_id',
    'registration_otp_hash',
    'registration_password',
    'otp_created_at',
    'registration_email',
    'otp_failed_attempts',
)

# One verification mail per address in this window, register and resend alike.
REGISTRATION_EMAIL_COOLDOWN_SECONDS = 60

GENERIC_REGISTRATION_MESSAGE = (
    'If your details are valid, a verification '
    'code has been sent to your email.'
)


def _registration_cooldown_key(email):
    digest = hashlib.sha256(email.lower().strip().encode()).hexdigest()
    return f"reg_otp_cooldown_{digest}"


def _registration_email_allowed(email):
    """Claim the right to mail this address; False while the cooldown runs."""
    return cache.add(
        _registration_cooldown_key(email), 1,
        timeout=REGISTRATION_EMAIL_COOLDOWN_SECONDS,
    )


def _dummy_registration(request, email):
    """Answer like a real registration without creating or mailing anything.

    The session gets a code nobody knows, so the verify page renders and
    never succeeds. The response does not show whether the details exist.
    """
    request.session['registration_user_id'] = -1
    request.session['registration_email'] = email
    request.session.pop('registration_password', None)
    dummy_otp = str(secrets.randbelow(900000) + 100000)
    request.session['registration_otp_hash'] = hashlib.sha256(
        f"{dummy_otp}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    request.session['otp_created_at'] = time.time()
    messages.success(request, GENERIC_REGISTRATION_MESSAGE)
    return redirect('verify_otp')


def _clear_registration_session(request):
    """Clear all registration-related keys from the session and cache."""
    user_id = request.session.get('registration_user_id')
    if user_id and user_id != -1:
        cache.delete(f"otp_failed_attempts_user_{user_id}")
    else:
        cache.delete(f"otp_failed_attempts_session_{request.session.session_key}")

    for key in REGISTRATION_SESSION_KEYS:
        request.session.pop(key, None)


def register_view(request):
    """Handle new user registration with OTP email verification."""
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']

            # Concurrency: serialize registration requests for the same email
            # using a lightweight, synchronized cache lock.
            email_lock_key = f"reg_lock_email_{hashlib.sha256(email.lower().strip().encode()).hexdigest()}"
            lock_acquired = cache.add(email_lock_key, "locked", timeout=10)
            if not lock_acquired:
                # Concurrent request in progress — return the same generic redirect.
                return _dummy_registration(request, email)

            is_new_user = False
            try:
                # Security: detect conflicts with existing accounts inside
                # an atomic block to eliminate race conditions between the
                # check and the subsequent insert.
                with transaction.atomic():
                    identity = Q(username__iexact=username) | Q(email__iexact=email)

                    # A signup that was never verified stops holding its
                    # username and email once the window has passed.
                    stale_before = timezone.now() - timedelta(
                        seconds=PENDING_REGISTRATION_MAX_AGE_SECONDS
                    )
                    pending_registrations().filter(
                        identity, date_joined__lt=stale_before
                    ).delete()

                    # Verified accounts are never touched from here, and
                    # that includes accounts an admin has deactivated.
                    established_conflict = User.objects.filter(identity).exclude(
                        is_active=False, last_login__isnull=True
                    ).select_for_update().exists()

                    if established_conflict:
                        # Return the same generic response as a successful
                        # registration so attackers cannot distinguish
                        # between "email/username exists" and "new account".
                        return _dummy_registration(request, email)

                    inactive_candidates = list(
                        pending_registrations().select_for_update().filter(identity)
                    )
                    exact_inactive_matches = [
                        u for u in inactive_candidates
                        if u.username.lower() == username.lower()
                        and u.email.lower() == email.lower()
                    ]

                    # If there are matching inactive accounts but none is a full identity match,
                    # trigger the generic dummy flow to prevent hijacking/enumeration.
                    if inactive_candidates and len(exact_inactive_matches) != 1:
                        return _dummy_registration(request, email)

                    inactive_user = exact_inactive_matches[0] if exact_inactive_matches else None

                    if inactive_user:
                        user = inactive_user
                        user.username = username
                        user.email = email
                        # A fresh attempt restarts the verification window.
                        user.date_joined = timezone.now()
                        user.full_clean(validate_unique=False)
                        user.save()
                    else:
                        try:
                            user = form.save(commit=False)
                            user.is_active = False
                            user.full_clean(validate_unique=False)
                            user.save()
                            is_new_user = True
                        except IntegrityError:
                            # Concurrent insert beat us despite the atomic
                            # block — return the same generic message.
                            return _dummy_registration(request, email)

                # The password picked in this browser is applied when this
                # browser verifies its code. Someone else registering the
                # same details in between cannot swap it.
                request.session['registration_password'] = make_password(
                    form.cleaned_data['password1']
                )

                if not _registration_email_allowed(email):
                    # A code went to this address moments ago, so nothing
                    # new is sent. A browser that holds that code keeps it.
                    if request.session.get('registration_user_id') != user.id:
                        return _dummy_registration(request, email)
                    messages.success(request, GENERIC_REGISTRATION_MESSAGE)
                    return redirect('verify_otp')

                # Generate 6-digit OTP
                otp = str(secrets.randbelow(900000) + 100000)
                request.session['registration_user_id'] = user.id
                # Hash OTP with SECRET_KEY as salt to prevent reading from signed cookies
                otp_hash = hashlib.sha256(
                    f"{otp}:{settings.SECRET_KEY}".encode()
                ).hexdigest()
                request.session['registration_otp_hash'] = otp_hash
                request.session['otp_created_at'] = time.time()
                request.session['last_otp_time'] = time.time()

                missing_email_credentials = (
                    not settings.EMAIL_HOST_USER or
                    not settings.EMAIL_HOST_PASSWORD
                )

                if settings.DEBUG and missing_email_credentials:
                    print(
                        f"[Checkora] Development registration OTP "
                        f"for {user.email}: {otp}"
                    )
                    messages.success(request, GENERIC_REGISTRATION_MESSAGE)
                    return redirect('verify_otp')

                # Send Email
                try:
                    msg_plain = (
                        f'Your OTP for registration is: {otp}\n\n'
                        'Please enter this code to activate your account.'
                    )
                    html_message = (
                        "<div style=\"font-family: 'Segoe UI', Arial, "
                        "sans-serif; background-color: #0f0f1a; color: "
                        "#d0d0d0; padding: 40px 20px; text-align: center;"
                        "\"><div style=\"background-color: #16162a; border"
                        ": 1px solid #252545; border-radius: 12px; padding"
                        ": 40px 30px; max-width: 450px; margin: 0 auto; "
                        "box-shadow: 0 10px 30px rgba(0,0,0,0.5);\">"
                        "<h1 style=\"color: #ffffff; margin-top: 0; "
                        "margin-bottom: 15px; font-size: 28px; "
                        "letter-spacing: 2px;\">CHECK<span style=\"color: "
                        "#f0c040;\">ORA</span></h1><hr style=\"border: "
                        "none; border-top: 1px solid #252545; margin: "
                        "20px 0;\"><p style=\"color: #e0e0e0; font-size: "
                        "16px; line-height: 1.5; margin-bottom: 30px;\">"
                        "Welcome to the elite chess platform. To activate "
                        "your account and start playing, please use the "
                        "verification code below:</p><div style=\"margin: "
                        "35px 0;\"><span style=\"font-family: 'Consolas', "
                        "monospace; font-size: 36px; font-weight: bold; "
                        "color: #f0c040; letter-spacing: 8px; background: "
                        "#0f0f1a; padding: 15px 25px; border-radius: 8px; "
                        "border: 1px solid #3d3222; display: inline-block;"
                        "\">{otp}</span></div><p style=\"color: #8a8aaa; "
                        "font-size: 14px; margin-top: 30px;\">Enter this "
                        "code on the verification page to complete your "
                        "registration.</p><p style=\"color: #5a5a7a; "
                        "font-size: 12px; margin-top: 40px;\">If you "
                        "didn't attempt to register on Checkora, please "
                        "safely ignore this email.</p></div></div>"
                    ).format(otp=otp)
                    send_mail(
                        'Your Checkora Verification Code',
                        msg_plain,
                        None,  # Will use EMAIL_HOST_USER
                        [user.email],
                        fail_silently=False,
                        html_message=html_message
                    )
                    messages.success(request, GENERIC_REGISTRATION_MESSAGE)
                    return redirect('verify_otp')
                except (SMTPException, BadHeaderError, OSError):
                    # If email fails, delete the user only if it was newly created.
                    # This preserves existing inactive accounts for re-verification.
                    if is_new_user:
                        user.delete()
                    _clear_registration_session(request)
                    # Nothing was sent, so the next attempt may mail again.
                    cache.delete(_registration_cooldown_key(email))
                    err_msg = (
                        'Failed to send OTP email. '
                        'Please check your email address and try again.'
                    )
                    messages.error(request, err_msg)
            finally:
                cache.delete(email_lock_key)
    else:
        form = CustomUserCreationForm()

    return render(request, 'game/register.html', {'form': form})


def send_welcome_email(request, user):
    """Mail a new player once their account exists. A failure never blocks signup."""
    try:
        from django.template import TemplateDoesNotExist, TemplateSyntaxError
        html_content = render_to_string(
            'game/welcome_email.html',
            {
                'username': user.username,
                'app_url': request.build_absolute_uri('/'),
            }
        )
        email = EmailMultiAlternatives(
            subject='Welcome to Checkora 🎉',
            body='Welcome to Checkora! Your account has been successfully activated.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)

    except (TemplateDoesNotExist, TemplateSyntaxError):
        logger.exception("Failed to render welcome email template.")
    except Exception as e:
        logger.warning("Failed to send welcome email: %s", e)


def verify_otp(request):
    if request.user.is_authenticated:
        return redirect('index')

    user_id = request.session.get('registration_user_id')
    stored_otp_hash = request.session.get('registration_otp_hash')

    if not user_id or not stored_otp_hash:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('register')

    if user_id and user_id != -1:
        cache_key = f"otp_failed_attempts_user_{user_id}"
    else:
        if not request.session.session_key:
            request.session.create()
        cache_key = f"otp_failed_attempts_session_{request.session.session_key}"

    if request.method == 'POST':
        # Check expiration first
        otp_created_at = request.session.get('otp_created_at')
        if otp_created_at and time.time() - otp_created_at > 300:
            messages.error(
                request,
                'OTP has expired. Please register again.',
            )
            # Retrieve attempts to preserve across expiration
            cache_attempts = cache.get(cache_key, 0)
            session_attempts = request.session.get('otp_failed_attempts', 0)
            otp_failed_attempts = max(session_attempts, cache_attempts)

            _clear_registration_session(request)
            if otp_failed_attempts:
                request.session['otp_failed_attempts'] = otp_failed_attempts
                cache.set(cache_key, otp_failed_attempts, timeout=900)

            return redirect('register')

        # Atomic increment of attempts in cache using cache.add and cache.incr
        session_attempts = request.session.get('otp_failed_attempts', 0)
        if not cache.add(cache_key, session_attempts + 1, timeout=900):
            otp_failed_attempts = cache.incr(cache_key)
        else:
            otp_failed_attempts = session_attempts + 1

        request.session['otp_failed_attempts'] = otp_failed_attempts

        if otp_failed_attempts > 5:
            _clear_registration_session(request)
            messages.error(request, 'Too many incorrect attempts. Please register again.')
            return redirect('register')

        entered_otp = request.POST.get('otp', '').strip()

        entered_otp_hash = hashlib.sha256(
            f"{entered_otp}:{settings.SECRET_KEY}".encode()
        ).hexdigest()

        if secrets.compare_digest(
            entered_otp_hash,
            stored_otp_hash
        ):
            try:
                if user_id == -1:
                    raise User.DoesNotExist()
                # Only a signup that is still waiting can be activated here.
                user = pending_registrations().get(id=user_id)
                password_hash = request.session.get('registration_password')
                if password_hash:
                    user.password = password_hash
                user.is_active = True
                user.full_clean()
                user.save()
                _clear_registration_session(request)

                send_welcome_email(request, user)

                login(request, user)
                messages.success(
                    request,
                    'Registration successful! Welcome to Checkora.'
                )
                request.session.cycle_key()
                return redirect('index')

            except User.DoesNotExist:
                messages.error(
                    request,
                    'User not found. Please register again.'
                )
                _clear_registration_session(request)
                return redirect('register')

        else:
            if otp_failed_attempts >= 5:
                _clear_registration_session(request)
                messages.error(request, 'Too many incorrect attempts. Please register again.')
                return redirect('register')

            messages.error(request, 'Invalid OTP. Please try again.')

    remaining_time = 0
    last_otp_time = request.session.get('last_otp_time')

    if last_otp_time:
        elapsed = int(time.time() - last_otp_time)
        remaining_time = max(0, 60 - elapsed)

    email = None
    if user_id == -1:
        email = request.session.get('registration_email')
    else:
        try:
            user = User.objects.get(id=user_id)
            email = user.email
        except User.DoesNotExist:
            email = None

    if email and '@' in email:
        name, domain = email.split('@', 1)
        if len(name) <= 2:
            masked_name = name[:1]
        else:
            masked_name = name[:2] + '*' * (len(name) - 2)
        user_email = f"{masked_name}@{domain}"
    else:
        user_email = None

    return render(
        request,
        'game/verify_otp.html',
        {
            'remaining_time': remaining_time,
            'user_email': user_email,
        }
    )

@require_POST
def resend_otp(request):
    user_id = request.session.get('registration_user_id')

    if not user_id:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('register')

    if user_id == -1:
        last_otp_time = request.session.get('last_otp_time')
        if last_otp_time and time.time() - last_otp_time < 60:
            remaining = int(60 - (time.time() - last_otp_time))
            messages.error(request, f'Please wait {remaining} seconds before requesting a new OTP.')
            return redirect('verify_otp')

        otp = str(secrets.randbelow(900000) + 100000)
        otp_hash = hashlib.sha256(
            f"{otp}:{settings.SECRET_KEY}".encode()
        ).hexdigest()
        request.session['registration_otp_hash'] = otp_hash
        request.session['otp_created_at'] = time.time()
        request.session['last_otp_time'] = time.time()
        messages.success(request, 'A new OTP has been sent to your email.')
        return redirect('verify_otp')

    try:
        user = pending_registrations().get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please register again.')
        return redirect('register')
    last_otp_time = request.session.get('last_otp_time')
    if last_otp_time and time.time() - last_otp_time < 60:
        remaining = int(60 - (time.time() - last_otp_time))
        messages.error(request, f'Please wait {remaining} seconds before requesting a new OTP.')
        return redirect('verify_otp')

    # The same address may be waiting in other browsers too.
    if not _registration_email_allowed(user.email):
        messages.error(request, 'Please wait a moment before requesting a new OTP.')
        return redirect('verify_otp')

    otp = str(secrets.randbelow(900000) + 100000)

    otp_hash = hashlib.sha256(
        f"{otp}:{settings.SECRET_KEY}".encode()
    ).hexdigest()

    try:
        send_mail(
            'Your Checkora Verification Code',
            f'Your new OTP is: {otp}',
            None,
            [user.email],
            fail_silently=False,
        )

        messages.success(
            request,
            'A new OTP has been sent to your email.'
        )
        request.session['registration_otp_hash'] = otp_hash
        request.session['otp_created_at'] = time.time()
        request.session['last_otp_time'] = time.time()

    except (SMTPException, BadHeaderError, OSError):
        cache.delete(_registration_cooldown_key(user.email))
        messages.error(
            request,
            'Failed to resend OTP. Please try again.'
        )

    return redirect('verify_otp')

class CustomPasswordResetView(PasswordResetView):
    """Password reset view with email cooldown and IP-level throttling."""

    form_class = PasswordResetForm
    email_cooldown_message = (
        'Please wait {duration} before requesting another password reset email.'
    )
    ip_throttle_message = (
        'Too many password reset requests were sent from your network. '
        'Please wait {duration} before trying again.'
    )

    def _cache_key(self, prefix, value):
        normalized = (value or 'unknown').strip().lower()
        digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        return f'{prefix}:{digest}'

    def _ip_expires_key(self, ip_key):
        return f'{ip_key}:expires'

    def _client_ip(self, request):
        remote_addr = request.META.get('REMOTE_ADDR', '')
        trusted_ips = getattr(settings, 'TRUSTED_PROXY_IPS', [])
        if not _is_trusted_proxy(remote_addr, trusted_ips):
            return remote_addr

        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded_for:
            hops = [h.strip() for h in forwarded_for.split(',') if h.strip()]
            for hop in reversed(hops):
                if not _is_trusted_proxy(hop, trusted_ips):
                    return hop
        return remote_addr

    def _format_duration(self, seconds):
        seconds = max(1, int(seconds))
        minutes, remainder = divmod(seconds, 60)
        if minutes and remainder:
            return f'{minutes} minute(s) and {remainder} second(s)'
        if minutes:
            return f'{minutes} minute(s)'
        return f'{remainder} second(s)'

    def _cooldown_remaining(self, cache_key):
        expires_at = cache.get(cache_key)
        if not expires_at:
            return 0
        return max(0, int(expires_at - time.time()))

    def _get_limited_response(self, request, email):
        email_key = self._cache_key('password-reset-email', email)
        remaining = self._cooldown_remaining(email_key)
        if remaining:
            messages.error(
                request,
                self.email_cooldown_message.format(
                    duration=self._format_duration(remaining)
                ),
            )
            return redirect('password_reset')

        ip_key = self._cache_key(
            'password-reset-ip',
            self._client_ip(request),
        )
        ip_attempts = cache.get(ip_key, 0)
        max_attempts = getattr(settings, 'PASSWORD_RESET_IP_MAX_REQUESTS', 3)
        if ip_attempts >= max_attempts:
            remaining = self._cooldown_remaining(self._ip_expires_key(ip_key))
            if not remaining:
                remaining = getattr(settings, 'PASSWORD_RESET_IP_WINDOW_SECONDS', 900)
            messages.error(
                request,
                self.ip_throttle_message.format(
                    duration=self._format_duration(remaining)
                ),
            )
            return redirect('password_reset')

        request._password_reset_email_key = email_key
        request._password_reset_ip_key = ip_key
        return None

    def _record_password_reset_request(self, request):
        email_timeout = getattr(
            settings,
            'PASSWORD_RESET_EMAIL_COOLDOWN_SECONDS',
            300,
        )
        cache.set(
            request._password_reset_email_key,
            time.time() + email_timeout,
            timeout=email_timeout,
        )

        ip_timeout = getattr(settings, 'PASSWORD_RESET_IP_WINDOW_SECONDS', 900)
        ip_expires_key = self._ip_expires_key(request._password_reset_ip_key)
        if not cache.add(request._password_reset_ip_key, 1, timeout=ip_timeout):
            cache.incr(request._password_reset_ip_key)
            if not cache.get(ip_expires_key):
                cache.set(ip_expires_key, time.time() + ip_timeout, timeout=ip_timeout)
        else:
            cache.set(ip_expires_key, time.time() + ip_timeout, timeout=ip_timeout)

    def post(self, request, *args, **kwargs):

        email = request.POST.get('email', '').strip().lower()
        if not email:
            messages.error(
                request,
                'Please enter a valid email address.'
            )

            return redirect('password_reset')

        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)

        limited_response = self._get_limited_response(request, email)
        if limited_response:
            return limited_response

        response = self.form_valid(form)
        self._record_password_reset_request(request)
        return response


def _is_trusted_proxy(ip_text, trusted_entries):
    """Check if an IP address matches trusted proxy entries (IP or CIDR)."""
    try:
        ip_obj = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    for entry in trusted_entries:
        try:
            if "/" in entry:
                if ip_obj in ipaddress.ip_network(entry, strict=False):
                    return True
            elif ip_obj == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def get_ai_move_rate_user_key(user_id):
    """Get the cache key for per-user AI move rate limiting."""
    digest = hashlib.sha256(str(user_id).encode('utf-8')).hexdigest()
    return f'ai_move_rate:user:{digest}'


def get_ai_move_rate_ip_key(ip):
    """Get the cache key for per-IP AI move rate limiting."""
    digest = hashlib.sha256(ip.encode('utf-8')).hexdigest()
    return f'ai_move_rate:ip:{digest}'

def get_client_ip(request):
    """Get client IP address safely by parsing trusted proxies."""
    remote_addr = request.META.get('REMOTE_ADDR', 'unknown')
    trusted_proxies = getattr(
        settings, 'TRUSTED_PROXIES', ['127.0.0.1', '::1']
    )
    if not _is_trusted_proxy(remote_addr, trusted_proxies):
        return remote_addr

    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    hops = [
        h.strip() for h in forwarded_for.split(',') if h.strip()
    ]
    for hop in reversed(hops):
        if not _is_trusted_proxy(hop, trusted_proxies):
            return hop
    return remote_addr


def normalize_username(username):
    """Normalize the username by stripping whitespace and converting to lowercase."""
    return (username or '').strip().lower()


def get_username_fail_count_key(username):
    """Get the cache key for username failed login attempts."""
    normalized = normalize_username(username)
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    return f'login_fail_count:user:{digest}'


def get_username_lockout_key(username):
    """Get the cache key for username lockout state."""
    normalized = normalize_username(username)
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    return f'login_lockout:user:{digest}'


def get_ip_fail_count_key(ip):
    """Get the cache key for IP failed login attempts."""
    digest = hashlib.sha256(ip.encode('utf-8')).hexdigest()
    return f'login_fail_count:ip:{digest}'


def get_ip_lockout_key(ip):
    """Get the cache key for IP lockout state."""
    digest = hashlib.sha256(ip.encode('utf-8')).hexdigest()
    return f'login_lockout:ip:{digest}'


def get_analyze_rate_user_key(user_id):
    """Get the cache key for per-user analyze game rate limiting."""
    digest = hashlib.sha256(str(user_id).encode('utf-8')).hexdigest()
    return f'analyze_rate:user:{digest}'


def get_analyze_rate_ip_key(ip):
    """Get the cache key for per-IP analyze game rate limiting."""
    digest = hashlib.sha256(ip.encode('utf-8')).hexdigest()
    return f'analyze_rate:ip:{digest}'


def _cache_counts_natively():
    """Tell whether the cache backend has its own atomic incr.

    The database and file backends inherit BaseCache.incr, which reads the
    value and writes it back with the default timeout. Every hit would then
    restart the window, so those backends take the locked path below.
    """
    return type(caches[DEFAULT_CACHE_ALIAS]).incr is not BaseCache.incr


def increment_counter(key, timeout):
    """Count one hit in a window of `timeout` seconds and return the total."""
    if _cache_counts_natively():
        try:
            if cache.add(key, 1, timeout=timeout):
                return 1
            else:
                return cache.incr(key)
        except (ValueError, TypeError):
            pass

    lock_key = f"lock:{key}"
    acquired = False
    # Spin lock: attempt to acquire for up to 5 seconds
    for _ in range(100):
        if cache.add(lock_key, 1, timeout=10):
            acquired = True
            break
        time.sleep(0.05)

    def _fallback_increment():
        now = time.time()
        expiry_key = f"{key}:expiry"
        expires_at = cache.get(expiry_key)

        new_window = expires_at is None or now >= expires_at
        if new_window:
            expires_at = now + timeout
            cache.set(expiry_key, expires_at, timeout=timeout)

        remaining = max(1, int(expires_at - now))

        # A new window starts from zero even if the old count is still cached.
        raw_val = None if new_window else cache.get(key)
        try:
            val = int(raw_val) if raw_val is not None else 0
        except (ValueError, TypeError):
            val = 0

        val += 1
        cache.set(key, val, timeout=remaining)
        return val

    if not acquired:
        # fail closed for brute-force logic without taking down login
        return _fallback_increment()

    try:
        return _fallback_increment()
    finally:
        if acquired:
            cache.delete(lock_key)


def rate_limit(window_setting, max_setting, prefix, error_message="Rate limit reached. Please try again shortly."):
    """
    Reusable rate limit decorator based on cache throttle.
    Limits requests to max_setting within window_setting seconds per user/IP.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                key_id = request.user.id
            else:
                key_id = get_client_ip(request)
            
            key_digest = hashlib.sha256(
                str(key_id).encode('utf-8')
            ).hexdigest()
            cache_key = f"rate_limit:{prefix}:{key_digest}"
            
            window_seconds = getattr(settings, window_setting, 60)
            max_requests = getattr(settings, max_setting, 60)
            
            current = increment_counter(cache_key, window_seconds)
            
            if current > max_requests:
                if request.accepts("text/html"):
                    return HttpResponse(
                        (
                            "<h1>429 Too Many Requests</h1>"
                            f"<p>{error_message}</p>"
                        ),
                        status=429
                    )
                return JsonResponse({"error": error_message}, status=429)
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def _login_destination(request):
    """Where to go after login: the `next` page when it is on this site."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return 'landing'


def login_view(request):
    if request.user.is_authenticated:
        return redirect('landing')

    if request.method == 'POST':
        username = request.POST.get('username', '')
        client_ip = get_client_ip(request)

        username_lockout_key = get_username_lockout_key(username)
        ip_lockout_key = get_ip_lockout_key(client_ip)

        ip_lockout_expiry = cache.get(ip_lockout_key)
        username_lockout_expiry = cache.get(username_lockout_key)

        # 1. IP Lockout Check
        if ip_lockout_expiry is not None:
            remaining_seconds = ip_lockout_expiry - time.time()
            if remaining_seconds <= 0:
                cache.delete(ip_lockout_key)
            else:
                remaining_minutes = max(
                    1, int(math.ceil(remaining_seconds / 60))
                )
                error_message = (
                    f"Too many login attempts from this IP address. "
                    f"Try again in {remaining_minutes} minutes."
                )
                form = AuthenticationForm(data=request.POST)
                form.add_error(None, error_message)
                return render(request, 'game/login.html', {'form': form})

        # 2. Username Lockout Check
        if username_lockout_expiry is not None:
            remaining_seconds = username_lockout_expiry - time.time()
            if remaining_seconds <= 0:
                cache.delete(username_lockout_key)
            else:
                remaining_minutes = max(
                    1, int(math.ceil(remaining_seconds / 60))
                )
                error_message = (
                    f"This account is temporarily locked. "
                    f"Try again in {remaining_minutes} minutes."
                )
                form = AuthenticationForm(data=request.POST)
                form.add_error(None, error_message)
                return render(request, 'game/login.html', {'form': form})

        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Clear username lockout and failure counter on successful login
            username_input = request.POST.get('username', '')
            cache.delete(get_username_fail_count_key(username_input))
            cache.delete(get_username_lockout_key(username_input))
            cache.delete(get_username_fail_count_key(user.username))
            cache.delete(get_username_lockout_key(user.username))

            login(request, user)
            request.session.cycle_key()  # Prevent session fixation

            remember_me = request.POST.get("remember_me")

            if remember_me:
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
            else:
                request.session.set_expiry(0)

            messages.success(
                request,
                f'Welcome back, {user.username}! Login successful.'
            )
            return redirect(_login_destination(request))
        else:
            # Login failed: track failed attempts
            username_fails = 0
            if username:
                username_fail_count_key = (
                    get_username_fail_count_key(username)
                )
                username_fails = increment_counter(
                    username_fail_count_key, timeout=LOCKOUT_SECONDS
                )

            ip_fail_count_key = get_ip_fail_count_key(client_ip)
            ip_fails = increment_counter(
                ip_fail_count_key, timeout=LOCKOUT_SECONDS
            )

            if ip_fails >= IP_MAX_FAILS:
                lockout_expiry = time.time() + LOCKOUT_SECONDS
                cache.set(
                    ip_lockout_key, lockout_expiry,
                    timeout=LOCKOUT_SECONDS
                )

                # Update error message immediately to show lockout
                error_message = (
                    f"Too many login attempts from this IP address. "
                    f"Try again in {LOCKOUT_SECONDS // 60} minutes."
                )
                form._errors = ErrorDict()
                form.add_error(None, error_message)
                return render(request, 'game/login.html', {'form': form})

            if username_fails >= USERNAME_MAX_FAILS:
                lockout_expiry = time.time() + LOCKOUT_SECONDS
                cache.set(
                    username_lockout_key, lockout_expiry,
                    timeout=LOCKOUT_SECONDS
                )

                # Update error message immediately to show lockout
                error_message = (
                    f"This account is temporarily locked. "
                    f"Try again in {LOCKOUT_SECONDS // 60} minutes."
                )
                form._errors = ErrorDict()
                form.add_error(None, error_message)
                return render(request, 'game/login.html', {'form': form})

    else:
        form = AuthenticationForm()

    return render(request, 'game/login.html', {'form': form})


@xframe_options_sameorigin
def rules(request):
    return render(request, 'game/rules.html')


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing')


# Protect the stats page with login requirement
@login_required
def stats_view(request):
    """Display game statistics."""
    # Only show real database records linked to the logged-in user
    user_results = request.user.game_results.all().exclude(mode__in=['', None])

    total_games = user_results.count()

    recent = user_results.order_by('-played_at')[:20]
    # Reading a page never creates rows: a PlayerRating made here would put a
    # player who never played on the leaderboard.
    progress = UserProgress.objects.filter(user=request.user).first() or UserProgress(user=request.user)
    ai_results = user_results.filter(mode='ai')

    # If winner == player_color, the user won
    user_ai_wins = ai_results.filter(winner=F('player_color')).count()
    # If winner != player_color and not a draw, the AI won
    ai_wins = ai_results.filter(
        Q(winner='white', player_color='black') |
        Q(winner='black', player_color='white')
    ).count()

    ai_draws = ai_results.filter(winner='draw').count()
    ai_total = ai_results.count()

    # Handle explicit edge cases (e.g. division by zero for win rate)
    win_percentage = (user_ai_wins / ai_total * 100) if ai_total > 0 else 0

    # Wins and losses are only counted against the engine. In a two-player
    # game on one board the account plays both sides.
    total_wins = user_ai_wins
    total_losses = ai_wins
    total_draws = ai_draws
    overall_win_rate = round(win_percentage, 2)

    rating = PlayerRating.objects.filter(user=request.user).first() or PlayerRating(user=request.user)

    history = RatingHistory.objects.filter(
        user=request.user
    )

    recent_history = history[:10]

    history_all = RatingHistory.objects.filter(
        user=request.user
    ).order_by('created_at')

    # Data for the rating chart, oldest first.
    chart_history = [
        {
            'date': timezone.localtime(entry.created_at).strftime('%Y-%m-%d %H:%M'),
            'timestamp': int(entry.created_at.timestamp()),
            'new_rating': entry.new_rating,
            'change': entry.rating_change,
            'result': entry.result,
        }
        for entry in history_all
    ]

    # Color Statistics
    games_as_white = ai_results.filter(
        player_color="white"
    ).count()

    games_as_black = ai_results.filter(
        player_color="black"
    ).count()

    white_wins = ai_results.filter(
        player_color="white",
        winner="white"
    ).count()

    black_wins = ai_results.filter(
        player_color="black",
        winner="black"
    ).count()

    white_win_rate = (
        round((white_wins / games_as_white) * 100, 2)
        if games_as_white else 0
    )

    black_win_rate = (
        round((black_wins / games_as_black) * 100, 2)
        if games_as_black else 0
    )
    
    # Activity Statistics
    week_ago = timezone.now() - timedelta(days=7)
    month_ago = timezone.now() - timedelta(days=30)

    games_this_week = user_results.filter(
        played_at__gte=week_ago
    ).count()

    games_this_month = user_results.filter(
        played_at__gte=month_ago
    ).count()

    # Rating Analytics
    if history.exists():
        highest_rating = max(
            history.aggregate(Max("new_rating"))["new_rating__max"],
            history.aggregate(Max("old_rating"))["old_rating__max"]
        )

        lowest_rating = min(
            history.aggregate(Min("new_rating"))["new_rating__min"],
            history.aggregate(Min("old_rating"))["old_rating__min"]
        )
    else:
        highest_rating = rating.rating
        lowest_rating = rating.rating
        
    average_rating = history.aggregate(
        Avg("new_rating")
    )["new_rating__avg"] or rating.rating

    total_rating_change = history.aggregate(
        Sum("rating_change")
    )["rating_change__sum"] or 0

    # Learning Progress
    lessons_completed = LessonProgress.objects.filter(
        user=request.user,
        completed=True
    ).count()

    total_lessons = sum(
        len(level["lessons"])
        for level in LESSON_LEVELS
    )
    lesson_completion_percentage = (
        round(
            (lessons_completed / total_lessons) * 100,
            2
        )
        if total_lessons > 0
        else 0
    )
    
    # Puzzle Analytics
    puzzle_stats = PuzzleStats.objects.filter(user=request.user).first() or PuzzleStats(user=request.user)

    opening_stats = OpeningProgress.objects.filter(
        user=request.user
    )

    completed_openings = opening_stats.filter(
        openings_completed__gt=0
    ).count()

    average_accuracy = (
        opening_stats.aggregate(
            Avg("accuracy_percentage")
        )["accuracy_percentage__avg"]
        or 0
    )

    most_practiced = opening_stats.order_by(
        "-openings_started"
    ).first()

    return render(request, 'game/stats.html', {
        'recent': recent,
        'ai_total': ai_total,
        'user_ai_wins': user_ai_wins,
        'ai_wins': ai_wins,
        'ai_draws': ai_draws,
        'win_percentage': round(win_percentage, 2),
        'progress': progress,
        'rating': rating,
        'history': recent_history,
        'history_all': history_all,
        'chart_history': chart_history,

        "total_games": total_games,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_draws": total_draws,
        "overall_win_rate": overall_win_rate,

        "games_as_white": games_as_white,
        "games_as_black": games_as_black,
        "white_win_rate": white_win_rate,
        "black_win_rate": black_win_rate,

        "highest_rating": highest_rating,
        "lowest_rating": lowest_rating,
        "average_rating": round(average_rating, 2),
        "total_rating_change": total_rating_change,
        "games_this_week": games_this_week,
        "games_this_month": games_this_month,

        "lessons_completed": lessons_completed,
        "lesson_completion_percentage": lesson_completion_percentage,

        "puzzle_stats": puzzle_stats,
        "puzzle_streak": puzzle_stats.streak_on(timezone.localdate()),
        "day_streak": progress.streak_on(progression.player_today(request.user)),
        "best_day_streak": progress.best_day_streak,
        
        "completed_openings": completed_openings,
        "average_opening_accuracy": round(
            average_accuracy,
            2
        ),
        "most_practiced_opening": (
            most_practiced.opening_name
            if most_practiced
            else "None"
        ),
    })


LEADERBOARD_SIZE = 50


def _ranked(queryset, *ordering):
    """Rows with a `position`: players level on every ordering share it, as in "1, 2, 2, 4".

    The user id is a last tiebreak only for the order rows are listed in, so
    the table doesn't reshuffle between page loads.
    """
    return (
        queryset
        .filter(user__is_active=True)
        .select_related("user__profile")
        .defer("user__profile__avatar")
        .annotate(position=Window(expression=Rank(), order_by=list(ordering)))
        .order_by(*ordering, "user_id")
    )


def _own_row(rows, queryset, user, ahead_of_user):
    """The signed-in player's row when they are on the board but not in the top rows shown."""
    if any(row.user_id == user.pk for row in rows):
        return None
    mine = queryset.filter(user=user).select_related("user__profile").defer("user__profile__avatar").first()
    if mine is None:
        return None
    mine.position = queryset.filter(ahead_of_user(mine), user__is_active=True).count() + 1
    return mine


@login_required
def leaderboard_view(request):
    # Only players who have done something are on a board: a row made by
    # opening a page must not sit at 1200 above people who played.
    solvers = PuzzleStats.objects.filter(puzzles_solved__gt=0)
    puzzle_rows = list(_ranked(solvers, F("puzzles_solved").desc(), F("best_streak").desc())[:LEADERBOARD_SIZE])

    rated = PlayerRating.objects.filter(games_played__gt=0)
    chess_rows = list(_ranked(rated, F("rating").desc())[:LEADERBOARD_SIZE])

    return render(request, "game/leaderboard.html", {
        "leaderboard": puzzle_rows,
        "chess_leaderboard": chess_rows,
        "my_puzzle_row": _own_row(
            puzzle_rows, solvers, request.user,
            lambda me: Q(puzzles_solved__gt=me.puzzles_solved)
            | Q(puzzles_solved=me.puzzles_solved, best_streak__gt=me.best_streak),
        ),
        "my_chess_row": _own_row(
            chess_rows, rated, request.user,
            lambda me: Q(rating__gt=me.rating),
        ),
        "leaderboard_size": LEADERBOARD_SIZE,
    })


def _puzzle_stats_payload(stats):
    if stats is None:
        return {"streak": 0, "longest_streak": 0, "puzzles_solved": 0, "daily_completions": 0}
    return {
        "streak": stats.streak_on(timezone.localdate()),
        "longest_streak": stats.best_streak,
        "puzzles_solved": stats.puzzles_solved,
        "daily_completions": stats.daily_completions,
    }


def puzzle_stats_view(request):
    stats = (
        PuzzleStats.objects.filter(user=request.user).first()
        if request.user.is_authenticated else None
    )
    return JsonResponse(_puzzle_stats_payload(stats))


def get_daily_puzzle(request):
    """Serve a puzzle corresponding to the current date."""
    puzzle = daily_puzzle_for(timezone.localdate())

    if not puzzle:
        # Only reached when the puzzle table is empty: a back-rank mate in one.
        return JsonResponse({
            "id": 0,
            "title": "Default Puzzle",
            "fen": "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
            "solution": ["e1e8"],
            "difficulty": "easy"
        })

    return JsonResponse({
        "id": puzzle.id,
        "title": puzzle.title,
        "fen": puzzle.fen,
        "difficulty": puzzle.difficulty or "medium"
    })


def puzzles_view(request):
    """Render the puzzles dashboard page."""
    return render(request, "game/puzzle_list.html")


@require_GET
def puzzles_list_api(request):
    """API endpoint to get list of puzzles, excluding solutions."""
    puzzles = ChessPuzzle.objects.all()

    # Filter by difficulty
    difficulty = request.GET.get('difficulty')
    if difficulty:
        puzzles = puzzles.filter(difficulty__iexact=difficulty)

    # Search by title
    search_query = request.GET.get('search') or request.GET.get('q')
    if search_query:
        puzzles = puzzles.filter(title__icontains=search_query)

    # Filter by tag (motif)
    tag = request.GET.get('tag')
    if tag:
        puzzles = puzzles.filter(
            Q(tags=tag) |
            Q(tags__startswith=tag + ",") |
            Q(tags__startswith=tag + ", ") |
            Q(tags__endswith="," + tag) |
            Q(tags__endswith=", " + tag) |
            Q(tags__contains="," + tag + ",") |
            Q(tags__contains=", " + tag + ",") |
            Q(tags__contains="," + tag + " ,") |
            Q(tags__contains=", " + tag + " ,")
        )

    # Filter by min_rating
    min_rating = request.GET.get('min_rating')
    if min_rating:
        try:
            puzzles = puzzles.filter(rating__gte=int(min_rating))
        except ValueError:
            pass

    # Filter by max_rating
    max_rating = request.GET.get('max_rating')
    if max_rating:
        try:
            puzzles = puzzles.filter(rating__lte=int(max_rating))
        except ValueError:
            pass

    # Order puzzles logically so pagination is stable
    puzzles = puzzles.order_by('id')

    # Pagination
    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 9)

    try:
        page = max(1, int(page))
    except ValueError:
        page = 1

    try:
        per_page = max(1, min(int(per_page), 100))
    except ValueError:
        per_page = 9

    paginator = Paginator(puzzles, per_page)
    try:
        puzzles_page = paginator.page(page)
    except EmptyPage:
        puzzles_page = []

    puzzles_data = []
    for puzzle in puzzles_page:
        puzzles_data.append({
            "id": puzzle.id,
            "title": puzzle.title,
            "fen": puzzle.fen,
            "difficulty": puzzle.difficulty or "medium",
            "date": puzzle.date.isoformat() if puzzle.date else None,
            "rating": puzzle.rating,
            "tags": [t.strip() for t in puzzle.tags.split(',')] if puzzle.tags else []
        })

    return JsonResponse({
        "puzzles": puzzles_data,
        "page": page,
        "total_pages": paginator.num_pages,
        "total_count": paginator.count,
        "has_next": puzzles_page.has_next() if hasattr(puzzles_page, 'has_next') else False,
        "has_previous": puzzles_page.has_previous() if hasattr(puzzles_page, 'has_previous') else False,
    }, safe=False)


@require_GET
def puzzle_detail_api(request, puzzle_id):
    """API endpoint to get a single puzzle's details (excluding solution)."""
    puzzle = get_object_or_404(ChessPuzzle, id=puzzle_id)
    return JsonResponse({
        "id": puzzle.id,
        "title": puzzle.title,
        "fen": puzzle.fen,
        "difficulty": puzzle.difficulty or "medium",
        "date": puzzle.date.isoformat() if puzzle.date else None,
        "rating": puzzle.rating,
        "tags": [t.strip() for t in puzzle.tags.split(',')] if puzzle.tags else []
    })


def _revealed_key(user_id, puzzle_id):
    return f"puzzle_revealed:{user_id}:{puzzle_id}"


# A signed-in player who looked at a solution gets no credit for that puzzle
# for this long; after that they may well have forgotten it.
REVEALED_PUZZLE_SECONDS = 7 * 24 * 3600


@require_GET
def puzzle_solution_api(request, puzzle_id):
    """API endpoint to retrieve the solution array for a specific puzzle."""
    puzzle = get_object_or_404(ChessPuzzle, id=puzzle_id)
    if request.user.is_authenticated:
        cache.set(_revealed_key(request.user.pk, puzzle.pk), 1, timeout=REVEALED_PUZZLE_SECONDS)
    return JsonResponse({
        "solution": puzzle.solution
    })


@require_POST
@rate_limit(
    window_setting="PUZZLE_SOLVE_RATE_WINDOW_SECONDS",
    max_setting="PUZZLE_SOLVE_MAX_REQUESTS",
    prefix="puzzle_solve",
    error_message="Too many puzzle answers at once. Take a breath and try again in a minute.",
)
def puzzle_solve_api(request, puzzle_id):
    """Check the moves played against the stored solution and count the solve.

    The totals and the streak are worked out on the server. Nothing the
    client says about its own progress is stored, and a puzzle whose
    solution this player opened earns nothing.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    puzzle = get_object_or_404(ChessPuzzle, id=puzzle_id)

    data = _json_object(request)
    moves = data.get('moves') if data is not None else None
    if not isinstance(moves, list) or not all(isinstance(m, str) for m in moves):
        return JsonResponse(
            {'success': False, 'error': 'moves must be a list of strings'},
            status=400,
        )

    solution = puzzle.solution if isinstance(puzzle.solution, list) else []
    correct = bool(solution) and len(moves) == len(solution) and all(
        played.strip().lower() == str(expected).strip().lower()
        for played, expected in zip(moves, solution)
    )

    revealed = cache.get(_revealed_key(request.user.pk, puzzle.pk)) is not None
    newly_solved = False
    if correct and not revealed:
        stats, newly_solved = record_puzzle_solve(request.user, puzzle)
    else:
        stats = PuzzleStats.objects.filter(user=request.user).first()

    return JsonResponse({
        'success': True,
        'correct': correct,
        'counted': correct and not revealed,
        'newly_solved': newly_solved,
        **_puzzle_stats_payload(stats),
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cleanup_cron(request):
    """Secure cron-triggered cleanup endpoint for abandoned games.

    Vercel calls cron paths with GET; POST stays for manual runs.
    """
    cron_secret = getattr(settings, 'CRON_SECRET', None)

    # Check authorization header
    auth_header = request.headers.get('Authorization')
    expected = f"Bearer {cron_secret}" if cron_secret else ""
    provided = auth_header or ""

    if (not cron_secret or
            not secrets.compare_digest(expected.encode(), provided.encode())):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        deleted, resigned = cleanup_stale_games()
        purged_records, purged_sessions = purge_expired_records()
        return JsonResponse({
            'status': 'success',
            'deleted_games': deleted,
            'resigned_games': resigned,
            'purged_records': purged_records,
            'purged_sessions': purged_sessions,
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# Centipawns given up against the engine's choice before a move gets a label.
BLUNDER_LOSS = 300
MISTAKE_LOSS = 100


def _classify_move(is_best, loss):
    """Label a move by the evaluation it gave up, in centipawns.

    `loss` is None when the engine had no evaluation to compare with.
    """
    if is_best:
        return 'Best'
    if loss is None:
        return 'Unknown'
    if loss >= BLUNDER_LOSS:
        return 'Blunder'
    if loss >= MISTAKE_LOSS:
        return 'Mistake'
    return 'Inaccuracy'


def _same_squares(move, from_sq, to_sq):
    return (
        move['from_row'] == from_sq[0] and move['from_col'] == from_sq[1]
        and move['to_row'] == to_sq[0] and move['to_col'] == to_sq[1]
    )


@require_POST
def analyze_game_view(request):
    """POST /api/analyze-game/ — engine-powered post-game analysis."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        if 'moves' not in data:
            return JsonResponse({'error': 'Missing moves field'}, status=400)
        moves = data['moves']
        result = data.get('result', 'Unknown')
        reason = data.get('reason', 'Unknown')

        window = getattr(settings, 'ANALYZE_GAME_RATE_WINDOW_SECONDS', 60)
        user_max = getattr(settings, 'ANALYZE_GAME_USER_MAX_REQUESTS', 10)
        ip_max = getattr(settings, 'ANALYZE_GAME_IP_MAX_REQUESTS', 20)

        user_key = get_analyze_rate_user_key(request.user.id)
        user_count = increment_counter(user_key, timeout=window)
        if user_count > user_max:
            return JsonResponse({'error': 'Too many requests'}, status=429)

        ip_key = get_analyze_rate_ip_key(get_client_ip(request))

        ip_count = increment_counter(ip_key, timeout=window)
        if ip_count > ip_max:
            return JsonResponse({'error': 'Too many requests'}, status=429)

        if not isinstance(moves, list):
            return JsonResponse({'error': 'Moves must be a list'}, status=400)
            
        if len(moves) > MAX_ANALYSIS_MOVES:
            return JsonResponse({'error': f'Moves list cannot exceed {MAX_ANALYSIS_MOVES} entries'}, status=400)

        for m in moves:
            if not isinstance(m, str) or len(m) > MAX_MOVE_LENGTH:
                return JsonResponse({'error': f'Move must be a string of at most {MAX_MOVE_LENGTH} characters'}, status=400)

        captures = checks = checkmates = promotions = blunders = mistakes = 0
        game = ChessGame()
        game.white_time = 10 ** 9
        game.black_time = 10 ** 9

        # The whole analysis has to fit in this many seconds. Past the
        # deadline the moves analysed so far are returned.
        ANALYSIS_TIMEOUT_SECONDS = getattr(settings, 'ANALYSIS_TIMEOUT_SECONDS', 10)
        deadline = time.monotonic() + ANALYSIS_TIMEOUT_SECONDS
        truncated = False

        def _engine_move():
            # A single engine call may not outlive what is left of the budget.
            game._analysis_timeout = max(1, deadline - time.monotonic())
            # Four plies, the depth the review has always used.
            return game.get_ai_move(depth=4)

        plies = []
        for idx, notation in enumerate(moves[:80]): # Cap at 80 for perf
            if time.monotonic() >= deadline:
                truncated = True
                break

            best_move = None
            try:
                best_move = _engine_move()
            except Exception as ex:
                logger.warning('Failed to get best move from engine for %s: %s', notation, ex)

            actual_from = actual_to = None
            clean_notation = notation.replace('+', '').replace('#', '')
            
            for r in range(8):
                for c in range(8):
                    piece = game.board[r][c]
                    if piece and game._color(piece) == game.current_turn:
                        for mv in game.get_valid_moves(r, c):
                            try:
                                tn = game._notation(r, c, mv['row'], mv['col'], piece, game.board[mv['row']][mv['col']], game.serialize_board(), game.serialize_castling_rights(), game._serialize_ep())
                                if tn.replace('+', '').replace('#', '') == clean_notation:
                                    actual_from, actual_to = (r, c), (mv['row'], mv['col'])
                            except Exception as ex:
                                logger.warning('Failed to generate notation during search: %s', ex)
                    if actual_from:
                        break
                if actual_from:
                    break

            if not actual_from or not actual_to:
                logger.warning('Could not resolve move notation %s, stopping analysis', notation)
                break

            # Now that it's resolved, increment stats
            if 'x' in notation:
                captures += 1
            if notation.endswith('+'):
                checks += 1
            if notation.endswith('#'):
                checkmates += 1
            if '=' in notation:
                promotions += 1

            best_notation = '?'
            if best_move and game.board[best_move['from_row']][best_move['from_col']]:
                try:
                    best_notation = game._notation(best_move['from_row'], best_move['from_col'], best_move['to_row'], best_move['to_col'], game.board[best_move['from_row']][best_move['from_col']], game.board[best_move['to_row']][best_move['to_col']], game.serialize_board(), game.serialize_castling_rights(), game._serialize_ep()).replace('+', '').replace('#', '')
                except Exception as ex:
                    logger.warning('Failed to get notation for best move: %s', ex)

            # A mating move cannot be improved on, whatever the engine chose.
            is_best = notation.endswith('#') or bool(
                best_move and _same_squares(best_move, actual_from, actual_to)
            )

            # The same search may have scored the played move as an alternative.
            played_eval = None
            if best_move:
                for alt in best_move.get('alts') or []:
                    if _same_squares(alt, actual_from, actual_to):
                        played_eval = alt.get('eval')
                        break

            plies.append({
                'move_num': idx // 2 + 1,
                'white': idx % 2 == 0,
                'played': notation,
                'best': best_notation,
                'is_best': is_best,
                'best_eval': best_move.get('eval') if best_move else None,
                'played_eval': played_eval,
            })

            game.make_move(actual_from[0], actual_from[1], actual_to[0], actual_to[1])
            game.last_ts = time.time()

        opening = detect_opening(moves) or 'Unknown'

        # Get evaluation of the final position
        final_eval = None
        if time.monotonic() < deadline:
            try:
                final_move = _engine_move()
                if final_move:
                    final_eval = final_move.get('eval')
            except Exception as ex:
                logger.warning('Failed to get final evaluation: %s', ex)
        else:
            truncated = True

        # Evaluations are in centipawns from White's side. A move is judged
        # by what the engine expected from its own choice against what the
        # played move led to: the next position's evaluation, unless the
        # search already scored the played move.
        move_analysis_details = []
        for i, ply in enumerate(plies):
            played_eval = ply['played_eval']
            if played_eval is None:
                played_eval = plies[i + 1]['best_eval'] if i + 1 < len(plies) else final_eval

            loss = None
            if ply['best_eval'] is not None and played_eval is not None:
                loss = ply['best_eval'] - played_eval
                if not ply['white']:
                    loss = -loss
                loss = max(0, loss)

            move_class = _classify_move(ply['is_best'], loss)
            if move_class == 'Blunder':
                blunders += 1
            elif move_class == 'Mistake':
                mistakes += 1

            move_analysis_details.append({
                'move_num': ply['move_num'],
                'color': 'White' if ply['white'] else 'Black',
                'played': ply['played'],
                'best': ply['best'],
                'class': move_class,
                'eval': ply['best_eval'],
            })

        # Moves the engine could not judge say nothing about accuracy.
        judged = sum(1 for detail in move_analysis_details if detail['class'] != 'Unknown')
        bad_moves = blunders + mistakes
        accuracy = round(((judged - bad_moves) / judged) * 100) if judged > 0 else None

        response_data = {
            'result': result,
            'end_reason': reason,
            'opening': opening,
            'captures': captures, 'checks': checks, 'checkmates': checkmates,
            'promotions': promotions, 'blunders': blunders, 'mistakes': mistakes,
            'accuracy': accuracy, 'total_moves': (len(moves) + 1) // 2, 'move_analysis_details': move_analysis_details,
            'move_analysis': [detail['class'] for detail in move_analysis_details],
            'analysis_timeout_seconds': ANALYSIS_TIMEOUT_SECONDS,
            'truncated': truncated,
            'final_eval': final_eval
        }

        response = JsonResponse(response_data)
        response['X-Analysis-Timeout'] = str(ANALYSIS_TIMEOUT_SECONDS)
        return response
    except Exception as e:
        logger.error('Failed to analyze game: %s', e)
        return JsonResponse({'error': 'Failed to analyze game'}, status=400)


_LESSON_NAMES = (
    "How Pieces Move",
    "Check and Checkmate",
    "Castling",
    "Opening Principles",
    "Chess Notation",
    "Piece Values",
    "En Passant",
    "Pawn Promotion",
    
    "Forks",
    "Pins",
    "Skewers",
    "Discovered Attacks",
    "Double Attacks",
    "Removing the Defender",
    "Deflection",
    "Decoy",

    "Pawn Structures",
    "King Safety",
    "Piece Activity",
    "Basic Endgames",
)

LESSON_LEVELS = [
    {
        "id": 1,
        "title": "Chess Fundamentals",
        "lessons": [
            "How Pieces Move",
            "Check and Checkmate",
            "Castling",
            "Opening Principles",
            "Chess Notation",
            "Piece Values",
            "En Passant",
            "Pawn Promotion",
        ],
    },
    {
        "id": 2,
        "title": "Basic Tactics",
        "lessons": [
            "Forks",
            "Pins",
            "Skewers",
            "Discovered Attacks",
            "Double Attacks",
            "Removing the Defender",
            "Deflection",
            "Decoy",
        ],
    },
    {
        "id": 3,
        "title": "Advanced Concepts",
        "lessons": [
            "Pawn Structures",
            "King Safety",
            "Piece Activity",
            "Basic Endgames",
        ],
    },
]

def _lesson_name_from_slug(lesson_slug):
    for name in _LESSON_NAMES:
        if slugify(name) == lesson_slug:
            return name
    return None


def _resolve_lesson_name(url_key):
    if url_key in _LESSON_NAMES:
        return url_key
    return _lesson_name_from_slug(url_key)


def get_unlocked_lessons(completed_lessons):
    unlocked = set()

    for level_index, level in enumerate(LESSON_LEVELS):
        
        lessons = level["lessons"]
        
        previous_level_complete = True

        if level_index > 0:
            previous_level = LESSON_LEVELS[level_index - 1]
            previous_level_complete = all(
                lesson in completed_lessons
                for lesson in previous_level["lessons"]
            )

        if not previous_level_complete:
            continue

        for i, lesson in enumerate(lessons):
            if i == 0:
                unlocked.add(lesson)
            elif lessons[i - 1] in completed_lessons:
                unlocked.add(lesson)

    return unlocked

def lesson_detail_view(request, lesson_name):
    resolved_name = _resolve_lesson_name(lesson_name)
    if resolved_name is not None:
        lesson_name = resolved_name

    lesson_data = {
        "How Pieces Move": {
            "title": "How Pieces Move",
            "description": "Learn how each chess piece moves on the board.",
            "practice_question": "Which piece can move any number of squares in any direction?",
            "practice_answer": "Queen",
            "quiz_question": "Which piece can jump over other pieces?",
            "quiz_options": [
                "Bishop",
                "Rook",
                "Knight",
                "Queen"
            ],
            "quiz_answer": "Knight",
            "content": [
                "Pawn moves forward one square and captures diagonally.",
                "Knight moves in an L-shape and can jump over pieces.",
                "Bishop moves diagonally across the board.",
                "Rook moves horizontally and vertically.",
                "Queen combines rook and bishop movement.",
                "King moves one square in any direction."
            ],

            "board_examples": [
                {
                    "title": "Pawn Movement",
                    "position": {
                        "e2": "P"
                    },
                    "highlight": [
                        "e3",
                        "e4"
                    ]
                },

                {
                    "title": "Knight Movement",
                    "position": {
                        "g1": "N"
                    },
                    "highlight": [
                        "e2",
                        "f3",
                        "h3"
                    ]
                },

                {
                    "title": "Bishop Movement",
                    "position": {
                        "d4": "B"
                    },
                    "highlight": [
                        "c3",
                        "b2",
                        "a1",
                        "e5",
                        "f6",
                        "g7",
                        "h8"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the knight from g1 to f3.",
                    "expected_move": "g1-f3"
                },
                {
                    "instruction": "Move the bishop from f1 to c4.",
                    "expected_move": "f1-c4"
                },
                {
                    "instruction": "Move the rook from a1 to a4.",
                    "expected_move": "a1-a4"
                },
                {
                    "instruction": "Move the queen from d1 to h5.",
                    "expected_move": "d1-h5"
                },
                {
                    "instruction": "Move the king from e1 to e2.",
                    "expected_move": "e1-e2"
                }
            ],
            "practice_position": {
                "g1": "N",
                "f1": "B",
                "a1": "R",
                "d1": "Q",
                "e1": "K"
            },
        },


        "Check and Checkmate": {
            "title": "Check and Checkmate",
            "description": "Understand checks and winning positions.",
            "practice_question": "What is the difference between check and checkmate?",
            "practice_answer": "Check can be escaped. Checkmate cannot be escaped and ends the game.",
            "quiz_question": "What ends a chess game immediately?",
            "quiz_options": [
                "Check",
                "Checkmate",
                "Castling",
                "Promotion"
            ],
            "quiz_answer": "Checkmate",
            "content": [
                "A king under attack is in check.",
                "A player must respond to a check immediately.",
                "You can escape check by moving, blocking, or capturing.",
                "Checkmate occurs when no legal move can save the king.",
                "Checkmate immediately ends the game."
            ],
            "board_examples": [
                {
                    "title": "Check Example",
                    "position": {
                        "e8": "K",
                        "e1": "R"
                    },
                    "highlight": ["e8"]
                },
                {
                    "title": "Simple Checkmate",
                    "position": {
                        "h8": "K",
                        "g7": "Q",
                        "f6": "K"
                    },
                    "highlight": ["g7"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the queen from h5 to f7 and deliver checkmate.",
                    "expected_move": "h5-f7"
                }
            ],

            "practice_position": {
                "h5": "Q",
                "e8": "K",
                "c4": "B",
                "f7": "P"
            },
        },

        "Castling": {
            "title": "Castling",
            "description": "Learn how castling protects your king.",
            "practice_question": "Can you castle if your king has already moved?",
            "practice_answer": "No. Castling is only allowed if the king and rook have never moved.",
            "quiz_question": "What is the main purpose of castling?",
            "quiz_options": [
                "To capture an opponent's piece",
                "To protect the king and activate the rook",
                "To promote a pawn",
                "To check the opponent's king"
            ],
            "quiz_answer": "To protect the king and activate the rook",
            "content": [
                "Castling moves the king and rook simultaneously.",
                "The king cannot castle if it has already moved.",
                "The rook involved must not have moved.",
                "The king cannot castle through check.",
                "Castling improves king safety and rook activity."
            ],
            "board_examples": [
                {
                    "title": "Kingside Castling",
                    "position": {
                        "e1": "K",
                        "h1": "R"
                    },
                    "highlight": [
                        "f1",
                        "g1"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Castle kingside by moving the king from e1 to g1.",
                    "expected_move": "e1-g1"
                }
            ],

            "practice_position": {
                "e1": "K",
                "h1": "R",
                "a1": "R"
            }
        },

        "Opening Principles": {
            "title": "Opening Principles",
            "description": "Build a strong position from the start.",
            "practice_question": "What area of the board should you try to control during the opening?",
            "practice_answer": "The center of the board.",
            "quiz_question": "What should you generally do first in the opening?",
            "quiz_options": [
                "Attack immediately",
                "Develop pieces",
                "Move queen repeatedly",
                "Push edge pawns"
            ],
            "quiz_answer": "Develop pieces",
            "content": [
                "Control the center with pawns and pieces.",
                "Develop knights and bishops early.",
                "Avoid moving the same piece repeatedly.",
                "Castle early for king safety.",
                "Connect your rooks."
            ],
            "board_examples": [
                {
                    "title": "Control the Center",
                    "position": {
                        "e2": "P",
                        "d2": "P"
                    },
                    "highlight": [
                        "e4",
                        "d4"
                    ]
                },
                {
                    "title": "Develop Knights",
                    "position": {
                        "b1": "N",
                        "g1": "N"
                    },
                    "highlight": [
                        "c3",
                        "f3"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Control the center by playing e4.",
                    "expected_move": "e2-e4"
                },
                {
                    "instruction": "Develop the knight from g1 to f3.",
                    "expected_move": "g1-f3"
                },
                {
                    "instruction": "Develop the bishop from f1 to c4.",
                    "expected_move": "f1-c4"
                }
            ],

            "practice_position": {
                "e1": "K",
                "d1": "Q",
                "f1": "B",
                "g1": "N",
                "e2": "P",
                "d2": "P"
            },
        },

        "Chess Notation": {
            "title": "Chess Notation",
            "description": "Learn how chess moves are recorded.",
            "practice_question": "What does Nf3 mean?",
            "practice_answer": "Knight moves to f3.",
            "quiz_question": "Which letter represents the King?",
            "quiz_options": [
                "Q",
                "K",
                "N",
                "R"
            ],
            "quiz_answer": "K",
            "content": [
                "Chess notation records every move in a game.",
                "Files are labeled a through h.",
                "Ranks are labeled 1 through 8.",
                "Pieces use letter abbreviations.",
                "Notation helps analyze games."
            ],
            "board_examples": [
                {
                    "title": "Square e4",
                    "position": {
                        "e4": "P"
                    },
                    "highlight": ["e4"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the pawn from e2 to e4.",
                    "expected_move": "e2-e4"
                }
            ],
            "practice_position": {
                "e2": "P"
            }
        },

        "Piece Values": {
            "title": "Piece Values",
            "description": "Understand the relative value of pieces.",
            "practice_question": "Which piece is usually worth 9 points?",
            "practice_answer": "Queen",
            "quiz_question": "How many points is a rook worth?",
            "quiz_options": [
                "3",
                "5",
                "9",
                "1"
            ],
            "quiz_answer": "5",
            "content": [
                "Pawn = 1 point.",
                "Knight = 3 points.",
                "Bishop = 3 points.",
                "Rook = 5 points.",
                "Queen = 9 points.",
                "King is invaluable."
            ],
            "board_examples": [
                {
                    "title": "Major Pieces",
                    "position": {
                        "d1": "Q",
                        "a1": "R"
                    },
                    "highlight": ["d1", "a1"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the queen from d1 to d4.",
                    "expected_move": "d1-d4"
                }
            ],
            "practice_position": {
                "d1": "Q"
            }
        },

        "En Passant": {
            "title": "En Passant",
            "description": "Learn the special pawn capture rule.",
            "practice_question": "When can en passant be played?",
            "practice_answer": "Immediately after a pawn advances two squares.",
            "quiz_question": "How long is an en passant opportunity available?",
            "quiz_options": [
                "One move",
                "Two moves",
                "Forever",
                "Until capture"
            ],
            "quiz_answer": "One move",
            "content": [
                "En passant is a special pawn capture.",
                "It occurs after an enemy pawn advances two squares.",
                "The capture must be immediate.",
                "The captured pawn is removed.",
                "The opportunity disappears after one move."
            ],
            "board_examples": [
                {
                    "title": "En Passant Opportunity",
                    "position": {
                        "e5": "P",
                        "d5": "P"
                    },
                    "highlight": ["d6"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Capture the pawn en passant.",
                    "expected_move": "d5-d6"
                }
            ],
            "practice_position": {
                "e5": "P",
                "d5": "P"
            }
        },

        "Pawn Promotion": {
            "title": "Pawn Promotion",
            "description": "Promote a pawn when it reaches the final rank.",
            "practice_question": "What piece is most commonly chosen during promotion?",
            "practice_answer": "Queen",
            "quiz_question": "When can a pawn be promoted?",
            "quiz_options": [
                "At the 5th rank",
                "At the 6th rank",
                "At the 8th rank",
                "After capturing"
            ],
            "quiz_answer": "At the 8th rank",
            "content": [
                "A pawn promotes upon reaching the last rank.",
                "Promotion usually becomes a queen.",
                "You may choose rook, bishop, knight, or queen.",
                "Promotion can decide games.",
                "Always look for promotion opportunities."
            ],
            "board_examples": [
                {
                    "title": "Promotion Square",
                    "position": {
                        "g7": "P"
                    },
                    "highlight": ["g8"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the pawn from g7 to g8.",
                    "expected_move": "g7-g8"
                }
            ],
            "practice_position": {
                "g7": "P"
            }
        },
        
        "Forks": {
            "title": "Forks",
            "description": "Attack multiple pieces with one move.",
            "steps": [
                {
                    "instruction": "Move the knight to fork the king and queen.",
                    "fen": "8/3q4/8/4N3/8/8/8/4K3 w - - 0 1",
                    "correct_move": "Nc6"
                }
            ],
            "practice_question": "Which piece is most famous for creating forks?",
            "practice_answer": "Knight",
            "quiz_question": "What is a fork in chess?",
            "quiz_options": [
                "Attacking the king",
                "Attacking two or more targets simultaneously",
                "Moving the queen",
                "Creating a pin"
            ],
            "quiz_answer": "Attacking two or more targets simultaneously",
            "content": [
                "A fork attacks two or more targets simultaneously.",
                "Knights are especially effective at creating forks.",
                "Forks often win material."
            ],
            "board_examples": [
                {
                    "title": "Knight Fork",
                    "position": {
                        "f6": "N",
                        "e8": "Q",
                        "g8": "R"
                    },
                    "highlight": [
                        "e8",
                        "g8"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the knight from e5 to c6 and fork the king and queen.",
                    "expected_move": "e5-c6"
                }
            ],
            "practice_position": {
                "e5": "N",
                "d8": "Q",
                "e8": "K"
            }
        },

        "Pins": {
            "title": "Pins",
            "description": "Restrict an opponent's piece from moving.",
            "practice_question": "What is an absolute pin?",
            "practice_answer": "A pin where moving the pinned piece would expose the king to attack.",
            "quiz_question": "What is an absolute pin?",
            "quiz_options": [
                "A pin against a rook",
                "A pin against a bishop",
                "A pin where moving exposes the king",
                "A pin against a queen"
            ],
            "quiz_answer": "A pin where moving exposes the king",
            "content": [
                "A pin occurs when moving a piece exposes a more valuable piece.",
                "Absolute pins involve the king.",
                "Pinned pieces often become vulnerable.",
                "Bishops and rooks commonly create pins.",
                "Pins can create tactical opportunities."
            ],
            "board_examples": [
                {
                    "title": "Bishop Pin",
                    "position": {
                        "b5": "B",
                        "c6": "N",
                        "e8": "K"
                    },
                    "highlight": [
                        "c6",
                        "e8"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the bishop from b5 to pin the knight to the king.",
                    "expected_move": "f1-b5"
                }
            ],
            "practice_position": {
                "f1": "B",
                "c6": "N",
                "e8": "K"
            }
        },

        "Skewers": {
            "title": "Skewers",
            "description": "Force a valuable piece to move and expose another piece.",
            "practice_question": "In a skewer, which piece is attacked first?",
            "practice_answer": "The more valuable piece is attacked first.",
            "quiz_question": "In a skewer, which piece is attacked first?",
            "quiz_options": [
                "The least valuable piece",
                "The king only",
                "The more valuable piece",
                "A pawn"
            ],
            "quiz_answer": "The more valuable piece",
            "content": [
                "A skewer is the opposite of a pin.",
                "The more valuable piece is attacked first.",
                "After it moves, a less valuable piece is exposed.",
                "Bishops, rooks, and queens often create skewers.",
                "Skewers frequently win material."
            ],
            "board_examples": [
                {
                    "title": "Queen Skewer",
                    "position": {
                        "a4": "Q",
                        "e8": "K",
                        "e7": "R"
                    },
                    "highlight": [
                        "e8",
                        "e7"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the queen from a4 to create a skewer.",
                    "expected_move": "a4-e8"
                }
            ],
            "practice_position": {
                "a4": "Q",
                "e8": "K",
                "d7": "R"
            }
        },

        "Discovered Attacks": {
            "title": "Discovered Attacks",
            "description": "Reveal an attack by moving another piece.",
            "practice_question": "What creates a discovered attack?",
            "practice_answer": "Moving one piece away to reveal an attack from another piece.",
            "quiz_question": "What creates a discovered attack?",
            "quiz_options": [
                "Promoting a pawn",
                "Moving a piece to reveal another attack",
                "Castling",
                "Checking the king"
            ],
            "quiz_answer": "Moving a piece to reveal another attack",
            "content": [
                "One piece moves away to uncover another attack.",
                "Discovered attacks can be very powerful.",
                "Discovered checks are especially dangerous.",
                "Always look for hidden lines between pieces.",
                "Coordinate your pieces to create tactical threats."
            ],
            "board_examples": [
                {
                    "title": "Discovered Attack",
                    "position": {
                        "a1": "R",
                        "a2": "N",
                        "a8": "Q"
                    },
                    "highlight": [
                        "a2",
                        "a8"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the knight from e2 to c3 to reveal the rook attack.",
                    "expected_move": "e2-c3"
                }
            ],
            "practice_position": {
                "a1": "R",
                "e2": "N",
                "a8": "Q"
            }
        },

        "Double Attacks": {
            "title": "Double Attacks",
            "description": "Attack two targets at the same time.",
            "practice_question": "What is the goal of a double attack?",
            "practice_answer": "To attack multiple targets simultaneously.",
            "quiz_question": "A fork is a type of?",
            "quiz_options": [
                "Pin",
                "Double Attack",
                "Skewer",
                "Promotion"
            ],
            "quiz_answer": "Double Attack",
            "content": [
                "A double attack threatens two targets at once.",
                "Forks are common examples of double attacks.",
                "Double attacks often win material.",
                "Look for overloaded defenders.",
                "Knights excel at double attacks."
            ],
            "board_examples": [
                {
                    "title": "Knight Double Attack",
                    "position": {
                        "e5": "N",
                        "d7": "Q",
                        "f7": "R"
                    },
                    "highlight": ["d7", "f7"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the knight from e5 to c6 and attack two pieces.",
                    "expected_move": "e5-c6"
                }
            ],
            "practice_position": {
                "e5": "N",
                "d8": "Q",
                "e8": "K"
            }
        },

        "Removing the Defender": {
            "title": "Removing the Defender",
            "description": "Eliminate a key defending piece.",
            "practice_question": "Why remove a defender?",
            "practice_answer": "To make another piece vulnerable.",
            "quiz_question": "What happens after removing a defender?",
            "quiz_options": [
                "The defended piece becomes vulnerable",
                "The king castles",
                "A pawn promotes",
                "The game ends"
            ],
            "quiz_answer": "The defended piece becomes vulnerable",
            "content": [
                "Many pieces rely on defenders.",
                "Removing a defender creates tactical opportunities.",
                "Captures often begin combinations.",
                "Always identify key defenders.",
                "Winning defenders wins material."
            ],
            "board_examples": [
                {
                    "title": "Remove the Defender",
                    "position": {
                        "d8": "q",
                        "d7": "R"
                    },
                    "highlight": ["d7"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Capture the defending rook on d7.",
                    "expected_move": "d1-d7"
                }
            ],
            "practice_position": {
                "d1": "Q",
                "d7": "R",
                "d8": "q"
            }
        },

        "Deflection": {
            "title": "Deflection",
            "description": "Force a piece away from an important square.",
            "practice_question": "What is the purpose of deflection?",
            "practice_answer": "To move a defender away from its duty.",
            "quiz_question": "Deflection works by?",
            "quiz_options": [
                "Promoting a pawn",
                "Moving a piece away from defense",
                "Castling",
                "Checking the king"
            ],
            "quiz_answer": "Moving a piece away from defense",
            "content": [
                "Deflection distracts a defending piece.",
                "The defender abandons an important square.",
                "This often wins material.",
                "Deflection appears in many combinations.",
                "Look for overloaded pieces."
            ],
            "board_examples": [
                {
                    "title": "Deflect the Rook",
                    "position": {
                        "d8": "R",
                        "d7": "Q"
                    },
                    "highlight": ["d8"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Move the queen to d8 and deflect the rook.",
                    "expected_move": "d1-d8"
                }
            ],
            "practice_position": {
                "d1": "Q",
                "d8": "R",
                "d7": "Q"
            }
        },

        "Decoy": {
            "title": "Decoy",
            "description": "Lure a piece onto a vulnerable square.",
            "practice_question": "What is a decoy tactic?",
            "practice_answer": "Luring a piece to an unfavorable square.",
            "quiz_question": "What does a decoy do?",
            "quiz_options": [
                "Protects a pawn",
                "Lures a piece",
                "Promotes a pawn",
                "Creates a draw"
            ],
            "quiz_answer": "Lures a piece",
            "content": [
                "A decoy lures a piece away.",
                "The target is forced onto a bad square.",
                "Decoys often lead to checkmate.",
                "Sacrifices are common in decoy tactics.",
                "Always look for forced responses."
            ],
            "board_examples": [
                {
                    "title": "Decoy the King",
                    "position": {
                        "g7": "Q",
                        "h8": "K"
                    },
                    "highlight": ["g7"]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Sacrifice the queen on g8 to lure the king.",
                    "expected_move": "g7-g8"
                }
            ],
            "practice_position": {
                "g7": "Q",
                "h8": "K"
            }
        },
        
        "Pawn Structures": {
            "title": "Pawn Structures",
            "description": "Understand how pawns shape the game.",
            "practice_question": "What type of pawn has no friendly pawns on adjacent files?",
            "practice_answer": "An isolated pawn.",
            "quiz_question": "Which pawn is considered a weakness?",
            "quiz_options": [
                "Passed pawn",
                "Connected pawn",
                "Isolated pawn",
                "Protected pawn"
            ],
            "quiz_answer": "Isolated pawn",
            "content": [
                "Pawn structure determines long-term strategy.",
                "Avoid creating unnecessary weak pawns.",
                "Passed pawns can become powerful assets.",
                "Pawn chains provide support and control.",
                "Doubled and isolated pawns can become weaknesses."
            ],
            "board_examples": [
                {
                    "title": "Pawn Chain",
                    "position": {
                        "c3": "P",
                        "d4": "P",
                        "e5": "P"
                    },
                    "highlight": [
                        "c3",
                        "d4",
                        "e5"
                    ]
                },
                {
                    "title": "Isolated Pawn",
                    "position": {
                        "d4": "P"
                    },
                    "highlight": [
                        "d4"
                    ]
                }
            ],
            
            "lesson_steps": [
                {
                    "instruction": "Advance the passed pawn from d5 to d6.",
                    "expected_move": "d5-d6"
                }
            ],
            
            "practice_position": {
                "d5": "P",
                "e1": "K"
            },
        },
        
        "King Safety": {
            "title": "King Safety",
            "description": "Keep your king protected throughout the game.",
            "practice_question": "What is usually the safest way to protect your king in the opening?",
            "practice_answer": "Castling.",
            "quiz_question": "What is the safest way to protect your king in the opening?",
            "quiz_options": [
                "Move the king forward",
                "Keep the king in the center",
                "Castle",
                "Trade queens immediately"
            ],
            "quiz_answer": "Castle",
            "content": [
                "Castle early whenever possible.",
                "Avoid weakening squares around your king.",
                "Keep defensive pieces nearby.",
                "Watch for open files and diagonals.",
                "A safe king allows active play elsewhere."
            ],
            "board_examples": [
                {
                    "title": "Safe Castled King",
                    "position": {
                        "g1": "K",
                        "f2": "P",
                        "g2": "P",
                        "h2": "P"
                    },
                    "highlight": [
                        "f2",
                        "g2",
                        "h2"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Castle kingside.",
                    "expected_move": "e1-g1"
                }
            ],
            "practice_position": {
                "e1": "K",
                "h1": "R"
            }
        },

        "Piece Activity": {
            "title": "Piece Activity",
            "description": "Maximize the effectiveness of your pieces.",
            "practice_question": "What is generally better: an active piece or a passive piece?",
            "practice_answer": "An active piece.",
            "quiz_question": "Which piece is generally stronger?",
            "quiz_options": [
                "A trapped piece",
                "A passive piece",
                "An active piece",
                "A blocked piece"
            ],
            "quiz_answer": "An active piece",
            "content": [
                "Active pieces control more squares.",
                "Avoid placing pieces on passive squares.",
                "Coordinate pieces to work together.",
                "Occupy open files and strong outposts.",
                "Activity often outweighs material advantages."
            ],
            "board_examples": [
                {
                    "title": "Active Knight",
                    "position": {
                        "d5": "N"
                    },
                    "highlight": [
                        "b4",
                        "b6",
                        "c3",
                        "c7",
                        "e3",
                        "e7",
                        "f4",
                        "f6"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Activate the rook by moving from a1 to a7.",
                    "expected_move": "a1-a7"
                }
            ],

            "practice_position": {
                "a1": "R",
                "e1": "K"
            },
        },

        "Basic Endgames": {
            "title": "Basic Endgames",
            "description": "Learn essential endgame techniques.",
            "practice_question": "Which piece becomes especially important in the endgame?",
            "practice_answer": "The king.",
            "quiz_question": "Which piece becomes especially powerful in the endgame?",
            "quiz_options": [
                "Knight",
                "Bishop",
                "Queen",
                "King"
            ],
            "quiz_answer": "King",
            "content": [
                "King activity becomes very important.",
                "Learn basic king and pawn endings.",
                "Understand opposition and triangulation.",
                "Promote passed pawns whenever possible.",
                "Practice common checkmating patterns."
            ],
            "board_examples": [
                {
                    "title": "King and Pawn Endgame",
                    "position": {
                        "e5": "K",
                        "e6": "P",
                        "e8": "K"
                    },
                    "highlight": [
                        "e6",
                        "e7",
                        "e8"
                    ]
                },
                {
                    "title": "Opposition",
                    "position": {
                        "e4": "K",
                        "e6": "K"
                    },
                    "highlight": [
                        "e4",
                        "e6"
                    ]
                }
            ],
            "lesson_steps": [
                {
                    "instruction": "Promote the pawn by moving from e7 to e8.",
                    "expected_move": "e7-e8"
                }
            ],
            "practice_position": {
                "e7": "P",
                "e1": "K",
                "e8": ""
            }
        }
    }

    lesson = lesson_data.get(lesson_name)

    if lesson is None:
        raise Http404("Lesson not found")

    lesson_order = list(lesson_data.keys())

    current_index = lesson_order.index(lesson_name)

    previous_lesson = None
    next_lesson = None

    if current_index > 0:
        previous_lesson = lesson_order[current_index - 1]

    if current_index < len(lesson_order) - 1:
        next_lesson = lesson_order[current_index + 1]

    is_completed = False

    if request.user.is_authenticated:
        is_completed = LessonProgress.objects.filter(
            user=request.user,
            lesson_name=lesson_name,
            completed=True
        ).exists()

    difficulty = "Beginner"
    if lesson_name in [
        "Forks",
        "Pins",
        "Skewers",
        "Discovered Attacks",
        "Double Attacks",
        "Removing the Defender",
        "Deflection",
        "Decoy",
        
    ]:
        difficulty = "Intermediate"

    elif lesson_name in [
        "Pawn Structures",
        "King Safety",
        "Piece Activity",
        "Basic Endgames"
    ]:
        difficulty = "Advanced"

    return render(
        request,
        "game/lesson_detail.html",
        {
            "lesson": lesson,
            "lesson_steps": lesson.get("lesson_steps", lesson.get("steps", [])),
            "practice_position": lesson.get("practice_position"),
            "board_examples": lesson.get(
                "board_examples",
                []
            ),
            "previous_lesson": previous_lesson,
            "next_lesson": next_lesson,
            "is_completed": is_completed,
            "difficulty": difficulty,

        }
    )


@login_required
@require_POST
def complete_lesson(request, lesson_name):
    resolved_name = _resolve_lesson_name(lesson_name)
    if resolved_name is not None:
        lesson_name = resolved_name

    if lesson_name not in _LESSON_NAMES:
        raise Http404("Lesson not found")

    completed_lessons = list(
        LessonProgress.objects.filter(
            user=request.user,
            completed=True
        ).values_list(
            "lesson_name",
            flat=True
        )
    )

    # The lesson map only shows the order; this is where it is enforced.
    if lesson_name not in get_unlocked_lessons(completed_lessons):
        messages.error(
            request,
            "Finish the earlier lessons first to unlock this one."
        )
        return redirect("lessons")

    with transaction.atomic():
        # The row lock makes two submissions at once award the XP only once.
        progress, _ = LessonProgress.objects.select_for_update().get_or_create(
            user=request.user,
            lesson_name=lesson_name,
        )

        if not progress.completed:
            progress.completed = True
            progress.completed_at = timezone.now()
            progress.save(update_fields=["completed", "completed_at"])

            award_xp(request.user, progression.XP_LESSON)

    return redirect(
        "lesson_detail",
        lesson_name=slugify(lesson_name)
    )


def lesson_map_view(request):

    completed_lessons = []

    if request.user.is_authenticated:
        completed_lessons = list(
            LessonProgress.objects.filter(
                user=request.user,
                completed=True
            ).values_list(
                "lesson_name",
                flat=True
            )
        )

    completed_count = len(completed_lessons)

    total_lessons = sum(
        len(level["lessons"])
        for level in LESSON_LEVELS
    )

    unlocked_lessons = get_unlocked_lessons(
        completed_lessons
    )

    return render(
        request,
        "game/lesson_map.html",
        {
            "levels": LESSON_LEVELS,
            "completed_lessons": completed_lessons,
            "completed_count": completed_count,
            "total_lessons": total_lessons,
            "unlocked_lessons": unlocked_lessons,
        }
    )


@rate_limit(
    window_setting="OPENING_RATE_LIMIT_WINDOW_SECONDS",
    max_setting="OPENING_RATE_LIMIT_MAX_REQUESTS",
    prefix="opening_lookup",
    error_message=(
        "Opening lookup rate limit reached. Please try again shortly."
    )
)
def opening_trainer(request):
    return render(
        request,
        "game/opening_trainer.html",
        {
            "openings": OPENINGS,
        }
    )

@ensure_csrf_cookie
@rate_limit(
    window_setting="OPENING_RATE_LIMIT_WINDOW_SECONDS",
    max_setting="OPENING_RATE_LIMIT_MAX_REQUESTS",
    prefix="opening_lookup",
    error_message=(
        "Opening lookup rate limit reached. Please try again shortly."
    )
)
def opening_detail(request, slug):
    opening = next(
        (
            opening
            for opening in OPENINGS
            if opening["slug"] == slug
        ),
        None,
    )

    if opening is None:
        raise Http404("Opening not found")

    return render(
        request,
        "game/opening_detail.html",
        {
            "opening": opening,
        }
    )

@login_required
@require_POST
def update_opening_stats(request):
    data = _json_object(request)
    if data is None:
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON payload",
            },
            status=400,
        )

    opening_name = data.get("opening_name")
    completed = data.get("completed", False)
    accuracy = data.get("accuracy", 0)

    if not opening_name:
        return JsonResponse(
            {
                "success": False,
                "error": "Opening name is required",
            },
            status=400,
        )

    valid_openings = {
        opening["name"]
        for opening in OPENINGS
    }

    if not isinstance(opening_name, str) or opening_name not in valid_openings:
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid opening name",
            },
            status=400,
        )

    if not isinstance(completed, bool):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid completed flag",
            },
            status=400,
        )

    if isinstance(accuracy, bool) or not isinstance(accuracy, (int, float)):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid accuracy",
            },
            status=400,
        )

    accuracy = max(0, min(100, accuracy))

    progress, first_completion = update_opening_progress(
        request.user,
        opening_name,
        completed=completed,
        accuracy=accuracy,
    )

    if completed and first_completion:
        award_xp(request.user, progression.XP_OPENING + (progression.XP_OPENING_PERFECT if accuracy == 100 else 0))

    return JsonResponse({
        "success": True,
        "accuracy": accuracy,
    })

@login_required
def achievements_view(request):
    try:
        achievements = Achievement.objects.all().order_by(
            "category",
            "title"
        )
    except Exception:
        achievements = Achievement.objects.none()

    try:
        unlocked = set(
            UserAchievement.objects.filter(
                user=request.user
            ).values_list(
                "achievement_id",
                flat=True
            )
        )
    except Exception:
        unlocked = set()

    try:
        featured_badges = FeaturedBadge.objects.filter(
            user=request.user
        ).select_related("achievement")
    except Exception:
        featured_badges = FeaturedBadge.objects.none()

    return render(
        request,
        "game/achievements.html",
        {
            "achievements": achievements,
            "unlocked": unlocked,
            "featured_badges": featured_badges,
        }
    )

@login_required
@require_POST
def feature_badge(request, achievement_id):
    achievement = get_object_or_404(
        Achievement,
        id=achievement_id
    )

    # Only unlocked badges can be featured
    if not UserAchievement.objects.filter(
        user=request.user,
        achievement=achievement
    ).exists():
        messages.error(
            request,
            "You can only feature unlocked badges."
        )
        return redirect("achievements")

    # Maximum 3 featured badges
    if FeaturedBadge.objects.filter(
        user=request.user
    ).count() >= 3:
        messages.error(
            request,
            "You can only feature up to 3 badges."
        )
        return redirect("achievements")

    FeaturedBadge.objects.get_or_create(
        user=request.user,
        achievement=achievement
    )

    messages.success(
        request,
        "Badge featured successfully."
    )

    return redirect("achievements")

@login_required
@require_POST
def remove_featured_badge(request, badge_id):
    FeaturedBadge.objects.filter(
        id=badge_id,
        user=request.user
    ).delete()

    messages.success(
        request,
        "Featured badge removed."
    )

    return redirect("achievements")

@login_required
def download_badge(request, achievement_id):
    user_achievement = get_object_or_404(
        UserAchievement,
        user=request.user,
        achievement_id=achievement_id
    )
    try:
        badge = generate_badge(
            user_achievement
        )

        safe_filename = (
            slugify(user_achievement.achievement.title)
            or f"badge_{achievement_id}"
        )

        return FileResponse(
            badge,
            as_attachment=True,
            filename=f"{safe_filename}.png",
            content_type="image/png",
        )
    except (
        FileNotFoundError,
        OSError,
    ) as exc:
        logger.error(
            "Badge generation failed for achievement %s: %s",
            achievement_id,
            exc,
        )

        return HttpResponseServerError(
            "Badge generation failed."
        )
    
def _live_replies():
    """Prefetch that leaves soft-deleted replies out of discussion.replies."""
    return Prefetch("replies", queryset=Reply.objects.filter(is_deleted=False))


def apply_discussion_sort(queryset, sort_by):
    live_reply = Q(replies__is_deleted=False)
    queryset = queryset.annotate(
        reply_count=Count("replies", filter=live_reply, distinct=True),
        bookmark_count=Count("bookmarks", distinct=True),
        last_reply_at=Max("replies__created_at", filter=live_reply),
    )

    if sort_by == "oldest":
        return queryset.order_by("created_at", "-id")

    if sort_by == "most_replies":
        return queryset.order_by("-reply_count", "-created_at", "-id")

    if sort_by == "most_bookmarked":
        return queryset.order_by("-bookmark_count", "-created_at", "-id")

    if sort_by == "recently_active":
        return queryset.order_by(
            F("last_reply_at").desc(nulls_last=True),
            "-updated_at",
            "-created_at",
            "-id"
        )

    return queryset.order_by("-created_at", "-id")


def forum_list(request):
    sort_by = request.GET.get("sort", "newest")
    page_number = request.GET.get("page", 1)
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()

    discussions = Discussion.objects.select_related(
        "user__profile"
    ).defer("user__profile__avatar").prefetch_related(_live_replies())

    if q:
        discussions = discussions.filter(
            Q(title__icontains=q) | Q(content__icontains=q)
        )
    if category:
        discussions = discussions.filter(category=category)

    user_discussions = Discussion.objects.none()
    bookmarked_discussions = Discussion.objects.none()
    bookmarked_ids = set()

    discussions = apply_discussion_sort(discussions, sort_by)

    paginator = Paginator(discussions, 20)
    page_obj = paginator.get_page(page_number)

    if request.user.is_authenticated:
        # Subqueries, not joins: a join here would also narrow the reply
        # and bookmark counts that the sort annotates afterwards.
        user_discussions = (
            Discussion.objects
            .filter(
                Q(user=request.user) |
                Q(id__in=Reply.objects.filter(
                    user=request.user
                ).values("discussion_id"))
            )
            .select_related("user")
            .prefetch_related(_live_replies())
        )
        if q:
            user_discussions = user_discussions.filter(
                Q(title__icontains=q) | Q(content__icontains=q)
            )
        if category:
            user_discussions = user_discussions.filter(category=category)

        bookmarked_discussions = (
            Discussion.objects
            .filter(id__in=DiscussionBookmark.objects.filter(
                user=request.user
            ).values("discussion_id"))
            .select_related("user")
            .prefetch_related(_live_replies())
        )
        if q:
            bookmarked_discussions = bookmarked_discussions.filter(
                Q(title__icontains=q) | Q(content__icontains=q)
            )
        if category:
            bookmarked_discussions = (
                bookmarked_discussions.filter(category=category)
            )

        user_discussions = apply_discussion_sort(
            user_discussions, sort_by
        )
        bookmarked_discussions = apply_discussion_sort(
            bookmarked_discussions, sort_by
        )

        bookmarked_ids = set(
            request.user.discussion_bookmarks.values_list(
                "discussion_id",
                flat=True
            )
        )

    return render(
        request,
        "game/forum_list.html",
        {
            "page_obj": page_obj,
            "discussions": discussions,
            "user_discussions": user_discussions,
            "bookmarked_discussions": bookmarked_discussions,
            "bookmarked_ids": bookmarked_ids,
            "sort_by": sort_by,
            "q": q,
            "selected_category": category,
            "categories": Discussion.CATEGORY_CHOICES,
        }
    )

@login_required
@require_POST
def toggle_discussion_bookmark(request, discussion_id):
    discussion = get_object_or_404(Discussion, id=discussion_id)

    bookmark, created = DiscussionBookmark.objects.get_or_create(
        user=request.user,
        discussion=discussion
    )

    if not created:
        bookmark.delete()

    next_url = request.POST.get("next")
    referer_url = request.META.get("HTTP_REFERER")
    allowed_hosts = {request.get_host()}
    require_https = request.is_secure()

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts=allowed_hosts,
        require_https=require_https,
    ):
        return redirect(next_url)
    elif referer_url and url_has_allowed_host_and_scheme(
        url=referer_url,
        allowed_hosts=allowed_hosts,
        require_https=require_https,
    ):
        return redirect(referer_url)

    return redirect("forum")

def forum_detail(request, discussion_id):
    discussion = get_object_or_404(Discussion, id=discussion_id)

    replies = (
        discussion.replies
        .select_related("user__profile", "reply_to", "reply_to__user")
        .defer("user__profile__avatar")
        .annotate(
            upvote_count=Count(
                "votes",
                filter=models.Q(votes__value=ReplyVote.UPVOTE)
            ),
            downvote_count=Count(
                "votes",
                filter=models.Q(votes__value=ReplyVote.DOWNVOTE)
            ),
        )
    )

    bookmarked_ids = set()
    user_reply_votes = {}

    if request.user.is_authenticated:
        bookmarked_ids = set(
            request.user.discussion_bookmarks.values_list(
                "discussion_id",
                flat=True
            )
        )

        user_reply_votes = {
            vote.reply_id: vote.value
            for vote in ReplyVote.objects.filter(
                user=request.user,
                reply__discussion=discussion
            )
        }

    form = ReplyForm()

    return render(
        request,
        "game/forum_detail.html",
        {
            "discussion": discussion,
            "replies": replies,
            "form": form,
            "bookmarked_ids": bookmarked_ids,
            "user_reply_votes": user_reply_votes,
        }
    )

@login_required
def forum_new(request):
    if request.method == "POST" and not request.user.is_staff:
        window_start = timezone.now() - timedelta(
            seconds=settings.FORUM_DISCUSSION_RATE_WINDOW_SECONDS
        )

        recent_discussions = Discussion.objects.filter(
            user=request.user,
            created_at__gte=window_start
        ).count()

        if recent_discussions >= settings.FORUM_DISCUSSION_MAX_REQUESTS:
            logger.warning(
                "Forum discussion rate limit exceeded: "
                "user=%s id=%s ip=%s",
                request.user.username,
                request.user.id,
                request.META.get("REMOTE_ADDR"),
            )

            messages.error(
                request,
                "You are creating discussions too quickly. "
                "Please wait before trying again."
            )

            return redirect("forum")

    if request.method == "POST":
        form = DiscussionForm(request.POST)

        if form.is_valid():
            discussion = form.save(commit=False)
            discussion.user = request.user
            discussion.save()

            messages.success(
                request,
                "Discussion created successfully."
            )

            return redirect(
                "forum_detail",
                discussion_id=discussion.id
            )
    else:
        form = DiscussionForm()

    return render(
        request,
        "game/forum_new.html",
        {
            "form": form,
        }
    )

@login_required
@require_POST
def forum_reply(request, discussion_id):
    discussion = get_object_or_404(
        Discussion,
        id=discussion_id
    )

    if not request.user.is_staff:
        window_start = timezone.now() - timedelta(
            seconds=settings.FORUM_REPLY_RATE_WINDOW_SECONDS
        )

        recent_replies = Reply.objects.filter(
            user=request.user,
            created_at__gte=window_start
        ).count()

        if recent_replies >= settings.FORUM_REPLY_MAX_REQUESTS:
            logger.warning(
                "Forum reply rate limit exceeded: "
                "user=%s id=%s ip=%s discussion=%s",
                request.user.username,
                request.user.id,
                request.META.get("REMOTE_ADDR"),
                discussion.id,
            )

            messages.error(
                request,
                "You are replying too quickly. "
                "Please wait before posting again."
            )

            return redirect(
                "forum_detail",
                discussion_id=discussion.id
            )

    form = ReplyForm(request.POST)

    reply_to_id = request.POST.get("reply_to")
    parent_reply = None

    if reply_to_id:
        # Anything that is not a plausible id is treated as a missing parent.
        if reply_to_id.isdigit() and len(reply_to_id) <= 18:
            parent_reply = Reply.objects.filter(
                id=reply_to_id,
                discussion=discussion,
                is_deleted=False
            ).first()

        if parent_reply is None:
            messages.error(
                request,
                "Selected parent reply is unavailable."
            )

            return redirect(
                "forum_detail",
                discussion_id=discussion.id
            )

    if form.is_valid():
        reply = form.save(commit=False)
        reply.discussion = discussion
        reply.user = request.user
        reply.reply_to = parent_reply
        reply.save()

        messages.success(
            request,
            "Reply posted successfully."
        )
    else:
        messages.error(
            request,
            "Reply could not be posted."
        )

    return redirect(
        "forum_detail",
        discussion_id=discussion.id
    )

@login_required
@require_POST
def forum_reply_edit(request, reply_id):
    reply = get_object_or_404(
        Reply,
        id=reply_id,
        user=request.user,
        is_deleted=False
    )

    content = request.POST.get("content", "").strip()

    if len(content) < 2:
        messages.error(request, "Reply cannot be empty.")
        return redirect("forum_detail", discussion_id=reply.discussion.id)

    updated = Reply.objects.filter(
        id=reply.id,
        user=request.user,
        is_deleted=False,
    ).update(
        content=content,
        is_edited=True,
        updated_at=timezone.now(),
    )
    if not updated:
        messages.error(request, "reply is no longer editable.")
        return redirect("forum_detail", discussion_id=reply.discussion.id)

    messages.success(request, "Reply updated successfully.")
    return redirect("forum_detail", discussion_id=reply.discussion.id)


@login_required
@require_POST
def forum_reply_delete(request, reply_id):
    reply = get_object_or_404(
        Reply,
        id=reply_id,
        user=request.user,
        is_deleted=False
    )

    deleted = Reply.objects.filter(
        id=reply.id,
        user=request.user,
        is_deleted=False,
    ).update(
        content="",
        is_deleted=True,
        updated_at=timezone.now(),
    )
    if not deleted:
        messages.error(request, "reply is already deleted.")
        return redirect("forum_detail", discussion_id=reply.discussion.id)

    messages.success(request, "Reply deleted successfully.")
    return redirect("forum_detail", discussion_id=reply.discussion.id)

@login_required
@require_POST
def toggle_reply_vote(request, reply_id):
    reply = get_object_or_404(Reply, id=reply_id)

    vote_type = request.POST.get("vote")

    if reply.user_id == request.user.id:
        return JsonResponse(
            {
                "success": False,
                "error": "You cannot vote on your own reply.",
            },
            status=400,
        )

    if reply.is_deleted:
        return JsonResponse(
            {"success": False, "error": "Cannot vote on deleted replies."},
            status=400
        )

    if vote_type == "up":
        vote_value = ReplyVote.UPVOTE
    elif vote_type == "down":
        vote_value = ReplyVote.DOWNVOTE
    else:
        return JsonResponse(
            {"success": False, "error": "Invalid vote type."},
            status=400
        )

    with transaction.atomic():
        reply = Reply.objects.select_for_update().get(pk=reply.pk)
        vote = (
            ReplyVote.objects
            .select_for_update()
            .filter(reply=reply, user=request.user)
            .first()
        )

        if vote is None:
            ReplyVote.objects.create(
                reply=reply,
                user=request.user,
                value=vote_value,
            )
            user_vote = vote_value
        elif vote.value == vote_value:
            vote.delete()
            user_vote = 0
        else:
            vote.value = vote_value
            vote.save(update_fields=["value", "updated_at"])
            user_vote = vote_value

        counts = ReplyVote.objects.filter(reply=reply).aggregate(
            upvotes=Count("id", filter=models.Q(value=ReplyVote.UPVOTE)),
            downvotes=Count("id", filter=models.Q(value=ReplyVote.DOWNVOTE)),
        )

    return JsonResponse(
        {
            "success": True,
            "upvotes": counts["upvotes"],
            "downvotes": counts["downvotes"],
            "user_vote": user_vote,
        }
    )
