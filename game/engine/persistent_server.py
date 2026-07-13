import os
import sys
import subprocess
import tempfile
import json
from multiprocessing.connection import Listener


def main():
    if len(sys.argv) < 3:
        print("Usage: persistent_server.py <game_id> <engine_cmd_json> "
              "[authkey_hex]")
        sys.exit(1)

    game_id = sys.argv[1]
    engine_cmd = json.loads(sys.argv[2])
    authkey = bytes.fromhex(sys.argv[3]) if len(sys.argv) > 3 else None

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

    def start_engine():
        nonlocal proc
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=1)
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

    inactivity_timeout = 300.0  # 5 minutes of no activity
    try:
        listener._listener._socket.settimeout(inactivity_timeout)
    except Exception:
        pass

    try:
        while True:
            try:
                conn = listener.accept()
            except (TimeoutError, OSError):
                # Socket timeout (inactivity) or socket was closed
                break

            try:
                msg = conn.recv()
                if msg == "SHUTDOWN":
                    conn.send("OK")
                    conn.close()
                    break

                # Check if subprocess is still running, if not restart it
                if proc.poll() is not None:
                    start_engine()

                # Write command to engine's stdin
                cmd_to_send = msg.strip() + "\n"
                proc.stdin.write(cmd_to_send)
                proc.stdin.flush()

                # Read response
                response = proc.stdout.readline()
                if not response:
                    # Engine closed stdout/died, try to restart and retry once
                    start_engine()
                    proc.stdin.write(cmd_to_send)
                    proc.stdin.flush()
                    response = proc.stdout.readline()

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
