import os
import sys
import subprocess
import tempfile
import json
import queue
import signal
import socket
import threading
from multiprocessing import AuthenticationError
from multiprocessing.connection import Listener

# Exit after this many seconds without a request. An abandoned game should
# not keep a server and an engine process alive for long; starting a new
# pair for a returning player takes a fraction of a second.
IDLE_TIMEOUT = 60.0
# A client that has connected must send its command within this time.
RECV_TIMEOUT = 5.0
# The engine must answer a command within this time (argv[4] overrides it).
REPLY_TIMEOUT = 15.0


def main():
    if len(sys.argv) < 3:
        print("Usage: persistent_server.py <game_id> <engine_cmd_json> "
              "[authkey_hex] [reply_timeout_seconds]")
        sys.exit(1)

    game_id = sys.argv[1]
    engine_cmd = json.loads(sys.argv[2])
    authkey = bytes.fromhex(sys.argv[3]) if len(sys.argv) > 3 else None
    reply_timeout = REPLY_TIMEOUT
    if len(sys.argv) > 4:
        try:
            reply_timeout = float(sys.argv[4])
        except ValueError:
            pass

    # Bind to loopback port 0 to get an OS-assigned free port (TCP/IP AF_INET)
    try:
        listener = Listener(('127.0.0.1', 0), family='AF_INET',
                            authkey=authkey)
    except Exception as e:
        print(f"Failed to start listener: {e}", file=sys.stderr)
        sys.exit(1)

    port = listener.address[1]

    # Write port file
    port_path = os.path.join(tempfile.gettempdir(),
                             f'checkora_engine_{game_id}.port')
    try:
        with open(port_path, 'w') as f:
            f.write(str(port))
    except Exception as e:
        print(f"Failed to write port file: {e}", file=sys.stderr)
        listener.close()
        sys.exit(1)

    # Write PID file for integration testing / verification
    pid_path = os.path.join(tempfile.gettempdir(),
                            f'checkora_engine_{game_id}.pid')
    try:
        with open(pid_path, 'w') as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    proc = None
    replies = None

    def pump(stream, lines):
        # readline() on the engine's pipe cannot time out, so a thread
        # reads it and the main loop waits on a queue instead.
        try:
            for line in stream:
                lines.put(line)
        except (OSError, ValueError):
            pass
        lines.put('')  # the engine closed its stdout

    def start_engine():
        nonlocal proc, replies
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        proc = subprocess.Popen(
            engine_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,  # line buffered
        )
        replies = queue.Queue()
        threading.Thread(target=pump, args=(proc.stdout, replies),
                         daemon=True).start()

    def ask(cmd_to_send):
        """Send one command line. Returns the reply line, '' when the
        engine has died, or None when it did not answer in time."""
        # Drop anything left over from an earlier command
        while True:
            try:
                replies.get_nowait()
            except queue.Empty:
                break
        proc.stdin.write(cmd_to_send)
        proc.stdin.flush()
        try:
            return replies.get(timeout=reply_timeout)
        except queue.Empty:
            return None

    def stop(signum, frame):
        # Leave through the finally block below so the engine is stopped too.
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, stop)
    except (ValueError, OSError):
        pass

    try:
        start_engine()
    except Exception as e:
        print(f"Failed to start engine: {e}", file=sys.stderr)
        listener.close()
        try:
            os.unlink(port_path)
            os.unlink(pid_path)
        except OSError:
            pass
        sys.exit(1)

    try:
        listener._listener._socket.settimeout(IDLE_TIMEOUT)
    except Exception:
        pass

    failed_accepts = 0
    try:
        while True:
            try:
                conn = listener.accept()
            except (TimeoutError, socket.timeout):
                # No request for IDLE_TIMEOUT seconds
                break
            except (OSError, EOFError, AuthenticationError):
                # A peer that dropped or failed the handshake must not take
                # the server down, but a broken listening socket must.
                failed_accepts += 1
                if failed_accepts > 20:
                    break
                continue
            failed_accepts = 0

            try:
                if not conn.poll(RECV_TIMEOUT):
                    # Connected but silent: do not let it block the others
                    continue
                msg = conn.recv()
                if msg == "SHUTDOWN":
                    conn.send("OK")
                    conn.close()
                    break

                # One request is one line: embedded newlines would make the
                # engine answer twice and put every later reply out of step.
                cmd_to_send = " ".join(msg.split()) + "\n"
                if cmd_to_send == "\n":
                    conn.send("ERROR: Empty command")
                    continue

                # Check if subprocess is still running, if not restart it
                if proc.poll() is not None:
                    start_engine()

                # Write command to engine's stdin and read the response
                response = ask(cmd_to_send)
                if response == '':
                    # Engine closed stdout/died, try to restart and retry once
                    start_engine()
                    response = ask(cmd_to_send)

                if response is None:
                    # A stuck engine would block every later request for
                    # this game; replace it.
                    start_engine()
                    res_msg = "ERROR: Engine timed out"
                else:
                    res_msg = (response.strip() if response
                               else "ERROR: Engine terminated")
                conn.send(res_msg)
            except Exception as e:
                try:
                    conn.send(f"ERROR: {str(e)}")
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    finally:
        listener.close()
        for path in (port_path, pid_path):
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                pass


if __name__ == '__main__':
    main()
