import json
import time
from unittest import mock

from django.test import TestCase, Client
from django.contrib.auth.models import User
from .engine import ChessGame
from .models import ActiveGame, GameRecord, GameResult, PlayerRating, UserAchievement
class ResignTest(TestCase):
    """Test the /api/resign/ endpoint."""

    def setUp(self):
        self.client.get('/play/')

    def test_resign_ends_game_as_white(self):
        """Resigning as white should mark game status as resignation."""
        response = self.client.post(
            '/api/resign/',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('game_status', data)
        self.assertEqual(data['game_status'], 'resignation')

    def test_resign_records_correct_winner(self):
        """When white resigns, black should be the winner."""
        response = self.client.post(
            '/api/resign/',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('winner', data)
        self.assertEqual(data['winner'], 'black')

    def test_resign_rejects_get_method(self):
        """GET request to /api/resign/ should return 405."""
        response = self.client.get('/api/resign/')
        self.assertEqual(response.status_code, 405)

    def test_resign_after_game_over_is_rejected(self):
        """Resigning a game that is already over should be rejected."""
        session = self.client.session
        game_data = session['game']
        game_data['game_status'] = 'checkmate'
        session['game'] = game_data
        session.save()

        response = self.client.post(
            '/api/resign/',
            content_type='application/json',
        )
        self.assertIn(response.status_code, [400, 200])
        if response.status_code == 200:
            data = response.json()
            self.assertNotEqual(data.get('game_status'), 'active')

    def test_state_reflects_resignation_after_resign(self):
        """After resigning, /api/state/ should show resignation status."""
        self.client.post('/api/resign/', content_type='application/json')
        state = self.client.get('/api/state/').json()
        self.assertEqual(state['game_status'], 'resignation')


class DrawAIModeTest(TestCase):
    """Test draw offer behaviour in AI mode."""

    def setUp(self):
        self.client.get('/play/')
        self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'ai'}),
            content_type='application/json',
        )

    def test_draw_accept_in_ai_mode_is_refused(self):
        """A draw by agreement does not exist against the engine."""
        response = self.client.post(
            '/api/draw/',
            data=json.dumps({'action': 'accept'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertFalse(GameResult.objects.exists())

    def test_game_goes_on_after_a_refused_draw(self):
        self.client.post(
            '/api/draw/',
            data=json.dumps({'action': 'accept'}),
            content_type='application/json',
        )
        state = self.client.get('/api/state/').json()
        self.assertEqual(state['game_status'], 'active')

    def test_draw_offer_and_decline_still_answer(self):
        for action in ('offer', 'decline'):
            response = self.client.post(
                '/api/draw/',
                data=json.dumps({'action': action}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['success'])


class NewGameEdgeCaseTest(TestCase):
    """Edge cases for /api/new-game/ not covered by NewGameTest."""

    def setUp(self):
        self.client.get('/play/')

    def test_new_game_default_mode_is_pvp(self):
        """Calling /api/new-game/ with no body should default to pvp."""
        response = self.client.post(
            '/api/new-game/',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('mode'), 'pvp')

    def test_new_game_invalid_mode_handled(self):
        """An invalid mode value should not crash the server."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'invalid'}),
            content_type='application/json',
        )
        self.assertIn(response.status_code, [200, 400])

    def test_new_game_rejects_get_method(self):
        """GET on /api/new-game/ should return 405."""
        response = self.client.get('/api/new-game/')
        self.assertEqual(response.status_code, 405)

    def test_new_game_resets_captured_pieces(self):
        """Captured pieces should be empty after starting a new game."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'pvp'}),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['captured_pieces']['white'], [])
        self.assertEqual(data['captured_pieces']['black'], [])

    def test_new_game_board_has_correct_dimensions(self):
        """Board returned by /api/new-game/ should be 8x8."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({'mode': 'pvp'}),
            content_type='application/json',
        )
        board = response.json()['board']
        self.assertEqual(len(board), 8)
        for row in board:
            self.assertEqual(len(row), 8)

    def test_new_game_ai_difficulty_and_bot_names(self):
        """Test that starting an AI game correctly assigns bot names based on difficulty."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai', 'difficulty': 'easy', 'player_color': 'white'
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['black_name'], '♟️ Novice Pawn')
        self.assertEqual(data['difficulty'], 'easy')

        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai', 'difficulty': 'medium', 'player_color': 'white'
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['black_name'], '♗ Tactical Bishop')

        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai', 'difficulty': 'hard', 'player_color': 'white'
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['black_name'], '♜ Grandmaster Rook')

    def test_new_game_ai_invalid_difficulty_fallback(self):
        """Test that invalid difficulty falls back to medium personality."""
        response = self.client.post(
            '/api/new-game/',
            data=json.dumps({
                'mode': 'ai',
                'difficulty': 'invalid_level',
                'player_color': 'white'
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['black_name'], '♗ Tactical Bishop')

    def test_ai_search_depth_mapping(self):
        """Test that the engine properly maps difficulty to search depth."""

        game = ChessGame(difficulty='easy')
        self.assertEqual(game._get_ai_search_depth(), 2)

        game = ChessGame(difficulty='medium')
        self.assertEqual(game._get_ai_search_depth(), 6)

        game = ChessGame(difficulty='hard')
        self.assertEqual(game._get_ai_search_depth(), 10)

        game = ChessGame(difficulty='master')
        self.assertEqual(game._get_ai_search_depth(), 14)

        game = ChessGame(difficulty='invalid_level')
        self.assertEqual(game._get_ai_search_depth(), 6)


class PuzzleStatsTest(TestCase):
    """Test the /api/puzzle-stats/ endpoint."""

    def test_puzzle_stats_returns_streak_fields(self):
        """Response must contain streak and longest_streak fields."""
        response = self.client.get('/api/puzzle-stats/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('streak', data)
        self.assertIn('longest_streak', data)

    def test_puzzle_stats_default_values_are_zero(self):
        """Fresh session should return streak of 0."""
        response = self.client.get('/api/puzzle-stats/')
        data = response.json()
        self.assertEqual(data['streak'], 0)
        self.assertEqual(data['longest_streak'], 0)

    def test_puzzle_stats_accepts_get(self):
        """GET to /api/puzzle-stats/ should return 200."""
        response = self.client.get('/api/puzzle-stats/')
        self.assertEqual(response.status_code, 200)


class SecurityHeadersTest(TestCase):
    """Test HTTP security headers applied by custom middleware."""

    def test_security_headers_present_on_pages(self):
        """Verify headers on standard HTML page responses."""
        response = self.client.get('/play/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Content-Security-Policy', response)
        self.assertIn('Permissions-Policy', response)
        self.assertTrue(response['Content-Security-Policy'].startswith("default-src 'self'"))
        self.assertIn("camera=()", response['Permissions-Policy'])


def post_json(client, url, payload=None):
    return client.post(
        url,
        data=json.dumps(payload if payload is not None else {}),
        content_type='application/json',
    )


E2E4 = {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4}
E7E5 = {'from_row': 1, 'from_col': 4, 'to_row': 3, 'to_col': 4}
MATE_IN_ONE_FEN = "6k1/5ppp/8/8/8/8/5PPP/6KQ w - - 0 1"


def fake_history(plies):
    """Move history entries good enough for PGN generation."""
    return [
        {
            'notation': 'e4', 'piece': 'P', 'from': [6, 4], 'to': [4, 4],
            'captured': None, 'color': 'white' if i % 2 == 0 else 'black',
            'promoted_to': None,
        }
        for i in range(plies)
    ]


class LoggedInGameTestCase(TestCase):
    """Helpers for tests that need a logged-in player and a stored game."""

    def setUp(self):
        self.user = User.objects.create_user(username='player', password='pw-12345678')
        self.client.force_login(self.user)

    def start(self, **options):
        response = post_json(self.client, '/api/new-game/', options)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def edit_game(self, **changes):
        active = ActiveGame.objects.get(user=self.user, status='active')
        state = dict(active.game_state)
        state.update(changes)
        ActiveGame.objects.filter(pk=active.pk).update(game_state=state)

    def rating(self):
        rating = PlayerRating.objects.filter(user=self.user).first()
        return rating.rating if rating else None


class BoardPageKeepsActiveGameTest(LoggedInGameTestCase):
    """Loading /play/ must not replace a logged-in user's game in progress."""

    def test_reload_keeps_moves_for_logged_in_user(self):
        self.start(mode='pvp')
        self.assertTrue(post_json(self.client, '/api/move/', E2E4).json()['valid'])

        self.client.get('/play/')

        state = self.client.get('/api/state/').json()
        self.assertEqual(len(state['move_history']), 1)
        self.assertEqual(state['current_turn'], 'black')

    def test_second_device_keeps_moves(self):
        self.start(mode='pvp')
        post_json(self.client, '/api/move/', E2E4)

        self.client.logout()
        self.client.force_login(self.user)
        self.client.get('/play/')

        active = ActiveGame.objects.get(user=self.user, status='active')
        self.assertEqual(len(active.game_state['move_history']), 1)

    def test_first_visit_still_creates_a_game(self):
        self.client.get('/play/')
        self.assertTrue(
            ActiveGame.objects.filter(user=self.user, status='active').exists()
        )

    def test_anonymous_reload_keeps_the_session_game(self):
        anonymous = Client()
        anonymous.get('/play/')
        post_json(anonymous, '/api/move/', E2E4)
        anonymous.get('/play/')
        self.assertEqual(len(anonymous.get('/api/state/').json()['move_history']), 1)


class StateEndpointDoesNotPauseTest(TestCase):
    """GET /api/state/ after a long think must not leave the game paused."""

    def setUp(self):
        engine_patcher = mock.patch.object(ChessGame, '_call_engine')
        mock_engine = engine_patcher.start()
        mock_engine.side_effect = lambda cmd: (
            'BESTMOVE 6 4 4 4' if cmd.startswith('BEST') else 'STATUS ok'
        )
        self.addCleanup(engine_patcher.stop)
        validate_patcher = mock.patch.object(
            ChessGame, 'validate_move', return_value=(True, 'ok')
        )
        validate_patcher.start()
        self.addCleanup(validate_patcher.stop)

    def _idle(self, seconds):
        session = self.client.session
        game = session['game']
        game['last_ts'] = time.time() - seconds
        session['game'] = game
        session.save()

    def test_idle_state_read_does_not_block_ai(self):
        post_json(self.client, '/api/new-game/', {'mode': 'ai', 'player_color': 'black'})
        self._idle(30)

        state = self.client.get('/api/state/').json()
        self.assertTrue(state['paused'])
        self.assertFalse(self.client.session['game']['paused'])

        reply = post_json(self.client, '/api/ai-move/')
        self.assertEqual(reply.status_code, 200)
        self.assertTrue(reply.json()['valid'])

    def test_idle_state_read_keeps_clock_for_resume(self):
        post_json(self.client, '/api/new-game/', {'mode': 'pvp'})
        self._idle(120)

        state = self.client.get('/api/state/').json()
        self.assertEqual(state['white_time'], 600)

        resumed = post_json(self.client, '/api/resume/').json()
        self.assertTrue(resumed['valid'])
        self.assertEqual(resumed['white_time'], 600)

    def test_idle_state_read_does_not_bump_the_version(self):
        user = User.objects.create_user(username='reader', password='pw-12345678')
        self.client.force_login(user)
        version = post_json(self.client, '/api/new-game/', {'mode': 'pvp'}).json()['version']
        active = ActiveGame.objects.get(user=user)
        state = dict(active.game_state)
        state['last_ts'] = time.time() - 60
        ActiveGame.objects.filter(pk=active.pk).update(game_state=state)

        data = self.client.get('/api/state/').json()

        self.assertTrue(data['paused'])
        self.assertEqual(data['version'], version)
        active.refresh_from_db()
        self.assertFalse(active.game_state['paused'])


class RatingIntegrityTest(LoggedInGameTestCase):
    """The client cannot talk its way into rating points."""

    def test_resigning_for_the_engine_is_ignored(self):
        self.start(mode='ai', player_color='white')

        data = post_json(self.client, '/api/resign/', {'resigning_player': 'black'}).json()

        self.assertTrue(data['valid'])
        self.assertEqual(data['winner'], 'black')
        result = GameResult.objects.get(user=self.user)
        self.assertEqual(result.winner, 'black')
        self.assertEqual(result.end_reason, 'resign')
        self.assertEqual(self.rating(), 1184)
        self.assertFalse(UserAchievement.objects.filter(user=self.user).exists())

    def test_resigning_as_black_against_the_engine(self):
        self.start(mode='ai', player_color='black')
        data = post_json(self.client, '/api/resign/', {'resigning_player': 'white'}).json()
        self.assertEqual(data['winner'], 'white')
        self.assertEqual(self.rating(), 1184)

    def test_two_player_resign_still_names_the_side(self):
        self.start(mode='pvp')
        data = post_json(self.client, '/api/resign/', {'resigning_player': 'black'}).json()
        self.assertEqual(data['winner'], 'white')
        self.assertIsNone(self.rating())

    def test_resign_saves_a_replay_with_the_real_result(self):
        self.start(mode='ai', player_color='black')
        post_json(self.client, '/api/resign/')

        record = GameRecord.objects.get(user=self.user)
        self.assertEqual(record.result, '1-0')
        self.assertEqual(record.termination, 'resignation')
        self.assertIn('[Result "1-0"]', record.pgn)
        self.assertTrue(record.pgn.rstrip().endswith('1-0'))
        self.assertEqual(GameResult.objects.get(user=self.user).replay_record, record)

    def test_draw_against_the_engine_gives_no_points(self):
        self.start(mode='ai')
        for _ in range(3):
            response = post_json(self.client, '/api/draw/', {'action': 'accept'})
            self.assertEqual(response.status_code, 400)

        self.assertFalse(GameResult.objects.exists())
        self.assertIsNone(self.rating())
        self.assertTrue(ActiveGame.objects.filter(user=self.user, status='active').exists())

    def test_two_player_draw_is_recorded_once_with_a_replay(self):
        self.start(mode='pvp')
        first = post_json(self.client, '/api/draw/', {'action': 'accept'})
        second = post_json(self.client, '/api/draw/', {'action': 'accept'})

        self.assertTrue(first.json()['success'])
        self.assertEqual(second.status_code, 400)
        self.assertEqual(GameResult.objects.filter(user=self.user).count(), 1)
        record = GameRecord.objects.get(user=self.user)
        self.assertEqual(record.result, '1/2-1/2')
        self.assertEqual(record.termination, 'agreement')

    def test_draw_on_a_game_left_in_the_session_cannot_be_repeated(self):
        # A game begun before login sits in the session, not in ActiveGame.
        game = ChessGame()
        session = self.client.session
        session['game'] = game.to_dict()
        session.save()

        first = post_json(self.client, '/api/draw/', {'action': 'accept'})
        second = post_json(self.client, '/api/draw/', {'action': 'accept'})

        self.assertTrue(first.json()['success'])
        self.assertEqual(second.status_code, 400)
        self.assertEqual(GameResult.objects.filter(user=self.user).count(), 1)
        self.assertNotIn('game', self.client.session)

    def test_moving_the_engines_pieces_is_refused(self):
        self.start(mode='ai', player_color='white')
        self.assertTrue(post_json(self.client, '/api/move/', E2E4).json()['valid'])

        response = post_json(self.client, '/api/move/', E7E5)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['valid'])
        state = self.client.get('/api/state/').json()
        self.assertEqual(len(state['move_history']), 1)
        self.assertEqual(state['current_turn'], 'black')

    def test_engine_does_not_move_for_the_player(self):
        self.start(mode='ai', player_color='white')
        response = post_json(self.client, '/api/ai-move/')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['valid'])
        self.assertEqual(self.client.get('/api/state/').json()['move_history'], [])

    def test_two_player_game_moves_both_sides(self):
        self.start(mode='pvp')
        self.assertTrue(post_json(self.client, '/api/move/', E2E4).json()['valid'])
        self.assertTrue(post_json(self.client, '/api/move/', E7E5).json()['valid'])

    def test_game_from_a_custom_position_is_unrated(self):
        data = self.start(mode='ai', player_color='white', fen=MATE_IN_ONE_FEN)
        self.assertFalse(data['rated'])
        self.assertFalse(self.client.get('/api/state/').json()['rated'])

        post_json(self.client, '/api/resign/')

        result = GameResult.objects.get(user=self.user)
        self.assertFalse(result.rated)
        self.assertIsNone(self.rating())

    @mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok'))
    @mock.patch.object(ChessGame, '_call_engine')
    def test_win_from_a_custom_position_gives_nothing(self, mock_engine, _validate):
        mock_engine.side_effect = lambda cmd: (
            'STATUS checkmate' if cmd.startswith('STATUS') else 'NOTATION Qa8'
        )
        self.start(mode='ai', player_color='white', fen=MATE_IN_ONE_FEN)

        data = post_json(self.client, '/api/move/', {
            'from_row': 7, 'from_col': 7, 'to_row': 0, 'to_col': 0,
        }).json()

        self.assertEqual(data['game_status'], 'checkmate')
        result = GameResult.objects.get(user=self.user)
        self.assertEqual(result.winner, 'white')
        self.assertFalse(result.rated)
        self.assertIsNone(self.rating())
        self.assertFalse(UserAchievement.objects.filter(user=self.user).exists())

    def test_game_from_the_normal_start_is_rated(self):
        start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        for options in ({'mode': 'ai'}, {'mode': 'ai', 'fen': start}):
            self.assertTrue(self.start(**options)['rated'])
        self.assertFalse(self.start(mode='pvp')['rated'])

    @mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok'))
    @mock.patch.object(ChessGame, '_call_engine')
    def test_rated_win_still_counts(self, mock_engine, _validate):
        mock_engine.side_effect = lambda cmd: (
            'STATUS checkmate' if cmd.startswith('STATUS') else 'NOTATION e4'
        )
        self.start(mode='ai', player_color='white')

        post_json(self.client, '/api/move/', E2E4)

        self.assertEqual(self.rating(), 1216)
        self.assertTrue(GameResult.objects.get(user=self.user).rated)
        self.assertTrue(UserAchievement.objects.filter(
            user=self.user, achievement__code='FIRST_WIN'
        ).exists())


class AbandonedGameTest(LoggedInGameTestCase):
    """Starting over in the middle of a rated game counts as resigning it."""

    def test_new_game_forfeits_a_rated_game_under_way(self):
        self.start(mode='ai', player_color='white')
        self.edit_game(move_history=fake_history(6))

        data = self.start(mode='ai')

        self.assertTrue(data['forfeited'])
        result = GameResult.objects.get(user=self.user)
        self.assertEqual((result.winner, result.end_reason), ('black', 'resign'))
        self.assertEqual(len(result.moves), 6)
        self.assertEqual(self.rating(), 1184)
        self.assertEqual(ActiveGame.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.client.get('/api/state/').json()['move_history'], [])

    def test_game_already_lost_on_time_by_the_engine_is_not_a_resignation(self):
        self.start(mode='ai', player_color='white')
        self.edit_game(
            move_history=fake_history(7), current_turn='black',
            black_time=5, last_ts=time.time() - 30,
        )

        self.assertTrue(self.start(mode='ai')['forfeited'])

        result = GameResult.objects.get(user=self.user)
        self.assertEqual((result.winner, result.end_reason), ('white', 'timeout'))
        self.assertFalse(result.rated)
        self.assertIsNone(self.rating())

    def test_short_game_is_just_replaced(self):
        self.start(mode='ai')
        self.edit_game(move_history=fake_history(4))

        self.assertFalse(self.start(mode='ai')['forfeited'])
        self.assertFalse(GameResult.objects.exists())
        self.assertIsNone(self.rating())

    def test_unrated_games_are_just_replaced(self):
        self.start(mode='pvp')
        self.edit_game(move_history=fake_history(8))
        self.assertFalse(self.start(mode='ai')['forfeited'])

        self.start(mode='ai', fen=MATE_IN_ONE_FEN)
        self.edit_game(move_history=fake_history(8))
        self.assertFalse(self.start(mode='pvp')['forfeited'])

        self.assertFalse(GameResult.objects.exists())

    def test_bad_fen_does_not_cost_the_game_in_progress(self):
        self.start(mode='ai', white_name='Keeper')
        self.edit_game(move_history=fake_history(6))

        response = post_json(self.client, '/api/new-game/', {'mode': 'ai', 'fen': 'not a fen'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(GameResult.objects.exists())
        active = ActiveGame.objects.get(user=self.user, status='active')
        self.assertEqual(len(active.game_state['move_history']), 6)
        self.assertEqual(self.client.session['white_name'], 'Keeper')


class LossOnTimeTest(LoggedInGameTestCase):
    """A clock that runs out ends the game and is recorded."""

    def test_claim_is_refused_while_the_clock_is_running(self):
        self.start(mode='ai', player_color='white')

        response = post_json(self.client, '/api/timeout/')

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['valid'])
        self.assertEqual(data['white_time'], 600)
        self.assertFalse(GameResult.objects.exists())

    def test_claim_needs_a_game(self):
        self.assertEqual(post_json(self.client, '/api/timeout/').status_code, 400)

    def test_player_losing_on_time_is_a_rated_loss(self):
        self.start(mode='ai', player_color='white')
        self.edit_game(white_time=0)

        data = post_json(self.client, '/api/timeout/').json()

        self.assertTrue(data['valid'])
        self.assertEqual(data['game_status'], 'timeout')
        self.assertEqual(data['winner'], 'black')
        result = GameResult.objects.get(user=self.user)
        self.assertEqual((result.winner, result.end_reason), ('black', 'timeout'))
        self.assertTrue(result.rated)
        self.assertEqual(self.rating(), 1184)
        self.assertFalse(ActiveGame.objects.filter(user=self.user).exists())
        record = GameRecord.objects.get(user=self.user)
        self.assertEqual((record.result, record.termination), ('0-1', 'timeout'))
        self.assertIn('[Result "0-1"]', record.pgn)

    def test_server_clock_decides_not_the_stored_number(self):
        self.start(mode='ai', player_color='white')
        self.edit_game(white_time=30, last_ts=time.time() - 45)

        data = post_json(self.client, '/api/timeout/').json()

        self.assertTrue(data['valid'])
        self.assertEqual(data['white_time'], 0)

    def test_engine_running_out_of_time_is_not_rated(self):
        self.start(mode='ai', player_color='white')
        self.edit_game(black_time=0, current_turn='black')

        data = post_json(self.client, '/api/timeout/').json()

        self.assertEqual(data['winner'], 'white')
        result = GameResult.objects.get(user=self.user)
        self.assertEqual(result.end_reason, 'timeout')
        self.assertFalse(result.rated)
        self.assertIsNone(self.rating())

    def test_claim_cannot_be_repeated(self):
        self.start(mode='ai', player_color='white')
        self.edit_game(white_time=0)
        post_json(self.client, '/api/timeout/')

        self.assertEqual(post_json(self.client, '/api/timeout/').status_code, 400)
        self.assertEqual(GameResult.objects.count(), 1)

    def test_move_after_the_flag_fell_ends_the_game(self):
        self.start(mode='pvp')
        self.edit_game(white_time=20, last_ts=time.time() - 60)

        data = post_json(self.client, '/api/move/', E2E4).json()

        self.assertFalse(data['valid'])
        self.assertEqual(data['game_status'], 'timeout')
        self.assertEqual(data['winner'], 'black')
        result = GameResult.objects.get(user=self.user)
        self.assertEqual((result.winner, result.end_reason), ('black', 'timeout'))
        self.assertFalse(ActiveGame.objects.filter(user=self.user).exists())

    def test_state_read_notices_the_flag(self):
        self.start(mode='pvp')
        self.edit_game(white_time=3, last_ts=time.time() - 6)

        data = self.client.get('/api/state/').json()

        self.assertEqual(data['game_status'], 'timeout')
        self.assertEqual(data['winner'], 'black')
        self.assertEqual(GameResult.objects.get(user=self.user).end_reason, 'timeout')

    def test_anonymous_loss_on_time_is_recorded_without_a_user(self):
        anonymous = Client()
        post_json(anonymous, '/api/new-game/', {'mode': 'pvp'})
        session = anonymous.session
        game = session['game']
        game['black_time'] = 0
        game['current_turn'] = 'black'
        session['game'] = game
        session.save()

        data = post_json(anonymous, '/api/timeout/').json()

        self.assertEqual(data['winner'], 'white')
        self.assertEqual(anonymous.get('/api/state/').json()['game_status'], 'timeout')
        self.assertEqual(GameResult.objects.get().user, None)


class EngineAnswerTest(LoggedInGameTestCase):
    """What ai_move does when the engine has no move to give."""

    def _engine(self, best, status):
        patcher = mock.patch.object(ChessGame, '_call_engine')
        engine = patcher.start()
        engine.side_effect = lambda cmd: (
            best if cmd.startswith('BEST') else status if cmd.startswith('STATUS') else None
        )
        self.addCleanup(patcher.stop)
        book = mock.patch.object(ChessGame, 'get_opening_book_move', return_value=None)
        book.start()
        self.addCleanup(book.stop)

    def test_silent_engine_is_a_503_and_the_game_goes_on(self):
        self._engine(None, None)
        self.start(mode='ai', player_color='black')

        response = post_json(self.client, '/api/ai-move/')

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['valid'])
        self.assertFalse(GameResult.objects.exists())
        self.assertIsNone(self.rating())
        active = ActiveGame.objects.get(user=self.user, status='active')
        self.assertEqual(active.game_state['game_status'], 'active')

    def test_engine_without_a_move_in_a_live_position_is_a_503(self):
        self._engine('BESTMOVE NONE', 'STATUS ok')
        self.start(mode='ai', player_color='black')
        self.assertEqual(post_json(self.client, '/api/ai-move/').status_code, 503)
        self.assertFalse(GameResult.objects.exists())

    def test_engine_that_is_mated_loses(self):
        self._engine('BESTMOVE NONE', 'STATUS checkmate')
        self.start(mode='ai', player_color='black')

        data = post_json(self.client, '/api/ai-move/').json()

        self.assertTrue(data['valid'])
        self.assertEqual(data['game_status'], 'checkmate')
        result = GameResult.objects.get(user=self.user)
        self.assertEqual((result.winner, result.end_reason), ('black', 'checkmate'))
        self.assertTrue(GameRecord.objects.filter(user=self.user, result='0-1').exists())
        self.assertFalse(ActiveGame.objects.filter(user=self.user).exists())

    def test_stalemated_engine_is_a_draw(self):
        self._engine('BESTMOVE NONE', 'STATUS stalemate')
        self.start(mode='ai', player_color='black')

        data = post_json(self.client, '/api/ai-move/').json()

        self.assertEqual(data['game_status'], 'stalemate')
        self.assertEqual(data['draw_reason'], 'stalemate')
        result = GameResult.objects.get(user=self.user)
        self.assertEqual((result.winner, result.end_reason), ('draw', 'stalemate'))

    def test_finished_game_takes_no_engine_move(self):
        anonymous = Client()
        post_json(anonymous, '/api/new-game/', {'mode': 'ai', 'player_color': 'black'})
        session = anonymous.session
        game = session['game']
        game['game_status'] = 'checkmate'
        session['game'] = game
        session.save()

        response = post_json(anonymous, '/api/ai-move/')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(GameResult.objects.exists())


class OpeningLineReplyTest(TestCase):
    """The engine follows the chosen opening line past its first move."""

    @mock.patch.object(ChessGame, 'validate_move', return_value=(True, 'ok'))
    @mock.patch.object(ChessGame, 'get_valid_moves')
    @mock.patch.object(ChessGame, 'get_ai_move')
    @mock.patch.object(ChessGame, '_call_engine')
    def test_second_book_move_is_played(self, mock_engine, mock_ai, mock_valid, _validate):
        mock_engine.side_effect = lambda cmd: (
            'STATUS ok' if cmd.startswith('STATUS') else 'NOTATION x'
        )
        # Every book move is offered as legal.
        mock_valid.side_effect = lambda row, col: [
            {'row': r, 'col': c} for r in range(8) for c in range(8)
        ]
        post_json(self.client, '/api/new-game/', {
            'mode': 'ai', 'player_color': 'black', 'opening': 'sicilian_defense',
        })

        first = post_json(self.client, '/api/ai-move/').json()
        self.assertEqual(
            [first['ai_move'][k] for k in ('from_row', 'from_col', 'to_row', 'to_col')],
            [6, 4, 4, 4],
        )
        # Black answers with the line's c5.
        post_json(self.client, '/api/move/', {
            'from_row': 1, 'from_col': 2, 'to_row': 3, 'to_col': 2,
        })
        second = post_json(self.client, '/api/ai-move/').json()

        self.assertEqual(
            [second['ai_move'][k] for k in ('from_row', 'from_col', 'to_row', 'to_col')],
            [7, 6, 5, 5],
        )
        self.assertEqual(second['opening'], 'sicilian_defense')
        mock_ai.assert_not_called()

    def test_comment_entry_is_not_an_opening(self):
        from game.services import get_opening_line, get_valid_openings
        self.assertNotIn('_named_lines_comment', get_valid_openings())
        self.assertEqual(get_opening_line('_named_lines_comment'), [])
        self.assertIn('sicilian_defense', get_valid_openings())


class RequestBodyValidationTest(TestCase):
    """Bodies that are not what the endpoint expects get a 400, not a crash."""

    def setUp(self):
        self.client.get('/play/')

    def test_non_object_json_is_rejected(self):
        for url in ('/api/new-game/', '/api/pause/', '/api/draw/'):
            for body in ('[1, 2]', '"text"', '5', '{bad json'):
                response = self.client.post(url, data=body, content_type='application/json')
                self.assertEqual(response.status_code, 400, (url, body))

    def test_optional_bodies_tolerate_non_objects(self):
        self.assertEqual(
            self.client.post('/api/resign/', data='[1]', content_type='application/json').status_code,
            200,
        )

    def test_odd_names_fall_back_to_defaults(self):
        data = post_json(self.client, '/api/new-game/', {
            'mode': 'pvp', 'white_name': 5, 'black_name': ['x'],
        }).json()
        self.assertEqual((data['white_name'], data['black_name']), ('White', 'Black'))

    def test_minutes_and_increment_string_is_clamped(self):
        data = post_json(self.client, '/api/new-game/', {'time_limit': '0|-5'}).json()
        self.assertEqual((data['time_limit'], data['increment']), (60, 0))

        data = post_json(self.client, '/api/new-game/', {'time_limit': '99999|999'}).json()
        self.assertEqual((data['time_limit'], data['increment']), (18000, 180))

        data = post_json(self.client, '/api/new-game/', {'time_limit': '5|3'}).json()
        self.assertEqual((data['time_limit'], data['increment']), (300, 3))

    def test_pause_flag_is_stored_as_a_boolean(self):
        post_json(self.client, '/api/pause/', {'pause': 'yes'})
        self.assertIs(self.client.session['game']['paused'], True)
