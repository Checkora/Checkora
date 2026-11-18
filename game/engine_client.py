"""Getting protocol lines to a chess engine and its replies back.

Every game has its own engine server, engine/persistent_server.py: a small
process that keeps one engine running and answers on a loopback port, so
that a request does not pay for starting an engine. The server's port is in
a file named after the game in the temp directory. A request that finds no
server starts one (a lock file makes sure only one request per game does);
a request that cannot get a server in time is answered by an engine process
started for it alone.

The engine is the compiled main.cpp when it runs on this machine and speaks
the current protocol, main.py otherwise. Nothing here knows the protocol
beyond VERSION and the server's SHUTDOWN; game/engine.py builds the
commands and reads the replies.
"""
import contextlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from multiprocessing import AuthenticationError, connection

logger = logging.getLogger(__name__)

ENGINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engine')
SERVER_SCRIPT = os.path.join(ENGINE_DIR, 'persistent_server.py')
ENGINE_CANDIDATES = [
    os.path.join(ENGINE_DIR, name)
    for name in (('main.exe', 'main') if os.name == 'nt' else ('main', 'main.exe')) + ('main.py',)
]
# Version of the line protocol. main.cpp and main.py answer "VERSION" with
# it; a compiled engine that answers anything else was built from older
# sources and is not used.
PROTOCOL_VERSION = 2
# The server reads its connection key from here (see persistent_server.py)
AUTHKEY_ENV = 'CHECKORA_ENGINE_AUTHKEY'

# How long a new server may take to come up before a request stops waiting
SERVER_START_SECONDS = 2.0
# A lock file older than this was left by a request that died while it
# was starting a server
STALE_LOCK_SECONDS = 5.0
# After a server failed to start, requests use one-off engines for this long
# instead of each waiting for another attempt
RETRY_SECONDS = 60

# Per process: compiled engines tried so far (path -> usable), the servers
# this process started (game_id -> Popen, kept so that they can be reaped),
# and the time.monotonic() before which no server is started.
_engine_health = {}
_server_procs = {}
_retry_at = 0.0


class ServerTimeout(Exception):
    """The game's server took a request and did not answer in time."""


def resolve_engine_path(candidates):
    """The first of *candidates* that exists and can be used here, or None."""
    for path in candidates:
        if os.path.exists(path) and (path.endswith('.py') or binary_runs(path)):
            return path
    return None


def binary_runs(path):
    """True when the compiled engine at *path* can be used.

    A binary built for another system or C library exists on disk but
    cannot run, and one built from older sources speaks another protocol;
    without this check main.py would never get its turn. The binary is
    asked for its protocol version, once per process.
    """
    if not os.path.isfile(path):
        return True  # nothing to inspect; the request will find out
    usable = _engine_health.get(path)
    if usable is None:
        usable = False
        if os.access(path, os.X_OK):
            proc = None
            try:
                proc = subprocess.Popen(
                    [path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True,
                )
                stdout, _ = proc.communicate(input='VERSION\n', timeout=5)
                usable = stdout.strip() == f'VERSION {PROTOCOL_VERSION}'
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
            except (OSError, ValueError):
                pass  # not a program for this machine, or one that prints bytes, not text
        if not usable:
            logger.warning(
                'Chess engine binary %s does not run here or is out of date '
                '(rebuild it from main.cpp); trying the next engine.', path)
        _engine_health[path] = usable
    return usable


def engine_command(engine_path):
    """The command that starts the engine at *engine_path*."""
    if engine_path.endswith('.py'):
        return [sys.executable, '-u', engine_path]
    return [engine_path]


def connect(address, authkey, timeout):
    """Open a connection to an engine server.

    Client() has no timeout, and its handshake waits for as long as the
    single-threaded server is busy, so it runs in a helper thread. Raises
    TimeoutError when the server does not answer in *timeout* seconds, and
    whatever Client() raises when it fails.
    """
    lock = threading.Lock()
    result = {}

    def run():
        try:
            conn = connection.Client(address, family='AF_INET', authkey=authkey)
        except Exception as exc:
            result['error'] = exc
            return
        with lock:
            if result.get('abandoned'):
                conn.close()  # nobody is waiting for it any more
            else:
                result['conn'] = conn

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)
    with lock:
        if 'conn' in result:
            return result['conn']
        if 'error' not in result:
            result['abandoned'] = True
    if 'error' in result:
        raise result['error']
    raise TimeoutError('engine server is busy')


def _reap_servers():
    """Forget servers started by this process that have exited."""
    for game_id, proc in list(_server_procs.items()):
        if proc.poll() is not None:
            _server_procs.pop(game_id, None)


class EngineClient:
    """The way to the engine for one game.

    *engine_cmd* starts the engine, and *server_reply_timeout* is how long
    a server started from here waits for its engine to answer; both are
    only needed to ask().
    """

    # What can go wrong while connecting to a server that is gone or is not
    # this game's (a stale port file whose port was taken by another one)
    CONNECT_ERRORS = (OSError, EOFError, AuthenticationError)

    def __init__(self, game_id, authkey, engine_cmd=None, server_reply_timeout=None):
        self.game_id = game_id
        self.authkey = authkey
        self.engine_cmd = engine_cmd
        self.server_reply_timeout = server_reply_timeout
        stem = os.path.join(tempfile.gettempdir(), f'checkora_engine_{game_id}')
        self.port_path = stem + '.port'
        self.lock_path = stem + '.lock'

    def ask(self, command, timeout):
        """Send one protocol line and return the engine's reply line, or
        None when no engine answered within *timeout* seconds.

        Raises ServerTimeout when the game's server took the request and
        did not answer in time, not even with an error.
        """
        # One request is one line: embedded newlines would make the engine
        # answer twice and put every later reply out of step.
        line = ' '.join(command.split())
        if not line:
            return None
        conn = self._server_connection(timeout)
        if conn is None:
            return self._ask_one_off(line, timeout)
        try:
            conn.send(line)
            if not conn.poll(timeout):
                raise ServerTimeout(f'no reply to {line.split()[0]} in {timeout} s')
            reply = conn.recv()
        except (OSError, EOFError):
            return None  # the server went away in the middle of the request
        finally:
            with contextlib.suppress(OSError):
                conn.close()
        if not isinstance(reply, str):
            return None
        if reply.startswith('ERROR:'):
            logger.warning('Chess engine server gave no reply to %s: %s', line.split()[0], reply)
            return None
        return reply

    def shutdown(self, wait):
        """Ask the game's server to stop; True when it confirmed.

        The server removes its own port file. One that is busy or stuck
        cannot take the request and is left to its idle timeout.
        """
        stopped = False
        address = self._server_address()
        if address:
            conn = None
            try:
                conn = connect(address, self.authkey, wait)
                conn.send('SHUTDOWN')
                stopped = bool(conn.poll(wait)) and conn.recv() == 'OK'
            except (TimeoutError,) + self.CONNECT_ERRORS:
                pass
            finally:
                if conn is not None:
                    with contextlib.suppress(OSError):
                        conn.close()

        proc = _server_procs.pop(self.game_id, None)
        if proc is not None:
            try:
                if stopped:
                    proc.wait(timeout=wait)  # reap it, so it does not stay behind as a zombie
                elif proc.poll() is None:
                    _server_procs[self.game_id] = proc
            except subprocess.TimeoutExpired:
                _server_procs[self.game_id] = proc
        return stopped

    def _server_address(self):
        try:
            with open(self.port_path) as handle:
                return ('127.0.0.1', int(handle.read().strip()))
        except (OSError, ValueError):
            return None

    def _server_connection(self, timeout):
        """A connection to the game's server, started first if there is
        none. None when there is no server to be had in time."""
        global _retry_at
        address = self._server_address()
        if address:
            try:
                return connect(address, self.authkey, timeout)
            except TimeoutError:
                # The server is busy with another request for this game; a
                # second server would not help.
                return None
            except self.CONNECT_ERRORS:
                pass  # the port file of a server that is gone

        if time.monotonic() < _retry_at:
            return None
        with contextlib.suppress(OSError):
            if time.time() - os.path.getmtime(self.lock_path) > STALE_LOCK_SECONDS:
                os.unlink(self.lock_path)
        deadline = time.monotonic() + SERVER_START_SECONDS
        try:
            os.close(os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except OSError:
            # Another request is starting the server
            return self._wait_for_server(deadline, None)

        try:
            proc = self._start_server()
            conn = self._wait_for_server(deadline, proc) if proc else None
        finally:
            with contextlib.suppress(OSError):
                os.unlink(self.lock_path)
        if conn is None:
            logger.warning(
                'Chess engine server did not start; using one engine process '
                'per request for the next %s s.', RETRY_SECONDS)
            _retry_at = time.monotonic() + RETRY_SECONDS
        return conn

    def _start_server(self):
        """Start the game's server; returns its Popen, or None."""
        # A port file still here belongs to a server that is gone
        with contextlib.suppress(OSError):
            os.unlink(self.port_path)
        _reap_servers()
        try:
            proc = subprocess.Popen(
                [sys.executable, SERVER_SCRIPT, self.port_path,
                 json.dumps(self.engine_cmd), str(self.server_reply_timeout)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=dict(os.environ, **{AUTHKEY_ENV: self.authkey.hex()}),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
        except OSError as exc:
            logger.warning('Could not start the chess engine server: %s', exc)
            return None
        _server_procs[self.game_id] = proc
        return proc

    def _wait_for_server(self, deadline, proc):
        """Connect to the server once its port file is there.

        Gives up at *deadline*, when *proc* (the server this request
        started) has exited, or, while another request is starting the
        server (*proc* is None), once that request is done.
        """
        delay = 0.01
        while True:
            others_done = proc is None and not os.path.exists(self.lock_path)
            address = self._server_address()
            if address:
                with contextlib.suppress((TimeoutError,) + self.CONNECT_ERRORS):
                    return connect(address, self.authkey, max(0.1, deadline - time.monotonic()))
            if others_done or time.monotonic() >= deadline or (proc is not None and proc.poll() is not None):
                return None
            time.sleep(delay)
            delay = min(delay * 2, 0.1)

    def _ask_one_off(self, line, timeout):
        """Answer the request with an engine process started for it alone."""
        name = line.split()[0]
        try:
            proc = subprocess.Popen(
                self.engine_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
        except OSError as exc:
            logger.warning('Failed to start chess engine while handling %s: %s', name, exc)
            return None
        try:
            stdout, stderr = proc.communicate(input=line + '\n', timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate()
            logger.warning('Chess engine timed out while handling %s. stderr: %s',
                           name, (stderr or '').strip())
            return None
        if stderr:
            logger.warning('Chess engine wrote to stderr while handling %s: %s', name, stderr.strip())
        return stdout.strip() or None
