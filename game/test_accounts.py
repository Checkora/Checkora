"""Tests for the account pages, profile pictures, ranks, points and streaks."""

import hashlib
import io
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from game import accounts, progression
from game.models import (
    ChessPuzzle,
    GoogleAccount,
    PlayerRating,
    PuzzleStats,
    RatingHistory,
    UserProfile,
    UserProgress,
)
from game.services import daily_puzzle_day, process_game_completion

PLAYED = ['e2e4', 'e7e5'] * (progression.STREAK_MIN_HALF_MOVES // 2)


def png_upload(name='me.png', size=(300, 200)):
    buffer = io.BytesIO()
    Image.new('RGBA', size, (200, 150, 50, 255)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class SignedInTestCase(TestCase):
    password = 'Pass12345!x'

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('player', 'player@example.com', self.password)
        self.client.force_login(self.user)


# ---------------------------------------------------------------------------
# Profile pictures
# ---------------------------------------------------------------------------

class AvatarTest(SignedInTestCase):
    def test_picking_a_preset(self):
        response = self.client.post(reverse('select_avatar_preset'), {'preset': 'bn'})

        self.assertRedirects(response, reverse('upload_avatar'), fetch_redirect_response=False)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.avatar_preset, 'bn')
        self.assertTrue(profile.avatar_url.endswith('pieces/staunton-single/bn.webp'))

    def test_unknown_preset_is_refused(self):
        self.client.post(reverse('select_avatar_preset'), {'preset': 'zz'})
        self.assertEqual(UserProfile.objects.get(user=self.user).avatar_preset, '')

    def test_upload_replaces_a_preset_and_is_served_by_url(self):
        self.client.post(reverse('select_avatar_preset'), {'preset': 'wq'})
        self.client.post(reverse('upload_avatar'), {'avatar': png_upload()})

        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.avatar_preset, '')
        self.assertTrue(profile.avatar.startswith('data:image/png;base64,'))
        self.assertTrue(profile.avatar_url.startswith(f'/u/{self.user.pk}/avatar/?v='))

        self.client.logout()  # pictures are public, like the leaderboard
        response = self.client.get(profile.avatar_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('immutable', response['Cache-Control'])
        image = Image.open(io.BytesIO(response.content))
        self.assertLessEqual(max(image.size), 256)

    def test_a_new_upload_gets_a_new_url(self):
        self.client.post(reverse('upload_avatar'), {'avatar': png_upload()})
        first = UserProfile.objects.get(user=self.user).avatar_url
        later = timezone.now() + timedelta(seconds=5)
        with mock.patch('game.models.timezone.now', return_value=later):
            self.client.post(reverse('upload_avatar'), {'avatar': png_upload(size=(80, 80))})
        self.assertNotEqual(UserProfile.objects.get(user=self.user).avatar_url, first)

    def test_no_upload_means_404(self):
        self.assertEqual(self.client.get(reverse('user_avatar', args=[self.user.pk])).status_code, 404)
        self.client.post(reverse('select_avatar_preset'), {'preset': 'wk'})
        self.assertEqual(self.client.get(reverse('user_avatar', args=[self.user.pk])).status_code, 404)

    def test_a_file_that_is_not_a_picture_is_refused(self):
        bad = SimpleUploadedFile('x.png', b'not a picture at all', content_type='image/png')
        self.client.post(reverse('upload_avatar'), {'avatar': bad})
        self.assertEqual(UserProfile.objects.get(user=self.user).avatar, '')

    def test_remove_clears_both_kinds(self):
        self.client.post(reverse('select_avatar_preset'), {'preset': 'wk'})
        self.client.post(reverse('remove_avatar'))
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual((profile.avatar, profile.avatar_preset, profile.avatar_url), ('', '', ''))

    def test_pages_never_inline_the_picture_data(self):
        self.client.post(reverse('upload_avatar'), {'avatar': png_upload()})
        for name in ('profile', 'stats', 'account_settings', 'upload_avatar'):
            with self.subTest(page=name):
                self.assertNotContains(self.client.get(reverse(name)), 'data:image/png;base64')


# ---------------------------------------------------------------------------
# Rating, rank, points
# ---------------------------------------------------------------------------

class EloTest(TestCase):
    def test_equal_ratings_split_the_points(self):
        self.assertAlmostEqual(progression.expected_score(1200, 1200), 0.5)
        self.assertEqual(progression.rating_change(1200, 1200, 'win', 0), 16)
        self.assertEqual(progression.rating_change(1200, 1200, 'loss', 0), -16)
        self.assertEqual(progression.rating_change(1200, 1200, 'draw', 0), 0)

    def test_beating_a_weak_engine_is_worth_little(self):
        easy = progression.engine_rating('easy')
        hard = progression.engine_rating('hard')
        self.assertLess(progression.rating_change(1500, easy, 'win', 30), 3)
        self.assertGreater(progression.rating_change(1500, hard, 'win', 30), 8)
        self.assertLess(progression.rating_change(1500, easy, 'loss', 30), -12)

    def test_established_ratings_move_more_slowly(self):
        early = progression.rating_change(1200, 1200, 'win', 0)
        later = progression.rating_change(1200, 1200, 'win', progression.PROVISIONAL_GAMES)
        self.assertEqual(early, 2 * later)

    def test_unknown_result_is_an_error(self):
        with self.assertRaises(ValueError):
            progression.rating_change(1200, 1200, 'abandoned', 0)

    def test_rank_bands(self):
        self.assertEqual(progression.rank_for(0).name, 'Pawn')
        self.assertEqual(progression.rank_for(799).name, 'Pawn')
        self.assertEqual(progression.rank_for(800).name, 'Knight')
        self.assertEqual(progression.rank_for(1200).name, 'Bishop')
        king = progression.rank_for(2600)
        self.assertEqual((king.name, king.next_at), ('King', None))
        self.assertEqual(progression.rank_for(1450).next_at, 1700)

    def test_level_progress(self):
        self.assertEqual(progression.level_progress(0), (1, 0, 100))
        self.assertEqual(progression.level_progress(130), (2, 30, 150))
        top = max(progression.LEVEL_THRESHOLDS.values())
        self.assertEqual(progression.level_progress(top + 10)[2], None)


class GameRewardsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('player', 'player@example.com', 'x')

    def test_a_rated_win_moves_rating_by_difficulty_and_awards_points(self):
        result = process_game_completion(
            self.user, 'ai', 'white', 'checkmate', 'white', moves=PLAYED, difficulty='hard',
        )
        rating = PlayerRating.objects.get(user=self.user)
        expected = progression.START_RATING + progression.rating_change(1200, 1600, 'win', 0)
        self.assertEqual(rating.rating, expected)
        self.assertEqual(RatingHistory.objects.get(user=self.user).game_result, result)
        self.assertEqual(UserProgress.objects.get(user=self.user).xp, progression.XP_FOR_RESULT['win'])

    def test_a_short_game_moves_the_rating_but_earns_no_points_or_streak(self):
        process_game_completion(self.user, 'ai', 'black', 'resign', 'white', moves=['e2e4'])
        self.assertEqual(PlayerRating.objects.get(user=self.user).games_played, 1)
        self.assertFalse(UserProgress.objects.filter(user=self.user, xp__gt=0).exists())
        self.assertFalse(UserProgress.objects.filter(user=self.user, day_streak__gt=0).exists())

    def test_cleanup_resignations_never_count_as_playing(self):
        process_game_completion(
            self.user, 'ai', 'black', 'resign', 'white', moves=PLAYED, counts_for_streak=False,
        )
        self.assertFalse(UserProgress.objects.filter(user=self.user, day_streak__gt=0).exists())

    def test_two_player_games_count_towards_play_achievements(self):
        from game.models import Achievement, UserAchievement
        Achievement.objects.get_or_create(code='PLAY_10', defaults={
            'title': 'Ten', 'description': '', 'icon': '', 'category': 'gameplay', 'rarity': 'common',
        })
        for _ in range(10):
            process_game_completion(self.user, 'pvp', 'white', 'checkmate', 'white', moves=PLAYED)
        self.assertTrue(UserAchievement.objects.filter(user=self.user, achievement__code='PLAY_10').exists())


class StreakTimezoneTest(SignedInTestCase):
    def test_middleware_stores_the_browser_zone_once(self):
        self.client.cookies['tz'] = 'Asia/Kolkata'
        self.client.get(reverse('profile'))
        self.assertEqual(UserProfile.objects.get(user=self.user).timezone, 'Asia/Kolkata')

        UserProfile.objects.filter(user=self.user).update(timezone='')
        self.client.get(reverse('profile'))
        # The session remembers it was written; no write on every request.
        self.assertEqual(UserProfile.objects.get(user=self.user).timezone, '')

    def test_a_made_up_zone_is_ignored(self):
        self.client.cookies['tz'] = 'Mars/Olympus_Mons'
        self.client.get(reverse('profile'))
        self.assertEqual(UserProfile.objects.get(user=self.user).timezone, '')

    def test_streak_day_follows_the_players_zone(self):
        UserProfile.objects.filter(user=self.user).update(timezone='Asia/Kolkata')
        # 20:00 UTC is already the next day in India.
        moment = datetime(2026, 11, 17, 20, 0, tzinfo=dt_timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=moment):
            self.assertEqual(progression.player_today(self.user).isoformat(), '2026-11-18')


# ---------------------------------------------------------------------------
# Puzzles
# ---------------------------------------------------------------------------

class PuzzleRewardsTest(SignedInTestCase):
    def setUp(self):
        super().setUp()
        self.puzzle = ChessPuzzle.objects.create(
            title='Back rank', fen='6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1',
            solution=['e1e8'], difficulty='easy', date=timezone.localdate(),
        )

    def solve(self):
        return self.client.post(
            reverse('puzzle_solve_api', args=[self.puzzle.pk]),
            data={'moves': ['e1e8']}, content_type='application/json',
        ).json()

    def test_daily_puzzle_solve_awards_points(self):
        data = self.solve()
        self.assertTrue(data['counted'])
        self.assertEqual(data['streak'], 1)
        self.assertEqual(
            UserProgress.objects.get(user=self.user).xp,
            progression.XP_PUZZLE + progression.XP_DAILY_PUZZLE,
        )

    def test_looking_at_the_solution_forfeits_the_credit(self):
        self.client.get(reverse('puzzle_solution_api', args=[self.puzzle.pk]))
        data = self.solve()
        self.assertTrue(data['correct'])
        self.assertFalse(data['counted'])
        self.assertEqual(data['puzzles_solved'], 0)

    @override_settings(PUZZLE_SOLVE_MAX_REQUESTS=3)
    def test_answers_are_rate_limited(self):
        url = reverse('puzzle_solve_api', args=[self.puzzle.pk])
        codes = [
            self.client.post(url, data={'moves': ['a1a2']}, content_type='application/json').status_code
            for _ in range(4)
        ]
        self.assertEqual(codes[-1], 429)

    def test_yesterdays_daily_counts_just_after_midnight(self):
        yesterday_puzzle = ChessPuzzle.objects.create(
            title='Old', fen=self.puzzle.fen, solution=['e1e8'],
            date=timezone.localdate() - timedelta(days=1),
        )
        just_after = timezone.localtime().replace(hour=0, minute=5, second=0, microsecond=0)
        self.assertEqual(daily_puzzle_day(yesterday_puzzle, now=just_after), just_after.date() - timedelta(days=1))
        an_hour_later = just_after + timedelta(hours=1)
        self.assertIsNone(daily_puzzle_day(yesterday_puzzle, now=an_hour_later))


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

class LeaderboardTest(SignedInTestCase):
    def rate(self, name, rating, games=5):
        user = User.objects.create_user(name, f'{name}@example.com', 'x')
        PlayerRating.objects.create(user=user, rating=rating, games_played=games, wins=games)
        return user

    def test_only_players_who_played_are_listed(self):
        self.rate('ghost', 1200, games=0)
        self.rate('real', 900)
        rows = self.client.get(reverse('leaderboard')).context['chess_leaderboard']
        self.assertEqual([row.user.username for row in rows], ['real'])

    def test_reading_pages_creates_no_rows(self):
        for name in ('stats', 'leaderboard', 'profile'):
            self.client.get(reverse(name))
        self.client.get(reverse('puzzle_stats'))
        self.assertFalse(PlayerRating.objects.filter(user=self.user).exists())
        self.assertFalse(PuzzleStats.objects.filter(user=self.user).exists())

    def test_level_players_share_a_place(self):
        self.rate('a', 1500)
        self.rate('b', 1500)
        self.rate('c', 1400)
        rows = self.client.get(reverse('leaderboard')).context['chess_leaderboard']
        self.assertEqual([row.position for row in rows], [1, 1, 3])

    def test_own_row_appears_below_the_top_rows(self):
        for index in range(3):
            self.rate(f'top{index}', 2000 + index)
        PlayerRating.objects.create(user=self.user, rating=1000, games_played=2, wins=2)
        with mock.patch('game.views.LEADERBOARD_SIZE', 2):
            context = self.client.get(reverse('leaderboard')).context
        self.assertEqual(len(context['chess_leaderboard']), 2)
        self.assertEqual(context['my_chess_row'].position, 4)

    def test_query_count_does_not_grow_with_the_table(self):
        for index in range(20):
            user = self.rate(f'p{index}', 1000 + index)
            UserProfile.objects.filter(user=user).update(avatar_preset='wk')
        with CaptureQueriesContext(connection) as queries:
            self.client.get(reverse('leaderboard'))
        self.assertLess(len(queries), 25)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class UsernameChangeTest(SignedInTestCase):
    def test_rename(self):
        response = self.client.post(reverse('change_username'), {'username': 'newname'})
        self.assertRedirects(response, reverse('account_settings'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'newname')

    def test_taken_name_is_refused(self):
        User.objects.create_user('Taken', 't@example.com', 'x')
        response = self.client.post(reverse('change_username'), {'username': 'taken'})
        self.assertContains(response, 'That username is taken', status_code=400)

    def test_once_a_month(self):
        self.client.post(reverse('change_username'), {'username': 'first'})
        response = self.client.post(reverse('change_username'), {'username': 'second'})
        self.assertContains(response, 'You can change your username again', status_code=400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'first')

    def test_changing_only_the_case_is_free(self):
        self.client.post(reverse('change_username'), {'username': 'Player'})
        self.client.post(reverse('change_username'), {'username': 'other'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'other')


class EmailChangeTest(SignedInTestCase):
    def ask(self, email='new@example.com', code=123456):
        with mock.patch('game.views_account.secrets.randbelow', return_value=code):
            return self.client.post(reverse('change_email'), {'email': email})

    def test_code_then_switch(self):
        self.ask()
        self.assertEqual(mail.outbox[-1].to, ['new@example.com'])
        self.assertIn('123456', mail.outbox[-1].body)

        response = self.client.post(reverse('verify_email_change'), {'code': '123456'})

        self.assertRedirects(response, reverse('account_settings'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.com')
        # The old address hears about it.
        self.assertEqual(mail.outbox[-1].to, ['player@example.com'])

    def test_wrong_codes_run_out(self):
        self.ask()
        for _ in range(5):
            self.client.post(reverse('verify_email_change'), {'code': '000000'})
        self.client.post(reverse('verify_email_change'), {'code': '123456'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'player@example.com')

    def test_someone_elses_address_gets_no_mail_and_no_switch(self):
        User.objects.create_user('owner', 'taken@example.com', 'x')
        response = self.ask('taken@example.com')
        self.assertRedirects(response, reverse('verify_email_change'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)
        self.client.post(reverse('verify_email_change'), {'code': '123456'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'player@example.com')

    def test_codes_expire(self):
        self.ask()
        session = self.client.session
        session['email_change']['sent_at'] = time.time() - 3600
        session.save()
        self.client.post(reverse('verify_email_change'), {'code': '123456'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'player@example.com')


class PasswordAndGoogleTest(SignedInTestCase):
    def test_change_password_keeps_the_session(self):
        response = self.client.post(reverse('change_password'), {
            'old_password': self.password,
            'new_password1': 'Another-Pass-987',
            'new_password2': 'Another-Pass-987',
        })
        self.assertRedirects(response, reverse('account_settings'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Another-Pass-987'))
        self.assertEqual(self.client.get(reverse('account_settings')).status_code, 200)

    def test_google_only_account_can_set_a_password(self):
        self.user.set_unusable_password()
        self.user.save()
        self.client.force_login(self.user)
        self.client.post(reverse('change_password'), {
            'new_password1': 'Another-Pass-987',
            'new_password2': 'Another-Pass-987',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Another-Pass-987'))

    def test_unlink_needs_a_password(self):
        GoogleAccount.objects.create(user=self.user, sub='g-1')
        self.user.set_unusable_password()
        self.user.save()
        self.client.force_login(self.user)
        self.client.post(reverse('unlink_google'))
        self.assertTrue(GoogleAccount.objects.filter(user=self.user).exists())

    def test_unlink(self):
        GoogleAccount.objects.create(user=self.user, sub='g-1')
        self.client.post(reverse('unlink_google'))
        self.assertFalse(GoogleAccount.objects.filter(user=self.user).exists())


@override_settings(GOOGLE_CLIENT_ID='client', GOOGLE_CLIENT_SECRET='secret')
class LinkGoogleFromSettingsTest(SignedInTestCase):
    def come_back(self, sub='g-7'):
        from game.test_google_login import fake_id_token, good_claims

        self.client.get(reverse('google_login') + '?link=1')
        attempt = self.client.session['google_oauth']
        claims = good_claims(attempt['nonce'], aud='client', sub=sub, email='me@gmail.com')
        with mock.patch('game.google_auth.exchange_code', return_value=fake_id_token(claims)):
            return self.client.get(reverse('google_callback'), {'state': attempt['state'], 'code': 'c'})

    def test_linking_from_settings(self):
        response = self.come_back()
        self.assertRedirects(response, reverse('account_settings'), fetch_redirect_response=False)
        self.assertEqual(GoogleAccount.objects.get(user=self.user).sub, 'g-7')

    def test_a_google_account_linked_elsewhere_is_refused(self):
        other = User.objects.create_user('other', 'o@example.com', 'x')
        GoogleAccount.objects.create(user=other, sub='g-7')
        self.come_back()
        self.assertFalse(GoogleAccount.objects.filter(user=self.user).exists())

    def test_signing_out_midway_cancels_the_link(self):
        self.client.get(reverse('google_login') + '?link=1')
        attempt = self.client.session['google_oauth']
        session_data = dict(self.client.session)
        self.client.logout()
        session = self.client.session
        session['google_oauth'] = session_data['google_oauth']
        session.save()
        self.client.get(reverse('google_callback'), {'state': attempt['state'], 'code': 'c'})
        self.assertFalse(GoogleAccount.objects.exists())


class AccountServiceTest(TestCase):
    def test_stale_unverified_signup_releases_its_name(self):
        stale = User.objects.create_user('holder', 'h@example.com', 'x', is_active=False)
        User.objects.filter(pk=stale.pk).update(date_joined=timezone.now() - timedelta(hours=2))
        self.assertFalse(accounts.username_taken('holder'))

    def test_code_hash_is_salted_with_the_secret_key(self):
        from game.views_account import _code_hash
        self.assertEqual(_code_hash('1'), hashlib.sha256(f'1:{settings.SECRET_KEY}'.encode()).hexdigest())
