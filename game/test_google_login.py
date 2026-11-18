"""Tests for "Continue with Google": the redirect, the callback, the username step."""

import base64
import io
import json
import time
import urllib.error
import urllib.parse
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from game import google_auth
from game.models import GoogleAccount

CLIENT_ID = 'test-client.apps.googleusercontent.com'


def _b64(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b'=').decode()


def fake_id_token(claims):
    return f"{_b64({'alg': 'RS256'})}.{_b64(claims)}.signature"


def good_claims(nonce, **changes):
    claims = {
        'iss': 'https://accounts.google.com',
        'aud': CLIENT_ID,
        'exp': time.time() + 300,
        'nonce': nonce,
        'sub': '110000000000000000001',
        'email': 'newplayer@gmail.com',
        'email_verified': True,
    }
    claims.update(changes)
    return claims


@override_settings(GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET='test-secret')
class GoogleFlowTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def start(self, query=''):
        response = self.client.get('/auth/google/' + query)
        return response, self.client.session['google_oauth']

    def come_back(self, **claim_changes):
        """Start a sign-in and return from Google as the player in the claims."""
        _, attempt = self.start()
        token = fake_id_token(good_claims(attempt['nonce'], **claim_changes))
        with mock.patch('game.google_auth.exchange_code', return_value=token) as exchange:
            response = self.client.get(
                '/auth/google/callback/', {'state': attempt['state'], 'code': 'code-1'}
            )
        self.exchange = exchange
        return response

    def signed_in_id(self):
        return self.client.session.get('_auth_user_id')


class GoogleButtonTest(TestCase):
    def test_button_hidden_without_a_google_client(self):
        with override_settings(GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET=''):
            self.assertNotContains(self.client.get('/login/'), 'Continue with Google')

    def test_button_shown_on_login_and_register(self):
        with override_settings(GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET='s'):
            self.assertContains(self.client.get('/login/'), 'Continue with Google')
            self.assertContains(self.client.get('/register/'), 'Continue with Google')

    def test_button_keeps_the_next_page(self):
        with override_settings(GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET='s'):
            response = self.client.get('/login/?next=/play/')
        self.assertContains(response, '/auth/google/?next=/play/')

    def test_start_without_a_google_client_goes_back_to_login(self):
        with override_settings(GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET=''):
            response = self.client.get('/auth/google/')
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)


class GoogleRedirectTest(GoogleFlowTestCase):
    def test_start_sends_the_browser_to_google(self):
        response, attempt = self.start()

        self.assertEqual(response.status_code, 302)
        url = urllib.parse.urlparse(response['Location'])
        query = urllib.parse.parse_qs(url.query)
        self.assertEqual(url.netloc, 'accounts.google.com')
        self.assertEqual(query['client_id'], [CLIENT_ID])
        self.assertEqual(query['redirect_uri'], ['http://testserver/auth/google/callback/'])
        self.assertEqual(query['state'], [attempt['state']])
        self.assertEqual(query['nonce'], [attempt['nonce']])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertNotIn(attempt['verifier'], response['Location'])

    def test_wrong_state_signs_nobody_in(self):
        _, attempt = self.start()
        with mock.patch('game.google_auth.exchange_code') as exchange:
            response = self.client.get(
                '/auth/google/callback/', {'state': 'forged', 'code': 'code-1'}
            )
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        exchange.assert_not_called()
        self.assertIsNone(self.signed_in_id())

    def test_callback_without_a_started_sign_in_is_refused(self):
        with mock.patch('game.google_auth.exchange_code') as exchange:
            response = self.client.get(
                '/auth/google/callback/', {'state': 'x', 'code': 'code-1'}
            )
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        exchange.assert_not_called()

    def test_a_state_works_only_once(self):
        _, attempt = self.start()
        token = fake_id_token(good_claims(attempt['nonce']))
        with mock.patch('game.google_auth.exchange_code', return_value=token):
            params = {'state': attempt['state'], 'code': 'code-1'}
            self.client.get('/auth/google/callback/', params)
            again = self.client.get('/auth/google/callback/', params)
        self.assertRedirects(again, '/login/', fetch_redirect_response=False)

    def test_cancelled_at_google(self):
        _, attempt = self.start()
        response = self.client.get(
            '/auth/google/callback/', {'state': attempt['state'], 'error': 'access_denied'}
        )
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.assertIsNone(self.signed_in_id())

    def test_unverified_google_email_is_refused(self):
        response = self.come_back(email_verified=False)
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.assertNotIn('google_signup', self.client.session)


class NewGooglePlayerTest(GoogleFlowTestCase):
    def test_no_account_exists_until_a_username_is_chosen(self):
        response = self.come_back()

        self.assertRedirects(response, '/auth/google/username/', fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(email='newplayer@gmail.com').exists())
        self.assertFalse(GoogleAccount.objects.exists())
        self.assertIsNone(self.signed_in_id())

        page = self.client.get('/auth/google/username/')
        self.assertContains(page, 'newplayer@gmail.com')

    def test_choosing_a_username_creates_the_account(self):
        self.come_back()
        response = self.client.post('/auth/google/username/', {'username': 'knightrider'})

        self.assertRedirects(response, '/', fetch_redirect_response=False)
        user = User.objects.get(username='knightrider')
        self.assertEqual(user.email, 'newplayer@gmail.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.google_account.sub, '110000000000000000001')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(self.signed_in_id(), str(user.pk))
        self.assertNotIn('google_signup', self.client.session)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['newplayer@gmail.com'])

    def test_taken_username_is_refused_case_insensitively(self):
        User.objects.create_user('KnightRider', 'other@example.com', 'Pass12345!x')
        self.come_back()

        response = self.client.post('/auth/google/username/', {'username': 'knightrider'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'That username is taken')
        self.assertEqual(User.objects.filter(email='newplayer@gmail.com').count(), 0)
        self.assertIn('google_signup', self.client.session)

    def test_invalid_username_is_refused(self):
        self.come_back()
        response = self.client.post('/auth/google/username/', {'username': 'no spaces!'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GoogleAccount.objects.exists())

    def test_username_page_needs_a_google_sign_in(self):
        response = self.client.get('/auth/google/username/')
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)

    def test_waiting_signup_expires(self):
        self.come_back()
        session = self.client.session
        session['google_signup']['started_at'] = time.time() - 3600
        session.save()

        response = self.client.post('/auth/google/username/', {'username': 'knightrider'})

        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(username='knightrider').exists())

    def test_next_page_is_kept_through_the_username_step(self):
        _, attempt = self.start('?next=/play/')
        token = fake_id_token(good_claims(attempt['nonce']))
        with mock.patch('game.google_auth.exchange_code', return_value=token):
            self.client.get('/auth/google/callback/', {'state': attempt['state'], 'code': 'c'})
        response = self.client.post('/auth/google/username/', {'username': 'knightrider'})
        self.assertRedirects(response, '/play/', fetch_redirect_response=False)

    def test_unverified_email_signup_gives_way_to_google(self):
        squatter = User.objects.create_user(
            'squatter', 'newplayer@gmail.com', 'Pass12345!x', is_active=False,
        )
        self.come_back()
        self.client.post('/auth/google/username/', {'username': 'knightrider'})

        self.assertFalse(User.objects.filter(pk=squatter.pk).exists())
        self.assertTrue(User.objects.filter(username='knightrider').exists())

    def test_recent_unverified_signup_still_holds_its_username(self):
        User.objects.create_user('knightrider', 'someone@example.com', 'Pass12345!x', is_active=False)
        self.come_back()

        response = self.client.post('/auth/google/username/', {'username': 'knightrider'})

        self.assertContains(response, 'That username is taken')

    def test_stale_unverified_signup_lets_its_username_go(self):
        stale = User.objects.create_user(
            'knightrider', 'someone@example.com', 'Pass12345!x', is_active=False,
        )
        User.objects.filter(pk=stale.pk).update(date_joined=timezone.now() - timedelta(hours=2))
        self.come_back()

        self.client.post('/auth/google/username/', {'username': 'knightrider'})

        self.assertEqual(User.objects.get(username='knightrider').email, 'newplayer@gmail.com')


class ReturningGooglePlayerTest(GoogleFlowTestCase):
    def test_linked_account_signs_straight_in(self):
        user = User.objects.create_user('knightrider', 'old@gmail.com')
        user.set_unusable_password()
        user.save()
        GoogleAccount.objects.create(user=user, sub='110000000000000000001', email='old@gmail.com')

        # The address on the Google account changed; the link still holds.
        response = self.come_back(email='renamed@gmail.com')

        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertEqual(self.signed_in_id(), str(user.pk))

    def test_existing_account_with_the_same_email_gets_linked(self):
        user = User.objects.create_user('oldtimer', 'NewPlayer@gmail.com', 'Pass12345!x')

        response = self.come_back()

        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertEqual(self.signed_in_id(), str(user.pk))
        self.assertEqual(GoogleAccount.objects.get(user=user).sub, '110000000000000000001')
        self.assertTrue(User.objects.get(pk=user.pk).check_password('Pass12345!x'))
        self.assertEqual(User.objects.count(), 1)

    def test_deactivated_linked_account_stays_out(self):
        user = User.objects.create_user('banned', 'newplayer@gmail.com', is_active=False)
        GoogleAccount.objects.create(user=user, sub='110000000000000000001')

        response = self.come_back()

        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.assertIsNone(self.signed_in_id())

    def test_deactivated_account_with_the_same_email_stays_out(self):
        banned = User.objects.create_user('banned', 'newplayer@gmail.com', 'Pass12345!x', is_active=False)
        banned.last_login = timezone.now()
        banned.save()

        response = self.come_back()

        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.assertFalse(GoogleAccount.objects.exists())
        self.assertNotIn('google_signup', self.client.session)

    def test_account_linked_to_another_google_account_is_not_relinked(self):
        user = User.objects.create_user('oldtimer', 'newplayer@gmail.com', 'Pass12345!x')
        GoogleAccount.objects.create(user=user, sub='someone-else')

        response = self.come_back()

        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.assertEqual(GoogleAccount.objects.get(user=user).sub, 'someone-else')
        self.assertIsNone(self.signed_in_id())

    def test_failed_code_exchange_signs_nobody_in(self):
        _, attempt = self.start()
        with mock.patch(
            'game.google_auth.exchange_code',
            side_effect=google_auth.GoogleAuthError('boom'),
        ):
            response = self.client.get(
                '/auth/google/callback/', {'state': attempt['state'], 'code': 'c'}
            )
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.assertIsNone(self.signed_in_id())


@override_settings(GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET='test-secret')
class IdTokenTest(TestCase):
    def test_good_token(self):
        identity = google_auth.read_id_token(fake_id_token(good_claims('n1')), 'n1')
        self.assertEqual(identity, {'sub': '110000000000000000001', 'email': 'newplayer@gmail.com'})

    def test_bad_tokens(self):
        cases = {
            'wrong audience': good_claims('n1', aud='another-client'),
            'wrong issuer': good_claims('n1', iss='https://evil.example'),
            'expired': good_claims('n1', exp=time.time() - 5),
            'wrong nonce': good_claims('other'),
            'no subject': good_claims('n1', sub=''),
            'unverified email': good_claims('n1', email_verified=False),
        }
        for name, claims in cases.items():
            with self.subTest(name):
                with self.assertRaises(google_auth.GoogleAuthError):
                    google_auth.read_id_token(fake_id_token(claims), 'n1')

    def test_garbage_token(self):
        for token in ('', 'one-part', 'a.%%%.c', f"a.{_b64(['list'])}.c"):
            with self.subTest(token=token):
                with self.assertRaises(google_auth.GoogleAuthError):
                    google_auth.read_id_token(token, 'n1')

    def test_code_exchange_posts_the_verifier_and_secret(self):
        answer = io.BytesIO(json.dumps({'id_token': 'tok'}).encode())
        with mock.patch('game.google_auth.urllib.request.urlopen', return_value=answer) as urlopen:
            token = google_auth.exchange_code('code-1', 'https://site/cb/', 'verifier-1')

        self.assertEqual(token, 'tok')
        request = urlopen.call_args.args[0]
        sent = urllib.parse.parse_qs(request.data.decode())
        self.assertEqual(request.full_url, google_auth.TOKEN_URL)
        self.assertEqual(sent['code_verifier'], ['verifier-1'])
        self.assertEqual(sent['client_secret'], ['test-secret'])
        self.assertEqual(sent['redirect_uri'], ['https://site/cb/'])

    def test_code_exchange_errors_become_google_auth_errors(self):
        error = urllib.error.HTTPError(google_auth.TOKEN_URL, 400, 'Bad Request', {}, io.BytesIO(b'{}'))
        with mock.patch('game.google_auth.urllib.request.urlopen', side_effect=error):
            with self.assertRaises(google_auth.GoogleAuthError):
                google_auth.exchange_code('code-1', 'https://site/cb/', 'v')


class GoogleAccountDeletionTest(TestCase):
    def test_google_only_account_can_ask_for_deletion_without_a_password(self):
        user = User.objects.create_user('knightrider', 'newplayer@gmail.com')
        user.set_unusable_password()
        user.save()
        self.client.force_login(user)

        page = self.client.get('/delete-account/')
        self.assertNotContains(page, 'name="password"')

        self.client.post('/delete-account/', {'username': 'knightrider'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/confirm-delete/', mail.outbox[0].body)

    def test_wrong_username_sends_nothing(self):
        user = User.objects.create_user('knightrider', 'newplayer@gmail.com')
        user.set_unusable_password()
        user.save()
        self.client.force_login(user)

        self.client.post('/delete-account/', {'username': 'someoneelse'})
        self.assertEqual(len(mail.outbox), 0)

    def test_password_accounts_still_need_the_password(self):
        user = User.objects.create_user('oldtimer', 'old@example.com', 'Pass12345!x')
        self.client.force_login(user)

        self.client.post('/delete-account/', {'username': 'oldtimer'})
        self.assertEqual(len(mail.outbox), 0)
