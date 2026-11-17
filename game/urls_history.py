"""URL patterns for the match history pages, included from game/urls.py."""

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