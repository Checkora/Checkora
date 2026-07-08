"""
game/views_history.py  ← NEW FILE
-----------------------------------
Paste this content into your existing game/views.py, OR keep it as a separate
file and import it in game/urls.py alongside the existing views.

These additions provide:
  • save_game_record()  — internal helper called when a game ends
  • match_history()     — renders the history list page
  • api_history()       — JSON list of recent games (for AJAX)
  • api_replay_pgn()    — JSON with a single game's PGN (for the viewer)
  • api_download_pgn()  — streams the PGN file for download

Integration point
-----------------
In the existing view that handles game-over (wherever you currently build/return
the "game over" response), call:

    from game.views_history import save_game_record
    save_game_record(request, pgn_string, result, termination,
                     white_label="You", black_label="AI")

That's the only change needed in views.py.
"""

import json
from datetime import timedelta

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from game.models import GameRecord


def _normalize_pgn(pgn: str) -> str:
    return pgn.replace('++', '+').replace('##', '#').replace('+#', '#').replace('#+', '#')


# ---------------------------------------------------------------------------
# Internal helper — call this when a game ends
# ---------------------------------------------------------------------------

def save_game_record(request, pgn: str, result: str, termination: str,
                     white_label: str = "White", black_label: str = "Black"):
    """
    Persist a completed game so the user can replay or download it later.

    Parameters
    ----------
    request      : The Django HttpRequest (used to read the session key).
    pgn          : Full PGN string, ideally with [%clk …] clock annotations.
    result       : "1-0", "0-1", or "1/2-1/2".
    termination  : Human-readable reason: "checkmate", "resignation",
                   "timeout", "stalemate", "draw", etc.
    white_label  : Display name for White (e.g. "You", "AI", or a username).
    black_label  : Display name for Black.

    Returns
    -------
    GameRecord instance (already saved).
    """
    # Make sure the session exists so we have a key.
    if not request.session.session_key:
        request.session.create()

    record_data = {
        'session_key': request.session.session_key,
        'white_label': white_label,
        'black_label': black_label,
        'result': result,
        'termination': termination,
        'pgn': pgn,
    }

    # If the user is logged in, attach their account to the record!
    if request.user.is_authenticated:
        record_data['user'] = request.user

    record = GameRecord.objects.create(**record_data)
    return record


# ---------------------------------------------------------------------------
# match_history page view
# ---------------------------------------------------------------------------

def match_history(request):
    """
    Render the Match History page (game/match_history.html).
    The page JS calls /api/history/ to fetch the game list dynamically.
    """
    return render(request, "game/match_history.html")


# ---------------------------------------------------------------------------
# JSON API — list recent games
# ---------------------------------------------------------------------------

@require_GET
def api_history(request):
    """
    GET /api/history/

    Returns up to 20 of the session's non-expired games as JSON.

    Response shape
    --------------
    {
        "games": [
            {
                "id": 42,
                "white": "You",
                "black": "AI",
                "result": "1-0",
                "termination": "checkmate",
                "played_at": "2026-06-10T14:32:00Z",
                "hours_remaining": 161
            },
            ...
        ]
    }
    """
    if request.user.is_authenticated:
        query = Q(user=request.user) | Q(session_key=request.session.session_key)
    else:
        query = Q(session_key=request.session.session_key)

    now = timezone.now()
    records = GameRecord.objects.filter(
        query,
        expires_at__gt=now,
    )[:20]

    games = [
        {
            "id": r.pk,
            "white": r.white_label,
            "black": r.black_label,
            "result": r.result,
            "termination": r.termination,
            "played_at": r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hours_remaining": r.hours_remaining,
        }
        for r in records
    ]
    return JsonResponse({"games": games})


# ---------------------------------------------------------------------------
# JSON API — load a single game's PGN for the in-page viewer
# ---------------------------------------------------------------------------

@require_GET
def api_replay_pgn(request, game_id: int):
    """
    GET /api/history/<game_id>/pgn/

    Returns the PGN of a specific game owned by the current session.

    Response shape (success)
    ------------------------
    { "pgn": "[Event ...] 1. e4 e5 ..." }

    Response shape (error / expired)
    ---------------------------------
    { "error": "Game not found or has expired." }
    """
    if request.user.is_authenticated:
        query = Q(user=request.user) | Q(session_key=request.session.session_key)
    else:
        if not request.session.session_key:
            return JsonResponse({"error": "Game not found or has expired."}, status=404)
        query = Q(session_key=request.session.session_key)

    now = timezone.now()
    try:
        record = GameRecord.objects.get(
            query,
            pk=game_id,
            expires_at__gt=now,
        )
    except GameRecord.DoesNotExist:
        return JsonResponse({"error": "Game not found or has expired."}, status=404)

    pgn = _normalize_pgn(record.pgn)
    return JsonResponse({"pgn": pgn})


# ---------------------------------------------------------------------------
# File download — streams the PGN as an attachment
# ---------------------------------------------------------------------------

@require_GET
def api_download_pgn(request, game_id: int):
    """
    GET /api/history/<game_id>/download/

    Streams the game's PGN as a downloadable .pgn file.
    Returns 404 if the game doesn't belong to this session or has expired.
    """
    if request.user.is_authenticated:
        query = Q(user=request.user) | Q(session_key=request.session.session_key)
    else:
        if not request.session.session_key:
            return HttpResponse("Game not found or has expired.", status=404)
        query = Q(session_key=request.session.session_key)

    now = timezone.now()
    try:
        record = GameRecord.objects.get(
            query,
            pk=game_id,
            expires_at__gt=now,
        )
    except GameRecord.DoesNotExist:
        return HttpResponse("Game not found or has expired.", status=404)

    filename = (
        f"checkora_{record.created_at.strftime('%Y%m%d_%H%M%S')}"
        f"_{record.result.replace('/', '-')}.pgn"
    )
    pgn = _normalize_pgn(record.pgn)
    response = HttpResponse(pgn, content_type="application/x-chess-pgn")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response