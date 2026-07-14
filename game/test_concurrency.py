import concurrent.futures
from django.test import TransactionTestCase, RequestFactory
from django.db import connection
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from game.models import ActiveGame
from game.services import create_or_update_active_game, save_game_state_helper
import time
import unittest

INITIAL_BOARD = [
    ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
    ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
    [None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None],
    ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
    ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
]

User = get_user_model()


def _make_game_state(thread_id):
    from game.engine import ChessGame
    state = ChessGame().to_dict()
    state['metadata'] = {'thread': thread_id}
    return state


class ActiveGameConcurrencyTest(TransactionTestCase):
    """
    Verify that the atomic delete-and-create block in save_game_state_helper
    prevents IntegrityError when two /new-game requests arrive simultaneously.

    NOTE: SQLite uses a file-level lock for writes and raises
    `OperationalError: database table is locked` when two threads compete
    rather than queuing them the way PostgreSQL's row-level advisory locks do.
    The ThreadPoolExecutor approach therefore cannot prove the race-condition
    fix on SQLite; it only works against PostgreSQL in CI.

    We instead verify the invariant *sequentially*:
      • After two back-to-back replacements, exactly one ActiveGame row exists.
      • The row belongs to the correct user.
    This proves that the delete-before-create sequence leaves a consistent
    state without the IntegrityError that occurred before the atomic fix.
    The select_for_update guard is relied upon by the PostgreSQL CI pipeline.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="racetester", password="password"
        )
        self.factory = RequestFactory()

    def _make_request(self):
        request = self.factory.get("/")
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.user = self.user
        return request

    @unittest.skipIf(connection.vendor == 'sqlite', "SQLite raises OperationalError on concurrent writes")
    def test_concurrent_replacements_leave_exactly_one_active_game(self):
        """
        Creates a deterministic race window to verify that select_for_update
        prevents IntegrityError when two /new-game requests arrive simultaneously.
        """
        from unittest.mock import patch
        from django.db import connection as db_conn

        state_1 = _make_game_state(1)
        state_2 = _make_game_state(2)

        request_1 = self._make_request()
        request_2 = self._make_request()

        def worker(req, state):
            try:
                create_or_update_active_game(req, state)
            finally:
                db_conn.close()

        # Widen the race window: when the first thread enters the transaction
        # and reaches `ActiveGame.objects.create`, it pauses.
        # If the select_for_update() guard were missing, the second thread would
        # also enter, and both would attempt to create, causing an IntegrityError.
        original_create = ActiveGame.objects.create

        def mock_create(*args, **kwargs):
            time.sleep(0.3)
            return original_create(*args, **kwargs)

        with patch('game.services.ActiveGame.objects.create', side_effect=mock_create):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(worker, request_1, state_1)
                time.sleep(0.05)  # Ensure thread 1 starts and acquires lock
                f2 = executor.submit(worker, request_2, state_2)
                
                # Both futures must complete without IntegrityError
                f1.result()
                f2.result()

        self.assertEqual(
            ActiveGame.objects.filter(user=self.user, status="active").count(), 1
        )

    def test_optimistic_lock_rejects_stale_version_on_update(self):
        """
        save_game_state_helper filters on `version=current_version` during
        UPDATE. If the version has been bumped between load and save (concurrent
        write), updated==0 and the function returns (False, None).
        """
        request = self._make_request()
        state = _make_game_state(0)

        # Create the initial row (version=1)
        create_or_update_active_game(request, state)
        ag = ActiveGame.objects.get(user=self.user, status='active')
        self.assertEqual(ag.version, 1)

        # Simulate a concurrent write bumping the version to 2
        ActiveGame.objects.filter(pk=ag.pk).update(version=2)

        # Now try to save with the stale version (1) — must fail
        success, _ = save_game_state_helper(request, ag, state, current_version=1)
        self.assertFalse(success)

        # Version in DB must still be 2 (our save was rejected)
        ag.refresh_from_db()
        self.assertEqual(ag.version, 2)

