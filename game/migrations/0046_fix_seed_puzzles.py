from django.db import migrations

# The seven puzzles added by 0019 were broken: two answers were illegal
# moves (f1h7, h1h7), three were not mate although tagged as mates, and the
# other two had several mating moves while only one was accepted. Each is
# replaced by a position with exactly one mating move.
#
# A row is changed only while it still holds the original seed position, so
# a puzzle an admin has since edited is left alone.

ORIGINAL = {
    "Daily Puzzle #1": ("6k1/5ppp/8/8/8/8/5PPP/6KQ w - - 0 1", ["g2g4"], "easy", 1200, "Mate in 2"),
    "Daily Puzzle #2": ("7k/5K2/6Q1/8/8/8/8/8 w - - 0 1", ["g6g7"], "easy", 1000, "Mate in 1"),
    "Daily Puzzle #3": ("6k1/5ppp/8/8/8/8/5PPP/5RK1 w - - 0 1", ["f1e1"], "easy", 1100, "Endgame"),
    "Daily Puzzle #4": ("6k1/5ppp/8/8/8/8/5PPP/5QK1 w - - 0 1", ["f1h7"], "medium", 1600, "Fork,Tactics"),
    "Daily Puzzle #5": ("7k/6pp/8/8/8/8/5PPP/6KQ w - - 0 1", ["h1h7"], "medium", 1500, "Pin,Tactics"),
    "Daily Puzzle #6": ("7k/5K2/7Q/8/8/8/8/8 w - - 0 1", ["h6g7"], "medium", 1800, "Mate in 2,Tactics"),
    "Daily Puzzle #7": ("6k1/5ppp/8/8/8/8/6PP/5RK1 w - - 0 1", ["f1e1"], "easy", 900, "Mate in 1,Endgame"),
}

# White to move and mate. Every position was checked to have exactly one
# mating move.
FIXED = {
    "Daily Puzzle #1": ("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1", ["e1e8"], "easy", 800, "Mate in 1,Endgame"),
    "Daily Puzzle #2": ("6k1/6p1/6Kp/8/8/8/8/1R6 w - - 0 1", ["b1b8"], "easy", 900, "Mate in 1,Endgame"),
    "Daily Puzzle #3": ("6k1/R7/1R6/8/8/8/8/6K1 w - - 0 1", ["b6b8"], "easy", 1000, "Mate in 1,Endgame"),
    "Daily Puzzle #4": ("6rk/6pp/8/6N1/8/8/5PPP/6K1 w - - 0 1", ["g5f7"], "medium", 1300, "Mate in 1,Tactics"),
    "Daily Puzzle #5": ("7k/R7/5N2/8/8/8/8/6K1 w - - 0 1", ["a7h7"], "medium", 1400, "Mate in 1,Tactics"),
    "Daily Puzzle #6": ("1n2kb1r/p4ppp/4q3/4p1B1/4P3/8/PPP2PPP/2KR4 w k - 0 1", ["d1d8"], "medium", 1500, "Mate in 1,Tactics"),
    "Daily Puzzle #7": ("3rkr2/8/8/8/8/1Q6/8/4K3 w - - 0 1", ["b3e6"], "medium", 1600, "Mate in 1,Tactics"),
}


def _swap(apps, source, target):
    ChessPuzzle = apps.get_model('game', 'ChessPuzzle')
    for title, (old_fen, *_rest) in source.items():
        fen, solution, difficulty, rating, tags = target[title]
        ChessPuzzle.objects.filter(title=title, fen=old_fen).update(
            fen=fen,
            solution=solution,
            difficulty=difficulty,
            rating=rating,
            tags=tags,
        )


def fix_puzzles(apps, schema_editor):
    _swap(apps, ORIGINAL, FIXED)


def restore_puzzles(apps, schema_editor):
    _swap(apps, FIXED, ORIGINAL)


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0045_seed_achievements'),
    ]

    operations = [
        migrations.RunPython(fix_puzzles, restore_puzzles),
    ]
