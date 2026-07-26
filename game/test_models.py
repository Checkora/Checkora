from django.test import TestCase
from django.core.exceptions import ValidationError
from game.models import validate_game_state, GameRecord
from game.engine import ChessGame
import time

class GameStateValidationTest(TestCase):
    def setUp(self):
        self.valid_board = [
            ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
            ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
            [None] * 8,
            [None] * 8,
            [None] * 8,
            [None] * 8,
            ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
            ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
        ]

    def test_valid_game_state(self):
        valid_state = {
            'board': self.valid_board,
            'current_turn': 'white',
            'white_time': 600,
            'black_time': 600,
            'last_ts': time.time()
        }
        # Should not raise any exception
        validate_game_state(valid_state)

    def test_none_value(self):
        # Should not raise exception
        validate_game_state(None)

    def test_invalid_falsy_values(self):
        for val in [[], "", 0]:
            with self.assertRaises(ValidationError) as ctx:
                validate_game_state(val)
            self.assertEqual(ctx.exception.message, "game_state must be a dictionary")
            
        with self.assertRaises(ValidationError) as ctx:
            validate_game_state({})
        self.assertIn("missing required keys", ctx.exception.message)

    def test_missing_required_keys(self):
        invalid_state = {
            'board': self.valid_board,
            'current_turn': 'white'
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_game_state(invalid_state)
        self.assertIn("missing required keys", ctx.exception.message)

    def test_invalid_turn(self):
        invalid_state = {
            'board': self.valid_board,
            'current_turn': 'blue',
            'white_time': 600,
            'black_time': 600,
            'last_ts': time.time()
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_game_state(invalid_state)
        self.assertEqual(ctx.exception.message, "current_turn must be 'white' or 'black'")

    def test_invalid_board_shape(self):
        invalid_board = self.valid_board.copy()
        invalid_board.pop() # Now it's 7x8
        
        invalid_state = {
            'board': invalid_board,
            'current_turn': 'white',
            'white_time': 600,
            'black_time': 600,
            'last_ts': time.time()
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_game_state(invalid_state)
        self.assertEqual(ctx.exception.message, "board must be an 8x8 array")


class GameRecordValidationTest(TestCase):
    def test_game_record_blank_pgn_allowed(self):
        record = GameRecord.objects.create(
            session_key="test_session_123",
            white_label="White",
            black_label="Black",
            result="0-1",
            termination="resignation",
            pgn=""
        )
        self.assertEqual(record.pgn, "")

    def test_generate_pgn_empty_history(self):
        game = ChessGame()
        game.game_status = "resignation"
        game.current_turn = "white"
        pgn = game.generate_pgn(white_name="Player1", black_name="Player2")
        self.assertIn('[Event "Checkora Match"]', pgn)
        self.assertIn('[White "Player1"]', pgn)
        self.assertIn('[Black "Player2"]', pgn)
        self.assertIn('[Result "0-1"]', pgn)
        self.assertTrue(pgn.endswith("0-1"))

