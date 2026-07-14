import os
import time
import tempfile
import hashlib
from unittest import mock
from django.test import TestCase
from django.conf import settings
from game.engine import ChessGame


class PersistentEngineTest(TestCase):
    def setUp(self):
        self.temp_files_to_clean = []
        self.pool_authkey = hashlib.sha256(settings.SECRET_KEY.encode()).digest()

    def tearDown(self):
        # Clean up any files created during tests
        for path in self.temp_files_to_clean:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def test_game_id_generation(self):
        """Test that ChessGame generates a unique game_id on creation."""
        game1 = ChessGame()
        game2 = ChessGame()
        self.assertIsNotNone(game1.game_id)
        self.assertIsNotNone(game2.game_id)
        self.assertNotEqual(game1.game_id, game2.game_id)

    def test_game_id_serialization(self):
        """Test game_id serialization/deserialization with authkey."""
        game = ChessGame()
        game_id = game.game_id
        authkey_hex = game.authkey.hex()

        data = game.to_dict()
        self.assertEqual(data['game_id'], game_id)
        self.assertEqual(data['authkey'], authkey_hex)

        restored = ChessGame.from_dict(data)
        self.assertEqual(restored.game_id, game_id)
        self.assertEqual(restored.authkey, game.authkey)

    @mock.patch('random.randint', return_value=0)
    def test_persistent_server_spawning_once(self, mock_randint):
        """Test that call_engine spawns the server only once (with pool authkey)."""
        game = ChessGame()
        port_path = os.path.join(tempfile.gettempdir(),
                                 'checkora_engine_pool_worker_0.port')
        self.temp_files_to_clean.append(port_path)

        # Mock subprocess.Popen to count spawns
        with mock.patch('subprocess.Popen') as mock_popen:
            # Setup mock Popen to act like the background server spawn
            mock_proc = mock.MagicMock()
            mock_proc.communicate.return_value = ("STATUS OK\n", "")

            def popen_side_effect(*args, **kwargs):
                # When spawning persistent_server.py, write the dummy port file
                if 'persistent_server.py' in str(args[0]):
                    with open(port_path, 'w') as f:
                        f.write("9999")
                return mock_proc

            mock_popen.side_effect = popen_side_effect

            # We want to mock Client to simulate connecting to the server
            mock_client_instance = mock.MagicMock()
            mock_client_instance.recv.return_value = "STATUS OK"

            with mock.patch('multiprocessing.connection.Client', side_effect=[
                Exception("Connection failed"),  # Initial connect fails
                mock_client_instance,            # Retry connect succeeds
                mock_client_instance,            # Second call succeeds
            ]) as mock_client:

                # First call
                resp1 = game._call_engine("STATUS")
                self.assertEqual(resp1, "STATUS OK")

                # Second call
                resp2 = game._call_engine("STATUS")
                self.assertEqual(resp2, "STATUS OK")

                # Verify multiprocessing Client was called
                self.assertEqual(mock_client.call_count, 3)

                # Verify Popen was called once to launch persistent_server.py
                persistent_server_spawns = [
                    call for call in mock_popen.call_args_list
                    if 'persistent_server.py' in str(call)
                ]
                self.assertEqual(len(persistent_server_spawns), 1)

    def test_cleanup_engine_on_game_over(self):
        """Test that cleanup_engine triggers on terminal status change."""
        game = ChessGame()

        with mock.patch.object(game, 'cleanup_engine') as mock_cleanup:
            # Set game status to terminal state, triggering setter
            game.game_status = 'checkmate'
            mock_cleanup.assert_called_once()

    @mock.patch('random.randint', return_value=0)
    def test_integration_engine_process_reused(self, mock_randint):
        """Integration test using python fallback to prove pool process reuse."""
        game = ChessGame()

        # Ensure we use the python engine fallback
        python_engine_path = os.path.join(ChessGame.ENGINE_DIR, 'main.py')

        # Dummy position command
        dummy_board = 'k' + '.' * 62 + 'K'
        cmd = f"STATUS {dummy_board} - white -1 -1"

        # Register generated temp files for clean up
        t_dir = tempfile.gettempdir()
        self.temp_files_to_clean.append(
            os.path.join(t_dir, 'checkora_engine_pool_worker_0.port')
        )
        self.temp_files_to_clean.append(
            os.path.join(t_dir, 'checkora_engine_pool_worker_0.pid')
        )

        with mock.patch.object(game, '_resolve_engine_path',
                               return_value=python_engine_path):
            # Call engine first time
            resp1 = game._call_engine(cmd)
            self.assertIsNotNone(resp1)

            # Read PID of the spawned persistent_server.py
            pid_path = os.path.join(tempfile.gettempdir(),
                                    'checkora_engine_pool_worker_0.pid')
            self.assertTrue(os.path.exists(pid_path),
                            f"PID file {pid_path} should exist")

            with open(pid_path, 'r') as f:
                pid1 = int(f.read().strip())

            # Call engine second time
            resp2 = game._call_engine(cmd)
            self.assertIsNotNone(resp2)

            # Read PID again
            self.assertTrue(os.path.exists(pid_path))
            with open(pid_path, 'r') as f:
                pid2 = int(f.read().strip())

            # Verify PID is identical
            self.assertEqual(pid1, pid2, "Server process should be reused")
            
            # Since cleanup_engine is a no-op, we must manually terminate the process 
            # for the integration test by sending SHUTDOWN
            from multiprocessing.connection import Client
            port_path = os.path.join(tempfile.gettempdir(), 'checkora_engine_pool_worker_0.port')
            if os.path.exists(port_path):
                with open(port_path, 'r') as f:
                    port = int(f.read().strip())
                try:
                    conn = Client(('127.0.0.1', port), family='AF_INET', authkey=self.pool_authkey)
                    conn.send("SHUTDOWN")
                    conn.recv()
                    conn.close()
                except Exception:
                    pass

    @mock.patch('random.randint', return_value=0)
    def test_stale_lock_cleanup(self, mock_randint):
        """Test that a stale lock file is automatically unlinked."""
        game = ChessGame()
        lock_path = os.path.join(tempfile.gettempdir(),
                                 'checkora_engine_pool_worker_0.lock')
        self.temp_files_to_clean.append(lock_path)

        # Create a stale lock file (simulate old creation time)
        with open(lock_path, 'w') as f:
            f.write("99999")

        # Backdate the modification time of the lock file to 10 seconds ago
        past_time = time.time() - 10.0
        os.utime(lock_path, (past_time, past_time))

        # Setup mock Popen and Client to check that it proceeds normally
        with mock.patch('subprocess.Popen') as mock_popen:
            mock_proc = mock.MagicMock()
            mock_proc.communicate.return_value = ("STATUS OK\n", "")
            mock_popen.return_value = mock_proc

            def popen_side_effect(*args, **kwargs):
                port_path = os.path.join(
                    tempfile.gettempdir(),
                    'checkora_engine_pool_worker_0.port'
                )
                with open(port_path, 'w') as f:
                    f.write("9999")
                return mock_proc

            mock_popen.side_effect = popen_side_effect

            mock_client_instance = mock.MagicMock()
            mock_client_instance.recv.return_value = "STATUS OK"

            with mock.patch('multiprocessing.connection.Client',
                            side_effect=[
                                Exception("failed"),
                                mock_client_instance
                            ]) as mock_client:

                resp = game._call_engine("STATUS")
                self.assertEqual(resp, "STATUS OK")

                # The stale lock file should have been deleted
                self.assertFalse(os.path.exists(lock_path),
                                 "Stale lock file should be deleted")
                self.assertEqual(mock_client.call_count, 2)
