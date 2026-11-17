"""Rule, protocol and search tests that talk to the engines themselves.

Every test runs against game/engine/main.py and, when a compiled engine
that runs here is present, against that binary too. Nothing is mocked.
"""
import os
import queue
import subprocess
import sys
import threading

from django.test import SimpleTestCase

from game.engine import ChessGame

MAIN_PY = os.path.join(ChessGame.ENGINE_DIR, 'main.py')


def engine_commands():
    """The engines that can be started on this machine."""
    commands = {'python': [sys.executable, '-u', MAIN_PY]}
    for path in ChessGame.ENGINE_CANDIDATES:
        if not path.endswith('.py') and os.path.isfile(path) and ChessGame._binary_runs(path):
            commands['cpp'] = [path]
            break
    return commands


class EngineProcess:
    """One engine process spoken to over its line protocol."""

    def __init__(self, command):
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self.lines = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.put(line.strip())
        self.lines.put(None)

    def ask(self, line, timeout=120):
        self.proc.stdin.write(line + '\n')
        self.proc.stdin.flush()
        return self.lines.get(timeout=timeout)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()


def fields(fen):
    """The protocol's position fields for a FEN string."""
    placement, turn, rights, ep = fen.split()[:4]
    board = ChessGame._parse_fen_placement(placement)
    board64 = ''.join(piece or '.' for row in board for piece in row)
    ep_fields = '-1 -1'
    if ep != '-':
        ep_fields = f"{8 - int(ep[1])} {'abcdefgh'.index(ep[0])}"
    return f"{board64} {rights} {'white' if turn == 'w' else 'black'} {ep_fields}"


def square(name):
    """'e4' -> 'row col' as the protocol counts them."""
    return f"{8 - int(name[1])} {'abcdefgh'.index(name[0])}"


class EngineTestCase(SimpleTestCase):
    """Starts each available engine once for the whole class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engines = {}
        for name, command in engine_commands().items():
            cls.engines[name] = EngineProcess(command)
            cls.addClassCleanup(cls.engines[name].close)

    def each_engine(self):
        for name, engine in self.engines.items():
            with self.subTest(engine=name):
                yield name, engine


START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
KIWIPETE = 'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1'

# The six standard move-generation test positions with the published
# number of positions reachable in exactly N plies.
PERFT = [
    (START, [20, 400, 8902, 197281]),
    (KIWIPETE, [48, 2039, 97862, 4085603]),
    ('8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1', [14, 191, 2812, 43238, 674624]),
    ('r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1', [6, 264, 9467, 422333]),
    ('rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8', [44, 1486, 62379, 2103487]),
    ('r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10',
     [46, 2079, 89890, 3894594]),
]


class PerftTest(EngineTestCase):
    """Move generation: castling, en passant, promotion, pins and checks."""

    def test_perft_matches_published_counts(self):
        for name, engine in self.each_engine():
            # The compiled engine goes one ply deeper than the Python one
            depth = 4 if name == 'cpp' else 3
            for fen, counts in PERFT:
                plies = min(depth, len(counts))
                if fen.startswith('8/2p5') and name == 'cpp':
                    plies = 5
                reply = engine.ask(f'PERFT {fields(fen)} {plies}')
                self.assertEqual(reply, f'PERFT {counts[plies - 1]}', fen)

    def test_moves_command_agrees_with_perft(self):
        """MOVES is what the web app uses; it must list the same moves."""
        for name, engine in self.each_engine():
            for fen, counts in PERFT:
                board = ChessGame._parse_fen_placement(fen.split()[0])
                white = fen.split()[1] == 'w'
                total = 0
                for row in range(8):
                    for col in range(8):
                        piece = board[row][col]
                        if not piece or piece.isupper() != white:
                            continue
                        tokens = engine.ask(f'MOVES {fields(fen)} {row} {col}').split()[1:]
                        for i in range(0, len(tokens), 4):
                            # one entry per target square stands for four promotions
                            total += 4 if tokens[i + 3] == '1' else 1
                self.assertEqual(total, counts[0], fen)


class RuleEdgeCaseTest(EngineTestCase):

    def moves(self, engine, fen, origin):
        tokens = engine.ask(f'MOVES {fields(fen)} {square(origin)}').split()[1:]
        return {(int(tokens[i]), int(tokens[i + 1])) for i in range(0, len(tokens), 4)}

    def test_no_castling_without_the_rook(self):
        for name, engine in self.each_engine():
            # the right is claimed but h1 holds a queen and a1 is empty
            targets = self.moves(engine, '4k3/8/8/8/8/8/8/4K2Q w KQ - 0 1', 'e1')
            self.assertNotIn((7, 6), targets)
            self.assertNotIn((7, 2), targets)

    def test_castling_rules(self):
        for name, engine in self.each_engine():
            both = self.moves(engine, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1')
            self.assertTrue({(7, 6), (7, 2)} <= both)
            in_check = self.moves(engine, 'r3k2r/8/8/8/4R3/8/8/4K3 b kq - 0 1', 'e8')
            self.assertFalse({(0, 6), (0, 2)} & in_check)
            through_check = self.moves(engine, 'r3k2r/8/8/8/5R2/8/8/4K3 b kq - 0 1', 'e8')
            self.assertNotIn((0, 6), through_check)
            self.assertIn((0, 2), through_check)

    def test_en_passant_needs_the_pawn_that_just_moved(self):
        for name, engine in self.each_engine():
            real = self.moves(engine, '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'e5')
            self.assertIn((2, 3), real)
            # a queen, not a pawn, stands on d5
            bogus = self.moves(engine, '4k3/8/8/3qP3/8/8/8/4K3 w - d6 0 1', 'e5')
            self.assertNotIn((2, 3), bogus)

    def test_en_passant_may_not_expose_the_king(self):
        for name, engine in self.each_engine():
            targets = self.moves(engine, '8/8/8/K2pP2r/8/8/8/7k w - d6 0 1', 'e5')
            self.assertEqual(targets, {(2, 4)})

    def test_validate_always_answers_and_checks_king_safety(self):
        for name, engine in self.each_engine():
            start = fields(START)
            self.assertEqual(engine.ask(f'VALIDATE {start} {square("e2")} {square("e4")}'), 'VALID')
            for origin, target in (('e4', 'e5'), ('e7', 'e5'), ('e2', 'e2'), ('a1', 'a2')):
                reply = engine.ask(f'VALIDATE {start} {square(origin)} {square(target)}')
                self.assertTrue(reply.startswith('INVALID'), reply)
            pinned = fields('4k3/4r3/8/8/8/8/4N3/4K3 w - - 0 1')
            reply = engine.ask(f'VALIDATE {pinned} {square("e2")} {square("d4")}')
            self.assertTrue(reply.startswith('INVALID'), reply)

    def test_promote_refuses_a_move_that_leaves_the_king_in_check(self):
        for name, engine in self.each_engine():
            free = fields('6k1/P7/8/8/8/8/8/4K3 w - - 0 1')
            reply = engine.ask(f'PROMOTE {free} {square("a7")} {square("a8")} q')
            self.assertTrue(reply.startswith('PROMOTE'), reply)
            # the rook on e8 gives check; promoting does not answer it
            in_check = fields('4r1k1/P7/8/8/8/8/8/4K3 w - - 0 1')
            reply = engine.ask(f'PROMOTE {in_check} {square("a7")} {square("a8")} q')
            self.assertTrue(reply.startswith('INVALID'), reply)

    def test_promote_without_a_piece_means_queen(self):
        for name, engine in self.each_engine():
            position = fields('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
            reply = engine.ask(f'PROMOTE {position} {square("a7")} {square("a8")}')
            self.assertEqual(reply.split()[1][0], 'Q')
            reply = engine.ask(f'PROMOTE {position} {square("a7")} {square("a8")} n')
            self.assertEqual(reply.split()[1][0], 'N')

    def test_every_line_gets_exactly_one_reply(self):
        for name, engine in self.each_engine():
            start = fields(START)
            self.assertEqual(engine.ask('VERSION'), f'VERSION {ChessGame.PROTOCOL_VERSION}')
            self.assertEqual(engine.ask('HELLO'), 'ERROR unknown command')
            self.assertEqual(engine.ask(f'STATUS {start[:70]}'), 'ERROR malformed command')
            self.assertEqual(engine.ask(f'MOVES {start} 9 9'), 'ERROR malformed command')
            self.assertEqual(engine.ask(f'MOVES {start} x y'), 'ERROR malformed command')
            # still in step afterwards
            self.assertEqual(engine.ask(f'STATUS {start}'), 'STATUS OK')

    def test_status(self):
        cases = [
            (START, 'OK'),
            ('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3', 'CHECKMATE'),
            ('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1', 'STALEMATE'),
            ('4k3/8/8/8/4R3/8/8/4K3 b - - 0 1', 'CHECK'),
            ('4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'DRAW'),
            ('4k3/8/8/8/8/8/8/4KN2 w - - 0 1', 'DRAW'),
            # bishops on squares of one colour cannot mate
            ('4k3/8/8/8/8/2B5/8/4K1b1 w - - 0 1', 'DRAW'),
            ('4k3/8/8/8/8/2B5/8/4K2b w - - 0 1', 'OK'),
            # a dead position is a draw even with the king in check
            ('B7/5K2/8/3k4/8/8/8/8 b - - 0 1', 'DRAW'),
            ('4k3/8/8/8/8/8/8/4KNN1 w - - 0 1', 'OK'),
        ]
        for name, engine in self.each_engine():
            for fen, expected in cases:
                self.assertEqual(engine.ask(f'STATUS {fields(fen)}'), f'STATUS {expected}', fen)

    def test_notation(self):
        cases = [
            (START, 'g1', 'f3', '', 'Nf3'),
            ('4k3/8/8/8/8/2N3N1/8/4K3 w - - 0 1', 'c3', 'e4', '', 'Nce4'),
            ('4k3/R7/8/8/8/8/R7/4K3 w - - 0 1', 'a2', 'a4', '', 'R2a4'),
            ('5k2/8/8/8/8/8/8/4K2R w K - 0 1', 'e1', 'g1', '', 'O-O+'),
            ('3k4/8/8/8/8/8/8/R3K3 w Q - 0 1', 'e1', 'c1', '', 'O-O-O+'),
            ('8/8/8/1k1pP2R/8/8/8/4K3 w - d6 0 1', 'e5', 'd6', '', 'exd6+'),
            ('4k3/P7/8/8/8/8/8/4K3 w - - 0 1', 'a7', 'a8', ' n', 'a8=N'),
            ('6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1', 'a1', 'a8', '', 'Ra8#'),
            # the en passant square left by Black's last move must not give
            # Black a way out of this mate
            ('1rk5/1pp4Q/8/3pN3/8/8/8/6K1 w - d6 0 1', 'h7', 'd7', '', 'Qd7#'),
        ]
        for name, engine in self.each_engine():
            for fen, origin, target, promo, expected in cases:
                reply = engine.ask(f'NOTATION {fields(fen)} {square(origin)} {square(target)}{promo}')
                self.assertEqual(reply, f'NOTATION {expected}', fen)


class EvaluationTest(EngineTestCase):

    POSITIONS = [fen for fen, _ in PERFT] + [
        'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
        'r1bq1rk1/ppp2ppp/3p1n2/2b1p3/2B1P3/3P1N2/PPP2PPP/R1BQ1RK1 b - - 0 8',
        '8/5pk1/6p1/8/3R4/6P1/r4P1K/8 w - - 0 40',
        '8/8/8/3k4/8/8/1Q6/K7 b - - 0 1',
        '8/8/4k3/8/2p5/8/1P3K2/8 w - - 0 1',
        '4k3/8/8/8/8/8/8/4KNN1 w - - 0 1',
    ]

    def evaluate(self, engine, fen):
        return int(engine.ask(f'EVAL {fields(fen)}').split()[1])

    def test_both_engines_evaluate_alike(self):
        if 'cpp' not in self.engines:
            self.skipTest('no compiled engine on this machine')
        for fen in self.POSITIONS:
            self.assertEqual(self.evaluate(self.engines['cpp'], fen),
                             self.evaluate(self.engines['python'], fen), fen)

    def test_evaluation_is_from_whites_side(self):
        for name, engine in self.each_engine():
            self.assertGreater(self.evaluate(engine, '4k3/8/8/8/8/8/8/3QK3 w - - 0 1'), 500)
            self.assertLess(self.evaluate(engine, '3qk3/8/8/8/8/8/8/4K3 w - - 0 1'), -500)
            self.assertEqual(self.evaluate(engine, '4k3/8/8/8/8/8/8/4KNN1 w - - 0 1'), 0)

    def test_king_stays_home_while_queens_are_on(self):
        """One traded pair of minor pieces must not send the king to the centre."""
        for name, engine in self.each_engine():
            home = self.evaluate(engine, 'r1bqk2r/ppp2ppp/3p1n2/2b1p3/2B1P3/3P1N2/PPP2PPP/R1BQ1RK1 b kq - 0 7')
            walked = self.evaluate(engine, 'r1bqk2r/ppp2ppp/3p1n2/2b1p3/2B1P3/3P1N2/PPP1KPPP/R1BQ3R b kq - 0 7')
            self.assertGreater(home, walked)


class SearchTest(EngineTestCase):

    def best(self, engine, fen, depth=6, extra=''):
        reply = engine.ask(f'BESTMOVE {fields(fen)} {depth} 30000 0 3{extra}')
        tokens = reply.split()
        if tokens[1] == 'NONE':
            return None, None
        files = 'abcdefgh'
        move = (f"{files[int(tokens[2])]}{8 - int(tokens[1])}"
                f"{files[int(tokens[4])]}{8 - int(tokens[3])}")
        return move, int(tokens[tokens.index('EVAL') + 1])

    def test_no_move_when_the_game_is_over(self):
        for name, engine in self.each_engine():
            self.assertEqual(self.best(engine, '7k/5Q2/6K1/8/8/8/8/8 b - - 0 1'), (None, None))
            self.assertEqual(self.best(engine, 'R5k1/5ppp/8/8/8/8/8/6K1 b - - 0 1'), (None, None))

    def test_finds_forced_mates(self):
        cases = [
            # mate in one, for either colour
            ('6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1', {'a1a8'}, 99998),
            ('r5k1/8/8/8/8/8/5PPP/6K1 b - - 0 1', {'a8a1'}, -99998),
            # mate in two: the rooks take the ranks one after the other
            ('7k/8/8/8/8/8/R7/1R4K1 w - - 0 1', {'a2a7', 'b1b7'}, 99996),
            # mate in three; more than one first move does it
            ('8/8/8/2K5/3B4/3Q4/PP5P/2k5 w - - 5 63', None, 99994),
        ]
        for name, engine in self.each_engine():
            for fen, keys, score in cases:
                move, evaluation = self.best(engine, fen)
                if keys:
                    self.assertIn(move, keys, fen)
                self.assertEqual(evaluation, score, fen)

    def test_wins_material_with_simple_tactics(self):
        cases = [
            ('3q3k/8/8/4N3/8/8/8/6K1 w - - 0 1', 'e5f7'),   # knight fork of king and queen
            ('3q4/8/8/3k4/8/8/8/R5K1 w - - 0 1', 'a1d1'),   # rook skewer
            ('6k1/8/2n1n3/8/3P4/8/8/7K w - - 0 1', 'd4d5'),  # pawn fork
            ('7k/8/8/3p4/8/2N1N3/8/6K1 b - - 0 1', 'd5d4'),  # the same for Black
        ]
        for name, engine in self.each_engine():
            for fen, key in cases:
                self.assertEqual(self.best(engine, fen)[0], key, fen)

    def test_does_not_take_a_defended_pawn_with_the_queen(self):
        for name, engine in self.each_engine():
            for depth in (1, 2, 3):
                move, _ = self.best(engine, '4k3/8/4p3/3p4/8/8/3Q4/4K3 w - - 0 1', depth)
                self.assertNotEqual(move, 'd2d5')

    def test_avoids_a_repetition_when_winning(self):
        """With the earlier positions sent along, a won game is not repeated."""
        fen = '7k/8/8/5K2/8/8/1R6/8 w - - 6 4'
        # The same position after Kf5-e5, which is what the game shows twice
        seen = ' 7k/8/8/4K3/8/8/1R6/8 b - -'
        for name, engine in self.each_engine():
            reply = engine.ask(f'BESTMOVE {fields(fen)} 4 30000 6 3{seen}{seen}')
            tokens = reply.split()
            self.assertNotEqual(tokens[1:5], ['3', '5', '3', '4'], reply)
            self.assertGreater(int(tokens[tokens.index('EVAL') + 1]), 300, reply)

    def test_saves_a_lost_game_by_perpetual_check(self):
        """Far behind in material, White has Qe8+ Kh7 Qh5+ Kg8 Qe8+ for ever."""
        for name, engine in self.each_engine():
            move, evaluation = self.best(engine, '6k1/6p1/8/8/8/1q6/rr2Q3/7K w - - 0 1')
            self.assertEqual((move, evaluation), ('e2e8', 0))

    def test_fifty_move_rule_is_seen(self):
        for name, engine in self.each_engine():
            fen = '7k/8/8/5K2/8/8/1R6/8 w - - 99 60'
            reply = engine.ask(f'BESTMOVE {fields(fen)} 4 30000 99 0')
            tokens = reply.split()
            # every move reaches the hundredth quiet half-move: a draw
            self.assertEqual(int(tokens[tokens.index('EVAL') + 1]), 0, reply)

    def test_search_stops_at_its_time_limit(self):
        for name, engine in self.each_engine():
            reply = engine.ask(f'BESTMOVE {fields(KIWIPETE)} 64 500 0 3')
            tokens = reply.split()
            # The engine aims to answer inside the limit. The bound here is
            # loose because a busy test machine may not run it on time.
            self.assertLess(int(tokens[tokens.index('TIME') + 1]), 1500, reply)
            self.assertGreaterEqual(int(tokens[tokens.index('DEPTH') + 1]), 1, reply)
            self.assertEqual(tokens[-1], 'timeout', reply)
