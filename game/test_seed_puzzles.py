"""The puzzles shipped with Checkora must be playable: every stored answer is
a legal move that gives mate, and no other move in the position mates too,
since the server accepts the stored answer only."""

from django.test import TestCase
from django.urls import reverse

from game.engine import ChessGame
from game.models import ChessPuzzle


def _squares(uci):
    """'e1e8' -> (fr, fc, tr, tc) in the engine's row/column numbering."""
    files = 'abcdefgh'
    return (
        8 - int(uci[1]), files.index(uci[0]),
        8 - int(uci[3]), files.index(uci[2]),
    )


def _mates(fen, uci):
    game = ChessGame.from_fen(fen)
    try:
        ok, *_ = game.make_move(*_squares(uci))
        return ok and game.check_game_status() == 'checkmate'
    finally:
        game.cleanup_engine()


def _all_mating_moves(fen):
    game = ChessGame.from_fen(fen)
    mating = []
    try:
        for row in range(8):
            for col in range(8):
                for target in game.get_valid_moves(row, col) or []:
                    tr, tc = target['row'], target['col']
                    uci = f"{'abcdefgh'[col]}{8 - row}{'abcdefgh'[tc]}{8 - tr}"
                    if _mates(fen, uci):
                        mating.append(uci)
    finally:
        game.cleanup_engine()
    return mating


class SeedPuzzleTests(TestCase):
    def test_seed_puzzles_are_unique_mates_in_one(self):
        puzzles = ChessPuzzle.objects.filter(title__startswith='Daily Puzzle #')
        self.assertEqual(puzzles.count(), 7)
        for puzzle in puzzles:
            with self.subTest(puzzle=puzzle.title):
                self.assertEqual(len(puzzle.solution), 1)
                self.assertIn('Mate in 1', puzzle.tags)
                self.assertEqual(_all_mating_moves(puzzle.fen), puzzle.solution)

    def test_fallback_puzzle_is_a_mate_in_one(self):
        ChessPuzzle.objects.all().delete()
        data = self.client.get(reverse('daily_puzzle')).json()
        self.assertTrue(_mates(data['fen'], data['solution'][0]))
