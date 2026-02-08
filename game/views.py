"""Game views for the Checkora chess platform."""

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .engine import ChessGame


@ensure_csrf_cookie
def index(request):
    """Render the board and initialise a new game in the session."""
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
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse(
            {'valid': False, 'message': 'Invalid request data.'},
            status=400,
        )

    game_data = request.session.get('game')
    game = ChessGame.from_dict(game_data) if game_data else ChessGame()

    success, message, captured = game.make_move(
        from_row, from_col, to_row, to_col,
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
    """Reset the game to the initial position."""
    game = ChessGame()
    request.session['game'] = game.to_dict()
    request.session.modified = True
    return JsonResponse({
        'board': game.board,
        'current_turn': game.current_turn,
        'move_history': [],
        'captured_pieces': {'white': [], 'black': []},
    })