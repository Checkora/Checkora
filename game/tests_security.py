"""
Security tests for the Checkora project.
Focuses on verifying Host Header protection and other core security settings.
"""

from django.test import TestCase, Client, override_settings
from django.core import mail
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

class SecurityHostHeaderTest(TestCase):
    """
    Validates that the application is protected against Host Header Poisoning.
    Host Header Poisoning can occur when absolute URLs (like password reset links)
    are generated using an unvalidated HTTP Host header.
    """

    def setUp(self):
        """Set up a test user for auth-related security flows."""
        self.user = User.objects.create_user(
            username='security_test_user',
            email='security@example.com',
            password='password123'
        )
        self.client = Client()

    def test_settings_does_not_contain_global_wildcard(self):
        """
        Ensures that ALLOWED_HOSTS does not contain the global '*' wildcard.
        """
        self.assertNotIn(
            '*', 
            settings.ALLOWED_HOSTS, 
            "CRITICAL: ALLOWED_HOSTS contains a wildcard '*'. This is insecure for production."
        )

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=['checkora.vercel.app', 'localhost', '127.0.0.1', 'testserver'],
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        VERCEL_ENV=None
    )
    def test_malicious_host_header_returns_400(self):
        """
        Verifies that an unknown Host header results in a 400 Bad Request
        when DEBUG is False, preventing any further processing.
        """
        malicious_host = 'attacker-domain.com'
        reset_url = reverse('password_reset')

        response = self.client.post(
            reset_url, 
            {'email': self.user.email}, 
            HTTP_HOST=malicious_host,
            secure=True
        )

        self.assertEqual(response.status_code, 400, "Should reject unknown Host header with 400 status")
        self.assertEqual(len(mail.outbox), 0, "No email should be sent for a rejected host")

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=['checkora.vercel.app', 'testserver'],
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        VERCEL_ENV=None
    )
    def test_trusted_host_generates_safe_links(self):
        """
        Verifies that when a trusted host is used, the generated links are correct
        and matches the provided Host header (if it's in the allowlist).
        """
        trusted_host = 'checkora.vercel.app'
        reset_url = reverse('password_reset')

        response = self.client.post(
            reset_url, 
            {'email': self.user.email}, 
            HTTP_HOST=trusted_host,
            secure=True
        )

        self.assertEqual(response.status_code, 302, "Should accept request from trusted host")
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        
        self.assertIn(f'://{trusted_host}', email_body)
        self.assertNotIn('attacker-domain.com', email_body)

    def test_production_config_no_broad_wildcards(self):
        """
        Ensures that broad wildcard patterns (like .vercel.app) are not 
        accidentally active in the default test/production configuration.
        """
        if getattr(settings, 'VERCEL_ENV', None) != 'preview':
            self.assertNotIn(
                '.vercel.app', 
                settings.ALLOWED_HOSTS,
                "The broad '.vercel.app' wildcard should not be active in non-preview environments."
            )
