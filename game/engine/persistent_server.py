"""Engine server for one game.

game/engine_client.py starts one of these per game. It keeps one engine
process running and answers requests on a loopback port, so that a
request does not pay for starting an engine. Once the engine is up, the
port is written to the port file the client named; the client reads it
to connect.

Usage: persistent_server.py <port_file> <engine_cmd_json> [reply_timeout_seconds]
The connection key is read from the CHECKORA_ENGINE_AUTHKEY environment
variable (hex), which, unlike the command line, other users cannot see.

Each connection carries one request: a protocol line, answered with the
engine's reply line, or "SHUTDOWN", answered with "OK" before the server
exits. A reply that starts with "ERROR:" means the engine gave none: it
did not answer in time or it stopped, and it has been restarted for the
next request.
"""
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
from multiprocessing import AuthenticationError
from multiprocessing.connection import Listener

AUTHKEY_ENV = 'CHECKORA_ENGINE_AUTHKEY'
# Exit after this many seconds without a request. An abandoned game should
# not keep a server and an engine process alive for long; starting a new
# pair for a returning player takes a fraction of a second.
IDLE_TIMEOUT = 60.0
# A client that has connected must send its command within this time.
RECV_TIMEOUT = 5.0
# The engine must answer a command within this time (argv[3] overrides it).
REPLY_TIMEOUT = 15.0
# Failed handshakes in a row after which the listening socket is taken to
# be broken rather than the peers
MAX_FAILED_ACCEPTS = 20


class Engine:
    """The engine process, spoken to one line at a time."""

    def __init__(self, command, reply_timeout):
        self.command = command
        self.reply_timeout = reply_timeout
        self.proc = None
        self.replies = None

    def start(self):
        """Start the engine, replacing the running one."""
        self.stop()
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        # readline() on the pipe cannot time out, so a thread reads it and
        # ask() waits on the queue instead.
        self.replies = queue.Queue()
        threading.Thread(target=self._pump, args=(self.proc.stdout, self.replies), daemon=True).start()

    @staticmethod
    def _pump(stream, lines):
        try:
            for line in stream:
                lines.put(line)
        except (OSError, ValueError):
            pass
        lines.put('')  # the engine closed its stdout

    def stop(self):
        if self.proc is None:
            return
        try:
            self.proc.terminate()
            self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        except OSError:
            pass
        self.proc = None

    def _exchange(self, line):
        """Send one line. Returns the reply, '' when the engine has stopped,
        or None when it did not answer in time."""
        # A reply that came too late for an earlier request must not be
        # taken for the answer to this one.
        while True:
            try:
                self.replies.get_nowait()
            except queue.Empty:
                break
        try:
            self.proc.stdin.write(line + '\n')
            self.proc.stdin.flush()
        except (OSError, ValueError):
            return ''
        try:
            return self.replies.get(timeout=self.reply_timeout)
        except queue.Empty:
            return None

    def ask(self, line):
        """The engine's reply to one protocol line, or an "ERROR:" reply."""
        if self.proc is None or self.proc.poll() is not None:
            self.start()
        reply = self._exchange(line)
        if reply == '':
            # The engine stopped; a new one gets the request once more
            self.start()
            reply = self._exchange(line)
        if reply is None:
            # A stuck engine would hold up every later request for this game
            self.start()
            return 'ERROR: Engine timed out'
        return reply.strip() or 'ERROR: Engine terminated'


def write_port_file(path, port):
    # Written to the side and renamed, so that a client never reads half a file
    partial = f'{path}.{os.getpid()}'
    with open(partial, 'w') as handle:
        handle.write(str(port))
    os.replace(partial, path)


def remove_port_file(path, port):
    """Remove the port file if it still names this server. A new server for
    the same game may have replaced it, and that one's file is not ours to
    remove."""
    try:
        with open(path) as handle:
            if handle.read().strip() != str(port):
                return
        os.unlink(path)
    except OSError:
        pass


def serve(listener, engine):
    """Answer requests until SHUTDOWN, the idle timeout or a broken socket."""
    failed_accepts = 0
    while True:
        try:
            conn = listener.accept()
        except (TimeoutError, socket.timeout):
            return
        except (OSError, EOFError, AuthenticationError):
            # A peer that dropped or failed the handshake must not take the
            # server down, but a broken listening socket must.
            failed_accepts += 1
            if failed_accepts > MAX_FAILED_ACCEPTS:
                return
            continue
        failed_accepts = 0

        try:
            if not conn.poll(RECV_TIMEOUT):
                continue  # connected but silent: do not let it block the others
            message = conn.recv()
            if message == 'SHUTDOWN':
                conn.send('OK')
                return
            # One request is one line: embedded newlines would make the
            # engine answer twice and put every later reply out of step.
            line = ' '.join(message.split()) if isinstance(message, str) else ''
            conn.send(engine.ask(line) if line else 'ERROR: Empty command')
        except Exception as exc:
            # Whatever one request does, the server stays up for the next
            try:
                conn.send(f'ERROR: {exc}')
            except (OSError, ValueError):
                pass
        finally:
            conn.close()


def main():
    authkey_hex = os.environ.get(AUTHKEY_ENV, '')
    if len(sys.argv) < 3 or not authkey_hex:
        print('Usage: persistent_server.py <port_file> <engine_cmd_json> [reply_timeout_seconds]'
              f' with the key in {AUTHKEY_ENV}', file=sys.stderr)
        sys.exit(1)
    port_path = sys.argv[1]
    engine_cmd = json.loads(sys.argv[2])
    reply_timeout = REPLY_TIMEOUT
    if len(sys.argv) > 3:
        try:
            reply_timeout = float(sys.argv[3])
        except ValueError:
            pass

    # Port 0: the system picks a free one
    listener = Listener(('127.0.0.1', 0), family='AF_INET', authkey=bytes.fromhex(authkey_hex))
    port = listener.address[1]
    engine = Engine(engine_cmd, reply_timeout)

    def stop(signum, frame):
        # Leave through the finally block below so the engine is stopped too
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, stop)
    except (ValueError, OSError):
        pass

    try:
        engine.start()
        write_port_file(port_path, port)
        try:
            listener._listener._socket.settimeout(IDLE_TIMEOUT)
        except AttributeError:
            pass  # Listener's internals moved: the server then stops only on SHUTDOWN
        serve(listener, engine)
    except OSError as exc:
        print(f'Engine server failed: {exc}', file=sys.stderr)
        sys.exit(1)
    finally:
        # Before the listener closes: until then no other server can have
        # this port, so a port file naming it is ours.
        remove_port_file(port_path, port)
        listener.close()
        engine.stop()


if __name__ == '__main__':
    main()
