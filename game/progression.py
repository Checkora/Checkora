"""How a player progresses: rating, rank, points (XP), level and streaks.

The rules live here so that every page and every API reports the same
numbers. Views and services call these functions; nothing here touches a
request.
"""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.utils import timezone

from .models import PlayerRating, PuzzleStats, UserAchievement, UserProfile, UserProgress

# ---------------------------------------------------------------------------
# Rating: Elo against the engine level that was played.
# ---------------------------------------------------------------------------

START_RATING = 1200
RATING_FLOOR = 100
# Until a player has this many rated games their rating moves faster and is
# shown with a "?", because it is still finding its level.
PROVISIONAL_GAMES = 20
K_PROVISIONAL = 32
K_ESTABLISHED = 16
# The rating each engine level plays at. Medium sits at the starting
# rating, so a new player is expected to score half against it. The gaps
# come from matches between the levels (scripts/engine_match.py, 200 games
# a pair): hard beat medium by about 650 points and master beat hard by
# about 140, rounded here to 150. Medium won all 200 games against easy,
# which puts easy at least 750 below it.
ENGINE_RATINGS = {'easy': 450, 'medium': 1200, 'hard': 1850, 'master': 2000}

RESULT_SCORES = {'win': 1.0, 'draw': 0.5, 'loss': 0.0}


def engine_rating(difficulty):
    return ENGINE_RATINGS.get(difficulty, ENGINE_RATINGS['medium'])


def expected_score(rating, opponent_rating):
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def rating_change(rating, opponent_rating, result, games_played):
    """Points a game moves the rating by, before the floor is applied."""
    if result not in RESULT_SCORES:
        raise ValueError(f'Invalid result: {result}')
    k = K_PROVISIONAL if games_played < PROVISIONAL_GAMES else K_ESTABLISHED
    return round(k * (RESULT_SCORES[result] - expected_score(rating, opponent_rating)))


def is_provisional(games_played):
    return games_played < PROVISIONAL_GAMES


# ---------------------------------------------------------------------------
# Rank: a title for a band of rating, named after the pieces.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rank:
    name: str
    piece: str            # the piece letter the badge shows: p n b r q k
    floor: int            # lowest rating in this rank
    next_at: int | None   # where the next rank starts, None at the top


RANK_FLOORS = (
    ('Pawn', 'p', 0),
    ('Knight', 'n', 800),
    ('Bishop', 'b', 1100),
    ('Rook', 'r', 1400),
    ('Queen', 'q', 1700),
    ('King', 'k', 2000),
)


def rank_for(rating):
    index = 0
    for position, (_, _, floor) in enumerate(RANK_FLOORS):
        if rating >= floor:
            index = position
    name, piece, floor = RANK_FLOORS[index]
    following = RANK_FLOORS[index + 1][2] if index + 1 < len(RANK_FLOORS) else None
    return Rank(name, piece, floor, following)


# ---------------------------------------------------------------------------
# Points (XP) and levels
# ---------------------------------------------------------------------------

LEVEL_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 250,
    4: 500,
    5: 1000,
    6: 1500,
    7: 2200,
    8: 3000,
}

XP_FOR_RESULT = {'win': 30, 'draw': 15, 'loss': 5}
XP_PUZZLE = 10
XP_DAILY_PUZZLE = 15
XP_LESSON = 25
XP_OPENING = 50
XP_OPENING_PERFECT = 25


def calculate_level(xp: int) -> int:
    if xp < 0:
        raise ValueError(f"xp must be non-negative, got {xp}")
    level = 1
    for lvl, threshold in LEVEL_THRESHOLDS.items():
        if xp >= threshold:
            level = lvl
    return level


def level_progress(xp):
    """(level, xp into this level, xp this level spans or None at the top)."""
    level = calculate_level(xp)
    start = LEVEL_THRESHOLDS[level]
    following = LEVEL_THRESHOLDS.get(level + 1)
    return level, xp - start, (following - start) if following is not None else None


def award_xp(user, amount: int) -> UserProgress:
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    with transaction.atomic():
        progress, _ = UserProgress.objects.select_for_update().get_or_create(user=user)
        progress.xp += amount
        progress.level = calculate_level(progress.xp)
        progress.save()
    return progress


# ---------------------------------------------------------------------------
# Streak days
# ---------------------------------------------------------------------------

# A game counts towards the day streak only once both sides have made this
# many moves between them, so opening a game and resigning does not.
STREAK_MIN_HALF_MOVES = 10


def zone_for(name):
    try:
        return ZoneInfo(name) if name else None
    except (ZoneInfoNotFoundError, ValueError):
        return None


def player_today(user) -> date:
    """Today's date where the player is, from the time zone their browser sent."""
    name = (
        UserProfile.objects.filter(user=user).values_list('timezone', flat=True).first()
        if user else None
    )
    zone = zone_for(name)
    return timezone.localdate(timezone=zone) if zone else timezone.localdate()


# ---------------------------------------------------------------------------
# What the profile shows
# ---------------------------------------------------------------------------

def player_summary(user):
    rating_row = PlayerRating.objects.filter(user=user).first()
    rating = rating_row.rating if rating_row else START_RATING
    games = rating_row.games_played if rating_row else 0

    progress = UserProgress.objects.filter(user=user).first()
    xp = progress.xp if progress else 0
    level, into_level, level_span = level_progress(xp)

    today = player_today(user)
    puzzles = PuzzleStats.objects.filter(user=user).first()
    rank = rank_for(rating)

    return {
        'rating': rating,
        'provisional': is_provisional(games),
        'rank': rank,
        'next_rank': rank_for(rank.next_at) if rank.next_at else None,
        'points_to_next_rank': rank.next_at - rating if rank.next_at else None,
        'wins': rating_row.wins if rating_row else 0,
        'losses': rating_row.losses if rating_row else 0,
        'draws': rating_row.draws if rating_row else 0,
        'games_played': games,
        'xp': xp,
        'level': level,
        'xp_into_level': into_level,
        'xp_level_span': level_span,
        'day_streak': progress.streak_on(today) if progress else 0,
        'best_day_streak': progress.best_day_streak if progress else 0,
        # The daily puzzle is the same for everyone and turns over at midnight UTC.
        'puzzle_streak': puzzles.streak_on(timezone.localdate()) if puzzles else 0,
        'best_puzzle_streak': puzzles.best_streak if puzzles else 0,
        'puzzles_solved': puzzles.puzzles_solved if puzzles else 0,
        'achievements': UserAchievement.objects.filter(user=user).count(),
        # Shown as full moves, which is how players count them.
        'streak_min_moves': STREAK_MIN_HALF_MOVES // 2,
    }
