"""Checkora Game Manager.

Manages chess game state and coordinates with the C++ engine for move
validation. Includes a persistent DP table (valid_moves_cache) that
updates on-demand to avoid redundant brute-force calculations while
ensuring 100% accuracy.

Opening Book
------------
During the first few moves the AI consults a pre-built opening book
(``game/engine/opening_book.json``) instead of running the expensive
minimax search.  Keys are minimal FEN strings (board layout + side to
move + castling rights, **no** en-passant / half-move / full-move
counters) and values are lists of ``[from_row, from_col, to_row,
to_col]`` move coordinates.  When multiple book moves are available one
is chosen at random to add variety.
"""

import os
import random
import subprocess
import json
import sys
import time

from django.conf import settings


class ChessGame:
    """Manage a single chess game: state, validation, and engine communication."""

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    ENGINE_DIR = os.path.join(CURRENT_DIR, 'engine')
    ENGINE_CANDIDATES = (
        [
            os.path.join(ENGINE_DIR, 'main.exe'),
            os.path.join(ENGINE_DIR, 'main'),
            os.path.join(ENGINE_DIR, 'main.py'),
        ]
        if os.name == 'nt' else
        [
            os.path.join(ENGINE_DIR, 'main'),
            os.path.join(ENGINE_DIR, 'main.exe'),
            os.path.join(ENGINE_DIR, 'main.py'),
        ]
    )
    FILES = 'abcdefgh'

    # Path to the JSON opening book
    OPENING_BOOK_PATH = os.path.join(ENGINE_DIR, 'opening_book.json')

    # Class-level cache so the file is read only once per process
    _opening_book: dict | None = None

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
        self.mode = 'pvp'
        self.player_color = 'white'
        self.castling_rights = {
            'w_k': True, 'w_q': True,
            'b_k': True, 'b_q': True
        }
        self.en_passant_target = None  # (row, col) of the square a pawn can capture en passant

    def serialize_board(self):
        """Flatten the 2-D board into a 64-char string for the C++ engine."""
        return ''.join(c if c else '.' for row in self.board for c in row)

    def to_dict(self):
        """Serialise state for Django session storage. DP cache is intentionally excluded to save cookie space."""
        return {
            'board': self.board,
            'current_turn': self.current_turn,
            'move_history': self.move_history,
            'captured': self.captured,
            'white_time': self.white_time,
            'black_time': self.black_time,
            'last_ts': self.last_ts,
            'paused': self.paused,
            'mode': self.mode,
            'castling_rights': self.castling_rights,
            'en_passant_target': self.en_passant_target,
            'player_color': self.player_color,
        }

    @classmethod
    def from_dict(cls, data):
        """Restore a game from a session dictionary."""
        game = cls.__new__(cls)
        game.board = data['board']
        game.current_turn = data['current_turn']
        game.move_history = data.get('move_history', [])
        game.captured = data.get('captured', {'white': [], 'black': []})
        game.paused = data.get('paused', False)
        game.white_time = data['white_time']
        game.black_time = data['black_time']
        game.last_ts = data['last_ts']
        game.mode = data.get('mode', 'pvp')
        game.player_color = data.get('player_color', 'white')
        game.castling_rights = data.get('castling_rights', {'w_k': True, 'w_q': True, 'b_k': True, 'b_q': True})
        game.en_passant_target = data.get('en_passant_target', None)

        game.valid_moves_cache = {}
        return game

    # ------------------------------------------------------------------
    #  C++ engine communication
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_engine_path(cls):
        """Return the first available engine entrypoint for this platform."""
        for path in cls.ENGINE_CANDIDATES:
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def _build_engine_command(engine_path):
        """Build the subprocess command for either a binary or Python script."""
        if engine_path.endswith('.py'):
            return [sys.executable, engine_path]
        return [engine_path]

    def _call_engine(self, command):
        """Run the C++ engine with *command* on stdin and return stdout."""
        engine_path = self._resolve_engine_path()
        if not engine_path:
            return None
        try:
            proc = subprocess.Popen(
                self._build_engine_command(engine_path),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, _ = proc.communicate(input=command, timeout=5)
            return stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            return None

    def _count_active_pieces(self):
        """Helper to count the total pieces currently alive on the board."""
        return sum(1 for row in self.board for piece in row if piece is not None)

    def _get_ai_search_depth(self):
        """Return appropriate search depth based on which engine is available and game phase."""
        engine_path = self._resolve_engine_path()
        if not engine_path:
            return self.AI_SEARCH_DEPTH_PYTHON
        # C++ binary is much faster than Python, use deeper search
        if engine_path.endswith('.py'):
            return self.AI_SEARCH_DEPTH_PYTHON
            
        piece_count = self._count_active_pieces()
        
        # Adaptive Search Depth for C++ engine in endgame
        if piece_count <= 6:
            return self.AI_SEARCH_DEPTH_CPP + 2
        elif piece_count <= 12:
            return self.AI_SEARCH_DEPTH_CPP + 1
            
        return self.AI_SEARCH_DEPTH_CPP

    def serialize_castling_rights(self):
        """Serialize castling rights to a string for the C++ engine."""
        rights = ''
        if self.castling_rights['w_k']: rights += 'K'
        if self.castling_rights['w_q']: rights += 'Q'
        if self.castling_rights['b_k']: rights += 'k'
        if self.castling_rights['b_q']: rights += 'q'
        return rights if rights else '-'

    def _serialize_ep(self):
        """Serialize en passant target for the C++ engine."""
        if not self.en_passant_target:
            return "-1 -1"
        return f"{self.en_passant_target[0]} {self.en_passant_target[1]}"

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
        if not piece or self._color(piece) != self.current_turn:
            return False, "Not your piece or empty square", None, 'active'

        is_valid, reason = self.validate_move(fr, fc, tr, tc)
        if not is_valid:
            return False, reason, None, 'active'

        # Check timeout BEFORE mutating board state
        self.update_clock()
        if self.white_time == 0:
            return False, "White ran out of time", None, 'timeout'
        if self.black_time == 0:
            return False, "Black ran out of time", None, 'timeout'

        captured = self.board[tr][tc]
        board_before = self.serialize_board()
        rights_before = self.serialize_castling_rights()
        ep_before = self._serialize_ep()

        # Detect En Passant capture before moving piece
        if piece.lower() == 'p' and fc != tc and not captured:
            if self.en_passant_target and tr == self.en_passant_target[0] and tc == self.en_passant_target[1]:
                captured = 'p' if piece.isupper() else 'P' # The captured piece is of opposite color
                # In EP, the captured pawn is at (fr, tc)
                self.board[fr][tc] = None

        if piece == 'K':
            self.castling_rights['w_k'] = False
            self.castling_rights['w_q'] = False
        elif piece == 'k':
            self.castling_rights['b_k'] = False
            self.castling_rights['b_q'] = False
        elif piece == 'R':
            if fr == 7 and fc == 0: self.castling_rights['w_q'] = False
            elif fr == 7 and fc == 7: self.castling_rights['w_k'] = False
        elif piece == 'r':
            if fr == 0 and fc == 0: self.castling_rights['b_q'] = False
            elif fr == 0 and fc == 7: self.castling_rights['b_k'] = False

        if captured == 'R':
            if tr == 7 and tc == 0: self.castling_rights['w_q'] = False
            elif tr == 7 and tc == 7: self.castling_rights['w_k'] = False
        elif captured == 'r':
            if tr == 0 and tc == 0: self.castling_rights['b_q'] = False
            elif tr == 0 and tc == 7: self.castling_rights['b_k'] = False

        # Pawn promotion: delegate to C++ engine for validation + board update
        promoted = False
        if self._is_promotion(piece, tr):
            choice = (promotion_piece or 'q').lower()
            new_board = self._call_engine_promote(fr, fc, tr, tc, choice)
            if new_board:
                # C++ returned the updated board - apply it directly
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
            if piece.lower() == 'k' and abs(tc - fc) == 2:
                if tc == 6:
                    self.board[tr][5] = self.board[tr][7]
                    self.board[tr][7] = None
                elif tc == 2:
                    self.board[tr][3] = self.board[tr][0]
                    self.board[tr][0] = None

        # Update En Passant target for the NEXT turn
        if piece.lower() == 'p' and abs(tr - fr) == 2:
            self.en_passant_target = ((fr + tr) // 2, fc)
        else:
            self.en_passant_target = None

        if captured:
            self.captured[self.current_turn].append(captured)

        notation = self._notation(fr, fc, tr, tc, piece, captured, board_before, rights_before, ep_before)
        if promoted and '=' not in notation:
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

        self.last_ts = time.time()

        # Check for checkmate / stalemate / check
        game_status = self.check_game_status()
        
        return True, notation, captured, game_status

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
        rights_str = self.serialize_castling_rights()
        ep_str = self._serialize_ep()
        cmd = f"MOVES {board_str} {rights_str} {self.current_turn} {ep_str} {row} {col}"
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
        rights_str = self.serialize_castling_rights()
        ep_str = self._serialize_ep()
        cmd = f"PROMOTE {board_str} {rights_str} {self.current_turn} {ep_str} {fr} {fc} {tr} {tc} {choice}"
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

    def _notation(self, fr, fc, tr, tc, piece, captured, board_str=None, rights_str=None, ep_str=None):
        """Generate SAN notation via C++ engine if possible, else simplified fallback."""
        if board_str and rights_str:
            ep_str = ep_str or self._serialize_ep()
            cmd = f"NOTATION {board_str} {rights_str} {self.current_turn} {ep_str} {fr} {fc} {tr} {tc}"
            resp = self._call_engine(cmd)
            if resp and resp.startswith("NOTATION"):
                parts = resp.split()
                if len(parts) >= 2:
                    return parts[1]

        # Fallback: simplified notation (e.g., e4, Nf3, exd5)
        files = "abcdefgh"
        f_coord = f"{files[fc]}{8 - fr}"
        t_coord = f"{files[tc]}{8 - tr}"
        
        if not piece: return f"{f_coord} -> {t_coord}"
        
        type = piece.lower()
        if type == 'p':
            if fc != tc: return f"{files[fc]}x{t_coord}"
            return t_coord
        
        p_char = type.upper()
        if captured: return f"{p_char}x{t_coord}"
        return f"{p_char}{t_coord}"

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

    # ------------------------------------------------------------------
    #  Game status detection (check / checkmate / stalemate)
    # ------------------------------------------------------------------

    def check_game_status(self):
        """Ask the C++ engine for the game status of the current side.

        Returns one of: 'checkmate', 'stalemate', 'check', 'ok'.
        """
        board_str = self.serialize_board()
        rights_str = self.serialize_castling_rights()
        ep_str = self._serialize_ep()
        cmd = f"STATUS {board_str} {rights_str} {self.current_turn} {ep_str}"
        resp = self._call_engine(cmd)
        if resp and resp.startswith("STATUS"):
            status = resp.split()[1].lower()
            if status in ('checkmate', 'stalemate', 'draw', 'check', 'ok'):
                return status
        return 'ok'

    # ------------------------------------------------------------------
    #  AI -- Opening Book
    # ------------------------------------------------------------------

    @classmethod
    def _load_opening_book(cls) -> dict:
        """Load the opening book JSON from disk (cached after first load)."""
        if cls._opening_book is None:
            try:
                with open(cls.OPENING_BOOK_PATH, encoding='utf-8') as fh:
                    cls._opening_book = json.load(fh)
            except (OSError, json.JSONDecodeError):
                cls._opening_book = {}  # Graceful fallback: no book
        return cls._opening_book

    def generate_fen_key(self) -> str:
        """Build a minimal FEN key (board + side + castling, no counters).

        This matches the key format used in ``opening_book.json``.
        """
        # Piece-placement section
        fen_rows = []
        for row in self.board:
            empty = 0
            row_str = ''
            for piece in row:
                if piece is None:
                    empty += 1
                else:
                    if empty:
                        row_str += str(empty)
                        empty = 0
                    row_str += piece
            if empty:
                row_str += str(empty)
            fen_rows.append(row_str)
        placement = '/'.join(fen_rows)

        # Side to move
        side = 'w' if self.current_turn == 'white' else 'b'

        # Castling rights
        castling = self.serialize_castling_rights()  # already returns '-' if none

        return f"{placement} {side} {castling}"

    def get_opening_book_move(self) -> dict | None:
        """Return a random book move for the current position, or ``None``.

        The move is validated against the engine before being returned so
        the AI never plays an illegal book move.
        """
        book = self._load_opening_book()
        fen_key = self.generate_fen_key()
        candidates = book.get(fen_key)
        if not candidates:
            return None

        # Shuffle so variety is uniform across the candidate list
        candidates = list(candidates)  # copy – do not mutate the book
        random.shuffle(candidates)

        for move in candidates:
            # Sanity-check: must be a 4-item sequence of ints, all in 0..7.
            # This prevents IndexError inside validate_move if the JSON ever
            # contains malformed entries like [9, 9, 9, 9].
            if (
                not isinstance(move, (list, tuple))
                or len(move) != 4
                or not all(isinstance(c, int) and 0 <= c <= 7 for c in move)
            ):
                continue
            fr, fc, tr, tc = move
            is_valid, _ = self.validate_move(fr, fc, tr, tc)
            if is_valid:
                return {
                    'from_row': fr,
                    'from_col': fc,
                    'to_row': tr,
                    'to_col': tc,
                }

        return None  # No valid book move found

    # ------------------------------------------------------------------
    #  AI -- Minimax via C++ engine
    # ------------------------------------------------------------------

    AI_SEARCH_DEPTH_CPP = 4  # C++ is much faster, can search deeper
    AI_SEARCH_DEPTH_PYTHON = 3  # Python engine needs conservative depth

    def get_ai_move(self, depth=None):
        """Return the best move for the current position.

        Checks the opening book first for an instant theory response.
        Falls back to the C++ minimax engine when the position is not
        in the book or the book move fails validation.

        Returns a dict with from/to coordinates, or None when no
        legal move exists (checkmate / stalemate).
        """
        # 1. Opening-book lookup (fast path)
        book_move = self.get_opening_book_move()
        if book_move:
            return book_move

        # 2. Minimax search (slow path)
        board_str = self.serialize_board()
        rights_str = self.serialize_castling_rights()
        if depth is None:
            depth = self._get_ai_search_depth()
        ep_str = self._serialize_ep()
        cmd = f"BESTMOVE {board_str} {rights_str} {self.current_turn} {ep_str} {depth}"
        resp = self._call_engine(cmd)

        if not resp or not resp.startswith("BESTMOVE"):
            return None

        parts = resp.split()
        if len(parts) < 5 or parts[1] == "NONE":
            return None

        return {
            'from_row': int(parts[1]),
            'from_col': int(parts[2]),
            'to_row':   int(parts[3]),
            'to_col':   int(parts[4]),
        }

