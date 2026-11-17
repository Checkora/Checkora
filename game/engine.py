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
import contextlib
import logging
import random
import subprocess
import json
import sys
import time
import threading
import uuid
from datetime import date


logger = logging.getLogger(__name__)


class ChessGame:
    """Manage a single chess game: state, validation,
      and engine communication."""

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
    _opening_book_lock = threading.Lock()

    # Why the last engine request of this object produced nothing usable:
    #   None        the engine answered
    #   'no_reply'  it could not be started or did not answer in time
    #   'bad_reply' it answered something that is not a reply to the command
    # get_ai_move() returning None with last_engine_error None means the
    # engine found no legal move; any other value means it did not answer.
    # Not stored in the session.
    last_engine_error = None

    # Version of the line protocol spoken with the engines. main.cpp and
    # main.py answer "VERSION" with it; a compiled engine that answers
    # anything else was built from older sources and is not used.
    PROTOCOL_VERSION = 2
    # Compiled engines that were tried in this process: path -> usable
    _engine_health = {}

    # Engine servers started by this process (game_id -> Popen), kept so
    # that the ones that have exited can be reaped
    _server_procs = {}
    # time.monotonic() before which no new engine server is started,
    # set after a start that failed
    _persistent_retry_at = 0.0
    PERSISTENT_RETRY_SECONDS = 60
    # How long cleanup_engine() waits for a server to accept SHUTDOWN
    SHUTDOWN_TIMEOUT_SECONDS = 2

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

    def __init__(self, time_limit=600, increment=0, difficulty='medium',
                 game_id=None, authkey=None):
        self.difficulty = difficulty
        self.game_id = game_id or str(uuid.uuid4())
        self.authkey = authkey or os.urandom(16)
        self.board = [row[:] for row in self.INITIAL_BOARD]
        self.current_turn = 'white'
        self.move_history = []
        self.captured = {'white': [], 'black': []}
        # DP Table: {(row, col): [list of moves]}
        self.valid_moves_cache = {}
        self.white_time = time_limit
        self.black_time = time_limit
        self.time_limit = time_limit
        self.increment = increment
        self.last_ts = time.time()
        self.paused = False
        self.mode = 'pvp'
        self.player_color = 'white'
        self.castling_rights = {
            'w_k': True, 'w_q': True,
            'b_k': True, 'b_q': True
        }
        # (row, col) of the square a pawn can capture en passant
        self.en_passant_target = None
        self.halfmove_clock = 0
        self.initial_fullmove = 1
        self.initial_turn_was_black = False
        self.repetition_history = [self.generate_position_key()]
        self.repetition_counts = {self.repetition_history[0]: 1}
        self._game_status = 'active'
        # True while the side to move is in check (set whenever the engine
        # is asked for the status of the position)
        self.in_check = False
        self.draw_reason = None
        self.threefold_warning = False
        self.opening_name = None
        self.opening_moves = None
        self.initial_fen = None

    def serialize_board(self):
        """Flatten the 2-D board into a 64-char string for the C++ engine."""
        return ''.join(c if c else '.' for row in self.board for c in row)

    def generate_pgn(self, white_name='White', black_name='Black'):
        """Generate a PGN string from move history."""
        # Compute result based on game status
        result = '*'
        if self.game_status == 'checkmate':
            result = '0-1' if self.current_turn == 'white' else '1-0'
        elif self.game_status in ('draw', 'stalemate'):
            result = '1/2-1/2'
        elif self.game_status == 'resignation':
            result = '1-0' if self.current_turn == 'black' else '0-1'

        pgn_moves = []
        
        def _fix_castling(move):
            return move.replace('0-0-0', 'O-O-O').replace('0-0', 'O-O')

        fullmove = getattr(self, 'initial_fullmove', 1)
        history = self.move_history or []
        i = 0

        # If Black moved first, write the first half-move as "N... move"
        if getattr(self, 'initial_turn_was_black', False) and history:
            black_move = _fix_castling(history[0]['notation'])
            pgn_moves.append(f"{fullmove}... {black_move}")
            fullmove += 1
            i = 1

        while i < len(history):
            white_move = _fix_castling(history[i]['notation'])
            if i + 1 < len(history):
                black_move = _fix_castling(history[i + 1]['notation'])
                pgn_moves.append(f"{fullmove}. {white_move} {black_move}")
            else:
                pgn_moves.append(f"{fullmove}. {white_move}")
            fullmove += 1
            i += 2
        
        today = date.today().strftime('%Y.%m.%d')
        headers = [
            '[Event "Checkora Match"]',
            '[Site "checkora.io"]',
            f'[Date "{today}"]',
            '[Round "?"]',
            f'[White "{white_name}"]',
            f'[Black "{black_name}"]',
            f'[Result "{result}"]',
        ]
        
        initial_fen = getattr(self, 'initial_fen', None)
        standard_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        if initial_fen and initial_fen.strip() != standard_fen:
            headers.extend([
                '[SetUp "1"]',
                f'[FEN "{initial_fen.strip()}"]',
            ])

        moves = " ".join(pgn_moves)
        moves_str = f"{moves} {result}" if moves else result
        return "\n".join(headers) + "\n\n" + moves_str

    @property
    def game_status(self):
        return self._game_status

    @game_status.setter
    def game_status(self, value):
        self._game_status = value
        if value != 'active':
            self.cleanup_engine()

    @property
    def display_status(self):
        """The status as the board shows it: 'check' while the game is on
        and the side to move is in check, otherwise game_status.

        game_status itself stays 'active' during a check, because the rest
        of the code reads anything else as "the game is over".
        """
        if self._game_status == 'active' and getattr(self, 'in_check', False):
            return 'check'
        return self._game_status

    def to_dict(self):
        """Serialise state for Django session storage.
DP cache is intentionally excluded to save cookie space."""
        return {
            'game_id': self.game_id,
            'authkey': self.authkey.hex(),
            'board': self.board,
            'current_turn': self.current_turn,
            'move_history': self.move_history,
            'captured': self.captured,
            'white_time': self.white_time,
            'black_time': self.black_time,
            'time_limit': self.time_limit,
            'increment': self.increment,
            'last_ts': self.last_ts,
            'paused': self.paused,
            'mode': self.mode,
            'difficulty': self.difficulty,
            'castling_rights': self.castling_rights,
            'en_passant_target': self.en_passant_target,
            'player_color': self.player_color,
            'halfmove_clock': self.halfmove_clock,
            'repetition_history': self.repetition_history,
            'game_status': self.game_status,
            'in_check': getattr(self, 'in_check', False),
            'draw_reason': self.draw_reason,
            'threefold_warning': self.threefold_warning,
            'opening_name': getattr(self, 'opening_name', None),
            'opening_moves': getattr(self, 'opening_moves', None),
            'initial_fullmove': getattr(self, 'initial_fullmove', 1),
            'initial_turn_was_black': getattr(
                self, 'initial_turn_was_black', False
            ),
            'initial_fen': getattr(self, 'initial_fen', None),
        }

    def cleanup_engine(self):
        """Send SHUTDOWN to the persistent engine server for this game."""
        game_id = getattr(self, 'game_id', None)
        if not game_id:
            return

        import tempfile

        port_path = os.path.join(
            tempfile.gettempdir(), f'checkora_engine_{game_id}.port'
        )
        stopped = False
        if os.path.exists(port_path):
            # Never wait long here: a server that is busy or stuck is left
            # to its own idle timeout.
            wait = self.SHUTDOWN_TIMEOUT_SECONDS
            try:
                with open(port_path, 'r') as f:
                    port = int(f.read().strip())
                address = ('127.0.0.1', port)
                conn = self._connect(address, wait)
                try:
                    conn.send("SHUTDOWN")
                    if conn.poll(wait):
                        conn.recv()
                        stopped = True
                finally:
                    conn.close()
            except Exception:
                pass

        # Reap the server if this process started it, so it does not stay
        # behind as a zombie
        proc = self._server_procs.pop(game_id, None)
        if proc is not None:
            try:
                if stopped:
                    proc.wait(timeout=self.SHUTDOWN_TIMEOUT_SECONDS)
                elif proc.poll() is None:
                    self._server_procs[game_id] = proc
            except Exception:
                self._server_procs[game_id] = proc

        # Clean up files
        lock_path = os.path.join(
            tempfile.gettempdir(), f'checkora_engine_{game_id}.lock'
        )
        pid_path = os.path.join(
            tempfile.gettempdir(), f'checkora_engine_{game_id}.pid'
        )
        for path in (lock_path, port_path, pid_path):
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    @classmethod
    def from_dict(cls, data):
        """Restore a game from a session dictionary."""
        game = cls.__new__(cls)
        game.game_id = data.get('game_id') or str(uuid.uuid4())
        authkey_hex = data.get('authkey')
        game.authkey = (bytes.fromhex(authkey_hex) if authkey_hex
                        else os.urandom(16))
        game.board = data['board']
        game.current_turn = data['current_turn']
        game.move_history = data.get('move_history', [])
        game.captured = data.get('captured', {'white': [], 'black': []})
        game.paused = data.get('paused', False)
        game.white_time = data['white_time']
        game.black_time = data['black_time']
        game.time_limit = data.get('time_limit', 600)
        game.increment = data.get('increment', 0)
        game.last_ts = data['last_ts']
        game.mode = data.get('mode', 'pvp')
        game.difficulty = data.get('difficulty', 'medium')
        game.player_color = data.get('player_color', 'white')
        game.castling_rights = data.get(
            'castling_rights',
            {'w_k': True, 'w_q': True, 'b_k': True, 'b_q': True})
        game.en_passant_target = data.get('en_passant_target', None)
        game.halfmove_clock = data.get('halfmove_clock', 0)
        game._game_status = data.get('game_status', 'active')
        game.in_check = bool(data.get('in_check', False))
        game.draw_reason = data.get('draw_reason', None)
        game.threefold_warning = data.get('threefold_warning', False)
        game.opening_name = data.get('opening_name')
        game.opening_moves = data.get('opening_moves')
        game.initial_fullmove = data.get('initial_fullmove', 1)
        game.initial_turn_was_black = data.get('initial_turn_was_black', False)
        game.initial_fen = data.get('initial_fen', None)
        repetition_history = data.get('repetition_history')
        if isinstance(repetition_history, list) and repetition_history:
            game.repetition_history = repetition_history
        else:
            game.repetition_history = [game.generate_position_key()]

        game._rebuild_repetition_counts()

        game.valid_moves_cache = {}
        return game

    @classmethod
    def from_fen(
        cls, fen: str, time_limit=600, increment=0, difficulty='medium'
    ):
        """Create a new game state from a FEN string (board, side, castling)."""
        if not isinstance(fen, str):
            raise ValueError("FEN must be a string.")

        fen = fen.strip()
        if not fen:
            raise ValueError("FEN is empty.")

        parts = fen.split()
        if len(parts) < 3:
            raise ValueError("FEN must have at least 3 fields.")

        placement, active_color, castling = parts[0], parts[1], parts[2]
        board = cls._parse_fen_placement(placement)

        if active_color not in ('w', 'b'):
            raise ValueError("Active color must be 'w' or 'b'.")

        castling_rights = cls._parse_fen_castling(castling)
        # A right only counts while king and rook stand on their home
        # squares; FEN strings often carry rights that no longer apply.
        homes = {
            'w_k': ((7, 4, 'K'), (7, 7, 'R')),
            'w_q': ((7, 4, 'K'), (7, 0, 'R')),
            'b_k': ((0, 4, 'k'), (0, 7, 'r')),
            'b_q': ((0, 4, 'k'), (0, 0, 'r')),
        }
        for right, squares in homes.items():
            if not all(board[r][c] == piece for r, c, piece in squares):
                castling_rights[right] = False

        white_king = sum(1 for row in board for p in row if p == 'K')
        black_king = sum(1 for row in board for p in row if p == 'k')
        if white_king != 1 or black_king != 1:
            raise ValueError(
                "FEN must include exactly one white and one black king.")

        game = cls(
            time_limit=time_limit, increment=increment, difficulty=difficulty
        )
        game.board = board
        game.current_turn = 'white' if active_color == 'w' else 'black'
        game.castling_rights = castling_rights

        # The side that is not to move must not be in check: the first move
        # would capture a king. The engine is asked; if it does not answer
        # the position is accepted as before.
        waiting = 'black' if active_color == 'w' else 'white'
        king = 'k' if active_color == 'w' else 'K'
        king_row, king_col = next(
            (r, c) for r in range(8) for c in range(8) if board[r][c] == king
        )
        if game._is_attacked(king_row, king_col, game.current_turn):
            game.cleanup_engine()
            raise ValueError(
                f"The {waiting} king is in check but it is not "
                f"{waiting}'s move.")

        # Parse en passant target (field 4)
        game.en_passant_target = None
        if len(parts) >= 4 and parts[3] != '-':
            ep_str = parts[3]
            if len(ep_str) == 2 and ep_str[0] in 'abcdefgh' and ep_str[1] in '12345678':
                col = ord(ep_str[0]) - ord('a')
                row = 8 - int(ep_str[1])
                # Only a pawn that has just made a double step can be taken
                # en passant: it stands in front of the target square and
                # the square it skipped and the one it came from are empty.
                white_to_move = active_color == 'w'
                pawn_row = 3 if white_to_move else 4
                start_row = 1 if white_to_move else 6
                if (
                    row == (2 if white_to_move else 5)
                    and board[pawn_row][col] == ('p' if white_to_move else 'P')
                    and board[row][col] is None
                    and board[start_row][col] is None
                ):
                    game.en_passant_target = (row, col)

        # Parse halfmove clock (field 5)
        if len(parts) >= 5:
            try:
                game.halfmove_clock = max(0, int(parts[4]))
            except ValueError:
                game.halfmove_clock = 0
        else:
            game.halfmove_clock = 0

        # Parse fullmove clock (field 6)
        if len(parts) >= 6:
            try:
                game.initial_fullmove = max(1, int(parts[5]))
            except ValueError:
                game.initial_fullmove = 1
        else:
            game.initial_fullmove = 1

        game.initial_turn_was_black = (active_color == 'b')
        ep_square = (
            f"{chr(ord('a') + game.en_passant_target[1])}{8 - game.en_passant_target[0]}"
            if game.en_passant_target else "-"
        )
        game.initial_fen = (
            f"{placement} {active_color} {game.serialize_castling_rights()} "
            f"{ep_square} {game.halfmove_clock} {game.initial_fullmove}"
        )

        game.move_history = []
        game.captured = {'white': [], 'black': []}
        game.valid_moves_cache = {}
        game.repetition_history = [game.generate_position_key()]
        game._rebuild_repetition_counts()
        game.game_status = 'active'
        game.draw_reason = None
        game.threefold_warning = False
        game.last_ts = time.time()

        # The position may already be a check, a mate or a draw. Ask now, so
        # that it is not reported as an ordinary position until the first
        # move is made.
        status = game.check_game_status()
        if status in ('checkmate', 'stalemate', 'draw'):
            game.game_status = status
            if status == 'stalemate':
                game.draw_reason = 'stalemate'
            elif status == 'draw':
                game.draw_reason = 'insufficient_material'
        return game

    @staticmethod
    def _parse_fen_placement(placement: str):
        rows = placement.split('/')
        if len(rows) != 8:
            raise ValueError("FEN must have 8 ranks.")

        valid_pieces = set('prnbqkPRNBQK')
        board = []

        for row in rows:
            row_cells = []
            for ch in row:
                if ch.isdigit():
                    count = int(ch)
                    if count < 1 or count > 8:
                        raise ValueError(
                            "Invalid empty-square count in FEN.")
                    row_cells.extend([None] * count)
                else:
                    if ch not in valid_pieces:
                        raise ValueError(
                            "Invalid piece character in FEN.")
                    row_cells.append(ch)

            if len(row_cells) != 8:
                raise ValueError("Each FEN rank must have 8 files.")
            board.append(row_cells)

        return board

    @staticmethod
    def _parse_fen_castling(castling: str):
        rights = {'w_k': False, 'w_q': False, 'b_k': False, 'b_q': False}

        if castling == '-':
            return rights

        valid_chars = set('KQkq')
        for ch in castling:
            if ch not in valid_chars:
                raise ValueError("Invalid castling rights in FEN.")
            if ch == 'K':
                rights['w_k'] = True
            elif ch == 'Q':
                rights['w_q'] = True
            elif ch == 'k':
                rights['b_k'] = True
            elif ch == 'q':
                rights['b_q'] = True

        return rights

    # ------------------------------------------------------------------
    #  C++ engine communication
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_engine_path(cls):
        """Return the first usable engine entrypoint for this platform."""
        for path in cls.ENGINE_CANDIDATES:
            if not os.path.exists(path):
                continue
            if path.endswith('.py') or cls._binary_runs(path):
                return path
        return None

    @classmethod
    def _binary_runs(cls, path):
        """Return True when the compiled engine at *path* can be used.

        A binary built for another system or C library exists on disk but
        cannot run, and one built from older sources speaks another
        protocol; without this check main.py would never get its turn.
        The binary is asked for its protocol version, once per process.
        """
        if not os.path.isfile(path):
            return True  # nothing to inspect; the caller will find out
        usable = cls._engine_health.get(path)
        if usable is None:
            usable = False
            if os.access(path, os.X_OK):
                proc = None
                try:
                    proc = subprocess.Popen(
                        [path],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                    )
                    stdout, _ = proc.communicate(input="VERSION\n", timeout=5)
                    usable = (
                        stdout.strip() == f"VERSION {cls.PROTOCOL_VERSION}"
                    )
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                except Exception:
                    pass
            if not usable:
                logger.warning(
                    "Chess engine binary %s does not run here or is out of "
                    "date (rebuild it from main.cpp); trying the next "
                    "engine.", path)
            cls._engine_health[path] = usable
        return usable

    @staticmethod
    def _build_engine_command(engine_path):
        """Build the subprocess command for either a binary
        or Python script."""
        if engine_path.endswith('.py'):
            return [sys.executable, '-u', engine_path]
        return [engine_path]

    @classmethod
    def _reap_servers(cls):
        """Forget engine servers started by this process that have exited."""
        for game_id, proc in list(cls._server_procs.items()):
            try:
                if proc.poll() is not None:
                    cls._server_procs.pop(game_id, None)
            except Exception:
                cls._server_procs.pop(game_id, None)

    def _connect(self, address, timeout):
        """Open a connection to this game's engine server.

        Client() has no timeout and its handshake waits for as long as the
        single-threaded server is busy, so it runs in a helper thread.
        Raises TimeoutError when the server does not answer in *timeout*
        seconds.
        """
        from multiprocessing.connection import Client

        lock = threading.Lock()
        result = {}

        def connect():
            try:
                conn = Client(address, family='AF_INET', authkey=self.authkey)
            except Exception as exc:
                result['error'] = exc
                return
            with lock:
                if result.get('abandoned'):
                    conn.close()  # nobody is waiting for it any more
                else:
                    result['conn'] = conn

        worker = threading.Thread(target=connect, daemon=True)
        worker.start()
        worker.join(timeout)
        with lock:
            if 'conn' in result:
                return result['conn']
            if 'error' not in result:
                result['abandoned'] = True
        if 'error' in result:
            raise result['error']
        raise TimeoutError("engine server is busy")

    def _call_engine(self, command):
        """Run the C++ engine with *command* on stdin and return stdout."""
        engine_path = self._resolve_engine_path()
        if not engine_path:
            return None

        game_id = getattr(self, 'game_id', None)
        if not game_id:
            self.game_id = str(uuid.uuid4())
            game_id = self.game_id

        import tempfile

        timeout_secs = getattr(
            self, "_analysis_timeout", self.ANALYSIS_TIMEOUT_SECONDS
        )

        port_path = os.path.join(
            tempfile.gettempdir(), f'checkora_engine_{game_id}.port'
        )
        lock_path = os.path.join(
            tempfile.gettempdir(), f'checkora_engine_{game_id}.lock'
        )

        def get_address():
            if os.path.exists(port_path):
                try:
                    with open(port_path, 'r') as f:
                        port = int(f.read().strip())
                        return ('127.0.0.1', port)
                except Exception:
                    pass
            return None

        # Try to connect if port file exists
        conn = None
        server_busy = False
        address = get_address()
        if address:
            try:
                conn = self._connect(address, timeout_secs)
            except TimeoutError:
                # The server is there but occupied. A second one would not
                # help; this request is answered by a one-off engine below.
                server_busy = True
            except Exception:
                pass

        # After a failed start, do not make every request wait for another
        # attempt; go straight to the one-off engine for a while.
        may_spawn = time.monotonic() >= ChessGame._persistent_retry_at

        if not conn and not server_busy and may_spawn:
            # Check for stale lock file and clean it up (5.0s TTL)
            if os.path.exists(lock_path):
                try:
                    if time.time() - os.path.getmtime(lock_path) > 5.0:
                        os.unlink(lock_path)
                except OSError:
                    pass

            # Connection failed or not started. Attempt to acquire spawn lock.
            lock_acquired = False
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                lock_acquired = True
            except OSError:
                pass

            if lock_acquired:
                # Spawn the server in the background
                try:
                    server_script = os.path.join(
                        self.ENGINE_DIR, 'persistent_server.py'
                    )
                    engine_cmd_json = json.dumps(
                        self._build_engine_command(engine_path)
                    )
                    authkey_hex = self.authkey.hex()

                    creationflags = 0
                    if os.name == 'nt':
                        creationflags = subprocess.CREATE_NO_WINDOW

                    if os.path.exists(port_path):
                        try:
                            os.unlink(port_path)
                        except OSError:
                            pass

                    # The server gives the engine as long to answer as
                    # this side is prepared to wait.
                    self._reap_servers()
                    self._server_procs[game_id] = subprocess.Popen(
                        [sys.executable, server_script, game_id,
                         engine_cmd_json, authkey_hex,
                         str(self.ANALYSIS_TIMEOUT_SECONDS)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        close_fds=True,
                        creationflags=creationflags
                    )
                except Exception:
                    pass

                # Poll for the port file to be created, and then connect
                start_time = time.time()
                backoff = 0.01
                while time.time() - start_time < 2.0:
                    address = get_address()
                    if address:
                        try:
                            conn = self._connect(address, 2.0)
                            break
                        except Exception:
                            pass
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 0.1)

                # Release the lock
                try:
                    os.unlink(lock_path)
                except OSError:
                    pass

                if not conn:
                    logger.warning(
                        "Chess engine server did not start; using one "
                        "engine process per request for the next %s s.",
                        self.PERSISTENT_RETRY_SECONDS,
                    )
                    ChessGame._persistent_retry_at = (
                        time.monotonic() + self.PERSISTENT_RETRY_SECONDS
                    )
            else:
                # Lock is held by someone else. Wait for lock release or
                # connection to succeed
                start_time = time.time()
                backoff = 0.01
                while time.time() - start_time < 2.0:
                    address = get_address()
                    if address:
                        try:
                            conn = self._connect(address, 2.0)
                            break
                        except Exception:
                            pass
                    if not os.path.exists(lock_path):
                        # Lock file was deleted, try connecting one last time
                        address = get_address()
                        if address:
                            try:
                                conn = self._connect(address, 2.0)
                            except Exception:
                                pass
                        break
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 0.1)

        if not conn:
            # Fallback to stateless spawning if the server failed to
            # start or connect
            proc = None
            try:
                proc = subprocess.Popen(
                    self._build_engine_command(engine_path),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                stdout, stderr = proc.communicate(
                    input=command, timeout=timeout_secs
                )
                if stderr:
                    logger.warning(
                        "Chess engine wrote to stderr while handling %s: %s",
                        command.split(maxsplit=1)[0] if command else "<empty>",
                        stderr.strip(),
                    )
                return stdout.strip()
            except subprocess.TimeoutExpired as exc:
                if proc:
                    try:
                        proc.kill()
                        _, stderr = proc.communicate()
                        stderr = stderr or getattr(exc, "stderr", None)
                        if stderr:
                            logger.warning(
                                "Chess engine timed out while handling %s. "
                                "stderr: %s",
                                command.split(maxsplit=1)[0]
                                if command else "<empty>",
                                stderr.strip()
                                if isinstance(stderr, str) else stderr,
                            )
                    except Exception:
                        pass
                return None
            except OSError as exc:
                logger.warning(
                    "Failed to start chess engine while handling %s: %s",
                    command.split(maxsplit=1)[0] if command else "<empty>",
                    exc,
                )
                return None

        try:
            conn.send(command)
            if conn.poll(timeout_secs):
                return conn.recv()

            # No answer in time. The server replaces a stuck engine by
            # itself; cleanup_engine() only waits a moment for it.
            with contextlib.suppress(OSError):
                conn.close()
            self.cleanup_engine()
            return None
        except Exception:
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ask_engine(self, command, prefix):
        """Send *command* and return the reply if it starts with *prefix*.

        Returns None otherwise and records the reason in
        ``last_engine_error`` ('no_reply' or 'bad_reply').
        """
        resp = self._call_engine(command)
        if not isinstance(resp, str) or not resp.strip():
            self.last_engine_error = 'no_reply'
            return None
        if not resp.startswith(prefix):
            self.last_engine_error = 'bad_reply'
            return None
        self.last_engine_error = None
        return resp

    def _is_attacked(self, row, col, attacker):
        """Ask the engine whether *attacker* ('white' or 'black') attacks
        the square. False when it does not, or when the engine is silent."""
        cmd = (
            f"ATTACKED {self.serialize_board()}"
            f" {self.serialize_castling_rights()} {attacker} {row} {col}"
        )
        return self._ask_engine(cmd, ("YES", "NO")) == "YES"

    def _get_ai_settings(self):
        """Return the search limits for this game's difficulty."""
        if self.difficulty in self.DIFFICULTY_SETTINGS:
            return self.DIFFICULTY_SETTINGS[self.difficulty]
        return self.DIFFICULTY_SETTINGS['medium']

    def _get_ai_search_depth(self):
        """Return appropriate search depth based on difficulty."""
        return self._get_ai_settings()['max_depth']

    def serialize_castling_rights(self):
        """Serialize castling rights to a string for the C++ engine."""
        rights = ''
        if self.castling_rights['w_k']:
            rights += 'K'
        if self.castling_rights['w_q']:
            rights += 'Q'
        if self.castling_rights['b_k']:
            rights += 'k'
        if self.castling_rights['b_q']:
            rights += 'q'
        return rights if rights else '-'

    def _serialize_ep(self):
        """Serialize en passant target for the C++ engine."""
        if not self.en_passant_target:
            return "-1 -1"
        return f"{self.en_passant_target[0]} {self.en_passant_target[1]}"

    def _en_passant_key(self):
        """Return a compact en-passant key for repetition tracking."""
        if not self._has_legal_en_passant_capture():
            return '-'
        return f"{self.en_passant_target[0]},{self.en_passant_target[1]}"

    def _has_legal_en_passant_capture(self):
        """Return True when the side to move can
        legally capture en passant."""
        if not self.en_passant_target:
            return False

        target_row, target_col = self.en_passant_target
        is_w = self.current_turn == 'white'
        pawn_row = target_row + 1 if is_w else target_row - 1
        pawn_piece = 'P' if self.current_turn == 'white' else 'p'

        if not (0 <= pawn_row < 8):
            return False

        for delta_col in (-1, 1):
            pawn_col = target_col + delta_col
            if (0 <= pawn_col < 8
                    and self.board[pawn_row][pawn_col] == pawn_piece):
                return True

        return False

    def generate_position_key(self):
        """Build the full repetition key for the current board state."""
        return f"{self.generate_fen_key()} {self._en_passant_key()}"

    def _update_repetition(self):
        """Increment and return the repetition count
        for the current position."""
        key = self.generate_position_key()
        self.repetition_history.append(key)
        self._rebuild_repetition_counts()
        return self.repetition_counts[key]

    def _rebuild_repetition_counts(self):
        """Rebuild the repetition counter
          from the stored history list."""
        counts = {}
        for key in self.repetition_history:
            counts[key] = counts.get(key, 0) + 1
        self.repetition_counts = counts

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
        """Execute move and invalidate cache
          to ensure fresh calculations."""
        self.last_engine_error = None
        if self.game_status != 'active':
            return False, "Game is already over.", None, self.game_status

        if not all(self._on_board(v) for v in (fr, fc, tr, tc)):
            return False, "Illegal move.", None, 'active'

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
        is_pawn_move = piece.lower() == 'p'
        board_before = self.serialize_board()
        rights_before = self.serialize_castling_rights()
        ep_before = self._serialize_ep()

        # Detect En Passant capture before moving piece
        if piece.lower() == 'p' and fc != tc and not captured:
            if (self.en_passant_target
                    and tr == self.en_passant_target[0]
                    and tc == self.en_passant_target[1]):
                # The captured piece is of opposite color
                captured = 'p' if piece.isupper() else 'P'
                # In EP, the captured pawn is at (fr, tc)
                self.board[fr][tc] = None

        if piece == 'K':
            self.castling_rights['w_k'] = False
            self.castling_rights['w_q'] = False
        elif piece == 'k':
            self.castling_rights['b_k'] = False
            self.castling_rights['b_q'] = False
        elif piece == 'R':
            if fr == 7 and fc == 0:
                self.castling_rights['w_q'] = False
            elif fr == 7 and fc == 7:
                self.castling_rights['w_k'] = False
        elif piece == 'r':
            if fr == 0 and fc == 0:
                self.castling_rights['b_q'] = False
            elif fr == 0 and fc == 7:
                self.castling_rights['b_k'] = False

        if captured == 'R':
            if tr == 7 and tc == 0:
                self.castling_rights['w_q'] = False
            elif tr == 7 and tc == 7:
                self.castling_rights['w_k'] = False
        elif captured == 'r':
            if tr == 0 and tc == 0:
                self.castling_rights['b_q'] = False
            elif tr == 0 and tc == 7:
                self.castling_rights['b_k'] = False

        # Pawn promotion: delegate to C++ engine for validation + board update
        promoted = False
        if self._is_promotion(piece, tr):
            # The choice comes from the client and goes into an engine
            # command: only one of q, r, b, n may get through.
            choice = (
                promotion_piece.lower()
                if isinstance(promotion_piece, str) else 'q'
            )
            if choice not in ('q', 'r', 'b', 'n'):
                choice = 'q'
            new_board = self._call_engine_promote(fr, fc, tr, tc, choice)
            if new_board:
                # C++ returned the updated board - apply it directly
                self.board = self._parse_board64(new_board)
                promoted = True
            else:
                # Fallback: apply promotion in Python
                self.board[tr][tc] = self._promote(piece, choice)
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

        if is_pawn_move or captured:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        notation = self._notation(
            fr, fc, tr, tc, piece, captured,
            board_before, rights_before, ep_before,
            promo_char=choice if promoted else None)

        # Invalidate DP cache because board state has changed
        self.valid_moves_cache = {}

        # Save who made this move before switching
        moved_by = self.current_turn

        # Apply increment to the player who just made the move
        is_white = self.current_turn == 'white'
        if self.increment > 0:
            if is_white:
                self.white_time += self.increment
            else:
                self.black_time += self.increment

        # Switch turn
        self.current_turn = 'black' if is_white else 'white'

        self.last_ts = time.time()

        current_rights = self.serialize_castling_rights()
        is_irreversible = is_pawn_move or bool(
            captured) or current_rights != rights_before
        if is_irreversible:
            self.repetition_history = [self.generate_position_key()]
            self._rebuild_repetition_counts()
        else:
            repetition_count = self._update_repetition()

        # Check for checkmate / stalemate / check
        game_status = self.check_game_status()
        # STATUS decides between check and mate; replace whatever suffix
        # the notation came with instead of adding a second one.
        if game_status == 'checkmate':
            notation = notation.rstrip('+#') + '#'
        elif game_status == 'check':
            notation = notation.rstrip('+#') + '+'
        self.move_history.append({
            'notation': notation,
            'piece': piece,
            'from': [fr, fc],
            'to': [tr, tc],
            'captured': captured,
            'color': moved_by,
            'promoted_to': self.board[tr][tc] if promoted else None,
        })

        if game_status == 'checkmate':
            self.game_status = game_status
            return True, notation, captured, game_status

        if game_status == 'stalemate':
            self.game_status = game_status
            self.draw_reason = 'stalemate'
            return True, notation, captured, game_status

        if game_status == 'draw':
            self.game_status = game_status
            self.draw_reason = 'insufficient_material'
            return True, notation, captured, game_status

        repetition_count = self.repetition_counts.get(
            self.generate_position_key(), 1)
        
        # Warning on second occurrence
        self.threefold_warning = (repetition_count == 2)

        if repetition_count >= 3:
            self.game_status = 'draw'
            self.draw_reason = 'threefold_repetition'
            return True, notation, captured, 'draw'

        if self.halfmove_clock >= 100:
            self.game_status = 'draw'
            self.draw_reason = 'fifty_move_rule'
            return True, notation, captured, 'draw'

        self.game_status = 'active'
        self.draw_reason = None
        
        if repetition_count != 2:
            self.threefold_warning = False
    
        return True, notation, captured, game_status

    def get_valid_moves(self, row, col):
        """Return legal moves from DP cache.

        An empty list with ``last_engine_error`` set means the engine did
        not answer, not that the piece has no moves.
        """
        self.last_engine_error = None
        if not (self._on_board(row) and self._on_board(col)):
            return []

        piece = self.board[row][col]
        if not piece or self._color(piece) != self.current_turn:
            return []

        # On-Demand Caching: If not in DP, compute once and store
        if (row, col) not in self.valid_moves_cache:
            moves = self._get_engine_moves(row, col)
            if moves is None:
                return []  # no answer: do not remember it as "no moves"
            self.valid_moves_cache[(row, col)] = moves

        return self.valid_moves_cache.get((row, col), [])

    def _get_engine_moves(self, row, col):
        """Internal helper to fetch piece moves from the C++ binary.

        Returns None when the engine did not answer."""
        board_str = self.serialize_board()
        rights_str = self.serialize_castling_rights()
        ep_str = self._serialize_ep()
        cmd = (
            f"MOVES {board_str} {rights_str}"
            f" {self.current_turn} {ep_str} {row} {col}"
        )
        resp = self._ask_engine(cmd, "MOVES")
        if resp is None:
            return None

        moves = []
        if resp and resp.startswith("MOVES"):
            parts = resp.split()[1:]
            # C++ returns 4 fields per move:
            # row col is_capture is_promotion
            rem = len(parts) % 4
            if rem != 0:
                logger.warning(
                    "get_valid_moves: skipped %d trailing tokens from engine: %s",
                    rem, parts[-rem:]
                )
            for i in range(0, len(parts) - 3, 4):
                try:
                    moves.append({
                        'row': int(parts[i]),
                        'col': int(parts[i+1]),
                        'is_capture': bool(int(parts[i+2])),
                        'is_promotion': bool(int(parts[i+3])),
                    })
                except ValueError as err:
                    logger.warning(
                        "get_valid_moves: invalid move tokens at index %d (%s): %s",
                        i, parts[i:i+4], err
                    )
                    continue
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
        cmd = (
            f"PROMOTE {board_str} {rights_str}"
            f" {self.current_turn} {ep_str}"
            f" {fr} {fc} {tr} {tc} {choice}"
        )
        resp = self._ask_engine(cmd, "PROMOTE")
        if resp:
            parts = resp.split()
            if len(parts) > 1 and len(parts[1]) == 64:
                return parts[1]
            self.last_engine_error = 'bad_reply'
        return None

    @staticmethod
    def _on_board(value):
        """True for a row or column index that is on the board."""
        return (
            isinstance(value, int) and not isinstance(value, bool)
            and 0 <= value <= 7
        )

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
        return ChessGame._is_promotion(board[fr][fc], tr)

    def _notation(self, fr, fc, tr, tc, piece, captured,
                  board_str=None, rights_str=None,
                  ep_str=None, promo_char=None):
        """
        Generate SAN notation via C++ engine if possible,
          else simplified fallback."""
        if promo_char:
            promo_char = (
                promo_char.lower() if isinstance(promo_char, str) else 'q'
            )
            if promo_char not in ('q', 'r', 'b', 'n'):
                promo_char = 'q'

        if board_str and rights_str:
            ep_str = ep_str or self._serialize_ep()
            cmd = (
                f"NOTATION {board_str} {rights_str}"
                f" {self.current_turn} {ep_str}"
                f" {fr} {fc} {tr} {tc}"
            )
            if promo_char:
                cmd += f" {promo_char}"
            resp = self._ask_engine(cmd, "NOTATION")
            if resp:
                parts = resp.split()
                if len(parts) >= 2:
                    return parts[1]
        # Castling
        if piece.lower() == 'k':
            if fc == 4 and tc == 6:
                notation = "O-O"
            elif fc == 4 and tc == 2:
                notation = "O-O-O"
            else:
                files = "abcdefgh"
                t_coord = f"{files[tc]}{8 - tr}"
                if captured:
                    notation = f"Kx{t_coord}"
                else:
                    notation = f"K{t_coord}"
        else:
            # Fallback: simplified notation
            files = "abcdefgh"
            f_coord = f"{files[fc]}{8 - fr}"
            t_coord = f"{files[tc]}{8 - tr}"

            if not piece:
                notation = f"{f_coord} -> {t_coord}"

            else:
                type = piece.lower()

                if type == 'p':
                    if fc != tc:
                        notation = f"{files[fc]}x{t_coord}"
                    else:
                        notation = t_coord

                else:
                    p_char = type.upper()

                    if captured:
                        notation = f"{p_char}x{t_coord}"
                    else:
                        notation = f"{p_char}{t_coord}"
        if promo_char and '=' not in notation:
            notation += '=' + promo_char.upper()
        return notation

    @staticmethod
    def _color(piece):
        if not piece:
            return None
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

        self.last_ts += elapsed

    # ------------------------------------------------------------------
    #  Game status detection (check / checkmate / stalemate)
    # ------------------------------------------------------------------

    def check_game_status(self):
        """Ask the C++ engine for the game status of the current side.

        Returns one of: 'checkmate', 'stalemate', 'draw', 'check', 'ok'.
        'ok' is also what comes back when the engine did not answer; in
        that case ``last_engine_error`` is set.
        """
        board_str = self.serialize_board()
        rights_str = self.serialize_castling_rights()
        ep_str = self._serialize_ep()
        cmd = f"STATUS {board_str} {rights_str} {self.current_turn} {ep_str}"
        resp = self._ask_engine(cmd, "STATUS")
        if resp:
            status = resp.split()[1].lower() if len(resp.split()) > 1 else ''
            if status in ('checkmate', 'stalemate', 'draw', 'check', 'ok'):
                self.in_check = status in ('check', 'checkmate')
                return status
            self.last_engine_error = 'bad_reply'
        return 'ok'

    # ------------------------------------------------------------------
    #  AI -- Opening Book
    # ------------------------------------------------------------------

    @classmethod
    def _load_opening_book(cls) -> dict:
        """Load the opening book JSON from disk (cached after first load)."""
        if cls._opening_book is None:
            with cls._opening_book_lock:
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
        # Already returns '-' if none
        castling = self.serialize_castling_rights()

        return f"{placement} {side} {castling}"

    def generate_full_fen(self) -> str:
        """Build a complete 6-field FEN string."""
        base_fen = self.generate_fen_key()

        # En Passant target
        ep_str = '-'
        if self.en_passant_target:
            row, col = self.en_passant_target
            file_char = chr(ord('a') + col)
            rank_char = str(8 - row)
            ep_str = f"{file_char}{rank_char}"

        # Halfmove clock
        halfmove = str(self.halfmove_clock)

        # Fullmove clock
        offset = 1 if getattr(self, 'initial_turn_was_black', False) else 0
        fullmove_count = getattr(self, 'initial_fullmove', 1)
        fullmove = str(fullmove_count + ((len(self.move_history) + offset) // 2))

        return f"{base_fen} {ep_str} {halfmove} {fullmove}"

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

    # Max seconds for engine analysis before returning best move
    ANALYSIS_TIMEOUT_SECONDS = 10

    # How each level plays. The search stops at max_depth plies or when
    # time_budget_ms is used up, whichever comes first. A level marked
    # time_only has no depth cut-off: it keeps deepening until its time is
    # used, and max_depth is only the depth it is expected to pass.
    # A level with error_rate makes deliberate mistakes: in about that
    # share of its moves it plays one of the engine's alternatives instead
    # of the best move, but never one the engine scores more than
    # error_max_loss centipawns below the best.
    DIFFICULTY_SETTINGS = {
        'easy': {'max_depth': 2, 'time_budget_ms': 500,
                 'error_rate': 0.5, 'error_max_loss': 900},
        'medium': {'max_depth': 4, 'time_budget_ms': 1500},
        'hard': {'max_depth': 6, 'time_budget_ms': 4000, 'time_only': True},
    }
    # Depth sent for a time_only level (the engines stop at 64 anyway)
    UNLIMITED_DEPTH = 64
    # Alternatives asked from the engine besides the best move, and how
    # many for a level that chooses among them
    ALTERNATIVES = 3
    ERROR_ALTERNATIVES = 8

    def get_ai_move(self, depth=None, difficulty=None):
        """Return the best move for the current position.

        Checks the opening book first for an instant theory response.
        Falls back to the C++ minimax engine when the position is not
        in the book or the book move fails validation.

        The search limits come from *difficulty* (or the game's own
        difficulty); *depth*, when given without a difficulty, replaces the
        depth limit, is taken as given, and switches off the deliberate
        mistakes of the easy level.

        Returns a dict with from/to coordinates, or None when no
        legal move exists (checkmate / stalemate). None is also returned
        when the engine did not answer; ``last_engine_error`` tells the
        two apart.
        """
        # 1. Opening-book lookup (fast path)
        book_move = self.get_opening_book_move()
        if book_move:
            return book_move

        # 2. Map difficulty settings
        if difficulty in self.DIFFICULTY_SETTINGS:
            cfg = self.DIFFICULTY_SETTINGS[difficulty]
        else:
            cfg = self._get_ai_settings()
        max_depth = cfg['max_depth']
        if cfg.get('time_only'):
            max_depth = self.UNLIMITED_DEPTH
        time_budget_ms = cfg['time_budget_ms']
        error_rate = cfg.get('error_rate', 0)
        if depth is not None and difficulty not in self.DIFFICULTY_SETTINGS:
            max_depth = max(1, int(depth))
            error_rate = 0
        alternatives = (
            self.ERROR_ALTERNATIVES if error_rate else self.ALTERNATIVES
        )

        # 3. Minimax search (slow path). The positions since the last
        # capture or pawn move go along so the search sees repetitions.
        board_str = self.serialize_board()
        rights_str = self.serialize_castling_rights()
        ep_str = self._serialize_ep()
        earlier = list(self.repetition_history[-101:])
        if earlier and earlier[-1] == self.generate_position_key():
            earlier.pop()  # the current position itself
        earlier = [
            key for key in earlier[-100:]
            if isinstance(key, str) and len(key.split()) == 4
        ]
        cmd = (
            f"BESTMOVE {board_str} {rights_str}"
            f" {self.current_turn} {ep_str} {max_depth} {time_budget_ms}"
            f" {self.halfmove_clock} {alternatives}"
        )
        if earlier:
            cmd += " " + " ".join(earlier)
        resp = self._ask_engine(cmd, "BESTMOVE")
        if not resp:
            return None

        parts = resp.split()
        if len(parts) >= 2 and parts[1] == "NONE":
            return None  # no legal move; last_engine_error stays None

        try:
            move_data = self._parse_bestmove(parts)
        except ValueError:
            move_data = None
        if move_data is None:
            self.last_engine_error = 'bad_reply'
            return None

        # The engines only ever promote to a queen
        piece = self.board[move_data['from_row']][move_data['from_col']]
        if self._is_promotion(piece, move_data['to_row']):
            move_data['promotion_piece'] = 'q'

        if error_rate:
            self._play_weaker(move_data, error_rate, cfg['error_max_loss'])
        return move_data

    @classmethod
    def _parse_bestmove(cls, parts):
        """Turn the tokens of a BESTMOVE reply into the move dict.

        Returns None for a reply without a usable move; a token that should
        be a number and is not raises ValueError.
        """
        if len(parts) < 5:
            return None

        move_data = {
            'from_row': int(parts[1]),
            'from_col': int(parts[2]),
            'to_row':   int(parts[3]),
            'to_col':   int(parts[4]),
            'eval': None,
            'alts': [],
            'depth': 0,
            'nodes': 0,
            'tthits': 0,
            'time': 0,
            'engine': 'unknown',
            'status': 'completed'
        }
        
        idx = 5
        while idx < len(parts):
            if parts[idx] == "EVAL" and idx + 1 < len(parts):
                move_data['eval'] = int(parts[idx + 1])
                idx += 2
            elif parts[idx] == "ALTS":
                idx += 1
                while idx + 4 < len(parts) and parts[idx] not in ("EVAL", "ALTS", "DEPTH", "NODES", "TTHITS", "TIME", "ENGINE", "STATUS"):
                    move_data['alts'].append({
                        'from_row': int(parts[idx]),
                        'from_col': int(parts[idx+1]),
                        'to_row': int(parts[idx+2]),
                        'to_col': int(parts[idx+3]),
                        'eval': int(parts[idx+4])
                    })
                    idx += 5
            elif parts[idx] == "DEPTH" and idx + 1 < len(parts):
                move_data['depth'] = int(parts[idx + 1])
                idx += 2
            elif parts[idx] == "NODES" and idx + 1 < len(parts):
                move_data['nodes'] = int(parts[idx + 1])
                idx += 2
            elif parts[idx] == "TTHITS" and idx + 1 < len(parts):
                move_data['tthits'] = int(parts[idx + 1])
                idx += 2
            elif parts[idx] == "TIME" and idx + 1 < len(parts):
                move_data['time'] = int(parts[idx + 1])
                idx += 2
            elif parts[idx] == "ENGINE" and idx + 1 < len(parts):
                move_data['engine'] = parts[idx + 1]
                idx += 2
            elif parts[idx] == "STATUS" and idx + 1 < len(parts):
                move_data['status'] = parts[idx + 1]
                idx += 2
            else:
                idx += 1

        squares = ('from_row', 'from_col', 'to_row', 'to_col')
        if not all(cls._on_board(move_data[key]) for key in squares):
            return None
        move_data['alts'] = [
            alt for alt in move_data['alts']
            if all(cls._on_board(alt[key]) for key in squares)
        ]
        return move_data

    def _play_weaker(self, move_data, rate, max_loss):
        """Now and then replace the best move by one of the alternatives.

        Used by the easy level. An alternative qualifies only if the engine
        scores it no more than *max_loss* centipawns below the best move.
        """
        best_eval = move_data.get('eval')
        if best_eval is None or random.random() >= rate:
            return
        squares = ('from_row', 'from_col', 'to_row', 'to_col')
        sign = 1 if self.current_turn == 'white' else -1  # eval is White's
        choices = [
            alt for alt in move_data['alts']
            if sign * (best_eval - alt['eval']) <= max_loss
        ]
        if not choices:
            return
        alt = random.choice(choices)
        best = {key: move_data[key] for key in squares + ('eval',)}
        others = [a for a in move_data['alts'] if a is not alt]
        move_data.update({key: alt[key] for key in squares + ('eval',)})
        move_data['alts'] = [best] + others
        piece = self.board[move_data['from_row']][move_data['from_col']]
        if self._is_promotion(piece, move_data['to_row']):
            move_data['promotion_piece'] = 'q'
        else:
            move_data.pop('promotion_piece', None)
