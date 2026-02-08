"""Tests for the Checkora chess engine and API endpoints."""

import json

from django.test import TestCase


class BoardViewTest(TestCase):
    """The board page should load and initialise a session."""

    def test_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkora')


class MoveValidationTest(TestCase):
    """Test move validation through the /api/move/ endpoint."""

    def setUp(self):
        self.client.get('/')  # initialise game session

    def _move(self, fr, fc, tr, tc):
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
        """e2-e3 is valid."""
        r = self._move(6, 4, 5, 4)
        self.assertTrue(r.json()['valid'])

    def test_pawn_double_advance(self):
        """e2-e4 is valid from the starting rank."""
        r = self._move(6, 4, 4, 4)
        self.assertTrue(r.json()['valid'])

    def test_pawn_triple_advance_invalid(self):
        """e2-e5 (three squares) is never valid."""
        r = self._move(6, 4, 3, 4)
        self.assertFalse(r.json()['valid'])

    # -- Turn enforcement -------------------------------------------

    def test_wrong_turn(self):
        """Black cannot move first."""
        r = self._move(1, 4, 3, 4)
        self.assertFalse(r.json()['valid'])

    def test_turn_alternation(self):
        """After white moves the turn switches to black."""
        r = self._move(6, 4, 4, 4)  # e4
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['current_turn'], 'black')

    # -- Knight -----------------------------------------------------

    def test_knight_valid(self):
        """b1-c3 (L-shape) is valid."""
        r = self._move(7, 1, 5, 2)
        self.assertTrue(r.json()['valid'])

    def test_knight_invalid(self):
        """b1-b3 (straight line) is not an L-shape."""
        r = self._move(7, 1, 5, 1)
        self.assertFalse(r.json()['valid'])

    # -- Capture rules ----------------------------------------------

    def test_capture_own_piece_blocked(self):
        """Rook a1 cannot land on own pawn a2."""
        r = self._move(7, 0, 6, 0)
        self.assertFalse(r.json()['valid'])

    # -- Bishop blocked by own pawn ---------------------------------

    def test_bishop_blocked(self):
        """c1-bishop cannot jump over d2-pawn."""
        r = self._move(7, 2, 5, 4)
        self.assertFalse(r.json()['valid'])

    # -- Multi-move sequence ----------------------------------------

    def test_three_move_sequence(self):
        """Play e4, e5, Nf3 — all valid."""
        self.assertTrue(self._move(6, 4, 4, 4).json()['valid'])  # e4
        self.assertTrue(self._move(1, 4, 3, 4).json()['valid'])  # e5
        self.assertTrue(self._move(7, 6, 5, 5).json()['valid'])  # Nf3

    def test_capture_tracked(self):
        """Captured pieces should appear in the response."""
        self._move(6, 4, 4, 4)  # e4
        self._move(1, 3, 3, 3)  # d5
        r = self._move(4, 4, 3, 3)  # exd5
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertEqual(data['captured'], 'p')


class ValidMovesTest(TestCase):
    """Test the /api/valid-moves/ endpoint."""

    def setUp(self):
        self.client.get('/')

    def test_pawn_initial_has_two_moves(self):
        """e2-pawn can go to e3 or e4."""
        r = self.client.get('/api/valid-moves/?row=6&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 2)

    def test_knight_initial_has_two_moves(self):
        """b1-knight can go to a3 or c3."""
        r = self.client.get('/api/valid-moves/?row=7&col=1')
        self.assertEqual(len(r.json()['valid_moves']), 2)

    def test_empty_square_no_moves(self):
        """An empty square returns zero moves."""
        r = self.client.get('/api/valid-moves/?row=4&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_opponent_piece_no_moves(self):
        """Black's piece should yield nothing on white's turn."""
        r = self.client.get('/api/valid-moves/?row=1&col=4')
        self.assertEqual(len(r.json()['valid_moves']), 0)

    def test_rook_blocked_at_start(self):
        """a1-rook has zero moves — surrounded by own pieces."""
        r = self.client.get('/api/valid-moves/?row=7&col=0')
        self.assertEqual(len(r.json()['valid_moves']), 0)


class NewGameTest(TestCase):
    """Test the /api/new-game/ endpoint."""

    def setUp(self):
        self.client.get('/')

    def test_reset(self):
        """After making a move, new-game restores the initial position."""
        self.client.post(
            '/api/move/',
            data=json.dumps({
                'from_row': 6, 'from_col': 4,
                'to_row': 4, 'to_col': 4,
            }),
            content_type='application/json',
        )
        r = self.client.post('/api/new-game/', content_type='application/json')
        data = r.json()
        self.assertEqual(data['current_turn'], 'white')
        self.assertEqual(len(data['move_history']), 0)
