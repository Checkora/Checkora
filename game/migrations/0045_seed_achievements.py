from django.db import migrations


# One row per code that game/services.py can unlock.
# (code, title, description, icon, category, rarity)
ACHIEVEMENTS = [
    ("FIRST_WIN", "First Win", "Win a game against the computer", "🏆", "gameplay", "common"),
    ("WIN_10", "10 Wins", "Win 10 games against the computer", "🏆", "gameplay", "rare"),
    ("WIN_50", "50 Wins", "Win 50 games against the computer", "🏆", "gameplay", "epic"),
    ("WIN_100", "100 Wins", "Win 100 games against the computer", "🏆", "gameplay", "legendary"),

    ("PLAY_10", "10 Games", "Finish 10 games", "♟️", "gameplay", "common"),
    ("PLAY_20", "20 Games", "Finish 20 games", "♟️", "gameplay", "common"),
    ("PLAY_50", "50 Games", "Finish 50 games", "♟️", "gameplay", "rare"),
    ("PLAY_100", "100 Games", "Finish 100 games", "♟️", "gameplay", "epic"),
    ("PLAY_500", "500 Games", "Finish 500 games", "♟️", "gameplay", "legendary"),

    ("FIRST_CHECKMATE", "First Checkmate", "Checkmate the computer", "👑", "gameplay", "common"),
    ("FIFTH_CHECKMATE", "5 Checkmates", "Checkmate the computer 5 times", "👑", "gameplay", "common"),
    ("CHECKMATE_10", "10 Checkmates", "Checkmate the computer 10 times", "👑", "gameplay", "rare"),
    ("CHECKMATE_20", "20 Checkmates", "Checkmate the computer 20 times", "👑", "gameplay", "rare"),
    ("CHECKMATE_30", "30 Checkmates", "Checkmate the computer 30 times", "👑", "gameplay", "epic"),
    ("CHECKMATE_50", "50 Checkmates", "Checkmate the computer 50 times", "👑", "gameplay", "epic"),
    ("CHECKMATE_100", "100 Checkmates", "Checkmate the computer 100 times", "👑", "gameplay", "legendary"),

    ("STALEMATE_DRAW", "Stalemate", "Draw a game by stalemate", "🤝", "special", "rare"),
    ("FAST_WIN", "Fast Win", "Win in under 20 moves", "⚡", "special", "rare"),

    ("FIRST_PUZZLE", "First Puzzle", "Solve a puzzle", "🧩", "puzzle", "common"),
    ("PUZZLE_10", "10 Puzzles", "Solve 10 puzzles", "🧩", "puzzle", "common"),
    ("PUZZLE_25", "25 Puzzles", "Solve 25 puzzles", "🧩", "puzzle", "rare"),
    ("PUZZLE_50", "50 Puzzles", "Solve 50 puzzles", "🧩", "puzzle", "rare"),
    ("PUZZLE_75", "75 Puzzles", "Solve 75 puzzles", "🧩", "puzzle", "epic"),
    ("PUZZLE_100", "100 Puzzles", "Solve 100 puzzles", "🧩", "puzzle", "epic"),
    ("PUZZLE_200", "200 Puzzles", "Solve 200 puzzles", "🧩", "puzzle", "legendary"),

    ("STREAK_3", "3 Day Streak", "Solve the daily puzzle 3 days in a row", "🔥", "streaks", "common"),
    ("STREAK_7", "7 Day Streak", "Solve the daily puzzle 7 days in a row", "🔥", "streaks", "rare"),
    ("STREAK_10", "10 Day Streak", "Solve the daily puzzle 10 days in a row", "🔥", "streaks", "rare"),
    ("STREAK_30", "30 Day Streak", "Solve the daily puzzle 30 days in a row", "🔥", "streaks", "epic"),
    ("STREAK_50", "50 Day Streak", "Solve the daily puzzle 50 days in a row", "🔥", "streaks", "epic"),
    ("STREAK_100", "100 Day Streak", "Solve the daily puzzle 100 days in a row", "🔥", "streaks", "legendary"),
]


def seed_achievements(apps, schema_editor):
    Achievement = apps.get_model('game', 'Achievement')
    for code, title, description, icon, category, rarity in ACHIEVEMENTS:
        # Rows somebody already created in the admin are left as they are.
        Achievement.objects.get_or_create(
            code=code,
            defaults={
                "title": title,
                "description": description,
                "icon": icon,
                "category": category,
                "rarity": rarity,
            },
        )


def keep_achievements(apps, schema_editor):
    # Users may hold these by now, so going back leaves the rows alone.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0044_rated_games_and_puzzle_solves'),
    ]

    operations = [
        migrations.RunPython(seed_achievements, keep_achievements),
    ]
