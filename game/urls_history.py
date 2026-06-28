"""
game/urls_history.py  ← NEW FILE
----------------------------------
Add these URL patterns to your existing game/urls.py (or api/urls.py,
wherever the other /api/ routes live).

In urls.py just do:

    from game.urls_history import history_urlpatterns

    urlpatterns = [
        # … your existing patterns …
    ] + history_urlpatterns

Or copy the individual path() calls directly.
"""

from django.urls import path
from game import views_history

history_urlpatterns = [
    # Renders the Match History page
    path("history/", views_history.match_history, name="match_history"),

    # JSON list of the session's games
    path("api/history/", views_history.api_history, name="api_history"),

    # Fetch a single game's PGN for the in-page viewer
    path(
        "api/history/<int:game_id>/pgn/",
        views_history.api_replay_pgn,
        name="api_replay_pgn",
    ),

    # Download a single game's PGN as a file
    path(
        "api/history/<int:game_id>/download/",
        views_history.api_download_pgn,
        name="api_download_pgn",
    ),
]