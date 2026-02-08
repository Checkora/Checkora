"""Checkora Game Manager.

Manages chess game state and coordinates with the C++ engine for move
validation.  When the compiled engine binary is unavailable the module
falls back to an equivalent pure-Python implementation so the platform
always remains functional.
"""

import os
import subprocess

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

    def serialize_board(self):
        """Flatten the 2-D board into a 64-char string for the C++ engine."""
        return ''.join(c if c else '.' for row in self.board for c in row)

    def to_dict(self):
        """Serialise state for Django session storage."""
        return {
            'board': self.board,
            'current_turn': self.current_turn,
            'move_history': self.move_history,
            'captured': self.captured,
        }

    @classmethod
    def from_dict(cls, data):
        """Restore a game from a session dictionary."""
        game = cls.__new__(cls)
        game.board = data['board']
        game.current_turn = data['current_turn']
        game.move_history = data.get('move_history', [])
        game.captured = data.get('captured', {'white': [], 'black': []})
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
        """Validate a proposed move.  Returns ``(is_valid, message)``."""
        board_str = self.serialize_board()
        cmd = f"VALIDATE {board_str} {self.current_turn} {fr} {fc} {tr} {tc}"
        resp = self._call_engine(cmd)

        if resp is not None:
            if resp.startswith("VALID"):
                return True, "Valid move."
            reason = resp[8:] if len(resp) > 8 else "Invalid move."
            return False, reason

        # Python fallback when C++ binary is absent
        return self._validate_py(fr, fc, tr, tc)

    def make_move(self, fr, fc, tr, tc):
        """Attempt a move.  Returns ``(success, message, captured_piece)``."""

        piece = self.board[fr][fc]
        captured = self.board[tr][tc]

        # Execute
        self.board[tr][tc] = piece
        self.board[fr][fc] = None

        # Track capture
        if captured:
            self.captured[self.current_turn].append(captured)

        # Record move
        notation = self._notation(fr, fc, tr, tc, piece, captured)
        self.move_history.append({
            'notation': notation,
            'piece': piece,
            'from': [fr, fc],
            'to': [tr, tc],
            'captured': captured,
            'color': self.current_turn,
        })

        # Switch turn
        self.current_turn = (
            'black' if self.current_turn == 'white' else 'white'
        )
        return True, notation, captured

    def get_valid_moves(self, row, col):
        """Return every legal destination for the piece at *(row, col)*."""
        board_str = self.serialize_board()
        cmd = f"MOVES {board_str} {self.current_turn} {row} {col}"
        resp = self._call_engine(cmd)

        if resp is not None and resp.startswith("MOVES"):
            parts = resp.split()[1:]
            moves = []
            for i in range(0, len(parts) - 2, 3):
                moves.append({
                    'row': int(parts[i]),
                    'col': int(parts[i + 1]),
                    'is_capture': bool(int(parts[i + 2])),
                })
            return moves

        # Python fallback
        return self._valid_moves_py(row, col)

    # ------------------------------------------------------------------
    #  Notation helper
    # ------------------------------------------------------------------

    def _notation(self, fr, fc, tr, tc, piece, captured):
        """Generate algebraic-style notation for a move."""
        to_sq = f"{self.FILES[tc]}{8 - tr}"
        t = piece.lower()
        if t == 'p':
            return f"{self.FILES[fc]}x{to_sq}" if captured else to_sq
        sym = t.upper()
        cap = 'x' if captured else ''
        return f"{sym}{cap}{to_sq}"

    # ------------------------------------------------------------------
    #  Pure-Python validation fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _color(piece):
        """Return ``'white'``, ``'black'``, or ``None``."""
        if not piece:
            return None
        return 'white' if piece.isupper() else 'black'

    def _validate_py(self, fr, fc, tr, tc):
        """Full move validation in pure Python."""
        if not all(0 <= v < 8 for v in (fr, fc, tr, tc)):
            return False, "Out of bounds."

        piece = self.board[fr][fc]
        if not piece:
            return False, "No piece on source square."
        if self._color(piece) != self.current_turn:
            return False, "Not your turn."
        if fr == tr and fc == tc:
            return False, "Must move to a different square."

        target = self.board[tr][tc]
        if target and self._color(target) == self._color(piece):
            return False, "Cannot capture your own piece."

        t = piece.lower()
        ok = False
        if t == 'p':
            ok = self._pawn(self._color(piece), fr, fc, tr, tc)
        elif t == 'r':
            ok = self._rook(fr, fc, tr, tc)
        elif t == 'n':
            ok = self._knight(fr, fc, tr, tc)
        elif t == 'b':
            ok = self._bishop(fr, fc, tr, tc)
        elif t == 'q':
            ok = self._rook(fr, fc, tr, tc) or self._bishop(fr, fc, tr, tc)
        elif t == 'k':
            ok = abs(tr - fr) <= 1 and abs(tc - fc) <= 1

        if ok:
            return True, "Valid move."
        return False, "Illegal move for this piece."

    def _valid_moves_py(self, row, col):
        """Enumerate legal destinations in pure Python."""
        piece = self.board[row][col]
        if not piece or self._color(piece) != self.current_turn:
            return []
        moves = []
        for tr in range(8):
            for tc in range(8):
                ok, _ = self._validate_py(row, col, tr, tc)
                if ok:
                    moves.append({
                        'row': tr,
                        'col': tc,
                        'is_capture': self.board[tr][tc] is not None,
                    })
        return moves

    # -- Piece rules (Python) ------------------------------------------

    def _pawn(self, color, fr, fc, tr, tc):
        d = -1 if color == 'white' else 1
        start = 6 if color == 'white' else 1
        dr, dc = tr - fr, tc - fc

        if dc == 0 and dr == d and not self.board[tr][tc]:
            return True
        if dc == 0 and dr == 2 * d and fr == start:
            if not self.board[fr + d][fc] and not self.board[tr][tc]:
                return True
        if abs(dc) == 1 and dr == d and self.board[tr][tc]:
            return True
        return False

    def _rook(self, fr, fc, tr, tc):
        if fr != tr and fc != tc:
            return False
        return self._clear(fr, fc, tr, tc)

    def _knight(self, fr, fc, tr, tc):
        dr, dc = abs(tr - fr), abs(tc - fc)
        return (dr == 2 and dc == 1) or (dr == 1 and dc == 2)

    def _bishop(self, fr, fc, tr, tc):
        if abs(tr - fr) != abs(tc - fc):
            return False
        return self._clear(fr, fc, tr, tc)

    def _clear(self, fr, fc, tr, tc):
        """Return True when the sliding path has no obstructions."""
        dr = 0 if tr == fr else (1 if tr > fr else -1)
        dc = 0 if tc == fc else (1 if tc > fc else -1)
        r, c = fr + dr, fc + dc
        while (r, c) != (tr, tc):
            if self.board[r][c]:
                return False
            r += dr
            c += dc
        return True
