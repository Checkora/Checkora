"""Checkora Game Manager.

Manages chess game state and coordinates with the C++ engine for move
validation. Includes a persistent DP table (valid_moves_cache) that 
updates on-demand to avoid redundant brute-force calculations while
ensuring 100% accuracy.
"""

import os
import subprocess
import json
import time

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
        self.white_time = 10 * 60  # 10 minutes
        self.black_time = 10 * 60
        self.last_ts = time.time()
        self.paused = False

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
            'valid_moves_cache': serializable_cache,
            'white_time': self.white_time,
            'black_time': self.black_time,
            'last_ts': self.last_ts,
            'paused': self.paused
        }

    @classmethod
    def from_dict(cls, data):
        """Restore a game and its DP cache from a session dictionary."""
        game = cls.__new__(cls)
        game.board = data['board']
        game.current_turn = data['current_turn']
        game.move_history = data.get('move_history', [])
        game.captured = data.get('captured', {'white': [], 'black': []})
        game.paused = data.get('paused', False)
        game.white_time = data['white_time']
        game.black_time = data['black_time']
        game.last_ts = data['last_ts']

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

    def make_move(self, fr, fc, tr, tc, promotion_piece=None):
        """Execute move and invalidate cache to ensure fresh calculations."""
        piece = self.board[fr][fc]
        captured = self.board[tr][tc]

        # Pawn promotion: delegate to C++ engine for validation + board update
        promoted = False
        if self._is_promotion(piece, tr):
            choice = (promotion_piece or 'q').lower()
            new_board = self._call_engine_promote(fr, fc, tr, tc, choice)
            if new_board:
                # C++ returned the updated board — apply it directly
                self.board = self._parse_board64(new_board)
                promoted = True
            else:
                # Fallback: apply promotion in Python
                self.board[tr][tc] = self._promote(piece, promotion_piece)
                self.board[fr][fc] = None
                promoted = True
        else:
            self.board[tr][tc] = piece
            self.board[fr][fc] = None

        if captured:
            self.captured[self.current_turn].append(captured)

        notation = self._notation(fr, fc, tr, tc, piece, captured)
        if promoted:
            notation += '=' + (self.board[tr][tc] or 'Q').upper()
        self.move_history.append({
            'notation': notation,
            'piece': piece,
            'from': [fr, fc],
            'to': [tr, tc],
            'captured': captured,
            'color': self.current_turn,
            'promoted_to': self.board[tr][tc] if promoted else None,
        })

        # Invalidate DP cache because board state has changed
        self.valid_moves_cache = {}

        # Switch turn
        self.current_turn = 'black' if self.current_turn == 'white' else 'white'

        self.update_clock()

        if self.white_time == 0:
            return False, "White ran out of time", None
        if self.black_time == 0:
            return False, "Black ran out of time", None
        
        self.last_ts = time.time()
        
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
            # C++ now returns 4 fields per move: row col is_capture is_promotion
            for i in range(0, len(parts), 4):
                moves.append({
                    'row': int(parts[i]),
                    'col': int(parts[i+1]),
                    'is_capture': bool(int(parts[i+2])),
                    'is_promotion': bool(int(parts[i+3])),
                })
        return moves

    # ------------------------------------------------------------------
    #  C++ engine promotion
    # ------------------------------------------------------------------

    def _call_engine_promote(self, fr, fc, tr, tc, choice):
        """Ask the C++ engine to validate and apply a promotion move.

        Returns the new 64-char board string on success, or None.
        """
        board_str = self.serialize_board()
        cmd = f"PROMOTE {board_str} {self.current_turn} {fr} {fc} {tr} {tc} {choice}"
        resp = self._call_engine(cmd)
        if resp and resp.startswith("PROMOTE"):
            return resp.split()[1]
        return None

    @staticmethod
    def _parse_board64(board_str):
        """Convert a 64-char string back into an 8x8 list."""
        result = []
        for r in range(8):
            row = []
            for c in range(8):
                ch = board_str[r * 8 + c]
                row.append(None if ch == '.' else ch)
            result.append(row)
        return result

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_promotion(piece, to_row):
        """Return True when a pawn reaches the opponent's back rank."""
        if not piece:
            return False
        return (piece == 'P' and to_row == 0) or (piece == 'p' and to_row == 7)

    @staticmethod
    def _promote(piece, choice=None):
        """Return the promoted piece character (defaults to queen)."""
        valid = {'q', 'r', 'b', 'n'}
        choice = (choice or 'q').lower()
        if choice not in valid:
            choice = 'q'
        return choice.upper() if piece.isupper() else choice.lower()

    @staticmethod
    def is_promotion_move(board, fr, fc, tr):
        """Public helper: check if a planned move would trigger promotion."""
        piece = board[fr][fc]
        if not piece:
            return False
        return (piece == 'P' and tr == 0) or (piece == 'p' and tr == 7)

    def _notation(self, fr, fc, tr, tc, piece, captured):
        to_sq = f"{self.FILES[fc]}{8 - fr} -> {self.FILES[tc]}{8 - tr}"
        return to_sq

    @staticmethod
    def _color(piece):
        if not piece: return None
        return 'white' if piece.isupper() else 'black'
    
    def update_clock(self):
        if self.paused:
            self.last_ts = time.time()
            return

        now = time.time()
        elapsed = int(now - self.last_ts)

        if elapsed > 0:
            if self.current_turn == 'white':
                self.white_time = max(0, self.white_time - elapsed)
            else:
                self.black_time = max(0, self.black_time - elapsed)

        self.last_ts = now

