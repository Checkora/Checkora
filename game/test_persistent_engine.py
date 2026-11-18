"""Tests for the per-game engine server and the client that starts it
(game/engine/persistent_server.py, game/engine_client.py)."""
import json
import os
import subprocess
import sys
import tempfile
import time
from unittest import mock

from django.test import SimpleTestCase

from game import engine_client
from game.engine import ChessGame

MAIN_PY = os.path.join(engine_client.ENGINE_DIR, 'main.py')
STATUS = f"STATUS k{'.' * 62}K - white -1 -1"


class ClientTestCase(SimpleTestCase):
    """Keeps the client's per-process state out of the way and removes the
    files a test leaves in the temp directory."""

    def setUp(self):
        for patcher in (
            mock.patch.object(ChessGame, '_resolve_engine_path', return_value=MAIN_PY),
            mock.patch.dict(engine_client._engine_health),
            mock.patch.dict(engine_client._server_procs),
            mock.patch.object(engine_client, '_retry_at', 0.0),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def game(self):
        game = ChessGame()
        self.addCleanup(self.remove_files, game.game_id)
        self.addCleanup(game.cleanup_engine)
        return game

    @staticmethod
    def remove_files(game_id):
        for suffix in ('port', 'lock'):
            path = os.path.join(tempfile.gettempdir(), f'checkora_engine_{game_id}.{suffix}')
            if os.path.exists(path):
                os.unlink(path)

    @staticmethod
    def port_file(game):
        return os.path.join(tempfile.gettempdir(), f'checkora_engine_{game.game_id}.port')


class GameIdTest(SimpleTestCase):

    def test_every_game_has_its_own_id(self):
        self.assertNotEqual(ChessGame().game_id, ChessGame().game_id)

    def test_id_and_key_survive_the_session(self):
        game = ChessGame()
        data = game.to_dict()
        self.assertEqual((data['game_id'], data['authkey']), (game.game_id, game.authkey.hex()))
        restored = ChessGame.from_dict(data)
        self.assertEqual((restored.game_id, restored.authkey), (game.game_id, game.authkey))


class ServerStartTest(ClientTestCase):

    def test_server_is_started_once(self):
        game = self.game()
        port_file = self.port_file(game)
        connection = mock.MagicMock()
        connection.recv.return_value = 'STATUS OK'

        def start(command, **kwargs):
            with open(port_file, 'w') as handle:
                handle.write('1')
            return mock.MagicMock()

        with mock.patch.object(engine_client.subprocess, 'Popen', side_effect=start) as popen, \
                mock.patch.object(engine_client.connection, 'Client',
                                  side_effect=[connection, connection]) as client:
            self.assertEqual(game._call_engine('STATUS'), 'STATUS OK')
            self.assertEqual(game._call_engine('STATUS'), 'STATUS OK')
        self.assertEqual(client.call_count, 2)
        self.assertEqual(popen.call_count, 1)
        command = popen.call_args.args[0]
        self.assertEqual(command[1:3], [engine_client.SERVER_SCRIPT, port_file])
        # the key goes in the environment, where other users cannot read it
        self.assertNotIn(game.authkey.hex(), ' '.join(command))
        self.assertEqual(popen.call_args.kwargs['env'][engine_client.AUTHKEY_ENV], game.authkey.hex())

    def test_stale_lock_is_removed(self):
        game = self.game()
        client = engine_client.EngineClient(game.game_id, game.authkey)
        with open(client.lock_path, 'w') as handle:
            handle.write('left by a request that died')
        past = time.time() - 2 * engine_client.STALE_LOCK_SECONDS
        os.utime(client.lock_path, (past, past))

        def start(command, **kwargs):
            with open(client.port_path, 'w') as handle:
                handle.write('1')
            return mock.MagicMock()

        connection = mock.MagicMock()
        connection.recv.return_value = 'STATUS OK'
        with mock.patch.object(engine_client.subprocess, 'Popen', side_effect=start) as popen, \
                mock.patch.object(engine_client.connection, 'Client', return_value=connection):
            self.assertEqual(game._call_engine('STATUS'), 'STATUS OK')
        self.assertEqual(popen.call_count, 1)
        self.assertFalse(os.path.exists(client.lock_path))

    def test_server_is_reused(self):
        game = self.game()
        self.assertEqual(game._call_engine(STATUS), 'STATUS DRAW')
        with open(self.port_file(game)) as handle:
            port = handle.read()
        proc = engine_client._server_procs[game.game_id]
        self.assertEqual(game._call_engine(STATUS), 'STATUS DRAW')
        with open(self.port_file(game)) as handle:
            self.assertEqual(handle.read(), port)
        self.assertIs(engine_client._server_procs[game.game_id], proc)
        self.assertIsNone(proc.poll())

        game.cleanup_engine()
        self.assertEqual(proc.wait(timeout=5), 0)
        self.assertFalse(os.path.exists(self.port_file(game)))


class ShutdownTest(ClientTestCase):

    def test_cleanup_engine_sends_shutdown(self):
        game = self.game()
        with open(self.port_file(game), 'w') as handle:
            handle.write('1')
        connection = mock.MagicMock()
        connection.recv.return_value = 'OK'
        with mock.patch.object(engine_client.connection, 'Client', return_value=connection) as client:
            game.cleanup_engine()
        client.assert_called_once()
        connection.send.assert_called_once_with('SHUTDOWN')
        connection.close.assert_called_once()

    def test_cleanup_engine_on_game_over(self):
        game = ChessGame()
        with mock.patch.object(game, 'cleanup_engine') as cleanup:
            game.game_status = 'checkmate'
        cleanup.assert_called_once()

    def test_files_stay_when_the_server_did_not_stop(self):
        """A SHUTDOWN that did not get through stops nothing, so the files
        are left alone. They used to be removed anyway; the next request then
        started a second server, whose port file the first one removed when
        it stopped at last."""
        game = self.game()
        self.assertEqual(game._call_engine(STATUS), 'STATUS DRAW')
        with open(self.port_file(game)) as handle:
            port = handle.read()
        server = engine_client._server_procs[game.game_id]
        with mock.patch.object(engine_client, 'connect', side_effect=TimeoutError):
            game.cleanup_engine()
        with open(self.port_file(game)) as handle:
            self.assertEqual(handle.read(), port)
        self.assertEqual(game._call_engine(STATUS), 'STATUS DRAW')
        # The same server answered: no second one was started for this game.
        # (_server_procs is per process, so other tests' servers are in it too.)
        self.assertIs(engine_client._server_procs[game.game_id], server)


class ServerTest(SimpleTestCase):
    """persistent_server.py on its own."""

    SERVER = os.path.join(engine_client.ENGINE_DIR, 'persistent_server.py')

    def start(self, port_file, authkey):
        proc = subprocess.Popen(
            [sys.executable, self.SERVER, port_file, json.dumps([sys.executable, MAIN_PY]), '5'],
            env=dict(os.environ, **{engine_client.AUTHKEY_ENV: authkey.hex()}),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(proc.wait, 10)
        self.addCleanup(proc.kill)
        deadline = time.monotonic() + 10
        while not os.path.exists(port_file):
            self.assertLess(time.monotonic(), deadline, 'the server did not come up')
            self.assertIsNone(proc.poll(), 'the server exited')
            time.sleep(0.02)
        with open(port_file) as handle:
            return proc, ('127.0.0.1', int(handle.read()))

    def request(self, address, authkey, message):
        conn = engine_client.connect(address, authkey, 10)
        try:
            conn.send(message)
            self.assertTrue(conn.poll(10))
            return conn.recv()
        finally:
            conn.close()

    def test_answers_and_stops(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(os.rmdir, folder)
        port_file = os.path.join(folder, 'game.port')
        authkey = os.urandom(16)
        proc, address = self.start(port_file, authkey)
        self.assertEqual(self.request(address, authkey, STATUS), 'STATUS DRAW')
        self.assertEqual(self.request(address, authkey, 'STATUS\nBESTMOVE'), 'ERROR malformed command')
        self.assertEqual(self.request(address, authkey, 'SHUTDOWN'), 'OK')
        self.assertEqual(proc.wait(timeout=10), 0)
        self.assertFalse(os.path.exists(port_file))

    def test_leaves_a_port_file_that_is_not_its_own(self):
        """A server that stops only removes the port file if it still names
        that server; a newer server for the same game may have written it."""
        folder = tempfile.mkdtemp()
        self.addCleanup(os.rmdir, folder)
        port_file = os.path.join(folder, 'game.port')
        self.addCleanup(lambda: os.path.exists(port_file) and os.unlink(port_file))
        authkey = os.urandom(16)
        proc, address = self.start(port_file, authkey)
        with open(port_file, 'w') as handle:
            handle.write('1')   # what a newer server would have written
        self.assertEqual(self.request(address, authkey, 'SHUTDOWN'), 'OK')
        self.assertEqual(proc.wait(timeout=10), 0)
        with open(port_file) as handle:
            self.assertEqual(handle.read(), '1')

    def test_needs_a_key(self):
        env = {key: value for key, value in os.environ.items() if key != engine_client.AUTHKEY_ENV}
        proc = subprocess.run(
            [sys.executable, self.SERVER, os.path.join(tempfile.gettempdir(), 'unused.port'), '[]'],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 1)


class OneOffEngineTest(ClientTestCase):
    """Requests answered without a server."""

    def ask(self, popen):
        game = ChessGame()
        game._analysis_timeout = 1
        with mock.patch.object(engine_client.EngineClient, '_server_connection', return_value=None), \
                mock.patch.object(engine_client.subprocess, 'Popen', popen), \
                self.assertLogs('game.engine_client', level='WARNING') as logs:
            return game._call_engine('STATUS'), logs.output

    def test_stderr_is_logged(self):
        engine = mock.MagicMock()
        engine.communicate.return_value = ('STATUS OK\n', 'diagnostic details\n')
        reply, logs = self.ask(mock.Mock(return_value=engine))
        self.assertEqual(reply, 'STATUS OK')
        self.assertTrue(any('diagnostic details' in line for line in logs))

    def test_timeout_kills_the_engine(self):
        engine = mock.MagicMock()
        engine.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd='engine', timeout=1),
            ('', 'timeout diagnostics\n'),
        ]
        reply, logs = self.ask(mock.Mock(return_value=engine))
        self.assertIsNone(reply)
        engine.kill.assert_called_once()
        self.assertTrue(any('timeout diagnostics' in line for line in logs))

    def test_start_failure_is_logged(self):
        reply, logs = self.ask(mock.Mock(side_effect=OSError('missing binary')))
        self.assertIsNone(reply)
        self.assertTrue(any('missing binary' in line for line in logs))
