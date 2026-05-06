# Checkora — Problem & Solution Documentation

> This document records two infrastructure defects that existed in the original codebase, explains why each one mattered, and describes the changes made to fix them.

---

## Table of Contents

1. [Problem 1 — `GameResult` Had No User Association](#problem-1--gameresult-had-no-user-association)
2. [Problem 2 — Game State Stored in Signed Cookies](#problem-2--game-state-stored-in-signed-cookies)
3. [Solution Overview](#solution-overview)
4. [File-by-File Changes](#file-by-file-changes)
5. [Database Migrations](#database-migrations)
6. [How to Apply](#how-to-apply)

---

## *Problem 1* — `GameResult` Had No User Association

### What was wrong

The original `GameResult` model (created in `0001_initial`) stored four fields:

| Field | Type |
|---|---|
| `mode` | `CharField` — `pvp` or `ai` |
| `winner` | `CharField` — `white`, `black`, or `draw` |
| `end_reason` | `CharField` — `checkmate`, `stalemate`, `resign`, `timeout`, or `agreement` |
| `played_at` | `DateTimeField` |

There was **no link to the authenticated user** who played the game. Every game result was effectively anonymous.

### Why it mattered

1. **Per-player statistics were impossible.** The stats page (`/stats/`) could only show aggregate counts across all games. There was no way to display how many games a specific user had won, lost, or drawn.
2. **Win/loss counts were ambiguous.** Even if you knew which user played, `winner = "white"` could mean a win *or* a loss depending on which colour the user was assigned. Without storing the player's colour alongside the result, computing personal W/L was impossible.
3. **Future features were blocked.** Leaderboards, game history pages, replays, and achievement systems all depend on knowing which user played which game.

### Root cause in code

```python
# game/models.py — BEFORE (0001_initial state)
class GameResult(models.Model):
    mode      = models.CharField(...)
    winner    = models.CharField(...)
    end_reason = models.CharField(...)
    played_at  = models.DateTimeField(auto_now_add=True)
    # No player field. No player_color field.
```

```python
# game/views.py — BEFORE
def record_game_result(mode, winner, reason):
    GameResult.objects.create(mode=mode, winner=winner, end_reason=reason)
    # request.user never passed in — anonymous by design.
```

---

## *Problem 2* — Game State Stored in Signed Cookies

### What was wrong

`core/settings.py` originally contained:

```python
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
```

Django's signed-cookie session backend serialises the **entire session dictionary into the browser cookie** and signs it with `SECRET_KEY`. The HTTP specification (RFC 6265) limits a single cookie to **4 096 bytes**.

### Why it mattered

A `ChessGame` session dictionary contains:

- An 8 × 8 board array (64 squares, each a piece string or `null`)
- Move history (algebraic notation strings, one per half-move)
- Captured pieces list
- Clock values, en-passant square, castling rights, turn indicator, FEN history for threefold-repetition detection

For an average game of 40 moves, the serialised payload is already close to the limit. For longer games (correspondence-style, or high-move-count AI games), it **exceeds 4 KB**. When that happens, Django silently drops the session — the user's game state is gone on the next request, with no error message shown.

### Secondary security concern

The signed-cookie backend means every piece of session data travels over the network on every request and response. Although it is signed (not encrypted), large payloads also increase the attack surface for timing-based side-channels against the HMAC verification.

### Root cause in settings

```python
# core/settings.py — BEFORE
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
```

---

## Solution Overview

| # | Problem | Fix |
|---|---|---|
| 1a | No user link on `GameResult` | Added nullable `ForeignKey(User)` field `player` |
| 1b | No colour recorded on `GameResult` | Added nullable `CharField` field `player_color` |
| 1c | `record_game_result()` didn't accept a user | Added `user` and `player_color` parameters; all call sites updated |
| 1d | Stats page showed no personal data | `stats_view` now queries `player=request.user` for authenticated users and passes `user_stats` to the template |
| 1e | Template had no personal stats section | `stats.html` now shows a "Your Stats" card row (hidden for guests) and a **Player** column in the recent games table |
| 2 | Signed-cookie sessions overflow silently | Switched to `django.contrib.sessions.backends.db` (server-side, no size limit) |

---

## File-by-File Changes

### `game/models.py`

Two new fields were added to `GameResult`:

```python
player = models.ForeignKey(
    User, null=True, blank=True, on_delete=models.SET_NULL,
    related_name='game_results',
)
player_color = models.CharField(max_length=5, null=True, blank=True)
```

**Design choices:**

- Both fields are **nullable** so that all existing rows and all guest (unauthenticated) games continue to work without any code path change.
- `on_delete=models.SET_NULL` means deleting a user account does not cascade-delete their game history — the rows remain with `player=NULL`.
- `player_color` stores `"white"` or `"black"` — the colour the user actually played, not the colour that won. This is the only correct way to derive a personal win/draw/loss breakdown when `winner` can be `"white"`, `"black"`, or `"draw"`.

---

### `game/views.py`

#### `record_game_result()`

```python
# BEFORE
def record_game_result(mode, winner, reason):
    GameResult.objects.create(mode=mode, winner=winner, end_reason=reason)

# AFTER
def record_game_result(mode, winner, reason, user=None, player_color=None):
    GameResult.objects.create(
        mode=mode, winner=winner, end_reason=reason,
        player=user if (user and user.is_authenticated) else None,
        player_color=player_color or None,
    )
```

The guard `user.is_authenticated` ensures anonymous/guest requests (`AnonymousUser`) are stored as `NULL` rather than raising an integrity error.

#### Call sites updated

Every place that called `record_game_result()` was updated to pass `request.user` and `game.player_color`:

| View | Trigger |
|---|---|
| `make_move` | Checkmate detected |
| `make_move` | Stalemate / automatic draw detected |
| `offer_draw` | Draw accepted by both players |
| `resign_game` | Player resigns |

Example (checkmate path):

```python
# BEFORE
record_game_result(game.mode, winner, 'checkmate')

# AFTER
record_game_result(game.mode, winner, 'checkmate', request.user, game.player_color)
```

#### `stats_view()`

```python
user_stats = None
if request.user.is_authenticated:
    user_results = GameResult.objects.filter(player=request.user)
    total = user_results.count()
    draws = user_results.filter(winner='draw').count()
    wins  = user_results.filter(winner=db_models.F('player_color')).count()
    user_stats = {
        'total':  total,
        'wins':   wins,
        'draws':  draws,
        'losses': total - wins - draws,
    }
```

`F('player_color')` compares the `winner` column to the `player_color` column **at the database level** — this is the correct way to count wins regardless of which colour the user was assigned. If `player_color` is `NULL` (legacy row), the `F()` comparison evaluates to `NULL` (unknown), which does not count as a win, so legacy rows are handled cleanly.

---

### `game/templates/game/stats.html`

Two additions:

1. **Personal stats card row** — shown only when `user_stats` is truthy (i.e., the user is logged in):

   ```html
   {% if user_stats %}
   <h2>Your Stats ({{ user.username }})</h2>
   <div class="summary">
       <div class="card"><div class="num">{{ user_stats.total }}</div><div class="label">Games Played</div></div>
       <div class="card"><div class="num">{{ user_stats.wins  }}</div><div class="label">Wins</div></div>
       <div class="card"><div class="num">{{ user_stats.draws }}</div><div class="label">Draws</div></div>
       <div class="card"><div class="num">{{ user_stats.losses }}</div><div class="label">Losses</div></div>
   </div>
   {% endif %}
   ```

2. **Player column** in the recent games table:

   ```html
   <th>Player</th>
   ...
   <td>{{ result.player.username|default:"—" }}</td>
   ```

   The `|default:"—"` filter renders a dash for guest games or legacy rows where `player` is `NULL`.

---

### `core/settings.py`

```python
# BEFORE
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# AFTER
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
```

With the database backend:

- Session data is stored in the `django_session` table (already created by `django.contrib.sessions`' own migration `0001_initial`).
- There is no cookie size limit for session payloads — the cookie only contains a short session key.
- Long games with large move histories will never lose state silently again.

---

## Database Migrations

Three migrations exist in `game/migrations/`:

| Migration | What it does |
|---|---|
| `0001_initial.py` | Creates the original `GameResult` table (no user link) |
| `0002_add_player_to_gameresult.py` | Adds nullable `player` `ForeignKey(User)` to `GameResult` |
| `0003_add_player_color_to_gameresult.py` | Adds nullable `player_color` `CharField(5)` to `GameResult` |

The `django_session` table is created by `django.contrib.sessions`' built-in migration and requires no extra work.

---

## How to Apply

```bash
# 1. Pull the latest changes
git pull

# 2. Apply all pending migrations (runs 0002 and 0003 automatically)
python manage.py migrate

# 3. Start the development server
python manage.py runserver
```

No data loss occurs. Existing `GameResult` rows will have `player=NULL` and `player_color=NULL`, which both the model and the template handle gracefully.

---

*Document maintained by the Checkora core team. Last updated 2026-05-06.*
