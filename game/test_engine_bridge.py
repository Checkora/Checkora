"""Tests for the bridge between Django and the engines (game/engine.py)."""
import json
import os
import shutil
import sys
import tempfile
import time
from unittest import mock

from django.test import SimpleTestCase

from game.engine import ChessGame

MAIN_PY = os.path.join(ChessGame.ENGINE_DIR, 'main.py')


class BridgeTestCase(SimpleTestCase):
    """Keeps per-process bridge state out of the way and stops every
    engine server a test started."""

    def setUp(self):
        for patcher in (
            mock.patch.dict(ChessGame._engine_health),
            mock.patch.dict(ChessGame._server_procs),
            mock.patch.object(ChessGame, '_persistent_retry_at', 0.0),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def game(self, fen=None, **kwargs):
        game = ChessGame.from_fen(fen, **kwargs) if fen else ChessGame(**kwargs)
        self.addCleanup(game.cleanup_engine)
        return game


class PromotionInputTest(BridgeTestCase):
    """The promotion piece comes from the client and ends up in an engine
    command; anything but q, r, b, n must become a queen."""

    FEN = '4k3/P7/8/8/8/8/8/R3K2R w - - 0 1'

    def fresh(self):
        """A new copy of the position that shares one engine server."""
        if not hasattr(self, 'base'):
            self.base = self.game(self.FEN)
        return ChessGame.from_dict(json.loads(json.dumps(self.base.to_dict())))

    def test_odd_values_promote_to_a_queen(self):
        for value in (' ', '\n', '\t', '', None, 5, ['q'], {'a': 1}, 'queen', 'q STATUS x'):
            with self.subTest(value=value):
                game = self.fresh()
                started = time.time()
                ok, notation, _, _ = game.make_move(1, 0, 0, 0, value)
                self.assertTrue(ok)
                self.assertEqual(game.board[0][0], 'Q')
                self.assertTrue(notation.startswith('a8=Q'), notation)
                self.assertLess(time.time() - started, 5)

    def test_under_promotion(self):
        for value, piece in (('n', 'N'), ('R', 'R'), ('b', 'B')):
            with self.subTest(value=value):
                game = self.fresh()
                ok, notation, _, _ = game.make_move(1, 0, 0, 0, value)
                self.assertTrue(ok)
                self.assertEqual(game.board[0][0], piece)
                self.assertTrue(notation.startswith(f'a8={piece}'), notation)

    def test_only_one_letter_reaches_the_engine(self):
        game = self.fresh()
        sent = []
        with mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok')), \
                mock.patch.object(ChessGame, '_call_engine', side_effect=lambda cmd: sent.append(cmd)):
            game.make_move(1, 0, 0, 0, 'q\nBESTMOVE x')
        promote = [cmd for cmd in sent if cmd.startswith('PROMOTE')]
        self.assertEqual(len(promote), 1)
        self.assertTrue(promote[0].endswith(' 1 0 0 0 q'), promote[0])


class EngineErrorAttributeTest(BridgeTestCase):
    """last_engine_error tells "nothing to report" from "engine silent"."""

    def test_no_legal_move_is_not_an_error(self):
        game = self.game('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')   # stalemate
        self.assertIsNone(game.get_ai_move())
        self.assertIsNone(game.last_engine_error)

    def test_silent_engine(self):
        game = ChessGame()
        ChessGame._opening_book = {}
        self.addCleanup(setattr, ChessGame, '_opening_book', None)
        with mock.patch.object(ChessGame, '_call_engine', return_value=None):
            self.assertIsNone(game.get_ai_move())
            self.assertEqual(game.last_engine_error, 'no_reply')
            self.assertEqual(game.get_valid_moves(6, 4), [])
            self.assertEqual(game.last_engine_error, 'no_reply')
            self.assertEqual(game.check_game_status(), 'ok')
            self.assertEqual(game.last_engine_error, 'no_reply')
            ok, message, _, _ = game.make_move(6, 4, 4, 4)
            self.assertFalse(ok)
            self.assertEqual(game.last_engine_error, 'no_reply')

    def test_unusable_reply(self):
        game = ChessGame()
        ChessGame._opening_book = {}
        self.addCleanup(setattr, ChessGame, '_opening_book', None)
        for reply in ('ERROR: Engine terminated', 'BESTMOVE 9 9 9 9', 'BESTMOVE a b c d', 'BESTMOVE 6 4'):
            with self.subTest(reply=reply), \
                    mock.patch.object(ChessGame, '_call_engine', return_value=reply):
                self.assertIsNone(game.get_ai_move())
                self.assertEqual(game.last_engine_error, 'bad_reply')

    def test_an_answer_clears_the_error(self):
        game = self.game()
        game.last_engine_error = 'no_reply'
        self.assertEqual(len(game.get_valid_moves(6, 4)), 2)
        self.assertIsNone(game.last_engine_error)
        game.last_engine_error = 'no_reply'
        self.assertEqual(game.get_valid_moves(3, 3), [])   # empty square: no engine call
        self.assertIsNone(game.last_engine_error)

    def test_a_failed_answer_is_not_cached(self):
        game = self.game()
        with mock.patch.object(ChessGame, '_call_engine', return_value=None):
            self.assertEqual(game.get_valid_moves(6, 4), [])
        self.assertEqual(len(game.get_valid_moves(6, 4)), 2)

    def test_not_stored_in_the_session(self):
        game = ChessGame()
        game.last_engine_error = 'no_reply'
        self.assertNotIn('last_engine_error', game.to_dict())
        self.assertIsNone(ChessGame.from_dict(game.to_dict()).last_engine_error)


class CoordinateTest(BridgeTestCase):

    def test_squares_off_the_board(self):
        game = ChessGame()
        with mock.patch.object(ChessGame, '_call_engine') as engine:
            for row, col in ((-1, -1), (8, 0), (0, 8), ('6', 4), (True, 4)):
                self.assertEqual(game.get_valid_moves(row, col), [])
            self.assertEqual(game.make_move(9, 4, 4, 4)[:2], (False, 'Illegal move.'))
            self.assertEqual(game.make_move(6, 4, -1, 4)[:2], (False, 'Illegal move.'))
        engine.assert_not_called()


class FromFenTest(BridgeTestCase):

    def test_castling_rights_need_king_and_rook_at_home(self):
        game = self.game('4k3/8/8/8/8/8/8/4K2Q w KQkq - 0 1')
        self.assertEqual(game.castling_rights, {'w_k': False, 'w_q': False, 'b_k': False, 'b_q': False})
        self.assertNotIn((7, 6), {(m['row'], m['col']) for m in game.get_valid_moves(7, 4)})
        game = self.game('r3k2r/8/8/8/8/8/8/R3K2R w Kq - 0 1')
        self.assertEqual(game.castling_rights, {'w_k': True, 'w_q': False, 'b_k': False, 'b_q': True})

    def test_en_passant_square_must_match_the_board(self):
        good = self.game('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1')
        self.assertEqual(good.en_passant_target, (5, 4))
        self.assertTrue(good.initial_fen.split()[3] == 'e3')
        for fen in (
            '4k3/8/8/3qP3/8/8/8/4K3 w - d6 0 1',    # a queen stands where the pawn should be
            '4k3/8/8/4P3/8/8/8/4K3 w - d6 0 1',     # nothing there
            '4k3/8/8/3pP3/8/8/8/4K3 b - d6 0 1',    # wrong side to move
            '4k3/8/8/3pP3/8/8/8/4K3 w - d3 0 1',    # wrong rank
        ):
            with self.subTest(fen=fen):
                game = self.game(fen)
                self.assertIsNone(game.en_passant_target)
                self.assertEqual(game.initial_fen.split()[3], '-')

    def test_side_not_to_move_may_not_be_in_check(self):
        with self.assertRaises(ValueError):
            ChessGame.from_fen('4k3/4Q3/8/8/8/8/8/4K3 w - - 0 1')
        # the same position with Black to move is a normal check
        game = self.game('4k3/4Q3/8/8/8/8/8/4K3 b - - 0 1')
        self.assertEqual(game.check_game_status(), 'check')


class LoadedPositionStatusTest(BridgeTestCase):
    """A position loaded from a FEN knows its status before the first move."""

    def test_side_to_move_in_check(self):
        game = self.game('4k3/8/8/8/7b/8/8/4K2R w K - 0 1')
        self.assertEqual(game.game_status, 'active')     # still playable
        self.assertTrue(game.in_check)
        self.assertEqual(game.display_status, 'check')
        restored = ChessGame.from_dict(json.loads(json.dumps(game.to_dict())))
        self.assertEqual(restored.display_status, 'check')
        # castling out of check is not on offer
        self.assertNotIn((7, 6), {(m['row'], m['col']) for m in restored.get_valid_moves(7, 4)})

    def test_quiet_position(self):
        game = self.game('4k3/8/8/8/8/8/8/4K2R w K - 0 1')
        self.assertFalse(game.in_check)
        self.assertEqual(game.display_status, 'active')

    def test_position_that_is_already_over(self):
        cases = [
            ('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3', 'checkmate', None),
            ('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1', 'stalemate', 'stalemate'),
            ('4k3/8/8/8/8/8/8/4KB2 w - - 0 1', 'draw', 'insufficient_material'),
        ]
        for fen, status, reason in cases:
            with self.subTest(fen=fen):
                game = self.game(fen)
                self.assertEqual((game.game_status, game.draw_reason), (status, reason))
                self.assertEqual(game.display_status, status)
                self.assertFalse(game.make_move(6, 0, 5, 0)[0])

    def test_check_is_tracked_move_by_move(self):
        game = self.game('4k3/8/8/8/8/8/8/R3K3 w Q - 0 1')
        self.assertEqual(game.make_move(7, 0, 0, 0)[3], 'check')      # Ra8+
        self.assertEqual((game.game_status, game.display_status), ('active', 'check'))
        self.assertTrue(game.to_dict()['in_check'])
        self.assertEqual(game.make_move(0, 4, 1, 4)[3], 'ok')         # Ke7
        self.assertEqual(game.display_status, 'active')
        self.assertFalse(game.to_dict()['in_check'])

    def test_older_sessions_load(self):
        state = ChessGame().to_dict()
        del state['in_check']
        self.assertFalse(ChessGame.from_dict(state).in_check)


class NotationTest(BridgeTestCase):

    def test_mate_is_written_once(self):
        game = self.game('1rk5/1pp4Q/8/3pN3/8/8/8/6K1 w - d6 0 1')
        ok, notation, _, status = game.make_move(1, 7, 1, 3)
        self.assertEqual((ok, notation, status), (True, 'Qd7#', 'checkmate'))

    def test_castling_with_check(self):
        game = self.game('5k2/8/8/8/8/8/8/4K2R w K - 0 1')
        ok, notation, _, status = game.make_move(7, 4, 7, 6)
        self.assertEqual((ok, notation, status), (True, 'O-O+', 'check'))

    def test_status_decides_the_suffix(self):
        game = ChessGame()
        replies = {'NOTATION': 'NOTATION Nf3+', 'STATUS': 'STATUS CHECKMATE'}
        with mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok')), \
                mock.patch.object(ChessGame, '_call_engine',
                                  side_effect=lambda cmd: replies.get(cmd.split()[0])):
            _, notation, _, status = game.make_move(7, 6, 5, 5)
        self.assertEqual((notation, status), ('Nf3#', 'checkmate'))


class AiMoveCommandTest(BridgeTestCase):
    """What get_ai_move() asks the engine for at each level."""

    FEN = 'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 5 4'

    def command(self, game, **kwargs):
        sent = []
        with mock.patch.object(ChessGame, '_call_engine', side_effect=lambda cmd: sent.append(cmd)):
            game.get_ai_move(**kwargs)
        return [cmd.split() for cmd in sent if cmd.startswith('BESTMOVE')][-1]

    def new_game(self, difficulty):
        ChessGame._opening_book = {}
        self.addCleanup(setattr, ChessGame, '_opening_book', None)
        return ChessGame.from_dict(dict(ChessGame(difficulty=difficulty).to_dict()))

    def test_levels(self):
        expected = {
            # level: depth, time limit, alternatives
            'easy': ('2', '500', '8'),
            'medium': ('4', '1500', '3'),
            'hard': ('64', '4000', '3'),
        }
        for level, (depth, limit, alternatives) in expected.items():
            with self.subTest(level=level):
                tokens = self.command(self.new_game(level))
                self.assertEqual(tokens[6:8], [depth, limit])
                self.assertEqual(tokens[9], alternatives)
                # the argument wins over the game's own level
                tokens = self.command(self.new_game('medium'), difficulty=level)
                self.assertEqual(tokens[6:8], [depth, limit])

    def test_explicit_depth_is_taken_as_given(self):
        game = self.new_game('hard')
        for depth in (1, 2, 3, 5):
            self.assertEqual(self.command(game, depth=depth)[6], str(depth))
        self.assertEqual(self.command(game, depth=0)[6], '1')

    def test_clock_and_earlier_positions_are_sent(self):
        game = self.new_game('medium')
        with mock.patch.object(ChessGame, '_call_engine',
                               side_effect=lambda cmd: 'STATUS OK' if cmd.startswith('STATUS') else None), \
                mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok')):
            for move in ((7, 6, 5, 5), (0, 6, 2, 5), (5, 5, 7, 6)):
                game.make_move(*move)
        tokens = self.command(game)
        self.assertEqual(tokens[8], '3')          # half-move clock
        earlier = tokens[10:]
        self.assertEqual(len(earlier), 3 * 4)     # three earlier positions, four fields each
        self.assertEqual(earlier[0], 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR')
        self.assertEqual(earlier[1:4], ['w', 'KQkq', '-'])

    def test_reply_is_parsed(self):
        game = self.new_game('medium')
        reply = ('BESTMOVE 6 4 4 4 EVAL 31 ALTS 6 3 4 3 25 7 6 5 5 20 DEPTH 9 NODES 1234 '
                 'TTHITS 56 TIME 120 ENGINE cpp STATUS completed')
        with mock.patch.object(ChessGame, '_call_engine', return_value=reply):
            move = game.get_ai_move()
        self.assertEqual((move['from_row'], move['from_col'], move['to_row'], move['to_col']), (6, 4, 4, 4))
        self.assertEqual((move['eval'], move['depth'], move['engine']), (31, 9, 'cpp'))
        self.assertEqual(len(move['alts']), 2)
        self.assertNotIn('promotion_piece', move)

    def test_promotion_is_reported(self):
        game = self.game('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        with mock.patch.object(ChessGame, '_call_engine', return_value='BESTMOVE 1 0 0 0 EVAL 900'):
            self.assertEqual(game.get_ai_move()['promotion_piece'], 'q')


class EasyLevelTest(BridgeTestCase):
    """The easy level makes bounded, deliberate mistakes."""

    REPLY = ('BESTMOVE 6 4 4 4 EVAL 40 ALTS 6 3 4 3 30 7 6 5 5 -500 7 1 5 2 -1000 '
             'DEPTH 2 NODES 100 TTHITS 0 TIME 1 ENGINE cpp STATUS completed')

    def play(self, difficulty, roll, **kwargs):
        ChessGame._opening_book = {}
        self.addCleanup(setattr, ChessGame, '_opening_book', None)
        game = ChessGame(difficulty=difficulty)
        with mock.patch.object(ChessGame, '_call_engine', return_value=self.REPLY), \
                mock.patch('game.engine.random.random', return_value=roll), \
                mock.patch('game.engine.random.choice', side_effect=lambda items: items[-1]):
            return game.get_ai_move(**kwargs)

    def test_usually_plays_the_best_move(self):
        move = self.play('easy', 0.5)
        self.assertEqual((move['from_row'], move['to_row'], move['eval']), (6, 4, 40))

    def test_sometimes_plays_a_weaker_move_within_the_bound(self):
        move = self.play('easy', 0.0)
        # the worst alternative allowed loses 540, the one losing 1040 is out of bounds
        self.assertEqual((move['from_row'], move['from_col'], move['eval']), (7, 6, -500))
        self.assertEqual(move['alts'][0]['eval'], 40)
        self.assertEqual(len(move['alts']), 3)

    def test_other_levels_and_explicit_depth_never_do(self):
        self.assertEqual(self.play('medium', 0.0)['eval'], 40)
        self.assertEqual(self.play('hard', 0.0)['eval'], 40)
        self.assertEqual(self.play('easy', 0.0, depth=2)['eval'], 40)

    def test_bound_counts_from_the_movers_side(self):
        ChessGame._opening_book = {}
        self.addCleanup(setattr, ChessGame, '_opening_book', None)
        game = ChessGame(difficulty='easy')
        game.current_turn = 'black'
        game.repetition_history = [game.generate_position_key()]
        reply = 'BESTMOVE 1 4 3 4 EVAL -40 ALTS 1 3 3 3 500 0 6 2 5 1000 DEPTH 2'
        with mock.patch.object(ChessGame, '_call_engine', return_value=reply), \
                mock.patch('game.engine.random.random', return_value=0.0), \
                mock.patch('game.engine.random.choice', side_effect=lambda items: items[-1]):
            move = game.get_ai_move()
        self.assertEqual(move['eval'], 500)   # 540 worse for Black; 1040 worse is not allowed


class EngineChoiceTest(BridgeTestCase):
    """A compiled engine is only used if it runs here and speaks the
    current protocol; otherwise main.py takes over."""

    def candidates(self, script):
        folder = tempfile.mkdtemp()
        binary = os.path.join(folder, 'main')
        with open(binary, 'w') as handle:
            handle.write(script)
        os.chmod(binary, 0o755)
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        return [binary, MAIN_PY]

    def resolve(self, script):
        with mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', self.candidates(script)), \
                self.assertLogs('game.engine', level='WARNING'):
            return ChessGame._resolve_engine_path()

    def test_file_that_is_not_a_program(self):
        self.assertEqual(self.resolve('not a program for this machine\n'), MAIN_PY)

    def test_engine_built_from_older_sources(self):
        if os.name == 'nt':
            self.skipTest('needs a shell script')
        self.assertEqual(self.resolve('#!/bin/sh\nread line\necho "STATUS OK"\n'), MAIN_PY)

    def test_engine_that_speaks_the_protocol(self):
        if os.name == 'nt':
            self.skipTest('needs a shell script')
        candidates = self.candidates(
            f'#!/bin/sh\nread line\necho "VERSION {ChessGame.PROTOCOL_VERSION}"\n')
        with mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', candidates):
            self.assertEqual(ChessGame._resolve_engine_path(), candidates[0])

    def test_not_executable(self):
        if os.name == 'nt':
            self.skipTest('every file is executable on Windows')
        candidates = self.candidates('#!/bin/sh\necho "VERSION 2"\n')
        os.chmod(candidates[0], 0o644)
        with mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', candidates), \
                self.assertLogs('game.engine', level='WARNING'):
            self.assertEqual(ChessGame._resolve_engine_path(), MAIN_PY)

    def test_the_game_is_playable_with_a_broken_binary(self):
        with mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', self.candidates('garbage\n')), \
                self.assertLogs('game.engine', level='WARNING'):
            game = self.game()
            self.assertEqual(game.make_move(6, 4, 4, 4)[:2], (True, 'e4'))
            self.assertIsNone(game.last_engine_error)


class EngineServerTest(BridgeTestCase):
    """The per-game engine server must not hang its callers."""

    def silent_engine(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.py', delete=False)
        handle.write('import sys, time\nfor line in sys.stdin:\n    time.sleep(3600)\n')
        handle.close()
        self.addCleanup(os.remove, handle.name)
        return [sys.executable, handle.name]

    def test_engine_that_never_answers(self):
        game = self.game()
        with mock.patch.object(ChessGame, '_resolve_engine_path', return_value=MAIN_PY), \
                mock.patch.object(ChessGame, '_build_engine_command', return_value=self.silent_engine()), \
                mock.patch.object(ChessGame, 'ANALYSIS_TIMEOUT_SECONDS', 1):
            started = time.time()
            self.assertEqual(game.check_game_status(), 'ok')
            self.assertEqual(game.last_engine_error, 'no_reply')
            # and again: the first failure must not leave anything stuck
            self.assertEqual(game.get_valid_moves(6, 4), [])
            self.assertLess(time.time() - started, 15)

    def test_server_exits_when_the_game_ends(self):
        game = self.game()
        self.assertEqual(game.check_game_status(), 'ok')
        pid_file = os.path.join(tempfile.gettempdir(), f'checkora_engine_{game.game_id}.pid')
        self.assertTrue(os.path.exists(pid_file))
        proc = ChessGame._server_procs[game.game_id]
        game.cleanup_engine()
        self.assertFalse(os.path.exists(pid_file))
        self.assertIsNotNone(proc.poll())            # reaped, not left as a zombie
        self.assertNotIn(game.game_id, ChessGame._server_procs)

    def test_failed_start_is_remembered(self):
        game = self.game()
        missing = os.path.join(tempfile.gettempdir(), 'no_such_engine_dir')
        with mock.patch.object(ChessGame, 'ENGINE_DIR', missing), \
                mock.patch.object(ChessGame, '_resolve_engine_path', return_value=MAIN_PY), \
                self.assertLogs('game.engine', level='WARNING'):
            started = time.time()
            self.assertEqual(game.check_game_status(), 'ok')     # answered by a one-off engine
            first = time.time() - started
            started = time.time()
            self.assertEqual(game.check_game_status(), 'ok')
            self.assertEqual(len(game.get_valid_moves(6, 4)), 2)
            self.assertLess(time.time() - started, first)        # no second wait for a server


class OpeningBookFileTest(SimpleTestCase):
    """Every move in opening_book.json must be legal in its position."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(ChessGame.OPENING_BOOK_PATH, encoding='utf-8') as handle:
            cls.book = json.load(handle)

    def game_for(self, key):
        placement, turn, rights = key.split()
        game = ChessGame()
        game.board = ChessGame._parse_fen_placement(placement)
        game.current_turn = 'white' if turn == 'w' else 'black'
        game.castling_rights = ChessGame._parse_fen_castling(rights)
        game.repetition_history = [game.generate_position_key()]
        return game

    def test_book_moves_are_legal(self):
        positions = [key for key in self.book if not key.startswith('_')]
        self.assertGreater(len(positions), 30)
        with mock.patch.object(ChessGame, '_resolve_engine_path', return_value=MAIN_PY):
            game = None
            try:
                for key in positions:
                    previous, game = game, self.game_for(key)
                    if previous:
                        game.game_id, game.authkey = previous.game_id, previous.authkey
                    self.assertEqual(game.generate_fen_key(), key)
                    self.assertTrue(self.book[key], key)
                    for move in self.book[key]:
                        self.assertEqual(len(move), 4, key)
                        fr, fc, tr, tc = move
                        self.assertTrue(game.validate_move(fr, fc, tr, tc)[0], f'{key}: {move}')
            finally:
                if game:
                    game.cleanup_engine()

    def test_named_lines_can_be_played(self):
        lines = {name: line for name, line in self.book.get('_named_lines', {}).items()
                 if isinstance(line, dict)}
        with mock.patch.object(ChessGame, '_resolve_engine_path', return_value=MAIN_PY):
            for name, line in lines.items():
                game = ChessGame(time_limit=10 ** 9)
                try:
                    for ply, move in enumerate(line['moves']):
                        self.assertTrue(game.make_move(*move)[0], f'{name}: move {ply + 1} {move}')
                finally:
                    game.cleanup_engine()
