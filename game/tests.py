"""Tests for the Checkora chess engine and API endpoints."""

import json
import random
import sys
from unittest import mock

from django.test import SimpleTestCase, TestCase

from .engine import ChessGame


class EnginePathResolutionTest(SimpleTestCase):
    """Engine path selection should work across local platforms."""

    def test_uses_first_existing_engine_binary(self):
        candidates = [
            r'C:\fake\game\engine\main.exe',
            '/fake/game/engine/main',
            r'C:\fake\game\engine\main.py',
        ]

        with (
            mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', candidates),
            mock.patch('game.engine.os.path.exists', side_effect=lambda path: path == candidates[0]),
        ):
            self.assertEqual(ChessGame._resolve_engine_path(), candidates[0])

    def test_prefers_cpp_binary_before_python_fallback(self):
        candidates = [
            r'C:\fake\game\engine\main.exe',
            '/fake/game/engine/main',
            r'C:\fake\game\engine\main.py',
        ]

        with (
            mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', candidates),
            mock.patch('game.engine.os.path.exists', side_effect=lambda path: path in {candidates[1], candidates[2]}),
        ):
            self.assertEqual(ChessGame._resolve_engine_path(), candidates[1])

    def test_falls_back_to_python_engine_script(self):
        candidates = [
            r'C:\fake\game\engine\main.exe',
            '/fake/game/engine/main',
            r'C:\fake\game\engine\main.py',
        ]

        with (
            mock.patch.object(ChessGame, 'ENGINE_CANDIDATES', candidates),
            mock.patch('game.engine.os.path.exists', side_effect=lambda path: path == candidates[2]),
        ):
            self.assertEqual(ChessGame._resolve_engine_path(), candidates[2])
            self.assertEqual(
                ChessGame._build_engine_command(candidates[2]),
                [sys.executable, candidates[2]],
            )


class BoardViewTest(TestCase):
    """The board page should load and initialise a session."""

    def test_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkora')


class MoveValidationTest(TestCase):
    """Test move validation wrapper by mocking validate_move."""

    def setUp(self):
        self.client.get('/')
        
        # We mock validate_move to return specific booleans to simulate engine validation
        # and _call_engine to bypass game status and promotion checks
        self.validate_patcher = mock.patch.object(ChessGame, 'validate_move')
        self.mock_validate = self.validate_patcher.start()
        
        self.engine_patcher = mock.patch.object(ChessGame, '_call_engine')
        self.mock_engine = self.engine_patcher.start()
        self.mock_engine.return_value = "STATUS ok"

    def tearDown(self):
        self.validate_patcher.stop()
        self.engine_patcher.stop()

    def _move(self, fr, fc, tr, tc, expected_valid=True):
        self.mock_validate.return_value = (expected_valid, "Mock validation.")
        return self.client.post(
            '/api/move/',
            data=json.dumps({
                'from_row': fr, 'from_col': fc,
                'to_row': tr, 'to_col': tc,
            }),
            content_type='application/json',
        )

    # -- Pawn -------------------------------------------------------

    def test_pawn_single_advance(self):
        r = self._move(6, 4, 5, 4, True)
        self.assertTrue(r.json()['valid'])

    def test_pawn_double_advance(self):
        r = self._move(6, 4, 4, 4, True)
        self.assertTrue(r.json()['valid'])

    def test_pawn_triple_advance_invalid(self):
        r = self._move(6, 4, 3, 4, False)
        self.assertFalse(r.json()['valid'])

    # -- Turn enforcement -------------------------------------------

    def test_wrong_turn(self):
        """Black cannot move first. Handled by native Python checks, validation isn't reached if fail."""
        self.mock_validate.return_value = (True, "")  # Bypass validate to ensure python wrapper rejects it
        r = self.client.post('/api/move/', data=json.dumps({'from_row': 1, 'from_col': 4, 'to_row': 3, 'to_col': 4}), content_type='application/json')
        self.assertFalse(r.json()['valid'])

    def test_turn_alternation(self):
        r = self._move(6, 4, 4, 4, True) 
        self.assertTrue(r.json()['valid'])
        self.assertEqual(r.json()['current_turn'], 'black')

    # -- Knight -----------------------------------------------------

    def test_knight_valid(self):
        r = self._move(7, 1, 5, 2, True)
        self.assertTrue(r.json()['valid'])

    def test_knight_invalid(self):
        r = self._move(7, 1, 5, 1, False)
        self.assertFalse(r.json()['valid'])

    # -- Capture rules ----------------------------------------------

    def test_capture_own_piece_blocked(self):
        r = self._move(7, 0, 6, 0, False)
        self.assertFalse(r.json()['valid'])

    # -- Bishop blocked by own pawn ---------------------------------

    def test_bishop_blocked(self):
        r = self._move(7, 2, 5, 4, False)
        self.assertFalse(r.json()['valid'])

    # -- Multi-move sequence ----------------------------------------

    def test_three_move_sequence(self):
        self.assertTrue(self._move(6, 4, 4, 4, True).json()['valid'])
        self.assertTrue(self._move(1, 4, 3, 4, True).json()['valid'])
        self.assertTrue(self._move(7, 6, 5, 5, True).json()['valid'])

    def test_capture_tracked(self):
        self._move(6, 4, 4, 4, True)
        self._move(1, 3, 3, 3, True)
        
        # To test capture, we spoof 'p' in the destination square before sending move
        session = self.client.session
        game_data = session['game']
        game_data['board'][3][3] = 'p'
        session['game'] = game_data
        session.save()
        
        r = self._move(4, 4, 3, 3, True)
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['captured'], 'p')


class ValidMovesTest(TestCase):
    """Test the /api/valid-moves/ endpoint. Mock _call_engine heavily to test parsers."""

    def setUp(self):
        self.client.get('/')
        self.engine_patcher = mock.patch.object(ChessGame, '_call_engine')
        self.mock_engine = self.engine_patcher.start()

    def tearDown(self):
        self.engine_patcher.stop()

    def test_pawn_initial_has_two_moves(self):
        self.mock_engine.return_value = "MOVES 5 4 0 0 4 4 0 0" 
        r = self.client.get('/api/valid-moves/?row=6&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 2)

    def test_knight_initial_has_two_moves(self):
        self.mock_engine.return_value = "MOVES 5 0 0 0 5 2 0 0"
        r = self.client.get('/api/valid-moves/?row=7&col=1')
        self.assertEqual(len(r.json()['valid_moves']), 2)

    def test_empty_square_no_moves(self):
        self.mock_engine.return_value = "MOVES"
        r = self.client.get('/api/valid-moves/?row=4&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_opponent_piece_no_moves(self):
        self.mock_engine.return_value = "MOVES" # Python shortcircuits this, but mock covers edge case
        r = self.client.get('/api/valid-moves/?row=1&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_rook_blocked_at_start(self):
        self.mock_engine.return_value = "MOVES"
        r = self.client.get('/api/valid-moves/?row=7&col=0')
        self.assertEqual(len(r.json()['valid_moves']), 0)


class NewGameTest(TestCase):
    """Test the /api/new-game/ endpoint."""

    def setUp(self):
        self.client.get('/')

    def test_reset(self):
        # We manually update board without _call_engine to simulate game progress
        session = self.client.session
        game_data = session['game']
        game_data['current_turn'] = 'black'
        game_data['move_history'] = ['e4']
        session['game'] = game_data
        session.save()

        r = self.client.post('/api/new-game/', content_type='application/json')
        data = r.json()
        self.assertEqual(data['current_turn'], 'white')
        self.assertEqual(len(data['move_history']), 0)


class CheckPromotionTest(TestCase):
    """Test the /api/check-promotion/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        self.client.get('/')
        self.promo_patcher = mock.patch('game.engine.ChessGame.is_promotion_move')
        self.mock_promo = self.promo_patcher.start()

    def tearDown(self):
        self.promo_patcher.stop()

    def test_white_pawn_promotion(self):
        self.mock_promo.return_value = True
        r = self.client.get('/api/check-promotion/?from_row=1&from_col=0&to_row=0')
        self.assertTrue(r.json()['is_promotion'])
        self.mock_promo.assert_called_once()

    def test_black_pawn_promotion(self):
        self.mock_promo.return_value = True
        r = self.client.get('/api/check-promotion/?from_row=6&from_col=0&to_row=7')
        self.assertTrue(r.json()['is_promotion'])
        self.mock_promo.assert_called_once()

    def test_no_promotion(self):
        self.mock_promo.return_value = False
        r = self.client.get('/api/check-promotion/?from_row=1&from_col=0&to_row=2')
        self.assertFalse(r.json()['is_promotion'])
        self.mock_promo.assert_called_once()


class GameStateTest(TestCase):
    """Test the /api/state/ endpoint."""

    def setUp(self):
        self.client.get('/')

    def test_get_state(self):
        r = self.client.get('/api/state/')
        data = r.json()
        self.assertTrue(data['paused'])
        self.assertEqual(data['current_turn'], 'white')
        self.assertEqual(data['mode'], 'pvp')
        self.assertIn('board', data)


class PauseTest(TestCase):
    """Test the /api/pause/ endpoint."""

    def setUp(self):
        self.client.get('/')

    def test_pause_toggle(self):
        r1 = self.client.post('/api/pause/', data=json.dumps({'pause': True}), content_type='application/json')
        self.assertTrue(r1.json()['paused'])

        r2 = self.client.post('/api/pause/', data=json.dumps({'pause': False}), content_type='application/json')
        self.assertFalse(r2.json()['paused'])


class OpeningBookTest(TestCase):
    """Tests for the opening book integration in get_ai_move."""

    def setUp(self):
        # Reset class-level book cache so each test starts clean
        ChessGame._opening_book = None
        ChessGame._opening_book_loaded = False

    # -- board_to_fen -------------------------------------------------

    def test_board_to_fen_initial_position(self):
        game = ChessGame()
        self.assertEqual(
            game.board_to_fen(),
            'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq',
        )

    def test_board_to_fen_after_e4(self):
        game = ChessGame()
        game.board[4][4] = 'P'
        game.board[6][4] = None
        game.current_turn = 'black'
        self.assertEqual(
            game.board_to_fen(),
            'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq',
        )

    def test_board_to_fen_reflects_castling_rights(self):
        game = ChessGame()
        game.castling_rights['w_k'] = False
        game.castling_rights['w_q'] = False
        self.assertTrue(game.board_to_fen().endswith(' w kq'))

    # -- _get_book_move -----------------------------------------------

    def test_get_book_move_returns_move_for_starting_position(self):
        game = ChessGame()
        move = game._get_book_move()
        self.assertIsNotNone(move)
        # All starting-position book entries are pawn moves: from row 6 to row 4
        self.assertEqual(move['from_row'], 6)
        self.assertEqual(move['to_row'], 4)

    def test_get_book_move_returns_none_for_unknown_position(self):
        game = ChessGame()
        # Place an extra queen on an empty square to produce an unrecognised FEN
        game.board[4][4] = 'Q'
        self.assertIsNone(game._get_book_move())

    def test_get_book_move_coordinates_are_on_board(self):
        game = ChessGame()
        move = game._get_book_move()
        self.assertIsNotNone(move)
        for key in ('from_row', 'from_col', 'to_row', 'to_col'):
            self.assertGreaterEqual(move[key], 0)
            self.assertLessEqual(move[key], 7)

    def test_get_book_move_covers_sicilian(self):
        """After 1.e4 c5 white should have a book response."""
        game = ChessGame()
        game.board[4][4] = 'P'
        game.board[6][4] = None
        game.board[3][2] = 'p'
        game.board[1][2] = None
        game.current_turn = 'white'
        self.assertIsNotNone(game._get_book_move())

    def test_get_book_move_covers_queens_gambit(self):
        """After 1.d4 d5 white should have a book response."""
        game = ChessGame()
        game.board[4][3] = 'P'
        game.board[6][3] = None
        game.board[3][3] = 'p'
        game.board[1][3] = None
        game.current_turn = 'white'
        self.assertIsNotNone(game._get_book_move())

    # -- get_ai_move integration --------------------------------------

    def test_get_ai_move_uses_book_first(self):
        """get_ai_move should return the book move without touching the engine."""
        game = ChessGame()
        with mock.patch.object(random, 'choice', return_value=[6, 4, 4, 4]):
            with mock.patch.object(ChessGame, '_call_engine') as mock_engine:
                move = game.get_ai_move()
        mock_engine.assert_not_called()
        self.assertEqual(move, {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4})

    def test_get_ai_move_falls_back_to_engine_when_not_in_book(self):
        """When position is outside the book the engine should be consulted."""
        game = ChessGame()
        game.board[4][4] = 'Q'  # Scramble position to miss book lookup
        with mock.patch.object(ChessGame, '_call_engine', return_value='BESTMOVE 7 1 5 2'):
            move = game.get_ai_move()
        self.assertIsNotNone(move)
        self.assertEqual(move['from_row'], 7)
        self.assertEqual(move['to_row'], 5)

    # -- _load_opening_book error handling ----------------------------

    def test_load_opening_book_handles_missing_file(self):
        """A missing book file should not crash; an empty dict is returned."""
        with mock.patch.object(ChessGame, 'ENGINE_DIR', '/nonexistent/path'):
            book = ChessGame._load_opening_book()
        self.assertEqual(book, {})

    def test_load_opening_book_is_cached(self):
        """The book file should only be read once across repeated calls."""
        game = ChessGame()
        with mock.patch('builtins.open', mock.mock_open(read_data='{}')) as m:
            ChessGame._load_opening_book()
            ChessGame._load_opening_book()
        m.assert_called_once()

    def test_all_book_moves_are_legal(self):
        """Every move stored in the opening book must be geometrically legal."""
        book = ChessGame._load_opening_book()
        self.assertTrue(book, "Opening book must not be empty")

        for fen, moves in book.items():
            placement, turn = fen.split()[:2]

            # Reconstruct board from FEN placement
            board = []
            for rank in placement.split('/'):
                row = []
                for ch in rank:
                    if ch.isdigit():
                        row.extend([None] * int(ch))
                    else:
                        row.append(ch)
                board.append(row)

            for move in moves:
                fr, fc, tr, tc = move
                ctx = f"FEN={fen} move={move}"

                # All coordinates on the board
                for v in (fr, fc, tr, tc):
                    self.assertIn(v, range(8), ctx)

                piece = board[fr][fc]
                self.assertIsNotNone(piece, f"Empty from-square in {ctx}")

                # Piece belongs to the side to move
                self.assertEqual(piece.isupper(), turn == 'w', f"Wrong colour in {ctx}")

                # Pawn geometry
                if piece in ('P', 'p'):
                    row_diff = tr - fr
                    col_diff = abs(tc - fc)
                    if piece == 'P':
                        self.assertLess(row_diff, 0, f"White pawn must move up in {ctx}")
                        self.assertGreaterEqual(row_diff, -2, f"White pawn >2 squares in {ctx}")
                        if row_diff == -2:
                            self.assertEqual(col_diff, 0, ctx)
                            self.assertEqual(fr, 6, f"White pawn double-advance not from rank 2 in {ctx}")
                    else:
                        self.assertGreater(row_diff, 0, f"Black pawn must move down in {ctx}")
                        self.assertLessEqual(row_diff, 2, f"Black pawn >2 squares in {ctx}")
                        if row_diff == 2:
                            self.assertEqual(col_diff, 0, ctx)
                            self.assertEqual(fr, 1, f"Black pawn double-advance not from rank 7 in {ctx}")

                # Knight geometry
                if piece in ('N', 'n'):
                    self.assertEqual(
                        {abs(tr - fr), abs(tc - fc)}, {1, 2},
                        f"Invalid knight move in {ctx}",
                    )

                # Bishop geometry
                if piece in ('B', 'b'):
                    self.assertEqual(
                        abs(tr - fr), abs(tc - fc),
                        f"Bishop must move diagonally in {ctx}",
                    )


class AIMoveTest(TestCase):
    """Test the /api/ai-move/ endpoint."""

    def setUp(self):
        self.client.get('/')
        self.engine_patcher = mock.patch.object(ChessGame, '_call_engine')
        self.mock_engine = self.engine_patcher.start()
        # Mock engine to return STATUS ok if checked, andBESTMOVE coordinates 
        self.mock_engine.side_effect = lambda cmd: "BESTMOVE 6 4 4 4" if cmd.startswith("BEST") else ("STATUS ok" if cmd.startswith("STATUS") else "PROMOTE")

        self.validate_patcher = mock.patch.object(ChessGame, 'validate_move')
        self.mock_validate = self.validate_patcher.start()
        self.mock_validate.return_value = (True, "Mock validate AI move")

    def tearDown(self):
        self.engine_patcher.stop()
        self.validate_patcher.stop()

    def test_ai_requires_ai_mode(self):
        r = self.client.post('/api/ai-move/', content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['valid'])

    def test_ai_makes_move(self):
        self.client.post('/api/new-game/', data=json.dumps({'mode': 'ai'}), content_type='application/json')
        
        r = self.client.post('/api/ai-move/', content_type='application/json')
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['current_turn'], 'black')
        self.assertEqual(data['ai_move']['from_row'], 6)
        self.assertEqual(data['ai_move']['to_row'], 4)
