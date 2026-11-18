"""Evaluation terms, and how far the two engines agree on them.

The king attack and the passed pawn term are checked on positions built
for them. Agreement between main.cpp and main.py, and between the
colours, is checked on the positions of seeded random games (python-chess
plays them; without it those tests are skipped).
"""
import random
import unittest

from game.test_engine_differential import chess, fields
from game.test_engine_rules import EngineTestCase
from game.test_engine_rules import fields as fen_fields

# Random games for the agreement tests, and how long each may run
GAMES = 12
MAX_PLIES = 160


def random_positions(games, max_plies):
    """The positions of seeded random games, as python-chess boards."""
    positions = []
    for game in range(games):
        rng = random.Random(game)
        board = chess.Board()
        while not board.is_game_over() and len(board.move_stack) < max_plies:
            positions.append(board.copy(stack=False))
            board.push(rng.choice(list(board.legal_moves)))
    return positions


class KingAttackTest(EngineTestCase):
    """White's pieces bear on the squares around g8. The black king stands
    as well on b8 (same table value, same pawn cover), where none of them
    reaches it, so the difference between the two scores is the attack."""

    PIECES = 'pppr1ppp/8/{rank5}/{rank4}/{rank3}/PPP2PPP/3R2K1 w - - 0 1'

    def attack(self, engine, rank5, rank4='8', rank3='8'):
        rest = self.PIECES.format(rank5=rank5, rank4=rank4, rank3=rank3)
        scores = [int(engine.ask(f'EVAL {fen_fields(f"{king}/{rest}")}').split()[1]) for king in ('6k1', '1k6')]
        return scores[0] - scores[1]

    def test_attack_grows_with_the_attackers(self):
        for name, engine in self.each_engine():
            alone = self.attack(engine, '7Q', rank3='4N3')     # the knight looks elsewhere
            two = self.attack(engine, '6NQ')                    # queen and knight
            three = self.attack(engine, '6NQ', rank4='2B5')     # and the bishop on f7
            self.assertEqual(alone, 0)
            self.assertGreater(two, 0)
            self.assertGreater(three, two)

    def test_attack_counts_for_black_too(self):
        """The same attack with the colours swapped costs White as much."""
        for name, engine in self.each_engine():
            white = int(engine.ask(f'EVAL {fen_fields("6k1/pppr1ppp/8/6NQ/8/8/PPP2PPP/3R2K1 w - - 0 1")}').split()[1])
            black = int(engine.ask(f'EVAL {fen_fields("3r2k1/ppp2ppp/8/8/6nq/8/PPPR1PPP/6K1 b - - 0 1")}').split()[1])
            self.assertEqual(black, -white)


class PassedPawnTest(EngineTestCase):
    """A white pawn on b6 and the two kings. Each pair of positions moves
    one king between squares that its endgame table values alike, so only
    the king's distance to b7, the square in front of the pawn, differs."""

    def evaluate(self, engine, fen):
        return int(engine.ask(f'EVAL {fen_fields(fen)}').split()[1])

    def test_the_kings_distance_to_the_pawns_path_counts(self):
        for name, engine in self.each_engine():
            # The black king one step from b7, or four
            self.assertGreater(self.evaluate(engine, '5k2/8/1P6/8/8/8/8/7K w - - 0 1'),
                               self.evaluate(engine, '2k5/8/1P6/8/8/8/8/7K w - - 0 1'))
            # The white king four steps from b7, or six
            self.assertGreater(self.evaluate(engine, '2k2K2/8/1P6/8/8/8/8/8 w - - 0 1'),
                               self.evaluate(engine, '2k5/8/1P6/8/8/8/8/2K5 w - - 0 1'))


@unittest.skipIf(chess is None, 'python-chess is not installed (pip install -r requirements-dev.txt)')
class EvaluationAgreementTest(EngineTestCase):

    def evaluate(self, engine, board):
        return int(engine.ask(f'EVAL {fields(board)}').split()[1])

    def test_engines_agree_on_random_positions(self):
        if 'cpp' not in self.engines:
            self.skipTest('no compiled engine on this machine')
        for board in random_positions(GAMES, MAX_PLIES):
            self.assertEqual(self.evaluate(self.engines['cpp'], board),
                             self.evaluate(self.engines['python'], board), board.fen())

    def test_colours_are_alike(self):
        """Swapping the colours (and the side to move) negates the score."""
        for name, engine in self.each_engine():
            for board in random_positions(GAMES // 2, MAX_PLIES):
                self.assertEqual(self.evaluate(engine, board.mirror()), -self.evaluate(engine, board), board.fen())
