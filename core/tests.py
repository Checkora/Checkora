from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
import json

class DjangoIntegrationRouteTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a test user for auth routes testing
        self.username = 'testplayer'
        self.password = 'supersecret123'
        self.email = 'player@checkora.com'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email=self.email
        )

    def test_landing_page_loads(self):
        """Verify the landing root URL returns 200 OK."""
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Checkora")

    def test_rules_page_loads(self):
        """Verify the game rules instructions page returns 200 OK."""
        response = self.client.get(reverse('rules'))
        self.assertEqual(response.status_code, 200)

    def test_stats_page_redirects_unauthenticated(self):
        """Verify that accessing the stats page unauthenticated redirects to login."""
        response = self.client.get(reverse('stats'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_stats_page_loads_for_authenticated_user(self):
        """Verify that authenticated users can view the stats page successfully."""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('stats'))
        self.assertEqual(response.status_code, 200)

    def test_login_page_renders(self):
        """Verify the authentication login page renders correctly."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_register_page_renders(self):
        """Verify the registration form is accessible."""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_api_new_game_expects_post(self):
        """Ensure GET requests to API create game endpoints return bad request/method not allowed."""
        response = self.client.get(reverse('new_game'))
        self.assertIn(response.status_code, [400, 405])
