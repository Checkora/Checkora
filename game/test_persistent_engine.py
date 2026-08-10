import os
import time
import tempfile
from unittest import mock
from django.test import TestCase
from game.engine import ChessGame


class PersistentEngineTest(TestCase):
    def setUp(self):
        self.temp_files_to_clean = []

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

    def test_persistent_server_spawning_once(self):
        """Test that call_engine spawns the server only once (with authkey)."""
        game = ChessGame()
        port_path = os.path.join(tempfile.gettempdir(),
                                 f'checkora_engine_{game.game_id}.port')
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

    def test_cleanup_engine_sends_shutdown(self):
        """Test that cleanup_engine sends a SHUTDOWN command."""
        game = ChessGame()

        port_path = os.path.join(tempfile.gettempdir(),
                                 f'checkora_engine_{game.game_id}.port')
        self.temp_files_to_clean.append(port_path)
        with open(port_path, 'w') as f:
            f.write("9999")

        mock_client_instance = mock.MagicMock()
        mock_client_instance.recv.return_value = "OK"

        with mock.patch('multiprocessing.connection.Client',
                        return_value=mock_client_instance) as mock_client:
            game.cleanup_engine()

            # Verify client was created to connect to IPC
            mock_client.assert_called_once()

            # Verify SHUTDOWN was sent
            mock_client_instance.send.assert_called_once_with("SHUTDOWN")
            mock_client_instance.close.assert_called_once()

    def test_cleanup_engine_on_game_over(self):
        """Test that cleanup_engine triggers on terminal status change."""
        game = ChessGame()

        with mock.patch.object(game, 'cleanup_engine') as mock_cleanup:
            # Set game status to terminal state, triggering setter
            game.game_status = 'checkmate'
            mock_cleanup.assert_called_once()

    def test_integration_engine_process_reused(self):
        """Integration test using python fallback to prove process reuse."""
        game = ChessGame()

        # Ensure we use the python engine fallback
        python_engine_path = os.path.join(ChessGame.ENGINE_DIR, 'main.py')

        # Dummy position command
        dummy_board = 'k' + '.' * 62 + 'K'
        cmd = f"STATUS {dummy_board} - white -1 -1"

        # Register generated temp files for clean up
        t_dir = tempfile.gettempdir()
        self.temp_files_to_clean.append(
            os.path.join(t_dir, f'checkora_engine_{game.game_id}.port')
        )
        self.temp_files_to_clean.append(
            os.path.join(t_dir, f'checkora_engine_{game.game_id}.pid')
        )

        with mock.patch.object(game, '_resolve_engine_path',
                               return_value=python_engine_path):
            # Call engine first time
            resp1 = game._call_engine(cmd)
            self.assertIsNotNone(resp1)

            # Read PID of the spawned persistent_server.py
            pid_path = os.path.join(tempfile.gettempdir(),
                                    f'checkora_engine_{game.game_id}.pid')
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

            # Explicitly clean up
            game.cleanup_engine()

            # Verify server shut down and PID file removed
            self.assertFalse(os.path.exists(pid_path),
                             "PID file should be deleted after shutdown")

    def test_stale_lock_cleanup(self):
        """Test that a stale lock file is automatically unlinked."""
        game = ChessGame()
        lock_path = os.path.join(tempfile.gettempdir(),
                                 f'checkora_engine_{game.game_id}.lock')
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
            mock_popen.return_value = mock_proc

            def popen_side_effect(*args, **kwargs):
                port_path = os.path.join(
                    tempfile.gettempdir(),
                    f'checkora_engine_{game.game_id}.port'
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
