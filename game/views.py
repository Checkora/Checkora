"""Game views for the Checkora chess platform."""
import logging
import json
import time
import hashlib
import secrets
import secrets as secrets_module
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.http import (
    urlsafe_base64_encode,
    urlsafe_base64_decode
)

from django.utils.encoding import (
    force_bytes,
    force_str
)
from django.utils.text import slugify

from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.views import PasswordResetView
from smtplib import SMTPException
from django.core.mail import (
    BadHeaderError,
    send_mail,
    EmailMultiAlternatives
)
from django.template.loader import render_to_string
from django.contrib import messages
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from .forms import CustomUserCreationForm
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required

from .engine import ChessGame
from .models import (
    GameResult,
    PuzzleStats,
    LessonProgress,
    Achievement,
    UserAchievement,
)
logger = logging.getLogger(__name__)
from game.services import (
    cleanup_stale_games,
    check_game_achievements,
    check_puzzle_achievements,
)

from .analysis import build_summary

def landing(request):
    """Render the landing page introduction to Checkora."""
    return render(request, 'game/landing.html')

def preloader(request):
    return render(request, 'game/preloading.html')

@ensure_csrf_cookie
def index(request):
    """Render the board and initialise a new game in the session."""
    if 'game' in request.session:
        game_data = request.session['game']
        status = game_data.get('game_status', 'active')
        if status in ['checkmate', 'draw', 'resign', 'stalemate', 'timeout']:
            del request.session['game']
    if 'game' not in request.session:
        game = ChessGame()
        request.session['game'] = game.to_dict()
    return render(request, 'game/board.html')


def record_game_result(request, mode, winner, reason, player_color='white', moves=None):
    """Save a completed game result to the database."""
    user = request.user if request.user.is_authenticated else None
    if moves is None:
        game_data = request.session.get('game')
        if game_data and isinstance(game_data, dict):
            moves = game_data.get('move_history', [])
        else:
            moves = []
    result = GameResult.objects.create(
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
        check_game_achievements(user)


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
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse(
            {"error": "Invalid board coordinates"},
            status=400,
        )

    game_data = request.session.get('game')
    game = ChessGame.from_dict(game_data) if game_data else ChessGame()

    success, message, captured, game_status = game.make_move(
        from_row, from_col, to_row, to_col, promotion_piece,
    )

    if success:
        request.session['game'] = game.to_dict()
        request.session.modified = True
        if game_status == 'checkmate':
            winner = 'black' if game.current_turn == 'white' else 'white'
            record_game_result(request, game.mode, winner, 'checkmate', game.player_color, moves=game.move_history)
        elif game_status in ('stalemate', 'draw'):
            record_game_result(request, game.mode, 'draw', game.draw_reason or 'stalemate', game.player_color, moves=game.move_history)

    return JsonResponse({
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
        'captured_pieces': game.captured,
        'game_status': game_status,
        'draw_reason': game.draw_reason,
        'threefold_warning': game.threefold_warning,
        'fen': game.generate_fen_key(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'white_name': request.session.get('white_name', 'White'),
        'black_name': request.session.get('black_name', 'Black'),
    })


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

    game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'valid_moves': []})

    game = ChessGame.from_dict(game_data)
    moves = game.get_valid_moves(row, col)
    return JsonResponse({'valid_moves': moves})


@require_POST
def new_game(request):
    """Reset the game to the initial position with selected mode."""
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'valid': False, 'message': 'Invalid request data.'}, status=400)

    mode = data.get('mode', 'pvp')
    difficulty = data.get('difficulty', 'medium')
    fen = data.get('fen')
    time_limit_raw = data.get('time_limit', 600)
    increment_raw = data.get('increment', 0)

    if isinstance(time_limit_raw, str) and '|' in time_limit_raw:
        try:
            parts = time_limit_raw.split('|')
            time_limit = int(parts[0]) * 60
            increment = int(parts[1])
        except (ValueError, IndexError, TypeError):
            time_limit = 600
            increment = 0
    else:
        try:
            time_limit = int(time_limit_raw)
            time_limit = max(60, min(18000, time_limit))
        except (ValueError, TypeError):
            time_limit = 600

        try:
            increment = int(increment_raw)
            increment = max(0, min(180, increment))
        except (ValueError, TypeError):
            increment = 0

    if mode not in ('pvp', 'ai'):
        mode = 'pvp'
    player_color = data.get('player_color', 'white')
    if player_color == 'random':
        player_color = secrets.choice(['white', 'black'])
    elif player_color not in ('white', 'black'):
        player_color = 'white'

    def _clean_name(raw, fallback):
        name = (raw or '').strip()
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

    fen = fen.strip() if isinstance(fen, str) else None
    if fen:
        try:
            game = ChessGame.from_fen(fen, time_limit=time_limit, increment=increment)
        except ValueError as exc:
            return JsonResponse(
                {'valid': False, 'message': f'Invalid FEN: {exc}'},
                status=400,
            )
    else:
        game = ChessGame(time_limit=time_limit, increment=increment)
    game.mode = mode
    game.player_color = player_color
    game.paused = False

    request.session['game'] = game.to_dict()
    request.session.modified = True
    request.session.save()

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
        'fen': game.generate_fen_key(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'game_status': game.game_status,
        'draw_reason': game.draw_reason,
    })


@require_POST
def resume_game(request):
    """Resume the existing session game without resetting it."""
    game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'valid': False, 'message': 'No saved game found.'}, status=404)

    game = ChessGame.from_dict(game_data)

    if game.game_status != 'active':
        return JsonResponse({'valid': False, 'message': 'No active game to resume.'}, status=404)

    game.paused = False
    game.last_ts = time.time()
    request.session['game'] = game.to_dict()
    request.session.modified = True

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
        'draw_reason': game.draw_reason,
        'threefold_warning': game.threefold_warning,
        'fen': game.generate_fen_key(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'difficulty': request.session.get('difficulty', 'medium'),
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

    game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'is_promotion': False})

    is_promo = ChessGame.is_promotion_move(
        game_data['board'], from_row, from_col, to_row,
    )
    return JsonResponse({'is_promotion': is_promo})


@require_GET
def get_state(request):
    """Return the full current game state without mutating pause state."""
    game_data = request.session.get('game')
    if not game_data:
        game = ChessGame()
    else:
        game = ChessGame.from_dict(game_data)

        # Skip clock deduction if tab was closed for too long
        elapsed = time.time() - game.last_ts
        if elapsed > 10 and not game.paused:
            game.paused = True  # pause without deducting lost time
        else:
            game.update_clock()

    request.session['game'] = game.to_dict()
    request.session.modified = True

    return JsonResponse({
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
        'fen': game.generate_fen_key(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'game_status': game.game_status,
        'draw_reason': game.draw_reason,
        'threefold_warning': game.threefold_warning,
    })


@require_POST
def set_pause(request):
    """Toggle the game clock between paused and running."""
    game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'paused': False})

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'valid': False, 'message': 'Invalid request data.'}, status=400)

    pause = data.get('pause', True)

    game = ChessGame.from_dict(game_data)

    # Only deduct elapsed time when transitioning from running to paused.
    if pause and not game.paused:
        game.update_clock()
    game.paused = pause
    game.last_ts = time.time()

    request.session['game'] = game.to_dict()
    request.session.modified = True

    return JsonResponse({
        'paused': game.paused,
        'white_time': game.white_time,
        'black_time': game.black_time,
    })


@require_POST
def ai_move(request):
    """Let the engine compute and play the best move for the current side."""
    game_data = request.session.get('game')
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

    # Depth Mapping — lower depth = faster response
    difficulty = request.session.get('difficulty', 'medium')
    depth_map = {'easy': 1, 'medium': 2, 'hard': 3}
    depth = depth_map.get(difficulty, 2)

    best = game.get_ai_move(depth=depth)

    if not best:
        if game.game_status == 'checkmate':
            winner = 'black' if game.current_turn == 'white' else 'white'
            record_game_result(request, game.mode, winner, 'checkmate', game.player_color, moves=game.move_history)
            game_status = 'checkmate'
        else:
            record_game_result(request, game.mode, 'draw', 'stalemate', game.player_color, moves=game.move_history)
            game_status = 'stalemate'

        game.game_status = game_status
        request.session['game'] = game.to_dict()
        request.session.modified = True

        return JsonResponse({
            'valid': True,
            'game_status': game_status,
            'board': game.board,
            'current_turn': game.current_turn,
            'white_time': game.white_time,
            'black_time': game.black_time,
            'move_history': game.move_history,
            'captured_pieces': game.captured,
            'message': '',
        })

    success, message, captured, game_status = game.make_move(
        best['from_row'], best['from_col'],
        best['to_row'],   best['to_col'],
    )

    if success:
        request.session['game'] = game.to_dict()
        request.session.modified = True

        if game_status == 'checkmate':
            winner = 'black' if game.current_turn == 'white' else 'white'
            record_game_result(request, game.mode, winner, 'checkmate', game.player_color, moves=game.move_history)
        elif game_status in ('stalemate', 'draw'):
            record_game_result(request, game.mode, 'draw', game.draw_reason or 'stalemate', game.player_color, moves=game.move_history)

    return JsonResponse({
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
        'captured_pieces': game.captured,
        'ai_move': best,
        'game_status': game_status,
        'draw_reason': game.draw_reason,
        'threefold_warning': game.threefold_warning,
        'fen': game.generate_fen_key(),
        'pgn': game.generate_pgn(request.session.get('white_name', 'White'), request.session.get('black_name', 'Black')),
        'white_name': request.session.get('white_name', 'White'),
        'black_name': request.session.get('black_name', 'Black'),
    })

@require_POST
def offer_draw(request):
    """Handle draw offers and agreements."""
    game_data = request.session.get('game')
    if not game_data:
        return JsonResponse(
            {'success': False, 'message': 'No active game.'}, status=400
        )

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
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
        game.game_status = 'draw'
        game.draw_reason = 'agreement'
        request.session['game'] = game.to_dict()
        request.session.modified = True
        record_game_result(request, game.mode, 'draw', 'agreement', game.player_color, moves=game.move_history)
        return JsonResponse({
            'success': True,
            'game_status': game.game_status,
            'draw_reason': game.draw_reason,
        })

    return JsonResponse({'success': True})

@require_POST
def resign_game(request):
    """Handle a player resigning the game."""
    game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'valid': False, 'message': 'No active game.'}, status=400)

    game = ChessGame.from_dict(game_data)

    resigning_player = game.player_color if game.mode == 'ai' else game.current_turn
    winner = 'black' if resigning_player == 'white' else 'white'
    game_status = 'resignation'

    game.game_status = game_status
    request.session['game'] = game.to_dict()
    request.session.modified = True

    try:
        record_game_result(request, game.mode, winner, 'resign', game.player_color, moves=game.move_history)
    except Exception as e:
        logger.error('Failed to record resign result: %s', e)

    return JsonResponse({
        'valid': True,
        'message': f'{resigning_player.capitalize()} resigned.',
        'winner': winner,
        'game_status': game_status
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
                request.session['registration_user_id'] = -1
                request.session['registration_email'] = email
                dummy_otp = str(secrets.randbelow(900000) + 100000)
                dummy_otp_hash = hashlib.sha256(
                    f"{dummy_otp}:{settings.SECRET_KEY}".encode()
                ).hexdigest()
                request.session['registration_otp_hash'] = dummy_otp_hash
                request.session['otp_created_at'] = time.time()
                messages.success(
                    request,
                    'If your details are valid, a verification '
                    'code has been sent to your email.',
                )
                return redirect('verify_otp')

            is_new_user = False
            try:
                # Security: detect conflicts with existing accounts inside
                # an atomic block to eliminate race conditions between the
                # check and the subsequent insert.
                with transaction.atomic():
                    active_conflict = User.objects.filter(
                        Q(username__iexact=username) | Q(email__iexact=email),
                        is_active=True,
                    ).select_for_update().exists()

                    if active_conflict:
                        # Return the same generic response as a successful
                        # registration so attackers cannot distinguish
                        # between "email/username exists" and "new account".
                        request.session['registration_user_id'] = -1
                        request.session['registration_email'] = email
                        dummy_otp = str(secrets.randbelow(900000) + 100000)
                        dummy_otp_hash = hashlib.sha256(
                            f"{dummy_otp}:{settings.SECRET_KEY}".encode()
                        ).hexdigest()
                        request.session['registration_otp_hash'] = dummy_otp_hash
                        request.session['otp_created_at'] = time.time()
                        messages.success(
                            request,
                            'If your details are valid, a verification '
                            'code has been sent to your email.',
                        )
                        return redirect('verify_otp')

                    inactive_candidates = list(
                        User.objects.select_for_update().filter(
                            Q(username__iexact=username) | Q(email__iexact=email),
                            is_active=False,
                        )
                    )
                    exact_inactive_matches = [
                        u for u in inactive_candidates
                        if u.username.lower() == username.lower()
                        and u.email.lower() == email.lower()
                    ]

                    # If there are matching inactive accounts but none is a full identity match,
                    # trigger the generic dummy flow to prevent hijacking/enumeration.
                    if inactive_candidates and len(exact_inactive_matches) != 1:
                        request.session['registration_user_id'] = -1
                        request.session['registration_email'] = email
                        dummy_otp = str(secrets.randbelow(900000) + 100000)
                        request.session['registration_otp_hash'] = hashlib.sha256(
                            f"{dummy_otp}:{settings.SECRET_KEY}".encode()
                        ).hexdigest()
                        request.session['otp_created_at'] = time.time()
                        # Return the same generic response to prevent username/email enumeration.
                        messages.success(
                            request,
                            'If your details are valid, a verification '
                            'code has been sent to your email.',
                        )
                        return redirect('verify_otp')

                    inactive_user = exact_inactive_matches[0] if exact_inactive_matches else None

                    if inactive_user:
                        user = inactive_user
                        # Update password to the one the user just supplied
                        user.set_password(form.cleaned_data['password1'])
                        user.username = username
                        user.email = email
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
                            request.session['registration_user_id'] = -1
                            request.session['registration_email'] = email
                            dummy_otp = str(secrets.randbelow(900000) + 100000)
                            dummy_otp_hash = hashlib.sha256(
                                f"{dummy_otp}:{settings.SECRET_KEY}".encode()
                            ).hexdigest()
                            request.session['registration_otp_hash'] = dummy_otp_hash
                            request.session['otp_created_at'] = time.time()
                            messages.success(
                                request,
                                'If your details are valid, a verification '
                                'code has been sent to your email.',
                            )
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

                missing_email_credentials = (
                    not settings.EMAIL_HOST_USER or
                    not settings.EMAIL_HOST_PASSWORD
                )

                if settings.DEBUG and missing_email_credentials:
                    print(
                        f"[Checkora] Development registration OTP "
                        f"for {user.email}: {otp}"
                    )
                    messages.success(
                        request,
                        'If your details are valid, a verification '
                        'code has been sent to your email.',
                    )
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
                    messages.success(
                        request,
                        'If your details are valid, a verification '
                        'code has been sent to your email.',
                    )
                    return redirect('verify_otp')
                except (SMTPException, BadHeaderError, OSError):
                    # If email fails, delete the user only if it was newly created.
                    # This preserves existing inactive accounts for re-verification.
                    if is_new_user:
                        user.delete()
                    request.session.pop('registration_user_id', None)
                    request.session.pop('registration_otp_hash', None)
                    request.session.pop('registration_email', None)
                    request.session.pop('otp_created_at', None)
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


def verify_otp(request):
    if request.user.is_authenticated:
        return redirect('index')

    user_id = request.session.get('registration_user_id')
    stored_otp_hash = request.session.get('registration_otp_hash')

    if not user_id or not stored_otp_hash:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('register')

    if request.method == 'POST':
        otp_created_at = request.session.get('otp_created_at')

        if otp_created_at:
            if time.time() - otp_created_at > 300:
                # Security: preserve the inactive account so the
                # user can re-register without losing their username.
                messages.error(
                    request,
                    'OTP has expired. Please register again.',
                )
                request.session.pop('registration_otp_hash', None)
                request.session.pop('otp_created_at', None)
                request.session.pop('registration_user_id', None)
                request.session.pop('registration_email', None)

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
                user = User.objects.get(id=user_id)
                user.is_active = True
                user.full_clean()
                user.save()
                del request.session['registration_user_id']
                del request.session['registration_otp_hash']
                request.session.pop('otp_created_at', None)
                request.session.pop('registration_email', None)

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
                        from_email=settings.EMAIL_HOST_USER,
                        to=[user.email],
                    )
                    email.attach_alternative(html_content, "text/html")
                    email.send(fail_silently=True)

                except (TemplateDoesNotExist, TemplateSyntaxError):
                    logger.exception("Failed to render welcome email template.")
                except Exception as e:
                    logger.warning("Failed to send welcome email: %s", e)

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
                request.session.pop('registration_otp_hash', None)
                request.session.pop('otp_created_at', None)
                request.session.pop('registration_user_id', None)
                request.session.pop('registration_email', None)
                return redirect('register')

        else:
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
        user = User.objects.get(id=user_id, is_active=False)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please register again.')
        return redirect('register')
    last_otp_time = request.session.get('last_otp_time')
    if last_otp_time and time.time() - last_otp_time < 60:
        remaining = int(60 - (time.time() - last_otp_time))
        messages.error(request, f'Please wait {remaining} seconds before requesting a new OTP.')
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
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')

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

    def _single_user_form(self, selected_user):
        base_form = self.get_form_class()

        class SingleUserPasswordResetForm(base_form):
            def get_users(self, email):
                if selected_user and selected_user.has_usable_password():
                    return [selected_user]
                return []

        return SingleUserPasswordResetForm

    def post(self, request, *args, **kwargs):

        email = request.POST.get('email', '').strip().lower()
        if not email:
            messages.error(
                request,
                'Please enter a valid email address.'
            )

            return redirect('password_reset')

        users = User.objects.filter(email__iexact=email)

        if users.count() > 1 and not request.POST.get(
            'selected_username'
        ):

            usernames = users.values_list(
                'username',
                flat=True
            )

            return render(
                request,
                'game/password_reset.html',
                {
                    'form': self.get_form(),
                    'usernames': usernames,
                    'email': email
                }
            )
        selected_username = request.POST.get(
            'selected_username'
        )

        form_class = self.get_form_class()
        if selected_username:

            selected_user = User.objects.filter(
                username=selected_username,
                email__iexact=email
            ).first()

            if not selected_user:
                messages.error(
                    request,
                    'Please select a valid account for this email address.',
                )
                return redirect('password_reset')

            form_class = self._single_user_form(selected_user)

        form = form_class(**self.get_form_kwargs())
        if not form.is_valid():
            return self.form_invalid(form)

        limited_response = self._get_limited_response(request, email)
        if limited_response:
            return limited_response

        response = self.form_valid(form)
        self._record_password_reset_request(request)
        return response


def login_view(request):
    if request.user.is_authenticated:
        return redirect('landing')

    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            request.session.cycle_key()  # Prevent session fixation

            remember_me = request.POST.get('remember_me')

            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)# Browser close

            messages.success(request, f'Welcome back, {user.username}! Login successful.')
            return redirect('landing')

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
    user_results = GameResult.objects.filter(
        user=request.user
    ).exclude(mode__in=['', None])

    recent = user_results.order_by('-played_at')[:20]
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

    return render(request, 'game/stats.html', {
        'recent': recent,
        'ai_total': ai_total,
        'user_ai_wins': user_ai_wins,
        'ai_wins': ai_wins,
        'ai_draws': ai_draws,
        'win_percentage': round(win_percentage, 2),
    })

@login_required
def leaderboard_view(request):
    leaderboard = PuzzleStats.objects.select_related(
        "user"
    ).order_by(
        "-puzzles_solved",
        "-best_streak"
    )

    return render(
        request,
        "game/leaderboard.html",
        {
            "leaderboard": leaderboard
        }
    )

@login_required
@require_POST
def update_puzzle_stats(request):
    data = json.loads(request.body)

    stats, _ = PuzzleStats.objects.get_or_create(
        user=request.user
    )

    stats.puzzles_solved = data.get("puzzles_solved", 0)
    stats.current_streak = data.get("current_streak", 0)
    stats.best_streak = data.get("best_streak", 0)
    stats.daily_completions = data.get("daily_completions", 0)

    stats.save()
    
    check_puzzle_achievements(
        request.user,
        stats
    )

    return JsonResponse({"success": True})

def puzzle_stats_view(request):
    return JsonResponse({
        "streak": 0,
        "longest_streak": 0
    })

@csrf_exempt
@require_POST
def cleanup_cron(request):
    """Secure cron-triggered cleanup endpoint for abandoned games."""
    cron_secret = getattr(settings, 'CRON_SECRET', None)

    # Check authorization header
    auth_header = request.headers.get('Authorization')
    expected = f"Bearer {cron_secret}" if cron_secret else ""
    provided = auth_header or ""

    if not cron_secret or not secrets_module.compare_digest(expected, provided):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        deleted, resigned = cleanup_stale_games()
        return JsonResponse({
            'status': 'success',
            'deleted_games': deleted,
            'resigned_games': resigned
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

def password_reset_account_selection(request):

    email = request.GET.get('email')

    users = User.objects.filter(email=email)

    return render(
        request,
        'game/password_reset_account_selection.html',
        {
            'users': users,
            'email': email
        }
    )


@login_required
def delete_account(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            username=username,
            password=password
        )

        if user and user == request.user:

            uid = urlsafe_base64_encode(
                force_bytes(user.pk)
            )

            token = default_token_generator.make_token(user)
            delete_link = request.build_absolute_uri(
                reverse(
                    'confirm_delete_account',
                    kwargs={
                        'uidb64': uid,
                        'token': token
                    }
                )
            )

            try:

                send_mail(
                    subject='Confirm Account Deletion',
                    message=f"""
Click the link below to permanently delete your account:

{delete_link}

If this wasn't you, ignore this email.
""",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

                messages.success(
                    request,
                    'Confirmation email sent to your registered email.'
                )

            except Exception:
                messages.error(
                    request,
                    'Failed to send confirmation email.'
                )

            return redirect('index')

        messages.error(
            request,
            'Invalid username or password.'
        )

    return render(
        request,
        'game/delete_account.html'
    )


def confirm_delete_account(request, uidb64, token):

    try:

        uid = force_str(
            urlsafe_base64_decode(uidb64)
        )

        user = User.objects.get(pk=uid)

    except Exception:

        user = None

    if user and default_token_generator.check_token(
        user,
        token
    ):

        logout(request)

        user.delete()

        return render(
            request,
            'game/delete_success.html'
        )

    messages.error(
        request,
        'Invalid or expired deletion link.'
    )

    return redirect('landing')
@csrf_exempt
@require_POST
def analyze_game_view(request):
    """
    Analyze a completed game based on its move history and return statistics.
    Expects JSON payload with 'moves' (list of notation strings), 'result', and 'reason'.
    """
    try:
        data = json.loads(request.body)
        moves = data.get('moves', [])
        result = data.get('result', 'Unknown')
        reason = data.get('reason', 'Unknown')

        # Ensure moves is a list of strings
        if not isinstance(moves, list):
            moves = []
        moves = [str(m) for m in moves]

        summary = build_summary(moves, result, reason)
        return JsonResponse(summary)
    except Exception as e:
        logger.error('Failed to analyze game: %s', e)
        return JsonResponse({'error': 'Failed to analyze game'}, status=400)


_LESSON_NAMES = (
    "How Pieces Move",
    "Check and Checkmate",
    "Castling",
    "Opening Principles",
    "Forks",
    "Pins",
    "Skewers",
    "Discovered Attacks",
    "Pawn Structures",
    "King Safety",
    "Piece Activity",
    "Basic Endgames",
)


def _lesson_name_from_slug(lesson_slug):
    for name in _LESSON_NAMES:
        if slugify(name) == lesson_slug:
            return name
    return None


def _resolve_lesson_name(url_key):
    if url_key in _LESSON_NAMES:
        return url_key
    return _lesson_name_from_slug(url_key)


def lessons_view(request):
    lessons = {
        "Beginner": [
            "How Pieces Move",
            "Check and Checkmate",
            "Castling",
            "Opening Principles",
        ],
        "Intermediate": [
            "Forks",
            "Pins",
            "Skewers",
            "Discovered Attacks",
        ],
        "Advanced": [
            "Pawn Structures",
            "King Safety",
            "Piece Activity",
            "Basic Endgames",
        ],
    }

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
    total_lessons = sum(
        len(lesson_list)
        for lesson_list in lessons.values()
    )

    completed_count = len(completed_lessons)

    return render(
        request,
        "game/lessons.html",
        {
            "lessons": lessons,
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "completed_count": completed_count
        }
    )


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
        "Discovered Attacks"
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

    LessonProgress.objects.update_or_create(
        user=request.user,
        lesson_name=lesson_name,
        defaults={
            "completed": True,
            "completed_at": timezone.now(),
        }
    )

    return redirect(
        "lesson_detail",
        lesson_name=slugify(lesson_name)
    )


@login_required
def achievements_view(request):
    achievements = Achievement.objects.all()
    
    unlocked = set(
        UserAchievement.objects.filter(
            user=request.user
        ).values_list(
            "achievement_id",
            flat=True
        )
    )

    return render(
        request,
        "game/achievements.html",
        {
            "achievements": achievements,
            "unlocked": unlocked,
        }
    )
