"""Game views for the Checkora chess platform."""

import json
import time

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .engine import ChessGame


@ensure_csrf_cookie
def index(request):
    """Render the board and initialise a new game in the session."""
    if 'game' not in request.session:
        game = ChessGame()
        request.session['game'] = game.to_dict()
    return render(request, 'game/board.html')


@require_POST
def make_move(request):
    """Validate and execute a chess move via the C++ engine."""
    try:
        data = json.loads(request.body)
        from_row = int(data['from_row'])
        from_col = int(data['from_col'])
        to_row = int(data['to_row'])
        to_col = int(data['to_col'])
        promotion_piece = data.get('promotion_piece', None)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse(
            {'valid': False, 'message': 'Invalid request data.'},
            status=400,
        )

    game_data = request.session.get('game')
    game = ChessGame.from_dict(game_data) if game_data else ChessGame()

    success, message, captured = game.make_move(
        from_row, from_col, to_row, to_col, promotion_piece,
    )

    if success:
        request.session['game'] = game.to_dict()
        request.session.modified = True

    return JsonResponse({
        'valid': success,
        'message': message,
        'captured': captured,
        'board': game.board,
        'current_turn': game.current_turn,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'move_history': game.move_history,
        'captured_pieces': game.captured,
    })


@require_GET
def valid_moves(request):
    """Return every legal destination for a piece."""
    try:
        row = int(request.GET['row'])
        col = int(request.GET['col'])
    except (KeyError, ValueError, TypeError):
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
    data = json.loads(request.body or '{}')
    mode = data.get('mode', 'pvp')  # Frontend se mode aayega
    
    game = ChessGame()
    game.mode = mode
    
    request.session['game'] = game.to_dict()
    request.session.modified = True
    
    return JsonResponse({
        'board': game.board,
        'current_turn': game.current_turn,
        'move_history': [],
        'captured_pieces': {'white': [], 'black': []},
        'mode': game.mode
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

    game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'is_promotion': False})

    is_promo = ChessGame.is_promotion_move(
        game_data['board'], from_row, from_col, to_row,
    )
    return JsonResponse({'is_promotion': is_promo})


@require_GET
def get_state(request):
    game_data = request.session.get('game')
    if not game_data:
        game = ChessGame()
    else:
        game = ChessGame.from_dict(game_data)
        
        # Agar bada gap hai (tab close kiya tha), toh time minus mat karo
        import time
        elapsed = time.time() - game.last_ts
        if elapsed > 10 and not game.paused:
            pass  # Force pause without time penalty
        else:
            game.update_clock() # Sirf chote refresh (few seconds) ka time minus karo
            
    # Jab bhi page load/refresh ho, game hamesha PAUSED state mein rahega
    game.paused = True
    game.last_ts = time.time()

    request.session['game'] = game.to_dict()
    request.session.modified = True

    return JsonResponse({
        'board': game.board,
        'current_turn': game.current_turn,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'paused': game.paused,
        'move_history': game.move_history,
        'captured_pieces': game.captured,
        'mode': game.mode if 'game' in locals() else game_data.get('mode', 'pvp'),
    })

@csrf_exempt
@require_POST
def set_pause(request):
    game_data = request.session.get('game')
    if not game_data:
        return JsonResponse({'paused': False})

    data = json.loads(request.body or '{}')
    pause = data.get('pause', True)

    game = ChessGame.from_dict(game_data)

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
        return JsonResponse({'valid': False, 'message': 'No active game.'}, status=400)

    game = ChessGame.from_dict(game_data)

    if game.mode != 'ai':
        return JsonResponse({'valid': False, 'message': 'Not in AI mode.'}, status=400)

    best = game.get_ai_move()
    if not best:
        return JsonResponse({
            'valid': False,
            'message': 'No legal moves available.',
            'board': game.board,
            'current_turn': game.current_turn,
        })

    success, message, captured = game.make_move(
        best['from_row'], best['from_col'],
        best['to_row'],   best['to_col'],
    )

    if success:
        request.session['game'] = game.to_dict()
        request.session.modified = True

    return JsonResponse({
        'valid': success,
        'message': message,
        'captured': captured,
        'board': game.board,
        'current_turn': game.current_turn,
        'white_time': game.white_time,
        'black_time': game.black_time,
        'move_history': game.move_history,
        'captured_pieces': game.captured,
        'ai_move': best,
    })


