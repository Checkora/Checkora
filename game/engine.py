"""Checkora Game Manager.

Manages chess game state and coordinates with the C++ engine for move
validation. Includes a persistent DP table (valid_moves_cache) that 
updates on-demand to avoid redundant brute-force calculations while
ensuring 100% accuracy.
"""

import os
import subprocess
import json

from django.conf import settings


class ChessGame:
    """Manage a single chess game: state, validation, and engine communication."""

    ENGINE_PATH = os.path.join(settings.BASE_DIR, 'game', 'engine', 'main.exe')
    FILES = 'abcdefgh'

    INITIAL_BOARD = [
        ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
        ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
        [None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None],
        ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
        ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R'],
    ]

    # ------------------------------------------------------------------
    #  Construction / serialization
    # ------------------------------------------------------------------

    def __init__(self):
        self.board = [row[:] for row in self.INITIAL_BOARD]
        self.current_turn = 'white'
        self.move_history = []
        self.captured = {'white': [], 'black': []}
        # DP Table: {(row, col): [list of moves]}
        self.valid_moves_cache = {}

    def serialize_board(self):
        """Flatten the 2-D board into a 64-char string for the C++ engine."""
        return ''.join(c if c else '.' for row in self.board for c in row)

    def to_dict(self):
        """Serialise state for Django session storage, including the DP cache."""
        serializable_cache = {f"{r},{c}": v for (r, c), v in self.valid_moves_cache.items()}
        return {
            'board': self.board,
            'current_turn': self.current_turn,
            'move_history': self.move_history,
            'captured': self.captured,
            'valid_moves_cache': serializable_cache
        }

    @classmethod
    def from_dict(cls, data):
        """Restore a game and its DP cache from a session dictionary."""
        game = cls.__new__(cls)
        game.board = data['board']
        game.current_turn = data['current_turn']
        game.move_history = data.get('move_history', [])
        game.captured = data.get('captured', {'white': [], 'black': []})
        
        cache_data = data.get('valid_moves_cache', {})
        game.valid_moves_cache = {}
        for k, v in cache_data.items():
            r, c = map(int, k.split(','))
            game.valid_moves_cache[(r, c)] = v
        return game

    # ------------------------------------------------------------------
    #  C++ engine communication
    # ------------------------------------------------------------------

    def _call_engine(self, command):
        """Run the C++ engine with *command* on stdin and return stdout."""
        if not os.path.exists(self.ENGINE_PATH):
            return None
        try:
            proc = subprocess.Popen(
                [self.ENGINE_PATH],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, _ = proc.communicate(input=command, timeout=5)
            return stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            return None

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def validate_move(self, fr, fc, tr, tc):
        """Check if move is in our DP cache."""
        moves = self.get_valid_moves(fr, fc)
        for m in moves:
            if m['row'] == tr and m['col'] == tc:
                return True, "Valid move."
        return False, "Illegal move."

    def make_move(self, fr, fc, tr, tc):
        """Execute move and invalidate cache to ensure fresh calculations."""
        piece = self.board[fr][fc]
        captured = self.board[tr][tc]

        self.board[tr][tc] = piece
        self.board[fr][fc] = None

        if captured:
            self.captured[self.current_turn].append(captured)

        notation = self._notation(fr, fc, tr, tc, piece, captured)
        self.move_history.append({
            'notation': notation,
            'piece': piece,
            'from': [fr, fc],
            'to': [tr, tc],
            'captured': captured,
            'color': self.current_turn,
        })

        # Invalidate DP cache because board state has changed
        self.valid_moves_cache = {}

        # Switch turn
        self.current_turn = 'black' if self.current_turn == 'white' else 'white'
        
        return True, notation, captured

    def get_valid_moves(self, row, col):
        """Return legal moves from DP cache (fetches from engine if missing)."""
        piece = self.board[row][col]
        if not piece or self._color(piece) != self.current_turn:
            return []

        # On-Demand Caching: If not in DP, compute once and store
        if (row, col) not in self.valid_moves_cache:
            self.valid_moves_cache[(row, col)] = self._get_engine_moves(row, col)
            
        return self.valid_moves_cache.get((row, col), [])

    def _get_engine_moves(self, row, col):
        """Internal helper to fetch piece moves from the C++ binary."""
        board_str = self.serialize_board()
        cmd = f"MOVES {board_str} {self.current_turn} {row} {col}"
        resp = self._call_engine(cmd)
        
        moves = []
        if resp and resp.startswith("MOVES"):
            parts = resp.split()[1:]
            for i in range(0, len(parts), 3):
                moves.append({
                    'row': int(parts[i]),
                    'col': int(parts[i+1]),
                    'is_capture': bool(int(parts[i+2]))
                })
        return moves

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _notation(self, fr, fc, tr, tc, piece, captured):
        to_sq = f"{self.FILES[fc]}{8 - fr} -> {self.FILES[tc]}{8 - tr}"
        return to_sq

    @staticmethod
    def _color(piece):
        if not piece: return None
        return 'white' if piece.isupper() else 'black'