from unittest import mock

from django.urls import reverse
from django.test import TestCase
from django.contrib.auth.models import User

from game.models import GameResult
from game.engine import ChessGame


class AuthenticationEndpointsTest(TestCase):
    """Tests for authentication related views."""

    def setUp(self):
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )

    def test_register_get(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/register.html')

    def test_register_authenticated_redirect(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('index'))

    def test_register_post_invalid(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'email': 'invalidemail'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'username',
            'A user with that username already exists.'
        )

    @mock.patch('game.views.send_mail')
    @mock.patch('game.views.CustomUserCreationForm')
    def test_register_post_valid(self, mock_form_class, mock_send_mail):
        mock_instance = mock_form_class.return_value
        mock_instance.is_valid.return_value = True

        mock_user = mock.MagicMock()
        mock_user.id = 999
        mock_user.email = 'new@example.com'
        mock_instance.save.return_value = mock_user

        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com'
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('verify_otp'))
        self.assertFalse(mock_user.is_active)
        mock_user.save.assert_called()
        mock_send_mail.assert_called_once()
        self.assertIn('registration_user_id', self.client.session)
        user_id = self.client.session['registration_user_id']
        self.assertEqual(user_id, mock_user.id)

    @mock.patch('game.views.send_mail', side_effect=Exception('SMTP err'))
    @mock.patch('game.views.CustomUserCreationForm')
    def test_register_post_email_failure(self, mock_form_class, _mock_mail):
        mock_instance = mock_form_class.return_value
        mock_instance.is_valid.return_value = True

        mock_user = mock.MagicMock()
        mock_user.id = 999
        mock_user.email = 'new@example.com'
        mock_instance.save.return_value = mock_user

        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com'
        })

        self.assertEqual(response.status_code, 200)
        mock_user.delete.assert_called_once()

        msgs = list(response.context['messages'])
        self.assertTrue(
            any('Failed to send OTP email' in str(m) for m in msgs)
        )

    @mock.patch('game.views.secrets.randbelow', return_value=23456)
    @mock.patch('game.views.CustomUserCreationForm')
    @mock.patch('game.views.send_mail')
    def setup_registration_session(self, _mock_mail, mock_form, _mock_rand):
        mock_instance = mock_form.return_value
        mock_instance.is_valid.return_value = True

        self.test_user.is_active = False
        self.test_user.save()
        mock_instance.save.return_value = self.test_user

        self.client.post(reverse('register'), {
            'username': 'testuser',
            'email': 'test@example.com'
        })

        return '123456'

    def test_verify_otp_get(self):
        response = self.client.get(reverse('verify_otp'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('register'))

        self.setup_registration_session()

        response = self.client.get(reverse('verify_otp'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/verify_otp.html')

    def test_verify_otp_authenticated_redirect(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('verify_otp'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('index'))

    def test_verify_otp_post_valid(self):
        otp = self.setup_registration_session()

        response = self.client.post(reverse('verify_otp'), {'otp': otp})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('index'))

        self.test_user.refresh_from_db()
        self.assertTrue(self.test_user.is_active)
        self.assertNotIn('registration_user_id', self.client.session)

    def test_verify_otp_post_invalid(self):
        self.setup_registration_session()

        response = self.client.post(reverse('verify_otp'), {'otp': 'wrong'})
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any('Invalid OTP' in str(m) for m in messages))

    def test_verify_otp_user_does_not_exist(self):
        otp = self.setup_registration_session()
        self.test_user.delete()

        response = self.client.post(reverse('verify_otp'), {'otp': otp})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('register'))

    def test_login_get(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/login.html')

    def test_login_authenticated_redirect(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('index'))

    def test_login_post_valid(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('index'))
        user_id = int(self.client.session['_auth_user_id'])
        self.assertEqual(user_id, self.test_user.pk)

    def test_login_post_invalid(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], None,
            'Please enter a correct username and password. '
            'Note that both fields may be case-sensitive.'
        )

    def test_logout(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('landing'))
        self.assertNotIn('_auth_user_id', self.client.session)


class AdditionalGameEndpointsTest(TestCase):
    """Tests for game-related views like resign and stats."""

    def test_resign_game_no_active_game(self):
        response = self.client.post(reverse('resign_game'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['valid'], False)
        self.assertEqual(response.json()['message'], 'No active game.')

    def test_resign_game_white_resigns(self):
        game = ChessGame()
        game.mode = 'pvp'
        game.current_turn = 'white'

        self.client.get(reverse('index'))
        session = self.client.session
        session['game'] = game.to_dict()
        session.save()

        response = self.client.post(reverse('resign_game'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['valid'], True)
        self.assertEqual(data['winner'], 'black')
        self.assertEqual(data['game_status'], 'resignation')

        result = GameResult.objects.first()
        self.assertIsNotNone(result)
        self.assertEqual(result.winner, 'black')
        self.assertEqual(result.end_reason, 'resign')
        self.assertEqual(result.mode, 'pvp')

    @mock.patch('game.views.ChessGame.from_dict')
    def test_resign_game_black_resigns(self, mock_from_dict):
        game = ChessGame()
        game.mode = 'pvp'
        game.current_turn = 'black'
        mock_from_dict.return_value = game

        self.client.get(reverse('index'))

        response = self.client.post(reverse('resign_game'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['valid'], True)
        self.assertEqual(data['winner'], 'white')

        result = GameResult.objects.last()
        self.assertEqual(result.winner, 'white')

    def test_stats_view(self):
        GameResult.objects.create(
            mode='ai', winner='white', end_reason='checkmate'
        )
        GameResult.objects.create(
            mode='pvp', winner='black', end_reason='resign'
        )

        response = self.client.get(reverse('stats'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/stats.html')
        self.assertEqual(response.context['ai_total'], 1)
        self.assertEqual(response.context['ai_wins'], 1)
        self.assertEqual(response.context['ai_draws'], 0)
        self.assertEqual(len(response.context['recent']), 2)
