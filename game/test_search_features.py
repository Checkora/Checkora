import sys
import os
import time
from unittest import mock
from django.test import SimpleTestCase
from game.engine import ChessGame

# Add engine directory to path to import main.py directly
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engine'))
import main as python_engine

class SearchFeaturesTest(SimpleTestCase):
    """Test suite for transposition table hashing, iterative deepening, timeout behavior, and metrics."""

    def setUp(self):
        # Reset python engine globals
        python_engine.transposition_table.clear()
        python_engine.W_K_CASTLE = True
        python_engine.W_Q_CASTLE = True
        python_engine.B_K_CASTLE = True
        python_engine.B_Q_CASTLE = True
        python_engine.EN_PASSANT_R = -1
        python_engine.EN_PASSANT_C = -1
        python_engine.BOARD = [['.'] * 8 for _ in range(8)]

    def test_zobrist_hash_determinism_and_uniqueness(self):
        """Zobrist hashes must be deterministic and change on state updates."""
        python_engine.BOARD[0][0] = 'R'
        python_engine.BOARD[7][4] = 'K'
        
        # 1. Determinism
        hash1 = python_engine.compute_hash('white')
        hash2 = python_engine.compute_hash('white')
        self.assertEqual(hash1, hash2)

        # 2. Side-to-move changes hash
        hash_black = python_engine.compute_hash('black')
        self.assertNotEqual(hash1, hash_black)

        # 3. Castling rights change hash
        python_engine.W_K_CASTLE = False
        hash_no_wk = python_engine.compute_hash('white')
        self.assertNotEqual(hash1, hash_no_wk)
        python_engine.W_K_CASTLE = True  # Restore

        # 4. En-passant square changes hash
        python_engine.EN_PASSANT_C = 4
        python_engine.EN_PASSANT_R = 2
        hash_ep = python_engine.compute_hash('white')
        self.assertNotEqual(hash1, hash_ep)
        python_engine.EN_PASSANT_C = -1  # Restore

        # 5. Piece placement changes hash
        python_engine.BOARD[0][0] = '.'
        hash_no_rook = python_engine.compute_hash('white')
        self.assertNotEqual(hash1, hash_no_rook)

    def test_timeout_behavior_returns_move(self):
        """Timeout should return the best move from the last completed depth instead of crashing."""
        # Set up a complex position that requires time
        # Standard starting position
        start_board = (
            "rnbqkbnr"
            "pppppppp"
            "........"
            "........"
            "........"
            "........"
            "PPPPPPPP"
            "RNBQKBNR"
        )
        python_engine.load_board(start_board)
        python_engine.load_castling_rights("KQkq")
        python_engine.load_en_passant(-1, -1)

        # Run search with extremely low time budget (1ms) and high depth
        # We redirect stdout to capture the output of handle_bestmove
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            python_engine.handle_bestmove('white', 6, time_limit_ms=1)
            output = sys.stdout.getvalue().strip()
        finally:
            sys.stdout = old_stdout

        self.assertTrue(output.startswith("BESTMOVE"))
        self.assertIn("STATUS timeout", output)
        self.assertIn("ENGINE python", output)

    def test_completed_search_status(self):
        """Search should report completed status when it completes within the budget."""
        # Shallow search depth 1 on empty/simple board
        python_engine.BOARD[7][4] = 'K'
        python_engine.BOARD[7][0] = 'R'
        python_engine.BOARD[0][4] = 'k'
        python_engine.load_castling_rights("-")
        python_engine.load_en_passant(-1, -1)

        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            python_engine.handle_bestmove('white', 1, time_limit_ms=5000)
            output = sys.stdout.getvalue().strip()
        finally:
            sys.stdout = old_stdout

        self.assertTrue(output.startswith("BESTMOVE"))
        self.assertIn("STATUS completed", output)
        self.assertIn("DEPTH 1", output)

    def test_transposition_table_cache_hits(self):
        """Transposition table must correctly cache evaluations and produce hits on repeated positions."""
        # We run a search to depth 4 on a simple board which should trigger hits
        python_engine.BOARD[7][4] = 'K'
        python_engine.BOARD[7][0] = 'R'
        python_engine.BOARD[0][4] = 'k'
        python_engine.BOARD[0][0] = 'r'
        python_engine.load_castling_rights("-")
        
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            python_engine.handle_bestmove('white', 4, time_limit_ms=5000)
            output = sys.stdout.getvalue().strip()
        finally:
            sys.stdout = old_stdout

        # Check for TTHITS in metrics
        parts = output.split()
        self.assertIn("TTHITS", parts)
        tthits_val = -1
        for i, part in enumerate(parts):
            if part == "TTHITS":
                tthits_val = int(parts[i+1])
                break
        self.assertGreater(tthits_val, 0)

    def test_wrapper_metrics_parsing(self):
        """Django wrapper ChessGame must correctly parse new metrics from engine responses."""
        game = ChessGame()
        
        # Mock engine call to return a mock response with all metrics
        mock_response = (
            "BESTMOVE 6 4 4 4 EVAL 30 ALTS 6 2 4 2 -10 "
            "DEPTH 4 NODES 1234 TTHITS 56 TIME 120 ENGINE cpp STATUS completed"
        )
        with mock.patch.object(game, '_call_engine', return_value=mock_response):
            move_data = game.get_ai_move(depth=4)

        self.assertIsNotNone(move_data)
        self.assertEqual(move_data['from_row'], 6)
        self.assertEqual(move_data['from_col'], 4)
        self.assertEqual(move_data['to_row'], 4)
        self.assertEqual(move_data['to_col'], 4)
        self.assertEqual(move_data['eval'], 30)
        self.assertEqual(move_data['depth'], 4)
        self.assertEqual(move_data['nodes'], 1234)
        self.assertEqual(move_data['tthits'], 56)
        self.assertEqual(move_data['time'], 120)
        self.assertEqual(move_data['engine'], 'cpp')
        self.assertEqual(move_data['status'], 'completed')

    def test_opening_book_compatibility(self):
        """AI must use the opening book first before calling minimax search."""
        game = ChessGame()
        # Initialize at starting position
        game.board = [row[:] for row in ChessGame.INITIAL_BOARD]
        game.current_turn = 'white'
        game.castling_rights = {'w_k': True, 'w_q': True, 'b_k': True, 'b_q': True}
        game.en_passant_target = None
        game.move_history = []

        # Mock validate_move to return True so the book move is verified without calling the engine
        with mock.patch.object(game, 'validate_move', return_value=(True, "Valid")):
            with mock.patch.object(game, '_call_engine') as mock_call:
                move = game.get_ai_move()
                mock_call.assert_not_called()
                self.assertIsNotNone(move)
                self.assertIn('from_row', move)
                self.assertIn('to_row', move)
