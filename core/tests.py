from django.test import TestCase

class BasicHealthCheckTest(TestCase):
    def test_environment_is_configured(self):
        """
        A basic test to ensure the Django testing environment is configured correctly.
        """
        self.assertEqual(1 + 1, 2)
